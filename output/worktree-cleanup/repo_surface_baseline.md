# Repo Surface Baseline

Recorded at: 2026-04-27 18:06:37 CST

## Desktop renderer surface

| Surface | Current source of truth |
| --- | --- |
| Main tabs | `tasks`, `client_workspace`, `strategic_accompaniment`, `topics_management`, `growth_handbook`, `settings` from `NavKey`. |
| Settings sections | `overview`, `org_dna`, `tasks`, `client_workspace`, `topics`, `handbook`, `system_admin`, `org_overview`, `org_departments`, `org_people`, `org_rules`, `system_logs`. |
| Deep-link/query gates | `tab`, `settingsSection`, `evidenceMode`, `taskId`, `clientId`. |
| View map root | `tasks -> TasksView`, `client_workspace -> ClientWorkspaceView`, `strategic_accompaniment -> StrategicBrainView/CockpitEvidenceView`, `topics_management -> TopicsManagementView`, `growth_handbook -> GrowthCenterView`, `settings -> SettingsView`. |
| API wrapper surface | 326 exported symbols in `src/renderer/lib/api.ts`; unused wrappers require separate evidence before deletion. |
| IPC bridge | preload exposes desktop info, startup gate, file/folder picking, collab sync, rebuild/install, file read/open/reveal/save/watch, quit. |

## Backend and cloud surface

| Surface | Count / role |
| --- | --- |
| Local backend FastAPI routes | 358 route decorators in `backend/app/main.py`; includes system health, auth/local input memory, settings, tasks/event-lines, reviews, data center/customer workspace, proposals/execution, public attachment endpoints. |
| Cloud backend FastAPI routes | 93 route decorators in `cloud_backend/app/main.py`; includes auth/session, org/feishu, mobile capabilities, event lines, tasks, reviews, public attachment endpoints. |
| Runtime status | Main source build currently passes for main and renderer. Old round2 runtime blockers are stale and must not be reused without re-run. |

## Mobile surface

| Surface | Current source of truth |
| --- | --- |
| Expo routes | `app/index.tsx`, `app/login.tsx`, `app/_layout.tsx`, tab layout, `calendar`, `consult`, `profile`, `tasks`. |
| Screen split | New `components/calendar-screen/` and `components/tasks-screen/` directories are migration-active, not orphan by default. |
| Local-first core | New repositories/stores/services under `mobile/lib/` are migration-active; direct write inventory still shows sync/attachment fallback paths. |
| Test guard | `npm run test:core` passed with 80 tests; new `lib/__tests__` files should be preserved until migration completes. |

## Entry criteria for future deletion

A file/symbol may enter `delete_candidate` only when it has no static importer, no route/UI/API/IPC entry, no ops/script entry, no test-guard purpose, and no runtime blocker preventing proof.
