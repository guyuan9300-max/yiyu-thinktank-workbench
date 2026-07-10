# Cloud Backend S1A：Direct-ID 组织隔离矩阵

日期：2026-07-11  
基线：`origin/sync-0.28.1` + `d699a87`（create-task 组织隔离修复）  
范围：`cloud_backend/app/main.py` 中 task、attachment、owner、collaborator、org-link、event-line 的 direct-ID 读写、上传与删除路径。

## 1. 判定标准

- **G（已限定）**：第一次读取目标资源时即同时使用 `id + current_user.organizationId`，后续写入只基于该已限定对象；跨组织统一 404，且不会写数据库或文件。
- **Y（迟限定/待动态证明）**：先按全局 ID 读取，之后再比对组织；表面响应可为 404，但仍需证明比对前无查询派生写入。
- **R（可利用或存在明确副作用窗口）**：按全局 ID 读取后执行权限判断、派生同步或写入；跨组织管理员、异常关联数据或可猜 ID 可触发泄漏/修改。
- **C（契约待定）**：接口被命名为 public，当前无组织身份上下文；不能只加组织过滤，需先决定签名 URL、分享 token 或认证契约。

统一修复原则：优先复用 `_get_org_*` / `_task_row_or_404(..., organization_id=...)` / `_event_line_row_or_404(...)`，在任何权限判断、派生 helper 或 I/O 之前完成组织限定；不做大重构。

## 2. 测试基线（修复前冻结）

命令：`python3 -m pytest cloud_backend/tests -q --tb=no`

结果：**15 failed, 149 passed**。已知失败节点如下，后续全量验证不得增加失败集合：

- `test_auth_tasks.py`（8）：`test_register_approve_login_and_collaboration_flow`、`test_personal_growth_content_is_self_only_and_excluded_from_team_report`、`test_task_overdue_only_after_calendar_day_ends`、`test_org_model_profile_roundtrip`、`test_task_org_link_and_department_control_permissions`、`test_task_plan_link_and_support_request_flow`、`test_task_review_approve_and_return_follow_org_permissions`、`test_org_model_backfill_restores_missing_task_links_for_existing_tasks`
- `test_bootstrap_security.py`（1）：`test_seed_password_from_env_refreshes_existing_admin_login`
- `test_local_first_auth.py`（3）：`test_cloud_registration_without_organization_name_uses_default_name`、`test_cloud_registration_uses_local_organization_name`、`test_cloud_registration_conflicting_email_returns_binding_guidance`
- `test_mobile_consult_contract.py`（1）：`test_thin_context_chat_returns_limited_context_metadata`
- `test_org_object_storage_config.py`（1）：`test_admin_writes_and_member_reads_object_storage_secret`
- `test_simulation_seed.py`（1）：`test_seed_simulated_review_org_populates_week_and_visibility`

## 3. Helper 边界

| Helper | 当前约束 | 状态 | 结论 |
|---|---|---:|---|
| `_task_row_or_404(state, task_id, organization_id=...)` | 传入组织时 `id + organization_id`；省略时全局 ID | Y | 所有认证 direct-ID 路由必须显式传组织；禁止依赖可选参数默认值。 |
| `_event_line_row_or_404(state, event_line_id, organization_id)` | 强制 `id + organization_id` | G | event-line direct-ID 路由应继续统一复用。 |
| `_task_attachment_row_or_404(state, attachment_id, task_id, organization_id)` | 强制 attachment + task + org 三重限定 | G | 转写路径的附件本身已安全，但它之前的 task 读取仍未限定。 |
| `_task_org_link_row(state, task_id)` | 全局 task_id；缺 link 时调用 `_sync_task_org_link` | R | 这是读操作触发写入的 helper；调用前必须先限定 task 组织。 |
| `_task_collaborator_ids(state, task_id)` | 仅 task_id | Y | 只能在已组织限定的 task 之后调用。 |
| `_task_record(...)` | creator/owner/list/collaborator/attachment/note/link 多处按全局 ID 聚合 | Y | 当前依赖“入口 task 已限定 + ID 全局唯一”；不得把它当组织授权边界。 |

## 4. Task / attachment / org-link 路由矩阵

| 路由 | 操作 | 当前第一道约束 | 静态状态 | 动态验证/处置 |
|---|---|---|---:|---|
| `GET /api/v1/tasks` | 列表读 | SQL `tasks.organization_id = current org` | G | 现有组织列表契约；非本批重点。 |
| `GET /api/v1/tasks/{task_id}` | 单项读 | 全局 task 后手工比 org/成员 | Y | 应改为 scoped helper；动态证明跨组织 404。 |
| `POST /api/v1/tasks` | 新建 | list、owner、collaborator 均限定当前 org | G | `test_task_create_org_scope.py` 6 个用例已覆盖。 |
| `PATCH /api/v1/tasks/{task_id}` | 更新 | 全局 task 后权限判断 | R | **本批首选**：跨组织 admin 现可修改；断言 404、task/collab/activity/link 均不变。 |
| `DELETE /api/v1/tasks/{task_id}` | 删除 | 全局 task 后权限判断 | R | **本批首选**：断言 404、task/activity/link/附件文件均保留。 |
| `POST /api/v1/tasks/{task_id}/attachments` | DB + 文件上传 | 全局 task 后权限判断 | R | **本批首选**：断言 404、无 attachment 行、无目录/文件、task evidence 不变。 |
| `POST /api/v1/tasks/{task_id}/attachments/{attachment_id}/transcribe-to-document` | 外部 AI + 文档写入 | task 全局；attachment 三重限定 | R | 先 scoped task；后续补“AI 未调用、知识请求/活动零写入”动态桩。 |
| `POST /api/v1/tasks/{task_id}/collaborators/{user_id}/accept` | 协作者状态写入 | 先查 task_id + user_id，再全局 task | R | 必须先 scoped task，再查协作者；异常跨组织关联也应 404/零写入。 |
| `POST /api/v1/tasks/{task_id}/collaborators/{user_id}/return` | 协作者状态写入 | 先查 task_id + user_id，无 scoped task | R | 同上。 |
| `POST /api/v1/tasks/{task_id}/complete-with-review` | 完成/复盘写入 | 全局 task 后权限判断 | R | scoped task；断言 status/note/activity 不变。 |
| `POST /api/v1/tasks/{task_id}/review/approve` | org-link 写入 | 全局 task 后调用可写 `_task_org_link_row` | R | scoped task 必须位于 link helper 之前。 |
| `POST /api/v1/tasks/{task_id}/review/return` | org-link 写入 | 全局 task 后调用可写 `_task_org_link_row` | R | 同上。 |
| `POST /api/v1/tasks/{task_id}/note` | note + activity 写入 | 全局 task；无 task 可见性/编辑校验 | R | **本批首选**：先保证跨组织 404/零写入；同组织“谁可写备注”另做产品契约测试。 |
| `GET /api/v1/tasks/{task_id}/activity` | 活动明细读 | 全局 task；无 org/成员校验 | R | **本批首选**：跨组织活动内容不可泄漏，统一 404。 |
| `GET /api/v1/tasks/{task_id}/plan-link` | org-link 读 | 全局 task 后手工比 org | Y | scoped helper 替换，动态证明 404。 |
| `POST /api/v1/tasks/{task_id}/plan-link/recompute` | org-link + activity 写入 | 全局 task 后手工比 org | Y | 当前比 org 在 helper 前，但改 scoped helper 消除迟限定。 |
| `PATCH /api/v1/tasks/{task_id}/plan-link` | org-link 写/删 | **先**调用可写 `_task_org_link_row`，后比 org | R | **本批首选**：跨组织现可能“返回 404 但生成 link”；断言 link/activity 零新增。 |
| `GET /api/v1/org-model/plan-items/{item_id}/tasks` | 反向关联读 | link org + task org 双限定 | G | 保留。 |

## 5. Owner / collaborator / list 关系矩阵

| 入口 | 关系字段 | 当前验证 | 状态 | 后续动态断言 |
|---|---|---|---:|---|
| task create | `ownerId`, `collaboratorIds` | `_get_org_user_or_404` | G | 已覆盖跨组织 404、零 task/collab/activity。 |
| task create | `listId` | 当前组织 active list，否则回退本组织默认 list | G | 已覆盖缺失/归档/跨组织回退与不变量。 |
| task update | `ownerId`, `collaboratorIds` | `_get_user_or_404`（全局） | R | 跨组织成员应 404，task/collab/mentions/activity/link 均不变。 |
| task update | `listId` | resolver 已限定，但写入仍使用原始 `payload.listId` | R | 跨组织/缺失/归档 ID 必须写 resolver 返回的本组织 list ID。 |
| event-line create/update | `ownerId` | `_get_user_or_404`（全局） | R | 跨组织 owner 应 404，event-line/activity 均不变。 |
| event-line create/update | `participantIds` | 未逐个按组织校验 | R | 跨组织 participant 应 404 或过滤；需先冻结产品契约。 |
| event-line create/update | `primaryDepartmentId` | create 按全局 ID 查名称；update 原样写入 | R | 只允许当前组织部门；跨组织 ID 统一 404/零写入。 |
| event-line create/update | `primaryClientId` | `_client_row_by_id(..., current org)` | G/Y | 找不到时当前可写 ID 但 name 为空；需决定 404 还是清空后再测。 |
| task-list PATCH/DELETE | `list_id` | 首次读取 `id + organization_id` | G | 后续按 ID 写删依赖全局唯一；入口已限定。 |

## 6. Event-line direct-ID 路由矩阵

以下认证路由均在首个业务 helper 中使用 `_event_line_row_or_404(state, id, current_user.organizationId)`，静态判定为 G：

- `GET /api/v1/event-lines/{event_line_id}`
- `GET /api/v1/event-lines/{event_line_id}/report-snapshot`
- `POST /api/v1/event-lines/{event_line_id}/attachments`
- `PATCH /api/v1/event-lines/{event_line_id}`
- `POST /api/v1/event-lines/{event_line_id}/close`
- `POST /api/v1/event-lines/{event_line_id}/reopen`
- `POST /api/v1/event-lines/{event_line_id}/merge-preview`
- `POST /api/v1/event-lines/{event_line_id}/merge`
- `DELETE /api/v1/event-lines/{event_line_id}`
- `POST /api/v1/event-lines/{event_line_id}/attachments/download-zip`

保留风险：event-line 对 owner/participant/department/client 的输入关系校验见上一节；merge 的 source IDs 需要动态确认每个 source 都使用当前 org 过滤。

## 7. Public attachment 契约

以下四个接口按全局 `attachment_id` 提供文件或派生内容，且允许 task attachment 与 event-line attachment 互相回退：

- `GET /api/public/task-attachments/{attachment_id}`
- `GET /api/public/task-attachments/{attachment_id}/thumbnail`
- `GET /api/public/task-attachments/{attachment_id}/text-content`
- `GET /api/public/task-attachments/{attachment_id}/ocr-summary`

静态判定为 C。它们被录音转写的外部 provider URL 和 event-line 上传返回值使用，直接改为登录态会破坏现有调用。建议单独设计不可猜签名 URL（attachment + org + expiry + purpose）或一次性 share token，并让旧裸 ID URL 经过迁移期后失效；本批不擅自改变公开契约。

## 8. 本批动态测试矩阵

| ID | 场景 | 预期 RED 原因 | GREEN 门禁 |
|---|---|---|---|
| S1A-T1 | 本组织 admin PATCH 外组织 task | admin 权限作用于全局 task | 404；标题/updated_at/collab/activity/link 不变。 |
| S1A-T2 | 本组织 admin DELETE 外组织 task | admin 可删除全局 task | 404；task 及关联数据仍存在。 |
| S1A-T3 | 本组织 admin 上传附件到外组织 task | 先全局命中再写 DB/磁盘 | 404；无 attachment 行、无新文件、evidence 不变。 |
| S1A-T4 | 本组织用户写外组织 task note | 无组织/可见性校验 | 404；无 note/activity。 |
| S1A-T5 | 本组织用户读外组织 task activity | 无组织/可见性校验 | 404；响应不含活动内容。 |
| S1A-T6 | PATCH 外组织 task plan-link（缺 link） | 404 前 `_task_org_link_row` 自动建 link | 404；无 link/activity。 |

本批只做上述六个高风险、契约明确的边界；转写、协作者收件箱、完成/复核、task update 关系字段、event-line 输入关系与 public attachment 进入后续有界批次。

## 9. 本批实施结果

- RED（修复前）：`test_task_direct_id_org_scope.py` **6 failed**；分别实证越权更新、越权删除、越权附件落盘/入库、越权备注、活动内容泄漏，以及 404 前隐式创建 org-link。
- GREEN（修复后）：同文件 **6 passed**；`test_task_create_org_scope.py` + 本批测试合计 **12 passed**。
- 全量：**15 failed, 155 passed**；失败节点集合与第 2 节冻结基线完全相同，新增 6 个测试全部通过，无新增失败。
- 已转为 G 的入口：task PATCH、DELETE、attachment upload、note、activity、plan-link PATCH。它们现在都在任何权限、link helper、数据库写入或文件 I/O 前，以 `_task_row_or_404(..., organization_id=current_user.organizationId)` 完成组织限定。
