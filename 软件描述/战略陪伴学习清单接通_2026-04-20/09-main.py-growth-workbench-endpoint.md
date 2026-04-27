# backend/app/main.py (growth/workbench endpoint neighborhood, lines 30601-30941)

```python
                    blocker=str(context.get("currentBlocker") or ""),
                    next_action=str(context.get("nextAction") or ""),
                    recent_decision=str(context.get("recentDecision") or ""),
                    context_summary=str(context.get("contextSummary") or ""),
                    evidence_refs=[str(ref) for ref in (context.get("evidenceRefs") or []) if ref],
                )
                if result.get("quote"):
                    context["insightQuote"] = result["quote"]
                    if result.get("sourceLabel"):
                        context["insightSourceLabel"] = result["sourceLabel"]
                    state.db.execute(
                        "UPDATE growth_signal_events SET context_json = ? WHERE id = ?",
                        (to_json(context), str(row["id"])),
                    )
                    enriched_captures += 1
            except Exception:
                continue

        # 2. Enrich handbook entries whose title looks like a raw task title (>80 chars or no insight pattern)
        entry_rows = state.db.fetchall(
            "SELECT id, title, summary, context_summary FROM handbook_entries ORDER BY created_at DESC LIMIT 30"
        )
        for entry_row in entry_rows:
            title = str(entry_row["title"] or "")
            # Skip entries that already look like refined quotes (short, no verb-heavy task patterns)
            if len(title) <= 80 and not any(kw in title for kw in ["完成", "推进", "创建", "更新", "处理", "提交"]):
                continue
            try:
                result = state.ai.distill_growth_insight_quote(
                    task_title=title,
                    task_desc=str(entry_row["summary"] or ""),
                    context_summary=str(entry_row["context_summary"] or ""),
                )
                if result.get("quote") and result["quote"] != title:
                    state.db.execute(
                        "UPDATE handbook_entries SET title = ?, summary = CASE WHEN summary = '' OR summary IS NULL THEN ? ELSE summary END WHERE id = ?",
                        (result["quote"], title, str(entry_row["id"])),
                    )
                    enriched_entries += 1
            except Exception:
                continue

        return {"enriched_captures": enriched_captures, "enriched_entries": enriched_entries}

    @app.post("/api/v1/growth/handbook/{entry_id}/mark-reused", response_model=GrowthValidationActionResponse)
    def mark_growth_handbook_reused(entry_id: str, payload: GrowthValidationPayload) -> GrowthValidationActionResponse:
        user_id, user_name = resolve_growth_actor()
        handbook_entries = list_handbook().entries
        entry = next((item for item in handbook_entries if item.id == entry_id), None)
        if entry is None:
            raise HTTPException(status_code=404, detail="成长手册条目不存在")
        return mark_handbook_entry_reused(
            state.db,
            user_id=user_id,
            user_name=user_name,
            entry=entry,
            week_label=resolve_growth_week_label(user_id, None),
            source_type=(payload.sourceType or "handbook_manual_reuse").strip() or "handbook_manual_reuse",
            source_id=(payload.sourceId or "").strip() or resolve_growth_week_label(user_id, None),
            source_label=payload.sourceLabel or "",
            context_summary=payload.contextSummary or "",
            linked_contexts=[item.model_dump() for item in payload.linkedContexts] if payload.linkedContexts else None,
            note=payload.note,
            created_at=now_iso(),
        )

    @app.get("/api/v1/growth/overview", response_model=GrowthOverviewRecord)
    def get_growth_overview(weekLabel: str | None = Query(default=None)) -> GrowthOverviewRecord:
        user_id, user_name = resolve_growth_actor()
        handbook_entries = list_handbook().entries
        if handbook_entries:
            backfill_handbook_entries(state.db, user_id=user_id, user_name=user_name, entries=handbook_entries)
        build_badge_board(state.db, user_id=user_id, user_name=user_name, auto_sync=True)
        return build_growth_overview(
            state.db,
            user_id=user_id,
            user_name=user_name,
            week_label=resolve_growth_week_label(user_id, weekLabel),
        )

    @app.get("/api/v1/growth/workbench", response_model=GrowthWorkbenchSnapshotRecord)
    def get_growth_workbench(
        weekLabel: str | None = Query(default=None),
        clientId: str | None = Query(default=None),
        mode: Literal["global", "strategic"] = Query(default="global"),
    ) -> GrowthWorkbenchSnapshotRecord:
        user_id, user_name = resolve_growth_actor()
        handbook_entries = list_handbook().entries
        if handbook_entries:
            backfill_handbook_entries(state.db, user_id=user_id, user_name=user_name, entries=handbook_entries)
        build_badge_board(state.db, user_id=user_id, user_name=user_name, auto_sync=True)
        return build_growth_workbench_snapshot(
            week_label=resolve_growth_week_label(user_id, weekLabel),
            client_id=clientId,
            mode=mode,
        )

    @app.get("/api/v1/growth/ledger", response_model=GrowthLedgerResponse)
    def get_growth_ledger(
        abilityKey: str | None = Query(default=None),
        weekLabel: str | None = Query(default=None),
    ) -> GrowthLedgerResponse:
        user_id, user_name = resolve_growth_actor()
        handbook_entries = list_handbook().entries
        if handbook_entries:
            backfill_handbook_entries(state.db, user_id=user_id, user_name=user_name, entries=handbook_entries)
        build_badge_board(state.db, user_id=user_id, user_name=user_name, auto_sync=True)
        return build_growth_ledger(state.db, user_id=user_id, ability_key=abilityKey, week_label=weekLabel)

    @app.get("/api/v1/growth/badges", response_model=BadgeBoardResponse)
    def get_growth_badges() -> BadgeBoardResponse:
        user_id, user_name = resolve_growth_actor()
        handbook_entries = list_handbook().entries
        if handbook_entries:
            backfill_handbook_entries(state.db, user_id=user_id, user_name=user_name, entries=handbook_entries)
        return build_badge_board(state.db, user_id=user_id, user_name=user_name, auto_sync=True)

    @app.get("/api/v1/growth/recommendations", response_model=list[LearningRecommendationRecord])
    def get_growth_recommendations() -> list[LearningRecommendationRecord]:
        user_id, user_name = resolve_growth_actor()
        handbook_entries = list_handbook().entries
        if handbook_entries:
            backfill_handbook_entries(state.db, user_id=user_id, user_name=user_name, entries=handbook_entries)
        return list_learning_recommendations(state.db, user_id)

    @app.post("/api/v1/growth/pending-captures/{capture_id}/state", response_model=GrowthPendingCaptureActionResponse)
    def update_growth_pending_capture(capture_id: str, payload: GrowthPendingCaptureActionPayload) -> GrowthPendingCaptureActionResponse:
        user_id, _user_name = resolve_growth_actor()
        updated = update_pending_capture_state(
            state.db,
            user_id=user_id,
            capture_id=capture_id,
            status=payload.status,
            reason=payload.reason,
            handbook_entry_id=payload.handbookEntryId,
            created_at=now_iso(),
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="待放大的成长信号不存在或已失效")
        return GrowthPendingCaptureActionResponse(capture=updated)

    @app.post("/api/v1/growth/recommendations/{recommendation_id}/accept", response_model=GrowthRecommendationActionResponse)
    def accept_growth_recommendation(recommendation_id: str) -> GrowthRecommendationActionResponse:
        user_id, user_name = resolve_growth_actor()
        recommendation = next((item for item in list_learning_recommendations(state.db, user_id) if item.id == recommendation_id), None)
        if recommendation is None:
            raise HTTPException(status_code=404, detail="成长练习推荐不存在或已失效")
        task_settings = _get_local_task_settings()
        task = create_task(
            TaskPayload(
                title=f"成长练习：{recommendation.title}",
                desc="\n".join(
                    line
                    for line in (
                        recommendation.summary.strip(),
                        f"推荐原因：{recommendation.reason.strip()}",
                        f"行动目标：{recommendation.practiceTask.strip()}",
                    )
                    if line
                ),
                priority="normal",
                listId=task_settings.defaultListId or "list-0",
                ownerName=user_name,
                tags=["成长练习", recommendation.abilityLabel],
                sourceType="growth_recommendation",
                sourceId=recommendation.id,
            )
        )
        updated = mark_recommendation_accepted(state.db, recommendation_id, task.id)
        if updated is None:
            raise HTTPException(status_code=404, detail="成长练习推荐不存在或已失效")
        return GrowthRecommendationActionResponse(recommendation=updated, task=task)

    @app.post("/api/v1/growth/recommendations/{recommendation_id}/dismiss", response_model=GrowthRecommendationActionResponse)
    def dismiss_growth_recommendation(
        recommendation_id: str,
        payload: GrowthRecommendationDismissPayload,
    ) -> GrowthRecommendationActionResponse:
        user_id, _ = resolve_growth_actor()
        recommendation = next((item for item in list_learning_recommendations(state.db, user_id) if item.id == recommendation_id), None)
        if recommendation is None:
            raise HTTPException(status_code=404, detail="成长练习推荐不存在或已失效")
        updated = mark_recommendation_dismissed(state.db, recommendation_id, payload.reason)
        if updated is None:
            raise HTTPException(status_code=404, detail="成长练习推荐不存在或已失效")
        return GrowthRecommendationActionResponse(recommendation=updated, task=None)

    return app


def build_excerpt(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt", ".json", ".csv"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:140] or f"{path.name} 已导入。"
        except Exception:
            pass
    return f"{path.name} 已进入资料缓冲池，可作为后续问答与证据引用来源。"


def backfill_local_task_tag_ids(state: AppState) -> None:
    timestamp = now_iso()
    operator_id = state.db.get_setting("current_operator_id", "") or "op_qh"
    state.db.execute(
        """
        UPDATE task_tags
        SET scope = COALESCE(NULLIF(scope, ''), 'org'),
            color = COALESCE(NULLIF(color, ''), CASE WHEN scope = 'self' THEN '#9CA3AF' ELSE '#5B7BFE' END),
            owner_operator_id = COALESCE(owner_operator_id, ''),
            created_by = COALESCE(NULLIF(created_by, ''), '系统'),
            created_at = COALESCE(NULLIF(created_at, ''), ?),
            updated_at = COALESCE(NULLIF(updated_at, ''), ?)
        """,
        (timestamp, timestamp),
    )
    state.db.execute(
        "UPDATE task_lists SET is_default = CASE WHEN id = 'list-0' THEN 1 ELSE COALESCE(is_default, 0) END WHERE is_default IS NULL OR is_default = ''"
    )
    for row in state.db.fetchall("SELECT id, tags_json, tag_ids_json FROM tasks"):
        tag_ids = _parse_json_list(row["tag_ids_json"])
        if tag_ids:
            continue
        tag_names = _parse_json_list(row["tags_json"])
        if not tag_names:
            continue
        resolved = [_ensure_local_tag(state.db, operator_id, name, "org") for name in tag_names if name.strip()]
        state.db.execute(
            "UPDATE tasks SET tag_ids_json = ?, tags_json = ?, updated_at = ? WHERE id = ?",
            (to_json([item.id for item in resolved]), to_json([item.name for item in resolved]), timestamp, str(row["id"])),
        )
    state.db.execute(
        "UPDATE weekly_reviews SET operator_id = COALESCE(NULLIF(operator_id, ''), ?), updated_at = COALESCE(NULLIF(updated_at, ''), created_at) WHERE operator_id = '' OR updated_at = ''",
        (operator_id,),
    )


def seed_defaults(state: AppState) -> None:
    timestamp = now_iso()
    state.db.set_setting("folders_root_label", state.db.get_setting("folders_root_label", "桌面客户资料"))
    state.db.set_setting("ai_provider", state.db.get_setting("ai_provider", DEFAULT_PROVIDER))
    state.db.set_setting("ai_model", state.db.get_setting("ai_model", DEFAULT_MODEL))
    state.db.set_setting("demo_data_loaded", state.db.get_setting("demo_data_loaded", "0"))
    if state.db.scalar("SELECT COUNT(1) AS count FROM operators") == 0:
        operators = [
            ("op_qh", "庆华", "首席咨询助理", "咨询策略", "#5B7BFE", 1),
            ("op_ys", "一朔", "研究分析师", "洞察研究", "#10B981", 0),
            ("op_jn", "嘉宁", "项目推进", "交付协同", "#F59E0B", 0),
        ]
        state.db.executemany(
            "INSERT INTO operators(id, name, role, team, color, is_current, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            [(item[0], item[1], item[2], item[3], item[4], item[5], timestamp, timestamp) for item in operators],
        )
        state.db.set_setting("current_operator_id", "op_qh")
    if state.db.scalar("SELECT COUNT(1) AS count FROM task_lists") == 0:
        state.db.executemany(
            "INSERT INTO task_lists(id, name, color, sort_order, is_default, scope, archived_at) VALUES(?, ?, ?, ?, ?, ?, NULL)",
            [
                ("list-0", "收集箱", "#5B7BFE", 0, 1, "org"),
                ("list-1", "客户推进", "#5B7BFE", 1, 0, "org"),
                ("list-2", "研究洞察", "#F59E0B", 2, 0, "org"),
                ("list-3", "交付沉淀", "#10B981", 3, 0, "org"),
                ("plist-1", "健身", "#5B7BFE", 10, 1, "personal"),
                ("plist-2", "约会", "#EC4899", 11, 0, "personal"),
                ("plist-3", "吃饭", "#F59E0B", 12, 0, "personal"),
                ("plist-4", "学习", "#10B981", 13, 0, "personal"),
            ],
        )
    state.db.execute("UPDATE task_lists SET scope = 'org' WHERE scope IS NULL OR scope = ''")
    if state.db.scalar("SELECT COUNT(1) AS count FROM task_lists WHERE scope = 'personal'") == 0:
        state.db.executemany(
            "INSERT INTO task_lists(id, name, color, sort_order, is_default, scope, archived_at) VALUES(?, ?, ?, ?, ?, ?, NULL)",
            [
                ("plist-1", "健身", "#5B7BFE", 10, 1, "personal"),
                ("plist-2", "约会", "#EC4899", 11, 0, "personal"),
                ("plist-3", "吃饭", "#F59E0B", 12, 0, "personal"),
                ("plist-4", "学习", "#10B981", 13, 0, "personal"),
            ],
        )
    if state.db.scalar("SELECT COUNT(1) AS count FROM task_tags") == 0:
        state.db.executemany(
            "INSERT INTO task_tags(id, name, scope, color, owner_operator_id, created_by, created_at, updated_at, archived_at) VALUES(?, ?, 'org', ?, '', '系统', ?, ?, NULL)",
            [
                (new_id("tag"), "高优", "#EF4444", timestamp, timestamp),
                (new_id("tag"), "会议", "#5B7BFE", timestamp, timestamp),
                (new_id("tag"), "待跟进", "#F59E0B", timestamp, timestamp),
                (new_id("tag"), "跨部门", "#10B981", timestamp, timestamp),
                (new_id("tag"), "选题", "#8B5CF6", timestamp, timestamp),
            ],
        )
    if state.db.scalar("SELECT COUNT(1) AS count FROM task_settings") == 0:
        state.db.executemany(
            """
            INSERT INTO task_settings(
                operator_id, default_list_id, default_priority, default_due_date_preset,
                default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
                auto_assign_self, updated_at
            ) VALUES(?, 'list-0', 'normal', 'today', 'calendar', 'manual', 0, 'work', 1, ?)
            """,
            [(str(row["id"]), timestamp) for row in state.db.fetchall("SELECT id FROM operators")],
        )
    if state.db.scalar("SELECT COUNT(1) AS count FROM analysis_templates") == 0:
        state.db.executemany(
            "INSERT INTO analysis_templates(id, title, description, template_key, created_at) VALUES(?, ?, ?, ?, ?)",
            [
                ("tpl_fundraising", "筹款分析", "聚焦筹资路径、渠道效率、节奏与风险。", "fundraising", timestamp),
                ("tpl_systemic", "系统分析", "聚焦组织问题、依赖关系、根因与推进建议。", "systemic", timestamp),
            ],
        )
    backfill_local_task_tag_ids(state)


app = create_app()
```
