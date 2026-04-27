# 源码文件：`backend/app/main.py`（分片 07）

- 行号范围：16801-19600
- 总行数：   30416
- 导出时间：2026-04-20

```python
            ),
            actions="可继续重试正式扩写；或直接基于这版简介补问某个项目、会议或下一步动作。",
            timeline="当前处于证据已命中、正式扩写未完成的阶段。",
        )

    def build_meeting_summary_answer_from_evidence(
        prompt: str,
        top_evidence: list[EvidenceItem],
        *,
        failure_detail: str,
    ) -> AiStructuredResponse:
        snippets = _collect_user_facing_fallback_evidence(top_evidence, limit=5)
        focus_lines = [f"- {excerpt}" for _, excerpt in snippets[:2]]
        decision_lines = [f"- {excerpt}" for _, excerpt in snippets[1:3]]
        action_lines = [f"- 基于《{label}》继续跟进：{excerpt}" for label, excerpt in snippets[:2]]
        risk_line = "- 当前仍有部分信息待确认，候选判断不能直接当作正式事实。"
        content = "\n".join(
            [
                f"围绕“{prompt}”，基于已命中资料先给一版可执行会议摘要：",
                "",
                "一、最近会议与讨论重点",
                *(focus_lines or ["- 当前命中材料显示会议主题聚焦推进节奏、协同边界和后续安排。"]),
                "",
                "二、已形成的决定 / 共识",
                *(decision_lines or ["- 已形成阶段性共识，但仍需结合原文与任务状态进一步确认。"]),
                "",
                "三、接下来谁做什么",
                *(action_lines or ["- 建议按会议纪要中的行动项拆解负责人、截止时间和交付标准。"]),
                "",
                "四、风险与待确认",
                risk_line,
                "",
                "引用依据：",
                *[f"{idx}. 《{label}》：{excerpt}" for idx, (label, excerpt) in enumerate(snippets[:4], start=1)],
            ]
        ).strip()
        return AiStructuredResponse(
            content=content,
            judgment="会议类问题已基于原始资料给出简版可执行回答，正式长文扩写本轮未完成。",
            analysis=f"本轮保留了会议问题最关键的四段结构（重点/共识/行动/风险），以避免只输出证据清单。\n\n失败详情：{failure_detail}",
            actions="可在同一问题上继续重试扩写，或直接追问“负责人与截止时间”。",
            timeline="当前可继续沿这版会议摘要推进。",
        )

    def build_next_actions_answer_from_workspace(
        prompt: str,
        top_evidence: list[EvidenceItem],
        *,
        state_answer_sections: StateAnswerSectionsRecord | None = None,
        failure_detail: str,
    ) -> AiStructuredResponse:
        snippets = _collect_user_facing_fallback_evidence(top_evidence, limit=4)
        explicit_actions = list(state_answer_sections.actions[:3]) if state_answer_sections else []
        if not explicit_actions:
            explicit_actions = [f"基于《{label}》推进：{excerpt}" for label, excerpt in snippets[:2]]
        need_more_evidence = list(state_answer_sections.unknowns[:3]) if state_answer_sections else []
        if not need_more_evidence:
            need_more_evidence = [
                "补齐负责人与截止时间，避免“下一步”停留在方向层。",
                "补齐对应原文出处，确保行动项能被追溯验证。",
            ]
        candidate_reminders: list[str] = []
        if state_answer_sections:
            candidate_reminders.extend(state_answer_sections.candidate[:2])
            candidate_reminders.extend(state_answer_sections.risks[:2])
        if not candidate_reminders:
            candidate_reminders = ["当前仍存在候选提醒与风险信号，需要与原文和任务状态交叉确认。"]
        content = "\n".join(
            [
                f"围绕“{prompt}”，当前下一步可以先按三类拆分：",
                "",
                "一、已经比较明确的行动",
                *[f"- {item}" for item in explicit_actions],
                "",
                "二、需要先补证据 / 补沟通的信息",
                *[f"- {item}" for item in need_more_evidence],
                "",
                "三、系统里的候选提醒（暂不当成确定事实）",
                *[f"- {item}" for item in candidate_reminders],
                "",
                "引用依据：",
                *[f"{idx}. 《{label}》：{excerpt}" for idx, (label, excerpt) in enumerate(snippets[:4], start=1)],
            ]
        ).strip()
        return AiStructuredResponse(
            content=content,
            judgment="下一步类问题已降级为可执行短答：明确行动、待补证据与候选提醒三段并行。",
            analysis=f"本轮把任务/会议/风险边界拆开呈现，避免将候选判断误写成正式事实。\n\n失败详情：{failure_detail}",
            actions="建议先完成“明确行动”中的前两项，再补齐证据缺口后回写正式判断。",
            timeline="当前可直接按三段结构执行与跟踪。",
        )

    def build_local_retrieval_fallback(
        client_id: str,
        prompt: str,
        evidence: list[EvidenceItem],
        retrieval_bundle,
        failure_detail: str,
        *,
        answer_intent: WorkspaceAnswerIntent | None = None,
        state_answer_sections: StateAnswerSectionsRecord | None = None,
        workspace_state_context: str = "",
    ) -> AiStructuredResponse:
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
        preferred_categories = [
            str(item)
            for item in retrieval_meta.get("preferredCategories", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("preferredCategories"), list) else []
        top_evidence = select_high_signal_evidence(
            evidence,
            limit=6,
            prompt=prompt,
            preferred_categories=preferred_categories,
        )
        if not top_evidence:
            return AiStructuredResponse(
                content="正式长回答阶段没有成功完成，当前也缺少可用于兜底的原始证据。",
                judgment="这次回答没有拿到足够的原始证据来组织一版可靠兜底稿。",
                analysis=f"错误信息：{failure_detail}",
                actions="建议直接重试；如果反复失败，请检查本地 AI 配置与当前证据链路。",
                timeline="恢复后可立即重新生成。",
            )
        _ = workspace_state_context
        resolved_intent = answer_intent or classify_workspace_chat_intent(prompt)
        if resolved_intent in {"intro_profile", "project_intro"}:
            return build_intro_profile_answer_from_evidence(
                client_id,
                prompt,
                top_evidence,
                failure_detail=failure_detail,
            )
        if resolved_intent == "meeting_summary":
            return build_meeting_summary_answer_from_evidence(
                prompt,
                top_evidence,
                failure_detail=failure_detail,
            )
        if resolved_intent == "next_actions":
            return build_next_actions_answer_from_workspace(
                prompt,
                top_evidence,
                state_answer_sections=state_answer_sections,
                failure_detail=failure_detail,
            )
        content = build_compact_user_fallback_content(client_id, prompt, top_evidence)
        judgment = (
            "当前已经命中一批可用于机构介绍的原始资料，可以先形成一版简要介绍；正式长文稿暂未完成。"
            if is_intro_profile_query(prompt)
            else "当前已经命中一批高信号原始资料，可以先形成一版简要判断；正式长文稿暂未完成。"
        )
        analysis = (
            "正式长回答没有完整完成，当前已自动降级为面向用户的简版资料回答，"
            "优先保留高信号原始资料，避免把内部组织过程或原始观察清单直接暴露给用户。"
            f"\n\n失败详情：{failure_detail}"
        )
        actions = "建议继续在同一问题上重试正式生成，或围绕这里保留下来的关键资料继续追问。"
        timeline = "当前处于证据已就位、正式成文未完成的状态。"
        return AiStructuredResponse(
            content=content,
            judgment=judgment,
            analysis=analysis,
            actions=actions,
            timeline=timeline,
        )

    def should_force_stable_fallback_path(client_id: str, answer_intent: WorkspaceAnswerIntent | None) -> bool:
        if answer_intent not in {"intro_profile", "project_intro", "meeting_summary", "next_actions"}:
            return False
        row = state.db.fetchone(
            """
            SELECT COUNT(1) AS fallback_count
            FROM (
                SELECT m.failure_reason
                FROM chat_messages m
                JOIN chat_threads t ON t.id = m.thread_id
                WHERE t.client_id = ? AND m.role = 'assistant'
                ORDER BY m.created_at DESC
                LIMIT 6
            ) recent
            WHERE failure_reason = 'llm_local_fallback_after_retry'
            """,
            (client_id,),
        )
        fallback_count = int(row["fallback_count"] or 0) if row else 0
        return fallback_count >= 3

    def build_partial_generation_fallback(
        prompt: str,
        partial_content: str,
        failure_detail: str,
        *,
        partial_structured: dict[str, object] | None = None,
    ) -> AiStructuredResponse:
        cleaned_content = partial_content.strip()
        if not cleaned_content:
            return AiStructuredResponse(
                content="正式成文阶段没有完整完成，当前也没有保留到足够可读的已生成正文。",
                judgment="这次回答进入了成文阶段，但没有留下可直接交付的部分正文。",
                analysis=f"错误信息：{failure_detail}",
                actions="建议稍后重试，或把问题拆小后继续追问。",
                timeline="恢复后可立即重新扩写。",
            )
        note = "注：后续扩写阶段未完整完成，当前先保留已生成的核心正文。"
        if note not in cleaned_content:
            cleaned_content = f"{cleaned_content}\n\n{note}"
        payload = partial_structured if isinstance(partial_structured, dict) else {}
        judgment = str(payload.get("judgment") or "").strip() or "当前已经生成一版可读的核心判断，但后续扩写阶段没有完整完成。"
        analysis = str(payload.get("analysis") or "").strip()
        actions = str(payload.get("actions") or "").strip() or "建议围绕当前已生成正文继续追问，或稍后重试扩写。"
        if analysis:
            analysis = f"{analysis}\n\n后续扩写失败详情：{failure_detail}"
        else:
            analysis = (
                "这次回答已经保留了前面成功生成的正文，失败发生在后续主体扩写或建议动作阶段。"
                "为避免旧兜底稿覆盖当前判断，系统当前会优先保留这版正文。"
                f"\n\n失败详情：{failure_detail}"
            )
        return AiStructuredResponse(
            content=cleaned_content,
            judgment=judgment,
            analysis=analysis,
            actions=actions,
            timeline="当前处于部分成文已完成、后续扩写未完成的状态。",
        )

    def determine_chat_fallback_presentation_mode(
        *,
        answer_mode: str,
        state_only_primary: bool,
        judgment_query_mode: str | None,
        partial_generation_preserved: bool,
        identity_role_insufficient: bool,
        compact_model_fallback_used: bool,
        local_fallback_used: bool,
    ) -> Literal["state_cards_only", "compact_user_answer", "full_answer"]:
        if answer_mode != "grounded_fallback":
            return "full_answer"
        if partial_generation_preserved or identity_role_insufficient:
            return "full_answer"
        if state_only_primary or judgment_query_mode in {"hybrid", "evidence_based_synthesis"}:
            return "state_cards_only"
        if compact_model_fallback_used or local_fallback_used:
            return "compact_user_answer"
        return "full_answer"

    def _scrub_compact_user_fallback_text(text: str) -> str:
        cleaned_lines: list[str] = []
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line:
                if cleaned_lines and cleaned_lines[-1]:
                    cleaned_lines.append("")
                continue
            line_lower = line.lower()
            if any(marker.lower() in line_lower for marker in FALLBACK_INTERNAL_TEXT_MARKERS):
                continue
            if any(marker.lower() in line_lower for marker in PPT_WPS_NOISE_HINTS):
                continue
            if re.fullmatch(r"\[[^\]]+\]", line):
                continue
            cleaned_lines.append(line)
        text = "\n".join(cleaned_lines).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def apply_chat_fallback_presentation_guard(
        structured: AiStructuredResponse,
        *,
        presentation_mode: Literal["state_cards_only", "compact_user_answer", "full_answer"],
        client_id: str,
        prompt: str,
        evidence: list[EvidenceItem],
        retrieval_bundle,
        answer_intent: WorkspaceAnswerIntent | None = None,
        state_answer_sections: StateAnswerSectionsRecord | None = None,
    ) -> AiStructuredResponse:
        content = str(structured.content or "").strip()
        if presentation_mode == "full_answer":
            return structured
        if presentation_mode == "state_cards_only":
            if fallback_text_contains_internal_markers(content) or fallback_text_contains_visual_noise(content):
                return structured.model_copy(update={"content": ""})
            return structured
        scrubbed = _scrub_compact_user_fallback_text(content)
        if (
            not scrubbed
            or fallback_text_contains_internal_markers(scrubbed)
            or fallback_text_contains_visual_noise(scrubbed)
        ):
            return build_local_retrieval_fallback(
                client_id,
                prompt,
                evidence,
                retrieval_bundle,
                failure_detail="用户态质量闸门触发重组",
                answer_intent=answer_intent,
                state_answer_sections=state_answer_sections,
            )
        if scrubbed == content:
            return structured
        return structured.model_copy(update={"content": scrubbed})

    def build_compact_grounded_note(client_id: str, prompt: str, evidence: list[EvidenceItem], retrieval_bundle) -> str:
        client = build_client_summary(client_id)
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
        preferred_categories = [
            str(item)
            for item in retrieval_meta.get("preferredCategories", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("preferredCategories"), list) else []
        curated_evidence = select_high_signal_evidence(
            evidence,
            limit=8,
            prompt=prompt,
            preferred_categories=preferred_categories,
        )
        summary_lines = [
            f"客户：{client.name}",
            f"问题：{prompt}",
            f"当前已命中证据数：{len(curated_evidence)}",
            "以下是已经命中的原始证据，请基于这些证据快速组织一版完整回答：",
        ]
        for index, item in enumerate(curated_evidence, start=1):
            label = item.title
            if item.sectionLabel:
                label = f"{label} / {item.sectionLabel}"
            compact_excerpt = re.sub(r"\s+", " ", item.excerpt or "").strip()[:220]
            summary_lines.append(f"[证据{index}] {label}\n{compact_excerpt}")
        return "\n\n".join(summary_lines)[:2600]

    def upsert_task_note(task_id: str, note: str) -> None:
        table_name = "task_notes" if state.db.fetchone("SELECT 1 FROM tasks WHERE id = ?", (task_id,)) else "task_notes_cloud"
        existing = state.db.fetchone(f"SELECT id FROM {table_name} WHERE task_id = ?", (task_id,))
        timestamp = now_iso()
        if existing:
            state.db.execute(
                f"UPDATE {table_name} SET note = ?, updated_at = ? WHERE task_id = ?",
                (note, timestamp, task_id),
            )
        else:
            state.db.execute(
                f"INSERT INTO {table_name}(id, task_id, note, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
                (new_id("tn"), task_id, note, timestamp, timestamp),
            )

    def _ensure_local_task_list(list_id: str) -> str:
        """Ensure a task list exists locally. For cloud lists, create a local mirror if missing."""
        row = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (list_id,))
        if row and not row["archived_at"]:
            return list_id
        fallback_id = _get_local_task_settings().defaultListId or "list-0"
        fallback_row = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (fallback_id,))
        if fallback_row and not fallback_row["archived_at"]:
            return fallback_id
        # Create a catch-all list so we never fail
        state.db.execute(
            "INSERT OR IGNORE INTO task_lists(id, name, color, sort_order, is_default, scope, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            ("list-0", "收集箱", "#5B7BFE", 0, 1, "personal", now_iso(), now_iso()),
        )
        return "list-0"

    def _try_cloud_sync_task(task_id: str, cloud_payload: dict) -> None:
        """Try to push a locally-saved task to cloud. Non-blocking: updates sync_status on result."""
        try:
            response = cloud_request("POST", "/api/v1/tasks", json_body=cloud_payload, timeout=6.0)
            if isinstance(response, dict) and response.get("id"):
                cloud_id = str(response["id"])
                state.db.execute(
                    "UPDATE tasks SET sync_status = 'synced', cloud_id = ?, cloud_payload_json = NULL WHERE id = ?",
                    (cloud_id, task_id),
                )
                _cloud_task_board_cache["data"] = None  # invalidate cache
            else:
                state.db.execute("UPDATE tasks SET sync_status = 'pending' WHERE id = ?", (task_id,))
        except Exception:
            state.db.execute("UPDATE tasks SET sync_status = 'pending' WHERE id = ?", (task_id,))

    _last_pending_sync_ts: float = 0.0

    def sync_pending_tasks_if_due() -> int:
        """Retry cloud sync for tasks stuck in 'pending'. Called opportunistically. Returns count synced."""
        nonlocal _last_pending_sync_ts
        import time
        now = time.time()
        if now - _last_pending_sync_ts < 60:
            return 0  # throttle: at most once per minute
        _last_pending_sync_ts = now
        if not get_cloud_token():
            return 0
        pending_rows = state.db.fetchall(
            "SELECT id, cloud_payload_json FROM tasks WHERE sync_status = 'pending' AND cloud_payload_json IS NOT NULL ORDER BY created_at LIMIT 10"
        )
        synced = 0
        for row in pending_rows:
            task_id = str(row["id"])
            try:
                cloud_payload = json.loads(str(row["cloud_payload_json"]))
            except Exception:
                state.db.execute("UPDATE tasks SET sync_status = 'error' WHERE id = ?", (task_id,))
                continue
            try:
                response = cloud_request("POST", "/api/v1/tasks", json_body=cloud_payload, timeout=6.0)
                if isinstance(response, dict) and response.get("id"):
                    state.db.execute(
                        "UPDATE tasks SET sync_status = 'synced', cloud_id = ?, cloud_payload_json = NULL WHERE id = ?",
                        (str(response["id"]), task_id),
                    )
                    synced += 1
            except Exception:
                break  # cloud still down, stop retrying
        if synced:
            _cloud_task_board_cache["data"] = None
        return synced

    def create_task(payload: TaskPayload, status: str = "todo") -> TaskRecord:
        scope_mode = payload.scopeMode or "COLLAB_SHARED"
        requested_client_id = None if scope_mode == "PERSONAL_ONLY" else payload.clientId
        requested_event_line_id = None if scope_mode == "PERSONAL_ONLY" else payload.eventLineId
        normalized_client_id, normalized_event_line_id = _normalize_task_client_and_event_line_refs(
            requested_client_id,
            requested_event_line_id,
        )
        requested_project_module_id = None if scope_mode == "PERSONAL_ONLY" else payload.projectModuleId
        requested_project_flow_id = None if scope_mode == "PERSONAL_ONLY" else payload.projectFlowId
        project_module, project_flow = resolve_project_structure_refs(normalized_client_id, requested_project_module_id, requested_project_flow_id)
        project_context = build_task_project_context(
            normalized_client_id,
            payload.sourceType,
            payload.sourceId,
            task_title=payload.title,
            task_desc=payload.desc,
            project_module_id=project_module.id if project_module else None,
            project_flow_id=project_flow.id if project_flow else None,
        )
        event_line_context = _event_line_snapshot_context(state.db, normalized_event_line_id, None)
        (
            business_category,
            current_blocker,
            next_action,
            recent_decision,
            evidence_count,
        ) = _resolve_task_action_os_fields(
            title=payload.title,
            desc=payload.desc,
            source_type=payload.sourceType,
            business_category=payload.businessCategory,
            current_blocker=payload.currentBlocker,
            next_action=payload.nextAction,
            recent_decision=payload.recentDecision,
            evidence_count=payload.evidenceCount,
            project_context=project_context,
            event_line_context=event_line_context,
            attachment_count=0,
        )

        # --- LOCAL-FIRST: always write to local SQLite first ---
        timestamp = now_iso()
        task_id = new_id("task")
        list_id = _ensure_local_task_list(payload.listId or (_get_local_task_settings().defaultListId or "list-0"))
        resolved_tags = normalize_local_task_tags(payload.tagIds, payload.tags)
        has_cloud = bool(get_cloud_token())
        initial_sync_status = "local" if not has_cloud else "syncing"

        state.db.execute(
            """
            INSERT INTO tasks(
                id, title, description, status, priority, list_id, owner_name, ddl, due_date, duration_minutes, event_line_id, source_type, source_id,
                client_id, project_module_id, project_flow_id, scope_mode, business_category, current_blocker, next_action, recent_decision, evidence_count,
                tags_json, tag_ids_json, sync_status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                payload.title,
                payload.desc,
                status,
                payload.priority,
                list_id,
                payload.ownerName,
                payload.ddl,
                payload.dueDate or normalize_due_date_input(payload.ddl),
                payload.durationMinutes,
                normalized_event_line_id,
                payload.sourceType,
                payload.sourceId,
                normalized_client_id,
                project_module.id if project_module else None,
                project_flow.id if project_flow else None,
                scope_mode,
                business_category,
                current_blocker,
                next_action,
                recent_decision,
                evidence_count,
                to_json([tag.name for tag in resolved_tags]),
                to_json([tag.id for tag in resolved_tags]),
                initial_sync_status,
                timestamp,
                timestamp,
            ),
        )
        if normalized_event_line_id:
            state.db.execute(
                """
                INSERT INTO event_line_activities(
                    id, event_line_id, source_type, source_id, happened_at, actor_id, actor_name, title, summary, metadata_json, is_key
                ) VALUES(?, ?, 'task_activity', ?, ?, NULL, ?, ?, ?, ?, 1)
                """,
                    (
                        new_id("ela"),
                    normalized_event_line_id,
                    task_id,
                    timestamp,
                    payload.ownerName or "",
                    f"新增任务：{payload.title}",
                    (payload.desc or "").strip() or f"创建任务：{payload.title}",
                    to_json({"eventType": "created"}),
                ),
            )
        log_activity("task.create", "task", task_id, payload.model_dump())
        created_task = fetch_tasks("t.id = ?", (task_id,))[0]
        record_task_writeback(
            state.db,
            task_id=created_task.id,
            title=created_task.title,
            description=created_task.desc,
            status=created_task.status,
            due_date=created_task.dueDate,
            client_id=created_task.clientId,
            event_line_id=created_task.eventLineId,
        )
        growth_user_id, growth_user_name = resolve_growth_actor()
        ingest_task_growth_candidate(
            state.db,
            user_id=growth_user_id,
            user_name=growth_user_name,
            task=created_task,
            source_type="task_context_candidate",
            created_at=timestamp,
            ai_service=state.ai,
        )
        Thread(target=_precompute_task_understanding, args=(created_task.id,), daemon=True).start()

        # --- ASYNC CLOUD SYNC: push to cloud in background, never block the user ---
        if has_cloud:
            session_user = get_cached_session_user()
            collaborator_ids = payload.collaboratorIds or ([session_user.id] if session_user else [])
            owner_id = payload.ownerId or (collaborator_ids[0] if collaborator_ids else None)
            cloud_payload = {
                "title": payload.title,
                "description": payload.desc,
                "priority": payload.priority,
                "listId": payload.listId,
                "dueDate": payload.dueDate or normalize_due_date_input(payload.ddl),
                "durationMinutes": payload.durationMinutes,
                "scopeMode": scope_mode,
                "clientId": normalized_client_id,
                "eventLineId": normalized_event_line_id,
                "projectModuleId": project_module.id if project_module else None,
                "projectFlowId": project_flow.id if project_flow else None,
                "collaboratorIds": collaborator_ids,
                "ownerId": owner_id,
                "sourceType": payload.sourceType,
                "sourceId": payload.sourceId,
                "businessCategory": business_category,
                "currentBlocker": current_blocker,
                "nextAction": next_action,
                "recentDecision": recent_decision,
                "evidenceCount": evidence_count,
            }
            # Store cloud payload for retry if initial sync fails
            state.db.execute(
                "UPDATE tasks SET cloud_payload_json = ? WHERE id = ?",
                (to_json(cloud_payload), task_id),
            )
            Thread(target=_try_cloud_sync_task, args=(task_id, cloud_payload), daemon=True).start()

        return created_task

    def extract_meeting_content(text: str) -> tuple[list[str], list[str], list[tuple[str, str, float]], list[tuple[str, str]], list[tuple[str, list[str]]]]:
        sentences = [segment.strip(" -") for segment in re.split(r"[\n。！？!?]+", text) if segment.strip()]
        agenda = sentences[:2] or ["会前目标梳理", "关键问题确认"]
        decisions = [item for item in sentences if "决定" in item or "确定" in item][:3]
        if not decisions and sentences:
            decisions = [f"优先推进：{sentences[0][:24]}"]
        actions = [item for item in sentences if any(keyword in item for keyword in ["负责", "跟进", "行动", "任务", "推进"])][:3]
        if not actions:
            actions = [f"跟进 {item[:20]}" for item in sentences[:2]] or ["补齐会议待办"]
        parsed_actions = [(item, current_operator_row()["name"], 0.84) for item in actions]
        risks = [(item, "high" if any(word in item for word in ["风险", "阻力", "卡点"]) else "normal") for item in sentences if any(word in item for word in ["风险", "阻力", "卡点", "资源", "预算"])]
        ambiguities = [(item, ["待确认责任人", "待确认时间点"]) for item in sentences if any(word in item for word in ["待确认", "待补", "需要再看", "?"])]
        return agenda, decisions, parsed_actions, risks[:3], ambiguities[:3]

    def is_private_task(task: TaskRecord) -> bool:
        return task.scopeMode == "PERSONAL_ONLY" or any(tag.scope == "self" for tag in task.tags)

    def local_review_row_for_week(week_label: str):
        operator_id = str(current_operator_row()["id"])
        return state.db.fetchone(
            "SELECT * FROM weekly_reviews WHERE week_label = ? AND operator_id = ? ORDER BY created_at DESC LIMIT 1",
            (week_label, operator_id),
        )

    def local_review_history() -> ReviewHistoryResponse:
        operator_id = str(current_operator_row()["id"])
        rows = state.db.fetchall(
            """
            SELECT
                r.week_label,
                COALESCE(r.updated_at, r.created_at) AS submitted_at,
                (
                    SELECT COUNT(*)
                    FROM weekly_review_task_entries e
                    WHERE e.review_id = r.id AND e.content_domain = 'work'
                ) AS work_item_count,
                (
                    SELECT COUNT(*)
                    FROM weekly_review_task_entries e
                    WHERE e.review_id = r.id AND e.content_domain = 'personal'
                ) AS personal_item_count
            FROM weekly_reviews r
            WHERE r.operator_id = ?
            ORDER BY COALESCE(r.updated_at, r.created_at) DESC, r.week_label DESC
            """,
            (operator_id,),
        )
        return ReviewHistoryResponse(
            items=[
                ReviewHistoryEntryRecord(
                    weekLabel=str(row["week_label"] or ""),
                    submittedAt=str(row["submitted_at"] or ""),
                    workItemCount=int(row["work_item_count"] or 0),
                    personalItemCount=int(row["personal_item_count"] or 0),
                )
                for row in rows
                if str(row["week_label"] or "").strip()
            ]
        )

    def build_local_review_record(row) -> WeeklyReviewRecord:
        operator = current_operator_row()
        return WeeklyReviewRecord(
            id=str(row["id"]),
            userId=str(operator["id"]),
            userName=str(operator["name"]),
            weekLabel=str(row["week_label"]),
            workFreeNote=str(row["work_free_note"] or row["summary"] or ""),
            personalGrowthNote=str(row["personal_growth_note"] or ""),
            personalPrivateNote=str(row["personal_private_note"] or ""),
            submittedAt=str(row["updated_at"] or row["created_at"]),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"] or row["created_at"]),
        )

    def build_preview_review_record(week_label: str) -> WeeklyReviewRecord:
        operator = current_operator_row()
        timestamp = now_iso()
        return WeeklyReviewRecord(
            id=f"review_preview::{week_label}",
            userId=str(operator["id"]),
            userName=str(operator["name"]),
            weekLabel=week_label,
            workFreeNote="",
            personalGrowthNote="",
            personalPrivateNote="",
            submittedAt=timestamp,
            createdAt=timestamp,
            updatedAt=timestamp,
        )

    def local_review_entries_by_task(review_id: str) -> dict[str, dict[str, object]]:
        rows = state.db.fetchall(
            "SELECT * FROM weekly_review_task_entries WHERE review_id = ? ORDER BY reviewed_at DESC",
            (review_id,),
        )
        return {str(row["task_id"]): dict(row) for row in rows}

    def summarize_local_review_notes(items: list[WeeklyReviewTaskEntryRecord]) -> str:
        if not items:
            return "本周还没有填写任务复盘。"
        issue_keywords = ("卡住", "阻力", "困难", "问题", "风险", "不足")
        harvest_keywords = ("收获", "学到", "发现", "有效", "清楚")
        support_keywords = ("需要支持", "需要帮助", "资源", "协同")
        overload_count = sum(1 for item in items if item.structuredNote.lightweightTag == "工作过度饱和")
        issue_count = sum(
            1
            for item in items
            if item.structuredNote.lightweightTag
            or item.structuredNote.blockerReason
            or any(keyword in item.note for keyword in issue_keywords)
        )
        harvest_count = sum(
            1
            for item in items
            if item.structuredNote.reflection
            or item.structuredNote.successReason
            or item.structuredNote.successExperience
            or any(keyword in item.note for keyword in harvest_keywords)
        )
        support_count = sum(
            1
            for item in items
            if item.structuredNote.lightweightTag
            or item.structuredNote.supportNeeded
            or any(keyword in item.note for keyword in support_keywords)
        )
        insight_count = sum(
            1
            for item in items
            if item.structuredNote.reflection or item.structuredNote.failureInsight or item.structuredNote.blockerReason
        )
        overload_text = f"，其中明确提到工作过度饱和 {overload_count} 次" if overload_count else ""
        return f"共记录 {len(items)} 条任务复盘，其中提到问题/阻力 {issue_count} 次，收获/有效经验 {harvest_count} 次，失败心得 {insight_count} 次，需要支持 {support_count} 次{overload_text}。"

    def current_review_week_label() -> str:
        iso = datetime.now().isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def build_client_business_context_modules(
        work_items: list[WeeklyReviewTaskEntryRecord],
    ) -> list[OrganizationDnaModuleRecord]:
        discovered_client_ids: list[str] = []
        seen_client_ids: set[str] = set()
        for item in work_items:
            task_rows = fetch_tasks("t.id = ?", (item.taskId,))
            if not task_rows:
                continue
            task = task_rows[0]
            source_id = (task.sourceId or "").strip()
            source_type = (task.sourceType or "").strip()
            client_id: str | None = (task.clientId or "").strip() or None
            if source_type == "meeting" and source_id:
                row = state.db.fetchone("SELECT client_id FROM meetings WHERE id = ?", (source_id,))
                client_id = str(row["client_id"]) if row else None
            elif source_id and state.db.fetchone("SELECT 1 FROM clients WHERE id = ?", (source_id,)):
                client_id = source_id
            elif source_id:
                row = state.db.fetchone("SELECT client_id FROM goal_records WHERE id = ?", (source_id,))
                client_id = str(row["client_id"]) if row else None
            elif task.clientName:
                row = state.db.fetchone("SELECT id FROM clients WHERE name = ?", (task.clientName,))
                client_id = str(row["id"]) if row and row["id"] else None
            if client_id and client_id not in seen_client_ids:
                seen_client_ids.add(client_id)
                discovered_client_ids.append(client_id)

        modules: list[OrganizationDnaModuleRecord] = []
        for client_id in discovered_client_ids[:3]:
            try:
                client = build_client_summary(client_id)
            except HTTPException:
                continue
            goals = list_client_goals(client_id)[:2]
            recent_meeting_rows = state.db.fetchall(
                "SELECT id FROM meetings WHERE client_id = ? ORDER BY updated_at DESC LIMIT 2",
                (client_id,),
            )
            decision_summaries: list[str] = []
            risk_summaries: list[str] = []
            for meeting_row in recent_meeting_rows:
                detail = build_meeting_detail(str(meeting_row["id"]))
                for decision in detail.decisions:
                    summary = decision.summary.strip()
                    if summary and summary not in decision_summaries:
                        decision_summaries.append(summary)
                    if len(decision_summaries) >= 2:
                        break
                for risk in detail.risks:
                    summary = risk.summary.strip()
                    if summary and summary not in risk_summaries:
                        risk_summaries.append(summary)
                    if len(risk_summaries) >= 2:
                        break
                if len(decision_summaries) >= 2 and len(risk_summaries) >= 2:
                    break
            document_cards = fetch_document_cards(state.db, client_id, data_dir=state.data_dir, limit=2)
            card_titles = [str(item.get("title") or "").strip() for item in document_cards if str(item.get("title") or "").strip()]
            client_dna_summary = next(
                (
                    module.summary.strip()
                    for module in list_client_dna_modules(client_id)
                    if module.summary.strip()
                ),
                "",
            )
            summary_parts = [f"客户阶段：{client.stage}"]
            if goals:
                summary_parts.append(f"关键目标：{'；'.join(goal.title for goal in goals)}")
            if decision_summaries:
                summary_parts.append(f"近期会议决策：{'；'.join(decision_summaries[:2])}")
            if risk_summaries:
                summary_parts.append(f"当前阻力：{'；'.join(risk_summaries[:2])}")
            if card_titles:
                summary_parts.append(f"资料线索：{'、'.join(card_titles[:2])}")
            if client_dna_summary:
                summary_parts.append(f"客户背景：{client_dna_summary}")
            normalized = " ".join(part for part in summary_parts if part).strip()
            if not normalized:
                continue
            modules.append(
                OrganizationDnaModuleRecord(
                    moduleKey="business_intro",
                    title=f"{client.name} 业务背景",
                    markdownContent=normalized,
                    normalizedText=normalized,
                    summary=normalized,
                    fileName=None,
                    contentHash=None,
                    updatedAt=None,
                    updatedBy="client_workspace_sync",
                    hasDocument=True,
                )
            )
        modules.sort(key=lambda item: ((item.title or "").strip(), (item.summary or "").strip()))
        return modules

    def build_review_context_modules(
        work_items: list[WeeklyReviewTaskEntryRecord],
        organization_modules: list[OrganizationDnaModuleRecord] | None = None,
    ) -> list[OrganizationDnaModuleRecord]:
        base_modules = list(organization_modules) if organization_modules is not None else list_organization_dna_modules()
        client_modules = build_client_business_context_modules(work_items)
        return [*client_modules, *base_modules]

    def build_review_analyses(
        week_label: str,
        work_items: list[WeeklyReviewTaskEntryRecord],
        personal_items: list[WeeklyReviewTaskEntryRecord],
        organization_modules: list[OrganizationDnaModuleRecord] | None = None,
        org_model_profile: OrgModelProfileRecord | None = None,
        viewer_role: Literal["employee", "department_lead", "admin"] = "employee",
    ) -> tuple[WeeklyReviewAnalysisRecord, WeeklyReviewAnalysisRecord]:
        work_modules = build_review_context_modules(work_items, organization_modules)
        personal_modules = list(organization_modules) if organization_modules is not None else list_organization_dna_modules()
        work_analysis = build_weekly_review_analysis(
            "work",
            week_label,
            work_items,
            work_modules,
            org_model_profile=org_model_profile,
            viewer_role=viewer_role,
        )
        personal_analysis = build_weekly_review_analysis("personal", week_label, personal_items, personal_modules, org_model_profile=org_model_profile)
        return work_analysis, personal_analysis

    def _memory_slot_label(slot_key: str) -> str:
        mapping = {
            "current_stage": "当前阶段",
            "current_work": "当前事项",
            "current_blocker": "当前阻塞",
            "recent_decision": "最近关键决策",
            "next_step": "下一步",
        }
        return mapping.get(slot_key.strip(), slot_key.strip())

    def _normalize_event_line_reference(value: str | None) -> str:
        normalized = str(value or "").strip()
        if normalized.startswith("event_line::"):
            return normalized.split("::", 1)[1].strip()
        return normalized

    def _memory_background_source_labels(
        *,
        has_notebook: bool,
        has_snapshot: bool,
        has_evidence: bool,
        has_review_signals: bool,
        has_linked_facts: bool,
        has_pending_clarification: bool,
    ) -> list[str]:
        labels: list[str] = []
        if has_notebook:
            labels.append("组织笔记")
        if has_snapshot:
            labels.append("事件线记忆")
        if has_review_signals:
            labels.append("周复盘信号")
        if has_linked_facts:
            labels.append("统一事实池")
        if has_evidence:
            labels.append("任务/附件证据")
        if has_pending_clarification:
            labels.append("待澄清槽位")
        return labels

    def _compact_business_line(value: str | None, *, max_length: int = 120) -> str:
        return sanitize_memory_background_text(value, reject_generic=True, max_length=max_length)

    def _task_clause_candidates(value: str | None) -> list[str]:
        return [
            clause
            for clause in (
                _compact_business_line(item, max_length=140)
                for item in re.split(r"[\n。；;]", str(value or ""))
            )
            if clause
        ]

    def _dedupe_lines(values: list[str], *, limit: int = 4) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = _compact_business_line(value, max_length=140)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
            if len(result) >= limit:
                break
        return result

    def _first_meaningful_line(*values: str | None) -> str:
        return next((item for item in (_compact_business_line(value, max_length=140) for value in values) if item), "")

    def _infer_bundle_operating_mode(bundle: EventLineContextBundleRecord) -> Literal["meeting", "delivery", "materials", "analysis", "coordination", "general"]:
        text = " ".join(
            [
                bundle.lineName,
                bundle.summary,
                bundle.intent,
                bundle.currentWork,
                bundle.currentBlocker,
                bundle.nextStep,
                *[fact.title for fact in bundle.taskFacts[:3]],
                *[fact.summary for fact in bundle.taskFacts[:3]],
                *[fact.title for fact in bundle.attachmentFacts[:3]],
                *[fact.summary for fact in bundle.attachmentFacts[:2]],
            ]
        )
        if _contains_any_keyword(text, ("见面", "会谈", "拜访", "演示", "电话会", "讨论", "交流", "看系统", "对接")):
            return "meeting"
        if _contains_any_keyword(text, ("方案", "报告", "提纲", "清单", "输出", "成稿", "交付", "文稿", "版本")):
            return "delivery"
        if _contains_any_keyword(text, ("资料", "材料", "台账", "导入", "归档", "工具包", "附件", "底稿")):
            return "materials"
        if _contains_any_keyword(text, ("诊断", "分析", "研判", "判断", "策略", "洞察")):
            return "analysis"
        if _contains_any_keyword(text, ("确认", "审批", "复核", "拍板", "协同", "流程")):
            return "coordination"
        return "general"

    def _bundle_key_evidence_lines(bundle: EventLineContextBundleRecord, *, limit: int = 3) -> list[str]:
        candidates = [
            *[fact.summary for fact in bundle.taskFacts[:2]],
            *[fact.summary for fact in bundle.meetingFacts[:2]],
            *[fact.title for fact in bundle.attachmentFacts[:2]],
            *bundle.recentFacts[:2],
            *[fact.summary for fact in bundle.clarificationFacts[:2]],
        ]
        return _dedupe_lines(candidates, limit=limit)

    def _bundle_people_or_products_hint(bundle: EventLineContextBundleRecord) -> str:
        people = _dedupe_lines(bundle.keyPeople, limit=2)
        products = _dedupe_lines(bundle.keyProducts, limit=2)
        if people and products:
            return f"关键对象是 {'、'.join(people)}，当前讨论对象涉及 {'、'.join(products)}。"
        if people:
            return f"关键对象是 {'、'.join(people)}。"
        if products:
            return f"当前讨论对象涉及 {'、'.join(products)}。"
        return ""

    def _bundle_missing_context_lines(bundle: EventLineContextBundleRecord) -> list[str]:
        missing: list[str] = []
        if not bundle.keyPeople:
            missing.append("关键人角色")
        if not bundle.collaborationRelationship:
            missing.append("合作关系")
        if not bundle.currentWork:
            missing.append("当前事项")
        if not bundle.nextStep:
            missing.append("下周动作")
        return missing[:3]

    def _bundle_coverage_score(bundle: EventLineContextBundleRecord) -> int:
        checks = [
            bool(bundle.summary or bundle.intent),
            bool(bundle.currentWork),
            bool(bundle.currentBlocker),
            bool(bundle.nextStep or bundle.recentDecision),
            bool(bundle.projectName or bundle.collaborationRelationship or bundle.organizationIntro),
            bool(bundle.currentChallenges or bundle.collaborationGoals),
            bool(bundle.keyPeople or bundle.keyProducts),
            bool(bundle.taskFacts),
            bool(bundle.meetingFacts or bundle.attachmentFacts or bundle.clarificationFacts),
            bool(bundle.evidenceRefs),
        ]
        return int(round((sum(1 for item in checks if item) / len(checks)) * 100))

    def _bundle_confidence_score(
        bundle: EventLineContextBundleRecord,
        *,
        coverage_score: int,
    ) -> int:
        readiness_weight = {"low": 0.35, "medium": 0.6, "high": 0.82}.get(bundle.readiness, 0.35)
        evidence_density = min(
            1.0,
            (
                min(bundle.taskCount, 3) * 0.16
                + min(bundle.meetingCount, 2) * 0.16
                + min(bundle.attachmentCount, 3) * 0.12
                + min(bundle.supportRequestCount, 2) * 0.08
                + min(len(bundle.clarificationFacts), 2) * 0.1
                + min(len(bundle.evidenceRefs), 4) * 0.06
            ),
        )
        confidence = min(
            1.0,
            (coverage_score / 100.0) * 0.52 + readiness_weight * 0.28 + evidence_density * 0.2,
        )
        return int(round(confidence * 100))

    def _bundle_safe_output_mode(
        bundle: EventLineContextBundleRecord,
        *,
        coverage_score: int,
        confidence_score: int,
    ) -> Literal["needs_input", "summary_only", "full_judgment"]:
        if coverage_score >= 70 and confidence_score >= 65:
            return "full_judgment"
        if coverage_score >= 40 and confidence_score >= 35:
            return "summary_only"
        return "needs_input"

    def _bundle_publish_state(
        *,
        viewer_role: ReviewViewerRole,
        safe_output_mode: Literal["needs_input", "summary_only", "full_judgment"],
    ) -> Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"]:
        if viewer_role in {"admin", "department_lead"} and safe_output_mode == "full_judgment":
            return "publish_ready"
        return "local_preview"

    def _bundle_fingerprint(bundle: EventLineContextBundleRecord) -> str:
        payload = {
            "eventLineId": bundle.eventLineId,
            "lineName": bundle.lineName,
            "businessCategory": bundle.businessCategory,
            "stage": bundle.stage,
            "summary": bundle.summary,
            "intent": bundle.intent,
            "currentWork": bundle.currentWork,
            "currentBlocker": bundle.currentBlocker,
            "recentDecision": bundle.recentDecision,
            "nextStep": bundle.nextStep,
            "recentProgress": bundle.recentProgress,
            "projectName": bundle.projectName,
            "collaborationRelationship": bundle.collaborationRelationship,
            "organizationIntro": bundle.organizationIntro,
            "currentChallenges": bundle.currentChallenges,
            "collaborationGoals": bundle.collaborationGoals,
            "keyPeople": bundle.keyPeople,
            "keyProducts": bundle.keyProducts,
            "recentFacts": bundle.recentFacts,
            "taskFacts": [fact.model_dump(mode="json") for fact in bundle.taskFacts[:6]],
            "meetingFacts": [fact.model_dump(mode="json") for fact in bundle.meetingFacts[:4]],
            "attachmentFacts": [fact.model_dump(mode="json") for fact in bundle.attachmentFacts[:6]],
            "clarificationFacts": [fact.model_dump(mode="json") for fact in bundle.clarificationFacts[:4]],
            "evidenceRefs": [ref.model_dump(mode="json") for ref in bundle.evidenceRefs[:8]],
            "trendSignals": [
                {
                    "key": signal.key,
                    "signalType": signal.signalType,
                    "severity": signal.severity,
                    "statement": signal.statement,
                }
                for signal in bundle.trendSignals[:6]
            ],
            "taskCount": bundle.taskCount,
            "meetingCount": bundle.meetingCount,
            "attachmentCount": bundle.attachmentCount,
            "supportRequestCount": bundle.supportRequestCount,
            "readiness": bundle.readiness,
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:16]

    def _event_line_bundle_readiness(
        *,
        notebook_confidence: float,
        snapshot_confidence: float,
        task_count: int,
        attachment_count: int,
        support_request_count: int,
        clarification_count: int,
        current_work: str,
        current_blocker: str,
        next_step: str,
    ) -> Literal["low", "medium", "high"]:
        score = 0
        if notebook_confidence >= 0.5:
            score += 1
        if snapshot_confidence >= 0.5:
            score += 1
        if task_count >= 2:
            score += 1
        if attachment_count >= 1:
            score += 1
        if support_request_count >= 1:
            score += 1
        if clarification_count >= 1:
            score += 1
        if current_work:
            score += 1
        if current_blocker:
            score += 1
        if next_step:
            score += 1
        if score >= 6:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    def _event_line_context_fact(
        *,
        source_type: Literal["task", "meeting", "attachment", "support_request", "clarification", "notebook", "event_line_memory"],
        source_id: str,
        title: str,
        summary: str,
        happened_at: str | None = None,
    ) -> EventLineContextFactRecord | None:
        normalized_title = str(title or "").strip()
        normalized_summary = _compact_business_line(summary, max_length=160)
        if not normalized_title and not normalized_summary:
            return None
        return EventLineContextFactRecord(
            sourceType=source_type,
            sourceId=source_id,
            title=normalized_title or normalized_summary,
            summary=normalized_summary or normalized_title,
            happenedAt=happened_at,
        )

    def _context_fact_to_evidence_ref(fact: EventLineContextFactRecord) -> ReviewDashboardEvidenceRefRecord:
        return ReviewDashboardEvidenceRefRecord(
            sourceType=fact.sourceType,
            sourceId=fact.sourceId,
            title=fact.title,
            summary=fact.summary,
        )

    def _dedupe_dashboard_evidence_refs(
        refs: list[ReviewDashboardEvidenceRefRecord],
        *,
        limit: int | None = None,
    ) -> list[ReviewDashboardEvidenceRefRecord]:
        deduped: list[ReviewDashboardEvidenceRefRecord] = []
        seen: set[tuple[str, str, str, str]] = set()
        for ref in refs:
            source_type = str(ref.sourceType or "").strip()
            source_id = str(ref.sourceId or "").strip()
            title = str(ref.title or "").strip()
            summary = str(ref.summary or "").strip()
            if not source_type or not source_id or not title:
                continue
            key = (source_type, source_id, title, summary)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(
                ReviewDashboardEvidenceRefRecord(
                    sourceType=ref.sourceType,
                    sourceId=source_id,
                    title=title,
                    summary=summary or None,
                )
            )
            if limit is not None and len(deduped) >= limit:
                break
        return deduped

    def _event_line_context_bundle(
        event_line_id: str,
        *,
        analysis: WeeklyReviewAnalysisRecord | None = None,
    ) -> EventLineContextBundleRecord | None:
        normalized_event_line_id = _normalize_event_line_reference(event_line_id)
        if not normalized_event_line_id:
            return None
        row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (normalized_event_line_id,))
        if not row:
            return None
        detail: EventLineDetailRecord
        if get_cloud_token():
            try:
                payload = cloud_request("GET", f"/api/v1/event-lines/{normalized_event_line_id}")
                detail = build_cloud_event_line_detail(payload) if isinstance(payload, dict) else build_event_line_detail(row)
            except HTTPException:
                detail = build_event_line_detail(row)
        else:
            detail = build_event_line_detail(row)
        snapshot = detail.memorySnapshot
        notebook = (
            get_client_notebook_response(state.db, detail.eventLine.primaryClientId).organizationNotebookSnapshot
            if detail.eventLine.primaryClientId
            else None
        )
        clarification_rows = state.db.fetchall(
            """
            SELECT *
            FROM clarification_records
            WHERE (scope_type = 'event_line' AND scope_id = ?)
               OR (scope_type = 'client' AND scope_id = ?)
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 8
            """,
            (
                normalized_event_line_id,
                detail.eventLine.primaryClientId or "",
            ),
        )
        clarification_facts = [
            fact
            for fact in (
                _event_line_context_fact(
                    source_type="clarification",
                    source_id=str(item["id"]),
                    title=_first_nonempty_text(item["question"], item["slot_key"], "澄清记录") or "澄清记录",
                    summary=_first_nonempty_text(item["answer_text"], item["question"], item["slot_key"]) or "",
                    happened_at=str(item["updated_at"] or item["created_at"] or ""),
                )
                for item in clarification_rows
            )
            if fact is not None
        ]
        task_facts = [
            fact
            for fact in (
                _event_line_context_fact(
                    source_type="task",
                    source_id=task.id,
                    title=task.title,
                    summary=_first_nonempty_text(
                        _task_clause_candidates(task.desc)[0] if _task_clause_candidates(task.desc) else None,
                        task.recentDecision,
                        task.nextAction,
                        task.currentBlocker,
                    ) or task.title,
                    happened_at=task.updatedAt,
                )
                for task in detail.tasks[:8]
            )
            if fact is not None
        ]
        meeting_facts = [
            fact
            for fact in (
                _event_line_context_fact(
                    source_type="meeting",
                    source_id=activity.sourceId,
                    title=activity.title,
                    summary=_first_nonempty_text(
                        activity.summary,
                        activity.detail,
                        activity.title,
                    ) or activity.title,
                    happened_at=activity.happenedAt,
                )
                for activity in detail.activities
                if activity.sourceType == "meeting"
            )
            if fact is not None
        ][:6]
        attachment_facts = [
            fact
            for fact in (
                _event_line_context_fact(
                    source_type="attachment",
                    source_id=attachment.id,
                    title=attachment.title,
                    summary=_first_nonempty_text(
                        attachment.summary if hasattr(attachment, "summary") else None,
                        attachment.title,
                        attachment.path,
                    ) or attachment.title,
                    happened_at=attachment.createdAt,
                )
                for task in detail.tasks
                for attachment in task.attachments
            )
            if fact is not None
        ][:8]
        support_request_records = _support_requests_for_tasks(detail.tasks)
        support_request_count = len(support_request_records) or len(
            [activity for activity in detail.activities if activity.sourceType == "support_request"]
        )
        trend_signals = [
            signal
            for signal in (analysis.trendSignals if analysis else [])
            if (
                _normalize_event_line_reference(signal.relatedEventLineId or "") == normalized_event_line_id
                or bool(set(signal.relatedTaskIds).intersection({task.id for task in detail.tasks}))
            )
        ]
        current_work = _first_nonempty_text(
            snapshot.currentWork if snapshot else None,
            detail.eventLine.intent,
            detail.eventLine.summary,
            task_facts[0].summary if task_facts else None,
            meeting_facts[0].summary if meeting_facts else None,
        ) or ""
        current_blocker = _first_nonempty_text(
            snapshot.currentBlocker if snapshot else None,
            detail.eventLine.currentBlocker,
            notebook.currentChallenges[0] if notebook and notebook.currentChallenges else None,
            clarification_facts[0].summary if clarification_facts else None,
        ) or ""
        recent_decision = _first_nonempty_text(
            snapshot.recentDecision if snapshot else None,
            detail.eventLine.recentDecision,
            meeting_facts[0].summary if meeting_facts else None,
            clarification_facts[0].summary if clarification_facts else None,
        ) or ""
        next_step = _first_nonempty_text(
            snapshot.nextStep if snapshot else None,
            detail.eventLine.nextStep,
            detail.tasks[0].nextAction if detail.tasks and detail.tasks[0].nextAction else None,
            notebook.collaborationGoals[0] if notebook and notebook.collaborationGoals else None,
        ) or ""
        recent_progress = _first_nonempty_text(
            detail.tasks[0].recentDecision if detail.tasks and detail.tasks[0].recentDecision else None,
            meeting_facts[0].summary if meeting_facts else None,
            task_facts[0].summary if task_facts else None,
            attachment_facts[0].title if attachment_facts else None,
        ) or ""
        notebook_facts = [
            fact
            for fact in (
                _event_line_context_fact(
                    source_type="notebook",
                    source_id=f"{detail.eventLine.primaryClientId or normalized_event_line_id}-fact-{index}",
                    title="组织业务笔记",
                    summary=fact_text,
                )
                for index, fact_text in enumerate(
                    _dedupe_lines(
                        [
                            notebook.collaborationRelationship if notebook else "",
                            notebook.organizationIntro if notebook else "",
                            *(notebook.recentFacts[:2] if notebook else []),
                            *([f"关键人：{'、'.join(notebook.keyPeople[:2])}"] if notebook and notebook.keyPeople else []),
                            *([f"关键产品：{'、'.join(notebook.keyProducts[:2])}"] if notebook and notebook.keyProducts else []),
                        ],
                        limit=4,
                    )
                )
            )
            if fact is not None
        ]
        evidence_refs = _dedupe_dashboard_evidence_refs(
            [
                *_story_evidence_refs(
                    {
                        "id": normalized_event_line_id,
                        "eventLineId": normalized_event_line_id,
                        "taskTitles": [task.title for task in detail.tasks],
                        "taskIds": [task.id for task in detail.tasks],
                    }
                ),
                *[_context_fact_to_evidence_ref(fact) for fact in task_facts[:3]],
                *[_context_fact_to_evidence_ref(fact) for fact in meeting_facts[:2]],
                *[_context_fact_to_evidence_ref(fact) for fact in attachment_facts[:3]],
                *[_context_fact_to_evidence_ref(fact) for fact in clarification_facts[:2]],
                *[_context_fact_to_evidence_ref(fact) for fact in notebook_facts[:2]],
            ]
        )[:8]
        readiness = _event_line_bundle_readiness(
            notebook_confidence=notebook.confidence if notebook else 0.0,
            snapshot_confidence=snapshot.confidence if snapshot else 0.0,
            task_count=len(detail.tasks),
            attachment_count=len(attachment_facts),
            support_request_count=support_request_count,
            clarification_count=len(clarification_facts),
            current_work=current_work,
            current_blocker=current_blocker,
            next_step=next_step,
        )
        return EventLineContextBundleRecord(
            eventLineId=normalized_event_line_id,
            lineName=detail.eventLine.name,
            businessCategory=detail.eventLine.businessCategory or "",
            stage=_first_nonempty_text(detail.eventLine.stage, snapshot.currentStage if snapshot else None) or "",
            summary=detail.eventLine.summary or "",
            intent=detail.eventLine.intent or "",
            currentWork=current_work,
            currentBlocker=current_blocker,
            recentDecision=recent_decision,
            nextStep=next_step,
            recentProgress=recent_progress,
            projectName=detail.eventLine.primaryClientName or "",
            collaborationRelationship=notebook.collaborationRelationship if notebook else "",
            organizationIntro=notebook.organizationIntro if notebook else "",
            currentChallenges=list(notebook.currentChallenges) if notebook else [],
            collaborationGoals=list(notebook.collaborationGoals) if notebook else [],
            keyPeople=list(notebook.keyPeople) if notebook else [],
            keyProducts=list(notebook.keyProducts) if notebook else [],
            recentFacts=list(notebook.recentFacts)[:5] if notebook else [],
            taskFacts=task_facts,
            meetingFacts=meeting_facts,
            attachmentFacts=attachment_facts,
            clarificationFacts=clarification_facts,
            evidenceRefs=evidence_refs,
            trendSignals=trend_signals,
            taskCount=len(detail.tasks),
            meetingCount=len(meeting_facts),
            attachmentCount=len(attachment_facts),
            supportRequestCount=support_request_count,
            readiness=readiness,
        )

    def _infer_bundle_blocker_type(bundle: EventLineContextBundleRecord) -> Literal["business", "collaboration", "decision", "structure", "capacity", "evidence"]:
        text = " ".join(
            [
                bundle.currentBlocker,
                bundle.recentDecision,
                bundle.nextStep,
                bundle.currentWork,
                *bundle.currentChallenges[:2],
                *[signal.signalType for signal in bundle.trendSignals],
            ]
        )
        rich_evidence = bundle.attachmentCount >= 2 or len(bundle.meetingFacts) >= 1 or len(bundle.recentFacts) >= 2
        if _contains_any_keyword(text, ("目标", "价值", "会谈", "演示", "方案", "定位", "合作", "客户", "场景", "判断", "收束", "落点")):
            return "business"
        if _contains_any_keyword(text, ("复核", "审批", "确认", "拍板", "决策")):
            return "decision"
        if _contains_any_keyword(text, ("跨部门", "协同", "对接", "等待他人", "支持")):
            return "collaboration"
        if _contains_any_keyword(text, ("带宽", "排期", "容量", "过载", "改期")):
            return "capacity"
        if _contains_any_keyword(text, ("模块", "流程", "结构", "归属", "口径")) and not rich_evidence:
            return "structure"
        if _contains_any_keyword(text, ("资料", "证据", "附件", "摘要", "背景包", "信息不足")) and not rich_evidence:
            return "evidence"
        return "business"

    def _build_event_line_judgment(
        bundle: EventLineContextBundleRecord,
        *,
        viewer_role: ReviewViewerRole = "employee",
    ) -> EventLineJudgmentRecord:
        judgment_version = "event_line_judgment_v1"
        bundle_fingerprint = _bundle_fingerprint(bundle)
        coverage_score = _bundle_coverage_score(bundle)
        confidence_score = _bundle_confidence_score(bundle, coverage_score=coverage_score)
        safe_output_mode = _bundle_safe_output_mode(
            bundle,
            coverage_score=coverage_score,
            confidence_score=confidence_score,
        )
        publish_state = _bundle_publish_state(
            viewer_role=viewer_role,
            safe_output_mode=safe_output_mode,
        )
        operating_mode = _infer_bundle_operating_mode(bundle)
        happened_basis = _first_meaningful_line(
            bundle.currentWork,
            bundle.recentDecision,
            bundle.recentProgress,
            bundle.taskFacts[0].summary if bundle.taskFacts else None,
            bundle.summary,
            bundle.intent,
        ) or f"{bundle.lineName} 本周仍在推进。"
        what_happened = happened_basis
        if viewer_role == "admin":
            why_it_matters = _first_meaningful_line(
                bundle.collaborationGoals[0] if bundle.collaborationGoals else None,
                bundle.collaborationRelationship and f"这条线直接影响 {bundle.projectName or '当前项目'} 的合作判断是否能继续往前推。",
                f"这条线决定 {bundle.projectName or '当前项目'} 这一阶段能否形成值得继续投入的明确结论。",
            )
            manager_implication = (
                "管理层现在要判断的不是资料量，而是这条线能否收成明确结论、责任边界和下轮动作。"
            )
        elif viewer_role == "department_lead":
            why_it_matters = _first_meaningful_line(
                bundle.collaborationGoals[0] if bundle.collaborationGoals else None,
                "这条线会直接占用部门带宽；如果不及时收束，部门会继续消耗在来回确认和补背景上。",
            )
            manager_implication = "部门负责人要盯的是接口、带宽和收束动作，不是继续加任务。"
        else:
            why_it_matters = _first_meaningful_line(
                bundle.collaborationGoals[0] if bundle.collaborationGoals else None,
                "这条线如果不尽快收成结论，你本周的推进会停在交流和准备层，而不是形成结果。",
            )
            manager_implication = "现在最关键的不是再补一轮泛背景，而是把这次推进后的判断和下一步钉住。"
        core_blocker = _first_meaningful_line(
            bundle.currentBlocker,
            bundle.currentChallenges[0] if bundle.currentChallenges else None,
        )
        blocker_type = _infer_bundle_blocker_type(bundle)
        missing_context = _bundle_missing_context_lines(bundle)
        if not core_blocker:
            if missing_context:
                core_blocker = f"现在还缺 {'、'.join(missing_context)}，所以这条线难以被准确判断和推进。"
                blocker_type = "evidence"
            elif operating_mode == "meeting":
                core_blocker = "真正的阻碍不是见面本身，而是会后要形成什么结论、谁接动作还不够明确。"
            elif operating_mode == "delivery":
                core_blocker = "真正的阻碍不是继续补话术，而是交付边界、收口标准和责任人还不够明确。"
            elif operating_mode == "materials":
                core_blocker = "真正的阻碍不是资料数量，而是哪些资料足以支撑判断、哪些还只是堆放并不清楚。"
            else:
                core_blocker = "当前最关键的阻碍还没有被明确写成一句业务判断。"
        key_evidence = _bundle_key_evidence_lines(bundle, limit=3)
        evidence_summary = "；".join(key_evidence) if key_evidence else (
            f"已关联 {bundle.taskCount} 条任务、{bundle.meetingCount} 次会议、{bundle.attachmentCount} 份附件"
            + (f"、{bundle.supportRequestCount} 条支持请求" if bundle.supportRequestCount else "")
        )
        next_week_focus = _first_meaningful_line(
            bundle.nextStep,
            bundle.collaborationGoals[0] if bundle.collaborationGoals else None,
            bundle.intent,
        ) or (
            "把这条线压成一句明确结论和一个最小动作。"
            if operating_mode != "meeting"
            else "把会谈要确认的结论、关键人反馈和会后动作一次性钉住。"
        )
        minimum_action = _first_meaningful_line(
            bundle.nextStep,
            bundle.recentDecision and f"把“{bundle.recentDecision}”转成明确跟进行动",
        ) or (
            "明确这次推进后的责任人、时间点和会后动作。"
            if operating_mode == "meeting"
            else "把这条线收成可执行结论、责任人和最小后续动作。"
        )
        risk_if_ignored = {
            "business": "如果继续不收束，这条线会继续停在泛交流或泛合作表达层，管理层看不清是否值得继续加码。",
            "collaboration": "如果继续不处理协同接口，这条线会继续卡在等待与来回确认上，并很快变成跨周风险。",
            "decision": "如果继续不拍板，这条线会把推进变成反复确认，后续动作很难真正启动。",
            "structure": "如果继续不把归属和产出链挂清楚，资料会越来越多，但判断仍然会继续发虚。",
            "capacity": "如果继续不做取舍，这条线会继续和别的事项争抢带宽，导致推进质量下滑。",
            "evidence": "如果继续不补关键证据，后续所有判断都会停在大概正确但无法指导动作的层面。",
        }.get(blocker_type, "如果继续放着不管，这条线会继续停在推进表面，难以形成真正结果。")
        opportunity_if_amplified = (
            "如果现在就把这条线沉成结论、证据和后续动作，它能从一次推进变成可复制的合作样板。"
            if operating_mode == "meeting"
            else "如果现在就把这条线沉成结论、证据和后续动作，它就能从一次推进变成可复制的正向样板。"
        )
        people_or_products_hint = _bundle_people_or_products_hint(bundle)
        if people_or_products_hint:
            why_it_matters = f"{why_it_matters} {people_or_products_hint}".strip()
        return EventLineJudgmentRecord(
            eventLineId=bundle.eventLineId,
            title=bundle.lineName,
            viewerRole=viewer_role if viewer_role in {"employee", "department_lead", "admin"} else "employee",
            judgmentVersion=judgment_version,
            bundleFingerprint=bundle_fingerprint,
            coverageScore=coverage_score,
            confidenceScore=confidence_score,
            safeOutputMode=safe_output_mode,
            publishState=publish_state,
            whatHappened=what_happened,
            whyItMatters=why_it_matters,
            coreBlocker=core_blocker,
            blockerType=blocker_type,
            evidenceSummary=evidence_summary,
            managerImplication=manager_implication,
            nextWeekFocus=next_week_focus,
            minimumAction=minimum_action,
            riskIfIgnored=risk_if_ignored,
            opportunityIfAmplified=opportunity_if_amplified,
            evidenceRefs=bundle.evidenceRefs[:6],
            target=ReviewDashboardCardTargetRecord(
                targetType="event_line",
                targetId=bundle.eventLineId,
                targetLabel=bundle.lineName,
                evidenceRefs=bundle.evidenceRefs[:4],
            ),
        )

    def _build_ad_hoc_task_context_bundle(task: TaskRecord) -> EventLineContextBundleRecord:
        notebook = (
            get_client_notebook_response(state.db, task.clientId).organizationNotebookSnapshot
            if task.clientId
            else None
        )
        task_clauses = _task_clause_candidates(task.desc)
        task_fact = _event_line_context_fact(
            source_type="task",
            source_id=task.id,
            title=task.title,
            summary=_first_nonempty_text(
                task_clauses[0] if task_clauses else None,
                task.recentDecision,
                task.nextAction,
                task.currentBlocker,
            ) or task.title,
            happened_at=task.updatedAt,
        )
        attachment_facts = [
            fact
            for fact in (
                _event_line_context_fact(
                    source_type="attachment",
                    source_id=item.id,
                    title=item.title,
                    summary=_first_nonempty_text(
                        item.summary if hasattr(item, "summary") else None,
                        item.title,
                        item.path,
                    ),
                    happened_at=item.createdAt,
                )
                for item in task.attachments
            )
            if fact is not None
        ]
        clarification_facts = [
            _event_line_context_fact(
                source_type="clarification",
                source_id=f"{task.id}-memory-hint-{index}",
                title="已关联背景",
                summary=hint,
            )
            for index, hint in enumerate((task.memoryHints or [])[:3])
        ]
        clarification_facts = [fact for fact in clarification_facts if fact is not None]
        evidence_refs = _dedupe_dashboard_evidence_refs(
            [
                ReviewDashboardEvidenceRefRecord(
                    sourceType="task",
                    sourceId=task.id,
                    title=task.title,
                    summary=_first_nonempty_text(
                        task_clauses[0] if task_clauses else None,
                        task.recentDecision,
                        task.nextAction,
                        task.currentBlocker,
                    ),
                ),
                *[_context_fact_to_evidence_ref(fact) for fact in attachment_facts[:4]],
                *[_context_fact_to_evidence_ref(fact) for fact in clarification_facts[:2]],
            ]
        )
        return EventLineContextBundleRecord(
            eventLineId=task.eventLineId or f"task::{task.id}",
            lineName=task.eventLineName or task.title,
            businessCategory=task.businessCategory or "",
            stage=_first_nonempty_text(task.projectContext.stage if task.projectContext else None, task.orgContext.organizationFocusKey if task.orgContext else None) or "",
            summary=_first_nonempty_text(task.desc, task.projectContext.backgroundSummary if task.projectContext else None) or task.title,
            intent=_first_nonempty_text(task.projectContext.currentFocus if task.projectContext else None, task.nextAction, task_clauses[0] if task_clauses else None, task.title) or task.title,
            currentWork=_first_nonempty_text(task.projectContext.currentFocus if task.projectContext else None, task_clauses[0] if task_clauses else None, task.title) or task.title,
            currentBlocker=_first_nonempty_text(task.currentBlocker, task.projectContext.currentBlocker if task.projectContext else None) or "",
            recentDecision=_first_nonempty_text(task.recentDecision, task.projectContext.recentProgress if task.projectContext else None) or "",
            nextStep=_first_nonempty_text(task.nextAction, task.projectContext.nextAction if task.projectContext else None) or "",
            recentProgress=_first_nonempty_text(task.recentDecision, task.projectContext.recentProgress if task.projectContext else None) or "",
            projectName=task.clientName or "",
            collaborationRelationship=notebook.collaborationRelationship if notebook else "",
            organizationIntro=notebook.organizationIntro if notebook else "",
            currentChallenges=list(notebook.currentChallenges) if notebook else [],
            collaborationGoals=list(notebook.collaborationGoals) if notebook else [],
            keyPeople=list(notebook.keyPeople) if notebook else [],
            keyProducts=list(notebook.keyProducts) if notebook else [],
            recentFacts=list(notebook.recentFacts)[:5] if notebook else [],
            taskFacts=[task_fact] if task_fact else [],
            meetingFacts=[],
            attachmentFacts=attachment_facts[:6],
            clarificationFacts=clarification_facts[:4],
            evidenceRefs=evidence_refs[:8],
            trendSignals=[],
            taskCount=1,
            meetingCount=0,
            attachmentCount=len(attachment_facts),
            supportRequestCount=0,
            readiness=_event_line_bundle_readiness(
                notebook_confidence=notebook.confidence if notebook else 0.0,
                snapshot_confidence=0.0,
                task_count=1,
                attachment_count=len(attachment_facts),
                support_request_count=0,
                clarification_count=len(clarification_facts),
                current_work=_first_nonempty_text(task.projectContext.currentFocus if task.projectContext else None, task.desc, task.title) or "",
                current_blocker=_first_nonempty_text(task.currentBlocker, task.projectContext.currentBlocker if task.projectContext else None) or "",
                next_step=_first_nonempty_text(task.nextAction, task.projectContext.nextAction if task.projectContext else None) or "",
            ),
        )

    def _build_task_context_preview(task: TaskRecord) -> TaskContextPreviewRecord:
        session_user = get_cached_session_user()
        governance = _review_governance_with_members() if session_user else None
        viewer_role = _resolve_review_viewer_role(session_user, governance)
        bundle = _event_line_context_bundle(task.eventLineId) if task.eventLineId else None
        if bundle is None:
            bundle = _build_ad_hoc_task_context_bundle(task)
        judgment = _build_event_line_judgment(bundle, viewer_role=viewer_role)
        summary_chips = _dedupe_texts(
            [
                bundle.businessCategory or task.businessCategory or "",
                f"项目 · {bundle.projectName}" if bundle.projectName else "",
                f"事件线 · {bundle.lineName}" if bundle.lineName and task.eventLineId else "",
                f"阶段 · {bundle.stage}" if bundle.stage else "",
            ],
            limit=4,
        )
        return TaskContextPreviewRecord(
            taskId=task.id,
            clientId=task.clientId,
            clientName=task.clientName,
            contextBundle=bundle,
            judgment=judgment,
            judgmentVersion=judgment.judgmentVersion,
            bundleFingerprint=judgment.bundleFingerprint,
            coverageScore=judgment.coverageScore,
            confidenceScore=judgment.confidenceScore,
            safeOutputMode=judgment.safeOutputMode,
            publishState=judgment.publishState,
            summaryChips=summary_chips,
            readiness=bundle.readiness,
        )

    def _enrich_weekly_review_analysis_with_memory(
        analysis: WeeklyReviewAnalysisRecord | None,
        *,
        viewer_role: ReviewViewerRole = "employee",
    ) -> WeeklyReviewAnalysisRecord | None:
        if analysis is None or not analysis.eventLineSummaries:
            return analysis

        summary_updates: dict[str, dict[str, object]] = {}
        completeness_updates: dict[str, dict[str, object]] = {}
        bundles: list[EventLineContextBundleRecord] = []
        judgments: list[EventLineJudgmentRecord] = []

        event_line_ids = list(
            {
                _normalize_event_line_reference(item.eventLineId)
                for item in analysis.eventLineSummaries
                if _normalize_event_line_reference(item.eventLineId)
            }
        )
        for event_line_id in event_line_ids:
            memory_response = get_event_line_memory_response(state.db, event_line_id)
            snapshot = memory_response.eventLineMemorySnapshot
            if snapshot is None:
                continue
            clean_current_work = sanitize_memory_background_text(snapshot.currentWork, reject_generic=True, max_length=140)
            clean_blocker = sanitize_memory_background_text(snapshot.currentBlocker, reject_generic=True, max_length=140)
            clean_recent_decision = sanitize_memory_background_text(snapshot.recentDecision, reject_generic=True, max_length=140)
            clean_next_step = sanitize_memory_background_text(snapshot.nextStep, reject_generic=True, max_length=140)
            event_line_row = state.db.fetchone(
                "SELECT primary_client_id FROM event_lines WHERE id = ?",
                (event_line_id,),
            )
            client_id = str(event_line_row["primary_client_id"]) if event_line_row and event_line_row["primary_client_id"] else None
            notebook = get_client_notebook_response(state.db, client_id).organizationNotebookSnapshot if client_id else None
            linked_facts_preview = get_task_memory_enrichment(
                state.db,
                task_id=f"event-line:{event_line_id}",
                client_id=client_id,
                event_line_id=event_line_id,
            )[2]
            merged_missing_slots = list(
                dict.fromkeys(
                    [
                        *[
                            slot
                            for item in analysis.eventLineSummaries
                            if _normalize_event_line_reference(item.eventLineId) == event_line_id
                            for slot in item.missingSlots
                        ],
                        *[_memory_slot_label(slot) for slot in snapshot.clarificationNeeds],
                    ]
                )
            )[:5]
            background_sources = _memory_background_source_labels(
                has_notebook=bool(notebook and notebook.confidence > 0),
                has_snapshot=True,
                has_evidence=bool(snapshot.evidenceRefs),
                has_review_signals=bool(snapshot.analysisSignals),
                has_linked_facts=bool(linked_facts_preview),
                has_pending_clarification=bool(snapshot.clarificationNeeds),
            )
            summary_update: dict[str, object] = {
                "eventLineId": event_line_id,
                "memoryConfidence": round(snapshot.confidence, 2),
                "backgroundSources": background_sources,
                "missingSlots": merged_missing_slots,
            }
            if clean_current_work:
                summary_update["whatThisLineIs"] = f"这条线当前主要在推进：{clean_current_work}"
                summary_update["whatHappenedThisWeek"] = f"本周主要在推进：{clean_current_work}。"
            elif clean_recent_decision:
                summary_update["whatHappenedThisWeek"] = f"本周形成的关键决策是：{clean_recent_decision}。"
            if clean_blocker:
                summary_update["mainBlocker"] = clean_blocker
            if clean_next_step:
                summary_update["nextCriticalMove"] = clean_next_step
            summary_updates[event_line_id] = summary_update
            completeness_updates[event_line_id] = {
                "eventLineId": event_line_id,
                "memoryConfidence": round(snapshot.confidence, 2),
                "backgroundSources": background_sources,
                "missingSlots": merged_missing_slots,
            }
            bundle = _event_line_context_bundle(event_line_id, analysis=analysis)
            if bundle is not None:
                bundles.append(bundle)
                judgment = _build_event_line_judgment(bundle, viewer_role=viewer_role)
                judgments.append(judgment)
                clean_line_identity = sanitize_memory_background_text(
                    bundle.summary or bundle.intent,
                    reject_generic=True,
                    max_length=140,
                )
                summary_updates[event_line_id].update(
                    {
                        "whatThisLineIs": clean_line_identity or summary_updates[event_line_id].get("whatThisLineIs"),
                        "whatHappenedThisWeek": judgment.whatHappened,
                        "currentState": judgment.whyItMatters,
                        "mainBlocker": judgment.coreBlocker,
                        "nextCriticalMove": judgment.minimumAction,
                        "evidencePreview": _dedupe_texts(
                            [
                                judgment.evidenceSummary,
                                *bundle.recentFacts[:2],
                                *(fact.summary for fact in bundle.taskFacts[:2]),
                            ],
                            limit=4,
                        ),
                        "target": judgment.target,
                        "evidenceRefs": judgment.evidenceRefs,
                        "publishState": judgment.publishState,
                        "publishedAt": judgment.publishedAt,
                        "publishedBy": judgment.publishedBy,
                        "invalidatedAt": judgment.invalidatedAt,
                        "projectName": bundle.projectName or summary_update.get("projectName"),
                    }
                )
                completeness_updates[event_line_id].update(
                    {
                        "strongestSlots": _dedupe_texts(
                            [
                                "当前推进",
                                "当前阻碍" if bundle.currentBlocker else "",
                                "下一步" if bundle.nextStep else "",
                                "会议证据" if bundle.meetingCount else "",
                                "附件证据" if bundle.attachmentCount else "",
                            ],
                            limit=4,
                        )
                    }
                )

        if not summary_updates and not completeness_updates and not bundles and not judgments:
            return analysis

        judgment_by_id = {item.eventLineId: item for item in judgments}
        risk_cards = list(analysis.riskCards or [])
        risk_by_id = {item.eventLineId: item for item in risk_cards}
        for judgment in judgments:
            if judgment.eventLineId in risk_by_id:
                item = risk_by_id[judgment.eventLineId]
                risk_by_id[judgment.eventLineId] = item.model_copy(
                    update={
                        "statement": judgment.coreBlocker,
                        "whyNow": judgment.whyItMatters,
                        "ifIgnored": judgment.riskIfIgnored,
                        "suggestedAction": judgment.minimumAction,
                        "target": judgment.target,
                        "evidenceRefs": judgment.evidenceRefs,
                        "publishState": judgment.publishState,
                        "publishedAt": judgment.publishedAt,
                        "publishedBy": judgment.publishedBy,
                        "invalidatedAt": judgment.invalidatedAt,
                    }
                )
            else:
                risk_by_id[judgment.eventLineId] = EventLineRiskCardRecord(
                    eventLineId=judgment.eventLineId,
                    title=judgment.title,
                    riskType=(
                        "collaboration_friction"
                        if judgment.blockerType == "collaboration"
                        else "decision_lag"
                        if judgment.blockerType == "decision"
                        else "workflow_breakdown"
                        if judgment.blockerType in {"structure", "evidence"}
                        else "overload"
                        if judgment.blockerType == "capacity"
                        else "goal_drift"
                    ),
                    statement=judgment.coreBlocker,
                    forecastWindow="1w",
                    probability="high" if judgment.blockerType in {"decision", "capacity", "structure"} else "medium",
                    impactScope="org" if viewer_role == "admin" else "team" if viewer_role == "department_lead" else "project",
                    triggerSignals=_dedupe_texts([judgment.coreBlocker, judgment.evidenceSummary], limit=3),
                    whyNow=judgment.whyItMatters,
                    ifIgnored=judgment.riskIfIgnored,
                    suggestedAction=judgment.minimumAction,
                    ownerRole="该线负责人",
                    publishState=judgment.publishState,
                    publishedAt=judgment.publishedAt,
                    publishedBy=judgment.publishedBy,
                    invalidatedAt=judgment.invalidatedAt,
                    target=judgment.target,
                    evidenceRefs=judgment.evidenceRefs,
                )

        opportunity_cards = list(analysis.opportunityCards or [])
        opportunity_by_id = {item.eventLineId: item for item in opportunity_cards}
        for judgment in judgments:
            if judgment.eventLineId in opportunity_by_id:
                item = opportunity_by_id[judgment.eventLineId]
                opportunity_by_id[judgment.eventLineId] = item.model_copy(
                    update={
                        "statement": judgment.opportunityIfAmplified,
                        "upside": judgment.managerImplication,
                        "recommendedAmplifier": judgment.minimumAction,
                        "target": judgment.target,
                        "evidenceRefs": judgment.evidenceRefs,
                        "publishState": judgment.publishState,
                        "publishedAt": judgment.publishedAt,
                        "publishedBy": judgment.publishedBy,
                        "invalidatedAt": judgment.invalidatedAt,
                    }
                )
            else:
                opportunity_by_id[judgment.eventLineId] = EventLineOpportunityCardRecord(
                    eventLineId=judgment.eventLineId,
                    title=judgment.title,
                    opportunityType="momentum_building",
                    statement=judgment.opportunityIfAmplified,
                    forecastWindow="1w",
                    confidence="medium" if judgments else "low",
                    upside=judgment.managerImplication,
                    supportingSignals=_dedupe_texts([judgment.evidenceSummary, judgment.whatHappened], limit=3),
                    recommendedAmplifier=judgment.minimumAction,
                    ownerRole="该线负责人",
                    publishState=judgment.publishState,
                    publishedAt=judgment.publishedAt,
                    publishedBy=judgment.publishedBy,
                    invalidatedAt=judgment.invalidatedAt,
                    target=judgment.target,
                    evidenceRefs=judgment.evidenceRefs,
                )

        return analysis.model_copy(
            update={
                "eventLineSummaries": [
                    item.model_copy(
                        update=summary_updates.get(
                            _normalize_event_line_reference(item.eventLineId),
                            {"eventLineId": _normalize_event_line_reference(item.eventLineId)},
                        )
                    )
                    for item in analysis.eventLineSummaries
                ],
                "eventLineCompleteness": [
                    item.model_copy(
                        update=completeness_updates.get(
                            _normalize_event_line_reference(item.eventLineId),
                            {"eventLineId": _normalize_event_line_reference(item.eventLineId)},
                        )
                    )
                    for item in analysis.eventLineCompleteness
                ],
                "eventLineContextBundles": bundles,
                "eventLineJudgments": judgments,
                "riskCards": list(risk_by_id.values())[:6],
                "opportunityCards": list(opportunity_by_id.values())[:6],
                "nextWeekFocus": _dedupe_texts(
                    [
                        *[f"{item.title}｜{item.nextWeekFocus}" for item in judgments],
                        *(analysis.nextWeekFocus or []),
                    ],
                    limit=6,
                ),
            }
        )

    def _format_review_week_label(value: datetime.date) -> str:
        iso = value.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def _previous_review_week_labels(week_label: str, *, count: int = 2) -> list[str]:
        bounds = _week_bounds(week_label)
        if bounds is None:
            return []
        start, _ = bounds
        return [
            _format_review_week_label(start - timedelta(days=7 * offset))
            for offset in range(1, count + 1)
        ]

    def _parse_iso_datetime(value: str | None) -> datetime | None:
        trimmed = str(value or "").strip()
        if not trimmed:
            return None
        normalized = trimmed[:-1] + "+00:00" if trimmed.endswith("Z") else trimmed
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    def _row_value(row: object, key: str, default: object = None) -> object:
        if isinstance(row, dict):
            return row.get(key, default)
        if row is None:
            return default
        try:
            value = row[key]  # sqlite3.Row / mapping-style access
        except Exception:
            return default
        return default if value is None else value

    def _historical_work_review_rows(week_labels: list[str]) -> list[dict[str, object]]:
        if not week_labels:
            return []
        operator_id = str(current_operator_row()["id"])
        placeholders = _sql_placeholders(tuple(week_labels))
        rows = state.db.fetchall(
            f"""
            SELECT e.*
            FROM weekly_review_task_entries e
            INNER JOIN weekly_reviews r ON r.id = e.review_id
            WHERE r.operator_id = ?
              AND e.content_domain = 'work'
              AND e.week_label IN ({placeholders})
            ORDER BY e.reviewed_at DESC, e.created_at DESC
            """,
            (operator_id, *week_labels),
        )
        return [dict(row) for row in rows]

    def _review_snapshot_dict(row: dict[str, object]) -> dict[str, object]:
        payload = from_json(str(_row_value(row, "task_snapshot_json", "{}") or "{}"), {})
        return payload if isinstance(payload, dict) else {}

    def _review_snapshot_org_context(snapshot: dict[str, object]) -> dict[str, object]:
        payload = snapshot.get("orgContext")
        return payload if isinstance(payload, dict) else {}

    def _review_snapshot_project_context(snapshot: dict[str, object]) -> dict[str, object]:
        payload = snapshot.get("projectContext")
        return payload if isinstance(payload, dict) else {}

    def _review_snapshot_event_line_context(snapshot: dict[str, object]) -> dict[str, object]:
        payload = snapshot.get("eventLineContext")
        return payload if isinstance(payload, dict) else {}

    def _review_row_event_line_id(row: dict[str, object]) -> str:
        snapshot = _review_snapshot_dict(row)
        event_line_context = _review_snapshot_event_line_context(snapshot)
        return _normalize_event_line_reference(
            _first_nonempty_text(
                snapshot.get("eventLineId"),
                event_line_context.get("id"),
            )
        )

    def _review_row_support_requested(row: dict[str, object]) -> bool:
        structured = coerce_review_structured_note(_row_value(row, "structured_note_json"))
        return bool(
            structured.supportNeeded.strip()
            or structured.lightweightTag.strip() in {"需要支持", "资源不够", "等待他人"}
        )

    def _review_row_blocker_text(row: dict[str, object]) -> str:
        structured = coerce_review_structured_note(_row_value(row, "structured_note_json"))
        snapshot = _review_snapshot_dict(row)
        event_line_context = _review_snapshot_event_line_context(snapshot)
        project_context = _review_snapshot_project_context(snapshot)
        return _first_nonempty_text(
            structured.blockerReason,
            event_line_context.get("currentBlocker"),
            project_context.get("currentBlocker"),
            _row_value(row, "note"),
        )

    def _review_row_needs_review(row: dict[str, object]) -> bool:
        snapshot = _review_snapshot_dict(row)
        org_context = _review_snapshot_org_context(snapshot)
        return bool(org_context.get("needsReview"))

    def _recent_due_date_change_stats(task_ids: list[str], *, lookback_days: int = 21) -> dict[str, dict[str, object]]:
        wanted = [task_id for task_id in task_ids if task_id]
        if not wanted:
            return {}
        since = (datetime.now() - timedelta(days=lookback_days)).isoformat(timespec="seconds")
        placeholders = _sql_placeholders(tuple(wanted))
        rows = state.db.fetchall(
            f"""
            SELECT entity_id, detail_json, created_at
            FROM activity_logs
            WHERE entity_type = 'task'
              AND action = 'task.update'
              AND entity_id IN ({placeholders})
              AND created_at >= ?
            ORDER BY created_at DESC
            """,
            (*wanted, since),
        )
        stats: dict[str, dict[str, object]] = {}
        for row in rows:
            detail = from_json(row["detail_json"], {}) if row["detail_json"] else {}
            if not isinstance(detail, dict):
                continue
            if "dueDate" not in detail and "ddl" not in detail:
                continue
            task_id = str(row["entity_id"])
            current = stats.setdefault(task_id, {"changeCount": 0, "weeks": set(), "lastChangedAt": None})
            current["changeCount"] = int(current["changeCount"]) + 1
            changed_at = _parse_iso_datetime(str(row["created_at"]))
            if changed_at is not None:
                weeks = current["weeks"]
                if isinstance(weeks, set):
                    weeks.add(_format_review_week_label(changed_at.date()))
                current["lastChangedAt"] = str(row["created_at"])
        return stats

    def _merge_trend_signals(
        existing: list[TrendSignalRecord],
        additions: list[TrendSignalRecord],
    ) -> list[TrendSignalRecord]:
        merged: dict[str, TrendSignalRecord] = {signal.key: signal for signal in existing}
        for signal in additions:
            merged[signal.key] = signal
        severity_rank = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            merged.values(),
            key=lambda item: (severity_rank.get(item.severity, 3), item.title),
        )[:8]

    def _enrich_weekly_review_analysis_with_operational_trends(
        analysis: WeeklyReviewAnalysisRecord | None,
        items: list[WeeklyReviewTaskEntryRecord],
        week_label: str,
    ) -> WeeklyReviewAnalysisRecord | None:
        if analysis is None or not items:
            return analysis

        previous_weeks = _previous_review_week_labels(week_label, count=2)
        if not previous_weeks:
            return analysis

        current_task_ids = [item.taskId for item in items if item.taskId]
        current_titles = {item.taskId: item.taskSnapshot.title for item in items if item.taskId}
        historical_rows = _historical_work_review_rows(previous_weeks)
        if not historical_rows and not current_task_ids:
            return analysis

        historical_review_tasks: set[str] = set()
        historical_review_event_lines: set[str] = set()
        historical_support_tasks: set[str] = set()
        historical_support_event_lines: set[str] = set()
        historical_blockers: dict[str, str] = {}

        for row in historical_rows:
            task_id = str(_row_value(row, "task_id", "") or "").strip()
            event_line_id = _review_row_event_line_id(row)
            if _review_row_needs_review(row):
                if task_id:
                    historical_review_tasks.add(task_id)
                if event_line_id:
                    historical_review_event_lines.add(event_line_id)
            if _review_row_support_requested(row):
                if task_id:
                    historical_support_tasks.add(task_id)
                if event_line_id:
                    historical_support_event_lines.add(event_line_id)
            blocker_text = _review_row_blocker_text(row)
            if blocker_text and event_line_id:
                historical_blockers[event_line_id] = blocker_text

        new_signals: list[TrendSignalRecord] = []

        recent_due_date_change_stats = _recent_due_date_change_stats(current_task_ids)
        repeated_reschedules: list[tuple[WeeklyReviewTaskEntryRecord, dict[str, object]]] = []
        for item in items:
            stats = recent_due_date_change_stats.get(item.taskId)
            if not stats:
                continue
            change_count = int(stats.get("changeCount") or 0)
            week_count = len(stats.get("weeks") or set())
            if change_count >= 2 and week_count >= 2:
                repeated_reschedules.append((item, stats))
        if repeated_reschedules:
            related_task_ids = [item.taskId for item, _ in repeated_reschedules[:5]]
            sample_titles = "、".join(current_titles.get(task_id, task_id) for task_id in related_task_ids[:2])
            new_signals.append(
                TrendSignalRecord(
                    key="repeat_reschedule::cross_week",
                    title="改期开始连续化",
                    statement=f"过去 2-3 周内至少 {len(repeated_reschedules)} 条任务反复改期，其中 {sample_titles or '相关任务'} 已跨周调整，说明排期不只是本周波动，而是推进路径尚未稳定。",
                    signalType="repeat_reschedule",
                    severity="high" if len(repeated_reschedules) >= 2 else "medium",
                    windowLabel="连续 2-3 周",
                    relatedEventLineId=None,
                    relatedTaskIds=related_task_ids,
                    evidenceRefs=[
                        ReviewDashboardEvidenceRefRecord(
                            sourceType="task",
                            sourceId=item.taskId,
                            title=item.taskSnapshot.title,
                            summary=f"过去 2-3 周改期 {int(stats.get('changeCount') or 0)} 次",
                        )
                        for item, stats in repeated_reschedules[:4]
                    ],
                    target=ReviewDashboardCardTargetRecord(
                        targetType="task_view",
                        targetId="builtin:risk",
                        targetLabel="风险视图",
                        targetFilters={"onlyRisky": True, "relatedTaskIds": related_task_ids},
                    ),
                )
            )

        repeated_review_items = [
            item
            for item in items
            if bool(item.taskSnapshot.orgContext and item.taskSnapshot.orgContext.needsReview)
            and (
                item.taskId in historical_review_tasks
                or _normalize_event_line_reference(item.taskSnapshot.eventLineId or (item.taskSnapshot.eventLineContext.id if item.taskSnapshot.eventLineContext else None)) in historical_review_event_lines
            )
        ]
        if repeated_review_items:
            related_task_ids = [item.taskId for item in repeated_review_items[:5]]
            new_signals.append(
                TrendSignalRecord(
                    key="repeat_review_pending::cross_week",
                    title="待复核事项连续两周未收束",
                    statement=f"当前仍有 {len(repeated_review_items)} 条任务连续两周停在复核/确认链上，问题已经从一次性审批延迟，变成持续拖慢推进的结构性回收链。",
                    signalType="repeat_review_pending",
                    severity="high" if len(repeated_review_items) >= 2 else "medium",
                    windowLabel="连续 2 周",
                    relatedEventLineId=None,
                    relatedTaskIds=related_task_ids,
                    evidenceRefs=[
                        ReviewDashboardEvidenceRefRecord(
                            sourceType="task",
                            sourceId=item.taskId,
                            title=item.taskSnapshot.title,
                            summary="连续两周待复核或待确认",
                        )
                        for item in repeated_review_items[:4]
                    ],
                    target=ReviewDashboardCardTargetRecord(
                        targetType="task_view",
                        targetId="builtin:risk",
                        targetLabel="风险视图",
                        targetFilters={"onlyRisky": True, "needsReview": True, "relatedTaskIds": related_task_ids},
                    ),
                )
            )

        repeated_support_items = [
            item
            for item in items
            if (
                item.structuredNote.supportNeeded.strip()
                or item.structuredNote.lightweightTag.strip() in {"需要支持", "资源不够", "等待他人"}
            )
            and (
                item.taskId in historical_support_tasks
                or _normalize_event_line_reference(item.taskSnapshot.eventLineId or (item.taskSnapshot.eventLineContext.id if item.taskSnapshot.eventLineContext else None)) in historical_support_event_lines
            )
        ]
        if repeated_support_items:
            related_task_ids = [item.taskId for item in repeated_support_items[:5]]
            new_signals.append(
                TrendSignalRecord(
                    key="repeat_support_request::cross_week",
                    title="支持依赖连续两周未化解",
                    statement=f"当前至少 {len(repeated_support_items)} 条任务连续两周提到支持或外部依赖，这不再是偶发协作缺口，而是需要管理层介入收束的协作链问题。",
                    signalType="repeat_support_request",
                    severity="medium" if len(repeated_support_items) == 1 else "high",
                    windowLabel="连续 2 周",
                    relatedEventLineId=None,
                    relatedTaskIds=related_task_ids,
                    evidenceRefs=[
                        ReviewDashboardEvidenceRefRecord(
                            sourceType="task",
                            sourceId=item.taskId,
                            title=item.taskSnapshot.title,
                            summary=_first_nonempty_text(item.structuredNote.supportNeeded, item.structuredNote.lightweightTag, item.note),
                        )
                        for item in repeated_support_items[:4]
                    ],
                    target=ReviewDashboardCardTargetRecord(
                        targetType="task_view",
                        targetId="builtin:risk",
                        targetLabel="风险视图",
                        targetFilters={"onlyRisky": True, "relatedTaskIds": related_task_ids},
                    ),
                )
            )

        escalating_blocker_items: list[tuple[WeeklyReviewTaskEntryRecord, str]] = []
        for item in items:
            event_line_id = _normalize_event_line_reference(
                item.taskSnapshot.eventLineId or (item.taskSnapshot.eventLineContext.id if item.taskSnapshot.eventLineContext else None)
            )
            if not event_line_id:
                continue
            current_blocker = _first_nonempty_text(
                item.structuredNote.blockerReason,
                item.taskSnapshot.eventLineContext.currentBlocker if item.taskSnapshot.eventLineContext else None,
                item.taskSnapshot.projectContext.currentBlocker if item.taskSnapshot.projectContext else None,
            )
            if not current_blocker or event_line_id not in historical_blockers:
                continue
            escalating_blocker_items.append((item, current_blocker))
        if escalating_blocker_items:
            related_task_ids = [item.taskId for item, _ in escalating_blocker_items[:5]]
            primary_item, primary_blocker = escalating_blocker_items[0]
            primary_event_line_id = _normalize_event_line_reference(
                primary_item.taskSnapshot.eventLineId or (primary_item.taskSnapshot.eventLineContext.id if primary_item.taskSnapshot.eventLineContext else None)
            )
            new_signals.append(
                TrendSignalRecord(
                    key=f"escalating_blocker::{primary_event_line_id or primary_item.taskId}",
                    title=f"{primary_item.taskSnapshot.eventLineName or primary_item.taskSnapshot.title} 阻塞升级",
                    statement=f"{primary_item.taskSnapshot.eventLineName or primary_item.taskSnapshot.title} 连续两周都卡在“{primary_blocker}”，如果下一周还不收束，这条线会继续从局部问题升级成趋势性风险。",
                    signalType="escalating_blocker",
                    severity="high",
                    windowLabel="连续 2 周",
                    relatedEventLineId=primary_event_line_id or None,
                    relatedTaskIds=related_task_ids,
                    evidenceRefs=[
                        ReviewDashboardEvidenceRefRecord(
                            sourceType="task",
                            sourceId=item.taskId,
                            title=item.taskSnapshot.title,
                            summary=blocker_text,
                        )
                        for item, blocker_text in escalating_blocker_items[:4]
                    ],
                    target=ReviewDashboardCardTargetRecord(
                        targetType="event_line" if primary_event_line_id else "task_view",
                        targetId=primary_event_line_id or "builtin:risk",
                        targetLabel=primary_item.taskSnapshot.eventLineName or primary_item.taskSnapshot.title,
                        targetFilters={} if primary_event_line_id else {"onlyRisky": True, "relatedTaskIds": related_task_ids},
                    ),
                )
            )

        if not new_signals:
            return analysis

        return analysis.model_copy(
            update={
                "trendSignals": _merge_trend_signals(list(analysis.trendSignals or []), new_signals),
            }
        )

    def _narratives_from_event_line_judgments(
        analysis: WeeklyReviewAnalysisRecord | None,
    ) -> list[NarrativeAnalysisRecord]:
        if analysis is None or not analysis.eventLineJudgments:
            return []
        bundle_by_id = {
            bundle.eventLineId: bundle
            for bundle in (analysis.eventLineContextBundles or [])
            if bundle.eventLineId
        }
        narratives: list[NarrativeAnalysisRecord] = []
        for judgment in analysis.eventLineJudgments[:4]:
            bundle = bundle_by_id.get(judgment.eventLineId)
            missing_lines: list[str] = []
            if bundle:
                if not bundle.keyPeople:
                    missing_lines.append("关键对象和角色")
                if not bundle.collaborationRelationship:
                    missing_lines.append("合作关系")
                if not bundle.recentFacts and not bundle.meetingFacts and not bundle.attachmentFacts:
                    missing_lines.append("近期证据")
            current_progress = judgment.nextWeekFocus
            if bundle and bundle.recentProgress:
                current_progress = bundle.recentProgress
            narratives.append(
                NarrativeAnalysisRecord(
                    eventLineId=judgment.eventLineId,
                    eventLineName=judgment.title,
                    clientName=bundle.projectName if bundle and bundle.projectName else None,
                    whatThisIs=judgment.whatHappened,
                    whyImportant=judgment.whyItMatters,
                    currentProgress=current_progress,
                    missingUnderstanding="、".join(missing_lines) if missing_lines else judgment.evidenceSummary,
                    riskNote=judgment.riskIfIgnored or None,
                    minimumAction=judgment.minimumAction or None,
                    managementAdvice=judgment.managerImplication or None,
                    contextLayersUsed=[
                        label
                        for label, available in [
                            ("organization_dna", True),
                            ("client_profile", bool(bundle and bundle.projectName)),
                            ("cooperation_relationship", bool(bundle and bundle.collaborationRelationship)),
                            ("event_line_history", bool(bundle and bundle.recentFacts)),
                            ("current_tasks", True),
                        ]
                        if available
                    ],
                    confidenceLevel="high"
                    if judgment.safeOutputMode == "full_judgment"
                    else "medium"
                    if judgment.safeOutputMode == "summary_only"
                    else "low",
                )
            )
        narratives.sort(key=lambda item: ((item.eventLineName or "").strip(), (item.eventLineId or "").strip()))
        return narratives

    def _weekly_overview_cache_payload(
        *,
        week_label: str,
        items: list[WeeklyReviewTaskEntryRecord],
        narratives: list[NarrativeAnalysisRecord],
        org_modules: list[OrganizationDnaModuleRecord],
    ) -> dict[str, object]:
        cache_version = "v2-line-cards"
        task_signatures = sorted(
            [
            {
                "taskId": item.taskId,
                "title": item.taskSnapshot.title,
                "note": item.note,
                "client": item.taskSnapshot.clientName,
                "eventLine": item.taskSnapshot.eventLineName,
            }
            for item in items
            ],
            key=lambda item: (
                str(item.get("eventLine") or ""),
                str(item.get("client") or ""),
                str(item.get("title") or ""),
                str(item.get("taskId") or ""),
            ),
        )
        narrative_signatures = sorted(
            [
            {
                "eventLineId": item.eventLineId,
                "eventLineName": item.eventLineName,
                "whatThisIs": item.whatThisIs,
                "whyImportant": item.whyImportant,
                "currentProgress": item.currentProgress,
                "missingUnderstanding": item.missingUnderstanding,
            }
            for item in narratives
            ],
            key=lambda item: (
                str(item.get("eventLineName") or ""),
                str(item.get("eventLineId") or ""),
            ),
        )
        module_signatures = sorted(
            [
            {
                "moduleKey": item.moduleKey,
                "title": item.title,
                "updatedAt": item.updatedAt,
                "summary": item.summary[:160],
            }
            for item in org_modules[:6]
            ],
            key=lambda item: (
                str(item.get("title") or ""),
                str(item.get("moduleKey") or ""),
            ),
        )
        fingerprint_source = json.dumps(
            {
                "cacheVersion": cache_version,
                "weekLabel": week_label,
                "tasks": task_signatures,
                "narratives": narrative_signatures,
                "modules": module_signatures,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return {
            "cacheVersion": cache_version,
            "fingerprint": hashlib.sha1(fingerprint_source.encode("utf-8")).hexdigest(),
        }

    def _load_cached_weekly_overview(
        *,
        week_label: str,
        fingerprint: str,
    ) -> tuple[str, list[str], list[str]] | None:
        raw = state.db.get_setting(f"weekly_overview_cache::{week_label}", "")
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        if not isinstance(payload, dict) or str(payload.get("fingerprint") or "") != fingerprint:
            return None
        return (
            str(payload.get("overview") or ""),
            [str(item) for item in payload.get("focusLines") or [] if str(item).strip()],
            [str(item) for item in payload.get("nextFocus") or [] if str(item).strip()],
        )

    def _save_cached_weekly_overview(
        *,
        week_label: str,
        fingerprint: str,
        overview: str,
        focus_lines: list[str],
        next_focus: list[str],
    ) -> None:
        state.db.set_setting(
            f"weekly_overview_cache::{week_label}",
            json.dumps(
                {
                    "cacheVersion": "v2-line-cards",
                    "fingerprint": fingerprint,
                    "overview": overview,
                    "focusLines": focus_lines,
                    "nextFocus": next_focus,
                    "updatedAt": now_iso(),
                },
                ensure_ascii=False,
            ),
        )

    def local_rollup_work_items(week_label: str) -> list[WeeklyReviewTaskEntryRecord]:
        rows = state.db.fetchall(
            """
            SELECT e.*
            FROM weekly_review_task_entries e
            INNER JOIN weekly_reviews r ON r.id = e.review_id
            WHERE e.week_label = ? AND e.content_domain = 'work'
            ORDER BY e.reviewed_at DESC, e.created_at DESC
            """,
            (week_label,),
        )
        items: list[WeeklyReviewTaskEntryRecord] = []
        for row in rows:
            task_id = str(row["task_id"])
            task_rows = fetch_tasks("t.id = ?", (task_id,))
            note = str(row["note"] or "")
            structured_note = coerce_review_structured_note(row["structured_note_json"])
            snapshot = from_json(str(row["task_snapshot_json"] or "{}"), {})
            if task_rows:
                task = task_rows[0]
                merged_snapshot = {
                    **_task_snapshot_from_task(task, state.db),
                    **(snapshot if isinstance(snapshot, dict) else {}),
                }
                items.append(
                    _review_entry_from_task(
                        task=task,
                        week_label=week_label,
                        content_domain="work",
                        review_id=str(row["review_id"]),
                        note=note,
                        structured_note=structured_note,
                        reviewed_at=str(row["reviewed_at"]) if row["reviewed_at"] else None,
                        snapshot=merged_snapshot,
                        db=state.db,
                    )
                )
                continue
            if isinstance(snapshot, dict) and snapshot:
                items.append(
                    WeeklyReviewTaskEntryRecord(
                        id=str(row["id"]),
                        reviewId=str(row["review_id"]),
                        taskId=task_id,
                        weekLabel=week_label,
                        contentDomain="work",
                        note=note,
                        structuredNote=structured_note,
                        reviewedAt=str(row["reviewed_at"]) if row["reviewed_at"] else None,
                        taskSnapshot=snapshot,  # type: ignore[arg-type]
                    )
                )
        return items

    def build_executive_review_overlay(
        week_label: str,
    ) -> tuple[HierarchyReportRecord | None, list[HierarchyReportRecord], ReviewSimulationBundleRecord | None]:
        session_user = get_cached_session_user()
        if not session_user:
            return None, [], None
        governance = _review_governance_with_members()
        viewer_role = _resolve_review_viewer_role(session_user, governance)
        base_org_modules = list_organization_dna_modules()
        org_model_profile: OrgModelProfileRecord | None = None
        try:
            org_model_payload = cloud_request("GET", "/api/v1/settings/org-model/profile")
            if isinstance(org_model_payload, dict):
                org_model_profile = OrgModelProfileRecord(**org_model_payload)
        except HTTPException:
            org_model_profile = None
        work_items = local_rollup_work_items(week_label)
        agent_work_items = build_agent_weekly_review_items(
            db=state.db,
            week_label=week_label,
            thread_sync_path=THREAD_SYNC_DOC_PATH,
        )
        org_modules = build_review_context_modules([*work_items, *agent_work_items], base_org_modules)
        executive_org_report, department_reports = build_executive_review_rollup(
            week_label=week_label,
            work_items=[*work_items, *agent_work_items],
            governance=governance,
            organization_dna_modules=org_modules,
            org_model_profile=org_model_profile,
        )
        if viewer_role != "admin":
            lead_department = _review_department_for_session_user(session_user, governance)
            if not lead_department:
                return None, [], None
            return None, [report for report in department_reports if report.scopeRefId == lead_department.name], None
        simulation_bundle = build_review_simulation_bundle(
            week_label=week_label,
            organization_dna_modules=base_org_modules,
        )
        return executive_org_report, department_reports, simulation_bundle

    def augment_review_response(response: ReviewResponse, week_label: str | None = None) -> ReviewResponse:
        target_week = week_label or (response.currentReview.weekLabel if response.currentReview else current_review_week_label())
        work_analysis = response.workAnalysis
        personal_analysis = response.personalAnalysis
        session_user = get_cached_session_user()
        governance = _review_governance_with_members() if session_user else None
        viewer_role = _resolve_review_viewer_role(session_user, governance)
        org_model_profile: OrgModelProfileRecord | None = None
        try:
            org_model_payload = cloud_request("GET", "/api/v1/settings/org-model/profile")
            if isinstance(org_model_payload, dict):
                org_model_profile = OrgModelProfileRecord(**org_model_payload)
        except HTTPException:
            org_model_profile = None
        if work_analysis is None or personal_analysis is None:
            computed_work_analysis, computed_personal_analysis = build_review_analyses(
                target_week,
                response.workItems,
                response.personalItems,
                org_model_profile=org_model_profile,
                viewer_role=viewer_role,
            )
            work_analysis = work_analysis or computed_work_analysis
            personal_analysis = personal_analysis or computed_personal_analysis
        work_analysis = _enrich_weekly_review_analysis_with_memory(work_analysis, viewer_role=viewer_role)
        work_analysis = _enrich_weekly_review_analysis_with_operational_trends(
            work_analysis,
            response.workItems,
            target_week,
        )
        weekly_overview = ""
        weekly_focus_lines: list[str] = []
        weekly_next_focus: list[str] = []
        if work_analysis is not None and response.workItems:
            narrative_modules = build_review_context_modules(response.workItems, list_organization_dna_modules())
            narrative_analyses = _narratives_from_event_line_judgments(work_analysis)
            cache_payload = _weekly_overview_cache_payload(
                week_label=target_week,
                items=response.workItems,
                narratives=narrative_analyses,
                org_modules=narrative_modules,
            )
            fingerprint = str(cache_payload["fingerprint"])
            cached_overview = _load_cached_weekly_overview(
                week_label=target_week,
                fingerprint=fingerprint,
            )
            if cached_overview is not None:
                weekly_overview, weekly_focus_lines, weekly_next_focus = cached_overview
            else:
                # Collect attachment texts from local cache (populated when user previews event lines)
                review_attachment_texts: list[str] = []
                cache_dir = _att_cache_dir()
                for text_cache_file in sorted(cache_dir.glob("*.text.json"))[:10]:
                    try:
                        td = json.loads(text_cache_file.read_bytes())
                        t = str(td.get("text", "")).strip()
                        title = str(td.get("title", "")).strip()
                        if t and len(t) > 100 and "提取失败" not in t and "No module" not in t:
                            review_attachment_texts.append(f"【{title}】\n{t}")
                    except Exception:
                        continue
                # Gather local project memory for AI context (fast — reads local files only)
                try:
                    client_ids = list({item.taskSnapshot.clientId for item in response.workItems if item.taskSnapshot.clientId})
                    el_ids = list({item.taskSnapshot.eventLineId for item in response.workItems if item.taskSnapshot.eventLineId})
                    local_memory = gather_project_context_for_ai(state.data_dir, client_ids, el_ids)
                except Exception:
                    local_memory = ""
                weekly_overview, weekly_focus_lines, weekly_next_focus = build_weekly_overview_draft(
                    ai=state.ai,
                    week_label=target_week,
                    items=response.workItems,
                    org_dna_modules=narrative_modules,
                    narratives=narrative_analyses,
                    fallback_overview=work_analysis.weeklyOverview,
                    fallback_focus_lines=work_analysis.weeklyFocusLines,
                    fallback_next_focus=work_analysis.weeklyNextFocus,
                    attachment_texts=review_attachment_texts,
                    local_memory_context=local_memory,
                )
                # Only cache AI-generated content (contains structured sections), never cache fallback
                if "\u3010" in weekly_overview:
                    _save_cached_weekly_overview(
                        week_label=target_week,
                        fingerprint=fingerprint,
                        overview=weekly_overview,
                        focus_lines=weekly_focus_lines,
                        next_focus=weekly_next_focus,
                    )
                    # Auto-update weekly memory snapshot + extract quotes from overview
                    try:
                        write_weekly_memory(state.data_dir, target_week, weekly_overview)
                        # Extract golden quotes from weekly overview (cross-project insights)
                        from app.services.local_memory import extract_quotes_from_text, save_pending_quotes
                        overview_quotes = extract_quotes_from_text(state.ai, weekly_overview, "周复盘概览")
                        if overview_quotes:
                            save_pending_quotes(state.db, overview_quotes)
                        # Check if it's time to dream (memory consolidation)
                        if should_dream(state.data_dir):
                            import threading as _dream_thr
                            _dream_thr.Thread(target=run_dream_cycle, args=(state.data_dir,), kwargs={"db": state.db}, daemon=True).start()
                    except Exception:
                        pass
            work_analysis = work_analysis.model_copy(
                update={
                    "narrativeAnalyses": narrative_analyses,
                    "weeklyOverview": weekly_overview,
                    "weeklyFocusLines": weekly_focus_lines,
                    "weeklyNextFocus": weekly_next_focus,
                }
            )
        self_report = response.selfReport
        if self_report is None and work_analysis is not None and response.workItems:
            self_report = build_employee_review_report(
                week_label=target_week,
                scope_ref_id=(response.currentReview.userId if response.currentReview else "self"),
                items=response.workItems,
                analysis=work_analysis,
                org_model_profile=org_model_profile,
                viewer_role=viewer_role,
            )
        # Override selfReport with AI-generated structured overview if available
        if self_report is not None and work_analysis is not None and weekly_overview and "【" in weekly_overview:
            # Extract headline (first line before any 【 section)
            overview_lines = weekly_overview.strip().split("\n")
            ai_headline = overview_lines[0].strip() if overview_lines else ""
            self_report = self_report.model_copy(
                update={
                    "headline": ai_headline or self_report.headline,
                    "summary": weekly_overview,
                    "focusAreas": weekly_focus_lines or self_report.focusAreas,
                    "suggestedActions": weekly_next_focus or self_report.suggestedActions,
                }
            )
        executive_org_report, department_reports, simulation_bundle = build_executive_review_overlay(target_week)
        # Override executiveOrgReport with AI overview too
        if executive_org_report is not None and work_analysis is not None and weekly_overview and "【" in weekly_overview:
            overview_lines = weekly_overview.strip().split("\n")
            ai_headline = overview_lines[0].strip() if overview_lines else ""
            executive_org_report = executive_org_report.model_copy(
                update={
                    "headline": ai_headline or executive_org_report.headline,
                    "summary": weekly_overview,
                    "suggestedActions": weekly_next_focus or executive_org_report.suggestedActions,
                }
            )
        # Async: write review notes to memory using LOCAL event line data (cloud returns null)
        if response.workItems:
            import threading as _mem_thr
            def _bg_write_review_memory():
                try:
                    # Build local event line → client mapping from DB
                    el_rows = state.db.fetchall("SELECT id, name, primary_client_id, primary_client_name FROM event_lines")
                    el_map = {str(r["id"]): r for r in el_rows}

                    # Group notes by client (using local mapping)
                    by_client: dict[str, tuple[str, list[tuple[str, str]]]] = {}  # cid → (cname, [(title, note)])

                    for item in response.workItems:
                        note = (item.note or "").strip()
                        if not note:
                            continue
                        snap = item.taskSnapshot
                        title = snap.title

                        # Try to find the right client from local event line data
                        el_id = snap.eventLineId or ""
                        cid = snap.clientId or ""
                        cname = snap.clientName or ""

                        # If cloud didn't provide eventLineId, try matching by:
                        # 1. Client name in task title (e.g. "日慈" in "日慈笑雨Q1...")
                        # 2. Event line name substring in task title
                        if not el_id:
                            for eid, erow in el_map.items():
                                el_name = str(erow["name"])
                                client_name_local = str(erow["primary_client_name"] or "")
                                # Match by client name or its first 2 chars (e.g. "日慈" from "日慈基金会")
                                client_short = client_name_local[:2] if len(client_name_local) >= 2 else ""
                                if client_name_local and len(client_name_local) >= 2 and (client_name_local in title or (client_short and client_short in title)):
                                    el_id = eid

```
