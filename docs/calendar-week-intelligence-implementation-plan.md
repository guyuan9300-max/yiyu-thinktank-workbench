# 日历模块周判断系统实施计划

## 1. 实施目标

把当前 `周复盘` 从“任务复盘填写页”升级成：

`低人工输入 + 高背景注入 + 高洞察输出` 的周判断系统

它的核心目标不是生成一篇周报，而是：
- 识别隐性问题
- 预测未来困难与机会
- 输出个人 / 部门 / 机构可执行动作

## 2. 页面改造目标

当前页面应从“采集页 + 草稿页”演进为四段式判断页：

1. `本周事实`
2. `AI 判断`
3. `可能性分析`
4. `建议动作`

### 2.1 页面顶部

保留：
- 周次切换
- 历史周查看
- 角色视角切换（个人 / 部门 / 机构）

新增：
- 当前证据来源概览
  - 组织背景
  - 部门计划
  - 项目背景
  - 会议纪要
  - 日历痕迹

作用：
- 让管理者知道这次判断“用了哪些背景”

## 3. 页面信息架构

### 3.1 本周事实区

自动生成，不要求人工填写。

显示模块：
- 本周任务总数
- 完成数 / 延期数 / 改期数
- 待复核 / 支持请求 / 跨部门任务数
- 时间轴进入率
- 未设时间任务池情况
- 高频改期任务
- 本周任务分布（按项目 / 部门 / 清单）

关键设计：
- 事实区只说“发生了什么”
- 不提前解释原因

### 3.2 AI 判断区

结合组织 / 部门 / 项目背景解释事实。

输出内容：
- 本周主要推进了哪些真正重要的事情
- 哪些任务虽然很多，但没有贴着当前目标
- 哪些岗位或成员开始偏离职责
- 哪些问题是管理问题，不只是执行问题

关键设计：
- 判断必须绑定证据来源
- 每条判断后面应有小字显示：
  - 来源：部门计划 / 项目背景 / 会议纪要 / 日历痕迹

### 3.3 可能性分析区

面向未来 1-3 周。

输出内容：
- 哪些风险可能放大
- 哪些困难尚未显性暴露
- 哪些机会值得提早加码
- 哪些项目 / 部门 / 个人可能出现分化

关键设计：
- 这是预测区，不写成假大空趋势判断
- 必须尽量具体到“哪类任务 / 哪个项目 / 哪条流程”

### 3.4 建议动作区

必须按角色分层：

个人动作：
- 下周应该优先做什么
- 该补什么资料 / 发起什么支持

部门动作：
- 部门负责人应该介入哪几个问题
- 哪些任务该重排 / 转派 / 拆分

机构动作：
- 哪些问题应升级到 CEO / 管理层
- 哪些项目需要协调会议 / 机制干预

关键设计：
- 每条建议动作应该尽量可转化为系统动作
- 后续可扩展成：
  - 一键转任务
  - 一键发起支持请求
  - 一键发起复核
  - 一键发起会议

## 4. 证据层设计

### 4.1 背景母盘来源

#### 组织层
- 组织 DNA
- 年度战略
- 当前季度重点

#### 部门层
- 部门使命
- 部门季度重点
- 部门月计划
- 部门周计划
- 岗位职责
- 岗位流程

#### 项目层
- 客户 / 项目介绍
- 当前阶段
- 当前目标
- 当前风险
- 会议纪要
- 行动项

#### 执行层
- 任务字段
- 日历排布
- 改期 / 拖期
- 未设时间池停留
- 复核 / 支持请求
- 轻量复盘

### 4.2 日历痕迹信号

新增标准信号：
- `rescheduleCount`
- `daysInUnscheduledPool`
- `enteredTimeline`
- `lateScheduled`
- `afterHoursScheduled`
- `highPriorityCollision`
- `reviewBlocked`
- `supportRequestOpen`
- `crossDepartment`
- `loadRiskLevel`

### 4.3 输出时的证据透明化

每条判断不需要展示所有底层数据，但至少标明：
- 使用了哪些背景层
- 当前结论更偏“事实”还是“预测”

## 5. AI 输入输出结构

## 5.1 输入 payload

```ts
type WeeklyIntelligenceInput = {
  weekLabel: string;
  perspective: 'self' | 'department' | 'organization';
  taskFacts: WeeklyTaskFact[];
  calendarSignals: WeeklyCalendarSignal[];
  lightReflections: WeeklyReflectionSignal[];
  backgroundContext: {
    organization?: OrganizationContext;
    department?: DepartmentContext;
    projects: ProjectContext[];
    roles: RoleContext[];
    workflows: WorkflowContext[];
  };
};
```

## 5.2 输出 payload

```ts
type WeeklyIntelligenceOutput = {
  factSummary: string[];
  analysisSummary: string[];
  possibilitySummary: string[];
  actionSummary: WeeklyActionSuggestion[];
  managementSignals: WeeklyManagementSignal[];
  growthSignals: WeeklyGrowthSignal[];
  predictedRisks: WeeklyPredictedRisk[];
};
```

## 6. 前端组件建议

### 6.1 新组件

- `WeeklyEvidenceSourcesBar`
  - 显示当前判断依赖的背景来源

- `WeeklyFactsPanel`
  - 本周事实区

- `WeeklyAnalysisPanel`
  - AI 判断区

- `WeeklyPossibilityPanel`
  - 可能性分析区

- `WeeklyActionPanel`
  - 建议动作区

- `WeeklySignalCard`
  - 用于统一呈现管理信号 / 风险信号 / 成长信号

### 6.2 现有组件调整

- `WeeklyReviewSummaryPanel`
  - 从“总结展示卡”升级成主容器

- `WeeklyReviewAnalysisPanel`
  - 不再单独孤立存在，应拆入 AI 判断 / 可能性分析区

- `HierarchyReportCard`
  - 继续保留，用于部门 / 机构层汇总卡

## 7. 后端分析器改造

### 7.1 P1 必做

- 把日历痕迹接进分析器
- 重新组织输出结构：
  - facts
  - analysis
  - possibilities
  - actions

### 7.2 P2 必做

- 把组织层、部门层、项目层背景接进分析器
- 支持任务 -> 部门计划 -> 组织目标 的链路判断

### 7.3 P3 必做

- 加风险预测
- 加机会识别
- 加动作优先级排序

## 8. 用户输入控制

### 8.1 员工端保持最小输入

只保留：
- 一句反思
- 一个轻量标签

### 8.2 管理层补根背景

允许补录：
- 部门计划
- 岗位流程
- 项目背景

但不要求成员为总结额外填资料。

## 9. 实施顺序

### P1：页面重组

目标：
- 不改输入复杂度
- 先把页面从“复盘页”改成“四段式判断页”

开发项：
1. 新增四段式页面骨架
2. 保留现有轻量复盘输入
3. 把现有分析结果重新映射到四段式结构

### P2：背景接入

目标：
- AI 判断开始真正吃背景母盘

开发项：
1. 接组织季度目标
2. 接部门周 / 月计划
3. 接项目 / 客户背景
4. 接会议纪要与行动项

### P3：预测与动作闭环

目标：
- 从“总结”升级成“管理系统”

开发项：
1. 风险预测
2. 机会提示
3. 支持请求联动
4. 一键转任务 / 会议 / 复核

## 10. 成功标准

### 10.1 对员工
- 不增加填写负担
- 能得到更具体的改进建议

### 10.2 对部门负责人
- 能看出哪些问题需要现在介入
- 能分辨执行问题和管理问题

### 10.3 对机构管理者
- 能提前看见 1-3 周后的风险和机会
- 能判断组织是否真的在推进战略，而不是只是忙

## 11. 结论

这套周判断系统的终极目标不是“把任务整理成一篇总结”，而是：

`用组织背景、计划背景、项目背景和执行痕迹，让 AI 给出真正有管理价值和成长价值的洞察。`
