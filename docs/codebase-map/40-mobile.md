# mobile/ 子仓库结构索引（浅）

**注意**：mobile 是 git submodule，自身工作区也 dirty。本索引仅覆盖结构与文件清单，**不深入代码细节**。需要改动时再单独读。

## 顶层

```
-rw-------   1 peaceful-admiring-hopper peaceful-admiring-hopper   6148 Apr  3 15:21 .DS_Store
drwx------   6 peaceful-admiring-hopper peaceful-admiring-hopper    192 Apr  2 12:33 .expo
drwx------  13 peaceful-admiring-hopper peaceful-admiring-hopper    416 Apr  5 10:07 .git
-rw-------   1 peaceful-admiring-hopper peaceful-admiring-hopper    324 Apr 19 01:18 .gitignore
drwx------   3 peaceful-admiring-hopper peaceful-admiring-hopper     96 May  8 09:44 .mobile-core-tests
-rw-------   1 peaceful-admiring-hopper peaceful-admiring-hopper    466 Apr  3 13:10 README.md
drwx------  14 peaceful-admiring-hopper peaceful-admiring-hopper    448 Apr 19 01:55 android
drwx------   6 peaceful-admiring-hopper peaceful-admiring-hopper    192 Apr 19 01:19 app
-rw-------   1 peaceful-admiring-hopper peaceful-admiring-hopper   1901 Mar 30 14:10 app.json
drwx------   9 peaceful-admiring-hopper peaceful-admiring-hopper    288 Mar 31 12:58 assets
drwx------  21 peaceful-admiring-hopper peaceful-admiring-hopper    672 Apr 19 09:18 components
drwx------   5 peaceful-admiring-hopper peaceful-admiring-hopper    160 Apr  2 12:32 dist
drwx------   8 peaceful-admiring-hopper peaceful-admiring-hopper    256 Mar 29 04:12 ios
drwx------  72 peaceful-admiring-hopper peaceful-admiring-hopper   2304 May  8 05:43 lib
drwx------ 413 peaceful-admiring-hopper peaceful-admiring-hopper  13216 Apr 19 09:30 node_modules
-rw-------   1 peaceful-admiring-hopper peaceful-admiring-hopper 337429 Apr 19 09:30 package-lock.json
-rw-------   1 peaceful-admiring-hopper peaceful-admiring-hopper   1859 Apr 19 09:29 package.json
drwx------  15 peaceful-admiring-hopper peaceful-admiring-hopper    480 May  8 08:30 scripts
-rw-------   1 peaceful-admiring-hopper peaceful-admiring-hopper    171 Apr  1 08:32 tsconfig.json
-rw-------   1 peaceful-admiring-hopper peaceful-admiring-hopper   1394 May  8 05:43 tsconfig.tests.json
```

## 关键目录文件清单

### mobile/app/
```
mobile/app/(tabs)/_layout.tsx
mobile/app/(tabs)/calendar.tsx
mobile/app/(tabs)/consult.tsx
mobile/app/(tabs)/profile.tsx
mobile/app/(tabs)/tasks.tsx
mobile/app/_layout.tsx
mobile/app/index.tsx
mobile/app/login.tsx
```

### mobile/components/
```
mobile/components/CreateTask.tsx
mobile/components/DateTimePickerSheet.tsx
mobile/components/EventLineDrawer.tsx
mobile/components/FocusBar.tsx
mobile/components/RecordNote.tsx
mobile/components/SettingsAI.tsx
mobile/components/SettingsAccount.tsx
mobile/components/SettingsCalendar.tsx
mobile/components/SettingsTasks.tsx
mobile/components/SmartInputSheet.tsx
mobile/components/SuperFAB.tsx
mobile/components/TaskDetail.tsx
mobile/components/TaskReviewComposer.tsx
mobile/components/TaskSyncBadge.tsx
mobile/components/UnderstandingCard.tsx
mobile/components/WeekSignalCard.tsx
mobile/components/WorkspaceLiteSheet.tsx
mobile/components/calendar-screen/CalendarDragLayer.tsx
mobile/components/calendar-screen/CalendarHeader.tsx
mobile/components/calendar-screen/CalendarModalCoordinator.tsx
mobile/components/calendar-screen/DayView.tsx
mobile/components/calendar-screen/MonthView.tsx
mobile/components/calendar-screen/WeekView.tsx
mobile/components/tasks-screen/DragCalendarOverlay.tsx
mobile/components/tasks-screen/InboxTaskList.tsx
mobile/components/tasks-screen/ScheduledTaskList.tsx
mobile/components/tasks-screen/SmartInputRecoveryController.tsx
mobile/components/tasks-screen/TaskModalCoordinator.tsx
mobile/components/tasks-screen/TasksFilterBar.tsx
mobile/components/tasks-screen/TasksHeader.tsx
```

### mobile/lib/
```
mobile/lib/account-scope.ts
mobile/lib/android-back.ts
mobile/lib/api.ts
mobile/lib/app-chrome.ts
mobile/lib/audio-recorder-core.ts
mobile/lib/audio-recorder-prepare-guard.ts
mobile/lib/auth-context.tsx
mobile/lib/base-url.ts
mobile/lib/boundary-cards.ts
mobile/lib/cache.ts
mobile/lib/calendar-repository-core.ts
mobile/lib/calendar-repository.ts
mobile/lib/calendar-selectors.ts
mobile/lib/client-intel-core.ts
mobile/lib/client-intel-store.ts
mobile/lib/consult-context-adapter.ts
mobile/lib/consult-context.ts
mobile/lib/consult-response-core.ts
mobile/lib/consult-thread-context.ts
mobile/lib/create-task-association.ts
mobile/lib/create-task-due-date-core.ts
mobile/lib/create-task-resources.ts
mobile/lib/create-task-service.ts
mobile/lib/current-focus-core.ts
mobile/lib/current-focus-store.ts
mobile/lib/date.ts
mobile/lib/dev-log.ts
mobile/lib/event-line-client-transfer.ts
mobile/lib/focus-selectors.ts
mobile/lib/legacy-upload-ops.ts
mobile/lib/legacy-upload-pseudo-op-core.ts
mobile/lib/legacy-upload-runner-core.ts
mobile/lib/legacy-upload-runner.ts
mobile/lib/local-db.ts
mobile/lib/local-ids.ts
mobile/lib/local-speech-recognition-core.ts
mobile/lib/pending-op-policy.ts
mobile/lib/record-note-flow-core.ts
mobile/lib/record-note-service.ts
mobile/lib/recording-session-core.ts
mobile/lib/recording-session-service.ts
mobile/lib/runtime-controller.ts
mobile/lib/runtime-flags.ts
mobile/lib/runtime.ts
mobile/lib/scope-storage-core.ts
mobile/lib/simple-markdown.tsx
mobile/lib/smart-input-queue-core.ts
mobile/lib/smart-input-queue.ts
mobile/lib/smart-input-recovery.ts
mobile/lib/storage.ts
mobile/lib/sync-engine.ts
mobile/lib/sync-errors.ts
mobile/lib/sync-freeze-core.ts
mobile/lib/system-health.ts
mobile/lib/task-board-store-core.ts
mobile/lib/task-board-store.ts
mobile/lib/task-detail-service.ts
mobile/lib/task-query-service.ts
mobile/lib/task-repository.ts
mobile/lib/task-review-service.ts
mobile/lib/task-sync-policy.ts
mobile/lib/task-sync-presentation.ts
mobile/lib/task-time.ts
mobile/lib/task-understanding.ts
mobile/lib/theme.ts
mobile/lib/types.ts
mobile/lib/use-local-speech-recognition.ts
mobile/lib/use-render-count.ts
mobile/lib/week-signal.ts
```

## package.json 摘要
```
{
  "name": "yiyu-mobile",
  "version": "1.0.0",
  "private": true,
  "main": "expo-router/entry",
  "scripts": {
    "start": "expo start",
    "android": "expo run:android",
    "ios": "expo run:ios",
    "web": "expo start --web",
    "test:core": "node scripts/run-mobile-core-tests.mjs",
    "check:no-direct-task-api-writes": "node scripts/check-no-direct-task-api-writes.mjs",
    "inventory:direct-api-usage": "node scripts/list-direct-api-usage.mjs",
    "checkpoint:snapshot": "node scripts/write-checkpoint-snapshot.mjs",
    "scan:stability-android": "bash scripts/run-mobile-stability-scan.sh",
    "verify:rc-android": "bash scripts/run-android-rc-gates.sh"
  },
  "dependencies": {
    "@react-native-async-storage/async-storage": "2.2.0",
    "expo": "55.0.10-canary-20260328-bdc6273",
    "expo-asset": "55.0.11-canary-20260328-bdc6273",
    "expo-audio": "55.0.10-canary-20260328-bdc6273",
    "expo-background-fetch": "55.0.12",
    "expo-blur": "55.0.11-canary-20260328-bdc6273",
    "expo-clipboard": "55.0.10-canary-20260328-bdc6273",
    "expo-constants": "55.0.10-canary-20260328-bdc6273",
    "expo-file-system": "55.0.13-canary-20260328-bdc6273",
    "expo-haptics": "55.0.10-canary-20260328-bdc6273",
    "expo-linking": "55.0.10-canary-20260328-bdc6273",
    "expo-router": "55.0.9-canary-20260328-bdc6273",
    "expo-secure-store": "55.0.10-canary-20260328-bdc6273",
    "expo-speech-recognition": "3.1.2",
    "expo-sqlite": "55.0.13",
    "expo-status-bar": "55.0.5-canary-20260328-bdc6273",
    "expo-task-manager": "55.0.12",
    "lucide-react-native": "1.7.0",
    "react": "19.2.0",
    "react-native": "0.83.4",
    "react-native-safe-area-context": "5.6.2",
    "react-native-screens": "~4.23.0",
    "react-native-svg": "15.15.3"
  },
  "devDependencies": {
    "@types/react": "19.2.14",
    "typescript": "5.9.3"
  }
}
```

## 顶层路由（expo router app/）
```
(tabs)
_layout.tsx
index.tsx
login.tsx
---
_layout.tsx
calendar.tsx
consult.tsx
profile.tsx
tasks.tsx
```

## mobile/lib/api.ts 接口（如存在）

总行数：783
```
27:export const CLOUD_PRIMARY_BASE_URL = process.env.EXPO_PUBLIC_YIYU_CLOUD_API_URL?.trim() || "";
28:export const CLOUD_FALLBACK_BASE_URL = "";
29:export const DEFAULT_BASE_URL =
31:export const DEFAULT_BASE_URL_PLACEHOLDER = "https://your-cloud.example.com";
40:export async function initBaseUrl(): Promise<void> {
56:export function setBaseUrl(url: string): void {
60:export function getBaseUrl(): string {
64:export async function setAndSaveBaseUrl(url: string): Promise<void> {
75:export async function saveTokens(auth: AuthTokenResponse): Promise<void> {
82:export async function clearTokens(): Promise<void> {
187:export async function login(email: string, password: string): Promise<AuthTokenResponse> {
283:export async function fetchHealth(baseUrlOverride?: string): Promise<HealthResponse> {
314:export async function probeMobileBackendContract(
386:export function formatMobileBackendProbeSummary(probe: MobileBackendContractProbe): string {
391:export async function getMe() {
395:export async function updateMe(payload: { fullName?: string; primaryRole?: string }) {
402:export async function getFeishuUserBinding() {
406:export async function startFeishuUserBinding() {
412:export async function clearFeishuUserBinding() {
418:export async function logout(): Promise<void> {
428:export async function fetchTaskBoard(): Promise<TaskBoardResponse> {
433:export async function fetchEventLines(): Promise<EventLineRecord[]> {
437:export async function createEventLine(payload: {
452:export async function updateEventLine(
476:export async function fetchClients(): Promise<ClientSummaryRecord[]> {
480:export async function enqueueConsultationKnowledgeRequest(
489:export async function fetchConsultationKnowledgeRequests(
512:export async function sendConsultationChat(
521:export async function fetchMobileCapabilities(baseUrlOverride?: string): Promise<MobileCapabilityRecord> {
565:export async function createTask(payload: CreateTaskPayload): Promise<TaskRecord> {
574:export async function updateTask(taskId: string, payload: UpdateTaskPayload): Promise<TaskRecord> {
583:export async function deleteTask(taskId: string): Promise<{ ok?: boolean; success?: boolean }> {
591:export async function completeTaskWithReview(taskId: string, reviewNote: string): Promise<TaskRecord> {
617:export async function uploadTaskAttachment(taskId: string, payload: UploadTaskAttachmentPayload): Promise<TaskRecord> {
641:export async function transcribeTaskAttachmentToDocument(
685:export async function ingestMobileRecordingText(
704:export async function generateSmartTaskDraft(
727:export async function fetchTaskLists(): Promise<TaskListRecord[]> {
733:export async function fetchTaskActivities(taskId: string): Promise<TaskActivityRecord[]> {
737:export async function fetchTaskUnderstanding(taskId: string): Promise<TaskUnderstandingRecord> {
741:export async function fetchTaskContextPreview(taskId: string): Promise<TaskContextPreviewRecord> {
745:export async function fetchClientWorkspace(clientId: string): Promise<Record<string, unknown>> {
749:export async function fetchStrategicCockpit(clientId: string): Promise<Record<string, unknown>> {
753:export async function fetchReviews(weekLabel?: string): Promise<Record<string, unknown>> {
770:export async function fetchTaskSettings(): Promise<TaskSettingsRecord> {
774:export async function updateTaskSettings(
```

## submodule 当前状态
```
 M .gitignore
 M android/app/src/main/AndroidManifest.xml
 M app/(tabs)/_layout.tsx
 M app/(tabs)/calendar.tsx
 M app/(tabs)/consult.tsx
 M app/(tabs)/profile.tsx
 M app/(tabs)/tasks.tsx
 M app/_layout.tsx
 M app/login.tsx
 M components/CreateTask.tsx
 D components/DateTimePicker.tsx
 M components/DateTimePickerSheet.tsx
 M components/RecordNote.tsx
 M components/SettingsAccount.tsx
 M components/SettingsTasks.tsx
 M components/SmartInputSheet.tsx
 M components/SuperFAB.tsx
 M components/TaskDetail.tsx
 M components/TaskReviewComposer.tsx
 M lib/api.ts
 M lib/auth-context.tsx
 M lib/cache.ts
 M lib/smart-input-queue.ts
 M lib/storage.ts
 M lib/types.ts
 M package-lock.json
 M package.json
?? components/EventLineDrawer.tsx
?? components/FocusBar.tsx
?? components/TaskSyncBadge.tsx
?? components/UnderstandingCard.tsx
?? components/WeekSignalCard.tsx
?? components/WorkspaceLiteSheet.tsx
?? components/calendar-screen/
?? components/tasks-screen/
?? lib/__tests__/
?? lib/account-scope.ts
?? lib/audio-recorder-core.ts
?? lib/audio-recorder-prepare-guard.ts
?? lib/base-url.ts
```
