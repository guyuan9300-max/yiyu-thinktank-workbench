# 事件线系统实施计划

## 1. 实施目标

把“事件线”从概念落到可运行系统，使其成为：

- 任务与日历里的工作主线对象
- 周判断系统的聚合单位
- AI 的连续记忆上下文
- 人类可导出的证据线

一句话目标：

`让任务不再只是孤立任务，而是成为某条工作线上的阶段动作。`

## 2. 第一原则

这套能力必须遵守两个边界：

1. 不增加员工填写负担  
2. 优先吸收已有痕迹，而不是创造新表单

所以实施路径应是：
- 先让任务能挂到事件线
- 再让系统自动吸收活动
- 再让周判断按事件线分组
- 最后再做导出和更强的 AI 摘要

## 3. 现有可复用基础

当前系统已经有一批可直接复用的对象与信号：

- `Task`
- `TaskActivityRecord`
- `Meeting`
- `SupportRequest`
- `WeeklyReviewTaskSnapshot`
- `projectContext`
- `orgContext`
- 周判断动作卡

所以事件线不是从零开始，只是把已有散点记录收束到一条工作线上。

## 4. P1：最小可用版

## 4.1 数据层

新增：
- `event_lines`
- `event_line_links`
- `event_line_activities`

### 4.1.1 event_lines
- `id`
- `name`
- `kind`
- `status`
- `stage`
- `summary`
- `intent`
- `next_step`
- `owner_id`
- `primary_client_id`
- `primary_department_id`
- `participant_ids`
- `created_at`
- `updated_at`

### 4.1.2 event_line_links
- `id`
- `event_line_id`
- `target_type`
- `target_id`
- `relation_type`
- `created_at`

### 4.1.3 event_line_activities
- `id`
- `event_line_id`
- `source_type`
- `source_id`
- `happened_at`
- `actor_id`
- `title`
- `summary`
- `metadata_json`

## 4.2 任务挂接

在任务对象上补：
- `eventLineId?`
- `eventLineName?`

任务编辑器新增：
- `加入事件线` 下拉
- `从当前任务新建事件线`

要求：
- 默认不强制填写
- 支持手工调整
- 后台允许任务挂一条主事件线

## 4.3 前端最小入口

### 4.3.1 任务弹窗
- 增加轻量事件线下拉

### 4.3.2 任务卡 / 日历详情
- 显示事件线名称小标签
- 点击可打开事件线抽屉

### 4.3.3 事件线抽屉

先做基础版，显示：
- 名称
- 状态 / 阶段
- 负责人
- 关联项目
- 最近活动
- 关联任务

## 4.4 自动活动吸收

P1 先吸这几类：
- 创建任务
- 任务完成
- 改期 / 改时长
- 创建支持请求
- 发起会议

先覆盖高频主干，不一上来就全接。

## 4.5 周判断接法

P1 先不彻底重写算法，只做这一层：
- 现有周判断里，如果任务存在 `eventLineId`
- 则先按事件线分组聚合
- 每条事件线形成一个判断模块

模块结构：
- 本周事实
- AI 判断
- 可能性分析
- 建议动作

## 5. P2：事件线成为周判断主单位

## 5.1 后端聚合逻辑

周判断分析器新增：
- `groupTasksByEventLine(...)`
- `buildEventLineWeeklyFactSummary(...)`
- `buildEventLineWeeklyAnalysis(...)`
- `buildEventLinePossibilities(...)`
- `buildEventLineActions(...)`

## 5.2 前端展示

周判断页改成：
- 先列事件线模块
- 每个模块下面再看任务和证据

不再让用户按任务一条条看。

## 5.3 自动吸收范围扩大

P2 接入：
- 复核通过 / 退回
- 会议纪要
- 附件
- 复盘补充

## 5.4 AI 摘要

每条事件线在抽屉里自动生成：
- 这条线现在推进到哪
- 最近发生了什么
- 当前卡点
- 下一步

## 6. P3：证据线与导出

## 6.1 证据线视图

事件线详情支持双视图：
- `AI 摘要视图`
- `证据时间线视图`

证据时间线视图按时间顺序列出：
- 任务
- 会议
- 支持请求
- 附件
- 关键活动

## 6.2 PDF 导出

新增导出：
- 事件线摘要 PDF
- 事件线证据线 PDF

## 6.3 全局聚焦

在任务与日历顶部增加：
- `当前聚焦事件线`

用途：
- 过滤任务
- 聚焦周判断
- 帮 AI 默认读取当前这条线

## 7. 接口建议

### 7.1 事件线
- `GET /api/v1/event-lines`
- `POST /api/v1/event-lines`
- `PATCH /api/v1/event-lines/:id`
- `GET /api/v1/event-lines/:id`

### 7.2 挂接
- `POST /api/v1/tasks/:taskId/event-line`
- `DELETE /api/v1/tasks/:taskId/event-line`

### 7.3 活动
- `GET /api/v1/event-lines/:id/activities`

### 7.4 导出
- `GET /api/v1/event-lines/:id/export/pdf`

## 8. 前端组件建议

新增：
- `EventLineSelectField`
- `EventLineChip`
- `EventLineDrawer`
- `EventLineActivityTimeline`
- `WeeklyEventLineSection`
- `EventLineExportMenu`

调整：
- `TaskCalendarView`
- `App.tsx` 任务弹窗
- `WeeklyReviewSummaryPanel`
- `HierarchyReportCard`

## 9. 与周判断系统的关系

事件线上线后，周判断系统需要调整为：

### 旧逻辑
- 任务是主颗粒

### 新逻辑
- 事件线是主颗粒
- 任务是事件线里的事实点

这意味着复盘的语义也变化：
- 不是“我做了 3 条任务”
- 而是“我推进了云南连心这条线”

## 10. 风险与控制

### 风险 1：事件线太重，变成第二套项目系统
控制：
- 第一版只做主事件线，不做复杂层级

### 风险 2：要求员工手工维护
控制：
- 优先自动吸收痕迹
- 人工只做轻量挂接

### 风险 3：和项目/客户对象混淆
控制：
- 项目是背景对象
- 事件线是工作推进对象
- 一个项目可以有多条事件线

## 11. 当前状态说明

截至 2026-03-21：
- 事件线功能尚未实现到产品
- 当前还没有：
  - 事件线下拉
  - 事件线对象
  - 事件线抽屉
  - 按事件线分组复盘

所以当前在界面里看不到，是正常的，因为它还没开始做产品实现。

## 12. 建议开发顺序

### 第 1 步
- 建表
- 补任务字段
- 做任务弹窗事件线下拉

### 第 2 步
- 做事件线抽屉
- 接自动活动吸收

### 第 3 步
- 周判断按事件线分组

### 第 4 步
- 做导出 PDF
- 做全局聚焦事件线
