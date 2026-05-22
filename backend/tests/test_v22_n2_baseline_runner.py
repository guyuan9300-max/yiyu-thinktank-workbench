"""[B] 自检 · V2.2 N2 5/19 金标准 runner 不依赖真实 db 的逻辑测试

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_n2_baseline_runner.py -v

服务: V2.2_NORTH_STAR.md N1 (runner 本身正确才能信 N2 数字)

覆盖:
- 0/7 命中场景 (空 db)
- 7/7 完美命中场景 (seed 全套真实事实)
- 部分命中 (2/7, 模拟当前 prod db 现状)
- 强命中 vs 弱命中区分 (role + 5/19 source)
- 不同 client_id 隔离
- atomic_facts 表不存在 → 报错
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# 让 scripts/ 在 import path 上
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.run_v22_n2_baseline import (  # noqa: E402
    DEFAULT_CLIENT_ID,
    PROBES_5_19_TRUE_ALIGN,
    BaselineReport,
    FactProbe,
    ProbeResult,
    probe_fact,
    run_baseline,
)


# ── Fixtures ────────────────────────────────────────────────


def _make_atomic_facts_schema(conn: sqlite3.Connection) -> None:
    """模拟 v2.2 atomic_facts 表 (含 5 维元数据字段)"""
    conn.execute(
        """
        CREATE TABLE atomic_facts (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            subject_entity_id TEXT,
            subject_text TEXT NOT NULL,
            attribute TEXT NOT NULL,
            value_text TEXT NOT NULL,
            value_normalized TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.0,
            source_v2_chunk_id TEXT,
            source_v2_document_id TEXT,
            evidence_text TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            -- v2.2 F1.8/F1.9 5 维元数据 (N3 预留)
            content_role TEXT DEFAULT '',
            actor_type TEXT DEFAULT 'human',
            actor_id TEXT DEFAULT '',
            verification_status TEXT DEFAULT 'unverified',
            superseded_by_id TEXT,
            time_anchor TEXT,
            reasoning_trace_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _insert(
    conn: sqlite3.Connection,
    *,
    id_: str,
    subject_text: str,
    attribute: str,
    value_text: str,
    client_id: str = DEFAULT_CLIENT_ID,
    content_role: str = "fact",
    confidence: float = 0.9,
    source_v2_document_id: str | None = None,
    evidence_text: str | None = None,
    status: str = "active",
) -> None:
    conn.execute(
        """
        INSERT INTO atomic_facts (
            id, client_id, subject_text, attribute, value_text,
            value_normalized, confidence, source_v2_document_id, evidence_text,
            status, content_role, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            id_, client_id, subject_text, attribute, value_text,
            value_text, confidence, source_v2_document_id, evidence_text,
            status, content_role, "2026-05-22", "2026-05-22",
        ),
    )


@pytest.fixture
def empty_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _make_atomic_facts_schema(conn)
    return conn


@pytest.fixture
def full_5_19_db() -> sqlite3.Connection:
    """7/7 完美命中 db (模拟 F2.1 LLM extractor 跑出理想结果)"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _make_atomic_facts_schema(conn)

    src_doc = "v2doc_doc_5_19_zhangzhen_align"  # 5/19 张真对齐会 docx id

    # 7 个关键事实分别 seed
    _insert(
        conn, id_="af_1", subject_text="张真", attribute="职务变更",
        value_text="接任法人代表", content_role="decision",
        source_v2_document_id=src_doc, evidence_text="张真接任法人",
    )
    _insert(
        conn, id_="af_2", subject_text="张真", attribute="职务",
        value_text="理事长", content_role="decision",
        source_v2_document_id=src_doc, evidence_text="张真接任理事长",
    )
    _insert(
        conn, id_="af_3", subject_text="强哥", attribute="入职日慈",
        value_text="担任秘书长", content_role="fact",
        source_v2_document_id=src_doc, evidence_text="强哥加入团队",
    )
    _insert(
        conn, id_="af_4", subject_text="日慈", attribute="秘书长",
        value_text="强哥", content_role="decision",
        source_v2_document_id=src_doc, evidence_text="新秘书长就位",
    )
    _insert(
        conn, id_="af_5", subject_text="兴盛", attribute="项目合并",
        value_text="兴盛 + 心理魔法学院合并为新业务线",
        content_role="decision",
        source_v2_document_id=src_doc, evidence_text="兴盛合并",
    )
    _insert(
        conn, id_="af_6", subject_text="心理魔法学院", attribute="状态",
        value_text="合并至新业务线", content_role="fact",
        source_v2_document_id=src_doc, evidence_text="心理魔法学院调整",
    )
    _insert(
        conn, id_="af_7", subject_text="安心妈妈", attribute="项目状态",
        value_text="新项目启动", content_role="decision",
        source_v2_document_id=src_doc, evidence_text="安心妈妈立项",
    )
    conn.commit()
    return conn


@pytest.fixture
def partial_2_of_7_db() -> sqlite3.Connection:
    """当前 prod db 现状: 只 2/7 命中 (理事长 + 兴盛)"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _make_atomic_facts_schema(conn)

    # 只 seed 2 个事实 (跟 prod 真实数据对应)
    _insert(
        conn, id_="af_p1", subject_text="比如说张真老师你",
        attribute="权限", value_text="最高权限",
        content_role="observation",  # role 不对 — 不是 decision
        # 无 source — 不是 5/19 docx
    )
    _insert(
        conn, id_="af_p2", subject_text="兴盛计划",
        attribute="说明", value_text="客户业务线之一",
        content_role="fact",
        # 无 source
    )
    conn.commit()
    return conn


# ── 测试: 0/7 命中 ─────────────────────────────────────────


def test_empty_db_zero_hit(empty_db: sqlite3.Connection) -> None:
    """空 db → 0/7 命中, B 门 FAIL"""
    results = [probe_fact(empty_db, probe) for probe in PROBES_5_19_TRUE_ALIGN]
    report = BaselineReport(
        client_id=DEFAULT_CLIENT_ID,
        db_path=":memory:",
        probes=results,
    )
    assert report.hit_count == 0
    assert report.total == 7
    assert report.strong_hit_count == 0
    # B 门
    assert report.to_dict()["summary"]["b_gate_pass"] is False


# ── 测试: 7/7 完美命中 (F2.1 抽取理想态) ──────────────────


def test_full_5_19_db_perfect_hit(full_5_19_db: sqlite3.Connection) -> None:
    """理想抽取 → 7/7 命中 + 全部强命中"""
    results = [probe_fact(full_5_19_db, probe) for probe in PROBES_5_19_TRUE_ALIGN]
    report = BaselineReport(
        client_id=DEFAULT_CLIENT_ID,
        db_path=":memory:",
        probes=results,
    )
    # 7 个 keyword 都命中
    assert report.hit_count == 7, (
        f"期望 7/7, 实际 {report.hit_count}/7. 缺: "
        f"{[p.probe.label for p in results if not p.hit]}"
    )
    # 全部强命中 (role 对 + 5/19 来源)
    assert report.strong_hit_count == 7
    # B 门
    assert report.to_dict()["summary"]["b_gate_pass"] is True


# ── 测试: 2/7 部分命中 (prod 真实现状) ───────────────────


def test_partial_2_of_7_matches_prod_baseline(
    partial_2_of_7_db: sqlite3.Connection,
) -> None:
    """模拟当前 prod db: 弱命中 2/7 (理事长 + 兴盛), 但都不是强命中"""
    results = [probe_fact(partial_2_of_7_db, probe) for probe in PROBES_5_19_TRUE_ALIGN]
    report = BaselineReport(
        client_id=DEFAULT_CLIENT_ID,
        db_path=":memory:",
        probes=results,
    )
    # 检查 2 弱命中
    hit_labels = {p.probe.label for p in results if p.hit}
    # subject_text='比如说张真老师你' → '张真' 弱命中
    # attribute='权限' value='最高权限' → '法人/理事长' 不一定命中
    # value='客户业务线之一' subject='兴盛计划' → '兴盛' 弱命中
    assert "兴盛 + 心理魔法学院合并" in hit_labels  # '兴盛' 命中
    # 强命中 0 (role 不对 + 没 5/19 source)
    assert report.strong_hit_count == 0
    # B 门 FAIL (<4/7)
    assert report.to_dict()["summary"]["b_gate_pass"] is False


# ── 测试: 强命中 vs 弱命中区分 ────────────────────────────


def test_strong_hit_requires_role_and_source(
    empty_db: sqlite3.Connection,
) -> None:
    """关键词命中但 role 错 / 没 5/19 source → 弱命中,不算强命中"""
    # seed: 命中 keyword 但 role 不在 expected, 也没 source
    _insert(
        empty_db, id_="af_weak", subject_text="安心妈妈",
        attribute="提到", value_text="某人聊天里提到了",
        content_role="speculation",  # 不在 expected_roles
        # 无 source
    )
    empty_db.commit()
    result = probe_fact(
        empty_db,
        next(p for p in PROBES_5_19_TRUE_ALIGN if p.id == "p7_anxin_mama"),
    )
    assert result.hit is True
    assert result.hit_count == 1
    assert result.strong_hit is False  # role 不对


def test_strong_hit_with_correct_role_and_source(
    empty_db: sqlite3.Connection,
) -> None:
    """关键词 + role + source 三者齐 → 强命中"""
    _insert(
        empty_db, id_="af_strong", subject_text="安心妈妈",
        attribute="项目状态", value_text="启动",
        content_role="decision",  # expected
        source_v2_document_id="20260519_zhangzhen_align",  # 含 5/19 关键词
    )
    empty_db.commit()
    result = probe_fact(
        empty_db,
        next(p for p in PROBES_5_19_TRUE_ALIGN if p.id == "p7_anxin_mama"),
    )
    assert result.hit is True
    assert result.has_correct_role is True
    assert result.has_5_19_source is True
    assert result.strong_hit is True


# ── 测试: client_id 隔离 ─────────────────────────────────


def test_client_isolation(empty_db: sqlite3.Connection) -> None:
    """其它 client 的事实不算日慈命中"""
    _insert(
        empty_db, id_="af_other", subject_text="张真",
        attribute="职务", value_text="理事长",
        client_id="client_other_org",  # 不是日慈
        content_role="decision",
    )
    empty_db.commit()
    results = [probe_fact(empty_db, probe) for probe in PROBES_5_19_TRUE_ALIGN]
    report = BaselineReport(
        client_id=DEFAULT_CLIENT_ID,
        db_path=":memory:",
        probes=results,
    )
    # 日慈不命中 (因为只有别的 client 有)
    assert report.hit_count == 0


# ── 测试: status='superseded' 不算 active 命中 ──────────


def test_superseded_facts_not_counted(empty_db: sqlite3.Connection) -> None:
    """旧版被 superseded 的事实不算 (R2 信息更新场景)"""
    _insert(
        empty_db, id_="af_old", subject_text="张真",
        attribute="职务", value_text="理事长",
        content_role="decision",
        status="superseded",  # 已被新版替换
    )
    empty_db.commit()
    result = probe_fact(
        empty_db,
        next(p for p in PROBES_5_19_TRUE_ALIGN if p.id == "p2_chairman"),
    )
    assert result.hit_count == 0  # superseded 不算


# ── 测试: 报告格式 ───────────────────────────────────────


def test_report_to_dict_has_summary_and_probes(
    full_5_19_db: sqlite3.Connection,
) -> None:
    results = [probe_fact(full_5_19_db, probe) for probe in PROBES_5_19_TRUE_ALIGN]
    report = BaselineReport(
        client_id=DEFAULT_CLIENT_ID,
        db_path=":memory:",
        probes=results,
    )
    d = report.to_dict()
    assert "summary" in d
    assert "probes" in d
    assert len(d["probes"]) == 7
    # summary 字段
    assert d["summary"]["total"] == 7
    assert d["summary"]["hit"] == 7
    assert d["summary"]["b_gate_pass"] is True
    assert d["summary"]["hit_rate"] == "7/7"


def test_report_human_text_includes_b_gate_marker(
    empty_db: sqlite3.Connection,
) -> None:
    """人读报告应该明显展示 B 门状态"""
    results = [probe_fact(empty_db, probe) for probe in PROBES_5_19_TRUE_ALIGN]
    report = BaselineReport(
        client_id=DEFAULT_CLIENT_ID,
        db_path=":memory:",
        probes=results,
    )
    text = report.to_human_text()
    assert "B 门" in text
    assert "FAIL" in text  # 0/7 必 FAIL
    assert "缺失" in text  # 缺失项报告


# ── 测试: run_baseline 端到端 (用临时 file db) ────────


def test_run_baseline_end_to_end(tmp_path: Path) -> None:
    """run_baseline 接受 file path, 不存在时抛 FileNotFoundError"""
    nonexistent = tmp_path / "ghost.db"
    with pytest.raises(FileNotFoundError):
        run_baseline(nonexistent)


def test_run_baseline_with_real_file_db(tmp_path: Path) -> None:
    """真 file db, 跑端到端"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _make_atomic_facts_schema(conn)
    _insert(
        conn, id_="af_e2e", subject_text="安心妈妈",
        attribute="项目状态", value_text="启动",
        content_role="decision",
        source_v2_document_id="20260519_doc",
    )
    conn.commit()
    conn.close()

    report = run_baseline(db_path)
    assert report.hit_count == 1
    assert report.to_dict()["summary"]["hit"] == 1


# ── 测试: atomic_facts 表不存在 ──────────────────────────


def test_missing_table_raises(tmp_path: Path) -> None:
    """db 存在但没 atomic_facts 表 → RuntimeError"""
    db_path = tmp_path / "no_table.db"
    conn = sqlite3.connect(str(db_path))
    # 不建 atomic_facts
    conn.close()
    with pytest.raises(RuntimeError, match="atomic_facts 表不存在"):
        run_baseline(db_path)
