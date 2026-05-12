"""关系三元组抽取测试（迭代 5）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.relation_extractor import (
    ExtractedRelation,
    extract_by_rules,
    extract_relations_from_chunk,
)


def _has(predicates: list[ExtractedRelation], subject: str, predicate: str, obj: str) -> bool:
    return any(
        r.subject_text == subject and r.predicate == predicate and r.object_text == obj
        for r in predicates
    )


@pytest.mark.unit
def test_extract_cooperates_with() -> None:
    rels = extract_by_rules("日慈科技和阿里集团合作推出新产品。")
    assert _has(rels, "日慈科技", "cooperates_with", "阿里集团")


@pytest.mark.unit
def test_extract_competes_with_via_compound_term() -> None:
    rels = extract_by_rules("日慈科技的主要竞品是字节科技。")
    assert _has(rels, "日慈科技", "competes_with", "字节科技")


@pytest.mark.unit
def test_extract_invests_in() -> None:
    rels = extract_by_rules("阿里集团投资了日慈科技。")
    assert _has(rels, "阿里集团", "invests_in", "日慈科技")


@pytest.mark.unit
def test_extract_acquires() -> None:
    rels = extract_by_rules("百度收购了日慈科技。")
    assert _has(rels, "百度", "acquires", "日慈科技")


@pytest.mark.unit
def test_extract_works_at() -> None:
    rels = extract_by_rules("张三在阿里集团担任总监。")
    # 第一个模式抓 "张三 任职 阿里集团"
    found = any(r.subject_text == "张三" and r.predicate == "works_at" for r in rels)
    assert found, f"未抓到 works_at: {rels}"


@pytest.mark.unit
def test_extract_founded() -> None:
    rels = extract_by_rules("马云创立了阿里巴巴集团。")
    assert _has(rels, "马云", "founded", "阿里巴巴集团")


@pytest.mark.unit
def test_extract_located_in() -> None:
    rels = extract_by_rules("日慈科技位于北京中关村。")
    assert _has(rels, "日慈科技", "located_in", "北京中关村")


@pytest.mark.unit
def test_extract_supersedes() -> None:
    rels = extract_by_rules("新方案取代了旧版本。")
    assert _has(rels, "新方案", "supersedes", "旧版本")


@pytest.mark.unit
def test_extract_no_match_returns_empty() -> None:
    rels = extract_by_rules("这是一段普通描述文字。")
    assert rels == []


@pytest.mark.unit
def test_extract_dedupes_same_triple_in_one_chunk() -> None:
    """同 (subject, predicate, object) 在同一段内多次出现 → 只算一次。"""
    text = "日慈科技和阿里集团合作。后来日慈科技和阿里集团合作的项目扩大了。"
    rels = extract_by_rules(text)
    matches = [r for r in rels if r.subject_text == "日慈科技" and r.object_text == "阿里集团"]
    assert len(matches) == 1


@pytest.mark.unit
def test_main_entry_combines_rule_and_llm() -> None:
    def fake_llm(_chunk: str) -> list[ExtractedRelation]:
        return [
            ExtractedRelation(
                predicate="evaluates",
                subject_text="客户",
                object_text="方案",
                confidence=0.6,
                evidence_text="...",
            ),
        ]

    rels = extract_relations_from_chunk(
        "日慈科技投资了字节跳动。",
        llm_extractor=fake_llm,
    )
    # 规则抓到 invests_in
    assert any(r.predicate == "invests_in" for r in rels)
    # LLM 加的 evaluates 也合并进来
    assert any(r.predicate == "evaluates" and r.subject_text == "客户" for r in rels)


@pytest.mark.unit
def test_main_entry_falls_back_when_llm_raises() -> None:
    def broken_llm(_chunk: str) -> list[ExtractedRelation]:
        raise RuntimeError("LLM 挂了")

    rels = extract_relations_from_chunk(
        "日慈科技投资了字节跳动。",
        llm_extractor=broken_llm,
    )
    assert len(rels) >= 1
    assert any(r.predicate == "invests_in" for r in rels)


@pytest.mark.unit
def test_extract_filters_invalid_pairs() -> None:
    """subject == object 或 长度 < 2 应当被过滤。"""
    rels = extract_by_rules("X和Y合作。")  # 单字主语
    assert rels == []
