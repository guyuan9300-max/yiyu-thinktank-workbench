# Mobile Repo Baseline

- Repo: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/mobile
- Branch: main
- HEAD: bb64401
- Dirty tracked/untracked/nested/deleted: 23/60/0/1

## Build/Test Entry Points

- Direct API inventory: `npm run inventory:direct-api-usage`
- Guardrail: `npm run check:no-direct-task-api-writes`
- Core tests: `npm run test:core`

## Audit Hooks Present

- Package-referenced scripts: scripts/check-no-direct-task-api-writes.mjs, scripts/list-direct-api-usage.mjs, scripts/run-android-rc-gates.sh, scripts/run-mobile-core-tests.mjs, scripts/run-mobile-stability-scan.sh, scripts/write-checkpoint-snapshot.mjs
- Mobile is treated as an independent repo and ledger.

