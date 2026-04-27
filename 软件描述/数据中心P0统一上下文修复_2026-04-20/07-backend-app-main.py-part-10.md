# 源码文件：`backend/app/main.py`（分片 10）

- 行号范围：25201-28000
- 总行数：   30416
- 导出时间：2026-04-20

```python
        *,
        retrieval_summary: dict[str, object] | None = None,
        timing: dict[str, float] | None = None,
        content: str | None = None,
    ) -> None:
        current_row = state.db.fetchone("SELECT retrieval_summary_json, timing_json, content FROM chat_messages WHERE id = ?", (assistant_id,))
        if not current_row:
            return
        merged_summary = from_json(str(current_row["retrieval_summary_json"] or "{}"), {})
        if not isinstance(merged_summary, dict):
            merged_summary = {}
        if retrieval_summary:
            merged_summary.update(retrieval_summary)
        merged_timing = from_json(str(current_row["timing_json"] or "{}"), {})
        if not isinstance(merged_timing, dict):
            merged_timing = {}
        if timing:
            merged_timing.update(timing)
        phase = str(merged_summary.get("phase") or "retrieving").strip() or "retrieving"
        floor, ceiling = phase_progress_window(phase)
        merged_summary["progressFloor"] = float(merged_summary.get("progressFloor", floor) or floor)
        merged_summary["progressCeiling"] = float(merged_summary.get("progressCeiling", ceiling) or ceiling)
        merged_summary["lastUpdatedAt"] = now_iso()
        next_content = content if content is not None else str(current_row["content"] or "")
        state.db.execute(
            """
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
        judgment_query_mode = detect_judgment_query_mode(prompt, state_context_pack)
        answer_intent = classify_workspace_chat_intent(prompt)
        should_run_retrieval, retrieval_decision_reason = decide_workspace_chat_retrieval_strategy(
            prompt,
            state_context_pack,
            search_id=search_id,
            judgment_query_mode=judgment_query_mode,
            answer_intent=answer_intent,
        )
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
            if "还没有已批准" in existing_content or "候选判断" in existing_content:
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
            citation_document_id: str | None = item.knowledge_document_id
            if citation_document_id.startswith("v2doc_"):
                mapped_document = state.db.fetchone(
                    "SELECT document_id FROM v2_documents WHERE id = ?",
                    (citation_document_id,),
                )
                if mapped_document and mapped_document["document_id"]:
                    legacy_document = state.db.fetchone(
                        "SELECT id FROM knowledge_documents WHERE document_id = ?",
                        (str(mapped_document["document_id"]),),
                    )
                    citation_document_id = str(legacy_document["id"]) if legacy_document and legacy_document["id"] else None
                else:
                    citation_document_id = None
            elif not state.db.fetchone(
                "SELECT id FROM knowledge_documents WHERE id = ?",
                (citation_document_id,),
            ):
                citation_document_id = None
            if not citation_document_id:
                continue
            state.db.execute(
                """
                INSERT INTO answer_citations(
                    id, answer_run_id, knowledge_document_id, chunk_id, source_stage, drillthrough_used, title, excerpt, score, coverage_contribution, section_label, matched_terms_json, path, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("cit"),
                    answer_run_id,
                    citation_document_id,
                    item.chunk_id,
                    item.source_stage,
                    1 if item.drillthrough_used else 0,
                    item.title,
                    item.excerpt,
                    item.score,
                    retrieval_bundle.coverage,
                    item.section_label,
                    to_json(item.matched_terms),
                    item.path,
                    timestamp,
                ),
            )
            state.db.execute(
                "UPDATE knowledge_documents SET deep_read = 1, last_hit_question = ?, updated_at = ? WHERE id = ?",
                (prompt[:120], timestamp, citation_document_id),
        )
        state.db.execute("UPDATE chat_threads SET updated_at = ? WHERE id = ?", (timestamp, thread_id))
        if run_id:
            update_client_analysis_run(
                run_id,
                status="completed" if answer_mode != "system_failure" else "failed",
                phase="completed" if answer_mode != "system_failure" else "failed",
                progress=100.0,
                progress_floor=100.0,
                progress_ceiling=100.0,
                stage_label="分析已完成" if answer_mode != "system_failure" else "回答生成失败",
                elapsed_ms=total_elapsed_ms,
                evidence_summary=evidence_summary,
                long_answer=run_long_answer,
                structured_summary=run_structured_summary,
                long_answer_status=run_long_answer_status,
                summary_status=run_summary_status,
                answer_mode=answer_mode,
                llm_invoked=llm_invoked,
                provider_used=provider_used,
                failure_reason=failure_reason,
                timing={"totalMs": total_elapsed_ms, "retrievalMs": retrieval_elapsed_ms, "llmMs": llm_elapsed_ms},
            )
        log_activity(
            "chat.reply",
            "chat_thread",
            thread_id,
            {
                "clientId": client_id,
                "prompt": prompt,
                "coverage": retrieval_bundle.coverage,
                "citationCount": len(retrieval_bundle.citations),
                "answerMode": answer_mode,
            },
        )
        # Keep memory extraction best-effort and off the critical path so state-first
        # answers stay fast even when the secondary extraction model is slow.
        try:
            _schedule_chat_fact_extraction(
                state,
                client_id=client_id,
                thread_id=thread_id,
                user_prompt=prompt,
                assistant_content=structured.content,
                answer_mode=answer_mode,
            )
        except Exception:
            logger.warning("[chat-fact-extract] Failed to queue background extraction", exc_info=True)
        row = state.db.fetchone("SELECT * FROM chat_messages WHERE id = ?", (assistant_id,))
        assert row is not None
        return build_chat_message(row)

    def background_resolve_chat_answer(client_id: str, thread_id: str, prompt: str, assistant_id: str, search_id: str | None, request_started: float, run_id: str | None = None) -> None:
        try:
            resolve_chat_answer(client_id, thread_id, prompt, assistant_id, search_id, request_started, run_id)
        except Exception as error:
            if is_client_analysis_run_canceled(run_id):
                return
            timestamp = now_iso()
            current_row = state.db.fetchone("SELECT retrieval_summary_json FROM chat_messages WHERE id = ?", (assistant_id,))
            existing_summary = from_json(str(current_row["retrieval_summary_json"] or "{}"), {}) if current_row else {}
            if not isinstance(existing_summary, dict):
                existing_summary = {}
            existing_summary.update(
                {
                    "phase": "failed",
                    "progress": 100.0,
                    "progressFloor": 100.0,
                    "progressCeiling": 100.0,
                    "stageLabel": "回答生成失败",
                    "failureReason": str(error),
                    "lastUpdatedAt": timestamp,
                }
            )
            state.db.execute(
                """
                UPDATE chat_messages
                SET content = ?, structured_data_json = ?, model_route = ?, llm_invoked = 0, provider_used = NULL,
                    answer_mode = 'system_failure', evidence_status = 'none', failure_reason = ?, timing_json = ?,
                    retrieval_summary_json = ?, evidence_json = '[]', status = 'success', created_at = ?
                WHERE id = ?
                """,
                (
                    "庆华暂时没能完成这次回答。",
                    to_json(
                        AiStructuredResponse(
                            content="庆华暂时没能完成这次回答。",
                            judgment="模型调用失败，本次回答未成功生成。",
                            analysis=f"错误信息：{str(error)}",
                            actions="建议稍后重试；如果持续失败，请检查本地后端与 AI 配置。",
                            timeline="恢复后可立即重新生成。",
                        ).model_dump()
                    ),
                    "AI 调用失败",
                    str(error),
                    to_json({"totalMs": round((perf_counter() - request_started) * 1000, 2), "retrievalMs": 0.0, "llmMs": 0.0}),
                    to_json(existing_summary),
                    timestamp,
                    assistant_id,
                ),
            )
            if run_id:
                update_client_analysis_run(
                    run_id,
                    status="failed",
                    phase="failed",
                    progress=100.0,
                    progress_floor=100.0,
                    progress_ceiling=100.0,
                    stage_label="回答生成失败",
                    failure_reason=str(error),
                    long_answer_status="failed",
                    summary_status="failed",
                    elapsed_ms=round((perf_counter() - request_started) * 1000, 2),
                    timing={"totalMs": round((perf_counter() - request_started) * 1000, 2), "retrievalMs": 0.0, "llmMs": 0.0},
                )

    @app.get("/api/v1/clients/{client_id}/page-context", response_model=PageContextPackRecord)
    def get_client_page_context(
        client_id: str,
        page: Literal["client_workspace", "workspace_chat"] = Query(default="client_workspace"),
        prompt: str = Query(default=""),
        includeRawEvidence: bool = Query(default=False),
    ) -> PageContextPackRecord:
        workspace_snapshot = workspace_for_client(client_id)
        intent = infer_page_intent(prompt, page)
        return build_client_page_context_pack(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
            prompt=prompt,
            page=page,
            intent=intent,
            include_raw_evidence=bool(includeRawEvidence or intent.requiresRawEvidence),
            workspace=workspace_snapshot,
        )

    @app.post("/api/v1/clients/{client_id}/workspace/chat/start", response_model=ChatStartResponse)
    def start_chat_message(client_id: str, payload: ChatRequest) -> ChatStartResponse:
        build_client_summary(client_id)
        timestamp = now_iso()
        thread_id = ensure_chat_thread(client_id, payload.threadId, payload.prompt, timestamp)
        user_message_id = insert_user_chat_message(thread_id, payload.prompt, timestamp)
        retrieval_summary: dict[str, object] = {}
        if payload.searchId:
            bundle, _ = load_cached_retrieval_bundle(client_id, payload.searchId, payload.prompt)
            if bundle and isinstance(bundle.retrieval_summary, dict):
                retrieval_summary = {
                    **bundle.retrieval_summary,
                    "searchId": payload.searchId,
                }
        assistant_id = insert_loading_assistant_message(thread_id, retrieval_summary, timestamp)
        analysis_run = create_client_analysis_run(client_id, thread_id, user_message_id, assistant_id, payload.prompt, timestamp)
        state.db.execute("UPDATE chat_threads SET updated_at = ? WHERE id = ?", (timestamp, thread_id))
        user_row = state.db.fetchone("SELECT * FROM chat_messages WHERE id = ?", (user_message_id,))
        assistant_row = state.db.fetchone("SELECT * FROM chat_messages WHERE id = ?", (assistant_id,))
        assert user_row is not None and assistant_row is not None
        if state.chat_answer_executor is None:
            raise HTTPException(status_code=500, detail="聊天执行器不可用")
        state.chat_answer_executor.submit(
            background_resolve_chat_answer,
            client_id,
            thread_id,
            payload.prompt,
            assistant_id,
            payload.searchId,
            perf_counter(),
            analysis_run.id,
        )
        return ChatStartResponse(
            threadId=thread_id,
            userMessage=build_chat_message(user_row),
            assistantMessage=build_chat_message(assistant_row),
            analysisRun=analysis_run,
        )

    @app.get("/api/v1/clients/{client_id}/analysis-runs/{run_id}", response_model=ClientAnalysisRunRecord)
    def get_client_analysis_run(client_id: str, run_id: str) -> ClientAnalysisRunRecord:
        build_client_summary(client_id)
        recover_stale_loading_chat_messages()
        return fetch_analysis_run_for_client(client_id, run_id)

    @app.post("/api/v1/clients/{client_id}/analysis-runs/{run_id}/cancel", response_model=ClientAnalysisRunRecord)
    def cancel_client_analysis_run(client_id: str, run_id: str) -> ClientAnalysisRunRecord:
        build_client_summary(client_id)
        return cancel_analysis_run_for_client(client_id, run_id)

    @app.get("/api/v1/clients/{client_id}/workspace/chat/messages/{message_id}", response_model=ChatMessageRecord)
    def get_chat_message(client_id: str, message_id: str) -> ChatMessageRecord:
        recover_stale_loading_chat_messages()
        return fetch_chat_message_for_client(client_id, message_id)

    @app.get("/api/v1/clients/{client_id}/workspace/chat/threads/{thread_id}", response_model=ChatThreadDetailResponse)
    def get_chat_thread_detail(client_id: str, thread_id: str) -> ChatThreadDetailResponse:
        build_client_summary(client_id)
        return ChatThreadDetailResponse(
            thread=fetch_chat_thread_for_client(client_id, thread_id),
            messages=list_chat_messages_for_thread(client_id, thread_id),
        )

    @app.post("/api/v1/clients/{client_id}/workspace/chat", response_model=ChatMessageRecord)
    def send_chat_message(client_id: str, payload: ChatRequest) -> ChatMessageRecord:
        build_client_summary(client_id)
        timestamp = now_iso()
        thread_id = ensure_chat_thread(client_id, payload.threadId, payload.prompt, timestamp)
        insert_user_chat_message(thread_id, payload.prompt, timestamp)
        assistant_id = insert_loading_assistant_message(thread_id, {}, timestamp)
        return resolve_chat_answer(client_id, thread_id, payload.prompt, assistant_id, payload.searchId, perf_counter())

    @app.post("/api/v1/clients/{client_id}/knowledge/vectorize-answer", response_model=ClientTextDocumentResponse)
    def vectorize_answer(client_id: str, payload: VectorizeAnswerPayload) -> ClientTextDocumentResponse:
        build_client_summary(client_id)
        message = fetch_chat_message_for_client(client_id, payload.messageId)
        timestamp = now_iso()
        memory = create_memory_surrogate_from_answer(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
            title=f"{build_client_summary(client_id).name} · 战略陪伴记忆",
            content=message.content,
            actions=message.structuredData.actions if message.structuredData else "",
            analysis=message.structuredData.analysis if message.structuredData else "",
            source_links=[
                {
                    "title": item.title,
                    "documentId": item.documentId,
                    "path": item.path,
                    "sectionLabel": item.sectionLabel,
                }
                for item in message.evidence
            ],
            created_at=timestamp,
            ai_service=state.ai,
        )
        generated = create_answer_memory_markdown_document(client_id, message)
        log_activity(
            "knowledge.vectorize_answer",
            "knowledge_memory",
            str(memory["id"]),
            {
                "clientId": client_id,
                "messageId": payload.messageId,
                "documentId": generated.documentId,
                "path": generated.path,
            },
        )
        return generated

    @app.post("/api/v1/clients/{client_id}/knowledge/enrich-surrogates")
    def enrich_surrogates(client_id: str) -> dict:
        """Batch-enrich all document surrogates for a client with AI-generated retrieval summaries."""
        result = batch_enrich_surrogates(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
            ai_service=state.ai,
        )
        log_activity(
            "knowledge.enrich_surrogates",
            "client",
            client_id,
            result,
        )
        return result

    @app.post("/api/v1/clients/{client_id}/knowledge/build-profile")
    def build_profile(client_id: str) -> dict:
        """Generate adaptive client profile blocks based on the client's actual data."""
        result = build_client_profile(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
            ai_service=state.ai,
        )
        log_activity(
            "knowledge.build_profile",
            "client",
            client_id,
            {"generated_count": len(result.get("generated", [])), "clientName": result.get("clientName")},
        )
        # Auto-sync to cloud ChromaDB
        try:
            from app.services.client_profile import _sync_to_cloud
            _sync_to_cloud(state.db, client_id)
        except Exception:
            pass
        return result

    @app.post("/api/v1/clients/{client_id}/knowledge/sync-to-cloud")
    def sync_to_cloud(client_id: str) -> dict:
        """Sync desktop surrogates and profile blocks to cloud ChromaDB for mobile access."""
        try:
            from app.services.client_profile import _sync_to_cloud
            return _sync_to_cloud(state.db, client_id)
        except Exception as exc:
            return {"error": str(exc)}

    @app.post("/api/v1/knowledge/backfill-all-clients")
    def backfill_all(client_id: str = "") -> dict:
        """One-time backfill: enrich surrogates + build profile blocks for all clients with existing data."""
        result = backfill_all_clients(
            state.db,
            data_dir=state.data_dir,
            ai_service=state.ai,
        )
        log_activity(
            "knowledge.backfill_all_clients",
            "system",
            "all",
            {"totalProcessed": result.get("totalProcessed", 0)},
        )
        return result

    @app.post("/api/v1/clients/{client_id}/knowledge/export-answer", response_model=ClientTextDocumentResponse)
    def export_answer(client_id: str, payload: ExportAnswerPayload) -> ClientTextDocumentResponse:
        build_client_summary(client_id)
        message = fetch_chat_message_for_client(client_id, payload.messageId)
        exported = create_answer_export_document(client_id, message)
        log_activity(
            "knowledge.export_answer",
            "document",
            exported.documentId,
            {"clientId": client_id, "messageId": payload.messageId, "path": exported.path},
        )
        return exported

    @app.post("/api/v1/clients/{client_id}/documents/from-text", response_model=ClientTextDocumentResponse)
    def create_client_document_from_text(client_id: str, payload: ClientTextDocumentPayload) -> ClientTextDocumentResponse:
        return create_client_text_document(client_id, payload)

    @app.post("/api/v1/clients/{client_id}/documents/fill-template", response_model=ClientTemplateFillResponse)
    def fill_client_template(client_id: str, payload: ClientTemplateFillPayload) -> ClientTemplateFillResponse:
        build_client_summary(client_id)
        return fill_client_template_docx(client_id, payload.templatePath)

    @app.post("/api/v1/clients/{client_id}/documents/fill-template/start", response_model=ClientTemplateFillRunRecord)
    def start_client_template_fill(client_id: str, payload: ClientTemplateFillPayload) -> ClientTemplateFillRunRecord:
        build_client_summary(client_id)
        expire_stuck_template_fill_runs()
        active_run = fetch_active_client_template_fill_run(client_id, template_path_raw=payload.templatePath)
        if active_run:
            return active_run
        other_active_run = fetch_active_client_template_fill_run(client_id)
        if other_active_run:
            raise HTTPException(
                status_code=409,
                detail=f"已有模板填写任务正在运行：{other_active_run.templateName}。请等待完成后再发起新的模板填写。",
            )
        run = create_client_template_fill_run(client_id, payload.templatePath)
        if state.template_fill_executor is None:
            raise HTTPException(status_code=503, detail="模板填写执行器不可用。")
        state.template_fill_executor.submit(run_client_template_fill, client_id, run.id, payload.templatePath)
        return fetch_client_template_fill_run(client_id, run.id)

    @app.get("/api/v1/clients/{client_id}/template-fill-runs/{run_id}", response_model=ClientTemplateFillRunRecord)
    def get_client_template_fill_run(client_id: str, run_id: str) -> ClientTemplateFillRunRecord:
        build_client_summary(client_id)
        expire_stuck_template_fill_runs()
        return fetch_client_template_fill_run(client_id, run_id)

    @app.post("/api/v1/clients/{client_id}/workspace/backfill-imports", response_model=WorkspaceImportBackfillResponse)
    def backfill_client_workspace_imports(client_id: str) -> WorkspaceImportBackfillResponse:
        build_client_summary(client_id)
        summary = backfill_workspace_import(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
        )
        log_activity("knowledge.backfill_workspace_import", "client", client_id, summary)
        return WorkspaceImportBackfillResponse(**summary)

    @app.get("/api/v1/clients/{client_id}/meetings", response_model=list[MeetingSummary])
    def list_meetings(client_id: str) -> list[MeetingSummary]:
        build_client_summary(client_id)
        return [
            build_meeting_summary(row)
            for row in state.db.fetchall("SELECT * FROM meetings WHERE client_id = ? ORDER BY updated_at DESC", (client_id,))
        ]

    @app.post("/api/v1/clients/{client_id}/meetings", response_model=MeetingPipelineResponse)
    def prepare_meeting(client_id: str, payload: MeetingCreatePayload) -> MeetingPipelineResponse:
        build_client_summary(client_id)
        meeting_id = new_id("meeting")
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO meetings(id, client_id, title, stage, scheduled_at, transcript_text, notes, created_at, updated_at)
            VALUES(?, ?, ?, 'prepared', ?, '', '', ?, ?)
            """,
            (meeting_id, client_id, payload.title, payload.scheduledAt, timestamp, timestamp),
        )
        agenda_source = workspace_for_client(client_id).goals[:2] or [GoalRecord(id="seed", clientId=client_id, title="明确本周推进重点", quarter="本季度", progress=0, ownerName=current_operator_row()["name"])]
        for index, goal in enumerate(agenda_source):
            state.db.execute(
                "INSERT INTO agenda_items(id, meeting_id, title, description, sort_order) VALUES(?, ?, ?, ?, ?)",
                (new_id("agenda"), meeting_id, goal.title, "会前准备议题", index),
            )
        log_activity("meeting.prepare", "meeting", meeting_id, {"title": payload.title})
        return MeetingPipelineResponse(meeting=build_meeting_detail(meeting_id), message="会议已准备，可继续入库会议原文。")

    @app.post("/api/v1/clients/{client_id}/meetings/launch-feishu", response_model=FeishuMeetingLaunchResponse)
    def launch_feishu_meeting(client_id: str, payload: FeishuMeetingLaunchPayload) -> FeishuMeetingLaunchResponse:
        prepared = prepare_meeting(client_id, MeetingCreatePayload(title=payload.title, scheduledAt=payload.scheduledAt))
        client_summary = build_client_summary(client_id)
        scheduled_label = payload.scheduledAt or "待补充"
        command_hint = f"纪要回写 {prepared.meeting.id}\\n请把会议纪要正文粘贴在第二行开始。"
        notice_text = (
            f"【会议草稿】{prepared.meeting.title}\n"
            f"客户/项目：{client_summary.name}\n"
            f"计划时间：{scheduled_label}\n"
            f"会议编号：{prepared.meeting.id}\n\n"
            f"纪要回写格式：\n{command_hint}"
        )
        delivery_status: Literal["sent", "skipped", "failed"] = "skipped"
        delivery_message = "已创建会议草稿，但尚未发送到飞书。"
        delivery_mode: Literal["bound_user", "configured_receiver", "none"] = "none"
        delivery_target: str | None = None
        receive_id_type, receive_id = None, None
        delivery_mode, receive_id_type, receive_id, delivery_target = _resolve_feishu_meeting_delivery()
        if receive_id_type and receive_id:
            try:
                _send_feishu_text_message(receive_id_type, receive_id, notice_text)
                delivery_status = "sent"
                if delivery_mode == "bound_user":
                    delivery_message = "已创建会议草稿，并按当前登录员工绑定的飞书账号发送会议通知。"
                else:
                    delivery_message = "已创建会议草稿，并把纪要回写指令发送到飞书。"
                log_activity("feishu.meeting.launch", "meeting", prepared.meeting.id, {"clientId": client_id, "sourceTaskId": payload.sourceTaskId, "deliveryMode": delivery_mode, "deliveryTarget": delivery_target})
            except FeishuApiError as exc:
                delivery_status = "failed"
                delivery_message = f"会议草稿已创建，但飞书发送失败：{exc}"
                log_activity("feishu.meeting.launch_failed", "meeting", prepared.meeting.id, {"clientId": client_id, "sourceTaskId": payload.sourceTaskId, "deliveryMode": delivery_mode, "deliveryTarget": delivery_target, "error": str(exc)})
        else:
            delivery_message = "会议草稿已创建，但当前登录员工还没有绑定飞书账号，且全局飞书接收方也未配置完整；请先完成飞书绑定或补齐 App ID、Secret 和接收方。"
        return FeishuMeetingLaunchResponse(
            meeting=prepared.meeting,
            deliveryStatus=delivery_status,
            deliveryMessage=delivery_message,
            commandHint=command_hint,
            noticeText=notice_text,
            deliveryMode=delivery_mode,
            deliveryTarget=delivery_target,
        )

    # ── 飞书同步引擎 ──────────────────────────────────────────

    from app.services.feishu_sync import (
        FeishuSyncState,
        list_minutes,
        get_minute_detail,
        get_minute_transcript,
        parse_minute_to_meeting_notes,
        create_task as feishu_create_task,
        send_interactive_card,
        build_weekly_review_card,
        build_badge_unlock_card,
        build_task_overdue_card,
    )

    _feishu_sync: FeishuSyncState | None = None

    def _get_feishu_sync() -> FeishuSyncState:
        nonlocal _feishu_sync
        if _feishu_sync is None:
            _feishu_sync = FeishuSyncState(state.db, state.feishu_secret_store)
        return _feishu_sync

    @app.get("/api/v1/feishu/status")
    def feishu_sync_status() -> dict:
        sync = _get_feishu_sync()
        configured = sync.is_configured()
        user_id, _ = resolve_growth_actor()
        binding = sync.get_user_binding(user_id)
        return {
            "configured": configured,
            "userBound": binding is not None,
            "userName": binding.get("name") if binding else None,
            "modules": {"minutes": configured, "tasks": configured, "calendar": configured, "messages": configured},
        }

    @app.get("/api/v1/feishu/minutes")
    def feishu_list_minutes(days: int = 30) -> dict:
        sync = _get_feishu_sync()
        user_id, _ = resolve_growth_actor()
        binding = sync.get_user_binding(user_id)
        if not binding:
            raise HTTPException(status_code=400, detail="请先绑定飞书账号")
        token = (binding.get("accessToken") or binding.get("access_token")) or sync.get_tenant_token()
        import time as _time
        end_t = int(_time.time())
        start_t = end_t - days * 86400
        try:
            result = list_minutes(user_access_token=token, start_time=start_t, end_time=end_t)
            items = result.get("data", {}).get("minutes") or result.get("data", {}).get("items") or []
            return {"minutes": items, "total": len(items)}
        except Exception as exc:
            return {"minutes": [], "total": 0, "error": str(exc), "hint": "妙记 API 需要用户身份 token，请确认飞书授权了妙记权限"}

    @app.post("/api/v1/feishu/minutes/{minute_token}/import")
    def feishu_import_minute(minute_token: str, client_id: str = "") -> dict:
        sync = _get_feishu_sync()
        user_id, user_name = resolve_growth_actor()
        binding = sync.get_user_binding(user_id)
        token = (binding or {}).get("accessToken") or (binding or {}).get("access_token") or sync.get_tenant_token()
        detail = get_minute_detail(user_access_token=token, minute_token=minute_token)
        paragraphs = get_minute_transcript(user_access_token=token, minute_token=minute_token)
        parsed = parse_minute_to_meeting_notes(detail, paragraphs)
        meeting_id = new_id("meeting")
        state.db.execute(
            "INSERT INTO meetings(id, client_id, title, transcript_text, notes, stage, source_type, source_id, created_at, updated_at) VALUES(?,?,?,?,?,'ingested','feishu_minutes',?,?,?)",
            (meeting_id, client_id or None, parsed["title"], parsed["transcript"], parsed["aiSummary"], minute_token, now_iso(), now_iso()),
        )
        created_tasks: list[str] = []
        for todo in parsed.get("aiTodoItems", []):
            content = todo.get("content", "").strip()
            if content:
                task_id = new_id("task")
                state.db.execute(
                    "INSERT INTO tasks(id, title, status, priority, list_id, source_type, source_id, owner_name, created_at, updated_at) VALUES(?,?,'todo','normal',?,'meeting',?,?,?,?)",
                    (task_id, content, _default_task_list_id(), meeting_id, todo.get("owner", user_name), now_iso(), now_iso()),
                )
                created_tasks.append(content)
        log_activity("feishu.minutes.import", "meeting", meeting_id, {"minuteToken": minute_token, "title": parsed["title"], "taskCount": len(created_tasks)})
        return {"meetingId": meeting_id, "title": parsed["title"], "speakers": parsed["speakers"], "transcriptLength": len(parsed["transcript"]), "createdTasks": created_tasks}

    @app.post("/api/v1/feishu/tasks/push")
    def feishu_push_task(task_id: str = "") -> dict:
        sync = _get_feishu_sync()
        if not sync.is_configured():
            raise HTTPException(status_code=400, detail="飞书应用未配置，请先设置 App ID 和 App Secret")
        token = sync.get_tenant_token()
        row = state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not row:
            raise HTTPException(status_code=404, detail="任务不存在")
        title = str(row["title"] or "")
        due_date = str(row["due_date"] or "")
        due_ts = None
        if due_date:
            try:
                due_ts = int(datetime.fromisoformat(due_date.replace("Z", "+00:00")).timestamp())
            except Exception:
                pass
        result = feishu_create_task(tenant_access_token=token, summary=title, description=str(row["description"] or ""), due_timestamp=due_ts)
        feishu_task = result.get("data", {}).get("task", {})
        feishu_guid = str(feishu_task.get("guid") or feishu_task.get("id") or "")
        if feishu_guid:
            state.db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (f"feishu_task_link:{task_id}", feishu_guid))
            state.db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (f"feishu_task_reverse:{feishu_guid}", task_id))
        log_activity("feishu.task.push", "task", task_id, {"feishuGuid": feishu_guid})
        return {"taskId": task_id, "feishuGuid": feishu_guid, "title": title}

    @app.post("/api/v1/feishu/notify/weekly-review")
    def feishu_notify_weekly_review(week_label: str = "") -> dict:
        sync = _get_feishu_sync()
        if not sync.is_configured():
            raise HTTPException(status_code=400, detail="飞书应用未配置")
        token = sync.get_tenant_token()
        receive_id_type, receive_id = sync.get_receiver_config()
        if not receive_id:
            raise HTTPException(status_code=400, detail="飞书接收方未配置")
        row = state.db.fetchone("SELECT * FROM weekly_reviews WHERE week_label = ? ORDER BY updated_at DESC LIMIT 1", (week_label,))
        if not row:
            raise HTTPException(status_code=404, detail="未找到该周复盘")
        summary = str(row["summary"] or row["work_free_note"] or "")
        card = build_weekly_review_card(week_label=week_label, headline=summary[:100] or "本周复盘", highlights=[l.strip() for l in summary.split("\n") if l.strip()][:3], blockers=[], next_focus="")
        send_interactive_card(tenant_access_token=token, receive_id_type=receive_id_type, receive_id=receive_id, card=card)
        return {"sent": True, "weekLabel": week_label}

    @app.post("/api/v1/feishu/notify/badge-unlock")
    def feishu_notify_badge(badge_name: str, badge_desc: str = "", category: str = "", xp: int = 0) -> dict:
        sync = _get_feishu_sync()
        if not sync.is_configured():
            raise HTTPException(status_code=400, detail="飞书应用未配置")
        token = sync.get_tenant_token()
        receive_id_type, receive_id = sync.get_receiver_config()
        if not receive_id:
            raise HTTPException(status_code=400, detail="飞书接收方未配置")
        _, user_name = resolve_growth_actor()
        card = build_badge_unlock_card(badge_name=badge_name, badge_description=badge_desc, category_name=category, xp=xp, user_name=user_name)
        send_interactive_card(tenant_access_token=token, receive_id_type=receive_id_type, receive_id=receive_id, card=card)
        return {"sent": True, "badgeName": badge_name}

    @app.get("/api/v1/clients/{client_id}/meetings/{meeting_id}", response_model=MeetingDetail)
    def get_meeting_detail(client_id: str, meeting_id: str) -> MeetingDetail:
        meeting = build_meeting_detail(meeting_id)
        if meeting.clientId != client_id:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return meeting

    @app.post("/api/v1/clients/{client_id}/meetings/{meeting_id}/proposals/prepare", response_model=ProposalRecordRecord)
    def create_meeting_prepare_proposal(client_id: str, meeting_id: str) -> ProposalRecordRecord:
        meeting = build_meeting_detail(meeting_id)
        if meeting.clientId != client_id:
            raise HTTPException(status_code=404, detail="Meeting not found")
        workspace = workspace_for_client(client_id)
        state_pack = build_state_answer_context_pack(workspace, f"为会议 {meeting.title} 生成会前 proposal")
        approved_judgments, candidate_judgments = _workspace_state_judgments(workspace)
        open_questions = [
            _workspace_state_compact(item.question + (f"；{item.reason}" if item.reason else ""), limit=120)
            for item in workspace.latestOpenQuestions[:4]
        ]
        risks = [
            _workspace_state_compact(item.title + "：" + item.summary, limit=120)
            for item in workspace.latestConflicts[:3]
        ]
        summary_parts = [
            f"会前 proposal 针对《{meeting.title}》生成。",
            f"当前正式判断：{approved_judgments[0].topic}" if approved_judgments else "",
            f"优先待确认：{candidate_judgments[0].topic}" if candidate_judgments else "",
            f"需要先问清的问题：{open_questions[0]}" if open_questions else "",
        ]
        summary = " ".join(part for part in summary_parts if part).strip() or state_pack.summary
        return _insert_proposal_record(
            client_id=client_id,
            kind="meeting_prep",
            title=f"会前准备 · {meeting.title}",
            summary=summary[:900],
            rationale="只读取客户工作台中的 official / radar / open question / 缺资料信号，为会议准备边界清晰的会前 proposal。",
            target_refs=[
                ProposalTargetRefRecord(targetType="client", targetId=client_id, label=workspace.client.name),
                ProposalTargetRefRecord(targetType="meeting", targetId=meeting.id, label=meeting.title),
            ],
            source_refs=list(dict.fromkeys(state_pack.stateSources or ["judgment", "meeting", "open_question"])),
            boundary_notes=list(dict.fromkeys([
                *state_pack.boundaryNotes,
                "会前 proposal 只生成准备建议，不直接写任务或 official judgment。",
            ]))[:6],
            payload={
                "meetingId": meeting.id,
                "meetingTitle": meeting.title,
                "approvedJudgments": [item.model_dump() for item in approved_judgments[:3]],
                "candidateJudgments": [item.model_dump() for item in candidate_judgments[:3]],
                "openQuestions": open_questions,
                "risks": risks,
                "stateSummary": state_pack.summary,
            },
            risk_level="medium" if risks else "low",
        )

    @app.post("/api/v1/clients/{client_id}/meetings/{meeting_id}/proposals/follow-up", response_model=ProposalRecordRecord)
    def create_meeting_followup_proposal(client_id: str, meeting_id: str) -> ProposalRecordRecord:
        meeting = build_meeting_detail(meeting_id)
        if meeting.clientId != client_id:
            raise HTTPException(status_code=404, detail="Meeting not found")
        if meeting.stage not in {"resolved", "published"}:
            raise HTTPException(status_code=400, detail="只有 resolved/published meeting 才能生成会后 follow-up proposal")
        action_payload = [
            {
                "title": item.title,
                "ownerName": item.ownerName,
                "dueDate": item.ddl or item.dueDate or "本周",
                "summary": item.desc or item.note or "来自 resolved meeting 的 action item",
            }
            for item in meeting.actionItems[:8]
            if item.title.strip()
        ]
        if not action_payload and not meeting.decisions and not meeting.risks:
            raise HTTPException(status_code=400, detail="该会议还没有可用于 follow-up proposal 的结构化结果")
        decision_lines = [_workspace_state_compact(item.summary, limit=120) for item in meeting.decisions[:3]]
        risk_lines = [_workspace_state_compact(item.summary, limit=120) for item in meeting.risks[:3]]
        summary_parts = [
            f"会后 follow-up proposal 针对《{meeting.title}》生成。",
            f"关键决议：{decision_lines[0]}" if decision_lines else "",
            f"待执行动作 {len(action_payload)} 条" if action_payload else "",
            f"风险提醒：{risk_lines[0]}" if risk_lines else "",
        ]
        payload_base = {
            "meetingId": meeting.id,
            "meetingTitle": meeting.title,
            "decisions": decision_lines,
            "actionItems": action_payload,
            "risks": risk_lines,
        }
        payload_hash = _proposal_payload_hash(payload_base)
        existing = _find_existing_meeting_proposal(
            client_id=client_id,
            meeting_id=meeting.id,
            kind="meeting_followup",
            payload_hash=payload_hash,
        )
        if existing:
            return existing
        return _insert_proposal_record(
            client_id=client_id,
            kind="meeting_followup",
            title=f"会后跟进 · {meeting.title}",
            summary=" ".join(part for part in summary_parts if part).strip()[:900],
            rationale="会后 proposal 只从 resolved meeting 的 decisions / action items / risks 派生，待人工批准后再生成 execution ticket。",
            target_refs=[
                ProposalTargetRefRecord(targetType="client", targetId=client_id, label=build_client_summary(client_id).name),
                ProposalTargetRefRecord(targetType="meeting", targetId=meeting.id, label=meeting.title),
            ],
            source_refs=["meeting", "decision", "action_item", "risk"],
            boundary_notes=[
                "会后 proposal 不直接写任务或 official judgment，必须先审批再执行。",
                "如果 action item 缺 owner/due date，执行阶段只会生成最小可追踪任务。",
            ],
            payload={
                **payload_base,
                "payloadHash": payload_hash,
            },
            risk_level="high" if risk_lines else "medium",
        )

    @app.post("/api/v1/clients/{client_id}/meetings/{meeting_id}/ingest", response_model=MeetingPipelineResponse)
    def ingest_meeting(client_id: str, meeting_id: str, payload: MeetingIngestPayload) -> MeetingPipelineResponse:
        meeting = build_meeting_detail(meeting_id)
        if meeting.clientId != client_id:
            raise HTTPException(status_code=404, detail="Meeting not found")
        state.db.execute(
            "UPDATE meetings SET transcript_text = ?, notes = ?, stage = 'ingested', updated_at = ? WHERE id = ?",
            (payload.transcriptText, payload.notes, now_iso(), meeting_id),
        )
        state.db.execute("DELETE FROM meeting_sources WHERE meeting_id = ?", (meeting_id,))
        source_text = payload.transcriptText or payload.notes
        if source_text:
            state.db.execute(
                "INSERT INTO meeting_sources(id, meeting_id, title, content_text, created_at) VALUES(?, ?, ?, ?, ?)",
                (new_id("ms"), meeting_id, "会议原文", source_text, now_iso()),
            )
        log_activity("meeting.ingest", "meeting", meeting_id, {"transcriptLength": len(payload.transcriptText), "notesLength": len(payload.notes)})
        return MeetingPipelineResponse(meeting=build_meeting_detail(meeting_id), message="会议原文已入库，可继续抽取。")

    @app.post("/api/v1/clients/{client_id}/meetings/{meeting_id}/extract", response_model=MeetingPipelineResponse)
    def extract_meeting(client_id: str, meeting_id: str) -> MeetingPipelineResponse:
        meeting = build_meeting_detail(meeting_id)
        if meeting.clientId != client_id:
            raise HTTPException(status_code=404, detail="Meeting not found")
        text = f"{meeting.transcriptText}\n{meeting.notes}".strip()
        agenda, decisions, actions, risks, ambiguities = extract_meeting_content(text)
        state.db.execute("DELETE FROM agenda_items WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("DELETE FROM decisions WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("DELETE FROM action_items WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("DELETE FROM risks WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("DELETE FROM ambiguities WHERE meeting_id = ?", (meeting_id,))
        for index, item in enumerate(agenda):
            state.db.execute("INSERT INTO agenda_items(id, meeting_id, title, description, sort_order) VALUES(?, ?, ?, ?, ?)", (new_id("agenda"), meeting_id, item[:28], "抽取后的议程点", index))
        for item in decisions:
            state.db.execute("INSERT INTO decisions(id, meeting_id, summary, created_at) VALUES(?, ?, ?, ?)", (new_id("dec"), meeting_id, item[:120], now_iso()))
        for item, owner, confidence in actions:
            state.db.execute(
                "INSERT INTO action_items(id, meeting_id, title, owner_name, due_date, confidence, publish_status, created_at) VALUES(?, ?, ?, ?, ?, ?, 'draft', ?)",
                (new_id("act"), meeting_id, item[:120], owner, "本周", confidence, now_iso()),
            )
        for item, severity in risks:
            state.db.execute("INSERT INTO risks(id, meeting_id, summary, severity, created_at) VALUES(?, ?, ?, ?, ?)", (new_id("risk"), meeting_id, item[:120], severity, now_iso()))
        for item, candidates in ambiguities:
            state.db.execute(
                "INSERT INTO ambiguities(id, meeting_id, raw_text, candidates_json, status, created_at) VALUES(?, ?, ?, ?, 'pending', ?)",
                (new_id("amb"), meeting_id, item[:120], to_json(candidates), now_iso()),
            )
        state.db.execute("UPDATE meetings SET stage = 'extracted', updated_at = ? WHERE id = ?", (now_iso(), meeting_id))
        log_activity("meeting.extract", "meeting", meeting_id, {"decisions": len(decisions), "actions": len(actions), "risks": len(risks)})
        return MeetingPipelineResponse(meeting=build_meeting_detail(meeting_id), message="结构化抽取完成，下一步可消歧。")

    @app.post("/api/v1/clients/{client_id}/meetings/{meeting_id}/resolve", response_model=MeetingPipelineResponse)
    def resolve_meeting(client_id: str, meeting_id: str) -> MeetingPipelineResponse:
        meeting = build_meeting_detail(meeting_id)
        if meeting.clientId != client_id:
            raise HTTPException(status_code=404, detail="Meeting not found")
        state.db.execute("UPDATE ambiguities SET status = 'resolved' WHERE meeting_id = ?", (meeting_id,))
        state.db.execute("UPDATE meetings SET stage = 'resolved', updated_at = ? WHERE id = ?", (now_iso(), meeting_id))
        log_activity("meeting.resolve", "meeting", meeting_id, {})
        return MeetingPipelineResponse(meeting=build_meeting_detail(meeting_id), message="低置信点已标记处理，可正式发布行动项。")

    @app.post("/api/v1/clients/{client_id}/meetings/{meeting_id}/publish", response_model=MeetingPipelineResponse)
    def publish_meeting(client_id: str, meeting_id: str) -> MeetingPipelineResponse:
        meeting = build_meeting_detail(meeting_id)
        if meeting.clientId != client_id:
            raise HTTPException(status_code=404, detail="Meeting not found")
        workspace_settings = get_client_workspace_settings()
        default_list_id = workspace_settings.meetingPublishDefaultListId or _get_local_task_settings().defaultListId or "list-0"
        for item in state.db.fetchall("SELECT * FROM action_items WHERE meeting_id = ? AND publish_status != 'published'", (meeting_id,)):
            payload = TaskPayload(
                title=str(item["title"]),
                desc="来自会议发布的行动项",
                priority=workspace_settings.meetingPublishDefaultPriority,
                listId=default_list_id,
                ddl=str(item["due_date"]),
                ownerName=str(item["owner_name"]),
                tags=["会议"],
                sourceType="meeting",
                sourceId=meeting_id,
            )
            create_task(payload, status="inbox")
            state.db.execute("UPDATE action_items SET publish_status = 'published' WHERE id = ?", (str(item["id"]),))
        for decision in state.db.fetchall("SELECT * FROM decisions WHERE meeting_id = ? ORDER BY created_at LIMIT 2", (meeting_id,)):
            state.db.execute(
                "INSERT INTO evidence_refs(id, client_id, meeting_id, document_id, title, excerpt, source_type, path, created_at) VALUES(?, ?, ?, NULL, ?, ?, 'meeting', NULL, ?)",
                (new_id("evr"), client_id, meeting_id, f"会议结论 · {meeting.title}", str(decision["summary"]), now_iso()),
            )
        state.db.execute("UPDATE meetings SET stage = 'published', updated_at = ? WHERE id = ?", (now_iso(), meeting_id))
        strategic_event_line_ids = _strategic_meeting_event_line_ids(client_id, meeting.title, meeting_id=meeting_id)
        record_meeting_publish_writeback(
            state.db,
            client_id=client_id,
            meeting_id=meeting_id,
            meeting_title=meeting.title,
            event_line_ids=strategic_event_line_ids,
        )
        growth_user_id, growth_user_name = resolve_growth_actor()
        ingest_meeting_growth_candidate(
            state.db,
            user_id=growth_user_id,
            user_name=growth_user_name,
            client_id=client_id,
            meeting=meeting,
            event_line_ids=strategic_event_line_ids,
            created_at=now_iso(),
        )
        # Write meeting activity to each related event line
        meeting_ts = now_iso()
        action_count = len([i for i in state.db.fetchall("SELECT id FROM action_items WHERE meeting_id = ? AND publish_status = 'published'", (meeting_id,))])
        decision_rows = state.db.fetchall("SELECT summary FROM decisions WHERE meeting_id = ? ORDER BY created_at LIMIT 3", (meeting_id,))
        decision_summary = "; ".join(str(d["summary"])[:60] for d in decision_rows) if decision_rows else ""
        for el_id in strategic_event_line_ids:
            state.db.execute(
                """
                INSERT INTO event_line_activities(
                    id, event_line_id, source_type, source_id, happened_at, actor_id, actor_name, title, summary, metadata_json, is_key, created_at
                ) VALUES(?, ?, 'meeting', ?, ?, NULL, ?, ?, ?, ?, 1, ?)
                """,
                (
                    new_id("ela"),
                    el_id,
                    meeting_id,
                    meeting_ts,
                    current_operator_name(),
                    f"会议发布：{meeting.title}",
                    f"会议已发布，产生 {action_count} 条行动项。" + (f" 关键决策：{decision_summary}" if decision_summary else ""),
                    to_json({"clientId": client_id, "actionCount": action_count, "meetingTitle": meeting.title}),
                    meeting_ts,
                ),
            )
        log_activity("meeting.publish", "meeting", meeting_id, {"tasksWritten": len(meeting.actionItems)})
        return MeetingPipelineResponse(meeting=build_meeting_detail(meeting_id), message="会议已发布，行动项已写入任务收件箱。")

    @app.get("/api/v1/tasks", response_model=TaskBoardResponse)
    def list_tasks() -> TaskBoardResponse:
        # Opportunistically sync pending tasks when user views task board
        Thread(target=sync_pending_tasks_if_due, daemon=True).start()
        # If cloud user but local DB is empty, pull cloud tasks into local first
        if get_cloud_token():
            _pull_cloud_tasks_to_local()
        # LOCAL IS PRIMARY — always read from local SQLite
        return TaskBoardResponse(
            tasks=fetch_tasks("t.source_type != ?", (AGENT_AUTO_SOURCE_TYPE,)),
            lists=task_lists(),
            tags=task_tags(),
        )

    @app.get("/api/v1/task-lists", response_model=TaskListLibraryResponse)
    def list_task_lists() -> TaskListLibraryResponse:
        if get_cloud_token():
            try:
                payload = cloud_request("GET", "/api/v1/task-lists")
                if isinstance(payload, dict):
                    return TaskListLibraryResponse(lists=[TaskListRecord(**item) for item in payload.get("lists", []) if isinstance(item, dict)])
            except Exception:
                pass  # cloud down — fall back to local
        return TaskListLibraryResponse(lists=task_lists())

    @app.post("/api/v1/task-lists", response_model=TaskListRecord)
    def create_task_list(payload: TaskListMutationPayload) -> TaskListRecord:
        if get_cloud_token():
            try:
                response = cloud_request("POST", "/api/v1/task-lists", json_body=payload.model_dump(exclude_none=True))
                if isinstance(response, dict):
                    return TaskListRecord(**response)
            except Exception:
                pass  # cloud down — create locally
        session_user = get_cached_session_user()
        if session_user and session_user.primaryRole != "admin" and (payload.scope or "org") != "personal":
            raise HTTPException(status_code=403, detail="Only admin can create public task lists")
        trimmed_name = payload.name.strip()
        if not trimmed_name:
            raise HTTPException(status_code=400, detail="清单名称不能为空")
        timestamp = now_iso()
        list_id = new_id("list")
        next_scope = payload.scope or "org"
        is_default = bool(payload.isDefault) or state.db.scalar("SELECT COUNT(1) AS count FROM task_lists WHERE scope = ?", (next_scope,)) == 0
        sort_order = payload.sortOrder if payload.sortOrder is not None else state.db.scalar("SELECT COALESCE(MAX(sort_order), -1) + 1 AS count FROM task_lists")
        if is_default:
            state.db.execute("UPDATE task_lists SET is_default = 0 WHERE scope = ?", (next_scope,))
        state.db.execute(
            """
            INSERT INTO task_lists(id, name, color, sort_order, is_default, scope, archived_at)
            VALUES(?, ?, ?, ?, ?, ?, NULL)
            """,
            (list_id, trimmed_name, payload.color.strip(), sort_order, 1 if is_default else 0, next_scope),
        )
        row = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (list_id,))
        assert row is not None
        log_activity("task-list.create", "task_list", list_id, payload.model_dump(exclude_none=True))
        return _local_task_list_record(row)

    @app.patch("/api/v1/task-lists/{list_id}", response_model=TaskListRecord)
    def update_task_list(list_id: str, payload: TaskListMutationPayload) -> TaskListRecord:
        if get_cloud_token():
            try:
                response = cloud_request("PATCH", f"/api/v1/task-lists/{list_id}", json_body=payload.model_dump(exclude_none=True))
                if isinstance(response, dict):
                    return TaskListRecord(**response)
            except Exception:
                pass  # cloud down — update locally
        session_user = get_cached_session_user()
        if session_user and session_user.primaryRole != "admin":
            row_scope = None
            row = state.db.fetchone("SELECT scope FROM task_lists WHERE id = ?", (list_id,))
            if row:
                row_scope = str(row["scope"] or "org")
            if (payload.scope or row_scope or "org") != "personal":
                raise HTTPException(status_code=403, detail="Only admin can update public task lists")
        row = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (list_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Task list not found")
        trimmed_name = payload.name.strip()
        timestamp = now_iso()
        next_archived_at = str(row["archived_at"]) if row["archived_at"] else None
        next_scope = payload.scope or str(row["scope"] or "org")
        if payload.archived is True:
            active_list_count = state.db.scalar(
                "SELECT COUNT(1) AS count FROM task_lists WHERE scope = ? AND (archived_at IS NULL OR archived_at = '')",
                (next_scope,),
            )
            if active_list_count <= 1 and not row["archived_at"]:
                raise HTTPException(status_code=400, detail="至少保留一个可用清单")
            next_archived_at = timestamp
        elif payload.archived is False:
            next_archived_at = None
        next_is_default = bool(payload.isDefault) if payload.isDefault is not None else bool(int(row["is_default"] or 0))
        if next_archived_at:
            next_is_default = False
        if next_is_default:
            state.db.execute("UPDATE task_lists SET is_default = 0 WHERE scope = ?", (next_scope,))
        state.db.execute(
            """
            UPDATE task_lists
            SET name = ?, color = ?, sort_order = ?, is_default = ?, scope = ?, archived_at = ?
            WHERE id = ?
            """,
            (
                trimmed_name,
                payload.color.strip(),
                payload.sortOrder if payload.sortOrder is not None else int(row["sort_order"] or 0),
                1 if next_is_default else 0,
                next_scope,
                next_archived_at,
                list_id,
            ),
        )
        if not next_is_default and not next_archived_at and state.db.scalar(
            "SELECT COUNT(1) AS count FROM task_lists WHERE scope = ? AND is_default = 1",
            (next_scope,),
        ) == 0:
            state.db.execute(
                "UPDATE task_lists SET is_default = 1 WHERE id = ?",
                (list_id,),
            )
        if next_archived_at and bool(int(row["is_default"] or 0)):
            fallback_row = state.db.fetchone(
                "SELECT id FROM task_lists WHERE scope = ? AND id != ? AND (archived_at IS NULL OR archived_at = '') ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1",
                (next_scope, list_id),
            )
            if fallback_row:
                state.db.execute(
                    "UPDATE task_lists SET is_default = CASE WHEN id = ? THEN 1 ELSE 0 END WHERE scope = ?",
                    (str(fallback_row["id"]), next_scope),
                )
        updated = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (list_id,))
        assert updated is not None
        log_activity("task-list.update", "task_list", list_id, payload.model_dump(exclude_none=True))
        return _local_task_list_record(updated)

    @app.delete("/api/v1/task-lists/{list_id}")
    def delete_task_list(list_id: str) -> dict[str, bool]:
        if get_cloud_token():
            try:
                cloud_request("DELETE", f"/api/v1/task-lists/{list_id}")
                return {"deleted": True}
            except Exception:
                pass  # cloud down — delete locally
        session_user = get_cached_session_user()
        if session_user and session_user.primaryRole != "admin":
            row = state.db.fetchone("SELECT scope FROM task_lists WHERE id = ?", (list_id,))
            if not row or str(row["scope"] or "org") != "personal":
                raise HTTPException(status_code=403, detail="Only admin can delete public task lists")
        row = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (list_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Task list not found")
        task_count = state.db.scalar("SELECT COUNT(1) AS count FROM tasks WHERE list_id = ?", (list_id,))
        if task_count > 0:
            raise HTTPException(status_code=400, detail="该清单已有任务，请先归档，不支持直接删除")
        if state.db.scalar("SELECT COUNT(1) AS count FROM task_lists WHERE scope = ?", (str(row["scope"] or "org"),)) <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个清单")
        if bool(int(row["is_default"] or 0)):
            fallback_row = state.db.fetchone(
                "SELECT id FROM task_lists WHERE scope = ? AND id != ? ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1",
                (str(row["scope"] or "org"), list_id),
            )
            if fallback_row:
                state.db.execute(
                    "UPDATE task_lists SET is_default = CASE WHEN id = ? THEN 1 ELSE 0 END WHERE scope = ?",
                    (str(fallback_row["id"]), str(row["scope"] or "org")),
                )
        state.db.execute("DELETE FROM task_lists WHERE id = ?", (list_id,))
        log_activity("task-list.delete", "task_list", list_id, {})
        return {"deleted": True}

    @app.get("/api/v1/task-tags", response_model=TaskTagLibraryResponse)
    def list_task_tags() -> TaskTagLibraryResponse:
        if get_cloud_token():
            response = cloud_request("GET", "/api/v1/task-tags")
            if isinstance(response, dict):
                return TaskTagLibraryResponse(
                    tags=[build_cloud_task_tag(item) for item in response.get("tags", []) if isinstance(item, dict)]
                )
        operator_row = current_operator_row()
        return TaskTagLibraryResponse(tags=_visible_local_task_tags(state.db, str(operator_row["id"])))

    @app.post("/api/v1/task-tags", response_model=TaskTagRecord)
    def create_task_tag(payload: TaskTagMutationPayload) -> TaskTagRecord:
        if get_cloud_token():
            response = cloud_request("POST", "/api/v1/task-tags", payload.model_dump())
            if isinstance(response, dict):
                return build_cloud_task_tag(response)
        operator_row = current_operator_row()
        return _ensure_local_tag(state.db, str(operator_row["id"]), payload.name, payload.scope, payload.color)

    @app.patch("/api/v1/task-tags/{tag_id}", response_model=TaskTagRecord)
    def update_task_tag(tag_id: str, payload: TaskTagMutationPayload) -> TaskTagRecord:
        if get_cloud_token():
            response = cloud_request("PATCH", f"/api/v1/task-tags/{tag_id}", payload.model_dump())
            if isinstance(response, dict):
                return build_cloud_task_tag(response)
        row = state.db.fetchone("SELECT * FROM task_tags WHERE id = ?", (tag_id,))
        if not row:
            raise HTTPException(status_code=404, detail="标签不存在")
        archived_at = now_iso() if payload.archived else None
        state.db.execute(
            "UPDATE task_tags SET name = ?, color = ?, scope = ?, archived_at = ?, updated_at = ? WHERE id = ?",
            (payload.name, payload.color or str(row["color"]), payload.scope, archived_at, now_iso(), tag_id),
        )
        updated = state.db.fetchone("SELECT * FROM task_tags WHERE id = ?", (tag_id,))
        assert updated is not None
        return _local_task_tag_record(updated)

    @app.delete("/api/v1/task-tags/{tag_id}")
    def delete_task_tag(tag_id: str) -> dict[str, bool]:
        if get_cloud_token():
            try:
                cloud_request("DELETE", f"/api/v1/task-tags/{tag_id}")
                return {"deleted": True}
            except Exception:
                pass  # cloud down — delete locally
        row = state.db.fetchone("SELECT * FROM task_tags WHERE id = ?", (tag_id,))
        if not row:
            raise HTTPException(status_code=404, detail="标签不存在")
        state.db.execute("DELETE FROM task_tags WHERE id = ?", (tag_id,))
        return {"deleted": True}

    @app.post("/api/v1/tasks/refresh-contexts", response_model=TaskContextRefreshResultRecord)
    def refresh_task_contexts() -> TaskContextRefreshResultRecord:
        if get_cloud_token():
            _pull_cloud_tasks_to_local()
        task_records = fetch_tasks()
        clients = [build_client_summary(str(row["id"])) for row in state.db.fetchall("SELECT id FROM clients ORDER BY updated_at DESC")]
        event_lines = list_event_lines()
        project_structures: dict[str, ProjectStructureResponse] = {}
        updated_tasks = 0
        unchanged_tasks = 0
        failed_tasks = 0
        client_updated_tasks = 0
        event_line_updated_tasks = 0
        module_updated_tasks = 0
        flow_updated_tasks = 0
        for task in task_records:
            payload = _build_task_scope_refresh_payload(task, clients, event_lines, project_structures)
            if not payload:
                unchanged_tasks += 1
                continue
            try:
                update_task(task.id, TaskUpdatePayload(**payload))
                updated_tasks += 1
                if "clientId" in payload:
                    client_updated_tasks += 1
                if "eventLineId" in payload:
                    event_line_updated_tasks += 1
                if "projectModuleId" in payload:
                    module_updated_tasks += 1
                if "projectFlowId" in payload:
                    flow_updated_tasks += 1
            except Exception:
                failed_tasks += 1
        unchanged_tasks = max(0, len(task_records) - updated_tasks - failed_tasks)
        backfill_memory_foundation(state.db)
        return TaskContextRefreshResultRecord(
            totalTasks=len(task_records),
            updatedTasks=updated_tasks,
            unchangedTasks=unchanged_tasks,
            failedTasks=failed_tasks,
            clientUpdatedTasks=client_updated_tasks,
            eventLineUpdatedTasks=event_line_updated_tasks,
            moduleUpdatedTasks=module_updated_tasks,
            flowUpdatedTasks=flow_updated_tasks,
            updatedAt=now_iso(),
        )

    @app.post("/api/v1/tasks/bootstrap-event-lines", response_model=TaskEventLineBootstrapResultRecord)
    def bootstrap_task_event_lines() -> TaskEventLineBootstrapResultRecord:
        if get_cloud_token():
            _pull_cloud_tasks_to_local()
        task_records = fetch_tasks()
        existing_event_lines = list_event_lines()
        event_line_by_signature = {
            f"{(item.primaryClientId or '').strip()}::{item.name.strip()}": item
            for item in existing_event_lines
            if item.name.strip()
        }
        created_event_lines = 0
        linked_tasks = 0
        skipped_tasks = 0
        failed_tasks = 0

        for task in task_records:
            if not _task_eligible_for_event_line_bootstrap(task):
                skipped_tasks += 1
                continue
            payload = _build_bootstrap_event_line_payload(task)
            signature = f"{(payload.primaryClientId or '').strip()}::{payload.name.strip()}"
            event_line = event_line_by_signature.get(signature)
            if event_line is None:
                try:
                    event_line = create_event_line(payload)
                    event_line_by_signature[signature] = event_line
                    created_event_lines += 1
                except Exception:
                    failed_tasks += 1
                    continue
            try:
                update_task(task.id, TaskUpdatePayload(eventLineId=event_line.id))
                linked_tasks += 1
            except Exception:
                failed_tasks += 1

        backfill_memory_foundation(state.db)
        return TaskEventLineBootstrapResultRecord(
            totalTasks=len(task_records),
            createdEventLines=created_event_lines,
            linkedTasks=linked_tasks,
            skippedTasks=skipped_tasks,
            failedTasks=failed_tasks,
            updatedAt=now_iso(),
        )

    @app.post("/api/v1/tasks", response_model=TaskRecord)
    def create_manual_task(payload: TaskPayload) -> TaskRecord:
        return create_task(payload)

    @app.patch("/api/v1/tasks/{task_id}", response_model=TaskRecord)
    def update_task(task_id: str, payload: TaskUpdatePayload) -> TaskRecord:
        if not get_cloud_token():
            row = state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            if payload.listId:
                list_row = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (payload.listId,))
                if not list_row or list_row["archived_at"]:
                    raise HTTPException(status_code=400, detail="任务清单无效")
            resolved_tags = normalize_local_task_tags(
                payload.tagIds if payload.tagIds is not None else _parse_json_list(row["tag_ids_json"]),
                payload.tags if payload.tags is not None else None,
            )
            next_client_id = payload.clientId if "clientId" in payload.model_fields_set else (str(row["client_id"]) if row["client_id"] else None)
            next_event_line_id = payload.eventLineId if "eventLineId" in payload.model_fields_set else (str(row["event_line_id"]) if row["event_line_id"] else None)
            next_scope_mode = payload.scopeMode if payload.scopeMode is not None else str(row["scope_mode"] or "COLLAB_SHARED")
            if next_scope_mode == "PERSONAL_ONLY":
                next_client_id = None
                next_event_line_id = None
            client_id, event_line_id = _normalize_task_client_and_event_line_refs(
                next_client_id,
                next_event_line_id,
            )
            project_module_id = None if next_scope_mode == "PERSONAL_ONLY" else (payload.projectModuleId if "projectModuleId" in payload.model_fields_set else (str(row["project_module_id"]) if row["project_module_id"] else None))
            project_flow_id = None if next_scope_mode == "PERSONAL_ONLY" else (payload.projectFlowId if "projectFlowId" in payload.model_fields_set else (str(row["project_flow_id"]) if row["project_flow_id"] else None))
            project_module, project_flow = resolve_project_structure_refs(client_id, project_module_id, project_flow_id)
            project_context = build_task_project_context(
                client_id,
                str(row["source_type"]),
                str(row["source_id"]) if row["source_id"] else None,
                task_title=payload.title or str(row["title"]),
                task_desc=payload.desc if payload.desc is not None else str(row["description"]),
                project_module_id=project_module.id if project_module else None,
                project_flow_id=project_flow.id if project_flow else None,
            )
            event_line_context = _event_line_snapshot_context(state.db, event_line_id, None)
            attachment_count = int(state.db.scalar("SELECT COUNT(1) FROM task_attachments WHERE task_id = ?", (task_id,)) or 0)
            (
                business_category,
                current_blocker,
                next_action,
                recent_decision,
                evidence_count,
            ) = _resolve_task_action_os_fields(
                title=payload.title or str(row["title"]),
                desc=payload.desc if payload.desc is not None else str(row["description"]),
                source_type=str(row["source_type"]),
                business_category=payload.businessCategory if "businessCategory" in payload.model_fields_set else (str(row["business_category"]) if row["business_category"] else None),
                current_blocker=payload.currentBlocker if "currentBlocker" in payload.model_fields_set else (str(row["current_blocker"]) if row["current_blocker"] else None),
                next_action=payload.nextAction if "nextAction" in payload.model_fields_set else (str(row["next_action"]) if row["next_action"] else None),
                recent_decision=payload.recentDecision if "recentDecision" in payload.model_fields_set else (str(row["recent_decision"]) if row["recent_decision"] else None),
                evidence_count=payload.evidenceCount if "evidenceCount" in payload.model_fields_set else int(row["evidence_count"] or 0),
                project_context=project_context,
                event_line_context=event_line_context,
                attachment_count=attachment_count,
            )
            merged = {
                "title": payload.title or row["title"],
                "description": payload.desc if payload.desc is not None else row["description"],
                "status": payload.status or row["status"],
                "priority": payload.priority or row["priority"],
                "list_id": payload.listId or row["list_id"],
                "scope_mode": next_scope_mode,
                "client_id": client_id,
                "event_line_id": event_line_id,
                "project_module_id": project_module.id if project_module else None,
                "project_flow_id": project_flow.id if project_flow else None,
                "ddl": payload.ddl or row["ddl"],
                "due_date": payload.dueDate if payload.dueDate is not None else row["due_date"],
                "duration_minutes": payload.durationMinutes if payload.durationMinutes is not None else int(row["duration_minutes"] or 60),
                "owner_name": payload.ownerName or row["owner_name"],
                "business_category": business_category,
                "current_blocker": current_blocker,
                "next_action": next_action,
                "recent_decision": recent_decision,
                "evidence_count": evidence_count,
                "tags_json": to_json([tag.name for tag in resolved_tags]),
                "tag_ids_json": to_json([tag.id for tag in resolved_tags]),
                "updated_at": now_iso(),
            }
            state.db.execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, status = ?, priority = ?, list_id = ?, scope_mode = ?, client_id = ?, event_line_id = ?, project_module_id = ?, project_flow_id = ?, ddl = ?, due_date = ?, duration_minutes = ?, owner_name = ?, business_category = ?, current_blocker = ?, next_action = ?, recent_decision = ?, evidence_count = ?, tags_json = ?, tag_ids_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    merged["title"],
                    merged["description"],
                    merged["status"],
                    merged["priority"],
                    merged["list_id"],
                    merged["scope_mode"],
                    merged["client_id"],
                    merged["event_line_id"],
                    merged["project_module_id"],
                    merged["project_flow_id"],
                    merged["ddl"],
                    merged["due_date"],
                    merged["duration_minutes"],
                    merged["owner_name"],
                    merged["business_category"],
                    merged["current_blocker"],
                    merged["next_action"],
                    merged["recent_decision"],
                    merged["evidence_count"],
                    merged["tags_json"],
                    merged["tag_ids_json"],
                    merged["updated_at"],
                    task_id,
                ),
            )
            _sync_task_attachment_scope(
                state.db,
                state.data_dir,
                build_task_attachment,
                build_attachment_event_line_activity,
                ensure_standard_client_folders,
                task_id,
                client_id,
                event_line_id,
                cloud=False,
            )
            if merged["event_line_id"]:
                old_status = str(row["status"])
                new_status = merged["status"]
                status_changed = old_status != new_status
                if status_changed:
                    status_labels = {
                        "done": ("任务完成", f"任务已完成：{merged['title']}"),
                        "doing": ("任务开始执行", f"任务进入执行中：{merged['title']}"),
                        "todo": ("任务已排入计划", f"任务进入待办：{merged['title']}"),
                        "rejected": ("任务已退回", f"任务被退回：{merged['title']}"),
                        "inbox": ("任务退回收件箱", f"任务退回收件箱：{merged['title']}"),
                    }
                    ela_title, ela_summary = status_labels.get(
                        new_status,
                        ("任务状态变更", f"任务状态变更为 {new_status}：{merged['title']}"),
                    )
                    state.db.execute(
                        """
                        INSERT INTO event_line_activities(
                            id, event_line_id, source_type, source_id, happened_at, actor_id, actor_name, title, summary, metadata_json, is_key
                        ) VALUES(?, ?, 'task_activity', ?, ?, NULL, ?, ?, ?, ?, 0)
                        """,
                        (
                            new_id("ela"),
                            merged["event_line_id"],
                            task_id,
                            merged["updated_at"],
                            merged["owner_name"],
                            ela_title,
                            ela_summary,
                            to_json({"eventType": "status_change", "from": old_status, "to": new_status}),
                        ),
                    )
                else:
                    # Detect meaningful field changes and only record those with informational value
                    change_parts: list[str] = []
                    change_meta: dict[str, object] = {"eventType": "updated", "changes": []}
                    old_owner = str(row["owner_name"] or "")
                    new_owner = str(merged["owner_name"] or "")
                    if old_owner != new_owner and new_owner:
                        change_parts.append(f"负责人变更：{old_owner or '未指定'} → {new_owner}")
                        change_meta["changes"].append("owner")  # type: ignore[union-attr]
                    old_due = str(row["due_date"] or "")
                    new_due = str(merged["due_date"] or "")
                    if old_due != new_due:
                        change_parts.append(f"截止日期变更：{old_due or '未设定'} → {new_due or '已取消'}")
                        change_meta["changes"].append("due_date")  # type: ignore[union-attr]
                    old_title = str(row["title"] or "")
                    new_title = str(merged["title"] or "")
                    if old_title != new_title:
                        change_parts.append(f"标题变更：{old_title} → {new_title}")
                        change_meta["changes"].append("title")  # type: ignore[union-attr]
                    # Only write activity if there are meaningful changes
                    if change_parts:
                        ela_title = "、".join(c.split("：")[0] for c in change_parts)
                        ela_summary = "；".join(change_parts)
                        is_key = 1 if "owner" in change_meta.get("changes", []) or "due_date" in change_meta.get("changes", []) else 0  # type: ignore[operator]
                        state.db.execute(
                            """
                            INSERT INTO event_line_activities(
                                id, event_line_id, source_type, source_id, happened_at, actor_id, actor_name, title, summary, metadata_json, is_key
                            ) VALUES(?, ?, 'task_activity', ?, ?, NULL, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_id("ela"),
                                merged["event_line_id"],
                                task_id,
                                merged["updated_at"],
                                merged["owner_name"],
                                ela_title,
                                ela_summary,
                                to_json(change_meta),
                                is_key,
                            ),
                        )
            log_activity("task.update", "task", task_id, payload.model_dump(exclude_none=True))
            updated_task = fetch_tasks("t.id = ?", (task_id,))[0]
            record_task_writeback(
                state.db,
                task_id=updated_task.id,
                title=updated_task.title,
                description=updated_task.desc,
                status=updated_task.status,
                due_date=updated_task.dueDate,
                client_id=updated_task.clientId,
                event_line_id=updated_task.eventLineId,
            )
            growth_user_id, growth_user_name = resolve_growth_actor()
            ingest_task_growth_candidate(
                state.db,
                user_id=growth_user_id,
                user_name=growth_user_name,
                task=updated_task,
                source_type="task_context_candidate",
                created_at=str(merged["updated_at"]),
                ai_service=state.ai,
            )
            return updated_task
        # Cloud path: try cloud sync, but don't block on failure
        cloud_status_map = {"todo": "todo", "doing": "doing", "done": "done", "inbox": "inbox", "rejected": "rejected"}
        cloud_update_payload = {
            "title": payload.title,
            "description": payload.desc,
            "priority": payload.priority,
            "listId": payload.listId,
            "dueDate": payload.dueDate if payload.dueDate is not None else normalize_due_date_input(payload.ddl),
            "durationMinutes": payload.durationMinutes,
            "scopeMode": payload.scopeMode,
            "clientId": payload.clientId,
            "eventLineId": payload.eventLineId,
            "projectModuleId": payload.projectModuleId,
            "projectFlowId": payload.projectFlowId,
            "progressStatus": cloud_status_map.get(payload.status) if payload.status else None,
            "collaboratorIds": payload.collaboratorIds,
            "ownerId": payload.ownerId,
            "businessCategory": payload.businessCategory,
            "currentBlocker": payload.currentBlocker,
            "nextAction": payload.nextAction,
            "recentDecision": payload.recentDecision,
            "evidenceCount": payload.evidenceCount,
        }
        try:
            response = cloud_request("PATCH", f"/api/v1/tasks/{task_id}", json_body=cloud_update_payload)
            if not isinstance(response, dict):
                raise HTTPException(status_code=502, detail="Invalid cloud task payload")
            log_activity("task.update", "task", task_id, payload.model_dump(exclude_none=True))
            updated_task = build_cloud_task(response, {})
            _upsert_cloud_task_shadow_local(response)
        except Exception:
            # Cloud failed — if task exists locally, update local copy and return that
            local_row = state.db.fetchone("SELECT * FROM tasks WHERE id = ? OR cloud_id = ?", (task_id, task_id))
            if local_row:
                local_id = str(local_row["id"])
                state.db.execute(
                    "UPDATE tasks SET title = COALESCE(?, title), description = COALESCE(?, description), status = COALESCE(?, status), priority = COALESCE(?, priority), due_date = COALESCE(?, due_date), sync_status = 'pending', updated_at = ? WHERE id = ?",
                    (payload.title, payload.desc, payload.status, payload.priority, payload.dueDate, now_iso(), local_id),
                )
                log_activity("task.update", "task", local_id, payload.model_dump(exclude_none=True))
                updated_task = fetch_tasks("t.id = ?", (local_id,))[0]
            else:
                raise HTTPException(status_code=502, detail="云端更新失败，且本地无此任务副本")
        growth_user_id, growth_user_name = resolve_growth_actor()
        ingest_task_growth_candidate(
            state.db,
            user_id=growth_user_id,
            user_name=growth_user_name,
            task=updated_task,
            source_type="task_context_candidate",
            created_at=now_iso(),
            ai_service=state.ai,
        )
        Thread(target=_precompute_task_understanding, args=(task_id,), daemon=True).start()
        _cloud_task_board_cache["data"] = None
        return updated_task

    @app.delete("/api/v1/tasks/{task_id}")
    def delete_task(task_id: str) -> dict[str, bool]:
        if not get_cloud_token():
            row = state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            task_title = str(row["title"] or "任务")
            event_line_id = str(row["event_line_id"]) if row["event_line_id"] else None
            client_id = str(row["client_id"]) if row["client_id"] else None
            state.db.execute("DELETE FROM activity_logs WHERE entity_type = 'task' AND entity_id = ?", (task_id,))
            state.db.execute("DELETE FROM event_line_activities WHERE source_type = 'task_activity' AND source_id = ?", (task_id,))
            state.db.execute("DELETE FROM memory_facts WHERE scope_type = 'task' AND scope_id = ?", (task_id,))
            state.db.execute(
                """
                DELETE FROM memory_facts
                WHERE source_type = 'task'
                  AND source_id = ?
                """,
                (task_id,),
            )
            state.db.execute("DELETE FROM growth_signal_events WHERE task_id = ?", (task_id,))
            state.db.execute("DELETE FROM growth_evidence_records WHERE task_id = ?", (task_id,))
            state.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            log_activity("task.delete", "task", task_id, {"title": task_title, "eventLineId": event_line_id, "clientId": client_id})
            if event_line_id:
                refresh_event_line_memory_snapshot(state.db, event_line_id)
            if client_id:
                refresh_organization_notebook_snapshot(state.db, client_id)
            return {"deleted": True}
        # Cloud mode: try cloud delete, also clean up local data
        try:
            cloud_request("DELETE", f"/api/v1/tasks/{task_id}")
        except HTTPException:
            pass  # Cloud task may not exist (local-only) — still clean up locally
        # Clean up local data regardless
        state.db.execute("DELETE FROM task_attachments_cloud WHERE task_id = ?", (task_id,))
        state.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        state.db.execute("DELETE FROM activity_logs WHERE entity_type = 'task' AND entity_id = ?", (task_id,))
        state.db.execute("DELETE FROM event_line_activities WHERE source_type = 'task_activity' AND source_id = ?", (task_id,))
        state.db.execute("DELETE FROM growth_signal_events WHERE task_id = ?", (task_id,))
        state.db.execute("DELETE FROM growth_evidence_records WHERE task_id = ?", (task_id,))
        _cloud_task_board_cache["data"] = None  # Invalidate cache
        log_activity("task.delete", "task", task_id, {})
        return {"deleted": True}

    @app.post("/api/v1/tasks/{task_id}/attachments", response_model=TaskRecord)
    def upload_task_attachment(
        task_id: str,
        file: UploadFile = File(...),
        clientId: str | None = Form(default=None),
        eventLineId: str | None = Form(default=None),
        taskTitle: str | None = Form(default=None),
    ) -> TaskRecord:
        local_task_row = state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        is_cloud_task = local_task_row is None
        # Allow offline upload — attachments are stored locally regardless of cloud status

        resolved_client_id = (
            str(local_task_row["client_id"]) if local_task_row and local_task_row["client_id"] else clientId
        )
        # Try to get clientId from event line if task doesn't have one
        if not resolved_client_id:
            el_id = str(local_task_row["event_line_id"]) if local_task_row and local_task_row["event_line_id"] else eventLineId
            if el_id:
                el_row = state.db.fetchone("SELECT primary_client_id FROM event_lines WHERE id = ?", (el_id,))
                if el_row and el_row["primary_client_id"]:
                    resolved_client_id = str(el_row["primary_client_id"])
        # Fall back to organization's default client
        if not resolved_client_id:
            org_client = state.db.fetchone("SELECT id FROM clients ORDER BY name LIMIT 1")
            if org_client:
                resolved_client_id = str(org_client["id"])
        build_client_summary(resolved_client_id)
        ensure_standard_client_folders(resolved_client_id)

        resolved_event_line_id = (
            str(local_task_row["event_line_id"]) if local_task_row and local_task_row["event_line_id"] else eventLineId
        )
        resolved_task_title = (
            str(local_task_row["title"]) if local_task_row and local_task_row["title"] else (taskTitle or file.filename or "任务附件")
        )
        upload_name = safe_filename(file.filename or f"{resolved_task_title}-附件")
        content = file.file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传失败：附件内容为空。")
        staged_path = stage_task_attachment_upload(resolved_client_id, upload_name, content)
        timestamp = now_iso()
        folder_row = state.db.fetchone(
            "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
            (resolved_client_id, "项目与业务"),
        )
        document_id = new_id("doc")
        excerpt_seed = ""
        if staged_path.suffix.lower() in {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".py", ".ts", ".tsx", ".js", ".jsx"}:
            excerpt_seed = content.decode("utf-8", errors="ignore")
        fallback_excerpt = (
            excerpt_seed.strip()[:140] or f"{upload_name} 已作为任务附件进入项目资料库，可用于后续检索、问答与事件线证据引用。"
        ) if excerpt_seed else f"{upload_name} 已作为任务附件进入项目资料库，可用于后续检索、问答与事件线证据引用。"
        state.db.execute(
            """
            INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                resolved_client_id,
                str(folder_row["id"]) if folder_row else None,
                upload_name,
                str(staged_path),
                str(staged_path),
                staged_path.suffix.lower().lstrip(".") or "bin",
                "task_attachment",
                fallback_excerpt,
                to_json(["task_attachment", staged_path.suffix.lower().lstrip(".") or "bin"]),
                timestamp,
            ),
        )
        ingest_document_knowledge(
            state.db,
            data_dir=state.data_dir,
            client_id=resolved_client_id,
            import_id=None,
            document_id=document_id,
            source_path=staged_path,
            original_source_path=staged_path,
            title=upload_name,
            kind=staged_path.suffix.lower().lstrip(".") or "bin",
            source="task_attachment",
            fallback_excerpt=fallback_excerpt,
            created_at=timestamp,
            ai_service=None,
        )
        document_row = state.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        if not document_row:
            raise HTTPException(status_code=500, detail="附件归档失败。")
        attachment_id = new_id("tatt")
        table_name = "task_attachments_cloud" if is_cloud_task else "task_attachments"
        state.db.execute(
            f"""
            INSERT INTO {table_name}(id, task_id, client_id, event_line_id, document_id, title, path, kind, source, size_bytes, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment_id,
                task_id,
                resolved_client_id,
                resolved_event_line_id,
                document_id,
                str(document_row["title"]),
                str(document_row["path"]),
                str(document_row["kind"]),
                str(document_row["source"]),
                len(content),
                timestamp,
            ),
        )
        state.db.execute(
            """
            INSERT INTO evidence_refs(id, client_id, meeting_id, document_id, title, excerpt, source_type, path, created_at)
            VALUES(?, ?, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("ev"),
                resolved_client_id,
                document_id,
                str(document_row["title"]),
                str(document_row["excerpt"]),
                "task_attachment",
                str(document_row["path"]),
                timestamp,
            ),
        )
        if not is_cloud_task and resolved_event_line_id:
            state.db.execute(
                """
                INSERT INTO event_line_activities(
                    id, event_line_id, source_type, source_id, happened_at, actor_id, actor_name, title, summary, metadata_json, is_key, created_at
                ) VALUES(?, ?, 'attachment', ?, ?, NULL, ?, ?, ?, ?, 1, ?)
                """,
                (
                    new_id("ela"),
                    resolved_event_line_id,
                    attachment_id,
                    timestamp,
                    current_operator_name(),
                    f"上传附件：{document_row['title']}",
                    f"任务附件已进入项目资料库：{document_row['title']}",
                    to_json(
                        {
                            "taskId": task_id,
                            "documentId": document_id,
                            "clientId": resolved_client_id,
                            "path": str(document_row["path"]),
                        }
                    ),
                    timestamp,
                ),
            )
        log_activity(
            "task.attachment.upload",
            "task",
            task_id,
            {
                "attachmentId": attachment_id,
                "documentId": document_id,
                "clientId": resolved_client_id,
                "eventLineId": resolved_event_line_id,
                "title": str(document_row["title"]),
            },
        )
        record_task_attachment_writeback(
            state.db,
            task_id=task_id,
            client_id=resolved_client_id,
            event_line_id=resolved_event_line_id,
            attachment_title=str(document_row["title"]),
            attachment_path=str(document_row["path"]),
        )
        if resolved_event_line_id and get_cloud_token():
            import threading

            def _bg_upload():
                try:

```
