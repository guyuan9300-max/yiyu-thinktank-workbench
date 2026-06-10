# Mobile Recording Chain Handoff - 2026-05-08

## Why this handoff exists

The previous mobile thread became unsafe to continue because its Codex session log grew too large:

- Session file: `/Users/guyuanyuan/.codex/sessions/2026/05/07/rollout-2026-05-07T18-04-05-019e01e4-fe32-7270-bded-906038a29086.jsonl`
- Size observed: 336 MB, 10266 JSONL lines.
- Large lines observed: 267 lines above 100 KB, 196 lines above 500 KB, max line about 1.8 MB.
- Context compactions observed: 255 `context_compacted` entries.
- Remote compact failures observed: 54 `Error running remote compact task` / `stream disconnected before completion` pairs.
- Token usage near the end exceeded 53M input tokens cumulatively.

Do not replay that session broadly. Use this handoff and targeted source reads instead.

## Current objective

Finish the mobile recording chain after local recording save:

1. A saved phone recording must remain visible even when local ASR fails.
2. Unbound local recordings must be discoverable and attachable to a task, client, or event line.
3. Task-detail recording must use the local-first recording session path instead of the legacy upload-first path.
4. After attach, text processing should continue when a clean transcript exists; when no transcript exists, the recording should stay in a clear `needs_action` local state.

## Prior validated work

The previous thread reported these mobile changes and checks before it became unusable:

- Recording start/stop was moved toward a guarded native recorder lifecycle to avoid repeated `prepareToRecordAsync` races.
- Local speech recognition failure was no longer treated as a hard terminal failure for standalone recording.
- A local recording-session model exists in `lib/recording-session-core.ts`.
- A local recording-session persistence/sync service exists in `lib/recording-session-service.ts`.
- Core tests reportedly passed: `npm run test:core` with 107 passing tests.
- Android release build reportedly passed and produced `/Users/guyuanyuan/Desktop/yiyu-mobile-voice-task-fix-2026-05-08.apk`.
- ADB install was not verified because no phone was connected at that time.

These checks must be rerun in the current thread after new edits.

## Current code anchors

- `components/RecordNote.tsx`: recording UI. Standalone mode already saves via `saveUnboundRecording`, but task mode still calls `attachRecordedAudioToTask`.
- `lib/recording-session-core.ts`: local recording paths, status model, summary building, ingest payload construction.
- `lib/recording-session-service.ts`: saves local recording sessions, syncs transcript text, currently has `saveTaskRecording` and `saveUnboundRecording`.
- `lib/local-db.ts`: SQLite tables for `recording_sessions` and `recording_segments`, plus target-based listing.
- `components/TaskDetail.tsx`: already displays local task recording sessions through `localDb.listRecordingSessionsForTarget("task", ...)`.
- `lib/record-note-flow-core.ts`: product state model for saved, pending attach, pending sync, needs-action, and complete.

## Worktree boundaries

The root repository and mobile subrepo are already dirty with many unrelated edits. Preserve those edits. For this takeover, keep changes scoped to mobile recording-chain files and this handoff file.

## Remaining implementation work

1. Add a local service/API for listing actionable unbound recordings.
2. Add a retarget/attach helper that can bind an existing local recording session to a task, client, or event line.
3. Switch task-mode recording in `RecordNote.tsx` to `saveTaskRecording`.
4. Surface unbound recordings in a real mobile UI entry so the user can attach an already saved local recording.
5. Add focused core tests for attach/retarget behavior and task-mode local-first behavior where possible.
6. Rerun `npm run test:core`; if it passes, check Android build and install only if a phone is connected.

## Working rule

Treat ASR failure as recoverable local state, not as the end of the workflow. The audio file is the source of truth; transcript sync is an optional continuation step.
