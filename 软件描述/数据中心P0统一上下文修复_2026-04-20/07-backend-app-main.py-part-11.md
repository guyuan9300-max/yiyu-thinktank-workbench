# 源码文件：`backend/app/main.py`（分片 11）

- 行号范围：28001-   30416
- 总行数：   30416
- 导出时间：2026-04-20

```python
                    cloud_upload_file(
                        f"/api/v1/tasks/{task_id}/attachments",
                        file_name=upload_name,
                        file_content=content,
                        content_type=file.content_type or "application/octet-stream",
                        form_fields={
                            "clientId": resolved_client_id or "",
                            "eventLineId": resolved_event_line_id,
                            "title": str(document_row["title"]),
                            "taskTitle": resolved_task_title,
                        },
                    )
                except Exception:
                    pass  # 云端上传失败不阻断本地流程

            threading.Thread(target=_bg_upload, daemon=True).start()

        # Async preprocess: extract text from attachment and write to event line memory
        att_kind = str(document_row["kind"])
        if att_kind in ("docx", "doc", "md", "txt", "pdf") and resolved_event_line_id:
            import threading as _thr

            def _bg_preprocess_attachment():
                try:
                    from app.services.local_memory import write_event_line_memory, read_event_line_memory
                    # Read file text
                    att_path = Path(str(document_row["path"]))
                    text = ""
                    if att_path.exists() and att_kind in ("md", "txt"):
                        text = att_path.read_text(encoding="utf-8", errors="ignore")
                    elif att_path.exists() and att_kind in ("docx", "doc"):
                        try:
                            from docx import Document as _DocxDoc
                            doc = _DocxDoc(str(att_path))
                            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                        except Exception:
                            pass
                    if not text or len(text) < 50:
                        return
                    # Cache text-content locally
                    _att_cache_write(attachment_id, json.dumps({"title": str(document_row["title"]), "text": text, "kind": att_kind}, ensure_ascii=False).encode("utf-8"), suffix=".text.json")
                    # AI summarize if available
                    health = state.ai.get_health()
                    if health.provider != "mock" and health.ready:
                        summary = state.ai._qwen_generate(
                            prompt=f"以下是一份工作文档（{document_row['title']}）的全文，请提炼出：1）核心议题 2）关键决策 3）下一步行动 4）主要风险或卡点。用简洁的要点格式输出。\n\n{text[:8000]}",
                            system_instruction="你是组织工作文档摘要助手。只输出结构化要点，不要输出原文。",
                            response_schema={"type": "object", "properties": {"topics": {"type": "string"}, "decisions": {"type": "string"}, "nextSteps": {"type": "string"}, "risks": {"type": "string"}}, "required": ["topics", "decisions", "nextSteps", "risks"]},
                            timeout_seconds=30.0,
                            max_tokens=800,
                            temperature=0.3,
                            top_p=0.9,
                            enable_thinking=False,
                        )
                        if isinstance(summary, dict):
                            el_row = state.db.fetchone("SELECT name, primary_client_name FROM event_lines WHERE id = ?", (resolved_event_line_id,))
                            el_name = str(el_row["name"]) if el_row else resolved_event_line_id
                            client_name = str(el_row["primary_client_name"]) if el_row else resolved_client_id
                            # Read existing memory and append
                            existing = read_event_line_memory(state.data_dir, resolved_client_id, resolved_event_line_id)
                            new_section = f"\n## 附件摘要：{document_row['title']}\n"
                            if summary.get("topics"):
                                new_section += f"**核心议题：** {summary['topics']}\n"
                            if summary.get("decisions"):
                                new_section += f"**关键决策：** {summary['decisions']}\n"
                            if summary.get("nextSteps"):
                                new_section += f"**下一步：** {summary['nextSteps']}\n"
                            if summary.get("risks"):
                                new_section += f"**风险/卡点：** {summary['risks']}\n"
                            content_to_write = (existing + new_section) if existing else f"## {el_name}\n{new_section}"
                            write_event_line_memory(state.data_dir, resolved_client_id, resolved_event_line_id, el_name, client_name, content_to_write)
                    # Extract golden quotes from attachment text
                    from app.services.local_memory import extract_quotes_from_text, save_pending_quotes
                    quotes = extract_quotes_from_text(state.ai, text, f"附件：{document_row['title']}")
                    if quotes:
                        save_pending_quotes(state.db, quotes)
                except Exception:
                    pass  # 预处理失败不影响主流程

            _thr.Thread(target=_bg_preprocess_attachment, daemon=True).start()

        # Invalidate task board cache
        _cloud_task_board_cache["data"] = None
        # Always rebuild task from local data first (local-first principle)
        if is_cloud_task:
            task_after_upload = fetch_cloud_task_by_id(task_id)
            # Ensure local attachments are included even if cloud hasn't synced yet
            local_atts = fetch_task_attachments(task_id, cloud=True)
            if len(local_atts) > len(task_after_upload.attachments):
                task_after_upload = task_after_upload.model_copy(update={"attachments": local_atts})
        else:
            task_after_upload = fetch_tasks("t.id = ?", (task_id,))[0]
        growth_user_id, growth_user_name = resolve_growth_actor()
        ingest_task_growth_candidate(
            state.db,
            user_id=growth_user_id,
            user_name=growth_user_name,
            task=task_after_upload,
            source_type="task_attachment_candidate",
            created_at=timestamp,
            ai_service=state.ai,
        )
        return task_after_upload

    @app.post("/api/v1/tasks/{task_id}/confirm", response_model=TaskRecord)
    def confirm_task(task_id: str) -> TaskRecord:
        if get_cloud_token():
            try:
                user = require_session_user()
                response = cloud_request("POST", f"/api/v1/tasks/{task_id}/collaborators/{user.id}/accept")
                if isinstance(response, dict):
                    log_activity("task.confirm", "task", task_id, {"userId": user.id})
                    _upsert_cloud_task_shadow_local(response)
                    return build_cloud_task(response, {})
            except Exception:
                pass  # cloud down — confirm locally
        state.db.execute("UPDATE tasks SET status = 'doing', updated_at = ? WHERE id = ?", (now_iso(), task_id))
        log_activity("task.confirm", "task", task_id, {})
        return fetch_tasks("t.id = ?", (task_id,))[0]

    @app.post("/api/v1/tasks/{task_id}/reject", response_model=TaskRecord)
    def reject_task(task_id: str, payload: TaskRejectPayload) -> TaskRecord:
        if get_cloud_token():
            try:
                user = require_session_user()
                response = cloud_request(
                    "POST",
                    f"/api/v1/tasks/{task_id}/collaborators/{user.id}/return",
                    json_body={"reason": payload.reason},
                )
                upsert_task_note(task_id, payload.reason)
                log_activity("task.reject", "task", task_id, {"reason": payload.reason, "userId": user.id})
                if isinstance(response, dict):
                    _upsert_cloud_task_shadow_local(response)
                    return build_cloud_task(response, {})
            except Exception:
                pass  # cloud down — reject locally
        state.db.execute("UPDATE tasks SET status = 'rejected', updated_at = ? WHERE id = ?", (now_iso(), task_id))
        upsert_task_note(task_id, payload.reason)
        log_activity("task.reject", "task", task_id, {"reason": payload.reason})
        return fetch_tasks("t.id = ?", (task_id,))[0]

    @app.post("/api/v1/tasks/{task_id}/complete-with-review", response_model=TaskRecord)
    def complete_task_with_review(task_id: str, payload: TaskCompletionReviewPayload) -> TaskRecord:
        if not get_cloud_token():
            raise HTTPException(status_code=400, detail="当前环境未启用组织复核链")
        response = cloud_request("POST", f"/api/v1/tasks/{task_id}/complete-with-review", payload.model_dump())
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid cloud task payload")
        log_activity("task.complete-with-review", "task", task_id, {"reviewNote": payload.reviewNote[:60]})
        _upsert_cloud_task_shadow_local(response)
        return build_cloud_task(response, {})

    @app.post("/api/v1/tasks/{task_id}/review/approve", response_model=TaskRecord)
    def approve_task_review(task_id: str) -> TaskRecord:
        if not get_cloud_token():
            raise HTTPException(status_code=400, detail="当前环境未启用组织复核链")
        response = cloud_request("POST", f"/api/v1/tasks/{task_id}/review/approve")
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid cloud task payload")
        log_activity("task.review.approve", "task", task_id, {})
        _upsert_cloud_task_shadow_local(response)
        return build_cloud_task(response, {})

    @app.post("/api/v1/tasks/{task_id}/review/return", response_model=TaskRecord)
    def return_task_review(task_id: str, payload: TaskRejectPayload) -> TaskRecord:
        if not get_cloud_token():
            raise HTTPException(status_code=400, detail="当前环境未启用组织复核链")
        response = cloud_request(
            "POST",
            f"/api/v1/tasks/{task_id}/review/return",
            json_body={"reason": payload.reason},
        )
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Invalid cloud task payload")
        log_activity("task.review.return", "task", task_id, {"reason": payload.reason})
        _upsert_cloud_task_shadow_local(response)
        return build_cloud_task(response, {})

    @app.post("/api/v1/tasks/{task_id}/note", response_model=TaskRecord)
    def save_task_note(task_id: str, payload: TaskNotePayload) -> TaskRecord:
        upsert_task_note(task_id, payload.note)
        log_activity("task.note", "task", task_id, {"noteLength": len(payload.note)})
        if not get_cloud_token():
            state.db.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now_iso(), task_id))
            return fetch_tasks("t.id = ?", (task_id,))[0]
        try:
            cloud_request("POST", f"/api/v1/tasks/{task_id}/note", {"note": payload.note})
        except HTTPException:
            pass  # 云端保存失败时保留本地备注，不阻断用户操作
        board = cloud_task_board()
        task = next((item for item in board.tasks if item.id == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.get("/api/v1/tasks/{task_id}/activity", response_model=list[TaskActivityRecord])
    def get_task_activity(task_id: str) -> list[TaskActivityRecord]:
        if not get_cloud_token():
            if task_id.startswith("agent_task_"):
                ensure_admin_for_sensitive_settings()
                return build_agent_execution_task_activity(
                    db=state.db,
                    task_id=task_id,
                    thread_sync_path=THREAD_SYNC_DOC_PATH,
                )
            return [
                TaskActivityRecord(
                    id=str(row["id"]),
                    taskId=task_id,
                    actorId=str(row["actor_name"] or "local"),
                    actorName=str(row["actor_name"] or "本地用户"),
                    eventType=str(row["action"]),
                    payload=from_json(row["detail_json"], {}) if row["detail_json"] else {},
                    createdAt=str(row["created_at"]),
                )
                for row in state.db.fetchall(
                    """
                    SELECT *
                    FROM activity_logs
                    WHERE entity_type = 'task' AND entity_id = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    (task_id,),
                )
            ]
        try:
            payload = cloud_request("GET", f"/api/v1/tasks/{task_id}/activity")
            if isinstance(payload, list):
                return [TaskActivityRecord(**item) for item in payload if isinstance(item, dict)]
        except Exception:
            pass
        return []

    @app.get("/api/v1/tasks/agent-execution", response_model=list[TaskRecord])
    def list_agent_execution_tasks(week: str | None = None, department: str | None = None) -> list[TaskRecord]:
        session_user = get_cached_session_user()
        if get_cloud_token() and session_user is None:
            session_user = require_session_user()
        governance = _review_governance_with_members()
        allowed_department = _resolve_agent_execution_department_scope(
            session_user=session_user,
            governance=governance,
            requested_department=department,
        )
        target_week = week or current_review_week_label()
        sync_agent_execution_tasks(
            db=state.db,
            week_label=target_week,
            thread_sync_path=THREAD_SYNC_DOC_PATH,
        )
        tasks = build_agent_execution_tasks(
            db=state.db,
            week_label=target_week,
            thread_sync_path=THREAD_SYNC_DOC_PATH,
        )
        if not allowed_department:
            return tasks
        normalized_allowed_department = _normalize_department_name(allowed_department)
        filtered: list[TaskRecord] = []
        for task in tasks:
            if any(_normalize_department_name(tag.name) == normalized_allowed_department for tag in task.tags):
                filtered.append(task)
        return filtered

    @app.post("/api/v1/local/tasks/tag-suggestions", response_model=AiTagSuggestionResponse)
    def suggest_task_tags(payload: AiTagSuggestionPayload) -> AiTagSuggestionResponse:
        _ = payload
        return AiTagSuggestionResponse(suggestedTags=[])

    def _cloud_is_available() -> bool:
        """Check if cloud backend is reachable (circuit breaker not active)."""
        import time as _time
        return _time.time() - _cloud_circuit_breaker["last_failure"] >= 60

    def _safe_cloud_request(method: str, path: str, **kwargs) -> object | None:
        """cloud_request wrapper: returns None on any failure instead of raising."""
        if not _cloud_is_available():
            return None
        try:
            return cloud_request(method, path, **kwargs)
        except Exception:
            return None

    @app.get("/api/v1/reviews", response_model=ReviewResponse)
    def list_reviews(weekLabel: str | None = Query(default=None)) -> ReviewResponse:
        if get_cloud_token():
            suffix = f"?weekLabel={quote(weekLabel)}" if weekLabel else ""
            payload = _safe_cloud_request("GET", f"/api/v1/reviews/dashboard{suffix}")
            if isinstance(payload, dict):
                try:
                    return augment_review_response(ReviewResponse(**payload), weekLabel)
                except Exception:
                    pass
        return local_review_dashboard(weekLabel)

    @app.get("/api/v1/reviews/history", response_model=ReviewHistoryResponse)
    def list_review_history() -> ReviewHistoryResponse:
        if get_cloud_token():
            try:
                payload = cloud_request("GET", "/api/v1/reviews/history")
                if isinstance(payload, dict):
                    return ReviewHistoryResponse(**payload)
            except Exception:
                pass  # cloud down — fall back to local
        return local_review_history()

    def save_local_weekly_review(
        payload: WeeklyReviewPayload,
    ) -> tuple[str, str, str, list[WeeklyReviewTaskEntryRecord]]:
        created_at = now_iso()
        operator_id = str(current_operator_row()["id"])
        existing = local_review_row_for_week(payload.weekLabel)
        if existing:
            review_id = str(existing["id"])
            state.db.execute(
                """
                UPDATE weekly_reviews
                SET work_free_note = ?, personal_growth_note = ?, personal_private_note = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.workFreeNote.strip(),
                    payload.personalGrowthNote.strip(),
                    payload.personalPrivateNote.strip(),
                    created_at,
                    review_id,
                ),
            )
        else:
            review_id = new_id("review")
            state.db.execute(
                """
                INSERT INTO weekly_reviews(
                    id, week_label, operator_id, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    payload.weekLabel,
                    operator_id,
                    "",
                    payload.workFreeNote.strip(),
                    payload.personalGrowthNote.strip(),
                    payload.personalPrivateNote.strip(),
                    created_at,
                    created_at,
                ),
            )
        reviewed_work_items: list[WeeklyReviewTaskEntryRecord] = []
        for entry in payload.taskEntries:
            task_id = str(entry.get("taskId", "")).strip()
            if not task_id:
                continue
            task_items = fetch_tasks("t.id = ?", (task_id,))
            if not task_items:
                continue
            task_row = task_items[0]
            structured_note = coerce_review_structured_note(entry.get("structuredNote"))
            note = compose_review_note(structured_note, str(entry.get("note", "")).strip())
            existing_entry = state.db.fetchone(
                "SELECT id FROM weekly_review_task_entries WHERE review_id = ? AND task_id = ?",
                (review_id, task_id),
            )
            if not note:
                if existing_entry:
                    state.db.execute("DELETE FROM weekly_review_task_entries WHERE id = ?", (str(existing_entry["id"]),))
                continue
            content_domain = str(entry.get("contentDomain") or ("personal" if is_private_task(task_row) else "work"))
            snapshot = _task_snapshot_from_task(task_row, state.db)
            if existing_entry:
                state.db.execute(
                    """
                    UPDATE weekly_review_task_entries
                    SET content_domain = ?, note = ?, structured_note_json = ?, reviewed_at = ?, task_snapshot_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (content_domain, note, to_json(structured_note.model_dump()), created_at, to_json(snapshot), created_at, str(existing_entry["id"])),
                )
            else:
                state.db.execute(
                    """
                    INSERT INTO weekly_review_task_entries(
                        id, review_id, task_id, week_label, content_domain, note, structured_note_json, reviewed_at, task_snapshot_json, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("review_item"),
                        review_id,
                        task_id,
                        payload.weekLabel,
                        content_domain,
                        note,
                        to_json(structured_note.model_dump()),
                        created_at,
                        to_json(snapshot),
                        created_at,
                        created_at,
                    ),
                )
            if content_domain == "work":
                reviewed_work_items.append(
                    _review_entry_from_task(
                        task=task_row,
                        week_label=payload.weekLabel,
                        content_domain=content_domain,
                        review_id=review_id,
                        note=note,
                        structured_note=structured_note,
                        reviewed_at=created_at,
                        snapshot=snapshot,
                        db=state.db,
                    )
                )
        state.db.execute(
            """
            UPDATE weekly_reviews
            SET summary = ?, work_free_note = ?, personal_growth_note = ?, personal_private_note = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                summarize_local_review_notes(reviewed_work_items),
                payload.workFreeNote.strip(),
                payload.personalGrowthNote.strip(),
                payload.personalPrivateNote.strip(),
                created_at,
                review_id,
            ),
        )
        log_activity("review.create", "weekly_review", review_id, {"weekLabel": payload.weekLabel})
        record_weekly_review_writeback(state.db, review_id=review_id)
        return review_id, created_at, operator_id, reviewed_work_items

    def enqueue_review_memory_writeback(
        reviewed_work_items: list[WeeklyReviewTaskEntryRecord],
        *,
        week_label: str,
    ) -> None:
        if not reviewed_work_items:
            return

        import threading as _thr

        def _bg_update_memory_from_review():
            try:
                from app.services.local_memory import write_project_memory, write_event_line_memory
                # Collect all review notes (regardless of clientId — cloud often returns null)
                all_notes: list[tuple[str, str]] = []  # (title, note)
                for item in reviewed_work_items:
                    note_text = item.note.strip()
                    if not note_text:
                        continue
                    snap = item.taskSnapshot
                    all_notes.append((snap.title, note_text))
                    # Write event line memory if available
                    if snap.eventLineId:
                        el_cid = snap.clientId or "general"
                        el_name = snap.eventLineName or snap.eventLineId
                        el_cname = snap.clientName or ""
                        el_content = f"## {el_name}\n\n### 本周复盘：{snap.title}\n{note_text}"
                        write_event_line_memory(state.data_dir, el_cid, snap.eventLineId, el_name, el_cname, el_content)
                # Write all notes as a general project memory (use "general" if no clientId)
                if all_notes:
                    # Try to find a client from local event lines
                    default_cid = "general"
                    default_cname = "通用项目"
                    for item in reviewed_work_items:
                        if item.taskSnapshot.clientId:
                            default_cid = item.taskSnapshot.clientId
                            default_cname = item.taskSnapshot.clientName or default_cid
                            break
                    # Also check local event lines for client info
                    if default_cid == "general":
                        for item in reviewed_work_items:
                            elc = item.taskSnapshot.eventLineContext
                            if elc and elc.primaryClientId:
                                default_cid = elc.primaryClientId
                                default_cname = elc.primaryClientName or default_cid
                                break
                    # Still no client? Use first available from local DB
                    if default_cid == "general":
                        first_client = state.db.fetchone("SELECT id, name FROM clients ORDER BY name LIMIT 1")
                        if first_client:
                            default_cid = str(first_client["id"])
                            default_cname = str(first_client["name"])
                    content = f"## {week_label} 复盘记录\n\n" + "\n\n".join(
                        f"### {title}\n{note}" for title, note in all_notes
                    )
                    write_project_memory(state.data_dir, default_cid, default_cname, content)
            except Exception:
                pass

        _thr.Thread(target=_bg_update_memory_from_review, daemon=True).start()

    @app.post("/api/v1/reviews/weekly/draft", response_model=ReviewResponse)
    def save_weekly_review_draft(payload: WeeklyReviewPayload) -> ReviewResponse:
        if get_cloud_token():
            # Preserve cloud-mode behavior. The installed-app fast path only applies to local saves.
            return create_weekly_review(payload)

        _, created_at, operator_id, reviewed_work_items = save_local_weekly_review(payload)
        response = local_review_dashboard_base(payload.weekLabel)
        if response.currentReview:
            _, user_name = resolve_growth_actor()
            ingest_review_growth(
                state.db,
                user_id=operator_id,
                user_name=user_name,
                review=response.currentReview,
                task_entries=[*response.workItems, *response.personalItems],
                created_at=created_at,
            )
        enqueue_review_memory_writeback(reviewed_work_items, week_label=payload.weekLabel)
        return response

    @app.post("/api/v1/reviews/weekly", response_model=ReviewResponse)
    def create_weekly_review(payload: WeeklyReviewPayload) -> ReviewResponse:
        if get_cloud_token():
            response_payload = cloud_request("POST", "/api/v1/reviews/weekly", json_body=payload.model_dump())
            if not isinstance(response_payload, dict):
                raise HTTPException(status_code=502, detail="Invalid review payload")
            log_activity(
                "review.create",
                "weekly_review",
                str(response_payload.get("currentReview", {}).get("id", "review")),
                {"weekLabel": payload.weekLabel, "personalExcludedFromAggregation": True},
            )
            try:
                parsed_response = ReviewResponse(**response_payload)
                response = augment_review_response(parsed_response, payload.weekLabel)
            except Exception as augment_exc:
                import traceback
                err_detail = traceback.format_exc()
                # Write error to file for debugging
                try:
                    Path(state.data_dir).joinpath("augment_error.log").write_text(err_detail, encoding="utf-8")
                except Exception:
                    pass
                # Try returning raw response without augmentation
                try:
                    response = ReviewResponse(**response_payload)
                except Exception:
                    raise HTTPException(status_code=500, detail=f"Review parse failed: {augment_exc}") from augment_exc
            if response.currentReview:
                user_id, user_name = resolve_growth_actor()
                ingest_review_growth(
                    state.db,
                    user_id=user_id,
                    user_name=user_name,
                    review=response.currentReview,
                    task_entries=[*response.workItems, *response.personalItems],
                )
            return response
        _, created_at, operator_id, reviewed_work_items = save_local_weekly_review(payload)
        response = local_review_dashboard(payload.weekLabel)
        if response.currentReview:
            _, user_name = resolve_growth_actor()
            ingest_review_growth(
                state.db,
                user_id=operator_id,
                user_name=user_name,
                review=response.currentReview,
                task_entries=[*response.workItems, *response.personalItems],
                created_at=created_at,
            )
            response = local_review_dashboard(payload.weekLabel)
        enqueue_review_memory_writeback(reviewed_work_items, week_label=payload.weekLabel)
        return response

    def build_topic_candidate(row) -> TopicCandidateRecord:
        return TopicCandidateRecord(
            id=str(row["id"]),
            radarId=str(row["radar_id"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            source=str(row["source"]),
            sourceUrl=str(row["source_url"]) if row["source_url"] else None,
            publishedAt=str(row["published_at"]) if row["published_at"] else None,
            captureMethod=str(row["capture_method"]) if row["capture_method"] else "manual",
            capturedBy=str(row["captured_by"]) if row["captured_by"] else None,
            status=str(row["status"]),  # type: ignore[arg-type]
            insightStatus=str(row["insight_status"] or "pending"),  # type: ignore[arg-type]
            insightUpdatedAt=str(row["insight_updated_at"]) if row["insight_updated_at"] else None,
            createdAt=str(row["created_at"]),
        )

    def build_topic_candidate_insight(row) -> TopicCandidateInsightRecord:
        return TopicCandidateInsightRecord(
            candidateId=str(row["candidate_id"]),
            overview=str(row["overview"]),
            keyPoints=_parse_json_list(row["key_points_json"]),
            recommendationReasons=_parse_json_list(row["recommendation_reasons_json"]),
            practicalUses=_parse_json_list(row["practical_uses_json"]),
            editorialNote=str(row["editorial_note"] or ""),
            discussionPrompts=_parse_json_list(row["discussion_prompts_json"]),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def _fallback_topic_source_label(url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        primary = host.split(".")[0] if host else ""
        primary = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "", primary)
        if 2 <= len(primary) <= 6:
            return primary
        if primary:
            return primary[:6]
        return "优先站点"

    def normalize_topic_radar_source_url(value: str) -> str:
        raw = value.strip()
        if not raw:
            raise HTTPException(status_code=400, detail="网址不能为空")
        candidate = raw if "://" in raw else f"https://{raw}"
        parsed = urlparse(candidate)
        if not parsed.netloc and parsed.path and "." in parsed.path:
            candidate = f"https://{parsed.path}"
            parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="网址格式无效")
        normalized_path = parsed.path.rstrip("/")
        return urlunparse((parsed.scheme, parsed.netloc.lower(), normalized_path, "", "", ""))

    def suggest_topic_radar_source_label(url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.strip("/")
        descriptor = f"资讯来源网址：{host}{('/' + path) if path else ''}，请提炼成 2 到 6 个字的中文来源标签。"
        label = state.ai.suggest_short_title(descriptor).strip()
        if label:
            return label[:10]
        return _fallback_topic_source_label(url)

    def normalize_topic_radar_preferred_sources(items: list[TopicRadarPreferredSourceRecord] | None) -> list[TopicRadarPreferredSourceRecord]:
        normalized: list[TopicRadarPreferredSourceRecord] = []
        seen_urls: set[str] = set()
        for item in items or []:
            url = normalize_topic_radar_source_url(item.url)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            label = item.label.strip() if item.label.strip() else suggest_topic_radar_source_label(url)
            normalized.append(TopicRadarPreferredSourceRecord(url=url, label=label[:10] or _fallback_topic_source_label(url)))
        return normalized

    def parse_topic_radar_preferred_sources(raw_value: object) -> list[TopicRadarPreferredSourceRecord]:
        parsed = from_json(raw_value, [])
        if not isinstance(parsed, list):
            return []
        normalized: list[TopicRadarPreferredSourceRecord] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            label = str(item.get("label") or "").strip()
            if not url:
                continue
            normalized.append(TopicRadarPreferredSourceRecord(url=url, label=label or _fallback_topic_source_label(url)))
        return normalized

    def build_topic_radar(row) -> TopicRadarRecord:
        return TopicRadarRecord(
            id=str(row["id"]),
            title=str(row["title"]),
            prompt=str(row["prompt"]),
            timeRange=str(row["time_range"]),
            preferredSources=parse_topic_radar_preferred_sources(row["preferred_sources_json"]),
            createdAt=str(row["created_at"]),
        )

    def fetch_topic_candidates() -> list[TopicCandidateRecord]:
        return [
            build_topic_candidate(row)
            for row in state.db.fetchall("SELECT * FROM topic_candidates ORDER BY created_at DESC")
        ]

    def save_topic_candidate_insight(
        *,
        candidate_id: str,
        overview: str,
        key_points: list[str],
        recommendation_reasons: list[str],
        practical_uses: list[str],
        editorial_note: str,
        discussion_prompts: list[str],
        source_excerpt: str,
    ) -> TopicCandidateInsightRecord:
        existing = state.db.fetchone("SELECT * FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,))
        timestamp = now_iso()
        if existing:
            state.db.execute(
                """
                UPDATE topic_candidate_insights
                SET overview = ?, key_points_json = ?, recommendation_reasons_json = ?, practical_uses_json = ?, editorial_note = ?, discussion_prompts_json = ?, source_excerpt = ?, updated_at = ?
                WHERE candidate_id = ?
                """,
                (
                    overview,
                    to_json(key_points),
                    to_json(recommendation_reasons),
                    to_json(practical_uses),
                    editorial_note,
                    to_json(discussion_prompts),
                    source_excerpt,
                    timestamp,
                    candidate_id,
                ),
            )
        else:
            state.db.execute(
                """
                INSERT INTO topic_candidate_insights(
                    id, candidate_id, overview, key_points_json, recommendation_reasons_json, practical_uses_json, editorial_note, discussion_prompts_json, source_excerpt, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("insight"),
                    candidate_id,
                    overview,
                    to_json(key_points),
                    to_json(recommendation_reasons),
                    to_json(practical_uses),
                    editorial_note,
                    to_json(discussion_prompts),
                    source_excerpt,
                    timestamp,
                    timestamp,
                ),
            )
        row = state.db.fetchone("SELECT * FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,))
        assert row is not None
        return build_topic_candidate_insight(row)

    def update_topic_candidate_insight_state(candidate_id: str, status: str, *, error: str | None = None) -> None:
        state.db.execute(
            """
            UPDATE topic_candidates
            SET insight_status = ?, insight_updated_at = ?, insight_error = ?
            WHERE id = ?
            """,
            (status, now_iso(), error or None, candidate_id),
        )

    def topic_candidate_insight_needs_refresh(candidate_row, cached_row) -> bool:
        overview = str(cached_row["overview"] or "").strip()
        key_points = _parse_json_list(cached_row["key_points_json"])
        reasons = _parse_json_list(cached_row["recommendation_reasons_json"])
        uses = _parse_json_list(cached_row["practical_uses_json"])
        editorial_note = str(cached_row["editorial_note"] or "").strip()
        discussion_prompts = _parse_json_list(cached_row["discussion_prompts_json"])
        source_excerpt = str(cached_row["source_excerpt"] or "").strip()

        if not overview or not key_points or not reasons or not uses or not editorial_note or not discussion_prompts:
            return True
        if candidate_row["source_url"] and not source_excerpt:
            return True
        if not state.ai._has_sufficient_cjk(overview):
            return True
        if not state.ai._has_sufficient_cjk(editorial_note):
            return True
        if len(overview) < 120:
            return True
        if len(editorial_note) < 120:
            return True
        if state.ai._looks_generic_topic_overview(overview):
            return True
        if state.ai._looks_stale_topic_editorial_note(editorial_note):
            return True
        if any(not state.ai._has_sufficient_cjk(item) for item in key_points):
            return True
        if any(not state.ai._has_sufficient_cjk(item) for item in discussion_prompts):
            return True
        return False

    def ensure_topic_candidate_insight(candidate_row) -> tuple[TopicCandidateInsightRecord, str]:
        topics_settings = get_topics_settings()
        cached = state.db.fetchone("SELECT * FROM topic_candidate_insights WHERE candidate_id = ?", (str(candidate_row["id"]),))
        if cached and not topic_candidate_insight_needs_refresh(candidate_row, cached):
            update_topic_candidate_insight_state(str(candidate_row["id"]), "ready")
            return build_topic_candidate_insight(cached), str(cached["source_excerpt"] or "")
        source_content = fetch_topic_source_excerpt(str(candidate_row["source_url"])) if candidate_row["source_url"] else ""
        insight_payload = state.ai.build_topic_candidate_insight(
            candidate_title=str(candidate_row["title"]),
            candidate_summary=str(candidate_row["summary"]),
            source=str(candidate_row["source"]),
            published_at=str(candidate_row["published_at"]) if candidate_row["published_at"] else None,
            source_url=str(candidate_row["source_url"]) if candidate_row["source_url"] else None,
            source_content=source_content,
            organization_context=build_organization_dna_context() if topics_settings.useOrgDnaForInsight else "",
        )
        insight = save_topic_candidate_insight(
            candidate_id=str(candidate_row["id"]),
            overview=str(insight_payload.get("overview") or "").strip(),
            key_points=[str(item) for item in insight_payload.get("keyPoints", []) if str(item).strip()] if isinstance(insight_payload.get("keyPoints"), list) else [],
            recommendation_reasons=[str(item) for item in insight_payload.get("recommendationReasons", []) if str(item).strip()] if isinstance(insight_payload.get("recommendationReasons"), list) else [],
            practical_uses=[str(item) for item in insight_payload.get("practicalUses", []) if str(item).strip()] if isinstance(insight_payload.get("practicalUses"), list) else [],
            editorial_note=str(insight_payload.get("editorialNote") or "").strip(),
            discussion_prompts=[str(item) for item in insight_payload.get("discussionPrompts", []) if str(item).strip()] if isinstance(insight_payload.get("discussionPrompts"), list) else [],
            source_excerpt=source_content,
        )
        update_topic_candidate_insight_state(str(candidate_row["id"]), "ready")
        log_activity("topic.candidate.insight", "topic_candidate", str(candidate_row["id"]), {"keyPoints": len(insight.keyPoints)})
        return insight, source_content

    def build_topic_candidate_chat_context(
        *,
        candidate_row,
        radar_title: str,
        insight: TopicCandidateInsightRecord | None,
        source_excerpt: str,
        history: list[TopicCandidateChatMessageRecord],
    ) -> str:
        key_points = insight.keyPoints if insight else []
        writing_angles = insight.practicalUses if insight else []
        discussion_prompts = insight.discussionPrompts if insight else []
        recommendation_reasons = insight.recommendationReasons if insight else []
        editorial_note = insight.editorialNote.strip() if insight else ""
        overview = insight.overview.strip() if insight else ""

        blocks = [
            f"当前情报标题：{str(candidate_row['title'])}",
            f"关联雷达：{radar_title}",
            f"来源：{str(candidate_row['source'])}",
        ]
        if candidate_row["published_at"]:
            blocks.append(f"发布时间：{str(candidate_row['published_at'])}")
        if candidate_row["source_url"]:
            blocks.append(f"原文链接：{str(candidate_row['source_url'])}")

        blocks.extend(
            [
                "",
                "候选摘要：",
                str(candidate_row["summary"] or "").strip() or "暂无摘要。",
            ]
        )
        if overview:
            blocks.extend(["", "大周对文章本身的概述：", overview])
        if recommendation_reasons:
            blocks.extend(["", "为什么这篇内容值得看："])
            blocks.extend(f"{index + 1}. {item}" for index, item in enumerate(recommendation_reasons[:4]))
        if key_points:
            blocks.extend(["", "核心观点："])
            blocks.extend(f"{index + 1}. {item}" for index, item in enumerate(key_points[:6]))
        if editorial_note:
            blocks.extend(["", "大周前哨判断：", editorial_note])
        if writing_angles:
            blocks.extend(["", "可继续展开成文的角度："])
            blocks.extend(f"{index + 1}. {item}" for index, item in enumerate(writing_angles[:4]))
        if discussion_prompts:
            blocks.extend(["", "原本建议继续追问的问题："])
            blocks.extend(f"{index + 1}. {item}" for index, item in enumerate(discussion_prompts[:4]))
        if source_excerpt.strip():
            blocks.extend(["", "原文关键摘录：", source_excerpt.strip()[:2800]])
        if history:
            blocks.extend(["", "已发生的对话："])
            for item in history[-8:]:
                speaker = "用户" if item.role == "user" else "大周"
                content = re.sub(r"\s+", " ", item.content.strip())[:500]
                if content:
                    blocks.append(f"{speaker}：{content}")
        return "\n".join(part for part in blocks if part is not None).strip()

    def prefetch_topic_candidate_insight(candidate_id: str) -> None:
        row = state.db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,))
        if not row:
            return
        update_topic_candidate_insight_state(candidate_id, "pending")
        try:
            ensure_topic_candidate_insight(row)
        except Exception as error:
            update_topic_candidate_insight_state(candidate_id, "failed", error=str(error)[:240])
            log_activity(
                "topic.candidate.insight.prefetch_failed",
                "topic_candidate",
                candidate_id,
                {"error": str(error)[:240]},
            )

    def schedule_topic_candidate_insight(candidate_id: str) -> None:
        if os.getenv("PYTEST_CURRENT_TEST"):
            prefetch_topic_candidate_insight(candidate_id)
            return
        if state.topic_insight_executor is None:
            prefetch_topic_candidate_insight(candidate_id)
            return
        state.topic_insight_executor.submit(prefetch_topic_candidate_insight, candidate_id)

    def create_topic_candidate_record(
        *,
        radar_id: str,
        title: str,
        summary: str,
        source: str,
        status: str,
        source_url: str | None = None,
        published_at: str | None = None,
        capture_method: str = "manual",
        captured_by: str | None = None,
    ) -> TopicCandidateRecord:
        candidate_id = new_id("cand")
        created_at = now_iso()
        state.db.execute(
            """
            INSERT INTO topic_candidates(
                id, radar_id, title, summary, source, source_url, published_at, capture_method, captured_by, status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                radar_id,
                title,
                summary,
                source,
                source_url,
                published_at,
                capture_method,
                captured_by,
                status,
                created_at,
                created_at,
            ),
        )
        row = state.db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,))
        assert row is not None
        remember_topic_candidate_seen(
            radar_id=radar_id,
            source_url=source_url,
            title=title,
            source=source,
        )
        schedule_topic_candidate_insight(candidate_id)
        return build_topic_candidate(row)

    def normalize_topic_candidate_source_url(value: str | None) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlparse(raw)
            path = (parsed.path or "").rstrip("/")
            normalized = urlunparse(
                (
                    (parsed.scheme or "https").lower(),
                    parsed.netloc.lower(),
                    path,
                    "",
                    "",
                    "",
                )
            ).strip()
            return normalized or raw.lower()
        except Exception:
            return raw.lower()

    def build_topic_candidate_match_keys(*, source_url: str | None, title: str, source: str) -> tuple[str, str]:
        source_url_key = normalize_topic_candidate_source_url(source_url)
        normalized_title = re.sub(r"\s+", " ", str(title or "").strip()).lower()
        normalized_source = re.sub(r"\s+", " ", str(source or "").strip()).lower()
        title_source_key = f"{normalized_title}||{normalized_source}".strip("|")
        return source_url_key, title_source_key

    def remember_topic_candidate_seen(
        *,
        radar_id: str,
        source_url: str | None,
        title: str,
        source: str,
        deleted_at: str | None = None,
    ) -> None:
        source_url_key, title_source_key = build_topic_candidate_match_keys(
            source_url=source_url,
            title=title,
            source=source,
        )
        if not source_url_key and not title_source_key:
            return
        existing = state.db.fetchone(
            """
            SELECT id
            FROM topic_candidate_seen
            WHERE radar_id = ?
              AND (
                (? <> '' AND source_url_key = ?)
                OR (? <> '' AND title_source_key = ?)
              )
            LIMIT 1
            """,
            (radar_id, source_url_key, source_url_key, title_source_key, title_source_key),
        )
        if existing:
            state.db.execute(
                """
                UPDATE topic_candidate_seen
                SET source_url_key = ?, title_source_key = ?, source_url = ?, title = ?, source = ?, deleted_at = ?
                WHERE id = ?
                """,
                (source_url_key, title_source_key, source_url, title, source, deleted_at, str(existing["id"])),
            )
            return
        state.db.execute(
            """
            INSERT INTO topic_candidate_seen(
                id, radar_id, source_url_key, title_source_key, source_url, title, source, created_at, deleted_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id("seen"), radar_id, source_url_key, title_source_key, source_url, title, source, now_iso(), deleted_at),
        )

    def topic_candidate_already_seen(*, radar_id: str, source_url: str | None, title: str, source: str) -> bool:
        source_url_key, title_source_key = build_topic_candidate_match_keys(
            source_url=source_url,
            title=title,
            source=source,
        )
        existing_candidate = state.db.fetchone(
            """
            SELECT id
            FROM topic_candidates
            WHERE radar_id = ?
              AND (
                (source_url IS NOT NULL AND source_url = ?)
                OR (LOWER(title) = LOWER(?) AND LOWER(source) = LOWER(?))
              )
            LIMIT 1
            """,
            (radar_id, source_url, title, source),
        )
        if existing_candidate is not None:
            return True
        if not source_url_key and not title_source_key:
            return False
        existing = state.db.fetchone(
            """
            SELECT id
            FROM topic_candidate_seen
            WHERE radar_id = ?
              AND (
                (? <> '' AND source_url_key = ?)
                OR (? <> '' AND title_source_key = ?)
              )
            LIMIT 1
            """,
            (radar_id, source_url_key, source_url_key, title_source_key, title_source_key),
        )
        return existing is not None

    def capture_topic_radar_internal(radar_row) -> TopicCaptureRunRecord:
        capture_limit = 5
        preferred_sources = parse_topic_radar_preferred_sources(radar_row["preferred_sources_json"])
        hits = fetch_topic_candidates_from_web(
            state.ai,
            radar_title=str(radar_row["title"]),
            radar_prompt=str(radar_row["prompt"]),
            time_range=str(radar_row["time_range"]),
            preferred_source_urls=[item.url for item in preferred_sources],
            max_items=capture_limit,
        )

        created_candidates: list[TopicCandidateRecord] = []
        skipped_count = 0
        query = hits[0].query if hits else ""

        for hit in hits:
            if len(created_candidates) >= capture_limit:
                break
            localized = state.ai.localize_topic_hit(
                title=hit.title,
                summary=hit.summary,
                radar_title=str(radar_row["title"]),
                radar_prompt=str(radar_row["prompt"]),
            )
            normalized_title = str(localized.get("title") or hit.title).strip()
            normalized_summary = str(localized.get("summary") or hit.summary).strip()
            if topic_candidate_already_seen(
                radar_id=str(radar_row["id"]),
                source_url=hit.source_url,
                title=normalized_title,
                source=hit.source,
            ):
                skipped_count += 1
                continue
            created_candidates.append(
                create_topic_candidate_record(
                    radar_id=str(radar_row["id"]),
                    title=normalized_title,
                    summary=normalized_summary,
                    source=hit.source,
                    status="tracking",
                    source_url=hit.source_url,
                    published_at=hit.published_at,
                    capture_method="web_search",
                    captured_by="大周",
                )
            )

        log_activity(
            "topic.radar.capture",
            "topic_radar",
            str(radar_row["id"]),
            {
                "radarTitle": str(radar_row["title"]),
                "query": query,
                "fetchedCount": len(hits),
                "createdCount": len(created_candidates),
                "skippedCount": skipped_count,
            },
        )
        return TopicCaptureRunRecord(
            radarId=str(radar_row["id"]),
            radarTitle=str(radar_row["title"]),
            query=query,
            fetchedCount=len(hits),
            createdCount=len(created_candidates),
            skippedCount=skipped_count,
            candidates=created_candidates,
        )

    @app.get("/api/v1/topics", response_model=TopicsResponse)
    def list_topics() -> TopicsResponse:
        radars = [build_topic_radar(row) for row in state.db.fetchall("SELECT * FROM topic_radars ORDER BY created_at ASC")]
        return TopicsResponse(radars=radars, candidates=fetch_topic_candidates())

    @app.post("/api/v1/topics/radars", response_model=TopicRadarRecord)
    def create_radar(payload: TopicRadarPayload) -> TopicRadarRecord:
        radar_id = new_id("radar")
        created_at = now_iso()
        preferred_sources = normalize_topic_radar_preferred_sources(payload.preferredSources)
        state.db.execute(
            "INSERT INTO topic_radars(id, title, prompt, time_range, preferred_sources_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
            (radar_id, payload.title, payload.prompt, payload.timeRange, to_json([item.model_dump() for item in preferred_sources]), created_at),
        )
        log_activity("topic.radar.create", "topic_radar", radar_id, payload.model_dump())
        return TopicRadarRecord(
            id=radar_id,
            title=payload.title,
            prompt=payload.prompt,
            timeRange=payload.timeRange,
            preferredSources=preferred_sources,
            createdAt=created_at,
        )

    @app.put("/api/v1/topics/radars/{radar_id}", response_model=TopicRadarRecord)
    def update_radar(radar_id: str, payload: TopicRadarPayload) -> TopicRadarRecord:
        row = state.db.fetchone("SELECT * FROM topic_radars WHERE id = ?", (radar_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Radar not found")
        preferred_sources = normalize_topic_radar_preferred_sources(payload.preferredSources)
        state.db.execute(
            "UPDATE topic_radars SET title = ?, prompt = ?, time_range = ?, preferred_sources_json = ? WHERE id = ?",
            (payload.title, payload.prompt, payload.timeRange, to_json([item.model_dump() for item in preferred_sources]), radar_id),
        )
        log_activity("topic.radar.update", "topic_radar", radar_id, payload.model_dump())
        return TopicRadarRecord(
            id=radar_id,
            title=payload.title,
            prompt=payload.prompt,
            timeRange=payload.timeRange,
            preferredSources=preferred_sources,
            createdAt=str(row["created_at"]),
        )

    @app.post("/api/v1/topics/radars/generate-title", response_model=TitleSuggestionResponse)
    def generate_radar_title(payload: TopicTitlePayload) -> TitleSuggestionResponse:
        return TitleSuggestionResponse(title=state.ai.suggest_short_title(payload.prompt))

    @app.post("/api/v1/topics/radars/source-label", response_model=TopicRadarSourceLabelResponse)
    def suggest_radar_source_label(payload: TopicRadarSourceLabelPayload) -> TopicRadarSourceLabelResponse:
        normalized_url = normalize_topic_radar_source_url(payload.url)
        return TopicRadarSourceLabelResponse(url=normalized_url, label=suggest_topic_radar_source_label(normalized_url))

    def _build_assisted_radar_prompt(*, prompt: str, title: str, queries: list[str], time_range: str) -> str:
        cleaned_prompt = prompt.strip()
        window_label = {
            "1_day": "近 1 天",
            "3_days": "近 3 天",
            "7_days": "近 7 天",
            "30_days": "近 30 天",
        }.get(time_range, "最近一周")
        query_text = "、".join(f"“{item}”" for item in queries[:3] if item.strip())
        focus_title = title.strip() or "这个主题"
        guidance = (
            f"重点追踪 {focus_title} 在 {window_label} 内的最新动态，优先留意政策发布、项目案例、方法总结、争议讨论与行业信号，"
            "并在整理时明确发布时间、适用场景、关键数据、执行门槛、涉及机构与可复用做法。"
        )
        if query_text:
            guidance = f"{guidance} 可优先使用 {query_text} 这些搜索表达。"
        return f"{cleaned_prompt}\n\n{guidance}".strip()

    @app.post("/api/v1/topics/radars/assist", response_model=TopicRadarAssistResponse)
    def assist_radar_draft(payload: TopicRadarAssistPayload) -> TopicRadarAssistResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")
        title = state.ai.suggest_short_title(prompt)
        queries = state.ai.suggest_topic_search_queries(title=title, prompt=prompt, time_range=payload.timeRange)
        assisted_prompt = _build_assisted_radar_prompt(prompt=prompt, title=title, queries=queries, time_range=payload.timeRange)
        return TopicRadarAssistResponse(title=title, prompt=assisted_prompt, queries=queries)

    @app.post("/api/v1/topics/candidates", response_model=TopicCandidateRecord)
    def create_candidate(payload: TopicCandidatePayload) -> TopicCandidateRecord:
        if not state.db.fetchone("SELECT 1 FROM topic_radars WHERE id = ?", (payload.radarId,)):
            raise HTTPException(status_code=404, detail="Radar not found")
        created = create_topic_candidate_record(
            radar_id=payload.radarId,
            title=payload.title,
            summary=payload.summary,
            source=payload.source,
            status="candidate",
        )
        log_activity("topic.candidate.create", "topic_candidate", created.id, payload.model_dump())
        return created

    @app.post("/api/v1/topics/candidates/{candidate_id}/insights", response_model=TopicCandidateInsightRecord)
    def get_candidate_insights(candidate_id: str) -> TopicCandidateInsightRecord:
        row = state.db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        if str(row["insight_status"] or "pending") != "ready":
            raise HTTPException(status_code=409, detail="候选解析尚未完成")
        insight, _ = ensure_topic_candidate_insight(row)
        return insight

    @app.post("/api/v1/topics/candidates/{candidate_id}/chat", response_model=TopicCandidateChatResponse)
    def chat_with_topic_candidate(candidate_id: str, payload: TopicCandidateChatPayload) -> TopicCandidateChatResponse:
        row = state.db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="问题不能为空")

        radar_row = state.db.fetchone("SELECT * FROM topic_radars WHERE id = ?", (str(row["radar_id"]),))
        radar_title = str(radar_row["title"]) if radar_row else "未命名雷达"

        insight: TopicCandidateInsightRecord | None = None
        source_excerpt = ""
        try:
            insight, source_excerpt = ensure_topic_candidate_insight(row)
        except Exception:
            cached = state.db.fetchone("SELECT * FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,))
            if cached:
                insight = build_topic_candidate_insight(cached)
                source_excerpt = str(cached["source_excerpt"] or "")

        context_summary = build_topic_candidate_chat_context(
            candidate_row=row,
            radar_title=radar_title,
            insight=insight,
            source_excerpt=source_excerpt,
            history=payload.history,
        )
        system_instruction = (
            "你是资讯情报站里的大周。"
            "你现在只围绕当前这篇情报继续回答问题。"
            "回答时优先基于这篇新闻本身、大周已有的解析和原文摘录，不要脱离当前材料泛泛而谈。"
            "你可以做更高层的判断，但不要编造当前材料里没有出现过的具体事实、数据、人名或时间。"
            "如果用户的问题已经超出当前材料，就直接说明材料还不够，并指出下一步该补什么信息。"
            "请用中文直接回答，不要解释系统过程，不要输出 JSON。"
        )
        try:
            structured = state.ai.generate_topic_candidate_chat_response(question, system_instruction, context_summary)
        except AiInvocationError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

        answer = structured.content.strip() or structured.analysis.strip() or structured.judgment.strip()
        if not answer:
            answer = "我暂时还没法基于这篇情报给出稳定回答，建议先点开原文再继续追问。"
        generated_at = now_iso()
        message = TopicCandidateChatMessageRecord(role="assistant", content=answer, createdAt=generated_at)
        log_activity(
            "topic.candidate.chat",
            "topic_candidate",
            candidate_id,
            {
                "questionLength": len(question),
                "answerLength": len(answer),
            },
        )
        return TopicCandidateChatResponse(
            candidateId=candidate_id,
            question=question,
            answer=answer,
            generatedAt=generated_at,
            message=message,
        )

    @app.post("/api/v1/topics/candidates/{candidate_id}/task-plan", response_model=TopicTaskPlanResponse)
    def build_candidate_task_plan(candidate_id: str) -> TopicTaskPlanResponse:
        row = state.db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        topics_settings = get_topics_settings()
        if topics_settings.requireInsightBeforeActions and str(row["insight_status"] or "pending") != "ready":
            raise HTTPException(status_code=409, detail="候选解析尚未完成")
        insight, source_content = ensure_topic_candidate_insight(row)
        plan = state.ai.build_topic_task_plan(
            candidate_title=str(row["title"]),
            candidate_summary=str(row["summary"]),
            source=str(row["source"]),
            published_at=str(row["published_at"]) if row["published_at"] else None,
            source_url=str(row["source_url"]) if row["source_url"] else None,
            source_content=source_content,
            candidate_insight=insight.model_dump(),
            organization_context=build_organization_dna_context() if topics_settings.useOrgDnaForTaskPlan else "",
        )
        tasks = [
            TopicTaskSuggestionRecord(**task)
            for task in plan.get("tasks", [])
            if isinstance(task, dict)
        ]
        if not tasks:
            fallback_title = str(row["title"])[:60]
            tasks = [
                TopicTaskSuggestionRecord(
                    title=fallback_title,
                    desc=str(row["summary"])[:180],
                    ddl="待确认",
                    note=f"来源：{row['source']}",
                    priority="normal",
                    tags=["资讯机会"],
                )
            ]
        return TopicTaskPlanResponse(
            candidateId=str(row["id"]),
            candidateTitle=str(row["title"]),
            candidateSummary=str(row["summary"]),
            candidateSource=str(row["source"]),
            candidateSourceUrl=str(row["source_url"]) if row["source_url"] else None,
            overview=str(plan.get("overview") or "").strip(),
            tasks=tasks,
        )

    @app.post("/api/v1/topics/candidates/{candidate_id}/promote-tasks", response_model=TopicTaskPromotionResponse)
    def promote_candidate_to_tasks(candidate_id: str, payload: TopicTaskPromotionPayload) -> TopicTaskPromotionResponse:
        row = state.db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        if not payload.tasks:
            raise HTTPException(status_code=400, detail="至少要选择一条任务")
        session_user = get_cached_session_user() if get_cloud_token() else None
        default_owner_name = session_user.fullName if session_user else current_operator_row()["name"]
        created_tasks: list[TaskRecord] = []
        for item in payload.tasks:
            if not item.title.strip():
                continue
            task = create_task(
                TaskPayload(
                    title=item.title.strip(),
                    desc=item.desc.strip(),
                    priority=item.priority,
                    listId=item.listId,
                    dueDate=item.dueDate,
                    ddl=item.ddl.strip() or item.dueDate or "待确认",
                    ownerId=item.ownerId,
                    ownerName=item.ownerName.strip() or default_owner_name,
                    collaboratorIds=item.collaboratorIds,
                    tagIds=item.tagIds,
                    tags=item.tags,
                    sourceType="topic_candidate",
                    sourceId=candidate_id,
                ),
                status="inbox",
            )
            if item.note.strip():
                upsert_task_note(task.id, item.note.strip())
            created_tasks.append(task)
        if not created_tasks:
            raise HTTPException(status_code=400, detail="没有可创建的任务")
        state.db.execute("UPDATE topic_candidates SET status = 'promoted', updated_at = ? WHERE id = ?", (now_iso(), candidate_id))
        log_activity(
            "topic.promote.tasks",
            "topic_candidate",
            candidate_id,
            {
                "taskIds": [task.id for task in created_tasks],
                "count": len(created_tasks),
            },
        )
        return TopicTaskPromotionResponse(tasks=created_tasks, createdCount=len(created_tasks))

    @app.post("/api/v1/topics/capture", response_model=TopicCaptureBatchResponse)
    def capture_all_topic_radars() -> TopicCaptureBatchResponse:
        radar_rows = state.db.fetchall("SELECT * FROM topic_radars ORDER BY created_at ASC")
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(radar_rows)))) as executor:
            runs = list(executor.map(capture_topic_radar_internal, radar_rows))
        return TopicCaptureBatchResponse(
            runs=runs,
            totalCreated=sum(item.createdCount for item in runs),
            totalSkipped=sum(item.skippedCount for item in runs),
        )

    @app.post("/api/v1/topics/candidates/{candidate_id}/promote-task", response_model=TaskRecord)
    def promote_candidate_to_task(candidate_id: str, payload: dict = Body(default_factory=dict)) -> TaskRecord:
        row = state.db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        event_line_id = str(payload.get("eventLineId", "") or _row_value(row, "event_line_id", "") or "").strip() or None
        state.db.execute("UPDATE topic_candidates SET status = 'promoted', updated_at = ? WHERE id = ?", (now_iso(), candidate_id))
        task = create_task(
            TaskPayload(
                title=str(row["title"]),
                desc=str(row["summary"]),
                priority="normal",
                listId="list-0",
                ddl="本周",
                ownerName=current_operator_row()["name"],
                tags=["选题"],
                sourceType="topic_candidate",
                sourceId=candidate_id,
                eventLineId=event_line_id,
            ),
            status="inbox",
        )
        log_activity("topic.promote.task", "topic_candidate", candidate_id, {"taskId": task.id, "eventLineId": event_line_id})
        return task

    @app.delete("/api/v1/topics/candidates/{candidate_id}")
    def delete_topic_candidate(candidate_id: str) -> dict[str, bool]:
        row = state.db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        remember_topic_candidate_seen(
            radar_id=str(row["radar_id"]),
            source_url=str(row["source_url"]) if row["source_url"] else None,
            title=str(row["title"]),
            source=str(row["source"]),
            deleted_at=now_iso(),
        )
        state.db.execute("DELETE FROM topic_candidates WHERE id = ?", (candidate_id,))
        log_activity("topic.candidate.delete", "topic_candidate", candidate_id, {"title": str(row["title"])})
        return {"deleted": True}

    def build_analysis_run_record(row) -> AnalysisRunRecord:
        coach_payload_data = from_json(row["coach_payload_json"], {}) if "coach_payload_json" in row.keys() else {}
        coach_payload = CoachPayload(**coach_payload_data) if coach_payload_data else None
        return AnalysisRunRecord(
            id=str(row["id"]),
            templateId=str(row["template_id"]),
            title=str(row["title"]),
            inputText=str(row["input_text"]),
            output=AiStructuredResponse(**from_json(row["output_json"], {})),
            parentRunId=str(row["parent_run_id"]) if row["parent_run_id"] else None,
            coachPayload=coach_payload,
            createdAt=str(row["created_at"]),
            status=str(row["status"]),  # type: ignore[arg-type]
        )

    def find_previous_analysis_run(run: AnalysisRunRecord) -> AnalysisRunRecord | None:
        if run.parentRunId:
            row = state.db.fetchone("SELECT * FROM analysis_runs WHERE id = ?", (run.parentRunId,))
            if row:
                return build_analysis_run_record(row)
        row = state.db.fetchone(
            "SELECT * FROM analysis_runs WHERE template_id = ? AND id != ? AND created_at < ? ORDER BY created_at DESC LIMIT 1",
            (run.templateId, run.id, run.createdAt),
        )
        if row:
            return build_analysis_run_record(row)
        return None

    @app.get("/api/v1/analysis-tools", response_model=AnalysisToolsResponse)
    def list_analysis_tools() -> AnalysisToolsResponse:
        templates = [
            AnalysisTemplateRecord(
                id=str(row["id"]),
                title=str(row["title"]),
                description=str(row["description"]),
                templateKey=str(row["template_key"]),
            )
            for row in state.db.fetchall("SELECT * FROM analysis_templates ORDER BY created_at ASC")
        ]
        runs = [
            build_analysis_run_record(row)
            for row in state.db.fetchall("SELECT * FROM analysis_runs ORDER BY created_at DESC")
        ]
        return AnalysisToolsResponse(templates=templates, runs=runs)

    @app.post("/api/v1/analysis-tools/runs", response_model=AnalysisRunRecord)
    def run_analysis(payload: AnalysisRunPayload) -> AnalysisRunRecord:
        template = state.db.fetchone("SELECT * FROM analysis_templates WHERE id = ?", (payload.templateId,))
        if not template:
            raise HTTPException(status_code=404, detail="Analysis template not found")
        analysis_settings = get_analysis_workbench_settings()
        if analysis_settings.enabledTemplateIds and payload.templateId not in analysis_settings.enabledTemplateIds:
            raise HTTPException(status_code=403, detail="当前模板已在系统设置中停用")
        mode_id = _extract_mode_from_input(payload.title, payload.inputText)
        active_norms = [
            norm for norm in analysis_settings.orgWritingNorms
            if mode_id in {"platform_fundraising", "monthly_donor", "key_person"}
            and (not norm.modeIds or mode_id in norm.modeIds)
            and (not norm.triggerKeywords or any(keyword and keyword in payload.inputText for keyword in norm.triggerKeywords))
        ]
        org_context = build_organization_dna_context() if analysis_settings.useOrgDna else ""
        norms_context = "\n".join(
            f"- {norm.title}：{norm.instruction}"
            for norm in active_norms[:4]
        )
        output = state.ai.generate_structured(
            payload.inputText,
            f"你是咨询分析助手，请根据模板 {template['title']} 输出结构化结果。",
            "\n\n".join(
                item
                for item in [
                    f"模板说明：{template['description']}",
                    org_context,
                    f"本轮写作规范：\n{norms_context}" if norms_context else "",
                ]
                if item
            ),
        )
        run_id = new_id("run")
        created_at = now_iso()
        coach_payload = _build_coach_payload(
            run_id=run_id,
            output=output,
            title=payload.title,
            input_text=payload.inputText,
            mode_id=mode_id,
            settings=analysis_settings,
        )
        state.db.execute(
            "INSERT INTO analysis_runs(id, template_id, title, input_text, output_json, parent_run_id, coach_payload_json, status, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, 'success', ?)",
            (
                run_id,
                payload.templateId,
                payload.title,
                payload.inputText,
                to_json(output.model_dump()),
                payload.parentRunId,
                to_json(coach_payload.model_dump()),
                created_at,
            ),
        )
        log_activity(
            "analysis.run",
            "analysis_run",
            run_id,
            {"templateId": payload.templateId, "title": payload.title, "parentRunId": payload.parentRunId},
        )
        return AnalysisRunRecord(
            id=run_id,
            templateId=payload.templateId,
            title=payload.title,
            inputText=payload.inputText,
            output=output,
            parentRunId=payload.parentRunId,
            coachPayload=coach_payload,
            createdAt=created_at,
            status="success",
        )

    @app.get("/api/v1/analysis-tools/fundraising/dna", response_model=list[DeepDnaRecord])
    def list_fundraising_deep_dna() -> list[DeepDnaRecord]:
        settings = get_analysis_workbench_settings()
        return settings.deepDnaLibrary

    @app.post("/api/v1/analysis-tools/fundraising/dna", response_model=DeepDnaRecord)
    def upsert_fundraising_deep_dna(payload: DeepDnaRecord) -> DeepDnaRecord:
        ensure_business_settings_editable()
        settings = get_analysis_workbench_settings()
        next_library = [item for item in settings.deepDnaLibrary if item.id != payload.id]
        next_library.append(payload.model_copy(update={"updatedAt": now_iso()}))
        next_settings = save_analysis_workbench_settings(settings.model_copy(update={"deepDnaLibrary": next_library, "updatedAt": now_iso()}))
        saved = next(item for item in next_settings.deepDnaLibrary if item.id == payload.id)
        log_activity("analysis.fundraising_dna.upsert", "analysis_settings", payload.id, {"groupKey": payload.groupKey, "label": payload.label})
        return saved

    @app.post("/api/v1/analysis-tools/fundraising/dna/manual", response_model=DeepDnaRecord)
    def create_fundraising_manual_dna(payload: dict[str, object] = Body(...)) -> DeepDnaRecord:
        ensure_business_settings_editable()
        group_key = str(payload.get("groupKey") or "").strip()
        label = str(payload.get("label") or "").strip()
        if group_key not in {"platform_fundraising", "monthly_donor", "key_person"}:
            raise HTTPException(status_code=400, detail="无效的 Deep DNA 分组。")
        if not label:
            raise HTTPException(status_code=400, detail="请先填写对象名称。")
        content_blocks = [
            f"# 基础身份\n{str(payload.get('identitySummary') or '').strip()}",
            f"# 核心偏好\n{str(payload.get('corePreferencesText') or '').strip()}",
            f"# 支持触发器\n{str(payload.get('supportTriggersText') or '').strip()}",
            f"# 红线与反感点\n{str(payload.get('redFlagsText') or '').strip()}",
            f"# 证据偏好\n{str(payload.get('evidencePreferencesText') or '').strip()}",
            f"# 说话风格\n{str(payload.get('voiceStyleText') or '').strip()}",
            f"# 常问问题\n{str(payload.get('commonQuestionsText') or '').strip()}",
        ]
        record = _build_deep_dna_from_text(
            group_key=group_key,  # type: ignore[arg-type]
            label=label,
            content="\n\n".join(block for block in content_blocks if block.strip()),
            source_kind="manual",
            authorization_status=str(payload.get("authorizationStatus") or "authorized_internal"),  # type: ignore[arg-type]
            status="published",
        )
        return upsert_fundraising_deep_dna(record)

    @app.post("/api/v1/analysis-tools/fundraising/dna/import", response_model=DeepDnaRecord)
    def import_fundraising_dna(payload: dict[str, object] = Body(...)) -> DeepDnaRecord:
        ensure_business_settings_editable()
        group_key = str(payload.get("groupKey") or "").strip()
        label = str(payload.get("label") or "").strip()
        content = str(payload.get("content") or "").strip()
        if group_key not in {"platform_fundraising", "monthly_donor", "key_person"}:
            raise HTTPException(status_code=400, detail="无效的 Deep DNA 分组。")
        if not label or not content:
            raise HTTPException(status_code=400, detail="导入对象档案时需要名称和文档内容。")
        record = _build_deep_dna_from_text(
            group_key=group_key,  # type: ignore[arg-type]
            label=label,
            content=content,
            source_kind="import",
            authorization_status=str(payload.get("authorizationStatus") or "authorized_internal"),  # type: ignore[arg-type]
            file_name=str(payload.get("fileName") or "") or None,
            file_path=str(payload.get("filePath") or "") or None,
            status="published",
        )
        return upsert_fundraising_deep_dna(record)

    @app.post("/api/v1/analysis-tools/fundraising/dna/web-drafts", response_model=DeepDnaDraft)
    def create_fundraising_web_draft(payload: dict[str, object] = Body(...)) -> DeepDnaDraft:
        ensure_business_settings_editable()
        group_key = str(payload.get("groupKey") or "").strip()
        label = str(payload.get("label") or "").strip()
        search_query = str(payload.get("searchQuery") or label).strip()
        if group_key not in {"platform_fundraising", "monthly_donor", "key_person"}:
            raise HTTPException(status_code=400, detail="无效的 Deep DNA 分组。")
        if not label or not search_query:
            raise HTTPException(status_code=400, detail="请先填写对象名称和联网检索描述。")
        hits = fetch_topic_candidates_from_web(
            state.ai,
            radar_title=label,
            radar_prompt=search_query,
            time_range="14_days",
            max_items=3,
        )
        if not hits:
            raise HTTPException(status_code=502, detail="这次联网没有抓到足够可用的公开资料，请换一个更具体的检索描述。")
        source_records: list[DeepDnaSourceRecord] = []
        content_parts: list[str] = []
        for hit in hits[:3]:
            excerpt = fetch_topic_source_excerpt(hit.source_url) or hit.summary
            source_records.append(
                DeepDnaSourceRecord(
                    id=new_id("dna_src"),
                    kind="web",
                    title=hit.title,
                    excerpt=excerpt[:420],
                    sourceUrl=hit.source_url,
                    createdAt=now_iso(),
                )
            )
            content_parts.append(
                "\n".join(
                    [
                        f"来源标题：{hit.title}",
                        f"来源摘要：{hit.summary}",
                        f"来源摘录：{excerpt[:1600]}",
                    ]
                )
            )
        draft_record = _build_deep_dna_from_text(
            group_key=group_key,  # type: ignore[arg-type]
            label=label,
            content="\n\n".join(content_parts),
            source_kind="web",
            authorization_status="public",
            search_query=search_query,
            status="draft",
        ).model_copy(update={"sources": source_records})
        settings = get_analysis_workbench_settings()
        next_library = [item for item in settings.deepDnaLibrary if item.id != draft_record.id]
        next_library.append(draft_record)
        save_analysis_workbench_settings(settings.model_copy(update={"deepDnaLibrary": next_library, "updatedAt": now_iso()}))
        return DeepDnaDraft(
            id=draft_record.id,
            groupKey=draft_record.groupKey,
            label=draft_record.label,
            searchQuery=search_query,
            draftRecord=draft_record,
            previewSources=source_records,
            createdAt=draft_record.createdAt,
            updatedAt=draft_record.updatedAt,
        )

    @app.post("/api/v1/analysis-tools/fundraising/dna/{dna_id}/publish", response_model=DeepDnaRecord)
    def publish_fundraising_dna(dna_id: str) -> DeepDnaRecord:
        ensure_business_settings_editable()
        settings = get_analysis_workbench_settings()
        target = next((item for item in settings.deepDnaLibrary if item.id == dna_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Deep DNA 草稿不存在。")
        published = target.model_copy(update={"status": "published", "updatedAt": now_iso()})
        next_library = [item for item in settings.deepDnaLibrary if item.id != dna_id]
        next_library.append(published)
        next_settings = save_analysis_workbench_settings(settings.model_copy(update={"deepDnaLibrary": next_library, "updatedAt": now_iso()}))
        saved = next(item for item in next_settings.deepDnaLibrary if item.id == dna_id)
        log_activity("analysis.fundraising_dna.publish", "analysis_settings", dna_id, {"label": saved.label})
        return saved

    @app.get("/api/v1/analysis-tools/fundraising/cases", response_model=list[CoachCaseRecord])
    def list_fundraising_cases() -> list[CoachCaseRecord]:
        settings = get_analysis_workbench_settings()
        return [*_system_coach_cases(), *settings.coachCaseLibrary]

    @app.post("/api/v1/analysis-tools/fundraising/cases", response_model=CoachCaseRecord)
    def upsert_fundraising_case(payload: CoachCaseRecord) -> CoachCaseRecord:
        ensure_business_settings_editable()
        settings = get_analysis_workbench_settings()
        next_library = [item for item in settings.coachCaseLibrary if item.id != payload.id]
        next_library.append(payload.model_copy(update={"sourceType": "organization", "updatedAt": now_iso()}))
        next_settings = save_analysis_workbench_settings(settings.model_copy(update={"coachCaseLibrary": next_library, "updatedAt": now_iso()}))
        saved = next(item for item in next_settings.coachCaseLibrary if item.id == payload.id)
        log_activity("analysis.fundraising_case.upsert", "analysis_settings", saved.id, {"title": saved.title})
        return saved

    @app.get("/api/v1/analysis-tools/fundraising/reminders", response_model=list[CoachReminderRule])
    def list_fundraising_reminders() -> list[CoachReminderRule]:
        return get_analysis_workbench_settings().coachReminderRules

    @app.post("/api/v1/analysis-tools/fundraising/reminders", response_model=CoachReminderRule)
    def upsert_fundraising_reminder(payload: CoachReminderRule) -> CoachReminderRule:
        ensure_business_settings_editable()
        settings = get_analysis_workbench_settings()
        next_library = [item for item in settings.coachReminderRules if item.id != payload.id]
        next_library.append(payload.model_copy(update={"updatedAt": now_iso()}))
        next_settings = save_analysis_workbench_settings(settings.model_copy(update={"coachReminderRules": next_library, "updatedAt": now_iso()}))
        saved = next(item for item in next_settings.coachReminderRules if item.id == payload.id)
        log_activity("analysis.fundraising_reminder.upsert", "analysis_settings", saved.id, {"title": saved.title})
        return saved

    @app.get("/api/v1/analysis-tools/fundraising/norms", response_model=list[OrgWritingNorm])
    def list_fundraising_norms() -> list[OrgWritingNorm]:
        return get_analysis_workbench_settings().orgWritingNorms

    @app.post("/api/v1/analysis-tools/fundraising/norms", response_model=OrgWritingNorm)
    def upsert_fundraising_norm(payload: OrgWritingNorm) -> OrgWritingNorm:
        ensure_business_settings_editable()
        settings = get_analysis_workbench_settings()
        next_library = [item for item in settings.orgWritingNorms if item.id != payload.id]
        next_library.append(payload.model_copy(update={"updatedAt": now_iso()}))
        next_settings = save_analysis_workbench_settings(settings.model_copy(update={"orgWritingNorms": next_library, "updatedAt": now_iso()}))
        saved = next(item for item in next_settings.orgWritingNorms if item.id == payload.id)
        log_activity("analysis.fundraising_norm.upsert", "analysis_settings", saved.id, {"title": saved.title})
        return saved

    @app.get("/api/v1/analysis-tools/fundraising/runs/{run_id}/comparison", response_model=RunComparison)
    def get_fundraising_run_comparison(run_id: str) -> RunComparison:
        row = state.db.fetchone("SELECT * FROM analysis_runs WHERE id = ?", (run_id,))
        if not row:
            raise HTTPException(status_code=404, detail="分析记录不存在。")
        current_run = build_analysis_run_record(row)
        previous_run = find_previous_analysis_run(current_run)
        return _build_run_comparison(current_run, previous_run)

    def build_handbook_entry_record(row) -> HandbookEntryRecord:
        client_id = str(row["client_id"]) if row["client_id"] else None
        client_name = None
        if client_id:
            client_row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
            client_name = str(client_row["name"]) if client_row and client_row["name"] else None
        linked_contexts: list[dict[str, object]] = []
        linked_contexts.append({"objectType": "handbook", "objectId": str(row["id"]), "label": str(row["title"]), "subtitle": str(row["source_type"] or ""), "tab": "growth", "statusLabel": ""})
        if row["source_object_id"] and row["source_title"]:
            linked_contexts.append(
                {
                    "objectType": str(row["source_object_type"] or "unknown"),
                    "objectId": str(row["source_object_id"]),
                    "label": str(row["source_title"]),
                    "subtitle": "",
                    "tab": "growth",
                    "statusLabel": "",
                }
            )
        if client_id and client_name:
            linked_contexts.append({"objectType": "client", "objectId": client_id, "label": client_name, "subtitle": "", "tab": "client_workspace", "statusLabel": ""})
        if row["event_line_id"] and row["event_line_name"]:
            linked_contexts.append(
                {
                    "objectType": "event_line",
                    "objectId": str(row["event_line_id"]),
                    "label": str(row["event_line_name"]),
                    "subtitle": str(row["project_stage"] or ""),
                    "tab": "tasks",
                    "statusLabel": "",
                }
            )
        author_name = str(row["author_user_name"]) if "author_user_name" in row.keys() and row["author_user_name"] else None
        author_id = str(row["author_user_id"]) if "author_user_id" in row.keys() and row["author_user_id"] else None
        return HandbookEntryRecord(
            id=str(row["id"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            tags=_parse_json_list(row["tags_json"]),
            sourceType=str(row["source_type"]),
            clientId=client_id,
            clientName=client_name,
            authorUserId=author_id,
            authorUserName=author_name,
            sourceObjectType=str(row["source_object_type"]) if row["source_object_type"] else None,
            sourceObjectId=str(row["source_object_id"]) if row["source_object_id"] else None,
            sourceTitle=str(row["source_title"]) if row["source_title"] else None,
            eventLineId=str(row["event_line_id"]) if row["event_line_id"] else None,
            eventLineName=str(row["event_line_name"]) if row["event_line_name"] else None,
            projectModuleId=str(row["project_module_id"]) if row["project_module_id"] else None,
            projectModuleName=str(row["project_module_name"]) if row["project_module_name"] else None,
            projectFlowId=str(row["project_flow_id"]) if row["project_flow_id"] else None,
            projectFlowName=str(row["project_flow_name"]) if row["project_flow_name"] else None,
            projectStage=str(row["project_stage"]) if row["project_stage"] else None,
            businessCategory=str(row["business_category"]) if row["business_category"] else None,
            abilityKeys=from_json(row["ability_keys_json"], []),
            evidenceRefs=from_json(row["evidence_refs_json"], []),
            contextSummary=str(row["context_summary"] or ""),
            reuseCount=int(row["reuse_count"] or 0),
            lastReusedAt=str(row["last_reused_at"]) if row["last_reused_at"] else None,
            linkedContexts=linked_contexts,
            createdAt=str(row["created_at"]),
        )

    def build_handbook_detail(entry_id: str, user_id: str) -> HandbookEntryDetailRecord:
        row = state.db.fetchone("SELECT * FROM handbook_entries WHERE id = ?", (entry_id,))
        if not row:
            raise HTTPException(status_code=404, detail="成长手册条目不存在")
        entry = build_handbook_entry_record(row)
        related_rows = state.db.fetchall(
            """
            SELECT
                l.*,
                e.reason,
                e.evidence_type,
                e.metadata_json,
                e.contribution_tags_json,
                e.validation_state,
                e.org_contribution_score,
                e.review_id,
                e.task_id,
                e.handbook_entry_id,
                s.source_type,
                s.source_id,
                s.context_json
            FROM xp_ledger l
            INNER JOIN growth_evidence_records e ON e.id = l.evidence_id
            INNER JOIN growth_signal_events s ON s.id = e.signal_id
            WHERE l.user_id = ? AND l.reversed_at IS NULL AND e.handbook_entry_id = ?
            ORDER BY l.created_at DESC
            LIMIT 20
            """,
            (user_id, entry_id),
        )
        from app.services.growth_engine import _build_ledger_entry, _fetch_profile_map

        profile_map = _fetch_profile_map(state.db)
        related_entries = [_build_ledger_entry(profile_map, ledger_row) for ledger_row in related_rows]

        def merge_context_dicts(*items: object) -> dict[str, object]:
            merged: dict[str, object] = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                for key, value in item.items():
                    if key not in merged or merged[key] in (None, "", [], {}):
                        merged[key] = value
            return merged

        def build_context_links(raw_links: object) -> list[GrowthContextLinkRecord]:
            if not isinstance(raw_links, list):
                return []
            links: list[GrowthContextLinkRecord] = []
            for raw in raw_links:
                if not isinstance(raw, dict):
                    continue
                object_type = str(raw.get("objectType") or "").strip()
                object_id = str(raw.get("objectId") or "").strip()
                label = str(raw.get("label") or "").strip()
                if not object_type or not object_id or not label:
                    continue
                links.append(
                    GrowthContextLinkRecord(
                        objectType=object_type,
                        objectId=object_id,
                        label=label,
                        subtitle=str(raw.get("subtitle") or ""),
                        tab=str(raw.get("tab") or ""),
                        statusLabel=str(raw.get("statusLabel") or ""),
                    )
                )
            return links

        def dedupe_context_links(*groups: list[GrowthContextLinkRecord]) -> list[GrowthContextLinkRecord]:
            deduped: list[GrowthContextLinkRecord] = []
            seen: set[tuple[str, str]] = set()
            for group in groups:
                for link in group:
                    key = (link.objectType, link.objectId)
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(link)
            return deduped

        origin_contexts = dedupe_context_links(
            entry.linkedContexts,
            *[ledger_entry.linkedContexts for ledger_entry in related_entries],
        )

        reuse_rows = state.db.fetchall(
            """
            SELECT
                v.*,
                l.delta,
                l.total_xp,
                e.metadata_json,
                s.context_json
            FROM growth_validation_events v
            INNER JOIN growth_evidence_records e ON e.id = v.evidence_id
            INNER JOIN growth_signal_events s ON s.id = e.signal_id
            LEFT JOIN xp_ledger l ON l.evidence_id = e.id AND l.reversed_at IS NULL
            WHERE v.user_id = ? AND e.handbook_entry_id = ? AND v.event_type = 'handbook_reused'
            ORDER BY v.created_at DESC
            """,
            (user_id, entry_id),
        )
        reuse_buckets: dict[str, dict[str, object]] = {}
        for reuse_row in reuse_rows:
            detail = from_json(reuse_row["detail_json"], {})
            metadata = from_json(reuse_row["metadata_json"], {})
            signal_context = from_json(reuse_row["context_json"], {})
            merged_context = merge_context_dicts(signal_context, metadata, detail)
            linked_contexts = build_context_links(detail.get("linkedContexts") if isinstance(detail, dict) else None)
            if not linked_contexts:
                linked_contexts = build_context_links(merged_context.get("linkedContexts"))
            bucket_id = f"{reuse_row['source_type']}::{reuse_row['source_id']}::{reuse_row['created_at']}"
            bucket = reuse_buckets.get(bucket_id)
            if bucket is None:
                source_label = (
                    str(detail.get("sourceLabel") or "").strip()
                    if isinstance(detail, dict)
                    else ""
                )
                if not source_label:
                    source_label = next((item.label for item in linked_contexts if item.label), "").strip()
                if not source_label:
                    source_label = str(reuse_row["source_id"] or "已记录复用").strip()
                bucket = {
                    "id": bucket_id,
                    "sourceType": str(reuse_row["source_type"] or ""),
                    "sourceId": str(reuse_row["source_id"] or ""),
                    "sourceLabel": source_label,
                    "note": str(detail.get("note") or "").strip() if isinstance(detail, dict) else "",
                    "contextSummary": str((detail.get("contextSummary") if isinstance(detail, dict) else "") or merged_context.get("contextSummary") or "").strip(),
                    "gainedXp": 0,
                    "createdAt": str(reuse_row["created_at"]),
                    "linkedContexts": linked_contexts,
                }
                reuse_buckets[bucket_id] = bucket
            bucket["gainedXp"] = int(bucket["gainedXp"]) + int(reuse_row["total_xp"] or reuse_row["delta"] or 0)
            bucket["linkedContexts"] = dedupe_context_links(bucket["linkedContexts"], linked_contexts)  # type: ignore[arg-type]

        reuse_history = [
            HandbookReuseRecord(
                id=str(item["id"]),
                sourceType=str(item["sourceType"]),
                sourceId=str(item["sourceId"]),
                sourceLabel=str(item["sourceLabel"]),
                note=str(item["note"]),
                contextSummary=str(item["contextSummary"]),
                gainedXp=int(item["gainedXp"]),
                createdAt=str(item["createdAt"]),
                linkedContexts=list(item["linkedContexts"]),  # type: ignore[arg-type]
            )
            for item in sorted(
                reuse_buckets.values(),
                key=lambda current: str(current["createdAt"]),
                reverse=True,
            )
        ]

        return HandbookEntryDetailRecord(
            **entry.model_dump(),
            relatedLedgerEntries=related_entries,
            originContexts=origin_contexts,
            reuseHistory=reuse_history,
        )

    def create_handbook_entry(payload: HandbookPayload) -> HandbookEntryRecord:
        handbook_settings = get_handbook_settings()
        if payload.sourceType == "task" and not handbook_settings.allowTaskSource:
            raise HTTPException(status_code=403, detail="当前系统设置禁止从任务沉淀进入成长手册")
        if payload.sourceType == "analysis" and not handbook_settings.allowAnalysisSource:
            raise HTTPException(status_code=403, detail="当前系统设置禁止从分析结论沉淀进入成长手册")
        resolved_tags = payload.tags or handbook_settings.defaultTags

        # ── AI insight quote refinement ────────────────────────────
        refined_title = payload.title
        refined_summary = payload.summary
        try:
            if state.ai is not None:
                result = state.ai.distill_growth_insight_quote(
                    task_title=payload.title,
                    task_desc=payload.summary or "",
                    client_name=payload.clientId or "",
                    event_line_name=payload.eventLineName or "",
                    context_summary=payload.contextSummary or "",
                    evidence_refs=payload.evidenceRefs or [],
                )
                if result.get("quote"):
                    refined_title = result["quote"]
                    # Keep original title in summary for reference
                    if not refined_summary or refined_summary == payload.title:
                        refined_summary = payload.title
        except Exception:
            pass  # Non-critical

        entry_id = new_id("handbook")
        created_at = now_iso()
        state.db.execute(
            """
            INSERT INTO handbook_entries(
                id, title, summary, tags_json, source_type, client_id, source_object_type, source_object_id, source_title,
                event_line_id, event_line_name, project_module_id, project_module_name, project_flow_id, project_flow_name,
                project_stage, business_category, ability_keys_json, evidence_refs_json, context_summary, reuse_count, last_reused_at,
                author_user_id, author_user_name, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?)
            """,
            (
                entry_id,
                refined_title,
                refined_summary,
                to_json(resolved_tags),
                payload.sourceType,
                payload.clientId,
                payload.sourceObjectType,
                payload.sourceObjectId,
                payload.sourceTitle,
                payload.eventLineId,
                payload.eventLineName,
                payload.projectModuleId,
                payload.projectModuleName,
                payload.projectFlowId,
                payload.projectFlowName,
                payload.projectStage,
                payload.businessCategory,
                to_json(payload.abilityKeys),
                to_json(payload.evidenceRefs),
                payload.contextSummary.strip(),
                resolve_growth_actor()[0],
                resolve_growth_actor()[1],
                created_at,
            ),
        )
        row = state.db.fetchone("SELECT * FROM handbook_entries WHERE id = ?", (entry_id,))
        assert row is not None
        return build_handbook_entry_record(row)

    @app.get("/api/v1/handbook", response_model=HandbookResponse)
    def list_handbook() -> HandbookResponse:
        entries = [build_handbook_entry_record(row) for row in state.db.fetchall("SELECT * FROM handbook_entries ORDER BY created_at DESC")]
        return HandbookResponse(entries=entries)

    @app.get("/api/v1/handbook/{entry_id}", response_model=HandbookEntryDetailRecord)
    def get_handbook_entry_detail(entry_id: str) -> HandbookEntryDetailRecord:
        user_id, _user_name = resolve_growth_actor()
        return build_handbook_detail(entry_id, user_id)

    @app.post("/api/v1/handbook", response_model=HandbookEntryRecord)
    def create_handbook(payload: HandbookPayload) -> HandbookEntryRecord:
        entry = create_handbook_entry(payload)
        user_id, user_name = resolve_growth_actor()
        ingest_handbook_codification(state.db, user_id=user_id, user_name=user_name, entry=entry, created_at=entry.createdAt)
        log_activity("handbook.create", "handbook_entry", entry.id, payload.model_dump())
        return entry

    @app.post("/api/v1/growth/enrich-insights")
    def enrich_growth_insights() -> dict:
        """Backfill AI-distilled insight quotes for existing pending captures and handbook entries."""
        if state.ai is None:
            return {"enriched_captures": 0, "enriched_entries": 0, "error": "AI service not available"}
        user_id, _user_name = resolve_growth_actor()
        enriched_captures = 0
        enriched_entries = 0

        # 1. Enrich pending captures that lack insightQuote
        rows = state.db.fetchall(
            """
            SELECT id, context_json, raw_text
            FROM growth_signal_events
            WHERE user_id = ?
              AND source_type IN ('task_context_candidate', 'task_attachment_candidate')
            ORDER BY created_at DESC
            LIMIT 30
            """,
            (user_id,),
        )
        for row in rows:
            context = from_json(row["context_json"], {})
            if not isinstance(context, dict) or context.get("insightQuote"):
                continue
            try:
                result = state.ai.distill_growth_insight_quote(
                    task_title=str(context.get("taskTitle") or ""),
                    task_desc=str(context.get("taskDesc") or ""),
                    client_name=str(context.get("clientName") or ""),
                    event_line_name=str(context.get("eventLineName") or ""),
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
