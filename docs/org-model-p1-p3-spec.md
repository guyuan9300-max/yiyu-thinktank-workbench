# 组织模型层 P1-P3 规格（计划、流程、趋势与业务对象）

## 1. 文档目标

本文件承接：
- [docs/org-model-foundation-plan.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-foundation-plan.md)
- [docs/org-model-p0-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p0-spec.md)

P0 解决的是“组织语义底座是否存在”，P1-P3 解决的是“这层底座如何真正驱动任务、周计划、周总结和 CEO 判断”。

设计总原则：
- 员工端继续轻输入，不新增复杂字段。
- 管理层负责补计划、目标、流程和权限背景。
- AI 负责后台自动挂接、结构化归因和总结生成。
- 前台优先展示动作和状态，不优先展示复杂分析表。

---

## 2. 分阶段目标

## P1：计划与对齐层

目标：
- 把“部门周计划”和“机构季度目标”做成正式对象。
- 让任务能稳定挂到“部门计划 -> 机构目标”上。
- 让“需要什么支持”从一句话变成可流转对象。

解决的问题：
- 个人任务是否真的支撑部门重点。
- 部门重点是否真的支撑机构季度目标。
- 哪些未完成任务需要正式支持，不再只是散落在复盘文本里。

## P2：复核与流程执行层

目标：
- 把当前已有的控制规则和流程模板变成真实执行链路。
- 让系统知道某件事现在卡在谁、卡在第几步、为什么卡。
- 让 AI 总结可以直接转成管理动作。

解决的问题：
- 为什么某类任务总在复核 / 协作确认环节停住。
- 退回复核后系统是否知道下一步该做什么。
- AI 总结不是只看，而是能立刻转任务、转支持、转会议。

## P3：趋势、机器人一等化、业务对象层

目标：
- 让系统从“单周判断”升级成“连续判断”。
- 让机器人和人类彻底共用同一套组织模型和执行面板。
- 把益语智库专属客户场景抽象成“业务对象层”，避免系统被 ToB 写死。

解决的问题：
- 连续 3 周的卡点和职责偏离如何识别。
- 庆华 / 大周 / 佳乐如何作为正式成员进入统计、复核和趋势。
- 客户 / 项目 / 会议 / 标杆案例如何统一进入总结引擎。

---

## 3. P1 规格：计划与对齐层

## 3.1 P1 必做对象

1. `OrgFocusItem`
- 机构季度目标的正式对象。
- 替代当前从 DNA 文本里临时抽取的“季度重点”。

2. `DepartmentWeeklyPlan`
- 部门负责人每周维护的一份计划头对象。

3. `DepartmentWeeklyPlanItem`
- 部门周计划下的具体计划项。

4. `TaskPlanLink`
- 把任务稳定挂到部门计划项和机构目标项上。

5. `SupportRequest`
- 把“需要什么支持”变成可追踪、可响应、可关闭的对象。

## 3.2 P1 表结构

### `org_focus_items`

用途：
- 结构化机构季度目标。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 目标项 id |
| `organization_id` | TEXT | NOT NULL | 所属机构 |
| `period_key` | TEXT | NOT NULL | 如 `2026-Q1` |
| `title` | TEXT | NOT NULL | 目标标题 |
| `statement` | TEXT | NOT NULL DEFAULT '' | 目标说明 |
| `owner_user_id` | TEXT | NULL | 负责人 |
| `priority` | TEXT | NOT NULL DEFAULT 'medium' | `high / medium / low` |
| `status` | TEXT | NOT NULL DEFAULT 'active' | `draft / active / paused / done` |
| `evidence_keywords_json` | TEXT | NOT NULL DEFAULT '[]' | 识别关键词 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

### `org_department_plans`

用途：
- 部门负责人每周维护的计划头。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 计划头 id |
| `department_id` | TEXT | NOT NULL | 所属部门 |
| `week_label` | TEXT | NOT NULL | 如 `2026-W12` |
| `owner_user_id` | TEXT | NOT NULL | 部门负责人 |
| `summary` | TEXT | NOT NULL DEFAULT '' | 本周计划概述 |
| `major_risks_json` | TEXT | NOT NULL DEFAULT '[]' | 本周主要风险 |
| `dependencies_json` | TEXT | NOT NULL DEFAULT '[]' | 关键依赖 |
| `status` | TEXT | NOT NULL DEFAULT 'draft' | `draft / active / closed` |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

唯一索引：
- `uniq_org_department_plans_department_week`

### `org_department_plan_items`

用途：
- 部门周计划中的具体计划项。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 计划项 id |
| `plan_id` | TEXT | NOT NULL | 所属计划头 |
| `focus_item_id` | TEXT | NULL | 关联机构目标 |
| `title` | TEXT | NOT NULL | 计划项标题 |
| `statement` | TEXT | NOT NULL DEFAULT '' | 计划项说明 |
| `owner_user_id` | TEXT | NULL | 负责推进人 |
| `status` | TEXT | NOT NULL DEFAULT 'active' | `active / paused / done / dropped` |
| `expected_output` | TEXT | NOT NULL DEFAULT '' | 预期产出 |
| `sort_order` | INTEGER | NOT NULL DEFAULT 0 | 排序 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

### `task_plan_links`

用途：
- 稳定记录任务和计划的关系。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `task_id` | TEXT | PK | 任务 id |
| `department_plan_item_id` | TEXT | NULL | 归属的部门计划项 |
| `focus_item_id` | TEXT | NULL | 归属的机构目标 |
| `linked_by` | TEXT | NOT NULL DEFAULT 'ai' | `ai / manager / rule` |
| `confidence` | REAL | NOT NULL DEFAULT 0 | 自动挂接置信度 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

### `support_requests`

用途：
- 把支持需求从复盘文本里抽出来。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 支持请求 id |
| `task_id` | TEXT | NULL | 来源任务 |
| `requester_user_id` | TEXT | NOT NULL | 发起人 |
| `target_scope` | TEXT | NOT NULL | `manager / department / org / cross_department` |
| `target_ref_id` | TEXT | NULL | 目标部门/人/机构 |
| `request_type` | TEXT | NOT NULL | `resource / decision / collaboration / workload / clarification` |
| `urgency` | TEXT | NOT NULL DEFAULT 'medium' | `high / medium / low` |
| `summary` | TEXT | NOT NULL | 请求摘要 |
| `status` | TEXT | NOT NULL DEFAULT 'open' | `open / accepted / resolved / dismissed` |
| `resolution_note` | TEXT | NOT NULL DEFAULT '' | 处理说明 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

## 3.3 P1 API 清单

### 机构目标
- `GET /api/v1/settings/org-model/focus-items?period=2026-Q1`
- `POST /api/v1/settings/org-model/focus-items`
- `PATCH /api/v1/settings/org-model/focus-items/{focusItemId}`
- `DELETE /api/v1/settings/org-model/focus-items/{focusItemId}`

### 部门周计划
- `GET /api/v1/settings/org-model/department-plans?weekLabel=2026-W12`
- `POST /api/v1/settings/org-model/department-plans`
- `PATCH /api/v1/settings/org-model/department-plans/{planId}`
- `POST /api/v1/settings/org-model/department-plans/{planId}/items`
- `PATCH /api/v1/settings/org-model/department-plan-items/{itemId}`
- `DELETE /api/v1/settings/org-model/department-plan-items/{itemId}`

### 任务挂接
- `GET /api/v1/tasks/{taskId}/plan-link`
- `PATCH /api/v1/tasks/{taskId}/plan-link`
- `POST /api/v1/tasks/{taskId}/plan-link/recompute`

### 支持请求
- `GET /api/v1/support-requests?status=open`
- `POST /api/v1/support-requests`
- `PATCH /api/v1/support-requests/{requestId}`
- `POST /api/v1/support-requests/{requestId}/resolve`

## 3.4 P1 页面落地

### 页面 A：机构目标页

用途：
- 维护季度重点，不再散落在 DNA 文本里。

模块：
- 季度切换
- 目标项列表
- 负责人
- 优先级
- 当前状态

### 页面 B：部门周计划页

用途：
- 部门负责人每周维护本部门重点计划。

模块：
- 周次切换
- 部门选择
- 计划项列表
- 风险与依赖
- 目标映射

### 页面 C：支持请求页

用途：
- 统一看本周需要谁支持什么。

模块：
- 支持请求列表
- 请求类型筛选
- 紧急程度
- 当前状态
- 处理动作

## 3.5 P1 与任务/总结的嫁接

任务创建/编辑后，后台自动尝试：
- 挂部门计划项
- 挂机构目标项
- 从复盘中抽出支持请求

部门总结新增真实判断：
- 本周任务支撑了哪些部门计划项
- 哪些计划项没人接住
- 哪些支持请求没有被响应

机构总结新增真实判断：
- 哪些部门计划在支撑机构重点
- 哪些部门计划与机构季度重点脱钩

## 3.6 P1 验收标准

系统至少要能回答：
1. 这条任务服务哪条部门计划、哪条机构目标。
2. 这个部门本周计划里，哪些有人承接，哪些没有。
3. 哪些未完成任务形成了正式支持请求。
4. 部门总结能稳定输出“计划对齐”和“支持响应”。

---

## 4. P2 规格：复核与流程执行层

## 4.1 P2 必做对象

1. `TaskReviewRequest`
- 任务变更或提交后触发的复核对象。

2. `TaskReviewAction`
- 审批、退回、补充说明等动作日志。

3. `TaskWorkflowState`
- 任务当前处于岗位流程的哪一步。

4. `ActionSuggestion`
- AI 总结转动作的中间对象。

## 4.2 P2 表结构

### `task_review_requests`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 复核请求 id |
| `task_id` | TEXT | NOT NULL | 来源任务 |
| `requester_user_id` | TEXT | NOT NULL | 发起人 |
| `reviewer_user_id` | TEXT | NOT NULL | 复核人 |
| `request_type` | TEXT | NOT NULL | `content_change / owner_change / deadline_change / completion_review` |
| `status` | TEXT | NOT NULL DEFAULT 'pending' | `pending / approved / returned / cancelled / expired` |
| `reason` | TEXT | NOT NULL DEFAULT '' | 发起原因 |
| `sla_due_at` | TEXT | NULL | 最迟复核时间 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

### `task_review_actions`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 动作 id |
| `review_request_id` | TEXT | NOT NULL | 关联复核请求 |
| `actor_user_id` | TEXT | NOT NULL | 动作者 |
| `action_type` | TEXT | NOT NULL | `approve / return / comment / reassign_reviewer` |
| `note` | TEXT | NOT NULL DEFAULT '' | 备注 |
| `created_at` | TEXT | NOT NULL | 创建时间 |

### `task_workflow_states`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `task_id` | TEXT | PK | 任务 id |
| `process_template_id` | TEXT | NULL | 采用的流程模板 |
| `current_step_key` | TEXT | NOT NULL DEFAULT '' | 当前步骤 |
| `current_step_status` | TEXT | NOT NULL DEFAULT 'idle' | `idle / active / blocked / done` |
| `waiting_role_id` | TEXT | NULL | 正在等待的岗位 |
| `waiting_user_id` | TEXT | NULL | 正在等待的人 |
| `last_transition_at` | TEXT | NULL | 最近流转时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

### `task_action_suggestions`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 建议 id |
| `source_type` | TEXT | NOT NULL | `weekly_review / department_report / org_report` |
| `source_ref_id` | TEXT | NOT NULL | 来源对象 |
| `suggestion_type` | TEXT | NOT NULL | `create_task / create_support_request / request_review / create_meeting` |
| `title` | TEXT | NOT NULL | 建议标题 |
| `payload_json` | TEXT | NOT NULL DEFAULT '{}' | 动作参数 |
| `status` | TEXT | NOT NULL DEFAULT 'pending' | `pending / applied / dismissed` |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

## 4.3 P2 API 清单

### 复核
- `GET /api/v1/tasks/review-queue?status=pending`
- `POST /api/v1/tasks/{taskId}/review-requests`
- `POST /api/v1/tasks/review-requests/{requestId}/approve`
- `POST /api/v1/tasks/review-requests/{requestId}/return`
- `POST /api/v1/tasks/review-requests/{requestId}/comment`

### 流程状态
- `GET /api/v1/tasks/{taskId}/workflow-state`
- `PATCH /api/v1/tasks/{taskId}/workflow-state`
- `POST /api/v1/tasks/{taskId}/workflow-state/recompute`

### 动作建议
- `GET /api/v1/review-action-suggestions?sourceType=department_report`
- `POST /api/v1/review-action-suggestions/{id}/apply`
- `POST /api/v1/review-action-suggestions/{id}/dismiss`

## 4.4 P2 页面落地

### 页面 D：复核队列

用途：
- 给 manager / leader 统一处理待复核事项。

模块：
- 待复核列表
- 复核类型
- 发起人
- 超时状态
- 通过 / 退回 / 评论

### 页面 E：流程状态抽屉

用途：
- 在任务详情里解释“这件事卡在哪里”。

模块：
- 当前流程模板
- 当前步骤
- 正在等待的岗位/人员
- 最近动作
- 下一步建议

### 页面 F：总结动作栏

用途：
- 把 AI 的结论直接转成动作。

模块：
- 建议动作列表
- 一键转任务
- 一键转支持请求
- 一键发起会议
- 一键升级复核

## 4.5 P2 与任务/总结的嫁接

任务系统：
- 受控任务改动时，自动创建复核请求。
- 退回复核时，任务自动记录退回原因并回流执行侧。
- 流程状态与复核状态共同决定 `blockedAtStep` 和 `approvalState`。

周总结：
- 部门总结新增：
  - 复核超时
  - 流程堵点
  - 协作确认瓶颈
- 机构总结新增：
  - 哪条审批链过长
  - 哪类任务最常退回

## 4.6 P2 验收标准

系统至少要能回答：
1. 哪些任务正在待谁复核。
2. 某条任务最近一次被退回的原因是什么。
3. 某类任务常卡在流程第几步。
4. AI 总结中至少 1 条建议可以一键转成正式动作。

---

## 5. P3 规格：趋势、机器人一等化、业务对象层

## 5.1 P3 必做对象

1. `WeeklySignalSnapshot`
- 多周趋势判断所需的快照对象。

2. `RoleLoadSnapshot`
- leader 管理负荷和职责偏离趋势对象。

3. `BusinessObject`
- 抽象客户 / 项目 / 会议 / 产品迭代等业务对象。

4. `TaskBusinessObjectLink`
- 任务和业务对象的稳定挂接。

5. `WorkerIdentity`
- 把机器人和人类统一到同一套组织身份模型里。

## 5.2 P3 表结构

### `org_weekly_signal_snapshots`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 快照 id |
| `week_label` | TEXT | NOT NULL | 周次 |
| `scope_type` | TEXT | NOT NULL | `employee / department / organization` |
| `scope_ref_id` | TEXT | NOT NULL | 对应对象 |
| `signal_type` | TEXT | NOT NULL | `role_drift / approval_bottleneck / workflow_block / alignment_gap / overload` |
| `signal_score` | REAL | NOT NULL DEFAULT 0 | 信号强度 |
| `evidence_json` | TEXT | NOT NULL DEFAULT '[]' | 证据摘要 |
| `created_at` | TEXT | NOT NULL | 创建时间 |

### `org_role_load_snapshots`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 快照 id |
| `week_label` | TEXT | NOT NULL | 周次 |
| `user_id` | TEXT | NOT NULL | 人员 |
| `execution_task_count` | INTEGER | NOT NULL DEFAULT 0 | 执行型任务数 |
| `management_task_count` | INTEGER | NOT NULL DEFAULT 0 | 管理型任务数 |
| `review_queue_count` | INTEGER | NOT NULL DEFAULT 0 | 待复核量 |
| `overload_score` | REAL | NOT NULL DEFAULT 0 | 负荷分 |
| `created_at` | TEXT | NOT NULL | 创建时间 |

### `org_business_objects`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 业务对象 id |
| `object_type` | TEXT | NOT NULL | `client / project / meeting / product / campaign / initiative` |
| `title` | TEXT | NOT NULL | 名称 |
| `stage` | TEXT | NOT NULL DEFAULT '' | 当前阶段 |
| `goal_statement` | TEXT | NOT NULL DEFAULT '' | 关键目标 |
| `current_blockers_json` | TEXT | NOT NULL DEFAULT '[]' | 当前阻力 |
| `completeness_score` | REAL | NOT NULL DEFAULT 0 | 资料完整度 |
| `benchmark_potential` | INTEGER | NOT NULL DEFAULT 0 | 是否具备标杆潜力 |
| `source_type` | TEXT | NOT NULL DEFAULT 'manual' | `manual / client_workspace / meeting / ai` |
| `source_ref_id` | TEXT | NULL | 来源对象 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

### `task_business_object_links`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `task_id` | TEXT | PK | 任务 id |
| `business_object_id` | TEXT | NOT NULL | 业务对象 id |
| `linked_by` | TEXT | NOT NULL DEFAULT 'ai' | `ai / manager / rule` |
| `confidence` | REAL | NOT NULL DEFAULT 0 | 置信度 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

### `org_worker_identities`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `worker_id` | TEXT | PK | 主键 |
| `worker_type` | TEXT | NOT NULL | `human / agent` |
| `user_id` | TEXT | NULL | 对应员工账号 |
| `agent_key` | TEXT | NULL | 如 `qinghua / dazhou / jiale` |
| `department_id` | TEXT | NOT NULL | 部门 |
| `primary_role_id` | TEXT | NOT NULL | 主岗位 |
| `manager_user_id` | TEXT | NULL | 上级 |
| `active` | INTEGER | NOT NULL DEFAULT 1 | 是否启用 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

## 5.3 P3 API 清单

### 趋势
- `GET /api/v1/reviews/trends?scopeType=department&scopeRefId=dept_xxx&weeks=8`
- `GET /api/v1/reviews/load-trends?userId=user_xxx&weeks=8`

### 业务对象
- `GET /api/v1/business-objects`
- `POST /api/v1/business-objects`
- `PATCH /api/v1/business-objects/{objectId}`
- `GET /api/v1/tasks/{taskId}/business-object`
- `PATCH /api/v1/tasks/{taskId}/business-object`

### 机器人身份
- `GET /api/v1/settings/org-model/workers`
- `PATCH /api/v1/settings/org-model/workers/{workerId}`

## 5.4 P3 页面落地

### 页面 G：趋势洞察页

模块：
- 连续周趋势图
- 重复卡点
- 角色负荷
- 对齐率变化
- 复盘沉淀率变化

### 页面 H：业务对象页

模块：
- 客户 / 项目 / 会议 / 产品对象列表
- 当前阶段
- 关键目标
- 当前阻力
- 标杆潜力
- 关联任务

### 页面 I：机器人配置页

模块：
- 机器人身份绑定
- 所属部门
- 主岗位
- 汇报关系
- 是否参与复核 / 总结 / 趋势

## 5.5 P3 与任务/总结的嫁接

趋势：
- 每次周复盘提交后，生成本周信号快照。
- CEO 总结优先读取最近 4-8 周的趋势，而不是只看当前周。

业务对象层：
- 益语模式下，优先从客户工作台、meeting、goals、documents 自动生成业务对象。
- 通用模式下，可手工维护项目/活动/产品对象。

机器人一等化：
- 机器人使用和员工同一套部门、岗位、汇报线、任务控制规则。
- 机器人任务进入同一套趋势和负荷统计。

## 5.6 P3 验收标准

系统至少要能回答：
1. 哪个部门连续 3 周重复卡在同类问题。
2. 哪个 leader 连续 3 周管理负荷过高。
3. 某条任务归属哪个业务对象，目前业务对象处于什么阶段。
4. 机器人是否已作为正式岗位承接者进入同一套组织统计。

---

## 6. 依赖关系与实施顺序

### 6.1 依赖关系

- P1 依赖 P0 的部门 / 岗位 / 人员 / 汇报线 / 控制规则已可读写。
- P2 依赖 P0 的流程模板和控制规则，依赖 P1 的计划挂接和支持请求。
- P3 依赖 P1 的计划与目标对象，依赖 P2 的复核和流程状态。

### 6.2 推荐顺序

1. 先做 P1
2. 再做 P2
3. 最后做 P3

不要倒着做，原因：
- 没有正式计划对象，趋势会缺锚点。
- 没有复核和流程状态，趋势会只剩情绪化描述。
- 没有业务对象层，益语专属总结会长期停在“任务视角”。

---

## 7. 总体验收标准

当 P1-P3 全部落地后，系统至少要稳定做到：

1. 员工端仍然只填极轻输入，但部门/机构总结能做深判断。
2. 每条任务都能回答：
- 属于谁的职责
- 支撑哪条部门计划
- 支撑哪条机构目标
- 当前卡在谁、卡在第几步
- 是否需要正式支持

3. 部门总结能回答：
- 部门计划是否被承接
- 卡点主要出在执行、权限、协作还是流程
- 哪些问题已经连续出现

4. CEO 总结能回答：
- 哪个部门在真正推进季度重点
- 哪个部门在职责偏离或管理过载
- 哪些业务对象有标杆潜力
- 哪些风险在未来 2-3 周会继续放大
