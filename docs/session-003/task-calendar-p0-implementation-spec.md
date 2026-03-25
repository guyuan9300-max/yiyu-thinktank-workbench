# Session 003
## 日历与任务判断系统：P0 Implementation Spec

## 0. 范围

本轮只处理：
1. 顶部判断状态条
2. signal cards
3. action cards
4. evidence drawer
5. 判断依据与边界区
6. calendar signal bar

本轮不处理：
- 新真源
- 战略陪伴大改
- 客户工作台大改
- 全量周报重写
- 复杂 manager cockpit

---

## 1. 页面骨架：什么该前置，什么必须后退

### 这轮新增的用户约束

这一轮必须按下面的使用原则改：

- 先给结果，再补边界
- 尽量少依赖额外人工录入
- 不把“缺失项”做成首屏主角
- 允许 AI 基于最小必需输入集做保守判断

### 最小必需输入集

P0 默认围绕这 5 类输入计算，不再要求更多表单先补齐：

1. `整个项目 / 业务的核心资料与介绍`
   - 来源：客户工作台已有资料、DNA、项目介绍、核心业务说明
2. `整个部门 / 整个机构的季度主要计划`
   - 来源：组织搭建中心、组织计划、部门季度计划
3. `任务标题`
4. `任务说明`
5. `任务复盘资料`
   - 包括单项复盘、周复盘里对这件事的判断

### 可选增强输入

这些输入会增强判断，但默认不构成“无法干活”的理由：

- 会议纪要 / action items
- 附件摘要
- 支持请求
- 事件线记忆
- 日历时间块
- 审批状态 / 组织控制规则

### 计算原则

- 只要最小必需输入集里已经有足够内容，系统就应先给出保守判断。
- 可选增强输入缺失时，不得把首屏变成大面积“缺失项列表”。
- 缺口只在两种情况下前置：
  - 当前判断明显不可信
  - 当前动作无法闭环

### 当前问题

当前真实页面更像：
- AI 复盘报告页
- 长文分析阅读页

而不是：
- 判断操作台
- 动作闭环台

导致：
- 个人不知道“现在先做什么”
- leader 不知道“现在该介入什么”
- 用户看不到“哪些内容其实没被纳入判断”

### P0 首屏骨架

#### 首屏顺序
1. `Judgment Status Strip`
2. `Role Sort Switch`
3. `Signal Cards`
4. `Action Cards`
5. `Calendar Signal Bar`
6. `Boundary Strip (compact)`
7. `Compact Task Stream`
8. `Evidence Drawer`
9. `Long-form Analysis / Weekly Summary` 折叠在后

### 为什么这么排
- 先让人知道当前判断质量
- 再告诉人当前最重要的信号
- 再给动作
- 再用紧凑方式提示系统边界与缺口
- 最后才给长分析

这条顺序必须统一应用到：
- 任务列表首屏
- 我的月历入口上方
- 周复盘 collect 首屏

---

## 2. P0 最小 contract：前台 5 个核心块

## 2.1 顶部判断状态条

### 目标
不是展示总任务数，也不是先展示“缺什么”，而是先展示“当前这批任务里，系统已经能给出多少可信判断和动作提示”。

### 字段
- `includedTaskCount`
- `notIncludedTaskCount`
- `degradedTaskCount`
- `highRiskTaskCount`
- `meetingFollowupOpenCount`
- `calendarCoverageGapCount`
- `safeOutputMode`
- `updatedAt`

### 交互
- 点击 `判断边界` -> 打开 compact boundary list
- 点击 `关键任务未入历` -> 滚动到 calendar signal bar

### 结果优先规则
- 如果 workspace 只能做到 `summary_only`
  - 状态条写“当前基于有限资料输出保守判断”
- 只有在 `needs_input` 且无法形成动作建议时
  - 才前置“待补输入”

---

## 2.2 Signal Cards

### P0 只允许 6 类首屏卡
1. `main_progress`
2. `largest_blocker`
3. `high_risk`
4. `calendar_gap`
5. `meeting_closure_gap`
6. `next_week_focus`

### 角色排序

#### 个人视角
1. `next_week_focus`
2. `largest_blocker`
3. `meeting_closure_gap`
4. `calendar_gap`
5. `high_risk`
6. `main_progress`

#### leader 视角
1. `high_risk`
2. `largest_blocker`
3. `meeting_closure_gap`
4. `support_debt`
5. `approval_bottleneck`
6. `main_progress`

### 每张卡必须包含
- `title`
- `statement`
- `whyNow`
- `confidence / coverage`
- `查看证据`
- `立即动作`

### 不允许继续的做法
- 把一大段 AI 摘要塞进卡片正文
- 卡片没有 evidence drawer 入口
- 卡片没有明确 target

---

## 2.3 Action Cards

### P0 的 3 类闭环动作
1. `task`
2. `support_request`
3. `meeting`

### 每张动作卡必须包含
- `title`
- `whyNow`
- `actionType`
- `payload`
- `ownerRole`
- `证据入口`

### 动作卡位置
- 首屏 signal cards 后面
- 长分析前面

### 不允许继续的做法
- 只有“建议动作”文字，没有主按钮
- 点击后不能落到真实对象
- 只生成“下周重点”这种不可执行短句

---

## 2.4 Evidence Drawer

### 目标
把“为什么系统这么判断”从黑盒里拉出来。

### P0 必须展示的内容
- 任务证据
- 会议证据
- support request
- 附件摘要
- event line memory
- context bundle
- judgment 对应 evidenceRefs
- missing slots
- backgroundSources

### 入口要求
每一张：
- signal card
- action card
- degraded item
都必须能打开 evidence drawer

### P0 技术前置
- 优先复用 `GET /api/v1/reviews/dashboard/drill-target`
- 缺 `task` target support 时，先补 backend，不在前端绕开

---

## 2.5 判断依据与边界区

### 为什么要保留，但不能喧宾夺主
- 用户需要知道系统判断的边界
- 但不应该一打开就先看到大量缺失项，导致“没有结果”
- 所以 P0 只保留一个紧凑的 boundary strip，默认折叠详细列表

### P0 的展示方式

首屏只显示：
- `X 条任务基于完整输入判断`
- `Y 条任务基于有限输入保守判断`
- `Z 条任务当前资料过弱，仅做轻提示`

点击后展开详细列表，再区分：
- `Not Included`
- `Degraded`

### Not Included 的定义

只有这些情况才算 `Not Included`：
- 任务标题过空或不可判读
- 任务说明为空，且没有复盘资料
- 既没有项目/业务核心背景，也没有部门/机构季度计划

### Degraded 的定义

`Degraded` 不是“东西缺得多”，而是：
- 系统已经输出结果
- 但它基于的是较少资料
- 因此只能做保守判断，而不是强判断

### 详细展开时才显示

- 当前用了哪些输入
- 缺的关键槽位是什么
- 推荐补的不是“大量资料”，而是最少的补充动作
  - 补任务说明
  - 补单项复盘
  - 补季度计划
  - 关联到正确的项目/业务背景

典型 reason：
- `thin_evidence`
- `missing_slot`
- `summary_only`
- `needs_input`

### 不允许继续的做法
- 用一句灰色提示带过
- 只说“证据不足”，不说到底缺什么
- 不给任何推荐修补动作

---

## 2.6 Calendar Signal Bar

### 目标
让“日历”真正成为判断系统的一部分，而不是只是展示 due date。

### P0 最小展示项
- `关键任务未入历`
- `会后动作未闭环`
- `待复核任务堆积`
- `逾期且未时间承接`
- `下周重点尚未时间块化`

### 交互
- 每个 signal 都必须能跳转：
  - 到 task list 筛选结果
  - 到 calendar 对应日期 / 周
  - 或生成 action card

### 和月历页的关系
- 月历页顶部只展示 compact 版 signal bar
- 任务列表首屏展示 full 版 signal bar

---

## 3. 哪些现有区块保留，哪些后退

## 保留
- `TaskCalendarView`
- `TaskOrgContextPanel`
- `WeeklyReviewStructuredFields`
- `WeeklyReviewAnalysisPanel`
- `WeeklyReviewSummaryPanel`

## 改造
- `TaskOrgContextPanel`
  - 从“前端会说的 AI 洞察卡”改成“共享 judgment panel + fallback strip”
- `WeeklyReviewAnalysisPanel`
  - 从长分析页改成：
    - signal-first
    - degrade-visible
    - evidence-openable
    - action-closable

## 后退 / 折叠
- 长文分析
- 长文周报
- 大段“为什么这周很重要”的解释

---

## 4. P0 页面范围建议

## 4.1 任务列表页

P0 必做：
- 顶部 judgment status strip
- role switch
- full signal bar
- signal cards
- action cards
- degraded zone
- compact task stream

任务卡展开层：
- 任务说明
- judgment panel
- related evidence trigger
- 轻动作入口

## 4.2 我的月历

P0 必做：
- compact signal bar
- 当前周/当前月的时间承接缺口
- 点击 signal 可回到任务列表筛选结果

P0 不做：
- 在日历格子里直接塞大量 AI 卡片

## 4.3 周复盘 collect

P0 必做：
- 任务状态选择
- 单条保存
- 顶部 compact judgment strip
- 当前条目的 degraded/needs-input 提示

P0 不做：
- collect 阶段继续前置大段 AI 总结

---

## 5. 推荐实现顺序

### P0.1 Contract & transport
- 新增 `TaskCalendarJudgmentWorkspace` projection response
- 补 `task` drill-target support
- 降级 `TaskOrgContextPanel` heuristics

### P0.2 First screen skeleton
- 状态条
- signal cards
- action cards
- degraded zone

### P0.3 Calendar signal bar
- full 版 + compact 版
- 与 task list / calendar 跳转接通

### P0.4 Evidence drawer
- 统一 drill-down path

### P0.5 Weekly review alignment
- collect 与 weekly judgment 使用同一条 workspace contract / judgment chain

---

## 6. 当前推荐路线

当前模块最需要修的，不是继续加分析区，而是：
- 把 judgment 质量显式化
- 把动作闭环前置
- 把日历正式纳入 judgment chain
- 把未纳入判断和降级处理暴露出来

只有先把这四件事做好，个人和 leader 才会把它当“操作台”，而不是“会说很多话的复盘页面”。
