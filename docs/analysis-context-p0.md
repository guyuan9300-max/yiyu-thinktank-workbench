# Analysis Context P0

## 当前复用的现有函数

- `workspace_for_client`（仅在路由层复用，不下沉到 service）
- `get_client_analysis_bundle`（复用 analysis center 聚合对象）
- `list_judgment_versions` / `list_open_questions` / `list_conflict_groups` / `list_theme_clusters` / `list_runtime_run_logs`
- `resolve_judgment_bundle` / `resolve_context_pack`
- `fetch_document_cards` / `retrieve_knowledge_bundle`
- `get_client_notebook_response` / `get_client_memory_status` / `get_event_line_memory_response` / `get_task_memory_enrichment`

## 新增 PageContextPack 字段（camelCase）

- `page` / `scopeType` / `scopeId` / `clientId` / `intent`
- `officialJudgments` / `candidateJudgments` / `overlayJudgments`
- `evidenceCards` / `rawEvidence`
- `openQuestions` / `conflicts` / `themeClusters`
- `relatedTasks` / `relatedMeetings` / `relatedDocuments`
- `notebookSummary` / `memoryFacts`
- `contextPack` / `judgmentBundle` / `resolutionTrace` / `stateProjection`
- `missingContext` / `boundaryNotes` / `sourceSummary`
- `answerPolicy` / `retrievalPlan` / `quality`

## 本阶段接入页面

- `client_workspace`
- `workspace_chat`
- `task_detail`
- `task_ai`

## 暂不接入页面

- `meeting_detail`
- `mobile_consult`
- `topic_radar`
- `strategic_cockpit`

## Fallback 策略

- 状态对象强（`strong|usable`）时允许 `analysis-first`，并保持 state-first 优先。
- 介绍/证据问法强制证据下钻（document cards + raw retrieval）。
- 状态不足时自动进入 evidence/raw fallback，不直接弱回答。
- 无 approved 但有 candidate 时走候选回答，显式边界披露。
- 全部资料不足时返回 `insufficient` + `missingContext` + proposal 建议。
- AI 失败时统一走可读 fallback，不暴露内部字段和过程词。

## 不做事项

- 不实现完整虚拟公司自治控制平面。
- 不自动写入 `approved judgment`。
- 不绕过 approval 边界写入正式层。
- 不实现无边界外部联网抓取。
- 不删除旧链路（保留 legacy retrieval 兜底）。
- 不做大规模前端重写。
