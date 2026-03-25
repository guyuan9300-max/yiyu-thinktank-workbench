# 任务与日历 + 事件线 + 周判断

## 行动操作系统收口方案

日期：2026-03-22

### 目标

把当前的：

- 任务录入
- 日历排布
- 事件线连续上下文
- 周判断
- 动作卡闭环

收成一套真正的 `Action OS`：

`执行痕迹 -> 连续上下文 -> 管理判断 -> 动作闭环`

而不是继续把它理解成：

- 任务页优化
- 周总结美化
- 卡片文案微调

---

## 一、最值得借鉴的 Plane 设计

参考：

- https://github.com/makeplane/plane
- https://docs.plane.so/core-concepts/projects/overview
- https://docs.plane.so/core-concepts/cycles
- https://docs.plane.so/core-concepts/views

### 1. 工作对象厚化，而不是薄任务

Plane 最值得借的是：Issue 不是 `title + status`，而是带完整属性、上下文、关系、活动流和视图归属的工作对象。

对应我们当前的真实障碍：

- 任务卡趋同，因为任务对象太薄，过度依赖共享 `projectContext`
- 会议、情报、周判断动作进入任务后容易失真
- 事件线虽然落地，但任务和事件线还没有完全成为同一个主结构

对当前系统的落地要求：

- 把任务对象正式收口成工作对象
- 任务判断必须优先读 `任务自身语义 + 事件线上下文`
- 项目背景只做第三层补充，不能再淹没任务差异

### 2. 视图是“管理问题”的固化，不是临时筛选

Plane 的 views/filter 值得借的是：

- 用户看到的不是一堆任务
- 而是按某个管理问题组织过的任务集合

对应我们当前的真实障碍：

- 现在虽然能按条件筛，但还没有“正式视图”
- 事件线视角、风险视角、来源视角、业务分类视角还停留在隐含逻辑里
- 用户无法稳定回到“我上次就是按这个管理问题在看任务”

对当前系统的落地要求：

- 正式做出可保存视图
- 至少第一批视图固定为：
  - 按事件线看任务
  - 按业务类别看任务
  - 按风险等级看任务
  - 按动作来源看任务

### 3. 活动流与分析是对象本身的一部分

Plane 的 analytics 和 activity 最值得借的是：

- 任务不是录入完就结束
- 活动、变化、趋势、阻塞都属于对象生命周期的一部分

对应我们当前的真实障碍：

- 会议、支持请求、附件、复核、改期已经开始统一，但还没完全成为可回看的工作线
- 事件线价值被分散在不同页面和对象里
- 周判断能生成文字，但还不够强地回到证据

对当前系统的落地要求：

- 强化任务活动流
- 把改期、阻塞、复核、附件、支持请求、会议统一沉为可回看的线
- 继续坚持统一文件层：任务附件必须进入客户/项目总文件库，并写进事件线证据层

---

## 二、最值得借鉴的 Metabase 设计

参考：

- https://github.com/metabase/metabase
- https://www.metabase.com/features/drill-through

### 1. 第一屏是压缩后的驾驶舱，不是长文前言

Metabase 最值得借的是：

- 先给管理者一个高度压缩、可扫读的 dashboard
- 再决定要不要下钻

对应我们当前的真实障碍：

- 周判断第一页过去太像摘要，不像驾驶舱
- 角色视角开始分叉，但还没成为稳定 dashboard
- 部门/机构 rollup 容易把内容压扁

对当前系统的落地要求：

- 周判断第一页固定成 dashboard
- 固定四层：
  - 本周关键事件线
  - 本周最值得关注的风险
  - 本周最值得放大的机会
  - 本周建议动作

### 2. 每张卡都必须可 drill-down

Metabase 的 drill-through 最值得借的是：

- 一句判断不是终点
- 它必须能继续点到数据、证据和上下文

对应我们当前的真实障碍：

- 当前周页面四层卡结构已经开始成形
- 但多数卡片还是展示层，不能继续点进事件线、任务、附件、会议或支持请求

对当前系统的落地要求：

- 每张卡至少携带：
  - 标题
  - 关键判断句
  - 标签/元数据
  - drill-down target
- 目标至少支持：
  - 事件线详情
  - 相关任务集合
  - 相关附件
  - 相关会议
  - 相关支持请求

### 3. Filters / alerts / subscriptions 是管理机制，不是附属功能

Metabase 最值得借的不是复杂通知，而是：

- 结构化 dashboard 要天然兼容过滤、提醒、订阅

对应我们当前的真实障碍：

- 现在大多还是“本周判断”
- 还不是“连续风险和连续机会判断”
- 也没有明确哪些信号未来应该自动提醒

对当前系统的落地要求：

- 先补一层最小告警模型
- 不立刻做复杂通知系统，但先把触发条件建出来

第一批信号：

- 连续改期
- 事件线长时间无推进
- 证据不足却持续产出判断
- 同类阻塞连续两周升级

---

## 三、映射到当前系统的 5 个核心障碍

### 1. 任务对象太薄

当前已正式存在并基本贯通：

- `sourceType`
- `eventLineId`
- `projectModuleId`
- `projectFlowId`

当前只存在于上下文层、还没收成正式任务主字段：

- `currentBlocker`
- `nextAction`
- `recentDecision`

当前尚未正式落地成共享主字段：

- `businessCategory`
- `evidenceCount`

结论：

- 当前任务对象还不像 Plane 式工作对象
- 仍然更像“带一点上下文的任务记录”

### 2. 事件线还没完全成为任务视图的主颗粒

当前已经做到：

- 事件线是一等对象
- 任务可以挂事件线
- 周复盘和周判断已经开始读事件线

还没做到：

- 任务视图正式按事件线组织
- 事件线视图成为一等入口
- dashboard 卡片点击直接 drill-down 到事件线

### 3. 周判断第一页还没完成 dashboard 收口

当前已经做到：

- 第一屏四层结构已开始落地
- summary/risk/opportunity/action 有结构化 card 模型

还没做到：

- 卡片稳定 drill-down
- 不同角色不同排序和字段
- dashboard 与后面的正文、证据链完全闭环

### 4. 证据链还没完全变成可点击回证据

当前已经做到：

- 任务附件进入项目文件库
- 事件线开始吸收附件、支持请求、会议、活动

还没做到：

- dashboard 卡片点进去就能看到对应证据
- 风险/机会/动作和附件/会议/支持请求的直接映射

### 5. 还缺跨周趋势层

当前大多还是：

- 本周发生了什么
- 本周怎么判断

还不是：

- 连续推进
- 连续阻塞
- 连续改期
- 风险升级
- 机会持续放大

---

## 四、这一轮先改什么

### 1. 字段层收口

先把以下字段明确成正式主结构，而不是继续只存在于 context 或推断层：

- `businessCategory`
- `currentBlocker`
- `nextAction`
- `recentDecision`
- `evidenceCount`

建议对象归属：

- `TaskRecord`
  - `businessCategory`
  - `currentBlocker`
  - `nextAction`
  - `evidenceCount`
- `EventLineRecord`
  - `businessCategory`
  - `currentBlocker`
  - `recentDecision`
  - `nextStep`
  - `evidenceCount`

原则：

- 任务保留执行态
- 事件线保留连续上下文态
- 项目背景只做第三层包

### 2. 视图层收口

第一批正式视图：

- `事件线视图`
- `风险视图`
- `来源视图`
- `业务分类视图`

每个视图都至少包含：

- 名称
- 过滤条件
- 排序条件
- 角色适用范围
- 是否可共享

### 3. Dashboard 层收口

把周判断第一页彻底做成 dashboard，而不是正文入口。

每张卡统一收成：

- `title`
- `statement`
- `chips`
- `targetType`
- `targetId`
- `targetPayload`

目标类型第一批：

- `event_line`
- `task_list`
- `meeting`
- `support_request`
- `attachment_group`

### 4. 趋势层启动

先不做复杂预测模型，先做稳定的跨周信号聚合：

- 连续改期计数
- 连续无推进周数
- 连续待复核周数
- 连续支持请求周数
- 风险类型升级计数

---

## 五、我准备先改哪些文件/接口

### 字段与模型

- `backend/app/models.py`
- `cloud_backend/app/models.py`
- `src/shared/types.ts`
- `backend/app/db.py`
- `cloud_backend/app/db.py`

### 视图与任务入口

- `src/renderer/App.tsx`
- `src/renderer/components/tasks/TaskCalendarView.tsx`
- 新增或扩展任务视图相关前端组件

### Dashboard 与 drill-down

- `src/renderer/components/tasks/HierarchyReportCard.tsx`
- `backend/app/services/review_analysis.py`
- `backend/app/services/review_rollup.py`

### API

优先扩展现有接口，而不是另起大系统：

- `/api/v1/tasks`
  - 补齐正式字段读写
- `/api/v1/event-lines`
  - 补 drill-down 所需元信息
- `/api/v1/event-lines/{id}`
  - 扩 detail 读口
- `/api/v1/event-lines/{id}/memory`
  - 扩证据链信息
- 新增正式视图接口：
  - `GET /api/v1/task-views`
  - `POST /api/v1/task-views`
  - `PATCH /api/v1/task-views/{id}`
- 新增 dashboard drill-down 目标接口：
  - `GET /api/v1/reviews/dashboard/drill-target`

---

## 六、人工测试链路

至少用这一条链验证不是“看板美化”，而是完整系统：

### 测试链 1

1. 从会议发起一条任务  
   要求：
   - `sourceType=meeting`
   - 自动或手动挂到正确事件线

2. 在任务里上传附件  
   要求：
   - 附件进入客户/项目总文件库
   - 事件线活动流新增 `attachment` 证据

3. 在周判断第一页看到这条事件线  
   要求：
   - 出现在 `本周关键事件线`
   - 如果证据不足，风险卡体现“证据不足”

4. 点击风险卡 drill-down  
   要求：
   - 进入对应事件线详情
   - 能看到相关任务、附件、会议、支持请求

5. 从动作卡发起动作  
   要求：
   - 创建任务 / 支持请求 / 会议
   - 新对象自动挂回原事件线

6. 回看任务和事件线  
   要求：
   - 活动流里有回写记录
   - 周判断下一次能读到这次动作结果

### 测试链 2

1. 同一项目下创建两条不同业务类别任务：
   - 一条业务扩展
   - 一条资料沉淀
2. 要求周判断和任务卡口径明显不同
3. 要求在 `业务分类视图` 可单独看到这两类任务

---

## 七、落地顺序

### Phase 1

- 字段层收口
- 事件线 / 风险 / 来源 / 业务分类正式视图
- dashboard card drill-down target

### Phase 2

- dashboard 第一屏彻底 drill-down 化
- 角色化 dashboard 真正分开
- 证据链可点击回看

### Phase 3

- 跨周趋势层
- 最小 alerts / subscriptions
- 连续风险和连续机会判断

---

## 八、判断

当前系统已经不是“从零开始”，而是已经有了：

- 任务对象基础字段
- 事件线对象
- 结构化周判断卡
- 统一附件归档
- 动作卡闭环

真正缺的不是更多页面，而是：

- 对象层再收口
- 视图层正式化
- dashboard drill-down
- 趋势层启动

所以这条主线最正确的推进方式是：

`先收对象 -> 再收视图 -> 再收 dashboard -> 再做趋势`

不要先做更重的独立事件线中心，也不要先堆复杂导出。
