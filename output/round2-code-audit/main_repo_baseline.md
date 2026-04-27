# Main Repo Baseline

- Repo: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench
- Branch: main
- HEAD: 7061440
- Dirty tracked/untracked/nested/deleted: 37/7/1/0
- Known missing files: runtimeManifest.ts=true, mainChainPresentation.ts=true, embedding_provider.py=true

## Build/Test Entry Points

- Desktop main build: `npm run build:main`
- Desktop renderer build: `npm run build:renderer`
- Backend minimal pytest: `uv run --project backend python -m pytest backend/tests/test_knowledge_v2.py -q`
- Cloud minimal pytest: `uv run --project cloud_backend python -m pytest cloud_backend/tests/test_auth_tasks.py cloud_backend/tests/test_simulation_seed.py -q`

## Audit Hooks Present

- Package-referenced scripts: scripts/ensure-mac-release-prereqs.mjs, scripts/generate-mac-icon.py, scripts/install-mac-app.mjs, scripts/open-installed-app.mjs, scripts/run-local-electron.mjs, scripts/stabilize-mac-app.mjs, scripts/verify-packaged-app.mjs, scripts/write-version-manifest.mjs
- Runtime UI proof remains blocked until source build is fixed.

