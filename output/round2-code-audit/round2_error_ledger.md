# Round 2 Error Ledger

## P0 / P1 Runtime and Contract Blockers

| Repo | Classification | Path / Symbol | Current Binding | Runtime Status | Test Status | Recommended Action | Blocking Dependency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| main | startup_blocker | src/main/main.ts -> ./runtimeManifest.js | build:main hard dependency | fail: missing runtimeManifest.ts/js import target | fail | restore or rewire runtime manifest module before any runtime UI proof | source build blocked |
| main | startup_blocker | src/renderer/App.tsx -> ../shared/mainChainPresentation | renderer root import | fail: build:renderer unresolved module | fail | restore or rewire shared presentation module before runtime UI audit | source build blocked |
| main | contract_mismatch | backend/app/services/knowledge_base.py -> app.services.embedding_provider | backend test import chain | fail: ModuleNotFoundError during pytest collection | fail | restore module or update imports before backend dead-code conclusions | backend test collection blocked |
| cloud_backend | runtime_divergence | auth/review/task org control flows | cloud API mainline | fail: 6 targeted tests under auth/review/simulation seed | fail | treat current cloud auth/task behavior as unstable; do not infer dead code from failed paths | cloud state diverges from tests |
| mobile | migration_residue | direct API writes in lib/sync-engine.ts, lib/calendar-repository.ts, lib/record-note-service.ts | local-first migration support path | pass guard on task surfaces, but inventory still reports direct writes | mixed | keep as explicit migration ledger; do not delete while local-first boundary is still active | migration not complete |
