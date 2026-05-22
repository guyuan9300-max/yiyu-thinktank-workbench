"""[DEPRECATED 2026-05-22] V2.1 NarrativeKernel 8 段单元测试 — 已废弃

NarrativeKernel 跟产品手册 §03 6 段叙事冲突, 主仓库 narrative_generator 已实现.
全部测试 skip. 原 18 个测试备份在: backend/tests/test_v22_narrative_kernel.py.DEPRECATED

详细决策: docs/V2.2_NEW_PLAN_20260522.md 阶段 0
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="NarrativeKernel 8 段已废弃 (跟产品手册 §03 6 段冲突). 改用主仓库 narrative_generator."
)


def test_deprecated_placeholder():
    """占位测试 — pytest collect 时不报错, 真实测试 skip."""
    pass
