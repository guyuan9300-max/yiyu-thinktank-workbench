# Round 2 Dead Code Ledger

## A. High-confidence unused or low-binding candidates

### Main repo component candidates

- `src/renderer/components/handbook/GrowthHandbookView.tsx` -> orphan_component
- `src/renderer/components/settings/FeishuAccountBindingPanel.tsx` -> orphan_component
- `src/renderer/components/settings/FeishuBotSettingsPanel.tsx` -> orphan_component
- `src/renderer/components/settings/OrganizationTreeCanvas.tsx` -> orphan_component
- `src/renderer/components/settings/UpdateSettingsPanel.tsx` -> orphan_component
- `src/renderer/components/tasks/ReviewHistoryPicker.tsx` -> orphan_component

### Main repo API wrappers with zero product usage

- `getAnalysisWorkbenchSettings` -> /api/v1/settings/analysis-workbench
- `updateAnalysisWorkbenchSettings` -> /api/v1/settings/analysis-workbench
- `getLogDates` -> /api/v1/logs/dates
- `createAnalysisJob` -> /api/v1/analysis/jobs
- `getAnalysisJob` -> /api/v1/analysis/jobs/{param}
- `getAnalysisJobStages` -> /api/v1/analysis/jobs/{param}/stages
- `getRuntimeRunLog` -> /api/v1/runtime/run-log/{param}
- `createDnaDelta` -> /api/v1/memory/dna/delta
- `confirmJudgment` -> /api/v1/memory/judgments/confirm
- `decideApproval` -> /api/v1/approvals/decide
- `getClientJudgments` -> /api/v1/clients/{param}/judgments
- `getClientTopics` -> /api/v1/clients/{param}/topics
- `getClientConflicts` -> /api/v1/clients/{param}/conflicts
- `getClientOpenQuestions` -> /api/v1/clients/{param}/open-questions
- `getClientRuntimeRunLogs` -> /api/v1/clients/{param}/runtime-run-logs
- `getClientDnaDocument` -> /api/v1/clients/{param}/dna-documents/{param}
- `deleteProjectFlow` -> /api/v1/clients/{param}/project-flows/{param}
- `getClientKnowledgeStatus` -> /api/v1/clients/{param}/knowledge/status
- `getRetrievalSettings` -> /api/v1/retrieval/settings
- `updateRetrievalSettings` -> /api/v1/retrieval/settings
- `getRetrievalHealth` -> /api/v1/retrieval/health
- `getRetrievalShadowSummary` -> /api/v1/retrieval/shadow-summary | /api/v1/retrieval/shadow-summary
- `getRetrievalShadowRuns` -> /api/v1/retrieval/shadow-runs
- `reindexClientVector` -> /api/v1/clients/{param}/knowledge/reindex-vector
- `getClientVectorIndexStatus` -> /api/v1/clients/{param}/knowledge/vector-index/status
- `diagnoseDataCenter` -> /api/v1/data-center/diagnose
- `getDataCenterShadowSummary` -> /api/v1/data-center/shadow-summary | /api/v1/data-center/shadow-summary
- `getDataCenterShadowRuns` -> /api/v1/data-center/shadow-runs
- `getWorkspaceChatDiagnostics` -> /api/v1/runtime/workspace-chat-diagnostics
- `getWorkspaceAnswerValueDiagnostics` -> /api/v1/runtime/workspace-answer-value-diagnostics
- `createWorkspaceAnswerValueReview` -> /api/v1/workspace-answer-value-reviews
- `listWorkspaceAnswerValueReviews` -> /api/v1/workspace-answer-value-reviews
- `getWorkspaceAnswerValueSummary` -> /api/v1/workspace-answer-value-summary
- `createWorkspaceValueValidationSession` -> /api/v1/workspace-value-validation-sessions
- `listWorkspaceValueValidationSessions` -> /api/v1/workspace-value-validation-sessions
- `getWorkspaceValueValidationSession` -> /api/v1/workspace-value-validation-sessions/{param}
- `completeWorkspaceValueValidationQuestion` -> /api/v1/workspace-value-validation-sessions/{param}/complete-question
- `finishWorkspaceValueValidationSession` -> /api/v1/workspace-value-validation-sessions/{param}/finish
- `listWorkspaceAnswerQualityFailures` -> /api/v1/workspace-answer-quality-failures
- `resolveWorkspaceAnswerQualityFailure` -> /api/v1/workspace-answer-quality-failures/{param}/resolve
- `getGenerationRuntimeState` -> /api/v1/runtime/generation-state
- `resetGenerationRuntimeState` -> /api/v1/runtime/generation-state/reset
- `resetGenerationRuntimeStateV2` -> /api/v1/runtime/generation-state/reset
- `runLlmHealthcheck` -> /api/v1/runtime/llm-healthcheck
- `runLlmProviderProbe` -> /api/v1/runtime/llm-provider-probe
- `getKnowledgeParseFailures` -> /api/v1/clients/{param}/knowledge/parse-failures
- `retryKnowledgeParseFailures` -> /api/v1/clients/{param}/knowledge/parse-failures/retry
- `getWorkspaceDataCenterReadiness` -> /api/v1/clients/{param}/workspace/data-center-readiness
- `runWorkspaceDataCenterReadinessAction` -> /api/v1/clients/{param}/workspace/data-center-readiness/actions
- `getWorkspaceContextRefreshEvents` -> /api/v1/clients/{param}/workspace/context-refresh-events | /api/v1/clients/{param}/workspace/context-refresh-events
- `enqueueWorkspaceContextRefreshEvent` -> /api/v1/clients/{param}/workspace/context-refresh-events
- `getExternalEvidenceCards` -> /api/v1/external-evidence-cards
- `createExternalEvidenceCardFromTopicCandidate` -> /api/v1/topic-candidates/{param}/external-evidence-card
- `acceptExternalEvidenceCard` -> /api/v1/external-evidence-cards/{param}/accept
- `rejectExternalEvidenceCard` -> /api/v1/external-evidence-cards/{param}/reject
- `createProposalDraftFromExternalEvidence` -> /api/v1/external-evidence-cards/{param}/create-proposal-draft
- `getDataCenterEvidenceQuality` -> /api/v1/data-center/evidence-quality
- `getMobileDataCenterSnapshot` -> /api/v1/clients/{param}/data-center/mobile-snapshot
- `confirmStrategicCockpit` -> /api/v1/clients/{param}/strategic-cockpit/confirm
- `createStrategicMeetingPack` -> /api/v1/clients/{param}/strategic-cockpit/meeting-pack

### Main repo IPC bridges with zero renderer usage

- `resumeFromStartupGate`
- `readTextFile`
- `quitApp`
- `watchFile`
- `unwatchFile`
- `onFileChanged`

## B. Candidates blocked by runtime/source build issues

- `src/renderer/components/handbook/GrowthAssetLibraryDrawer.tsx` imported only from currently unreachable renderer branches; keep blocked_by_runtime_issue until source build runs
- `src/renderer/components/handbook/GrowthBadgeWall.tsx` imported only from currently unreachable renderer branches; keep blocked_by_runtime_issue until source build runs
- `src/renderer/components/handbook/GrowthLearningWorkbench.tsx` imported only from currently unreachable renderer branches; keep blocked_by_runtime_issue until source build runs
- `src/renderer/components/handbook/GrowthLedgerDrawer.tsx` imported only from currently unreachable renderer branches; keep blocked_by_runtime_issue until source build runs

## C. Mobile orphan candidates


## D. Main repo script_or_ops_only candidates

- `scripts/cleanup_audit_data.py`
- `scripts/deploy-cloud-backend-volcengine.sh`
- `scripts/smoke-cloud-backend-volcengine.sh`
- `scripts/sync-local-event-lines-to-cloud.py`
- `scripts/test-template-save.sh`

## E. Backend/cloud low-binding endpoint inventories

### backend_only_no_ui_binding

- `backend/app/main.py:22113` GET /api/public/task-attachments/{attachment_id}
- `backend/app/main.py:22198` GET /api/public/task-attachments/{attachment_id}/thumbnail
- `backend/app/main.py:22218` GET /api/public/task-attachments/{attachment_id}/text-content
- `backend/app/main.py:22309` GET /api/public/task-attachments/{attachment_id}/ocr-summary
- `backend/app/main.py:22357` POST /api/v1/event-lines/{event_line_id}/attachments/download-zip
- `backend/app/main.py:22489` POST /api/v1/system/self-heal
- `backend/app/main.py:22504` POST /api/v1/system/diagnose
- `backend/app/main.py:22517` GET /api/v1/system/heal-log
- `backend/app/main.py:22580` GET /api/v1/account/overview
- `backend/app/main.py:22956` GET /api/v1/consultation/knowledge-requests
- `backend/app/main.py:23154` GET /api/v1/event-lines/{event_line_id}/memory
- `backend/app/main.py:23161` GET /api/v1/event-lines/{event_line_id}/context-bundle
- `backend/app/main.py:24734` GET /api/v1/proposals
- `backend/app/main.py:25032` POST /api/v1/event-lines/{event_line_id}/attachments
- `backend/app/main.py:25733` POST /api/v1/event-lines/{event_line_id}/export-word
- `backend/app/main.py:26940` PATCH /api/v1/task-views/{view_id}
- `backend/app/main.py:27013` GET /api/v1/tasks/{task_id}/plan-link
- `backend/app/main.py:27022` POST /api/v1/tasks/{task_id}/plan-link/recompute
- `backend/app/main.py:27031` PATCH /api/v1/tasks/{task_id}/plan-link
- `backend/app/main.py:27158` GET /api/v1/logs
- `backend/app/main.py:27176` GET /api/v1/logs/export
- `backend/app/main.py:27201` GET /api/v1/tasks/agent-worklogs
- `backend/app/main.py:27596` POST /api/v1/channels/feishu/events
- `backend/app/main.py:27877` GET /api/v1/strategic/thoughts
- `backend/app/main.py:28013` GET /api/v1/clients/{client_id}/strategic-cockpit/lines/{line_id}

### compatibility_only

- `cloud_backend/app/main.py:8850` GET /api/v1/mobile/capabilities
- `cloud_backend/app/main.py:8872` POST /api/v1/mobile/knowledge-mirror/publish
- `cloud_backend/app/main.py:9558` GET /api/v1/tasks/{task_id}/plan-link
- `cloud_backend/app/main.py:9569` POST /api/v1/tasks/{task_id}/plan-link/recompute
- `cloud_backend/app/main.py:9581` PATCH /api/v1/tasks/{task_id}/plan-link
- `cloud_backend/app/main.py:9763` GET /api/v1/consultation/knowledge-requests
- `cloud_backend/app/main.py:9796` POST /api/v1/consultation/knowledge-requests
- `cloud_backend/app/main.py:9820` POST /api/v1/consultation/knowledge-requests/{request_id}/status
- `cloud_backend/app/main.py:9869` POST /api/v1/consultation/chat
- `cloud_backend/app/main.py:10827` POST /api/v1/mobile/smart-input/task-draft
- `cloud_backend/app/main.py:11876` POST /api/v1/tasks/{task_id}/attachments/{attachment_id}/transcribe-to-document
- `cloud_backend/app/main.py:11983` POST /api/v1/tasks/{task_id}/collaborators/{user_id}/accept
- `cloud_backend/app/main.py:12008` POST /api/v1/tasks/{task_id}/collaborators/{user_id}/return
- `cloud_backend/app/main.py:12142` GET /api/v1/tasks/{task_id}/activity
- `cloud_backend/app/main.py:12168` GET /api/v1/reviews/dashboard

## F. Mobile test-guarded files

- `lib/__tests__/account-scope.test.mjs`
- `lib/__tests__/base-url.test.mjs`
- `lib/__tests__/boundary-cards.test.mjs`
- `lib/__tests__/calendar-repository-core.test.mjs`
- `lib/__tests__/consult-context-adapter.test.mjs`
- `lib/__tests__/consult-context.test.mjs`
- `lib/__tests__/consult-thread-context.test.mjs`
- `lib/__tests__/create-task-association.test.mjs`
- `lib/__tests__/current-focus-core.test.mjs`
- `lib/__tests__/date.test.mjs`
- `lib/__tests__/focus-selectors.test.mjs`
- `lib/__tests__/legacy-upload-pseudo-op-core.test.mjs`
- `lib/__tests__/legacy-upload-runner-core.test.mjs`
- `lib/__tests__/pending-op-policy.test.mjs`
- `lib/__tests__/record-note-flow-core.test.mjs`
- `lib/__tests__/runtime-controller.test.mjs`
- `lib/__tests__/scope-storage-core.test.mjs`
- `lib/__tests__/smart-input-queue-core.test.mjs`
- `lib/__tests__/smart-input-recovery.test.mjs`
- `lib/__tests__/sync-freeze-core.test.mjs`
- `lib/__tests__/task-board-store.test.mjs`
- `lib/__tests__/task-sync-policy.test.mjs`
- `lib/__tests__/task-sync-presentation.test.mjs`
- `lib/__tests__/task-understanding.test.mjs`
- `lib/__tests__/week-signal.test.mjs`

## G. Mobile migration-active files (do not delete yet)

- `components/calendar-screen/CalendarDragLayer.tsx`
- `components/calendar-screen/CalendarHeader.tsx`
- `components/calendar-screen/CalendarModalCoordinator.tsx`
- `components/calendar-screen/DayView.tsx`
- `components/calendar-screen/MonthView.tsx`
- `components/calendar-screen/WeekView.tsx`
- `components/tasks-screen/DragCalendarOverlay.tsx`
- `components/tasks-screen/InboxTaskList.tsx`
- `components/tasks-screen/ScheduledTaskList.tsx`
- `components/tasks-screen/SmartInputRecoveryController.tsx`
- `components/tasks-screen/TaskModalCoordinator.tsx`
- `components/tasks-screen/TasksFilterBar.tsx`
- `components/tasks-screen/TasksHeader.tsx`
- `lib/calendar-repository-core.ts`
- `lib/current-focus-core.ts`
- `lib/legacy-upload-ops.ts`
- `lib/legacy-upload-pseudo-op-core.ts`
- `lib/legacy-upload-runner-core.ts`
- `lib/legacy-upload-runner.ts`
- `lib/record-note-flow-core.ts`
- `lib/runtime-controller.ts`
- `lib/runtime-flags.ts`
- `lib/runtime.ts`
- `lib/scope-storage-core.ts`
- `lib/smart-input-queue-core.ts`
- `lib/smart-input-recovery.ts`
- `lib/sync-engine.ts`
- `lib/sync-freeze-core.ts`
- `lib/task-board-store-core.ts`

