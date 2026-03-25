# Reality Audit v2

## Scope

本轮审计覆盖两件事：
1. 日历与任务判断系统的真实代码与真实链路
2. 当前虚拟项目组的角色设计是否贴近真实软件团队

审计依据：
- `backend/app/models.py`
- `cloud_backend/app/models.py`
- `backend/app/main.py`
- `backend/app/services/review_analysis.py`
- `backend/app/services/memory_foundation.py`
- `src/shared/types.ts`
- `src/renderer/components/tasks/*`
- `src/renderer/components/strategic_accompaniment/StrategicAccompanimentShell.tsx`
- `.codex/agents/*`
- `docs/virtual-team/*`

## 1. 当前真实对象

### 1.1 已经存在的底座快照与事实池

在 `backend/app/models.py` 中，当前已经存在：
- `OrganizationNotebookSnapshot`
- `EventLineMemorySnapshot`
- `MemoryFact`
- `ClarificationRecord`
- `MemoryStatus`
- `BackgroundReadiness`

在 `backend/app/db.py` 中，当前已经存在对应持久化表：
- `organization_notebook_snapshots`
- `event_line_memory_snapshots`
- `memory_facts`
- `clarification_records`

结论：
- memory foundation 已是现实，不是规划。
- 任何新方案都不能假装这层还没落地。

### 1.2 已经存在的 judgment objects

在 `backend/app/models.py` 中，当前已经存在：
- `EventLineContextBundleRecord`
- `EventLineJudgmentRecord`
- `TaskContextPreviewRecord`
- `EventLineSummaryCardRecord`
- `EventLineRiskCardRecord`
- `EventLineOpportunityCardRecord`
- `TrendSignalRecord`
- `WeeklyReviewAnalysisRecord`
- `StrategicCockpitSnapshotRecord`
- `ManagementSignalCardRecord`

在 `src/shared/types.ts` 中，前端共享类型已经与之对齐：
- `EventLineContextBundle`
- `EventLineJudgment`
- `TaskContextPreview`
- `ManagementSignalCard`

结论：
- 当前系统不是“没有统一判断对象”。
- 当前问题是：对象已存在，但消费链和降级口径未完全收口。

### 1.3 已经存在的组织与协作真源

在 `cloud_backend/app/models.py` 中，当前已经存在：
- `OrgProfileRecord`
- `OrgQuarterPlanRecord`
- `OrgDepartmentRecord`
- `OrgDepartmentQuarterPlanRecord`
- `OrgRoleTemplateRecord`
- `OrgTaskControlRuleRecord`
- `ManagementSignalCardRecord`

结论：
- 组织、部门、季度承接、任务控制边界都已有真源。
- 日历与任务判断系统不应新建一套组织判断真源。

## 2. 当前真实链路

### 2.1 任务详情判断链

当前真实链路在 `backend/app/main.py`：
1. 任务详情请求可走 `/api/v1/tasks/{task_id}/context-preview`
2. 后端调用 `_build_task_context_preview(task)`
3. 如果任务已有 `eventLineId`，优先走 `_event_line_context_bundle(event_line_id)`
4. 如果任务没有事件线，回退到 `_build_ad_hoc_task_context_bundle(task)`
5. 再统一进入 `_build_event_line_judgment(bundle)`

结论：
- 当前任务判断链已经是“event line bundle → judgment”结构
- 但仍保留 ad hoc fallback
- 这是现阶段最重要的降级与兼容逻辑之一

### 2.2 周判断链

当前真实链路由两部分组成：
- `backend/app/services/review_analysis.py`
  - 负责从 weekly review entries、任务事实、DNA 模块形成初步分析
- `backend/app/main.py`
  - `_enrich_weekly_review_analysis_with_memory(...)`
  - 再把 `event_line_memory_snapshots`、notebook、clarification、linked facts 合并回 `WeeklyReviewAnalysisRecord`

结论：
- 周判断已经不是纯前端派生
- 它已经混合：
  - review analysis
  - event line memory
  - notebook
  - facts
- 但 enrich 仍然是“后加”的，而不是单一主链

### 2.3 战略陪伴链

前端在：
- `src/renderer/components/strategic_accompaniment/StrategicAccompanimentShell.tsx`

已真实消费：
- `snapshot.notebookSummary`
- `snapshot.memoryStatus`
- `line.predictionReadiness`
- `line.clarificationNeeds`

结论：
- 战略陪伴已经部分切到快照与记忆底座
- 但还未证明所有判断卡都统一走同一后端链

### 2.4 客户工作台链

当前客户工作台返回：
- `ClientWorkspaceResponse`

其中已包含：
- `notebookSummary`
- `memoryStatus`

结论：
- 客户工作台已经接到 memory foundation 读口
- 但问答、分析、证据 lane 与背景 lane 仍是分层混用状态，需要继续收口

## 3. 当前真实页面

任务相关页面与组件已经存在，不是空白：
- `TaskCalendarView.tsx`
- `TaskOrgContextPanel.tsx`
- `WeeklyReviewAnalysisPanel.tsx`
- `WeeklyReviewSummaryPanel.tsx`
- `WeeklyReviewStructuredFields.tsx`
- `EventLineClarificationComposer.tsx`

结论：
- 本轮不应重新发明新页面
- 应围绕现有组件做“保留 / 改造 / 删除 / 新增最小件”

## 4. 当前真实回退与降级逻辑

当前至少存在 4 条关键降级逻辑：

1. `TaskContextPreview`
- 无事件线时，退回 `_build_ad_hoc_task_context_bundle`

2. `EventLineJudgmentRecord.safeOutputMode`
- 已有：
  - `needs_input`
  - `summary_only`
  - `full_judgment`

3. `EventLineSummaryCardRecord.predictionReadiness`
- 已有：
  - `not_ready`
  - `summary_only`
  - `conservative_forecast`
  - `strong_forecast`

4. `BackgroundReadiness`
- 已有：
  - `score`
  - `level`
  - `missingSlots`
  - `backgroundSources`

结论：
- “低完整度降级输出”不是从零开始设计
- 当前任务是统一这些降级口径，而不是再发明一层新状态

## 5. 与既有方案不一致处

### 5.1 与“从零做统一判断对象”不一致

现实：
- judgment objects 已经存在
- memory foundation 已经存在
- 周判断 enrich 已经存在

所以新方案必须从“收口既有对象”开始，而不是重新命名一轮。

### 5.2 与“前端先重做页面”不一致

现实：
- 任务详情面板、周判断分析面板、战略陪伴壳、澄清组件都已经在
- 真正缺的是统一后端链、统一降级口径和首屏排序

所以不应该先做新页面再找数据。

### 5.3 与“只有业务风险，没有结构风险”不一致

现实结构风险包括：
- `projectContext` 仍与 `event line memory` 混用
- 周判断是 `review_analysis + memory_enrich` 的叠加链，而非单一 pipeline
- 战略陪伴、任务详情、周判断虽然都在吃判断对象，但未确认完全同源
- local backend 与 cloud backend 同时持有任务、管理信号与组织信息，真源边界必须继续盯紧

结论：
- 当前最大风险并不只是“判断不准”，而是“判断链不单一”。

## 6. 当前虚拟项目组的现实缺口

当前 `.codex/agents` 第一版是方法论角色，适合讨论，不够贴近真实软件团队。

现实缺口：
- 缺一个真正对“人怎么工作”负责的产品经理
- 缺一个真正研究 CEO / 部门负责人 / 员工工作流的 UX 角色
- 缺一个真正对信息分层负责的 IA 角色
- 缺一个真正对桌面运行稳定性负责的平台角色
- 缺一个真正对证据引擎负责的相关性角色
- 缺一个专门去外部搜成熟模式和真实产品先例的角色
- 缺一个对交互状态和反馈负责的交互设计角色
- 缺一个把多源资料收成统一判断合同的分析工程角色

结论：
- 当前 agent 体系适合“内部方法论讨论”
- 不足以支撑长期软件产品项目组

## 7. 对当前软件最贴切的岗位维度

按当前仓库真实工作量，最需要的是 4 条工作线：

1. 面向人
- Product Manager
- UX Researcher
- Interaction Designer
- Information Architect

2. 面向数据与判断
- Data Engineer
- Analytics Engineer
- Relevance Engineer

3. 面向运行与交付
- Platform Engineer
- QA Engineer
- Product Operations Manager

4. 面向外部模式吸收
- Competitive Intelligence Analyst

结论：
- 下一轮虚拟项目组应改成真实软件岗位
- 不再以抽象方法论角色作为长期主配置
