# Round 2 Cleanup Backlog

## P0

- Fix main source build blockers: missing `src/main/runtimeManifest.ts` binding and missing `src/shared/mainChainPresentation.ts` binding.
- Fix backend import chain so minimal pytest can collect: `app.services.embedding_provider` missing from current tree.
- Triage cloud auth/task/review regressions before using cloud runtime failures as evidence for dead-code removal.

## P1

- Re-run runtime UI audit after main source build is restored; promote `blocked_by_runtime_issue` candidates only after runtime proof remains empty.
- Review main repo zero-use API wrappers and unused IPC bridges for safe deletion or consolidation.
- Review mobile direct API write sites as migration-active technical debt, not dead code.

## P2

- Review script_or_ops_only scripts under `scripts/` and `mobile/scripts/` for publish-chain relevance.
- Review compatibility-only backend/cloud endpoints for admin-only or install-only retention rules.

