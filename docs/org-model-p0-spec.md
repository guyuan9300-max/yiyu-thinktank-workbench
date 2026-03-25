# 组织模型层 P0 规格（数据库 + 接口 + 页面字段）

> P1-P3 的延续规格见：[docs/org-model-p1-p3-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p1-p3-spec.md)

## 1. P0 范围

P0 只做组织语义底座，不做复杂流程引擎，不做 HR 档案库，不做绩效系统。

本阶段目标：

- 系统知道每个人属于哪个部门、哪个岗位
- 系统知道谁向谁汇报，谁有任务调整权
- 系统知道岗位本来负责什么，不该长期承担什么
- 系统能把任务挂到部门 / 岗位 / 季度重点上
- 为后续部门总结、机构总结、权限判断提供真实背景

P0 只覆盖：

- 机构
- 部门
- 岗位
- 人员绑定
- 汇报线
- 任务控制规则
- 任务与组织关系映射

---

## 2. P0 表结构

命名原则：

- 统一使用 `org_*` 前缀
- 复用现有 `employee_accounts`、`tasks`
- 先保守建表，避免一次侵入太多现有链路

## 2.1 `org_profiles`

用途：
- 存机构级背景

字段：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 机构 id |
| `name` | TEXT | NOT NULL | 机构名称 |
| `annual_goal` | TEXT | NOT NULL DEFAULT '' | 年度目标 |
| `quarterly_focus_json` | TEXT | NOT NULL DEFAULT '[]' | 当前季度重点 |
| `leader_user_id` | TEXT | NULL | 机构负责人 |
| `management_user_ids_json` | TEXT | NOT NULL DEFAULT '[]' | 管理层名单 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

建议：
- 默认一机构一条，可直接沿用当前组织维度。

## 2.2 `org_departments`

用途：
- 部门级背景和部门判断单位

字段：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 部门 id |
| `organization_id` | TEXT | NOT NULL | 所属机构 |
| `name` | TEXT | NOT NULL | 部门名称 |
| `parent_department_id` | TEXT | NULL | 上级部门 |
| `leader_user_id` | TEXT | NULL | 部门负责人 |
| `mission` | TEXT | NOT NULL DEFAULT '' | 部门使命 |
| `quarterly_focus_json` | TEXT | NOT NULL DEFAULT '[]' | 部门季度重点 |
| `core_partner_department_ids_json` | TEXT | NOT NULL DEFAULT '[]' | 核心协作部门 |
| `active` | INTEGER | NOT NULL DEFAULT 1 | 是否启用 |
| `sort_order` | INTEGER | NOT NULL DEFAULT 0 | 排序 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

索引：
- `idx_org_departments_org`
- `idx_org_departments_parent`

## 2.3 `org_role_templates`

用途：
- 岗位职责模板

字段：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 岗位模板 id |
| `department_id` | TEXT | NOT NULL | 所属部门 |
| `name` | TEXT | NOT NULL | 岗位名称 |
| `level` | TEXT | NOT NULL | `staff / supervisor / department_lead / executive` |
| `reports_to_role_id` | TEXT | NULL | 汇报岗位模板 |
| `is_manager` | INTEGER | NOT NULL DEFAULT 0 | 是否管理岗 |
| `objective` | TEXT | NOT NULL DEFAULT '' | 岗位目标 |
| `responsibilities_json` | TEXT | NOT NULL DEFAULT '[]' | 主要职责 |
| `anti_responsibilities_json` | TEXT | NOT NULL DEFAULT '[]' | 不应长期承担的事务 |
| `key_partner_role_ids_json` | TEXT | NOT NULL DEFAULT '[]' | 关键协作岗位 |
| `active` | INTEGER | NOT NULL DEFAULT 1 | 是否启用 |
| `sort_order` | INTEGER | NOT NULL DEFAULT 0 | 排序 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

索引：
- `idx_org_role_templates_department`

## 2.4 `org_employee_role_bindings`

用途：
- 把岗位模板绑定到具体员工

字段：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `user_id` | TEXT | PK | 员工 id |
| `department_id` | TEXT | NOT NULL | 当前所属部门 |
| `primary_role_id` | TEXT | NOT NULL | 主岗位 |
| `manager_user_id` | TEXT | NULL | 直属上级 |
| `is_manager` | INTEGER | NOT NULL DEFAULT 0 | 是否管理岗 |
| `project_role_labels_json` | TEXT | NOT NULL DEFAULT '[]' | 项目角色 |
| `current_focus` | TEXT | NOT NULL DEFAULT '' | 当前主责方向 |
| `task_edit_scope` | TEXT | NOT NULL DEFAULT 'self' | `self / team / department / org` |
| `can_approve_tasks` | INTEGER | NOT NULL DEFAULT 0 | 是否可审批任务 |
| `can_reassign_tasks` | INTEGER | NOT NULL DEFAULT 0 | 是否可改负责人 |
| `can_change_deadline` | INTEGER | NOT NULL DEFAULT 0 | 是否可改日期 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

建议：
- 这个表一人一条。
- 与 `employee_accounts.department_id` 保持同步，但以本表为任务与总结系统主来源。

## 2.5 `org_reporting_lines`

用途：
- 结构化业务汇报 / 行政汇报 / 审批线 / 协作确认线

字段：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 主键 |
| `from_user_id` | TEXT | NOT NULL | 发起方 |
| `to_user_id` | TEXT | NOT NULL | 接收方 |
| `line_type` | TEXT | NOT NULL | `business / admin / approval / collaboration_confirm` |
| `can_approve_tasks` | INTEGER | NOT NULL DEFAULT 0 | 可审批任务 |
| `can_reassign_tasks` | INTEGER | NOT NULL DEFAULT 0 | 可改负责人 |
| `can_change_deadline` | INTEGER | NOT NULL DEFAULT 0 | 可改日期 |
| `active` | INTEGER | NOT NULL DEFAULT 1 | 是否启用 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

索引：
- `idx_org_reporting_lines_from`
- `idx_org_reporting_lines_to`
- `idx_org_reporting_lines_type`

## 2.6 `org_task_control_rules`

用途：
- 统一任务控制权限规则

字段：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | 主键 |
| `scope_type` | TEXT | NOT NULL | `task_type / department / role / project` |
| `scope_ref_id` | TEXT | NOT NULL | 作用对象 |
| `control_level` | TEXT | NOT NULL | `normal / leader_control / department_control / org_control` |
| `can_edit_content_by` | TEXT | NOT NULL | `owner / manager / department / org` |
| `can_edit_time_by` | TEXT | NOT NULL | 同上 |
| `can_edit_owner_by` | TEXT | NOT NULL | 同上 |
| `can_cancel_by` | TEXT | NOT NULL | 同上 |
| `requires_confirmation_on_change` | INTEGER | NOT NULL DEFAULT 0 | 改动需确认 |
| `default_approver_type` | TEXT | NOT NULL DEFAULT 'none' | `manager / department_lead / org_lead / none` |
| `active` | INTEGER | NOT NULL DEFAULT 1 | 是否启用 |
| `created_at` | TEXT | NOT NULL | 创建时间 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

索引：
- `idx_org_task_control_rules_scope`

## 2.7 `task_org_links`

用途：
- 把任务和组织模型挂起来

字段：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `task_id` | TEXT | PK | 任务 id |
| `department_id` | TEXT | NULL | 主要归属部门 |
| `role_template_id` | TEXT | NULL | 主要归属岗位 |
| `organization_focus_key` | TEXT | NOT NULL DEFAULT '' | 机构季度重点 key |
| `department_focus_key` | TEXT | NOT NULL DEFAULT '' | 部门重点 key |
| `is_cross_department` | INTEGER | NOT NULL DEFAULT 0 | 是否跨部门 |
| `approval_state` | TEXT | NOT NULL DEFAULT 'none' | `none / pending / approved / rejected` |
| `blocked_at_step` | TEXT | NOT NULL DEFAULT '' | 当前卡点步骤 |
| `control_rule_id` | TEXT | NULL | 命中的控制规则 |
| `derived_from` | TEXT | NOT NULL DEFAULT 'manual' | `manual / ai / rule` |
| `confidence` | REAL | NOT NULL DEFAULT 0 | 推断置信度 |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

说明：
- 第一版不强求 100% 自动推断。
- 允许后台规则先写入，再由管理者修正。

---

## 3. P0 API 清单

原则：
- 先做内部设置型 API
- 只支持当前机构作用域
- 权限先收在 admin 和被明确授权的管理岗

## 3.1 机构接口

### `GET /api/v1/settings/org-model/profile`
- 返回当前机构组织模型总配置

返回：
- `organization`
- `departments[]`
- `roles[]`
- `bindings[]`
- `reportingLines[]`
- `taskControlRules[]`

### `POST /api/v1/settings/org-model/profile`
- 更新机构层背景

请求字段：
- `name`
- `annualGoal`
- `quarterlyFocus[]`
- `leaderUserId`
- `managementUserIds[]`

## 3.2 部门接口

### `GET /api/v1/settings/org-model/departments`

### `POST /api/v1/settings/org-model/departments`

### `PATCH /api/v1/settings/org-model/departments/{departmentId}`

### `DELETE /api/v1/settings/org-model/departments/{departmentId}`

限制：
- 第一版建议只支持“停用”，不做物理删除。

## 3.3 岗位接口

### `GET /api/v1/settings/org-model/roles?departmentId=...`

### `POST /api/v1/settings/org-model/roles`

### `PATCH /api/v1/settings/org-model/roles/{roleId}`

### `DELETE /api/v1/settings/org-model/roles/{roleId}`

## 3.4 人员绑定接口

### `GET /api/v1/settings/org-model/bindings`

### `PATCH /api/v1/settings/org-model/bindings/{userId}`

请求字段：
- `departmentId`
- `primaryRoleId`
- `managerUserId`
- `isManager`
- `projectRoleLabels[]`
- `currentFocus`
- `taskEditScope`
- `canApproveTasks`
- `canReassignTasks`
- `canChangeDeadline`

## 3.5 汇报线接口

### `GET /api/v1/settings/org-model/reporting-lines`

### `POST /api/v1/settings/org-model/reporting-lines`

### `PATCH /api/v1/settings/org-model/reporting-lines/{lineId}`

### `DELETE /api/v1/settings/org-model/reporting-lines/{lineId}`

## 3.6 任务控制规则接口

### `GET /api/v1/settings/org-model/task-control-rules`

### `POST /api/v1/settings/org-model/task-control-rules`

### `PATCH /api/v1/settings/org-model/task-control-rules/{ruleId}`

### `DELETE /api/v1/settings/org-model/task-control-rules/{ruleId}`

## 3.7 任务挂接接口

### `GET /api/v1/tasks/{taskId}/org-link`
- 返回当前任务的组织挂接结果。

### `PATCH /api/v1/tasks/{taskId}/org-link`
- 允许管理岗手工修正任务挂接。

请求字段：
- `departmentId`
- `roleTemplateId`
- `organizationFocusKey`
- `departmentFocusKey`
- `isCrossDepartment`
- `approvalState`
- `blockedAtStep`
- `controlRuleId`

### `POST /api/v1/tasks/{taskId}/org-link/recompute`
- 按当前任务标题、说明、负责人、协作者、客户背景，重新做一次后台自动判断。

## 4. 页面字段表

原则：
- 第一阶段只做 4 个页面
- 页面以“编辑组织语义底座”为目标，不做花哨图形交互
- 复杂判断先放后台，前台尽量做卡片化和表格化

## 4.1 页面一：组织总览页

目标：
- 快速看清当前机构、部门、负责人和管理关系

模块与字段：

| 模块 | 字段 |
| --- | --- |
| 机构卡 | 机构名称、年度目标、当前季度重点、机构负责人、管理层名单 |
| 部门概览区 | 部门名称、部门负责人、部门使命、本季度重点、核心协作部门 |
| 汇报关系总览 | 一级部门树、部门负责人、直属汇报关系数量 |
| 快捷入口 | 进入部门与岗位页、进入人员配置页、进入流程与权限页 |

操作：
- 查看机构整体配置
- 点击部门进入详情
- 从总览跳到人员或权限编辑

## 4.2 页面二：部门与岗位页

目标：
- 成为整个组织模型层的核心编辑中心

模块与字段：

| 模块 | 字段 |
| --- | --- |
| 部门列表 | 部门名称、负责人、上级部门、季度重点、协作部门 |
| 部门详情卡 | 部门使命、部门负责人、本季度重点、核心协作部门、状态 |
| 岗位卡片列表 | 岗位名称、岗位层级、是否管理岗、汇报对象、岗位目标 |
| 岗位详情区 | 主要职责、不该长期承担的事务、关键协作岗位、默认任务权限 |

操作：
- 新增/编辑部门
- 新增/编辑岗位
- 调整岗位顺序和状态
- 查看某岗位挂了哪些人员

## 4.3 页面三：人员配置页

目标：
- 让“人 -> 岗位 -> 上级 -> 权限”关系落地

模块与字段：

| 模块 | 字段 |
| --- | --- |
| 人员表格 | 姓名、所属部门、当前岗位、直属上级、是否管理岗 |
| 任务权限列 | 可否审批任务、可否调整负责人、可否调整截止日、任务编辑范围 |
| 项目角色列 | 当前负责客户/项目、附加项目角色、当前阶段主责方向 |
| 绑定详情抽屉 | 主岗位、直属上级、绑定说明、特殊覆盖权限 |

操作：
- 变更人员所属部门
- 变更人员主岗位
- 变更直属上级
- 配置特殊任务权限

## 4.4 页面四：流程与权限页

目标：
- 第一阶段先承载汇报线和任务控制规则
- 岗位流程模板作为 P1 再逐步补进来

模块与字段：

| 模块 | 字段 |
| --- | --- |
| 汇报线列表 | 发起人岗位、目标岗位、关系类型、审批权、改期权、改负责人权 |
| 任务控制规则列表 | 控制级别、适用部门/岗位、谁可改内容、谁可改时间、谁可改负责人、默认审批人 |
| 权限详情区 | 是否需要协作确认、是否允许取消任务、例外说明 |
| 预留流程区 | 流程名称、适用岗位、触发条件、步骤数、协作节点数 |

操作：
- 新增/编辑汇报线
- 新增/编辑任务控制规则
- 查看某部门当前生效的控制规则

## 5. 与现有任务系统的关联关系

## 5.1 创建任务时

后台需要在任务创建或编辑保存时，自动尝试补以下挂接：
- `departmentId`
- `roleTemplateId`
- `organizationFocusKey`
- `departmentFocusKey`
- `isCrossDepartment`
- `controlRuleId`

自动判断优先级：
1. 当前负责人所在部门与岗位
2. 当前创建人所在部门与岗位
3. 任务标题和说明中的关键词
4. 当前客户 / 项目背景
5. 协作者和历史相似任务

要求：
- 前台不新增复杂字段
- 后台自动挂接失败时允许为空，但要标记 `needsReview=true`

## 5.2 修改任务时

任务修改时需要走权限校验：
- 是否允许改内容
- 是否允许改时间
- 是否允许改负责人
- 是否允许取消任务
- 是否要求发起协作确认

P0 规则：
- 先做后台校验 + 前台阻断提示
- 暂不做完整审批工作流引擎
- 先把“能不能改”判断清楚

## 5.3 周计划 / 周总结时

周计划和周总结需要读这层组织模型做背景判断：
- `org_profiles.quarterly_focus_json`
- `org_departments.quarterly_focus_json`
- `org_role_templates.responsibilities_json`
- `org_reporting_lines`
- `org_task_control_rules`
- `task_org_links`

这样 AI 才能在总结里判断：
- 任务是否偏离岗位职责
- 部门工作是否偏离部门季度重点
- 某个问题是执行问题、权限问题还是汇报线问题

## 6. 迁移和落地顺序

## 6.1 第一步：先建表，不急着接复杂 UI

目标：
- 先让底层结构存在
- 先能录入和读取

动作：
- 本地 backend 建表
- cloud backend 建表
- models 和 db 初始化补齐
- 先保留空数据兼容，不影响当前任务系统运行

## 6.2 第二步：先做设置页

优先落地：
- 组织总览页
- 部门与岗位页
- 人员配置页
- 流程与权限页

要求：
- 所有字段都走结构化表单
- 不做大段自由文本输入
- 不做复杂组织图拖拽编辑器

## 6.3 第三步：接任务挂接

把组织模型接到任务系统：
- 创建任务时自动挂接
- 编辑任务时自动重算
- 提供管理岗手工修正入口
- 把控制规则接到“谁可改任务”判断里

## 6.4 第四步：接周总结

把组织模型接到：
- 个人周总结
- 部门总结
- CEO 机构总结

优先做的判断：
- 职责偏离
- 管理负荷
- 协作失配
- 权限瓶颈
- 季度重点偏离

## 7. P0 验收标准

完成 P0 后，系统至少要能回答：
1. 某个人属于哪个部门、哪个岗位、向谁汇报
2. 某个人是否具备审批、改期、改负责人权限
3. 某条任务属于哪个部门、哪个岗位职责范围
4. 某条任务是否属于跨部门任务
5. 某条任务当前受哪条控制规则约束
6. 某部门本周任务是否明显偏离本季度重点

不要求在 P0 完成的能力：
- 完整流程引擎
- 自动绩效评分
- 花哨组织图交互
- 全组织全岗位流程模板

## 8. 实现原则

- 先做结构，不先做漂亮图
- 字段优先短、硬、可枚举
- 复杂判断尽量放后台，不加重前台录入负担
- 机器人和人类共用同一套组织模型
- 第一优先级是让 AI 能判断，不是让页面看起来像 HR 系统
