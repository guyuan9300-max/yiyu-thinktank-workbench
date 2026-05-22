"""[A] V2.3 阶段 3 P0 · cross_source_check 单测

核心验收: B AI K-3 §1 经典案例 — '心灵 vs 心理' 必须能撞出来
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def test_layer1_string_eq():
    from app.services.cross_source_check import layer1_string_eq
    assert layer1_string_eq("日慈基金会", "日慈基金会") is True
    assert layer1_string_eq("  日慈基金会  ", "日慈基金会") is True
    assert layer1_string_eq("日慈基金会", "广东省日慈基金会") is False


def test_layer2_char_similarity_xinling_vs_xinli():
    """B AI K-3 §1 经典案例: '心灵 vs 心理' 同 pinyin xinli."""
    from app.services.cross_source_check import layer2_char_similarity

    # 短词
    sim1 = layer2_char_similarity("心灵", "心理")
    assert 0.4 <= sim1 <= 0.6  # 共享"心"字, LCS=1, max=2 → 0.5

    # 长词 (心灵魔法学院 vs 心理魔法学院)
    sim2 = layer2_char_similarity("心灵魔法学院", "心理魔法学院")
    assert sim2 >= 0.83  # 共享 5 字 / 6 字


def test_layer2_张真_vs_张铮():
    """另一个经典案例: 人名同音字."""
    from app.services.cross_source_check import layer2_char_similarity
    sim = layer2_char_similarity("张真", "张铮")
    assert 0.4 <= sim <= 0.6


def test_check_with_xinling_vs_xinli():
    """综合 check: '心灵魔法学院' vs '心理魔法学院' 应该进 clarify."""
    from app.services.cross_source_check import check

    result = check("心灵魔法学院", "心理魔法学院")
    assert result.layer1_string_eq is False
    assert result.layer2_char_similarity >= 0.83
    assert result.suspicion_score >= 0.6
    assert result.suggested_action == "clarify"  # 进澄清队列


def test_check_with_identical():
    """完全相同 → auto_merge."""
    from app.services.cross_source_check import check
    result = check("日慈基金会", "日慈基金会")
    assert result.layer1_string_eq is True
    assert result.suspicion_score == 1.0
    assert result.suggested_action == "auto_merge"


def test_check_with_completely_different():
    """完全不同 → different."""
    from app.services.cross_source_check import check
    result = check("日慈基金会", "腾讯公司")
    assert result.layer2_char_similarity < 0.3
    assert result.suggested_action == "different"


def test_scan_client_for_cross_source_candidates():
    """scan_client 批量扫描 — 应能从 atomic_facts 中找到嫌疑对."""
    from app.services.cross_source_check import scan_client_for_cross_source_candidates

    class _SimpleDb:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
        def execute(self, sql, params=()): return self.conn.execute(sql, params)
        def fetchall(self, sql, params=()): return self.conn.execute(sql, params).fetchall()

    db = _SimpleDb()
    db.execute(
        """CREATE TABLE atomic_facts (
            id TEXT PRIMARY KEY, client_id TEXT,
            subject_text TEXT, attribute TEXT, value_text TEXT,
            status TEXT DEFAULT 'active'
        )"""
    )

    # 加 3 条事实 (含同音字)
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, status) "
        "VALUES ('f1', 'cli', '心灵魔法学院', '类型', '项目', 'active')"
    )
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, status) "
        "VALUES ('f2', 'cli', '心理魔法学院', '类型', '项目', 'active')"
    )
    db.execute(
        "INSERT INTO atomic_facts (id, client_id, subject_text, attribute, value_text, status) "
        "VALUES ('f3', 'cli', '腾讯公司', '类型', '企业', 'active')"
    )

    candidates = scan_client_for_cross_source_candidates(db, "cli", threshold=0.6, limit=10)

    assert len(candidates) >= 1
    # 至少能撞出 心灵 vs 心理 这对
    top = candidates[0]
    assert {top["text_a"], top["text_b"]} == {"心灵魔法学院", "心理魔法学院"}
    assert top["action"] == "clarify"
    assert top["suspicion"] >= 0.83
