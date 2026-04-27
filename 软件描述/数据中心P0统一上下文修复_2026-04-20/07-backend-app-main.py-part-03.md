# 源码文件：`backend/app/main.py`（分片 03）

- 行号范围：5601-8400
- 总行数：   30416
- 导出时间：2026-04-20

```python
        project_structures: dict[str, ProjectStructureResponse],
    ) -> dict[str, str]:
        payload: dict[str, str] = {}
        event_line_by_id = {item.id: item for item in event_lines}
        existing_event_line = event_line_by_id.get(task.eventLineId or "")
        resolved_client_id = (task.clientId or "").strip() or ((existing_event_line.primaryClientId or "").strip() if existing_event_line else "")
        if existing_event_line and existing_event_line.primaryClientId:
            event_line_client_id = existing_event_line.primaryClientId.strip()
            if event_line_client_id and resolved_client_id != event_line_client_id:
                resolved_client_id = event_line_client_id
                payload["clientId"] = event_line_client_id

        resolved_event_line_id = (task.eventLineId or "").strip()
        if not resolved_event_line_id and resolved_client_id:
            inferred_event_line_id, _ = _infer_task_event_line(
                task.title,
                task.desc,
                event_lines,
                current_client_id=resolved_client_id,
            )
            if inferred_event_line_id:
                resolved_event_line_id = inferred_event_line_id
                payload["eventLineId"] = inferred_event_line_id
        resolved_event_line = event_line_by_id.get(resolved_event_line_id or "")

        if not resolved_client_id:
            return payload

        structure = project_structures.get(resolved_client_id)
        if structure is None:
            structure = build_project_structure(resolved_client_id)
            project_structures[resolved_client_id] = structure

        resolved_module_id = (task.projectModuleId or "").strip()
        resolved_flow_id = (task.projectFlowId or "").strip()
        if resolved_flow_id and not resolved_module_id:
            derived_module, derived_flow = resolve_project_structure_refs(
                resolved_client_id,
                None,
                resolved_flow_id,
                strict=False,
            )
            if derived_flow and derived_module:
                resolved_module_id = derived_module.id
                payload["projectModuleId"] = derived_module.id

        if not resolved_module_id:
            inferred_module_id, _ = _infer_task_project_module(
                task.title,
                task.desc,
                structure.modules,
                event_line=resolved_event_line,
            )
            if inferred_module_id:
                resolved_module_id = inferred_module_id
                payload["projectModuleId"] = inferred_module_id

        if not resolved_flow_id:
            inferred_flow_id, _ = _infer_task_project_flow(
                task.title,
                task.desc,
                structure.flows,
                selected_module_id=resolved_module_id or None,
                event_line=resolved_event_line,
            )
            if inferred_flow_id:
                payload["projectFlowId"] = inferred_flow_id
        return payload

    _EVENT_LINE_BOOTSTRAP_SKIP_KEYWORDS = ("吃饭", "健身", "体检", "相机", "飞北京", "机票", "拍照", "采购")
    _EVENT_LINE_BOOTSTRAP_HINT_KEYWORDS = (
        "合作",
        "系统",
        "方案",
        "数字化",
        "官网",
        "工作坊",
        "讨论",
        "诊断",
        "提纲",
        "资料",
        "计划",
        "战略",
        "介绍",
        "开源",
        "纪要",
        "流程",
        "汇总",
        "推进",
    )

    def _task_eligible_for_event_line_bootstrap(task: TaskRecord) -> bool:
        if not (task.clientId or "").strip():
            return False
        if (task.eventLineId or "").strip():
            return False
        title = (task.title or "").strip()
        desc = (task.desc or "").strip()
        text = f"{title}\n{desc}"
        if any(keyword in text for keyword in _EVENT_LINE_BOOTSTRAP_SKIP_KEYWORDS):
            return False
        if task.sourceType == "topic_candidate":
            return False
        if task.sourceType == "pressure_seed_doc_v2":
            return True
        if any(keyword in text for keyword in _EVENT_LINE_BOOTSTRAP_HINT_KEYWORDS):
            return True
        return len(desc) >= 40

    def _derive_event_line_name_from_task(task: TaskRecord) -> str:
        title = re.sub(r"\s+", " ", (task.title or "").strip())
        client_name = (task.clientName or "").strip()
        if client_name and title.lower().startswith(client_name.lower()):
            title = title[len(client_name):].strip(" -_:：|")
        if " " in title:
            first, rest = title.split(" ", 1)
            if rest and len(first.strip()) <= 4 and re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fff]+", first.strip()):
                if any(keyword in rest for keyword in _EVENT_LINE_BOOTSTRAP_HINT_KEYWORDS):
                    title = rest.strip()
        title = title.strip(" -_:：|")
        return title[:36] or (task.title or "").strip()[:36] or "未命名事件线"

    def _derive_event_line_kind_from_task(task: TaskRecord) -> str:
        text = f"{task.title}\n{task.desc}".strip()
        if any(keyword in text for keyword in ("约见", "介绍", "讨论", "会", "对接", "沟通")):
            return "coordination_line"
        if any(keyword in text for keyword in ("问题", "阻塞", "卡点", "待补", "待确认")):
            return "issue_line"
        return "project_line"

    def _build_bootstrap_event_line_payload(task: TaskRecord) -> EventLineCreatePayload:
        project_context = task.projectContext
        line_name = _derive_event_line_name_from_task(task)
        summary = (
            (project_context.currentFocus if project_context and project_context.currentFocus else None)
            or (project_context.recentProgress if project_context and project_context.recentProgress else None)
            or (task.desc.strip() if task.desc else None)
            or f"围绕“{line_name}”持续推进。"
        )
        intent = (
            (project_context.goalSummary if project_context and project_context.goalSummary else None)
            or (task.desc.strip() if task.desc else None)
            or f"把“{line_name}”这条线的任务、会议和资料沉淀到同一上下文里。"
        )
        current_blocker = (
            (project_context.currentBlocker if project_context and project_context.currentBlocker else None)
            or (project_context.riskSummary if project_context and project_context.riskSummary else None)
        )
        next_step = (
            (project_context.nextAction if project_context and project_context.nextAction else None)
            or ("继续推进并明确下一步关键动作。" if task.status != "done" else "在已有推进基础上明确下一阶段动作。")
        )
        recent_decision = (
            (project_context.recentProgress if project_context and project_context.recentProgress else None)
            or ("本周已完成一个关键动作，可据此继续推进。" if task.status == "done" else None)
        )
        stage = (
            (project_context.stage if project_context and project_context.stage else None)
            or ("推进中" if task.status != "done" else "已有阶段结果")
        )
        participant_ids = [task.ownerId] if task.ownerId else []
        return EventLineCreatePayload(
            name=line_name,
            kind=_derive_event_line_kind_from_task(task),  # type: ignore[arg-type]
            status="active",
            stage=stage,
            summary=summary[:160] if summary else None,
            intent=intent[:200] if intent else None,
            currentBlocker=current_blocker[:120] if current_blocker else None,
            recentDecision=recent_decision[:120] if recent_decision else None,
            nextStep=next_step[:120] if next_step else None,
            ownerId=task.ownerId,
            primaryClientId=task.clientId,
            participantIds=participant_ids,
        )

    def build_client_dna_context(client_id: str, prompt: str, max_chars: int = 2200) -> str:
        modules = [module for module in list_client_dna_modules(client_id) if module.hasDocument and module.normalizedText.strip()]
        rows = state.db.fetchall("SELECT * FROM dna_terms WHERE client_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 8", (client_id,))
        if not modules and not rows:
            return ""

        tokens = tokenize(prompt)

        def module_rank(module: ClientDnaModuleRecord) -> tuple[int, int, str]:
            text = f"{module.title}\n{module.summary}\n{module.normalizedText[:2400]}".lower()
            match_count = sum(1 for token in tokens if token and token in text)
            return (1 if match_count > 0 else 0, match_count, module.updatedAt or "")

        ordered_modules = sorted(modules, key=module_rank, reverse=True)
        lines = [
            "客户背景底稿（仅用于理解客户，不作为正式引证）：",
            "背景底稿使用规则=背景底稿只用于理解客户、修正语境和帮助组织分析，不作为正式引证或确定性事实来源。",
        ]
        for module in ordered_modules[:4]:
            preview = module.summary.strip() or re.sub(r"\s+", " ", module.normalizedText).strip()[:360]
            if preview:
                lines.append(f"[{module.title}] {preview}")
        if rows:
            lines.append("客户补充词条（仅用于补足背景语境）：")
            for row in rows[:8]:
                aliases = _parse_json_list(row["aliases_json"])
                alias_text = f"；别名：{'、'.join(aliases[:4])}" if aliases else ""
                lines.append(f"- [{row['category']}] {row['canonical_name']}：{row['description']}{alias_text}")
        return "\n\n".join(lines)[:max_chars]

    def build_client_dna_priority_note(client_id: str, prompt: str, max_items: int = 3) -> str:
        modules = [module for module in list_client_dna_modules(client_id) if module.hasDocument and module.normalizedText.strip()]
        if not modules:
            return ""
        tokens = tokenize(prompt)

        def module_rank(module: ClientDnaModuleRecord) -> tuple[int, int, str]:
            text = f"{module.title}\n{module.summary}\n{module.normalizedText[:1600]}".lower()
            match_count = sum(1 for token in tokens if token and token in text)
            return (1 if match_count > 0 else 0, match_count, module.updatedAt or "")

        ordered_modules = sorted(modules, key=module_rank, reverse=True)
        top_titles = [module.title for module in ordered_modules[:max_items]]
        return "本次已优先参考客户 DNA 背景：" + "、".join(top_titles)

    def build_client_memory_background_context(
        client_id: str,
        prompt: str,
        *,
        max_chars: int = 2400,
    ) -> tuple[str, dict[str, object]]:
        notebook_response = get_client_notebook_response(state.db, client_id)
        memory_status = get_client_memory_status(state.db, client_id)
        snapshot = notebook_response.organizationNotebookSnapshot
        key_facts = notebook_response.keyFacts
        linked_event_lines = notebook_response.linkedEventLines
        if not snapshot and not key_facts and not linked_event_lines:
            return "", {"memoryBackgroundUsed": False}

        prompt_tokens = tokenize(prompt)

        def compact(value: object, *, limit: int = 220) -> str:
            text = re.sub(r"\s+", " ", str(value or "")).strip()
            return text[:limit]

        def event_line_rank(memory_snapshot) -> tuple[int, int, str]:
            text = "\n".join(
                item
                for item in (
                    compact(memory_snapshot.lineName, limit=80),
                    compact(memory_snapshot.currentStage, limit=80),
                    compact(memory_snapshot.currentWork, limit=160),
                    compact(memory_snapshot.currentBlocker, limit=160),
                    compact(memory_snapshot.recentDecision, limit=160),
                    compact(memory_snapshot.nextStep, limit=160),
                )
                if item
            ).lower()
            match_count = sum(1 for token in prompt_tokens if token and token in text)
            return (1 if match_count > 0 else 0, match_count, memory_snapshot.updatedAt or "")

        event_line_snapshots: list[object] = []
        for line in linked_event_lines[:8]:
            memory_response = get_event_line_memory_response(state.db, line.id)
            if memory_response.eventLineMemorySnapshot:
                event_line_snapshots.append(memory_response.eventLineMemorySnapshot)
        ordered_event_lines = sorted(event_line_snapshots, key=event_line_rank, reverse=True)

        lines = [
            "统一记忆背景（仅用于帮助理解组织与推进，不作为正式引证）：",
            "统一记忆使用规则=统一记忆只作为背景上下文，帮助理解组织现状、事件线推进和待澄清问题；它不能作为 citation，也不能替代原始证据。",
        ]
        if snapshot:
            notebook_parts = [
                compact(snapshot.organizationIntro, limit=200),
                compact(snapshot.collaborationRelationship, limit=220),
            ]
            notebook_text = "；".join(item for item in notebook_parts if item)
            if notebook_text:
                lines.append(f"组织笔记：{notebook_text}")
            if snapshot.currentStage:
                lines.append(f"组织当前阶段：{compact(snapshot.currentStage, limit=120)}")
            if snapshot.businessModules:
                lines.append(f"主要业务模块：{'；'.join(compact(item, limit=80) for item in snapshot.businessModules[:4])}")
            if snapshot.collaborationGoals:
                lines.append(f"当前合作目标：{'；'.join(compact(item, limit=90) for item in snapshot.collaborationGoals[:3])}")
            if snapshot.currentChallenges:
                lines.append(f"当前组织困境：{'；'.join(compact(item, limit=90) for item in snapshot.currentChallenges[:3])}")
        if key_facts:
            lines.append("已确认背景事实（来自组织笔记/澄清结果，只作背景，不作引用）：")
            for fact in key_facts[:4]:
                lines.append(f"- {compact(fact.factValue, limit=180)}")
        # Inject chat-extracted facts (cross-conversation memory)
        chat_fact_rows = state.db.fetchall(
            """
            SELECT fact_key, fact_value, valid_from, valid_to, confidence
            FROM memory_facts
            WHERE scope_type = 'client' AND scope_id = ? AND source_type = 'chat_extraction'
              AND (valid_to IS NULL OR valid_to >= date('now'))
            ORDER BY updated_at DESC LIMIT 6
            """,
            (client_id,),
        )
        if chat_fact_rows:
            lines.append("对话沉淀记忆（从历次对话中自动提取的关键事实，只作背景，不作引用）：")
            for row in chat_fact_rows:
                validity = ""
                if row["valid_to"]:
                    validity = f"（有效期至{row['valid_to']}）"
                lines.append(f"- [{row['fact_key']}] {compact(row['fact_value'], limit=180)}{validity}")
        if ordered_event_lines:
            lines.append("相关事件线记忆（只作背景，不作引用）：")
            for item in ordered_event_lines[:3]:
                event_line_parts = [
                    f"阶段：{compact(item.currentStage, limit=60)}" if item.currentStage else "",
                    f"当前事项：{compact(item.currentWork, limit=100)}" if item.currentWork else "",
                    f"当前阻塞：{compact(item.currentBlocker, limit=100)}" if item.currentBlocker else "",
                    f"最近决策：{compact(item.recentDecision, limit=100)}" if item.recentDecision else "",
                    f"下一步：{compact(item.nextStep, limit=100)}" if item.nextStep else "",
                ]
                event_line_text = "；".join(part for part in event_line_parts if part)
                if event_line_text:
                    lines.append(f"- [{item.lineName}] {event_line_text}")
        missing_slots = list(snapshot.informationGaps[:3] if snapshot else [])
        if missing_slots:
            lines.append(f"当前待澄清槽位：{'；'.join(compact(item, limit=80) for item in missing_slots)}")

        source_labels = [
            "organization_notebook" if snapshot else "",
            "key_facts" if key_facts else "",
            "event_line_memory" if ordered_event_lines else "",
        ]
        confidence_candidates = [
            float(snapshot.confidence) if snapshot else 0.0,
            *(float(item.confidence) for item in ordered_event_lines[:3]),
        ]
        meta = {
            "memoryBackgroundUsed": True,
            "memoryBackgroundSources": [item for item in source_labels if item],
            "memoryBackgroundConfidence": round(max(confidence_candidates) if confidence_candidates else 0.0, 2),
            "memoryMissingFacts": missing_slots,
            "memoryEventLineCount": len(ordered_event_lines),
            "memoryPendingClarifications": int(memory_status.pendingClarifications),
        }
        return "\n\n".join(lines)[:max_chars], meta

    def build_client_dna_retrieval_hint(client_id: str, prompt: str, max_terms: int = 6) -> list[str]:
        modules = [module for module in list_client_dna_modules(client_id) if module.hasDocument and (module.summary.strip() or module.normalizedText.strip())]
        rows = state.db.fetchall("SELECT * FROM dna_terms WHERE client_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 8", (client_id,))
        if not modules and not rows:
            return []

        prompt_tokens = set(tokenize(prompt))
        hint_terms: list[str] = []

        def append_tokens(source_text: str) -> None:
            for token in tokenize(source_text):
                if token in prompt_tokens or token in hint_terms:
                    continue
                hint_terms.append(token)
                if len(hint_terms) >= max_terms:
                    return

        for module in sorted(modules, key=lambda item: (item.updatedAt or "", item.title), reverse=True)[:3]:
            append_tokens(f"{module.title} {module.summary or module.normalizedText[:400]}")
            if len(hint_terms) >= max_terms:
                return hint_terms[:max_terms]
        for row in rows:
            append_tokens(f"{row['category']} {row['canonical_name']} {row['description']}")
            if len(hint_terms) >= max_terms:
                return hint_terms[:max_terms]
        return hint_terms[:max_terms]

    def build_client_dna_term_context(client_id: str, max_chars: int = 1200) -> str:
        rows = state.db.fetchall("SELECT * FROM dna_terms WHERE client_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 8", (client_id,))
        if not rows:
            return ""
        lines = ["客户补充 DNA：以下词条仅作为当前客户的补充语境。"]
        for row in rows:
            aliases = _parse_json_list(row["aliases_json"])
            alias_text = f"；别名：{'、'.join(aliases[:4])}" if aliases else ""
            lines.append(f"[{row['category']}] {row['canonical_name']}：{row['description']}{alias_text}")
        return "\n".join(lines)[:max_chars]

    def refresh_cloud_session() -> SessionUserRecord:
        refresh_token = get_cloud_refresh_token()
        if not refresh_token:
            raise HTTPException(status_code=401, detail="登录状态已过期，请重新登录")
        persist_session = state.cloud_session_persistent or _has_persisted_cloud_session()
        try:
            response = httpx.request(
                "POST",
                f"{state.cloud_api_url}/api/v1/auth/refresh",
                json={"refreshToken": refresh_token},
                timeout=20.0,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Cloud backend unavailable: {exc}") from exc
        if response.status_code >= 400:
            try:
                payload = response.json()
                detail = payload.get("detail") if isinstance(payload, dict) else response.text
            except Exception:
                detail = response.text
            if response.status_code in {401, 403}:
                clear_cloud_session()
            raise HTTPException(status_code=response.status_code, detail=detail or f"HTTP {response.status_code}")
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Invalid cloud refresh payload")
        token = str(payload.get("accessToken", ""))
        next_refresh_token = str(payload.get("refreshToken", ""))
        user_payload = payload.get("user")
        if not token or not next_refresh_token or not isinstance(user_payload, dict):
            raise HTTPException(status_code=502, detail="Cloud refresh payload missing session data")
        user = SessionUserRecord(**user_payload)
        set_cloud_session(token, user, persist=persist_session)
        set_cloud_refresh_token(next_refresh_token, persist=persist_session)
        return user

    # Circuit breaker: if cloud was unreachable, skip retries for 60s
    _cloud_circuit_breaker: dict[str, float] = {"last_failure": 0.0}

    class CloudUnavailableError(Exception):
        """Raised when cloud backend is unreachable. Caught by try/except Exception in local-first endpoints."""
        pass

    def cloud_request(method: str, path: str, *, json_body: dict | None = None, allow_unauthenticated: bool = False, timeout: float = 3.0) -> object:
        import time as _time

        # Fast fail if cloud was down recently (circuit breaker)
        if _time.time() - _cloud_circuit_breaker["last_failure"] < 60:
            raise CloudUnavailableError("Cloud backend unavailable (circuit breaker active)")

        def perform_request(token: str | None):
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            return httpx.request(
                method,
                f"{state.cloud_api_url}{path}",
                json=json_body,
                headers=headers,
                timeout=timeout,
            )

        token = get_cloud_token()
        if not token and not allow_unauthenticated:
            if get_cloud_refresh_token():
                refresh_cloud_session()
                token = get_cloud_token()
            else:
                raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            response = perform_request(token)
        except httpx.HTTPError:
            # Retry once on connection/timeout error
            _time.sleep(0.5)
            try:
                response = perform_request(token)
            except httpx.HTTPError as exc:
                _cloud_circuit_breaker["last_failure"] = _time.time()
                raise HTTPException(status_code=502, detail=f"Cloud backend unavailable: {exc}") from exc
        if response.status_code == 401 and not allow_unauthenticated and get_cloud_refresh_token():
            refresh_cloud_session()
            token = get_cloud_token()
            try:
                response = perform_request(token)
            except httpx.HTTPError as exc:
                _cloud_circuit_breaker["last_failure"] = _time.time()
                raise HTTPException(status_code=502, detail=f"Cloud backend unavailable: {exc}") from exc
        # Cloud responded — reset circuit breaker
        _cloud_circuit_breaker["last_failure"] = 0.0
        if response.status_code == 401 and not allow_unauthenticated:
            clear_cloud_session()
        if response.status_code == 403 and not allow_unauthenticated and path.startswith("/api/v1/auth/"):
            clear_cloud_session()
        if response.status_code >= 400:
            try:
                payload = response.json()
                detail = payload.get("detail") if isinstance(payload, dict) else response.text
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail or f"HTTP {response.status_code}")
        if not response.content:
            return {}
        return response.json()

    def cloud_upload_file(
        path: str,
        *,
        file_name: str,
        file_content: bytes,
        content_type: str = "application/octet-stream",
        form_fields: dict[str, str] | None = None,
    ) -> object:
        def _do_upload(token: str):
            headers = {"Authorization": f"Bearer {token}"}
            files = {"file": (file_name, file_content, content_type)}
            data = form_fields or {}
            return httpx.post(
                f"{state.cloud_api_url}{path}",
                headers=headers,
                files=files,
                data=data,
                timeout=60.0,
            )

        token = get_cloud_token()
        if not token:
            if get_cloud_refresh_token():
                refresh_cloud_session()
                token = get_cloud_token()
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            response = _do_upload(token)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Cloud upload unavailable: {exc}") from exc
        if response.status_code == 401 and get_cloud_refresh_token():
            refresh_cloud_session()
            token = get_cloud_token()
            if token:
                try:
                    response = _do_upload(token)
                except httpx.HTTPError as exc:
                    raise HTTPException(status_code=502, detail=f"Cloud upload unavailable: {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text) if response.content else response.text
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail or f"HTTP {response.status_code}")
        return response.json() if response.content else {}

    def require_session_user() -> SessionUserRecord:
        payload = cloud_request("GET", "/api/v1/auth/me")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Invalid auth response")
        user = SessionUserRecord(**payload)
        set_cloud_session(get_cloud_token(), user)
        return user

    def _parse_iso_moment(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    def list_cloud_consultation_knowledge_requests(
        status_filter: Literal["pending", "processing", "completed", "failed"] | None = None,
    ) -> list[ConsultationKnowledgeRequestRecord]:
        try:
            suffix = f"?status={quote(status_filter)}" if status_filter else ""
            payload = cloud_request("GET", f"/api/v1/consultation/knowledge-requests{suffix}")
            if isinstance(payload, list):
                return [ConsultationKnowledgeRequestRecord(**item) for item in payload if isinstance(item, dict)]
        except Exception:
            pass
        return []

    def update_cloud_consultation_knowledge_request_status(
        request_id: str,
        *,
        status: Literal["processing", "completed", "failed"],
        error_message: str = "",
        local_document_id: str | None = None,
        local_document_path: str | None = None,
    ) -> ConsultationKnowledgeRequestRecord:
        payload = cloud_request(
            "POST",
            f"/api/v1/consultation/knowledge-requests/{request_id}/status",
            json_body={
                "status": status,
                "errorMessage": error_message,
                "localDocumentId": local_document_id,
                "localDocumentPath": local_document_path,
            },
        )
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Invalid consultation knowledge status payload")
        return ConsultationKnowledgeRequestRecord(**payload)

    def _should_retry_consultation_knowledge_request(request: ConsultationKnowledgeRequestRecord, *, now_ts: float) -> bool:
        if request.status == "pending":
            return True
        if request.status != "processing":
            return False
        updated_at = _parse_iso_moment(request.updatedAt)
        if updated_at is None:
            return True
        return now_ts - updated_at.timestamp() >= 300

    def resolve_growth_actor() -> tuple[str, str]:
        session_user = get_cached_session_user()
        if get_cloud_token() and session_user is None:
            session_user = require_session_user()
        if session_user:
            return session_user.id, session_user.fullName or session_user.email or "当前用户"
        operator = current_operator_row()
        return str(operator["id"]), str(operator["name"] or "当前用户")

    def resolve_growth_week_label(user_id: str, requested_week: str | None = None) -> str:
        if requested_week:
            return requested_week
        current_week = current_review_week_label()
        current_week_row = state.db.fetchone(
            """
            SELECT 1
            FROM xp_ledger
            WHERE user_id = ? AND reversed_at IS NULL AND week_label = ?
            LIMIT 1
            """,
            (user_id, current_week),
        )
        if current_week_row:
            return current_week
        latest_row = state.db.fetchone(
            """
            SELECT week_label
            FROM xp_ledger
            WHERE user_id = ? AND reversed_at IS NULL AND week_label <> ''
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        if latest_row and str(latest_row["week_label"]).strip():
            return str(latest_row["week_label"])
        return current_week

    def task_due_label(due_date: str | None) -> str:
        if not due_date:
            return "今天"
        try:
            normalized = due_date.replace("Z", "+00:00")
            moment = datetime.fromisoformat(normalized)
        except ValueError:
            return due_date
        date = moment.date()
        today = datetime.now().date()
        has_time = bool(re.match(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}", due_date))
        time_label = moment.strftime("%H:%M") if has_time else ""
        if date == today:
            return f"今天 {time_label}".strip()
        return f"{date.strftime('%m-%d')} {time_label}".strip()

    def normalize_due_date_input(value: str | None) -> str | None:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        match = re.match(r"^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2})(?::\d{2})?$", text)
        if match:
            return f"{match.group(1)}T{match.group(2)}"
        today = datetime.now().date()
        weekdays = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}
        if text == "今天":
            return today.isoformat()
        if text == "本周":
            return today.isoformat()
        if text in weekdays:
            delta = (weekdays[text] - today.weekday() + 7) % 7
            return (today + timedelta(days=delta)).isoformat()
        match = re.match(r"^(\d{2})-(\d{2})$", text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            return datetime(today.year, month, day).date().isoformat()
        return text if re.match(r"^\d{4}-\d{2}-\d{2}$", text) else None

    def build_cloud_task_tag(payload: dict[str, object]) -> TaskTagRecord:
        return TaskTagRecord(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            color=str(payload.get("color") or ("#9CA3AF" if str(payload.get("scope", "org")) == "self" else "#5B7BFE")),
            scope=str(payload.get("scope", "org")),  # type: ignore[arg-type]
            ownerUserId=str(payload.get("ownerUserId")) if payload.get("ownerUserId") else None,
            createdBy=str(payload.get("createdBy")) if payload.get("createdBy") else None,
            updatedAt=str(payload.get("updatedAt", now_iso())),
            archivedAt=str(payload.get("archivedAt")) if payload.get("archivedAt") else None,
        )

    def build_task_attachment(row) -> TaskAttachmentRecord:
        summary_value = None
        if hasattr(row, "keys"):
            row_keys = set(row.keys())
            if "document_excerpt" in row_keys:
                summary_value = row["document_excerpt"]
            elif "excerpt" in row_keys:
                summary_value = row["excerpt"]
        return TaskAttachmentRecord(
            id=str(row["id"]),
            taskId=str(row["task_id"]),
            clientId=str(row["client_id"]),
            eventLineId=str(row["event_line_id"]) if row["event_line_id"] else None,
            documentId=str(row["document_id"]) if row["document_id"] else None,
            title=str(row["title"]),
            summary=str(summary_value) if summary_value else None,
            path=str(row["path"]),
            kind=str(row["kind"]),
            source=str(row["source"]),
            sizeBytes=int(row["size_bytes"] or 0),
            createdAt=str(row["created_at"]),
        )

    def fetch_task_attachments(task_id: str, *, cloud: bool) -> list[TaskAttachmentRecord]:
        table_name = "task_attachments_cloud" if cloud else "task_attachments"
        rows = state.db.fetchall(
            f"""
            SELECT
                a.*,
                d.excerpt AS document_excerpt
            FROM {table_name} a
            LEFT JOIN documents d ON d.id = a.document_id
            WHERE a.task_id = ?
            ORDER BY a.created_at DESC
            """,
            (task_id,),
        )
        return [build_task_attachment(row) for row in rows]

    def build_attachment_event_line_activity(attachment: TaskAttachmentRecord) -> EventLineActivityRecord:
        return EventLineActivityRecord(
            id=f"attachment-activity:{attachment.id}",
            eventLineId=attachment.eventLineId or "",
            sourceType="attachment",
            sourceId=attachment.id,
            happenedAt=attachment.createdAt,
            actorId=None,
            actorName=None,
            title=f"上传附件：{attachment.title}",
            summary=f"任务附件已进入项目资料库：{attachment.title}",
            isKey=True,
            metadata={
                "taskId": attachment.taskId,
                "documentId": attachment.documentId,
                "clientId": attachment.clientId,
                "path": attachment.path,
            },
        )

    def stage_task_attachment_upload(client_id: str, file_name: str, content: bytes) -> Path:
        folders = ensure_client_workspace(state.data_dir, client_id)
        base_root = folders.get("项目与业务") or next(iter(folders.values()))
        target_root = base_root / "任务附件"
        target_root.mkdir(parents=True, exist_ok=True)
        safe_name = safe_filename(file_name or "task-attachment")
        candidate = target_root / safe_name
        if candidate.exists():
            stem = safe_filename(Path(safe_name).stem or "task-attachment")
            candidate = target_root / f"{stem}__{uuid4().hex[:6]}{Path(safe_name).suffix.lower()}"
        candidate.write_bytes(content)
        return candidate

    def build_cloud_task(payload: dict[str, object], lists_by_id: dict[str, TaskListRecord]) -> TaskRecord:
        def ensure_local_cloud_event_line_shadow(
            event_line_id: str | None,
            *,
            fallback_name: str | None = None,
            client_id: str | None = None,
        ) -> None:
            normalized_id = (event_line_id or "").strip()
            if not normalized_id or not get_cloud_token():
                return
            try:
                response_payload = cloud_request("GET", f"/api/v1/event-lines/{normalized_id}")
            except HTTPException:
                return
            if not isinstance(response_payload, dict):
                return
            record = (
                response_payload.get("eventLine")
                if isinstance(response_payload.get("eventLine"), dict)
                else response_payload
            )
            if not isinstance(record, dict):
                return
            existing_row = state.db.fetchone("SELECT created_at FROM event_lines WHERE id = ?", (normalized_id,))
            timestamp = now_iso()
            resolved_client_id = str(record.get("primaryClientId") or client_id or "").strip() or None
            client_row = (
                state.db.fetchone("SELECT name FROM clients WHERE id = ?", (resolved_client_id,))
                if resolved_client_id
                else None
            )
            participant_ids = [
                str(item).strip()
                for item in (record.get("participantIds") or [])
                if str(item).strip()
            ]
            state.db.execute(
                """
                INSERT INTO event_lines(
                    id, name, kind, status, business_category, stage, summary, intent, current_blocker, recent_decision, next_step,
                    evidence_count, owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id,
                    primary_department_name, participant_ids_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    kind = excluded.kind,
                    status = excluded.status,
                    business_category = excluded.business_category,
                    stage = excluded.stage,
                    summary = excluded.summary,
                    intent = excluded.intent,
                    current_blocker = excluded.current_blocker,
                    recent_decision = excluded.recent_decision,
                    next_step = excluded.next_step,
                    evidence_count = excluded.evidence_count,
                    owner_id = excluded.owner_id,
                    owner_name = excluded.owner_name,
                    primary_client_id = excluded.primary_client_id,
                    primary_client_name = excluded.primary_client_name,
                    primary_department_id = excluded.primary_department_id,
                    primary_department_name = excluded.primary_department_name,
                    participant_ids_json = excluded.participant_ids_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_id,
                    str(record.get("name") or fallback_name or "").strip() or normalized_id,
                    str(record.get("kind") or "custom"),
                    str(record.get("status") or "active"),
                    str(record.get("businessCategory")) if record.get("businessCategory") else None,
                    str(record.get("stage")) if record.get("stage") else None,
                    str(record.get("summary")) if record.get("summary") else None,
                    str(record.get("intent")) if record.get("intent") else None,
                    str(record.get("currentBlocker")) if record.get("currentBlocker") else None,
                    str(record.get("recentDecision")) if record.get("recentDecision") else None,
                    str(record.get("nextStep")) if record.get("nextStep") else None,
                    int(record.get("evidenceCount") or 0),
                    str(record.get("ownerId")) if record.get("ownerId") else None,
                    str(record.get("ownerName")) if record.get("ownerName") else None,
                    resolved_client_id,
                    str(client_row["name"]) if client_row and client_row["name"] else (str(record.get("primaryClientName")) if record.get("primaryClientName") else None),
                    str(record.get("primaryDepartmentId")) if record.get("primaryDepartmentId") else None,
                    str(record.get("primaryDepartmentName")) if record.get("primaryDepartmentName") else None,
                    to_json(participant_ids),
                    str(existing_row["created_at"]) if existing_row and existing_row["created_at"] else timestamp,
                    timestamp,
                ),
            )
            refresh_event_line_memory_snapshot(state.db, normalized_id)
            _invalidate_event_line_snapshot_cache(normalized_id)

        cloud_note = str(payload.get("note")) if payload.get("note") else None
        note_row = state.db.fetchone("SELECT note FROM task_notes_cloud WHERE task_id = ?", (str(payload.get("id")),))
        resolved_note = cloud_note or (str(note_row["note"]) if note_row and note_row["note"] else None)
        client_id = str(payload.get("clientId")) if payload.get("clientId") else None
        event_line_id = str(payload.get("eventLineId")) if payload.get("eventLineId") else None
        event_line_name = str(payload.get("eventLineName")) if payload.get("eventLineName") else None
        ensure_local_cloud_event_line_shadow(event_line_id, fallback_name=event_line_name, client_id=client_id)
        client_row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,)) if client_id else None
        project_module_id = str(payload.get("projectModuleId")) if payload.get("projectModuleId") else None
        project_flow_id = str(payload.get("projectFlowId")) if payload.get("projectFlowId") else None
        project_module, project_flow = resolve_project_structure_refs(client_id, project_module_id, project_flow_id, strict=False) if client_id else (None, None)
        collaborators = [
            TaskCollaboratorRecord(
                userId=str(item.get("userId", "")),
                fullName=str(item.get("fullName", "")),
                email=str(item.get("email", "")),
                orderIndex=int(item.get("orderIndex", 0)),
                isOwner=bool(item.get("isOwner", False)),
                inboxStatus=str(item.get("inboxStatus", "pending")),  # type: ignore[arg-type]
                returnReason=item.get("returnReason") if isinstance(item.get("returnReason"), str) else None,
                handledAt=item.get("handledAt") if isinstance(item.get("handledAt"), str) else None,
            )
            for item in payload.get("collaborators", []) if isinstance(item, dict)
        ]
        list_id = str(payload.get("listId", "list-0"))
        list_record = lists_by_id.get(
            list_id,
            TaskListRecord(
                id=list_id,
                name=str(payload.get("listName", "收集箱")),
                color=str(payload.get("listColor", "#5B7BFE")),
                sortOrder=0,
                isDefault=False,
                archivedAt=None,
            ),
        )
        progress_status = str(payload.get("progressStatus", "todo"))
        viewer_status = payload.get("viewerInboxStatus")
        task_status = "inbox" if viewer_status == "pending" else progress_status
        org_context_payload = payload.get("orgContext")
        org_context = (
            TaskOrgContextRecord(**org_context_payload)
            if isinstance(org_context_payload, dict)
            else None
        )
        project_context = build_task_project_context(
            client_id,
            str(payload.get("sourceType", "manual")),
            str(payload.get("sourceId")) if payload.get("sourceId") else None,
            task_title=str(payload.get("title", "")),
            task_desc=str(payload.get("description", "")),
            project_module_id=project_module.id if project_module else None,
            project_flow_id=project_flow.id if project_flow else None,
        )
        def resolve_cloud_event_line_context(
            normalized_id: str,
            fallback_name: str | None,
        ) -> dict[str, object] | None:
            if not get_cloud_token():
                return None
            try:
                event_line_payload = cloud_request("GET", f"/api/v1/event-lines/{normalized_id}")
            except HTTPException:
                return None
            if not isinstance(event_line_payload, dict):
                return None
            record = event_line_payload.get("eventLine") if isinstance(event_line_payload.get("eventLine"), dict) else event_line_payload
            if not isinstance(record, dict):
                return None
            return {
                "id": str(record.get("id") or normalized_id),
                "name": str(record.get("name") or fallback_name or "").strip(),
                "businessCategory": record.get("businessCategory"),
                "stage": record.get("stage"),
                "summary": record.get("summary"),
                "intent": record.get("intent"),
                "currentBlocker": record.get("currentBlocker"),
                "recentDecision": record.get("recentDecision"),
                "nextStep": record.get("nextStep"),
                "evidenceCount": int(record.get("evidenceCount") or 0),
                "primaryClientId": record.get("primaryClientId"),
                "primaryClientName": record.get("primaryClientName"),
            }

        event_line_context = _event_line_snapshot_context(
            state.db,
            event_line_id,
            event_line_name,
            cloud_resolver=resolve_cloud_event_line_context,
        )
        _sync_task_attachment_scope(
            state.db,
            state.data_dir,
            build_task_attachment,
            build_attachment_event_line_activity,
            ensure_standard_client_folders,
            str(payload.get("id")),
            client_id,
            event_line_id,
            cloud=True,
        )
        attachments = fetch_task_attachments(str(payload.get("id")), cloud=True)
        (
            business_category,
            current_blocker,
            next_action,
            recent_decision,
            evidence_count,
        ) = _resolve_task_action_os_fields(
            title=str(payload.get("title", "")),
            desc=str(payload.get("description", "")),
            source_type=str(payload.get("sourceType", "manual")),
            business_category=str(payload.get("businessCategory")) if payload.get("businessCategory") else None,
            current_blocker=str(payload.get("currentBlocker")) if payload.get("currentBlocker") else None,
            next_action=str(payload.get("nextAction")) if payload.get("nextAction") else None,
            recent_decision=str(payload.get("recentDecision")) if payload.get("recentDecision") else None,
            evidence_count=int(payload.get("evidenceCount") or 0),
            project_context=project_context,
            event_line_context=event_line_context,
            attachment_count=len(attachments),
        )
        memory_hints, background_readiness, linked_facts_preview = get_task_memory_enrichment(
            state.db,
            task_id=str(payload.get("id")),
            client_id=client_id,
            event_line_id=event_line_id,
        )
        return TaskRecord(
            id=str(payload.get("id")),
            title=str(payload.get("title", "")),
            desc=str(payload.get("description", "")),
            status=task_status,  # type: ignore[arg-type]
            creatorId=str(payload.get("creatorId")) if payload.get("creatorId") else None,
            creatorName=str(payload.get("creatorName")) if payload.get("creatorName") else None,
            priority=str(payload.get("priority", "normal")),  # type: ignore[arg-type]
            listId=list_record.id,
            listName=list_record.name,
            listColor=list_record.color,
            ddl=task_due_label(payload.get("dueDate") if isinstance(payload.get("dueDate"), str) else None),
            dueDate=payload.get("dueDate") if isinstance(payload.get("dueDate"), str) else None,
            durationMinutes=int(payload.get("durationMinutes") or 60),
            scopeMode=str(payload.get("scopeMode") or "COLLAB_SHARED"),  # type: ignore[arg-type]
            clientId=client_id,
            clientName=str(client_row["name"]) if client_row else None,
            eventLineId=event_line_id,
            eventLineName=event_line_name,
            projectModuleId=project_module.id if project_module else project_module_id,
            projectModuleName=project_module.name if project_module else None,
            projectFlowId=project_flow.id if project_flow else project_flow_id,
            projectFlowName=project_flow.name if project_flow else None,
            ownerId=str(payload.get("ownerId")) if payload.get("ownerId") else None,
            ownerName=str(payload.get("ownerName") or ""),
            sourceType=str(payload.get("sourceType", "manual")),
            sourceId=str(payload.get("sourceId")) if payload.get("sourceId") else None,
            businessCategory=business_category,
            currentBlocker=current_blocker,
            nextAction=next_action,
            recentDecision=recent_decision,
            evidenceCount=evidence_count,
            tags=[build_cloud_task_tag(item) for item in payload.get("tags", []) if isinstance(item, dict)],
            note=resolved_note,
            attachments=attachments,
            collaborators=collaborators,
            collaborationSummary=payload.get("collaborationSummary") if isinstance(payload.get("collaborationSummary"), dict) else {},
            viewerInboxStatus=viewer_status if isinstance(viewer_status, str) else None,
            orgContext=org_context,
            projectContext=project_context,
            memoryHints=memory_hints,
            backgroundReadiness=background_readiness,
            linkedFactsPreview=linked_facts_preview,
            createdAt=str(payload.get("createdAt", now_iso())),
            updatedAt=str(payload.get("updatedAt", now_iso())),
        )

    _cloud_task_board_cache: dict[str, object] = {"data": None, "ts": 0.0}
    _cloud_tasks_pulled_to_local: bool = False

    def _upsert_cloud_task_list_shadow_local(
        payload: dict[str, object],
        *,
        list_id: str | None = None,
        name: str | None = None,
        color: str | None = None,
    ) -> str:
        normalized_list_id = (list_id or str(payload.get("id") or "")).strip() or "list-0"
        timestamp = now_iso()
        existing = state.db.fetchone(
            "SELECT id FROM task_lists WHERE id = ? OR cloud_id = ?",
            (normalized_list_id, normalized_list_id),
        )
        local_list_id = str(existing["id"]) if existing and existing["id"] else normalized_list_id
        resolved_name = (name or str(payload.get("name") or "")).strip() or "收集箱"
        resolved_color = (color or str(payload.get("color") or "")).strip() or "#5B7BFE"
        state.db.execute(
            """
            INSERT INTO task_lists(
                id, organization_id, name, color, sort_order, is_default, scope, archived_at,
                sync_status, cloud_id, cloud_payload_json, last_synced_at, last_cloud_version,
                pending_sync_action, last_sync_error
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                color = excluded.color,
                sort_order = excluded.sort_order,
                is_default = excluded.is_default,
                scope = excluded.scope,
                archived_at = excluded.archived_at,
                sync_status = excluded.sync_status,
                cloud_id = excluded.cloud_id,
                cloud_payload_json = excluded.cloud_payload_json,
                last_synced_at = excluded.last_synced_at,
                last_cloud_version = excluded.last_cloud_version,
                pending_sync_action = excluded.pending_sync_action,
                last_sync_error = excluded.last_sync_error
            """,
            (
                local_list_id,
                str(payload.get("organizationId") or ""),
                resolved_name,
                resolved_color,
                int(payload.get("sortOrder", 0) or 0),
                1 if payload.get("isDefault") else 0,
                str(payload.get("scope") or "org"),
                str(payload.get("archivedAt")) if payload.get("archivedAt") else None,
                "synced",
                normalized_list_id,
                to_json(payload),
                timestamp,
                str(payload.get("updatedAt") or payload.get("createdAt") or ""),
                "",
                "",
            ),
        )
        return local_list_id

    def _upsert_cloud_task_shadow_local(payload: dict[str, object]) -> str | None:
        cloud_id = str(payload.get("id") or "").strip()
        if not cloud_id:
            return None
        list_id = _upsert_cloud_task_list_shadow_local(
            {
                "id": payload.get("listId"),
                "name": payload.get("listName"),
                "color": payload.get("listColor"),
            },
            list_id=str(payload.get("listId") or "list-0"),
            name=str(payload.get("listName") or "收集箱"),
            color=str(payload.get("listColor") or "#5B7BFE"),
        )
        existing = state.db.fetchone(
            "SELECT id, organization_id, creator_id, owner_name, ddl, created_at FROM tasks WHERE id = ? OR cloud_id = ?",
            (cloud_id, cloud_id),
        )
        local_task_id = str(existing["id"]) if existing and existing["id"] else cloud_id
        due_date = str(payload.get("dueDate")) if payload.get("dueDate") else None
        progress_status = str(payload.get("progressStatus") or "todo")
        viewer_status = str(payload.get("viewerInboxStatus")) if payload.get("viewerInboxStatus") else None
        local_status = "inbox" if viewer_status == "pending" else progress_status
        tags = [item for item in payload.get("tags", []) if isinstance(item, dict)]
        timestamp = now_iso()
        resolved_updated_at = str(payload.get("updatedAt") or timestamp)
        state.db.execute(
            """
            INSERT INTO tasks(
                id, organization_id, title, description, status, priority, list_id, creator_id, owner_id, owner_name,
                progress_status, ddl, due_date, duration_minutes, scope_mode, client_id, event_line_id, project_module_id,
                project_flow_id, business_category, current_blocker, next_action, recent_decision, evidence_count,
                source_type, source_id, tags_json, tag_ids_json, created_at, updated_at, sync_status, cloud_id,
                cloud_payload_json, last_synced_at, last_cloud_version, pending_sync_action, last_sync_error
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                organization_id = excluded.organization_id,
                title = excluded.title,
                description = excluded.description,
                status = excluded.status,
                priority = excluded.priority,
                list_id = excluded.list_id,
                creator_id = excluded.creator_id,
                owner_id = excluded.owner_id,
                owner_name = excluded.owner_name,
                progress_status = excluded.progress_status,
                ddl = excluded.ddl,
                due_date = excluded.due_date,
                duration_minutes = excluded.duration_minutes,
                scope_mode = excluded.scope_mode,
                client_id = excluded.client_id,
                event_line_id = excluded.event_line_id,
                project_module_id = excluded.project_module_id,
                project_flow_id = excluded.project_flow_id,
                business_category = excluded.business_category,
                current_blocker = excluded.current_blocker,
                next_action = excluded.next_action,
                recent_decision = excluded.recent_decision,
                evidence_count = excluded.evidence_count,
                source_type = excluded.source_type,
                source_id = excluded.source_id,
                tags_json = excluded.tags_json,
                tag_ids_json = excluded.tag_ids_json,
                updated_at = excluded.updated_at,
                sync_status = excluded.sync_status,
                cloud_id = excluded.cloud_id,
                cloud_payload_json = excluded.cloud_payload_json,
                last_synced_at = excluded.last_synced_at,
                last_cloud_version = excluded.last_cloud_version,
                pending_sync_action = excluded.pending_sync_action,
                last_sync_error = excluded.last_sync_error
            """,
            (
                local_task_id,
                str(payload.get("organizationId") or (str(existing["organization_id"]) if existing and existing["organization_id"] else "")),
                str(payload.get("title") or ""),
                str(payload.get("description") or ""),
                local_status,
                str(payload.get("priority") or "normal"),
                list_id,
                str(payload.get("creatorId") or (str(existing["creator_id"]) if existing and existing["creator_id"] else "")),
                str(payload.get("ownerId")) if payload.get("ownerId") else None,
                str(payload.get("ownerName") or (str(existing["owner_name"]) if existing and existing["owner_name"] else "")),
                progress_status,
                task_due_label(due_date) if due_date else (str(existing["ddl"]) if existing and existing["ddl"] else "待确认"),
                due_date,
                int(payload.get("durationMinutes") or 60),
                str(payload.get("scopeMode") or "COLLAB_SHARED"),
                str(payload.get("clientId")) if payload.get("clientId") else None,
                str(payload.get("eventLineId")) if payload.get("eventLineId") else None,
                str(payload.get("projectModuleId")) if payload.get("projectModuleId") else None,
                str(payload.get("projectFlowId")) if payload.get("projectFlowId") else None,
                str(payload.get("businessCategory")) if payload.get("businessCategory") else None,
                str(payload.get("currentBlocker")) if payload.get("currentBlocker") else None,
                str(payload.get("nextAction")) if payload.get("nextAction") else None,
                str(payload.get("recentDecision")) if payload.get("recentDecision") else None,
                int(payload.get("evidenceCount") or 0),
                str(payload.get("sourceType") or "manual"),
                str(payload.get("sourceId")) if payload.get("sourceId") else None,
                to_json([str(item.get("name") or "") for item in tags]),
                to_json([str(item.get("id") or "") for item in tags]),
                str(payload.get("createdAt") or (str(existing["created_at"]) if existing and existing["created_at"] else timestamp)),
                resolved_updated_at,
                "synced",
                cloud_id,
                to_json(payload),
                timestamp,
                resolved_updated_at,
                "",
                "",
            ),
        )
        collaborators = payload.get("collaborators")
        if isinstance(collaborators, list):
            state.db.execute("DELETE FROM task_collaborators WHERE task_id = ?", (local_task_id,))
            for item in collaborators:
                if not isinstance(item, dict):
                    continue
                state.db.execute(
                    """
                    INSERT INTO task_collaborators(
                        task_id, organization_id, user_id, full_name, email, order_index, is_owner,
                        inbox_status, return_reason, handled_at, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        local_task_id,
                        str(payload.get("organizationId") or ""),
                        str(item.get("userId") or ""),
                        str(item.get("fullName") or ""),
                        str(item.get("email") or ""),
                        int(item.get("orderIndex") or 0),
                        1 if item.get("isOwner") else 0,
                        str(item.get("inboxStatus") or "pending"),
                        str(item.get("returnReason")) if item.get("returnReason") else None,
                        str(item.get("handledAt")) if item.get("handledAt") else None,
                        str(payload.get("createdAt") or timestamp),
                        resolved_updated_at,
                    ),
                )
        cloud_note = str(payload.get("note")).strip() if isinstance(payload.get("note"), str) else None
        if cloud_note is not None:
            upsert_task_note(local_task_id, cloud_note)
        _cloud_task_board_cache["data"] = None
        return local_task_id

    def _ensure_task_tag_schema_for_cloud_pull() -> bool:
        try:
            if not state.db.has_column("task_tags", "operator_id"):
                state.db.ensure_column("task_tags", "operator_id", "TEXT NOT NULL DEFAULT ''")
            if not state.db.has_column("task_tags", "owner_operator_id"):
                state.db.ensure_column("task_tags", "owner_operator_id", "TEXT NOT NULL DEFAULT ''")
            state.db.execute(
                """
                UPDATE task_tags
                SET operator_id = COALESCE(NULLIF(operator_id, ''), owner_operator_id, '')
                """
            )
            return True
        except Exception as error:
            if state.system_logger:
                state.system_logger.error("tasks.sync", f"云端任务同步前置检查失败: {error}")
            return False

    def _pull_cloud_tasks_to_local() -> None:
        """One-time pull: download cloud tasks and upsert them into local SQLite."""
        nonlocal _cloud_tasks_pulled_to_local
        if _cloud_tasks_pulled_to_local:
            return
        _cloud_tasks_pulled_to_local = True
        if not get_cloud_token():
            return
        if not _ensure_task_tag_schema_for_cloud_pull():
            _cloud_tasks_pulled_to_local = False
            return
        try:
            payload = cloud_request("GET", "/api/v1/tasks", timeout=10.0)
        except Exception:
            _cloud_tasks_pulled_to_local = False  # retry next time
            return
        if not isinstance(payload, dict):
            return
        timestamp = now_iso()
        # Mirror cloud lists locally
        for item in payload.get("lists", []):
            if not isinstance(item, dict):
                continue
            _upsert_cloud_task_list_shadow_local(item)
        # Mirror cloud tags locally
        for item in payload.get("tags", []):
            if not isinstance(item, dict):
                continue
            tid = str(item.get("id", ""))
            if not tid:
                continue
            existing = state.db.fetchone("SELECT id FROM task_tags WHERE id = ?", (tid,))
            if not existing:
                owner_operator_id = str(item.get("operatorId") or "")
                state.db.execute(
                    """
                    INSERT OR IGNORE INTO task_tags(
                        id, name, color, scope, owner_operator_id, operator_id, created_by, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tid,
                        str(item.get("name", "")),
                        str(item.get("color", "#5B7BFE")),
                        str(item.get("scope", "org")),
                        owner_operator_id,
                        owner_operator_id,
                        "cloud_sync",
                        timestamp,
                        timestamp,
                    ),
                )
        # Mirror cloud tasks locally
        for item in payload.get("tasks", []):
            if not isinstance(item, dict):
                continue
            _upsert_cloud_task_shadow_local(item)

    def _merge_local_tasks_into(board: TaskBoardResponse) -> TaskBoardResponse:
        """Local-first merge: add recent local-only tasks + merge local attachments into cloud tasks."""
        cloud_task_map = {t.id: t for t in board.tasks}
        merged_tasks = []
        changed = False

        # For each cloud task, check if local has more attachments
        for task in board.tasks:
            local_atts = fetch_task_attachments(task.id, cloud=True)
            if len(local_atts) > len(task.attachments):
                merged_tasks.append(task.model_copy(update={"attachments": local_atts}))
                changed = True
            else:
                merged_tasks.append(task)

        # Only merge LOCAL tasks created in the last 7 days (avoid resurrecting old seed/deleted data)
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()[:19]
        local_rows = state.db.fetchall(
            "SELECT id FROM tasks WHERE id NOT LIKE 'agent_%' AND id NOT LIKE 'task_seed_%' AND created_at > ?",
            (cutoff,),
        )
        for row in local_rows:
            local_id = str(row["id"])
            if local_id not in cloud_task_map:
                try:
                    local_tasks = fetch_tasks("t.id = ?", (local_id,))
                    if local_tasks:
                        merged_tasks.append(local_tasks[0])
                        changed = True
                except Exception:
                    pass

        if changed:
            return TaskBoardResponse(tasks=merged_tasks, lists=board.lists, tags=board.tags, commonTags=board.commonTags)
        return board

    def cloud_task_board() -> TaskBoardResponse:
        import time
        now = time.time()
        if _cloud_task_board_cache["data"] is not None and now - _cloud_task_board_cache["ts"] < 30:
            return _merge_local_tasks_into(_cloud_task_board_cache["data"])  # type: ignore[arg-type]
        payload = cloud_request("GET", "/api/v1/tasks")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Invalid task board payload")
        lists = [
            TaskListRecord(
                id=str(item["id"]),
                name=str(item["name"]),
                color=str(item["color"]),
                sortOrder=int(item.get("sortOrder", 0)),
                isDefault=bool(item.get("isDefault", False)),
                scope=str(item.get("scope") or "org"),
                archivedAt=str(item.get("archivedAt")) if item.get("archivedAt") else None,
            )
            for item in payload.get("lists", [])
            if isinstance(item, dict)
        ]
        lists_by_id = {item.id: item for item in lists}
        tasks = [build_cloud_task(item, lists_by_id) for item in payload.get("tasks", []) if isinstance(item, dict)]
        cloud_tags = [build_cloud_task_tag(item) for item in payload.get("tags", []) if isinstance(item, dict)]
        cloud_common_tags = [str(item) for item in payload.get("commonTags", []) if isinstance(item, str)]
        result = TaskBoardResponse(tasks=tasks, lists=lists, tags=cloud_tags, commonTags=cloud_common_tags)
        result = _merge_local_tasks_into(result)
        _cloud_task_board_cache["data"] = result
        _cloud_task_board_cache["ts"] = now
        return result

    def fetch_cloud_task_by_id(task_id: str) -> TaskRecord:
        board = cloud_task_board()
        task = next((item for item in board.tasks if item.id == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def task_lists() -> list[TaskListRecord]:
        return [
            _local_task_list_record(row)
            for row in state.db.fetchall(
                """
                SELECT *
                FROM task_lists
                ORDER BY CASE WHEN archived_at IS NULL OR archived_at = '' THEN 0 ELSE 1 END,
                         CASE WHEN is_default = 1 THEN 0 ELSE 1 END,
                         sort_order ASC,
                         name COLLATE NOCASE ASC
                """
            )
        ]

    def task_tags() -> list[TaskTagRecord]:
        operator_row = current_operator_row()
        return _visible_local_task_tags(state.db, str(operator_row["id"]))

    def build_task(row) -> TaskRecord:
        note_row = state.db.fetchone("SELECT note FROM task_notes WHERE task_id = ?", (str(row["id"]),))
        client_id = str(row["client_id"]) if row["client_id"] else None
        event_line_id = str(row["event_line_id"]) if row["event_line_id"] else None
        event_line_row = state.db.fetchone("SELECT name FROM event_lines WHERE id = ?", (event_line_id,)) if event_line_id else None
        project_module_id = str(row["project_module_id"]) if row["project_module_id"] else None
        project_flow_id = str(row["project_flow_id"]) if row["project_flow_id"] else None
        project_module, project_flow = resolve_project_structure_refs(client_id, project_module_id, project_flow_id, strict=False) if client_id else (None, None)
        project_context = build_task_project_context(
            client_id,
            str(row["source_type"]),
            str(row["source_id"]) if row["source_id"] else None,
            task_title=str(row["title"]),
            task_desc=str(row["description"]),
            project_module_id=project_module.id if project_module else project_module_id,
            project_flow_id=project_flow.id if project_flow else project_flow_id,
        )
        event_line_context = _event_line_snapshot_context(state.db, event_line_id, str(event_line_row["name"]) if event_line_row else None)
        attachments = fetch_task_attachments(str(row["id"]), cloud=False)
        (
            business_category,
            current_blocker,
            next_action,
            recent_decision,
            evidence_count,
        ) = _resolve_task_action_os_fields(
            title=str(row["title"]),
            desc=str(row["description"]),
            source_type=str(row["source_type"]),
            business_category=str(row["business_category"]) if row["business_category"] else None,
            current_blocker=str(row["current_blocker"]) if row["current_blocker"] else None,
            next_action=str(row["next_action"]) if row["next_action"] else None,
            recent_decision=str(row["recent_decision"]) if row["recent_decision"] else None,
            evidence_count=int(row["evidence_count"] or 0),
            project_context=project_context,
            event_line_context=event_line_context,
            attachment_count=len(attachments),
        )
        memory_hints, background_readiness, linked_facts_preview = get_task_memory_enrichment(
            state.db,
            task_id=str(row["id"]),
            client_id=client_id,
            event_line_id=event_line_id,
        )
        return TaskRecord(
            id=str(row["id"]),
            title=str(row["title"]),
            desc=str(row["description"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            priority=str(row["priority"]),  # type: ignore[arg-type]
            listId=str(row["list_id"]),
            listName=str(row["list_name"]),
            listColor=str(row["list_color"]),
            ddl=str(row["ddl"]),
            dueDate=str(row["due_date"]) if row["due_date"] else None,
            durationMinutes=int(row["duration_minutes"] or 60),
            scopeMode=str(row["scope_mode"] or "COLLAB_SHARED"),  # type: ignore[arg-type]
            clientId=client_id,
            clientName=str(row["client_name"]) if row["client_name"] else None,
            eventLineId=event_line_id,
            eventLineName=str(event_line_row["name"]) if event_line_row else None,
            projectModuleId=project_module.id if project_module else project_module_id,
            projectModuleName=project_module.name if project_module else None,
            projectFlowId=project_flow.id if project_flow else project_flow_id,
            projectFlowName=project_flow.name if project_flow else None,
            ownerName=str(row["owner_name"]),
            sourceType=str(row["source_type"]),
            sourceId=str(row["source_id"]) if row["source_id"] else None,
            businessCategory=business_category,
            currentBlocker=current_blocker,
            nextAction=next_action,
            recentDecision=recent_decision,
            evidenceCount=evidence_count,
            tags=[],
            note=str(note_row["note"]) if note_row else None,
            attachments=attachments,
            projectContext=project_context,
            memoryHints=memory_hints,
            backgroundReadiness=background_readiness,
            linkedFactsPreview=linked_facts_preview,
            syncStatus=str(row["sync_status"]) if row["sync_status"] else None,
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def build_cloud_event_line(payload: dict[str, object]) -> EventLineRecord:
        client_id = str(payload.get("primaryClientId")) if payload.get("primaryClientId") else None
        client_row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,)) if client_id else None
        cloud_client_name = str(payload.get("primaryClientName")).strip() if payload.get("primaryClientName") else None
        return EventLineRecord(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            kind=str(payload.get("kind", "custom")),  # type: ignore[arg-type]
            status=str(payload.get("status", "active")),  # type: ignore[arg-type]
            visibilityScope=str(payload.get("visibilityScope", "project_public")),  # type: ignore[arg-type]
            businessCategory=str(payload.get("businessCategory")) if payload.get("businessCategory") else None,
            stage=str(payload.get("stage")) if payload.get("stage") else None,
            summary=str(payload.get("summary")) if payload.get("summary") else None,
            intent=str(payload.get("intent")) if payload.get("intent") else None,
            currentBlocker=str(payload.get("currentBlocker")) if payload.get("currentBlocker") else None,
            recentDecision=str(payload.get("recentDecision")) if payload.get("recentDecision") else None,
            nextStep=str(payload.get("nextStep")) if payload.get("nextStep") else None,
            evidenceCount=int(payload.get("evidenceCount") or 0),
            ownerId=str(payload.get("ownerId")) if payload.get("ownerId") else None,
            ownerName=str(payload.get("ownerName")) if payload.get("ownerName") else None,
            primaryClientId=client_id,
            primaryClientName=cloud_client_name or (str(client_row["name"]) if client_row else None),
            primaryDepartmentId=str(payload.get("primaryDepartmentId")) if payload.get("primaryDepartmentId") else None,
            primaryDepartmentName=str(payload.get("primaryDepartmentName")) if payload.get("primaryDepartmentName") else None,
            participantIds=[str(item) for item in payload.get("participantIds", [])] if isinstance(payload.get("participantIds"), list) else [],
            closedAt=str(payload.get("closedAt")) if payload.get("closedAt") else None,
            closedByUserId=str(payload.get("closedByUserId")) if payload.get("closedByUserId") else None,
            createdAt=str(payload.get("createdAt", now_iso())),
            updatedAt=str(payload.get("updatedAt", now_iso())),
        )

    def _compute_activity_is_key(source_type: str, metadata: object) -> bool:
        """Determine if an event-line activity is a key action (shown by default) or a system trace.
        Key events: task created, manual note, attachment upload.
        System traces: status changes, field updates, meetings, reviews, support requests."""
        if source_type in ("manual_note", "attachment"):
            return True
        if source_type == "task_activity" and isinstance(metadata, dict):
            if metadata.get("eventType") == "created":
                return True
        return False

    def build_cloud_event_line_activity(payload: dict[str, object]) -> EventLineActivityRecord:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        source_type = str(payload.get("sourceType", "manual_note"))
        is_key = payload.get("isKey")
        if is_key is None:
            is_key = _compute_activity_is_key(source_type, metadata)
        return EventLineActivityRecord(
            id=str(payload.get("id", "")),
            eventLineId=str(payload.get("eventLineId", "")),
            sourceType=source_type,  # type: ignore[arg-type]
            sourceId=str(payload.get("sourceId", "")),
            happenedAt=str(payload.get("happenedAt", now_iso())),
            actorId=str(payload.get("actorId")) if payload.get("actorId") else None,
            actorName=str(payload.get("actorName")) if payload.get("actorName") else None,
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            metadata=metadata,
            isKey=bool(is_key),
        )

    def build_event_line(row) -> EventLineRecord:
        client_id = str(row["primary_client_id"]) if row["primary_client_id"] else None
        client_row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,)) if client_id else None
        activity_count = int(state.db.scalar("SELECT COUNT(1) FROM event_line_activities WHERE event_line_id = ?", (str(row["id"]),)) or 0)
        return EventLineRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            kind=str(row["kind"]),  # type: ignore[arg-type]
            status=str(row["status"]),  # type: ignore[arg-type]
            visibilityScope=str(row["visibility_scope"]) if row["visibility_scope"] else "project_public",  # type: ignore[arg-type]
            businessCategory=str(row["business_category"]) if row["business_category"] else None,
            stage=str(row["stage"]) if row["stage"] else None,
            summary=str(row["summary"]) if row["summary"] else None,
            intent=str(row["intent"]) if row["intent"] else None,
            currentBlocker=str(row["current_blocker"]) if row["current_blocker"] else None,
            recentDecision=str(row["recent_decision"]) if row["recent_decision"] else None,
            nextStep=str(row["next_step"]) if row["next_step"] else None,
            evidenceCount=max(int(row["evidence_count"] or 0), activity_count),
            ownerId=str(row["owner_id"]) if row["owner_id"] else None,
            ownerName=str(row["owner_name"]) if row["owner_name"] else None,
            primaryClientId=client_id,
            primaryClientName=str(client_row["name"]) if client_row else (str(row["primary_client_name"]) if row["primary_client_name"] else None),
            primaryDepartmentId=str(row["primary_department_id"]) if row["primary_department_id"] else None,
            primaryDepartmentName=str(row["primary_department_name"]) if row["primary_department_name"] else None,
            participantIds=[str(item) for item in from_json(row["participant_ids_json"], []) if str(item)],
            closedAt=str(row["closed_at"]) if row["closed_at"] else None,
            closedByUserId=str(row["closed_by_user_id"]) if row["closed_by_user_id"] else None,
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def build_event_line_activity(row) -> EventLineActivityRecord:
        metadata = from_json(row["metadata_json"], {})
        return EventLineActivityRecord(
            id=str(row["id"]),
            eventLineId=str(row["event_line_id"]),
            sourceType=str(row["source_type"]),  # type: ignore[arg-type]
            sourceId=str(row["source_id"]),
            happenedAt=str(row["happened_at"]),
            actorId=str(row["actor_id"]) if row["actor_id"] else None,
            actorName=str(row["actor_name"]) if row["actor_name"] else None,
            title=str(row["title"]),
            summary=str(row["summary"]),
            metadata=metadata if isinstance(metadata, dict) else {},
            isKey=bool(row["is_key"]) if "is_key" in row.keys() else False,
        )

    def build_cloud_event_line_detail(payload: dict[str, object]) -> EventLineDetailRecord:
        event_line_payload = payload.get("eventLine")
        tasks_payload = payload.get("tasks")
        activities_payload = payload.get("activities")
        event_line = (
            build_cloud_event_line(event_line_payload)
            if isinstance(event_line_payload, dict)
            else EventLineRecord(
                id="",
                name="",
                kind="custom",
                status="active",
                participantIds=[],
                createdAt=now_iso(),
                updatedAt=now_iso(),
            )
        )
        remote_activities = [build_cloud_event_line_activity(item) for item in activities_payload if isinstance(item, dict)] if isinstance(activities_payload, list) else []
        local_attachment_rows = state.db.fetchall(
            "SELECT * FROM task_attachments_cloud WHERE event_line_id = ? ORDER BY created_at DESC",
            (event_line.id,),
        ) if event_line.id else []
        attachment_activities = [
            build_attachment_event_line_activity(build_task_attachment(row))
            for row in local_attachment_rows
        ]
        combined_activities = remote_activities + attachment_activities
        combined_activities.sort(key=lambda item: (item.happenedAt, item.id), reverse=True)
        memory_response = get_event_line_memory_response(state.db, event_line.id) if event_line.id else EventLineMemoryResponse(
            eventLineId="",
            lineName="",
            eventLineMemorySnapshot=None,
            clarificationNeeds=[],
        )
        return EventLineDetailRecord(
            eventLine=event_line,
            tasks=[build_cloud_task(item, {}) for item in tasks_payload if isinstance(item, dict)] if isinstance(tasks_payload, list) else [],
            activities=combined_activities,
            memorySnapshot=memory_response.eventLineMemorySnapshot,
            predictionReadiness=memory_response.eventLineMemorySnapshot.predictionReadiness if memory_response.eventLineMemorySnapshot else None,
            clarificationNeeds=memory_response.clarificationNeeds,
        )

    def build_event_line_detail(row) -> EventLineDetailRecord:
        tasks = fetch_tasks("t.event_line_id = ?", (str(row["id"]),))
        activity_rows = state.db.fetchall(
            """
            SELECT *
            FROM event_line_activities
            WHERE event_line_id = ?
            ORDER BY happened_at DESC, created_at DESC
            """,
            (str(row["id"]),),
        )
        memory_response = get_event_line_memory_response(state.db, str(row["id"]))
        return EventLineDetailRecord(
            eventLine=build_event_line(row),
            tasks=tasks,
            activities=[build_event_line_activity(item) for item in activity_rows],
            memorySnapshot=memory_response.eventLineMemorySnapshot,
            predictionReadiness=memory_response.eventLineMemorySnapshot.predictionReadiness if memory_response.eventLineMemorySnapshot else None,
            clarificationNeeds=memory_response.clarificationNeeds,
        )

    def _cloud_event_line_unavailable_status(
        detail: str,
        *,
        organization_id: str | None = None,
        organization_name: str | None = None,
    ) -> EventLineSourceStatusRecord:
        return EventLineSourceStatusRecord(
            mode="cloud_only",
            cloudAvailable=False,
            organizationId=organization_id,
            organizationName=organization_name,
            cloudApiUrl=state.cloud_api_url,
            detail=detail,
            projectOptions=[
                EventLineProjectFilterOptionRecord(
                    id="__orphan__",
                    label="未归档项目",
                    kind="orphan",
                    lineCount=0,
                )
            ],
        )

    def _cached_event_line_organization_context() -> tuple[str | None, str | None]:
        session_user = get_cached_session_user()
        organization_id = session_user.organizationId if session_user else None
        organization_name = None
        if organization_id:
            local_org_row = state.db.fetchone(
                "SELECT name FROM org_profiles WHERE organization_id = ?",
                (organization_id,),
            )
            if local_org_row and local_org_row["name"]:
                organization_name = str(local_org_row["name"])
        return organization_id, organization_name

    def _require_cloud_event_line_session() -> SessionUserRecord:
        if not get_cloud_token() and not get_cloud_refresh_token():
            raise HTTPException(status_code=503, detail="请先连接云端协作后再使用事件线")
        try:
            return require_session_user()
        except HTTPException as exc:
            if exc.status_code in {401, 403}:
                raise HTTPException(status_code=503, detail="请先连接云端协作后再使用事件线") from exc
            if exc.status_code in {502, 503, 504}:
                raise HTTPException(status_code=503, detail="云端不可用，当前无法查看或操作事件线") from exc
            raise

    def _fetch_cloud_event_lines_payload() -> list[dict[str, object]]:
        response = cloud_request("GET", "/api/v1/event-lines")
        if not isinstance(response, list):
            raise HTTPException(status_code=502, detail="Invalid event line payload")
        return [item for item in response if isinstance(item, dict)]

    def _fetch_cloud_clients_payload() -> list[dict[str, object]]:
        response = cloud_request("GET", "/api/v1/clients")
        if not isinstance(response, list):
            raise HTTPException(status_code=502, detail="Invalid client payload")
        return [item for item in response if isinstance(item, dict)]

    def _build_event_line_source_status() -> EventLineSourceStatusRecord:
        cached_org_id, cached_org_name = _cached_event_line_organization_context()
        try:
            session_user = _require_cloud_event_line_session()
        except HTTPException as exc:
            return _cloud_event_line_unavailable_status(
                str(exc.detail) if exc.detail else "云端不可用，当前无法查看或操作事件线",
                organization_id=cached_org_id,
                organization_name=cached_org_name,
            )

        organization_id = session_user.organizationId
        organization_name = cached_org_name
        try:
            org_profile_payload = cloud_request("GET", "/api/v1/settings/org-model/profile")
            if isinstance(org_profile_payload, dict):
                organization_payload = org_profile_payload.get("organization")
                if isinstance(organization_payload, dict) and organization_payload.get("name"):
                    organization_name = str(organization_payload.get("name")).strip() or organization_name
        except HTTPException:
            pass

        try:
            event_lines_payload = _fetch_cloud_event_lines_payload()
            clients_payload = _fetch_cloud_clients_payload()
        except HTTPException as exc:
            return _cloud_event_line_unavailable_status(
                str(exc.detail) if exc.detail else "云端不可用，当前无法查看或操作事件线",
                organization_id=organization_id,
                organization_name=organization_name,
            )

        client_name_by_id: dict[str, str] = {}
        for item in clients_payload:
            client_id = str(item.get("id") or "").strip()
            if not client_id:
                continue
            client_label = str(item.get("name") or "").strip() or "未命名项目"
            client_name_by_id[client_id] = client_label

        project_counts: dict[str, int] = {}
        project_labels: dict[str, str] = {}
        orphan_count = 0
        for item in event_lines_payload:
            client_id = str(item.get("primaryClientId") or "").strip()
            cloud_label = str(item.get("primaryClientName") or "").strip() or "未命名项目"
            if not client_id:
                orphan_count += 1
                continue
            if client_id not in client_name_by_id:
                orphan_count += 1
                continue
            project_counts[client_id] = project_counts.get(client_id, 0) + 1
            project_labels[client_id] = client_name_by_id.get(client_id) or cloud_label

        project_options = [
            EventLineProjectFilterOptionRecord(
                id=client_id,
                label=project_labels[client_id],
                kind="client",
                lineCount=line_count,
            )
            for client_id, line_count in project_counts.items()
        ]
        project_options.sort(key=lambda item: item.label)
        project_options.append(
            EventLineProjectFilterOptionRecord(
                id="__orphan__",
                label="未归档项目",
                kind="orphan",
                lineCount=orphan_count,
            )
        )
        return EventLineSourceStatusRecord(
            mode="cloud_only",
            cloudAvailable=True,
            organizationId=organization_id,
            organizationName=organization_name,
            cloudApiUrl=state.cloud_api_url,
            detail="当前页面直接操作云端事件线数据",
            projectOptions=project_options,
        )

    def fetch_tasks(where_clause: str = "", params: tuple = ()) -> list[TaskRecord]:
        query = """
            SELECT t.*, l.name AS list_name, l.color AS list_color, c.name AS client_name
            FROM tasks t
            JOIN task_lists l ON l.id = t.list_id
            LEFT JOIN clients c ON c.id = t.client_id
        """
        if where_clause:
            query += f" WHERE {where_clause}"
        query += " ORDER BY CASE t.status WHEN 'inbox' THEN 0 WHEN 'doing' THEN 1 WHEN 'todo' THEN 2 WHEN 'done' THEN 3 ELSE 4 END, t.updated_at DESC"
        return [build_task(row) for row in state.db.fetchall(query, params)]

    def build_growth_workbench_snapshot(
        week_label: str | None = None,
        client_id: str | None = None,
        mode: Literal["global", "strategic"] = "global",
    ) -> GrowthWorkbenchSnapshotRecord:
        phase_blueprints = [
            ("p1", "需求接收", "明确需求来源、目标对象和优先级", ["需求来源模糊", "优先级未经确认"]),
            ("p2", "信息核对", "确认关键事实、材料和依赖项都已到位", ["输入材料不完整", "事实口径未统一"]),
            ("p3", "内部对齐", "明确会议目标、参会人及预期结论", ["未提前拉齐信息", "会议目标发散"]),
            ("p4", "方案产出", "形成结构清晰、可执行的初版方案", ["结构与受众不匹配", "缺少支撑数据"]),
            ("p5", "沟通推进", "把边界、责任人和时间线谈清楚", ["临场判断不足", "关键利益方未提前对齐"]),
            ("p6", "交付闭环", "形成明确交付物、待办与复核节点", ["只做了动作，没有闭环", "责任人和时间点不明确"]),
            ("p7", "复盘沉淀", "把本次有效做法转成可复用经验", ["只记录结果，没有方法", "经验无法迁移复用"]),
        ]
        task_kind_blueprints = [
            {
                "taskKind": "agreement_alignment",
                "keywords": ("协议", "合同", "条款", "说明迭代", "合作说明", "合作协议", "修订"),
                "riskTypes": ["boundary_risk", "commitment_risk", "negotiation_risk"],
                "requiredAbilities": ["collab", "risk", "write", "insight"],
                "defaultGoal": "把合作边界、关键争议点和本次要确认的结论谈清楚",
                "defaultDeliverable": "一版协议差异、待确认点和下一轮修改动作",
                "whyRelevant": "这类任务不是单纯沟通，而是边界与承诺对齐，稍早拍板就会留下后续风险。",
                "cards": [
                    {
                        "cardType": "动作卡",
                        "title": "沟通前先列本次必须确认的 3 个点",
                        "summary": "先把本次沟通一定要拿到的结论写清楚，再决定怎么开口。",
                        "checklist": ["本次必须确认的条款或边界", "哪些问题你能现场确认", "哪些问题需要带回内部"],
                        "talkTrack": ["这次我希望先把三件事对齐，避免双方理解继续漂移。"],
                        "templateHint": "协议沟通前置清单",
                        "expectedOutput": "本次沟通的核心议题与确认边界",
                    },
                    {
                        "cardType": "检查卡",
                        "title": "协议沟通前先排查承诺风险",
                        "summary": "把不能现场承诺的内容提前划出来，避免沟通时话说满。",
                        "checklist": ["哪些条款涉及资源/交付承诺", "哪些点需要负责人或法务兜底", "哪些说法只能表达方向不能表态"],
                        "talkTrack": [],
                        "templateHint": "风险排查清单",
                        "expectedOutput": "不能现场确认的条款清单",
                    },
                    {
                        "cardType": "话术卡",
                        "title": "先问真实顾虑，再谈条款表述",
                        "summary": "如果先急着改字句，容易错过对方真正卡住的顾虑。",
                        "checklist": [],
                        "talkTrack": ["为了避免我们只改表述不改问题，我想先确认您最担心的是哪一类合作风险。"],
                        "templateHint": "",
                        "expectedOutput": "对方真实顾虑与协商空间",
                    },
                    {
                        "cardType": "模板卡",
                        "title": "沟通后立刻沉淀版本差异与待确认项",
                        "summary": "会后不只记结论，要沉淀版本变化、待确认项和责任人。",
                        "checklist": ["版本差异", "待确认项", "责任人和时间点"],
                        "talkTrack": [],
                        "templateHint": "协议迭代纪要模板",
                        "expectedOutput": "带责任人的版本差异纪要",
                    },
                ],
            },
            {
                "taskKind": "external_communication",
                "keywords": ("沟通", "联系", "对接", "访谈", "拜访", "电话", "老师", "客户", "约访"),
                "riskTypes": ["boundary_risk", "fact_gap", "negotiation_risk"],
                "requiredAbilities": ["collab", "insight", "risk"],
                "defaultGoal": "确认对方真实诉求、边界和下一步推进条件",
                "defaultDeliverable": "一次带结论的沟通纪要和下一步动作",
                "whyRelevant": "外部沟通的关键不是把信息说完，而是拿到真实顾虑与下一步承诺。",
                "cards": [
                    {
                        "cardType": "动作卡",
                        "title": "沟通前先定目标、对象和预期结论",
                        "summary": "先回答这次为什么沟通、找谁沟通、沟通完要留下什么。",
                        "checklist": ["核心目标", "对方角色与立场", "预期结论"],
                        "talkTrack": [],
                        "templateHint": "外部沟通准备卡",
                        "expectedOutput": "明确的沟通目标和预期结论",
                    },
                    {
                        "cardType": "检查卡",
                        "title": "先补项目背景，再进入沟通",
                        "summary": "没有项目背景时，沟通容易停留在表面信息交换。",
                        "checklist": ["当前项目阶段", "最近一次相关沟通结论", "本次沟通与整体项目的关系"],
                        "talkTrack": [],
                        "templateHint": "",
                        "expectedOutput": "足够支撑沟通判断的背景包",
                    },
                    {
                        "cardType": "话术卡",
                        "title": "先确认对方最关注什么，再给方案",
                        "summary": "先问对方担心点，比上来先讲方案更容易收口。",
                        "checklist": [],
                        "talkTrack": ["为了确保这次沟通不跑偏，我想先确认一下您目前最关注的是什么。"],
                        "templateHint": "",
                        "expectedOutput": "对方最关注的问题清单",
                    },
                ],
            },
            {
                "taskKind": "cross_team_coordination",
                "keywords": ("跨部门", "协调", "资源", "协同", "对齐", "推动", "联动"),
                "riskTypes": ["boundary_risk", "fact_gap"],
                "requiredAbilities": ["collab", "exec", "risk"],
                "defaultGoal": "把协作边界、责任人和时间线收清楚",
                "defaultDeliverable": "一组已确认的协作动作和责任归属",
                "whyRelevant": "跨团队事项最容易卡在边界模糊和责任漂移。",
                "cards": [
                    {
                        "cardType": "动作卡",
                        "title": "先写清协作边界和第一责任人",
                        "summary": "没有边界和第一责任人，协作推进只会停在口头共识。",
                        "checklist": ["交付物是什么", "谁先动", "最晚时间点"],
                        "talkTrack": [],
                        "templateHint": "协作边界清单",
                        "expectedOutput": "带责任人和时间点的协作边界",
                    },
                    {
                        "cardType": "话术卡",
                        "title": "对齐资源时先谈约束，不要直接要结果",
                        "summary": "先把对方当前约束讲清楚，后面才知道怎么交换优先级。",
                        "checklist": [],
                        "talkTrack": ["为了让这件事有落地可能，我想先了解你们当前最大的排期约束是什么。"],
                        "templateHint": "",
                        "expectedOutput": "协作约束和可谈空间",
                    },
                ],
            },
            {
                "taskKind": "meeting_preparation",
                "keywords": ("会议", "议程", "纪要", "评审", "复盘会", "对齐会"),
                "riskTypes": ["fact_gap", "boundary_risk"],
                "requiredAbilities": ["collab", "write", "exec"],
                "defaultGoal": "让会议开始前就知道结论、边界和会后动作如何落地",
                "defaultDeliverable": "会议议程、参会人、预期结论和会后待办结构",
                "whyRelevant": "会前准备做得差，会议会退化成信息交换。",
                "cards": [
                    {
                        "cardType": "动作卡",
                        "title": "会前先锁定议题、参会人和预期结论",
                        "summary": "这三件事不清楚，会议就很难产出有效结论。",
                        "checklist": ["会议目标", "关键参会人", "预期结论"],
                        "talkTrack": [],
                        "templateHint": "会议准备模板",
                        "expectedOutput": "可执行的会议准备单",
                    },
                    {
                        "cardType": "模板卡",
                        "title": "会后直接转责任到人",
                        "summary": "纪要不只记结论，要能直接落到任务和负责人。",
                        "checklist": ["待办", "责任人", "截止时间"],
                        "talkTrack": [],
                        "templateHint": "会议纪要转任务模板",
                        "expectedOutput": "会后行动项清单",
                    },
                ],
            },
            {
                "taskKind": "proposal_output",
                "keywords": ("方案", "白皮书", "提案", "大纲", "汇报", "说明书", "材料"),
                "riskTypes": ["fact_gap", "commitment_risk"],
                "requiredAbilities": ["write", "analyze", "insight"],
                "defaultGoal": "形成结构清楚、面向对象、可被继续推进的输出物",
                "defaultDeliverable": "一个可继续编辑或评审的结构化版本",
                "whyRelevant": "方案类任务最怕只写内容，不先想受众、结论和支撑依据。",
                "cards": [
                    {
                        "cardType": "动作卡",
                        "title": "先定受众、目的和目录结构",
                        "summary": "结构先错了，后面只会越写越重。",
                        "checklist": ["面向谁", "想推进什么", "目录骨架"],
                        "talkTrack": [],
                        "templateHint": "方案大纲模板",
                        "expectedOutput": "清晰的目录和表达主线",
                    },
                    {
                        "cardType": "检查卡",
                        "title": "每一页都要有事实和判断的对应关系",
                        "summary": "没有支撑依据的判断，后续很难被采纳。",
                        "checklist": ["关键事实", "判断结论", "下一步动作"],
                        "talkTrack": [],
                        "templateHint": "",
                        "expectedOutput": "事实-判断-动作链条",
                    },
                ],
            },
            {
                "taskKind": "review_and_closure",
                "keywords": ("复盘", "验收", "闭环", "总结", "回顾", "沉淀"),
                "riskTypes": ["fact_gap"],
                "requiredAbilities": ["write", "analyze", "risk"],
                "defaultGoal": "把结果、原因、方法和下次动作讲清楚",
                "defaultDeliverable": "一条可复用经验或复盘结论",
                "whyRelevant": "复盘的价值不在记录结果，而在把方法和误区说清楚。",
                "cards": [
                    {
                        "cardType": "动作卡",
                        "title": "结果后面一定要补原因和改法",
                        "summary": "只有结果没有原因，这次经验很难迁移。",
                        "checklist": ["发生了什么", "为什么会这样", "下次如何更好"],
                        "talkTrack": [],
                        "templateHint": "复盘四段式模板",
                        "expectedOutput": "可复用的复盘记录",
                    },
                    {
                        "cardType": "模板卡",
                        "title": "把有效做法沉淀成经验卡",
                        "summary": "把一次有效动作沉淀出来，后面才能在相似项目里复用。",
                        "checklist": ["适用场景", "方法", "边界", "下一次提醒"],
                        "talkTrack": [],
                        "templateHint": "经验沉淀模板",
                        "expectedOutput": "一条结构完整的经验资产",
                    },
                ],
            },
        ]
        client_workspace_cache: dict[str, ClientWorkspaceResponse | None] = {}
        strategic_snapshot_cache: dict[str, StrategicCockpitSnapshotRecord | None] = {}

        def normalize_text(value: str | None) -> str:
            return (value or "").strip()

        normalized_mode: Literal["global", "strategic"] = "strategic" if mode == "strategic" else "global"
        scoped_client_id = normalize_text(client_id) or None
        event_line_client_cache: dict[str, str | None] = {}

        def resolve_scope_client_name(target_client_id: str | None) -> str | None:
            normalized_client_id = normalize_text(target_client_id)
            if not normalized_client_id:
                return None
            row = state.db.fetchone("SELECT name FROM clients WHERE id = ?", (normalized_client_id,))
            if not row:
                return None
            return normalize_text(row["name"]) or None

        scope_client_name = resolve_scope_client_name(scoped_client_id)

        def event_line_primary_client(event_line_id: str | None) -> str | None:
            normalized_event_line_id = normalize_text(event_line_id)
            if not normalized_event_line_id:
                return None
            if normalized_event_line_id not in event_line_client_cache:
                row = state.db.fetchone("SELECT primary_client_id FROM event_lines WHERE id = ?", (normalized_event_line_id,))
                event_line_client_cache[normalized_event_line_id] = normalize_text(row["primary_client_id"]) or None if row else None
            return event_line_client_cache[normalized_event_line_id]

        def task_client_matches(task: TaskRecord, target_client_id: str) -> bool:
            normalized_target = normalize_text(target_client_id)
            if not normalized_target:
                return False
            direct_client_id = normalize_text(task.clientId)
            if direct_client_id and direct_client_id == normalized_target:
                return True
            if task.projectContext and normalize_text(task.projectContext.clientId) == normalized_target:
                return True
            if task.eventLineId and event_line_primary_client(task.eventLineId) == normalized_target:
                return True
            return False

        strategic_keywords = (
            "战略",
            "陪伴",
            "研判",
            "判断",
            "客户",
            "基金会",
            "机构",
            "项目",
            "会议",
            "纪要",
            "资料",
            "方案",
            "复盘",
            "沟通",
            "推进",
            "行动项",
            "风险",
            "未决问题",
        )

        def is_strategic_learning_task(task: TaskRecord, target_client_id: str | None) -> bool:
            if target_client_id and task_client_matches(task, target_client_id):
                return True
            haystack = " ".join(
                item
                for item in (
                    task.title,
                    task.desc,
                    task.note or "",
                    task.sourceType or "",
                    task.businessCategory or "",
                    task.currentBlocker or "",
                    task.nextAction or "",
                    task.recentDecision or "",
                    task.eventLineName or "",
                    task.projectModuleName or "",
                    task.projectFlowName or "",
                    task.clientName or "",
                    task.projectContext.backgroundSummary if task.projectContext else "",
                    task.projectContext.goalSummary if task.projectContext else "",
                    task.projectContext.riskSummary if task.projectContext else "",
                )
                if item
            )
            return any(keyword in haystack for keyword in strategic_keywords)

        def parse_task_date(value: str | None):
            if not value:
                return None
            candidate = f"{value}T00:00:00" if len(value) <= 10 else value
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                return None

        def sort_updated_at(value: str | None):
            if not value:
                return datetime(1970, 1, 1)
            try:
                normalized = value.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is not None:
                    return parsed.replace(tzinfo=None)
                return parsed
            except ValueError:
                return datetime(1970, 1, 1)

        def format_deadline(task: TaskRecord) -> str:
            raw = task.dueDate or task.ddl
            if not raw:
                return "待补日期"
            date = parse_task_date(raw)
            if not date:
                return raw
            today = datetime.now()
            target = date.replace(hour=0, minute=0, second=0, microsecond=0)
            base = today.replace(hour=0, minute=0, second=0, microsecond=0)
            diff_days = round((target - base).total_seconds() / 86400)
            if diff_days < 0:
                return f"已超期 {abs(diff_days)} 天"
            if diff_days == 0:
                return "今天"
            if diff_days == 1:
                return "明天"
            if diff_days <= 7:
                return f"{diff_days} 天后"
            return f"{date.month}月{date.day}日"

        def infer_phase(task: TaskRecord) -> str:
            haystack = " ".join(
                part
                for part in (
                    task.title,
                    task.desc,
                    task.note or "",
                    task.orgContext.blockedAtStep if task.orgContext else "",
                    task.projectContext.projectFlowName if task.projectContext else "",
                )
                if part
            )
            if any(keyword in haystack for keyword in ("需求", "接收", "收件")) or task.status == "inbox":
                return "需求接收"
            if any(keyword in haystack for keyword in ("信息", "资料", "材料", "核对", "澄清")):
                return "信息核对"
            if any(keyword in haystack for keyword in ("对齐", "会议", "纪要", "评审")):
                return "内部对齐"
            if any(keyword in haystack for keyword in ("方案", "白皮书", "提案", "文档", "大纲", "写作", "输出")):
                return "方案产出"
            if any(keyword in haystack for keyword in ("沟通", "协调", "协作", "推进", "谈判", "资源")):
                return "沟通推进"
            if any(keyword in haystack for keyword in ("交付", "验收", "上线", "发布", "闭环")):
                return "交付闭环"
            if task.status == "done":
                return "复盘沉淀"
            if task.status == "doing":
                return "沟通推进" if (task.orgContext.isCrossDepartment if task.orgContext else False) else "交付闭环"
            return "内部对齐" if (task.orgContext.isCrossDepartment if task.orgContext else False) or task.collaborators else "信息核对"

        def urgency_meta(task: TaskRecord) -> tuple[str, str]:
            due_date = parse_task_date(task.dueDate or task.ddl)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            diff_days = round((due_date.replace(hour=0, minute=0, second=0, microsecond=0) - today).total_seconds() / 86400) if due_date else None
            if diff_days is not None and diff_days < 0:
                return "建议优先处理", "text-red-700 bg-red-100"
            if task.priority == "high" or (diff_days is not None and diff_days <= 2):
                return "建议优先处理", "text-red-700 bg-red-100"
            if task.viewerInboxStatus == "pending" or (task.orgContext.needsReview if task.orgContext else False) or (task.orgContext.blockedAtStep if task.orgContext else False):
                return "需先补关键动作", "text-orange-700 bg-orange-100"
            return "可直接推进", "text-green-700 bg-green-100"

        def risks_for_task(task: TaskRecord, phase: str) -> list[str]:
            risks: list[str] = []
            if not normalize_text(task.desc) and not normalize_text(task.note):
                risks.append("任务背景信息偏少，开始前建议先补齐目标、上下文和预期输出。")
            if not task.dueDate and not task.ddl:
                risks.append("截止时间尚未明确，推进节奏容易在中途松掉。")
            if (task.orgContext.isCrossDepartment if task.orgContext else False) or task.collaborators:
                risks.append("涉及多人或跨部门协作，如果不先对齐边界和责任人，后续容易返工。")
            if task.viewerInboxStatus == "pending" or (task.collaborationSummary.get("pending", 0) > 0):
                risks.append("仍有协作者未完成接收确认，关键动作可能停在等待。")
            if task.orgContext.needsReview if task.orgContext else False:
                risks.append("当前任务仍需要复核或审批，建议先补齐说明与证据。")
            if risks:
                return risks[:2]
            defaults = {
                "需求接收": "需求来源和目标对象还未完全确认，过早执行容易方向跑偏。",
                "信息核对": "关键信息口径若未先统一，后续材料和决策会反复返工。",
                "内部对齐": "参会人、边界和预期结论不清楚时，会议很容易变成信息交换。",
                "方案产出": "结构与受众若不匹配，方案会花很多时间在重写上。",
                "沟通推进": "关键利益方未提前识别时，推进节点最容易卡在协作博弈上。",
                "交付闭环": "只推进动作不收责任人和时间点，容易在最后一步失去闭环。",
                "复盘沉淀": "如果只记录结果不提炼方法，这次经验很难转成下次可复用资产。",
            }
            return [defaults.get(phase, "先补齐关键动作，再继续推进。")]

        def robot_assessment(task: TaskRecord, phase: str) -> tuple[bool, list[str]]:
            context_signals = len(
                [
                    item
                    for item in (
                        normalize_text(task.desc),
                        normalize_text(task.note),
                        "tags" if task.tags else "",
                        task.dueDate or task.ddl or "",
                    )
                    if item
                ]
            )
            haystack = f"{task.title}{task.desc}{task.note or ''}"
            standardizable = any(keyword in haystack for keyword in ("会议", "纪要", "清单", "模板", "方案", "提纲", "白皮书", "复盘", "风险", "对齐", "材料", "SOP", "文档"))
            human_heavy = (task.orgContext.isCrossDepartment if task.orgContext else False) or any(keyword in haystack for keyword in ("协调", "沟通", "谈判", "客户", "资源", "博弈", "冲突"))
            ready = context_signals >= 2 and standardizable and not human_heavy and task.status != "inbox"
            if ready:
                return True, ["任务上下文已补齐到可生成首稿", f"当前处在 {phase} 阶段，标准输出较明确", "可先由机器人生成准备清单或文档草稿"]
            reasons: list[str] = []
            if context_signals < 2:
                reasons.append("任务描述、备注或截止信息仍不够完整")
            if human_heavy:
                reasons.append("当前阶段强依赖跨部门或现场判断，暂不适合全自动执行")
            if not standardizable:
                reasons.append("任务输出结构还不够标准化，机器人难以稳定接手")
            return False, reasons[:3] or ["当前任务仍需要人先定调，再适合让机器人协助执行"]

        def next_advice(task: TaskRecord, phase: str) -> str:
            task_name = f"「{task.title}」"
            mapping = {
                "需求接收": f"先为{task_name}确认目标对象、优先级和成功标准，再进入执行。",
                "信息核对": f"先补齐{task_name}所需的材料、数据和关键口径，再进入下一步。",
                "内部对齐": f"建议先把{task_name}的参会人、边界和预期结论写清楚，再开始拉会或对齐。",
                "方案产出": f"已具备开始条件，建议先为{task_name}拉出结构化大纲，再补细节。",
                "沟通推进": f"不要直接硬推，先把{task_name}的责任人、协作边界和时间线谈清楚。",
                "交付闭环": f"把{task_name}的交付物、待办和复核节点一起收拢，避免最后一步失焦。",
                "复盘沉淀": f"完成{task_name}后，尽快把有效做法沉淀成一条可复用经验。",
            }
            return task.nextAction or (task.projectContext.nextAction if task.projectContext else None) or mapping.get(phase, f"先补齐{task_name}的关键动作，再继续推进。")

        def task_contexts(task: TaskRecord) -> list[GrowthContextLinkRecord]:
            contexts = [
                GrowthContextLinkRecord(
                    objectType="task",
                    objectId=task.id,
                    label=task.title,
                    subtitle=(task.projectContext.stage if task.projectContext else None) or task.eventLineName or task.clientName or task.listName,
                    tab="tasks",
                    statusLabel=task.status,
                )
            ]
            if task.eventLineId and task.eventLineName:
                contexts.append(
                    GrowthContextLinkRecord(
                        objectType="event_line",
                        objectId=task.eventLineId,
                        label=task.eventLineName,
                        subtitle=task.businessCategory or (task.projectContext.stage if task.projectContext else "") or "事件线",
                        tab="tasks",
                        statusLabel="事件线",
                    )
                )
            if task.clientId and task.clientName:
                contexts.append(
                    GrowthContextLinkRecord(
                        objectType="client",
                        objectId=task.clientId,
                        label=task.clientName,
                        subtitle=(task.projectContext.stage if task.projectContext else "") or task.businessCategory or "项目工作台",
                        tab="client_workspace",
                        statusLabel="客户项目",
                    )
                )
            project_module_id = (task.projectContext.projectModuleId if task.projectContext else None) or task.projectModuleId
            project_module_name = (task.projectContext.projectModuleName if task.projectContext else None) or task.projectModuleName
            if project_module_id and project_module_name:
                contexts.append(
                    GrowthContextLinkRecord(
                        objectType="project_module",
                        objectId=project_module_id,
                        label=project_module_name,
                        subtitle=task.clientName or task.eventLineName or "项目模块",
                        tab="tasks",
                        statusLabel="项目模块",
                    )
                )
            project_flow_id = (task.projectContext.projectFlowId if task.projectContext else None) or task.projectFlowId
            project_flow_name = (task.projectContext.projectFlowName if task.projectContext else None) or task.projectFlowName
            if project_flow_id and project_flow_name:
                contexts.append(
                    GrowthContextLinkRecord(
                        objectType="project_flow",
                        objectId=project_flow_id,
                        label=project_flow_name,
                        subtitle=(task.projectContext.stage if task.projectContext else "") or task.businessCategory or "流程节点",
                        tab="tasks",
                        statusLabel="项目流程",
                    )
                )
            strategic_snapshot = strategic_snapshot_for_client_cached(task.clientId or (task.projectContext.clientId if task.projectContext else None))
            if strategic_snapshot and strategic_snapshot.strategicLines:
                line = strategic_snapshot.strategicLines[0]
                contexts.append(
                    GrowthContextLinkRecord(
                        objectType="strategic_focus",
                        objectId=line.id,
                        label=line.title,
                        subtitle=line.stage or "战略呼应",
                        tab="strategic_accompaniment",
                        statusLabel="战略线",
                    )
                )
            return contexts

        def workspace_for_client_cached(client_id: str | None) -> ClientWorkspaceResponse | None:
            normalized = normalize_text(client_id)
            if not normalized:
                return None
            if normalized not in client_workspace_cache:
                try:
                    client_workspace_cache[normalized] = workspace_for_client(normalized)
                except HTTPException:
                    client_workspace_cache[normalized] = None
            return client_workspace_cache[normalized]

        def strategic_snapshot_for_client_cached(client_id: str | None) -> StrategicCockpitSnapshotRecord | None:
            normalized = normalize_text(client_id)
            if not normalized:
                return None
            if normalized not in strategic_snapshot_cache:
                try:
                    strategic_snapshot_cache[normalized] = build_strategic_cockpit_snapshot(normalized)
                except HTTPException:
                    strategic_snapshot_cache[normalized] = None
            return strategic_snapshot_cache[normalized]

        def primary_task_context(task: TaskRecord, contexts: list[GrowthContextLinkRecord]) -> GrowthContextLinkRecord | None:
            return (
                next((context for context in contexts if context.objectType == "task"), None)
                or next((context for context in contexts if context.objectType == "event_line"), None)
                or next((context for context in contexts if context.objectType == "client"), None)
                or (contexts[0] if contexts else None)
            )

        def infer_task_intent(task: TaskRecord, phase: str) -> GrowthTaskIntentRecord:
            haystack = normalize_text(
                " ".join(
                    part
                    for part in (
                        task.title,
                        task.desc,
                        task.note or "",
                        task.projectContext.projectFlowName if task.projectContext else "",
                        task.projectContext.projectModuleName if task.projectContext else "",
                    )
                    if part
                )
            )
            matched_blueprint = next(
                (
                    blueprint
                    for blueprint in task_kind_blueprints
                    if any(keyword in haystack for keyword in blueprint["keywords"])
                ),
                None,
            )
            if matched_blueprint is None:
                matched_blueprint = {
                    "taskKind": "general_execution",
                    "riskTypes": ["fact_gap"],
                    "requiredAbilities": ["exec", "collab"],
                    "defaultGoal": "把当前任务推进到下一个明确节点",
                    "defaultDeliverable": "一条带责任人和时间点的下一步动作",
                    "whyRelevant": f"当前任务处在「{phase}」阶段，系统会先给出最小可执行动作，再逐步补齐背景。",
                    "cards": [],
                }
            goal = (
                normalize_text(task.projectContext.goalSummary if task.projectContext else None)
                or normalize_text(task.nextAction)
                or normalize_text(task.recentDecision)
                or str(matched_blueprint["defaultGoal"])
            )
            deliverable = (
                normalize_text(task.projectContext.projectFlowSummary if task.projectContext else None)
                or normalize_text(task.projectContext.projectModuleSummary if task.projectContext else None)
                or normalize_text(task.nextAction)
                or str(matched_blueprint["defaultDeliverable"])
            )
            risk_types = list(matched_blueprint["riskTypes"])
            if not normalize_text(task.desc) and not normalize_text(task.note):
                risk_types.append("fact_gap")
            if (task.orgContext.isCrossDepartment if task.orgContext else False) or task.collaborators:
                risk_types.append("boundary_risk")
            if task.viewerInboxStatus == "pending":
                risk_types.append("coordination_gap")
            return GrowthTaskIntentRecord(
                taskKind=str(matched_blueprint["taskKind"]),
                goal=goal,
                deliverable=deliverable,
                riskTypes=list(dict.fromkeys(str(item) for item in risk_types if str(item).strip())),
                requiredAbilities=[str(item) for item in matched_blueprint["requiredAbilities"]],  # type: ignore[list-item]
                confidence=0.84 if matched_blueprint["taskKind"] != "general_execution" else 0.56,
                whyRelevant=str(matched_blueprint["whyRelevant"]),
            )

        def build_project_context_pack(task: TaskRecord, contexts: list[GrowthContextLinkRecord]) -> GrowthProjectContextPackRecord:
            workspace = workspace_for_client_cached(task.clientId or (task.projectContext.clientId if task.projectContext else None))
            strategic_snapshot = strategic_snapshot_for_client_cached(task.clientId or (task.projectContext.clientId if task.projectContext else None))
            task_notes = [
                item
                for item in (
                    normalize_text(task.desc),
                    normalize_text(task.note),
                    normalize_text(task.projectContext.backgroundSummary if task.projectContext else None),
                    normalize_text(task.projectContext.goalSummary if task.projectContext else None),
                    normalize_text(task.recentDecision),
                    normalize_text(task.nextAction),
                )
                if item
            ]
            linked_facts = [normalize_text(item.factValue) for item in task.linkedFactsPreview if normalize_text(item.factValue)]
            recent_meetings = [
                item
                for item in (
                    [
                        " · ".join(
                            part
                            for part in (
                                normalize_text(meeting.title),
                                normalize_text(meeting.stageLabel if hasattr(meeting, "stageLabel") else None),
                                normalize_text(meeting.updatedAt[:10] if getattr(meeting, "updatedAt", None) else None),
                            )
                            if part
                        )
                        for meeting in (workspace.meetings[:3] if workspace else [])
                    ]
                )
                if item
            ]
            strategic_focus: list[str] = []
            if strategic_snapshot:
                strategic_focus.extend(str(item).strip() for item in strategic_snapshot.headline.focusItems[:3] if str(item).strip())
                strategic_focus.extend(
                    item.title
                    for item in strategic_snapshot.strategicLines[:2]
                    if normalize_text(item.title)
                )
            context_gaps = [
                item
                for item in (
                    "缺任务背景说明" if not task_notes else "",
                    "缺历史会议信息" if not recent_meetings else "",
                    "缺附件或事实依据" if not task.attachments and not linked_facts else "",
                    "缺战略焦点" if not strategic_focus and task.clientId else "",
                )
                if item
            ]
            event_line_summary = "；".join(
                item
                for item in (
                    normalize_text(task.eventLineName),
                    normalize_text(task.projectContext.currentFocus if task.projectContext else None),
                    normalize_text(task.projectContext.currentBlocker if task.projectContext else None),
                )
                if item
            )
            return GrowthProjectContextPackRecord(
                title=(task.clientName or (task.projectContext.clientName if task.projectContext else None) or task.eventLineName or task.title),
                taskNotes=task_notes[:4],
                attachments=[normalize_text(item.title) for item in task.attachments[:4] if normalize_text(item.title)],
                memoryHints=[normalize_text(item) for item in task.memoryHints[:4] if normalize_text(item)],
                linkedFacts=linked_facts[:4],
                clientSummary=normalize_text(workspace.client.intro if workspace else None) or normalize_text(task.projectContext.backgroundSummary if task.projectContext else None),
                recentMeetings=recent_meetings[:3],
                eventLineSummary=event_line_summary,
                strategicFocus=list(dict.fromkeys(str(item) for item in strategic_focus if str(item).strip()))[:3],
                keyWarnings=list(dict.fromkeys(task.projectContext.riskSummary.split("；") if task.projectContext and normalize_text(task.projectContext.riskSummary) else []))[:3],
                contextGaps=context_gaps[:4],
            )

        def build_universal_skills(
            task: TaskRecord,
            *,
            task_intent: GrowthTaskIntentRecord,
            primary_context: GrowthContextLinkRecord | None,
            project_context_pack: GrowthProjectContextPackRecord,
        ) -> list[GrowthUniversalSkillItemRecord]:
            blueprint = next((item for item in task_kind_blueprints if item["taskKind"] == task_intent.taskKind), None)
            cards = list(blueprint["cards"]) if blueprint else []
            skill_items: list[GrowthUniversalSkillItemRecord] = []
            for index, card in enumerate(cards[:4]):
                skill_items.append(
                    GrowthUniversalSkillItemRecord(
                        id=f"{task.id}-skill-{index + 1}",
                        cardType=str(card["cardType"]),  # type: ignore[arg-type]
                        title=str(card["title"]),
                        summary=str(card["summary"]),
                        whyRelevant=task_intent.whyRelevant,
                        checklist=[str(item) for item in card.get("checklist", []) if str(item).strip()],
                        talkTrack=[str(item) for item in card.get("talkTrack", []) if str(item).strip()],
                        templateHint=str(card.get("templateHint") or ""),
                        sourceKind="rule",
                        expectedOutput=str(card.get("expectedOutput") or ""),
                        linkedContext=primary_context,
                    )
                )
            if len(skill_items) < 2 and project_context_pack.contextGaps:
                skill_items.append(
                    GrowthUniversalSkillItemRecord(
                        id=f"{task.id}-skill-ai-gap",
                        cardType="检查卡",
                        title="先补齐当前任务最缺的背景再继续推进",
                        summary="系统已识别到上下文缺口，先把缺的背景或事实补齐，推荐质量才会稳定。",
                        whyRelevant="当前任务背景不足时，任何泛化建议都会变空。",
                        checklist=project_context_pack.contextGaps[:3],
                        talkTrack=[],
                        templateHint="任务背景补齐清单",
                        sourceKind="ai_supplement",
                        expectedOutput="最小可执行的项目背景包",
                        linkedContext=primary_context,
                    )
                )
            return skill_items[:4]

        def build_material_refs(
            task: TaskRecord,
            *,
            contexts: list[GrowthContextLinkRecord],
            project_context_pack: GrowthProjectContextPackRecord,
        ) -> list[GrowthMaterialRefRecord]:
            refs: list[GrowthMaterialRefRecord] = []
            task_context = next((context for context in contexts if context.objectType == "task"), None)
            client_context = next((context for context in contexts if context.objectType == "client"), None)
            event_line_context = next((context for context in contexts if context.objectType == "event_line"), None)
            strategic_context = next((context for context in contexts if context.objectType == "strategic_focus"), None)
            for attachment in task.attachments[:3]:
                refs.append(
                    GrowthMaterialRefRecord(
                        id=f"attachment-{attachment.id}",
                        title=attachment.title,
                        summary="任务附件中已存在的资料，可直接进入本次动作准备。",
                        sourceKind="task_material",
                        linkedContext=task_context,
                    )
                )
            for index, meeting in enumerate(project_context_pack.recentMeetings[:2]):
                refs.append(
                    GrowthMaterialRefRecord(
                        id=f"meeting-{task.id}-{index}",
                        title=meeting,
                        summary="最近一次相关会议，可先读结论和争议点再进入本次动作。",
                        sourceKind="client_workspace",
                        linkedContext=client_context,
                    )
                )
            if project_context_pack.eventLineSummary:
                refs.append(
                    GrowthMaterialRefRecord(
                        id=f"event-line-{task.id}",
                        title=task.eventLineName or "当前事件线",
                        summary=project_context_pack.eventLineSummary,
                        sourceKind="event_line",
                        linkedContext=event_line_context,
                    )
                )
            for index, focus in enumerate(project_context_pack.strategicFocus[:2]):
                refs.append(
                    GrowthMaterialRefRecord(
                        id=f"strategic-focus-{task.id}-{index}",
                        title=focus,
                        summary="这条任务和当前战略焦点直接相关，沟通或输出时要对齐这一层目标。",
                        sourceKind="strategic_focus",
                        linkedContext=strategic_context or client_context,
                    )
                )
            if project_context_pack.clientSummary:
                refs.append(
                    GrowthMaterialRefRecord(
                        id=f"client-summary-{task.id}",
                        title=(task.clientName or "当前客户") + "背景摘要",
                        summary=project_context_pack.clientSummary,
                        sourceKind="project_context",
                        linkedContext=client_context,
                    )
                )
            return refs[:6]

        def build_action_plan(
            task: TaskRecord,
            *,
            task_intent: GrowthTaskIntentRecord,
            phase: str,
            primary_context: GrowthContextLinkRecord | None,
            project_context_pack: GrowthProjectContextPackRecord,
        ) -> list[GrowthActionPlanItemRecord]:
            return [
                GrowthActionPlanItemRecord(
                    id=f"{task.id}-plan-before-1",
                    phaseGroup="before",
                    title="开始前先确认本次要拿到的结论",
                    purpose="避免把沟通或推进做成无产出的信息交换。",
                    expectedOutput=task_intent.goal or "本次任务的目标与结论清单",
                    ifMissing="没有目标，沟通和输出都会发散，后面很难判断这次任务是否成功。",
                    actionLabel="回到当前任务补目标",
                    sourceKind="rule",
                    linkedContext=primary_context,
                ),
                GrowthActionPlanItemRecord(
                    id=f"{task.id}-plan-before-2",
                    phaseGroup="before",
                    title="先补项目背景和最近事实",
                    purpose="让当前动作建立在真实项目材料和历史结论上。",
                    expectedOutput="一份可执行的背景包：任务说明、最近会议、附件、关键事实",
                    ifMissing="背景不足时，建议会变空，沟通也容易停留在表面。",
                    actionLabel="查看项目背景包",
                    sourceKind="project_context",
                    linkedContext=primary_context,
                ),
                GrowthActionPlanItemRecord(
                    id=f"{task.id}-plan-during-1",
                    phaseGroup="during",
                    title=f"执行中围绕「{task_intent.taskKind}」收口关键问题",
                    purpose="把对方顾虑、边界和下一步动作在现场讲清楚。",
                    expectedOutput=task_intent.deliverable or "一组可执行的结论与待办",
                    ifMissing="执行时只讲信息不收结论，后续就只能靠会后补猜测。",
                    actionLabel="打开沟通/执行清单",
                    sourceKind="rule",
                    linkedContext=primary_context,
                ),
                GrowthActionPlanItemRecord(
                    id=f"{task.id}-plan-after-1",
                    phaseGroup="after",
                    title="完成后立即沉淀版本差异、待确认项和责任人",
                    purpose="把这次动作转成后续任务、会议和成长沉淀的证据。",
                    expectedOutput="带责任人的纪要、待办或经验记录",
                    ifMissing="如果会后不沉淀，这次任务里的有效判断很难进入后续成长账本。",
                    actionLabel="沉淀为经验",
                    sourceKind="project_context" if project_context_pack.attachments or project_context_pack.recentMeetings else "rule",
                    linkedContext=primary_context,
                ),
            ]

        def workbench_task_from_task(task: TaskRecord) -> GrowthWorkbenchTaskRecord:
            phase = infer_phase(task)
            urgency, urgency_color = urgency_meta(task)
            robot_ready, robot_reasons = robot_assessment(task, phase)
            contexts = task_contexts(task)
            primary_context = primary_task_context(task, contexts)
            task_intent = infer_task_intent(task, phase)
            project_context_pack = build_project_context_pack(task, contexts)
            universal_skills = build_universal_skills(
                task,
                task_intent=task_intent,
                primary_context=primary_context,
                project_context_pack=project_context_pack,
            )
            material_refs = build_material_refs(
                task,
                contexts=contexts,
                project_context_pack=project_context_pack,
            )
            action_plan = build_action_plan(
                task,
                task_intent=task_intent,
                phase=phase,
                primary_context=primary_context,
                project_context_pack=project_context_pack,
            )
            return GrowthWorkbenchTaskRecord(
                id=task.id,
                title=task.title,
                project=(task.projectContext.projectFlowName if task.projectContext else None) or (task.projectContext.projectModuleName if task.projectContext else None) or task.eventLineName or (task.projectContext.clientName if task.projectContext else None) or task.clientName or task.listName or task.ownerName or "任务执行",
                clientName=(task.projectContext.clientName if task.projectContext else None) or task.clientName,
                eventLineName=task.eventLineName,
                deadline=format_deadline(task),
                urgency=urgency,
                urgencyColor=urgency_color,
                phase=phase,
                risks=risks_for_task(task, phase),
                nextAdvice=next_advice(task, phase),
                robotReady=robot_ready,
                robotReasons=robot_reasons,
                recommendationId=None,
                linkedTaskId=task.id,
                linkedContexts=contexts,
                xpReward=28 if task.priority == "high" else 22 if task.priority == "normal" else 16,
                contextSummary=(task.projectContext.backgroundSummary if task.projectContext else "") or task.desc or task.note or "",
                projectModuleName=(task.projectContext.projectModuleName if task.projectContext else None) or task.projectModuleName,
                projectFlowName=(task.projectContext.projectFlowName if task.projectContext else None) or task.projectFlowName,
                projectStage=(task.projectContext.stage if task.projectContext else None),
                businessCategory=task.businessCategory,
                sourceEvidence=(task.projectContext.sourceEvidence if task.projectContext else []) or [],
                currentBlocker=task.currentBlocker or (task.projectContext.currentBlocker if task.projectContext else None) or (task.orgContext.blockedAtStep if task.orgContext else None),
                missingSignals=[
                    item
                    for item in (
                        "缺任务背景说明" if not normalize_text(task.desc) and not normalize_text(task.note) else "",
                        "缺明确时间点" if not task.dueDate and not task.ddl else "",
                        "缺协作边界确认" if ((task.orgContext.isCrossDepartment if task.orgContext else False) or task.collaborators) else "",
                        "缺复核说明" if (task.orgContext.needsReview if task.orgContext else False) else "",
                    )
                    if item
                ],
                hasBackground=bool(normalize_text(task.desc) or normalize_text(task.note) or (task.projectContext.backgroundSummary if task.projectContext else "")),
                hasDeadline=bool(task.dueDate or task.ddl),
                isCrossDepartment=bool((task.orgContext.isCrossDepartment if task.orgContext else False) or task.collaborators),
                needsReview=bool(task.orgContext.needsReview if task.orgContext else False),
                evidenceCount=task.evidenceCount,
                pendingCollaborations=int(task.collaborationSummary.get("pending", 0)),
                taskIntent=task_intent,
                universalSkills=universal_skills,
                projectContextPack=project_context_pack,
                actionPlan=action_plan,
                materialRefs=material_refs,
            )

        def workbench_task_from_focus(index: int, action: GrowthFocusActionRecord) -> GrowthWorkbenchTaskRecord:
            phase = next((item[1] for item in phase_blueprints if item[1] in (action.triggerNode or "") or item[1] in (action.projectStage or "") or item[1] in action.title or item[1] in action.summary), phase_blueprints[min(index + 2, len(phase_blueprints) - 1)][1])
            linked_contexts = list(action.linkedContexts)
            if action.linkedTaskId and not any(context.objectType == "task" and context.objectId == action.linkedTaskId for context in linked_contexts):
                linked_contexts.insert(
                    0,
                    GrowthContextLinkRecord(
                        objectType="task",
                        objectId=action.linkedTaskId,
                        label=action.title,
                        subtitle=action.projectStage or action.eventLineName or action.clientName or "当前焦点",
                        tab="tasks",
                        statusLabel="成长练习",
                    ),
                )
            return GrowthWorkbenchTaskRecord(
                id=f"focus-{action.id}",
                title=action.title,
                project=action.clientName or action.eventLineName or action.triggerNode or "成长焦点",
                clientName=action.clientName,
                eventLineName=action.eventLineName,
                deadline="本周补动作",
                urgency="建议优先处理" if any(keyword in action.whyNow for keyword in ("风险", "卡住", "返工", "阻塞", "现在")) else "需先补关键动作",
                urgencyColor="text-red-700 bg-red-100" if any(keyword in action.whyNow for keyword in ("风险", "卡住", "返工", "阻塞", "现在")) else "text-orange-700 bg-orange-100",
                phase=phase,
                risks=[action.whyNow or action.summary or "当前动作还没有稳定落到真实任务中。"],
                nextAdvice=action.summary or action.whyNow or f"先围绕 {action.title} 补一条可执行动作。",
                robotReady=any(keyword in f"{action.title}{action.summary}{action.whyNow}" for keyword in ("模板", "清单", "纪要", "生成", "对齐", "跟踪", "排查", "草案")),
                robotReasons=["当前动作有清晰输出", "已匹配到可复用练习或模板", "适合先让机器人生成草案再人工判断"] if any(keyword in f"{action.title}{action.summary}{action.whyNow}" for keyword in ("模板", "清单", "纪要", "生成", "对齐", "跟踪", "排查", "草案")) else ["仍需要人工结合现场判断", "当前动作更偏策略或协作博弈，不适合直接自动执行"],
                recommendationId=None,
                linkedTaskId=action.linkedTaskId,
                linkedContexts=linked_contexts,
                xpReward=20,
                contextSummary=action.summary,
                projectFlowName=action.triggerNode,
                projectStage=action.projectStage,
                sourceEvidence=[item for item in (action.whyNow, action.summary) if item],
                currentBlocker=action.whyNow or None,
                missingSignals=[action.whyNow] if action.whyNow else [],
                hasBackground=True,
                hasDeadline=False,
                isCrossDepartment=bool(action.eventLineId or action.clientId),
                needsReview=False,
                evidenceCount=1,
                pendingCollaborations=0,
            )

        def workbench_task_from_recommendation(index: int, recommendation: LearningRecommendationRecord) -> GrowthWorkbenchTaskRecord:
            phase = next((item[1] for item in phase_blueprints if item[1] in (recommendation.projectStage or "") or item[1] in (recommendation.triggerNode or "") or item[1] in recommendation.title), phase_blueprints[min(index + 2, len(phase_blueprints) - 1)][1])
            linked_contexts = list(recommendation.linkedContexts)
            if recommendation.linkedTaskId and not any(context.objectType == "task" and context.objectId == recommendation.linkedTaskId for context in linked_contexts):
                linked_contexts.insert(
                    0,
                    GrowthContextLinkRecord(
                        objectType="task",
                        objectId=recommendation.linkedTaskId,
                        label=recommendation.title,
                        subtitle=recommendation.projectStage or recommendation.eventLineName or recommendation.clientName or "成长练习",

```
