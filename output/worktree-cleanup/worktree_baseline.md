# V2.0 Worktree Baseline

Recorded at: 2026-04-27 18:06:37 CST

## Main repository

| Field | Value |
| --- | --- |
| Path | `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench` |
| Branch | `main` |
| HEAD | `3a1d25d` |
| origin/main | `3a1d25d` |
| Ahead/behind | `## main...origin/main` |
| Staged paths | 0 |
| Tracked modified paths | 1 |
| Untracked paths | 10 |
| Nested mobile state | ` m mobile` |
| build:main | pass: `npm run build:main` |
| build:renderer | pass: `npm run build:renderer` |

## Mobile repository

| Field | Value |
| --- | --- |
| Path | `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile` |
| Branch | `main` |
| HEAD | `bb64401` |
| origin/main | `bb64401` |
| Ahead/behind | `## main...origin/main` |
| Staged paths | 0 |
| Tracked modified paths | 23 |
| Deleted tracked paths | 1 |
| Untracked paths | 106 |
| Direct task write guard | pass: `npm run check:no-direct-task-api-writes` |
| Core tests | pass: `npm run test:core`, 80 passed |
| Direct API inventory | warning: direct writes still present in sync-engine/calendar-repository/record-note-service |

## Hygiene observations

- Main product source has no tracked source edits besides the intentional `.gitignore` guard update and this audit output.
- `.yiyu-sync/settings.system_admin.json` is    17810 bytes and did not match token/secret/password/API-key keywords during scan; classify as `shared_config`.
- Historical tracked generated files remain in HEAD: 45 Playwright CLI YAML files and 4 database files. `.gitignore` can prevent new ones, but removing tracked ones requires a dedicated cleanup commit.
- `mobile/` is an independent git repository/submodule at mode `160000`; root should not flatten or auto-stage mobile internals.
