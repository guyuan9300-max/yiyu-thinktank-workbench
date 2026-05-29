"""Tests for app.services.freshness_decay."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.freshness_decay import (
    DEFAULT_CONFIG,
    HALF_LIFE_BY_TYPE,
    MIN_FLOOR,
    NEUTRAL_WHEN_UNKNOWN,
    compute_effective_freshness,
    compute_time_decay,
)


NOW = datetime(2026, 5, 12, tzinfo=timezone.utc)


@pytest.mark.unit
class TestComputeTimeDecay:
    def test_pinned_always_full(self) -> None:
        """user_pinned → 不管多老都返回 1.0"""
        very_old = NOW - timedelta(days=10000)
        assert compute_time_decay(very_old, "news", now=NOW, user_pinned=True) == 1.0

    def test_none_created_at_returns_neutral(self) -> None:
        """None 时间 → 中性值"""
        assert compute_time_decay(None, "client_judgment", now=NOW) == NEUTRAL_WHEN_UNKNOWN

    def test_invalid_string_returns_neutral(self) -> None:
        """无法解析的字符串 → 中性值"""
        assert compute_time_decay("not a date", "news", now=NOW) == NEUTRAL_WHEN_UNKNOWN
        assert compute_time_decay("", "news", now=NOW) == NEUTRAL_WHEN_UNKNOWN

    def test_half_life_exact_returns_half(self) -> None:
        """老化恰好等于半衰期 → 鲜度 ≈ 0.5"""
        created = NOW - timedelta(days=90)  # client_judgment 半衰期
        result = compute_time_decay(created, "client_judgment", now=NOW)
        assert abs(result - 0.5) < 0.01

    def test_double_half_life_returns_quarter(self) -> None:
        """2 倍半衰期 → 鲜度 ≈ 0.25"""
        created = NOW - timedelta(days=60)  # news 是 30 天半衰期
        result = compute_time_decay(created, "news", now=NOW)
        assert abs(result - 0.25) < 0.01

    def test_background_no_decay(self) -> None:
        """background 类型 9999 半衰期 → 一年也几乎不衰减"""
        created = NOW - timedelta(days=365)
        result = compute_time_decay(created, "background", now=NOW)
        assert result > 0.97  # 365/9999 ≈ 0.0365 → 0.5^0.0365 ≈ 0.975

    def test_min_floor(self) -> None:
        """衰减到下限以下时被 floor 截住"""
        created = NOW - timedelta(days=10000)
        result = compute_time_decay(created, "news", now=NOW)
        assert result == MIN_FLOOR

    def test_future_dated_treated_as_full(self) -> None:
        """未来时间 → 视作最新 1.0"""
        created = NOW + timedelta(days=30)
        result = compute_time_decay(created, "news", now=NOW)
        assert result == 1.0

    def test_iso_string_input(self) -> None:
        """接受 ISO 字符串"""
        # 大约 90 天前（client_judgment 的半衰期）
        result = compute_time_decay(
            "2026-02-11T00:00:00+00:00",
            "client_judgment",
            now=NOW,
        )
        assert 0.49 < result < 0.51

    def test_iso_string_with_z_suffix(self) -> None:
        """接受 ISO + Z 时区后缀（Python 3.10 兼容性）"""
        result = compute_time_decay(
            "2026-02-11T00:00:00Z",
            "client_judgment",
            now=NOW,
        )
        assert 0.49 < result < 0.51

    def test_date_only_string(self) -> None:
        """接受仅日期字符串"""
        result = compute_time_decay("2026-02-11", "client_judgment", now=NOW)
        # 2026-02-11 → 2026-05-12 ≈ 90 天
        assert 0.49 < result < 0.51

    def test_unknown_doc_type_uses_default(self) -> None:
        """未知类型 → 用 default (90 天半衰期)"""
        created = NOW - timedelta(days=90)
        result = compute_time_decay(created, "totally_made_up_type", now=NOW)
        # default 也是 90 天半衰期 → ≈ 0.5
        assert abs(result - 0.5) < 0.01

    def test_none_doc_type_uses_default(self) -> None:
        created = NOW - timedelta(days=90)
        result = compute_time_decay(created, None, now=NOW)
        assert abs(result - 0.5) < 0.01

    def test_naive_datetime_treated_as_utc(self) -> None:
        """无时区信息的 datetime → 视作 UTC"""
        created = datetime(2026, 2, 11)  # naive
        now_naive = datetime(2026, 5, 12)  # naive
        result = compute_time_decay(created, "client_judgment", now=now_naive)
        assert 0.49 < result < 0.51

    def test_returns_within_bounds(self) -> None:
        """无论什么输入，结果在 [min_floor, 1.0]"""
        for days in [-30, 0, 1, 30, 90, 365, 3650, 36500]:
            for kind in [None, "news", "background", "unknown_xyz"]:
                created = NOW - timedelta(days=days)
                result = compute_time_decay(created, kind, now=NOW)
                assert MIN_FLOOR <= result <= 1.0


@pytest.mark.unit
class TestComputeEffectiveFreshness:
    def test_intrinsic_multiplied_by_decay(self) -> None:
        """intrinsic=0.9 + 半衰期老化 → ≈ 0.45"""
        created = NOW - timedelta(days=90)
        result = compute_effective_freshness(0.9, created, "client_judgment", now=NOW)
        assert abs(result - 0.45) < 0.01

    def test_pinned_returns_intrinsic(self) -> None:
        """pinned 时不衰减，只取 intrinsic"""
        very_old = NOW - timedelta(days=10000)
        result = compute_effective_freshness(0.8, very_old, "news", now=NOW, user_pinned=True)
        assert abs(result - 0.8) < 0.001

    def test_intrinsic_clamped_to_unit_interval(self) -> None:
        """intrinsic 超出 [0,1] 自动夹紧"""
        result_hi = compute_effective_freshness(1.5, NOW, "news", now=NOW)
        assert result_hi <= 1.0
        result_lo = compute_effective_freshness(-0.5, NOW, "news", now=NOW)
        assert result_lo >= MIN_FLOOR

    def test_min_floor_applied(self) -> None:
        """衰减很多 + intrinsic 低 → 仍 ≥ min_floor"""
        very_old = NOW - timedelta(days=10000)
        result = compute_effective_freshness(0.1, very_old, "news", now=NOW)
        assert result >= MIN_FLOOR


@pytest.mark.unit
class TestHalfLifeByType:
    def test_all_keys_positive(self) -> None:
        for key, value in HALF_LIFE_BY_TYPE.items():
            assert value > 0, f"{key} has non-positive half-life {value}"

    def test_default_present(self) -> None:
        assert "default" in HALF_LIFE_BY_TYPE

    def test_background_is_largest(self) -> None:
        """background 应该是衰减最慢的"""
        assert HALF_LIFE_BY_TYPE["background"] == max(HALF_LIFE_BY_TYPE.values())

    def test_news_is_smallest_among_active_types(self) -> None:
        """新闻应当衰减最快（不算 background 这种永久类型）"""
        active = {k: v for k, v in HALF_LIFE_BY_TYPE.items() if k != "background"}
        assert HALF_LIFE_BY_TYPE["news"] == min(active.values())
