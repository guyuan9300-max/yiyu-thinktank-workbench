# backend/app/main.py:10440-10860

```python
            "待办",
            "后续安排",
        ),
        "next_actions": (
            "下一步",
            "行动项",
            "待办",
            "本周推进",
            "后续安排",
            "负责人",
            "截止时间",
            "风险",
            "卡点",
            "未决问题",
        ),
    }

    def build_retrieval_bundle(
        client_id: str,
        prompt: str,
        *,
        answer_intent: WorkspaceAnswerIntent | None = None,
    ):
        hint_terms = build_client_dna_retrieval_hint(client_id, prompt)
        expansion_terms = list(RETRIEVAL_INTENT_EXPANSION_TERMS.get(answer_intent or "", ()))
        retrieval_prompt_parts = [prompt]
        if hint_terms:
            retrieval_prompt_parts.append(f"背景关注：{' '.join(hint_terms)}")
        if expansion_terms:
            retrieval_prompt_parts.append(f"检索扩展词：{' '.join(expansion_terms)}")
        retrieval_prompt = "\n".join(part for part in retrieval_prompt_parts if part).strip()
        bundle = retrieve_knowledge_bundle(state.db, state.data_dir, client_id, retrieval_prompt)
        retrieval_summary = bundle.retrieval_summary if isinstance(bundle.retrieval_summary, dict) else {}
        bundle.retrieval_summary = {
            **retrieval_summary,
            "sourcePrompt": prompt,
            "clientDnaHintTerms": hint_terms,
            "answerIntent": answer_intent,
            "retrievalExpansionTerms": expansion_terms,
        }
        return bundle

    def map_route_intent_to_workspace_intent(intent: str) -> WorkspaceAnswerIntent:
        normalized = str(intent or "").strip()
        mapping: dict[str, WorkspaceAnswerIntent] = {
            "intro_profile": "intro_profile",
            "project_intro": "project_intro",
            "meeting_summary": "meeting_summary",
            "next_actions": "next_actions",
            "official_judgment_registry": "official_judgment_registry",
            "evidence_question": "evidence_question",
            "status_progress": "status_progress",
            "task_context": "status_progress",
            "task_next_action": "next_actions",
            "general": "general",
        }
        return mapping.get(normalized, "general")

    def route_decision_to_retrieval_reason(
        route_decision: RouteDecisionRecord | None,
        *,
        state_pack: StateAnswerContextPackRecord,
        current_reason: ChatRetrievalDecisionReason,
    ) -> ChatRetrievalDecisionReason:
        if route_decision is None:
            return current_reason
        intent = route_decision.intent
        retrieval_mode = route_decision.retrievalMode
        if intent == "official_judgment_registry":
            return "official_registry_requested" if state_pack.hits else "state_pool_empty"
        if intent == "intro_profile":
            return "intro_query_needs_evidence"
        if intent == "project_intro":
            return "project_intro_needs_evidence"
        if intent == "meeting_summary":
            return "meeting_summary_needs_evidence"
        if intent == "next_actions" or intent == "task_next_action":
            return "next_actions_needs_evidence"
        if intent == "evidence_question":
            return "evidence_question_needs_evidence"
        if intent == "status_progress" and retrieval_mode == "hybrid":
            return "status_progress_needs_hybrid_evidence"
        if retrieval_mode == "state_only":
            return "state_first_default" if state_pack.hits else "state_pool_empty"
        if retrieval_mode in {"hybrid", "raw_only"}:
            return "default_hybrid_evidence"
        return current_reason

    def build_multi_query_retrieval_bundle(
        client_id: str,
        route_decision: RouteDecisionRecord,
        prompt: str,
        *,
        answer_intent: WorkspaceAnswerIntent | None = None,
    ):
        query_plan = [
            str(item).strip()
            for item in route_decision.queryPlan
            if str(item).strip()
        ]
        deduped_query_plan = list(dict.fromkeys(query_plan))[:3]
        if len(deduped_query_plan) < 2:
            return build_retrieval_bundle(client_id, prompt, answer_intent=answer_intent)

        sub_bundles = []
        for subquery in deduped_query_plan:
            sub_prompt = f"{prompt}\n检索子问题：{subquery}"
            sub_bundles.append((subquery, build_retrieval_bundle(client_id, sub_prompt, answer_intent=answer_intent)))

        merged: dict[str, dict[str, object]] = {}
        for subquery, bundle in sub_bundles:
            for citation in bundle.citations[:20]:
                citation_payload = {
                    "knowledge_document_id": citation.knowledge_document_id,
                    "chunk_id": citation.chunk_id,
                    "title": citation.title,
                    "excerpt": citation.excerpt,
                    "score": citation.score,
                    "coverage": citation.coverage,
                    "section_label": citation.section_label,
                    "source_stage": citation.source_stage,
                    "drillthrough_used": citation.drillthrough_used,
                    "matched_terms": citation.matched_terms,
                    "path": citation.path,
                }
                excerpt_digest = hashlib.sha1(str(citation.excerpt).encode("utf-8")).hexdigest()[:10]
                key = "|".join(
                    [
                        str(citation.knowledge_document_id or ""),
                        str(citation.chunk_id or ""),
                        excerpt_digest,
                    ]
                )
                existing = merged.get(key)
                if existing is None:
                    merged[key] = {
                        "payload": citation_payload,
                        "score_sum": float(citation.score or 0.0),
                        "max_score": float(citation.score or 0.0),
                        "subqueries": [subquery],
                    }
                    continue
                existing["score_sum"] = float(existing.get("score_sum", 0.0) or 0.0) + float(citation.score or 0.0)
                existing["max_score"] = max(
                    float(existing.get("max_score", 0.0) or 0.0),
                    float(citation.score or 0.0),
                )
                seen_subqueries = [str(item) for item in existing.get("subqueries", []) if str(item).strip()]
                if subquery not in seen_subqueries:
                    seen_subqueries.append(subquery)
                existing["subqueries"] = seen_subqueries
                if float(citation.score or 0.0) >= float(existing.get("max_score", 0.0) or 0.0):
                    existing["payload"] = citation_payload

        ranked = sorted(
            merged.values(),
            key=lambda item: (
                float(item.get("score_sum", 0.0) or 0.0),
                float(item.get("max_score", 0.0) or 0.0),
            ),
            reverse=True,
        )[:30]
        citations = [cast(dict[str, object], item.get("payload", {})) for item in ranked if isinstance(item.get("payload"), dict)]
        combined_summary: dict[str, object] = {}
        for _, bundle in sub_bundles:
            if isinstance(bundle.retrieval_summary, dict):
                combined_summary.update(bundle.retrieval_summary)
        combined_summary.update(
            {
                "multiQueryUsed": True,
                "subqueryCount": len(deduped_query_plan),
                "queryPlan": deduped_query_plan,
                "subqueryHitCount": len(citations),
            }
        )
        return deserialize_retrieval_bundle(
            {
                "citations": citations,
                "coverage": max((float(bundle.coverage or 0.0) for _, bundle in sub_bundles), default=0.0),
                "retrieval_summary": combined_summary,
                "context_text": "\n\n".join(
                    [
                        f"[{index}] {subquery}\n{bundle.context_text}".strip()
                        for index, (subquery, bundle) in enumerate(sub_bundles, start=1)
                    ]
                ),
                "matched_terms": list(
                    dict.fromkeys(
                        [
                            term
                            for _, bundle in sub_bundles
                            for term in bundle.matched_terms
                            if str(term).strip()
                        ]
                    )
                ),
                "failure_reason": next((bundle.failure_reason for _, bundle in sub_bundles if bundle.failure_reason), None),
            }
        )

    def build_empty_retrieval_bundle(
        *,
        failure_reason: str | None = None,
        retrieval_summary: dict[str, object] | None = None,
    ):
        return deserialize_retrieval_bundle(
            {
                "citations": [],
                "coverage": 0.0,
                "retrieval_summary": retrieval_summary or {},
                "context_text": "",
                "matched_terms": [],
                "failure_reason": failure_reason,
            }
        )

    def prompt_requests_document_drilldown(prompt: str) -> bool:
        normalized = re.sub(r"\s+", "", str(prompt or "")).lower()
        document_tokens = (
            "原文",
            "原话",
            "出处",
            "来源",
            "引用",
            "哪份资料",
            "哪份材料",
            "哪篇",
            "附件",
            "文档",
            "文件",
            "全文",
            "摘录",
            "截图",
            "根据资料",
            "基于资料",
            "知识库",
            "搜索",
            "citation",
            "source",
            "document",
            "file",
        )
        return any(token in normalized for token in document_tokens)

    def detect_judgment_query_mode(
        prompt: str,
        state_pack: StateAnswerContextPackRecord,
    ) -> JudgmentQueryMode | None:
        if state_pack.plan.primaryIntent != "judgment":
            return None
        normalized = re.sub(r"\s+", "", str(prompt or "")).lower()
        registry_tokens = (
            "系统里",
            "系统内",
            "已登记",
            "已批准",
            "officiallayer",
            "official层",
            "登记的正式判断",
            "当前系统内正式判断",
            "正式结论登记",
        )
        evidence_tokens = (
            "基于资料",
            "根据资料",
            "从资料看",
            "能形成哪些判断",
            "形成哪些判断",
            "依据是什么",
            "为什么这样判断",
            "为何这样判断",
            "请引用",
            "请给出处",
            "请看原文",
            "原文支撑",
        )
        if any(token in normalized for token in registry_tokens):
            return "registry_only"
        if any(token in normalized for token in evidence_tokens) or prompt_requests_document_drilldown(prompt):
            return "evidence_based_synthesis"
        return "hybrid"

    def decide_workspace_chat_retrieval_strategy(
        prompt: str,
        state_pack: StateAnswerContextPackRecord,
        *,
        search_id: str | None,
        judgment_query_mode: JudgmentQueryMode | None = None,
        answer_intent: WorkspaceAnswerIntent | None = None,
    ) -> tuple[bool, str]:
        normalized = re.sub(r"\s+", "", str(prompt or "").lower())
        wants_document_drilldown = prompt_requests_document_drilldown(prompt)
        if search_id:
            return True, "search_cache_requested"
        if is_identity_role_query(prompt):
            return True, "identity_query_needs_evidence"
        if answer_intent == "official_judgment_registry":
            if state_pack.hits:
                # Backward-compat: explicit "系统里/系统内/已批准" asks were historically
                # labeled as state_first_default in retrieval metadata.
                if any(token in normalized for token in ("系统里", "系统内", "已批准", "已登记")):
                    return False, "state_first_default"
                return False, "official_registry_requested"
            return True, "state_pool_empty"
        if answer_intent == "intro_profile":
            return True, "intro_query_needs_evidence"
        if answer_intent == "project_intro":
            return True, "project_intro_needs_evidence"
        if answer_intent == "meeting_summary":
            return True, "meeting_summary_needs_evidence"
        if answer_intent == "next_actions":
            return True, "next_actions_needs_evidence"
        if answer_intent == "evidence_question":
            if wants_document_drilldown:
                return True, "document_drilldown_requested"
            return True, "evidence_question_needs_evidence"
        if answer_intent == "status_progress":
            return (False, "state_first_default") if state_pack.hits else (True, "state_pool_empty")
        if judgment_query_mode == "registry_only":
            return False, "state_first_default" if state_pack.hits else "state_pool_empty"
        if judgment_query_mode == "evidence_based_synthesis":
            if wants_document_drilldown:
                return True, "document_drilldown_requested"
            return True, "default_hybrid_evidence"
        if judgment_query_mode == "hybrid":
            if wants_document_drilldown:
                return True, "document_drilldown_requested"
            return (False, "default_hybrid_evidence") if state_pack.hits else (True, "state_pool_empty")
        if not state_pack.hits:
            return True, "state_pool_empty"
        if wants_document_drilldown:
            return True, "document_drilldown_requested"
        return False, "state_first_default"

    def build_state_unknowns_with_strategy(
        base_unknowns: list[str],
        *,
        retrieval_decision_reason: ChatRetrievalDecisionReason,
        judgment_query_mode: JudgmentQueryMode | None = None,
        evidence_support_mode: EvidenceSupportMode | None = None,
    ) -> list[str]:
        if judgment_query_mode == "registry_only":
            strategy_note = "当前优先展示系统内已登记的正式判断。"
            return list(dict.fromkeys([*base_unknowns, strategy_note]))
        if judgment_query_mode == "hybrid":
            strategy_note = (
                "当前先读取已登记判断，再结合资料、会议、任务和 DNA 信号形成待确认判断。"
                if evidence_support_mode != "raw_doc_drilldown"
                else "当前先读取已登记判断，再结合资料、会议、任务和 DNA 信号形成待确认判断，并补充少量原文回引。"
            )
            return list(dict.fromkeys([*base_unknowns, strategy_note]))
        if judgment_query_mode == "evidence_based_synthesis":
            strategy_note = "当前已进入证据下钻，将结合状态池与原始资料回答。"
            return list(dict.fromkeys([*base_unknowns, strategy_note]))
        strategy_note = {
            "state_first_default": "这次优先读取客户状态池，未下钻原文；如需出处，请继续追问“哪份原文/请引用文件”。",
            "official_registry_requested": "当前优先展示系统内已登记的正式判断。",
            "intro_query_needs_evidence": "介绍类问题会优先回到原始资料和项目证据，不直接套状态池。",
            "project_intro_needs_evidence": "项目介绍类问题会优先检索项目资料与原始证据。",
            "meeting_summary_needs_evidence": "会议纪要类问题会优先下钻会议、行动项和原文证据。",
            "next_actions_needs_evidence": "下一步行动类问题会优先结合任务、会议与原始证据。",
            "evidence_question_needs_evidence": "证据问法会优先引用原文与资料出处。",
            "status_progress_needs_hybrid_evidence": "进展类问题默认走状态池+原始证据的混合回答。",
            "default_hybrid_evidence": "当前采用状态池与原始资料的混合证据回答。",
            "state_pool_insufficient": "当前状态池覆盖还不够稳，本次回答会更多依赖证据检索或兜底链路。",
            "state_pool_empty": "当前状态池仍为空，暂时无法给出稳定的客户状态判断。",
        }.get(retrieval_decision_reason)
        if not strategy_note:
            return base_unknowns
        return list(dict.fromkeys([*base_unknowns, strategy_note]))

    def persist_retrieval_bundle(client_id: str, prompt: str, thread_id: str | None, bundle, retrieval_elapsed_ms: float) -> str:
        search_id = new_id("ks")
        timestamp = now_iso()
        payload = serialize_retrieval_bundle(bundle)
        payload["timing"] = {"retrievalMs": retrieval_elapsed_ms}
        normalized_thread_id: str | None = None
        if thread_id:
            existing_thread = state.db.fetchone(
                "SELECT id FROM chat_threads WHERE id = ? AND client_id = ?",
                (thread_id, client_id),
            )
            if existing_thread:
                normalized_thread_id = str(existing_thread["id"])
        state.db.execute(
            """
            INSERT INTO knowledge_search_runs(id, client_id, thread_id, prompt, status, retrieval_json, created_at, updated_at)
            VALUES(?, ?, ?, ?, 'ready', ?, ?, ?)
            """,
            (search_id, client_id, normalized_thread_id, prompt, to_json(payload), timestamp, timestamp),
        )
        return search_id

    def load_cached_retrieval_bundle(client_id: str, search_id: str, prompt: str):
        row = state.db.fetchone(
            """
            SELECT *
            FROM knowledge_search_runs
            WHERE id = ? AND client_id = ? AND status = 'ready'
            """,
            (search_id, client_id),
        )
        if not row:
            return None, 0.0
        if str(row["prompt"]).strip() != prompt.strip():
            return None, 0.0
        payload = from_json(str(row["retrieval_json"]), {})
        if not isinstance(payload, dict):
            return None, 0.0
        timing = payload.get("timing", {})
        retrieval_elapsed_ms = float(timing.get("retrievalMs", 0.0) or 0.0) if isinstance(timing, dict) else 0.0
        return deserialize_retrieval_bundle(payload), retrieval_elapsed_ms

    def fetch_chat_message_for_client(client_id: str, message_id: str) -> ChatMessageRecord:
        row = state.db.fetchone(
            """
            SELECT m.*
            FROM chat_messages m
            JOIN chat_threads t ON t.id = m.thread_id
            WHERE m.id = ? AND t.client_id = ?
            """,
```

---

# backend/app/main.py:24740-24930

```python
    def answer_clarification(clarification_id: str, payload: ClarificationAnswerPayload) -> ClarificationRecord:
        try:
            return answer_clarification_record(state.db, clarification_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Clarification not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/clients/{client_id}/knowledge/reclass-events", response_model=list[FileReclassEventRecord])
    def list_reclass_events(client_id: str) -> list[FileReclassEventRecord]:
        build_client_summary(client_id)
        return [FileReclassEventRecord(**item) for item in fetch_recent_reclass_events(state.db, client_id, limit=50)]

    @app.get("/api/v1/clients/{client_id}/knowledge/status", response_model=KnowledgeStatusRecord)
    def get_client_knowledge_status(client_id: str) -> KnowledgeStatusRecord:
        build_client_summary(client_id)
        ensure_standard_client_folders(client_id)
        return build_knowledge_status_record(client_id)

    @app.post("/api/v1/clients/{client_id}/knowledge/reindex-vector")
    def reindex_client_vector_collection(client_id: str) -> dict[str, object]:
        build_client_summary(client_id)
        result = reindex_client_vector(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
            ai_service=state.ai,
        )
        log_activity(
            "knowledge.reindex_vector",
            "client",
            client_id,
            result,
        )
        return result

    @app.get("/api/v1/retrieval/settings", response_model=RetrievalModelSettingsRecord)
    def get_retrieval_settings() -> RetrievalModelSettingsRecord:
        return get_retrieval_model_settings(state.db)

    @app.post("/api/v1/retrieval/settings", response_model=RetrievalModelSettingsRecord)
    def update_retrieval_settings(payload: RetrievalModelSettingsPayload) -> RetrievalModelSettingsRecord:
        previous = get_retrieval_model_settings(state.db)
        next_settings = save_retrieval_model_settings(state.db, payload)
        if retrieval_embedding_signature(previous) != retrieval_embedding_signature(next_settings):
            client_rows = state.db.fetchall("SELECT id FROM clients", ())
            for row in client_rows:
                state.db.set_setting(f"knowledge.active_embedding_signature:{str(row['id'])}", "")
        return next_settings

    @app.get("/api/v1/retrieval/health", response_model=RetrievalHealthRecord)
    def get_retrieval_health() -> RetrievalHealthRecord:
        settings = get_retrieval_model_settings(state.db)
        embedding_signature = retrieval_embedding_signature(settings)
        embedding_error: str | None = None
        embedding_ready = True
        if settings.embeddingProvider == "doubao":
            try:
                store = state.ai._store_for("doubao")  # type: ignore[attr-defined]
                has_key = bool(store and str(store.get_api_key() or "").strip())
            except Exception:
                has_key = False
            if not has_key:
                embedding_ready = False
                embedding_error = "doubao_api_key_missing"
        router_ready = True
        router_error: str | None = None
        if settings.routerEnabled and settings.routerProvider == "doubao":
            try:
                store = state.ai._store_for("doubao")  # type: ignore[attr-defined]
                has_key = bool(store and str(store.get_api_key() or "").strip())
            except Exception:
                has_key = False
            if not has_key:
                router_ready = False
                router_error = "doubao_api_key_missing"
        return RetrievalHealthRecord(
            embedding=RetrievalHealthComponentRecord(
                provider=settings.embeddingProvider,
                model=settings.embeddingModel,
                dimension=settings.embeddingDimension,
                signature=embedding_signature,
                ready=embedding_ready,
                error=embedding_error,
            ),
            router=RetrievalHealthComponentRecord(
                provider=settings.routerProvider,
                model=settings.routerModel,
                dimension=None,
                signature=None,
                ready=router_ready,
                error=router_error,
            ),
            rerank={
                "enabled": settings.rerankEnabled,
                "provider": settings.rerankProvider,
            },
            shadowMode=settings.shadowMode,
        )

    @app.get("/api/v1/retrieval/shadow-runs", response_model=list[RetrievalShadowRunRecord])
    def get_retrieval_shadow_runs(
        clientId: str | None = Query(default=None),
        limit: int = Query(default=60, ge=1, le=200),
    ) -> list[RetrievalShadowRunRecord]:
        return list_retrieval_shadow_runs(state.db, client_id=clientId, limit=limit)

    @app.get("/api/v1/retrieval/shadow-summary", response_model=RetrievalShadowSummaryRecord)
    def get_retrieval_shadow_summary_api(
        clientId: str | None = Query(default=None),
    ) -> RetrievalShadowSummaryRecord:
        return get_retrieval_shadow_summary(state.db, client_id=clientId)

    @app.post("/api/v1/clients/{client_id}/knowledge/rebuild", response_model=KnowledgeJobRecord)
    def rebuild_client_knowledge(client_id: str) -> KnowledgeJobRecord:
        build_client_summary(client_id)
        primary_job_types = (*MAIN_KNOWLEDGE_STATUS_JOB_TYPES, "rebuild_client_knowledge")
        placeholders = ", ".join("?" for _ in primary_job_types)
        pending = state.db.fetchone(
            f"""
            SELECT *
            FROM knowledge_jobs
            WHERE client_id = ? AND job_type IN ({placeholders}) AND status IN ('queued', 'running')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (client_id, *primary_job_types),
        )
        if pending:
            return KnowledgeJobRecord(
                id=str(pending["id"]),
                clientId=str(pending["client_id"]),
                jobType=str(pending["job_type"]),
                status=str(pending["status"]),  # type: ignore[arg-type]
                totalItems=int(pending["total_items"]),
                processedItems=int(pending["processed_items"]),
                lastError=str(pending["last_error"]) if pending["last_error"] else None,
                createdAt=str(pending["created_at"]),
                startedAt=str(pending["started_at"]) if pending["started_at"] else None,
                finishedAt=str(pending["finished_at"]) if pending["finished_at"] else None,
                updatedAt=str(pending["updated_at"]),
            )
        total_items = int(state.db.scalar("SELECT COUNT(1) AS count FROM documents WHERE client_id = ?", (client_id,)))
        job = enqueue_knowledge_job(
            client_id,
            "rebuild_client_knowledge",
            {"clientId": client_id},
            total_items=total_items,
        )
        log_activity("knowledge.rebuild", "client", client_id, {"jobId": job.id})
        return job

    @app.post("/api/v1/clients/{client_id}/knowledge/search", response_model=KnowledgeSearchResponse)
    def search_client_knowledge(client_id: str, payload: ChatRequest) -> KnowledgeSearchResponse:
        build_client_summary(client_id)
        query = payload.prompt.strip()
        retrieval_started = perf_counter()
        bundle = build_retrieval_bundle(client_id, query)
        retrieval_elapsed_ms = round((perf_counter() - retrieval_started) * 1000, 2)
        hits = [
            KnowledgeSearchHitRecord(
                title=item.title,
                excerpt=item.excerpt,
                score=item.score,
                stage={"master_index": "master_index", "surrogate": "surrogate"}.get(item.source_stage, "raw_chunk"),  # type: ignore[arg-type]
                path=item.path,
                sectionLabel=item.section_label,
                matchedTerms=item.matched_terms,
            )
            for item in bundle.citations
        ]
        preview_evidence = [
            EvidenceItem(
                id=new_id("ev"),
                title=item.title,
                excerpt=item.excerpt,
                sourceType="knowledge_chunk" if item.chunk_id else "knowledge_document",
                documentId=item.knowledge_document_id,
                path=item.path,
                score=item.score,
                coverage=item.coverage,
                sectionLabel=item.section_label,
                retrievalStage={"master_index": "master_index", "surrogate": "surrogate"}.get(item.source_stage, "raw_chunk"),
                isFallback=item.source_stage == "master_index",
                matchedTerms=item.matched_terms,
            )
            for item in bundle.citations
        ]
        retrieval_meta = bundle.retrieval_summary if isinstance(bundle.retrieval_summary, dict) else {}
        preview_summary = build_retrieval_preview_summary(client_id, query, preview_evidence, bundle)
        work_trace = build_answer_work_trace(query, preview_evidence, bundle)
```

---

# backend/app/main.py:25500-26820

```python
            UPDATE chat_messages
            SET content = ?, retrieval_summary_json = ?, timing_json = ?
            WHERE id = ? AND status = 'loading'
            """,
            (next_content, to_json(merged_summary), to_json(merged_timing), assistant_id),
        )

    def resolve_chat_answer(
        client_id: str,
        thread_id: str,
        prompt: str,
        assistant_id: str,
        search_id: str | None,
        request_started: float,
        run_id: str | None = None,
    ) -> ChatMessageRecord:
        if is_client_analysis_run_canceled(run_id):
            return fetch_chat_message_for_client(client_id, assistant_id)
        workspace_snapshot = workspace_for_client(client_id)
        page_intent = infer_page_intent(prompt, "workspace_chat")
        page_context_pack = build_client_page_context_pack(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
            prompt=prompt,
            page="workspace_chat",
            intent=page_intent,
            include_raw_evidence=page_intent.requiresRawEvidence,
            workspace=workspace_snapshot,
        )
        answer_policy = decide_answer_policy(page_context_pack)
        page_context_quality = page_context_pack.quality.contextQuality
        page_state_object_count = int(page_context_pack.quality.stateObjectCount or 0)
        should_prefer_legacy_fallback = bool(
            page_context_pack.quality.mustFallbackToLegacy or answer_policy.fallbackToLegacyRetrieval
        )
        candidate_boundary_disclosed = False
        state_context_pack = build_state_answer_context_pack(workspace_snapshot, prompt)
        retrieval_settings = get_retrieval_model_settings(state.db)
        embedding_signature = retrieval_embedding_signature(retrieval_settings)
        baseline_route_decision = page_context_pack.routeDecision or route_page_query(
            state.db,
            page="workspace_chat",
            prompt=prompt,
            client_id=client_id,
            page_context=page_context_pack,
            settings=retrieval_settings,
            ai_service=None,
        )
        candidate_route_decision = baseline_route_decision
        if retrieval_settings.routerEnabled:
            candidate_route_decision = route_page_query(
                state.db,
                page="workspace_chat",
                prompt=prompt,
                client_id=client_id,
                page_context=page_context_pack,
                settings=retrieval_settings,
                ai_service=state.ai,
            )
        shadow_mode_enabled = bool(retrieval_settings.shadowMode)
        use_router_shadow = bool(shadow_mode_enabled and retrieval_settings.routerEnabled)
        effective_route_decision = baseline_route_decision if use_router_shadow else candidate_route_decision
        page_context_pack.routeDecision = effective_route_decision

        explicit_registry_query = bool(
            re.search(r"(系统里|系统内|已批准|已登记|officiallayer|official层)", prompt, re.IGNORECASE)
        )
        answer_intent = classify_workspace_chat_intent(prompt)
        route_answer_intent = map_route_intent_to_workspace_intent(effective_route_decision.intent)
        if route_answer_intent != "general":
            if route_answer_intent == "official_judgment_registry" and not explicit_registry_query:
                pass
            elif route_answer_intent == "evidence_question" and answer_intent in {"intro_profile", "project_intro"}:
                pass
            else:
                answer_intent = route_answer_intent

        judgment_query_mode = detect_judgment_query_mode(prompt, state_context_pack)
        if (
            effective_route_decision.judgmentQueryMode in {"registry_only", "hybrid", "evidence_based_synthesis"}
            and not (effective_route_decision.judgmentQueryMode == "registry_only" and not explicit_registry_query)
        ):
            judgment_query_mode = effective_route_decision.judgmentQueryMode
        if answer_intent == "official_judgment_registry" and explicit_registry_query:
            judgment_query_mode = "registry_only"
        if (
            answer_intent == "next_actions"
            and judgment_query_mode in {"hybrid", "evidence_based_synthesis"}
            and not re.search(r"(判断|正式|approved|registry)", prompt, re.IGNORECASE)
        ):
            judgment_query_mode = None
        should_run_retrieval, retrieval_decision_reason = decide_workspace_chat_retrieval_strategy(
            prompt,
            state_context_pack,
            search_id=search_id,
            judgment_query_mode=judgment_query_mode,
            answer_intent=answer_intent,
        )
        retrieval_decision_reason = route_decision_to_retrieval_reason(
            effective_route_decision,
            state_pack=state_context_pack,
            current_reason=retrieval_decision_reason,
        )
        if effective_route_decision.retrievalMode == "state_only":
            should_run_retrieval = False
        elif (
            effective_route_decision.retrievalMode in {"hybrid", "raw_only"}
            and effective_route_decision.intent in {"intro_profile", "project_intro", "meeting_summary", "evidence_question", "task_next_action"}
        ):
            should_run_retrieval = True
        if (
            effective_route_decision.shouldUseRawEvidence
            and judgment_query_mode != "registry_only"
            and effective_route_decision.intent in {"intro_profile", "project_intro", "meeting_summary", "evidence_question", "task_next_action"}
        ):
            should_run_retrieval = True
            retrieval_decision_reason = route_decision_to_retrieval_reason(
                effective_route_decision,
                state_pack=state_context_pack,
                current_reason=retrieval_decision_reason,
            )
        if answer_intent in {"intro_profile", "project_intro"} and retrieval_decision_reason == "evidence_question_needs_evidence":
            retrieval_decision_reason = (
                "project_intro_needs_evidence"
                if answer_intent == "project_intro"
                else "intro_query_needs_evidence"
            )
        if answer_intent == "official_judgment_registry" and explicit_registry_query and state_context_pack.hits:
            retrieval_decision_reason = "state_first_default"
        if prompt_requests_document_drilldown(prompt) and judgment_query_mode != "registry_only":
            retrieval_decision_reason = "document_drilldown_requested"
        if judgment_query_mode != "registry_only":
            if answer_policy.mustUseRawEvidence and not should_run_retrieval:
                should_run_retrieval = True
                if answer_intent in {"intro_profile", "project_intro"}:
                    retrieval_decision_reason = "intro_query_needs_evidence"
                elif answer_intent == "evidence_question":
                    retrieval_decision_reason = "evidence_question_needs_evidence"
                else:
                    retrieval_decision_reason = "document_drilldown_requested"
            elif (
                should_prefer_legacy_fallback
                and not should_run_retrieval
                and answer_intent != "official_judgment_registry"
                and judgment_query_mode not in {"hybrid", "evidence_based_synthesis"}
            ):
                should_run_retrieval = True
                retrieval_decision_reason = "state_pool_insufficient"
        if (
            answer_intent in {"next_actions", "status_progress"}
            and len(page_context_pack.officialJudgments) >= 1
            and bool(state_context_pack.hits)
            and page_context_quality in {"strong", "usable"}
            and not page_intent.requiresRawEvidence
            and judgment_query_mode not in {"hybrid", "evidence_based_synthesis"}
        ):
            should_run_retrieval = False
            retrieval_decision_reason = "state_first_default"
        if judgment_query_mode == "registry_only":
            state_first_preview = (
                f"围绕“{prompt}”，当前优先展示系统内已登记的正式判断。"
            )
        elif judgment_query_mode == "hybrid":
            state_first_preview = (
                f"围绕“{prompt}”，当前先读取已登记判断，再结合资料、会议、任务和 DNA 信号形成待确认判断。"
            )
        elif judgment_query_mode == "evidence_based_synthesis":
            state_first_preview = (
                f"围绕“{prompt}”，当前已进入证据下钻，会结合状态池与原始资料组织 judgment 回答。"
            )
        elif answer_intent == "meeting_summary":
            state_first_preview = f"围绕“{prompt}”，当前优先回到会议纪要、行动项和原文证据组织回答。"
        elif answer_intent == "next_actions":
            state_first_preview = f"围绕“{prompt}”，当前会先结合任务、会议行动项与原始资料组织下一步回答。"
        elif answer_intent in {"intro_profile", "project_intro"}:
            state_first_preview = f"围绕“{prompt}”，当前会优先回到机构/项目资料组织可交付介绍。"
        else:
            state_first_preview = (
                f"围绕“{prompt}”，当前优先命中了客户状态池中的 {', '.join(state_context_pack.stateSources[:4]) or '状态对象'}，"
                "会先给出边界清晰的状态回答，再按需补充底层证据。"
            )
        retrieval_bundle = None
        retrieval_elapsed_ms = 0.0
        cached_retrieval = False
        linked_support_items: list[EvidenceSupportItemRecord] = []
        evidence_support_mode: EvidenceSupportMode = "none"
        rerank_used = False
        if judgment_query_mode in {"hybrid", "evidence_based_synthesis"}:
            linked_support_items = _build_linked_evidence_support_items(workspace_snapshot, prompt)
            if linked_support_items:
                evidence_support_mode = (
                    "evidence_cards"
                    if any(item.sourceType == "evidence_card" for item in linked_support_items)
                    else "linked_state_evidence"
                )
                retrieval_bundle = _linked_support_items_to_retrieval_bundle(
                    linked_support_items,
                    evidence_support_mode=evidence_support_mode,
                )
        if (
            judgment_query_mode in {"hybrid", "evidence_based_synthesis"}
            and should_prefer_legacy_fallback
            and not should_run_retrieval
            and not linked_support_items
            and answer_intent != "official_judgment_registry"
        ):
            should_run_retrieval = True
            retrieval_decision_reason = "state_pool_insufficient"
        if should_run_retrieval:
            generic_bundle = None
            if search_id:
                generic_bundle, retrieval_elapsed_ms = load_cached_retrieval_bundle(client_id, search_id, prompt)
                cached_retrieval = generic_bundle is not None
            if generic_bundle is None:
                retrieval_started = perf_counter()
                query_plan = [str(item).strip() for item in effective_route_decision.queryPlan if str(item).strip()]
                if len(query_plan) >= 2:
                    generic_bundle = build_multi_query_retrieval_bundle(
                        client_id,
                        effective_route_decision,
                        prompt,
                        answer_intent=answer_intent,
                    )
                else:
                    generic_bundle = build_retrieval_bundle(client_id, prompt, answer_intent=answer_intent)
                retrieval_elapsed_ms = round((perf_counter() - retrieval_started) * 1000, 2)
                if retrieval_decision_reason in {"intro_query_needs_evidence", "project_intro_needs_evidence"} and not generic_bundle.citations:
                    client_name = workspace_snapshot.client.name if workspace_snapshot and workspace_snapshot.client else ""
                    intro_prompt = (
                        f"{prompt}\n"
                        f"请优先检索{client_name or '该客户'}的组织介绍、核心业务、团队介绍、战略方向、会议纪要与任务推进线索。"
                    )
                    intro_retrieval_started = perf_counter()
                    boosted_bundle = build_retrieval_bundle(client_id, intro_prompt, answer_intent=answer_intent)
                    retrieval_elapsed_ms = round(
                        retrieval_elapsed_ms + (perf_counter() - intro_retrieval_started) * 1000,
                        2,
                    )
                    if boosted_bundle.citations:
                        boosted_summary = (
                            boosted_bundle.retrieval_summary
                            if isinstance(boosted_bundle.retrieval_summary, dict)
                            else {}
                        )
                        boosted_bundle.retrieval_summary = {
                            **boosted_summary,
                            "introEvidenceBoosted": True,
                        }
                        generic_bundle = boosted_bundle
            if generic_bundle and effective_route_decision.rerankNeeded and generic_bundle.citations:
                rerank_provider = build_rerank_provider(retrieval_settings)
                reranked_citations, rerank_meta = rerank_provider.rerank(prompt, list(generic_bundle.citations))
                rerank_used = bool(rerank_meta.rerankUsed and reranked_citations)
                rerank_payload = serialize_retrieval_bundle(generic_bundle)
                rerank_payload["citations"] = [
                    {
                        "knowledge_document_id": item.knowledge_document_id,
                        "chunk_id": item.chunk_id,
                        "title": item.title,
                        "excerpt": item.excerpt,
                        "score": item.score,
                        "coverage": item.coverage,
                        "section_label": item.section_label,
                        "source_stage": item.source_stage,
                        "drillthrough_used": item.drillthrough_used,
                        "matched_terms": item.matched_terms,
                        "path": item.path,
                    }
                    for item in reranked_citations[:30]
                ]
                rerank_summary = rerank_payload.get("retrieval_summary", {})
                rerank_payload["retrieval_summary"] = {
                    **(rerank_summary if isinstance(rerank_summary, dict) else {}),
                    "rerankUsed": rerank_used,
                    "rerankProvider": rerank_meta.provider,
                    "rerankCandidateCount": rerank_meta.candidateCount,
                    "rerankHitCount": rerank_meta.outputCount,
                    **({"rerankError": rerank_meta.error} if rerank_meta.error else {}),
                }
                generic_bundle = deserialize_retrieval_bundle(rerank_payload)
            if retrieval_bundle is None:
                retrieval_bundle = generic_bundle
                evidence_support_mode = (
                    "raw_doc_drilldown"
                    if generic_bundle.citations
                    else "generic_retrieval_fallback"
                )
            else:
                evidence_support_mode = (
                    "raw_doc_drilldown"
                    if generic_bundle.citations
                    else evidence_support_mode
                )
                retrieval_bundle = _merge_retrieval_bundles(
                    retrieval_bundle,
                    generic_bundle,
                    evidence_support_mode=evidence_support_mode,
                )
        if retrieval_bundle is None:
            retrieval_bundle = build_empty_retrieval_bundle(
                failure_reason="state_pool_preferred",
                retrieval_summary={
                    "retrievalDeferred": True,
                    "retrievalDecisionReason": retrieval_decision_reason,
                    "stateFirstEligible": True,
                    "previewSummary": state_first_preview,
                    "retrievalStage": "state_pool",
                },
            )
        retrieval_bundle.retrieval_summary = {
            **(retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}),
            "retrievalDeferred": not should_run_retrieval,
            "retrievalDecisionReason": retrieval_decision_reason,
            "answerIntent": answer_intent,
            "stateFirstEligible": bool(state_context_pack.hits),
            "judgmentQueryMode": judgment_query_mode,
            "evidenceSupportMode": evidence_support_mode,
            "routeDecision": effective_route_decision.model_dump(mode="json"),
            "routerSource": effective_route_decision.routerSource,
            "routerFallbackUsed": bool(effective_route_decision.fallbackUsed),
            "embeddingProvider": retrieval_settings.embeddingProvider,
            "embeddingModel": retrieval_settings.embeddingModel,
            "embeddingSignature": embedding_signature,
            "rerankUsed": rerank_used,
            "shadowMode": bool(shadow_mode_enabled),
            **(
                {"shadowRouteDecision": candidate_route_decision.model_dump(mode="json")}
                if use_router_shadow
                else {}
            ),
            **({"searchId": search_id, "cacheHit": cached_retrieval} if search_id and should_run_retrieval else {}),
        }
        evidence = [
            EvidenceItem(
                id=new_id("ev"),
                title=item.title,
                excerpt=item.excerpt,
                sourceType="knowledge_chunk" if item.chunk_id else "knowledge_document",
                documentId=item.knowledge_document_id,
                path=item.path,
                score=item.score,
                coverage=item.coverage,
                sectionLabel=item.section_label,
                retrievalStage={"master_index": "master_index", "surrogate": "surrogate"}.get(item.source_stage, "raw_chunk"),
                isFallback=item.source_stage == "master_index",
                matchedTerms=item.matched_terms,
            )
            for item in retrieval_bundle.citations
        ]
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
        client_dna_priority_note = build_client_dna_priority_note(client_id, prompt)
        if client_dna_priority_note:
            retrieval_bundle.retrieval_summary = {
                **retrieval_meta,
                "clientDnaPriority": client_dna_priority_note,
                "clientDnaTrail": client_dna_priority_note.replace("本次已优先参考客户 DNA 背景：", "").split("、"),
            }
            retrieval_meta = retrieval_bundle.retrieval_summary
        has_state_pool = bool(state_context_pack.hits)
        surrogate_hit_count = int(retrieval_meta.get("surrogateHitCount", 0) or 0)
        raw_chunk_hit_count = int(retrieval_meta.get("rawChunkHitCount", 0) or 0)
        has_grounded_evidence = bool(evidence)
        effective_answer_level = answer_policy.answerLevel
        if effective_answer_level == "insufficient" and has_grounded_evidence:
            effective_answer_level = "evidence_based"
        state_only_primary = (
            retrieval_decision_reason in {"state_first_default", "official_registry_requested"}
            and has_state_pool
            and not has_grounded_evidence
        )

        if has_state_pool and has_grounded_evidence:
            answer_mode = "grounded_answer"
            evidence_status = "sufficient"
            retrieval_stage = "state_plus_evidence"
        elif has_state_pool:
            answer_mode = "grounded_fallback"
            evidence_status = "partial"
            retrieval_stage = "state_pool"
            evidence = []
        elif has_grounded_evidence:
            answer_mode = "grounded_answer"
            evidence_status = "sufficient"
            retrieval_stage = "raw_chunk"
        else:
            answer_mode = "general_answer"
            evidence_status = "none"
            retrieval_stage = "background_only"
            evidence = []
        hybrid_judgment_pack = None
        if judgment_query_mode in {"hybrid", "evidence_based_synthesis"}:
            hybrid_judgment_pack = build_hybrid_judgment_context_pack(
                workspace_snapshot,
                prompt,
                judgment_query_mode=judgment_query_mode,
                evidence_support_mode=evidence_support_mode,
                support_items=linked_support_items,
                evidence=evidence,
            )
            if judgment_query_mode == "hybrid" and evidence_support_mode == "none" and hybrid_judgment_pack.evidenceSupportItems:
                evidence_support_mode = (
                    "evidence_cards"
                    if any(item.sourceType == "evidence_card" for item in hybrid_judgment_pack.evidenceSupportItems)
                    else "linked_state_evidence"
                )
                hybrid_judgment_pack.evidenceSupportMode = evidence_support_mode
                if isinstance(retrieval_bundle.retrieval_summary, dict):
                    retrieval_bundle.retrieval_summary = {
                        **retrieval_bundle.retrieval_summary,
                        "evidenceSupportMode": evidence_support_mode,
                    }
                    retrieval_meta = retrieval_bundle.retrieval_summary
            state_answer_sections = StateAnswerSectionsRecord(**hybrid_judgment_pack.sections.model_dump())
            state_source_summary = StateSourceSummaryRecord(**hybrid_judgment_pack.sourceSummary.model_dump())
        else:
            state_answer_sections = StateAnswerSectionsRecord(**state_context_pack.sections.model_dump())
            state_answer_sections.unknowns = build_state_unknowns_with_strategy(
                state_answer_sections.unknowns,
                retrieval_decision_reason=retrieval_decision_reason,
                judgment_query_mode=judgment_query_mode,
                evidence_support_mode=evidence_support_mode,
            )
            state_source_summary = StateSourceSummaryRecord(**state_context_pack.sourceSummary.model_dump())
        state_source_summary.documents = len(
            [
                item
                for item in evidence
                if item.retrievalStage == "raw_chunk"
            ]
        ) or state_source_summary.documents
        if judgment_query_mode == "hybrid":
            retrieval_stage = "hybrid_raw_drilldown" if evidence_support_mode == "raw_doc_drilldown" else "hybrid_linked_evidence"
        elif judgment_query_mode == "evidence_based_synthesis":
            retrieval_stage = "hybrid_raw_drilldown"
        state_first_hit_rate = (
            1
            if retrieval_decision_reason in {"state_first_default", "official_registry_requested"} and not should_run_retrieval and has_state_pool
            else 0
        )
        state_only_fallback_rate = 1 if answer_mode == "grounded_fallback" and state_only_primary else 0
        document_drilldown_rate = (
            1
            if retrieval_decision_reason
            in {
                "document_drilldown_requested",
                "intro_query_needs_evidence",
                "project_intro_needs_evidence",
                "meeting_summary_needs_evidence",
                "next_actions_needs_evidence",
                "evidence_question_needs_evidence",
                "status_progress_needs_hybrid_evidence",
                "default_hybrid_evidence",
            }
            else 0
        )
        raw_fallback_triggered = bool(
            should_run_retrieval
            and retrieval_decision_reason
            in {
                "document_drilldown_requested",
                "intro_query_needs_evidence",
                "project_intro_needs_evidence",
                "meeting_summary_needs_evidence",
                "next_actions_needs_evidence",
                "evidence_question_needs_evidence",
                "status_progress_needs_hybrid_evidence",
                "default_hybrid_evidence",
                "state_pool_insufficient",
                "state_pool_empty",
            }
        )
        legacy_fallback_used = bool(should_prefer_legacy_fallback and should_run_retrieval)
        identity_evidence_guard_rate = 1 if retrieval_decision_reason == "identity_query_needs_evidence" else 0
        candidate_leakage_count = int(state_context_pack.candidateLeakageCount or 0)
        retrieval_trace_record = RetrievalTraceRecord(
            routeDecision=effective_route_decision,
            embeddingProvider=str(retrieval_settings.embeddingProvider or "local_fastembed"),
            embeddingModel=str(retrieval_settings.embeddingModel or ""),
            embeddingDimension=int(retrieval_settings.embeddingDimension or 256),
            embeddingSignature=embedding_signature,
            vectorCollection=str(retrieval_meta.get("activeVectorCollection") or retrieval_meta.get("vectorCollection") or "") or None,
            lexicalHitCount=max(0, surrogate_hit_count),
            vectorHitCount=max(0, raw_chunk_hit_count),
            mergedHitCount=len(evidence),
            rerankHitCount=int(retrieval_meta.get("rerankHitCount", len(evidence) if rerank_used else 0) or 0),
            rawChunkHitCount=max(0, raw_chunk_hit_count),
            fallbackUsed=legacy_fallback_used,
            latencyMs={"retrievalMs": retrieval_elapsed_ms},
        )
        evidence_summary = build_analysis_evidence_summary(client_id, prompt, retrieval_bundle)
        work_trace = build_answer_work_trace(prompt, evidence, retrieval_bundle)
        if is_client_analysis_run_canceled(run_id):
            return fetch_chat_message_for_client(client_id, assistant_id)
        if run_id:
            update_client_analysis_run(
                run_id,
                status="running",
                phase="evidence_ready",
                progress=45.0,
                progress_floor=30.0,
                progress_ceiling=45.0,
                stage_label="背景材料已整理，正在组织长回答",
                elapsed_ms=retrieval_elapsed_ms,
                evidence_summary=evidence_summary,
                long_answer_status="pending",
                summary_status="pending",
                timing={"retrievalMs": retrieval_elapsed_ms},
            )
        pre_llm_meta = {
            **retrieval_meta,
            "retrievalStage": retrieval_stage,
            "answerMode": answer_mode,
            "answerIntent": answer_intent,
            "evidenceStatus": evidence_status,
            "shouldRunRetrieval": should_run_retrieval,
            "stateHitCount": len(state_context_pack.hits),
            "candidateLeakageCount": candidate_leakage_count,
            "judgmentQueryMode": judgment_query_mode,
            "evidenceSupportMode": evidence_support_mode,
            "stateSources": hybrid_judgment_pack.stateSources if hybrid_judgment_pack else state_context_pack.stateSources,
            "boundaryNotes": hybrid_judgment_pack.boundaryNotes if hybrid_judgment_pack else state_context_pack.boundaryNotes,
            "stateConfidence": hybrid_judgment_pack.stateConfidence if hybrid_judgment_pack else state_context_pack.stateConfidence,
            "stateAnswerSections": state_answer_sections.model_dump(mode="json"),
            "stateSourceSummary": state_source_summary.model_dump(mode="json"),
            "fallbackReason": (
                hybrid_judgment_pack.fallbackReason
                if hybrid_judgment_pack and hybrid_judgment_pack.fallbackReason
                else state_context_pack.fallbackReason or ("state_only" if state_only_primary else None)
            ),
            "state_first_hit_rate": state_first_hit_rate,
            "state_only_fallback_rate": state_only_fallback_rate,
            "document_drilldown_rate": document_drilldown_rate,
            "identity_evidence_guard_rate": identity_evidence_guard_rate,
            "candidate_leakage_count": candidate_leakage_count,
            "pageContextQuality": page_context_quality,
            "stateObjectCount": page_state_object_count,
            "answerLevel": effective_answer_level,
            "mustDiscloseCandidateBoundary": answer_policy.mustDiscloseCandidateBoundary,
            "mustUseRawEvidence": answer_policy.mustUseRawEvidence,
            "rawFallbackTriggered": raw_fallback_triggered,
            "candidateBoundaryDisclosed": False,
            "legacyFallbackUsed": legacy_fallback_used,
            "routeDecision": effective_route_decision.model_dump(mode="json"),
            "retrievalTrace": retrieval_trace_record.model_dump(mode="json"),
            "routerSource": effective_route_decision.routerSource,
            "routerFallbackUsed": bool(effective_route_decision.fallbackUsed),
            "embeddingProvider": retrieval_settings.embeddingProvider,
            "embeddingModel": retrieval_settings.embeddingModel,
            "embeddingSignature": embedding_signature,
            "rerankUsed": rerank_used,
            "shadowMode": bool(shadow_mode_enabled),
            **(
                {"shadowRouteDecision": candidate_route_decision.model_dump(mode="json")}
                if use_router_shadow
                else {}
            ),
            "llmInvoked": False,
            "previewSummary": (
                state_first_preview
                if state_only_primary
                else str(retrieval_meta.get("previewSummary") or build_retrieval_preview_summary(client_id, prompt, evidence, retrieval_bundle))
            ),
            "workTrace": work_trace,
            "phase": "generating",
            "progress": 54.0 if state_only_primary else (58.0 if answer_mode != "general_answer" else 46.0),
            "progressFloor": 50.0 if state_only_primary else (55.0 if answer_mode != "general_answer" else 25.0),
            "progressCeiling": 92.0,
            "stageLabel": (
                "庆华正在优先生成一版边界清晰的客户状态回答"
                if state_only_primary
                else "庆华正在组装 judgment hybrid 回答，整理已登记判断、证据支撑和判断草稿"
                if judgment_query_mode in {"hybrid", "evidence_based_synthesis"}
                else "庆华已经整理好当前问题所需的背景材料，正在调用千问组织完整分析"
                if answer_mode != "general_answer"
                else "当前没有命中足够的原始材料，庆华正在生成通用背景判断"
            ),
        }
        update_loading_assistant_message(
            assistant_id,
            retrieval_summary=pre_llm_meta,
            timing={"retrievalMs": retrieval_elapsed_ms},
            content="庆华正在整理背景材料，并组织分析答案……",
        )
        if is_client_analysis_run_canceled(run_id):
            return fetch_chat_message_for_client(client_id, assistant_id)
        if run_id:
            update_client_analysis_run(
                run_id,
                status="running",
                phase="generating_long_answer",
                progress=float(pre_llm_meta.get("progress", 58.0) or 58.0),
                progress_floor=45.0,
                progress_ceiling=85.0,
                stage_label=str(pre_llm_meta.get("stageLabel") or "正在生成长回答"),
                elapsed_ms=retrieval_elapsed_ms,
                evidence_summary=evidence_summary,
                timing={"retrievalMs": retrieval_elapsed_ms},
            )

        llm_started = perf_counter()
        provider_used = state.ai.current_provider()
        llm_invoked = True
        model_route = f"AI · {provider_used}"
        local_fallback_used = False
        compact_model_fallback_used = False
        stable_timeout_guard_triggered = False
        partial_generation_preserved = False
        state_only_generation_failure_detail: str | None = None
        hybrid_generation_failure_detail: str | None = None
        memory_background_context = ""
        memory_background_meta: dict[str, object] = {}
        workspace_state_context = hybrid_judgment_pack.summary if hybrid_judgment_pack else state_context_pack.summary
        answer_context = workspace_state_context
        if not state_only_primary and judgment_query_mode not in {"hybrid", "evidence_based_synthesis"}:
            memory_background_context, memory_background_meta = build_client_memory_background_context(client_id, prompt)
            if memory_background_meta.get("memoryBackgroundUsed"):
                retrieval_bundle.retrieval_summary = {
                    **retrieval_meta,
                    **memory_background_meta,
                }
                retrieval_meta = retrieval_bundle.retrieval_summary
            answer_context = build_chat_answer_context(
                client_id,
                prompt,
                evidence,
                retrieval_bundle,
                answer_intent=answer_intent,
                memory_background_context=memory_background_context,
                workspace_state_context=workspace_state_context,
            )
        answer_context_chars = len(answer_context or "")
        answer_context_evidence_count = len(re.findall(r"\[原始证据\s+\d+\]", answer_context or ""))
        retrieval_bundle.retrieval_summary = {
            **(retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}),
            "answerContextChars": answer_context_chars,
            "answerContextEvidenceCount": answer_context_evidence_count,
        }
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else retrieval_meta
        identity_role_insufficient = False
        latest_partial_content = ""
        latest_partial_structured: dict[str, object] | None = None

        def has_meaningful_partial_content(value: str) -> bool:
            cleaned = str(value or "").strip()
            if not cleaned:
                return False
            normalized = re.sub(r"\s+", "", cleaned)
            placeholder_variants = {
                re.sub(r"\s+", "", "正在围绕核心判断、关键张力和潜在风险整合原始证据，准备输出连续长文分析。"),
                re.sub(r"\s+", "", "千问正在基于完整材料直接生成长文回答。"),
                re.sub(r"\s+", "", "庆华正在整理背景材料，并组织分析答案……"),
                re.sub(r"\s+", "", "当前没有命中足够的原始材料，庆华正在生成通用背景判断"),
            }
            if normalized in placeholder_variants:
                return False
            return True

        grounded_system_instruction = (
            "你是一位资深战略顾问。请基于给定的客户原始材料回答问题。\n"
            "回答要先给结论，再展开关键依据与下一步建议。\n"
            "不要把答案写成证据罗列、材料摘要或系统说明。\n"
            "允许基于多条材料做综合判断，但未证实事实必须标注为待确认。\n\n"
            "【输出要求】\n"
            "1. 用 3-4 个小节组织回答。\n"
            "2. 每节 2-4 句话，必要时用「- 」列要点。\n"
            "3. 默认 400-900 字，不要为凑字数重复表达。\n"
            "4. 风险与待确认信息要单独列出。\n"
        )
        identity_sensitive_instruction = (
            grounded_system_instruction
            + "如果问题涉及创始人、负责人、理事长、秘书长等具体人物身份，只有在原始证据明确把人名与角色绑定时，才能下结论；否则只能说明当前证据不足以确认。"
        )
        grounded_fallback_instruction = (
            "请只基于当前已经整理出的原始证据继续回答。\n"
            "不要编造原始证据里没有的确定性事实。\n"
            "不要停留在表层摘录；只要证据允许，就尽量把深层判断讲透。\n"
            "排版规则：用「一、二、三」分层，并列要点用「- 」列表，关键结论用 **加粗**，禁止全篇连续长段落。\n"
        )
        state_pool_instruction = (
            "请优先基于当前客户状态池回答，不要退回成普通资料摘要。\n"
            "回答时必须显式区分：正式判断、待确认判断、本周动作、风险提醒、缺失信息。\n"
            "candidate 和 risk 只能写成提醒或待确认，不能写成已证实事实。\n"
            "如果底层原文证据暂时不充分，也要给出边界清晰的状态回答。\n"
        )

        def load_preserved_partial() -> tuple[str, dict[str, object] | None]:
            preserved_content = latest_partial_content
            preserved_structured = latest_partial_structured
            if run_id and not preserved_content:
                row = state.db.fetchone(
                    "SELECT long_answer, structured_summary_json FROM client_analysis_runs WHERE id = ?",
                    (run_id,),
                )
                if row:
                    if row["long_answer"]:
                        preserved_content = str(row["long_answer"]).strip()
                    structured_payload = from_json(str(row["structured_summary_json"] or "{}"), {})
                    if isinstance(structured_payload, dict) and structured_payload:
                        preserved_structured = structured_payload
            if preserved_content and not has_meaningful_partial_content(preserved_content):
                preserved_content = ""
                preserved_structured = None
            return preserved_content, preserved_structured

        def push_partial_analysis(partial: dict[str, object]) -> None:
            nonlocal latest_partial_content, latest_partial_structured
            if is_client_analysis_run_canceled(run_id):
                return
            partial_content = str(partial.get("content") or "").strip()
            if not partial_content:
                return
            meaningful_partial = has_meaningful_partial_content(partial_content)
            partial_structured = partial.get("structured") if isinstance(partial.get("structured"), dict) else None
            if meaningful_partial:
                latest_partial_content = partial_content
                latest_partial_structured = partial_structured
            partial_stage = str(partial.get("stageLabel") or "正在生成长回答")
            partial_progress = float(partial.get("progress") or 62.0)
            elapsed_now_ms = round((perf_counter() - request_started) * 1000, 2)
            update_client_analysis_run(
                run_id,
                status="running",
                phase="generating_long_answer",
                progress=partial_progress,
                progress_floor=58.0,
                progress_ceiling=95.0,
                stage_label=partial_stage,
                elapsed_ms=elapsed_now_ms,
                evidence_summary=evidence_summary,
                long_answer=partial_content if meaningful_partial else None,
                structured_summary=partial_structured if meaningful_partial and isinstance(partial_structured, dict) else None,
                long_answer_status="pending",
                summary_status="pending",
                answer_mode=answer_mode,
                llm_invoked=True,
                provider_used=provider_used,
                timing={
                    "retrievalMs": retrieval_elapsed_ms,
                    "llmMs": round((perf_counter() - llm_started) * 1000, 2),
                    "totalMs": elapsed_now_ms,
                },
            )

        def build_compact_model_fallback(failure_detail: str) -> AiStructuredResponse:
            note = build_compact_grounded_note(client_id, prompt, evidence, retrieval_bundle)
            return state.ai.generate_compact_grounded_fallback(
                prompt,
                f"{note}\n\n本轮正式成文未完整完成。失败详情：{failure_detail}",
            )

        force_stable_fallback = should_force_stable_fallback_path(client_id, answer_intent)
        if force_stable_fallback and answer_intent in {"intro_profile", "project_intro", "meeting_summary", "next_actions"} and evidence:
            llm_invoked = False
            provider_used = None
            model_route = "稳定简版链路"
            local_fallback_used = True
            stable_timeout_guard_triggered = True
            structured = build_local_retrieval_fallback(
                client_id,
                prompt,
                evidence,
                retrieval_bundle,
                "检测到连续模型读超时，已自动切换稳定简版回答链路。",
                answer_intent=answer_intent,
                state_answer_sections=state_answer_sections,
                workspace_state_context=workspace_state_context,
            )
            answer_mode = "grounded_fallback"
            evidence_status = "partial"
        elif hybrid_judgment_pack and judgment_query_mode in {"hybrid", "evidence_based_synthesis"}:
            try:
                structured = generate_hybrid_judgment_answer(
                    prompt,
                    hybrid_judgment_pack,
                    on_partial=push_partial_analysis,
                )
            except AiInvocationError as error:
                provider_used = error.provider
                model_route = f"AI · {error.provider}"
                hybrid_generation_failure_detail = error.detail
                local_fallback_used = True
                structured = build_hybrid_judgment_local_fallback(
                    prompt,
                    hybrid_judgment_pack,
                    failure_detail=error.detail,
                )
                answer_mode = "grounded_fallback"
                evidence_status = "partial"
            except Exception as error:
                llm_invoked = False
                provider_used = None
                model_route = "Judgment 回答降级"
                hybrid_generation_failure_detail = str(error)
                local_fallback_used = True
                structured = build_hybrid_judgment_local_fallback(
                    prompt,
                    hybrid_judgment_pack,
                    failure_detail=str(error),
                )
                answer_mode = "grounded_fallback"
                evidence_status = "partial"
        elif state_only_primary:
            try:
                structured = state.ai.generate_workspace_state_response(
                    prompt,
                    state_context_pack.summary,
                    on_partial=push_partial_analysis,
                )
            except AiInvocationError as error:
                provider_used = error.provider
                model_route = f"AI · {error.provider}"
                state_only_generation_failure_detail = error.detail
                local_fallback_used = True
                structured = build_state_only_local_fallback(
                    prompt,
                    state_answer_sections,
                    state_source_summary,
                    state_context_pack.boundaryNotes,
                    failure_detail=error.detail,
                )
            except Exception as error:
                llm_invoked = False
                provider_used = None
                model_route = "状态回答降级"
                state_only_generation_failure_detail = str(error)
                local_fallback_used = True
                structured = build_state_only_local_fallback(
                    prompt,
                    state_answer_sections,
                    state_source_summary,
                    state_context_pack.boundaryNotes,
                    failure_detail=str(error),
                )
        elif answer_mode == "grounded_answer" and is_identity_role_query(prompt):
            org_names = organization_identity_names()
            explicit_role_support = [
                item
                for item in evidence
                if evidence_has_explicit_role_binding(item, prompt=prompt, names=org_names)
            ]
            if not explicit_role_support:
                structured = build_identity_guard_response(client_id, prompt, evidence, retrieval_bundle)
                answer_mode = "grounded_fallback"
                evidence_status = "partial"
                llm_invoked = False
                provider_used = None
                model_route = "证据校验"
                identity_role_insufficient = True
            else:
                try:
                    structured = state.ai.generate_chat_response(
                        prompt,
                        identity_sensitive_instruction,
                        answer_context,
                        on_partial=push_partial_analysis,
                    )
                except AiInvocationError as error:
                    answer_mode = "system_failure"
                    model_route = f"AI · {error.provider}"
                    structured = AiStructuredResponse(
                        content="庆华暂时没能完成这次回答。",
                        judgment="模型调用失败，本次回答未成功生成。",
                        analysis=f"错误信息：{error.detail}",
                        actions="建议稍后重试；如果持续失败，请检查本地后端与 AI 配置。",
                        timeline="恢复后可立即重新生成。",
                    )
                    if evidence:
                        preserved_content, preserved_structured = load_preserved_partial()
                        if preserved_content:
                            structured = build_partial_generation_fallback(
                                prompt,
                                preserved_content,
                                error.detail,
                                partial_structured=preserved_structured,
                            )
                            partial_generation_preserved = True
                        else:
                            timeout_error = "超时" in error.detail or "timed out" in error.detail.lower()
                            if timeout_error:
                                structured = build_local_retrieval_fallback(
                                    client_id,
                                    prompt,
                                    evidence,
                                    retrieval_bundle,
                                    error.detail,
                                    answer_intent=answer_intent,
                                    state_answer_sections=state_answer_sections,
                                    workspace_state_context=workspace_state_context,
                                )
                                local_fallback_used = True
                            else:
                                try:
                                    structured = build_compact_model_fallback(error.detail)
                                    compact_model_fallback_used = True
                                except AiInvocationError:
                                    structured = build_local_retrieval_fallback(
                                        client_id,
                                        prompt,
                                        evidence,
                                        retrieval_bundle,
                                        error.detail,
                                        answer_intent=answer_intent,
                                        state_answer_sections=state_answer_sections,
                                        workspace_state_context=workspace_state_context,
                                    )
                                    local_fallback_used = True
                        answer_mode = "grounded_fallback"
                        evidence_status = "partial"
                    else:
                        structured = AiStructuredResponse(
                            content="当前没有命中足够的原始材料，且本次通用回答阶段也未成功完成。",
                            judgment="这次请求没有整理出足够直接的原始证据，同时大模型通用回答阶段超时。",
                            analysis=f"错误信息：{error.detail}",
                            actions="建议先换一个更明确的问题重试；如果持续失败，请检查本地 AI 配置与网络状态。",
                            timeline="恢复后可立即重新生成。",
                        )
                except Exception as error:
                    llm_invoked = False
                    provider_used = None
                    answer_mode = "system_failure"
                    model_route = "AI 调用失败"
                    structured = AiStructuredResponse(
                        content="庆华暂时没能完成这次回答。",
                        judgment="模型调用失败，本次回答未成功生成。",
                        analysis=f"错误信息：{str(error)}",
                        actions="建议稍后重试；如果持续失败，请检查本地后端与 AI 配置。",
                        timeline="恢复后可立即重新生成。",
                    )
        else:
            try:
                if answer_mode == "general_answer":
                    structured = state.ai.generate_general_fallback(
                        prompt,
                        (
                            "当前没有命中足够可支撑正式分析的原始材料。"
                            "请明确把这次回答写成基于通用背景的初步判断，而不是客户资料结论；不要伪造本地背景里不存在的事实、数据、会议结论或项目状态。"
                        ),
                        subject_name=build_client_summary(client_id).name,
                    )
                elif answer_mode == "grounded_fallback":
                    structured = state.ai.generate_chat_response(
                        prompt,
                        grounded_fallback_instruction,
                        answer_context,
                        on_partial=push_partial_analysis,
                    )
                else:
                    structured = state.ai.generate_chat_response(
                        prompt,
                        grounded_system_instruction,
                        answer_context,
                        on_partial=push_partial_analysis,
                    )
            except AiInvocationError as error:
                answer_mode = "system_failure"
                model_route = f"AI · {error.provider}"
                structured = AiStructuredResponse(
                    content="庆华暂时没能完成这次回答。",
                    judgment="模型调用失败，本次回答未成功生成。",
                    analysis=f"错误信息：{error.detail}",
                    actions="建议稍后重试；如果持续失败，请检查本地后端与 AI 配置。",
                    timeline="恢复后可立即重新生成。",
                )
                if evidence:
                    preserved_content, preserved_structured = load_preserved_partial()
                    if preserved_content:
                        structured = build_partial_generation_fallback(
                            prompt,
                            preserved_content,
                            error.detail,
                            partial_structured=preserved_structured,
                        )
                        partial_generation_preserved = True
                    else:
                        timeout_error = "超时" in error.detail or "timed out" in error.detail.lower()
                        if timeout_error:
                            structured = build_local_retrieval_fallback(
                                client_id,
                                prompt,
                                evidence,
                                retrieval_bundle,
                                error.detail,
                                answer_intent=answer_intent,
                                state_answer_sections=state_answer_sections,
                                workspace_state_context=workspace_state_context,
                            )
                            local_fallback_used = True
                        else:
                            try:
                                structured = build_compact_model_fallback(error.detail)
                                compact_model_fallback_used = True
                            except AiInvocationError:
                                structured = build_local_retrieval_fallback(
                                    client_id,
                                    prompt,
                                    evidence,
                                    retrieval_bundle,
                                    error.detail,
                                    answer_intent=answer_intent,
                                    state_answer_sections=state_answer_sections,
                                    workspace_state_context=workspace_state_context,
                                )
                                local_fallback_used = True
                    answer_mode = "grounded_fallback"
                    evidence_status = "partial"
                else:
                    structured = AiStructuredResponse(
                        content="当前没有命中足够的原始材料，且本次通用回答阶段也未成功完成。",
                        judgment="这次请求没有整理出足够直接的原始证据，同时大模型通用回答阶段超时。",
                        analysis=f"错误信息：{error.detail}",
                        actions="建议先换一个更明确的问题重试；如果持续失败，请检查本地 AI 配置与网络状态。",
                        timeline="恢复后可立即重新生成。",
                    )
            except Exception as error:
                llm_invoked = False
                provider_used = None
                answer_mode = "system_failure"
                model_route = "AI 调用失败"
                structured = AiStructuredResponse(
                    content="庆华暂时没能完成这次回答。",
                    judgment="模型调用失败，本次回答未成功生成。",
                    analysis=f"错误信息：{str(error)}",
                    actions="建议稍后重试；如果持续失败，请检查本地后端与 AI 配置。",
                    timeline="恢复后可立即重新生成。",
                )
        if is_client_analysis_run_canceled(run_id):
            return fetch_chat_message_for_client(client_id, assistant_id)
        if answer_mode == "general_answer":
            disclaimer = "以下内容不是基于当前客户原始资料的正式分析，而是基于通用背景的初步判断。"
            if not structured.content.startswith(disclaimer):
                structured.content = f"{disclaimer}\n\n{structured.content.strip()}"
            if disclaimer not in structured.judgment:
                structured.judgment = f"{disclaimer}{structured.judgment}"
        if answer_policy.mustDiscloseCandidateBoundary and answer_intent == "official_judgment_registry":
            candidate_boundary_prefix = (
                "当前还没有已批准的正式判断。"
                "基于当前资料和待确认判断，我先给出一版候选判断："
            )
            existing_content = str(structured.content or "").strip()
            if "还没有已批准的正式判断" in existing_content:
                candidate_boundary_disclosed = True
            else:
                structured.content = f"{candidate_boundary_prefix}\n{existing_content}".strip()
                candidate_boundary_disclosed = True
            state_answer_sections.official = []
            if not state_answer_sections.candidate and page_context_pack.candidateJudgments:
                state_answer_sections.candidate = [
                    str(item.get("summary") or item.get("topic") or "").strip()
                    for item in page_context_pack.candidateJudgments[:3]
                    if str(item.get("summary") or item.get("topic") or "").strip()
                ]
            if not any("候选判断" in item or "已批准" in item for item in state_answer_sections.unknowns):
                state_answer_sections.unknowns = list(
                    dict.fromkeys(
                        [
                            *state_answer_sections.unknowns,
                            "当前还没有已批准的正式判断，以上内容属于候选判断。",
                        ]
                    )
                )
        if answer_mode == "system_failure":
            run_long_answer_status = "failed"
            run_summary_status = "failed"
        elif answer_mode == "grounded_fallback":
            run_long_answer_status = "fallback"
            run_summary_status = "fallback"
        else:
            run_long_answer_status = "ready"
            run_summary_status = "ready"
        llm_elapsed_ms = round((perf_counter() - llm_started) * 1000, 2) if llm_invoked or answer_mode == "system_failure" else 0.0
        total_elapsed_ms = round((perf_counter() - request_started) * 1000, 2)
        failure_reason = None
        if answer_mode == "grounded_fallback":
            if identity_role_insufficient:
                failure_reason = "identity_role_evidence_insufficient"
            elif state_only_primary:
                failure_reason = "state_only"
            elif partial_generation_preserved:
                failure_reason = "llm_partial_preserved_after_retry"
            elif compact_model_fallback_used:
                failure_reason = "llm_compact_fallback_after_retry"
            elif local_fallback_used:
                failure_reason = "llm_local_fallback_after_retry"
            else:
                failure_reason = "partial_materials"
        elif answer_mode == "general_answer":
            failure_reason = "no_relevant_materials"
        elif answer_mode == "system_failure":
            failure_reason = "llm_failure"
        fallback_presentation_mode = determine_chat_fallback_presentation_mode(
            answer_mode=answer_mode,
            state_only_primary=state_only_primary,
            judgment_query_mode=judgment_query_mode,
            partial_generation_preserved=partial_generation_preserved,
            identity_role_insufficient=identity_role_insufficient,
            compact_model_fallback_used=compact_model_fallback_used,
            local_fallback_used=local_fallback_used,
        )
        if answer_mode != "system_failure":
            structured = apply_chat_fallback_presentation_guard(
                structured,
                presentation_mode=fallback_presentation_mode,
                client_id=client_id,
                prompt=prompt,
                evidence=evidence,
                retrieval_bundle=retrieval_bundle,
                answer_intent=answer_intent,
                state_answer_sections=state_answer_sections,
            )
        run_long_answer = structured.content if answer_mode != "system_failure" else None
        run_structured_summary = structured if answer_mode != "system_failure" else None
        response_meta = {
            **retrieval_meta,
            "retrievalStage": retrieval_stage,
            "answerMode": answer_mode,
            "answerIntent": answer_intent,
            "evidenceStatus": evidence_status,
            "failureReason": failure_reason,
            "shouldRunRetrieval": should_run_retrieval,
            "stateHitCount": len(state_context_pack.hits),
            "fallbackPresentationMode": fallback_presentation_mode,
            "fallbackReason": (
                hybrid_judgment_pack.fallbackReason
                if hybrid_judgment_pack and hybrid_judgment_pack.fallbackReason
                else state_context_pack.fallbackReason or failure_reason
            ),
            "stateSources": hybrid_judgment_pack.stateSources if hybrid_judgment_pack else state_context_pack.stateSources,
            "boundaryNotes": hybrid_judgment_pack.boundaryNotes if hybrid_judgment_pack else state_context_pack.boundaryNotes,
            "stateConfidence": hybrid_judgment_pack.stateConfidence if hybrid_judgment_pack else state_context_pack.stateConfidence,
            "stateAnswerSections": state_answer_sections.model_dump(mode="json"),
            "stateSourceSummary": state_source_summary.model_dump(mode="json"),
            "judgmentQueryMode": judgment_query_mode,
            "evidenceSupportMode": evidence_support_mode,
            "stableTimeoutGuardTriggered": stable_timeout_guard_triggered,
            "state_first_hit_rate": state_first_hit_rate,
            "state_only_fallback_rate": state_only_fallback_rate,
            "document_drilldown_rate": document_drilldown_rate,
            "identity_evidence_guard_rate": identity_evidence_guard_rate,
            "candidate_leakage_count": candidate_leakage_count,
            "candidateLeakageCount": candidate_leakage_count,
            "pageContextQuality": page_context_quality,
            "stateObjectCount": page_state_object_count,
            "answerLevel": effective_answer_level,
            "mustDiscloseCandidateBoundary": answer_policy.mustDiscloseCandidateBoundary,
            "mustUseRawEvidence": answer_policy.mustUseRawEvidence,
            "rawFallbackTriggered": raw_fallback_triggered,
            "candidateBoundaryDisclosed": candidate_boundary_disclosed,
            "legacyFallbackUsed": legacy_fallback_used,
            "routeDecision": effective_route_decision.model_dump(mode="json"),
            "retrievalTrace": retrieval_trace_record.model_dump(mode="json"),
            "routerSource": effective_route_decision.routerSource,
            "routerFallbackUsed": bool(effective_route_decision.fallbackUsed),
            "embeddingProvider": retrieval_settings.embeddingProvider,
            "embeddingModel": retrieval_settings.embeddingModel,
            "embeddingSignature": embedding_signature,
            "rerankUsed": rerank_used,
            "shadowMode": bool(shadow_mode_enabled),
            **(
                {"shadowRouteDecision": candidate_route_decision.model_dump(mode="json")}
                if use_router_shadow
                else {}
            ),
            **({"generationFailureDetail": state_only_generation_failure_detail} if state_only_generation_failure_detail else {}),
            **({"hybridGenerationFailureDetail": hybrid_generation_failure_detail} if hybrid_generation_failure_detail else {}),
            "workTrace": work_trace,
            "phase": "completed" if answer_mode != "system_failure" else "failed",
            "progress": 100.0,
            "progressFloor": 100.0,
            "progressCeiling": 100.0,
            "stageLabel": "回答已生成" if answer_mode != "system_failure" else "回答生成失败",
            "timing": {
                "totalMs": total_elapsed_ms,
                "retrievalMs": retrieval_elapsed_ms,
                "llmMs": llm_elapsed_ms,
            },
        }
        if use_router_shadow:
            shadow_failure_reason: str | None = None
            candidate_summary: dict[str, object] = {
                "routeDecision": candidate_route_decision.model_dump(mode="json"),
                "routerSource": candidate_route_decision.routerSource,
                "routerFallbackUsed": bool(candidate_route_decision.fallbackUsed),
                "citationCount": 0,
                "topDocs": [],
                "timing": {},
            }
            baseline_doc_keys = {
                f"{item.documentId or ''}:{item.path or ''}"
                for item in evidence
                if item.documentId or item.path
            }
            candidate_doc_keys: set[str] = set()
            try:
                if candidate_route_decision.retrievalMode in {"hybrid", "raw_only"}:
                    shadow_started = perf_counter()
                    candidate_intent = map_route_intent_to_workspace_intent(candidate_route_decision.intent)
                    if len(candidate_route_decision.queryPlan) >= 2:
                        candidate_bundle = build_multi_query_retrieval_bundle(
                            client_id,
                            candidate_route_decision,
                            prompt,
                            answer_intent=candidate_intent,
                        )
                    else:
                        candidate_bundle = build_retrieval_bundle(
                            client_id,
                            prompt,
                            answer_intent=candidate_intent,
                        )
                    candidate_elapsed_ms = round((perf_counter() - shadow_started) * 1000, 2)
                    candidate_doc_keys = {
                        f"{item.knowledge_document_id}:{item.path or ''}"
                        for item in candidate_bundle.citations
                        if item.knowledge_document_id or item.path
                    }
                    candidate_summary = {
                        **candidate_summary,
                        "citationCount": len(candidate_bundle.citations),
                        "topDocs": list(candidate_doc_keys)[:8],
                        "coverage": float(candidate_bundle.coverage or 0.0),
                        "timing": {"totalMs": candidate_elapsed_ms},
                    }
            except Exception as shadow_error:
                shadow_failure_reason = str(shadow_error)
            overlap_base = baseline_doc_keys | candidate_doc_keys
            overlap_rate = (
                (len(baseline_doc_keys & candidate_doc_keys) / len(overlap_base))
                if overlap_base
                else 0.0
            )
            try:
                create_retrieval_shadow_run(
                    state.db,
                    client_id=client_id,
                    page="workspace_chat",
                    prompt=prompt,
                    baseline_summary={
                        "routeDecision": baseline_route_decision.model_dump(mode="json"),
                        "retrievalDecisionReason": retrieval_decision_reason,
                        "citationCount": len(evidence),
                        "topDocs": list(baseline_doc_keys)[:8],
                        "timing": {"totalMs": total_elapsed_ms, "retrievalMs": retrieval_elapsed_ms},
                    },
                    candidate_summary=candidate_summary,
                    overlap_rate=overlap_rate,
                    candidate_better=len(candidate_doc_keys) > len(baseline_doc_keys),
                    failure_reason=shadow_failure_reason,
                )
            except Exception:
                pass
        timestamp = now_iso()
        if run_id:
            update_client_analysis_run(
                run_id,
                status="running" if answer_mode != "system_failure" else "failed",
                phase="generating_summary" if answer_mode != "system_failure" else "failed",
                progress=90.0 if answer_mode != "system_failure" else 100.0,
                progress_floor=85.0 if answer_mode != "system_failure" else 100.0,
                progress_ceiling=100.0,
                stage_label="正在整理最终答案" if answer_mode != "system_failure" else "回答生成失败",
                elapsed_ms=total_elapsed_ms,
                evidence_summary=evidence_summary,
                long_answer=run_long_answer,
                long_answer_status=run_long_answer_status,
                summary_status="pending" if answer_mode != "system_failure" else "failed",
                answer_mode=answer_mode,
                llm_invoked=llm_invoked,
                provider_used=provider_used,
                failure_reason=failure_reason,
                timing={"totalMs": total_elapsed_ms, "retrievalMs": retrieval_elapsed_ms, "llmMs": llm_elapsed_ms},
            )
        state.db.execute(
            """
            UPDATE chat_messages
            SET content = ?, structured_data_json = ?, model_route = ?, llm_invoked = ?, provider_used = ?,
                answer_mode = ?, evidence_status = ?, failure_reason = ?, timing_json = ?, retrieval_summary_json = ?,
                evidence_json = ?, status = 'success', created_at = ?
            WHERE id = ?
            """,
            (
                structured.content,
                to_json(structured.model_dump()),
                model_route,
                1 if llm_invoked else 0,
                provider_used,
                answer_mode,
                evidence_status,
                failure_reason,
                to_json({"totalMs": total_elapsed_ms, "retrievalMs": retrieval_elapsed_ms, "llmMs": llm_elapsed_ms}),
                to_json(response_meta),
                to_json([item.model_dump() for item in evidence]),
                timestamp,
                assistant_id,
            ),
        )
        answer_run_id = new_id("ans")
        state.db.execute(
            """
            INSERT INTO answer_runs(
                id, client_id, thread_id, prompt, status, coverage_score, retrieval_mode, llm_invoked,
                provider_used, failure_reason, retrieval_json, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                answer_run_id,
                client_id,
                thread_id,
                prompt,
                "completed" if answer_mode in {"grounded_answer", "grounded_fallback", "general_answer"} else "failed",
                retrieval_bundle.coverage,
                retrieval_stage,
                1 if llm_invoked else 0,
                provider_used,
                failure_reason,
                to_json(response_meta),
                timestamp,
            ),
        )
        for item in retrieval_bundle.citations:
```
