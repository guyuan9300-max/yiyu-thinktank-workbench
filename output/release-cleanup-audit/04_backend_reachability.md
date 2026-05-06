# 04 Backend Reachability

Generated: 2026-05-06T12:09:27.425Z

## Summary
- Backend/script Python files scanned: 183
- Deleted backend/cloud paths already present in working tree: 4
- Static reachability is conservative; FastAPI route imports and script entrypoints require manual review before deletion.

## Deleted Backend / Cloud Paths Currently in Working Tree
- backend/app/services/department_catalog.py
- backend/app/services/experience_story_engine.py
- backend/tests/test_experience_story_engine.py
- cloud_backend/app/department_catalog.py

## Candidate Services / Scripts
| Path | Ref Count | Sample Referrers | Recommendation | Evidence |
| --- | ---: | --- | --- | --- |
| backend/app/services/review_simulation.py | 9 | backend/app/main.py; backend/tests/test_review_simulation.py | needs_product_review | deprecated/simulation/legacy naming |
| backend/app/services/workspace_action_perspective.py | 0 |  | delete_candidate | no direct basename references in backend/src scan |
| backend/scripts/bettafish_bridge.py | 0 |  | needs_product_review | script entrypoint requires explicit owner review |
| backend/scripts/install_bettafish_source.py | 0 |  | needs_product_review | script entrypoint requires explicit owner review |
| backend/scripts/probe_diagnosis_engines.py | 0 |  | needs_product_review | no direct basename references in backend/src scan |
| cloud_backend/app/simulation_seed.py | 4 | cloud_backend/app/task_pressure_seed.py; cloud_backend/tests/test_simulation_seed.py | needs_product_review | deprecated/simulation/legacy naming |
| cloud_backend/app/task_pressure_seed.py | 1 | cloud_backend/tests/test_task_pressure_seed.py | needs_product_review | deprecated/simulation/legacy naming |
| scripts/audit_growth_badge_scope.py | 0 |  | needs_product_review | script entrypoint requires explicit owner review |
| scripts/cleanup_audit_data.py | 0 |  | needs_product_review | script entrypoint requires explicit owner review |
| scripts/generate-mac-icon.py | 0 |  | needs_product_review | script entrypoint requires explicit owner review |
| scripts/rebucket_workspace_folders.py | 0 |  | needs_product_review | script entrypoint requires explicit owner review |
| scripts/repair_orphan_data_center_ingest.py | 0 |  | needs_product_review | script entrypoint requires explicit owner review |
| scripts/smoke_workspace_chat_async.py | 0 |  | needs_product_review | no direct basename references in backend/src scan |
| scripts/smoke_workspace_chat_generation.py | 1 | scripts/smoke_workspace_chat_async.py | needs_product_review | deprecated/simulation/legacy naming |
| scripts/sync-local-event-lines-to-cloud.py | 0 |  | needs_product_review | script entrypoint requires explicit owner review |

## Interpretation Rules
- delete_candidate still requires a focused import/API/test check before deletion.
- seed/simulation/smoke scripts are usually product-review candidates, not automatic deletes.
- cloud_backend and backend must be cleaned in separate batches because they have different runtime surfaces.
