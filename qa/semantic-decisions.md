# Semantic Drift Decisions

## Decision rubric
- `expected_by_product`: 产品明确要求的新语义，代码与测试对齐到新语义。
- `runtime_intentional`: 当前运行时行为是有意设计，但文档/测试尚未同步。
- `unexpected_regression`: 非预期回归，修代码恢复旧契约。
- `unknown_needs_decision`: 暂无裁决，保留在 `known-failures-p2.yaml`。

## Open items

| Test | Current behavior | Proposed owner | Decision | Effective date |
| --- | --- | --- | --- | --- |
| `test_register_approve_login_and_collaboration_flow` | 注册/审批登录门禁与断言不一致 | cloud-product | `unknown_needs_decision` | TBD |
| `test_task_org_link_and_department_control_permissions` | `needsReview` 返回与断言不一致 | cloud-product | `unknown_needs_decision` | TBD |
| `test_task_review_approve_and_return_follow_org_permissions` | 审批链路权限断言偏移 | cloud-product | `unknown_needs_decision` | TBD |
| `test_personal_growth_content_is_self_only_and_excluded_from_team_report` | `teamReport` 缺失 | cloud-product | `unknown_needs_decision` | TBD |
| `test_feishu_binding_relay_session_roundtrip` | 回传页提示组织未完成飞书接入 | cloud-product | `unknown_needs_decision` | TBD |
| `test_seed_simulated_review_org_populates_week_and_visibility` | `currentReview` 返回 `None` | cloud-product | `unknown_needs_decision` | TBD |
| `test_template_fill_start_reuses_existing_active_run_for_same_template` | 模板重复启动不再复用 active run | backend-product | `unknown_needs_decision` | TBD |
| `test_chat_local_fallback_includes_workspace_state_summary` | fallback 文案不再是六段结构 | backend-product | `unknown_needs_decision` | TBD |
| `test_cloud_task_board_builds_event_line_shadow_and_memory_hints` | `backgroundReadiness` 降为 `low` | backend-product | `unknown_needs_decision` | TBD |
| `test_local_mode_feishu_collaboration_requires_cloud_and_org` | `lastValidationMessage` 为空 | backend-product | `unknown_needs_decision` | TBD |
| `test_personal_register_can_upgrade_to_shared_org_and_invite_member` | `/api/v1/account/membership` 404 | cloud-product | `unknown_needs_decision` | TBD |
| `test_import_local_structured_data_creates_lists_tasks_and_tags` | `/api/v1/sync/import-local` 404 | cloud-product | `unknown_needs_decision` | TBD |

## Update protocol
1. 裁决前不批量改断言。  
2. 裁决后同步更新：实现/测试/文档三者。  
3. 每条裁决需记录 owner、依据（需求/设计文档/评审结论）与生效日期。  
