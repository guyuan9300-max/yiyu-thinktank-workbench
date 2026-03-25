# Session 003
## 日历与任务判断系统：P0 Judgment / Data Contract

## 0. 结论先行

P0 不新增新的 judgment 真源，不再包一层持久化 envelope。  
P0 只允许：

1. 继续以现有后端对象为主真源
2. 新增一层 **transport-only projection**
3. 让任务详情 AI 面板、周判断、calendar signal bar、未纳入判断/降级区、动作卡，共用同一套 judgment/data contract

推荐路线：
- 保留当前真源：
  - `EventLineContextBundleRecord`
  - `EventLineJudgmentRecord`
  - `EventLineSummaryCardRecord`
  - `EventLineRiskCardRecord`
  - `EventLineOpportunityCardRecord`
  - `EventLineCompletenessRecord`
  - `TrendSignalRecord`
  - `ReviewActionCardRecord`
  - `TaskContextPreviewRecord`
  - `WeeklyReviewAnalysisRecord`
- 新增一个 **请求时组装** 的 projection endpoint：
  - `GET /api/v1/tasks/judgment-workspace`
- 这个 endpoint 只返回首屏 judgment workspace，不写表、不落库、不形成第二真源

### 0.1 本轮新增的计算原则

本轮不按“缺多少资料”组织页面，而按“在最小必需输入下能算到什么”组织页面。

#### 最小必需输入集

P0 只要求这 5 类输入作为默认主输入：

1. `整个项目 / 业务的核心资料与介绍`
2. `整个部门 / 整个机构的季度主要计划`
3. `任务标题`
4. `任务说明`
5. `任务复盘资料`

#### 可选增强输入

这些输入会提高判断质量，但缺失时默认不阻塞输出：
- 会议纪要 / action items
- 附件摘要
- 支持请求
- 事件线记忆
- 日历时间块

#### 设计原则

- 先出保守判断，再提示边界
- 不因可选增强输入缺失就直接打成 `needs_input`
- 不把“缺失列表”做成首屏主角

---

## 1. 当前必须共用的后端对象与字段

### 1.1 任务详情 AI 面板

当前真实接口：
- `GET /api/v1/tasks/{task_id}/context-preview`

当前真实对象：
- `TaskContextPreviewRecord`
- 内嵌：
  - `EventLineContextBundleRecord`
  - `EventLineJudgmentRecord`

P0 主读字段：

#### 来自 `TaskContextPreviewRecord`
- `taskId`
- `judgmentVersion`
- `bundleFingerprint`
- `coverageScore`
- `confidenceScore`
- `safeOutputMode`
- `publishState`
- `summaryChips`
- `readiness`

#### 来自 `contextBundle`
- `eventLineId`
- `lineName`
- `summary`
- `intent`
- `currentWork`
- `currentBlocker`
- `recentDecision`
- `nextStep`
- `recentProgress`
- `recentFacts`
- `taskFacts`
- `meetingFacts`
- `attachmentFacts`
- `clarificationFacts`
- `evidenceRefs`
- `trendSignals`
- `readiness`

#### 来自 `judgment`
- `judgmentVersion`
- `bundleFingerprint`
- `coverageScore`
- `confidenceScore`
- `safeOutputMode`
- `whatHappened`
- `whyItMatters`
- `coreBlocker`
- `blockerType`
- `evidenceSummary`
- `managerImplication`
- `nextWeekFocus`
- `minimumAction`
- `riskIfIgnored`
- `opportunityIfAmplified`
- `evidenceRefs`
- `target`

P0 约束：
- 任务详情 AI 面板以 `TaskContextPreviewRecord` 为唯一主判断输入
- `Task.projectContext`、`Task.memoryHints`、`Task.backgroundReadiness` 只作辅助显示，不再作为主判断来源
- 如果 `safeOutputMode != full_judgment`，前台必须显示边界说明，但仍应优先展示可落地的保守判断与动作

---

### 1.2 周判断

当前真实聚合对象：
- `WeeklyReviewAnalysisRecord`

当前真实前端消费：
- `WeeklyReviewAnalysis`
- `WeeklyReviewAnalysisPanel`

P0 主读字段：

#### 首屏信号层
- `eventLineSummaries`
- `riskCards`
- `opportunityCards`
- `trendSignals`

#### 降级/缺口层
- `eventLineCompleteness`

#### 判断层
- `eventLineJudgments`
- `eventLineContextBundles`

#### 事实层
- `metricCards`
- `confirmedFacts`
- `evidenceWeights`

#### 行动层
- `nextWeekFocus`

P0 约束：
- 周判断首屏不再自己组织另一套判断语义
- 事件线摘要、风险、机会、缺口、趋势都必须直接来自 `WeeklyReviewAnalysisRecord`
- `WeeklyReviewAnalysisPanel` 只负责消费这些对象，不再成为独立 judgment producer

---

### 1.3 Calendar Signal Bar

P0 不新建持久化对象。  
Calendar signal bar 必须从现有对象实时计算。

P0 计算输入：

#### 任务输入
来自 `Task`
- `id`
- `title`
- `status`
- `priority`
- `dueDate`
- `ddl`
- `durationMinutes`
- `sourceType`
- `eventLineId`
- `currentBlocker`
- `nextAction`
- `recentDecision`
- `evidenceCount`
- `orgContext.needsReview`
- `orgContext.approvalState`
- `orgContext.blockedAtStep`

#### judgment 输入
来自 `TaskContextPreviewRecord`
- `safeOutputMode`
- `coverageScore`
- `confidenceScore`
- `summaryChips`
- `readiness`
- `contextBundle.currentBlocker`
- `contextBundle.nextStep`
- `judgment.minimumAction`
- `judgment.coreBlocker`

#### 周判断输入
来自 `WeeklyReviewAnalysisRecord`
- `nextWeekFocus`
- `eventLineSummaries`
- `riskCards`
- `trendSignals`

#### 会议输入
来自 `MeetingSummary` / `MeetingDetail`
- `id`
- `scheduledAt`
- `actionItems`

P0 只允许算这 5 类信号：
1. `criticalTasksWithoutCalendar`
2. `meetingFollowupsStillOpen`
3. `reviewPendingTasks`
4. `overdueTasksStillUnscheduled`
5. `unscheduledNextWeekFocusCount`

其中“已上历”的最小判断口径，必须与当前真实日历页一致：
- 使用 `TaskCalendarView.tsx` 的现有规则
- 任务有 `dueDate` 且 `splitTaskDueDateTime(task.dueDate).time` 可解析出时分，才算真正进入时间块
- 只有日期、没有时间的任务，不算“已上历”，只算“挂了日期未时间承接”

---

### 1.4 判断边界区

P0 来源不新建，直接取现有对象：

#### 未纳入判断
来自：
- `Task`
- `TaskContextPreviewRecord` 是否存在
- `Task.eventLineId`

判定条件收紧为：
- 任务标题不可判读
- 任务说明为空，且没有复盘资料
- 同时缺 `项目/业务核心背景` 与 `部门/机构季度计划`

说明：
- 不再因为缺事件线、缺附件、缺会议就直接判为未纳入
- 这些属于“增强输入不足”，默认进入保守计算

#### 降级处理
来自：
- `TaskContextPreviewRecord.safeOutputMode`
- `EventLineCompletenessRecord.status`
- `EventLineCompletenessRecord.missingSlots`
- `TrendSignalRecord.signalType = thin_evidence`

判定条件：
- `safeOutputMode = summary_only`
- `safeOutputMode = needs_input`
- `EventLineCompletenessRecord.status in ('insufficient', 'summary_ready')`

解释规则：
- `summary_only`
  - 代表已经根据最小必需输入集给出保守判断
  - 但没有足够证据支撑强判断
- `needs_input`
  - 只在最小必需输入集本身过弱时使用
  - 不是“附件/会议/支持请求没补齐”就触发

---

### 1.5 动作卡

当前真实动作对象：
- `ReviewActionCardRecord`

当前真实可闭环执行结果对象：
- `ReviewActionExecutionResult`

当前真实闭环能力上限：
- `objectType: 'task' | 'support_request' | 'meeting'`

所以 P0 优先接这 3 类动作：
1. `task`
2. `support_request`
3. `meeting`

不优先做：
- `resource_request`
- `one_on_one`

原因：
- 这三类已经有执行结果 contract
- 能直接形成“去做 / 去求助 / 去开会/落会议动作”的闭环
- 最贴合 Session 002 的主问题：不是更会分析，而是更会转动作

---

## 2. 哪些旧 heuristics 仍在前端，必须降级为 fallback

### 2.1 当前最核心的前端 heuristics 热区

文件：
- `src/renderer/components/tasks/TaskOrgContextPanel.tsx`

当前仍在直接合成 judgment 文案的函数：
- `inferTaskMode`
- `inferBusinessCategory`
- `buildModeFocus`
- `buildModeRisk`
- `buildModeOpportunity`
- `buildModeAction`
- `buildContextRisk`
- `buildOpportunity`
- `buildInsights`

问题：
- 这些函数目前不是纯展示 fallback，而是在 `contextPreview` 不完整时直接生产“当前重点 / 当前卡点 / 可放大点 / 先做什么”
- 这会让任务详情 AI 面板继续形成一套前端判断系统
- 与 `WeeklyReviewAnalysisRecord`、`EventLineJudgmentRecord` 的后端判断发生漂移

P0 裁决：
- 这些函数全部降级为 fallback-only
- 只允许在以下条件下触发：
  1. `TaskContextPreviewRecord` 不存在
  2. `safeOutputMode = needs_input`
  3. `safeOutputMode = summary_only`
  4. `contextBundle` 或 `judgment` 缺关键字段
- 触发时 UI 必须显式显示：
  - `fallback`
  - `summary_only`
  - `needs_input`
  之一

### 2.2 仍可保留但不得进入 judgment 主链的 heuristics

文件：
- `src/renderer/App.tsx`

当前仍存在的任务关联辅助 heuristics：
- `inferPersonalTaskKeywordLabels`
- `inferTaskPriority`
- `inferTaskClient`
- `inferTaskEventLine`
- `inferTaskProjectModule`
- `inferTaskProjectFlow`

P0 裁决：
- 这些函数只允许存在于“任务创建/编辑建议”
- 不允许进入：
  - 任务详情 AI 面板
  - 周判断
  - calendar signal bar
  - 顶部判断状态条
  - 动作卡

---

## 3. P0 最小 contract

P0 推荐新增以下 **transport-only** 类型：

### 3.1 `TaskCalendarJudgmentWorkspace`

用途：
- 任务列表首屏
- 周判断首屏
- 日历 signal 入口

字段：
- `viewerRole`
- `judgmentVersion`
- `bundleFingerprint`
- `statusStrip`
- `signalCards`
- `actionCards`
- `degradedItems`
- `notIncludedItems`
- `calendarSignalBar`
- `updatedAt`

说明：
- 这是 projection response，不落库
- 主入口建议新增：
  - `GET /api/v1/tasks/judgment-workspace?viewerRole=employee|department_lead|admin`

### 3.2 `TaskCalendarJudgmentStatusStrip`

字段：
- `includedTaskCount`
- `notIncludedTaskCount`
- `degradedTaskCount`
- `highRiskTaskCount`
- `meetingFollowupOpenCount`
- `calendarCoverageGapCount`
- `updatedAt`
- `safeOutputMode`

来源：
- `Task[]`
- `TaskContextPreviewRecord[]`
- `WeeklyReviewAnalysisRecord`

### 3.3 `TaskCalendarSignalCard`

字段：
- `id`
- `kind`
  - `main_progress`
  - `largest_blocker`
  - `high_risk`
  - `calendar_gap`
  - `meeting_closure_gap`
  - `support_debt`
  - `approval_bottleneck`
  - `next_week_focus`
- `role`
- `title`
- `statement`
- `whyNow`
- `safeOutputMode`
- `coverageScore`
- `confidenceScore`
- `target`
- `evidenceRefs`

主映射：
- `main_progress` -> `EventLineSummaryCardRecord`
- `largest_blocker` -> `EventLineJudgmentRecord.coreBlocker`
- `high_risk` -> `EventLineRiskCardRecord`
- `calendar_gap` -> transport 计算项
- `meeting_closure_gap` -> transport 计算项
- `support_debt` -> `SupportRequestRecord` 聚合项
- `approval_bottleneck` -> `Task.orgContext` 聚合项
- `next_week_focus` -> `WeeklyReviewAnalysisRecord.nextWeekFocus`

### 3.4 `TaskCalendarActionCard`

字段：
- `id`
- `actionType`
  - `task`
  - `support_request`
  - `meeting`
- `title`
- `whyNow`
- `payload`
- `ownerRole`
- `target`
- `evidenceRefs`
- `source`
  - `review_action_card`
  - `judgment_minimum_action`
  - `risk_suggested_action`
  - `calendar_gap_fix`

P0 来源顺序：
1. `ReviewActionCardRecord`
2. `EventLineJudgmentRecord.minimumAction`
3. `EventLineRiskCardRecord.suggestedAction`
4. `calendar signal` 派生动作

### 3.5 `TaskCalendarEvidenceDrawerPayload`

用途：
- 每张信号卡
- 每张动作卡
- 降级项

字段：
- `target`
- `contextBundle?`
- `judgment?`
- `eventLineMemory?`
- `tasks`
- `meetings`
- `supportRequests`
- `attachments`
- `evidenceRefs`
- `missingSlots`
- `backgroundSources`

主来源：
- 复用现有：
  - `GET /api/v1/reviews/dashboard/drill-target`
  - `GET /api/v1/event-lines/{event_line_id}/context-bundle`
  - `GET /api/v1/event-lines/{event_line_id}/memory`

P0 技术前置：
- `ReviewDashboardCardTarget.targetType` 在 shared type 里已经支持 `task`
- 但后端 `/api/v1/reviews/dashboard/drill-target` 目前不支持 `task`
- P0 必须二选一：
  1. 给 backend 补 `task` target support
  2. 或者所有 P0 卡片先只挂 `event_line` / `task_view`

推荐路线：
- 补 `task` target support
- 因为 shared type 已经声明了 `task`，现在后端缺的是实现，不是设计

### 3.6 `TaskCalendarNotIncludedItem`

字段：
- `taskId`
- `taskTitle`
- `reasonCode`
  - `missing_event_line`
  - `missing_context_preview`
  - `missing_owner_scope`
- `reasonText`
- `recommendedActionType`
  - `bind_event_line`
  - `fill_context`
  - `keep_as_plain_task`
- `target`

### 3.7 `TaskCalendarDegradedItem`

字段：
- `taskId`
- `taskTitle`
- `eventLineId?`
- `safeOutputMode`
- `reasonCode`
  - `thin_evidence`
  - `missing_slot`
  - `summary_only`
  - `needs_input`
- `missingSlots`
- `backgroundSources`
- `recommendedFix`
  - `upload_docs`
  - `clarify_now`
  - `wait_for_more_trace`
- `target`
- `evidenceRefs`

### 3.8 `TaskCalendarSignalBar`

字段：
- `criticalTasksWithoutCalendar`
- `meetingFollowupsStillOpen`
- `reviewPendingTasks`
- `overdueTasksStillUnscheduled`
- `unscheduledNextWeekFocusCount`
- `recommendedMoves`

---

## 4. Calendar signal bar 的计算输入

### 4.1 `criticalTasksWithoutCalendar`

输入：
- `Task.status != done`
- `Task.priority == high`
- `Task.dueDate` 存在
- `splitTaskDueDateTime(task.dueDate).time` 为空

加权增强：
- 若 `TaskContextPreviewRecord.readiness = high`
- 或 `EventLineRiskCardRecord.probability = high`
- 则优先进入该计数

### 4.2 `meetingFollowupsStillOpen`

输入：
- `Task.sourceType == meeting`
- `Task.status != done`

增强来源：
- `MeetingDetail.actionItems`
- `MeetingSummary.scheduledAt`

说明：
- 这是当前最稳的最小口径
- 不需要先做复杂 meeting-task graph 才能上线

### 4.3 `reviewPendingTasks`

输入：
- `Task.orgContext.needsReview == true`
- 或 `Task.orgContext.approvalState == pending`
- 或 `Task.orgContext.blockedAtStep` 非空

### 4.4 `overdueTasksStillUnscheduled`

输入：
- `Task.status != done`
- `Task` 逾期
- 且 `splitTaskDueDateTime(task.dueDate).time` 为空

### 4.5 `unscheduledNextWeekFocusCount`

输入：
- `WeeklyReviewAnalysisRecord.nextWeekFocus`
- `EventLineJudgmentRecord.nextWeekFocus`
- 映射到关联 `Task`
- 这些任务没有具体时间块

说明：
- P0 允许是 conservative match
- 不要求先做复杂 NLP 对齐
- 只要优先使用现有 `eventLineId / target / relatedTaskIds`

---

## 5. 推荐路线与风险

## 推荐路线

### Route A（推荐）
1. 保持现有 judgment 真源不动
2. 新增 `TaskCalendarJudgmentWorkspace` projection endpoint
3. 让：
   - 任务详情 AI 面板继续读 `/tasks/{id}/context-preview`
   - 周判断继续读 `WeeklyReviewAnalysisRecord`
   - 首屏 judgment workspace 读新的 projection endpoint
4. 同时把 `TaskOrgContextPanel` heuristics 降为 fallback-only

优点：
- 改动小
- 不动真源
- 首屏可以一次返回状态条、signal cards、degraded zone、action cards、calendar bar
- 任务详情和周判断仍各自保留现有入口

### Route B（不推荐）
把 `WeeklyReviewAnalysisRecord` 继续往上包一层 persisted envelope，再让任务详情也读它。

放弃理由：
- 会新造一个更像真源的 envelope
- 任务详情的 task-scoped preview 反而会被稀释
- 双判断源风险更高

## 当前最关键的 5 个风险
1. `TaskOrgContextPanel` heuristics 继续主导任务详情文案，导致 task detail 与 weekly judgment 说两套话
2. `ReviewDashboardCardTarget.targetType` 已支持 `task`，但 backend drill-target 尚未支持 `task`，证据抽屉无法闭环到任务卡
3. calendar signal bar 若只看 `dueDate`、不看是否有具体 time block，会把“挂了日期”误判成“已上历”
4. 会议当前只有 `scheduledAt`，没有完整 duration，`tasksCollidingWithMeetings` 只能做弱信号，P0 不应过度承诺精确碰撞检测
5. `projectContext` 仍在多个前端面板里作为可说服文本来源，如果不显式降级，会继续污染 judgment chain
