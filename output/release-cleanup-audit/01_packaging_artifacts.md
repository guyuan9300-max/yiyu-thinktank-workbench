# 01 Packaging Artifacts

Generated: 2026-05-06T12:09:27.425Z

## Summary
- Artifact candidates found: 819
- Default action: do not delete; keep local files and exclude generated/local data from release packages.
- Current focus is desktop DMG; mobile artifacts are listed for visibility only.

## High-Risk Local Data and Generated Paths
| Path | Kind | Size | Recommendation | Evidence |
| --- | --- | ---: | --- | --- |
| .DS_Store | macOS metadata | 12 KB | exclude_from_package | local/generated file pattern |
| .playwright-cli | playwright cli artifacts |  | exclude_from_package | generated/local directory |
| .pytest_cache | pytest cache directory |  | exclude_from_package | generated/local directory |
| app.db | local database | 0 B | exclude_from_package | local/generated file pattern |
| backend/.DS_Store | macOS metadata | 6.0 KB | exclude_from_package | local/generated file pattern |
| backend/.pytest_cache | pytest cache directory |  | exclude_from_package | generated/local directory |
| backend/app.db | local database | 0 B | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__ | python cache directory |  | exclude_from_package | generated/local directory |
| backend/app/__pycache__/__init__.cpython-310.pyc | runtime cache file | 159 B | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/__init__.cpython-311.pyc | runtime cache file | 248 B | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/__init__.cpython-312.pyc | runtime cache file | 237 B | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/db.cpython-310.pyc | runtime cache file | 76 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/db.cpython-311.pyc | runtime cache file | 154 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/db.cpython-312.pyc | runtime cache file | 148 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/local_request_guard.cpython-310.pyc | runtime cache file | 1.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/local_request_guard.cpython-311.pyc | runtime cache file | 2.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/local_request_guard.cpython-312.pyc | runtime cache file | 2.5 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/main.cpython-310.pyc | runtime cache file | 742 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/main.cpython-311.pyc | runtime cache file | 2.5 MB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/main.cpython-312.pyc | runtime cache file | 2.1 MB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/models.cpython-310.pyc | runtime cache file | 140 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/models.cpython-311.pyc | runtime cache file | 401 KB | exclude_from_package | local/generated file pattern |
| backend/app/__pycache__/models.cpython-312.pyc | runtime cache file | 331 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__ | python cache directory |  | exclude_from_package | generated/local directory |
| backend/app/services/__pycache__/__init__.cpython-310.pyc | runtime cache file | 147 B | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/__init__.cpython-311.pyc | runtime cache file | 236 B | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/__init__.cpython-312.pyc | runtime cache file | 225 B | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/action_suggestion_service.cpython-311.pyc | runtime cache file | 5.2 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/action_suggestion_service.cpython-312.pyc | runtime cache file | 4.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/agent_worklogs.cpython-310.pyc | runtime cache file | 34 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/agent_worklogs.cpython-311.pyc | runtime cache file | 60 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/agent_worklogs.cpython-312.pyc | runtime cache file | 53 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/ai.cpython-310.pyc | runtime cache file | 109 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/ai.cpython-311.pyc | runtime cache file | 239 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/ai.cpython-312.pyc | runtime cache file | 214 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/analysis_center.cpython-311.pyc | runtime cache file | 172 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/analysis_center.cpython-312.pyc | runtime cache file | 159 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/analysis_context.cpython-311.pyc | runtime cache file | 94 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/analysis_context.cpython-312.pyc | runtime cache file | 80 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/answer_layer.cpython-311.pyc | runtime cache file | 29 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/answer_layer.cpython-312.pyc | runtime cache file | 25 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/badge_engine.cpython-310.pyc | runtime cache file | 47 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/badge_engine.cpython-311.pyc | runtime cache file | 158 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/badge_engine.cpython-312.pyc | runtime cache file | 143 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/client_profile.cpython-310.pyc | runtime cache file | 10 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/client_profile.cpython-311.pyc | runtime cache file | 19 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/client_profile.cpython-312.pyc | runtime cache file | 16 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_access.cpython-311.pyc | runtime cache file | 16 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_access.cpython-312.pyc | runtime cache file | 14 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_artifacts.cpython-311.pyc | runtime cache file | 17 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_artifacts.cpython-312.pyc | runtime cache file | 15 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_ingest.cpython-311.pyc | runtime cache file | 89 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_ingest.cpython-312.pyc | runtime cache file | 79 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_kernel.cpython-311.pyc | runtime cache file | 28 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_kernel.cpython-312.pyc | runtime cache file | 26 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_operational_status.cpython-311.pyc | runtime cache file | 9.0 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_operational_status.cpython-312.pyc | runtime cache file | 7.6 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_prep.cpython-311.pyc | runtime cache file | 20 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_prep.cpython-312.pyc | runtime cache file | 14 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_profiler.cpython-311.pyc | runtime cache file | 2.1 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_profiler.cpython-312.pyc | runtime cache file | 1.7 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_proposal.cpython-311.pyc | runtime cache file | 28 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_proposal.cpython-312.pyc | runtime cache file | 26 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_quality.cpython-311.pyc | runtime cache file | 7.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_quality.cpython-312.pyc | runtime cache file | 6.5 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_rollback_drill.cpython-311.pyc | runtime cache file | 2.2 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_rollback_drill.cpython-312.pyc | runtime cache file | 1.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_schema.cpython-311.pyc | runtime cache file | 8.0 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_schema.cpython-312.pyc | runtime cache file | 7.1 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_search.cpython-311.pyc | runtime cache file | 19 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_search.cpython-312.pyc | runtime cache file | 17 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_shadow.cpython-311.pyc | runtime cache file | 12 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_shadow.cpython-312.pyc | runtime cache file | 11 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_sync.cpython-311.pyc | runtime cache file | 31 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/data_center_sync.cpython-312.pyc | runtime cache file | 26 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/department_catalog.cpython-310.pyc | runtime cache file | 1.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/department_catalog.cpython-311.pyc | runtime cache file | 2.7 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/department_catalog.cpython-312.pyc | runtime cache file | 2.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/diagnosis_engines.cpython-310.pyc | runtime cache file | 11 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/diagnosis_engines.cpython-311.pyc | runtime cache file | 21 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/diagnosis_engines.cpython-312.pyc | runtime cache file | 18 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/digital_asset_center.cpython-311.pyc | runtime cache file | 216 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/digital_asset_center.cpython-312.pyc | runtime cache file | 196 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/digital_asset_narrative.cpython-311.pyc | runtime cache file | 42 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/digital_asset_narrative.cpython-312.pyc | runtime cache file | 35 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/embedding_provider.cpython-311.pyc | runtime cache file | 27 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/embedding_provider.cpython-312.pyc | runtime cache file | 22 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/event_line_timeline.cpython-311.pyc | runtime cache file | 42 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/event_line_timeline.cpython-312.pyc | runtime cache file | 32 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_quality_feedback_snapshot.cpython-311.pyc | runtime cache file | 11 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_quality_feedback_snapshot.cpython-312.pyc | runtime cache file | 8.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_quality_feedback.cpython-311.pyc | runtime cache file | 2.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_quality_feedback.cpython-312.pyc | runtime cache file | 2.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_quality_store.cpython-311.pyc | runtime cache file | 10 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_quality_store.cpython-312.pyc | runtime cache file | 9.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_quality.cpython-311.pyc | runtime cache file | 11 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_quality.cpython-312.pyc | runtime cache file | 9.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_selector.cpython-311.pyc | runtime cache file | 22 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/evidence_selector.cpython-312.pyc | runtime cache file | 20 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/execution_retry_metrics.cpython-311.pyc | runtime cache file | 7.5 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/execution_retry_metrics.cpython-312.pyc | runtime cache file | 6.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/experience_story_engine.cpython-311.pyc | runtime cache file | 44 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/experience_story_engine.cpython-312.pyc | runtime cache file | 38 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/external_evidence.cpython-311.pyc | runtime cache file | 20 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/external_evidence.cpython-312.pyc | runtime cache file | 17 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/feishu_sync.cpython-311.pyc | runtime cache file | 25 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/feishu_sync.cpython-312.pyc | runtime cache file | 23 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/feishu.cpython-310.pyc | runtime cache file | 4.5 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/feishu.cpython-311.pyc | runtime cache file | 8.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/feishu.cpython-312.pyc | runtime cache file | 7.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/generation_runtime_policy.cpython-311.pyc | runtime cache file | 18 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/generation_runtime_policy.cpython-312.pyc | runtime cache file | 16 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/growth_engine.cpython-310.pyc | runtime cache file | 80 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/growth_engine.cpython-311.pyc | runtime cache file | 148 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/growth_engine.cpython-312.pyc | runtime cache file | 136 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/internet_crawler.cpython-311.pyc | runtime cache file | 59 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/internet_crawler.cpython-312.pyc | runtime cache file | 52 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/kernel_primary_rollout.cpython-311.pyc | runtime cache file | 24 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/kernel_primary_rollout.cpython-312.pyc | runtime cache file | 20 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/knowledge_base.cpython-310.pyc | runtime cache file | 103 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/knowledge_base.cpython-311.pyc | runtime cache file | 211 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/knowledge_base.cpython-312.pyc | runtime cache file | 175 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/knowledge_v2.cpython-310.pyc | runtime cache file | 46 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/knowledge_v2.cpython-311.pyc | runtime cache file | 192 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/knowledge_v2.cpython-312.pyc | runtime cache file | 166 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/learning_presets.cpython-311.pyc | runtime cache file | 26 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/learning_presets.cpython-312.pyc | runtime cache file | 24 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/link_material_import.cpython-311.pyc | runtime cache file | 53 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/link_material_import.cpython-312.pyc | runtime cache file | 47 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/local_memory.cpython-311.pyc | runtime cache file | 32 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/local_memory.cpython-312.pyc | runtime cache file | 28 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/local_semantic_router.cpython-311.pyc | runtime cache file | 8.5 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/local_semantic_router.cpython-312.pyc | runtime cache file | 7.7 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/meeting_context.cpython-311.pyc | runtime cache file | 11 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/meeting_context.cpython-312.pyc | runtime cache file | 9.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/meeting_followup.cpython-311.pyc | runtime cache file | 10.0 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/meeting_followup.cpython-312.pyc | runtime cache file | 8.6 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/memory_foundation.cpython-310.pyc | runtime cache file | 49 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/memory_foundation.cpython-311.pyc | runtime cache file | 107 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/memory_foundation.cpython-312.pyc | runtime cache file | 86 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/organization_dna_v2.cpython-311.pyc | runtime cache file | 47 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/organization_dna_v2.cpython-312.pyc | runtime cache file | 40 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/platform_dna.cpython-310.pyc | runtime cache file | 3.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/platform_dna.cpython-311.pyc | runtime cache file | 6.6 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/platform_dna.cpython-312.pyc | runtime cache file | 5.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/proposal_approval.cpython-311.pyc | runtime cache file | 15 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/proposal_approval.cpython-312.pyc | runtime cache file | 12 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/proposal_execution.cpython-311.pyc | runtime cache file | 19 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/proposal_execution.cpython-312.pyc | runtime cache file | 17 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/query_router.cpython-311.pyc | runtime cache file | 17 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/query_router.cpython-312.pyc | runtime cache file | 16 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/question_focus.cpython-311.pyc | runtime cache file | 2.6 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/question_focus.cpython-312.pyc | runtime cache file | 2.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/rerank_provider.cpython-311.pyc | runtime cache file | 9.2 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/rerank_provider.cpython-312.pyc | runtime cache file | 7.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/retrieval_model_settings.cpython-311.pyc | runtime cache file | 7.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/retrieval_model_settings.cpython-312.pyc | runtime cache file | 6.6 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/retrieval_shadow.cpython-311.pyc | runtime cache file | 7.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/retrieval_shadow.cpython-312.pyc | runtime cache file | 6.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_analysis.cpython-310.pyc | runtime cache file | 98 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_analysis.cpython-311.pyc | runtime cache file | 175 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_analysis.cpython-312.pyc | runtime cache file | 144 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_narrative.cpython-310.pyc | runtime cache file | 26 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_narrative.cpython-311.pyc | runtime cache file | 152 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_narrative.cpython-312.pyc | runtime cache file | 131 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_rollup.cpython-310.pyc | runtime cache file | 50 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_rollup.cpython-311.pyc | runtime cache file | 101 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_rollup.cpython-312.pyc | runtime cache file | 83 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_simulation.cpython-310.pyc | runtime cache file | 7.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_simulation.cpython-311.pyc | runtime cache file | 8.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/review_simulation.cpython-312.pyc | runtime cache file | 8.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/secrets.cpython-310.pyc | runtime cache file | 4.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/secrets.cpython-311.pyc | runtime cache file | 7.2 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/secrets.cpython-312.pyc | runtime cache file | 6.5 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/self_heal.cpython-311.pyc | runtime cache file | 45 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/self_heal.cpython-312.pyc | runtime cache file | 39 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/source_integrity.cpython-311.pyc | runtime cache file | 5.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/source_integrity.cpython-312.pyc | runtime cache file | 5.1 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/source_reachability.cpython-311.pyc | runtime cache file | 13 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/source_reachability.cpython-312.pyc | runtime cache file | 9.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/source_semantics.cpython-311.pyc | runtime cache file | 8.9 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/source_semantics.cpython-312.pyc | runtime cache file | 7.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/system_logger.cpython-311.pyc | runtime cache file | 16 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/system_logger.cpython-312.pyc | runtime cache file | 14 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/task_context_brief_engine.cpython-311.pyc | runtime cache file | 34 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/task_context_brief_engine.cpython-312.pyc | runtime cache file | 29 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/template_fill.cpython-310.pyc | runtime cache file | 25 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/template_fill.cpython-311.pyc | runtime cache file | 47 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/template_fill.cpython-312.pyc | runtime cache file | 41 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/topic_capture.cpython-310.pyc | runtime cache file | 19 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/topic_capture.cpython-311.pyc | runtime cache file | 36 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/topic_capture.cpython-312.pyc | runtime cache file | 31 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/topic_data_center.cpython-311.pyc | runtime cache file | 7.4 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/topic_data_center.cpython-312.pyc | runtime cache file | 6.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/topic_source_fetcher.cpython-310.pyc | runtime cache file | 11 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/topic_source_fetcher.cpython-311.pyc | runtime cache file | 21 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/topic_source_fetcher.cpython-312.pyc | runtime cache file | 18 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/understanding_builder.cpython-310.pyc | runtime cache file | 14 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/understanding_builder.cpython-311.pyc | runtime cache file | 25 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/understanding_builder.cpython-312.pyc | runtime cache file | 23 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/version_manifest.cpython-311.pyc | runtime cache file | 3.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/version_manifest.cpython-312.pyc | runtime cache file | 3.2 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/weekly_review_material_pack.cpython-311.pyc | runtime cache file | 54 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/weekly_review_material_pack.cpython-312.pyc | runtime cache file | 45 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_action_perspective.cpython-311.pyc | runtime cache file | 5.8 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_action_perspective.cpython-312.pyc | runtime cache file | 5.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_answer_experience.cpython-311.pyc | runtime cache file | 14 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_answer_experience.cpython-312.pyc | runtime cache file | 12 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_answer_finalizer.cpython-311.pyc | runtime cache file | 7.0 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_answer_finalizer.cpython-312.pyc | runtime cache file | 6.2 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_answer_value_diagnostics.cpython-311.pyc | runtime cache file | 57 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_answer_value_diagnostics.cpython-312.pyc | runtime cache file | 49 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_chat_diagnostics.cpython-311.pyc | runtime cache file | 26 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_chat_diagnostics.cpython-312.pyc | runtime cache file | 22 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_chat_kernel_bridge.cpython-311.pyc | runtime cache file | 1.7 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_chat_kernel_bridge.cpython-312.pyc | runtime cache file | 1.3 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_context_refresh.cpython-311.pyc | runtime cache file | 14 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_context_refresh.cpython-312.pyc | runtime cache file | 12 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_data_center_adapter.cpython-311.pyc | runtime cache file | 83 KB | exclude_from_package | local/generated file pattern |
| backend/app/services/__pycache__/workspace_data_center_adapter.cpython-312.pyc | runtime cache file | 71 KB | exclude_from_package | local/generated file pattern |


Truncated: 599 more rows. See 06_keep_exclude_delete_matrix.csv for selected action rows.

## Safety Notes
- Local databases are not deletion candidates in this phase.
- output/, dist/, cache, and env files should stay out of DMG and source release bundles.
- mobile/ artifacts should be reviewed separately from desktop release cleanup.
