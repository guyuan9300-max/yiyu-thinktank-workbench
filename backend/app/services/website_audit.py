"""官方网站客观评测 (P13-E).

跑 Google Lighthouse → 拿四维分数 (Performance / Accessibility / Best Practices / SEO),
再扫 brand_official_corpus 已抓 markdown 里的 PDF/DOC 链接 → 给"文档可下载性"客观数字.
结果落 website_audit_snapshots, 同 client_id 历史可对比.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIGHTHOUSE_RUNNER_REL = "backend/runtime/lighthouse/run_audit.mjs"
LIGHTHOUSE_TIMEOUT_SECONDS = 240
DOC_EXT_RE = re.compile(r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx)(?:\?[^\s)\"']*)?$", re.IGNORECASE)
PROJECT_ROOT_ENV = "YIYU_PROJECT_ROOT"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _new_id() -> str:
    return "wha_" + secrets.token_hex(5)


def _resolve_project_root() -> Path:
    env = os.environ.get(PROJECT_ROOT_ENV)
    if env:
        candidate = Path(env)
        if (candidate / LIGHTHOUSE_RUNNER_REL).exists():
            return candidate
    # backend/app/services/website_audit.py → repo root 4 levels up
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / LIGHTHOUSE_RUNNER_REL).exists():
            return parent
    return here.parents[3]


@dataclass(frozen=True)
class WebsiteAuditResult:
    snapshot_id: str
    target_url: str
    final_url: str
    scores: dict[str, int | None]
    mobile_friendly: bool
    requests: int
    transfer_kb: int
    downloadable_docs: list[dict[str, str]]
    fetched_at: str
    error: str | None


def _scan_downloadable_docs_from_corpus(
    conn: sqlite3.Connection, client_id: str
) -> list[dict[str, str]]:
    """从 brand_official_corpus 已抓 markdown 里扫所有 PDF/DOC/XLS 链接.

    Lighthouse 一次只测一个页面 (首页), 但日慈的"年报/审计报告/工作报告"是子页才有 PDF.
    所以可下载文档数要走整站语料库扫描, 不是 lighthouse single-page network requests.
    """
    cur = conn.execute(
        """
        SELECT v.markdown_content
        FROM v2_documents v
        WHERE v.client_id = ? AND v.content_domain = 'brand_official_corpus'
        """,
        (client_id,),
    )
    seen: set[str] = set()
    docs: list[dict[str, str]] = []
    url_pattern = re.compile(r"https?://[^\s)\"'<>]+", re.IGNORECASE)
    for row in cur.fetchall():
        markdown = row[0] or ""
        for match in url_pattern.finditer(markdown):
            link = match.group(0).rstrip(".,;:!?)")
            ext_match = DOC_EXT_RE.search(link)
            if not ext_match:
                continue
            if link in seen:
                continue
            seen.add(link)
            docs.append({"url": link, "type": ext_match.group(1).lower()})
    return docs


def _run_lighthouse(target_url: str) -> dict[str, Any]:
    project_root = _resolve_project_root()
    runner = project_root / LIGHTHOUSE_RUNNER_REL
    if not runner.exists():
        raise FileNotFoundError(f"lighthouse runner not found at {runner}")
    node_bin = shutil.which("node")
    if not node_bin:
        raise RuntimeError("node executable not found in PATH; install Node.js to run website audit")
    cmd = [node_bin, str(runner), target_url, "--max-wait=120000"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=LIGHTHOUSE_TIMEOUT_SECONDS,
        cwd=str(runner.parent),
    )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        raise RuntimeError(
            f"lighthouse produced no stdout (exit={proc.returncode}); stderr={proc.stderr[:400]}"
        )
    # runner only writes a single JSON line, but tolerate trailing log lines just in case.
    last_line = stdout.splitlines()[-1].strip()
    try:
        return json.loads(last_line)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"lighthouse stdout not JSON ({error}); first 400 chars: {stdout[:400]}"
        )


def run_website_audit(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    target_url: str,
) -> WebsiteAuditResult:
    """同步跑一次网站评测 → 入库 → 返回快照.

    被 endpoint 调用 (15-60 秒同步等待). 后续如要异步可走 knowledge_jobs.
    """
    target_url = target_url.strip()
    if not target_url:
        raise ValueError("target_url is required")
    fetched_at = _now_iso()
    snapshot_id = _new_id()
    error: str | None = None
    payload: dict[str, Any] = {}
    try:
        payload = _run_lighthouse(target_url)
        if payload.get("error"):
            error = str(payload["error"])
    except Exception as exc:  # noqa: BLE001 — lighthouse failures captured into snapshot
        error = f"lighthouse_failed: {str(exc)[:400]}"

    scores = payload.get("scores") or {}
    stats = payload.get("stats") or {}
    final_url = str(stats.get("finalUrl") or target_url)
    # 从已爬语料库扫 PDF/DOC, 比 lighthouse 单页 network requests 准确.
    corpus_docs = _scan_downloadable_docs_from_corpus(conn, client_id)
    # 合并 lighthouse 报告里 first-party 页面里直接出现的下载链接 (一般是空, 但兜底).
    for entry in payload.get("downloadableDocs") or []:
        url = str(entry.get("url") or "")
        if url and not any(d["url"] == url for d in corpus_docs):
            corpus_docs.append({"url": url, "type": str(entry.get("type") or "unknown")})

    result = WebsiteAuditResult(
        snapshot_id=snapshot_id,
        target_url=target_url,
        final_url=final_url,
        scores={
            "performance": scores.get("performance"),
            "accessibility": scores.get("accessibility"),
            "bestPractices": scores.get("bestPractices"),
            "seo": scores.get("seo"),
        },
        mobile_friendly=bool(payload.get("mobileFriendly")),
        requests=int(stats.get("requests") or 0),
        transfer_kb=int(stats.get("transferKb") or 0),
        downloadable_docs=corpus_docs,
        fetched_at=str(payload.get("fetchedAt") or fetched_at),
        error=error,
    )

    conn.execute(
        """
        INSERT INTO website_audit_snapshots (
            id, client_id, target_url, final_url,
            performance, accessibility, best_practices, seo,
            mobile_friendly, requests, transfer_kb,
            downloadable_docs_count, downloadable_docs_json, raw_json, error,
            fetched_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.snapshot_id,
            client_id,
            result.target_url,
            result.final_url,
            result.scores.get("performance"),
            result.scores.get("accessibility"),
            result.scores.get("bestPractices"),
            result.scores.get("seo"),
            1 if result.mobile_friendly else 0,
            result.requests,
            result.transfer_kb,
            len(result.downloadable_docs),
            json.dumps(result.downloadable_docs, ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
            result.error,
            result.fetched_at,
            fetched_at,
        ),
    )
    conn.commit()
    return result


def latest_website_audit(
    conn: sqlite3.Connection, *, client_id: str
) -> dict[str, Any] | None:
    cur = conn.execute(
        """
        SELECT id, target_url, final_url, performance, accessibility, best_practices, seo,
               mobile_friendly, requests, transfer_kb,
               downloadable_docs_count, downloadable_docs_json, error,
               fetched_at, created_at
        FROM website_audit_snapshots
        WHERE client_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (client_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    try:
        docs = json.loads(row[11] or "[]")
    except json.JSONDecodeError:
        docs = []
    return {
        "id": row[0],
        "targetUrl": row[1],
        "finalUrl": row[2],
        "scores": {
            "performance": row[3],
            "accessibility": row[4],
            "bestPractices": row[5],
            "seo": row[6],
        },
        "mobileFriendly": bool(row[7]),
        "requests": row[8],
        "transferKb": row[9],
        "downloadableDocsCount": row[10],
        "downloadableDocs": docs,
        "error": row[12],
        "fetchedAt": row[13],
        "createdAt": row[14],
    }
