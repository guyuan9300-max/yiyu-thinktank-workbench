# 源码文件：`backend/app/main.py`（分片 06）

- 行号范围：14001-16800
- 总行数：   30416
- 导出时间：2026-04-20

```python
            evidenceLevel="none",
            reason="资料缺口导致暂不形成正式判断",
        )

    def _build_system_strategic_thoughts() -> list[StrategicThoughtRecord]:
        chat_count = int(state.db.scalar("SELECT COUNT(*) FROM chat_messages WHERE role = 'user'") or 0)
        review_count = int(state.db.scalar("SELECT COUNT(*) FROM weekly_reviews") or 0)
        meeting_count = int(state.db.scalar("SELECT COUNT(*) FROM meetings") or 0)
        weekly_new_facts = int(state.db.scalar("SELECT COUNT(*) FROM memory_facts WHERE created_at >= date('now', '-7 days')") or 0)
        thoughts: list[StrategicThoughtRecord] = []

        if chat_count <= 0 and review_count <= 0 and meeting_count <= 0:
            return thoughts

        source_id = "dashboard:signal_density"
        thought_id = _strategic_thought_id(
            scope="system",
            client_id=None,
            source_type="brain_dashboard",
            source_id=source_id,
            topic_key=_strategic_thought_topic_key(source_id),
        )
        if chat_count >= max(20, weekly_new_facts * 6) and (review_count == 0 or meeting_count == 0):
            observation = (
                f"系统看到：AI 对话较活跃（{chat_count}），但近一周结构化沉淀仅 {weekly_new_facts} 条，"
                f"会议 {meeting_count} 场、复盘 {review_count} 次。"
            )
            suggestion = "建议先完成至少一场完整会议或一次周复盘，把关键判断沉淀进结构化链路。"
            status: Literal["draft", "waiting_evidence"] = "waiting_evidence"
            tags = ["系统观察", "结构化沉淀不足"]
        else:
            observation = (
                f"系统看到：本周新增结构化记忆 {weekly_new_facts} 条，"
                f"会议 {meeting_count} 场，复盘 {review_count} 次。"
            )
            suggestion = "建议持续把高价值讨论沉淀为会议纪要、复盘和待确认判断，避免只停留在聊天层。"
            status = "draft"
            tags = ["系统观察"]

        thoughts.append(
            StrategicThoughtRecord(
                id=thought_id,
                scope="system",
                clientId=None,
                clientName="全部客户",
                line="系统观察：结构化沉淀节奏",
                observation=observation,
                suggestion=suggestion,
                confidence=None,
                confidenceLevel="none",
                status=status,
                isSystem=True,
                dueDateHint="本周",
                tags=tags,
                sources=[
                    StrategicThoughtSourceRecord(
                        sourceType="brain_dashboard",
                        sourceId=source_id,
                        label="战略驾驶舱统计",
                        detail=f"chat={chat_count}, meeting={meeting_count}, review={review_count}, weeklyFacts={weekly_new_facts}",
                    )
                ],
                evidenceCount=1,
                generatedAt=now_iso(),
                staleReason=None if status == "draft" else "结构化信号偏弱",
                evidenceLevel="weak" if status == "draft" else "none",
                reason=None if status == "draft" else "结构化沉淀不足，优先补证",
            )
        )
        return thoughts

    def _build_client_strategic_thoughts(
        client_id: str,
        *,
        max_items: int,
    ) -> list[StrategicThoughtRecord]:
        snapshot = build_strategic_cockpit_snapshot(client_id)
        client_name = snapshot.clientName
        generated_at = now_iso()
        has_meeting_or_review = any("会议" in card.label or "复盘" in card.label for card in snapshot.evidencePreview.cards)
        has_confirmed_headline = (
            snapshot.headline.focusStatus == "confirmed"
            or snapshot.headline.weekSummary.status == "confirmed"
            or snapshot.headline.mainContradiction.status == "confirmed"
            or snapshot.headline.coreBreakthrough.status == "confirmed"
        )
        candidate_cards: list[StrategicThoughtRecord] = []
        action_cards: list[StrategicThoughtRecord] = []
        waiting_reasons: list[str] = []

        def _safe_text(value: str | None) -> str:
            return _normalize_text_for_matching(value)

        def _meaningful_text(value: str | None) -> bool:
            text = _safe_text(value)
            return bool(text) and not _is_placeholder_text(text)

        def _has_actionable_next_step(value: str | None) -> bool:
            text = _safe_text(value)
            if not text or _is_placeholder_text(text):
                return False
            if len(text) < 6:
                return False
            return any(token in text for token in ["建议", "先", "本周", "完成", "推进", "补齐", "确认", "落实", "拆成"])

        def build_thought(
            *,
            line: str,
            observation: str,
            suggestion: str,
            status: Literal["draft", "waiting_evidence"] = "draft",
            tags: list[str] | None = None,
            sources: list[StrategicThoughtSourceRecord],
            evidence_count: int,
            stale_reason: str | None = None,
            has_line_evidence: bool = False,
            has_meaningful_summary: bool = True,
            has_actionable_next_step: bool = True,
            reason: str | None = None,
        ) -> StrategicThoughtRecord:
            primary = sources[0]
            thought_id = _strategic_thought_id(
                scope="client",
                client_id=client_id,
                source_type=primary.sourceType,
                source_id=primary.sourceId,
                topic_key=_strategic_thought_topic_key(line),
            )
            confidence, confidence_level = _strategic_thought_confidence(
                readiness_score=snapshot.readiness.score,
                readiness_status=snapshot.readiness.status,
                evidence_count=evidence_count,
                has_line_evidence=has_line_evidence,
                has_meeting_or_review=has_meeting_or_review,
                has_confirmed_headline=has_confirmed_headline,
                has_meaningful_summary=has_meaningful_summary,
                has_actionable_next_step=has_actionable_next_step,
            )
            evidence_level = _evidence_level(
                evidence_count=evidence_count,
                sources=sources,
                has_meaningful_summary=has_meaningful_summary,
                has_actionable_next_step=has_actionable_next_step,
            )
            confidence, confidence_level = _cap_confidence_by_evidence(
                confidence,
                confidence_level,
                evidence_level,
                status=status,
            )
            return StrategicThoughtRecord(
                id=thought_id,
                scope="client",
                clientId=client_id,
                clientName=client_name,
                line=line,
                observation=observation,
                suggestion=suggestion,
                confidence=confidence,
                confidenceLevel=confidence_level,
                status=status,
                isSystem=False,
                dueDateHint="本周",
                tags=tags or [],
                sources=sources,
                evidenceCount=max(evidence_count, 0),
                generatedAt=generated_at,
                staleReason=stale_reason,
                evidenceLevel=evidence_level,
                reason=reason,
            )

        headline_summary = _safe_text(snapshot.headline.mainContradiction.value)
        if _meaningful_text(headline_summary):
            action_cards.append(
                build_thought(
                    line=f"{client_name}：当前主矛盾判断",
                    observation=f"系统看到：{headline_summary}",
                    suggestion=(
                        f"建议先围绕「{_safe_text(snapshot.headline.coreBreakthrough.value)}」收敛一条最小推进动作。"
                        if _meaningful_text(snapshot.headline.coreBreakthrough.value)
                        else "建议先把主矛盾拆成可执行动作，并挂到本周任务或会议议程。"
                    ),
                    tags=["系统候选", "战略驾驶舱"],
                    sources=[
                        StrategicThoughtSourceRecord(
                            sourceType="headline",
                            sourceId=f"{client_id}:main_contradiction",
                            label="主矛盾判断",
                            detail=headline_summary,
                        ),
                        StrategicThoughtSourceRecord(
                            sourceType="strategic_cockpit",
                            sourceId=client_id,
                            label="战略驾驶舱",
                        ),
                    ],
                    evidence_count=max(len(snapshot.evidencePreview.keyFacts), 1),
                    has_line_evidence=True,
                    has_meaningful_summary=True,
                    has_actionable_next_step=True,
                )
            )

        for strategic_line in snapshot.strategicLines[:6]:
            title = _safe_text(strategic_line.title)
            summary = _safe_text(strategic_line.summary)
            blocker = _safe_text(strategic_line.blocker)
            next_step = _safe_text(strategic_line.nextStep)
            evidence_count = len(strategic_line.evidence or [])
            has_meaningful_summary = _meaningful_text(summary)
            has_specific_blocker = _meaningful_text(blocker)
            has_actionable_step = _has_actionable_next_step(next_step)
            has_specific_title = _looks_specific_line_title(title)
            evidence_text = " ".join(strategic_line.evidence or [])
            has_real_signal_source = any(token in f"{evidence_text}{summary}" for token in ["会议", "复盘", "事件线", "判断", "纪要"])
            is_valid_line = (
                (has_specific_blocker and has_actionable_step)
                or (has_meaningful_summary and evidence_count >= 2)
                or (has_specific_title and has_actionable_step)
                or has_real_signal_source
            )
            if not is_valid_line:
                if blocker and _is_placeholder_text(blocker):
                    waiting_reasons.append("该业务线当前阻塞仍待澄清")
                if next_step and _is_placeholder_text(next_step):
                    waiting_reasons.append("该业务线缺少可执行下一步动作")
                if not has_meaningful_summary:
                    waiting_reasons.append("该业务线摘要不足，暂不能形成稳定判断")
                continue
            observation = (
                f"系统看到这条线当前重点：{summary}"
                if has_meaningful_summary
                else f"系统看到该条线当前阻塞：{blocker}"
            )
            suggestion = (
                f"建议下一步先执行：{next_step}"
                if has_actionable_step
                else "建议先把下一步动作写成可执行任务，再进入判断确认。"
            )
            action_sources = [
                StrategicThoughtSourceRecord(
                    sourceType="strategic_line",
                    sourceId=strategic_line.id,
                    label=title or "战略线",
                    detail=summary or None,
                ),
                StrategicThoughtSourceRecord(
                    sourceType="strategic_cockpit",
                    sourceId=client_id,
                    label="战略驾驶舱",
                ),
            ]
            action_cards.append(
                build_thought(
                    line=f"{client_name}：{title or '业务推进'}",
                    observation=observation,
                    suggestion=suggestion,
                    tags=["系统候选", f"势能：{strategic_line.momentum}"],
                    sources=action_sources,
                    evidence_count=evidence_count,
                    has_line_evidence=evidence_count > 0,
                    has_meaningful_summary=has_meaningful_summary,
                    has_actionable_next_step=has_actionable_step,
                )
            )

        candidate_judgments = snapshot.radarLayer.get("candidateJudgments") if isinstance(snapshot.radarLayer, dict) else []
        if isinstance(candidate_judgments, list):
            for raw_candidate in candidate_judgments:
                if not isinstance(raw_candidate, dict):
                    continue
                topic = _safe_text(str(raw_candidate.get("topic") or ""))
                summary = _safe_text(str(raw_candidate.get("summary") or ""))
                candidate_id = _safe_text(str(raw_candidate.get("id") or "")) or None
                if not _meaningful_text(summary):
                    waiting_reasons.append("候选判断缺少可解释摘要，暂不能进入待确认卡")
                    continue
                topic_label = _humanize_candidate_topic(topic, summary)
                safe_summary = re.sub(
                    r"^(client_overview|org_overview|project_overview|main_contradiction|core_breakthrough|pending_material|pending_decision|[a-z]+(?:_[a-z0-9]+)+)\s*[:：-]\s*",
                    "",
                    summary,
                    flags=re.I,
                ).strip()
                safe_summary = _strategic_truncate(safe_summary or summary, 160)
                if _is_internal_topic_key(safe_summary):
                    safe_summary = "系统已识别一条待确认判断，但摘要仍需补充可读描述。"
                evidence_count = 1
                if isinstance(raw_candidate.get("evidenceIds"), list):
                    evidence_count = max(evidence_count, len([item for item in raw_candidate.get("evidenceIds", []) if item]))
                candidate_cards.append(
                    build_thought(
                        line=f"{client_name}：{topic_label}",
                        observation=f"系统看到：{safe_summary}",
                        suggestion="建议先确认这条判断是否成立；若成立，再把它写入正式判断或转成下一步任务。",
                        tags=["系统候选", "待确认判断"],
                        sources=[
                            StrategicThoughtSourceRecord(
                                sourceType="judgment_version",
                                sourceId=candidate_id,
                                label=topic_label,
                                detail=safe_summary,
                            ),
                            StrategicThoughtSourceRecord(
                                sourceType="strategic_cockpit",
                                sourceId=client_id,
                                label="战略驾驶舱",
                            ),
                        ],
                        evidence_count=evidence_count,
                        has_line_evidence=evidence_count > 0,
                        has_meaningful_summary=True,
                        has_actionable_next_step=True,
                    )
                )
                break

        if snapshot.pendingDecisions:
            decision = snapshot.pendingDecisions[0]
            title = _safe_text(decision.title)
            detail = _safe_text(decision.detail)
            if _meaningful_text(title):
                action_cards.append(
                    build_thought(
                        line=f"{client_name}：待确认决策",
                        observation=f"系统看到当前待拍板事项：{title}{f'（{detail}）' if detail else ''}",
                        suggestion="建议本周完成该事项决策，并把决策结果写入会议纪要或判断记录。",
                        tags=["系统候选", "待拍板"],
                        sources=[
                            StrategicThoughtSourceRecord(
                                sourceType="pending_decision",
                                sourceId=f"{client_id}:pending_decision:0",
                                label=title,
                                detail=detail or None,
                            ),
                            StrategicThoughtSourceRecord(
                                sourceType="strategic_cockpit",
                                sourceId=client_id,
                                label="战略驾驶舱",
                            ),
                        ],
                        evidence_count=1,
                        has_line_evidence=True,
                        has_meaningful_summary=_meaningful_text(detail) or _meaningful_text(title),
                        has_actionable_next_step=True,
                    )
                )

        for material in snapshot.pendingMaterials[:3]:
            text = _safe_text(f"{material.title} {material.detail}")
            if _meaningful_text(text):
                waiting_reasons.append(text)

        if snapshot.readiness.status == "insufficient":
            waiting_reasons.extend(snapshot.readiness.gaps[:3])

        waiting_reasons = _strategic_unique_non_empty(waiting_reasons)
        waiting_card: StrategicThoughtRecord | None = None
        if waiting_reasons:
            preview = "；".join(waiting_reasons[:3])
            waiting_card = build_thought(
                line=f"{client_name}：资料缺口影响判断",
                observation=f"系统看到当前仍有资料缺口：{preview}",
                suggestion="建议先补齐最影响判断的 1-2 项材料，再推进正式判断。",
                status="waiting_evidence",
                tags=["等待补证", "资料缺口"],
                sources=[
                    StrategicThoughtSourceRecord(
                        sourceType="pending_material" if snapshot.pendingMaterials else "strategic_cockpit",
                        sourceId=f"{client_id}:waiting_evidence",
                        label="资料缺口",
                        detail=preview,
                    ),
                    StrategicThoughtSourceRecord(
                        sourceType="strategic_cockpit",
                        sourceId=client_id,
                        label="战略驾驶舱",
                    ),
                ],
                evidence_count=max(0, len(snapshot.pendingMaterials)),
                stale_reason=preview,
                has_line_evidence=False,
                has_meaningful_summary=False,
                has_actionable_next_step=False,
                reason="资料不足，暂不构成正式判断",
            )

        selected: list[StrategicThoughtRecord] = []
        if candidate_cards:
            selected.append(sorted(candidate_cards, key=lambda item: (_source_strength(item), item.confidence or 0), reverse=True)[0])
        if action_cards:
            selected.append(
                sorted(
                    action_cards,
                    key=lambda item: (_evidence_level_weight(item.evidenceLevel), _source_strength(item), item.confidence or 0),
                    reverse=True,
                )[0]
            )
        if waiting_card:
            selected.append(waiting_card)

        selected = _dedupe_strategic_thoughts(selected)
        if not selected and snapshot.readiness.status == "insufficient":
            selected.append(
                _build_waiting_evidence_thought(
                    client_id=client_id,
                    client_name=client_name,
                    readiness_summary=snapshot.readiness.summary,
                    gaps=snapshot.readiness.gaps,
                )
            )
        return selected[:max_items]

    def _build_strategic_thoughts(
        *,
        selected_client_id: str | None,
        include_dismissed: bool,
        limit: int,
    ) -> list[StrategicThoughtRecord]:
        thoughts: list[StrategicThoughtRecord] = []
        if selected_client_id:
            thoughts.extend(_build_client_strategic_thoughts(selected_client_id, max_items=min(3, max(1, limit))))
        else:
            thoughts.extend(_build_system_strategic_thoughts())
            client_rows = state.db.fetchall("SELECT id FROM clients ORDER BY updated_at DESC LIMIT 12")
            for row in client_rows:
                client_id = str(row["id"])
                thoughts.extend(_build_client_strategic_thoughts(client_id, max_items=1))
        thoughts = _merge_strategic_thought_reviews(thoughts, include_dismissed=include_dismissed)
        thoughts = _dedupe_strategic_thoughts(thoughts)
        thoughts.sort(
            key=lambda item: (
                _status_weight(item.status),
                1 if not item.isSystem else 0,
                _evidence_level_weight(item.evidenceLevel if hasattr(item, "evidenceLevel") else "none"),
                _source_strength(item),
                item.confidence or -1,
                item.generatedAt,
            ),
            reverse=True,
        )
        return thoughts[:limit]

    def _find_strategic_thought_by_id(thought_id: str) -> StrategicThoughtRecord | None:
        if not thought_id.strip():
            return None
        thoughts = _build_strategic_thoughts(selected_client_id=None, include_dismissed=True, limit=240)
        return next((item for item in thoughts if item.id == thought_id), None)

    def _save_strategic_thought_review(
        *,
        thought: StrategicThoughtRecord,
        status: Literal["confirmed", "dismissed", "task_created"],
        note: str,
        task_id: str | None,
        judgment_id: str | None,
        reviewer_id: str,
        reviewer_name: str,
    ) -> StrategicThoughtReviewRecord:
        now = now_iso()
        existing = state.db.fetchone(
            "SELECT id, created_at, task_id, judgment_id FROM strategic_thought_reviews WHERE thought_id = ?",
            (thought.id,),
        )
        source = thought.sources[0] if thought.sources else StrategicThoughtSourceRecord(sourceType="system", label="系统")
        persisted_task_id = task_id if task_id is not None else (str(existing["task_id"]) if existing and existing["task_id"] else None)
        persisted_judgment_id = (
            judgment_id if judgment_id is not None else (str(existing["judgment_id"]) if existing and existing["judgment_id"] else None)
        )
        if existing:
            review_id = str(existing["id"])
            created_at = str(existing["created_at"] or now)
            state.db.execute(
                """
                UPDATE strategic_thought_reviews
                SET client_id = ?,
                    status = ?,
                    note = ?,
                    task_id = ?,
                    judgment_id = ?,
                    source_type = ?,
                    source_id = ?,
                    reviewed_by_id = ?,
                    reviewed_by_name = ?,
                    reviewed_at = ?,
                    updated_at = ?
                WHERE thought_id = ?
                """,
                (
                    thought.clientId,
                    status,
                    note,
                    persisted_task_id,
                    persisted_judgment_id,
                    source.sourceType,
                    source.sourceId or "",
                    reviewer_id,
                    reviewer_name,
                    now,
                    now,
                    thought.id,
                ),
            )
        else:
            review_id = new_id("sthr")
            created_at = now
            state.db.execute(
                """
                INSERT INTO strategic_thought_reviews(
                    id, thought_id, client_id, status, note, task_id, judgment_id,
                    source_type, source_id, reviewed_by_id, reviewed_by_name, reviewed_at, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    thought.id,
                    thought.clientId,
                    status,
                    note,
                    persisted_task_id,
                    persisted_judgment_id,
                    source.sourceType,
                    source.sourceId or "",
                    reviewer_id,
                    reviewer_name,
                    now,
                    created_at,
                    now,
                ),
            )
        return StrategicThoughtReviewRecord(
            thoughtId=thought.id,
            status=status,
            note=note,
            taskId=persisted_task_id,
            judgmentId=persisted_judgment_id,
            reviewedAt=now,
            reviewedBy=reviewer_name or reviewer_id,
        )

    def build_strategic_cockpit_snapshot(client_id: str) -> StrategicCockpitSnapshotRecord:
        workspace = workspace_for_client(client_id)
        cockpit_projection = get_client_analysis_bundle(
            state.db,
            workspace,
            requested_scope_type="client",
            requested_scope_id=client_id,
            intent_profile="strategic_cockpit",
        )
        client = workspace.client
        notebook_response = get_client_notebook_response(state.db, client_id)
        notebook_summary = notebook_response.organizationNotebookSnapshot
        memory_status = get_client_memory_status(state.db, client_id)
        candidate_review_sla = get_candidate_review_sla_summary(state.db, client_id=client_id)
        review_dashboard = local_review_dashboard()
        review_analysis = review_dashboard.workAnalysis
        client_tasks = _strategic_task_pool(client_id, workspace)
        analyzable_tasks = sorted(
            [task for task in client_tasks if _strategic_has_meaningful_task_background(task)],
            key=lambda item: (_strategic_background_signal_score(item), item.updatedAt),
            reverse=True,
        )
        background_thin_tasks = sorted(
            [task for task in client_tasks if not _strategic_has_meaningful_task_background(task)],
            key=lambda item: item.updatedAt,
            reverse=True,
        )
        linked_event_lines = list_linked_event_lines(state.db, client_id)
        event_line_ids = {task.eventLineId for task in analyzable_tasks if task.eventLineId}
        event_line_ids.update({item.id for item in linked_event_lines})
        module_names = {item.name for item in workspace.projectModules}
        event_line_names = {task.eventLineName for task in analyzable_tasks if task.eventLineName}

        review_event_line_summaries = [
            item
            for item in (review_analysis.eventLineSummaries if review_analysis else [])
            if item.eventLineId in event_line_ids
            or item.projectName == client.name
            or (item.moduleName and item.moduleName in module_names)
            or item.title in event_line_names
        ]
        review_completeness = [
            item for item in (review_analysis.eventLineCompleteness if review_analysis else []) if item.eventLineId in event_line_ids
        ]
        review_risk_cards = [
            item for item in (review_analysis.riskCards if review_analysis else []) if item.eventLineId in event_line_ids
        ]
        review_opportunity_cards = [
            item for item in (review_analysis.opportunityCards if review_analysis else []) if item.eventLineId in event_line_ids
        ]

        notebook_stage = notebook_summary.currentStage if notebook_summary else ""
        notebook_intro = notebook_summary.organizationIntro if notebook_summary else ""
        notebook_recent_facts = list(notebook_summary.recentFacts) if notebook_summary else []
        notebook_gaps = list(notebook_summary.informationGaps) if notebook_summary else []
        snapshot_row = _load_strategic_snapshot_row(client_id)
        session_user = get_cached_session_user()
        org_model_profile = _load_org_model_profile_safe()
        leader_user_id = org_model_profile.organization.leaderUserId if org_model_profile else None
        is_ceo = bool(session_user and leader_user_id and session_user.id == leader_user_id)
        permission = StrategicPermissionRecord(
            canEdit=is_ceo,
            isCeo=is_ceo,
            leaderUserId=leader_user_id,
            notice="请先在组织设置中确认 CEO 账号" if not leader_user_id else (None if is_ceo else "当前页面仅 CEO 可确认和改写经营判断"),
        )

        recent_meeting = workspace.meetings[0] if workspace.meetings else None
        recent_analysis = workspace.analysisRuns[0] if workspace.analysisRuns else None
        recent_judgment = next(
            (
                item
                for item in [
                    cockpit_projection.judgment_bundle.baselineJudgment if cockpit_projection.judgment_bundle else None,
                    *(
                        cockpit_projection.judgment_bundle.overlayDeltas
                        if cockpit_projection.judgment_bundle
                        else []
                    ),
                ]
                if item is not None and item.authorityLevel == "approved"
            ),
            None,
        )
        recent_conflict = workspace.latestConflicts[0] if workspace.latestConflicts else None
        active_task = next((item for item in analyzable_tasks if item.status == "doing"), analyzable_tasks[0] if analyzable_tasks else None)
        completed_tasks = [item for item in analyzable_tasks if item.status == "done"]
        blocked_tasks = [item for item in analyzable_tasks if item.status in {"todo", "rejected"}]

        readiness_checks = [
            any(module.hasDocument for module in workspace.dnaModules),
            bool(workspace.analysisRuns),
            bool(workspace.meetings),
            bool(workspace.goals),
            bool(workspace.projectModules),
            bool(workspace.projectFlows),
            bool(review_event_line_summaries or review_risk_cards or review_opportunity_cards),
            bool(analyzable_tasks or linked_event_lines),
        ]
        readiness_count = len([item for item in readiness_checks if item])
        readiness_status: Literal["ready", "insufficient"] = "ready" if readiness_count >= 4 else "insufficient"
        readiness_gaps = _strategic_unique_non_empty([
            None if workspace.meetings else "当前还没有会议沉淀，缺少经营讨论后的正式信号。",
            None if workspace.goals else "当前还没有业务目标锚点，页面无法判断什么算真正推进。",
            None if workspace.projectModules else "当前还没有业务模块定义，任务和资料难以挂到稳定承接位。",
            None if workspace.projectFlows else "当前还没有关键流程，阻塞和下一步只能停在泛描述。",
            None if (review_event_line_summaries or review_risk_cards or review_opportunity_cards) else "周复盘里还没有事件线摘要、风险卡或机会卡，预测基础不足。",
            f"当前有 {len(background_thin_tasks)} 条任务只写了动作名，没有补对象背景、合作关系和推进目的，暂不纳入洞察与预测。"
            if background_thin_tasks
            else None,
            *notebook_gaps,
        ])
        readiness = StrategicReadinessRecord(
            status=readiness_status,
            score=round(readiness_count / len(readiness_checks) * 100),
            summary=(
                "当前已具备基本判断条件，可以把任务、资料、会议和分析压成经营判断。"
                if readiness_status == "ready"
                else f"当前判断准备度不足。优先补齐：{('；'.join(readiness_gaps[:3])) if readiness_gaps else '会议、目标、模块和流程信号。'}"
            ),
            gaps=readiness_gaps,
        )

        dossier_summary = _strategic_first_non_empty(
            [
                notebook_intro,
                client.intro,
                *[item.summary for item in workspace.dnaModules],
                *[item.summary for item in workspace.documentCards],
            ],
            "当前还没有足够厚的业务底稿。建议优先复用客户 DNA、战略分析、业务分析和战略规划资料，形成对这条业务的稳定描述。",
        )
        dossier_cards = [
            StrategicEvidenceCardRecord(label="机构阶段", value=(notebook_stage or client.stage or "待判断")),
            StrategicEvidenceCardRecord(label="DNA 模块", value=f"{len([item for item in workspace.dnaModules if item.hasDocument])} 个已接入"),
            StrategicEvidenceCardRecord(label="项目模块", value=f"{len(workspace.projectModules)} 个模块"),
            StrategicEvidenceCardRecord(label="项目流程", value=f"{len(workspace.projectFlows)} 条流程"),
            StrategicEvidenceCardRecord(label="资料卡", value=f"{len(workspace.documentCards)} 份"),
            StrategicEvidenceCardRecord(label="分析运行", value=f"{len(workspace.analysisRuns)} 次"),
        ]
        dossier_boundaries = _strategic_unique_non_empty([
            *[risk for flow in workspace.projectFlows for risk in flow.riskPoints],
            *[f"DNA 缺口：{missing}" for module in workspace.dnaModules for missing in module.missingInfo],
            *notebook_gaps,
            f"当前仍有 {workspace.knowledgeStatus.reviewPendingDocuments} 份资料待复核，关键判断不能说太满。"
            if workspace.knowledgeStatus and workspace.knowledgeStatus.reviewPendingDocuments
            else None,
        ])[:4]

        key_facts = _strategic_unique_non_empty([
            f"最近会议“{recent_meeting.title}”更新于 {_strategic_format_date_label(recent_meeting.updatedAt)}。" if recent_meeting else None,
            f"最近分析围绕“{_strategic_truncate(recent_analysis.question, 32)}”，当前状态 {recent_analysis.status}。" if recent_analysis else None,
            f"最新 judgment 已落到“{_strategic_truncate(recent_judgment.topic, 28)}”，状态 {recent_judgment.status}。" if recent_judgment else None,
            f"当前最明确的业务锚点是“{workspace.goals[0].title}”。" if workspace.goals else None,
            f"最近完成的关键动作包括“{completed_tasks[0].title}”。" if completed_tasks else None,
            f"最近一次资料导入来自 {Path(workspace.imports[0].sourcePath).name}。" if workspace.imports else None,
            f"当前最稳定的事件线是“{linked_event_lines[0].name}”。" if linked_event_lines else None,
            *notebook_recent_facts[:2],
        ])[:5]
        key_warnings = _strategic_unique_non_empty([
            readiness.summary if readiness_status == "insufficient" else None,
            recent_conflict.summary if recent_conflict else None,
            review_risk_cards[0].statement if review_risk_cards else None,
            review_risk_cards[1].statement if len(review_risk_cards) > 1 else None,
            "客户 DNA 还不完整，宏观判断容易受短期热度影响。" if not any(item.hasDocument for item in workspace.dnaModules) else None,
            "当前还没有稳定项目模块，经营讨论缺少承载位。" if not workspace.projectModules else None,
            "当前还没有关键流程结构，阻塞容易反复出现。" if not workspace.projectFlows else None,
            f"有 {len(background_thin_tasks)} 条任务缺少背景描述，当前只保留在事实层，不进入洞察与预测。" if background_thin_tasks else None,
        ])[:5]

        contradiction_auto = "当前业务已经有推进痕迹，但还需要把过程信号稳定压缩成经营判断。"
        contradiction_sources = _strategic_unique_non_empty([
            review_risk_cards[0].title if review_risk_cards else None,
            workspace.goals[0].title if workspace.goals else None,
            active_task.title if active_task else None,
        ])
        if readiness_status == "insufficient":
            contradiction_auto = f"当前先不强行判断，主要因为{readiness_gaps[0] if readiness_gaps else '业务结构和周判断信号都还偏薄'}。"
        elif not any(item.hasDocument for item in workspace.dnaModules):
            contradiction_auto = "运行信号在增加，但业务底稿仍然偏薄，容易把短期现象误当成长期方向。"
        elif not workspace.projectModules or not workspace.projectFlows:
            contradiction_auto = "业务目标已经出现，但承接结构还不够清楚，目标难以稳定落到模块与流程。"
        elif len(workspace.documentCards) >= 6 and not workspace.analysisRuns:
            contradiction_auto = "资料已经在变厚，但还没有被收敛成正式分析与管理判断。"
        elif review_risk_cards:
            contradiction_auto = review_risk_cards[0].statement
        elif recent_conflict:
            contradiction_auto = recent_conflict.summary
        elif len(blocked_tasks) > max(2, len(completed_tasks)):
            contradiction_auto = "当前推进动作不少，但卡点没有被持续拆解，管理注意力容易停留在事务层。"

        core_breakthrough_auto = "先把最重要的一条业务线说清楚，再围绕它组织下一次周会与行动推进。"
        core_breakthrough_sources = _strategic_unique_non_empty([
            contradiction_auto,
            recent_analysis.question if recent_analysis else None,
            workspace.goals[0].title if workspace.goals else None,
        ])
        if readiness_status == "insufficient":
            core_breakthrough_auto = "先补“业务目标 + 模块/流程 + 周会沉淀 + 任务背景说明”这四件基础设施，再谈洞察和预测。"
        elif not any(item.hasDocument for item in workspace.dnaModules):
            core_breakthrough_auto = "先补齐机构说明、项目说明和团队说明，让后续判断不被短期波动带偏。"
        elif not workspace.projectModules:
            core_breakthrough_auto = "把当前业务拆成稳定的项目模块，让经营判断有明确承载位。"
        elif not workspace.projectFlows:
            core_breakthrough_auto = "优先补齐关键流程，让阻塞不再只停留在口头描述。"
        elif recent_analysis:
            core_breakthrough_auto = f"围绕“{_strategic_truncate(recent_analysis.question, 30)}”收敛出 1 个本周期主问题，并让任务链围绕它推进。"
        elif recent_judgment:
            core_breakthrough_auto = f"先把“{_strategic_truncate(recent_judgment.topic, 30)}”从 draft judgment 推进到可确认结论。"
        elif workspace.goals:
            core_breakthrough_auto = f"围绕“{workspace.goals[0].title}”组织下一轮动作与证据，不要同时铺开太多陪伴线。"

        focus_items_auto = _strategic_unique_non_empty([
            f"先把“{workspace.goals[0].title}”落成真正可跟踪的业务目标。" if readiness_status == "insufficient" and workspace.goals else None,
            "先明确这条业务本周期只抓的一个核心目标，不再让任务各走各的。" if readiness_status == "insufficient" and not workspace.goals else None,
            "先把当前业务拆成 2 到 4 个稳定模块，别再直接拿零散任务做判断。" if readiness_status == "insufficient" and not workspace.projectModules else None,
            "先补一条关键推进流程，让“当前阻塞 / 下一步”有稳定承接位。" if readiness_status == "insufficient" and not workspace.projectFlows else None,
            "关系推进类任务必须在描述里写清：对象是谁、当前关系、这次动作想推动什么。" if readiness_status == "insufficient" and background_thin_tasks else None,
            "本周至少形成一次业务盘点会或推进会，让战略页开始有正式会议信号。" if readiness_status == "insufficient" and not recent_meeting else None,
            f"围绕“{workspace.goals[0].title}”校准当前业务的真实优先级。" if readiness_status == "ready" and workspace.goals else None,
            f"把推进动作“{active_task.title}”和本周主问题挂钩。" if readiness_status == "ready" and active_task else None,
            f"下一次会谈先对齐最近会议“{recent_meeting.title}”里仍未闭环的问题。" if readiness_status == "ready" and recent_meeting else None,
            f"把最近分析“{_strategic_truncate(recent_analysis.question, 32)}”从洞察变成动作。" if readiness_status == "ready" and recent_analysis else None,
        ])[:3]

        snapshot_focus_items = _parse_json_list(snapshot_row["focus_items_json"]) if snapshot_row and snapshot_row["focus_items_json"] else []
        week_summary_confirmed = str(snapshot_row["week_summary"]).strip() if snapshot_row and snapshot_row["week_summary"] else ""
        main_contradiction_confirmed = str(snapshot_row["main_contradiction"]).strip() if snapshot_row and snapshot_row["main_contradiction"] else ""
        core_breakthrough_confirmed = str(snapshot_row["core_breakthrough"]).strip() if snapshot_row and snapshot_row["core_breakthrough"] else ""

        week_summary_auto = (
            "当前先把业务底稿补厚，暂不把零散动作抬成经营判断。"
            if readiness_status == "insufficient"
            else _strategic_first_non_empty([
                review_dashboard.orgReport.headline if review_dashboard.orgReport else None,
                f"这条业务当前更需要把“{_strategic_truncate(workspace.goals[0].title if workspace.goals else recent_analysis.question if recent_analysis else review_event_line_summaries[0].title if review_event_line_summaries else '主问题', 28)}”收敛成稳定经营判断。",
            ], "当前业务还缺经营摘要，需要先补齐底稿和周判断。")
        )
        freshness = " / ".join(_strategic_unique_non_empty([
            f"会议 {_strategic_format_date_label(recent_meeting.updatedAt)}" if recent_meeting else None,
            f"分析 {_strategic_format_date_label(recent_analysis.updatedAt)}" if recent_analysis else None,
            f"导入 {_strategic_format_date_label(workspace.imports[0].createdAt)}" if workspace.imports else None,
            f"任务 {_strategic_format_date_label(client_tasks[0].updatedAt)}" if client_tasks else None,
            f"复盘 {_strategic_format_date_label(review_dashboard.currentReview.updatedAt)}" if review_dashboard.currentReview else None,
        ])[:4]) or "当前还没有足够新的更新信号"

        headline = StrategicHeadlineRecord(
            weekSummary=StrategicJudgmentRecord(
                value=week_summary_confirmed or week_summary_auto,
                status="confirmed" if week_summary_confirmed else "system_draft",
                sources=["CEO 已确认"] if week_summary_confirmed else _strategic_unique_non_empty([
                    recent_meeting.title if recent_meeting else None,
                    recent_analysis.question if recent_analysis else None,
                    workspace.goals[0].title if workspace.goals else None,
                ])[:3],
            ),
            mainContradiction=StrategicJudgmentRecord(
                value=main_contradiction_confirmed or contradiction_auto,
                status="confirmed" if main_contradiction_confirmed else ("waiting" if readiness_status == "insufficient" else "system_draft"),
                sources=["CEO 已确认"] if main_contradiction_confirmed else contradiction_sources[:3],
            ),
            coreBreakthrough=StrategicJudgmentRecord(
                value=core_breakthrough_confirmed or core_breakthrough_auto,
                status="confirmed" if core_breakthrough_confirmed else ("waiting" if readiness_status == "insufficient" else "system_draft"),
                sources=["CEO 已确认"] if core_breakthrough_confirmed else core_breakthrough_sources[:3],
            ),
            focusItems=snapshot_focus_items[:3] if snapshot_focus_items else focus_items_auto,
            focusStatus="confirmed" if snapshot_focus_items else ("waiting" if readiness_status == "insufficient" else "system_draft"),
            freshness=freshness,
        )

        event_line_memory_rows = {
            str(row["event_line_id"]): row
            for row in state.db.fetchall(
                "SELECT * FROM event_line_memory_snapshots WHERE event_line_id IN ({})".format(",".join("?" for _ in event_line_ids)) if event_line_ids else "SELECT * FROM event_line_memory_snapshots WHERE 0",
                tuple(event_line_ids),
            )
        }

        def _strategic_line_id(title: str, module_name: str | None = None, flow_name: str | None = None) -> str:
            payload = "::".join(
                [
                    client_id,
                    (module_name or "").strip(),
                    (flow_name or "").strip(),
                    title.strip(),
                ]
            )
            return f"sl_{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:12]}"

        strategic_lines: list[StrategicLineRecord] = []
        if workspace.projectModules:
            for module in workspace.projectModules:
                module_tasks = [item for item in client_tasks if item.projectModuleId == module.id or item.projectModuleName == module.name]
                module_summary = next((item for item in review_event_line_summaries if item.moduleName == module.name), None)
                flow = next((item for item in workspace.projectFlows if item.moduleId == module.id), None)
                module_event_line_id = next((item.eventLineId for item in module_tasks if item.eventLineId), None)
                memory_row = event_line_memory_rows.get(module_event_line_id or "") if module_event_line_id else None
                momentum: Literal["加码", "稳住", "收口", "暂停"] = (
                    "暂停"
                    if module_summary and module_summary.status == "blocked"
                    else "收口"
                    if module_tasks and all(item.status == "done" for item in module_tasks)
                    else "加码"
                    if module_summary and module_summary.predictionReadiness == "strong_forecast" and review_opportunity_cards
                    else "稳住"
                )
                strategic_lines.append(
                    StrategicLineRecord(
                        id=_strategic_line_id(module.name, module.name, flow.name if flow else None),
                        title=module.name,
                        summary=_strategic_first_non_empty([
                            str(memory_row["current_work"]).strip() if memory_row and memory_row["current_work"] else None,
                            module.goal,
                            module.description,
                            module_summary.whatThisLineIs if module_summary else None,
                        ], "这条业务线需要进一步明确它到底在推进什么。"),
                        module=module.name,
                        flow=flow.name if flow else None,
                        stage=str(memory_row["current_stage"]).strip() if memory_row and memory_row["current_stage"] else (module_tasks[0].projectContext.stage if module_tasks and module_tasks[0].projectContext else None),
                        blocker=_strategic_first_non_empty([
                            str(memory_row["current_blocker"]).strip() if memory_row and memory_row["current_blocker"] else None,
                            module_summary.mainBlocker if module_summary else None,
                            *[item.projectContext.currentBlocker for item in module_tasks if item.projectContext],
                        ], "当前还没有稳定识别到这条线最主要的阻塞。"),
                        decision=_strategic_first_non_empty([
                            str(memory_row["recent_decision"]).strip() if memory_row and memory_row["recent_decision"] else None,
                            module_summary.currentState if module_summary else None,
                            *[item.eventLineName for item in module_tasks],
                        ], "最近关键决策仍待补充。"),
                        nextStep=_strategic_first_non_empty([
                            str(memory_row["next_step"]).strip() if memory_row and memory_row["next_step"] else None,
                            module_summary.nextCriticalMove if module_summary else None,
                            *[item.projectContext.nextAction for item in module_tasks if item.projectContext],
                        ], "先把下一步动作拆清楚，再进入会谈推进。"),
                        momentum=momentum,
                        evidence=_strategic_unique_non_empty([
                            module_summary.whatHappenedThisWeek if module_summary else None,
                            flow.description if flow else None,
                            *(_parse_json_list(memory_row["evidence_refs_json"])[:2] if memory_row and memory_row["evidence_refs_json"] else []),
                            module_tasks[0].title if module_tasks else None,
                            module_tasks[1].title if len(module_tasks) > 1 else None,
                        ])[:3],
                        memoryConfidence=float(memory_row["confidence"] or 0.0) if memory_row else None,
                        predictionReadiness=float(memory_row["prediction_readiness"] or 0.0) if memory_row else None,
                        clarificationNeeds=_parse_json_list(memory_row["clarification_needs_json"]) if memory_row and memory_row["clarification_needs_json"] else [],
                    )
                )
        else:
            for item in review_event_line_summaries[:6]:
                memory_row = event_line_memory_rows.get(item.eventLineId)
                strategic_lines.append(
                    StrategicLineRecord(
                        id=_strategic_line_id(item.title, item.moduleName, item.flowName),
                        title=item.title,
                        summary=_strategic_first_non_empty([
                            str(memory_row["current_work"]).strip() if memory_row and memory_row["current_work"] else None,
                            item.whatThisLineIs,
                        ], "当前还缺稳定战略线。"),
                        module=item.moduleName,
                        flow=item.flowName,
                        stage=str(memory_row["current_stage"]).strip() if memory_row and memory_row["current_stage"] else None,
                        blocker=_strategic_first_non_empty([
                            str(memory_row["current_blocker"]).strip() if memory_row and memory_row["current_blocker"] else None,
                            item.mainBlocker,
                        ], "当前阻塞仍待澄清。"),
                        decision=_strategic_first_non_empty([
                            str(memory_row["recent_decision"]).strip() if memory_row and memory_row["recent_decision"] else None,
                            item.currentState,
                        ], "当前状态仍待澄清。"),
                        nextStep=_strategic_first_non_empty([
                            str(memory_row["next_step"]).strip() if memory_row and memory_row["next_step"] else None,
                            item.nextCriticalMove,
                        ], "先补下一步动作。"),
                        momentum="暂停" if item.status == "blocked" else "收口" if item.status == "done" else "加码" if item.predictionReadiness == "strong_forecast" else "稳住",
                        evidence=_strategic_unique_non_empty([
                            item.whatHappenedThisWeek,
                            *item.evidencePreview[:2],
                            *(_parse_json_list(memory_row["evidence_refs_json"])[:2] if memory_row and memory_row["evidence_refs_json"] else []),
                        ])[:3],
                        memoryConfidence=float(memory_row["confidence"] or 0.0) if memory_row else None,
                        predictionReadiness=float(memory_row["prediction_readiness"] or 0.0) if memory_row else None,
                        clarificationNeeds=_parse_json_list(memory_row["clarification_needs_json"]) if memory_row and memory_row["clarification_needs_json"] else [],
                    )
                )
        if not strategic_lines:
            for event_line in linked_event_lines[:6]:
                memory_row = event_line_memory_rows.get(event_line.id)
                momentum: Literal["加码", "稳住", "收口", "暂停"] = (
                    "暂停"
                    if event_line.status == "blocked"
                    else "收口"
                    if event_line.status == "done"
                    else "加码"
                    if memory_row and float(memory_row["prediction_readiness"] or 0.0) >= 0.72
                    else "稳住"
                )
                strategic_lines.append(
                    StrategicLineRecord(
                        id=_strategic_line_id(event_line.name, event_line.primaryClientName, None),
                        title=event_line.name,
                        summary=_strategic_first_non_empty(
                            [
                                str(memory_row["current_work"]).strip() if memory_row and memory_row["current_work"] else None,
                                event_line.summary,
                                event_line.intent,
                            ],
                            "当前还缺这条业务线的稳定摘要。",
                        ),
                        module=event_line.primaryClientName,
                        flow=None,
                        stage=str(memory_row["current_stage"]).strip() if memory_row and memory_row["current_stage"] else event_line.stage,
                        blocker=_strategic_first_non_empty(
                            [
                                str(memory_row["current_blocker"]).strip() if memory_row and memory_row["current_blocker"] else None,
                                event_line.currentBlocker,
                            ],
                            "当前阻塞仍待澄清。",
                        ),
                        decision=_strategic_first_non_empty(
                            [
                                str(memory_row["recent_decision"]).strip() if memory_row and memory_row["recent_decision"] else None,
                                event_line.recentDecision,
                            ],
                            "最近关键决策仍待补充。",
                        ),
                        nextStep=_strategic_first_non_empty(
                            [
                                str(memory_row["next_step"]).strip() if memory_row and memory_row["next_step"] else None,
                                event_line.nextStep,
                            ],
                            "先补下一步动作。",
                        ),
                        momentum=momentum,
                        evidence=_strategic_unique_non_empty(
                            [
                                *(_parse_json_list(memory_row["evidence_refs_json"])[:3] if memory_row and memory_row["evidence_refs_json"] else []),
                                event_line.intent,
                            ]
                        )[:3],
                        memoryConfidence=float(memory_row["confidence"] or 0.0) if memory_row else None,
                        predictionReadiness=float(memory_row["prediction_readiness"] or 0.0) if memory_row else None,
                        clarificationNeeds=_parse_json_list(memory_row["clarification_needs_json"]) if memory_row and memory_row["clarification_needs_json"] else [],
                    )
                )

        linked_event_line_memories = [
            response.eventLineMemorySnapshot
            for line in linked_event_lines[:8]
            for response in [get_event_line_memory_response(state.db, line.id)]
            if response.eventLineMemorySnapshot is not None
        ]

        direction_calibrated = bool(workspace.goals or strategic_lines or (review_analysis and review_analysis.nextWeekFocus))
        direction_score = (30 if workspace.goals else 0) + (25 if strategic_lines else 0) + (25 if any(task.projectContext and task.projectContext.currentFocus for task in client_tasks) else 0) + (20 if review_analysis and review_analysis.nextWeekFocus else 0)
        carrying_calibrated = bool(workspace.projectModules or workspace.projectFlows or analyzable_tasks)
        carrying_score = (25 if workspace.projectModules else 0) + (25 if workspace.projectFlows else 0) + (20 if any(task.ownerName.strip() for task in client_tasks) else 0) + (30 if len(blocked_tasks) <= max(1, (len(client_tasks) + 1) // 2) else 10)
        collaboration_calibrated = bool(workspace.meetings or any(task.collaborators for task in client_tasks) or review_risk_cards)
        collaboration_score = (25 if workspace.meetings else 0) + (25 if any(task.collaborators for task in client_tasks) else 0) + (10 if any(item.riskType == "collaboration_friction" for item in review_risk_cards) else 25) + (25 if review_event_line_summaries else 10)
        decision_calibrated = bool(workspace.meetings or review_risk_cards or review_completeness or workspace.analysisRuns)
        decision_score = (25 if recent_meeting else 0) + (10 if any(item.riskType == "decision_lag" for item in review_risk_cards) else 30) + (25 if any(item.status in {"forecast_ready", "high_confidence"} for item in review_completeness) else 10) + (20 if recent_analysis else 10)
        deposition_calibrated = bool(workspace.dnaModules or workspace.documentCards or workspace.analysisRuns or client_tasks)
        deposition_score = (25 if any(item.hasDocument for item in workspace.dnaModules) else 0) + (25 if len(workspace.documentCards) >= 3 else 15 if workspace.documentCards else 0) + (20 if workspace.analysisRuns else 0) + (30 if workspace.knowledgeStatus and workspace.knowledgeStatus.reviewPendingDocuments == 0 else 15)

        health = [
            StrategicHealthLineRecord(
                key="direction",
                title="方向健康",
                status=_strategic_health_status(direction_score, calibrated=direction_calibrated),
                trend="正在收敛" if workspace.goals and strategic_lines else "待校准",
                summary="目标、任务与当前业务主线已经开始对齐。" if workspace.goals else "当前业务仍缺少足够清晰的阶段锚点。",
                evidence=_strategic_unique_non_empty([workspace.goals[0].title if workspace.goals else None, strategic_lines[0].title if strategic_lines else None, review_analysis.nextWeekFocus[0] if review_analysis and review_analysis.nextWeekFocus else None])[:3],
            ),
            StrategicHealthLineRecord(
                key="carrying",
                title="承接健康",
                status=_strategic_health_status(carrying_score, calibrated=carrying_calibrated),
                trend="结构在变清楚" if workspace.projectModules and workspace.projectFlows else "承接位不足",
                summary="业务已经开始落到模块与流程。" if workspace.projectModules else "还缺稳定模块，经营动作容易只停留在会议和任务表层。",
                evidence=_strategic_unique_non_empty([workspace.projectModules[0].name if workspace.projectModules else None, workspace.projectFlows[0].name if workspace.projectFlows else None, active_task.title if active_task else None])[:3],
            ),
            StrategicHealthLineRecord(
                key="collaboration",
                title="协同健康",
                status=_strategic_health_status(collaboration_score, calibrated=collaboration_calibrated),
                trend="有会谈节律" if workspace.meetings else "协同节律偏弱",
                summary="当前已有跨人协作推进。" if any(task.collaborators for task in client_tasks) else "关键事项仍更多依赖单点推进。",
                evidence=_strategic_unique_non_empty([recent_meeting.title if recent_meeting else None, next((task.title for task in client_tasks if task.collaborators), None), next((item.statement for item in review_risk_cards if item.riskType == "collaboration_friction"), None)])[:3],
            ),
            StrategicHealthLineRecord(
                key="decision",
                title="决策健康",
                status=_strategic_health_status(decision_score, calibrated=decision_calibrated),
                trend="拍板偏慢" if any(item.riskType == "decision_lag" for item in review_risk_cards) else "决策节奏可用",
                summary="存在关键问题未被及时拍板。" if any(item.riskType == "decision_lag" for item in review_risk_cards) else "当前尚未观察到显著决策拖延。",
                evidence=_strategic_unique_non_empty([next((item.statement for item in review_risk_cards if item.riskType == "decision_lag"), None), recent_meeting.title if recent_meeting else None, recent_analysis.question if recent_analysis else None])[:3],
            ),
            StrategicHealthLineRecord(
                key="deposition",
                title="沉淀健康",
                status=_strategic_health_status(deposition_score, calibrated=deposition_calibrated),
                trend="证据在变厚" if workspace.documentCards else "底稿偏薄",
                summary="资料、分析与 DNA 已开始形成可复用底座。" if workspace.documentCards else "还没有形成足够稳定的资料沉淀与分析层。",
                evidence=_strategic_unique_non_empty([next((item.title for item in workspace.dnaModules if item.hasDocument), None), workspace.documentCards[0].title if workspace.documentCards else None, recent_analysis.question if recent_analysis else None])[:3],
            ),
        ]

        ambiguity_rows = state.db.fetchall(
            """
            SELECT a.raw_text, m.title AS meeting_title
            FROM ambiguities a
            JOIN meetings m ON m.id = a.meeting_id
            WHERE m.client_id = ? AND a.status = 'pending'
            ORDER BY m.updated_at DESC
            LIMIT 4
            """,
            (client_id,),
        )
        clarify_items_records = [
            *[
                StrategicChecklistItemRecord(
                    title=f"{item.title}：{slot.label}待澄清",
                    detail=slot.summary,
                    source="周复盘 / 事件线完整度",
                    priority="high" if slot.key in {"blocker", "next_action"} else "medium",
                )
                for item in review_completeness
                for slot in item.slots
                if slot.recommendedFix == "clarify_now" and slot.coverage != "full"
            ],
            *[
                StrategicChecklistItemRecord(
                    title=f"{module.title}：补充关键背景",
                    detail=missing,
                    source="客户 DNA 缺口",
                    priority="medium",
                )
                for module in workspace.dnaModules
                for missing in module.missingInfo
            ],
        ]
        if not workspace.projectModules:
            clarify_items_records.append(StrategicChecklistItemRecord(title="当前业务线还缺稳定模块定义", detail="建议在周会上先确认：这条业务到底按哪几个模块来看，而不是继续按零散事项推进。", source="项目结构缺口", priority="high"))
        if background_thin_tasks:
            clarify_items_records.append(StrategicChecklistItemRecord(title="关系推进任务需要补背景说明", detail=f"当前有 {len(background_thin_tasks)} 条任务只写了动作名。请在任务描述里补对象是谁、当前关系、这次动作想推动什么。", source="任务描述缺口", priority="high"))
        clarify_items_records = list({f"{item.title}::{item.detail}": item for item in clarify_items_records}.values())[:8]

        decision_items_records = [
            *([StrategicChecklistItemRecord(title="拍板：本周期这条业务到底只抓什么", detail="先定一个主问题，再决定这条业务按哪些模块和流程推进；否则战略页只能继续堆事实，不能形成判断。", source="经营结构缺口", priority="high")] if readiness_status == "insufficient" else []),
            *[
                StrategicChecklistItemRecord(
                    title=f"拍板：{item.title}",
                    detail=item.statement,
                    source="周复盘风险卡",
                    priority=_strategic_priority(item.probability),
                )
                for item in review_risk_cards
                if item.riskType in {"decision_lag", "goal_drift"}
            ],
            *[
                StrategicChecklistItemRecord(
                    title=f"拍板：{_strategic_truncate(str(row['meeting_title']), 20)}",
                    detail=str(row["raw_text"]),
                    source="会议待澄清项",
                    priority="high",
                )
                for row in ambiguity_rows
            ],
            *[
                StrategicChecklistItemRecord(
                    title=f"拍板：{task.title}",
                    detail=task.projectContext.currentBlocker if task.projectContext and task.projectContext.currentBlocker else (task.desc or "这条推进链还缺关键拍板。"),
                    source="任务推进阻塞",
                    priority="medium",
                )
                for task in blocked_tasks[:2]
            ],
        ]
        decision_items_records = list({f"{item.title}::{item.detail}": item for item in decision_items_records}.values())[:5]

        material_items_records = [
            *[
                StrategicChecklistItemRecord(
                    title=f"{item.title}：补充资料",
                    detail=slot.summary,
                    source="周复盘资料缺口",
                    priority="medium",
                )
                for item in review_completeness
                for slot in item.slots
                if slot.recommendedFix == "upload_docs" and slot.coverage != "full"
            ],
            *([StrategicChecklistItemRecord(title="复核待确认资料", detail=f"当前仍有 {workspace.knowledgeStatus.reviewPendingDocuments} 份资料待复核，会影响经营判断置信度。", source="知识状态", priority="medium")] if workspace.knowledgeStatus and workspace.knowledgeStatus.reviewPendingDocuments else []),
            *([StrategicChecklistItemRecord(title="为关系推进任务补背景", detail="以后凡是“吃饭 / 见面 / 介绍 / 合作推进”类任务，都要在描述里补对象背景、合作关系和预期结果。", source="任务描述规范", priority="high")] if background_thin_tasks else []),
        ]
        material_items_records = list({f"{item.title}::{item.detail}": item for item in material_items_records}.values())[:6]

        asset_candidates = [
            *[
                StrategicAssetCandidateRecord(
                    title=item.title,
                    source="资料卡",
                    summary=_strategic_truncate(item.shortSummary or item.retrievalSummary or item.summary, 80),
                    nextAction=item.coreQuestions[0] if item.coreQuestions else item.queryHints[0] if item.queryHints else "继续抽出一版稳定摘要或模板。",
                )
                for item in workspace.documentCards[:3]
            ],
            *[
                StrategicAssetCandidateRecord(
                    title=_strategic_truncate(item.question, 42),
                    source="分析运行",
                    summary=f"当前状态 {item.status}，已有 {len(item.evidenceSummary.evidenceList)} 条证据命中。",
                    nextAction="从这次分析里抽一版可复用的方法、框架或顾问判断模板。",
                )
                for item in workspace.analysisRuns[:2]
            ],
            *([StrategicAssetCandidateRecord(title=recent_meeting.title, source="会议", summary=f"最近会谈更新于 {_strategic_format_date_label(recent_meeting.updatedAt)}。", nextAction="把会谈里有效的问题结构沉淀成下次可复用的共创议程。")] if recent_meeting else []),
        ]
        asset_candidates = list({item.title: item for item in asset_candidates}.values())[:6]

        facts_group_items = [
            *([StrategicChecklistItemRecord(title="同步最近会议变化", detail=f"最近会议是“{recent_meeting.title}”，更新时间 {_strategic_format_date_label(recent_meeting.updatedAt)}。", source="会议", priority="low")] if recent_meeting else []),
            *([StrategicChecklistItemRecord(title="同步最近分析主题", detail=f"最近分析围绕“{_strategic_truncate(recent_analysis.question, 36)}”，状态 {recent_analysis.status}。", source="分析运行", priority="low")] if recent_analysis else []),
            *([StrategicChecklistItemRecord(title="同步当前业务锚点", detail=f"当前最明确的目标是“{workspace.goals[0].title}”。", source="目标", priority="low")] if workspace.goals else []),
            *([StrategicChecklistItemRecord(title="同步当前推进动作", detail=f"当前最活跃的动作是“{active_task.title}”，状态 {active_task.status}。", source="任务", priority="low")] if active_task else []),
        ][:5]
        observe_group_items = [
            *[
                StrategicChecklistItemRecord(
                    title=f"观察：{item.title}",
                    detail=item.ifIgnored,
                    source="风险卡",
                    priority=_strategic_priority(item.probability),
                )
                for item in review_risk_cards[:2]
            ],
            *[
                StrategicChecklistItemRecord(
                    title=f"观察：{item.title}",
                    detail=item.recommendedAmplifier,
                    source="机会卡",
                    priority="medium" if item.confidence == "high" else "low",
                )
                for item in review_opportunity_cards[:2]
            ],
        ][:5]
        meeting_pack_groups = [
            StrategicChecklistGroupRecord(key="facts", title="先同步的事实", description="先把真正改变业务状态的事实说清楚，再进入判断。", items=facts_group_items),
            StrategicChecklistGroupRecord(key="clarify", title="必须澄清的问题", description="这些未知项不问清楚，会直接拖低判断质量。", items=clarify_items_records),
            StrategicChecklistGroupRecord(key="decision", title="必须拍板的事项", description="这些地方不拍板，下周推进大概率会继续卡住。", items=decision_items_records),
            StrategicChecklistGroupRecord(key="material", title="必须补的资料", description="这些材料不是锦上添花，而是判断证据缺口。", items=material_items_records),
            StrategicChecklistGroupRecord(key="asset", title="必须沉淀的资产", description="这条业务除了要往前推，也要给益语留下可复用能力。", items=[StrategicChecklistItemRecord(title=item.title, detail=item.nextAction, source=item.source, priority="medium" if item.source != "分析运行" else "high") for item in asset_candidates[:3]]),
            StrategicChecklistGroupRecord(key="observe", title="下周观察点", description="这些信号会决定局面是在转好，还是在继续失衡。", items=observe_group_items),
        ]
        meeting_pack_agenda = _strategic_unique_non_empty([
            f"先对齐主矛盾：{headline.mainContradiction.value}",
            f"再确认核心突破：{headline.coreBreakthrough.value}",
            f"重点澄清：{clarify_items_records[0].title}" if clarify_items_records else None,
            f"重点拍板：{decision_items_records[0].title}" if decision_items_records else None,
            "补关系推进任务背景：对象是谁、当前关系、推进目标分别是什么" if background_thin_tasks else None,
        ])[:4]

        two_week_changes: list[StrategicChangePointRecord] = []
        if readiness_status == "insufficient":
            two_week_changes.append(StrategicChangePointRecord(title="当前不做经营预测", summary="当前先不输出经营预测。现在最有价值的不是猜下周会怎样，而是把能支撑判断的结构化信号补出来。", confidence="等待更多信号", signals=readiness_gaps[:3]))
        else:
            if review_risk_cards:
                risk = review_risk_cards[0]
                two_week_changes.append(StrategicChangePointRecord(title=f"如果 {risk.title} 不补", summary=f"如果当前阻塞不拆，2 周内最可能 {risk.ifIgnored}", confidence="中等置信" if risk.probability == "high" else "保守判断", signals=_strategic_unique_non_empty([risk.whyNow, *risk.triggerSignals[:2]])[:3]))
            if review_opportunity_cards:
                opportunity = review_opportunity_cards[0]
                two_week_changes.append(StrategicChangePointRecord(title=f"如果 {opportunity.title} 被放大", summary=f"如果相关动作被拍板并继续推进，这条线最可能转向 {opportunity.upside}", confidence="中等置信" if opportunity.confidence == "high" else "观察中", signals=_strategic_unique_non_empty([*opportunity.supportingSignals[:2], opportunity.recommendedAmplifier])[:3]))
            if workspace.knowledgeStatus and workspace.knowledgeStatus.reviewPendingDocuments:
                two_week_changes.append(StrategicChangePointRecord(title="如果关键资料继续不补", summary=f"如果这 {workspace.knowledgeStatus.reviewPendingDocuments} 份待复核资料继续悬空，接下来两周很多判断都会停在保守层。", confidence="高依赖资料", signals=["待复核资料数量偏多", "证据链稳定性不足"]))
        two_week_changes = two_week_changes[:3]
        approved_judgments = [
            item for item in list_judgment_versions(
                state.db,
                client_id,
                limit=6,
                minimum_authority="approved",
                include_fallback=False,
            )
            if item.status == "approved"
        ]
        approved_dna_deltas = [
            item.model_dump(mode="json")
            for item in list_dna_deltas(state.db, client_id, limit=6)
            if item.status == "approved"
        ]
        resolved_conflicts = [
            item.model_dump(mode="json")
            for item in cockpit_projection.latest_conflicts
            if item.resolutionStatus == "approved"
        ]
        candidate_judgments: list[dict[str, object]] = []
        if cockpit_projection.judgment_bundle and cockpit_projection.judgment_bundle.baselineJudgment:
            baseline = cockpit_projection.judgment_bundle.baselineJudgment
            if baseline.authorityLevel != "approved":
                candidate_judgments.append(baseline.model_dump(mode="json"))
        if cockpit_projection.judgment_bundle:
            for item in cockpit_projection.judgment_bundle.overlayDeltas:
                if item.authorityLevel == "approved":
                    continue
                dumped = item.model_dump(mode="json")
                if dumped not in candidate_judgments:
                    candidate_judgments.append(dumped)
        high_severity_conflicts = [
            item.model_dump(mode="json")
            for item in cockpit_projection.latest_conflicts
            if item.severity == "high" and item.resolutionStatus != "approved"
        ]
        radar_open_questions = [
            item.model_dump(mode="json")
            for item in cockpit_projection.latest_open_questions
            if item.status in {"draft", "awaiting_review", "awaiting_revision"}
        ]
        radar_review_signals: list[dict[str, object]] = []
        if candidate_review_sla["overdueCount"] > 0:
            radar_review_signals.append(
                {
                    "level": "overdue",
                    "count": candidate_review_sla["overdueCount"],
                    "summary": f"有 {candidate_review_sla['overdueCount']} 条候选对象超过 {candidate_review_sla['overdueAfterHours']} 小时未处理。",
                }
            )
        if candidate_review_sla["warningCount"] > 0:
            radar_review_signals.append(
                {
                    "level": "warning",
                    "count": candidate_review_sla["warningCount"],
                    "summary": f"有 {candidate_review_sla['warningCount']} 条候选对象超过 {candidate_review_sla['warningAfterHours']} 小时待处理。",
                }
            )
        official_baseline = next(
            (
                item.model_dump(mode="json")
                for item in approved_judgments
                if item.targetType == "client" and item.targetId == client_id
            ),
            approved_judgments[0].model_dump(mode="json") if approved_judgments else None,
        )
        official_layer = {
            "officialBaseline": official_baseline,
            "approvedDnaDeltas": approved_dna_deltas,
            "resolvedConflicts": resolved_conflicts,
        }
        radar_layer = {
            "candidateJudgments": candidate_judgments,
            "highSeverityConflicts": high_severity_conflicts,
            "openQuestions": radar_open_questions,
            "reviewSignals": radar_review_signals,
        }
        official_layer_status: Literal["ready", "empty"] = "ready" if any(
            (
                official_layer["officialBaseline"],
                official_layer["approvedDnaDeltas"],
                official_layer["resolvedConflicts"],
            )
        ) else "empty"
        official_empty_reason = None if official_layer_status == "ready" else "当前暂无已批准判断"
        if official_layer_status == "empty" and not any(
            (
                week_summary_confirmed,
                main_contradiction_confirmed,
                core_breakthrough_confirmed,
                snapshot_focus_items,
            )
        ):
            headline = StrategicHeadlineRecord(
                weekSummary=StrategicJudgmentRecord(
                    value="当前暂无已批准判断",
                    status="waiting",
                    sources=["以下仅展示候选信号与风险雷达"],
                ),
                mainContradiction=StrategicJudgmentRecord(
                    value="以下内容仅供排查，不代表正式结论",
                    status="waiting",
                    sources=["候选 judgment 与风险雷达"],
                ),
                coreBreakthrough=StrategicJudgmentRecord(
                    value="请先完成审批或补齐证据，再形成正式判断",
                    status="waiting",
                    sources=["当前官方层为空"],
                ),
                focusItems=focus_items_auto,
                focusStatus="waiting",
                freshness=freshness,
            )

        return StrategicCockpitSnapshotRecord(
            clientId=client_id,
            clientName=client.name,
            clientTagline=" · ".join(_strategic_unique_non_empty([client.type, client.domain])) or "业务发展驾驶台",
            stageLabel=notebook_stage or client.stage or "待判断",
            permission=permission,
            readiness=readiness,
            headline=headline,
            health=health,
            strategicLines=strategic_lines[:6],
            twoWeekChanges=two_week_changes,
            pendingDecisions=decision_items_records[:3],
            pendingMaterials=material_items_records[:3],
            meetingPackDraft=StrategicMeetingPackDraftRecord(title=f"{client.name} 周盘点会", agenda=meeting_pack_agenda, groups=meeting_pack_groups),
            evidencePreview=StrategicEvidencePreviewRecord(summary=dossier_summary, cards=dossier_cards, boundaries=dossier_boundaries, keyFacts=key_facts, keyWarnings=key_warnings),
            assetCandidates=asset_candidates,
            officialLayer=official_layer,
            radarLayer=radar_layer,
            officialLayerStatus=official_layer_status,
            officialEmptyReason=official_empty_reason,
            resolutionTrace=cockpit_projection.latest_resolution_trace.model_dump(mode="json") if cockpit_projection.latest_resolution_trace else {},
            notebookSummary=notebook_summary,
            memoryStatus=memory_status,
            linkedEventLineMemories=linked_event_line_memories,
        )

    def save_strategic_cockpit_snapshot(client_id: str, payload: StrategicCockpitConfirmPayload, session_user: SessionUserRecord) -> None:
        existing = _load_strategic_snapshot_row(client_id)
        focus_items = _strategic_unique_non_empty([item for item in payload.focusItems])[:3]
        week_summary = (payload.weekSummary or "").strip()
        main_contradiction = (payload.mainContradiction or "").strip()
        core_breakthrough = (payload.coreBreakthrough or "").strip()
        if not week_summary and not main_contradiction and not core_breakthrough and not focus_items:
            state.db.execute("DELETE FROM strategic_cockpit_snapshots WHERE client_id = ?", (client_id,))
            return
        created_at = str(existing["created_at"]) if existing and existing["created_at"] else now_iso()
        state.db.execute(
            """
            INSERT INTO strategic_cockpit_snapshots(
                client_id, week_summary, main_contradiction, core_breakthrough, focus_items_json,
                confirmed_by_user_id, confirmed_by_user_name, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                week_summary = excluded.week_summary,
                main_contradiction = excluded.main_contradiction,
                core_breakthrough = excluded.core_breakthrough,
                focus_items_json = excluded.focus_items_json,
                confirmed_by_user_id = excluded.confirmed_by_user_id,
                confirmed_by_user_name = excluded.confirmed_by_user_name,
                updated_at = excluded.updated_at
            """,
            (
                client_id,
                week_summary,
                main_contradiction,
                core_breakthrough,
                to_json(focus_items),
                session_user.id,
                session_user.fullName,
                created_at,
                now_iso(),
            ),
        )

    def _render_strategic_meeting_pack_text(snapshot: StrategicCockpitSnapshotRecord) -> str:
        lines: list[str] = [snapshot.meetingPackDraft.title, ""]
        if snapshot.meetingPackDraft.agenda:
            lines.append("建议议程")
            for item in snapshot.meetingPackDraft.agenda:
                lines.append(f"- {item}")
            lines.append("")
        for group in snapshot.meetingPackDraft.groups:
            lines.append(group.title)
            lines.append(group.description)
            for item in group.items:
                lines.append(f"- {item.title}")
                lines.append(f"  说明：{item.detail}")
                lines.append(f"  来源：{item.source}")
            lines.append("")
        return "\n".join(lines).strip()

    def _require_strategic_ceo() -> SessionUserRecord:
        session_user = get_cached_session_user()
        if session_user is None:
            session_user = require_session_user()
        org_model_profile = _load_org_model_profile_safe()
        leader_user_id = org_model_profile.organization.leaderUserId if org_model_profile else None
        if not leader_user_id:
            raise HTTPException(status_code=403, detail="请先在组织设置中确认 CEO 账号")
        if session_user.id != leader_user_id:
            raise HTTPException(status_code=403, detail="当前页面只有 CEO 可以确认经营判断")
        return session_user

    def _create_strategic_meeting_pack(client_id: str) -> MeetingDetail:
        snapshot = build_strategic_cockpit_snapshot(client_id)
        meeting_id = new_id("meeting")
        timestamp = now_iso()
        notes_text = _render_strategic_meeting_pack_text(snapshot)
        state.db.execute(
            """
            INSERT INTO meetings(id, client_id, title, stage, scheduled_at, transcript_text, notes, created_at, updated_at)
            VALUES(?, ?, ?, 'prepared', NULL, '', ?, ?, ?)
            """,
            (meeting_id, client_id, snapshot.meetingPackDraft.title, notes_text, timestamp, timestamp),
        )
        for index, agenda_item in enumerate(snapshot.meetingPackDraft.agenda[:8]):
            state.db.execute(
                "INSERT INTO agenda_items(id, meeting_id, title, description, sort_order) VALUES(?, ?, ?, ?, ?)",
                (new_id("agenda"), meeting_id, agenda_item[:80], "战略陪伴周会清单议程", index),
            )
        state.db.execute(
            "INSERT INTO meeting_sources(id, meeting_id, title, content_text, created_at) VALUES(?, ?, ?, ?, ?)",
            (new_id("ms"), meeting_id, "战略陪伴周会清单草案", notes_text, timestamp),
        )
        log_activity("meeting.prepare_from_strategic_cockpit", "meeting", meeting_id, {"clientId": client_id, "agendaItems": len(snapshot.meetingPackDraft.agenda)})
        return build_meeting_detail(meeting_id)

    def _build_strategic_payload_from_meeting(client_id: str, meeting: MeetingDetail) -> StrategicCockpitConfirmPayload:
        current_snapshot = build_strategic_cockpit_snapshot(client_id)
        note_lines = [
            line.strip(" -\t")
            for line in (meeting.notes or "").splitlines()
            if line.strip() and "建议议程" not in line and "来源：" not in line and "说明：" not in line and line.strip() not in {
                meeting.title,
                "先同步的事实",
                "必须澄清的问题",
                "必须拍板的事项",
                "必须补的资料",
                "必须沉淀的资产",
                "下周观察点",
            }
        ]
        week_summary = _strategic_first_non_empty(
            [
                meeting.decisions[0].summary if meeting.decisions else None,
                note_lines[0] if note_lines else None,
                current_snapshot.headline.weekSummary.value,
            ],
            current_snapshot.headline.weekSummary.value,
        )
        main_contradiction = _strategic_first_non_empty(
            [
                meeting.ambiguities[0].rawText if meeting.ambiguities else None,
                meeting.risks[0].summary if meeting.risks else None,
                current_snapshot.headline.mainContradiction.value,
            ],
            current_snapshot.headline.mainContradiction.value,
        )
        core_breakthrough = _strategic_first_non_empty(
            [
                meeting.actionItems[0].title if meeting.actionItems else None,
                meeting.decisions[0].summary if meeting.decisions else None,
                current_snapshot.headline.coreBreakthrough.value,
            ],
            current_snapshot.headline.coreBreakthrough.value,
        )
        focus_items = _strategic_unique_non_empty(
            [
                *[item.title for item in meeting.actionItems[:3]],
                *[item.title for item in meeting.agendaItems[:2]],
                *current_snapshot.headline.focusItems,
            ]
        )[:3]
        return StrategicCockpitConfirmPayload(
            weekSummary=week_summary,
            mainContradiction=main_contradiction,
            coreBreakthrough=core_breakthrough,
            focusItems=focus_items,
        )

    def fetch_chat_thread_for_client(client_id: str, thread_id: str) -> ChatThread:
        row = state.db.fetchone(
            "SELECT * FROM chat_threads WHERE id = ? AND client_id = ?",
            (thread_id, client_id),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        return ChatThread(
            id=str(row["id"]),
            clientId=str(row["client_id"]),
            title=str(row["title"]),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def list_chat_messages_for_thread(client_id: str, thread_id: str) -> list[ChatMessageRecord]:
        fetch_chat_thread_for_client(client_id, thread_id)
        return [
            build_chat_message(row)
            for row in state.db.fetchall(
                """
                SELECT m.*
                FROM chat_messages m
                JOIN chat_threads t ON t.id = m.thread_id
                WHERE t.client_id = ? AND m.thread_id = ?
                ORDER BY m.created_at ASC
                """,
                (client_id, thread_id),
            )
        ]

    def build_chat_message(row) -> ChatMessageRecord:
        structured = from_json(row["structured_data_json"], None)
        data = AiStructuredResponse(**structured) if structured else None
        evidence_data = from_json(row["evidence_json"], [])
        evidence = [EvidenceItem(**item) for item in evidence_data] if isinstance(evidence_data, list) else []
        raw_status = str(row["status"] or "").strip().lower()
        normalized_status = "loading" if raw_status == "loading" else "success"
        retrieval_summary = from_json(row["retrieval_summary_json"], {})
        timing = from_json(row["timing_json"], {})
        state_sources = [
            str(item).strip()
            for item in retrieval_summary.get("stateSources", [])
            if str(item).strip()
        ] if isinstance(retrieval_summary, dict) and isinstance(retrieval_summary.get("stateSources"), list) else []
        boundary_notes = [
            str(item).strip()
            for item in retrieval_summary.get("boundaryNotes", [])
            if str(item).strip()
        ] if isinstance(retrieval_summary, dict) and isinstance(retrieval_summary.get("boundaryNotes"), list) else []
        state_confidence_raw = str(retrieval_summary.get("stateConfidence") or "").strip() if isinstance(retrieval_summary, dict) else ""
        state_confidence = state_confidence_raw if state_confidence_raw in {"low", "medium", "high"} else None
        fallback_reason = str(retrieval_summary.get("fallbackReason") or "").strip() if isinstance(retrieval_summary, dict) else ""
        fallback_presentation_mode_raw = str(retrieval_summary.get("fallbackPresentationMode") or "").strip() if isinstance(retrieval_summary, dict) else ""
        fallback_presentation_mode = (
            fallback_presentation_mode_raw
            if fallback_presentation_mode_raw in {"state_cards_only", "compact_user_answer", "full_answer"}
            else None
        )
        retrieval_decision_reason_raw = str(retrieval_summary.get("retrievalDecisionReason") or "").strip() if isinstance(retrieval_summary, dict) else ""
        retrieval_decision_reason = (
            retrieval_decision_reason_raw
            if retrieval_decision_reason_raw in {
                "state_first_default",
                "document_drilldown_requested",
                "search_cache_requested",
                "intro_query_needs_evidence",
                "identity_query_needs_evidence",
                "project_intro_needs_evidence",
                "meeting_summary_needs_evidence",
                "next_actions_needs_evidence",
                "evidence_question_needs_evidence",
                "official_registry_requested",
                "status_progress_needs_hybrid_evidence",
                "default_hybrid_evidence",
                "state_pool_insufficient",
                "state_pool_empty",
            }
            else None
        )
        answer_intent_raw = str(retrieval_summary.get("answerIntent") or "").strip() if isinstance(retrieval_summary, dict) else ""
        answer_intent = (
            answer_intent_raw
            if answer_intent_raw in {
                "intro_profile",
                "project_intro",
                "meeting_summary",
                "next_actions",
                "official_judgment_registry",
                "evidence_question",
                "status_progress",
                "general",
            }
            else None
        )
        judgment_query_mode_raw = str(retrieval_summary.get("judgmentQueryMode") or "").strip() if isinstance(retrieval_summary, dict) else ""
        judgment_query_mode = (
            judgment_query_mode_raw
            if judgment_query_mode_raw in {"registry_only", "hybrid", "evidence_based_synthesis"}
            else None
        )
        evidence_support_mode_raw = str(retrieval_summary.get("evidenceSupportMode") or "").strip() if isinstance(retrieval_summary, dict) else ""
        evidence_support_mode = (
            evidence_support_mode_raw
            if evidence_support_mode_raw in {"none", "linked_state_evidence", "evidence_cards", "raw_doc_drilldown", "generic_retrieval_fallback"}
            else None
        )
        state_answer_sections = None
        if isinstance(retrieval_summary, dict) and isinstance(retrieval_summary.get("stateAnswerSections"), dict):
            try:
                state_answer_sections = StateAnswerSectionsRecord(**retrieval_summary["stateAnswerSections"])
            except Exception:
                state_answer_sections = None
        state_source_summary = None
        if isinstance(retrieval_summary, dict) and isinstance(retrieval_summary.get("stateSourceSummary"), dict):
            try:
                state_source_summary = StateSourceSummaryRecord(**retrieval_summary["stateSourceSummary"])
            except Exception:
                state_source_summary = None
        return ChatMessageRecord(
            id=str(row["id"]),
            threadId=str(row["thread_id"]),
            role=str(row["role"]),  # type: ignore[arg-type]
            content=str(row["content"]),
            createdAt=str(row["created_at"]),
            status=normalized_status,
            modelRoute=str(row["model_route"]) if row["model_route"] else None,
            llmInvoked=bool(row["llm_invoked"]),
            providerUsed=str(row["provider_used"]) if row["provider_used"] else None,
            answerMode=str(row["answer_mode"]) if row["answer_mode"] else None,  # type: ignore[arg-type]
            evidenceStatus=str(row["evidence_status"]) if row["evidence_status"] else None,  # type: ignore[arg-type]
            failureReason=str(row["failure_reason"]) if row["failure_reason"] else None,
            timing=timing if isinstance(timing, dict) else {},
            retrievalSummary=retrieval_summary if isinstance(retrieval_summary, dict) else {},
            structuredData=data,
            evidence=evidence,
            fallbackReason=fallback_reason or None,
            fallbackPresentationMode=fallback_presentation_mode,
            stateConfidence=state_confidence,
            stateSources=state_sources,
            boundaryNotes=boundary_notes,
            answerIntent=answer_intent,
            retrievalDecisionReason=retrieval_decision_reason,
            judgmentQueryMode=judgment_query_mode,
            evidenceSupportMode=evidence_support_mode,
            stateAnswerSections=state_answer_sections,
            stateSourceSummary=state_source_summary,
        )

    def build_meeting_summary(row) -> MeetingSummary:
        return MeetingSummary(
            id=str(row["id"]),
            clientId=str(row["client_id"]),
            title=str(row["title"]),
            stage=str(row["stage"]),  # type: ignore[arg-type]
            scheduledAt=str(row["scheduled_at"]) if row["scheduled_at"] else None,
            updatedAt=str(row["updated_at"]),
        )

    def build_meeting_detail(meeting_id: str) -> MeetingDetail:
        row = state.db.fetchone("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Meeting not found")
        agenda = [
            AgendaItem(id=str(item["id"]), title=str(item["title"]), description=str(item["description"]))
            for item in state.db.fetchall("SELECT * FROM agenda_items WHERE meeting_id = ? ORDER BY sort_order", (meeting_id,))
        ]
        decisions = [
            DecisionItem(id=str(item["id"]), summary=str(item["summary"]))
            for item in state.db.fetchall("SELECT * FROM decisions WHERE meeting_id = ? ORDER BY created_at", (meeting_id,))
        ]
        action_items = []
        for item in state.db.fetchall("SELECT * FROM action_items WHERE meeting_id = ? ORDER BY created_at", (meeting_id,)):
            action_items.append(
                TaskRecord(
                    id=str(item["id"]),
                    title=str(item["title"]),
                    desc="来自会议抽取的行动项",
                    status="todo" if item["publish_status"] == "published" else "inbox",
                    priority="normal",
                    listId="list-0",
                    listName="会议草稿",
                    listColor="#5B7BFE",
                    ddl=str(item["due_date"]),
                    ownerName=str(item["owner_name"]),
                    sourceType="meeting",
                    sourceId=str(meeting_id),
                    tags=[
                        TaskTagRecord(
                            id="tag_meeting_builtin",
                            name="会议",
                            color="#F59E0B",
                            scope="org",
                            ownerUserId=None,
                            createdBy="system",
                            updatedAt=str(item["created_at"]),
                            archivedAt=None,
                        )
                    ],
                    note=None,
                    createdAt=str(item["created_at"]),
                    updatedAt=str(item["created_at"]),
                )
            )
        risks = [
            RiskItem(
                id=str(item["id"]),
                summary=str(item["summary"]),
                severity="normal" if str(item["severity"] or "normal") == "medium" else str(item["severity"] or "normal"),
            )  # type: ignore[arg-type]
            for item in state.db.fetchall("SELECT * FROM risks WHERE meeting_id = ? ORDER BY created_at", (meeting_id,))
        ]
        ambiguities = [
            AmbiguityItem(
                id=str(item["id"]),
                rawText=str(item["raw_text"]),
                candidates=_parse_json_list(item["candidates_json"]),
                status=str(item["status"]),  # type: ignore[arg-type]
            )
            for item in state.db.fetchall("SELECT * FROM ambiguities WHERE meeting_id = ? ORDER BY created_at", (meeting_id,))
        ]
        return MeetingDetail(
            **build_meeting_summary(row).model_dump(),
            transcriptText=str(row["transcript_text"]),
            notes=str(row["notes"]),
            agendaItems=agenda,
            decisions=decisions,
            actionItems=action_items,
            risks=risks,
            ambiguities=ambiguities,
        )

    def select_evidence(client_id: str, prompt: str) -> list[EvidenceItem]:
        bundle = build_retrieval_bundle(client_id, prompt)
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
                retrievalStage={"master_index": "doc_index", "surrogate": "section_index"}.get(item.source_stage, item.source_stage),
                isFallback=item.source_stage in {"master_index", "doc_index"},
                matchedTerms=item.matched_terms,
            )
            for item in bundle.citations
        ]
        for goal in state.db.fetchall("SELECT * FROM goal_records WHERE client_id = ? ORDER BY updated_at DESC LIMIT 1", (client_id,)):
            evidence.append(
                EvidenceItem(
                    id=new_id("ev"),
                    title=f"目标：{goal['title']}",
                    excerpt=f"季度 {goal['quarter']}，进度 {goal['progress']}%，负责人 {goal['owner_name']}",
                    sourceType="goal",
                    coverage=bundle.coverage,
                    matchedTerms=[],
                )
            )
        return evidence[:4]

    def context_summary(client_id: str, prompt: str, evidence: list[EvidenceItem]) -> str:
        client = build_client_summary(client_id)
        dna_count = state.db.scalar("SELECT COUNT(1) AS count FROM dna_terms WHERE client_id = ?", (client_id,))
        dna_doc_count = state.db.scalar("SELECT COUNT(1) AS count FROM client_dna_documents WHERE client_id = ?", (client_id,))
        return (
            f"客户={client.name}/{client.domain}；当前阶段={client.stage}；"
            f"客户DNA文档={dna_doc_count}；组织补充词条={dna_count}"
        )

    def build_workspace_chat_state_context(client_id: str) -> str:
        workspace = workspace_for_client(client_id)
        state_pack = build_state_answer_context_pack(workspace, "客户状态总览")
        return state_pack.summary

    def build_chat_answer_context(
        client_id: str,
        prompt: str,
        evidence: list[EvidenceItem],
        retrieval_bundle,
        *,
        answer_intent: WorkspaceAnswerIntent | None = None,
        memory_background_context: str = "",
        workspace_state_context: str = "",
    ) -> str:
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
        resolved_intent = answer_intent or classify_workspace_chat_intent(prompt)
        evidence_limit = 20
        excerpt_limit = 1200
        evidence_char_budget = 18000
        if resolved_intent in {"intro_profile", "project_intro"}:
            evidence_limit = 14
            excerpt_limit = 900
            evidence_char_budget = 12000
        elif resolved_intent in {"meeting_summary", "next_actions"}:
            evidence_limit = 18
            excerpt_limit = 1000
            evidence_char_budget = 15000
        elif resolved_intent == "evidence_question":
            evidence_limit = 24
            excerpt_limit = 1400
            evidence_char_budget = 22000
        client_dna_context = build_client_dna_context(client_id, prompt)
        preferred_categories = [
            str(item)
            for item in retrieval_meta.get("preferredCategories", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("preferredCategories"), list) else []
        curated_evidence = select_high_signal_evidence(
            evidence,
            limit=evidence_limit,
            prompt=prompt,
            preferred_categories=preferred_categories,
        )
        evidence_blocks: list[str] = []
        evidence_char_used = 0
        for index, item in enumerate(curated_evidence, start=1):
            label = item.title
            if item.sectionLabel:
                label = f"{label} / {item.sectionLabel}"
            excerpt = re.sub(r"\s+", " ", item.excerpt or "").strip()
            block = (
                f"[原始证据 {index}]\n"
                f"标题：{label}\n"
                f"片段：{excerpt[:excerpt_limit]}"
            ).strip()
            if evidence_blocks and evidence_char_used + len(block) > evidence_char_budget:
                break
            evidence_blocks.append(block)
            evidence_char_used += len(block)
        client_name = build_client_summary(client_id).name
        should_include_state_context = bool(workspace_state_context) and resolved_intent in {
            "status_progress",
            "official_judgment_registry",
            "general",
        }
        summary_lines = [
            f"用户问题：{prompt}",
            f"当前对象：{client_name}",
            (
                "请像一位资深顾问那样，基于下面的原始材料回答问题。\n"
                "【深度要求——最重要】\n"
                "- 每个层次不能只给结论，必须用 2-4 段话展开讲为什么、具体怎么体现\n"
                "- 对于业务介绍：说清做什么、为什么有价值、怎么做、未来方向\n"
                "- 对于战略判断：说清从什么变到什么、为什么变、变的张力是什么\n"
                "- 默认写成 600-1200 字的完整回答；如果用户只要简介或会议摘要，优先保证可执行和清晰，不要凑长\n"
                "- 最后要有升华收束，把具体信息提升到战略意义层面\n\n"
                "【排版规则】\n"
                "- 用「一、二、三」分层，并列要点用「- 」列表\n"
                "- 只加粗完整判断句（如 **核心不是X而是Y**），不要只加粗单个关键词\n"
                "- 列表项之后可以跟解释段落，不要为了格式整齐而牺牲深度\n"
                "- 写完最后一个层次后，必须有总结收束\n\n"
                "【事实底线】\n"
                "- 允许基于多条材料的信号做高强度归纳和深层判断\n"
                "- 只有材料里不存在的具体事实、数字、人名、时间和身份，不要写成已被证实"
            ),
        ]
        if should_include_state_context:
            summary_lines.append(
                "【状态回答边界】\n"
                "- 优先使用客户状态池回答，不要退回成单纯资料摘录\n"
                "- 明确区分：正式判断、待确认判断、本周动作、风险提醒、缺失信息\n"
                "- candidate、risk、unknown 不能改写成已证实事实"
            )
        if memory_background_context:
            summary_lines.append(memory_background_context)
        if client_dna_context:
            summary_lines.append(client_dna_context)
        if should_include_state_context:
            summary_lines.append(workspace_state_context)
        if evidence_blocks:
            summary_lines.append(
                "原始证据包（可用于正式判断）：\n"
                + "\n\n".join(evidence_blocks)
            )
        return "\n\n".join(summary_lines).strip()

    def build_retrieval_preview_summary(client_id: str, prompt: str, evidence: list[EvidenceItem], retrieval_bundle) -> str:
        client = build_client_summary(client_id)
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
        category_coverage = [str(item) for item in retrieval_meta.get("categoryCoverage", []) if str(item).strip()] if isinstance(retrieval_meta.get("categoryCoverage"), list) else []
        preferred_categories = [
            str(item)
            for item in retrieval_meta.get("preferredCategories", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("preferredCategories"), list) else []
        top_evidence = select_high_signal_evidence(
            evidence,
            limit=3,
            prompt=prompt,
            preferred_categories=preferred_categories or category_coverage,
        )
        if not top_evidence:
            return (
                f"围绕“{prompt}”，当前还没有命中足够可支撑正式判断的原始材料。"
                f"如果继续回答，只能作为基于通用背景的初步判断，不属于基于 {client.name} 原始资料的正式分析。"
            )
        titles = "、".join(dict.fromkeys(item.title for item in top_evidence))
        if is_strategy_analysis_query(prompt):
            dimension_text = "、".join(category_coverage) if category_coverage else "项目与业务、品牌与传播、财务与筹款、组织与战略"
            return (
                f"围绕“{prompt}”，我已经先从 {client.name} 的原始材料里命中了几组最相关的证据，包括：{titles}。"
                f"这些证据大致覆盖 {dimension_text} 等维度。下面会在这些原始证据之上继续组织更完整的战略分析。"
            )
        return (
            f"围绕“{prompt}”，我已经先从 {client.name} 的原始材料里命中了几份最相关的证据，包括：{titles}。"
            "下面会基于这些原始证据继续生成更完整的分析回答。"
        )

    def build_answer_work_trace(prompt: str, evidence: list[EvidenceItem], retrieval_bundle) -> dict[str, object]:
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
        preferred_categories = [
            str(item)
            for item in retrieval_meta.get("preferredCategories", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("preferredCategories"), list) else []
        covered_categories = [
            str(item)
            for item in retrieval_meta.get("categoryCoverage", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("categoryCoverage"), list) else []
        strategic_mode = bool(retrieval_meta.get("strategicMode", False))

        def stage_label(stage: str | None) -> str:
            return {
                "doc_index": "文档索引",
                "master_index": "文档索引",
                "section_index": "章节定位",
                "surrogate": "章节定位",
                "background": "背景材料",
                "raw_chunk": "原文片段",
            }.get(stage or "", stage or "资料")

        focus = preferred_categories or covered_categories
        if not focus:
            focus = ["机构定位", "核心业务", "战略张力", "价值落地"]
        web_trail = [
            item
            for item in retrieval_meta.get("webTrail", [])
            if isinstance(item, dict)
        ][:6] if isinstance(retrieval_meta.get("webTrail"), list) else []
        linked_evidence_trail = [
            item
            for item in retrieval_meta.get("linkedEvidenceTrail", [])
            if isinstance(item, dict)
        ][:8] if isinstance(retrieval_meta.get("linkedEvidenceTrail"), list) else []
        raw_material_trail = [
            {
                "title": item.title,
                "stage": stage_label(item.retrievalStage),
                "sectionLabel": item.sectionLabel,
                "path": item.path,
                "excerpt": item.excerpt,
            }
            for item in select_high_signal_evidence(
                [item for item in evidence if item.retrievalStage == "raw_chunk"],
                limit=6,
                prompt=prompt,
                preferred_categories=preferred_categories or covered_categories,
            )
        ]
        linked_evidence_count = int(retrieval_meta.get("linkedEvidenceCount", 0) or len(linked_evidence_trail))
        return {
            "note": "这里展示的是本次回答如何利用背景底稿、联网补充和原始证据，不展示模型原始思维全文。",
            "problemFrame": (
                f"围绕“{prompt}”，先用背景底稿和联网补充建立客户语境，再确认原始证据能支撑哪些事实，最后在此基础上形成顾问式判断。"
            ),
            "analysisPlan": (
                f"优先围绕 {'、'.join(focus)} 组织分析，把背景理解、联网补充和原始证据整合成一版顾问式回答。"
                if strategic_mode
                else "优先整理机构定位、核心业务、推进线索和最值得展开的判断，并用原始证据校准判断。"
            ),
            "analysisFocus": focus[:6],
            "backgroundTrail": [
                item
                for item in retrieval_meta.get("backgroundTrail", [])
                if isinstance(item, dict)
            ][:8] if isinstance(retrieval_meta.get("backgroundTrail"), list) else [],
            "materialTrail": raw_material_trail,
            "rawEvidenceCount": len(raw_material_trail),
            "linkedEvidenceCount": linked_evidence_count,
            "linkedEvidenceTrail": linked_evidence_trail,
            "clientDnaTrail": [str(item) for item in retrieval_meta.get("clientDnaTrail", []) if str(item).strip()] if isinstance(retrieval_meta.get("clientDnaTrail"), list) else [],
            "webTrail": web_trail,
        }

    def prompt_targets_org_content(prompt: str) -> bool:
        return any(token in prompt for token in ("益语", "你们", "顾问方法", "工作方法", "服务方式"))

    INTRO_INTENT_TOKENS = ("介绍", "简介", "概况", "概览", "背景", "定位", "做什么", "机构", "组织", "是谁")
    PROJECT_INTENT_TOKENS = ("项目介绍", "项目资料", "项目清单", "核心项目", "项目概览", "项目")
    MEETING_INTENT_TOKENS = ("会议纪要", "会议", "纪要", "飞书", "妙记", "沟通记录", "会谈", "最新会议")
    NEXT_ACTION_INTENT_TOKENS = ("接下来", "下一步", "待办", "行动项", "本周推进", "要做什么", "后续安排")
    OFFICIAL_INTENT_TOKENS = ("正式判断", "已登记", "已批准", "系统内", "系统里", "official", "approved", "officiallayer")
    EVIDENCE_INTENT_TOKENS = ("引用", "原文", "依据", "证据", "资料里", "根据资料", "从资料看", "请给出处")
    STATUS_INTENT_TOKENS = (
        "最近",
        "当前",
        "现在",
        "状态",
        "进展",
        "推进",
        "风险",
        "卡点",
        "阻塞",
        "阻塞点",
        "最重要",
        "最值得关注",
        "关注",
        "关注点",
        "关注事项",
        "事项",
    )

    INTRO_QUERY_HINTS = ("介绍", "简介", "概况", "概览", "背景", "定位", "做什么", "业务", "团队", "历史")
    INTRO_PRIORITY_HINTS = (
        "介绍",
        "简介",
        "概览",
        "定位",
        "核心业务",
        "团队",
        "访谈",
        "纪要",
        "理事会",
        "工作坊",
        "战略框架",
        "业务介绍",
        "组织介绍",
    )
    INTRO_NOISE_HINTS = (
        "文件导入",
        "完整解决方案",
        "上传说明",
        "目录重分类",
        "重建知识索引",
        "导入飞书",
        "缓冲池",
        "精简版",
        "完整版",
        "第8稿",
        "第7稿",
        "click to edit master",
        "master title style",
        "工作台",
    )
    FALLBACK_INTERNAL_TEXT_MARKERS = (
        "analysis-first",
        "当前最值得抓住的原始观察包括",
        "先基于客户工作台里的最新状态信号",
        "[本周动作]",
        "[缺失信息]",
    )
    PPT_WPS_NOISE_HINTS = (
        "click to edit master",
        "master title style",
        "second level third level fourth level",
        "单击此处编辑母版文本样式",
        "单击此处编辑标题",
        "单击此处编辑副标题",
        "演示文稿标题",
        "演示文稿副标题",
        "作者和日期",
        "第二级",
        "第三级",
        "第四级",
        "第五级",
        "wps 演示",
    )
    INTRO_DOCUMENT_PRIORITY_HINTS = (
        "机构介绍",
        "组织介绍",
        "组织概况",
        "机构概况",
        "业务介绍",
        "项目介绍",
        "核心业务介绍",
        "基金会介绍",
        "机构简介",
    )
    MEETING_SUMMARY_HINTS = (
        "会议纪要",
        "沟通纪要",
        "沟通会",
        "整理版",
        "周会",
        "复盘",
        "盘点",
    )
    STRATEGY_OUTLINE_HINTS = (
        "事项清单",
        "重点事项",
        "战略陪伴",
        "讨论稿",
        "路线图",
        "战略框架",
        "战略第二曲线",
        "方案提纲",
    )
    TRANSCRIPT_HINTS = (
        "转写",
        "逐字",
        "原文版",
        "录音",
        "访谈",
    )
    SLIDE_VISUAL_HINTS = (
        ".ppt",
        ".pptx",
        "ppt",
        "幻灯片",
        "演示文稿",
        "视觉规范",
        "banner",
        "海报",
        "辅助图形",
    )

    def classify_workspace_chat_intent(prompt: str) -> WorkspaceAnswerIntent:
        normalized = re.sub(r"\s+", "", (prompt or "").lower())
        if not normalized:
            return "general"
        if any(token in normalized for token in OFFICIAL_INTENT_TOKENS):
            return "official_judgment_registry"
        if any(token in normalized for token in MEETING_INTENT_TOKENS):
            return "meeting_summary"
        if any(token in normalized for token in PROJECT_INTENT_TOKENS):
            return "project_intro"
        if any(token in normalized for token in EVIDENCE_INTENT_TOKENS):
            return "evidence_question"
        if any(token in normalized for token in STATUS_INTENT_TOKENS):
            return "status_progress"
        if any(token in normalized for token in NEXT_ACTION_INTENT_TOKENS):
            return "next_actions"
        if any(token in normalized for token in INTRO_INTENT_TOKENS):
            return "intro_profile"
        return "general"

    def is_intro_profile_query(prompt: str) -> bool:
        intent = classify_workspace_chat_intent(prompt)
        if intent in {"intro_profile", "project_intro"}:
            return True
        normalized = re.sub(r"\s+", "", (prompt or "").lower())
        return any(token in normalized for token in INTRO_QUERY_HINTS)

    def fallback_text_contains_internal_markers(text: str) -> bool:
        haystack = (text or "").lower()
        return any(marker.lower() in haystack for marker in FALLBACK_INTERNAL_TEXT_MARKERS)

    def fallback_text_contains_visual_noise(text: str) -> bool:
        haystack = (text or "").lower()
        return any(marker.lower() in haystack for marker in PPT_WPS_NOISE_HINTS)

    IDENTITY_ROLE_TERMS = (
        "创始人",
        "联合创始人",
        "创办人",
        "发起人",
        "负责人",
        "理事长",
        "董事长",
        "秘书长",
        "CEO",
        "主席",
    )

    def is_identity_role_query(prompt: str) -> bool:
        return any(token in prompt for token in IDENTITY_ROLE_TERMS)

    def organization_identity_names(max_items: int = 12) -> list[str]:
        modules = [module for module in list_organization_dna_modules() if module.hasDocument and module.normalizedText.strip()]
        if not modules:
            return []
        text = "\n".join(module.normalizedText[:3200] for module in modules)
        names: list[str] = []
        seen: set[str] = set()
        stopwords = {
            "益语智库",
            "我们",
            "客户",
            "团队",
            "公司",
            "业务",
            "战略",
            "组织",
            "方向",
            "判断",
            "品牌",
            "市场",
            "核心",
            "现阶段",
            "人类团队",
            "人类同事",
            "角色",
            "支点",
            "三位",
        }

        def append_candidate(value: str) -> None:
            candidate = value.strip("：:，,。；;、 ")
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", candidate):
                return
            if candidate in stopwords or candidate in seen:
                return
            seen.add(candidate)
            names.append(candidate)

        for pattern in (
            r"(?:同事有|成员有|核心人类同事有|现阶段.*?有三位)[:：]?\s*([^\n。]{2,40})",
            r"([\u4e00-\u9fff]{2,4})：",
            r"([\u4e00-\u9fff]{2,4})是益语智库",
        ):
            for match in re.finditer(pattern, text):
                if match.lastindex and match.lastindex >= 1:
                    value = match.group(1)
                    if "、" in value or "，" in value or "," in value:
                        for part in re.split(r"[、，,和及\s]+", value):
                            append_candidate(part)
                    else:
                        append_candidate(value)
                if len(names) >= max_items:
                    return names[:max_items]
        return names[:max_items]

    def prompt_identity_role_terms(prompt: str) -> list[str]:
        matched = [token for token in IDENTITY_ROLE_TERMS if token in prompt]
        return matched or ["创始人", "负责人"]

    def evidence_text(item: EvidenceItem) -> str:
        return re.sub(r"\s+", " ", f"{item.title} {item.sectionLabel or ''} {item.excerpt or ''}").strip()

    def evidence_has_explicit_role_binding(item: EvidenceItem, *, prompt: str, names: list[str] | None = None) -> bool:
        text = evidence_text(item)
        role_terms = prompt_identity_role_terms(prompt)
        role_pattern = "|".join(re.escape(token) for token in role_terms)
        if not re.search(role_pattern, text):
            return False
        candidate_names = names or organization_identity_names()
        person_pattern = "|".join(re.escape(name) for name in candidate_names) if candidate_names else r"[\u4e00-\u9fff]{2,4}"
        binding_patterns = (
            rf"(?:{person_pattern}).{{0,10}}(?:是|为|担任|作为)?(?:[^。；，\n]{{0,8}})?(?:{role_pattern})",
            rf"(?:{role_pattern})[:： ]?(?:[^。；，\n]{{0,8}})?(?:{person_pattern})",
        )
        return any(re.search(pattern, text) for pattern in binding_patterns)

    def evidence_mentions_org_identity_name(item: EvidenceItem, names: list[str] | None = None) -> bool:
        org_names = names or organization_identity_names()
        if not org_names:
            return False
        text = evidence_text(item)
        return any(name in text for name in org_names)

    def build_identity_guard_response(client_id: str, prompt: str, evidence: list[EvidenceItem], retrieval_bundle) -> AiStructuredResponse:
        client = build_client_summary(client_id)
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
        preferred_categories = [
            str(item)
            for item in retrieval_meta.get("preferredCategories", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("preferredCategories"), list) else []
        top_evidence = select_high_signal_evidence(
            evidence,
            limit=4,
            prompt=prompt,
            preferred_categories=preferred_categories,
        )
        org_names = organization_identity_names()
        mentioned_org_people = [
            name
            for name in org_names
            if any(name in evidence_text(item) for item in top_evidence)
        ]
        title = f"{client.name} 人物角色仍待确认"
        content_lines = [
            f"{title}",
            "",
            f"当前资料不足以直接确认 {client.name} 的{prompt_identity_role_terms(prompt)[0]}是谁。现有命中材料更多是在讨论机构战略、工作坊判断、项目设计或外部顾问参与，并没有出现一条可以直接把具体人名与该角色绑定起来的原文证据。",
        ]
        if mentioned_org_people:
            people_text = "、".join(mentioned_org_people[:3])
            content_lines.append(
                f"值得特别排除的是，当前材料里确实出现了 {people_text} 等益语侧人物，但这些内容体现的是外部顾问、访谈参与者或发言人角色，不能据此推断其就是 {client.name} 的{prompt_identity_role_terms(prompt)[0]}。"
            )
        if top_evidence:
            content_lines.append("")
            content_lines.append("当前更像背景材料而非角色证据的命中文档包括：")
            for index, item in enumerate(top_evidence[:4], start=1):
                label = item.title
                if item.sectionLabel:
                    label = f"{label} / {item.sectionLabel}"
                content_lines.append(f"{index}. {label}")
        judgment = f"当前证据不足以确认 {client.name} 的{prompt_identity_role_terms(prompt)[0]}身份，任何具体人名结论都不可靠。"
        analysis = (
            "这类问题必须依赖明确的人名-角色绑定证据，比如机构介绍、注册资料、正式署名访谈、年报或直接写出“某人是创始人/负责人”的原文。"
            "当前命中的高频发言人与外部顾问材料，不足以支撑这种身份判断。"
        )
        actions = "建议优先补充机构介绍、明确署名访谈、注册/年报资料，或直接检索包含“创始人/负责人/秘书长”等角色词的原文。"
        timeline = "补入显式角色证据后，可立即重新生成更可靠的人物分析。"
        return AiStructuredResponse(
            content="\n".join(content_lines).strip(),
            judgment=judgment,
            analysis=analysis,
            actions=actions,
            timeline=timeline,
        )

    def infer_evidence_category(item: EvidenceItem) -> str | None:
        haystack = " ".join(
            part for part in (
                item.path or "",
                item.title or "",
                item.sectionLabel or "",
                item.excerpt[:180] if item.excerpt else "",
            )
            if part
        )
        for category in ("组织与战略", "项目与业务", "品牌与传播", "财务与筹款", "其他资料"):
            if category in haystack:
                return category
        haystack_lower = haystack.lower()
        keyword_map = {
            "组织与战略": ("战略", "组织", "治理", "团队", "人力", "负责人", "路线图"),
            "项目与业务": ("业务", "项目", "交付", "会员", "产品", "运营", "执行"),
            "品牌与传播": ("品牌", "传播", "媒体", "内容", "活动", "公关"),
            "财务与筹款": ("财务", "筹款", "预算", "募资", "捐赠", "现金流"),
        }
        for category, keywords in keyword_map.items():
            if any(keyword in haystack_lower for keyword in keywords):
                return category
        return None

    def evidence_mentions_service_provider(item: EvidenceItem) -> bool:
        haystack = f"{item.title} {item.excerpt or ''}".lower()
        return any(
            marker in haystack
            for marker in (
                "益语智库",
                "我们不卖",
                "标准答案",
                "长期陪伴",
                "增长式咨询",
                "战略陪伴",
                "顾问方法",
                "导师介绍",
                "我们的业务",
                "我们的服务",
            )
        )

    def should_penalize_service_provider_evidence(item: EvidenceItem, *, prompt: str) -> bool:
        if not evidence_mentions_service_provider(item):
            return False
        if prompt_targets_org_content(prompt):
            return False
        if is_intro_profile_query(prompt):
            return False
        return True

    def intro_document_kind(item: EvidenceItem) -> Literal["intro_doc", "meeting_summary", "strategy_outline", "transcript", "slide_visual", "other"]:
        haystack = " ".join(
            part.lower()
            for part in (
                item.title or "",
                item.path or "",
                item.sectionLabel or "",
                item.excerpt[:220] if item.excerpt else "",
            )
            if part
        )
        if any(marker in haystack for marker in INTRO_DOCUMENT_PRIORITY_HINTS):
            return "intro_doc"
        if any(marker in haystack for marker in MEETING_SUMMARY_HINTS):
            return "meeting_summary"
        if any(marker in haystack for marker in STRATEGY_OUTLINE_HINTS):
            return "strategy_outline"
        if any(marker in haystack for marker in TRANSCRIPT_HINTS):
            return "transcript"
        if any(marker in haystack for marker in SLIDE_VISUAL_HINTS):
            return "slide_visual"
        return "other"

    def intro_document_kind_rank(item: EvidenceItem) -> int:
        return {
            "intro_doc": 0,
            "meeting_summary": 1,
            "strategy_outline": 2,
            "transcript": 3,
            "other": 4,
            "slide_visual": 5,
        }[intro_document_kind(item)]

    def evidence_family_key(item: EvidenceItem) -> str:
        raw = (item.title or Path(item.path or "").name or item.documentId or "").strip()
        stem = Path(raw).stem if raw else ""
        normalized = re.sub(r"^副本", "", stem)
        normalized = re.sub(r"__[\da-f]{4,}$", "", normalized, flags=re.I)
        normalized = re.sub(r"[\(（]\d+[\)）]$", "", normalized)
        normalized = re.sub(r"\s+", "", normalized)
        return normalized.lower()

    def evidence_is_intro_noise(item: EvidenceItem) -> bool:
        haystack = " ".join(
            part.lower()
            for part in (
                item.title or "",
                item.path or "",
                item.sectionLabel or "",
                item.excerpt[:220] if item.excerpt else "",
            )
            if part
        )
        return any(marker in haystack for marker in (*INTRO_NOISE_HINTS, *PPT_WPS_NOISE_HINTS))

    def evidence_is_intro_priority(item: EvidenceItem) -> bool:
        haystack = " ".join(
            part.lower()
            for part in (
                item.title or "",
                item.path or "",
                item.sectionLabel or "",
                item.excerpt[:220] if item.excerpt else "",
            )
            if part
        )
        if "核心业务介绍" in haystack or "业务介绍" in haystack or "组织介绍" in haystack:
            return True
        if any(marker in haystack for marker in INTRO_PRIORITY_HINTS):
            return True
        inferred_category = infer_evidence_category(item)
        return inferred_category in {"组织与战略", "项目与业务"}

    def evidence_is_noisy_for_fallback(item: EvidenceItem, *, prompt: str = "") -> bool:
        haystack = f"{item.title} {item.excerpt or ''}".lower()
        if any(
            marker in haystack
            for marker in (*PPT_WPS_NOISE_HINTS, "pdf 文档：原文件", "总页数:", "代理文档")
        ):
            return True
        excerpt = re.sub(r"\s+", " ", item.excerpt or "").strip()
        if re.search(r"[!@#$%^&*()_+=<>]{4,}", excerpt):
            return True
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", excerpt))
        latin_tokens = len(re.findall(r"[A-Za-z]{4,}", excerpt))
        if chinese_chars < 18 and latin_tokens >= 8:
            return True
        if should_penalize_service_provider_evidence(item, prompt=prompt):
            return True
        if is_identity_role_query(prompt):
            org_names = organization_identity_names()
            if evidence_mentions_org_identity_name(item, org_names) and not evidence_has_explicit_role_binding(item, prompt=prompt, names=org_names):
                return True
        return False

    def select_high_signal_evidence(
        evidence: list[EvidenceItem],
        limit: int = 8,
        *,
        prompt: str = "",
        preferred_categories: list[str] | None = None,
    ) -> list[EvidenceItem]:
        intro_mode = is_intro_profile_query(prompt)
        finance_mode = is_finance_query(prompt)
        finance_statement_mode = is_finance_statement_query(prompt)

        def document_key(item: EvidenceItem) -> str:
            base = (item.documentId or item.path or item.title or "").strip().lower()
            return re.sub(r"\s+", " ", base)

        def section_key(item: EvidenceItem) -> str:
            label = (item.sectionLabel or "").strip().lower()
            return re.sub(r"\s+", " ", label)

        def score(item: EvidenceItem) -> float:
            ranking = float(item.score or 0.0)
            if item.retrievalStage == "raw_chunk":
                ranking += 1.2
            if item.retrievalStage == "surrogate":
                ranking -= 0.6
            if item.isFallback:
                ranking -= 0.4
            if item.sectionLabel and item.sectionLabel not in {"概览", "目录索引", "代理文档"}:
                ranking += 0.15
            inferred_category = infer_evidence_category(item)
            if preferred_categories and inferred_category in preferred_categories:
                ranking += 0.22
            if finance_mode:
                if inferred_category == "财务与筹款":
                    ranking += 0.95
                if is_finance_priority_text(item.title, item.sectionLabel, item.excerpt[:320] if item.excerpt else "", item.path):
                    ranking += 0.68
                if finance_statement_mode:
                    if is_finance_statement_priority_text(item.title, item.sectionLabel, item.excerpt[:320] if item.excerpt else "", item.path):
                        ranking += 0.9
                    elif inferred_category != "财务与筹款":
                        ranking -= 0.28
                elif inferred_category != "财务与筹款":
                    ranking -= 0.22
            if is_identity_role_query(prompt):
                org_names = organization_identity_names()
                if evidence_has_explicit_role_binding(item, prompt=prompt, names=org_names):
                    ranking += 2.0
                else:
                    ranking -= 0.8
                if evidence_mentions_org_identity_name(item, org_names) and not evidence_has_explicit_role_binding(item, prompt=prompt, names=org_names):
                    ranking -= 2.4
            if intro_mode:
                if evidence_is_intro_priority(item):
                    ranking += 0.55
                if evidence_is_intro_noise(item):
                    ranking -= 3.2
                document_kind = intro_document_kind(item)
                if document_kind == "intro_doc":
                    ranking += 1.8
                elif document_kind == "meeting_summary":
                    ranking += 1.35
                elif document_kind == "strategy_outline":
                    ranking += 1.1
                elif document_kind == "transcript":
                    ranking += 0.45
                elif document_kind == "slide_visual":
                    ranking -= 1.35
            if evidence_is_noisy_for_fallback(item, prompt=prompt):
                ranking -= 3.0
            return ranking

        ranked = sorted(evidence, key=score, reverse=True)
        selected = [
            item
            for item in ranked
            if not evidence_is_noisy_for_fallback(item, prompt=prompt)
            and not (intro_mode and evidence_is_intro_noise(item))
        ]
        if intro_mode and not selected:
            selected = [
                item
                for item in ranked
                if evidence_is_intro_priority(item) and not evidence_is_intro_noise(item)
            ]
        if not selected:
            selected = [
                item
                for item in ranked
                if item.retrievalStage == "raw_chunk"
                and not (intro_mode and evidence_is_intro_noise(item))
            ] or [
                item
                for item in ranked
                if not (intro_mode and evidence_is_intro_noise(item))
            ] or ranked
        concentrated: list[EvidenceItem] = []
        seen_units: set[str] = set()
        seen_families: set[str] = set()

        for item in selected:
            key = document_key(item)
            section_value = section_key(item)
            excerpt_key = re.sub(r"\s+", " ", (item.excerpt or "")[:320].strip().lower())
            unit_key = f"{key}::{section_value}::{excerpt_key}"
            if unit_key in seen_units:
                continue
            family_key = evidence_family_key(item)
            if intro_mode and family_key and family_key in seen_families:
                continue
            concentrated.append(item)
            seen_units.add(unit_key)
            if intro_mode and family_key:
                seen_families.add(family_key)
            if len(concentrated) >= limit:
                break

        return concentrated[:limit] if concentrated else selected[:limit]

    def _user_facing_evidence_label(item: EvidenceItem) -> str:
        raw = item.title or Path(item.path or "").name or "相关资料"
        label = Path(raw).stem if raw else "相关资料"
        label = re.sub(r"^副本", "", label)
        label = re.sub(r"__[\da-f]{4,}$", "", label, flags=re.I)
        label = re.sub(r"\s+", " ", label).strip()
        return label[:36] if label else "相关资料"

    def _clean_user_facing_evidence_excerpt(excerpt: str, *, limit: int = 120) -> str:
        text = re.sub(r"\s+", " ", excerpt or "").strip()
        if not text:
            return ""
        if fallback_text_contains_visual_noise(text):
            return ""
        text = re.sub(r"\b[0-9A-F]{8,}\b", " ", text)
        text = re.sub(r"(单击此处编辑[^。；，\s]*)", " ", text)
        text = re.sub(r"(第二级|第三级|第四级|第五级|演示文稿标题|演示文稿副标题|作者和日期|正文：?)", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" ：:；;，,、")
        if len(text) < 16:
            return ""
        if len(text) <= limit:
            return text
        candidate = text[:limit]
        cut_points = [candidate.rfind(marker) for marker in ("。", "；", "，", "：", " ")]
        safe_cut = max(cut_points)
        if safe_cut >= 28:
            candidate = candidate[:safe_cut]
        return candidate.rstrip(" ：:；;，,、") + "…"

    def build_compact_user_fallback_content(
        client_id: str,
        prompt: str,
        top_evidence: list[EvidenceItem],
    ) -> str:
        client = build_client_summary(client_id)
        bullets: list[str] = []
        for item in top_evidence[:5]:
            cleaned_excerpt = _clean_user_facing_evidence_excerpt(item.excerpt or "")
            if not cleaned_excerpt:
                continue
            bullets.append(f"- {_user_facing_evidence_label(item)}：{cleaned_excerpt}")
            if len(bullets) >= 4:
                break
        if not bullets:
            bullets = [f"- 已命中 {len(top_evidence)} 份相关资料，但当前只适合先保留简版说明。"]
        if is_intro_profile_query(prompt):
            lead = f"围绕 {client.name}，当前已命中机构介绍、会议纪要和项目资料，可以先给出一版简要介绍："
            close = "这版先保留为基于已命中资料的简要介绍；如需更完整的顾问式长答，可继续重试正式生成。"
        else:
            lead = f"围绕“{prompt}”，当前先基于已命中的原始资料给出一版简要回答："
            close = "这版先保留为基于已命中资料的简要回答；如需更完整分析，可继续重试正式生成。"
        return "\n".join([lead, *bullets, close]).strip()

    def _collect_user_facing_fallback_evidence(
        top_evidence: list[EvidenceItem],
        *,
        limit: int = 4,
        excerpt_limit: int = 120,
    ) -> list[tuple[str, str]]:
        lines: list[tuple[str, str]] = []
        for item in top_evidence[: max(limit + 2, limit)]:
            label = _user_facing_evidence_label(item)
            excerpt = _clean_user_facing_evidence_excerpt(item.excerpt or "", limit=excerpt_limit)
            if not excerpt:
                continue
            lines.append((label, excerpt))
            if len(lines) >= limit:
                break
        return lines

    INTRO_PROJECT_SIGNAL_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("教师赋能", ("教师赋能", "教师成长", "教师项目")),
        ("心盛计划", ("心盛计划", "心盛")),
        ("繁星计划", ("繁星计划", "繁星")),
        ("关怀员培养", ("关怀员", "关怀员培养")),
        ("行动营", ("行动营",)),
    )
    INTRO_PROJECT_PATTERN = re.compile(r"([\u4e00-\u9fffA-Za-z0-9]{2,12}(?:计划|项目))")
    INTRO_PROJECT_STOPWORDS = {
        "核心项目",
        "项目资料",
        "项目清单",
        "阶段项目",
        "本项目",
        "年度项目",
        "项目推进",
    }

    def _trim_intro_sentence(text: str, *, limit: int = 44) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip(" ：:；;，,、")
        if not cleaned:
            return ""
        if len(cleaned) <= limit:
            return cleaned
        candidate = cleaned[:limit]
        safe_cut = max(candidate.rfind(marker) for marker in ("。", "；", "，", "：", " "))
        if safe_cut >= 14:
            candidate = candidate[:safe_cut]
        return candidate.rstrip(" ：:；;，,、") + "…"

    def _extract_intro_project_signals(top_evidence: list[EvidenceItem], *, max_items: int = 4) -> list[str]:
        projects: list[str] = []
        seen: set[str] = set()
        for canonical, hints in INTRO_PROJECT_SIGNAL_HINTS:
            if any(any(hint in f"{item.title} {item.excerpt or ''}" for hint in hints) for item in top_evidence):
                projects.append(canonical)
                seen.add(canonical)
                if len(projects) >= max_items:
                    return projects
        for item in top_evidence:
            haystack = f"{item.title} {item.excerpt or ''}"
            for match in INTRO_PROJECT_PATTERN.findall(haystack):
                candidate = re.sub(r"\s+", "", match).strip()
                if len(candidate) < 2 or len(candidate) > 12:
                    continue
                if candidate in INTRO_PROJECT_STOPWORDS or candidate in seen:
                    continue
                seen.add(candidate)
                projects.append(candidate)
                if len(projects) >= max_items:
                    return projects
        return projects

    def _derive_intro_workline_keywords(top_evidence: list[EvidenceItem]) -> list[str]:
        combined = " ".join(f"{item.title} {item.excerpt or ''}" for item in top_evidence)
        keywords: list[str] = []
        if any(token in combined for token in ("教师", "赋能", "教研")):
            keywords.append("教师赋能")
        if any(token in combined for token in ("心理", "关怀", "青年", "社群")):
            keywords.append("青少年支持")
        if any(token in combined for token in ("生态", "传播", "资源", "协同")):
            keywords.append("生态协同")
        if any(token in combined for token in ("战略", "路线", "组织", "推进")):
            keywords.append("战略推进")
        return keywords[:3]

    def _project_signal_default_summary(project: str) -> str:
        if "教师赋能" in project or ("教师" in project and "计划" not in project):
            return "聚焦带领者培养、教师支持与协作机制。"
        if "心盛" in project:
            return "聚焦关怀员培养、青年社群与内容协同。"
        if "繁星" in project:
            return "聚焦定位校准、传播联动与资源协同。"
        if "行动营" in project:
            return "聚焦行动节奏、执行分工与复盘闭环。"
        if project.endswith("计划"):
            return "当前命中资料显示该计划处于持续推进中。"
        return "当前命中资料显示该项目在持续推进。"

    def build_intro_profile_answer_from_evidence(
        client_id: str,
        prompt: str,
        top_evidence: list[EvidenceItem],
        *,
        failure_detail: str,
    ) -> AiStructuredResponse:
        client = build_client_summary(client_id)
        snippets = _collect_user_facing_fallback_evidence(top_evidence, limit=6, excerpt_limit=84)
        short_snippets = [
            (label, _trim_intro_sentence(excerpt, limit=42))
            for label, excerpt in snippets
            if _trim_intro_sentence(excerpt, limit=42)
        ]
        project_signals = _extract_intro_project_signals(top_evidence, max_items=4)
        workline_keywords = _derive_intro_workline_keywords(top_evidence)
        org_nature = "公益基金会" if "基金会" in client.name else "机构团队"
        identity_summary = (
            f"从已入库资料看，{client.name}是一家围绕{'、'.join(workline_keywords)}持续推进项目的{org_nature}。"
            if workline_keywords
            else f"从已入库资料看，{client.name}是一家持续推进项目协同与阶段执行的{org_nature}。"
        )
        intro_lines = [identity_summary]
        intro_lines.append("当前资料以会议纪要和项目复盘为主，适合形成执行导向介绍；机构使命与成果口径仍建议补充官方简介。")

        project_bullets: list[str] = []
        if project_signals:
            for project in project_signals[:4]:
                project_bullets.append(f"- {project}：{_project_signal_default_summary(project)}")
        else:
            for label, excerpt in short_snippets[:3]:
                project_bullets.append(f"- {label}：{excerpt}")
        if not project_bullets:
            project_bullets = ["- 当前已命中资料，但核心项目描述仍偏少，建议补充项目手册或年度资料。"]

        meeting_clues = [label for label, _ in short_snippets if any(token in label for token in ("会议", "纪要", "沟通"))]
        clue_line = (
            f"- 最近可直接引用的推进线索主要来自：{'、'.join(meeting_clues[:2])}。"
            if meeting_clues
            else "- 近期资料以会议纪要、项目梳理和行动跟进为主，可用于快速形成对外介绍草稿。"
        )

        citation_lines = [
            f"{index}. 《{label}》：{_trim_intro_sentence(excerpt, limit=76)}"
            for index, (label, excerpt) in enumerate(snippets[:4], start=1)
        ]
        if not citation_lines:
            citation_lines = ["1. 当前命中资料不足，建议补充机构介绍、项目手册和会议纪要。"]
        content = "\n".join(
            [
                f"根据当前已入库资料，{client.name}可以先这样介绍：",
                "",
                "一、它是谁 / 在做什么",
                *( [f"- {line}" for line in intro_lines] if intro_lines else [f"- 现有资料显示，{client.name}围绕公益项目推进、组织协同和阶段性执行在持续展开工作。"] ),
                "",
                "二、目前资料里可见的核心项目与工作条线",
                *project_bullets,
                "",
                "三、近期可确认的推进线索",
                clue_line,
                "",
                "四、仍建议补充的信息",
                "- 机构官方简介（使命/服务对象/核心成果）",
                "- 项目手册或年度复盘（便于补齐完整叙事）",
                "",
                "引用依据：",
                *citation_lines,
            ]
        ).strip()
        return AiStructuredResponse(
            content=content,
            judgment="当前已命中可用资料，可先交付一版简洁组织介绍；正式扩写稿本轮未完整完成。",
            analysis=(
                "正式长回答未完整完成，系统已降级为可交付简介模式：保留“组织定位 + 项目要点 + 引用依据”的最小可用结构。"
                f"\n\n失败详情：{failure_detail}"

```
