# 组织模型层落地计划（任务与周总结系统）

## 1. 目标定义

本期不是做一个好看的组织架构页，而是补一层可被系统和 AI 共同读取的“组织语义底座”，让以下能力从模拟走向真实：

- 部门总结
- CEO 机构总结
- 任务权限判断
- 岗位职责偏离分析
- 汇报线瓶颈分析
- 跨部门协作卡点分析

一句话原则：

`先搭组织关系 + 角色职责 + 权限规则 + 流程节点的最小底座，再让任务、周计划、周总结挂上去。`

---

## 2. 第一阶段必须嫁接上的能力

### 2.1 必须先有的 8 个能力

1. 机构层背景
- 年度目标
- 当前季度重点
- 负责人
- 管理层名单

2. 部门层模型
- 部门名称
- 部门负责人
- 上级部门
- 部门使命
- 本季度重点
- 核心协作部门

3. 岗位层模型
- 岗位名称
- 所属部门
- 岗位层级
- 汇报对象
- 是否管理岗
- 岗位目标
- 主要职责
- 不该长期承担的事务
- 关键协作岗位

4. 人员绑定岗位
- 姓名
- 部门
- 当前岗位
- 直属上级
- 是否管理岗
- 当前主责方向
- 可否调整任务

5. 汇报线 / 审批线 / 协作确认线
- 谁向谁汇报
- 是业务汇报还是行政汇报
- 谁审批谁的任务
- 谁能调整谁的任务
- 谁是跨部门协作确认人

6. 岗位流程模板
- 触发条件
- 关键步骤
- 需协作节点
- 需审批节点
- 产出物
- 常见卡点

7. 任务控制规则
- 控制级别
- 谁可改内容
- 谁可改时间
- 谁可改负责人
- 谁可取消任务
- 是否必须协作确认
- 默认审批人

8. 任务与组织关系映射
- 任务归属部门
- 任务主要岗位
- 关联部门重点
- 关联机构季度重点
- 是否跨部门
- 当前处于哪个流程节点

---

## 3. 第一阶段核心对象

本层先只做 7 个对象，不超过这个数量。

## 3.1 Organization

用途：
- 提供机构级战略背景
- 给 CEO 总结提供顶层参照

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | string | 是 | 主键 |
| name | string | 是 | 机构名称 |
| annual_goal | string | 是 | 年度目标，短句 |
| quarterly_focus | json[string] | 是 | 当前季度重点，1-5 条 |
| leader_user_id | string | 是 | 机构负责人 |
| management_user_ids | json[string] | 否 | 管理层名单 |
| updated_at | datetime | 是 | 更新时间 |

实现要求：
- `quarterly_focus` 必须结构化，不要只存一整段长文。

## 3.2 Department

用途：
- 作为部门总结、任务归属、部门对齐判断的基本单位

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | string | 是 | 主键 |
| organization_id | string | 是 | 所属机构 |
| name | string | 是 | 部门名称 |
| parent_department_id | string | 否 | 上级部门 |
| leader_user_id | string | 是 | 部门负责人 |
| mission | string | 是 | 部门使命，一句话 |
| quarterly_focus | json[string] | 是 | 本季度重点，最多 3 条 |
| core_partner_department_ids | json[string] | 否 | 核心协作部门 |
| active | bool | 是 | 是否启用 |
| updated_at | datetime | 是 | 更新时间 |

## 3.3 RoleTemplate

用途：
- 不是展示职位，而是提供“任务判断模板”

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | string | 是 | 主键 |
| department_id | string | 是 | 所属部门 |
| name | string | 是 | 岗位名称 |
| level | enum | 是 | `staff / supervisor / department_lead / executive` |
| reports_to_role_id | string | 否 | 典型汇报岗位 |
| is_manager | bool | 是 | 是否管理岗 |
| objective | string | 是 | 岗位目标，一句话 |
| responsibilities | json[string] | 是 | 主要职责，3-5 条 |
| anti_responsibilities | json[string] | 否 | 不该长期承担的事务 |
| key_partner_role_ids | json[string] | 否 | 关键协作岗位 |
| updated_at | datetime | 是 | 更新时间 |

## 3.4 EmployeeRoleBinding

用途：
- 把岗位模板落到具体人

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| user_id | string | 是 | 员工 |
| department_id | string | 是 | 当前部门 |
| primary_role_id | string | 是 | 主岗位 |
| manager_user_id | string | 否 | 直属上级 |
| is_manager | bool | 是 | 是否管理岗 |
| project_role_labels | json[string] | 否 | 附加项目角色 |
| current_focus | string | 否 | 当前阶段主责方向 |
| task_edit_scope | enum | 是 | `self / team / department / org` |
| updated_at | datetime | 是 | 更新时间 |

说明：
- 一个人只绑定一个主岗位。
- 项目角色只做补充，不替代主岗位。

## 3.5 ReportingLine

用途：
- 让系统知道真实组织链路，而不是只看组织图

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | string | 是 | 主键 |
| from_user_id | string | 是 | 发起方 |
| to_user_id | string | 是 | 接收方 |
| line_type | enum | 是 | `business / admin / approval / collaboration_confirm` |
| can_approve_tasks | bool | 是 | 可否审批任务 |
| can_reassign_tasks | bool | 是 | 可否改负责人 |
| can_change_deadline | bool | 是 | 可否改日期 |
| active | bool | 是 | 是否启用 |

## 3.6 RoleProcessTemplate

用途：
- 让 AI 知道“流程卡在哪一步”

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | string | 是 | 主键 |
| role_id | string | 是 | 适用岗位 |
| name | string | 是 | 流程名称 |
| trigger_condition | string | 是 | 触发条件 |
| output_artifact | string | 是 | 产出物 |
| common_blockers | json[string] | 否 | 常见卡点 |
| updated_at | datetime | 是 | 更新时间 |

子表 `role_process_steps`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | string | 是 | 主键 |
| process_id | string | 是 | 所属流程 |
| step_order | int | 是 | 顺序 |
| title | string | 是 | 步骤名称 |
| requires_collaboration | bool | 是 | 是否需协作 |
| requires_approval | bool | 是 | 是否需审批 |
| partner_role_ids | json[string] | 否 | 需协作岗位 |

## 3.7 TaskControlRule

用途：
- 把权限和任务控制规则结构化

建议字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | string | 是 | 主键 |
| scope_type | enum | 是 | `task_type / department / role / project` |
| scope_ref_id | string | 是 | 对应对象 |
| control_level | enum | 是 | `normal / leader_control / department_control / org_control` |
| can_edit_content_by | enum | 是 | `owner / manager / department / org` |
| can_edit_time_by | enum | 是 | 同上 |
| can_edit_owner_by | enum | 是 | 同上 |
| can_cancel_by | enum | 是 | 同上 |
| requires_confirmation_on_change | bool | 是 | 是否改动需确认 |
| default_approver_type | enum | 否 | `manager / department_lead / org_lead / none` |
| updated_at | datetime | 是 | 更新时间 |

---

## 4. 最小闭环关系

第一阶段只要打通这 4 条关系，就能开始产出真实组织判断。

1. 人 -> 岗位  
2. 岗位 -> 职责  
3. 人/岗位 -> 汇报线与权限  
4. 任务 -> 岗位/部门/机构季度重点

一旦这 4 条存在，AI 就可以开始做：
- 岗位职责偏离判断
- 部门任务对齐判断
- 机构目标对齐判断
- 权限瓶颈判断

---

## 5. 数据库设计建议

## 5.1 新增表

建议新增以下表：

- `org_profiles`
- `org_departments`
- `org_role_templates`
- `org_employee_role_bindings`
- `org_reporting_lines`
- `org_role_process_templates`
- `org_role_process_steps`
- `org_task_control_rules`

## 5.2 复用现有表

尽量复用当前已有：
- `employee_accounts`
- `tasks`
- `weekly_review_entries`
- `weekly_review_task_entries`
- `plan_nodes`
- `aggregated_scope_reports`

## 5.3 对现有任务表要补的字段

不建议一次改太重，但为了接上组织层，任务至少要多一层后台元数据，可先放进 `task_snapshot_json` 类似结构，后续再视情况升字段。

建议新增或衍生的后台字段：

| 字段 | 说明 |
|---|---|
| `department_id` | 任务主要归属部门 |
| `role_template_id` | 任务更接近哪个岗位职责 |
| `organization_focus_key` | 对应哪条季度重点 |
| `department_focus_key` | 对应哪条部门重点 |
| `is_cross_department` | 是否跨部门 |
| `approval_state` | 当前是否在审批链 |
| `blocked_at_step` | 卡在哪个流程步骤 |
| `control_rule_id` | 当前套用的任务控制规则 |

---

## 6. 页面结构（第一阶段只做 4 页）

## 6.1 页面一：组织总览页

目标：
- 让管理者快速看到机构、部门、负责人和基本汇报结构

模块：
- 机构卡片
- 当前季度重点
- 一级部门列表
- 简化树状组织关系图
- 管理层概览

本页定位：
- 轻展示
- 轻导航
- 不做重编辑中心

## 6.2 页面二：部门与岗位页

目标：
- 作为组织语义底座的核心编辑页

布局：
- 左侧：部门列表
- 右侧上部：部门使命 / 季度重点 / 协作部门
- 右侧下部：岗位卡片列表
- 点岗位后进入岗位详情抽屉或侧栏

岗位详情模块：
- 岗位目标
- 主要职责
- 不该长期承担
- 关键协作岗位
- 汇报对象
- 当前承接人

## 6.3 页面三：人员配置页

目标：
- 给每个人挂岗位、上级、项目角色和任务权限

模块：
- 人员列表
- 主岗位选择
- 部门选择
- 直属上级
- 是否管理岗
- 项目角色
- 任务编辑权限

页面原则：
- 只服务任务和总结系统
- 不做 HR 档案库

## 6.4 页面四：流程与权限页

目标：
- 管关键岗位流程和任务控制规则

模块：
- 岗位流程模板列表
- 流程步骤编辑器
- 任务控制规则列表
- 审批 / 协作确认链路说明

页面原则：
- 第一阶段只录关键岗位 2-3 条流程
- 不做全组织流程引擎

---

## 7. 与任务系统的嫁接方式

## 7.1 任务创建时

前台不新增复杂字段。

后台自动推断或推荐：
- 归属部门
- 归属岗位
- 是否跨部门
- 是否需要审批
- 可能采用哪条控制规则

## 7.2 任务协作时

协作记录要落到：
- 是否跨部门协作
- 协作确认人是谁
- 退回是执行问题还是权限问题
- 当前卡在哪个审批/汇报节点

## 7.3 周计划时

要接两层背景：
- 部门负责人周计划 -> 部门对象
- CEO 季度重点 -> 机构对象

之后部门总结才可以判断：
- 这周任务有没有支撑部门重点
- 部门重点有没有支撑机构重点

## 7.4 周总结时

员工端继续极简：
- 一段反思
- 一个轻量卡点

后台自动做：
- 任务 vs 岗位职责
- 任务 vs 部门重点
- 部门重点 vs 季度目标
- 阻塞 vs 汇报线 / 权限 / 流程

## 7.5 机器人系统

庆华 / 大周 / 佳乐不能继续只是外挂日志。

必须接入：
- 机器人也有部门
- 机器人也有岗位
- 机器人也有汇报线
- 机器人任务也挂部门/岗位/权限规则

这样部门总结和机构总结的执行样本才完整。

---

## 8. AI 可立即获得的判断能力

组织底座接完后，AI 可以稳定输出以下判断：

1. 职责偏离
- 某人长期做的事是否偏离岗位职责

2. 管理负荷
- leader 是否被执行细节淹没

3. 汇报线瓶颈
- 任务是否总卡在某个确认节点

4. 协作失配
- 某类任务理论上该有的角色是否长期缺位

5. 流程卡点
- 是不会做、没权限、任务不清还是流程有问题

6. 控制规则合理性
- 某类任务是否锁得过死或太松

---

## 9. 开发阶段计划

详细的 P1-P3 可执行规格见：
- [docs/org-model-p1-p3-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p1-p3-spec.md)

## P0：组织语义底座

目标：
- 把机构、部门、岗位、人员、汇报线、任务控制规则结构化

开发项：
- 新增 8 张底座表
- 新增 4 个设置页入口
- 完成人员绑定主岗位
- 完成部门负责人、直属上级、任务权限录入

验收：
- 系统能回答“谁属于哪个部门、哪个岗位、向谁汇报、拥有什么任务权限”

## P1：任务系统挂接

目标：
- 让任务可以挂到组织模型上

开发项：
- 任务后台自动推断部门 / 岗位 / 目标
- 任务协作事件映射到汇报线和审批线
- 机器人任务进入同一套组织模型

验收：
- 系统能回答“这条任务属于哪个部门 / 岗位 / 是否跨部门 / 当前是否在审批或等待节点”

## P2：周计划与周总结重构

目标：
- 用真实组织关系替换当前模拟判断

开发项：
- 部门负责人周计划接入部门对象
- CEO 季度重点接入机构对象
- 部门总结 / 机构总结重写
- 恢复并稳定输出对齐判断

验收：
- 部门总结能写出“任务是否支撑部门重点”
- 机构总结能写出“部门是否支撑季度重点”

## P3：流程判断与高级洞察

目标：
- 让 AI 开始判断“为什么卡”

开发项：
- 岗位流程模板录入
- 流程步骤挂接任务
- 输出流程卡点 / 协作失配 / 汇报瓶颈判断

验收：
- 系统能输出“卡在第几步、卡点更像流程问题还是权限问题”

---

## 10. 第一阶段明确不做

- 不做 HR 全量字段
- 不做复杂绩效评分
- 不做完整流程引擎
- 不做花哨组织图拖拽编辑器

---

## 11. 建议的实施顺序

1. 先录部门和岗位
2. 再录人员与权限
3. 再补汇报线
4. 再让任务挂接
5. 最后补岗位流程

这是成本最低、见效最快的路径。

---

## 12. 给开发的实现原则

组织模型层第一阶段不追求“完整的人事系统”，只追求形成 AI 可读的最小组织语义底座。该底座至少要让系统清楚知道：谁属于哪个部门，承担哪个岗位，向谁汇报，负责什么职责，遵循什么关键流程，拥有什么任务调整与审批权限。所有字段优先结构化、短句化、可枚举化，以支持后续任务判断、部门总结、组织洞察与预测分析。
