# Feishu Single-Bot Phase 1 Plan

## Goal

在不改客户工作台核心架构的前提下，为益语智库增加一个飞书单机器人入口。

Phase 1 只解决两件事：

1. 单机器人显式切换客户上下文
2. 资讯情报站的每日摘要推送

## Hard Constraints

- 只有一个飞书机器人。
- 客户专属问答必须先显式切换客户，再开始问答。
- 不新增旁路客户问答机制。
- 不重做客户工作台检索、长期记忆、线程架构。
- 飞书日推不能改变当前客户上下文。

## Existing Mechanisms To Reuse

现有客户工作台已经有完整的客户隔离机制，Phase 1 直接复用：

- 前端客户切换：`currentClientId`
- 后端客户聚合入口：`workspace_for_client(client_id)`
- 客户 DNA 与长期语境：`dna_terms`、`client_dna_documents`
- 客户问答入口：`/api/v1/clients/{client_id}/workspace/chat/start`
- 客户内聊天线程：`chat_threads`
- 客户内聊天消息：`chat_messages`
- 客户内分析运行：`client_analysis_runs`

结论：飞书层只做 `feishu_session -> client_id -> existing_thread_id` 的映射，不改上述主链路。

## Do Not Touch In Phase 1

- `workspace_for_client(client_id)` 的聚合结构
- `build_client_dna_context / build_client_dna_priority_note / build_client_dna_retrieval_hint`
- 现有 `/api/v1/clients/{client_id}/workspace/chat*` 路由语义
- 客户工作台前端 `currentClientId -> refreshWorkspace()` 切换逻辑

## New Tables

### 1) `channel_sessions`

用途：记录一个飞书会话当前绑定哪个客户。

建议字段：

- `id`
- `channel`，固定 `feishu`
- `conversation_key`
- `conversation_type`，例如 `p2p` / `group_thread`
- `user_external_id`
- `active_client_id`
- `status`，`idle` / `client_bound` / `awaiting_client_choice`
- `last_message_at`
- `created_at`
- `updated_at`

说明：

- `conversation_key` 在私聊场景可直接用 `user_open_id`
- 群聊场景建议用 `chat_id + thread_id`
- `active_client_id` 为空时，机器人不得回答客户专属问题

### 2) `channel_session_client_threads`

用途：同一个飞书会话下，为每个客户映射一条现有客户工作台线程。

建议字段：

- `id`
- `session_id`
- `client_id`
- `chat_thread_id`
- `last_used_at`
- `created_at`
- `updated_at`

说明：

- 这样切回老客户时，可以恢复该客户之前那条 thread
- 避免多个客户混进一条 `chat_threads`

### 3) `channel_push_subscriptions`

用途：记录谁每天早上接收资讯摘要。

建议字段：

- `id`
- `channel`，固定 `feishu`
- `receiver_external_id`
- `receiver_type`，如 `user`
- `digest_kind`，Phase 1 固定 `topic_daily_summary`
- `schedule_time`
- `timezone`
- `enabled`
- `created_at`
- `updated_at`

### 4) `channel_delivery_logs`

用途：记录日推与问答回发，便于查重和排障。

建议字段：

- `id`
- `channel`
- `receiver_external_id`
- `delivery_type`，`topic_daily_summary` / `chat_reply`
- `source_key`
- `status`
- `detail_json`
- `created_at`

## New API Surface

Phase 1 只增加外围路由，不替换客户工作台现有路由。

### Session APIs

- `POST /api/v1/channels/feishu/sessions/resolve-client`
  - 输入：自然语言中的客户名或显式切换文本
  - 输出：精确命中 / 候选列表 / 未命中

- `POST /api/v1/channels/feishu/sessions/{conversation_key}/switch-client`
  - 输入：`clientId`
  - 行为：写入 `channel_sessions.active_client_id`
  - 输出：确认文本与当前绑定客户

- `GET /api/v1/channels/feishu/sessions/{conversation_key}`
  - 输出：当前绑定客户、当前状态、最近更新时间

- `POST /api/v1/channels/feishu/sessions/{conversation_key}/clear-client`
  - 行为：清空 `active_client_id`

### Chat Relay API

- `POST /api/v1/channels/feishu/sessions/{conversation_key}/relay-chat`
  - 输入：用户消息文本
  - 行为：
    1. 读取当前 `active_client_id`
    2. 从 `channel_session_client_threads` 取该客户的现有 `thread_id`
    3. 复用现有客户问答入口
    4. 更新该客户对应的 `chat_thread_id`
  - 输出：回答文本、当前客户、thread 关联信息

### Topic Digest APIs

- `POST /api/v1/channels/feishu/topic-digest/preview`
  - 复用现有 topics 能力，生成单次摘要预览

- `POST /api/v1/channels/feishu/topic-digest/deliver`
  - 按订阅配置执行一次推送

## Runtime Boundary

Phase 1 的飞书机器人与定时推送不应依赖 Electron 窗口保持打开。

原因：

- 当前本地后端跟随桌面应用启动
- 如果桌面窗口关闭，日推无法保证执行

因此建议：

- 客户工作台问答逻辑仍复用本仓已有后端
- 飞书 bridge 与定时调度运行在常驻进程
- 常驻进程通过新增的 channel APIs 调用本仓能力

如果短期内只能本地运行，则需要接受一个限制：

- 只有软件开着时，机器人问答与日推才可用

## Message Flow

### A. 切换客户

1. 用户发：`切换到 XX 客户`
2. bridge 调 `resolve-client`
3. 命中唯一客户后调 `switch-client`
4. 机器人回：`已切换到 XX 客户数据库`

### B. 客户专属问答

1. 用户发普通问题
2. bridge 查 `channel_sessions.active_client_id`
3. 若为空，直接拦截并要求先切客户
4. 若存在：
   - 查 `channel_session_client_threads`
   - 调现有 `/api/v1/clients/{client_id}/workspace/chat/start`
   - 保存返回的 `threadId`
5. 机器人回答案，并附 `当前客户：XX`

### C. 日推

1. 调度器触发 topic digest
2. bridge 读取 `channel_push_subscriptions`
3. 为订阅用户发送摘要
4. 不修改任何 `channel_sessions.active_client_id`

## Mandatory Guardrails

### 1) No Silent Switch

- 没有显式切客户，不允许自动切
- 模糊命中时只返回候选，不进问答

### 2) No Global Qinhua Memory

- 不做“庆华全局切换记忆”
- 只做 `session -> active_client_id -> existing_thread_id`

### 3) Thread Ownership Check

当前 `ensure_chat_thread` 只校验 `thread_id` 是否存在，Phase 1 实现时必须确保外部映射层不会把其他客户的 thread 传进来。

最低要求：

- 查询与保存 `channel_session_client_threads` 时必须带 `client_id`
- relay-chat 前必须确认 `chat_thread_id` 属于当前 `client_id`

## Phase 1 File Touch Plan

只允许新增外围能力，不改现有客户工作台主链路语义：

- `backend/app/db.py`
  - 新增 channel tables
- `backend/app/models.py`
  - 新增 channel records / payloads / responses
- `backend/app/main.py`
  - 新增 channel helper 与 channel routes
- `backend/tests/test_api_smoke.py`
  - 新增 session switch / relay / digest smoke

暂不改：

- `src/renderer/App.tsx`
- `src/renderer/lib/api.ts`
- `backend/app/services/knowledge_base.py`

## Delivery Sequence

1. 建表
2. 客户解析与切换 API
3. relay-chat API
4. digest preview / deliver API
5. 常驻 bridge 接入飞书
6. 最后再决定是否补桌面端配置页面
