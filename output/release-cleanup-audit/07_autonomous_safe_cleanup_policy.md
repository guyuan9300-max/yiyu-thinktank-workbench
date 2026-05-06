# 07 Autonomous Safe Cleanup Policy

Generated: 2026-05-06T20:19:00+08:00

## Decision

The user should not need to confirm low-level technical reachability. Cleanup will use a conservative autonomous policy:

- Automatically handle only release packaging exclusions and disposable generated files.
- Do not automatically delete product code, API code, scripts, database files, docs, or mobile code.
- Anything that needs product judgment remains `needs_product_review`.

## Autonomous Confirmation Rule

An item is autonomous-safe only if all of these are true:

1. It is not tracked source code.
2. It is not a database, env file, document, source file, script entrypoint, or installed app data.
3. It can be recreated by normal builds/tests/tool runs.
4. It is already ignored by Git or blocked by package verification.

If any one condition fails, the item is not deleted autonomously.

## Safe Classes

These can be handled without product confirmation:

- `.DS_Store`
- `.pytest_cache/`
- `__pycache__/`
- `*.pyc`
- `*.pyo`
- `*.tsbuildinfo`
- generated Playwright CLI snapshots under `.playwright-cli/`
- package-only exclusions already covered by `electron-builder` and `verify-packaged-app`

For physical cleanup, use Trash/recoverable deletion rather than permanent removal.

## Package-Only Classes

These should be excluded from DMG/source release bundles but not deleted automatically:

- `*.db`, `*.sqlite`, `*.sqlite3`, `*-wal`, `*-shm`
- `.env`, `.env.*`
- `output/`
- `dist/`
- local virtual environments such as `.venv/`
- QA logs unless a separate evidence-retention decision says otherwise

## Never Autonomous Delete

These always require a separate small-batch decision:

- frontend components or pages, even if static scan says no direct references
- backend services or FastAPI route helpers
- scripts under `scripts/` or `backend/scripts/`
- `cloud_backend/` runtime code and seed utilities
- `mobile/`
- docs and product descriptions
- current installed app or any path under `~/Library/Application Support`

## Next Safe Batch

The next autonomous cleanup batch should only move disposable ignored files to Trash:

- root and subdirectory `.DS_Store`
- root/backend/cloud `.pytest_cache/`
- root/backend/cloud/scripts `__pycache__/`
- Python bytecode under those cache directories
- `tsconfig.node.tsbuildinfo`
- `.playwright-cli/` generated page snapshots

Do not include databases, env files, output reports, QA logs, source files, or mobile files in that batch.
