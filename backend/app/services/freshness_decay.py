"""Time-based freshness decay for evidence and memory items.

设计意图：
- 仓内多处使用 ``freshness`` 字段，但此前要么是静态常量（写入时的 intrinsic
  confidence），要么是粗糙的"年份正则 + 线性"启发式。
- 本模块只负责**时间衰减因子**：给定文档 created_at + 类型，输出 ``[min_floor, 1.0]``
  之间的浮点数。
- 由调用方决定如何把它与 intrinsic confidence 合成（典型做法是相乘）。

迭代 1 引入；后续迭代可扩展 ``HALF_LIFE_BY_TYPE``、引入 ``user_pinned`` UI、
为 memory_facts 接入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Final, Mapping

# ---- 半衰期表 ------------------------------------------------------------

# 单位：天。越大 = 衰减越慢。
# - 新闻/动态：1 个月衰一半
# - 客户判断/会议纪要：3 个月衰一半（陪伴客户的高频更新周期）
# - 证据材料/战略文档：6 个月（中长期参考）
# - 政策文档：1 年（参考性长）
# - 背景资料：9999 ≈ 永不衰减（用户主动标记为历史背景）
HALF_LIFE_BY_TYPE: Final[Mapping[str, float]] = MappingProxyType({
    "news": 30.0,
    "client_judgment": 90.0,
    "meeting_minutes": 90.0,
    "meeting_note": 90.0,
    "meeting_decision": 90.0,
    "evidence_artifact": 180.0,
    "strategy_doc": 180.0,
    "policy_doc": 365.0,
    "background": 9999.0,
    "default": 90.0,
})

# 鲜度下限——避免任何资料完全归零失踪。
MIN_FLOOR: Final[float] = 0.05

# created_at 不可用时的中性值——既不优待也不打压。
NEUTRAL_WHEN_UNKNOWN: Final[float] = 0.5


# ---- 类型 ----------------------------------------------------------------


@dataclass(frozen=True)
class DecayConfig:
    """暴露给上层调参用的配置（保留未来扩展空间）。"""

    # 用 default_factory 避开 dataclass "mutable default" 检查；
    # 实际指向的是 MappingProxyType（只读视图），不可修改。
    half_life_by_type: Mapping[str, float] = field(
        default_factory=lambda: HALF_LIFE_BY_TYPE
    )
    min_floor: float = MIN_FLOOR
    neutral_when_unknown: float = NEUTRAL_WHEN_UNKNOWN


DEFAULT_CONFIG: Final[DecayConfig] = DecayConfig()


# ---- 主函数 --------------------------------------------------------------


def compute_time_decay(
    created_at: datetime | str | None,
    doc_type: str | None = None,
    *,
    now: datetime | None = None,
    user_pinned: bool = False,
    config: DecayConfig = DEFAULT_CONFIG,
) -> float:
    """计算文档的时间衰减因子。

    Args:
        created_at: 文档创建时间。可以是 ``datetime``、ISO 8601 字符串、或
            ``None``（未知时间）。
        doc_type: 文档类型键，用于查 ``HALF_LIFE_BY_TYPE``。``None`` 或未知
            类型 → 使用 ``default``。
        now: 计算"现在"用的时间，默认 ``datetime.now(timezone.utc)``。注入
            参数便于测试。
        user_pinned: 用户主动 pin 的资料 → 直接返回 ``1.0``。
        config: 可注入的衰减配置；默认使用全局 ``DEFAULT_CONFIG``。

    Returns:
        ``[min_floor, 1.0]`` 之间的浮点数。

        - ``user_pinned=True`` → 始终 ``1.0``
        - ``created_at is None`` → ``neutral_when_unknown``（默认 0.5）
        - ``created_at`` 在未来 → ``1.0``（视作最新）
        - 其他 → ``max(0.5 ** (age_days / half_life), min_floor)``

    Examples:
        >>> from datetime import datetime, timedelta, timezone
        >>> now = datetime(2026, 5, 12, tzinfo=timezone.utc)
        >>> created = now - timedelta(days=90)
        >>> abs(compute_time_decay(created, "client_judgment", now=now) - 0.5) < 0.01
        True
    """
    if user_pinned:
        return 1.0

    if created_at is None:
        return config.neutral_when_unknown

    parsed = _coerce_datetime(created_at)
    if parsed is None:
        return config.neutral_when_unknown

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    age_seconds = (now - parsed).total_seconds()
    if age_seconds <= 0:
        # 未来时间或刚刚创建 → 满鲜度
        return 1.0

    age_days = age_seconds / 86400.0
    half_life = config.half_life_by_type.get(
        doc_type or "default",
        config.half_life_by_type["default"],
    )
    if half_life <= 0:
        return config.min_floor

    decay = 0.5 ** (age_days / half_life)
    return max(decay, config.min_floor)


def compute_effective_freshness(
    intrinsic: float,
    created_at: datetime | str | None,
    doc_type: str | None = None,
    *,
    now: datetime | None = None,
    user_pinned: bool = False,
    config: DecayConfig = DEFAULT_CONFIG,
) -> float:
    """合成最终鲜度：intrinsic × 时间衰减，并按 min_floor 截断。

    用于调用方既想保留写入时的 intrinsic confidence，又想叠加时间衰减的
    场景。

    Args:
        intrinsic: 写入时的内禀置信度（如 memory_foundation 里的 0.9/0.92 等）。
        其他参数同 :func:`compute_time_decay`。

    Returns:
        ``[min_floor, intrinsic]`` 之间的浮点数。
    """
    intrinsic = max(0.0, min(1.0, float(intrinsic)))
    decay = compute_time_decay(
        created_at,
        doc_type,
        now=now,
        user_pinned=user_pinned,
        config=config,
    )
    return max(intrinsic * decay, config.min_floor)


# ---- 内部工具 ------------------------------------------------------------


def _coerce_datetime(value: datetime | str) -> datetime | None:
    """容错地把输入转 ``datetime``。失败返回 ``None``。"""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # 兼容 "Z" 后缀（Python 3.11 起 fromisoformat 支持，但 3.10 不支持）
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        # 兜底：仅有日期 "YYYY-MM-DD"
        try:
            return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


__all__ = [
    "HALF_LIFE_BY_TYPE",
    "MIN_FLOOR",
    "NEUTRAL_WHEN_UNKNOWN",
    "DecayConfig",
    "DEFAULT_CONFIG",
    "compute_time_decay",
    "compute_effective_freshness",
]
