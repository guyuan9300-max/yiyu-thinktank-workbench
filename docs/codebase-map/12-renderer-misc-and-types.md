# src/renderer 其他文件 + src/shared/types.ts 分类索引

## src/renderer 目录结构

```
src/renderer/App.tsx
src/renderer/assets/brand/app-logo-ai.png
src/renderer/assets/brand/brand-avatar-yiyu.png
src/renderer/assets/yiyu-brand-logo.png
src/renderer/components/client_workspace/ClientProjectSetupPage.tsx
src/renderer/components/client_workspace/ClientWorkspaceView.tsx
src/renderer/components/collab/CollabDialogs.tsx
src/renderer/components/collab/CollabSyncCard.tsx
src/renderer/components/data_center/DataCenterOpsPanel.tsx
src/renderer/components/data_center/FileSearchResultPanel.tsx
src/renderer/components/data_center/WorkStatusPanel.tsx
src/renderer/components/growth/GrowthContext.tsx
src/renderer/components/handbook/GrowthAssetLibraryDrawer.tsx
src/renderer/components/handbook/GrowthBadgeWall.tsx
src/renderer/components/handbook/GrowthCenterView.tsx
src/renderer/components/handbook/GrowthHandbookView.tsx
src/renderer/components/handbook/GrowthLearningWorkbench.tsx
src/renderer/components/handbook/GrowthLedgerDrawer.tsx
src/renderer/components/settings/BrandLogoSettingsCard.tsx
src/renderer/components/settings/DataCenterProposalInboxPanel.tsx
src/renderer/components/settings/FeishuAccountBindingPanel.tsx
src/renderer/components/settings/FeishuBotSettingsPanel.tsx
src/renderer/components/settings/FeishuOrgIntegrationPanel.tsx
src/renderer/components/settings/OrganizationModelSettingsPanel.tsx
src/renderer/components/settings/OrganizationSetupCenter.tsx
src/renderer/components/settings/OrganizationTreeCanvas.tsx
src/renderer/components/settings/ReviewGovernanceSettingsPanel.tsx
src/renderer/components/settings/SystemLogPanel.tsx
src/renderer/components/settings/UpdateSettingsPanel.tsx
src/renderer/components/strategic_accompaniment/StrategicBrainView.tsx
src/renderer/components/tasks/AgentExecutionPanel.tsx
src/renderer/components/tasks/AgentSimulationCalendarView.tsx
src/renderer/components/tasks/AgentWeeklyDigestPanel.tsx
src/renderer/components/tasks/AgentWeeklyPlanEditor.tsx
src/renderer/components/tasks/AgentWeeklyPlanPanel.tsx
src/renderer/components/tasks/EventLineClarificationComposer.tsx
src/renderer/components/tasks/EventLineReportPanel.tsx
src/renderer/components/tasks/ReviewHistoryPicker.tsx
src/renderer/components/tasks/ReviewMetricGrid.tsx
src/renderer/components/tasks/TaskCalendarView.tsx
src/renderer/components/tasks/TaskOrgContextPanel.tsx
src/renderer/components/tasks/TaskTemplateEditorModal.tsx
src/renderer/components/tasks/UnderstandingPanel.tsx
src/renderer/components/tasks/WeeklyReviewStructuredFields.tsx
src/renderer/components/tasks/WeeklyReviewSummaryPanel.tsx
src/renderer/components/tasks/reviewDraft.ts
src/renderer/components/topics/TopicIntelChatPanel.tsx
src/renderer/components/topics/TopicIntelDetailPanel.tsx
src/renderer/components/topics/TopicsManagementView.tsx
src/renderer/legacy_features/topics/LegacyTopicsManagementView.tsx
src/renderer/legacy_features/topics/TopicIntelInboxCard.tsx
src/renderer/lib/api.ts
src/renderer/lib/clientDnaPromptTemplates.ts
src/renderer/lib/organizationEmployeeFilters.ts
src/renderer/lib/taskTimeline.ts
src/renderer/lib/workspaceClientUiStore.test.ts
src/renderer/lib/workspaceClientUiStore.ts
src/renderer/main.tsx
src/renderer/qrcode.d.ts
src/renderer/styles.css
src/renderer/vite-env.d.ts
```

## src/renderer/lib/api.ts 导出（API 客户端函数清单）

总行数：3339

### export 函数
```
480:export async function getHealth() {
516:export async function getBrainDashboard() {
795:export async function getDigitalAssetDashboard() {
799:export async function getOrganizationDnaV2Snapshot() {
803:export async function refreshOrganizationDnaV2(triggerSource = 'manual') {
810:export async function getClientDigitalAssets(clientId: string) {
814:export async function refreshClientDigitalAssetNarrative(clientId: string) {
820:export async function getTaskContextPreview(taskId: string) {
824:export async function getClientPageContext(
851:export async function getTaskPageContext(taskId: string, prompt = '', includeRawEvidence = false) {
888:export async function getTaskUnderstanding(taskId: string) {
892:export async function getTaskSmartBrief(taskId: string) {
896:export async function getTaskContextBrief(taskId: string) {
900:export async function getTaskContextBriefsBatch(taskIds: string[]) {
907:export async function getTaskPrepPack(taskId: string) {
911:export async function createTaskPrepProposal(taskId: string) {
917:export async function getTaskSmartBriefsBatch(taskHints: Array<{ id: string; title: string; desc?: string; clientId?: string | null; eventLineId?: string | null; attachmentTitles?: string[] }>) {
924:export async function adoptTaskSmartBriefAction(taskId: string, actionKey: string, payload: { createdTaskId: string; actionText?: string }) {
934:export async function getAuthState() {
938:export async function register(payload: AuthRegisterPayload) {
945:export async function getDepartmentOptions(params?: { organizationId?: string | null; inviteCode?: string | null }) {
953:export async function resolveInviteCode(code: string) {
957:export async function login(payload: AuthLoginPayload) {
964:export async function processPendingConsultationKnowledgeRequests() {
970:export async function logout() {
974:export async function changePassword(payload: ChangePasswordPayload) {
981:export async function updateProfile(payload: UpdateProfilePayload) {
988:export async function getLocalInputMemory() {
992:export async function saveCloudAuthInputMemory(payload: SaveCloudAuthInputMemoryPayload) {
999:export async function saveAiInputMemory(payload: SaveAiInputMemoryPayload) {
1006:export async function saveFeishuInputMemory(payload: SaveFeishuInputMemoryPayload) {
1013:export async function adminResetPassword(employeeId: string, payload: AdminResetPasswordPayload) {
1020:export async function getSettings() {
1024:export async function getMaintenanceModeStatus() {
1028:export async function enterMaintenanceMode() {
1032:export async function exitMaintenanceMode() {
1036:export async function getMaintenanceModeMembers() {
1040:export async function updateMaintenanceModeMembers(payload: MaintenancePermissionUpdatePayload) {
1047:export async function updateSettings(payload: SettingsPayload) {
1054:export async function getTaskSettings() {
1058:export async function updateTaskSettings(payload: TaskSettingsPayload) {
1065:export async function getOrgModelProfile() {
1069:export async function updateOrgModelProfile(payload: OrgModelSettings) {
1076:export async function parseOrgIntroDocument(payload: OrgIntroDocumentUploadPayload) {
1083:export async function backfillOrgTaskLinks() {
1089:export async function getClientWorkspaceSettings() {
1093:export async function updateClientWorkspaceSettings(payload: ClientWorkspaceSettingsPayload) {
1100:export async function getTopicsSettings() {
1104:export async function updateTopicsSettings(payload: TopicsSettingsPayload) {
1111:export async function getAnalysisWorkbenchSettings() {
1115:export async function updateAnalysisWorkbenchSettings(payload: AnalysisWorkbenchSettingsPayload) {
1122:export async function getHandbookSettings() {
1126:export async function updateHandbookSettings(payload: HandbookSettingsPayload) {
1133:export async function getSystemAdminSettings() {
1137:export async function updateSystemAdminSettings(payload: SystemAdminSettingsPayload) {
1144:export async function getMainChainStabilitySettings() {
1148:export async function updateMainChainStabilitySettings(payload: MainChainStabilitySettingsPayload) {
1155:export async function getFeishuBotSettings() {
1159:export async function updateFeishuBotSettings(payload: FeishuBotSettingsPayload) {
1166:export async function getFeishuUserBinding() {
1170:export async function startFeishuUserBinding() {
1176:export async function clearFeishuUserBinding() {
1182:export async function getOrgMembershipSummary() {
1186:export async function applyOrgMembership(payload: OrgMembershipApplyPayload) {
1193:export async function getFeishuMemberAuthorization() {
1197:export async function startFeishuMemberAuthorization() {
1203:export async function clearFeishuMemberAuthorization() {
1209:export async function getOrgFeishuIntegration() {
1213:export async function saveOrgFeishuIntegration(payload: OrgFeishuIntegrationPayload) {
1220:export async function getFeishuDeliveryProfile() {
1224:export async function saveFeishuDeliveryProfile(payload: FeishuDeliveryProfilePayload) {
1231:export async function createBackup() {
1235:export async function scanLegacy(path: string) {
1242:export async function loadDemoData() {
1246:export async function clearDemoData() {
1250:export async function getActivityLogs() {
1290:export async function getSystemLogs(params?: {
1309:export async function exportSystemLogs(params?: {
1327:export async function getLogDates() {
1331:export async function getEmployees() {
1335:export async function approveEmployee(id: string, payload: EmployeeRolePayload) {
1342:export async function rejectEmployeeReview(id: string, payload: EmployeeRejectPayload) {
1349:export async function disableEmployee(id: string) {
1355:export async function updateEmployeeRole(id: string, payload: EmployeeRolePayload) {
1362:export async function updateEmployeeDepartment(id: string, payload: EmployeeDepartmentPayload) {
1369:export async function getMentionCandidates(query = '') {
1373:export async function getClients() {
1378:export async function createClient(payload: ClientMutationPayload) {
1385:export async function updateClient(id: string, payload: ClientMutationPayload) {
1392:export async function deleteClient(id: string) {
1398:export async function deleteClientFolder(clientId: string, folderId: string) {
1404:export async function getClientWorkspace(id: string) {
1408:export async function createAnalysisJob(payload: AnalysisJobCreatePayload) {
1415:export async function backfillAnalysisMainChain(payload: AnalysisBackfillMainChainPayload) {
1422:export async function getAnalysisJob(jobId: string) {
1426:export async function getAnalysisJobStages(jobId: string) {
1430:export async function getRuntimeRunLog(runId: string) {
1434:export async function createDnaDelta(payload: DnaDeltaCreatePayload) {
1441:export async function confirmJudgment(payload: JudgmentConfirmPayload) {
1448:export async function decideApproval(payload: ApprovalDecisionPayload) {
1455:export async function getClientJudgments(clientId: string) {
1459:export async function getClientTopics(clientId: string) {
1463:export async function getClientConflicts(clientId: string) {
1467:export async function getClientOpenQuestions(clientId: string) {
1471:export async function getClientRuntimeRunLogs(clientId: string) {
1475:export async function getAnalysisMigrationMetrics() {
1479:export async function getClientDnaDocuments(clientId: string) {
1483:export async function getClientDnaDocument(clientId: string, moduleKey: ClientDnaModule['moduleKey']) {
1487:export async function updateClientDnaDocument(
1498:export async function getClientProjectStructure(clientId: string) {
1502:export async function getProjectModuleDetail(clientId: string, moduleId: string) {
1506:export async function createProjectModule(clientId: string, payload: ProjectModulePayload) {
1513:export async function updateProjectModule(clientId: string, moduleId: string, payload: ProjectModulePayload) {
1520:export async function deleteProjectModule(clientId: string, moduleId: string) {
1526:export async function getProjectFlowDetail(clientId: string, flowId: string) {
1530:export async function createProjectFlow(clientId: string, payload: ProjectFlowPayload) {
1537:export async function updateProjectFlow(clientId: string, flowId: string, payload: ProjectFlowPayload) {
1544:export async function deleteProjectFlow(clientId: string, flowId: string) {
1550:export async function getClientKnowledgeStatus(clientId: string) {
1554:export async function getClientKnowledgeProgress(clientId: string) {
1558:export async function getRetrievalSettings() {
1562:export async function updateRetrievalSettings(payload: Partial<RetrievalModelSettings>) {
1569:export async function getRetrievalHealth() {
1573:export async function getRetrievalShadowSummary(clientId?: string) {
1581:export async function getRetrievalShadowRuns(clientId?: string, limit = 60) {
1588:export async function reindexClientVector(clientId: string) {
1601:export async function getClientVectorIndexStatus(clientId: string) {
1615:export async function resolveDataCenterKernel(payload: DataCenterRequest) {
1622:export async function diagnoseDataCenter(params: {
1640:export async function getDataCenterShadowSummary(params?: { scopeType?: string; scopeId?: string }) {
1649:export async function getDataCenterShadowRuns(params?: { scopeType?: string; scopeId?: string; limit?: number }) {
1657:export async function getWorkspaceChatDiagnostics(clientId: string, recentMessages = 20) {
1664:export async function getWorkspaceAnswerValueDiagnostics(clientId: string, recentMessages = 50) {
1671:export async function createWorkspaceAnswerValueReview(payload: {
1700:export async function listWorkspaceAnswerValueReviews(params?: { clientId?: string; limit?: number }) {
1707:export async function getWorkspaceAnswerValueSummary(clientId: string) {
1713:export async function createWorkspaceValueValidationSession(clientId: string) {
1720:export async function listWorkspaceValueValidationSessions(params?: { clientId?: string; limit?: number }) {
1727:export async function getWorkspaceValueValidationSession(sessionId: string) {
1731:export async function completeWorkspaceValueValidationQuestion(
1766:export async function finishWorkspaceValueValidationSession(sessionId: string) {
1772:export async function listWorkspaceAnswerQualityFailures(params?: { clientId?: string; limit?: number }) {
1779:export async function resolveWorkspaceAnswerQualityFailure(failureId: string, note = '') {
1789:export async function createWorkspaceAnswerActionProposal(messageId: string) {
1798:export async function createWorkspaceAnswerActionTask(messageId: string) {
1807:export async function createWorkspaceAnswerActionEvidenceRequest(messageId: string) {
1816:export async function getGenerationRuntimeState(
1829:export async function resetGenerationRuntimeState(payload: { clientId: string; answerIntent?: string }) {
1842:export async function resetGenerationRuntimeStateV2(payload: {
1861:export async function runLlmHealthcheck(payload?: {
1876:export async function runLlmProviderProbe(payload: {
1891:export async function getSourceIntegrity(workspaceBackendRoot?: string, options?: {
1904:export async function getKnowledgeParseFailures(clientId: string) {
1908:export async function retryKnowledgeParseFailures(clientId: string, payload?: { documentIds?: string[]; force?: boolean; ocrMaxPages?: number; ocrBatchSize?: number; ocrContinueToEnd?: boolean; forceOcr?: boolean }) {
1922:export async function getWorkspaceDataCenterReadiness(clientId: string) {
1926:export async function runWorkspaceDataCenterReadinessAction(
1947:export async function getWorkspaceContextRefreshEvents(
1961:export async function enqueueWorkspaceContextRefreshEvent(
1981:export async function createWorkspaceProposalDraft(
2008:export async function getDataCenterProposalDrafts(params?: {
2026:export async function markDataCenterProposalDraftReviewed(draftId: string, payload?: { note?: string }) {
2035:export async function rejectDataCenterProposalDraft(draftId: string, payload?: { reason?: string }) {
2044:export async function promoteDataCenterProposalDraft(
2067:export async function getExternalEvidenceCards(params?: {
2081:export async function createExternalEvidenceCardFromTopicCandidate(topicId: string) {
2087:export async function acceptExternalEvidenceCard(cardId: string) {
2093:export async function rejectExternalEvidenceCard(cardId: string) {
2099:export async function createProposalDraftFromExternalEvidence(cardId: string) {
2108:export async function getDataCenterEvidenceQuality(params?: {
2122:export async function labelDataCenterEvidenceQuality(
2138:export async function getMeetingPageContext(meetingId: string, prompt?: string, includeRawEvidence?: boolean) {
2147:export async function getMobileDataCenterSnapshot(clientId: string) {
2151:export async function searchClientKnowledge(clientId: string, prompt: string, threadId?: string) {
2158:export async function rebuildClientKnowledge(clientId: string) {
2164:export async function generateClientDnaCandidates(clientId: string, payload?: { refreshGenerated?: boolean }) {
2171:export async function importPaths(clientId: string, mode: 'folder' | 'file', paths: string[], options?: { allowLegacy?: boolean }) {
2178:export async function getDocumentReadingPreview(clientId: string, documentId: string) {
2182:export async function startClientMessage(
2199:export async function getClientMessage(clientId: string, messageId: string) {
2203:export async function getClientChatThread(clientId: string, threadId: string) {
2207:export async function getClientAnalysisRun(clientId: string, runId: string) {
2211:export async function cancelClientAnalysisRun(clientId: string, runId: string) {
2217:export async function vectorizeAnswer(clientId: string, messageId: string) {
2224:export async function exportAnswer(clientId: string, messageId: string) {
2231:export async function createClientTextDocument(clientId: string, payload: { title?: string | null; content: string }) {
2238:export async function startClientLinkMaterialImport(
2253:export async function getLatestClientLinkMaterialImportRun(clientId: string) {
2257:export async function getClientLinkMaterialImportRun(clientId: string, runId: string) {
2261:export async function startClientTemplateFill(clientId: string, templatePath: string) {
2268:export async function getClientTemplateFillRun(clientId: string, runId: string) {
2272:export async function backfillClientWorkspaceImports(clientId: string) {
2278:export async function createMeeting(clientId: string, title: string, scheduledAt?: string) {
2285:export async function getStrategicCockpit(clientId: string) {
2289:export async function confirmStrategicCockpit(clientId: string, payload: StrategicCockpitConfirmPayload) {
2296:export async function createStrategicMeetingPack(clientId: string) {
2302:export async function applyStrategicMeetingPack(clientId: string, meetingId: string) {
2308:export async function getStrategicThoughts(params?: {
2325:export async function refreshStrategicThoughts(payload: StrategicThoughtRefreshPayload) {
2332:export async function updateStrategicThoughtState(thoughtId: string, payload: StrategicThoughtStatePayload) {
2339:export async function reviewStrategicThought(thoughtId: string, payload: StrategicThoughtReviewPayload) {
2346:export async function createClientFolder(clientId: string, label: string) {
2353:export async function renameClientFolder(clientId: string, folderId: string, label: string) {
2360:export async function updateClientFolder(clientId: string, folderId: string, payload: { label?: string; isHidden?: boolean; sortOrder?: number }) {
2367:export async function moveClientDocumentToFolder(clientId: string, documentId: string, payload: { folderId?: string | null; folderLabel?: string | null }) {
2374:export async function recommendClientFolder(
2384:export async function recommendClientFolderPlan(clientId: string) {
2391:export async function applyClientFolderRecommendation(clientId: string, payload?: { targetFolderLabels?: string[] }) {
2398:export async function previewClientDocumentAutoRepair(clientId: string, payload?: DocumentAutoRepairPreviewPayload) {
2405:export async function applyClientDocumentAutoRepair(clientId: string, payload?: DocumentAutoRepairApplyPayload) {
2412:export async function launchFeishuMeeting(clientId: string, payload: { title: string; scheduledAt?: string; sourceTaskId?: string | null }) {
2419:export async function ingestMeeting(clientId: string, meetingId: string, transcriptText: string, notes: string) {
2426:export async function extractMeeting(clientId: string, meetingId: string) {
2432:export async function resolveMeeting(clientId: string, meetingId: string) {
2438:export async function publishMeeting(clientId: string, meetingId: string) {
2444:export async function createMeetingPrepareProposal(clientId: string, meetingId: string) {
2450:export async function createMeetingFollowupProposal(clientId: string, meetingId: string) {
2456:export async function getProposals(options?: { status?: string; clientId?: string; kind?: string; limit?: number }) {
2466:export async function getProposal(proposalId: string) {
2470:export async function approveProposal(
2482:export async function rejectProposal(
2494:export async function getProposalExecutionPreview(proposalId: string) {
2498:export async function createProposalExecutionTicket(
2511:export async function getExecutionTickets(params?: { clientId?: string; status?: string; limit?: number }) {
2519:export async function executeExecutionTicket(ticketId: string, payload: ProposalExecutionPayload = {}) {
2529:export async function retryExecutionTicket(ticketId: string, payload: ProposalExecutionPayload = {}) {
2539:export async function getExecutionTicketLogs(ticketId: string, limit = 200) {
2545:export async function batchApproveProposals(payload: ProposalBatchActionPayload) {
2556:export async function batchRejectProposals(payload: ProposalBatchActionPayload) {
2567:export async function startKernelPrimaryRollout(payload: KernelPrimaryRolloutStartPayload) {
2578:export async function completeKernelPrimaryRollout(runId: string) {
2584:export async function rollbackKernelPrimaryRollout(runId: string, payload: KernelPrimaryRolloutRollbackPayload = {}) {
2591:export async function listKernelPrimaryRollouts(limit = 40) {
2597:export async function getExecutionRetryMetrics(params?: { clientId?: string; days?: number }) {
2604:export async function createEvidenceQualitySnapshot(days = 7) {
2611:export async function listEvidenceQualitySnapshots(limit = 30) {
2617:export async function runDataCenterRollbackDrill(payload: RollbackDrillPayload) {
2627:export async function getDataCenterOperationalStatus(params?: { clientId?: string }) {
2634:export async function getDataCenterArtifactStatus() {
2638:export async function getDataCenterSchemaStatus() {
2642:export async function ensureDataCenterSchema() {
2648:export async function executeProposal(proposalId: string, payload: ProposalApprovalPayload = {}) {
2656:export async function createGoal(clientId: string, payload: { title: string; quarter: string; progress: number; ownerName: string }) {
2663:export async function upsertDna(clientId: string, payload: { category: string; canonicalName: string; aliases: string[]; description: string }) {
2670:export async function getTaskBoard() {
2674:export async function createSupportRequest(payload: SupportRequestCreatePayload) {
2681:export async function getSupportRequests(params?: { status?: string; taskId?: string }) {
2689:export async function resolveSupportRequest(id: string, payload: SupportRequestResolvePayload) {
2696:export async function getAgentWorklogs(month?: string) {
2701:export async function updateAgentWeeklyPlan(weekLabel: string, agentKey: string, payload: AgentWeeklyPlanPayload) {
2708:export async function getAgentExecutionTasks(weekLabel: string, departmentName?: string) {
2716:export async function createTaskList(payload: TaskListMutationPayload) {
2723:export async function updateTaskList(id: string, payload: TaskListMutationPayload) {
2730:export async function deleteTaskList(id: string) {
2736:export async function createTaskTag(payload: TaskTagMutationPayload) {
2743:export async function updateTaskTag(id: string, payload: TaskTagMutationPayload) {
2750:export async function deleteTaskTag(id: string) {
2756:export async function createTask(payload: TaskMutationPayload) {
2763:export async function updateTask(id: string, payload: Partial<TaskMutationPayload> & { status?: string }) {
2770:export async function deleteTask(id: string) {
2776:export async function uploadTaskAttachment(
2797:export async function getEventLines() {
2801:export async function createEventLine(payload: EventLineMutationPayload) {
2808:export async function getEventLine(id: string) {
2812:export async function getEventLineReportSnapshot(id: string) {
2816:export async function updateEventLine(id: string, payload: Partial<EventLineMutationPayload>) {
2823:export async function closeEventLine(id: string) {
2829:export async function reopenEventLine(id: string) {
2835:export async function deleteEventLine(id: string) {
2841:export async function addEventLineNote(id: string, text: string) {
2848:export async function generateEventLineClarificationDraft(
2858:export async function confirmTask(id: string) {
2862:export async function rejectTask(id: string, reason: string) {
2869:export async function approveTaskReview(id: string) {
2873:export async function returnTaskReview(id: string, reason: string) {
2880:export async function saveTaskNote(id: string, note: string) {
2887:export async function completeTaskWithReview(id: string, reviewNote: string) {
2894:export async function getTaskViews() {
2898:export async function getTaskTagSuggestions(payload: TaskTagSuggestionPayload) {
2905:export async function getReviews(weekLabel?: string, options?: { skipAi?: boolean; perspective?: ReviewPerspectiveKey; departmentId?: string | null; signal?: AbortSignal }) {
2915:export async function refreshWeeklyOverview(payload: WeeklyOverviewRefreshPayload) {
2922:export async function getWeeklyOverviewRefreshStatus(params: {
2935:export async function getReviewDashboardDrillTarget(params: {
2954:export async function getReviewHistory() {
2958:export async function createWeeklyReview(payload: WeeklyReviewPayload) {
2965:export async function createWeeklyReviewDraft(payload: WeeklyReviewPayload) {
2972:export async function getTopics() {
2976:export async function captureTopicRadars() {
2982:export async function captureIntelligenceRadarTest(id: string) {
2996:export async function createRadar(payload: TopicRadarPayload) {
3003:export async function updateRadar(id: string, payload: TopicRadarPayload) {
3010:export async function deleteRadar(id: string) {
3014:export async function suggestRadarTitle(prompt: string) {
3021:export async function assistRadarDraft(prompt: string, timeRange: string) {
3028:export async function suggestRadarSourceLabel(url: string) {
3035:export async function getCandidateInsights(id: string) {
3039:export async function askCandidateQuestion(id: string, payload: TopicCandidateChatPayload) {
3059:export async function getCandidateTaskPlan(id: string) {
3063:export async function promoteCandidateTasks(id: string, tasks: TopicTaskPromotionDraft[]) {
3070:export async function deleteCandidate(id: string) {
3074:export async function favoriteIntelligenceItem(
3081:export async function unfavoriteIntelligenceItem(candidateId: string, userId: string) {
3085:export async function shareIntelligenceItem(
3098:export async function runDueIntelligenceProfiles(_options?: { limit?: number }) {
3108:export async function refreshIntelligenceProfile(id: string, payload?: Record<string, unknown>) {
3115:export async function trialRunIntelligenceProfile(id: string) {
3121:export async function updateIntelligenceProfile(id: string, payload: unknown) {
3128:export async function getAnalysisTools() {
3132:export async function runAnalysis(payload: AnalysisRunPayload) {
3139:export async function getFundraisingDeepDnaLibrary() {
3143:export async function upsertFundraisingDeepDna(payload: DeepDnaRecord) {
3150:export async function createFundraisingManualDna(payload: {
3168:export async function importFundraisingDna(payload: {
3182:export async function createFundraisingWebDnaDraft(payload: {
3193:export async function publishFundraisingDna(id: string) {
3199:export async function getFundraisingCases() {
3203:export async function upsertFundraisingCase(payload: CoachCaseRecord) {
3210:export async function getFundraisingReminderRules() {
3214:export async function upsertFundraisingReminderRule(payload: CoachReminderRule) {
3221:export async function getFundraisingWritingNorms() {
3225:export async function upsertFundraisingWritingNorm(payload: OrgWritingNorm) {
3232:export async function getFundraisingRunComparison(runId: string) {
3236:export async function getHandbook() {
3240:export async function getHandbookEntry(id: string) {
3244:export async function createHandbook(payload: HandbookEntryPayload) {
3251:export async function getGrowthOverview(weekLabel?: string) {
3256:export async function getGrowthWorkbench(params?: {
3269:export async function getGrowthBadges() {
3273:export async function getGrowthLedger(params?: { abilityKey?: string; weekLabel?: string }) {
3281:export async function acceptGrowthRecommendation(id: string) {
3287:export async function dismissGrowthRecommendation(id: string, payload: GrowthRecommendationDismissPayload = {}) {
3294:export async function markHandbookEntryReused(id: string, payload: GrowthValidationPayload = {}) {
3301:export async function updateGrowthPendingCapture(id: string, payload: GrowthPendingCaptureActionPayload) {
3309:export async function selectCollabRepo() {
3313:export async function getCollabRepoStatus(repoPath?: string | null) {
3317:export async function previewPushToMain(repoPath: string) {
3321:export async function commitAndPushToMain(payload: CommitAndPushToMainPayload) {
3325:export async function previewPullFromMain(repoPath: string, targetCommit?: string | null) {
3329:export async function pullSelectedFromMain(payload: PullSelectedFromMainPayload) {
3333:export async function rebuildAndInstallFromRepo(repoPath: string) {
3337:export async function setWorkspaceInteractionState(payload: { active: boolean; source: string; detail?: string | null }) {
```

### export const（含箭头函数）
```
```

### fetch / 请求路径出现位置
```
481:  return request<HealthResponse>('/api/v1/system/health');
517:  return request<BrainDashboard>('/api/v1/brain/dashboard');
796:  return request<DigitalAssetDashboard>('/api/v1/digital-assets/dashboard');
800:  return request<OrganizationDnaV2Snapshot>('/api/v1/digital-assets/organization-dna');
804:  return request<OrganizationDnaRefreshRun>('/api/v1/digital-assets/organization-dna/refresh', {
901:  return request<{ briefs: TaskContextBrief[] }>('/api/v1/tasks/context-briefs/batch', {
918:  return request<TaskSmartBrief[]>('/api/v1/tasks/smart-briefs', {
935:  return request<AuthState>('/api/v1/auth/me');
939:  return request<AuthState>('/api/v1/auth/register', {
958:  return request<AuthState>('/api/v1/auth/login', {
965:  return request<ConsultationKnowledgeProcessSummary>('/api/v1/consultation/knowledge-requests/process-pending', {
971:  return request<AuthState>('/api/v1/auth/logout', { method: 'POST' });
975:  return request<{ message: string }>('/api/v1/auth/change-password', {
982:  return request<AuthState>('/api/v1/auth/me', {
989:  return request<LocalInputMemory>('/api/v1/local-input-memory');
993:  return request<LocalInputMemory>('/api/v1/local-input-memory/cloud-auth', {
1000:  return request<LocalInputMemory>('/api/v1/local-input-memory/ai', {
1007:  return request<LocalInputMemory>('/api/v1/local-input-memory/feishu', {
1021:  return request<{ settings: AppSettings; operators: Operator[]; health: HealthResponse }>('/api/v1/settings');
1025:  return request<MaintenanceModeStatus>('/api/v1/maintenance-mode/status');
1029:  return request<MaintenanceModeStatus>('/api/v1/maintenance-mode/enter', { method: 'POST' });
1033:  return request<MaintenanceModeStatus>('/api/v1/maintenance-mode/exit', { method: 'POST' });
1037:  return request<MaintenanceMemberPermission[]>('/api/v1/admin/maintenance-mode/members');
1041:  return request<MaintenanceMemberPermission[]>('/api/v1/admin/maintenance-mode/members', {
1048:  return request<{ settings: AppSettings; operators: Operator[]; health: HealthResponse }>('/api/v1/settings', {
1055:  return request<TaskSettings>('/api/v1/settings/tasks');
1059:  return request<TaskSettings>('/api/v1/settings/tasks', {
1066:  return request<OrgModelSettings>('/api/v1/settings/org-model/profile');
1070:  return request<OrgModelSettings>('/api/v1/settings/org-model/profile', {
1077:  return request<OrgIntroDocumentSettings>('/api/v1/settings/org-model/intro-document', {
1084:  return request<TaskOrgBackfillResult>('/api/v1/settings/org-model/backfill-task-links', {
1090:  return request<ClientWorkspaceSettings>('/api/v1/settings/client-workspace');
1094:  return request<ClientWorkspaceSettings>('/api/v1/settings/client-workspace', {
1101:  return request<TopicsSettings>('/api/v1/settings/topics');
1105:  return request<TopicsSettings>('/api/v1/settings/topics', {
1112:  return request<AnalysisWorkbenchSettings>('/api/v1/settings/analysis-workbench');
1116:  return request<AnalysisWorkbenchSettings>('/api/v1/settings/analysis-workbench', {
1123:  return request<HandbookSettings>('/api/v1/settings/handbook');
1127:  return request<HandbookSettings>('/api/v1/settings/handbook', {
1134:  return request<SystemAdminSettings>('/api/v1/settings/system-admin');
1138:  return request<SystemAdminSettings>('/api/v1/settings/system-admin', {
1145:  return request<MainChainStabilitySettings>('/api/v1/settings/main-chain-stability');
1149:  return request<MainChainStabilitySettings>('/api/v1/settings/main-chain-stability', {
1156:  return request<FeishuBotSettings>('/api/v1/settings/feishu-bot');
1160:  return request<FeishuBotSettings>('/api/v1/settings/feishu-bot', {
1167:  return request<FeishuUserBinding>('/api/v1/settings/feishu-user-binding');
1171:  return request<FeishuUserBindingStartResult>('/api/v1/settings/feishu-user-binding/start', {
1177:  return request<FeishuUserBinding>('/api/v1/settings/feishu-user-binding', {
1183:  return request<OrgMembershipSummary>('/api/v1/me/org-membership');
1187:  return request<OrgMembershipSummary>('/api/v1/me/org-membership/apply', {
1194:  return request<FeishuMemberAuthorization>('/api/v1/me/feishu-authorization');
1198:  return request<FeishuMemberAuthorizationStartResult>('/api/v1/me/feishu-authorization/start', {
1204:  return request<FeishuMemberAuthorization>('/api/v1/me/feishu-authorization', {
1210:  return request<OrgFeishuIntegration>('/api/v1/org-integrations/feishu');
1214:  return request<OrgFeishuIntegration>('/api/v1/org-integrations/feishu/validate-and-save', {
1221:  return request<FeishuDeliveryProfile>('/api/v1/me/feishu-delivery-profile');
1225:  return request<FeishuDeliveryProfile>('/api/v1/me/feishu-delivery-profile', {
1232:  return request<{ backupPath: string; createdAt: string }>('/api/v1/settings/backup', { method: 'POST' });
1236:  return request<LegacyScanReport>('/api/v1/settings/legacy-scan', {
1243:  return request<DemoDataReport>('/api/v1/settings/demo-data/load', { method: 'POST' });
```

## src/shared/types.ts 分类

总行数：6582

### export interface 清单
```
90:export interface Operator {
99:export interface AiModelProfileRecord {
109:export interface AppSettings {
129:export interface SessionUser {
144:export interface AuthState {
154:export interface ConsultationKnowledgeRequestRecord {
176:export interface ConsultationKnowledgeProcessSummary {
186:export interface EmployeeRecord {
209:export interface MaintenanceModeStatus {
219:export interface MaintenanceMemberPermission {
228:export interface MaintenancePermissionUpdatePayload {
236:export interface DepartmentOption {
242:export interface OrgInviteResolveResult {
251:export interface OrgProfileSettings {
268:export interface OrgQuarterPlanSettings {
280:export interface OrgDepartmentQuarterPlanSettings {
290:export interface OrgDepartmentSettings {
308:export interface OrgIntroDocumentSettings {
319:export interface OrgRoleTemplateSettings {
339:export interface OrgEmployeeBindingSettings {
354:export interface OrgReportingLineSettings {
368:export interface OrgTaskControlRuleSettings {
384:export interface OrgRoleProcessTemplateSettings {
399:export interface OrgFocusItemSettings {
411:export interface OrgDepartmentPlanItemSettings {
423:export interface OrgDepartmentPlanSettings {
436:export interface TaskPlanLinkRecord {
445:export interface SupportRequestRecord {
460:export interface SupportRequestCreatePayload {
470:export interface SupportRequestResolvePayload {
475:export interface TaskOrgBackfillResult {
484:export interface OrgModelSettings {
497:export interface MentionCandidate {
505:export interface HealthAiState {
518:export interface HealthResponse {
552:export interface ClientSummary {
567:export interface ClientFolder {
584:export interface ClientFolderRecommendation {
594:export interface ClientFolderRecommendationPlan {
608:export interface DocumentAutoRepairPreviewPayload {
614:export interface DocumentAutoRepairApplyPayload {
640:export interface DocumentAutoRepairItem {
659:export interface DocumentAutoRepairPreview {
670:export interface DocumentAutoRepairApplyResult {
679:export interface DocumentRecord {
692:export interface KnowledgeStatus {
722:export interface OrganizationNotebookSnapshot {
739:export interface EventLineMemorySnapshot {
756:export interface MemoryFact {
771:export interface ClarificationRecord {
787:export interface MemoryStatus {
799:export interface BackgroundReadiness {
806:export interface DocumentCard {
848:export interface ImportDocumentRecord {
855:export interface ImportRecord {
868:export interface WorkspaceImportBackfillResponse {
877:export interface ClientTemplateFillField {
892:export interface ClientTemplateFillResponse {
903:export interface ClientTemplateFillRun {
933:export interface LinkMaterialImportRun {
951:export interface GoalRecord {
960:export interface DnaTerm {
970:export interface EvidenceItem {
1001:export interface AiStructuredResponse {
1077:export interface PageIntent {
1088:export interface ContextQuality {
1110:export interface RetrievalModelSettings {
1136:export interface RouteDecision {
1158:export interface RetrievalTrace {
1174:export interface RetrievalHealthComponent {
1183:export interface RetrievalHealth {
1193:export interface RetrievalShadowRun {
1206:export interface RetrievalShadowSummary {
1214:export interface DataCenterShadowRun {
1234:export interface DataCenterShadowSummary {
1247:export interface GenerationRuntimeState {
1262:export interface GenerationRuntimeDecision {
1272:export interface DiagnosticsBucket {
1277:export interface WorkspaceChatDiagnostics {
1317:export interface WorkspaceAnswerFinalization {
1329:export interface WorkspaceAnswerPresentationSection {
1337:export interface WorkspaceAnswerPresentation {
1341:export interface WorkspaceAnswerEvidenceChip {
1352:export interface WorkspaceAnswerActionCard {
1363:export interface WorkspaceAnswerExperience {
1376:export interface WorkspaceAnswerValueTopItem {
1381:export interface WorkspaceAnswerValueDiagnostics {
1426:export interface WorkspaceAnswerValueReview {
1442:export interface WorkspaceAnswerValueSummary {
1458:export interface WorkspaceValueValidationQuestion {
1463:export interface WorkspaceValueValidationSessionSummary {
1475:export interface WorkspaceValueValidationSession {
1486:export interface DataCenterArtifactStatusItem {
1502:export interface DataCenterArtifactStatus {
1508:export interface DataCenterSchemaStatus {
1516:export interface WorkspaceAnswerActionCardResult {
1528:export interface WorkspaceAnswerQualityFailure {
1549:export interface SourceIntegrityReport {
1565:export interface LlmHealthcheckResult {
1574:export interface LlmProviderProbeResult {
1581:export interface AnswerPolicy {
1591:export interface PageContextPack {
1624:export interface AnswerPlan {
1648:export interface AnswerMaterial {
1662:export interface BusinessProfileSlots {
1671:export interface StrategyProfileSlots {
1680:export interface EvidenceQualitySignal {
1705:export interface ActionSuggestion {
1724:export interface DataCenterSearchHit {
1747:export interface DataCenterSearchResult {
1758:export interface DataCenterPrepSection {
1764:export interface DataCenterPrepResult {
1778:export interface DataCenterProposalDraft {
1813:export interface DataCenterProposalDraftPromoteResponse {
1828:export interface ExternalEvidenceCard {
1850:export interface KnowledgeParseFailure {
1864:export interface DataCenterScope {
1886:export interface DataCenterRequest {
1897:export interface AnswerQualityReport {
1912:export interface DataCenterKernelResult {
1929:export interface KnowledgeParseFailureRetryItem {
1947:export interface KnowledgeParseFailureRetryResult {
1972:export interface WorkspaceDocumentProcessingStatus {
2007:export interface WorkspaceDataCenterReadinessSummary {
2048:export interface WorkspaceDataCenterReadinessJobEvent {
2055:export interface WorkspaceDataCenterLocalOptimizationStatus {
2076:export interface WorkspaceDataCenterReadinessJobs {
2083:export interface WorkspaceDataCenterReadinessFix {
2093:export interface WorkspaceDataCenterReadinessRecentJob {
2103:export interface WorkspaceDataCenterReadiness {
2114:export interface WorkspaceDataCenterReadinessActionPayload {
2132:export interface WorkspaceDataCenterReadinessActionResult {
2142:export interface WorkspaceContextRefreshEvent {
2159:export interface WorkspaceContextRefreshEnqueuePayload {
2168:export interface WorkspaceContextRefreshEnqueueResult {
2173:export interface WorkspaceProposalDraftCreatePayload {
2194:export interface StateAnswerSections {
2204:export interface StateSourceSummary {
2213:export interface ChatMessage {
2245:export interface ChatThread {
2253:export interface ChatStartResponse {
2260:export interface ChatThreadDetailResponse {
2265:export interface WorkspaceStateItem {
2276:export interface WorkspaceStateProjection {
2284:export interface StateQueryPlan {
2290:export interface StateQueryHit {
2299:export interface StateAnswerContextPack {
2312:export interface AgendaItem {
2318:export interface DecisionItem {
2323:export interface RiskItem {
2329:export interface AmbiguityItem {
2336:export interface MeetingSummary {
2345:export interface MeetingDetail extends MeetingSummary {
2355:export interface FeishuMeetingLaunchResult {
2365:export interface TaskList {
2375:export interface TaskTag {
2386:export interface Task {
2439:export interface TaskAttachment {
2456:export interface TaskOrgContext {
2471:export interface TaskProjectContext {
2496:export interface EventLine {
2527:export interface EventLineActivity {
2541:export interface EventLineDetail {
2550:export interface TaskSmartBriefActionItem {
2562:export interface TaskSmartBrief {
2569:export interface TaskContextBrief {
2585:export interface PrepPackMaterial {
2593:export interface PrepPackCard {
2606:export interface ProposalTargetRef {
2612:export interface ProposalRecord {
2643:export interface ExecutionTicketArtifactRef {
2649:export interface ExecutionTicketResult {
2656:export interface ExecutionTicket {
2675:export interface ExecutionTicketLog {
2685:export interface ProposalExecutionResponse {
2690:export interface ProposalApprovalPayload {
2696:export interface ProposalExecutionPayload {
2701:export interface ProposalExecutionPreview {
2713:export interface ProposalApprovalResult {
2718:export interface ProposalExecutionResult {
2723:export interface ProposalBatchActionPayload {
2729:export interface ProposalBatchResult {
2739:export interface KernelPrimaryRolloutRun {
2756:export interface KernelPrimaryRolloutStartPayload {
2762:export interface KernelPrimaryRolloutRollbackPayload {
2766:export interface ExecutionRetryMetricsTopItem {
2771:export interface ExecutionRetryMetricsAlert {
2776:export interface ExecutionRetryMetrics {
2790:export interface EvidenceQualityFeedbackSnapshot {
2802:export interface RollbackDrillPayload {
2807:export interface RollbackDrillResult {
2820:export interface DataCenterOperationalStatus {
2833:export interface MobileDataCenterSnapshotSummary {
2850:export interface EvidenceQualityAnnotation {
2868:export interface EventLineReportAttachment {
2899:export interface EventLineTimelineNode {
2919:export interface EventLineReportSnapshot {
2932:export interface EventLineAttachment {
2950:export interface EventLineApprovalNode {
2962:export interface EventLineMutationPayload {
2982:export interface EventLineClarificationDraftPayload {
2986:export interface EventLineClarificationDraftResult {
2997:export interface ProjectModule {
3012:export interface ProjectFlow {
3030:export interface ProjectStructureResponse {
3035:export interface ProjectModuleDetail extends ProjectModule {
3043:export interface ProjectFlowDetail extends ProjectFlow {
3049:export interface TaskCollaborator {
3060:export interface TaskActivityRecord {
3070:export interface WeeklyReview {
3091:export interface AgentWorklog {
3106:export interface AgentWeeklyDigest {
3118:export interface AgentWeeklyPlanItem {
3126:export interface AgentWeeklyPlan {
3137:export interface AgentWorklogResponse {
3144:export interface AgentWeeklyPlanItemPayload {
3151:export interface AgentWeeklyPlanPayload {
3158:export interface WeeklyReviewTaskSnapshot {
3182:export interface WeeklyReviewEventLineContext {
3199:export interface WeeklyReviewTaskStructuredNote {
3217:export interface ReviewMetricCard {
3228:export interface WeeklyReviewTaskEntry {
3240:export interface ReviewEvidenceWeight {
3247:export interface ReviewHypothesis {
3259:export interface EventLineEvidenceSlot {
3277:export interface EventLineCompleteness {
3289:export interface ReviewDashboardEvidenceRef {
3296:export interface ReviewDashboardCardTarget {
3304:export interface EventLineContextFact {
3312:export interface EventLineJudgment {
3339:export interface EventLineContextBundle {
3372:export interface EventLineSummaryCard {
3400:export interface EventLineRiskCard {
3421:export interface EventLineOpportunityCard {
3440:export interface TrendSignal {
3459:export interface WeeklyReviewAnalysis {
3483:export interface WeeklyMainlineCard {
3493:export interface WeeklyMainlineCards {
3502:export interface WeeklyEventReviewCard {
3516:export interface WeeklyEventReviewCards {
3522:export interface WeeklyOverviewRefreshPayload {
3529:export interface WeeklyOverviewRefreshStatus {
3542:export interface TaskContextPreview {
3558:export interface PlanNode {
3571:export interface ManagementSignalCard {
3586:export interface PersonalGrowthCard {
3598:export interface ReviewActionCard {
3613:export interface ReviewActionExecutionResult {
3625:export interface HierarchyReport {
3653:export interface TaskViewFilterSet {
3663:export interface TaskViewDefinition {
3679:export interface TaskViewPreset {
3686:export interface TaskViewsResponse {
3691:export interface TaskViewMutationPayload {
3703:export interface ReviewDashboardDrillTargetResponse {
3713:export interface ReviewSimulationBundle {
3722:export interface ReviewPerspectiveOption {
3729:export interface ReviewDashboard {
3761:export interface UnderstandingSourceBreakdown {
3767:export interface UnderstandingOptionalAdvice {
3774:export interface UnderstandingSnapshotV1 {
3795:export interface ClientStrategicProfile {
3808:export interface CooperationRelationship {
3823:export interface CooperationStakeholder {
3830:export interface EventLineWeeklySnapshot {
3846:export interface NarrativeAnalysis {
3868:export interface StrategicPermission {
3875:export interface StrategicReadiness {
3882:export interface StrategicJudgment {
3888:export interface StrategicHeadline {
3897:export interface StrategicHealthLine {
3906:export interface StrategicLine {
3923:export interface StrategicLineDetail extends StrategicLine {
3932:export interface StrategicChecklistItem {
3939:export interface StrategicChecklistGroup {
3946:export interface StrategicChangePoint {
3953:export interface StrategicEvidenceCard {
3958:export interface StrategicEvidencePreview {
3966:export interface StrategicAssetCandidate {
3973:export interface StrategicMeetingPackDraft {
3979:export interface StrategicCockpitSnapshot {
4005:export interface StrategicCockpitConfirmPayload {
4046:export interface StrategicThoughtSource {
4053:export interface StrategicThoughtReview {
4063:export interface StrategicThought {
4099:export interface StrategicThoughtsResponse {
4108:export interface StrategicThoughtRefreshPayload {
4114:export interface StrategicThoughtStatePayload {
4118:export interface StrategicThoughtReviewPayload {
4125:export interface ReviewHistoryEntry {
4132:export interface ReviewHistoryResponse {
4136:export interface TaskSettings {
4148:export interface ClientDnaModule {
4164:export interface ClientDnaModulesResponse {
4168:export interface ClientDnaGeneratePayload {
4172:export interface ClientWorkspaceSettings {
4181:export interface TopicsSettings {
4190:export interface DiagnosisProfileRecord {
4205:export interface OrganizationRiskDnaDocument {
4216:export interface FundraisingKnowledgeDocument {
4230:export interface DeepDnaSourceRecord {
4241:export interface DeepDnaRecord {
4264:export interface DeepDnaDraft {
4275:export interface CoachCaseRecord {
4291:export interface CoachReminderRule {
4302:export interface OrgWritingNorm {
4313:export interface CoachCardRecord {
4327:export interface CoachPayload {
4333:export interface RunComparison {
4343:export interface AnalysisWorkbenchSettings {
4358:export interface HandbookSettings {
4367:export interface SystemAdminSettings {
4376:export interface FeishuBotSettings {
4393:export interface FeishuUserBinding {
4411:export interface FeishuUserBindingStartResult {
4420:export interface OrgMembershipSummary {
4432:export interface OrgFeishuIntegrationAuditRecord {
4443:export interface OrgFeishuIntegration {
4462:export interface OrgFeishuIntegrationPayload {
4470:export interface FeishuDeliveryProfile {
4485:export interface FeishuDeliveryProfilePayload {
4489:export interface FeishuMemberAuthorization {
4510:export interface FeishuMemberAuthorizationStartResult {
4519:export interface TopicRadar {
4528:export interface IntelligenceProfileBackgroundEnrichment {
4535:export interface IntelligenceProfileFetchSummary {
4544:export interface IntelligenceProfile {
4585:export interface IntelligenceProfileMutationPayload {
4597:export interface TopicRadarPreferredSource {
4602:export interface TopicCandidate {
4632:export interface TopicCandidateInsight {
4645:export interface TopicCandidateChatMessage {
4651:export interface TopicCandidateChatPayload {
4656:export interface TopicCandidateChatResponse {
4664:export interface TopicCaptureRun {
4674:export interface TopicCaptureBatchResult {
4680:export interface TopicTaskSuggestion {
4690:export interface TopicTaskPlanResult {
4700:export interface TopicTaskPromotionDraft {
4721:export interface TopicTaskPromotionResult {
4728:export interface AnalysisTemplate {
4735:export interface AnalysisRun {
4747:export interface HandbookEntry {
4777:export interface GrowthContextLink {
4786:export interface HandbookEntryDetail extends HandbookEntry {
4792:export interface HandbookReuseRecord {
4804:export interface XpLedgerEntry {
4844:export interface GrowthAbilityScore {
4856:export interface GrowthRank {
4866:export interface LearningRecommendation {
4897:export interface GrowthOverview {
4921:export interface GrowthSourceCoverage {
4931:export interface GrowthProjectHighlight {
4942:export interface GrowthPendingCapture {
4963:export interface GrowthFocusAction {
4978:export interface GrowthAbilityGap {
4990:export interface GrowthTaskIntent {
5000:export interface GrowthUniversalSkillItem {
5014:export interface GrowthProjectContextPack {
5028:export interface GrowthActionPlanItem {
5040:export interface GrowthMaterialRef {
5048:export interface GrowthWorkbenchStep {
5055:export interface GrowthWorkbenchTask {
5094:export interface GrowthWorkbenchAction {
5109:export interface GrowthWorkbenchMaterial {
5118:export interface GrowthLearningSummary {
5126:export interface GrowthGenericLesson {
5136:export interface GrowthProjectGuidance {
5146:export interface GrowthReasoningInput {
5153:export interface GrowthReasoningTrace {
5163:export interface GrowthRobotAssist {
5170:export interface GrowthAfterActionCapture {
5177:export interface GrowthWorkbenchSupportCopy {
5183:export interface GrowthWorkbenchSnapshot {
5208:export interface GrowthLedgerResponse {
5212:export interface GrowthRecommendationDismissPayload {
5216:export interface GrowthRecommendationActionResponse {
5221:export interface BadgeActionLink {
5226:export interface BadgeEvidence {
5235:export interface BadgeProgress {
5264:export interface BadgeCategory {
5274:export interface BadgeBoardOverview {
5284:export interface BadgeBoard {
5290:export interface GrowthValidationPayload {
5299:export interface GrowthPendingCaptureActionPayload {
5305:export interface GrowthPendingCaptureActionResponse {
5309:export interface GrowthValidationActionResponse {
5320:export interface ClientAnalysisEvidenceSummary {
5331:export interface ClientAnalysisRun {
5360:export interface AnalysisJobCreatePayload {
5373:export interface AnalysisJob {
5403:export interface AnalysisJobStageRun {
5427:export interface RuntimeRunLog {
5452:export interface ThemeCluster {
5472:export interface ConflictGroup {
5491:export interface OpenQuestion {
5508:export interface ContextPack {
5530:export interface DnaDelta {
5552:export interface DnaDeltaCreatePayload {
5562:export interface JudgmentVersion {
5586:export interface JudgmentConfirmPayload {
5592:export interface ApprovalDecisionPayload {
5601:export interface ApprovalRecord {
5614:export interface ApprovalState {
5622:export interface ResolutionScope {
5627:export interface ResolutionCandidate {
5640:export interface ResolutionTrace {
5650:export interface JudgmentBundle {
5656:export interface AnalysisMigrationMetrics {
5671:export interface AnalysisMigrationMetricBucket {
5678:export interface AnalysisWorkerCounterSnapshot {
5684:export interface MainChainCanaryObservation {
5708:export interface MainChainCanaryObservationPayload {
5731:export interface MainChainStabilitySettings {
5739:export interface MainChainStabilitySettingsPayload {
5745:export interface AnalysisCenterSummary {
5761:export interface ClientWorkspace {
5797:export interface AnalysisBackfillMainChainJob {
5806:export interface AnalysisBackfillMainChainPayload {
5814:export interface AnalysisBackfillMainChainResult {
5824:export interface FileReclassEvent {
5836:export interface KnowledgeJob {
5854:export interface KnowledgeJobEvent {
5862:export interface KnowledgeProgress {
5867:export interface KnowledgeSearchHit {
5877:export interface KnowledgeSearchResult {
5901:export interface DocumentReadingPreview {
5915:export interface KnowledgeMemoryRecord {
5930:export interface SettingsPayload {
5946:export interface LegacyScanReport {
5957:export interface DemoDataReport {
5966:export interface ClientMutationPayload {
5976:export interface TaskMutationPayload {
6008:export interface AuthRegisterPayload {
6021:export interface AuthLoginPayload {
6028:export interface RememberedCloudAuthAccount {
6036:export interface LocalInputMemoryCloudAuth {
6042:export interface LocalInputMemoryAiSettings {
6047:export interface LocalInputMemoryFeishuIntegration {
6055:export interface LocalInputMemory {
6061:export interface SaveCloudAuthInputMemoryPayload {
6069:export interface SaveAiInputMemoryPayload {
6074:export interface SaveFeishuInputMemoryPayload {
6082:export interface EmployeeRolePayload {
6086:export interface EmployeeDepartmentPayload {
6090:export interface EmployeeRejectPayload {
6094:export interface ChangePasswordPayload {
6099:export interface UpdateProfilePayload {
6105:export interface OrgMembershipApplyPayload {
6113:export interface AdminResetPasswordPayload {
6117:export interface TaskTagSuggestionPayload {
6125:export interface TaskTagMutationPayload {
6132:export interface TaskListMutationPayload {
6141:export interface TaskSettingsPayload {
6152:export interface OrganizationDnaUploadPayload {
6158:export interface OrgIntroDocumentUploadPayload {
6165:export interface ProjectModulePayload {
6176:export interface ProjectFlowPayload {
6189:export interface ClientWorkspaceSettingsPayload {
6197:export interface TopicsSettingsPayload {
6205:export interface AnalysisWorkbenchSettingsPayload {
6219:export interface HandbookSettingsPayload {
6227:export interface SystemAdminSettingsPayload {
6235:export interface FeishuBotSettingsPayload {
6247:export interface WeeklyReviewPayload {
6268:export interface TopicRadarPayload {
6275:export interface MeetingPipelineResult {
6280:export interface TopicCandidatePayload {
6287:export interface HandbookEntryPayload {
6309:export interface AnalysisRunPayload {
6320:export interface DiagnosisContextReference {
6325:export interface ExternalDiagnosisRequest {
6355:export interface DiagnosisEngineHealth {
6365:export interface BettaFishSignal {
6375:export interface DesktopAppInfo {
6404:export interface DesktopStartupGateResumeResult {
6423:export interface CollabConflictRisk {
6428:export interface CollabFileChange {
6438:export interface CollabChangeGroup {
6446:export interface CollabEffectPreview {
6458:export interface CollabRepoStatus {
6478:export interface PushPreview {
6488:export interface PullPreview {
6502:export interface CollabRemoteCommit {
6518:export interface CommitAndPushToMainPayload {
6525:export interface PullSelectedFromMainPayload {
6533:export interface CollabActionResult {
```

### export type 清单
```
1:export type Priority = 'low' | 'normal' | 'high';
2:export type TaskStatus = 'inbox' | 'todo' | 'doing' | 'done' | 'rejected';
3:export type TaskDueDatePreset = 'today' | 'none';
4:export type TaskListSortMode = 'dueDate' | 'priority' | 'manual';
5:export type TaskViewPreference = 'inbox' | 'list' | 'calendar' | 'review';
6:export type TaskReviewScope = 'work' | 'personal';
7:export type TaskScopeMode = 'COLLAB_SHARED' | 'PERSONAL_ONLY';
8:export type ReviewCompletionStatus = 'done_on_time' | 'done_late' | 'in_progress' | 'not_done';
9:export type ReviewAlignmentStatus = 'aligned' | 'partial' | 'misaligned' | 'unknown';
10:export type ReviewLightweightTag = '' | '资料不足' | '等待他人' | '方向不清' | '资源不够' | '工作过度饱和';
11:export type AgentDepartmentKey = 'strategy_design' | 'tech_development' | 'info_data';
12:export type AgentPlanStatus = 'planned' | 'doing' | 'done' | 'blocked';
13:export type TopicTaskOwnerMode = 'self' | 'empty';
14:export type TopicCandidateStatus = 'candidate' | 'tracking' | 'promoted' | 'archived';
15:export type TopicCandidateInsightStatus = 'pending' | 'ready' | 'failed';
16:export type MeetingStage = 'prepared' | 'ingested' | 'extracted' | 'resolved' | 'published';
17:export type AiProvider = 'mock' | 'openai_compatible' | 'qwen' | 'doubao';
18:export type AiModelMode = 'auto' | 'online_first' | 'local_first' | 'local_only';
19:export type AiModelProfileKey = 'online_primary' | 'local_text_deep' | 'local_vision_ocr' | 'local_fast';
20:export type AiModelCapability = 'online_primary' | 'deep_analysis' | 'vision_ocr' | 'fast_structured';
21:export type AccountStatus = 'pending' | 'approved' | 'rejected' | 'disabled';
22:export type MembershipStatus = 'none' | 'pending' | 'approved' | 'rejected';
23:export type EmployeeRole = 'admin' | 'employee';
24:export type CollaboratorInboxStatus = 'pending' | 'accepted' | 'returned';
25:export type OrgRoleLevel = 'employee' | 'supervisor' | 'department_lead' | 'organization_lead';
26:export type OrgReportingLineType = 'business' | 'administrative';
27:export type OrgTaskEditScope = 'self' | 'manager' | 'department' | 'organization';
28:export type OrgTaskControlLevel = 'normal' | 'leader_control' | 'department_control' | 'organization_control';
29:export type OrgRuleActorScope = 'assignee' | 'manager' | 'department_lead' | 'organization_lead' | 'creator';
30:export type OrgWorkflowTriggerType = 'weekly_followup' | 'task_created' | 'meeting_closed' | 'client_update' | 'manual';
31:export type OrgFocusPriority = 'high' | 'medium' | 'low';
32:export type OrgFocusStatus = 'draft' | 'active' | 'paused' | 'done';
33:export type OrgDepartmentPlanStatus = 'draft' | 'active' | 'closed';
34:export type OrgDepartmentPlanItemStatus = 'active' | 'paused' | 'done' | 'dropped';
35:export type TaskPlanLinkSource = 'ai' | 'manager' | 'rule';
36:export type SupportRequestTargetScope = 'manager' | 'department' | 'organization' | 'cross_department';
37:export type SupportRequestType = 'resource' | 'decision' | 'collaboration' | 'workload' | 'clarification';
38:export type SupportRequestStatus = 'open' | 'accepted' | 'resolved' | 'dismissed';
39:export type DnaSourceLevel = 'organization' | 'client';
40:export type OrganizationDnaModuleKey = 'organization_intro' | 'business_intro' | 'team_intro' | 'market_intro';
41:export type FeishuReceiveIdType = 'open_id' | 'user_id' | 'email' | 'chat_id';
42:export type GrowthAbilityKey = 'exec' | 'collab' | 'analyze' | 'insight' | 'risk' | 'write';
43:export type GrowthEvidenceType = 'reflection' | 'codification' | 'reuse' | 'improvement';
44:export type GrowthConfidence = 'high' | 'medium' | 'low';
45:export type LearningContentType = 'method_card' | 'practice_card' | 'correction_card';
46:export type LearningRecommendationStatus = 'active' | 'accepted' | 'dismissed';
47:export type GrowthContributionTag = 'knowledge_asset' | 'critical_resolution' | 'collaboration_enablement' | 'risk_alignment' | 'mechanism_building';
48:export type GrowthValidationState = 'candidate' | 'observed' | 'validated' | 'institutionalized';
49:export type GrowthPendingCaptureState = 'open' | 'dismissed' | 'reviewed' | 'promoted';
50:export type BadgeState = 'locked' | 'progress' | 'ready' | 'lit' | 'mastered';
51:export type AnalysisScopeType = 'client' | 'event_line' | 'meeting' | 'task' | 'module' | 'flow';
52:export type AnalysisJobType = 'asset_ingest' | 'evidence_extract' | 'customer_compare' | 'meeting_enhance' | 'dna_refresh' | 'strategy_pack';
53:export type AnalysisJobStatus =
66:export type AnalysisReviewState = 'draft' | 'awaiting_review' | 'awaiting_revision' | 'approved' | 'rejected' | 'superseded';
67:export type AnalysisStageStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped';
68:export type AnalysisOriginType = 'projection' | 'analysis' | 'human_override';
69:export type AnalysisAuthorityLevel = 'fallback' | 'candidate' | 'approved';
70:export type AnalysisQualityTier = 'legacy' | 'normalized' | 'reviewed';
71:export type AnalysisIntentProfile = 'task_ai' | 'weekly_review' | 'meeting_enhance' | 'client_overview' | 'strategic_cockpit' | 'dna_summary';
72:export type AnalysisStaleReason =
79:export type AnalysisRejectedReason =
86:export type ApprovalDecision = 'approved' | 'rejected' | 'returned_for_revision';
87:export type ApprovalTargetType = 'judgment_version' | 'dna_delta' | 'conflict_group' | 'proposal_record';
88:export type AnalysisLane = 'light_extractor' | 'local_deep' | 'cloud_final';
151:export type ConsultationKnowledgeTarget = 'vector_memory' | 'document_archive';
152:export type ConsultationKnowledgeRequestStatus = 'pending' | 'processing' | 'completed' | 'failed';
266:export type OrgQuarterKey = 'Q1' | 'Q2' | 'Q3' | 'Q4';
621:export type DocumentAutoRepairHealthStatus =
631:export type DocumentAutoRepairStage =
928:export type LinkMaterialPlatform = 'bilibili' | 'xiaohongshu';
929:export type LinkMaterialImportStatus = 'queued' | 'running' | 'completed' | 'failed';
930:export type LinkMaterialMediaCacheStatus = 'not_downloaded' | 'cleaned' | 'retained' | 'failed';
931:export type LinkMaterialCookieBrowser = 'firefox' | 'chrome' | 'edge' | 'safari';
1009:export type JudgmentQueryMode = 'registry_only' | 'hybrid' | 'evidence_based_synthesis';
1011:export type EvidenceSupportMode =
1018:export type WorkspaceAnswerIntent =
1030:export type RetrievalDecisionReason =
1046:export type PageContextPage =
1059:export type PageIntentType =
1074:export type AnswerLevel = 'official' | 'candidate' | 'evidence_based' | 'fallback' | 'insufficient';
1075:export type ContextQualityLevel = 'none' | 'weak' | 'usable' | 'strong';
1102:export type RouteMode =
1134:export type RetrievalMode = 'state_only' | 'raw_only' | 'hybrid' | 'deferred';
1957:export type WorkspaceDataCenterReadinessActionType =
2192:export type FallbackPresentationMode = 'state_cards_only' | 'compact_user_answer' | 'full_answer';
2454:export type TaskAttachmentRecord = TaskAttachment;
2492:export type EventLineKind = 'project_line' | 'issue_line' | 'coordination_line' | 'case_line' | 'custom';
2493:export type EventLineStatus = 'active' | 'blocked' | 'paused' | 'done' | 'archived';
2494:export type EventLineVisibilityScope = 'private' | 'project_public';
2641:export type ExecutionTicketResultType = 'recorded_only' | 'prep_artifact_ready' | 'followup_task_created' | 'failed';
2736:export type KernelPrimaryRolloutStage = 'stage_1_client' | 'stage_3_clients' | 'stage_10_clients';
2737:export type KernelPrimaryRolloutStatus = 'planned' | 'running' | 'completed' | 'rolled_back' | 'failed';
2888:export type EventLineTimelineNodeKind =
2897:export type EventLineTimelineNodeWarning = string;
2930:export type EventLineAttachmentDisplayMode = 'expanded' | 'collapsed';
2948:export type EventLineApprovalStatus = 'pending' | 'approved' | 'rejected';
3500:export type WeeklyEventReviewCardKind = 'event_line' | 'task_cluster' | 'single_task' | 'needs_assignment';
3720:export type ReviewPerspectiveKey = 'organization' | 'department' | 'mine';
3759:export type UnderstandingMode = 'basic' | 'enhanced';
3791:export type CooperationType = 'strategic_companion' | 'single_project' | 'exploring' | 'dormant';
3792:export type RelationshipHealth = 'thriving' | 'steady' | 'cooling' | 'at_risk';
3863:export type StrategicJudgmentStatus = 'system_draft' | 'confirmed' | 'waiting';
3864:export type StrategicHealthStatus = 'healthy' | 'watch' | 'risk' | 'uncalibrated';
3865:export type StrategicLineMomentum = '加码' | '稳住' | '收口' | '暂停';
3866:export type StrategicItemPriority = 'high' | 'medium' | 'low';
4012:export type StrategicThoughtScope = 'client' | 'project' | 'system';
4013:export type StrategicThoughtStatus = 'draft' | 'confirmed' | 'dismissed' | 'task_created' | 'waiting_evidence';
4014:export type StrategicThoughtConfidenceLevel = 'low' | 'medium' | 'high' | 'none';
4015:export type StrategicInsightType =
4023:export type StrategicThoughtSourceType =
6316:export type DiagnosisScene = 'fundraising' | 'pr' | 'project';
6317:export type DiagnosisAudienceType = 'donor' | 'media' | 'public' | 'key_person' | 'beneficiary' | 'partner';
6318:export type DiagnosisEngineMode = 'fast' | 'standard' | 'deep';
6410:export type CollabChangeGroupKey =
6419:export type CollabFileChangeType = 'modified' | 'added' | 'deleted' | 'renamed' | 'untracked';
6421:export type CollabConflictRiskKind = 'overlap' | 'unmerged' | 'binary' | 'rename' | 'delete_replace';
6444:export type CollabEffectVisibility = 'visible' | 'mixed' | 'background';
```

### export const 清单（常量）
```
```
