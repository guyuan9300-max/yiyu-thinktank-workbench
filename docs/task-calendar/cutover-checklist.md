# Cutover Checklist: 理解优先主链

## 新主链已就位

| 组件 | 文件 | 状态 |
|------|------|------|
| 最小输入模型文档 | `docs/task-calendar/minimal-input-v1.md` | DONE |
| 字段审计文档 | `docs/task-calendar/minimal-input-field-audit.md` | DONE |
| UnderstandingSnapshotV1 类型 | `src/shared/types.ts` | DONE |
| UnderstandingSnapshotV1 后端模型 | `backend/app/models.py` | DONE |
| basic builder | `backend/app/services/understanding_builder.py` | DONE (9/9 tests) |
| enhanced builder | `backend/app/services/understanding_builder.py` | DONE (6/6 tests) |
| 测试论坛A 联合样本验证 | `backend/tests/test_cffc_sample.py` | DONE (7/7 tests) |
| UnderstandingPanel 前端组件 | `src/renderer/components/tasks/UnderstandingPanel.tsx` | DONE |
| 任务理解 API | `GET /api/v1/tasks/{id}/understanding` | DONE |
| 前端 API 调用 | `src/renderer/lib/api.ts → getTaskUnderstanding()` | DONE |
| 任务详情页面板替换 | `App.tsx` (line ~8302) | DONE |
| 周复盘首屏改造 | `WeeklyReviewSummaryPanel.tsx` | DONE |
| 角色透镜（同构排序） | `WeeklyReviewSummaryPanel.tsx` | DONE |

## 旧主链停用状态

| 旧组件 | 文件 | 状态 | 说明 |
|--------|------|------|------|
| HierarchyReportCard 独立报告渲染 | `HierarchyReportCard.tsx` | 停用 | 不再在 SummaryPanel 中渲染完整报告卡，改用 ReportSignals |
| 绿色 banner "我的本周总结" | 原 WeeklyReviewSummaryPanel | 删除 | 替换为理解优先的"本周理解"首屏 |
| 双壳并列渲染 | App.tsx | 合并 | WeeklyReviewSummaryPanel 移入 collect 阶段内部 |
| ExecutiveReviewPanel | 已删除 | 清理 | 孤儿组件，功能已由 SummaryPanel 吸收 |
| AgentWorklogPanel | 已删除 | 清理 | 孤儿组件，功能已由 AgentDigest + AgentExecution 替代 |
| 旧 AI 上下文面板（sky-100 border） | App.tsx | 替换 | 由 UnderstandingPanel 替代 |

## 核心行为验证

| 检查项 | 预期 | 测试 |
|--------|------|------|
| basic 模式只靠最小输入能出结果 | 4 项主输出非空 | test_understanding_basic.py ✅ |
| 永远不返回"无法判断" | whatIsThis/whyItMatters 不含"无法判断" | test_never_returns_cannot_judge ✅ |
| basic 不生成假建议 | optionalAdvice 为 null | test_no_false_advice_in_basic ✅ |
| enhanced 有更多可用源 | available count > basic | test_enhanced_mode_deeper_understanding ✅ |
| enhanced 也不硬写建议 | 无 LLM 时 optionalAdvice 为 null | test_no_false_advice_without_llm ✅ |
| 输出不先写风险 | whatIsThis 不含"风险/阻碍/建议" | test_basic_never_starts_with_risk ✅ |
| 测试论坛A 识别客户 | 输出含"测试论坛A" | test_basic_mode_mentions_cffc ✅ |
| 任务详情页读同一套理解对象 | UnderstandingPanel 渲染 | 前端已切换 |
| 周复盘首屏不再是旧报告头 | 首屏显示"本周理解"而非"周判断视角" | WeeklyReviewSummaryPanel 已改 |

## 模式说明

| 模式 | 输入 | 输出 |
|------|------|------|
| basic | 益语背景卡、客户背景卡、季度主线卡、任务标题、任务说明、复盘资料 | whatIsThis + whyItMatters + progressNow + unknowns |
| enhanced | basic + 事件线记忆 + 会议 + 支持请求 | basic 4 项 + optionalAdvice（仅证据充分时） |

## 为什么系统先做理解，再做建议

系统的核心优势不是生成更多建议，而是持续记住上下文，并判断这件事在整条合作线和更大业务版图中的位置。所有分析应优先回答：这是什么事、为什么重要、现在推进到哪、还缺什么理解；只有在信息足够时，才进一步升级为风险、动作和管理建议。
