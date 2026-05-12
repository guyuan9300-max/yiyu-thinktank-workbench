"""chunk 语义分类测试（迭代 4）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.semantic_classifier import (
    SemanticLabel,
    classify_by_rules,
    classify_chunk_semantic,
    parse_llm_output,
    semantic_weight,
)


@pytest.mark.unit
def test_classify_action_pattern() -> None:
    cases = [
        "本周内需要完成 Q3 财务报表的初稿。",
        "TODO: 跟进客户的合同审批。",
        "下一步：准备好产品发布会的物料。",
    ]
    for text in cases:
        label = classify_by_rules(text)
        assert label is not None
        assert label.semantic_type == "action", f"failed: {text}"


@pytest.mark.unit
def test_classify_question_pattern() -> None:
    cases = [
        "客户的预算到底有多少？",
        "为什么这个项目卡在合同评审环节？",
        "能否在月底前完成上线？",
    ]
    for text in cases:
        label = classify_by_rules(text)
        assert label is not None
        assert label.semantic_type == "question", f"failed: {text}"


@pytest.mark.unit
def test_classify_conclusion_pattern() -> None:
    cases = [
        "综上所述，客户对当前方案持谨慎态度。",
        "因此，建议把上线时间推迟到 Q4。",
        "结论是：人力投入不足是主要瓶颈。",
    ]
    for text in cases:
        label = classify_by_rules(text)
        assert label is not None
        assert label.semantic_type == "conclusion", f"failed: {text}"


@pytest.mark.unit
def test_classify_background_pattern() -> None:
    cases = [
        "简介：日慈基金会成立于 2014 年。",
        "历史上，客户曾尝试过两次组织变革。",
        "此前的合作主要集中在战略层面。",
    ]
    for text in cases:
        label = classify_by_rules(text)
        assert label is not None
        assert label.semantic_type == "background", f"failed: {text}"


@pytest.mark.unit
def test_classify_no_rule_match_returns_none() -> None:
    """普通陈述句不应命中任何规则——留给 LLM 层。"""
    assert classify_by_rules("客户的会计制度规定，年度预算需经理事会审议。") is None


@pytest.mark.unit
def test_classify_empty_returns_none_for_rules_and_unclassified_for_main() -> None:
    assert classify_by_rules("") is None
    assert classify_by_rules("   \n  ") is None
    label = classify_chunk_semantic("")
    assert label.semantic_type == "unclassified"


@pytest.mark.unit
def test_parse_llm_output_handles_plain_json() -> None:
    raw = '{"semantic_type":"fact","confidence":0.92}'
    label = parse_llm_output(raw)
    assert label is not None
    assert label.semantic_type == "fact"
    assert label.confidence == 0.92


@pytest.mark.unit
def test_parse_llm_output_handles_markdown_fence() -> None:
    raw = "好的。下面是分类结果：\n```json\n{\"semantic_type\": \"judgment\", \"confidence\": 0.7}\n```"
    label = parse_llm_output(raw)
    assert label is not None
    assert label.semantic_type == "judgment"


@pytest.mark.unit
def test_parse_llm_output_rejects_unknown_type() -> None:
    raw = '{"semantic_type":"alien","confidence":0.9}'
    assert parse_llm_output(raw) is None


@pytest.mark.unit
def test_classify_chunk_falls_back_when_llm_raises() -> None:
    def broken_llm(_chunk: str) -> SemanticLabel:
        raise RuntimeError("LLM 挂了")

    label = classify_chunk_semantic(
        "客户的会计制度规定年度预算需经理事会审议。",
        llm_classifier=broken_llm,
    )
    assert label.semantic_type == "unclassified"


@pytest.mark.unit
def test_classify_chunk_uses_llm_when_rules_dont_match() -> None:
    def stub_llm(_chunk: str) -> SemanticLabel:
        return SemanticLabel("fact", 0.9)

    label = classify_chunk_semantic(
        "客户公司注册地址在朝阳区，注册资本 100 万元。",
        llm_classifier=stub_llm,
    )
    assert label.semantic_type == "fact"
    assert label.confidence == 0.9


@pytest.mark.unit
def test_semantic_weight_priorities() -> None:
    """fact 应高于 opinion，conclusion 应高于 judgment。"""
    assert semantic_weight("fact") > semantic_weight("opinion")
    assert semantic_weight("conclusion") > semantic_weight("judgment")
    assert semantic_weight("question") < semantic_weight("fact")
    assert semantic_weight(None) == 1.0
    assert semantic_weight("unknown_type") == 1.0
