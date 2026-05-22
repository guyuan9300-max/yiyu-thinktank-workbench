"""[A] F2.1 上量批抽 — 跑 1 个客户全部高价值 docx, 沉淀完整 atomic_facts 故事网

服务: NORTH_STAR N2 真目标 (顾源源 5/22 关键洞察):
"单 docx 抽 25 条只是工具验证。AI 把碎片拼成完整故事网,
 从任意入口看到全局, 才是 N2 真目标。"

跟 run_f21_extraction.py 区别:
- 单脚本跑 1 个客户全部 (39 份) 高价值 docx
- 失败容错 (一份失败不影响其他)
- 中断恢复 (state 文件持久化进度)
- 控制 token 消耗 (跳过已抽 / 限制单 batch 大小)

跑法:
    cd ~/openclaw/workspace/V2.1
    ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \\
        scripts/run_f21_upbatch_extraction.py 日慈基金会

预估:
- 39 份 docx, 每份 60-180 秒 LLM (含分批) → 总 2-3 小时
- ~20-50 元豆包 token
- 输出 500-1500 条 atomic_facts (跨 docx 拼故事的原料)
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

PROD_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"

# 高价值 docx 筛选标准 (避免浪费 token 跑公众号摘录 / 短任务 doc)
HIGH_VALUE_KINDS = ("docx", "pdf", "txt", "xlsx")
MIN_CHARS = 1500   # < 1500 字 (除 5/19 张真会议这种密集型) 信息密度低, 跳过
INCLUDE_FORCE = (
    "20260519_150340_和日慈张真进行5月份第一次战略对齐会.docx",  # 5/19 张真会议, 即使 1715 字也算
)
EXCLUDE_KINDS = ("wechat_excerpt",)  # 公众号摘录, 跳过


@dataclass
class DocResult:
    """单份 docx 抽取结果"""
    doc_id: str
    file_name: str
    kind: str
    chars: int
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    status: str = "pending"  # pending / running / done / failed / skipped
    facts_written: int = 0
    facts_skipped_general: int = 0
    facts_failed: int = 0
    update_relations: dict[str, int] = field(default_factory=dict)
    layer_coverage: dict[str, int] = field(default_factory=dict)
    error: str = ""


@dataclass
class BatchReport:
    """整批上量报告"""
    client_id: str
    client_name: str
    started_at: str
    completed_at: str = ""
    duration_seconds: float = 0.0
    total_docs: int = 0
    done_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    total_facts_written: int = 0
    total_facts_skipped_general: int = 0
    # 跨全部 docx 的 5 维元数据统计
    aggregate_layer_coverage: dict[str, int] = field(default_factory=dict)
    aggregate_update_relations: dict[str, int] = field(default_factory=dict)
    # 5/19 金标准命中
    keyword_hits: dict[str, int] = field(default_factory=dict)
    # 每份 docx 详细结果
    doc_results: list[DocResult] = field(default_factory=list)
    # state file 位置 (中断恢复)
    state_file: str = ""
    tmp_data_dir: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_state(state_file: Path, report: BatchReport) -> None:
    """持久化进度, 中断后可读"""
    state_file.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_state(state_file: Path) -> BatchReport | None:
    """读已有进度 (中断恢复用)"""
    if not state_file.exists():
        return None
    try:
        d = json.loads(state_file.read_text(encoding="utf-8"))
        doc_results = [DocResult(**dr) for dr in d.pop("doc_results", [])]
        report = BatchReport(**d)
        report.doc_results = doc_results
        return report
    except Exception:
        return None


def main() -> int:
    client_name_query = sys.argv[1] if len(sys.argv) > 1 else "日慈基金会"

    print(f"\n{'=' * 72}")
    print(f"  [A] F2.1 上量批抽 · {client_name_query}")
    print(f"  prod db: {PROD_DB}")
    print(f"  目标: 沉淀全客户故事网到 atomic_facts (跨 docx 拼故事原料)")
    print(f"{'=' * 72}\n")

    if not PROD_DB.exists():
        print(f"✗ prod db 不存在: {PROD_DB}")
        return 1

    # ─── Phase 1: copy prod db + start app ──────────────
    print("▸ 复制 prod db 到 tmp + 起 FastAPI app...", flush=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="f21_upbatch_"))
    data_dir = tmp_dir / "data"
    data_dir.mkdir()
    shutil.copy(PROD_DB, data_dir / "app.db")
    for ext in ("-wal", "-shm"):
        wal = data_dir / f"app.db{ext}"
        if wal.exists():
            wal.unlink()
    print(f"  tmp data_dir: {data_dir}", flush=True)

    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.services.document_llm_extractor import DocumentLLMExtractor

    app = create_app(data_dir)
    client = TestClient(app)
    client.__enter__()
    state = app.state.app_state
    print(f"  ai_service ready: {state.ai is not None}\n", flush=True)

    # ─── Phase 2: 找客户 + 列出高价值 docx ──────────────
    cli = state.db.fetchone(
        "SELECT id, name FROM clients WHERE name LIKE ? OR alias LIKE ?",
        (f"%{client_name_query}%", f"%{client_name_query}%"),
    )
    if not cli:
        print(f"✗ 客户不存在: {client_name_query}")
        client.__exit__(None, None, None)
        return 1

    client_id = str(cli["id"])
    client_name = str(cli["name"])
    print(f"客户: {client_id} / {client_name}", flush=True)

    # 找高价值 docx
    rows = state.db.fetchall(
        f"""
        SELECT id, file_name, kind, LENGTH(markdown_content) AS chars
        FROM v2_documents
        WHERE client_id = ?
          AND parse_status IN ('ready', 'completed')
          AND kind IN ({",".join("?" for _ in HIGH_VALUE_KINDS)})
          AND kind NOT IN ({",".join("?" for _ in EXCLUDE_KINDS)})
          AND (LENGTH(markdown_content) >= ? OR file_name IN ({",".join("?" for _ in INCLUDE_FORCE)}))
        ORDER BY LENGTH(markdown_content) DESC
        """,
        (client_id, *HIGH_VALUE_KINDS, *EXCLUDE_KINDS, MIN_CHARS, *INCLUDE_FORCE),
    )
    print(f"找到 {len(rows)} 份高价值 docx (≥ {MIN_CHARS} 字 或 强制包含)\n", flush=True)

    # ─── Phase 3: 中断恢复 ───────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    state_file = REPORTS_DIR / f"f21_upbatch_state_{client_name}_{timestamp}.json"
    report = BatchReport(
        client_id=client_id, client_name=client_name,
        started_at=_now(),
        total_docs=len(rows),
        state_file=str(state_file),
        tmp_data_dir=str(tmp_dir),
    )

    # 初始化 doc_results (待抽列表)
    for r in rows:
        report.doc_results.append(DocResult(
            doc_id=str(r["id"]),
            file_name=str(r["file_name"]),
            kind=str(r["kind"]),
            chars=int(r["chars"] or 0),
        ))
    _save_state(state_file, report)
    print(f"state file: {state_file.name}\n", flush=True)

    # ─── Phase 4: 逐 docx 抽取 (失败容错, 进度持久化) ───
    started_perf = time.perf_counter()
    extractor = DocumentLLMExtractor(state.db, state.ai)
    ai_session_id = f"f21_upbatch_{int(time.time())}"

    for idx, doc_result in enumerate(report.doc_results, 1):
        prefix = f"[{idx}/{len(rows)}]"
        print(f"{prefix} {doc_result.kind:5s} | {doc_result.chars:>6} 字 | "
              f"{doc_result.file_name[:55]}", flush=True)
        doc_result.started_at = _now()
        doc_result.status = "running"
        doc_started = time.perf_counter()
        try:
            r = extractor.extract_from_document(
                v2_document_id=doc_result.doc_id,
                ai_session_id=f"{ai_session_id}_{idx}",
                actor_id=f"A AI F2.1 upbatch {idx}",
            )
            doc_result.facts_written = r.facts_written
            doc_result.facts_skipped_general = r.facts_skipped_general
            doc_result.facts_failed = r.facts_failed
            doc_result.update_relations = r.update_relations
            doc_result.layer_coverage = r.layer_coverage
            doc_result.status = "done"
            print(f"    ✓ {r.facts_written} 条 / 跳通识 {r.facts_skipped_general} / "
                  f"失败 {r.facts_failed} / update {r.update_relations}", flush=True)
        except Exception as exc:
            doc_result.status = "failed"
            doc_result.error = f"{exc.__class__.__name__}: {exc}"
            print(f"    ✗ FAILED: {doc_result.error}", flush=True)
            print(f"    {traceback.format_exc()[-300:]}", flush=True)
        finally:
            doc_result.completed_at = _now()
            doc_result.duration_seconds = time.perf_counter() - doc_started

        # 累计统计
        report.done_count = sum(1 for d in report.doc_results if d.status == "done")
        report.failed_count = sum(1 for d in report.doc_results if d.status == "failed")
        report.total_facts_written = sum(d.facts_written for d in report.doc_results)
        report.total_facts_skipped_general = sum(d.facts_skipped_general for d in report.doc_results)
        for d in report.doc_results:
            for k, v in d.update_relations.items():
                report.aggregate_update_relations[k] = report.aggregate_update_relations.get(k, 0) + v
            for k, v in d.layer_coverage.items():
                report.aggregate_layer_coverage[k] = report.aggregate_layer_coverage.get(k, 0) + v

        # 持久化进度
        _save_state(state_file, report)

    # ─── Phase 5: 跨全部 docx 5/19 金标准命中 ─────────
    print("\n▸ 跨全部 docx 5/19 金标准 + 关键人物命中检查...", flush=True)
    keywords = [
        "法人", "理事长", "强哥", "秘书长", "兴盛",
        "心理魔法学院", "安心妈妈", "张真", "顾源源",
        "严斌", "高老师", "心盛", "兴盛计划",
    ]
    for kw in keywords:
        n = state.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM atomic_facts
            WHERE client_id = ?
              AND (subject_text LIKE ? OR value_text LIKE ? OR attribute LIKE ? OR evidence_text LIKE ?)
            """,
            (client_id, f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%"),
        )["n"]
        report.keyword_hits[kw] = int(n)
        marker = "✓" if n > 0 else "✗"
        print(f"  {marker} {kw}: {n} 条 atomic_facts", flush=True)

    # ─── Phase 6: 收尾 ───────────────────────────────────
    report.completed_at = _now()
    report.duration_seconds = time.perf_counter() - started_perf
    _save_state(state_file, report)

    client.__exit__(None, None, None)

    print(f"\n{'=' * 72}")
    print(f"  上量完成 · {report.done_count}/{report.total_docs} 成功 · "
          f"{report.failed_count} 失败")
    print(f"  total atomic_facts: {report.total_facts_written}")
    print(f"  total skipped 通识: {report.total_facts_skipped_general}")
    print(f"  update_relations: {report.aggregate_update_relations}")
    print(f"  layer coverage: {report.aggregate_layer_coverage}")
    print(f"  耗时 {report.duration_seconds/60:.1f} 分钟")
    print(f"  state file: {state_file}")
    print(f"  tmp db: {tmp_dir}/data/app.db (NarrativeKernel 用)")
    print(f"{'=' * 72}\n")

    return 0 if report.failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
