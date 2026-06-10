# Mobile Stability Verification

This document is the single source of truth for repeated stability scans on the mobile release candidate and the follow-up PRs.

## Scan Loop

Run this order every round:

1. `npx tsc --noEmit`
2. `npm run test:core`
3. `npm run verify:rc-android`
4. `npm run check:no-direct-task-api-writes`
5. Static grep gates
6. Strategy risk review
7. Android real-device blocker checklist
8. Blocker layer assignment
9. After any fix, restart from step 1

Convenience entrypoint:

- `npm run scan:stability-android`

That command runs:

- TypeScript
- core tests
- Android RC gate
- no-direct-task-api-writes guard
- lifecycle ownership grep
- strategy review reminders

It does not replace the manual real-device checklist.

## Hard Gates

These are release-blocking and should be zero-regression gates:

- page-level `fetchTaskBoard` or `loadWithCache(...taskBoard)` residues
- UTC `toISOString().slice(0, 10)` date-key logic
- legacy `DateTimePicker` usage in the main flow

Commands:

```bash
rg "fetchTaskBoard|loadWithCache\\(.*taskBoard" app components lib
rg "toISOString\\(\\)\\.slice\\(0, 10\\)" app components lib
rg "DateTimePicker([^S]|$)" app components lib
```

Expected release behavior:

- `fetchTaskBoard` hits may exist only in lower-level sync or API code, never in page/component taskBoard reads
- UTC date-key hits should be zero
- legacy `DateTimePicker` hits should be zero

## Risk Surfaces To Re-scan

Every round, review these ownership boundaries:

- runtime lifecycle remains idempotent:
  - `initializeRuntime`
  - `startAuthenticatedRuntime`
  - `stopAuthenticatedRuntime`
  - `startSyncEngine`
  - `stopSyncEngine`
- sync registration stays centralized in `lib/sync-engine.ts`
- taskBoard read path stays centralized in `lib/task-board-store.ts`
- task pages do not fork taskBoard state
- local date helpers remain the only source for “today” logic
- smart-input recovery stays event-driven and never reintroduces background polling in the tasks flow
- CreateTask association precedence remains `manual > auto > default`

Targeted review files:

- `lib/runtime.ts`
- `lib/runtime-controller.ts`
- `lib/sync-engine.ts`
- `lib/task-board-store.ts`
- `app/(tabs)/tasks.tsx`
- `app/(tabs)/calendar.tsx`
- `app/(tabs)/consult.tsx`
- `components/CreateTask.tsx`

Lifecycle ownership grep:

```bash
rg "setInterval|useFocusEffect|AppState\\.addEventListener|BackgroundFetch\\.registerTaskAsync|triggerSync\\(" app components lib
```

This grep is review-required, not auto-fail by itself. Use it to confirm the owner is still intentional:

- `lib/sync-engine.ts`: foreground sync timer, AppState listener, BackgroundFetch registration, `triggerSync()` owner
- `lib/task-board-store-core.ts`: unified `triggerSync()` consumer
- `lib/system-health.ts`: explicit diagnostics retry actions only
- `lib/record-note-service.ts`: legacy attachment bind retry only, not recording lifecycle ownership
- `lib/android-back.ts`: Android back navigation helper via `useFocusEffect`
- `components/RecordNote.tsx`: recording duration timer
- `components/SmartInputSheet.tsx`: queued-recording counter refresh only, not task recovery polling
- `components/tasks-screen/SmartInputRecoveryController.tsx`: tasks-page recovery hooks for `tasks_enter`, `app_active`, and manual recovery only
- `app/(tabs)/calendar.tsx`: minute tick for day-view current-time indicator only
- `app/(tabs)/profile.tsx`: explicit `立即同步` button only

If new hits appear outside those boundaries, treat them as blockers until reviewed. If they reintroduce page-level data fetching, polling, or duplicated lifecycle ownership, they are release-blocking.

## Strategy Risk Review

Each round, confirm the gates still cover these release risks:

1. login starts sync exactly once
2. `tasks / calendar / consult` share one taskBoard snapshot
3. pull-to-refresh still routes through unified `refresh()`
4. smart-input recovery does not interrupt the user
5. logout clears local SQLite and avoids cross-account residue
6. offline restart still renders from the local board after one successful sync
7. `calendar` and `tasks` drag flows still behave the same

Blocker layering must stay stable:

- `runtime / baseUrl / sync / local-db / taskBoard store` issues return to foundation first
- `tasks` issues stay in the tasks layer
- `calendar / consult` issues stay in their screen layers
- `CreateTask / picker` issues stay in the create flow layer

Release decision rules must stay stable:

- release behavior is the only go/no-go truth
- debug/dev builds are diagnostic only
- BackgroundFetch is checked only for correct registration and cleanup, not schedule guarantees
- RC release requires two clean results:
  - one full real-device blocker pass
  - one confirmation re-scan

## Android RC Checklist

Use `scripts/android-rc-blocker-checklist.md` for the real-device order. Do not reorder it.

The confirmation re-scan must repeat at least:

- `npm run verify:rc-android`
- the 3 hard grep gates
- login -> sync starts once
- tab switching shows one snapshot
- logout clears local state
- offline restart renders from the local board

## PR Cadence

`PR1 foundation`

- rerun all automated gates after every change
- rerun the full real-device checklist when runtime, sync, or local-db changes

`PR2 store + tasks`

- rerun all automated gates
- rerun at least: quick tab switch, tasks refresh, smart-input recovery, tasks drag-to-calendar

`PR3 calendar + consult`

- rerun all automated gates
- rerun at least: calendar date drag, duration resize, consult context consistency, background/foreground

`PR4 CreateTask / picker / verify`

- rerun all automated gates
- rerun at least: CreateTask association precedence, picker main flow, logout isolation, offline restart

If any PR reopens a hard gate or alters release decision rules, treat it as a blocker immediately. Do not defer it to a later PR.

## Blocker Closure Standard

A blocker is closed only when all of the following are true:

1. reproduced
2. fixed
3. full automated gates rerun
4. affected real-device steps rerun
5. if foundation/store/sync related, one extra full RC re-scan rerun

Record every RC or PR scan in `scripts/mobile-blocker-ledger.md`.
