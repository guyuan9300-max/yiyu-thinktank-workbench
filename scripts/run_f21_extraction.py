"""[A] F2.1 真跑通 5/19 docx LLM 抽取 — standalone 脚本

服务 NORTH_STAR §8 警报破解:
- 当前 N2 客户感知 ~5-10% (5/19 金标准 2/7 命中)
- 本脚本跑「日慈第一天下午.docx」一次真实 LLM 抽取
- 预期: atomic_facts 表新增 50-150 条客户特定事实
- 顾源源评判 → 调 prompt → 再跑直到 5/7+ 命中

技术路径:
1. 复制 prod db 到 tmp 目录 (只读 + 副本, 不污染 prod)
2. 用 create_app(tmp_data_dir) 起 FastAPI app (复用主进程初始化)
3. 通过 app.state.app_state.ai 拿真实 ai_service (含豆包 Seed token)
4. DocumentLLMExtractor 跑抽取
5. 输出:
   - atomic_facts 表新增条数 + 5 维元数据完整度
   - reasoning_traces 表新增 (1 条 / 批)
   - update_relations 分布 (none/conflict/supersedes/complement)
   - layer 覆盖度
   - LLM 调用失败次数
   - 报告 dump 到 tests/reports/f21_extraction_<date>.json

跑法:
    cd ~/openclaw/workspace/V2.1
    ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \\
        scripts/run_f21_extraction.py [doc_file_name]

如果不传 doc_file_name 参数, 默认跑「日慈第一天下午.docx」。
"""
from __future__ import annotations

import json
import shutil
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
DEFAULT_DOC = "日慈第一天下午.docx"


@dataclass
class ExtractionReport:
    doc_id: str
    doc_file_name: str
    doc_size_chars: int
    started_at: str
    completed_at: str = ""
    duration_seconds: float = 0.0
    # IngestPipeline 结果
    facts_written: int = 0
    facts_skipped_duplicate: int = 0
    facts_skipped_general: int = 0
    facts_failed: int = 0
    update_relations: dict[str, int] = field(default_factory=dict)
    layer_coverage: dict[str, int] = field(default_factory=dict)
    # reasoning_traces 统计
    reasoning_traces_total: int = 0
    reasoning_traces_completed: int = 0
    reasoning_traces_failed: int = 0
    # 5/19 金标准 7 个关键事实预查 (LIKE 查 value_text + subject_text)
    hits_5_19_baseline: dict[str, int] = field(default_factory=dict)
    hits_5_19_total: int = 0
    # 错误
    errors: list[str] = field(default_factory=list)
    extraction_summary: str = ""
    # ★ 抽出的事实样本 (顾源源评判用) — 全部 facts dump
    extracted_facts: list[dict] = field(default_factory=list)
    # tmp data dir 路径 (不自动删除, 顾源源可手动查 / 删)
    tmp_data_dir: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    doc_file_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DOC
    print(f"\n{'=' * 72}")
    print(f"  [A] F2.1 真跑通 LLM 抽取 · {doc_file_name}")
    print(f"  prod db: {PROD_DB}")
    print(f"  目标: 5/19 金标准 2/7 → 5/7+ 命中")
    print(f"{'=' * 72}\n")

    if not PROD_DB.exists():
        print(f"✗ prod db 不存在: {PROD_DB}")
        return 1

    report = ExtractionReport(
        doc_id="", doc_file_name=doc_file_name, doc_size_chars=0,
        started_at=_now(),
    )
    started_perf = time.perf_counter()

    try:
        # ─── Phase 1: copy prod db + start app ──────────────
        print("▸ 1/5 复制 prod db 到 tmp...", flush=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix="f21_extraction_"))
        data_dir = tmp_dir / "data"
        data_dir.mkdir()
        shutil.copy(PROD_DB, data_dir / "app.db")
        # 清掉 -wal / -shm 避免引用过期连接
        for ext in ("-wal", "-shm"):
            wal = data_dir / f"app.db{ext}"
            if wal.exists():
                wal.unlink()
        print(f"  ✓ tmp data_dir: {data_dir}", flush=True)

        print("▸ 2/5 起 FastAPI app (会跑 migrations, 30-60 秒)...", flush=True)
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app(data_dir)
        client = TestClient(app)
        client.__enter__()
        state = app.state.app_state  # type: ignore[attr-defined]
        print(f"  ✓ app started, ai_service ready: {state.ai is not None}", flush=True)

        # ─── Phase 2: 找目标 docx ───────────────────────────
        print(f"▸ 3/5 找目标 docx「{doc_file_name}」...", flush=True)
        doc_row = state.db.fetchone(
            "SELECT id, client_id, kind, markdown_content FROM v2_documents "
            "WHERE file_name = ? AND parse_status IN ('ready', 'completed') "
            "ORDER BY imported_at DESC LIMIT 1",
            (doc_file_name,),
        )
        if not doc_row:
            err = f"docx 不在 prod db: {doc_file_name}"
            report.errors.append(err)
            print(f"  ✗ {err}", flush=True)
            return 1

        report.doc_id = str(doc_row["id"])
        markdown = str(doc_row["markdown_content"] or "")
        report.doc_size_chars = len(markdown)
        client_id = str(doc_row["client_id"])
        print(f"  ✓ doc_id={report.doc_id[:24]}.. / {report.doc_size_chars} 字 / client={client_id}", flush=True)

        # ─── Phase 3: 跑抽取 ────────────────────────────────
        print("▸ 4/5 调 DocumentLLMExtractor 跑 LLM 抽取 (可能 60-180 秒)...", flush=True)
        from app.services.document_llm_extractor import DocumentLLMExtractor

        ai_session_id = f"f21_run_{int(time.time())}"
        extractor = DocumentLLMExtractor(state.db, state.ai)
        result = extractor.extract_from_document(
            v2_document_id=report.doc_id,
            ai_session_id=ai_session_id,
            actor_id="A AI F2.1 standalone",
        )

        report.facts_written = result.facts_written
        report.facts_skipped_duplicate = result.facts_skipped_duplicate
        report.facts_skipped_general = result.facts_skipped_general
        report.facts_failed = result.facts_failed
        report.update_relations = result.update_relations
        report.layer_coverage = result.layer_coverage
        report.extraction_summary = result.extraction_summary
        report.errors.extend(result.errors)

        # reasoning_traces 统计
        trace_rows = state.db.fetchall(
            "SELECT status FROM reasoning_traces WHERE ai_session_id = ?",
            (ai_session_id,),
        )
        report.reasoning_traces_total = len(trace_rows)
        report.reasoning_traces_completed = sum(1 for r in trace_rows if r["status"] == "completed")
        report.reasoning_traces_failed = sum(1 for r in trace_rows if r["status"] == "failed")

        print(f"  ✓ 抽出 {report.facts_written} 条 / 跳过重复 {report.facts_skipped_duplicate} 条 "
              f"/ 跳过通识 {report.facts_skipped_general} 条 / 失败 {report.facts_failed} 条", flush=True)

        # ─── Phase 4: 5/19 金标准命中检查 ───────────────────
        print("▸ 5/5 5/19 金标准 7 关键事实命中检查...", flush=True)
        keywords = ["法人", "理事长", "强哥", "秘书长", "兴盛", "心理魔法学院", "安心妈妈"]
        for kw in keywords:
            rows = state.db.fetchall(
                """
                SELECT id, subject_text, attribute, value_text
                FROM atomic_facts
                WHERE client_id = ?
                  AND (subject_text LIKE ? OR value_text LIKE ? OR attribute LIKE ?)
                """,
                (client_id, f"%{kw}%", f"%{kw}%", f"%{kw}%"),
            )
            report.hits_5_19_baseline[kw] = len(rows)

        report.hits_5_19_total = sum(1 for c in report.hits_5_19_baseline.values() if c > 0)
        print(f"  ✓ 5/19 金标准命中: {report.hits_5_19_total}/7", flush=True)
        for kw, count in report.hits_5_19_baseline.items():
            marker = "✓" if count > 0 else "✗"
            print(f"    {marker} {kw}: {count} 条", flush=True)

        # ★ dump 全部抽出的 facts 到报告 (顾源源评判用, tmp 删了也能看)
        fact_rows = state.db.fetchall(
            """
            SELECT id, subject_text, attribute, value_text, content_role,
                   source_type, confidence, time_anchor, speaker_person_id,
                   verification_status, update_relation, evidence_text
            FROM atomic_facts
            WHERE actor_id = ?
            ORDER BY created_at
            """,
            (ai_session_id,),
        )
        report.extracted_facts = [
            {
                "id": str(r["id"]),
                "subject": str(r["subject_text"] or ""),
                "attribute": str(r["attribute"] or ""),
                "value": str(r["value_text"] or ""),
                "role": str(r["content_role"] or ""),
                "source_type": str(r["source_type"] or ""),
                "confidence": float(r["confidence"] or 0),
                "time_anchor": str(r["time_anchor"] or ""),
                "speaker": str(r["speaker_person_id"] or ""),
                "verify": str(r["verification_status"] or ""),
                "update_relation": str(r["update_relation"] or ""),
                "evidence": (str(r["evidence_text"] or ""))[:200],
            }
            for r in fact_rows
        ]
        print(f"  ✓ 已 dump {len(report.extracted_facts)} 条 facts 到报告", flush=True)

        client.__exit__(None, None, None)

    except Exception as exc:
        tb = traceback.format_exc()
        report.errors.append(f"运行错误: {exc}\n{tb[-2000:]}")
        print(f"\n✗ 出错:\n{tb[-2000:]}", flush=True)
        return 1
    finally:
        # ★ 不删 tmp — 顾源源可能要看 atomic_facts 表里抽到的事实, 手动 sqlite 查
        # 命令: sqlite3 /tmp/f21_extraction_xxx/data/app.db "SELECT * FROM atomic_facts"
        if 'tmp_dir' in locals():
            report.tmp_data_dir = str(tmp_dir)
            print(f"  ℹ tmp db 保留 (review 用): {tmp_dir}", flush=True)

        report.completed_at = _now()
        report.duration_seconds = time.perf_counter() - started_perf

        # 写报告
        json_path = REPORTS_DIR / f"f21_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path.write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"\n{'=' * 72}")
        print(f"  报告: {json_path.relative_to(ROOT)}")
        print(f"  耗时 {report.duration_seconds:.1f}s")
        print(f"{'=' * 72}\n")

    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
