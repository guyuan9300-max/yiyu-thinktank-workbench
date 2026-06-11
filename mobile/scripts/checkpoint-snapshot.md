# Checkpoint Snapshot

Generated at: `2026-04-18T12:18:39.499Z`

## Baseline

- Branch: `main`
- Commit: `bb64401746c436ebf5284980ce26882a6ac78d21`
- Schema version: `3`

## Runtime Flags Default

- `task_local_first_write_enabled: true`
- `task_local_first_read_enabled: true`
- `calendar_local_first_write_enabled: true`

## Gate Summary

- `npx tsc --noEmit`: PASS
- `npm run test:core`: PASS
- `npm run check:no-direct-task-api-writes`: PASS
- `npm run inventory:direct-api-usage`: PASS

## Inventory Snapshot

```text
> yiyu-mobile@1.0.0 inventory:direct-api-usage
> node scripts/list-direct-api-usage.mjs

=== direct-task-writes ===
lib/sync-engine.ts:353:            const created = await api.createTask(payload);
lib/sync-engine.ts:365:            const updated = await api.updateTask(remoteTaskId, payload);
lib/sync-engine.ts:382:            const reviewedTask = await api.completeTaskWithReview(remoteTaskId, reviewNote);
lib/sync-engine.ts:392:              await api.deleteTask(remoteTaskId);
lib/calendar-repository.ts:60:  const updatedTask = await api.updateTask(existing.remoteId, payload);
lib/record-note-service.ts:268:    const uploadedTask = await api.uploadTaskAttachment(resolved.remoteTaskId, {
lib/record-note-service.ts:374:    const uploadedTask = await api.uploadTaskAttachment(remote.remoteTaskId, {
=== direct-api-imports ===
app/(tabs)/consult.tsx:21:import { enqueueConsultationKnowledgeRequest, fetchConsultationKnowledgeRequests, sendConsultationChat } from "../../lib/api";
app/(tabs)/consult.tsx:22:import type { ConsultationKnowledgeRequestRecord } from "../../lib/api";
components/SmartInputSheet.tsx:28:import * as api from "../lib/api";
app/(tabs)/profile.tsx:19:import { fetchHealth, updateMe } from "../../lib/api";
app/login.tsx:17:import * as api from "../lib/api";
components/SettingsTasks.tsx:14:import { fetchTaskSettings, updateTaskSettings } from "../lib/api";
components/SettingsAccount.tsx:13:import * as api from "../lib/api";
```

## Git Status

```text
M app/(tabs)/calendar.tsx
 M app/(tabs)/consult.tsx
 M app/(tabs)/profile.tsx
 M app/(tabs)/tasks.tsx
 M app/login.tsx
 M components/CreateTask.tsx
 D components/DateTimePicker.tsx
 M components/DateTimePickerSheet.tsx
 M components/RecordNote.tsx
 M components/SettingsAccount.tsx
 M components/SmartInputSheet.tsx
 M components/TaskDetail.tsx
 M components/TaskReviewComposer.tsx
 M lib/api.ts
 M lib/auth-context.tsx
 M lib/smart-input-queue.ts
 M lib/types.ts
 M package-lock.json
 M package.json
?? components/EventLineDrawer.tsx
?? components/FocusBar.tsx
?? components/UnderstandingCard.tsx
?? components/WeekSignalCard.tsx
?? components/WorkspaceLiteSheet.tsx
?? components/calendar-screen/
?? components/tasks-screen/
?? lib/__tests__/
?? lib/account-scope.ts
?? lib/base-url.ts
?? lib/boundary-cards.ts
?? lib/calendar-repository-core.ts
?? lib/calendar-repository.ts
?? lib/calendar-selectors.ts
?? lib/client-intel-store.ts
?? lib/consult-context-adapter.ts
?? lib/consult-context.ts
?? lib/consult-thread-context.ts
?? lib/create-task-association.ts
?? lib/create-task-resources.ts
?? lib/create-task-service.ts
?? lib/current-focus-core.ts
?? lib/current-focus-store.ts
?? lib/date.ts
?? lib/dev-log.ts
?? lib/event-line-client-transfer.ts
?? lib/focus-selectors.ts
?? lib/legacy-upload-ops.ts
?? lib/legacy-upload-pseudo-op-core.ts
?? lib/local-db.ts
?? lib/local-ids.ts
?? lib/pending-op-policy.ts
?? lib/record-note-flow-core.ts
?? lib/record-note-service.ts
?? lib/runtime-controller.ts
?? lib/runtime-flags.ts
?? lib/runtime.ts
?? lib/smart-input-queue-core.ts
?? lib/smart-input-recovery.ts
?? lib/sync-engine.ts
?? lib/sync-errors.ts
?? lib/sync-freeze-core.ts
?? lib/system-health.ts
?? lib/task-board-store-core.ts
?? lib/task-board-store.ts
?? lib/task-detail-service.ts
?? lib/task-query-service.ts
?? lib/task-repository.ts
?? lib/task-review-service.ts
?? lib/task-sync-policy.ts
?? lib/task-understanding.ts
?? lib/use-render-count.ts
?? lib/week-signal.ts
?? scripts/
?? tsconfig.tests.json
```
