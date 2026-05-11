# backend/app 本地后端索引

## 目录结构

```
backend/app/__init__.py
backend/app/db.py
backend/app/local_request_guard.py
backend/app/main.py
backend/app/models.py
backend/app/services/__init__.py
backend/app/services/action_suggestion_service.py
backend/app/services/agent_worklogs.py
backend/app/services/ai.py
backend/app/services/analysis_center.py
backend/app/services/analysis_context.py
backend/app/services/answer_layer.py
backend/app/services/badge_engine.py
backend/app/services/client_profile.py
backend/app/services/data_center_access.py
backend/app/services/data_center_artifacts.py
backend/app/services/data_center_ingest.py
backend/app/services/data_center_kernel.py
backend/app/services/data_center_operational_status.py
backend/app/services/data_center_prep.py
backend/app/services/data_center_profiler.py
backend/app/services/data_center_proposal.py
backend/app/services/data_center_quality.py
backend/app/services/data_center_rollback_drill.py
backend/app/services/data_center_schema.py
backend/app/services/data_center_search.py
backend/app/services/data_center_shadow.py
backend/app/services/data_center_sync.py
backend/app/services/department_catalog.py
backend/app/services/diagnosis_engines.py
backend/app/services/digital_asset_center.py
backend/app/services/digital_asset_narrative.py
backend/app/services/embedding_provider.py
backend/app/services/event_line_timeline.py
backend/app/services/evidence_quality.py
backend/app/services/evidence_quality_feedback.py
backend/app/services/evidence_quality_feedback_snapshot.py
backend/app/services/evidence_quality_store.py
backend/app/services/evidence_selector.py
backend/app/services/execution_retry_metrics.py
backend/app/services/experience_story_engine.py
backend/app/services/external_evidence.py
backend/app/services/feishu.py
backend/app/services/feishu_sync.py
backend/app/services/generation_runtime_policy.py
backend/app/services/growth_engine.py
backend/app/services/internet_crawler.py
backend/app/services/kernel_primary_rollout.py
backend/app/services/knowledge_base.py
backend/app/services/knowledge_v2.py
backend/app/services/learning_presets.py
backend/app/services/link_material_import.py
backend/app/services/local_memory.py
backend/app/services/local_model_optimizer.py
backend/app/services/local_semantic_router.py
backend/app/services/meeting_context.py
backend/app/services/meeting_followup.py
backend/app/services/memory_foundation.py
backend/app/services/organization_dna_v2.py
backend/app/services/platform_dna.py
backend/app/services/proposal_approval.py
backend/app/services/proposal_execution.py
backend/app/services/query_router.py
backend/app/services/question_focus.py
backend/app/services/rerank_provider.py
backend/app/services/retrieval_model_settings.py
backend/app/services/retrieval_shadow.py
backend/app/services/review_analysis.py
backend/app/services/review_narrative.py
backend/app/services/review_rollup.py
backend/app/services/review_simulation.py
backend/app/services/secrets.py
backend/app/services/self_heal.py
backend/app/services/source_integrity.py
backend/app/services/source_reachability.py
backend/app/services/source_semantics.py
backend/app/services/system_logger.py
backend/app/services/task_context_brief_engine.py
backend/app/services/template_fill.py
backend/app/services/topic_capture.py
backend/app/services/topic_data_center.py
backend/app/services/topic_source_fetcher.py
backend/app/services/understanding_builder.py
backend/app/services/version_manifest.py
backend/app/services/weekly_review_material_pack.py
backend/app/services/workspace_action_perspective.py
backend/app/services/workspace_answer_experience.py
backend/app/services/workspace_answer_finalizer.py
backend/app/services/workspace_answer_value_diagnostics.py
backend/app/services/workspace_chat_diagnostics.py
backend/app/services/workspace_chat_kernel_bridge.py
backend/app/services/workspace_context_refresh.py
backend/app/services/workspace_data_center_adapter.py
backend/app/services/workspace_file_search.py
backend/app/services/workspace_followups.py
backend/app/services/workspace_query_router.py
backend/app/services/workspace_relation_docs.py
backend/app/services/workspace_thread_memory.py
```

## backend/app/main.py 路由表（method + path + handler）

总行数：43381

### FastAPI 装饰器（按行号）
```
24377:    @app.get("/api/public/task-attachments/{attachment_id}")
24462:    @app.get("/api/public/task-attachments/{attachment_id}/thumbnail")
24482:    @app.get("/api/public/task-attachments/{attachment_id}/text-content")
24573:    @app.get("/api/public/task-attachments/{attachment_id}/ocr-summary")
24621:    @app.post("/api/v1/event-lines/{event_line_id}/attachments/download-zip")
24644:    @app.get("/api/v1/brain/dashboard")
24724:    @app.get("/api/v1/digital-assets/dashboard", response_model=DigitalAssetDashboardRecord)
24850:    @app.get("/api/v1/digital-assets/organization-dna", response_model=OrganizationDnaV2SnapshotRecord)
24854:    @app.post("/api/v1/digital-assets/organization-dna/refresh", response_model=OrganizationDnaRefreshRunRecord)
24860:    @app.get("/api/v1/clients/{client_id}/digital-assets", response_model=DigitalAssetClientDetailRecord)
24869:    @app.post("/api/v1/clients/{client_id}/digital-assets/narrative/refresh", response_model=DigitalAssetNarrativeRecord)
24882:    @app.get("/api/v1/system/health", response_model=HealthResponse)
24900:    @app.get("/api/v1/system/health-check")
24914:    @app.post("/api/v1/system/self-heal")
24929:    @app.post("/api/v1/system/diagnose")
24942:    @app.get("/api/v1/system/heal-log")
24980:    @app.get("/api/v1/auth/me", response_model=AuthStateResponse)
25028:    @app.get("/api/v1/account/overview", response_model=AccountOverviewResponse)
25074:    @app.get("/api/v1/local-input-memory", response_model=LocalInputMemoryResponse)
25078:    @app.post("/api/v1/local-input-memory/cloud-auth", response_model=LocalInputMemoryResponse)
25154:    @app.post("/api/v1/local-input-memory/ai", response_model=LocalInputMemoryResponse)
25172:    @app.post("/api/v1/local-input-memory/feishu", response_model=LocalInputMemoryResponse)
25196:    @app.get("/api/v1/me/org-membership", response_model=OrgMembershipSummaryRecord)
25208:    @app.post("/api/v1/me/org-membership/apply", response_model=OrgMembershipSummaryRecord)
25227:    @app.get("/api/v1/org-integrations/feishu", response_model=OrgFeishuIntegrationRecord)
25243:    @app.post("/api/v1/org-integrations/feishu/validate-and-save", response_model=OrgFeishuIntegrationRecord)
25256:    @app.get("/api/v1/me/feishu-authorization", response_model=FeishuMemberAuthorizationRecord)
25279:    @app.post("/api/v1/me/feishu-authorization/start", response_model=FeishuMemberAuthorizationStartResponse)
25288:    @app.delete("/api/v1/me/feishu-authorization", response_model=FeishuMemberAuthorizationRecord)
25305:    @app.get("/api/v1/auth/department-options", response_model=list[DepartmentOptionRecord])
25325:    @app.get("/api/v1/auth/invite-code/resolve", response_model=OrgInviteResolveResultRecord)
25339:    @app.post("/api/v1/auth/register", response_model=AuthStateResponse)
25362:    @app.post("/api/v1/auth/login", response_model=AuthStateResponse)
25384:    @app.post("/api/v1/auth/change-password")
25389:    @app.patch("/api/v1/auth/me", response_model=AuthStateResponse)
25400:    @app.post("/api/v1/auth/logout", response_model=AuthStateResponse)
25483:    @app.get("/api/v1/consultation/knowledge-requests", response_model=list[ConsultationKnowledgeRequestRecord])
25492:    @app.post(
25519:    @app.get("/api/v1/admin/employees", response_model=list[EmployeeRecord])
25529:    @app.get("/api/v1/settings/org-model/profile", response_model=OrgModelProfileRecord)
25554:    @app.post("/api/v1/settings/org-model/profile", response_model=OrgModelProfileRecord)
25567:    @app.post("/api/v1/settings/org-model/intro-document", response_model=OrgIntroDocumentRecord)
25571:    @app.post("/api/v1/settings/org-model/backfill-task-links", response_model=TaskOrgBackfillResultRecord)
25578:    @app.get("/api/v1/event-lines", response_model=list[EventLineRecord])
25598:    @app.post("/api/v1/event-lines", response_model=EventLineRecord)
25674:    @app.get("/api/v1/event-lines/{event_line_id}", response_model=EventLineDetailRecord)
25694:    @app.post("/api/v1/event-lines/{event_line_id}/clarification-draft", response_model=EventLineClarificationDraftRecord)
25726:    @app.get("/api/v1/event-lines/{event_line_id}/memory", response_model=EventLineMemoryResponse)
25733:    @app.get("/api/v1/event-lines/{event_line_id}/context-bundle", response_model=EventLineContextBundleRecord)
25791:    @app.get("/api/v1/tasks/{task_id}/understanding")
25806:    @app.get("/api/v1/tasks/{task_id}/page-context", response_model=PageContextPackRecord)
25827:    @app.get("/api/v1/tasks/{task_id}/context-preview", response_model=TaskContextPreviewRecord)
26607:    @app.get("/api/v1/tasks/{task_id}/smart-brief", response_model=TaskSmartBriefRecord)
26624:    @app.post("/api/v1/tasks/smart-briefs", response_model=list[TaskSmartBriefRecord])
26660:    @app.get("/api/v1/tasks/{task_id}/context-brief", response_model=TaskContextBriefRecord)
26670:    @app.post("/api/v1/tasks/context-briefs/batch", response_model=TaskContextBriefBatchResponse)
26688:    @app.post("/api/v1/tasks/{task_id}/smart-brief-actions/{action_key}/adopt")
27187:    @app.get("/api/v1/tasks/{task_id}/prep-pack", response_model=PrepPackCardRecord)
27192:    @app.post("/api/v1/tasks/{task_id}/prep-pack/proposals", response_model=ProposalRecordRecord)
27332:    @app.get("/api/v1/proposals", response_model=list[ProposalRecordRecord])
27347:    @app.post("/api/v1/proposals/batch-approve", response_model=ProposalBatchResultRecord)
27381:    @app.post("/api/v1/proposals/batch-reject", response_model=ProposalBatchResultRecord)
27415:    @app.get("/api/v1/proposals/{proposal_id}", response_model=ProposalRecordRecord)
27422:    @app.get("/api/v1/proposals/{proposal_id}/execution-preview", response_model=ProposalExecutionPreviewRecord)
27430:    @app.post("/api/v1/proposals/{proposal_id}/approve", response_model=ProposalRecordRecord)
27458:    @app.post("/api/v1/proposals/{proposal_id}/reject", response_model=ProposalRecordRecord)
27486:    @app.post("/api/v1/proposals/{proposal_id}/execution-ticket", response_model=ProposalExecutionResultRecord)
27517:    @app.get("/api/v1/execution-tickets", response_model=list[ExecutionTicketRecord])
27530:    @app.post("/api/v1/execution-tickets/{ticket_id}/execute", response_model=ProposalExecutionResponse)
27556:    @app.get("/api/v1/execution-tickets/{ticket_id}/logs", response_model=list[ExecutionTicketLogRecord])
27567:    @app.post("/api/v1/execution-tickets/{ticket_id}/retry", response_model=ProposalExecutionResponse)
27595:    @app.post("/api/v1/proposals/{proposal_id}/execute", response_model=ProposalExecutionResponse)
27630:    @app.post("/api/v1/event-lines/{event_line_id}/attachments")
28312:    @app.get("/api/v1/event-lines/{event_line_id}/report-snapshot")
28331:    @app.post("/api/v1/event-lines/{event_line_id}/export-word")
29152:    @app.patch("/api/v1/event-lines/{event_line_id}", response_model=EventLineRecord)
29331:    @app.post("/api/v1/event-lines/{event_line_id}/close")
29376:    @app.post("/api/v1/event-lines/{event_line_id}/reopen")
29413:    @app.delete("/api/v1/event-lines/{event_line_id}")
29473:    @app.post("/api/v1/event-lines/{event_line_id}/notes")
29519:    @app.get("/api/v1/task-views", response_model=TaskViewsResponse)
29538:    @app.post("/api/v1/task-views", response_model=TaskViewDefinitionRecord)
29575:    @app.patch("/api/v1/task-views/{view_id}", response_model=TaskViewDefinitionRecord)
29614:    @app.get("/api/v1/reviews/dashboard/drill-target", response_model=ReviewDashboardDrillTargetResponse)
29648:    @app.get("/api/v1/tasks/{task_id}/plan-link", response_model=TaskPlanLinkRecord | None)
29657:    @app.post("/api/v1/tasks/{task_id}/plan-link/recompute", response_model=TaskPlanLinkRecord | None)
29666:    @app.patch("/api/v1/tasks/{task_id}/plan-link", response_model=TaskPlanLinkRecord | None)
29675:    @app.get("/api/v1/support-requests", response_model=list[SupportRequestRecord])
29688:    @app.post("/api/v1/support-requests", response_model=SupportRequestRecord)
29695:    @app.post("/api/v1/support-requests/{request_id}/resolve", response_model=SupportRequestRecord)
29734:    @app.post("/api/v1/admin/employees/{employee_id}/approve", response_model=EmployeeRecord)
29741:    @app.post("/api/v1/admin/employees/{employee_id}/reject", response_model=EmployeeRecord)
29748:    @app.post("/api/v1/admin/employees/{employee_id}/disable", response_model=EmployeeRecord)
29755:    @app.post("/api/v1/admin/employees/{employee_id}/reset-password")
29760:    @app.patch("/api/v1/admin/employees/{employee_id}/role", response_model=EmployeeRecord)
29767:    @app.patch("/api/v1/admin/employees/{employee_id}/department", response_model=EmployeeRecord)
29774:    @app.get("/api/v1/employees/mention-candidates", response_model=list[MentionCandidateRecord])
29781:    @app.get("/api/v1/settings", response_model=SettingsResponse)
29785:    @app.get("/api/v1/maintenance-mode/status", response_model=MaintenanceModeStatusRecord)
29789:    @app.post("/api/v1/maintenance-mode/enter", response_model=MaintenanceModeStatusRecord)
29805:    @app.post("/api/v1/maintenance-mode/exit", response_model=MaintenanceModeStatusRecord)
29820:    @app.get("/api/v1/admin/maintenance-mode/members", response_model=list[MaintenanceMemberPermissionRecord])
29828:    @app.patch("/api/v1/admin/maintenance-mode/members", response_model=list[MaintenanceMemberPermissionRecord])
29847:    @app.post("/api/v1/maintenance-mode/audit")
29864:    @app.get("/api/v1/settings/logs", response_model=list[ActivityLogRecord])
29926:    @app.get("/api/v1/logs")
29953:    @app.get("/api/v1/logs/export")
29980:    @app.get("/api/v1/logs/dates")
29986:    @app.get("/api/v1/tasks/agent-worklogs", response_model=AgentWorklogResponse)
30000:    @app.put("/api/v1/tasks/agent-weekly-plans/{week_label}/{agent_key}", response_model=AgentWeeklyPlanRecord)
30037:    @app.post("/api/v1/settings", response_model=SettingsResponse)
30104:    @app.get("/api/v1/settings/tasks", response_model=TaskSettingsRecord)
30118:    @app.post("/api/v1/settings/tasks", response_model=TaskSettingsRecord)
30180:    @app.get("/api/v1/settings/org-dna", response_model=OrganizationDnaResponse)
30184:    @app.get("/api/v1/settings/org-dna/{module_key}", response_model=OrganizationDnaModuleRecord)
30188:    @app.post("/api/v1/settings/org-dna/{module_key}", response_model=OrganizationDnaModuleRecord)
30192:    @app.get("/api/v1/settings/client-workspace", response_model=ClientWorkspaceSettingsRecord)
30196:    @app.post("/api/v1/settings/client-workspace", response_model=ClientWorkspaceSettingsRecord)
30212:    @app.get("/api/v1/settings/topics", response_model=TopicsSettingsRecord)
30216:    @app.post("/api/v1/settings/topics", response_model=TopicsSettingsRecord)
30228:    @app.get("/api/v1/settings/analysis-workbench", response_model=AnalysisWorkbenchSettingsRecord)
30232:    @app.post("/api/v1/settings/analysis-workbench", response_model=AnalysisWorkbenchSettingsRecord)
30253:    @app.get("/api/v1/settings/handbook", response_model=HandbookSettingsRecord)
30257:    @app.post("/api/v1/settings/handbook", response_model=HandbookSettingsRecord)
30269:    @app.get("/api/v1/settings/system-admin", response_model=SystemAdminSettingsRecord)
30273:    @app.post("/api/v1/settings/system-admin", response_model=SystemAdminSettingsRecord)
30286:    @app.get("/api/v1/settings/main-chain-stability", response_model=MainChainStabilitySettingsRecord)
30290:    @app.post("/api/v1/settings/main-chain-stability", response_model=MainChainStabilitySettingsRecord)
30297:    @app.get("/api/v1/settings/feishu-bot", response_model=FeishuBotSettingsRecord)
30301:    @app.post("/api/v1/settings/feishu-bot", response_model=FeishuBotSettingsRecord)
30306:    @app.get("/api/v1/settings/feishu-user-binding", response_model=FeishuUserBindingRecord)
30312:    @app.post("/api/v1/settings/feishu-user-binding/start", response_model=FeishuUserBindingStartResponse)
30363:    @app.delete("/api/v1/settings/feishu-user-binding", response_model=FeishuUserBindingRecord)
30371:    @app.get("/api/v1/auth/feishu/callback", response_class=HTMLResponse)
30407:    @app.post("/api/v1/channels/feishu/events")
30414:    @app.post("/api/v1/settings/backup", response_model=BackupResponse)
30423:    @app.post("/api/v1/settings/demo-data/load", response_model=DemoDataResponse)
30429:    @app.post("/api/v1/settings/demo-data/clear", response_model=DemoDataResponse)
30435:    @app.post("/api/v1/settings/legacy-scan", response_model=LegacyScanResponse)
30458:    @app.get("/api/v1/clients", response_model=list[ClientSummary])
30463:    @app.post("/api/v1/clients", response_model=ClientSummary)
30495:    @app.put("/api/v1/clients/{client_id}", response_model=ClientSummary)
31616:    @app.post("/api/v1/clients/{client_id}/folders", response_model=ClientFolder)
31646:    @app.patch("/api/v1/clients/{client_id}/folders/{folder_id}", response_model=ClientFolder)
31691:    @app.put("/api/v1/clients/{client_id}/folders/{folder_id}", response_model=ClientFolder)
31695:    @app.post("/api/v1/clients/{client_id}/documents/{document_id}/move-folder", response_model=DocumentRecord)
31776:    @app.post("/api/v1/clients/{client_id}/folders/recommend", response_model=ClientFolderRecommendationRecord | ClientFolderRecommendationPlanRecord)
31806:    @app.post("/api/v1/clients/{client_id}/folders/apply-recommendation", response_model=ClientWorkspaceResponse)
31815:    @app.post("/api/v1/clients/{client_id}/documents/auto-repair/preview", response_model=DocumentAutoRepairPreviewRecord)
31824:    @app.post("/api/v1/clients/{client_id}/documents/auto-repair/apply", response_model=DocumentAutoRepairApplyResultRecord)
31879:    @app.delete("/api/v1/clients/{client_id}/folders/{folder_id}")
31896:    @app.delete("/api/v1/clients/{client_id}")
31911:    @app.get("/api/v1/clients/{client_id}/workspace", response_model=ClientWorkspaceResponse)
31915:    @app.post("/api/v1/analysis/jobs", response_model=AnalysisJobRecord)
31938:    @app.post("/api/v1/analysis/backfill-main-chain", response_model=AnalysisBackfillMainChainResultRecord)
31944:    @app.get("/api/v1/analysis/jobs/{jobId}", response_model=AnalysisJobRecord)
31951:    @app.get("/api/v1/analysis/jobs/{jobId}/stages", response_model=list[AnalysisJobStageRunRecord])
31958:    @app.get("/api/v1/runtime/run-log/{runId}", response_model=RuntimeRunLogRecord)
31965:    @app.post("/api/v1/memory/dna/delta", response_model=DnaDeltaRecord)
31970:    @app.post("/api/v1/memory/judgments/confirm", response_model=JudgmentVersionRecord)
31994:    @app.post("/api/v1/approvals/decide", response_model=ApprovalRecordRecord)
32018:    @app.get("/api/v1/clients/{client_id}/judgments", response_model=list[JudgmentVersionRecord])
32023:    @app.get("/api/v1/clients/{client_id}/topics", response_model=list[ThemeClusterRecord])
32028:    @app.get("/api/v1/clients/{client_id}/conflicts", response_model=list[ConflictGroupRecord])
32033:    @app.get("/api/v1/clients/{client_id}/open-questions", response_model=list[OpenQuestionRecord])
32038:    @app.get("/api/v1/clients/{client_id}/runtime-run-logs", response_model=list[RuntimeRunLogRecord])
32043:    @app.get("/api/v1/runtime/analysis-migration-metrics", response_model=AnalysisMigrationMetricsRecord)
32047:    @app.get("/api/v1/strategic/thoughts", response_model=StrategicThoughtsResponseRecord)
32077:    @app.post("/api/v1/strategic/thoughts/refresh", response_model=StrategicThoughtsResponseRecord)
32099:    @app.post("/api/v1/strategic/thoughts/{thought_id}/state", response_model=StrategicThoughtRecord)
32120:    @app.post("/api/v1/strategic/thoughts/{thought_id}/review", response_model=StrategicThoughtRecord)
32178:    @app.get("/api/v1/clients/{client_id}/strategic-cockpit", response_model=StrategicCockpitSnapshotRecord)
32183:    @app.get("/api/v1/clients/{client_id}/strategic-cockpit/lines/{line_id}", response_model=StrategicLineDetailRecord)
32217:    @app.post("/api/v1/clients/{client_id}/strategic-cockpit/confirm", response_model=StrategicCockpitSnapshotRecord)
32238:    @app.post("/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack", response_model=MeetingPipelineResponse)
32245:    @app.post("/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack/{meeting_id}/apply", response_model=StrategicCockpitSnapshotRecord)
32292:    @app.get("/api/v1/clients/{client_id}/notebook", response_model=ClientNotebookResponse)
32297:    @app.get("/api/v1/clients/{client_id}/memory-status", response_model=MemoryStatus)
32302:    @app.post("/api/v1/memory/backfill", response_model=MemoryBackfillResultRecord)
32313:    @app.post("/api/v1/memory/backfill-documents")
32332:    @app.post("/api/v1/clarifications", response_model=ClarificationRecord)
32340:    @app.post("/api/v1/clarifications/{clarification_id}/answer", response_model=ClarificationRecord)
32349:    @app.get("/api/v1/clients/{client_id}/knowledge/reclass-events", response_model=list[FileReclassEventRecord])
32354:    @app.get("/api/v1/clients/{client_id}/knowledge/status", response_model=KnowledgeStatusRecord)
32360:    @app.get("/api/v1/clients/{client_id}/knowledge/progress", response_model=KnowledgeProgressRecord)
32369:    @app.get("/api/v1/clients/{client_id}/knowledge/parse-failures", response_model=list[KnowledgeParseFailureRecord])
32840:    @app.post(
32851:    @app.get(
33537:    @app.post(
34057:    @app.get(
34074:    @app.post(
34095:    @app.get("/api/v1/clients/{client_id}/data-center/mobile-snapshot")
34169:    @app.post("/api/v1/clients/{client_id}/knowledge/reindex-vector")
34186:    @app.get("/api/v1/clients/{client_id}/knowledge/vector-index/status")
34196:    @app.get("/api/v1/retrieval/settings", response_model=RetrievalModelSettingsRecord)
34200:    @app.post("/api/v1/retrieval/settings", response_model=RetrievalModelSettingsRecord)
34210:    @app.get("/api/v1/retrieval/health", response_model=RetrievalHealthRecord)
34264:    @app.get("/api/v1/retrieval/shadow-runs", response_model=list[RetrievalShadowRunRecord])
34271:    @app.get("/api/v1/retrieval/shadow-summary", response_model=RetrievalShadowSummaryRecord)
34277:    @app.get("/api/v1/runtime/generation-state", response_model=GenerationRuntimeStateRecord)
34293:    @app.post("/api/v1/runtime/generation-state/reset", response_model=GenerationRuntimeStateRecord)
34307:    @app.post("/api/v1/runtime/llm-healthcheck", response_model=LlmHealthcheckRecord)
34318:    @app.post("/api/v1/runtime/llm-provider-probe", response_model=LlmProviderProbeResultRecord)
34331:    @app.get("/api/v1/runtime/workspace-chat-diagnostics", response_model=WorkspaceChatDiagnosticsRecord)
34346:    @app.get("/api/v1/runtime/workspace-answer-value-diagnostics", response_model=WorkspaceAnswerValueDiagnosticsRecord)
34360:    @app.post("/api/v1/workspace-answer-value-reviews", response_model=WorkspaceAnswerValueReviewRecord)
34370:    @app.get("/api/v1/workspace-answer-value-reviews", response_model=list[WorkspaceAnswerValueReviewRecord])
34383:    @app.get("/api/v1/workspace-answer-value-summary", response_model=WorkspaceAnswerValueSummaryRecord)
34393:    @app.post("/api/v1/workspace-value-validation-sessions", response_model=WorkspaceValueValidationSessionRecord)
34400:    @app.get("/api/v1/workspace-value-validation-sessions", response_model=list[WorkspaceValueValidationSessionRecord])
34413:    @app.get("/api/v1/workspace-value-validation-sessions/{session_id}", response_model=WorkspaceValueValidationSessionRecord)
34417:    @app.post(
34439:    @app.post("/api/v1/workspace-value-validation-sessions/{session_id}/finish", response_model=WorkspaceValueValidationSessionRecord)
34443:    @app.get("/api/v1/workspace-answer-quality-failures", response_model=list[WorkspaceAnswerQualityFailureRecord])
34456:    @app.post(
34470:    @app.post(
34541:    @app.post(
34599:    @app.post(
34639:    @app.get("/api/v1/data-center/execution-retry-metrics", response_model=ExecutionRetryMetricsRecord)
34650:    @app.post(
34662:    @app.get(
34674:    @app.post("/api/v1/data-center/rollback-drill", response_model=DataCenterRollbackDrillResultRecord)
34683:    @app.get("/api/v1/data-center/operational-status", response_model=DataCenterOperationalStatusRecord)
34692:    @app.get("/api/v1/data-center/artifact-status", response_model=DataCenterArtifactStatusRecord)
34696:    @app.get("/api/v1/data-center/schema/status", response_model=DataCenterSchemaStatusRecord)
34700:    @app.post("/api/v1/data-center/schema/ensure", response_model=DataCenterSchemaStatusRecord)
34704:    @app.get("/api/v1/data-center/sync/preview")
34710:    @app.post(
34727:    @app.post(
34742:    @app.post(
34759:    @app.get(
34771:    @app.get(
34784:    @app.get("/api/v1/data-center/proposal-drafts", response_model=list[DataCenterProposalDraftRecord])
34803:    @app.post(
34864:    @app.post(
34893:    @app.post(
34922:    @app.post(
35094:    @app.get("/api/v1/external-evidence-cards", response_model=list[ExternalEvidenceCardRecord])
35109:    @app.post("/api/v1/topic-candidates/{topic_id}/external-evidence-card", response_model=ExternalEvidenceCardRecord)
35129:    @app.post("/api/v1/external-evidence-cards/{card_id}/accept", response_model=ExternalEvidenceCardRecord)
35150:    @app.post("/api/v1/external-evidence-cards/{card_id}/reject", response_model=ExternalEvidenceCardRecord)
35171:    @app.post(
35197:    @app.get("/api/v1/data-center/evidence-quality", response_model=list[EvidenceQualityAnnotationRecord])
35212:    @app.post("/api/v1/data-center/evidence-quality/{annotation_id}/label", response_model=EvidenceQualityAnnotationRecord)
35238:    @app.get("/api/v1/system/source-integrity")
35262:    @app.get("/api/v1/data-center/shadow-runs", response_model=list[DataCenterShadowRunRecord])
35275:    @app.get("/api/v1/data-center/shadow-summary", response_model=DataCenterShadowSummaryRecord)
35286:    @app.post("/api/v1/clients/{client_id}/knowledge/rebuild", response_model=KnowledgeJobRecord)
35325:    @app.post("/api/v1/clients/{client_id}/knowledge/search", response_model=KnowledgeSearchResponse)
35395:    @app.get("/api/v1/clients/{client_id}/goals", response_model=list[GoalRecord])
35399:    @app.post("/api/v1/clients/{client_id}/goals", response_model=GoalRecord)
35414:    @app.get("/api/v1/clients/{client_id}/dna-documents", response_model=ClientDnaModulesResponse)
35419:    @app.post("/api/v1/clients/{client_id}/dna-documents/generate", response_model=KnowledgeJobRecord)
35461:    @app.get("/api/v1/clients/{client_id}/dna-documents/{module_key}", response_model=ClientDnaModuleRecord)
35470:    @app.post("/api/v1/clients/{client_id}/dna-documents/{module_key}", response_model=ClientDnaModuleRecord)
35491:    @app.get("/api/v1/clients/{client_id}/project-structure", response_model=ProjectStructureResponse)
35495:    @app.get("/api/v1/clients/{client_id}/project-modules/{module_id}", response_model=ProjectModuleDetailRecord)
35500:    @app.post("/api/v1/clients/{client_id}/project-modules", response_model=ProjectModuleRecord)
35545:    @app.patch("/api/v1/clients/{client_id}/project-modules/{module_id}", response_model=ProjectModuleRecord)
35596:    @app.delete("/api/v1/clients/{client_id}/project-modules/{module_id}")
35615:    @app.get("/api/v1/clients/{client_id}/project-flows/{flow_id}", response_model=ProjectFlowDetailRecord)
35620:    @app.post("/api/v1/clients/{client_id}/project-flows", response_model=ProjectFlowRecord)
35674:    @app.patch("/api/v1/clients/{client_id}/project-flows/{flow_id}", response_model=ProjectFlowRecord)
35727:    @app.delete("/api/v1/clients/{client_id}/project-flows/{flow_id}")
35750:    @app.get("/api/v1/clients/{client_id}/dna", response_model=list[DnaTerm])
35754:    @app.post("/api/v1/clients/{client_id}/dna", response_model=DnaTerm)
35801:    @app.post("/api/v1/imports", response_model=list[ImportRecord])
36035:    @app.get("/api/v1/clients/{client_id}/documents/{document_id}/reading-preview", response_model=DocumentReadingPreviewRecord)
37787:    @app.get("/api/v1/clients/{client_id}/page-context", response_model=PageContextPackRecord)
37891:    @app.post("/api/v1/data-center/resolve", response_model=DataCenterKernelResultRecord)
37900:    @app.get("/api/v1/data-center/diagnose", response_model=DataCenterKernelResultRecord)
37965:    @app.post("/api/v1/clients/{client_id}/workspace/chat/start", response_model=ChatStartResponse)
38032:    @app.get("/api/v1/clients/{client_id}/analysis-runs/{run_id}", response_model=ClientAnalysisRunRecord)
38038:    @app.post("/api/v1/clients/{client_id}/analysis-runs/{run_id}/cancel", response_model=ClientAnalysisRunRecord)
38043:    @app.get("/api/v1/clients/{client_id}/workspace/chat/messages/{message_id}", response_model=ChatMessageRecord)
38048:    @app.get("/api/v1/clients/{client_id}/workspace/chat/threads/{thread_id}", response_model=ChatThreadDetailResponse)
38056:    @app.post("/api/v1/clients/{client_id}/workspace/chat", response_model=ChatMessageRecord)
38076:    @app.post("/api/v1/clients/{client_id}/knowledge/vectorize-answer", response_model=ClientTextDocumentResponse)
38115:    @app.post("/api/v1/clients/{client_id}/knowledge/enrich-surrogates")
38132:    @app.post("/api/v1/clients/{client_id}/knowledge/build-profile")
38155:    @app.post("/api/v1/clients/{client_id}/knowledge/sync-to-cloud")
38164:    @app.post("/api/v1/knowledge/backfill-all-clients")
38180:    @app.post("/api/v1/clients/{client_id}/knowledge/export-answer", response_model=ClientTextDocumentResponse)
38193:    @app.post("/api/v1/clients/{client_id}/documents/from-text", response_model=ClientTextDocumentResponse)
38197:    @app.post("/api/v1/clients/{client_id}/link-materials/import/start", response_model=LinkMaterialImportRunRecord)
38217:    @app.get("/api/v1/clients/{client_id}/link-materials/import-runs/latest", response_model=LinkMaterialImportRunRecord | None)
38222:    @app.get("/api/v1/clients/{client_id}/link-materials/import-runs/{run_id}", response_model=LinkMaterialImportRunRecord)
38227:    @app.post("/api/v1/clients/{client_id}/documents/fill-template", response_model=ClientTemplateFillResponse)
38232:    @app.post("/api/v1/clients/{client_id}/documents/fill-template/start", response_model=ClientTemplateFillRunRecord)
38251:    @app.get("/api/v1/clients/{client_id}/template-fill-runs/{run_id}", response_model=ClientTemplateFillRunRecord)
38257:    @app.post("/api/v1/clients/{client_id}/workspace/backfill-imports", response_model=WorkspaceImportBackfillResponse)
38277:    @app.get("/api/v1/clients/{client_id}/meetings", response_model=list[MeetingSummary])
38285:    @app.get("/api/v1/meetings/{meeting_id}/page-context", response_model=PageContextPackRecord)
38302:    @app.get("/api/v1/clients/{client_id}/meetings/{meeting_id}/page-context", response_model=PageContextPackRecord)
38324:    @app.get("/api/v1/event-lines/{event_line_id}/page-context", response_model=PageContextPackRecord)
38344:    @app.get(
38369:    @app.get(
38394:    @app.post("/api/v1/clients/{client_id}/meetings", response_model=MeetingPipelineResponse)
38424:    @app.post("/api/v1/clients/{client_id}/meetings/launch-feishu", response_model=FeishuMeetingLaunchResponse)
38491:    @app.get("/api/v1/feishu/status")
```

### 顶层 def 函数声明
```
983:def now_iso() -> str:
990:def detect_runtime_mode() -> Literal["packaged", "dev"]:
1017:def new_id(prefix: str) -> str:
1021:def today_label() -> str:
1025:def normalize_markdown_text(markdown_content: str) -> str:
1040:def summarize_markdown_document(title: str, normalized_text: str) -> str:
1055:def normalize_configured_cloud_api_url(raw_url: str | None) -> str:
1066:def resolve_initial_cloud_api_url(db: Database) -> str:
1109:def _require_runtime_state() -> AppState:
1115:def _run_chat_fact_extraction(
1141:def _schedule_chat_fact_extraction(
1180:def _parse_json_list(value: str | None) -> list[str]:
1185:def _parse_date_only(value: str | None) -> datetime.date | None:
1194:def _week_bounds(week_label: str) -> tuple[datetime.date, datetime.date] | None:
1207:def _task_review_date(task: TaskRecord) -> datetime.date | None:
1223:def _task_in_week(task: TaskRecord, week_label: str) -> bool:
1387:def _visible_local_task_tags(db: Database, operator_id: str) -> list[TaskTagRecord]:
1391:def _local_tag_rows_by_ids(db: Database, tag_ids: list[str]) -> list:
1402:def _global_local_task_tag_record(row) -> TaskTagRecord:
1414:def _ensure_local_tag(
1461:def _resolve_local_task_tags(db: Database, operator_id: str, tag_ids: list[str], legacy_names: list[str]) -> list[TaskTagRecord]:
1473:def _invalidate_event_line_snapshot_cache(*event_line_ids: str | None) -> None:
1480:def _event_line_snapshot_context(
1526:def _client_workspace_relative_path(path_value: str | None) -> Path | None:
1541:def _resolve_client_folder_ref_by_path(db: Database, client_id: str, path_value: str | None) -> tuple[str | None, str]:
1551:def _rehome_client_workspace_path(
1590:def _sync_task_attachment_scope(
1837:def _sync_event_line_client_scope_records(
1948:def _first_nonempty_text(*values: object) -> str | None:
1958:def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
1962:def _infer_action_os_business_category(
2000:def _resolve_task_action_os_fields(
2077:def _task_snapshot_from_task(task: TaskRecord, db: Database | None = None) -> dict[str, object]:
2103:def empty_review_structured_note() -> WeeklyReviewTaskStructuredNoteRecord:
2107:def _derive_reflection_text_from_legacy_structured(parsed: dict[str, object]) -> str:
2121:def coerce_review_structured_note(value: object) -> WeeklyReviewTaskStructuredNoteRecord:
2148:def compose_review_note(structured_note: WeeklyReviewTaskStructuredNoteRecord, fallback_note: str = "") -> str:
2182:def _review_entry_from_task(
2209:def _sql_placeholders(values: tuple[str, ...] | list[str]) -> str:
2213:def demo_data_loaded(db: Database) -> bool:
2220:def build_demo_data_response(db: Database) -> DemoDataResponse:
2235:def clear_demo_dataset(state: AppState) -> DemoDataResponse:
2292:def load_demo_dataset(state: AppState) -> DemoDataResponse:
2399:def create_pre_migration_backup(data_dir: Path, db_path: Path) -> Path | None:
2431:def rollback_database_from_backup(db_path: Path, backup_path: Path | None) -> None:
2446:def init_database_with_migration_guard(data_dir: Path) -> tuple[Database, Path | None]:
2456:def create_app(data_dir: Path | None = None) -> FastAPI:
43251:def build_excerpt(path: Path) -> str:
43260:def backfill_local_task_tag_ids(state: AppState) -> None:
43296:def seed_defaults(state: AppState) -> None:
```

### import from app.services / app.schemas / .models
```
14:from app.services.system_logger import SystemLogger as _SystemLogger
30:from app.db import BACKEND_SCHEMA_VERSION, Database, from_json, to_json
32:from app.models import (
496:from app.services.ai import (
506:from app.services.analysis_context import (
515:from app.services.answer_layer import (
523:from app.services.data_center_kernel import resolve_data_center_kernel
524:from app.services.data_center_quality import validate_answer_quality
525:from app.services.workspace_data_center_adapter import (
534:from app.services.workspace_file_search import build_file_search_user_summary
535:from app.services.workspace_followups import (
542:from app.services.workspace_query_router import route_workspace_query
543:from app.services.workspace_thread_memory import (
551:from app.services.data_center_shadow import (
555:from app.services.data_center_proposal import (
565:from app.services.external_evidence import (
572:from app.services.evidence_selector import select_answer_evidence
573:from app.services.evidence_quality import classify_evidence_quality
574:from app.services.evidence_quality_store import (
579:from app.services.evidence_quality_feedback_snapshot import (
584:from app.services.event_line_timeline import build_event_line_timeline_nodes
585:from app.services.execution_retry_metrics import get_execution_retry_metrics
586:from app.services.task_context_brief_engine import generate_task_context_brief_snapshot
587:from app.services.generation_runtime_policy import (
593:from app.services.meeting_context import build_meeting_page_context_pack
594:from app.services.question_focus import build_question_focus_frame
595:from app.services.query_router import route_page_query
596:from app.services.rerank_provider import build_rerank_provider
597:from app.services.retrieval_model_settings import (
602:from app.services.retrieval_shadow import (
607:from app.services.source_integrity import build_source_integrity_report
608:from app.services.proposal_approval import (
615:from app.services.proposal_execution import (
623:from app.services.workspace_answer_finalizer import (
627:from app.services.workspace_answer_experience import build_workspace_answer_experience
628:from app.services.workspace_answer_value_diagnostics import (
641:from app.services.workspace_chat_diagnostics import build_workspace_chat_diagnostics
642:from app.services.workspace_chat_kernel_bridge import decide_kernel_primary_gate
643:from app.services.kernel_primary_rollout import (
650:from app.services.data_center_rollback_drill import run_data_center_rollback_drill
651:from app.services.data_center_artifacts import build_data_center_artifact_status
652:from app.services.data_center_operational_status import build_data_center_operational_status
653:from app.services.data_center_schema import ensure_data_center_schema
654:from app.services.data_center_sync import build_data_center_sync_preview
655:from app.services.workspace_context_refresh import (
664:from app.services.analysis_center import (
690:from app.services.agent_worklogs import (
701:from app.services.knowledge_base import (
717:from app.services.knowledge_v2 import (
743:from app.services.link_material_import import (
753:from app.services.client_profile import backfill_all_clients, build_client_profile
754:from app.services.digital_asset_center import build_client_digital_assets, build_digital_asset_dashboard
755:from app.services.digital_asset_narrative import (
760:from app.services.organization_dna_v2 import (
764:from app.services.data_center_ingest import (
776:from app.services.data_center_access import DataCenterAccessContext
777:from app.services.local_model_optimizer import (
782:from app.services.internet_crawler import run_internet_enrichment
783:from app.services.memory_foundation import (
801:from app.services.platform_dna import extract_platform_dna_text, supported_platform_dna_extensions
802:from app.services.template_fill import (
815:from app.services.topic_capture import fetch_topic_candidates_from_web, fetch_topic_source_excerpt
816:from app.services.review_analysis import _dedupe_texts, _story_evidence_refs, build_weekly_review_analysis
817:from app.services.review_narrative import (
826:from app.services.local_memory import gather_project_context_for_ai, read_project_memory, rehome_event_line_memory, write_project_memory, write_event_line_memory, write_weekly_memory, should_dream, run_dream_cycle
827:from app.services.review_rollup import build_employee_review_report, build_executive_review_rollup
828:from app.services.review_simulation import build_review_simulation_bundle
829:from app.services.feishu import (
838:from app.services.badge_engine import build_badge_board
839:from app.services.growth_engine import (
855:from app.services.learning_presets import (
862:from app.services.secrets import MacOSKeychainSecretStore, MemorySecretStore
863:from app.services.version_manifest import (
```

## backend/app/services 模块清单

```
__init__.py                                                       2 lines
action_suggestion_service.py                                    133 lines
agent_worklogs.py                                              1158 lines
ai.py                                                          4582 lines
analysis_center.py                                             3932 lines
analysis_context.py                                            2080 lines
answer_layer.py                                                 430 lines
badge_engine.py                                                1228 lines
client_profile.py                                               391 lines
data_center_access.py                                           236 lines
data_center_artifacts.py                                        271 lines
data_center_ingest.py                                          1850 lines
data_center_kernel.py                                           690 lines
data_center_operational_status.py                               145 lines
data_center_prep.py                                             163 lines
data_center_profiler.py                                          23 lines
data_center_proposal.py                                         630 lines
data_center_quality.py                                          142 lines
data_center_rollback_drill.py                                    56 lines
data_center_schema.py                                           156 lines
data_center_search.py                                           366 lines
data_center_shadow.py                                           234 lines
data_center_sync.py                                             579 lines
department_catalog.py                                            58 lines
diagnosis_engines.py                                            333 lines
digital_asset_center.py                                        3513 lines
digital_asset_narrative.py                                      657 lines
embedding_provider.py                                           491 lines
event_line_timeline.py                                          544 lines
evidence_quality.py                                             225 lines
evidence_quality_feedback.py                                     61 lines
evidence_quality_feedback_snapshot.py                           171 lines
evidence_quality_store.py                                       230 lines
evidence_selector.py                                            478 lines
execution_retry_metrics.py                                      183 lines
experience_story_engine.py                                      132 lines
external_evidence.py                                            426 lines
feishu.py                                                       161 lines
feishu_sync.py                                                  591 lines
generation_runtime_policy.py                                    439 lines
growth_engine.py                                               3015 lines
internet_crawler.py                                            1052 lines
kernel_primary_rollout.py                                       503 lines
knowledge_base.py                                              4358 lines
knowledge_v2.py                                                4044 lines
learning_presets.py                                             640 lines
link_material_import.py                                        1071 lines
local_memory.py                                                 663 lines
local_model_optimizer.py                                        823 lines
local_semantic_router.py                                        234 lines
meeting_context.py                                              244 lines
meeting_followup.py                                             178 lines
memory_foundation.py                                           2253 lines
organization_dna_v2.py                                          872 lines
platform_dna.py                                                 108 lines
proposal_approval.py                                            249 lines
proposal_execution.py                                           458 lines
query_router.py                                                 448 lines
question_focus.py                                                66 lines
rerank_provider.py                                              141 lines
retrieval_model_settings.py                                     134 lines
retrieval_shadow.py                                             162 lines
review_analysis.py                                             2724 lines
review_narrative.py                                            2507 lines
review_rollup.py                                               1465 lines
review_simulation.py                                            147 lines
secrets.py                                                      137 lines
self_heal.py                                                    748 lines
source_integrity.py                                             110 lines
source_reachability.py                                          216 lines
source_semantics.py                                             264 lines
system_logger.py                                                298 lines
task_context_brief_engine.py                                    586 lines
template_fill.py                                                918 lines
topic_capture.py                                                922 lines
topic_data_center.py                                            173 lines
topic_source_fetcher.py                                         579 lines
understanding_builder.py                                        701 lines
version_manifest.py                                              63 lines
weekly_review_material_pack.py                                  862 lines
workspace_action_perspective.py                                  80 lines
workspace_answer_experience.py                                  290 lines
workspace_answer_finalizer.py                                   201 lines
workspace_answer_value_diagnostics.py                          1155 lines
workspace_chat_diagnostics.py                                   436 lines
workspace_chat_kernel_bridge.py                                  24 lines
workspace_context_refresh.py                                    337 lines
workspace_data_center_adapter.py                               1409 lines
workspace_file_search.py                                         65 lines
workspace_followups.py                                          318 lines
workspace_query_router.py                                       365 lines
workspace_relation_docs.py                                      756 lines
workspace_thread_memory.py                                      513 lines
```

## backend/app/models.py 模型分类

总行数：7254

### class 声明
```
81:class OperatorRecord(BaseModel):
90:class AiModelProfileRecord(BaseModel):
100:class AppSettingsPayload(BaseModel):
116:class AppSettingsResponse(BaseModel):
136:class HealthAiState(BaseModel):
149:class HealthResponse(BaseModel):
174:class SettingsResponse(BaseModel):
180:class SessionUserRecord(BaseModel):
195:class AuthStateResponse(BaseModel):
202:class CloudConfigResponse(BaseModel):
207:class AccountOverviewResponse(BaseModel):
214:class ConsultationKnowledgeRequestRecord(BaseModel):
236:class ConsultationKnowledgeProcessSummaryResponse(BaseModel):
246:class AuthRegisterPayload(BaseModel):
259:class AuthLoginPayload(BaseModel):
266:class RememberedCloudAuthAccount(BaseModel):
274:class LocalInputMemoryCloudAuth(BaseModel):
280:class LocalInputMemoryAiSettings(BaseModel):
285:class LocalInputMemoryFeishuIntegration(BaseModel):
293:class LocalInputMemoryResponse(BaseModel):
299:class SaveCloudAuthInputMemoryPayload(BaseModel):
307:class SaveAiInputMemoryPayload(BaseModel):
312:class SaveFeishuInputMemoryPayload(BaseModel):
320:class UpdateProfilePayload(BaseModel):
326:class EmployeeRecord(BaseModel):
349:class MaintenanceModeStatusRecord(BaseModel):
359:class MaintenanceMemberPermissionRecord(BaseModel):
368:class MaintenancePermissionMemberPayload(BaseModel):
374:class MaintenancePermissionUpdatePayloadRecord(BaseModel):
378:class MaintenanceAuditPayloadRecord(BaseModel):
384:class EmployeeRolePayload(BaseModel):
388:class EmployeeDepartmentPayload(BaseModel):
392:class EmployeeRejectPayload(BaseModel):
396:class DepartmentOptionRecord(BaseModel):
402:class OrgInviteResolveResultRecord(BaseModel):
411:class OrgProfileRecord(BaseModel):
426:class OrgQuarterPlanRecord(BaseModel):
438:class OrgDepartmentQuarterPlanRecord(BaseModel):
448:class OrgDepartmentRecord(BaseModel):
466:class OrgIntroDocumentRecord(BaseModel):
477:class OrgRoleTemplateRecord(BaseModel):
497:class OrgEmployeeBindingRecord(BaseModel):
512:class OrgReportingLineRecord(BaseModel):
526:class OrgTaskControlRuleRecord(BaseModel):
542:class OrgRoleProcessTemplateRecord(BaseModel):
557:class OrgFocusItemRecord(BaseModel):
569:class OrgDepartmentPlanItemRecord(BaseModel):
581:class OrgDepartmentPlanRecord(BaseModel):
594:class TaskPlanLinkRecord(BaseModel):
603:class SupportRequestRecord(BaseModel):
618:class OrgModelProfileRecord(BaseModel):
631:class TaskOrgBackfillResultRecord(BaseModel):
640:class TaskContextRefreshResultRecord(BaseModel):
652:class TaskEventLineBootstrapResultRecord(BaseModel):
661:class MemoryBackfillResultRecord(BaseModel):
675:class MentionCandidateRecord(BaseModel):
683:class DemoDataResponse(BaseModel):
692:class ActivityLogRecord(BaseModel):
702:class BackupResponse(BaseModel):
707:class LegacyScanRequest(BaseModel):
711:class LegacyScanEntry(BaseModel):
717:class LegacyScanResponse(BaseModel):
724:class ClientMutationPayload(BaseModel):
734:class ClientSummary(BaseModel):
749:class ClientFolder(BaseModel):
766:class ClientFolderCreatePayload(BaseModel):
770:class ClientFolderUpdatePayload(BaseModel):
776:class ClientDocumentMoveFolderPayload(BaseModel):
781:class ClientFolderRecommendPayload(BaseModel):
789:class ClientFolderRecommendationRecord(BaseModel):
799:class ClientFolderRecommendationPlanRecord(BaseModel):
813:class ClientFolderApplyRecommendationPayload(BaseModel):
817:class DocumentAutoRepairPreviewPayloadRecord(BaseModel):
823:class DocumentAutoRepairApplyPayloadRecord(BaseModel):
830:class DocumentAutoRepairItemRecord(BaseModel):
866:class DocumentAutoRepairPreviewRecord(BaseModel):
877:class DocumentAutoRepairApplyResultRecord(BaseModel):
886:class ImportDocumentRecord(BaseModel):
893:class ImportRecord(BaseModel):
906:class ImportPayload(BaseModel):
913:class WorkspaceImportBackfillResponse(BaseModel):
922:class DocumentRecord(BaseModel):
935:class KnowledgeStatusRecord(BaseModel):
965:class DocumentCardRecord(BaseModel):
1007:class GoalRecord(BaseModel):
1016:class GoalPayload(BaseModel):
1023:class DnaTerm(BaseModel):
1033:class DnaTermPayload(BaseModel):
1040:class EvidenceItem(BaseModel):
1071:class AiStructuredResponse(BaseModel):
1178:class EvidenceSupportItemRecord(BaseModel):
1190:class StateAnswerSectionsRecord(BaseModel):
1200:class StateSourceSummaryRecord(BaseModel):
1209:class ChatMessageRecord(BaseModel):
1239:class ChatThread(BaseModel):
1247:class ChatRequest(BaseModel):
1254:class ChatStartResponse(BaseModel):
1263:class ChatThreadDetailResponse(BaseModel):
1268:class AgendaItem(BaseModel):
1274:class DecisionItem(BaseModel):
1279:class RiskItem(BaseModel):
1285:class AmbiguityItem(BaseModel):
1292:class OrganizationNotebookSnapshot(BaseModel):
1309:class EventLineMemorySnapshot(BaseModel):
1326:class MemoryFact(BaseModel):
1341:class ClarificationRecord(BaseModel):
1357:class MemoryStatus(BaseModel):
1369:class BackgroundReadiness(BaseModel):
1376:class TaskRecord(BaseModel):
1428:class TaskAttachmentRecord(BaseModel):
1443:class TaskOrgContextRecord(BaseModel):
1458:class TaskProjectContextRecord(BaseModel):
1479:class ProjectModuleRecord(BaseModel):
1494:class ProjectFlowRecord(BaseModel):
1512:class ProjectStructureResponse(BaseModel):
1517:class ProjectModuleDetailRecord(ProjectModuleRecord):
1525:class ProjectFlowDetailRecord(ProjectFlowRecord):
1531:class MeetingSummary(BaseModel):
1540:class MeetingDetail(MeetingSummary):
1550:class MeetingCreatePayload(BaseModel):
1555:class MeetingIngestPayload(BaseModel):
1560:class MeetingPipelineResponse(BaseModel):
1565:class FeishuMeetingLaunchPayload(BaseModel):
1571:class FeishuMeetingLaunchResponse(BaseModel):
1581:class TaskListRecord(BaseModel):
1591:class TaskTagRecord(BaseModel):
1602:class TaskSettingsRecord(BaseModel):
1614:class ReviewDepartmentMemberRecord(BaseModel):
1620:class ReviewDepartmentConfigRecord(BaseModel):
1630:class ReviewGovernanceSettingsRecord(BaseModel):
1635:class TaskTagLibraryResponse(BaseModel):
1639:class TaskListLibraryResponse(BaseModel):
1643:class TaskListDuplicateRepairGroupRecord(BaseModel):
1654:class TaskListDuplicateRepairResponse(BaseModel):
1663:class TaskBoardResponse(BaseModel):
1670:class TaskCollaboratorRecord(BaseModel):
1681:class TaskActivityRecord(BaseModel):
1691:class TaskPayload(BaseModel):
1723:class TaskUpdatePayload(BaseModel):
1754:class TaskNotePayload(BaseModel):
1758:class TaskCompletionReviewPayload(BaseModel):
1762:class TaskPlanLinkUpsertPayload(BaseModel):
1769:class TaskRejectPayload(BaseModel):
1773:class SupportRequestCreatePayload(BaseModel):
1783:class SupportRequestResolvePayload(BaseModel):
1788:class TaskTagMutationPayload(BaseModel):
1795:class TaskListMutationPayload(BaseModel):
1804:class TaskSettingsPayload(BaseModel):
1815:class DnaReadinessQuestionRecord(BaseModel):
1821:class OrganizationDnaModuleRecord(BaseModel):
1840:class OrganizationDnaResponse(BaseModel):
1844:class OrganizationDnaUploadPayload(BaseModel):
1850:class OrgIntroDocumentUploadPayload(BaseModel):
1857:class ProjectModulePayload(BaseModel):
1868:class ProjectFlowPayload(BaseModel):
1881:class ClientDnaModuleRecord(BaseModel):
1897:class ClientDnaGeneratePayload(BaseModel):
1901:class ClientDnaModulesResponse(BaseModel):
1905:class ClientWorkspaceSettingsRecord(BaseModel):
1914:class ClientWorkspaceSettingsPayload(BaseModel):
1922:class TopicsSettingsRecord(BaseModel):
1931:class TopicsSettingsPayload(BaseModel):
1939:class DiagnosisProfileRecord(BaseModel):
1954:class OrganizationRiskDnaDocument(BaseModel):
1965:class FundraisingKnowledgeDocument(BaseModel):
1979:class DeepDnaSourceRecord(BaseModel):
1990:class DeepDnaRecord(BaseModel):
2013:class DeepDnaDraft(BaseModel):
2024:class CoachCaseRecord(BaseModel):
2040:class CoachReminderRule(BaseModel):
2051:class OrgWritingNorm(BaseModel):
2062:class CoachCardRecord(BaseModel):
2076:class CoachPayload(BaseModel):
2082:class RunComparison(BaseModel):
2092:class AnalysisWorkbenchSettingsRecord(BaseModel):
2107:class AnalysisWorkbenchSettingsPayload(BaseModel):
2121:class HandbookSettingsRecord(BaseModel):
2130:class HandbookSettingsPayload(BaseModel):
2138:class SystemAdminSettingsRecord(BaseModel):
2147:class SystemAdminSettingsPayload(BaseModel):
2155:class AnalysisWorkerCounterSnapshotRecord(BaseModel):
2161:class MainChainCanaryObservationRecord(BaseModel):
2185:class MainChainCanaryObservationPayload(BaseModel):
2208:class MainChainStabilitySettingsRecord(BaseModel):
2216:class MainChainStabilitySettingsPayload(BaseModel):
2222:class FeishuBotSettingsRecord(BaseModel):
2239:class FeishuBotSettingsPayload(BaseModel):
2251:class FeishuUserBindingRecord(BaseModel):
2269:class FeishuUserBindingStartResponse(BaseModel):
2278:class OrgMembershipSummaryRecord(BaseModel):
2290:class OrgMembershipApplyPayload(BaseModel):
2298:class OrgFeishuIntegrationAuditRecord(BaseModel):
2309:class OrgFeishuIntegrationRecord(BaseModel):
2323:class OrgFeishuIntegrationSavePayload(BaseModel):
2329:class FeishuDeliveryProfileRecord(BaseModel):
2344:class FeishuDeliveryProfileSavePayload(BaseModel):
2348:class FeishuMemberAuthorizationRecord(BaseModel):
2369:class FeishuMemberAuthorizationStartResponse(BaseModel):
2378:class AiTagSuggestionPayload(BaseModel):
2386:class AiTagSuggestionResponse(BaseModel):
```
