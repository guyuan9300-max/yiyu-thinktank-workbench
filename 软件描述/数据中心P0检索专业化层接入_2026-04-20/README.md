# 数据中心 P0 检索专业化层源码包（2026-04-20）

## 1. 本包说明
本目录收录了本轮 **P0 检索专业化层** 的源码导出（按 MD 分文件）。
目标是：在已有 PageContextPack/AnswerPolicy 基础上，补齐向量模型配置、路由决策、shadow 安全回退、检索追踪与相关 API/类型/测试。

## 2. 我已完成的内容
- 新增检索配置服务：`retrieval_model_settings.py`
- 新增 embedding provider 抽象：`embedding_provider.py`
- 新增 query router：`query_router.py`
- 新增 rerank provider：`rerank_provider.py`
- 新增 shadow run 服务：`retrieval_shadow.py`
- 新增评测脚本：`backend/scripts/eval_retrieval_p0.py`
- 扩展后端模型：`RetrievalModelSettingsRecord`、`RouteDecisionRecord`、`RetrievalTraceRecord`、`RetrievalHealthRecord`、`RetrievalShadow*`
- 扩展 `PageContextPack`：`routeDecision`、`retrievalTrace`
- 扩展 `KnowledgeStatus`：embedding/router/rerank/vector index 状态字段
- 后端新增 API：
  - `GET /api/v1/retrieval/settings`
  - `POST /api/v1/retrieval/settings`
  - `GET /api/v1/retrieval/health`
  - `POST /api/v1/clients/{client_id}/knowledge/reindex-vector`
  - `GET /api/v1/retrieval/shadow-runs`
  - `GET /api/v1/retrieval/shadow-summary`
- `workspace/chat` 接入 RouteDecision/RetrievalTrace，新增 retrievalSummary 字段（兼容保留旧字段）
- 新增多子查询轻量检索与 rule-rerank 接入点
- 新增测试：
  - `test_retrieval_model_settings_p0.py`
  - `test_embedding_provider_p0.py`
  - `test_query_router_p0.py`
  - `test_workspace_chat_router_shadow_p0.py`
  - `test_retrieval_shadow_eval_p0.py`
- 新增评测样例：`backend/tests/fixtures/retrieval_eval_cases.json`（20 条）

## 3. 我还没有做（明确留到后续）
- vision embedding 主链接入（仅保留策略层空间）
- 外部 rerank provider 正式接入（仅保留接口）
- Smart Router 生产主链全量启用（当前默认 `shadowMode=true`）
- meeting/mobile/topic/strategic cockpit 的完整 page-context 接入
- external evidence 抓取执行链路

## 4. 安全边界（本轮保持）
- 不自动写入 approved judgment
- 不绕过 approval/resolver
- 不删除 FastEmbed/hash fallback 旧链路
- 凭证不写入 settings（继续走 Keychain）

## 5. 代码导出清单
- `01_backend_services_retrieval_model_settings.md`
- `02_backend_services_embedding_provider.md`
- `03_backend_services_query_router.md`
- `04_backend_services_rerank_provider.md`
- `05_backend_services_retrieval_shadow.md`
- `06_backend_services_analysis_context_关键片段.md`
- `07_backend_services_knowledge_base_关键片段.md`
- `08_backend_services_knowledge_v2_关键片段.md`
- `09_backend_main_检索层改动片段.md`
- `10_backend_models_新增结构片段.md`
- `11_backend_scripts_eval_retrieval_p0.md`
- `12_backend_tests_新增测试代码.md`
- `13_frontend_types_新增结构片段.md`
- `14_frontend_api_新增接口片段.md`
