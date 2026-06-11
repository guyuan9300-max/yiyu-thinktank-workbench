from __future__ import annotations

import hashlib
import hmac
import html
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


DEFAULT_DB_PATH = "/var/lib/yiyu-oauth-relay/relay.sqlite3"


class RelaySessionCreatePayload(BaseModel):
    stateHash: str = Field(min_length=32, max_length=128)
    claimSecretHash: str = Field(min_length=32, max_length=128)
    expiresAt: str = Field(min_length=1)


class RelayCodeClaimPayload(BaseModel):
    state: str = Field(min_length=16)
    claimSecret: str = Field(min_length=16)


class RelaySessionRecord(BaseModel):
    status: Literal["registered", "pending", "authorized", "expired", "error"]
    expiresAt: str | None = None
    receivedAt: str | None = None
    errorMessage: str | None = None


class RelayCodeClaimResult(BaseModel):
    status: Literal["pending", "authorized", "expired", "error"]
    code: str | None = None
    receivedAt: str | None = None
    errorMessage: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_hash(value: str) -> str:
    return value.strip().lower()


def _safe_error(value: str | None) -> str:
    return str(value or "").strip()[:240]


def _render_callback_page(title: str, detail: str, *, success: bool) -> HTMLResponse:
    tone = "#16a34a" if success else "#dc2626"
    escaped_title = html.escape(title)
    escaped_detail = html.escape(detail)
    markup = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escaped_title}</title>
    <style>
      body {{ margin:0; padding:32px; background:#f8fafc; color:#0f172a; font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Helvetica Neue',sans-serif; }}
      .card {{ max-width:560px; margin:8vh auto; background:#fff; border:1px solid #e2e8f0; border-radius:24px; padding:28px; box-shadow:0 16px 48px rgba(15,23,42,.08); }}
      .badge {{ display:inline-flex; padding:6px 12px; border-radius:999px; color:{tone}; background:#f1f5f9; font-size:12px; font-weight:700; }}
      h1 {{ font-size:24px; margin:18px 0 12px; line-height:1.3; }}
      p {{ font-size:14px; line-height:1.75; color:#475569; margin:0 0 12px; }}
    </style>
  </head>
  <body>
    <main class="card">
      <div class="badge">{'授权已收到' if success else '授权失败'}</div>
      <h1>{escaped_title}</h1>
      <p>{escaped_detail}</p>
      <p>现在可以回到益语智库软件，软件会自动刷新飞书授权状态。</p>
    </main>
  </body>
</html>"""
    return HTMLResponse(markup)


def _db_path() -> Path:
    return Path(os.environ.get("YIYU_FEISHU_OAUTH_RELAY_DB", DEFAULT_DB_PATH)).expanduser()


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS relay_sessions (
            state_hash TEXT PRIMARY KEY,
            claim_secret_hash TEXT NOT NULL,
            code TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            received_at TEXT,
            claimed_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_relay_sessions_expires ON relay_sessions(expires_at)")
    conn.commit()
    return conn


def _cleanup_expired(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM relay_sessions WHERE expires_at <= ? OR claimed_at IS NOT NULL", (_now_iso(),))
    conn.commit()


def create_app() -> FastAPI:
    app = FastAPI(title="YiYu Feishu OAuth Relay")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        with _connect() as conn:
            _cleanup_expired(conn)
        return {"status": "ok"}

    @app.post("/feishu/member/sessions", response_model=RelaySessionRecord)
    def create_session(payload: RelaySessionCreatePayload) -> RelaySessionRecord:
        state_hash = _normalize_hash(payload.stateHash)
        claim_secret_hash = _normalize_hash(payload.claimSecretHash)
        try:
            expires_at = _parse_iso(payload.expiresAt)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="expiresAt 必须是合法 ISO 时间。") from exc
        if expires_at <= _now():
            raise HTTPException(status_code=400, detail="授权会话已过期。")
        timestamp = _now_iso()
        with _connect() as conn:
            _cleanup_expired(conn)
            conn.execute(
                """
                INSERT INTO relay_sessions(
                    state_hash, claim_secret_hash, code, error_message, created_at, expires_at, received_at, claimed_at
                ) VALUES(?, ?, NULL, NULL, ?, ?, NULL, NULL)
                ON CONFLICT(state_hash) DO UPDATE SET
                    claim_secret_hash = excluded.claim_secret_hash,
                    code = NULL,
                    error_message = NULL,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    received_at = NULL,
                    claimed_at = NULL
                """,
                (state_hash, claim_secret_hash, timestamp, expires_at.isoformat()),
            )
            conn.commit()
        return RelaySessionRecord(status="registered", expiresAt=expires_at.isoformat())

    @app.get("/feishu/member/callback", response_class=HTMLResponse)
    def feishu_member_callback(
        code: str | None = Query(default=None),
        state: str | None = Query(default=None),
        error: str | None = Query(default=None),
        error_description: str | None = Query(default=None),
    ) -> HTMLResponse:
        if not state:
            return _render_callback_page("飞书授权失败", "缺少授权状态，请回到益语智库软件重新发起授权。", success=False)
        state_hash = _sha256(state)
        with _connect() as conn:
            _cleanup_expired(conn)
            row = conn.execute("SELECT * FROM relay_sessions WHERE state_hash = ?", (state_hash,)).fetchone()
            if not row:
                return _render_callback_page("飞书授权失败", "这次授权会话不存在或已过期，请回到益语智库软件重新发起授权。", success=False)
            try:
                if _parse_iso(str(row["expires_at"])) <= _now():
                    conn.execute(
                        "UPDATE relay_sessions SET error_message = ? WHERE state_hash = ?",
                        ("授权会话已过期。", state_hash),
                    )
                    conn.commit()
                    return _render_callback_page("飞书授权失败", "这次授权会话已过期，请回到益语智库软件重新发起授权。", success=False)
            except ValueError:
                conn.execute(
                    "UPDATE relay_sessions SET error_message = ? WHERE state_hash = ?",
                    ("授权会话时间损坏。", state_hash),
                )
                conn.commit()
                return _render_callback_page("飞书授权失败", "这次授权会话状态异常，请回到益语智库软件重新发起授权。", success=False)
            if error:
                message = _safe_error(error_description or error)
                conn.execute(
                    "UPDATE relay_sessions SET error_message = ?, received_at = ? WHERE state_hash = ?",
                    (message or "飞书拒绝了本次授权。", _now_iso(), state_hash),
                )
                conn.commit()
                return _render_callback_page("飞书授权失败", "飞书没有完成本次授权，请回到益语智库软件重新发起。", success=False)
            if not code or not code.strip():
                conn.execute(
                    "UPDATE relay_sessions SET error_message = ?, received_at = ? WHERE state_hash = ?",
                    ("飞书没有返回有效授权码。", _now_iso(), state_hash),
                )
                conn.commit()
                return _render_callback_page("飞书授权失败", "飞书没有返回有效授权码，请回到益语智库软件重新发起授权。", success=False)
            conn.execute(
                "UPDATE relay_sessions SET code = ?, error_message = NULL, received_at = ? WHERE state_hash = ?",
                (code.strip(), _now_iso(), state_hash),
            )
            conn.commit()
        return _render_callback_page("飞书授权已收到", "授权结果已安全回传，稍后会由你的组织云端完成绑定。", success=True)

    @app.post("/feishu/member/code/claim", response_model=RelayCodeClaimResult)
    def claim_code(payload: RelayCodeClaimPayload) -> RelayCodeClaimResult:
        state_hash = _sha256(payload.state)
        claim_secret_hash = _sha256(payload.claimSecret)
        with _connect() as conn:
            _cleanup_expired(conn)
            row = conn.execute("SELECT * FROM relay_sessions WHERE state_hash = ?", (state_hash,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="授权会话不存在或已过期。")
            if not hmac.compare_digest(str(row["claim_secret_hash"]), claim_secret_hash):
                raise HTTPException(status_code=403, detail="授权会话校验失败。")
            try:
                if _parse_iso(str(row["expires_at"])) <= _now():
                    conn.execute("DELETE FROM relay_sessions WHERE state_hash = ?", (state_hash,))
                    conn.commit()
                    return RelayCodeClaimResult(status="expired", errorMessage="授权会话已过期。")
            except ValueError:
                conn.execute("DELETE FROM relay_sessions WHERE state_hash = ?", (state_hash,))
                conn.commit()
                return RelayCodeClaimResult(status="error", errorMessage="授权会话时间损坏。")
            if row["error_message"]:
                message = str(row["error_message"])
                conn.execute("DELETE FROM relay_sessions WHERE state_hash = ?", (state_hash,))
                conn.commit()
                return RelayCodeClaimResult(status="error", errorMessage=message)
            if not row["code"]:
                return RelayCodeClaimResult(status="pending", receivedAt=str(row["received_at"]) if row["received_at"] else None)
            code = str(row["code"])
            received_at = str(row["received_at"]) if row["received_at"] else None
            conn.execute(
                "UPDATE relay_sessions SET claimed_at = ? WHERE state_hash = ?",
                (_now_iso(), state_hash),
            )
            conn.commit()
        return RelayCodeClaimResult(status="authorized", code=code, receivedAt=received_at)

    return app


app = create_app()
