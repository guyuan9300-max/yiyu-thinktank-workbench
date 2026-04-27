# V2.0 Cleanup Backlog

Recorded at: 2026-04-27 18:06:37 CST

## P0 - keep the tree safe before more feature work

- Commit the root hygiene batch only: `.gitignore`, `.yiyu-sync/settings.system_admin.json`, and `output/worktree-cleanup/` audit files. Do not stage `mobile/` internals from the root repo.
- Keep generated/local files out of future collaboration sync: `.db`, `.sqlite*`, `.env*`, `__pycache__`, `.pyc`, `.playwright-cli/`, `dist/`, `build/`, `tmp/`, test output.
- Treat old round2 error ledger runtime blockers as stale because `npm run build:main` and `npm run build:renderer` now pass; re-run before using any blocker as evidence.

## P1 - clean tracked historical generated files in dedicated commits

- Remove or migrate 45 tracked `.playwright-cli/*.yml` files after confirming no test/tool entry depends on them.
- Remove or replace 4 tracked database files after confirming tests do not require real local DB snapshots: `app.db`, `cloud_backend/app.db`, `cloud_backend/app/dev.db`, `cloud_backend/yiyu_cloud.db`.
- Re-run frontend/API/backend unused-code audit after root tree is clean; only promote candidates with static + entry proof.

## P1 - mobile migration ledger

- Keep current `mobile/` files as `migration_active` until route/import/test proof is generated.
- Resolve direct write inventory intentionally: `lib/sync-engine.ts`, `lib/calendar-repository.ts`, `lib/record-note-service.ts` remain allowed migration/fallback paths until local-first write boundary is finished.
- Split mobile commits by theme: route/screen split, local-first repositories/stores, sync/runtime guards, test harness/scripts.

## P2 - later consolidation

- Review script/ops-only endpoints and scripts after product surfaces are stable.
- Review unused API wrappers, IPC bridges, and backend-only endpoints from the next refreshed audit; do not delete based on stale round2 counts alone.
- Decide whether `.yiyu-sync/settings.system_admin.json` should remain shared config or be split into shared policy + local private branding.
