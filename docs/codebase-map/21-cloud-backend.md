# cloud_backend/app 云端后端索引

## 目录结构

```
cloud_backend/app/__init__.py
cloud_backend/app/bootstrap_security.py
cloud_backend/app/db.py
cloud_backend/app/knowledge_store.py
cloud_backend/app/main.py
cloud_backend/app/models.py
cloud_backend/app/security.py
cloud_backend/app/services/__init__.py
cloud_backend/app/services/event_line_timeline.py
cloud_backend/app/simulation_seed.py
cloud_backend/app/smart_input.py
cloud_backend/app/task_pressure_seed.py
cloud_backend/tests/test_auth_refresh.py
cloud_backend/tests/test_auth_register.py
cloud_backend/tests/test_auth_tasks.py
cloud_backend/tests/test_bootstrap_security.py
cloud_backend/tests/test_feishu_notification_service.py
cloud_backend/tests/test_feishu_org_integration.py
cloud_backend/tests/test_feishu_query_service.py
cloud_backend/tests/test_local_first_auth.py
cloud_backend/tests/test_maintenance_mode.py
cloud_backend/tests/test_mobile_consult_contract.py
cloud_backend/tests/test_review_task_time.py
cloud_backend/tests/test_simulation_seed.py
cloud_backend/tests/test_smart_input.py
cloud_backend/tests/test_task_feishu_notifications.py
cloud_backend/tests/test_task_list_repair.py
cloud_backend/tests/test_task_pressure_seed.py
```

## cloud_backend/app/main.py 路由表

总行数：13616

### FastAPI 装饰器
```
8824:    @app.get("/health", response_model=HealthResponse)
8875:    @app.get("/api/v1/auth/department-options", response_model=list[DepartmentOption])
8894:    @app.get("/api/v1/auth/invite-code/resolve", response_model=OrgInviteResolveResult)
8937:    @app.post("/api/v1/auth/register", response_model=AuthTokenResponse)
9051:    @app.post("/api/v1/auth/login", response_model=AuthTokenResponse)
9079:    @app.post("/api/v1/auth/refresh", response_model=AuthTokenResponse)
9121:    @app.get("/api/v1/auth/me", response_model=SessionUser)
9129:    @app.patch("/api/v1/auth/me", response_model=SessionUser)
9179:    @app.post("/api/v1/auth/change-password")
9196:    @app.post("/api/v1/auth/logout")
9209:    @app.get("/api/v1/maintenance-mode/status", response_model=MaintenanceModeStatus)
9215:    @app.post("/api/v1/maintenance-mode/enter", response_model=MaintenanceModeStatus)
9225:    @app.post("/api/v1/maintenance-mode/exit", response_model=MaintenanceModeStatus)
9232:    @app.post("/api/v1/maintenance-mode/audit")
9249:    @app.get("/api/v1/admin/maintenance-mode/members", response_model=list[MaintenanceMemberPermission])
9267:    @app.patch("/api/v1/admin/maintenance-mode/members", response_model=list[MaintenanceMemberPermission])
9321:    @app.get("/api/v1/me/org-membership", response_model=OrgMembershipSummaryRecord)
9327:    @app.post("/api/v1/me/org-membership/apply", response_model=OrgMembershipSummaryRecord)
9413:    @app.get("/api/v1/org-integrations/feishu", response_model=OrgFeishuIntegrationRecord)
9420:    @app.post("/api/v1/org-integrations/feishu/validate-and-save", response_model=OrgFeishuIntegrationRecord)
9527:    @app.get("/api/v1/me/feishu-delivery-profile", response_model=FeishuDeliveryProfileRecord)
9533:    @app.post("/api/v1/me/feishu-delivery-profile", response_model=FeishuDeliveryProfileRecord)
9616:    @app.post("/api/v1/me/feishu-notifications/badge-unlock", response_model=FeishuNotificationDispatchRecord)
9625:    @app.post("/api/v1/integrations/feishu/user-binding/sessions", response_model=FeishuBindingRelaySessionStatusRecord)
9663:    @app.get("/api/v1/integrations/feishu/user-binding/sessions/{state_token}", response_model=FeishuBindingRelaySessionStatusRecord)
9678:    @app.delete("/api/v1/integrations/feishu/user-binding/sessions/{state_token}")
9694:    @app.get("/api/v1/integrations/feishu/member-authorization/callback", response_class=HTMLResponse)
9695:    @app.get("/api/v1/integrations/feishu/user-binding/callback", response_class=HTMLResponse)
9842:    @app.get("/api/v1/admin/employees", response_model=list[EmployeeRecord])
9876:    @app.get("/api/v1/settings/org-ai-config", response_model=OrgAiConfigRecord)
9902:    @app.post("/api/v1/settings/org-ai-config", response_model=OrgAiConfigRecord)
9945:    @app.get("/api/v1/settings/org-ai-config/secret", response_model=OrgAiConfigSecretRecord)
9979:    @app.get("/api/v1/settings/org-model/profile", response_model=OrgModelProfileRecord)
9985:    @app.post("/api/v1/settings/org-model/profile", response_model=OrgModelProfileRecord)
9992:    @app.post("/api/v1/settings/org-model/backfill-task-links", response_model=TaskOrgBackfillResultRecord)
10006:    @app.get("/api/v1/event-lines", response_model=list[EventLineRecord])
10022:    @app.get("/api/v1/clients", response_model=list[ClientSummaryRecord])
10041:    @app.get("/api/v1/mobile/capabilities", response_model=MobileCapabilityRecord)
10047:    @app.get("/api/v1/clients/{client_id}/workspace", response_model=MobileWorkspaceCompatResponse)
10055:    @app.get("/api/v1/clients/{client_id}/strategic-cockpit", response_model=MobileStrategicCockpitCompatResponse)
10063:    @app.post("/api/v1/mobile/knowledge-mirror/publish", response_model=CloudKnowledgeMirrorPublishResultRecord)
10113:    @app.post("/api/v1/event-lines", response_model=EventLineRecord)
10176:    @app.post("/api/v1/event-lines/import-desktop", response_model=EventLineImportResultRecord)
10380:    @app.get("/api/v1/event-lines/{event_line_id}", response_model=EventLineDetailRecord)
10394:    @app.get("/api/v1/event-lines/{event_line_id}/report-snapshot", response_model=EventLineReportSnapshotRecord)
10533:    @app.post("/api/v1/event-lines/{event_line_id}/attachments")
10578:    @app.patch("/api/v1/event-lines/{event_line_id}", response_model=EventLineRecord)
10698:    @app.post("/api/v1/event-lines/{event_line_id}/close")
10745:    @app.post("/api/v1/event-lines/{event_line_id}/reopen")
10761:    @app.delete("/api/v1/event-lines/{event_line_id}")
10788:    @app.get("/api/v1/tasks/{task_id}/plan-link", response_model=TaskPlanLinkRecord | None)
10799:    @app.post("/api/v1/tasks/{task_id}/plan-link/recompute", response_model=TaskPlanLinkRecord | None)
10811:    @app.patch("/api/v1/tasks/{task_id}/plan-link", response_model=TaskPlanLinkRecord | None)
10874:    @app.get("/api/v1/support-requests", response_model=list[SupportRequestRecord])
10899:    @app.post("/api/v1/support-requests", response_model=SupportRequestRecord)
10949:    @app.post("/api/v1/support-requests/{request_id}/resolve", response_model=SupportRequestRecord)
10993:    @app.get("/api/v1/consultation/knowledge-requests", response_model=list[ConsultationKnowledgeRequestRecord])
11026:    @app.post("/api/v1/consultation/knowledge-requests", response_model=ConsultationKnowledgeRequestRecord)
11050:    @app.post("/api/v1/consultation/knowledge-requests/{request_id}/status", response_model=ConsultationKnowledgeRequestRecord)
11099:    @app.post("/api/v1/consultation/chat", response_model=ConsultationChatResponse)
11869:    @app.get("/api/public/smart-input-audio/{file_key}")
11879:    @app.get("/api/public/task-attachments/{attachment_id}")
11892:    @app.get("/api/public/task-attachments/{attachment_id}/thumbnail")
11923:    @app.get("/api/public/task-attachments/{attachment_id}/text-content")
11950:    @app.get("/api/public/task-attachments/{attachment_id}/ocr-summary")
11997:    @app.post("/api/v1/event-lines/{event_line_id}/attachments/download-zip")
12057:    @app.post("/api/v1/mobile/smart-input/task-draft", response_model=SmartTaskDraftResponse)
12133:    @app.get("/api/v1/employees/directory", response_model=list[EmployeeRecord])
12148:    @app.post("/api/v1/admin/employees/{employee_id}/approve", response_model=EmployeeRecord)
12175:    @app.post("/api/v1/admin/employees/{employee_id}/reject", response_model=EmployeeRecord)
12196:    @app.post("/api/v1/admin/employees/{employee_id}/disable", response_model=EmployeeRecord)
12209:    @app.post("/api/v1/admin/employees/{employee_id}/reset-password")
12223:    @app.patch("/api/v1/admin/employees/{employee_id}/role", response_model=EmployeeRecord)
12242:    @app.patch("/api/v1/admin/employees/{employee_id}/department", response_model=EmployeeRecord)
12270:    @app.get("/api/v1/employees/mention-candidates", response_model=list[MentionCandidate])
12324:    @app.get("/api/v1/settings/tasks", response_model=TaskSettingsRecord)
12328:    @app.post("/api/v1/settings/tasks", response_model=TaskSettingsRecord)
12390:    @app.get("/api/v1/task-lists", response_model=TaskListLibraryResponse)
12433:    @app.post("/api/v1/task-lists", response_model=TaskListRecord)
12479:    @app.post("/api/v1/task-lists/repair-duplicates", response_model=TaskListDuplicateRepairResponse)
12487:    @app.patch("/api/v1/task-lists/{list_id}", response_model=TaskListRecord)
12563:    @app.delete("/api/v1/task-lists/{list_id}")
12600:    @app.get("/api/v1/task-tags", response_model=TaskTagLibraryResponse)
12604:    @app.post("/api/v1/task-tags", response_model=TaskTagRecord)
12611:    @app.patch("/api/v1/task-tags/{tag_id}", response_model=TaskTagRecord)
12630:    @app.delete("/api/v1/task-tags/{tag_id}")
12641:    @app.get("/api/v1/tasks", response_model=TaskBoardResponse)
12673:    @app.post("/api/v1/tasks", response_model=TaskRecord)
12833:    @app.patch("/api/v1/tasks/{task_id}", response_model=TaskRecord)
13073:    @app.delete("/api/v1/tasks/{task_id}")
13087:    @app.post("/api/v1/tasks/{task_id}/attachments", response_model=TaskRecord)
13190:    @app.post("/api/v1/tasks/{task_id}/attachments/{attachment_id}/transcribe-to-document", response_model=TaskAttachmentTranscriptionResponse)
13297:    @app.post("/api/v1/tasks/{task_id}/collaborators/{user_id}/accept", response_model=TaskRecord)
13323:    @app.post("/api/v1/tasks/{task_id}/collaborators/{user_id}/return", response_model=TaskRecord)
13343:    @app.post("/api/v1/tasks/{task_id}/complete-with-review", response_model=TaskRecord)
13383:    @app.post("/api/v1/tasks/{task_id}/review/approve", response_model=TaskRecord)
13409:    @app.post("/api/v1/tasks/{task_id}/review/return", response_model=TaskRecord)
13436:    @app.post("/api/v1/tasks/{task_id}/note", response_model=TaskRecord)
13458:    @app.get("/api/v1/tasks/{task_id}/activity", response_model=list[TaskActivityRecord])
13484:    @app.get("/api/v1/reviews/dashboard", response_model=ReviewDashboardResponse)
13491:    @app.get("/api/v1/reviews/history", response_model=ReviewHistoryResponse)
13495:    @app.post("/api/v1/reviews/weekly", response_model=ReviewDashboardResponse)
```

### 顶层 def 函数（前 200 条）
```
183:def now_iso() -> str:
187:def task_has_explicit_time(value: str | None) -> bool:
193:def normalize_task_time_field(value: str | None) -> str | None:
205:def derive_task_temporal_fields(
251:def new_id(prefix: str) -> str:
255:def safe_filename(name: str) -> str:
261:def _is_public_hostname(hostname: str) -> bool:
271:def _resolve_public_base_url(request: Request) -> str | None:
302:def _state(app: FastAPI) -> AppState:
306:def _sql_placeholders(values: list[str] | tuple[str, ...]) -> str:
310:def _row_get(row, key: str, default=None):
319:def _normalize_account_phone(raw_value: str | None) -> str:
336:def _account_membership_status(row) -> Literal["none", "pending", "approved", "rejected"]:
348:def _repair_membership_status_from_account(state: AppState, row):
368:def _organization_has_approved_admin(state: AppState, organization_id: str, *, exclude_user_id: str | None = None) -> bool:
390:def _is_first_organization_account(state: AppState, organization_id: str, user_id: str) -> bool:
404:def _should_bootstrap_organization_owner(state: AppState, organization_id: str | None, user_id: str | None) -> bool:
412:def _ensure_founder_role_bindings(state: AppState, organization_id: str, user_id: str, timestamp: str) -> None:
421:def _ensure_org_profile_owner(state: AppState, organization_id: str, user_id: str, full_name: str, timestamp: str) -> None:
451:def _auto_approve_bootstrap_owner_account(state: AppState, row):
494:def _invite_seed(value: str) -> str:
501:def _base36_seed(value: str, modulo: int) -> str:
515:def _normalize_invite_segment(raw_value: str | None, limit: int, aliases: dict[str, str] | None = None) -> str:
536:def _department_invite_checksum(organization_id: str, department_id: str) -> str:
540:def _department_invite_code(
560:def _department_invite_lookup_values(raw_code: str | None) -> list[str]:
605:def _resolved_invite_from_department_row(row) -> ResolvedDepartmentInvite:
615:def _department_option_from_row(row) -> DepartmentOption:
619:def _list_department_option_rows(state: AppState, organization_id: str):
631:def _get_org_department_option(state: AppState, organization_id: str, department_id: str | None) -> DepartmentOption | None:
645:def _resolve_department_id_globally(
669:def _resolve_department_from_invite(
743:def _create_registration_organization(
770:def _row_user(row) -> SessionUser:
789:def _employee_record(row) -> EmployeeRecord:
816:def _split_lines(value: str | None) -> list[str]:
822:def _bool_value(row, key: str) -> bool:
826:def _normalize_quarter(value: str | None) -> Literal["Q1", "Q2", "Q3", "Q4"]:
833:def _default_quarter_plan(year: str, quarter: Literal["Q1", "Q2", "Q3", "Q4"]) -> OrgQuarterPlanRecord:
847:def _coerce_org_quarter_plans(raw_value, year: str) -> list[OrgQuarterPlanRecord]:
869:def _coerce_department_quarter_plan(raw_value) -> OrgDepartmentQuarterPlanRecord:
884:def _coerce_org_intro_document(raw_value) -> OrgIntroDocumentRecord | None:
903:def _org_intro_document_json(record: OrgIntroDocumentRecord | None) -> str:
911:def _org_profile_record(state: AppState, organization_id: str) -> OrgProfileRecord:
948:def _list_org_departments(state: AppState, organization_id: str) -> list[OrgDepartmentRecord]:
980:def _list_org_roles(state: AppState, organization_id: str) -> list[OrgRoleTemplateRecord]:
1014:def _list_org_bindings(state: AppState, organization_id: str) -> list[OrgEmployeeBindingRecord]:
1043:def _list_org_reporting_lines(state: AppState, organization_id: str) -> list[OrgReportingLineRecord]:
1071:def _list_org_task_control_rules(state: AppState, organization_id: str) -> list[OrgTaskControlRuleRecord]:
1101:def _list_org_role_process_templates(state: AppState, organization_id: str) -> list[OrgRoleProcessTemplateRecord]:
1131:def _list_org_focus_items(state: AppState, organization_id: str) -> list[OrgFocusItemRecord]:
1159:def _list_org_department_plan_items(state: AppState, organization_id: str, plan_id: str) -> list[OrgDepartmentPlanItemRecord]:
1185:def _list_org_department_plans(state: AppState, organization_id: str) -> list[OrgDepartmentPlanRecord]:
1212:def _week_label_for_task_due_date(value: str | None) -> str:
1218:def _matching_fragments(*values: str | None) -> list[str]:
1238:def _score_text_against_fragments(task_text: str, fragments: list[str]) -> float:
1247:def _resolve_focus_item_candidate(state: AppState, organization_id: str, task_text: str):
1268:def _resolve_department_plan_candidate(state: AppState, organization_id: str, department_id: str | None, week_label: str, task_text: str):
1342:def _task_plan_link_row(state: AppState, task_id: str):
1346:def _task_plan_link_record(row) -> TaskPlanLinkRecord:
1357:def _sync_task_plan_link(state: AppState, task_row, org_link_row=None):
1397:def _support_request_record(row) -> SupportRequestRecord:
1414:def _consultation_knowledge_request_record(row) -> ConsultationKnowledgeRequestRecord:
1438:def _consultation_request_row_or_404(state: AppState, request_id: str, organization_id: str):
1462:def _create_consultation_knowledge_request_internal(
1540:def _event_line_row_or_404(state: AppState, event_line_id: str, organization_id: str):
1550:def _event_line_primary_client_id(row) -> str | None:
1557:def _event_line_primary_client_name(row) -> str | None:
1564:def _client_row_by_id(state: AppState, client_id: str | None, organization_id: str | None = None):
1576:def _client_summary_record(row) -> ClientSummaryRecord:
1588:def _normalize_workspace_client_name(value: str | None) -> str:
1592:def _ensure_organization_workspace_client(
1660:def _client_row_or_404(state: AppState, client_id: str, organization_id: str):
1667:def _mirror_latest_row(
1683:def _mirror_rows(
1702:def _mirror_payload(row) -> dict[str, object]:
1709:def _mirror_updated_at(row) -> str | None:
1715:def _mirror_has_any_records(state: AppState, organization_id: str) -> bool:
1725:def _context_source_status(
1742:def _coerce_text(value: object | None, default: str = "") -> str:
1749:def _mobile_summary_item(item: dict[str, object] | None, fallback_title: str) -> MobileWorkspaceCompatItemRecord:
1768:def _mobile_task_item(item: dict[str, object] | None) -> MobileWorkspaceCompatTaskRecord:
1780:def _build_mobile_capabilities(state: AppState, current_user: SessionUser) -> MobileCapabilityRecord:
1792:def _workspace_related_tasks(state: AppState, client_id: str, organization_id: str, limit: int = 6) -> list[MobileWorkspaceCompatTaskRecord]:
1814:def _event_line_summary_items(state: AppState, client_id: str, organization_id: str, limit: int = 4) -> list[MobileWorkspaceCompatItemRecord]:
1837:def _recent_meeting_items_from_mirror(state: AppState, organization_id: str, client_id: str) -> list[MobileWorkspaceCompatItemRecord]:
1854:def _recent_document_items_from_mirror(state: AppState, organization_id: str, client_id: str) -> list[MobileWorkspaceCompatItemRecord]:
1871:def _build_workspace_compat_response(state: AppState, client_row, organization_id: str) -> MobileWorkspaceCompatResponse:
2089:def _build_cockpit_compat_response(state: AppState, client_row, organization_id: str) -> MobileStrategicCockpitCompatResponse:
2260:def _upsert_cloud_mirror_item(
2308:def _event_line_record(state: AppState, row) -> EventLineRecord:
2348:def _event_line_activity_record(state: AppState, row) -> EventLineActivityRecord:
2368:def _record_event_line_activity(
2400:def _first_nonempty_text(*values: object) -> str | None:
2410:def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
2414:def _infer_action_os_business_category(
2443:def _resolve_cloud_task_action_os_fields(
2484:def _event_line_detail_record(state: AppState, row, viewer_id: str | None = None) -> EventLineDetailRecord:
2514:def _event_line_dependency_counts(state: AppState, event_line_id: str, organization_id: str) -> dict[str, int]:
2546:def _get_org_model_profile(state: AppState, organization_id: str) -> OrgModelProfileRecord:
2584:def _org_binding_row_for_user(state: AppState, organization_id: str, user_id: str | None):
2597:def _org_role_row(state: AppState, organization_id: str, role_id: str | None):
2610:def _org_reporting_line_row(state: AppState, organization_id: str, manager_user_id: str, report_user_id: str):
2626:def _normalize_loose_text(value: str | None) -> str:
2632:def _match_manager_user_id(state: AppState, organization_id: str, employee_id: str, manager_name: str | None) -> str | None:
2654:def _match_role_template_for_employee(state: AppState, organization_id: str, account_row, department_id: str | None):
2705:def _sync_employee_org_binding_from_account(
2800:def _backfill_employee_org_bindings_from_accounts(state: AppState, organization_id: str) -> None:
2814:def _first_focus_from_json(value: str | None) -> str | None:
2822:def _resolve_task_control_rule_for_binding(state: AppState, organization_id: str, binding_row):
2854:def _task_collaborator_ids(state: AppState, task_id: str) -> list[str]:
2864:def _sync_task_org_link(state: AppState, task_row, collaborator_ids: list[str] | None = None):
2918:def _task_org_link_row(state: AppState, task_id: str):
2926:def _is_organization_lead(state: AppState, organization_id: str, user_id: str, primary_role: str) -> bool:
2934:def _is_task_manager(state: AppState, organization_id: str, actor_id: str, owner_id: str | None) -> bool:
2943:def _manager_has_capability(state: AppState, organization_id: str, actor_id: str, owner_id: str | None, capability: str) -> bool:
2966:def _matches_rule_actor_scope(state: AppState, actor: SessionUser, task_row, task_link_row, scope: str, capability: str) -> bool:
2994:def _assert_task_edit_permission(
3036:def _can_review_task(state: AppState, actor: SessionUser, task_row, task_link_row) -> bool:
3066:def _ensure_org_model_seed(state: AppState) -> None:
3092:def _ensure_seed_data(state: AppState) -> None:
3252:def _log_audit(state: AppState, action: str, *, actor_user_id: str | None, target_user_id: str | None, detail: dict[str, object]) -> None:
3259:def _save_org_model_profile(state: AppState, current_user: SessionUser, payload: OrgModelProfileRecord) -> OrgModelProfileRecord:
3631:def _get_user_or_404(state: AppState, user_id: str):
3638:def _get_org_user_or_404(state: AppState, organization_id: str, user_id: str):
3648:def _auto_approve_legacy_pending_account(state: AppState, row):
3652:def _require_auth(app: FastAPI, authorization: str | None = Header(default=None)) -> SessionUser:
3671:def _require_admin(app: FastAPI, authorization: str | None = Header(default=None)) -> SessionUser:
3680:def _maintenance_permission_row(state: AppState, organization_id: str, user_id: str):
3691:def _can_enter_maintenance_mode(state: AppState, user: SessionUser) -> bool:
3699:def _can_manage_maintenance_permissions(state: AppState, user: SessionUser) -> bool:
3708:def _maintenance_status_record(state: AppState, user: SessionUser, *, active: bool = False, reason: str | None = None) -> MaintenanceModeStatus:
3721:def _require_maintenance_permission_manager(state: AppState, user: SessionUser) -> None:
3726:def _maintenance_member_record(state: AppState, row) -> MaintenanceMemberPermission:
3739:def _safe_maintenance_audit_detail(detail: dict[str, object]) -> dict[str, object]:
3756:def _render_feishu_relay_callback_page(title: str, detail: str, *, success: bool) -> HTMLResponse:
3787:def _normalize_feishu_custom_callback_url(value: str | None) -> str:
3791:def _is_public_https_feishu_url(url: str | None) -> bool:
3802:def _build_org_feishu_callback_url(request: Request, callback_mode: str, custom_callback_url: str) -> tuple[str, str | None]:
3815:def _feishu_parse_response_json(response) -> dict:
3825:def _raise_for_feishu_api_error(payload: dict, fallback_message: str) -> None:
3833:def _feishu_fetch_app_access_token(*, app_id: str, app_secret: str) -> tuple[str, dict]:
3849:def _feishu_exchange_authorization_code(*, app_access_token: str, app_id: str, app_secret: str, code: str) -> dict:
3874:def _feishu_fetch_user_info(*, user_access_token: str) -> dict:
3890:def _build_feishu_authorize_url(*, app_id: str, redirect_uri: str, state_token: str) -> str:
3897:def _org_feishu_encrypt(state: AppState, plain_text: str, organization_id: str) -> tuple[str, str]:
3910:def _org_feishu_decrypt(state: AppState, encrypted_b64: str, nonce_b64: str, organization_id: str) -> str:
3924:def _org_membership_summary(state: AppState, current_user: SessionUser) -> OrgMembershipSummaryRecord:
3951:def _org_feishu_audit_records(state: AppState, organization_id: str, limit: int = 6) -> list[OrgFeishuIntegrationAuditRecord]:
3978:def _record_org_feishu_audit(
4005:def _org_feishu_integration_record(state: AppState, current_user: SessionUser, request: Request | None = None) -> OrgFeishuIntegrationRecord:
4050:def _normalize_feishu_mobile(raw_value: str | None) -> str:
4057:def _feishu_delivery_status_label(status: str) -> str:
4068:def _feishu_delivery_profile_record(state: AppState, current_user: SessionUser) -> FeishuDeliveryProfileRecord:
4147:def _feishu_fetch_tenant_access_token(*, app_id: str, app_secret: str) -> tuple[str, dict]:
4163:def _feishu_lookup_open_id_by_mobile(*, tenant_access_token: str, mobile: str) -> tuple[str | None, str | None]:
4200:def _resolve_org_feishu_tenant_access_token(
4226:def _feishu_send_text_message(*, tenant_access_token: str, receive_id_type: Literal["open_id"], receive_id: str, text: str) -> dict:
4245:def _feishu_send_interactive_message(*, tenant_access_token: str, receive_id_type: Literal["open_id"], receive_id: str, card: dict) -> dict:
4264:def _feishu_patch_interactive_message(*, tenant_access_token: str, message_id: str, card: dict) -> dict:
4281:def _feishu_message_id_from_payload(payload: dict | None) -> str | None:
4292:def _upsert_org_feishu_delivery_target(
4330:def _resolve_feishu_delivery_target(
4438:def _feishu_extract_text_content(content: str | None) -> str:
4453:def _feishu_text_for_match(value: str | None) -> str:
4457:def _feishu_extract_json_object(raw: str | None) -> dict[str, object] | None:
4479:def _org_ai_decrypt_value(state: AppState, encrypted_b64: str, nonce_b64: str, organization_id: str) -> str:
4492:def _load_feishu_query_model_config(state: AppState, organization_id: str) -> FeishuQueryModelConfig | None:
4522:def _feishu_name_matches(candidate: str | None, target: str | None) -> bool:
4530:def _task_matches_keyword(task: TaskRecord, keyword: str | None) -> bool:
4548:def _task_matches_participant(task: TaskRecord, participant_name: str | None) -> bool:
4557:def _feishu_query_card_template(status: str) -> str:
4567:def _feishu_query_card_title(query_type: str, status: str) -> str:
4596:def _build_feishu_query_progress_card(question: str) -> dict:
4613:def _build_feishu_query_result_card(*, query_type: str, status: str, reply_text: str) -> dict:
4631:def _week_label_for_today() -> str:
4636:def _task_progress_label(value: str | None) -> str:
4646:def _task_time_brief(record: TaskRecord) -> str:
4654:def _task_latest_activity_brief(state: AppState, task_id: str) -> str | None:
4680:def _task_date_span(record: TaskRecord) -> tuple[datetime.date | None, datetime.date | None]:
4686:def _task_intersects_dates(record: TaskRecord, range_start: datetime.date, range_end: datetime.date) -> bool:
4696:def _task_sort_key(record: TaskRecord) -> tuple[datetime, int, str]:
4706:def _match_accounts_by_field(state: AppState, organization_id: str, field_name: str, value: str | None) -> list:
4749:def _feishu_fetch_contact_user_profile(
4800:def _record_feishu_query_log(
5798:def _record_task_feishu_notification(
5832:def _task_datetime_text(value: str | None) -> str:
5850:def _task_person_name_map(state: AppState, user_ids: list[str]) -> dict[str, str]:
5860:def _task_role_label(task_row, recipient_user_id: str) -> str:
5865:def _task_changed_field_labels(changed_fields: list[str]) -> list[str]:
5888:def _task_change_notice_heading(changed_fields: list[str]) -> str:
5894:def _task_priority_label(value: str | None) -> str:
5902:def _task_list_name(state: AppState, list_id: str | None) -> str:
5909:def _build_task_created_feishu_message(
5929:def _build_task_changed_feishu_message(
5974:def _task_datetime_value(value: str | None) -> datetime | None:
5992:def _truncate_plain_text(value: str, limit: int = 48) -> str:
5999:def _extract_non_empty_lines(*values: str, limit: int) -> list[str]:
6011:def _build_feishu_readonly_card(
6051:def _feishu_dispatch_record(row) -> FeishuNotificationDispatchRecord:
```

### import 行（前 60 条）
```
1:from __future__ import annotations
3:import asyncio
4:import hashlib
5:import html
6:import ipaddress
7:import json
8:import logging
9:import mimetypes
10:import os
11:import re
12:import time
13:from dataclasses import dataclass, field
14:from datetime import datetime, timedelta
15:from pathlib import Path
16:from threading import Event, Thread
17:from typing import Literal, cast
18:from urllib.parse import parse_qs, unquote, urlparse
19:from uuid import uuid4
21:from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
22:from fastapi.middleware.cors import CORSMiddleware
23:from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
27:from app.db import Database, from_json, to_json
28:from app.models import (
153:from app.smart_input import build_smart_task_draft, transcribe_audio_with_doubao
154:from app.bootstrap_security import DEFAULT_BOOTSTRAP_ADMIN_EMAIL, ensure_cloud_secret, resolve_seed_users
155:from app.security import create_access_token, decode_access_token, hash_password, verify_password
156:from app.services.event_line_timeline import build_event_line_timeline_nodes
```

## cloud_backend 其他 py 文件清单

```
app/__init__.py                                                   1 lines
app/bootstrap_security.py                                       139 lines
app/db.py                                                      1371 lines
app/knowledge_store.py                                          306 lines
app/models.py                                                  1608 lines
app/security.py                                                  39 lines
app/simulation_seed.py                                          846 lines
app/smart_input.py                                              936 lines
app/task_pressure_seed.py                                       951 lines
app/services/__init__.py                                          1 lines
app/services/event_line_timeline.py                             159 lines
```

## tests 覆盖

```
test_auth_refresh.py                                  46 lines    1 test cases
test_auth_register.py                                265 lines    4 test cases
test_auth_tasks.py                                  1407 lines   19 test cases
test_bootstrap_security.py                            63 lines    2 test cases
test_feishu_notification_service.py                  175 lines    3 test cases
test_feishu_org_integration.py                       121 lines    2 test cases
test_feishu_query_service.py                         539 lines    7 test cases
test_local_first_auth.py                             183 lines    6 test cases
test_maintenance_mode.py                             110 lines    2 test cases
test_mobile_consult_contract.py                      128 lines    3 test cases
test_review_task_time.py                              47 lines    2 test cases
test_simulation_seed.py                              121 lines    1 test cases
test_smart_input.py                                   66 lines    3 test cases
test_task_feishu_notifications.py                    330 lines    4 test cases
test_task_list_repair.py                             137 lines    3 test cases
test_task_pressure_seed.py                           115 lines    2 test cases
```

### 测试用例清单
```
cloud_backend/tests/test_auth_refresh.py:13:def test_refresh_token_rotates_and_restores_session(tmp_path, monkeypatch):
cloud_backend/tests/test_auth_register.py:49:def test_register_returns_tokens_and_allows_immediate_login(tmp_path, monkeypatch):
cloud_backend/tests/test_auth_register.py:110:def test_legacy_pending_account_can_login_without_manual_approval(tmp_path, monkeypatch):
cloud_backend/tests/test_auth_register.py:161:def test_valid_invite_registration_syncs_org_ai_config_and_space_profile(tmp_path, monkeypatch):
cloud_backend/tests/test_auth_register.py:224:def test_existing_cloud_account_apply_valid_invite_unlocks_member_resources(tmp_path, monkeypatch):
cloud_backend/tests/test_auth_tasks.py:111:def test_register_approve_login_and_collaboration_flow():
cloud_backend/tests/test_auth_tasks.py:281:def test_mention_candidates_fill_recent_gap_with_other_approved_employees():
cloud_backend/tests/test_auth_tasks.py:296:def test_collaborator_can_update_task_content_and_owner():
cloud_backend/tests/test_auth_tasks.py:341:def test_event_line_clarification_fields_persist_in_cloud_backend():
cloud_backend/tests/test_auth_tasks.py:387:def test_event_line_report_snapshot_returns_attachment_document_fields_in_cloud():
cloud_backend/tests/test_auth_tasks.py:466:def test_event_line_transfer_syncs_linked_task_client_ids_in_cloud():
cloud_backend/tests/test_auth_tasks.py:554:def test_desktop_event_line_import_preserves_id_and_skips_existing_rows():
cloud_backend/tests/test_auth_tasks.py:621:def test_review_dashboard_works_for_task_with_event_line_context():
cloud_backend/tests/test_auth_tasks.py:701:def test_personal_task_scope_mode_persists_in_cloud_backend():
cloud_backend/tests/test_auth_tasks.py:751:def test_personal_growth_content_is_self_only_and_excluded_from_team_report():
cloud_backend/tests/test_auth_tasks.py:791:def test_feishu_binding_relay_session_roundtrip():
cloud_backend/tests/test_auth_tasks.py:836:def test_task_overdue_only_after_calendar_day_ends():
cloud_backend/tests/test_auth_tasks.py:903:def test_review_history_lists_previous_weeks_and_dashboard_can_switch_by_weeklabel():
cloud_backend/tests/test_auth_tasks.py:950:def test_org_model_profile_roundtrip():
cloud_backend/tests/test_auth_tasks.py:1045:def test_task_org_link_and_department_control_permissions():
cloud_backend/tests/test_auth_tasks.py:1099:def test_task_plan_link_and_support_request_flow():
cloud_backend/tests/test_auth_tasks.py:1196:def test_event_line_roundtrip_and_detail_collects_task_and_support_request():
cloud_backend/tests/test_auth_tasks.py:1265:def test_task_review_approve_and_return_follow_org_permissions():
cloud_backend/tests/test_auth_tasks.py:1372:def test_org_model_backfill_restores_missing_task_links_for_existing_tasks():
cloud_backend/tests/test_bootstrap_security.py:16:def test_secure_bootstrap_defaults_do_not_accept_source_credentials(tmp_path: Path, monkeypatch):
cloud_backend/tests/test_bootstrap_security.py:45:def test_seed_password_from_env_refreshes_existing_admin_login(tmp_path: Path, monkeypatch):
cloud_backend/tests/test_feishu_notification_service.py:69:def test_weekly_review_send_uses_unified_card_service(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_notification_service.py:104:def test_badge_unlock_endpoint_sends_once_with_dedupe(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_notification_service.py:136:def test_overdue_digest_sends_red_summary_once_per_day(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_org_integration.py:31:def test_org_feishu_validate_and_delivery_profile_flow(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_org_integration.py:84:def test_invalid_feishu_config_does_not_override_existing_valid_config(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_query_service.py:148:def test_mapped_sender_can_query_today_tasks_and_logs_result(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_query_service.py:188:def test_unfinished_task_question_is_treated_as_task_list_not_title_keyword_search(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_query_service.py:224:def test_sender_profile_can_auto_bind_unique_account_before_querying(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_query_service.py:269:def test_unresolved_sender_gets_binding_guide_and_scope_denied_is_explicit(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_query_service.py:318:def test_weekly_review_and_event_line_queries_return_personal_summaries(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_query_service.py:393:def test_model_parse_can_filter_tasks_by_collaboration_partner(tmp_path, monkeypatch):
cloud_backend/tests/test_feishu_query_service.py:467:def test_model_parse_can_distinguish_overdue_unfinished_tasks(tmp_path, monkeypatch):
cloud_backend/tests/test_local_first_auth.py:24:def test_cloud_registration_without_organization_name_uses_default_name(tmp_path, monkeypatch):
cloud_backend/tests/test_local_first_auth.py:51:def test_cloud_registration_uses_local_organization_name(tmp_path, monkeypatch):
cloud_backend/tests/test_local_first_auth.py:76:def test_cloud_registration_with_profile_fields_bootstraps_owner(tmp_path, monkeypatch):
cloud_backend/tests/test_local_first_auth.py:104:def test_first_organization_account_repairs_even_with_later_admin(tmp_path, monkeypatch):
cloud_backend/tests/test_local_first_auth.py:145:def test_cloud_registration_conflicting_email_returns_binding_guidance(tmp_path, monkeypatch):
cloud_backend/tests/test_local_first_auth.py:170:def test_cloud_registration_invalid_invite_returns_clear_error(tmp_path, monkeypatch):
cloud_backend/tests/test_maintenance_mode.py:38:def test_admin_can_authorize_employee_for_maintenance_mode(tmp_path: Path, monkeypatch) -> None:
cloud_backend/tests/test_maintenance_mode.py:80:def test_maintenance_permissions_are_organization_scoped(tmp_path: Path, monkeypatch) -> None:
cloud_backend/tests/test_mobile_consult_contract.py:47:def test_mobile_capabilities_and_openapi_contract(tmp_path: Path, monkeypatch) -> None:
cloud_backend/tests/test_mobile_consult_contract.py:76:def test_workspace_and_cockpit_return_structured_missing_for_valid_client(tmp_path: Path, monkeypatch) -> None:
cloud_backend/tests/test_mobile_consult_contract.py:101:def test_thin_context_chat_returns_limited_context_metadata(tmp_path: Path, monkeypatch) -> None:
cloud_backend/tests/test_review_task_time.py:28:def test_unfinished_review_week_uses_schedule_or_deadline_not_created_at():
cloud_backend/tests/test_review_task_time.py:39:def test_completed_review_week_prefers_completed_at():
cloud_backend/tests/test_simulation_seed.py:50:def test_seed_simulated_review_org_populates_week_and_visibility():
cloud_backend/tests/test_smart_input.py:7:def test_build_smart_task_draft_extracts_range_title_and_match():
cloud_backend/tests/test_smart_input.py:33:def test_build_smart_task_draft_handles_relative_day_and_analysis_tag():
cloud_backend/tests/test_smart_input.py:46:def test_build_smart_task_draft_builds_structured_title_for_client_event_line_and_action():
cloud_backend/tests/test_task_feishu_notifications.py:52:def test_create_task_sends_card_notifications_to_phone_matched_owner_and_collaborators(tmp_path, monkeypatch):
cloud_backend/tests/test_task_feishu_notifications.py:129:def test_title_only_update_is_queued_then_sent_as_content_notification(tmp_path, monkeypatch):
cloud_backend/tests/test_task_feishu_notifications.py:193:def test_key_field_changes_send_immediately_and_missing_mobile_recipients_are_skipped(tmp_path, monkeypatch):
cloud_backend/tests/test_task_feishu_notifications.py:273:def test_immediate_change_absorbs_pending_content_change_into_one_notification(tmp_path, monkeypatch):
cloud_backend/tests/test_task_list_repair.py:34:def test_cloud_create_task_list_is_idempotent_for_active_name():
cloud_backend/tests/test_task_list_repair.py:55:def test_cloud_repair_duplicate_task_lists_moves_tasks_and_deletes_empty_duplicates():
cloud_backend/tests/test_task_list_repair.py:118:def test_cloud_task_settings_default_list_only_allows_inbox_or_org_task_destination():
cloud_backend/tests/test_task_pressure_seed.py:83:def test_parse_pressure_seed_markdown_skips_template_block(tmp_path: Path):
cloud_backend/tests/test_task_pressure_seed.py:94:def test_seed_task_pressure_doc_populates_tasks_reviews_and_collaboration(tmp_path: Path):
```
