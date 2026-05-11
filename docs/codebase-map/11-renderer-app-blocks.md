# src/renderer/App.tsx 区块图

文件总行数：**23465** 行（单文件巨石；接手第一关）

## 顶层 import 来源（前 60 条，去掉 from 路径细节）

```
1:import React, { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
2:import { flushSync } from 'react-dom';
3:import {
62:import type {
178:import {
188:import { ClientWorkspaceView } from './components/client_workspace/ClientWorkspaceView';
189:import type {
195:import {
201:import {
212:import {
216:import {
226:import {
231:import { parseDepartmentInviteCode } from '../shared/departmentInvite';
232:import {
425:import { getClientDnaPromptTemplate } from './lib/clientDnaPromptTemplates';
426:import { ClientProjectSetupPage } from './components/client_workspace/ClientProjectSetupPage';
427:import { EventLineClarificationComposer } from './components/tasks/EventLineClarificationComposer';
428:import EventLineReportPanel from './components/tasks/EventLineReportPanel';
429:import type { ReportDraft } from './components/tasks/EventLineReportPanel';
430:import { TaskTemplateEditorModal } from './components/tasks/TaskTemplateEditorModal';
431:import type { TemplateData } from './components/tasks/TaskTemplateEditorModal';
432:import { SystemLogPanel } from './components/settings/SystemLogPanel';
433:import { StrategicBrainView, type ThoughtTaskPayload } from './components/strategic_accompaniment/StrategicBrainView';
434:import { TopicsManagementView } from './components/topics/TopicsManagementView';
435:import { TaskCalendarView } from './components/tasks/TaskCalendarView';
436:import { AgentSimulationCalendarView } from './components/tasks/AgentSimulationCalendarView';
437:import { AgentWeeklyPlanEditor } from './components/tasks/AgentWeeklyPlanEditor';
438:import { TaskOrgContextPanel } from './components/tasks/TaskOrgContextPanel';
439:import { UnderstandingPanel } from './components/tasks/UnderstandingPanel';
440:import { WeeklyReviewStructuredFields, composeReviewNoteFromStructuredFields, createEmptyReviewStructuredNote, getSimpleReviewText, hasMeaningfulReviewStructuredNote } from './components/tasks/WeeklyReviewStructuredFields';
441:import { reviewStatusLabel, reviewTaskDateLabel, type ReviewTaskRow } from './components/tasks/reviewDraft';
442:import { GrowthProvider, notifyGrowthRefresh } from './components/growth/GrowthContext';
443:import { GrowthCenterView } from './components/handbook/GrowthCenterView';
444:import { AppLogoMark, BrandLogoMark } from './components/settings/BrandLogoSettingsCard';
445:import { DataCenterOpsPanel } from './components/data_center/DataCenterOpsPanel';
446:import { FileSearchResultPanel } from './components/data_center/FileSearchResultPanel';
447:import { WorkStatusPanel } from './components/data_center/WorkStatusPanel';
448:import { FeishuOrgIntegrationPanel } from './components/settings/FeishuOrgIntegrationPanel';
449:import type { OrgModelTab } from './components/settings/OrganizationModelSettingsPanel';
450:import { OrganizationSetupCenter } from './components/settings/OrganizationSetupCenter';
451:import type { OrganizationSetupInputDraftState } from './components/settings/OrganizationSetupCenter';
452:import { isLegacyOrganizationEmployee } from './lib/organizationEmployeeFilters';
453:import { filterSharedTasks, isPersonalOnlyTask } from '../shared/taskVisibility';
454:import {
```

## 顶层 interface / type 声明

（数量多，仅列前 80 条；详细类型见 12-renderer-misc-and-types.md）

```
473:type TemplateFillStage = 'queued' | 'parsing' | 'retrieving' | 'writing' | 'completed' | 'failed';
475:type TemplateFillDialogState = {
500:type FeishuAuthorizationFlowState = {
511:type ImportFeedback = {
518:type ActiveWorkingDocument = {
615:type NavKey = 'tasks' | 'client_workspace' | 'strategic_accompaniment' | 'topics_management' | 'growth_handbook' | 'settings';
616:type TaskViewMode = 'inbox' | 'list' | 'calendar' | 'agent_schedule' | 'review' | 'event_lines';
617:type ClientOverlayMode = 'meeting' | 'goal' | 'dna' | 'paste_document' | 'link_material' | null;
618:type SettingsSectionKey = 'overview' | 'tasks' | 'client_workspace' | 'topics' | 'handbook' | 'system_admin' | 'org_overview' | 'org_departments' | 'org_people' | 'org_rules' | 'system_logs';
619:type ReviewFormState = {
624:type ClientTextDocumentDraft = {
630:type ClientLinkMaterialDraft = {
636:type ReviewTaskGroup = {
651:type WeeklyOverviewLine = {
661:type WeeklyOverviewLineSignals = {
668:type WeeklyOverviewModel = {
676:type ReviewEventCardView = {
693:type GrowthContextJumpRequest = {
727:type EvidenceMode = 'task-ai' | 'cockpit';
763:type InitialNavigationState = {
869:type EventLineClarificationState = EventLineClarificationDraftResult & {
873:type TaskEventLineCreateDraftState = {
883:type CollabDialogState =
922:type TaskEditorState = {
953:type StrategicTaskDraftRequest = {
1032:type AiConfigPresetKey = keyof typeof AI_CONFIG_PRESETS;
1193:type HealthAiSnapshot = HealthResponse['ai'] | null | undefined;
1668:type AnswerBlock =
2433:type GlobalBanner = { type: 'success' | 'error' | 'info'; text: string } | null;
3321:type TaskListFilter = 'doing' | 'done' | 'overdue' | 'all';
3322:type TaskParticipationFilter = 'all' | 'personal' | 'collab';
3323:type TaskTimeSort = 'newest' | 'oldest';
3324:type TaskTimeRangeFilter = 'all' | 'last3days' | 'lastMonth' | 'lastHalfYear' | 'custom';
3325:type TaskExecutionGroupKey = 'today' | 'overdue' | 'week' | 'waiting' | 'undated' | 'later' | 'done';
3327:type TaskExecutionGroup = {
4289:type ReviewPerspectiveUserLike = {
5025:type DroppedImportFile = File & { path?: string };
5026:type DroppedTransferEntry = { isDirectory?: boolean };
5027:type DroppedTransferItem = DataTransferItem & {
5140:type ClientEditorDraft = {
5150:type ClientEditorModalCloseReason = 'user_close' | 'cancel' | 'save_success' | 'delete_success';
5152:type ClientEditorModalState = {
5183:type ClientEditorModalProps = {
5393:type TaskPropertyRowProps = {
```

## 顶层 function 声明（最大粒度的代码块边界）

```
535:function normalizeWorkingDocumentStatus(value?: string | null): ActiveWorkingDocument['status'] {
541:function mergeActiveWorkingDocuments(
557:function buildActiveWorkingDocumentsFromImports(importResults: ImportRecord[]) {
581:function readStoredActiveWorkingDocuments(clientId: string) {
600:function writeStoredActiveWorkingDocuments(clientId: string, docs: ActiveWorkingDocument[]) {
717:function parseNavKey(value: string | null): NavKey | null {
722:function parseSettingsSectionKey(value: string | null): SettingsSectionKey | null {
729:function parseEvidenceMode(value: string | null): EvidenceMode | null {
734:function normalizeEvidenceQueryValue(value: string | null): string | null {
739:function evidenceSupportClass(level: EvidenceSupportLevel): string {
745:function evidenceCitationRoleClass(role?: EvidenceCitationRole | string | null): string {
751:function evidenceTagClass(tag: EvidenceBusinessTag): string {
772:function readInitialNavigationState() {
796:function normalizeStartupNavigationState(state: InitialNavigationState): InitialNavigationState {
807:function syncNavigationStateToUrl(activeTab: NavKey, settingsSection: SettingsSectionKey) {
831:function extractTaskEvidenceFields(preview: TaskContextPreview | null, task: Task | null) {
844:function extractCockpitCandidateSummaries(snapshot: StrategicCockpitSnapshot | null) {
864:function readCockpitCandidateJudgmentCount(snapshot: StrategicCockpitSnapshot | null) {
894:function buildEventLineClarificationDraft(
910:function buildTaskEventLineCreateDraft(): TaskEventLineCreateDraftState {
971:function inferPersonalTaskKeywordLabels(title: string, desc: string) {
1049:function normalizeAiBaseUrl(value?: string | null) {
1053:function isLocalAiBaseUrl(value?: string | null) {
1122:function normalizeAiModelProfiles(
1140:function resolveAiConfigPresetKey(draft: {
1159:function aiModelDisplayLabel(provider?: AiProvider | string | null, model?: string | null, providerLabel?: string | null) {
1174:function aiRouteLabel(provider?: AiProvider | string | null, model?: string | null, providerLabel?: string | null) {
1181:function cloudApiHostValue(rawUrl?: string | null) {
1188:function cloudApiUrlFromHost(rawHost?: string | null) {
1195:function isRealAiConfigured(ai: HealthAiSnapshot) {
1204:function getWorkspaceAiUnavailableReason(ai: HealthAiSnapshot) {
1219:function normalizeCollabRepoPathValue(rawPath: string) {
1223:function normalizeInitialCollabRepoPath(storedPath: string | null) {
1503:function normalizeAuthStateForDesktop(state: AuthState | null | undefined): AuthState {
1516:function getEffectiveMembershipStatus(state: AuthState | null | undefined) {
1521:function membershipStatusLabel(status: string | null | undefined) {
1540:function isWorkspaceAnalysisRunPending(run: ClientAnalysisRun | null | undefined): run is ClientAnalysisRun {
1544:function formatElapsedLabel(milliseconds?: number) {
1549:function mergeDisplayMessages(existingMessages: DisplayChatMessage[], incomingMessages: DisplayChatMessage[]) {
1577:function resolveLoadingPhase(summary?: Record<string, unknown> | null) {
1588:function loadingPhaseBounds(summary?: Record<string, unknown> | null) {
1606:function loadingProgressValue(summary: Record<string, unknown> | null | undefined, elapsedMs: number) {
1618:function loadingStageText(summary?: Record<string, unknown> | null, modelLabel = '当前模型') {
1634:function loadingSubText(summary?: Record<string, unknown> | null, modelLabel = '当前模型') {
1646:function loadingPreviewText(summary?: Record<string, unknown> | null) {
1651:function stageLabelForUi(stage?: string | null) {
1658:function renderInlineEmphasis(text: string) {
1675:function parseAnswerBlocks(text: string): AnswerBlock[] {
1767:function AnswerDocument({ text }: { text: string }) {
1830:function WorkTracePanel({
2399:function extractLoadingHits(summary?: Record<string, unknown> | null) {
2403:function readWorkspaceContextLine(item: unknown): string {
2422:function mapWorkspaceContextItems(items: unknown, limit = 3): string[] {
2439:function emitGlobalBanner(nextBanner: GlobalBanner) {
2444:function showGlobalBanner(type: 'success' | 'error' | 'info', text: string) {
2456:function clearGlobalBanner() {
2464:function getGlobalBanner() {
2468:function useGlobalBannerState() {
2497:function deriveLiveFocusQuestions(question: string, analysisFocus: string[]) {
3061:function getTint(hexColor: string) {
3073:function normalizeTaskListName(name: string | null | undefined) {
3077:function taskListDedupeKey(list: TaskList) {
3081:function chooseTaskListDisplayCandidate(current: TaskList, candidate: TaskList) {
3096:function dedupeTaskListsForDisplay(lists: TaskList[]) {
3111:function taskListDisplayName(list: TaskList) {
3115:function taskDefaultDestinationRank(list: TaskList) {
3123:function getTaskDefaultDestinationLists(lists: TaskList[]) {
3134:function taskDefaultDestinationOptionLabel(list: TaskList) {
3141:function resolveTaskSettings(taskSettings: TaskSettings | null, lists: TaskList[]): TaskSettings {
3157:function defaultDueDateFromPreset(preset: TaskSettings['defaultDueDatePreset']) {
3161:function defaultDdlFromPreset(preset: TaskSettings['defaultDueDatePreset']) {
3165:function formatDateOnlyValue(date: Date) {
3169:function splitTaskDueDateTime(value?: string | null) {
3188:function combineTaskDueDateTime(datePart?: string | null, timePart?: string | null) {
3195:function formatTaskDueLabel(value?: string | null) {
3211:function formatTaskDuePickerDateLabel(datePart?: string | null) {
3217:function taskCalendarSpanDays(durationMinutes?: number | null) {
3223:function formatTaskDuePickerSummaryLabel(datePart?: string | null, timePart?: string | null, durationMinutes?: number | null) {
3236:function taskTagPillStyle(tag: TaskTag, emphasized = false): React.CSSProperties {
3244:function sortTasksForListView(tasks: Task[]) {
3263:function isTaskRiskyForFormalView(task: Task) {
3270:function taskMatchesFormalView(
3302:function sortTasksByFormalView(tasks: Task[], view: TaskViewDefinition) {
3373:function resolveOrganizationTaskName(organizationName?: string | null) {
3378:function buildOrganizationTaskAutoReason(organizationName?: string | null) {
3382:function buildOrganizationTaskManualReason(organizationName?: string | null) {
3386:function inferTaskPriority(params: {
3420:function inferTaskClient(params: {
3502:function inferTaskEventLine(params: {
3571:function tokenizeScopeText(value?: string | null, minLength = 2, maxLength = 18) {
3578:function inferTaskProjectModule(params: {
3641:function inferTaskProjectFlow(params: {
3713:function labelTaskClientConfidence(confidence: 'none' | 'low' | 'medium' | 'high' | 'manual') {
3728:function buildTaskProjectPreview(params: {
4063:function parseTaskDateValue(value?: string | null) {
4075:function resolveTaskDueDate(task: Task) {
4079:function startOfCalendarDay(date: Date) {
4083:function isPastCalendarDueDay(dueDate: Date, today = new Date()) {
4087:function isTaskOverdue(task: Task, today = new Date()) {
4091:function resolveTaskTimelineDateTime(task: Task) {
4102:function taskDateForCalendar(task: Task) {
4106:function taskInvolvesUser(task: Task, userId: string | null | undefined) {
4113:function taskIsPrimaryForUser(task: Task, userId: string | null | undefined) {
4118:function taskIsCollaborativeWatchForUser(task: Task, userId: string | null | undefined) {
4124:function taskIsCollaborative(task: Task) {
4136:function taskWaitsForOthers(task: Task, userId: string | null | undefined) {
4142:function taskMatchesParticipationFilter(task: Task, filter: TaskParticipationFilter) {
4148:function isSameCalendarDay(left: Date, right: Date) {
4152:function isTaskDueToday(task: Task, today = new Date()) {
4156:function isTaskDueInCurrentWeekBucket(task: Task, today = new Date(), includeCompletedPastDays = false) {
4161:function taskHasNoEffectiveDueDate(task: Task) {
4165:function getTaskExecutionGroupKey(
4182:function buildExecutionTaskGroups(
4200:function getTaskPrimaryActionLine(task: Task) {
4206:function getTaskStatusLabel(task: Task) {
4214:function getTaskDueState(task: Task) {
4224:function taskCanToggleCompletion(task: Task, userId: string | null | undefined) {
4230:function taskMatchesTimeRange(
4268:function sortTasksByTimeDirection(tasks: Task[], direction: TaskTimeSort) {
4276:function weekLabelForDate(baseDate: Date) {
4285:function currentWeekLabel() {
4295:function resolveDefaultReviewPerspectiveForUser(user?: ReviewPerspectiveUserLike | null): ReviewPerspectiveKey {
4301:function resolveDefaultReviewDepartmentIdForUser(
4309:function weekLabelCN(label: string): string {
4314:function addCalendarDays(baseDate: Date, days: number) {
4320:function weekBounds(weekLabel: string) {
4337:function shiftWeekLabel(weekLabel: string, offsetWeeks: number) {
4343:function reviewWeekMondayLabel(weekLabel: string) {
4349:function taskDateForReview(task: Task) {
4356:function isTaskInReviewWeek(task: Task, weekLabel: string) {
4363:function materializeTaskFromReviewItem(item: WeeklyReviewTaskEntry, existingTask?: Task | null): Task {
4450:function pickSharedReviewStructuredNote(rows: ReviewTaskRow[]) {
4458:function pickUnifiedReviewStructuredNote(rows: ReviewTaskRow[], taskStatus?: Task['status']) {
4474:function hasWrittenReviewContent(structuredNote: WeeklyReviewTaskStructuredNote, note: string) {
4482:function buildReviewGroups(rows: ReviewTaskRow[]): ReviewTaskGroup[] {
4543:function reviewEventCardKindLabel(kind: WeeklyEventReviewCardKind) {
4557:function reviewFoldedTaskCountLabel(taskCount: number, completedCount: number, pendingCount: number) {
4561:function buildReviewEventCardFallbackPrompt(card: WeeklyEventReviewCard, rows: ReviewTaskRow[]) {
4573:function buildReviewEventCardViews(cards: WeeklyEventReviewCards | null | undefined, rows: ReviewTaskRow[]): ReviewEventCardView[] {
4609:function cleanWeeklyOverviewText(value?: string | null) {
4613:function stripWeeklyOverviewEnding(value: string) {
4617:function truncateWeeklyOverviewText(value: string, maxLength = 72) {
4623:function joinWeeklyOverviewItems(items: string[], limit = 3) {
4628:function dedupeWeeklyOverviewLines(items: string[], limit = 4) {
4639:function isUsefulWeeklyOverviewNarrative(value?: string | null) {
4647:function weeklyOverviewGroupKey(row: ReviewTaskRow) {
4660:function weeklyOverviewGroupTitle(row: ReviewTaskRow) {
4673:function buildWeeklyOverviewGroups(rows: ReviewTaskRow[]): Array<{ id: string; title: string; rows: ReviewTaskRow[] }> {
4695:function lineHasOpenLoopText(value: string) {
4699:function formatWeeklyOverviewSentence(value: string) {
4704:function normalizeWeeklyOverviewAction(value: string) {
4711:function inferWeeklyOverviewStage(title: string, rows: ReviewTaskRow[]) {
4748:function buildWeeklyOverviewLineSignals(rows: ReviewTaskRow[]): WeeklyOverviewLineSignals {
4782:function buildWeeklyOverviewProgressText(title: string, rows: ReviewTaskRow[]) {
4825:function hasWeeklyOverviewSignal(rows: ReviewTaskRow[], selector: (row: ReviewTaskRow) => Array<string | null | undefined>) {
4829:function buildWeeklyOverviewNextGoalText(title: string, rows: ReviewTaskRow[], signals: WeeklyOverviewLineSignals) {
4860:function scoreWeeklyOverviewGroup(group: { id: string; rows: ReviewTaskRow[] }) {
4887:function buildWeeklyOverviewModel(rows: ReviewTaskRow[], scope: 'work' | 'personal'): WeeklyOverviewModel {
4931:function buildWeeklyOverviewModelFromBackendCards(cards: WeeklyMainlineCards | null | undefined, fallback: WeeklyOverviewModel): WeeklyOverviewModel {
4960:function isPrivateTask(task: Task) {
4964:function isLocalDraftTaskId(taskId?: string | null) {
4968:function createEmptyReviewForm(weekLabel = currentWeekLabel()): ReviewFormState {
4975:function selectFolderBridge() {
4980:function selectFilesBridge() {
4985:function inferClientTextDocumentTitle(content: string) {
4996:function detectClientLinkMaterialPlatform(value: string): ClientLinkMaterialDraft {
5010:function inferTaskArchiveDocumentTitle(params: {
5031:function hasFileDragData(dataTransfer?: DataTransfer | null) {
5036:function droppedDataContainsDirectory(dataTransfer?: DataTransfer | null) {
5044:function extractDroppedFilePaths(dataTransfer?: DataTransfer | null) {
5063:function extractDroppedFiles(dataTransfer?: DataTransfer | null) {
5083:function normalizeDroppedFsPath(targetPath: string) {
5087:function parentDirectoryOfDroppedPath(targetPath: string) {
5098:function inferDroppedDirectoryPath(paths: string[]) {
5116:function openPathBridge(targetPath: string) {
5121:function revealInFinderBridge(targetPath: string) {
5126:function saveFileAsBridge(sourcePath: string, suggestedName?: string) {
5131:function selectCollabRepoBridge() {
5136:function createUiId(prefix: string) {
5159:function createEmptyClientEditorDraft(): ClientEditorDraft {
5171:function buildClientEditorDraft(client: ClientSummary): ClientEditorDraft {
5192:function ClientEditorModal({
5411:function TaskPropertyRow({ icon, label, children }: TaskPropertyRowProps) {
5423:export default function App() {
```

## 顶层 const 组件 / 工具（col 0 的 `const Xxx = `，按行排序）

```
466:const InternalCollabPreviewDialog = React.lazy(() => import('./components/collab/CollabDialogs').then((module) => ({ default: module.CollabPreviewDialog })));
468:const InternalCollabSyncCard = React.lazy(() => import('./components/collab/CollabSyncCard').then((module) => ({ default: module.CollabSyncCard })));
470:const SHOW_WORKSPACE_CHAT_DIAGNOSTICS = false;
471:const normalizeDepartmentInviteInput = (value: string | null | undefined) => parseDepartmentInviteCode(value || '').trim();
531:const ACTIVE_WORKING_DOCUMENTS_STORAGE_KEY = 'yiyu.workspace.activeWorkingDocuments.v1';
532:const ACTIVE_WORKING_DOCUMENTS_MAX_AGE_MS = 6 * 60 * 60 * 1000;
533:const ACTIVE_WORKING_DOCUMENTS_LIMIT = 6;
698:const NAV_QUERY_TAB_PARAM = 'tab';
699:const NAV_QUERY_SETTINGS_SECTION_PARAM = 'settingsSection';
700:const NAV_QUERY_EVIDENCE_MODE_PARAM = 'evidenceMode';
701:const NAV_QUERY_TASK_ID_PARAM = 'taskId';
702:const NAV_QUERY_CLIENT_ID_PARAM = 'clientId';
703:const NAV_KEYS: NavKey[] = ['tasks', 'client_workspace', 'strategic_accompaniment', 'topics_management', 'growth_handbook', 'settings'];
704:const SETTINGS_SECTION_KEYS: SettingsSectionKey[] = [
961:const TASK_TIME_PRESET_OPTIONS = ['09:00', '10:30', '14:00', '18:00', '20:00'] as const;
962:const TASK_TIME_HOUR_OPTIONS = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, '0'));
963:const TASK_TIME_MINUTE_OPTIONS = Array.from({ length: 12 }, (_, index) => String(index * 5).padStart(2, '0'));
964:const PERSONAL_TASK_KEYWORD_RULES = [
979:const colorPalette = ['#888681', '#5B7BFE', '#10B981', '#F59E0B', '#F43F5E', '#8B5CF6', '#06B6D4'];
980:const AI_CONFIG_PRESETS = {
1033:const AI_CONFIG_PRESET_ORDER: AiConfigPresetKey[] = ['doubao', 'qwen', 'deepseek', 'tencent', 'local', 'custom'];
1035:const providerDefaultModels = {
1042:const providerDisplayNames = {
1066:const AI_MODEL_MODE_OPTIONS: Array<{ value: AiModelMode; label: string; description: string }> = [
1073:const AI_MODEL_PROFILE_ORDER: AiModelProfileKey[] = ['online_primary', 'local_text_deep', 'local_vision_ocr', 'local_fast'];
1074:const AI_LOCAL_MODEL_PROFILE_ORDER: AiModelProfileKey[] = ['local_text_deep', 'local_vision_ocr', 'local_fast'];
1076:const AI_MODEL_PROFILE_DEFAULTS: Record<AiModelProfileKey, AiModelProfileRecord> = {
1115:const AI_MODEL_PROFILE_META: Record<AiModelProfileKey, { title: string; purpose: string }> = {
1179:const CLOUD_API_URL_PREFIX = 'http://';
1212:const COLLAB_REPO_PATH_STORAGE_KEY = 'yiyu-collab-repo-path';
1213:const EVENT_LINE_PROJECT_FILTER_STORAGE_KEY = 'yiyu-event-line-project-filter';
1214:const COLLAB_PRIMARY_REPO_NAME = 'yiyu-thinktank-workbench';
1215:const COLLAB_LEGACY_REPO_NAME = 'yiyu-thinktank-workbench-main-sync';
1216:const COLLAB_VISIBLE_WORKSPACE_SEGMENT = '/openclaw/workspace';
1217:const COLLAB_HIDDEN_WORKSPACE_SEGMENT = '/.openclaw/workspace';
1238:const REQUIRED_BACKEND_FEATURES = [
1248:const DEFAULT_TASK_SETTINGS: TaskSettings = {
1260:const EMPTY_ORG_MODEL_SETTINGS: OrgModelSettings = {
1286:const CLIENT_DNA_MODULES: Array<{ moduleKey: ClientDnaModule['moduleKey']; title: string; helper: string }> = [
1293:const DEFAULT_CLIENT_WORKSPACE_SETTINGS: ClientWorkspaceSettings = {
1302:const DEFAULT_TOPICS_SETTINGS: TopicsSettings = {
1311:const DEFAULT_HANDBOOK_SETTINGS: HandbookSettings = {
1320:const DEFAULT_SYSTEM_ADMIN_SETTINGS: SystemAdminSettings = {
1329:const DEFAULT_MAIN_CHAIN_STABILITY_SETTINGS: MainChainStabilitySettings = {
1341:const DEFAULT_FEISHU_BOT_SETTINGS: FeishuBotSettings = {
1358:const DEFAULT_FEISHU_USER_BINDING: FeishuUserBinding = {
1376:const DEFAULT_ORG_MEMBERSHIP_SUMMARY: OrgMembershipSummary = {
1388:const DEFAULT_ORG_FEISHU_INTEGRATION: OrgFeishuIntegration = {
1407:const DEFAULT_FEISHU_MEMBER_AUTHORIZATION: FeishuMemberAuthorization = {
1428:const DEFAULT_FEISHU_DELIVERY_PROFILE: FeishuDeliveryProfile = {
1443:const DEFAULT_LOCAL_INPUT_MEMORY: LocalInputMemory = {
1462:const DEFAULT_LOCAL_AUTH_STATE: AuthState = {
1477:const EMPTY_PROJECT_STRUCTURE_RESPONSE: ProjectStructureResponse = { modules: [], flows: [] };
1478:const PROJECT_STRUCTURE_FAILURE_CACHE_MS = 5 * 60 * 1000;
1480:const proposalEffectMeta = {
1538:const TASK_COLOR_OPTIONS = ['#5B7BFE', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#64748B', '#EC4899'];
2435:const globalBannerSubscribers = new Set<(banner: GlobalBanner) => void>();
2479:const GlobalBannerHost = React.memo(function GlobalBannerHost() {
2526:const LiveThinkingTrace = React.memo(function LiveThinkingTrace({
2636:const THINKING_HELPER_LINES = [
2642:const ThinkingWorkbenchPanel = React.memo(function ThinkingWorkbenchPanel({
2833:const AnalysisRunCard = React.memo(function AnalysisRunCard({
3025:const Button = ({
3065:const STABLE_TASK_LIST_IDS: Record<string, string> = {
3334:const TASK_EXECUTION_GROUP_META: Record<TaskExecutionGroupKey, Omit<TaskExecutionGroup, 'tasks'>> = {
3344:const TASK_EXECUTION_GROUP_ORDER: TaskExecutionGroupKey[] = ['today', 'overdue', 'week', 'waiting', 'undated', 'later', 'done'];
3345:const TASK_EXECUTION_ALWAYS_VISIBLE_GROUP_KEYS = new Set<TaskExecutionGroupKey>(['week']);
3347:const TASK_LIST_FILTER_OPTIONS: Array<{ value: TaskListFilter; label: string }> = [
3354:const TASK_PARTICIPATION_FILTER_OPTIONS: Array<{ value: TaskParticipationFilter; label: string }> = [
3360:const TASK_TIME_SORT_OPTIONS: Array<{ value: TaskTimeSort; label: string }> = [
3365:const TASK_TIME_RANGE_OPTIONS: Array<{ value: TaskTimeRangeFilter; label: string }> = [
5399:const COMMON_SURNAME_SET = new Set(['王', '张', '李', '赵', '刘', '陈', '杨', '黄', '周', '吴', '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗', '梁', '宋', '郑', '谢', '韩', '唐', '冯', '于', '董', '程']);
5401:const buildNameBadge = (name: string) => {
```

## App() 函数内嵌套子组件（缩进 const 开头的大写组件）

这是 §3 `AuthShell` Bug 的同类风险源——任何在 App() 函数体内 `const Xxx = () =>` 声明且用 `<Xxx />` 渲染的组件，都会在 App 重渲染时被 React 视为新类型而重挂载。

（取前 80 条；行号是声明位置）

```
7556:  const AuthShell = () => {
22162:    const AccountProfileCard = () => {
22224:    const AccountIdentityCard = () => {
22705:    const EmployeeReviewPanel = () => {
22982:  const CockpitEvidenceView = () => {
23131:  const IdentityGate = () => {
```

## renderXxx 系列渲染函数

```
5745:  const renderBranch = loading ? 'loading' : (!authState.authenticated || !currentSessionUser ? 'auth' : shouldShowIdentityGate ? 'identity' : 'main');
7895:  const renderCloudAuthModal = () => {
15702:  const renderClientWorkspaceView = () => {
17830:	    const renderLatestLinkMaterialRunStatus = (variant: 'compact' | 'full' = 'full') => {
21497:	  const renderClientEditorModal = () => {
21534:	  const renderSettingsView = () => {
22301:    const renderOverviewSection = () => {
22587:    const renderTasksSection = () => (
22635:    const renderTopicsSection = () => (
22672:    const renderHandbookSection = () => (
22764:      const renderEmployeeRow = (employee: typeof employeeReviews[number], actions: React.ReactNode) => (
22840:    const renderSystemAdminSection = (initialAdvancedTab: OrgModelTab | null = null) => (
22870:    const renderSectionContent = () => {
```

## handleXxx 事件处理（前 80 条）

```
5221:  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
6097:    const handlePopState = () => {
6562:    const handleFocus = () => { void refreshHealth(); };
6563:    const handleVisibilityChange = () => {
7122:  const handleCloudAuthSubmit = async () => {
7225:    const handleFocus = () => { void refreshDesktopAppInfo().catch(() => undefined); };
7226:    const handleVisibilityChange = () => {
7611:    const handleSubmit = async () => {
9539:    const handleReviewDashboardDrillTarget = async (target: ReviewDashboardCardTarget) => {
9706:    const handleNavigateReviewWeek = async (weekLabel: string) => {
9727:    const handleShiftReviewWeek = (offsetWeeks: number) => {
9746:    const handleSaveEventLineClarification = async () => {
9769:    const handleGenerateEventLineClarification = async () => {
9790:    const handleSaveTaskEventLineClarification = async () => {
9816:    const handleGenerateTaskEventLineClarification = async () => {
9837:    const handleCreateEventLineFromTask = async () => {
9846:    const handleSubmitTaskEventLineCreate = async () => {
9889:    const handleEditEventLineFromTask = () => {
9894:    const handleCloseEventLine = async (targetEventLine: EventLine) => {
9916:    const handleReopenEventLine = async (targetEventLine: EventLine) => {
9930:    const handleDeleteEventLine = async (targetEventLine: EventLine) => {
9952:    const handleDeleteEventLineFromTask = async () => {
9961:    const handleCreateProjectModuleFromTask = () => {
9971:    const handleSaveTemplate = async (data: TemplateData) => {
10036:    const handleCreateProjectFlowFromTask = async () => {
10273:    const handleTaskAttachmentFiles = async (files: File[]) => {
10306:    const handleTaskAttachmentDrop = (event: React.DragEvent<HTMLDivElement>) => {
10317:    const handleTaskAttachmentDragOver = (event: React.DragEvent<HTMLDivElement>) => {
10324:    const handleSaveTask = async () => {
10590:	    const handleDeleteTaskRecord = async (
10691:    const handleTriggerReviewAction = async (action: ReviewActionCard, report: HierarchyReport): Promise<ReviewActionExecutionResult | void> => {
10816:    const handleOpenReviewActionResult = async (
10860:    const handleResolveSupportRequest = async (status: 'accepted' | 'resolved' | 'dismissed') => {
11161:    const handleCalendarShift = (monthDelta: number) => {
11168:    const handleCalendarToday = () => {
11175:    const handleCalendarDateSelect = (date: Date) => {
11181:    const handleTaskCalendarDateSelect = (date: Date) => {
11186:    const handleAlignTaskCalendarDate = (date: Date) => {
11348:    const handleQuickCreateTask = async (title: string, dueDate: string) => {
11377:    const handleRescheduleTask = async (
11456:    const handleUpdateTaskDuration = async (task: Task, durationMinutes: number) => {
11504:    const handleBatchCompleteSelectedTasks = async () => {
11543:    const handleBatchRescheduleSelectedTasks = async () => {
11581:    const handleBatchAssignEventLineSelectedTasks = async () => {
11639:    const handleSaveAgentWeeklyPlan = async (payload: AgentWeeklyPlanPayload) => {
11649:    const handleManualTaskViewModeChange = (mode: TaskViewMode) => {
11660:    const handleApproveTaskReview = async (taskId: string) => {
11673:    const handleReturnTaskReview = async (taskId: string) => {
11692:    const handleCompleteWithReview = async (taskId: string) => {
11711:    const handleConfirmTasks = async (idsToConfirm: string[]) => {
11746:    const handleProposalDecision = async (proposalId: string, action: 'approve' | 'reject' | 'execute') => {
11772:    const handleCreateMeetingProposal = async (kind: 'prepare' | 'followup') => {
11913:    const handleUpdateReviewGroupStatus = async (
17011:    const handlePersistedDraftAction = useCallback(
17309:	    const handleCreateWorkspaceMeetingProposal = async (kind: 'prepare' | 'followup') => {
17386:    const handleRebuildKnowledge = async () => {
17397:    const handleBackfillWorkspaceImports = async () => {
17411:    const handleUploadClientDna = async (moduleKey: ClientDnaModule['moduleKey']) => {
17433:    const handleCopyClientDnaPrompt = async (moduleKey: ClientDnaModule['moduleKey']) => {
17444:    const handleGenerateClientDnaCandidates = async () => {
17455:    const handleCreateProjectModule = async (payload: ProjectModulePayload) => {
17466:    const handleCreateProjectFlow = async (payload: ProjectFlowPayload) => {
17477:    const handleDeleteClientFolder = async (folder: ClientWorkspace['folders'][number]) => {
17495:    const handleRenameClientFolder = async (folder: ClientWorkspace['folders'][number]) => {
17512:    const handlePreviewFolderRecommendation = async () => {
17526:    const handleApplyFolderRecommendation = async () => {
17543:    const handlePreviewDocumentAutoRepair = async () => {
17557:    const handleApplyDocumentAutoRepair = async () => {
17606:    const handleImport = async (mode: 'folder' | 'file', paths: string[], options?: { attachToComposer?: boolean }) => {
17743:    const handleFillTemplate = async () => {
17793:	    const handleClientLinkMaterialUrlChange = (value: string) => {
17800:	    const handleStartClientLinkMaterialImport = async () => {
17942:	    const handleClientTextDocumentContentChange = (value: string) => {
17954:    const handleCreateClientTextDocument = async () => {
17986:    const handleDroppedClientFiles = async (paths: string[], options?: { attachToComposer?: boolean }) => {
18009:    const handleClientImportDragEnter =
18018:    const handleClientImportDragOver =
18029:    const handleClientImportDragLeave =
18040:    const handleClientImportDrop =
18060:    const handleSelectImportFiles = async () => {
```

## activeTab / setActiveTab 切换点

```
811:  if (activeTab === 'tasks') {
818:  if (activeTab === 'settings') {
6099:      setActiveTab(nextState.activeTab);
6684:      setActiveTab('client_workspace');
7306:      setActiveTab(normalizedTab as NavKey);
17274:      setActiveTab('settings');
18619:                  onClick={() => setActiveTab('settings')}
22266:                  setActiveTab('client_workspace');
23103:	          setActiveTab('tasks');
23341:                  onClick={() => setActiveTab(item.id)}
```
