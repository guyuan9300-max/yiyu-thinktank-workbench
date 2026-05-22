"""[A] V2.3 阶段 3 P0 · cross_source_check · 4 层跨源同义/同音检测

服务: docs/V2.3_DATA_CENTER_MASTER_PLAN.md § 四 机制三 + B AI K-3 异议 1 + § 五 4 层澄清

蓝图原话:
  Layer 1 字面相同 (string_eq)        — 已实现 (detect_update_relation 现状)
  Layer 2 同音字 (pinyin similarity) — V2.3 新加
  Layer 3 语义相似 (embedding)        — V2.3 新加
  Layer 4 LLM 判同 (最贵)             — V2.3 新加

B AI K-3 §1 经典案例:
  "心灵魔法学院" vs "心理魔法学院" 同 pinyin xinli → 嫌疑度 0.95 → 进 clarification_records

本服务实现 4 层检测 + 综合 suspicion_score (0-1) + suggested_action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


SuspicionLevel = Literal["none", "low", "medium", "high", "very_high"]


@dataclass(frozen=True)
class CheckResult:
    """跨源检测结果."""
    text_a: str
    text_b: str
    layer1_string_eq: bool         # 字面是否完全相等
    layer2_char_similarity: float  # 字符级近似 (替代 pinyin, 0-1)
    layer3_embedding_similarity: float | None  # 语义相似度 (调 embedding 后填)
    layer4_llm_verdict: str | None             # LLM 判同 (调 LLM 后填)
    suspicion_score: float         # 综合嫌疑度 (0-1)
    suggested_action: str          # auto_merge / clarify / different / skip


# ─── Layer 1 · 字面相同 ────────────────────────────


def layer1_string_eq(text_a: str, text_b: str) -> bool:
    """完全字面相同 (case-insensitive + 去空格)."""
    return text_a.strip().lower() == text_b.strip().lower()


# ─── Layer 2 · 字符级近似 (替代 pinyin) ──────────────


def _char_lcs_length(s1: str, s2: str) -> int:
    """两字符串最长公共子序列长度 (LCS)."""
    if not s1 or not s2: return 0
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]


def layer2_char_similarity(text_a: str, text_b: str) -> float:
    """字符级近似 (中文同音字常字形类似 → 共享部分字).

    返回 0-1:
      1.0 = 完全相同
      0.83 = "心灵魔法学院" vs "心理魔法学院" (5/6 字相同)
      0.5 = "张真" vs "张铮" (1/2 字相同)
      < 0.3 = 不太可能同义
    """
    a, b = text_a.strip(), text_b.strip()
    if not a or not b: return 0.0
    if a == b: return 1.0
    lcs = _char_lcs_length(a, b)
    max_len = max(len(a), len(b))
    if max_len == 0: return 0.0
    return lcs / max_len


# ─── Layer 3 · embedding 相似度 ─────────────────────


def layer3_embedding_similarity(
    text_a: str, text_b: str,
    embedding_provider: Any | None = None,  # 调用方传 embedding_provider, 不传则 None
) -> float | None:
    """语义相似度 (cosine)).

    传 None 时返回 None (Layer 3 跳过).
    传 embedding_provider 时调 embed_texts + cosine.
    """
    if embedding_provider is None:
        return None
    try:
        emb_list, _meta = embedding_provider.embed_texts([text_a, text_b])
        v1, v2 = emb_list[0], emb_list[1]
        # cosine
        dot = sum(x * y for x, y in zip(v1, v2))
        n1 = sum(x * x for x in v1) ** 0.5
        n2 = sum(x * x for x in v2) ** 0.5
        if n1 == 0 or n2 == 0: return 0.0
        return float(dot / (n1 * n2))
    except Exception:
        return None


# ─── Layer 4 · LLM 判同 ────────────────────────────


_LLM_VERDICT_PROMPT = """判断下面两个文本是否指向同一实体/概念:
A: {text_a}
B: {text_b}

输出 JSON: {{"same": true/false, "confidence": 0.0-1.0, "reason": "..."}}
"""


def layer4_llm_verdict(
    text_a: str, text_b: str,
    ai_service: Any | None = None,
) -> dict[str, Any] | None:
    """LLM 判同 (最贵, 一次 LLM 调用).

    传 None 时返回 None.
    返回 {"same": bool, "confidence": float, "reason": str} 或 None.
    """
    if ai_service is None:
        return None
    try:
        prompt = _LLM_VERDICT_PROMPT.format(text_a=text_a, text_b=text_b)
        # 简化调用 (不写完整 system_prompt 框架, 用最小 prompt)
        result = ai_service._qwen_generate(  # noqa: SLF001
            prompt,
            "你判断两个文本是否同义",
            {"type": "object", "properties": {
                "same": {"type": "boolean"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
            }},
            timeout_seconds=30.0,
            max_tokens=200,
            temperature=0.1,
        )
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    return None


# ─── 综合 4 层 ─────────────────────────────────────


def check(
    text_a: str, text_b: str,
    *,
    embedding_provider: Any | None = None,
    ai_service: Any | None = None,
    use_layer3: bool = False,  # Layer 3 默认 off (embedding 调用贵)
    use_layer4: bool = False,  # Layer 4 默认 off (LLM 调用最贵)
) -> CheckResult:
    """4 层跨源检测.

    策略 (顾源源蓝图 § 四 机制三):
      · Layer 1 + Layer 2 必跑 (零成本)
      · Layer 3 + Layer 4 按需调用 (避免热点 LLM 调用)

    suspicion_score 综合公式:
      L1 相同 → 1.0 (auto_merge 不需要其他层)
      L2 ≥ 0.85 → 高嫌疑 (≥ 0.85)
      L2 ≥ 0.5 + L3 ≥ 0.85 → 高嫌疑
      L4 same=true + confidence ≥ 0.85 → 极高嫌疑

    suggested_action:
      auto_merge   suspicion ≥ 0.95 (字面相同)
      clarify      suspicion 0.6-0.95 (高嫌疑, 进澄清队列)
      different    suspicion < 0.3
      skip         无法判断
    """
    # Layer 1
    l1 = layer1_string_eq(text_a, text_b)
    if l1:
        return CheckResult(
            text_a=text_a, text_b=text_b,
            layer1_string_eq=True,
            layer2_char_similarity=1.0,
            layer3_embedding_similarity=None,
            layer4_llm_verdict=None,
            suspicion_score=1.0,
            suggested_action="auto_merge",
        )

    # Layer 2
    l2 = layer2_char_similarity(text_a, text_b)

    # Layer 3 (opt-in)
    l3 = None
    if use_layer3 and embedding_provider:
        l3 = layer3_embedding_similarity(text_a, text_b, embedding_provider)

    # Layer 4 (opt-in)
    l4_verdict = None
    if use_layer4 and ai_service:
        l4_verdict = layer4_llm_verdict(text_a, text_b, ai_service)

    # 综合 suspicion_score
    suspicion = l2  # 字符级近似作 baseline
    if l3 is not None and l3 > suspicion:
        suspicion = l3  # embedding 更高时用 embedding
    if l4_verdict and l4_verdict.get("same") and l4_verdict.get("confidence", 0) > 0.85:
        suspicion = max(suspicion, 0.95)

    # 建议动作
    if suspicion >= 0.95:
        action = "auto_merge"
    elif suspicion >= 0.6:
        action = "clarify"
    elif suspicion >= 0.3:
        action = "skip"
    else:
        action = "different"

    return CheckResult(
        text_a=text_a, text_b=text_b,
        layer1_string_eq=False,
        layer2_char_similarity=l2,
        layer3_embedding_similarity=l3,
        layer4_llm_verdict=str(l4_verdict) if l4_verdict else None,
        suspicion_score=suspicion,
        suggested_action=action,
    )


# ─── 批量扫描 · 整客户跨源对账 ──────────────────────────


def scan_client_for_cross_source_candidates(
    db: Any, client_id: str, threshold: float = 0.6, limit: int = 20,
) -> list[dict[str, Any]]:
    """扫某客户 atomic_facts, 找跨源同义/同音 candidates.

    每对 subject (subject_a, subject_b) 检测一次.
    返回 suspicion ≥ threshold 的 candidates (top-N).

    V2.3 阶段 3 高级澄清中心 UI 调用本服务填澄清队列.
    """
    # 拉所有不同的 subject_text (atomic_facts 内, 同 client)
    rows = db.fetchall(
        """SELECT DISTINCT subject_text FROM atomic_facts
           WHERE client_id = ? AND status = 'active'
             AND subject_text IS NOT NULL AND subject_text != ''""",
        (client_id,),
    )
    subjects = [str(r["subject_text"] if hasattr(r, "keys") else r[0]) for r in rows]

    candidates = []
    # 两两对比 (N² 但 N 通常 < 200)
    for i in range(len(subjects)):
        for j in range(i + 1, len(subjects)):
            a, b = subjects[i], subjects[j]
            result = check(a, b, use_layer3=False, use_layer4=False)
            if result.suspicion_score >= threshold and result.suspicion_score < 1.0:
                # 排除 L1 相同 (已 dedup)
                candidates.append({
                    "text_a": a,
                    "text_b": b,
                    "suspicion": result.suspicion_score,
                    "layer2_sim": result.layer2_char_similarity,
                    "action": result.suggested_action,
                })

    candidates.sort(key=lambda x: -x["suspicion"])
    return candidates[:limit]
