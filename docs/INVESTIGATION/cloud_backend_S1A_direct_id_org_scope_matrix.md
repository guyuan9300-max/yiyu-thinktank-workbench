# Cloud Backend S1A：Direct-ID 组织隔离矩阵

日期：2026-07-11
基线：`origin/sync-0.28.1` + `d699a87`（create-task 组织隔离修复）；本批起点 `32faaff`。
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
| `_task_attachment_row_or_404(state, attachment_id, task_id, organization_id)` | 强制 attachment + task + org 三重限定 | G | 转写入口现已先限定 task 组织与成员权限，再进入附件查询。 |
| `_task_org_link_row(state, task_id)` | 全局 task_id；缺 link 时调用 `_sync_task_org_link` | R | 这是读操作触发写入的 helper；调用前必须先限定 task 组织。 |
| `_task_collaborator_ids(state, task_id)` | 仅 task_id | Y | 只能在已组织限定的 task 之后调用。 |
| `_assert_task_visible_or_404(...)` | 当前组织内仅 admin / creator / owner / collaborator 可见；其余统一 404 | G | 必须位于权限 helper、派生写入和外部 I/O 之前。 |
| `_task_collaboration_for_actor_or_404(...)` | scoped task + 成员可见性 + actor 自己 + task/org JOIN | G | accept/return 共用 fail-closed 边界；异常跨组织关系也不会先写协作状态。 |
| `_task_record(...)` | creator/owner/list/collaborator/attachment/note/link 多处按全局 ID 聚合 | Y | 当前依赖“入口 task 已限定 + ID 全局唯一”；不得把它当组织授权边界。 |

## 4. Task / attachment / org-link 路由矩阵

| 路由 | 操作 | 当前第一道约束 | 静态状态 | 动态验证/处置 |
|---|---|---|---:|---|
| `GET /api/v1/tasks` | 列表读 | SQL `tasks.organization_id = current org` | G | 现有组织列表契约；非本批重点。 |
| `GET /api/v1/tasks/{task_id}` | 单项读 | scoped task + 成员可见性 | G | 跨组织及同组织 outsider 均 404。 |
| `POST /api/v1/tasks` | 新建 | list、owner、collaborator 均限定当前 org | G | `test_task_create_org_scope.py` 6 个用例已覆盖。 |
| `PATCH /api/v1/tasks/{task_id}` | 更新 | scoped task 后权限判断 | G | 跨组织 admin 404；task/collab/activity/link 零变化。 |
| `DELETE /api/v1/tasks/{task_id}` | 删除 | scoped task 后权限判断 | G | 跨组织 404；task/activity/link/附件文件均保留。 |
| `POST /api/v1/tasks/{task_id}/attachments` | DB + 文件上传 | scoped task 后权限判断 | G | 跨组织 404；无 attachment 行、目录或文件副作用。 |
| `POST /api/v1/tasks/{task_id}/attachments/{attachment_id}/transcribe-to-document` | 外部 AI + 文档写入 | scoped task + 成员可见性 + 编辑授权，再查附件/文件 | G | 异常跨组织附件及同组织 outsider 均 404；文件读取、ASR、文档沉淀、摘要和数据库活动均零调用/零写入。 |
| `POST /api/v1/tasks/{task_id}/collaborators/{user_id}/accept` | 协作者状态写入 | scoped task + 成员可见性 + actor 自己 + org JOIN | G | 跨组织异常关系、同组织 outsider 均 404/零写入；合法 collaborator 自己保留 200。 |
| `POST /api/v1/tasks/{task_id}/collaborators/{user_id}/return` | 协作者状态写入 | scoped task + 成员可见性 + actor 自己 + org JOIN | G | 同上；更新语句再次用 task organization `EXISTS` 防御。 |
| `POST /api/v1/tasks/{task_id}/complete-with-review` | 完成/复盘写入 | scoped task + 成员可见性，再进入完成 helper | G | 跨组织与同组织 outsider 均 404；status/note/activity 零变化；creator/owner/collaborator/admin 合法路径保留。 |
| `POST /api/v1/tasks/{task_id}/review/approve` | org-link 写入 | scoped task + 成员可见性 + admin，再调用 `_task_org_link_row` | G | 跨组织与 outsider 404；link/task/activity 零变化；本组织 admin 合法路径保留。 |
| `POST /api/v1/tasks/{task_id}/review/return` | org-link 写入 | scoped task + 成员可见性 + admin，再调用 `_task_org_link_row` | G | 同上。 |
| `POST /api/v1/tasks/{task_id}/note` | note + activity 写入 | scoped task + 成员可见性 + 编辑授权 | G | 跨组织和同组织 outsider 均 404/零写入；合法成员与 admin 保留语义。 |
| `GET /api/v1/tasks/{task_id}/activity` | 活动明细读 | scoped task + 成员可见性 | G | 跨组织和同组织 outsider 均 404，不泄漏活动内容。 |
| `GET /api/v1/tasks/{task_id}/plan-link` | org-link 读 | 全局 task 后手工比 org | Y | scoped helper 替换，动态证明 404。 |
| `POST /api/v1/tasks/{task_id}/plan-link/recompute` | org-link + activity 写入 | 全局 task 后手工比 org | Y | 当前比 org 在 helper 前，但改 scoped helper 消除迟限定。 |
| `PATCH /api/v1/tasks/{task_id}/plan-link` | org-link 写/删 | scoped task 位于可写 link helper 之前 | G | 跨组织 404 且 link/activity 零新增。 |
| `GET /api/v1/org-model/plan-items/{item_id}/tasks` | 反向关联读 | link org + task org 双限定 | G | 保留。 |

## 5. Owner / collaborator / list 关系矩阵

| 入口 | 关系字段 | 当前验证 | 状态 | 后续动态断言 |
|---|---|---|---:|---|
| task create | `ownerId`, `collaboratorIds` | `_get_org_user_or_404` | G | 已覆盖跨组织 404、零 task/collab/activity。 |
| task create | `listId` | 当前组织 active list，否则回退本组织默认 list | G | 已覆盖缺失/归档/跨组织回退与不变量。 |
| task update | `ownerId`, `collaboratorIds` | `_get_org_user_or_404`，且位于 mutation 前 | G | 跨组织关系 404，task/collab/mentions/activity/link 均不变；本组织 owner/collaborator 合法更新通过。 |
| task update | `listId` | 当前组织 active-list resolver 的返回值参与写入 | G | 跨组织/缺失/归档 ID 均回退本组织默认 list，不再写入原始不可信 ID。 |
| event-line create/update | `ownerId` | `_get_org_user_or_404`，且位于 event-line/activity 写入前 | G | 跨组织 owner 404，零副作用。 |
| event-line create/update | `participantIds` | 每个 ID 由 `_get_org_user_or_404` 校验 | G | 跨组织或不存在 participant 统一 404，零副作用；同组织合法成员保留。 |
| event-line create/update | `primaryDepartmentId` | `id + current organization` 查询 | G | 跨组织/不存在部门 404，零副作用。 |
| event-line create/update | `primaryClientId` | 先查当前组织，再探测全局是否属于其他组织 | G/Y | 已存在于其他组织的 client 404；全局不存在的本地优先 opaque ID 为兼容桌面同步暂保留，后续首次镜像时仍须防 ID 碰撞。 |
| task-list PATCH/DELETE | `list_id` | 首次读取 `id + organization_id` | G | 后续按 ID 写删依赖全局唯一；入口已限定。 |

## 6. Event-line direct-ID 路由矩阵

event-line 增加两层 actor 边界：`private` 仅 owner / participant / admin 可读，`project_public` 可由同组织成员读取；PATCH、上传、时间线重生成、close/reopen、merge、delete 等 mutation 仅 owner / participant / admin 可执行。跨组织或同组织无权 actor 统一 404。

以下认证路由均先使用 `_event_line_row_or_404(state, id, current_user.organizationId)`，再按读/写边界校验，静态与动态判定为 G：

- `GET /api/v1/event-lines/{event_line_id}`
- `GET /api/v1/event-lines/{event_line_id}/report-snapshot`
- `GET /api/v1/event-lines/{event_line_id}/timeline-narrative`
- `POST /api/v1/event-lines/{event_line_id}/timeline-narrative/regenerate`
- `POST /api/v1/event-lines/{event_line_id}/attachments`
- `PATCH /api/v1/event-lines/{event_line_id}`
- `POST /api/v1/event-lines/{event_line_id}/close`
- `POST /api/v1/event-lines/{event_line_id}/reopen`
- `POST /api/v1/event-lines/{event_line_id}/merge-preview`
- `POST /api/v1/event-lines/{event_line_id}/merge`
- `DELETE /api/v1/event-lines/{event_line_id}`
- `POST /api/v1/event-lines/{event_line_id}/attachments/download-zip`

列表接口也按上述可见性逐条过滤；detail/record 中 owner、participant、department、client、activity actor 的名称聚合均增加组织限定。merge 的 source 可管理性在 client 一致性和迁移写入前校验，带 `organization_id` 的子表更新、计数与 cache 清理均再次限定当前组织。

保留风险：`POST /api/v1/event-lines/import-desktop` 仍是单批非事务导入，且本地 opaque client ID 的镜像/碰撞策略未统一；应在独立批次加入全批回滚、跨组织 client 拒绝和 ID 重映射测试。

## 7. Public attachment 契约

以下四个接口按全局 `attachment_id` 提供文件或派生内容，且允许 task attachment 与 event-line attachment 互相回退：

- `GET /api/public/task-attachments/{attachment_id}`
- `GET /api/public/task-attachments/{attachment_id}/thumbnail`
- `GET /api/public/task-attachments/{attachment_id}/text-content`
- `GET /api/public/task-attachments/{attachment_id}/ocr-summary`

静态判定为 C，当前四条均可由匿名请求凭全局可猜 ID 读取；OCR 还会匿名消耗全局方舟 key，并把下游异常文本带回响应。调用链同时包含 report snapshot / upload 返回的裸 URL、前端 renderer 的匿名 text/OCR 请求、桌面代理（仅 raw 路径附带 bearer）以及需要公网 URL 的豆包 ASR，因此不能只改单个路由签名。

后续必须作为一次协调迁移实施：

1. thumbnail/text/OCR 改为登录态并做 attachment + task/event-line + org + actor 可见性校验；OCR 使用该组织自己的 `org_ai_config`，增加限流、缓存和审计。
2. 仅为外部 ASR 保留 purpose-bound HMAC URL，签名至少覆盖 `version + kind + attachment_id + organization_id + purpose + expires_at`，短期有效且可轮换。
3. 同步更新 report/upload URL 生产者、renderer、桌面代理和按 org/sandbox 分槽的本地缓存；完成旧 URL 迁移和密钥轮换后禁用裸 ID。
4. RED 门禁覆盖跨组织 raw/thumbnail/text/OCR、过期/错 purpose/错 org/篡改签名、组织 key 选择、匿名限流与旧 URL 失效。本批遵守“不可半改公开签名”的约束，仅完成审计，不改线上契约。

## 8. 本批动态测试矩阵

| ID | 场景 | 预期 RED 原因 | GREEN 门禁 |
|---|---|---|---|
| S1A-T1 | 本组织 admin PATCH 外组织 task | admin 权限作用于全局 task | 404；标题/updated_at/collab/activity/link 不变。 |
| S1A-T2 | 本组织 admin DELETE 外组织 task | admin 可删除全局 task | 404；task 及关联数据仍存在。 |
| S1A-T3 | 本组织 admin 上传附件到外组织 task | 先全局命中再写 DB/磁盘 | 404；无 attachment 行、无新文件、evidence 不变。 |
| S1A-T4 | 本组织用户写外组织 task note | 无组织/可见性校验 | 404；无 note/activity。 |
| S1A-T5 | 本组织用户读外组织 task activity | 无组织/可见性校验 | 404；响应不含活动内容。 |
| S1A-T6 | PATCH 外组织 task plan-link（缺 link） | 404 前 `_task_org_link_row` 自动建 link | 404；无 link/activity。 |
| S1A-T7 | 当前组织附件行异常指向外组织 task 后请求转写 | 全局 task + admin 放行，读取文件并调用 ASR/文档/摘要 | 404；文件读取、三个外部/沉淀 helper 均 0 调用，task/attachment/activity/knowledge 零变化。 |
| S1A-T8 | 同组织 outsider 请求成员 task 转写 | 编辑 helper 先建 link，随后 403 | 404；link、文件、AI、文档、活动均零副作用。 |
| S1A-T9 | creator / owner / collaborator / admin 合法转写 | 收紧边界可能误伤合法成员 | 四种角色均 200；各调用一次文件读取、ASR、文档沉淀和摘要。 |
| S1A-T10 | 当前组织 actor 的异常 collaborator 行指向外组织 task，accept/return | 先按 task + user 查关系并写状态，跨组织两条路径均 200 | 404；协作行、task 状态、activity、link 均不变。 |
| S1A-T11 | 同组织 outsider 代操作合法 collaborator 的 accept/return | actor 自检早于 task 可见性，返回可区分的 403 | 404；协作状态和活动零变化。 |
| S1A-T12 | 合法 collaborator 操作自己的 accept/return | 收紧边界可能破坏既有收件箱语义 | 两条路径均 200；仅自己的关系与对应活动按预期变化。 |

S1A-T1～T12 已实施；以下为本批扩展门禁。

| ID | 场景 | GREEN 门禁 |
|---|---|---|
| S1A-T13 | complete-with-review 跨组织 / 同组织 outsider | 404；task/note/activity/link 快照不变。 |
| S1A-T14 | creator / owner / collaborator / admin 合法完成 | 均保留 200 与预期状态变化。 |
| S1A-T15 | review approve/return 跨组织 / outsider 与合法 admin | 越权 404/零写入；合法 admin 200。 |
| S1A-T16 | task PATCH owner/collaborator/list | 外组织关系 404/零写入；非法 list 回退本组织默认；合法本组织关系通过。 |
| S1A-T17 | event-line create/update 外组织 owner/participant/department/client | 404；event-line/activity/同步传播零副作用。 |
| S1A-T18 | private/project_public detail/list | private outsider 404/列表排除；owner/participant/admin 可读；project_public 同组织可读。 |
| S1A-T19 | event-line PATCH actor 与跨组织 direct-ID | outsider/跨组织 404、快照不变；owner/participant/admin 合法更新。 |

S1A-T13～T19 已实施；public attachment 签名迁移与 import-desktop 事务化进入后续协调批次。

## 9. 实施结果

- 第一批 direct-ID mutation：RED **6 failed**，GREEN **6 passed**；全量由冻结基线 **15 failed, 149 passed** 增至 **15 failed, 155 passed**，失败集合不变。
- 第二批同组织成员可见性/备注：RED `test_task_direct_id_org_scope.py` **2 failed, 10 passed**，GREEN **12 passed**；全量 **15 failed, 161 passed**，失败集合不变。
- 本批转写/协作者收件箱：RED 新增边界集 **6 failed, 6 passed**；跨组织转写实际返回 200 并完成文件读取、ASR、文档沉淀和摘要，跨组织 accept/return 实际返回 200 并改变协作状态，同组织 outsider 暴露为 403。
- 本批 GREEN：新增边界集 **12 passed**；`test_task_direct_id_org_scope.py` + 原有 `test_task_attachment_transcribe.py` 合计 **26 passed**。
- 当前全量：**15 failed, 173 passed**（188 tests，98.51s）；15 个失败节点与第 2 节冻结基线逐项完全相同，新增 12 个测试全部通过，无新增失败。
- 当前已转为 G 的入口：task detail、PATCH、DELETE、attachment upload/transcribe、note、activity、collaborator accept/return、plan-link PATCH。所有这些入口均在权限判断、可写 link helper、数据库 mutation、文件读取或外部 AI/文档 helper 之前完成当前组织与成员边界校验。
- 本批 task 完成/复核与关系字段：RED **12 failed, 7 passed**，GREEN **19 passed**。
- 本批 event-line 关系与可见性：RED **10 failed, 5 passed**，GREEN **15 passed**；与原有 event-line 相关回归合计 **22 passed**。
- 本批聚焦门禁：`test_task_direct_id_org_scope.py` + `test_event_line_org_scope.py` 合计 **58 passed**；`compileall app/main.py` 通过。
- 本批最终全量：**15 failed, 207 passed**（222 tests，97.99s）；15 个失败节点与第 2 节冻结基线逐项完全相同，新增 34 个测试全部通过，无新增失败。
- 当前新增转为 G 的入口：complete-with-review、review approve/return、task PATCH 的 owner/collaborator/list，以及 event-line 的 create/update/detail/list/report/timeline/upload/close/reopen/merge/delete/zip actor 与组织边界。
