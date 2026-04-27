# Retrieval Router Vector P0

## 当前已有 P0 完成项

- 已完成 `analysis_context.py` 统一上下文、`PageContextPack` 和 `AnswerPolicy`。
- 已完成客户/任务 `page-context` API 与 workspace chat 的兼容接入。
- 已完成状态不足 raw fallback、candidate 边界披露、AI 失败可读回退与回归测试。

## 当前检索链路缺口

- 向量模型与路由模型仍未抽象成可配置 provider。
- Qdrant collection 仍缺少 embedding signature 隔离，存在不同维度混用风险。
- 缺少 route decision / retrieval trace 的可观察对象。
- 缺少 shadow mode 对比记录与检索评测集。

## 向量 / 路由 / 重排职责划分

- `embedding`：负责召回覆盖率和语义相似度召回。
- `router`：负责问题类型判别、数据源选择、检索路径建议。
- `rerank`：负责在召回后的小候选集上做二阶段排序提纯。

## Shadow-First 原因

- 默认 `shadowMode=true`，先旁路评估新链路再考虑切主链。
- 用户答案仍走 baseline，避免新链路异常影响线上可用性。
- 通过 shadow runs 观察 overlap、latency、failure、candidateBetterRate 再决策。

## 新增对象

- `RetrievalModelSettings`：统一模型/路由/重排与 shadow 配置。
- `RouteDecision`：单次问题路由决策与解释。
- `RetrievalTrace`：检索过程命中与耗时跟踪。

## 边界与不做事项

- Router 仅做路由建议，不生成最终回答，不改 judgment，不绕过审批。
- 不自动写入 `approved judgment`。
- 不实现无限制外部抓取。
- 不默认切换到外部 embedding 主链；无 key 或失败时必须 fallback。
- P0 不接 `vision embedding` 主链，仅保留接口与 TODO。

## Embedding Signature 与索引规则

- signature 固定：`provider:model:dimension`。
- 不同 signature 必须写入不同 collection，禁止向量混用。
- signature 变更后标记 vector index `stale`，active collection 未 ready 必须回退 legacy。

## 回滚策略

- 将 retrieval settings 回退到：
  - `embeddingProvider=local_fastembed`
  - `routerEnabled=false`
  - `rerankEnabled=false`
  - `shadowMode=true`
- 若新 collection 异常，active 回退 legacy collection。
- 任何 router/smart-router 异常统一 fallback rules，保持旧链路可用。

