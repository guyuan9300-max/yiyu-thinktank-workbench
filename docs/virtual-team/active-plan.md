# Active Plan v5

## Phase

当前处于：
- `Session 003 + Loop 6: Implementation Ready`

本轮已经完成 Session 003 的 docs-first 收口，进入实现前放行状态。

## Current Phase Goal

1. 锁定 Session 003 已批准的 P0 范围
2. 只允许进入最小可辩护改动实现
3. 避免在实现阶段重新发散回抽象改版

## Approved Scope

### A. 真源收口
- 明确以下对象是当前主对象：
  - `OrganizationNotebookSnapshot`
  - `EventLineMemorySnapshot`
  - `MemoryFact`
  - `ClarificationRecord`
  - `EventLineContextBundleRecord`
  - `EventLineJudgmentRecord`
  - `TaskContextPreviewRecord`
  - `WeeklyReviewAnalysisRecord`

### B. Judgment Contract 收口
- 统一收口这些公共字段：
  - `coverageScore`
  - `confidenceScore`
  - `safeOutputMode`
  - `judgmentVersion`
  - `bundleFingerprint`
  - `missingSlots`
  - `backgroundSources`
  - `predictionReadiness`

### C. 低完整度降级输出
- 当 evidence / memory 不足时，只允许：
  - `needs_input`
  - `summary_only`
- 禁止默认给出 full judgment
- 但缺会议、缺附件、缺支持请求、缺事件线等增强输入时，默认仍要先做保守计算，不得把“缺失项”前置成主结果

### D. 最小预处理
- 对会议与附件补最小摘要预处理
- 不重做 knowledge engine
- 不重做第二套 chunk pipeline

### E. 首屏骨架
- 顶部判断状态条
- 信号卡前置
- 动作卡面板
- 日历信号条
- 紧凑的判断边界区
- 证据抽屉

### F. Calendar Signal Bar
- 关键任务未入历
- 本周时间承接不足
- 会议与任务冲突
- 本周重点未形成时间块

### G. 角色排序
- 个人排序
- leader 排序
- manager 兼容层

## Explicitly Out of Scope

本轮不做：
- 新 envelope 真源
- 新的 workgroup 真源
- 全量战略陪伴重写
- 客户工作台页面大改
- 第二套知识底座

## Open Conflicts

1. `GET /api/v1/tasks/judgment-workspace` 是否必须作为单独 endpoint 实现  
当前裁决：允许独立 endpoint，也允许先以内联装配入口起步，但都只能是 transport-only projection。

2. `projectContext` 是否立即下线  
当前裁决：不立即下线，先从主判断链降级为辅助背景。

3. 战略陪伴是否本轮同步改  
当前裁决：只做兼容，不做大改。先把任务详情与周判断收口。

## Next Implementation Batch

批准工程实现下一轮只做：
1. 新增或抽出 transport-only judgment workspace projection 装配入口
2. 复用现有真源装配：
   - `TaskContextPreviewRecord`
   - `WeeklyReviewAnalysisRecord`
   - `EventLineCompletenessRecord`
   - `ReviewActionCardRecord`
   - `ReviewDashboardDrillTargetResponse`
3. 补 `/api/v1/reviews/dashboard/drill-target` 的 `task` target support
4. 明确并落地 6 个 transport-only contracts：
   - `TaskCalendarJudgmentWorkspace`
   - `TaskCalendarJudgmentStatusStrip`
   - `TaskCalendarSignalCard`
   - `TaskCalendarActionCard`
   - `TaskCalendarEvidenceDrawerPayload`
   - `TaskCalendarNotIncludedItem / TaskCalendarDegradedItem / TaskCalendarSignalBar`
5. 把 `TaskOrgContextPanel` 的前端 judgment heuristics 全部降级为 fallback-only
6. 在任务列表 / 周判断 / 月历页接入首屏状态条、signal cards、action cards、boundary strip、calendar signal bar 的最小骨架
7. 以 `docs/session-003/task-calendar-release-gates.md` 作为实现后第一轮 gate 检查表
