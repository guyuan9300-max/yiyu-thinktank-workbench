"""[DEPRECATED 2026-05-22] V2.1 实验仓库 NarrativeKernel 8 段叙事 — 已废弃

================================================================================
DO NOT IMPORT THIS MODULE. 任何 from app.services.narrative_kernel import ... 都应该改为
主仓库的 narrative_generator + narrative_collector (产品手册 §03 钦定 6 段叙事).
================================================================================

废弃原因(顾源源 5/22 4 维度评估发现):

1. **段数冲突**: V2.1 此模块设计 8 段(identity / main_lines / recent_changes /
   risks / our_collab / open_questions 等), 跟产品手册 §03 钦定的 6 段不一致:
        essence / cooperation / business_intro / people / timeline / next_steps

2. **重复造轮子**: 主仓库 backend/app/services/narrative_generator.py (1156 行) +
   narrative_collector.py 已完整实现 6 段叙事 + 现成表 collector
   (拉 clients/risk_signals/tasks/weekly_review_task_entries/meetings/glossary 等
   13 张现成表). 本模块只是"从 atomic_facts 一张表分组"的 deterministic 列事实,
   不是真正的叙事。

3. **不接 broadcast**: 主仓库 data_center_broadcast.py 是 "一处写全局刷" 的核心机制,
   本模块完全没接, 用户在 app 里看不到 LLM 编排的叙事。

替代方案 — 用主仓库 narrative_generator:

    from app.services.narrative_generator import generate_narrative
    from app.services.narrative_collector import NarrativeCollector

    collector = NarrativeCollector(db)
    bundle = collector.collect_for_client(client_id)   # 拉 13 张现成表
    narrative = generate_narrative(bundle, ai_service)  # LLM 编排出 6 段

详细决策见:
- docs/V2.2_NEW_PLAN_20260522.md (新计划 6 阶段)
- docs/V2.2_ASSESSMENT_4D_20260522.md (4 维度评估)
- docs/V2.2_PRODUCT_MANUAL_FULL_TEXT.md §03 (产品手册官方 6 段定义)

原 V2.1 实现(13957 字, deterministic 列事实)备份在:
    backend/app/services/narrative_kernel.py.DEPRECATED

任何引用本模块的代码(B AI 在 5/22 阶段 0 清理):
- backend/app/api/full_narrative_router.py
- backend/tests/test_v22_full_narrative_endpoint.py
"""
from __future__ import annotations


def __getattr__(name: str):
    """Module-level __getattr__ — 任何 from narrative_kernel import X 都抛 ImportError."""
    raise ImportError(
        f"narrative_kernel.{name} 已废弃 (V2.1 8 段叙事, 跟产品手册 §03 钦定 6 段冲突). "
        f"改用主仓库 backend/app/services/narrative_generator.py + narrative_collector.py. "
        f"详见 docs/V2.2_NEW_PLAN_20260522.md 阶段 0/1/2."
    )
