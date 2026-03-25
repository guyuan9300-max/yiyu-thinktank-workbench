# Session 003
## 日历与任务判断系统：P0 Rollout / Risks / Release Gates

## 0. 推荐路线

当前推荐路线是：

### Route A：保守增量路线（推荐）
1. 保持当前 judgment 真源不动
2. 新增一个 transport-only endpoint：
   - `GET /api/v1/tasks/judgment-workspace`
3. 让：
   - 任务详情 AI 面板继续读 `/api/v1/tasks/{task_id}/context-preview`
   - 周判断继续读 `WeeklyReviewAnalysisRecord`
   - 首屏骨架读 `judgment-workspace`
4. evidence drawer 继续复用 `/api/v1/reviews/dashboard/drill-target`
5. 补 `task` target support

### 放弃路线
不走：
- persisted envelope
- 第二套 judgment dashboard 真源
- 前端继续自产主要 judgment 文案

原因：
- 会立刻形成双真源
- 会让 task detail 与 weekly judgment 的判断版本漂移

---

## 1. P0 风险清单

## Blocker 级

### 1. `TaskOrgContextPanel` heuristics 仍作为主输出
影响：
- 任务详情与周判断仍然两套话
- 用户最先看到的仍是前端启发式，不是后端 judgment

### 2. `ReviewDashboardCardTarget.targetType = task` 已声明，但 backend drill-target 不支持
影响：
- 证据抽屉无法对任务级卡片闭环
- 前端只能绕开 target contract

### 3. calendar signal bar 若把“有日期”当成“已上历”
影响：
- 用户会误以为任务已时间承接
- 实际上只挂了日期，没有时间块

### 4. collect 阶段继续前置长分析
影响：
- 单项复盘继续失去“即时补写”价值
- 用户仍会把页面理解成报告页

## Non-blocking 级

### 5. 会议只有 `scheduledAt`，缺 duration
影响：
- 只能做“meeting overlap candidate”，不能做高精度 collision

### 6. `projectContext` 仍然文本很强
影响：
- 容易继续压过 event line judgment

### 7. manager / leader 排序暂时无法做到非常细
影响：
- P0 先做 `employee` / `department_lead` 两层，`admin` 保留兼容层

---

## 2. Rollout 顺序

### Sprint 1：contract 收口
- 明确 `TaskCalendarJudgmentWorkspace`
- 明确 6 个 transport types
- 补 `task` drill-target support
- 把 `TaskOrgContextPanel` heuristics 降级为 fallback-only

### Sprint 2：首屏骨架
- judgment status strip
- signal cards
- action cards
- not-included / degraded zone

### Sprint 3：calendar signal bar
- full bar（任务列表）
- compact bar（月历）
- signal -> task filter / calendar jump

### Sprint 4：evidence drawer
- 所有 signal / action / degraded item 统一 drill-down

### Sprint 5：review collect 对齐
- 单项复盘页引入 compact judgment status
- collect 阶段不再优先展示长分析

---

## 3. Release Gates

## Gate 1：真源与版本
- 不新增新的 persisted judgment 真源
- `TaskContextPreviewRecord` 和 `WeeklyReviewAnalysisRecord` 继续是主 judgment 输入
- 首屏 workspace 只是 projection
- task detail 与 weekly judgment 至少共享：
  - `judgmentVersion`
  - `bundleFingerprint`
  - `safeOutputMode`

## Gate 2：heuristics 退场
- `TaskOrgContextPanel` 中以下函数不再主导输出：
  - `inferTaskMode`
  - `inferBusinessCategory`
  - `buildModeFocus`
  - `buildModeRisk`
  - `buildModeOpportunity`
  - `buildModeAction`
  - `buildContextRisk`
  - `buildOpportunity`
  - `buildInsights`
- fallback 触发时必须显式显示 `fallback / summary_only / needs_input`

## Gate 3：首屏结构
- 首屏已经前置：
  - judgment status strip
  - signal cards
  - action cards
  - degraded zone
- 长分析和长总结不在首屏最前

## Gate 4：calendar 进入 judgment chain
- 至少可见：
  - 关键任务未入历
  - 会后动作未闭环
  - 逾期且未时间承接
  - 下周重点尚未时间块化

## Gate 5：证据可信
- 每张 signal card 都能打开 evidence drawer
- 每张 action card 都能打开 evidence drawer
- degraded item 能解释：
  - 为什么降级
  - 缺什么槽位
  - 推荐补法

## Gate 6：动作闭环
- 至少 3 类动作可闭环：
  - `task`
  - `support_request`
  - `meeting`
- `ReviewActionExecutionResult` 能真实返回 object result

## Gate 7：角色差异
- 个人视角排序与 leader 视角排序不同
- 不能继续共用同一套首屏顺序

## Gate 8：回归
以下旧链路不得回退：
- 任务列表
- 我的月历
- 单项复盘输入与保存
- 周复盘保存
- 任务状态切换
- 任务卡展开
- evidence / memory 数据加载

---

## 4. 当前允许进入实现的前提

只有当下面 6 项都明确，才允许从 Session 003 进入业务实现：

1. judgment source 明确
2. transport contract 明确
3. heuristics 降级边界明确
4. calendar signal 输入明确
5. action closure 优先级明确
6. release gates 明确

当前状态判断：
- 以上 6 项已经可以进入实现
- 下一轮不应再回到“页面到底像不像 AI 分析页”的抽象争论
- 下一轮应直接开始最小实现
