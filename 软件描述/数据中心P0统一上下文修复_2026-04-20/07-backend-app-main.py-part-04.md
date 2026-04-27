# 源码文件：`backend/app/main.py`（分片 04）

- 行号范围：8401-11200
- 总行数：   30416
- 导出时间：2026-04-20

```python
                        tab="tasks",
                        statusLabel="成长练习",
                    ),
                )
            return GrowthWorkbenchTaskRecord(
                id=f"recommendation-{recommendation.id}",
                title=recommendation.title,
                project=recommendation.clientName or recommendation.eventLineName or recommendation.abilityLabel,
                clientName=recommendation.clientName,
                eventLineName=recommendation.eventLineName,
                deadline="本周排期" if recommendation.priority == "high" else "可安排到下周",
                urgency="建议优先处理" if recommendation.priority == "high" else "需先补关键动作",
                urgencyColor="text-red-700 bg-red-100" if recommendation.priority == "high" else "text-orange-700 bg-orange-100",
                phase=phase,
                risks=[recommendation.reason or recommendation.summary],
                nextAdvice=recommendation.practiceTask or recommendation.summary,
                robotReady=any(keyword in f"{recommendation.title}{recommendation.summary}{recommendation.practiceTask}" for keyword in ("模板", "清单", "纪要", "生成", "对齐", "跟踪", "排查")),
                robotReasons=["任务输出格式明确", "已匹配学习资产", "当前阶段可先由机器人生成首稿"] if any(keyword in f"{recommendation.title}{recommendation.summary}{recommendation.practiceTask}" for keyword in ("模板", "清单", "纪要", "生成", "对齐", "跟踪", "排查")) else ["关键判断仍需人工定调", "上下文还需要结合现场信息", "属于高博弈或高创造性动作"],
                recommendationId=recommendation.id,
                linkedTaskId=recommendation.linkedTaskId,
                linkedContexts=linked_contexts,
                xpReward=20,
                contextSummary=recommendation.reason or recommendation.summary,
                projectFlowName=recommendation.triggerNode,
                projectStage=recommendation.projectStage,
                sourceEvidence=[recommendation.summary] if recommendation.summary else [],
                currentBlocker=recommendation.reason or None,
                missingSignals=[recommendation.reason] if recommendation.reason else [],
                hasBackground=True,
                hasDeadline=False,
                isCrossDepartment=bool(recommendation.eventLineId or recommendation.clientId),
                needsReview=False,
                evidenceCount=1,
                pendingCollaborations=0,
            )

        def workbench_task_from_capture(index: int, capture: GrowthPendingCaptureRecord) -> GrowthWorkbenchTaskRecord:
            phase = next((item[1] for item in phase_blueprints if item[1] in (capture.projectStage or "") or item[1] in capture.nextActionText or item[1] in capture.summary), "复盘沉淀" if capture.sourceType == "task_attachment_candidate" else phase_blueprints[min(index + 3, len(phase_blueprints) - 1)][1])
            linked_task = next((context.objectId for context in capture.linkedContexts if context.objectType == "task"), None)
            return GrowthWorkbenchTaskRecord(
                id=f"capture-{capture.id}",
                title=capture.title,
                project=capture.clientName or capture.eventLineName or "待放大成长",
                clientName=capture.clientName,
                eventLineName=capture.eventLineName,
                deadline="等待闭环",
                urgency="需先补关键动作" if any(any(keyword in reason for keyword in ("复盘", "沉淀", "闭环")) for reason in capture.missingReasons) else "可继续推进",
                urgencyColor="text-orange-700 bg-orange-100" if any(any(keyword in reason for keyword in ("复盘", "沉淀", "闭环")) for reason in capture.missingReasons) else "text-green-700 bg-green-100",
                phase=phase,
                risks=capture.missingReasons[:2] or [capture.summary or "系统已经识别到成长信号，但还缺最终闭环。"],
                nextAdvice=capture.nextActionText or capture.summary or "先补资料、复盘或沉淀，再把这条成长放大。",
                robotReady=False,
                robotReasons=["当前更适合先由人补资料、复盘或沉淀说明", "这类信号需要解释层，不适合只靠自动执行完成"],
                recommendationId=None,
                linkedTaskId=linked_task,
                linkedContexts=list(capture.linkedContexts),
                xpReward=16,
                contextSummary=capture.summary,
                projectFlowName=capture.projectStage,
                projectStage=capture.projectStage,
                sourceEvidence=list(capture.missingReasons),
                currentBlocker=capture.missingReasons[0] if capture.missingReasons else None,
                missingSignals=list(capture.missingReasons),
                hasBackground=True,
                hasDeadline=False,
                isCrossDepartment=bool(capture.eventLineId or capture.clientId),
                needsReview=any(any(keyword in reason for keyword in ("复盘", "解释", "说明")) for reason in capture.missingReasons),
                evidenceCount=1,
                pendingCollaborations=0,
            )

        def context_key(context: GrowthContextLinkRecord) -> str:
            return f"{context.objectType}:{context.objectId}"

        def overlaps(left: list[GrowthContextLinkRecord], right: list[GrowthContextLinkRecord]) -> bool:
            if not left or not right:
                return False
            right_keys = {context_key(context) for context in right}
            return any(context_key(context) in right_keys for context in left)

        def matches_task(
            task: GrowthWorkbenchTaskRecord,
            *,
            linked_task_id: str | None = None,
            linked_contexts: list[GrowthContextLinkRecord] | None = None,
            client_name: str | None = None,
            event_line_name: str | None = None,
            project_stage: str | None = None,
        ) -> bool:
            if linked_task_id and task.linkedTaskId and linked_task_id == task.linkedTaskId:
                return True
            if overlaps(task.linkedContexts, linked_contexts or []):
                return True
            if normalize_text(event_line_name) and normalize_text(event_line_name) in normalize_text(task.project):
                return True
            if normalize_text(client_name) and normalize_text(client_name) in normalize_text(task.project):
                return True
            if normalize_text(project_stage) and normalize_text(project_stage) in normalize_text(task.phase):
                return True
            return False

        def dedupe_strings(values: list[str], *, limit: int | None = None) -> list[str]:
            seen: set[str] = set()
            output: list[str] = []
            for value in values:
                normalized = normalize_text(value)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                output.append(normalized)
                if limit is not None and len(output) >= limit:
                    break
            return output

        def dedupe_records_by_id(records: list[object], *, limit: int | None = None) -> list[object]:
            seen: set[str] = set()
            output: list[object] = []
            for record in records:
                record_id = normalize_text(getattr(record, "id", None))
                if not record_id or record_id in seen:
                    continue
                seen.add(record_id)
                output.append(record)
                if limit is not None and len(output) >= limit:
                    break
            return output

        def preferred_task_context(task: GrowthWorkbenchTaskRecord) -> GrowthContextLinkRecord | None:
            return (
                next((context for context in task.linkedContexts if context.objectType == "task"), None)
                or next((context for context in task.linkedContexts if context.objectType == "event_line"), None)
                or next((context for context in task.linkedContexts if context.objectType == "client"), None)
                or (task.linkedContexts[0] if task.linkedContexts else None)
            )

        def infer_learning_ability_keys(
            task: GrowthWorkbenchTaskRecord,
            focus_actions: list[GrowthFocusActionRecord],
            captures: list[GrowthPendingCaptureRecord],
            recommendations: list[LearningRecommendationRecord],
        ) -> list[str]:
            keys: list[str] = [item.abilityKey for item in recommendations if item.abilityKey]
            haystack = " ".join(
                item
                for item in (
                    task.title,
                    task.project,
                    task.phase,
                    task.currentBlocker or "",
                    task.contextSummary,
                    " ".join(task.risks),
                    " ".join(item.title for item in focus_actions),
                    " ".join(item.title for item in captures),
                )
                if item
            )
            if task.isCrossDepartment or any(keyword in haystack for keyword in ("沟通", "协作", "对齐", "会议", "负责人")):
                keys.append("collab")
            if task.currentBlocker or any(keyword in haystack for keyword in ("风险", "卡点", "依赖", "阻塞", "返工")):
                keys.append("risk")
            if any(keyword in haystack for keyword in ("方案", "提案", "文档", "白皮书", "输出", "写")):
                keys.append("write")
            if any(keyword in haystack for keyword in ("分析", "判断", "研究", "说明", "原因")):
                keys.append("analyze")
            if any(keyword in haystack for keyword in ("客户", "访谈", "顾虑", "诉求", "对象")):
                keys.append("insight")
            if task.phase in {"需求接收", "信息核对", "交付闭环"}:
                keys.append("exec")
            ordered = [key for key in dict.fromkeys(keys) if key in {"exec", "collab", "analyze", "insight", "risk", "write"}]
            return ordered or ["exec", "risk"]

        def build_generic_lessons(
            task: GrowthWorkbenchTaskRecord,
            focus_actions: list[GrowthFocusActionRecord],
            captures: list[GrowthPendingCaptureRecord],
            recommendations: list[LearningRecommendationRecord],
        ) -> list[GrowthGenericLessonRecord]:
            lessons: list[GrowthGenericLessonRecord] = []
            default_context = preferred_task_context(task)
            for recommendation in recommendations[:2]:
                lessons.append(
                    GrowthGenericLessonRecord(
                        id=f"recommendation-{recommendation.id}",
                        title=recommendation.title or recommendation.summary,
                        judgment=recommendation.summary or recommendation.reason or recommendation.practiceTask,
                        applicableScene=recommendation.projectStage or recommendation.triggerNode or task.phase,
                        whyItWorks=recommendation.reason or recommendation.whyNow or recommendation.body or "这条方法来自近期真实成长推荐，可直接作为当前任务的练习模板。",
                        reuseHint=recommendation.practiceTask or "把这条方法写回到任务模板、会议纪要或复盘沉淀里。",
                        linkedContext=recommendation.linkedContexts[0] if recommendation.linkedContexts else default_context,
                    )
                )
            fallback_items = build_generic_learning_fallback(
                infer_learning_ability_keys(task, focus_actions, captures, recommendations),
                limit=3,
            )
            existing_titles = {normalize_text(item.title) for item in lessons}
            for item in fallback_items:
                if normalize_text(item.title) in existing_titles:
                    continue
                lessons.append(
                    GrowthGenericLessonRecord(
                        id=f"fallback-{item.id}",
                        title=item.title,
                        judgment=item.summary or item.body,
                        applicableScene=f"当前处在「{task.phase}」阶段，适合先把动作标准压实。",
                        whyItWorks=item.body or item.summary,
                        reuseHint=item.practiceTask or "把这条方法沉淀到成长手册，后续同类任务直接复用。",
                        linkedContext=default_context,
                    )
                )
                if len(lessons) >= 3:
                    break
            return lessons[:3]

        def build_project_guidance(
            task: GrowthWorkbenchTaskRecord,
            focus_actions: list[GrowthFocusActionRecord],
            captures: list[GrowthPendingCaptureRecord],
            recommendations: list[LearningRecommendationRecord],
            *,
            source_mode_value: Literal["task", "growth_seed", "empty"],
        ) -> list[GrowthProjectGuidanceRecord]:
            guidance: list[GrowthProjectGuidanceRecord] = []
            if source_mode_value != "task":
                guidance.append(
                    GrowthProjectGuidanceRecord(
                        id=f"{task.id}-context-mode",
                        title="当前还不是完整项目判断",
                        judgment="现在更多是成长推荐或待放大信号，不是来自一条上下文完整的真实任务。",
                        whySpecial="缺少真实任务、附件证据和连续事件线时，系统只能给规则基础版建议，不能假装已经理解了整个项目。",
                        guidanceType="context_gap",
                        linkedContexts=task.linkedContexts,
                        evidenceRefs=dedupe_strings(task.missingSignals + ["缺真实任务上下文"], limit=3),
                    )
                )
            if task.eventLineName:
                guidance.append(
                    GrowthProjectGuidanceRecord(
                        id=f"{task.id}-event-line",
                        title=f"这条动作属于事件线「{task.eventLineName}」",
                        judgment=task.currentBlocker or task.nextAdvice or "这次判断标准不是把单点动作做满，而是让整条业务线继续向前。",
                        whySpecial="一旦任务已经挂到事件线上，就不能只把它当孤立事项处理，优先级应该围绕整条线的连续推进来判断。",
                        guidanceType="project_specific",
                        linkedContexts=[context for context in task.linkedContexts if context.objectType in {"event_line", "task", "client"}],
                        evidenceRefs=dedupe_strings(task.sourceEvidence + ([task.currentBlocker] if task.currentBlocker else []), limit=3),
                    )
                )
            elif task.projectFlowName or task.projectModuleName:
                subject = task.projectFlowName or task.projectModuleName or "当前项目流程"
                guidance.append(
                    GrowthProjectGuidanceRecord(
                        id=f"{task.id}-project-flow",
                        title=f"当前动作受「{subject}」约束",
                        judgment=f"这次更像「{task.phase}」阶段的推进节点，要优先满足流程继续推进的标准，而不是一次性把内容写满。",
                        whySpecial="项目模块和流程已经给了当前任务明确的判断边界，所以真正关键的是让这个节点向前，而不是追求泛化的完整产出。",
                        guidanceType="project_specific",
                        linkedContexts=[context for context in task.linkedContexts if context.objectType in {"project_flow", "project_module", "task"}],
                        evidenceRefs=dedupe_strings(task.sourceEvidence + [subject], limit=3),
                    )
                )
            if task.currentBlocker or task.risks:
                guidance.append(
                    GrowthProjectGuidanceRecord(
                        id=f"{task.id}-stage-risk",
                        title="当前阶段最容易返工的点",
                        judgment=task.currentBlocker or task.risks[0],
                        whySpecial="这条风险不是静态模板里推导出来的泛化句，而是当前任务对象已经显式暴露出的阻塞或缺口。",
                        guidanceType="stage_risk",
                        linkedContexts=[context for context in task.linkedContexts if context.objectType in {"task", "event_line", "client"}],
                        evidenceRefs=dedupe_strings(task.risks + task.missingSignals, limit=3),
                    )
                )
            if task.isCrossDepartment or task.pendingCollaborations > 0 or task.needsReview or not task.hasBackground or task.evidenceCount <= 0:
                gap_reasons = dedupe_strings(
                    [
                        "缺任务背景说明" if not task.hasBackground else "",
                        "缺附件或明确证据" if task.evidenceCount <= 0 and not task.sourceEvidence else "",
                        "缺协作边界确认" if task.isCrossDepartment or task.pendingCollaborations > 0 else "",
                        "缺复核说明或审批依据" if task.needsReview else "",
                    ],
                    limit=4,
                )
                guidance.append(
                    GrowthProjectGuidanceRecord(
                        id=f"{task.id}-context-gap",
                        title="项目特有判断还不够稳",
                        judgment="当前项目背景、证据或协作边界仍有缺口，所以系统只能先给基础建议，不能假装已经理解了全部业务语境。",
                        whySpecial="先把缺口补齐，再去看更深的项目判断，页面才能真正像助理而不是像模板卡。",
                        guidanceType="context_gap",
                        linkedContexts=task.linkedContexts,
                        evidenceRefs=gap_reasons,
                    )
                )
            return guidance[:3]

        def build_reasoning_trace(
            task: GrowthWorkbenchTaskRecord,
            focus_actions: list[GrowthFocusActionRecord],
            captures: list[GrowthPendingCaptureRecord],
            recommendations: list[LearningRecommendationRecord],
            *,
            source_mode_value: Literal["task", "growth_seed", "empty"],
        ) -> GrowthReasoningTraceRecord:
            used_inputs: list[GrowthReasoningInputRecord] = []
            for context in task.linkedContexts[:4]:
                source_type = context.objectType if context.objectType in {"task", "event_line", "client", "project_module", "project_flow"} else "rule"
                used_inputs.append(
                    GrowthReasoningInputRecord(
                        id=f"context-{context.objectType}-{context.objectId}",
                        sourceType=source_type,
                        label=context.label,
                        detail=context.subtitle or context.statusLabel or "",
                    )
                )
            for action in focus_actions[:1]:
                used_inputs.append(
                    GrowthReasoningInputRecord(
                        id=f"focus-{action.id}",
                        sourceType="focus_action",
                        label=action.title,
                        detail=action.summary or action.whyNow,
                    )
                )
            for capture in captures[:1]:
                used_inputs.append(
                    GrowthReasoningInputRecord(
                        id=f"capture-{capture.id}",
                        sourceType="pending_capture",
                        label=capture.title,
                        detail=capture.summary or capture.nextActionText,
                    )
                )
            for recommendation in recommendations[:1]:
                used_inputs.append(
                    GrowthReasoningInputRecord(
                        id=f"recommendation-{recommendation.id}",
                        sourceType="recommendation",
                        label=recommendation.title,
                        detail=recommendation.summary or recommendation.reason,
                    )
                )
            if not used_inputs:
                used_inputs.append(
                    GrowthReasoningInputRecord(
                        id="rule-only",
                        sourceType="rule",
                        label="规则推导基线",
                        detail="当前没有足够的真实对象输入，系统只能输出基础规则判断。",
                    )
                )

            evidence_refs = dedupe_strings(
                task.sourceEvidence
                + ([task.currentBlocker] if task.currentBlocker else [])
                + task.risks
                + [capture.summary for capture in captures if capture.summary]
                + [recommendation.summary for recommendation in recommendations if recommendation.summary],
                limit=6,
            )
            missing_context = dedupe_strings(
                task.missingSignals
                + [
                    "当前没有真实任务上下文" if source_mode_value != "task" else "",
                    "缺事件线连续上下文" if not any(context.objectType == "event_line" for context in task.linkedContexts) else "",
                    "缺项目模块或流程归属" if not any(context.objectType in {"project_module", "project_flow"} for context in task.linkedContexts) else "",
                    "缺附件或明确证据" if task.evidenceCount <= 0 and not task.sourceEvidence else "",
                    "缺任务背景说明" if not task.hasBackground else "",
                ],
                limit=6,
            )
            confidence: Literal["high", "medium", "low"]
            if source_mode_value == "task" and task.hasBackground and (task.evidenceCount > 0 or task.sourceEvidence) and len(missing_context) <= 1:
                confidence = "high"
            elif source_mode_value == "empty" or len(missing_context) >= 3:
                confidence = "low"
            else:
                confidence = "medium"
            return GrowthReasoningTraceRecord(
                mode="rules_only",
                usedInputs=used_inputs[:6],
                evidenceRefs=evidence_refs,
                missingContext=missing_context,
                aiContribution=[],
                modelLabel=None,
                confidence=confidence,
            )

        def build_ai_learning_synthesis(
            task: GrowthWorkbenchTaskRecord,
            generic_lessons: list[GrowthGenericLessonRecord],
            guidance_items: list[GrowthProjectGuidanceRecord],
            reasoning: GrowthReasoningTraceRecord,
            *,
            source_mode_value: Literal["task", "growth_seed", "empty"],
        ) -> tuple[
            list[GrowthGenericLessonRecord],
            list[GrowthProjectGuidanceRecord],
            GrowthReasoningTraceRecord,
            GrowthLearningSummaryRecord,
        ] | None:
            ai_health = state.ai.get_health()
            provider_name = str(ai_health.provider or "").strip().lower()
            if source_mode_value != "task" or not ai_health.ready or provider_name in {"", "mock"}:
                return None
            if not task.hasBackground or len(reasoning.missingContext) >= 4:
                return None

            def clean_ai_text(value: str | None, *, prefixes: tuple[str, ...] = ()) -> str:
                text = re.sub(r"\s+", " ", str(value or "")).strip().strip("•-")
                for prefix in prefixes:
                    if text.startswith(prefix):
                        text = text[len(prefix):].strip("：: -")
                return text

            context_lines: list[str] = [
                f"任务标题：{task.title}",
                f"项目：{task.project}",
                f"阶段：{task.phase}",
                f"当前建议动作：{task.nextAdvice}",
                f"当前阻塞：{task.currentBlocker or '暂无显式阻塞'}",
                f"上下文摘要：{task.contextSummary or '暂无'}",
                f"当前缺口：{'；'.join(reasoning.missingContext) or '暂无'}",
            ]
            if task.linkedContexts:
                context_lines.append(
                    "关联对象：" + "；".join(
                        f"{item.label}{f'（{item.subtitle}）' if item.subtitle else ''}"
                        for item in task.linkedContexts[:6]
                    )
                )
            if reasoning.evidenceRefs:
                context_lines.append("证据引用：" + "；".join(reasoning.evidenceRefs[:6]))
            if guidance_items:
                context_lines.append(
                    "当前规则判断：" + "；".join(f"{item.title}：{item.judgment}" for item in guidance_items[:3])
                )
            if generic_lessons:
                context_lines.append(
                    "当前可迁移方法：" + "；".join(f"{item.title}：{item.judgment}" for item in generic_lessons[:3])
                )

            prompt = (
                "请基于下面的真实任务上下文，为“任务学习页”补一版 AI 综合判断。\n"
                "输出约束：\n"
                "1. judgment：只写一句“这次真正要学什么”，控制在 16-36 字。\n"
                "2. analysis：第一行写“为什么值得学：…”。后面最多三行，每行分别以“项目特有：”“阶段风险：”“上下文缺口：”开头。\n"
                "3. actions：只写一句“现在先做什么”，不要解释。\n"
                "4. timeline：每行以“AI贡献：”或“置信度：”开头，最多四行。\n"
                "5. 不要假装已经掌握缺失信息；如果证据不足，必须明确写进“上下文缺口”。\n"
                "6. 保持中文、简洁、可执行，不要写套话。\n\n"
                f"{chr(10).join(context_lines)}"
            )
            system_instruction = (
                "你是任务学习页的项目判断助手。你的职责不是替代规则，而是在真实任务上下文已经足够时，"
                "补充项目特有判断、阶段风险和可迁移方法。必须如实说明缺口，不得编造。"
            )

            try:
                structured = state.ai.generate_structured(prompt, system_instruction, task.contextSummary or "")
            except Exception:
                return None

            ai_headline = clean_ai_text(structured.judgment)
            ai_action = clean_ai_text(structured.actions) or task.nextAdvice
            analysis_lines = [
                clean_ai_text(line)
                for line in re.split(r"[\r\n]+", str(structured.analysis or ""))
                if clean_ai_text(line)
            ]
            why_line = next(
                (
                    clean_ai_text(line, prefixes=("为什么值得学", "为什么值得学：", "为什么值得学:"))
                    for line in analysis_lines
                    if line.startswith("为什么值得学")
                ),
                "",
            )
            if not why_line:
                why_line = clean_ai_text(structured.analysis) or (
                    guidance_items[0].whySpecial
                    if guidance_items
                    else "AI 已基于当前真实任务、背景和证据做了一次项目特有判断补充。"
                )

            ai_guidance: list[GrowthProjectGuidanceRecord] = []
            for index, line in enumerate(analysis_lines, start=1):
                guidance_type: Literal["project_specific", "stage_risk", "context_gap"] | None = None
                title = ""
                if line.startswith("项目特有"):
                    guidance_type = "project_specific"
                    title = "AI 识别到的项目特有提醒"
                elif line.startswith("阶段风险"):
                    guidance_type = "stage_risk"
                    title = "AI 识别到的阶段风险"
                elif line.startswith("上下文缺口"):
                    guidance_type = "context_gap"
                    title = "AI 识别到的上下文缺口"
                if guidance_type is None:
                    continue
                ai_guidance.append(
                    GrowthProjectGuidanceRecord(
                        id=f"{task.id}-ai-guidance-{index}",
                        title=title,
                        judgment=clean_ai_text(line, prefixes=("项目特有", "阶段风险", "上下文缺口")),
                        whySpecial="这条判断来自 AI 对真实任务、项目上下文和当前缺口的综合归纳。",
                        guidanceType=guidance_type,
                        linkedContexts=task.linkedContexts[:4],
                        evidenceRefs=reasoning.evidenceRefs[:4],
                    )
                )

            ai_timeline_lines = [
                clean_ai_text(line)
                for line in re.split(r"[\r\n]+", str(structured.timeline or ""))
                if clean_ai_text(line)
            ]
            ai_contribution = [
                clean_ai_text(line, prefixes=("AI贡献", "AI贡献：", "AI贡献:"))
                for line in ai_timeline_lines
                if line.startswith("AI贡献")
            ]
            confidence_line = next((line for line in ai_timeline_lines if line.startswith("置信度")), "")
            confidence_value = reasoning.confidence
            if "高" in confidence_line:
                confidence_value = "high"
            elif "中" in confidence_line:
                confidence_value = "medium"
            elif "低" in confidence_line:
                confidence_value = "low"

            merged_generic_lessons = list(generic_lessons)
            if ai_headline:
                ai_generic_lesson = GrowthGenericLessonRecord(
                    id=f"{task.id}-ai-lesson",
                    title="AI 抽象出的通用方法",
                    judgment=ai_headline,
                    applicableScene=f"当前处在「{task.phase}」阶段，且已有真实任务上下文。",
                    whyItWorks=why_line,
                    reuseHint="下次遇到同类任务时，先用这条方法判断应该先补哪一步，再决定是否扩写细节。",
                    linkedContext=preferred_task_context(task),
                )
                existing_titles = {normalize_text(item.title) for item in merged_generic_lessons}
                if normalize_text(ai_generic_lesson.title) not in existing_titles:
                    merged_generic_lessons = [ai_generic_lesson, *merged_generic_lessons]

            merged_guidance = [*ai_guidance, *guidance_items]
            deduped_guidance: list[GrowthProjectGuidanceRecord] = []
            seen_guidance_keys: set[str] = set()
            for item in merged_guidance:
                dedupe_key = normalize_text(f"{item.guidanceType}:{item.judgment}")
                if dedupe_key in seen_guidance_keys:
                    continue
                seen_guidance_keys.add(dedupe_key)
                deduped_guidance.append(item)

            updated_reasoning = GrowthReasoningTraceRecord(
                mode="ai_synthesized",
                usedInputs=reasoning.usedInputs,
                evidenceRefs=reasoning.evidenceRefs,
                missingContext=reasoning.missingContext,
                aiContribution=ai_contribution or [
                    "AI 已基于真实任务、项目上下文和证据线索做了一次项目特有判断补充。",
                    "AI 没有覆盖缺失上下文，缺口仍保留在页面里。",
                ],
                modelLabel=state.ai.current_model(),
                confidence=confidence_value,
            )
            updated_summary = GrowthLearningSummaryRecord(
                headline=ai_headline or reasoning.usedInputs[0].label,
                whyItMatters=why_line,
                immediateMove=ai_action,
                generator="ai",
                confidence=confidence_value,
            )
            return merged_generic_lessons[:3], deduped_guidance[:3], updated_reasoning, updated_summary

        def build_learning_summary(
            task: GrowthWorkbenchTaskRecord,
            guidance_items: list[GrowthProjectGuidanceRecord],
            reasoning: GrowthReasoningTraceRecord,
            *,
            source_mode_value: Literal["task", "growth_seed", "empty"],
        ) -> GrowthLearningSummaryRecord:
            if source_mode_value == "empty":
                return GrowthLearningSummaryRecord(
                    headline="当前还没有可学习的真实任务，上下文还没进入任务学习页。",
                    whyItMatters="没有真实任务、客户背景或事件线时，页面最多只能展示空壳，不能给出负责任的学习判断。",
                    immediateMove="先去任务与日历、客户工作台或战略陪伴生成一个真实对象，再回来学习。",
                    generator="rules",
                    confidence="low",
                )
            if source_mode_value == "growth_seed":
                return GrowthLearningSummaryRecord(
                    headline="先把成长信号压成真实任务，再谈更深的项目判断。",
                    whyItMatters="现在还处在成长种子模式，系统能告诉你先做什么，但不能假装已经理解了整个项目语境。",
                    immediateMove=task.nextAdvice or "先把这条信号落成真实任务，并补齐背景、附件和责任人。",
                    generator="rules",
                    confidence=reasoning.confidence,
                )
            if not task.hasBackground:
                headline = "这次最该学的不是直接推进，而是先把任务背景、目标和边界补清楚。"
            elif task.isCrossDepartment:
                headline = "这次真正要学的是：多人协作里先收边界、责任人与时间线。"
            elif task.phase in {"方案产出", "交付闭环"}:
                headline = "这次真正要学的是：先把结构和交付标准拉稳，再扩写细节。"
            elif task.phase == "复盘沉淀":
                headline = "这次真正要学的是：把有效动作拆成可复用方法，而不是只记结果。"
            else:
                headline = "这次真正要学的是：先判断当前阶段最关键的一步，再推进动作。"
            why_it_matters = (
                guidance_items[0].whySpecial
                if guidance_items
                else "任务学习页的价值不在于堆动作，而在于先说清这次任务真正值得学的判断。"
            )
            return GrowthLearningSummaryRecord(
                headline=headline,
                whyItMatters=why_it_matters,
                immediateMove=task.nextAdvice or (guidance_items[0].judgment if guidance_items else "先补当前任务的关键动作。"),
                generator="rules",
                confidence=reasoning.confidence,
            )

        def build_robot_assist(task: GrowthWorkbenchTaskRecord) -> GrowthRobotAssistRecord:
            haystack = f"{task.title}{task.project}{task.contextSummary}{task.currentBlocker or ''}"
            can_delegate: list[str] = []
            if any(keyword in haystack for keyword in ("会议", "对齐", "沟通", "纪要")):
                can_delegate.extend(["会议议程初稿", "会后纪要骨架", "行动项清单"])
            if any(keyword in haystack for keyword in ("方案", "提案", "白皮书", "文档", "大纲", "写")):
                can_delegate.extend(["结构化大纲", "首版文档骨架", "待确认问题清单"])
            if any(keyword in haystack for keyword in ("复盘", "总结", "方法", "沉淀")):
                can_delegate.extend(["复盘骨架", "方法卡初稿"])
            if task.evidenceCount > 0 or task.sourceEvidence:
                can_delegate.append("材料整理与证据摘录")
            if not can_delegate:
                can_delegate.extend(["待确认问题清单", "材料整理清单"])

            must_stay_human: list[str] = []
            if task.isCrossDepartment or task.pendingCollaborations > 0:
                must_stay_human.append("跨部门边界和责任分配")
            if any(keyword in haystack for keyword in ("客户", "沟通", "谈判", "协调")):
                must_stay_human.append("关键对象口径和现场判断")
            if task.needsReview:
                must_stay_human.append("复核 / 审批结论")
            must_stay_human.append("最终优先级和是否推进的拍板")
            return GrowthRobotAssistRecord(
                ready=task.robotReady,
                canDelegate=dedupe_strings(can_delegate, limit=3),
                mustStayHuman=dedupe_strings(must_stay_human, limit=3),
                why=dedupe_strings(task.robotReasons, limit=3),
            )

        def build_after_action_capture(
            task: GrowthWorkbenchTaskRecord,
            captures: list[GrowthPendingCaptureRecord],
        ) -> GrowthAfterActionCaptureRecord:
            if captures:
                capture = captures[0]
                return GrowthAfterActionCaptureRecord(
                    title=capture.title,
                    summary=capture.summary or capture.nextActionText,
                    experienceType="待放大成长信号",
                    recommendedWriteback=(
                        f"优先写回事件线「{capture.eventLineName}」" if capture.eventLineName else f"优先写回客户「{capture.clientName}」" if capture.clientName else "写回成长手册或项目经验库"
                    ),
                )
            return GrowthAfterActionCaptureRecord(
                title=f"{task.title}：{task.phase} 阶段复盘",
                summary=f"记录这次在「{task.phase}」阶段的关键判断、有效动作、适用边界和下次可复用的方法。",
                experienceType="方法卡" if task.isCrossDepartment or task.phase in {"沟通推进", "复盘沉淀"} else "复盘卡",
                recommendedWriteback=(
                    f"优先写回事件线「{task.eventLineName}」" if task.eventLineName else f"优先写回客户「{task.project}」背景与经验库" if task.project else "写回成长手册"
                ),
            )

        user_id, user_name = resolve_growth_actor()
        resolved_week = resolve_growth_week_label(user_id, week_label)
        overview = build_growth_overview(state.db, user_id=user_id, user_name=user_name, week_label=resolved_week)

        real_tasks = (
            fetch_tasks("t.source_type != ? AND t.status NOT IN ('done', 'rejected')", (AGENT_AUTO_SOURCE_TYPE,))
        )
        real_tasks = sorted(
            real_tasks,
            key=lambda task: (
                {"doing": 0, "todo": 1, "inbox": 2, "done": 3, "rejected": 4}.get(task.status, 5),
                {"high": 0, "normal": 1, "low": 2}.get(task.priority, 3),
                parse_task_date(task.dueDate or task.ddl) or datetime.max,
                -sort_updated_at(task.updatedAt).timestamp(),
            ),
        )
        if normalized_mode == "strategic":
            strategic_ranked: list[tuple[int, int, TaskRecord]] = []
            for index, task in enumerate(real_tasks):
                is_client_match = bool(scoped_client_id and task_client_matches(task, scoped_client_id))
                is_keyword_match = is_strategic_learning_task(task, scoped_client_id)
                if is_client_match:
                    strategic_ranked.append((0, index, task))
                    continue
                if is_keyword_match:
                    strategic_ranked.append((1, index, task))
            strategic_ranked.sort(key=lambda item: (item[0], item[1]))
            real_tasks = [task for _, _, task in strategic_ranked]

        workbench_tasks = [workbench_task_from_task(task) for task in real_tasks[:3]]
        source_mode: Literal["task", "growth_seed", "empty"] = "task"
        if not workbench_tasks:
            source_mode = "growth_seed"
            focus_actions = overview.currentFocusActions
            recommendations = overview.recommendations
            pending_captures = overview.pendingCaptures
            if normalized_mode == "strategic" and scoped_client_id:
                focus_actions = [
                    item
                    for item in focus_actions
                    if normalize_text(item.clientId) == scoped_client_id
                    or any(context.objectType == "client" and normalize_text(context.objectId) == scoped_client_id for context in item.linkedContexts)
                ]
                recommendations = [
                    item
                    for item in recommendations
                    if normalize_text(item.clientId) == scoped_client_id
                    or any(context.objectType == "client" and normalize_text(context.objectId) == scoped_client_id for context in item.linkedContexts)
                ]
                pending_captures = [
                    item
                    for item in pending_captures
                    if normalize_text(item.clientId) == scoped_client_id
                    or any(context.objectType == "client" and normalize_text(context.objectId) == scoped_client_id for context in item.linkedContexts)
                ]
            if focus_actions:
                workbench_tasks = [workbench_task_from_focus(index, action) for index, action in enumerate(focus_actions[:2])]
            elif recommendations:
                workbench_tasks = [workbench_task_from_recommendation(index, item) for index, item in enumerate(recommendations[:2])]
            elif pending_captures:
                workbench_tasks = [workbench_task_from_capture(index, item) for index, item in enumerate(pending_captures[:2])]
        if not workbench_tasks:
            source_mode = "empty"
            process_steps = [GrowthWorkbenchStepRecord(id=step_id, name=name, output=output, bottlenecks=bottlenecks) for step_id, name, output, bottlenecks in phase_blueprints]
            active_process_id = next((step.id for step in process_steps if step.name == "信息核对"), process_steps[1].id if len(process_steps) > 1 else None)
            if normalized_mode == "strategic":
                preset_cards = default_starter_learning_presets(mode="strategic")
                strategic_generic_lessons = [preset_card_to_generic_lesson(card) for card in preset_cards]
                strategic_support_materials = [preset_card_to_support_material(card) for card in preset_cards[:6]]
                preset_checklist = dedupe_strings(
                    [item for card in preset_cards for item in card.checklist],
                    limit=8,
                )
                preset_before, preset_during, preset_after = build_actions_from_presets(preset_cards)
                return GrowthWorkbenchSnapshotRecord(
                    tasks=[],
                    activeTaskId=None,
                    learningSummary=GrowthLearningSummaryRecord(
                        headline="还没有真实任务，先从基础训练开始",
                        whyItMatters="这些是战略陪伴高频方法卡，不是针对某个客户的个性化判断。创建客户任务或会议行动项后，系统会自动生成更具体的学习清单。",
                        immediateMove="先选择一张方法卡，或从客户工作台把一个问题转成任务。",
                        generator="rules",
                        confidence="low",
                    ),
                    genericLessons=strategic_generic_lessons[:6],
                    projectGuidance=[
                        GrowthProjectGuidanceRecord(
                            id="strategic-empty-context",
                            title="当前是基础训练模式",
                            judgment="系统尚未拿到可用于战略陪伴判断的真实任务对象，因此先返回预置方法卡。",
                            whySpecial="这不是个性化判断。创建任务、补充会议纪要或事件线后，推荐会切换为实时匹配。",
                            guidanceType="context_gap",
                            linkedContexts=[],
                            evidenceRefs=["缺真实任务", "缺客户上下文", "缺会议 / 项目资料"],
                        )
                    ],
                    reasoningTrace=GrowthReasoningTraceRecord(
                        mode="rules_only",
                        usedInputs=[
                            GrowthReasoningInputRecord(
                                id="strategic-rule-only",
                                sourceType="rule",
                                label="预置方法卡规则",
                                detail="当前没有真实任务输入，系统返回战略陪伴基础训练卡。",
                            )
                        ],
                        evidenceRefs=[],
                        missingContext=["缺真实任务", "缺客户上下文", "缺会议 / 项目资料"],
                        aiContribution=[],
                        modelLabel=None,
                        confidence="low",
                    ),
                    robotAssist=GrowthRobotAssistRecord(
                        ready=False,
                        canDelegate=[],
                        mustStayHuman=["先形成真实任务对象"],
                        why=["当前没有真实任务上下文，机器人无法输出可靠执行包。"],
                    ),
                    afterActionCapture=GrowthAfterActionCaptureRecord(
                        title="先沉淀为基础练习记录",
                        summary="完成任意一张方法卡后，建议把有效动作写回成长手册。",
                        experienceType="基础训练",
                        recommendedWriteback="优先写回成长手册",
                    ),
                    processSteps=process_steps,
                    activeProcessId=active_process_id,
                    actionsBefore=cast(list[GrowthWorkbenchActionRecord], dedupe_records_by_id(preset_before, limit=4)),
                    actionsDuring=cast(list[GrowthWorkbenchActionRecord], dedupe_records_by_id(preset_during, limit=4)),
                    actionsAfter=cast(list[GrowthWorkbenchActionRecord], dedupe_records_by_id(preset_after, limit=4)),
                    supportMaterials=cast(list[GrowthWorkbenchMaterialRecord], dedupe_records_by_id(strategic_support_materials, limit=6)),
                    checklistItems=preset_checklist,
                    supportCopy=GrowthWorkbenchSupportCopyRecord(
                        title="当前是基础训练模式（非个性化判断）",
                        intro="你还没有把真实任务带入学习清单。先练一张方法卡，或先创建客户任务，再回来即可获得更精准推荐。",
                        bullets=["本轮为规则匹配，没有调用 AI 自由生成学习建议。"],
                    ),
                    robotPlan=[],
                    sourceMode=source_mode,
                    scopeMode=normalized_mode,
                    scopeClientId=scoped_client_id,
                    scopeClientName=scope_client_name,
                    updatedAt=now_iso(),
                )
            return GrowthWorkbenchSnapshotRecord(
                tasks=[],
                activeTaskId=None,
                learningSummary=GrowthLearningSummaryRecord(
                    headline="当前还没有可学习的真实任务。",
                    whyItMatters="没有真实任务、项目上下文或成长信号时，系统不能负责任地给出学习判断。",
                    immediateMove="先去任务与日历、客户工作台或战略陪伴形成真实对象，再回来学习。",
                    generator="rules",
                    confidence="low",
                ),
                genericLessons=[],
                projectGuidance=[
                    GrowthProjectGuidanceRecord(
                        id="empty-context",
                        title="当前只能给空白提示",
                        judgment="系统还没有拿到真实任务、附件、事件线或项目背景，所以这里不会假装在做深度分析。",
                        whySpecial="任务学习页应该建立在真实对象上，而不是建立在想象中的项目上。",
                        guidanceType="context_gap",
                        linkedContexts=[],
                        evidenceRefs=["缺真实任务", "缺项目上下文"],
                    )
                ],
                reasoningTrace=GrowthReasoningTraceRecord(
                    mode="rules_only",
                    usedInputs=[
                        GrowthReasoningInputRecord(
                            id="rule-only",
                            sourceType="rule",
                            label="空上下文保护规则",
                            detail="当前没有真实对象输入，所以系统只返回空白保护提示。",
                        )
                    ],
                    evidenceRefs=[],
                    missingContext=["缺真实任务", "缺项目背景", "缺事件线连续上下文"],
                    aiContribution=[],
                    modelLabel=None,
                    confidence="low",
                ),
                robotAssist=GrowthRobotAssistRecord(
                    ready=False,
                    canDelegate=[],
                    mustStayHuman=["先创建真实任务或业务对象"],
                    why=["没有真实对象输入前，机器人也无法给出有意义的执行包。"],
                ),
                afterActionCapture=GrowthAfterActionCaptureRecord(
                    title="当前没有可沉淀内容",
                    summary="先让真实任务进入学习页，再决定沉淀成什么。",
                    experienceType="待创建",
                    recommendedWriteback="暂不写回",
                ),
                processSteps=process_steps,
                activeProcessId=active_process_id,
                actionsBefore=[],
                actionsDuring=[],
                actionsAfter=[],
                supportMaterials=[],
                checklistItems=[],
                supportCopy=GrowthWorkbenchSupportCopyRecord(
                    title="当前没有可执行的成长上下文",
                    intro="先在任务与日历创建一条任务，或在客户工作台发布会议 / 行动项，任务学习页就会自动补齐上下文。",
                    bullets=["当前没有真实任务、事件线或成长推荐进入任务学习页。"],
                ),
                robotPlan=[],
                sourceMode=source_mode,
                scopeMode=normalized_mode,
                scopeClientId=scoped_client_id,
                scopeClientName=scope_client_name,
                updatedAt=now_iso(),
            )

        active_task = workbench_tasks[0]
        related_focus_actions = [item for item in overview.currentFocusActions if matches_task(active_task, linked_task_id=item.linkedTaskId, linked_contexts=item.linkedContexts, client_name=item.clientName, event_line_name=item.eventLineName, project_stage=item.projectStage or item.triggerNode)][:3]
        related_captures = [item for item in overview.pendingCaptures if matches_task(active_task, linked_contexts=item.linkedContexts, client_name=item.clientName, event_line_name=item.eventLineName, project_stage=item.projectStage)][:3]
        related_recommendations = [item for item in overview.recommendations if matches_task(active_task, linked_task_id=item.linkedTaskId, linked_contexts=item.linkedContexts, client_name=item.clientName, event_line_name=item.eventLineName, project_stage=item.projectStage or item.triggerNode)][:3]
        generic_lessons = build_generic_lessons(active_task, related_focus_actions, related_captures, related_recommendations)
        project_guidance = build_project_guidance(active_task, related_focus_actions, related_captures, related_recommendations, source_mode_value=source_mode)
        reasoning_trace = build_reasoning_trace(active_task, related_focus_actions, related_captures, related_recommendations, source_mode_value=source_mode)
        learning_summary = build_learning_summary(active_task, project_guidance, reasoning_trace, source_mode_value=source_mode)
        robot_assist = build_robot_assist(active_task)
        after_action_capture = build_after_action_capture(active_task, related_captures)
        preset_cards = (
            match_learning_presets(
                task_title=active_task.title,
                task_desc=active_task.contextSummary,
                phase=active_task.phase,
                client_name=scope_client_name or active_task.clientName or None,
                current_blocker=active_task.currentBlocker,
                evidence_count=active_task.evidenceCount,
                mode="strategic",
            )
            if normalized_mode == "strategic"
            else []
        )
        if normalized_mode != "strategic":
            ai_learning_bundle = build_ai_learning_synthesis(
                active_task,
                generic_lessons,
                project_guidance,
                reasoning_trace,
                source_mode_value=source_mode,
            )
            if ai_learning_bundle:
                generic_lessons, project_guidance, reasoning_trace, learning_summary = ai_learning_bundle
        elif preset_cards:
            strategic_generic_lessons = [preset_card_to_generic_lesson(card, task_title=active_task.title) for card in preset_cards]
            merged_generic_lessons = dedupe_records_by_id([*strategic_generic_lessons, *generic_lessons], limit=6)
            generic_lessons = cast(list[GrowthGenericLessonRecord], merged_generic_lessons)

            strategic_missing_context = [
                "缺真实任务" if source_mode != "task" else "",
                "缺客户上下文" if not scoped_client_id else "",
                "缺会议 / 项目资料" if active_task.evidenceCount <= 0 and not active_task.sourceEvidence else "",
            ]
            strategic_inputs = [
                *reasoning_trace.usedInputs,
                GrowthReasoningInputRecord(
                    id=f"strategic-task-{active_task.id}",
                    sourceType="task",
                    label=active_task.title,
                    detail=active_task.phase or "当前任务",
                ),
                GrowthReasoningInputRecord(
                    id=f"strategic-client-{scoped_client_id or 'all'}",
                    sourceType="client" if scoped_client_id else "rule",
                    label=scope_client_name or "全部客户",
                    detail="当前客户作用域" if scoped_client_id else "全局战略作用域",
                ),
                GrowthReasoningInputRecord(
                    id="strategic-preset-rule",
                    sourceType="rule",
                    label="预置方法卡规则",
                    detail="根据任务标题、阶段、阻点和证据数量进行规则匹配。",
                ),
            ]
            reasoning_trace = GrowthReasoningTraceRecord(
                mode="rules_only",
                usedInputs=cast(list[GrowthReasoningInputRecord], dedupe_records_by_id(strategic_inputs, limit=8)),
                evidenceRefs=reasoning_trace.evidenceRefs,
                missingContext=dedupe_strings(reasoning_trace.missingContext + strategic_missing_context, limit=6),
                aiContribution=[],
                modelLabel=None,
                confidence="medium" if source_mode == "task" else "low",
            )
            first_preset = preset_cards[0]
            learning_summary = GrowthLearningSummaryRecord(
                headline=f"当前最值得练：{first_preset.title}",
                whyItMatters=(
                    f"当前对象处在「{active_task.phase}」阶段，这张卡可以帮助你把下一步动作做实。"
                    if source_mode == "task"
                    else "当前还没有真实任务，因此先展示战略陪伴最常用的基础方法卡。"
                ),
                immediateMove=first_preset.steps[0] if first_preset.steps else "先选择一张方法卡开始练习。",
                generator="rules",
                confidence="medium" if source_mode == "task" else "low",
            )

        process_steps: list[GrowthWorkbenchStepRecord] = []
        active_process_id: str | None = None
        for step_id, name, output, bottlenecks in phase_blueprints:
            if name == active_task.phase:
                process_steps.append(
                    GrowthWorkbenchStepRecord(
                        id=step_id,
                        name=name,
                        output=active_task.nextAdvice or output,
                        bottlenecks=active_task.risks[:2] or bottlenecks,
                    )
                )
                active_process_id = step_id
            elif name == "复盘沉淀" and related_captures:
                process_steps.append(
                    GrowthWorkbenchStepRecord(
                        id=step_id,
                        name=name,
                        output=related_captures[0].nextActionText or output,
                        bottlenecks=related_captures[0].missingReasons[:2] or bottlenecks,
                    )
                )
            else:
                process_steps.append(GrowthWorkbenchStepRecord(id=step_id, name=name, output=output, bottlenecks=bottlenecks))
        active_process_id = active_process_id or process_steps[0].id

        primary_context = active_task.linkedContexts[0] if active_task.linkedContexts else None
        before_actions = [
            GrowthWorkbenchActionRecord(
                id=f"{active_task.id}-before-1",
                title=related_focus_actions[0].title if related_focus_actions else f"开始前先定：{active_task.title} 的目标与边界",
                output=related_focus_actions[0].summary if related_focus_actions else f"{active_task.nextAdvice or active_task.phase}，并明确第一责任人",
                scenario=f"{active_task.phase} 开始前",
                actionLabel="排入练习" if active_task.recommendationId else "打开当前任务",
                supportTitle="查看为什么要做这一步",
                detail=related_focus_actions[0].whyNow if related_focus_actions else active_task.contextSummary,
                kind="schedule" if active_task.recommendationId else "task",
                recommendationId=active_task.recommendationId,
                linkedContext=primary_context,
            ),
            GrowthWorkbenchActionRecord(
                id=f"{active_task.id}-before-2",
                title=f"优先处理卡点：{active_task.currentBlocker}" if active_task.currentBlocker else "识别风险：先排查最可能翻车的 2 个点",
                output=related_captures[0].nextActionText if related_captures else "关键争议点 + 一条可执行预案",
                scenario="正式拉人或开工前",
                actionLabel="回到当前任务" if active_task.currentBlocker else "先做风险排查",
                supportTitle="查看常见翻车案例",
                detail=(related_captures[0].missingReasons[0] if related_captures and related_captures[0].missingReasons else "") or (active_task.risks[0] if active_task.risks else ""),
                kind="task" if active_task.currentBlocker else "support",
                linkedContext=primary_context,
            ),
        ]
        during_actions = [
            GrowthWorkbenchActionRecord(
                id=f"{active_task.id}-during-1",
                title=f"执行中关键动作：稳住{active_task.phase}",
                output="各方认同的交付物、边界与时间线" if active_task.isCrossDepartment else active_task.nextAdvice,
                scenario="讨论开始发散或推进变慢时",
                actionLabel="生成沟通话术" if active_task.isCrossDepartment else "查看节点清单",
                supportTitle="查看沟通原理" if active_task.isCrossDepartment else "查看节点标准",
                detail=active_task.contextSummary,
                kind="support",
                linkedContext=primary_context,
            )
        ]
        after_actions = [
            GrowthWorkbenchActionRecord(
                id=f"{active_task.id}-after-1",
                title=f"完成后补强：{related_captures[0].title}" if related_captures else "完成后沉淀：把这次动作转成可复用经验",
                output=related_captures[0].nextActionText if related_captures else f"一条可复用经验 + {active_task.xpReward} XP 的练习回流",
                scenario="动作完成后 2 小时内",
                actionLabel="沉淀为经验" if related_captures else "去记录经验",
                supportTitle=(related_captures[0].missingReasons[0] if related_captures and related_captures[0].missingReasons else "") or "查看标准沉淀方式",
                kind="compose",
                linkedContext=primary_context,
                seedTitle=related_captures[0].title if related_captures else active_task.title,
                seedSummary=(related_captures[0].summary or related_captures[0].nextActionText) if related_captures else active_task.nextAdvice,
            )
        ]
        if normalized_mode == "strategic" and preset_cards:
            preset_before, preset_during, preset_after = build_actions_from_presets(preset_cards)
            before_actions = cast(
                list[GrowthWorkbenchActionRecord],
                dedupe_records_by_id([*preset_before, *before_actions], limit=6),
            )
            during_actions = cast(
                list[GrowthWorkbenchActionRecord],
                dedupe_records_by_id([*preset_during, *during_actions], limit=6),
            )
            after_actions = cast(
                list[GrowthWorkbenchActionRecord],
                dedupe_records_by_id([*preset_after, *after_actions], limit=6),
            )
        support_materials: list[GrowthWorkbenchMaterialRecord] = []
        if active_task.projectFlowName or active_task.projectModuleName:
            support_materials.append(
                GrowthWorkbenchMaterialRecord(
                    id=f"{active_task.id}-flow",
                    title=active_task.projectFlowName or active_task.projectModuleName or "当前项目流程说明",
                    type="流程说明",
                    scenario=active_task.contextSummary or f"适用于当前 {active_task.phase} 阶段",
                    summary=(active_task.sourceEvidence[0] if active_task.sourceEvidence else "") or active_task.nextAdvice,
                    linkedContext=next((context for context in active_task.linkedContexts if context.objectType in {"project_flow", "project_module", "task"}), primary_context),
                )
            )
        if related_recommendations:
            support_materials.append(
                GrowthWorkbenchMaterialRecord(
                    id=f"recommendation-{related_recommendations[0].id}",
                    title=related_recommendations[0].summary or related_recommendations[0].title,
                    type="模板工具" if related_recommendations[0].contentType == "practice_card" else "流程说明",
                    scenario=related_recommendations[0].whyNow or related_recommendations[0].reason,
                    summary=related_recommendations[0].practiceTask or related_recommendations[0].summary,
                    linkedContext=related_recommendations[0].linkedContexts[0] if related_recommendations[0].linkedContexts else None,
                )
            )
        if related_captures:
            support_materials.append(
                GrowthWorkbenchMaterialRecord(
                    id=f"capture-{related_captures[0].id}",
                    title=related_captures[0].title,
                    type="经验案例",
                    scenario=related_captures[0].summary or related_captures[0].projectStage or "系统已识别到待放大的成长信号",
                    summary="；".join(related_captures[0].missingReasons) or related_captures[0].nextActionText,
                    linkedContext=related_captures[0].linkedContexts[0] if related_captures[0].linkedContexts else None,
                )
            )
        if normalized_mode == "strategic" and preset_cards:
            preset_materials = [preset_card_to_support_material(card) for card in preset_cards]
            support_materials = cast(
                list[GrowthWorkbenchMaterialRecord],
                dedupe_records_by_id([*preset_materials, *support_materials], limit=6),
            )
        else:
            support_materials = support_materials[:3]
        checklist_items = [
            f"明确该节点的预期产出：{next((step.output for step in process_steps if step.id == active_process_id), active_task.nextAdvice)}",
            "补齐任务背景、目标和预期输出" if not active_task.hasBackground else "",
            "补齐明确的截止时间或推进节奏" if not active_task.hasDeadline else "",
            "把协作边界、责任人和时间点讲清楚" if active_task.isCrossDepartment else "",
            f"完成 {active_task.pendingCollaborations} 个待确认协作动作" if active_task.pendingCollaborations > 0 else "",
            "补复核说明、审批依据或验证证据" if active_task.needsReview else "",
            f"把「{related_focus_actions[0].title}」压进当前任务动作清单" if related_focus_actions else "",
            f"完成后处理「{related_captures[0].title}」的复盘或经验沉淀" if related_captures else "",
        ]
        checklist_items = [item for item in checklist_items if item]
        if normalized_mode == "strategic" and preset_cards:
            preset_checklist = [item for card in preset_cards for item in card.checklist]
            checklist_items = dedupe_strings([*preset_checklist, *checklist_items], limit=8)
        else:
            checklist_items = checklist_items[:5]
        support_copy = GrowthWorkbenchSupportCopyRecord(
            title=(
                "当前是基础训练模式（非个性化判断）"
                if normalized_mode == "strategic" and source_mode != "task"
                else (
                    "为什么这件事要先讲清边界与责任？"
                    if active_task.isCrossDepartment
                    else ("为什么开始前一定要先补齐上下文？" if not active_task.hasBackground else (f"为什么在「{active_task.phase}」阶段要先补关键动作？"))
                )
            ),
            intro=(
                "系统当前优先给出预置方法卡，帮助你把任务对象、证据和行动结构先搭起来。"
                if normalized_mode == "strategic" and source_mode != "task"
                else (
                    "这类跨部门或多人任务最容易翻车的点，不是大家不努力，而是边界、责任人和时间点没有先被讲清楚。"
                    if active_task.isCrossDepartment
                    else ("系统已经识别到当前任务缺少背景、目标或预期输出。没有这些上下文，后续动作看起来很忙，但很容易做偏。" if not active_task.hasBackground else "学习导航不是给你一堆资料，而是提醒你在当前节点最应该补的那一步。先把动作做对，再去扩写内容。")
                )
            ),
            bullets=[
                "当前轮次为规则匹配，没有调用 AI 自由生成学习建议。" if normalized_mode == "strategic" else ("当前任务已经有基础背景，可以直接对齐关键动作。" if active_task.hasBackground else "先写清任务目标、对象和预期交付物。"),
                "先把当前问题转成真实任务，系统再给个性化学习清单。" if normalized_mode == "strategic" and source_mode != "task" else ("当前已经有时间点，下一步重点是把责任和边界讲清楚。" if active_task.hasDeadline else "没有截止时间时，动作很容易在中途失焦。"),
                "沉淀到成长手册后，下次可直接复用这张方法卡。" if normalized_mode == "strategic" else ("跨部门任务要优先处理协作边界，避免会后推诿返工。" if active_task.isCrossDepartment else "单点任务更要先补事实依据和当前阶段判断。"),
            ],
        )
        robot_plan = [
            f"根据 {active_task.project} 的上下文，先拟一版「{active_task.phase}」阶段动作清单",
            f"围绕当前卡点「{active_task.currentBlocker}」生成一版应对草案" if active_task.currentBlocker else "",
            f"把推荐动作「{related_focus_actions[0].title}」整理成可直接执行的脚本或清单" if related_focus_actions else "",
            f"预先生成「{related_captures[0].title}」对应的复盘或经验沉淀骨架" if related_captures else "",
        ]
        robot_plan = [item for item in robot_plan if item][:3]
        return GrowthWorkbenchSnapshotRecord(
            tasks=workbench_tasks,
            activeTaskId=active_task.id,
            learningSummary=learning_summary,
            genericLessons=generic_lessons,
            projectGuidance=project_guidance,
            reasoningTrace=reasoning_trace,
            robotAssist=robot_assist,
            afterActionCapture=after_action_capture,
            processSteps=process_steps,
            activeProcessId=active_process_id,
            actionsBefore=before_actions,
            actionsDuring=during_actions,
            actionsAfter=after_actions,
            supportMaterials=support_materials,
            checklistItems=checklist_items,
            supportCopy=support_copy,
            robotPlan=robot_plan,
            sourceMode=source_mode,
            scopeMode=normalized_mode,
            scopeClientId=scoped_client_id,
            scopeClientName=scope_client_name,
            updatedAt=now_iso(),
        )

    def _builtin_task_view_blueprints() -> list[dict[str, object]]:
        visible_fields = ["title", "status", "priority", "sourceType", "businessCategory", "eventLine", "evidenceCount"]
        return [
            {
                "id": "builtin_event_line_view",
                "name": "事件线视图",
                "kind": "event_line",
                "description": "优先看已经挂到事件线的持续推进事项。",
                "calendarScope": "event_line",
                "shareability": "org",
                "sortBy": "updatedAt",
                "sortDirection": "desc",
                "visibleFields": visible_fields,
                "filterSet": {"onlyWithEventLine": True},
                "builtIn": True,
            },
            {
                "id": "builtin_risk_view",
                "name": "风险视图",
                "kind": "risk",
                "description": "优先看有阻塞、待复核、低证据或已逾期的事项。",
                "calendarScope": "risk",
                "shareability": "org",
                "sortBy": "evidenceCount",
                "sortDirection": "asc",
                "visibleFields": visible_fields,
                "filterSet": {"onlyRisky": True},
                "builtIn": True,
            },
            {
                "id": "builtin_source_view",
                "name": "来源视图",
                "kind": "source",
                "description": "按会议、周判断动作、支持请求等来源追踪任务。",
                "calendarScope": "source",
                "shareability": "org",
                "sortBy": "updatedAt",
                "sortDirection": "desc",
                "visibleFields": visible_fields,
                "filterSet": {},
                "builtIn": True,
            },
            {
                "id": "builtin_business_category_view",
                "name": "业务分类视图",
                "kind": "business_category",
                "description": "按业务扩展、项目推进、组织协同等业务类别查看任务。",
                "calendarScope": "business_category",
                "shareability": "org",
                "sortBy": "updatedAt",
                "sortDirection": "desc",
                "visibleFields": visible_fields,
                "filterSet": {},
                "builtIn": True,
            },
        ]

    def _task_view_record_from_row(row) -> TaskViewDefinitionRecord:
        visible_fields = from_json(row["visible_fields_json"], [])
        filter_set = from_json(row["filter_set_json"], {})
        return TaskViewDefinitionRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            kind=str(row["kind"]),  # type: ignore[arg-type]
            description=str(row["description"] or ""),
            calendarScope=str(row["calendar_scope"] or "all"),  # type: ignore[arg-type]
            shareability=str(row["shareability"] or "private"),  # type: ignore[arg-type]
            sortBy=str(row["sort_by"] or "updatedAt"),  # type: ignore[arg-type]
            sortDirection=str(row["sort_direction"] or "desc"),  # type: ignore[arg-type]
            visibleFields=[str(item) for item in visible_fields if str(item).strip()],
            filterSet=filter_set if isinstance(filter_set, dict) else {},
            builtIn=bool(int(row["built_in"] or 0)),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def _task_view_presets(views: list[TaskViewDefinitionRecord]) -> list[TaskViewPresetRecord]:
        presets: list[TaskViewPresetRecord] = []
        for key, label, description in [
            ("event_line", "事件线视图", "按持续推进的工作线查看任务"),
            ("risk", "风险视图", "优先看阻塞、复核与低证据事项"),
            ("source", "来源视图", "按会议、支持请求、周判断动作等来源查看"),
            ("business_category", "业务分类视图", "按业务扩展、项目推进、组织协同等查看"),
        ]:
            matched = next((item for item in views if item.kind == key and item.builtIn), None)
            if matched:
                presets.append(
                    TaskViewPresetRecord(
                        key=key,  # type: ignore[arg-type]
                        label=label,
                        description=description,
                        viewId=matched.id,
                    )
                )
        return presets

    def _ensure_builtin_task_views() -> list[TaskViewDefinitionRecord]:
        timestamp = now_iso()
        for blueprint in _builtin_task_view_blueprints():
            state.db.execute(
                """
                INSERT OR IGNORE INTO task_views(
                    id, name, kind, description, calendar_scope, shareability, sort_by, sort_direction,
                    visible_fields_json, filter_set_json, built_in, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(blueprint["id"]),
                    str(blueprint["name"]),
                    str(blueprint["kind"]),
                    str(blueprint["description"]),
                    str(blueprint["calendarScope"]),
                    str(blueprint["shareability"]),
                    str(blueprint["sortBy"]),
                    str(blueprint["sortDirection"]),
                    to_json(blueprint["visibleFields"]),
                    to_json(blueprint["filterSet"]),
                    1,
                    timestamp,
                    timestamp,
                ),
            )
            state.db.execute(
                """
                UPDATE task_views
                   SET name = ?, kind = ?, description = ?, calendar_scope = ?, shareability = ?,
                       sort_by = ?, sort_direction = ?, visible_fields_json = ?, filter_set_json = ?,
                       built_in = 1, updated_at = ?
                 WHERE id = ?
                """,
                (
                    str(blueprint["name"]),
                    str(blueprint["kind"]),
                    str(blueprint["description"]),
                    str(blueprint["calendarScope"]),
                    str(blueprint["shareability"]),
                    str(blueprint["sortBy"]),
                    str(blueprint["sortDirection"]),
                    to_json(blueprint["visibleFields"]),
                    to_json(blueprint["filterSet"]),
                    timestamp,
                    str(blueprint["id"]),
                ),
            )
        rows = state.db.fetchall("SELECT * FROM task_views ORDER BY built_in DESC, updated_at DESC")
        return [_task_view_record_from_row(row) for row in rows]

    def _task_is_risky(task: TaskRecord) -> bool:
        if bool(task.orgContext and task.orgContext.needsReview):
            return True
        if (task.currentBlocker or "").strip():
            return True
        if is_task_overdue(task):
            return True
        return int(task.evidenceCount or 0) <= 1 and task.status != "done"

    def _matches_task_view(task: TaskRecord, view: TaskViewDefinitionRecord, extra_filters: dict[str, object] | None = None) -> bool:
        filters = dict(extra_filters or {})
        filter_set = view.filterSet
        source_types = list(filters.get("sourceTypes") or filter_set.sourceTypes or [])
        business_categories = list(filters.get("businessCategories") or filter_set.businessCategories or [])
        event_line_ids = list(filters.get("eventLineIds") or filter_set.eventLineIds or [])
        client_names = [str(item).strip() for item in filters.get("clientNames", []) if str(item).strip()]
        related_task_ids = [str(item).strip() for item in filters.get("relatedTaskIds", []) if str(item).strip()]
        only_risky = bool(filters.get("onlyRisky", filter_set.onlyRisky))
        only_with_event_line = bool(filters.get("onlyWithEventLine", filter_set.onlyWithEventLine))
        needs_review = filters.get("needsReview", filter_set.needsReview)
        minimum_evidence = filters.get("minimumEvidenceCount", filter_set.minimumEvidenceCount)

        if view.kind == "event_line" and not (task.eventLineId or "").strip():
            return False
        if view.kind == "risk" and not _task_is_risky(task):
            return False
        if view.kind == "source" and (task.sourceType or "").strip() in {"", "manual"}:
            return False
        if view.kind == "business_category" and not (task.businessCategory or "").strip():
            return False
        if source_types and (task.sourceType or "") not in source_types:
            return False
        if business_categories and (task.businessCategory or "") not in business_categories:
            return False
        if event_line_ids and (task.eventLineId or "") not in event_line_ids:
            return False
        if client_names and (task.projectContext.clientName if task.projectContext else "") not in client_names:
            return False
        if related_task_ids and task.id not in related_task_ids:
            return False
        if only_risky and not _task_is_risky(task):
            return False
        if only_with_event_line and not (task.eventLineId or "").strip():
            return False
        if needs_review is not None and bool(task.orgContext and task.orgContext.needsReview) != bool(needs_review):
            return False
        if minimum_evidence is not None and int(task.evidenceCount or 0) < int(minimum_evidence):
            return False
        return True

    def _sort_tasks_for_view(tasks: list[TaskRecord], view: TaskViewDefinitionRecord) -> list[TaskRecord]:
        reverse = view.sortDirection == "desc"

        def priority_rank(task: TaskRecord) -> int:
            return {"high": 0, "medium": 1, "low": 2}.get(task.priority, 3)

        def due_timestamp(task: TaskRecord) -> float:
            parsed = parse_task_date_value(task.dueDate)
            return parsed.timestamp() if parsed else 0

        if view.sortBy == "priority":
            return sorted(tasks, key=priority_rank, reverse=reverse)
        if view.sortBy == "dueDate":
            return sorted(tasks, key=due_timestamp, reverse=reverse)
        if view.sortBy == "evidenceCount":
            return sorted(tasks, key=lambda item: int(item.evidenceCount or 0), reverse=reverse)
        return sorted(tasks, key=lambda item: item.updatedAt, reverse=reverse)

    def _task_records_for_ids(task_ids: list[str]) -> list[TaskRecord]:
        wanted = {task_id for task_id in task_ids if task_id}
        if not wanted:
            return []
        records = _task_records_for_views()
        return [task for task in records if task.id in wanted]

    def _attachments_for_tasks(tasks: list[TaskRecord], *, cloud: bool) -> list[TaskAttachmentRecord]:
        attachments: dict[str, TaskAttachmentRecord] = {}
        source_modes = [False, True] if cloud else [False]
        for task in tasks:
            for use_cloud in source_modes:
                for attachment in fetch_task_attachments(task.id, cloud=use_cloud):
                    attachments[attachment.id] = attachment
        return sorted(attachments.values(), key=lambda item: item.createdAt, reverse=True)

    def _attachments_for_ids(attachment_ids: list[str]) -> list[TaskAttachmentRecord]:
        wanted = {attachment_id for attachment_id in attachment_ids if attachment_id}
        if not wanted:
            return []
        attachments: dict[str, TaskAttachmentRecord] = {}
        for table_name in ("task_attachments", "task_attachments_cloud"):
            rows = state.db.fetchall(
                f"SELECT * FROM {table_name} WHERE id IN ({_sql_placeholders(tuple(wanted))}) ORDER BY created_at DESC",
                tuple(wanted),
            )
            for row in rows:
                attachment = build_task_attachment(row)
                attachments[attachment.id] = attachment
        return sorted(attachments.values(), key=lambda item: item.createdAt, reverse=True)

    def _attachments_for_event_line(event_line_id: str) -> list[TaskAttachmentRecord]:
        if not event_line_id:
            return []
        attachments: dict[str, TaskAttachmentRecord] = {}
        for table_name in ("task_attachments", "task_attachments_cloud"):
            rows = state.db.fetchall(
                f"SELECT * FROM {table_name} WHERE event_line_id = ? ORDER BY created_at DESC",
                (event_line_id,),
            )
            for row in rows:
                attachment = build_task_attachment(row)
                attachments[attachment.id] = attachment
        return sorted(attachments.values(), key=lambda item: item.createdAt, reverse=True)

    def _meeting_summaries_for_tasks(tasks: list[TaskRecord]) -> list[MeetingSummary]:
        meeting_ids = [task.sourceId for task in tasks if task.sourceType == "meeting" and task.sourceId]
        if not meeting_ids:
            return []
        rows = state.db.fetchall(
            f"SELECT * FROM meetings WHERE id IN ({_sql_placeholders(meeting_ids)}) ORDER BY updated_at DESC",
            tuple(meeting_ids),
        )
        return [
            MeetingSummary(
                id=str(row["id"]),
                clientId=str(row["client_id"]),
                title=str(row["title"]),
                stage=str(row["stage"]),  # type: ignore[arg-type]
                scheduledAt=str(row["scheduled_at"]) if row["scheduled_at"] else None,
                updatedAt=str(row["updated_at"]),
            )
            for row in rows
        ]

    def _meeting_summary_for_id(meeting_id: str) -> MeetingSummary:
        row = state.db.fetchone("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return build_meeting_summary(row)

    def _support_request_by_id(request_id: str) -> SupportRequestRecord:
        if not get_cloud_token():
            raise HTTPException(status_code=404, detail="Support request drill-down requires cloud support")
        response = cloud_request("GET", "/api/v1/support-requests")
        if not isinstance(response, list):
            raise HTTPException(status_code=502, detail="Invalid support request payload")
        for item in response:
            if not isinstance(item, dict):
                continue
            if str(item.get("id")) == request_id:
                return SupportRequestRecord(**item)
        raise HTTPException(status_code=404, detail="Support request not found")

    def _task_records_for_views() -> list[TaskRecord]:
        # Local-first: always read from local DB
        if get_cloud_token():
            _pull_cloud_tasks_to_local()
        return fetch_tasks("t.source_type != ?", (AGENT_AUTO_SOURCE_TYPE,))

    def _load_task_view_definition(view_id: str) -> TaskViewDefinitionRecord | None:
        rows = _ensure_builtin_task_views()
        return next((item for item in rows if item.id == view_id), None)

    def _build_ad_hoc_task_view(
        *,
        target_id: str,
        target_label: str | None,
        target_filters: dict[str, object] | None,
    ) -> TaskViewDefinitionRecord:
        filter_set = target_filters if isinstance(target_filters, dict) else {}
        return TaskViewDefinitionRecord(
            id=target_id or "adhoc_task_view",
            name=target_label or "临时任务视图",
            kind="custom",
            description="从周判断卡片下钻得到的临时任务集合。",
            calendarScope="all",
            shareability="private",
            sortBy="updatedAt",
            sortDirection="desc",
            visibleFields=["title", "status", "priority", "sourceType", "businessCategory", "eventLine", "evidenceCount"],
            filterSet=filter_set,
            builtIn=False,
            createdAt=now_iso(),
            updatedAt=now_iso(),
        )

    def _tasks_for_task_view(
        view: TaskViewDefinitionRecord,
        *,
        extra_filters: dict[str, object] | None = None,
    ) -> list[TaskRecord]:
        records = _task_records_for_views()
        filtered = [task for task in records if _matches_task_view(task, view, extra_filters)]
        return _sort_tasks_for_view(filtered, view)

    def _support_requests_for_tasks(tasks: list[TaskRecord]) -> list[SupportRequestRecord]:
        if not get_cloud_token():
            return []
        request_ids: set[str] = set()
        records: list[SupportRequestRecord] = []
        for task in tasks:
            if not task.id:
                continue
            response = _safe_cloud_request("GET", f"/api/v1/support-requests?taskId={quote(task.id)}")
            if not isinstance(response, list):
                continue
            for item in response:
                if not isinstance(item, dict):
                    continue
                record = SupportRequestRecord(**item)
                if record.id in request_ids:
                    continue
                request_ids.add(record.id)
                records.append(record)
        records.sort(key=lambda item: item.createdAt, reverse=True)
        return records

    def _drill_target_response_for_event_line(
        target: ReviewDashboardCardTargetRecord,
    ) -> ReviewDashboardDrillTargetResponse:
        event_line_id = _normalize_event_line_reference(target.targetId)
        local_row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
        detail: EventLineDetailRecord | None = None
        if get_cloud_token():
            response = cloud_request("GET", f"/api/v1/event-lines/{event_line_id}")
            if isinstance(response, dict):
                detail = build_cloud_event_line_detail(response)
        if detail is None:
            if not local_row:
                raise HTTPException(status_code=404, detail="Event line not found")
            detail = build_event_line_detail(local_row)
        memory_response = get_event_line_memory_response(state.db, event_line_id) if local_row else None
        attachments = _attachments_for_tasks(detail.tasks, cloud=bool(get_cloud_token()))
        meetings = _meeting_summaries_for_tasks(detail.tasks)
        support_requests = _support_requests_for_tasks(detail.tasks)
        return ReviewDashboardDrillTargetResponse(
            target=target,
            eventLineDetail=detail,
            eventLineMemory=memory_response.eventLineMemorySnapshot if memory_response else None,
            tasks=detail.tasks,
            meetings=meetings,
            supportRequests=support_requests,
            attachments=attachments,
        )

    def _drill_target_response_for_task_view(
        target: ReviewDashboardCardTargetRecord,
    ) -> ReviewDashboardDrillTargetResponse:
        view = _load_task_view_definition(target.targetId)
        if view is None:
            view = _build_ad_hoc_task_view(
                target_id=target.targetId,
                target_label=target.targetLabel,
                target_filters=target.targetFilters,
            )
        tasks = _tasks_for_task_view(view, extra_filters=target.targetFilters)
        attachments = _attachments_for_tasks(tasks, cloud=bool(get_cloud_token()))
        meetings = _meeting_summaries_for_tasks(tasks)
        support_requests = _support_requests_for_tasks(tasks)
        return ReviewDashboardDrillTargetResponse(
            target=target,
            tasks=tasks,
            meetings=meetings,
            supportRequests=support_requests,
            attachments=attachments,
        )

    def _drill_target_response_for_meeting(
        target: ReviewDashboardCardTargetRecord,
    ) -> ReviewDashboardDrillTargetResponse:
        meeting = _meeting_summary_for_id(target.targetId)
        tasks = [
            task
            for task in _task_records_for_views()
            if task.sourceId == meeting.id and task.sourceType in {"meeting", "meeting_publish", "meeting_action_item_publish"}
        ]
        attachments = _attachments_for_tasks(tasks, cloud=bool(get_cloud_token()))
        support_requests = _support_requests_for_tasks(tasks)
        return ReviewDashboardDrillTargetResponse(
            target=target,
            tasks=tasks,
            meetings=[meeting],
            supportRequests=support_requests,
            attachments=attachments,
        )

    def _drill_target_response_for_support_request(
        target: ReviewDashboardCardTargetRecord,
    ) -> ReviewDashboardDrillTargetResponse:
        request_record = _support_request_by_id(target.targetId)
        tasks = _task_records_for_ids([request_record.taskId] if request_record.taskId else [])
        attachments = _attachments_for_tasks(tasks, cloud=bool(get_cloud_token()))
        meetings = _meeting_summaries_for_tasks(tasks)
        return ReviewDashboardDrillTargetResponse(
            target=target,
            tasks=tasks,
            meetings=meetings,
            supportRequests=[request_record],
            attachments=attachments,
        )

    def _drill_target_response_for_attachment_group(
        target: ReviewDashboardCardTargetRecord,
    ) -> ReviewDashboardDrillTargetResponse:
        attachment_ids = [
            str(item)
            for item in target.targetFilters.get("attachmentIds", [])
            if isinstance(item, str) and item.strip()
        ]
        task_ids = [
            str(item)
            for item in target.targetFilters.get("taskIds", [])
            if isinstance(item, str) and item.strip()
        ]
        event_line_id = str(target.targetFilters.get("eventLineId") or "").strip()

        attachments = _attachments_for_ids(attachment_ids)
        if not attachments and task_ids:
            tasks = _task_records_for_ids(task_ids)
            attachments = _attachments_for_tasks(tasks, cloud=bool(get_cloud_token()))
        elif not attachments and event_line_id:
            attachments = _attachments_for_event_line(event_line_id)

        related_task_ids = task_ids or [attachment.taskId for attachment in attachments if attachment.taskId]
        tasks = _task_records_for_ids(related_task_ids)
        meetings = _meeting_summaries_for_tasks(tasks)
        support_requests = _support_requests_for_tasks(tasks)
        return ReviewDashboardDrillTargetResponse(
            target=target,
            tasks=tasks,
            meetings=meetings,
            supportRequests=support_requests,
            attachments=attachments,
        )

    def normalize_local_task_tags(tag_ids: list[str] | None, legacy_names: list[str] | None) -> list[TaskTagRecord]:
        _ = tag_ids, legacy_names
        return []

    def sync_local_tasks_for_tag_change(tag_id: str) -> None:
        tag_row = state.db.fetchone("SELECT * FROM task_tags WHERE id = ?", (tag_id,))
        task_rows = state.db.fetchall("SELECT id, tag_ids_json FROM tasks")
        for row in task_rows:
            tag_ids = _parse_json_list(row["tag_ids_json"])
            if tag_id not in tag_ids:
                continue
            if tag_row:
                resolved_tags = [
                    _local_task_tag_record(item)
                    for item in _local_tag_rows_by_ids(state.db, tag_ids)
                ]
            else:
                next_tag_ids = [item for item in tag_ids if item != tag_id]
                resolved_tags = [
                    _local_task_tag_record(item)
                    for item in _local_tag_rows_by_ids(state.db, next_tag_ids)
                ]
            state.db.execute(
                "UPDATE tasks SET tag_ids_json = ?, tags_json = ?, updated_at = ? WHERE id = ?",
                (to_json([item.id for item in resolved_tags]), to_json([item.name for item in resolved_tags]), now_iso(), str(row["id"])),
            )

    def build_client_summary(client_id: str):
        row = state.db.fetchone("SELECT * FROM clients WHERE id = ?", (client_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Client not found")
        return ClientSummary(
            id=str(row["id"]),
            name=str(row["name"]),
            alias=str(row["alias"]),
            domain=str(row["domain"]),
            type=str(row["type"]),
            intro=str(row["intro"]),
            stage=str(row["stage"]),
            color=str(row["color"] or "#5B7BFE"),
            folderCount=len(HUMAN_VISIBLE_CATEGORIES),
            documentCount=state.db.scalar("SELECT COUNT(1) AS count FROM documents WHERE client_id = ?", (client_id,)),
            taskCount=state.db.scalar(
                """
                SELECT COUNT(1) AS count
                FROM tasks
                WHERE source_id = ?
                   OR source_id IN (SELECT id FROM meetings WHERE client_id = ?)
                """,
                (client_id, client_id),
            ),
            lastActivityAt=str(row["updated_at"]),
        )

    def build_task_project_context(
        client_id: str | None,
        source_type: str | None = None,
        source_id: str | None = None,
        task_title: str = "",
        task_desc: str = "",
        project_module_id: str | None = None,
        project_flow_id: str | None = None,
    ) -> TaskProjectContextRecord | None:
        if not client_id:
            return None
        client_row = state.db.fetchone("SELECT * FROM clients WHERE id = ?", (client_id,))
        if not client_row:
            return None
        client_name = str(client_row["name"])
        stage = str(client_row["stage"]) if client_row["stage"] else None
        intro = str(client_row["intro"] or "").strip()
        dna_modules = {module.moduleKey: module for module in list_client_dna_modules(client_id)}
        business_module = dna_modules.get("business_intro")
        organization_module = dna_modules.get("organization_intro")
        team_module = dna_modules.get("team_intro")
        market_module = dna_modules.get("market_intro")
        project_module, project_flow = resolve_project_structure_refs(client_id, project_module_id, project_flow_id, strict=False)
        goal_rows = state.db.fetchall(
            "SELECT title, quarter, progress FROM goal_records WHERE client_id = ? ORDER BY updated_at DESC LIMIT 3",
            (client_id,),
        )
        goals = [str(row["title"]).strip() for row in goal_rows if str(row["title"]).strip()]
        meeting_rows = state.db.fetchall(
            "SELECT title FROM meetings WHERE client_id = ? ORDER BY updated_at DESC LIMIT 2",
            (client_id,),
        )
        meetings = [str(row["title"]).strip() for row in meeting_rows if str(row["title"]).strip()]
        excerpt_row = state.db.fetchone(
            "SELECT excerpt FROM documents WHERE client_id = ? AND excerpt IS NOT NULL AND TRIM(excerpt) != '' ORDER BY created_at DESC LIMIT 1",
            (client_id,),
        )
        document_excerpt = str(excerpt_row["excerpt"]).strip() if excerpt_row and excerpt_row["excerpt"] else ""
        open_related_task_count = int(state.db.scalar(
            """
            SELECT COUNT(1) AS count
            FROM tasks
            WHERE status != 'done'
              AND (source_id = ? OR source_id IN (SELECT id FROM meetings WHERE client_id = ?))
            """,
            (client_id, client_id),
        ) or 0)

        dna_ready_count = sum(
            1
            for module in [organization_module, business_module, team_module, market_module]
            if module and module.hasDocument and module.normalizedText.strip()
        )
        completeness_points = dna_ready_count
        if goals:
            completeness_points += 1
        if project_module or project_flow:
            completeness_points += 1
        info_completeness = 'high' if completeness_points >= 5 else 'medium' if completeness_points >= 3 else 'low'

        normalized_task_desc = re.sub(r"\s+", " ", task_desc or "").strip()
        task_clauses = [
            item.strip()
            for item in re.split(r"\n|[。；;|｜]", task_desc or "")
            if item and item.strip()
        ]

        def pick_task_clause(patterns: list[str], fallback_to_first: bool = False) -> str:
            for clause in task_clauses:
                if any(pattern in clause for pattern in patterns):
                    return clause.strip()[:120]
            if fallback_to_first and task_clauses:
                return task_clauses[0].strip()[:120]
            return ""

        desc_background = pick_task_clause(["背景", "对象", "关系", "合作", "机构", "联系人"], fallback_to_first=True)
        desc_focus = pick_task_clause(["推进", "目标", "输出", "形成", "确认", "介绍", "合作"], fallback_to_first=True)
        desc_risk = pick_task_clause(["阻塞", "卡", "风险", "待", "未", "缺", "补", "没有"])
        desc_next = pick_task_clause(["下一步", "继续", "先", "补", "推进", "确认"])

        def summarize_module_text(module: ClientDnaModuleRecord | None, fallback_length: int = 220) -> str:
            if not module:
                return ""
            summary_text = (module.summary or "").strip()
            if summary_text:
                return summary_text
            normalized = re.sub(r"\s+", " ", module.normalizedText or "").strip()
            return normalized[:fallback_length]

        background_parts = [
            desc_background,
            summarize_module_text(business_module, 240),
            summarize_module_text(organization_module, 180),
            summarize_module_text(team_module, 160),
            summarize_module_text(market_module, 160),
        ]
        background_summary = "；".join(part for part in background_parts if part)[:160]
        if not background_summary:
            background_summary = intro or document_excerpt or f"{client_name}当前处于{stage or '推进中'}，建议继续补充项目背景和关键资料。"

        module_summary = None
        if project_module:
            module_summary = "；".join(part for part in [project_module.goal.strip(), project_module.description.strip()] if part)[:140] or None
        flow_summary = None
        if project_flow:
            flow_summary = "；".join(
                part for part in [
                    project_flow.scenario.strip(),
                    " / ".join(project_flow.steps[:3]).strip(),
                    " / ".join(project_flow.riskPoints[:2]).strip(),
                ] if part
            )[:140] or None

        if project_module and project_module.goal.strip():
            goal_summary = project_module.goal.strip()[:120]
        elif goals:
            goal_summary = '；'.join(goals[:2])[:120]
        elif desc_focus:
            goal_summary = desc_focus[:120]
        elif business_module and summarize_module_text(business_module, 180):
            goal_summary = summarize_module_text(business_module, 180)[:120]
        else:
            goal_summary = '当前还没有写入明确的项目目标。'

        if project_flow and project_flow.riskPoints:
            risk_summary = f"当前流程风险：{'；'.join(project_flow.riskPoints[:2])}"[:120]
        elif desc_risk:
            risk_summary = desc_risk[:120]
        elif market_module and summarize_module_text(market_module, 180):
            risk_summary = f"外部环境提示：{summarize_module_text(market_module, 180)}"[:120]
        elif info_completeness == 'low':
            risk_summary = '当前项目背景资料仍偏薄，建议补齐组织、项目、团队和市场四张资料卡后再做更深判断。'
        elif open_related_task_count > 0:
            risk_summary = f'当前仍有{open_related_task_count}条关联任务待推进，需持续跟进项目节奏。'
        elif meetings:
            risk_summary = f"最近会议聚焦于：{' / '.join(meetings[:2])}。"[:120]
        else:
            risk_summary = '当前暂无明显风险信号，可围绕既定目标继续推进。'

        if project_module and project_module.name.strip():
            current_focus = (
                f"{project_module.name.strip()}：{(project_module.goal or '').strip()}"
                if (project_module.goal or "").strip()
                else project_module.name.strip()
            )[:120]
        elif desc_focus:
            current_focus = desc_focus[:120]
        elif goals:
            current_focus = f"当前主要在推进：{goals[0]}"[:120]
        elif meetings:
            current_focus = f"当前讨论集中在：{meetings[0]}"[:120]
        else:
            current_focus = f"{client_name}当前重点仍待补充，建议先明确这一阶段的核心事项。"[:120]

        if project_flow and project_flow.riskPoints:
            current_blocker = f"当前阻塞：{'；'.join(project_flow.riskPoints[:2])}"[:120]
        elif desc_risk:
            current_blocker = desc_risk[:120]
        elif info_completeness == 'low':
            current_blocker = '当前阻塞更像资料不足，项目背景、目标和流程线索都还不完整。'
        elif open_related_task_count > 0:
            current_blocker = f"当前仍有 {open_related_task_count} 条关联任务未收束，推进节奏容易被拉长。"[:120]
        else:
            current_blocker = '当前没有特别突出的阻塞，但仍需盯住推进收束。'

        if project_flow and project_flow.steps:
            next_action = f"下一步动作：{project_flow.steps[0]}"[:120]
        elif desc_next:
            next_action = desc_next[:120]
        elif project_module and project_module.description.strip():
            next_action = f"下一步动作：围绕{project_module.name.strip()}继续细化并推进落地。"[:120]
        elif goals:
            next_action = f"下一步动作：继续围绕“{goals[0]}”推进具体动作。"[:120]
        elif meetings:
            next_action = f"下一步动作：根据最近会议“{meetings[0]}”形成明确后续安排。"[:120]
        else:
            next_action = '下一步动作：先补齐项目背景，再明确这一阶段最核心的推进事项。'

        if meetings:
            recent_progress = f"最近进展：{' / '.join(meetings[:2])}"[:120]
        elif normalized_task_desc:
            recent_progress = f"任务补充：{desc_focus or desc_background or normalized_task_desc}"[:120]
        elif open_related_task_count > 0:
            recent_progress = f"最近进展：已有 {open_related_task_count} 条关联任务在持续推进。"[:120]
        elif document_excerpt:
            recent_progress = f"最近线索：{document_excerpt}"[:120]
        else:
            recent_progress = f"最近进展仍待补充，建议尽快沉淀会议或推进记录。"[:120]

        source_evidence: list[str] = []
        if source_type == 'meeting':
            source_evidence.append('会议来源')
        elif source_type == 'goal':
            source_evidence.append('目标来源')
        elif source_id == client_id:
            source_evidence.append('客户工作台来源')
        else:
            source_evidence.append('任务关联客户')
        if normalized_task_desc:
            source_evidence.append('任务描述补充')
        for module in [organization_module, business_module, team_module, market_module]:
            if module and module.hasDocument and module.normalizedText.strip():
                source_evidence.append(module.title)
        if goals:
            source_evidence.append('项目目标')
        if project_module:
            source_evidence.append(f"任务模块：{project_module.name}")
        if project_flow:
            source_evidence.append(f"流程：{project_flow.name}")
        if intro or document_excerpt:
            source_evidence.append('历史项目摘要')

        return TaskProjectContextRecord(
            clientId=client_id,
            clientName=client_name,
            stage=stage,
            projectModuleId=project_module.id if project_module else None,
            projectModuleName=project_module.name if project_module else None,
            projectModuleSummary=module_summary,
            projectFlowId=project_flow.id if project_flow else None,
            projectFlowName=project_flow.name if project_flow else None,
            projectFlowSummary=flow_summary,
            backgroundSummary=background_summary[:160],
            goalSummary=goal_summary[:120],
            riskSummary=risk_summary[:120],
            currentFocus=current_focus[:120],
            currentBlocker=current_blocker[:120],
            nextAction=next_action[:120],
            recentProgress=recent_progress[:120],
            infoCompleteness=info_completeness,
            sourceEvidence=source_evidence,
        )

    def ensure_standard_client_folders(client_id: str) -> None:
        folders = ensure_client_workspace(state.data_dir, client_id)
        timestamp = now_iso()
        for label, path in folders.items():
            existing = state.db.fetchone(
                "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
                (client_id, label),
            )
            file_count = int(
                state.db.scalar(
                    """
                    SELECT COUNT(1) AS count
                    FROM knowledge_documents
                    WHERE client_id = ? AND human_folder_category = ?
                    """,
                    (client_id, label),
                )
            )
            if file_count > 0:
                unhide_client_folder_label(client_id, label)
            if existing:
                state.db.execute(
                    "UPDATE client_folders SET path = ?, file_count = ?, last_scanned_at = ? WHERE id = ?",
                    (str(path), file_count, timestamp, str(existing["id"])),
                )
            else:
                state.db.execute(
                    """
                    INSERT INTO client_folders(id, client_id, label, path, file_count, last_scanned_at, created_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (new_id("fld"), client_id, label, str(path), file_count, timestamp, timestamp),
                    )

    def build_document_card_record(payload: dict[str, object]) -> DocumentCardRecord:
        return DocumentCardRecord(**payload)

    def build_knowledge_status_record(client_id: str) -> KnowledgeStatusRecord:
        return KnowledgeStatusRecord(**compute_knowledge_status(state.db, client_id, state.data_dir))

    RETRIEVAL_INTENT_EXPANSION_TERMS: dict[str, tuple[str, ...]] = {
        "intro_profile": (
            "机构介绍",
            "组织介绍",
            "基金会简介",
            "年报",
            "对外介绍",
            "业务介绍",
            "核心项目",
            "项目清单",
            "战略资料",
        ),
        "project_intro": (
            "项目介绍",
            "项目清单",
            "核心项目",
            "交付路径",
            "阶段目标",
            "项目成果",
            "项目规划",
        ),
        "meeting_summary": (
            "会议纪要",
            "沟通记录",
            "飞书",
            "妙记",
            "会议决定",
            "行动项",
            "风险",
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
            (message_id, client_id),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Chat message not found")
        return build_chat_message(row)

    def build_analysis_evidence_summary(client_id: str, prompt: str, retrieval_bundle) -> ClientAnalysisEvidenceSummaryRecord:
        retrieval_meta = retrieval_bundle.retrieval_summary if isinstance(retrieval_bundle.retrieval_summary, dict) else {}
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
            if item.source_stage == "raw_chunk"
        ]
        preferred_categories = [
            str(item)
            for item in retrieval_meta.get("preferredCategories", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("preferredCategories"), list) else []
        curated_hits = select_high_signal_evidence(
            evidence,
            limit=8,
            prompt=prompt,
            preferred_categories=preferred_categories,
        )
        hits = [
            KnowledgeSearchHitRecord(
                title=item.title,
                excerpt=item.excerpt,
                score=item.score,
                stage=item.retrievalStage,  # type: ignore[arg-type]
                path=item.path,
                sectionLabel=item.sectionLabel,
                matchedTerms=item.matchedTerms,
            )
            for item in curated_hits
        ]
        preview_summary = str(retrieval_meta.get("previewSummary") or "").strip()
        if not preview_summary:
            preview_summary = build_retrieval_preview_summary(client_id, prompt, evidence, retrieval_bundle)
        covered_categories = [
            str(item)
            for item in retrieval_meta.get("categoryCoverage", [])
            if str(item).strip()
        ] if isinstance(retrieval_meta.get("categoryCoverage"), list) else []
        missing_categories = [item for item in preferred_categories if item not in covered_categories]
        return ClientAnalysisEvidenceSummaryRecord(
            summaryText=preview_summary,
            masterHitCount=int(retrieval_meta.get("masterHitCount", 0) or 0),
            surrogateHitCount=int(retrieval_meta.get("surrogateHitCount", 0) or 0),
            rawChunkHitCount=int(retrieval_meta.get("rawChunkHitCount", 0) or 0),
            drillthroughUsed=bool(retrieval_meta.get("drillthroughUsed", False)),
            coveredCategories=covered_categories,
            missingCategories=missing_categories,
            evidenceList=hits,
        )

    def create_client_analysis_run(
        client_id: str,
        thread_id: str,
        user_message_id: str,
        assistant_message_id: str,
        question: str,
        created_at: str,
    ) -> ClientAnalysisRunRecord:
        run_id = new_id("analysis")
        state.db.execute(
            """
            INSERT INTO client_analysis_runs(
                id, client_id, thread_id, user_message_id, assistant_message_id, question,
                status, phase, progress, progress_floor, progress_ceiling, stage_label, elapsed_ms,
                evidence_summary_json, long_answer, structured_summary_json, long_answer_status, summary_status,
                answer_mode, llm_invoked, provider_used, failure_reason, timing_json, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, 'queued', 'queued', 0, 0, 30, '等待开始整理背景材料', 0, '{}', NULL, '{}', 'pending', 'pending', NULL, 0, NULL, NULL, '{}', ?, ?)
            """,
            (run_id, client_id, thread_id, user_message_id, assistant_message_id, question, created_at, created_at),
        )
        row = state.db.fetchone("SELECT * FROM client_analysis_runs WHERE id = ?", (run_id,))
        assert row is not None
        return build_client_analysis_run(row)

    _ANALYSIS_FIELD_UNSET = object()

    def update_client_analysis_run(
        run_id: str,
        *,
        status: str | None = None,
        phase: str | None = None,
        progress: float | None = None,
        progress_floor: float | None = None,
        progress_ceiling: float | None = None,
        stage_label: str | None = None,
        elapsed_ms: float | None = None,
        evidence_summary: ClientAnalysisEvidenceSummaryRecord | dict[str, object] | object = _ANALYSIS_FIELD_UNSET,
        long_answer: str | None | object = _ANALYSIS_FIELD_UNSET,
        structured_summary: AiStructuredResponse | dict[str, object] | None | object = _ANALYSIS_FIELD_UNSET,
        long_answer_status: str | None = None,
        summary_status: str | None = None,
        answer_mode: str | None = None,
        llm_invoked: bool | None = None,
        provider_used: str | None = None,
        failure_reason: str | None = None,
        timing: dict[str, float] | None = None,
    ) -> None:
        row = state.db.fetchone("SELECT * FROM client_analysis_runs WHERE id = ?", (run_id,))
        if not row:
            return
        next_status = status or str(row["status"])
        next_phase = phase or str(row["phase"])
        next_progress = float(progress if progress is not None else row["progress"])
        next_floor = float(progress_floor if progress_floor is not None else row["progress_floor"])
        next_ceiling = float(progress_ceiling if progress_ceiling is not None else row["progress_ceiling"])
        next_stage_label = stage_label if stage_label is not None else (str(row["stage_label"]) if row["stage_label"] else None)
        next_elapsed = float(elapsed_ms if elapsed_ms is not None else row["elapsed_ms"])
        next_evidence_summary = (
            evidence_summary.model_dump()
            if isinstance(evidence_summary, ClientAnalysisEvidenceSummaryRecord)
            else evidence_summary
        )
        if next_evidence_summary is _ANALYSIS_FIELD_UNSET:
            stored_summary = from_json(str(row["evidence_summary_json"] or "{}"), {})
            next_evidence_summary = stored_summary if isinstance(stored_summary, dict) else {}
        next_structured_summary = (
            structured_summary.model_dump()
            if isinstance(structured_summary, AiStructuredResponse)
            else structured_summary
        )
        if next_structured_summary is _ANALYSIS_FIELD_UNSET:
            stored_structured = from_json(str(row["structured_summary_json"] or "{}"), {})
            next_structured_summary = stored_structured if isinstance(stored_structured, dict) else {}
        elif next_structured_summary is None:
            next_structured_summary = {}
        next_timing = timing
        if next_timing is None:
            stored_timing = from_json(str(row["timing_json"] or "{}"), {})
            next_timing = stored_timing if isinstance(stored_timing, dict) else {}
        next_long_answer = str(row["long_answer"]) if row["long_answer"] is not None else None
        if long_answer is not _ANALYSIS_FIELD_UNSET:
            next_long_answer = str(long_answer) if isinstance(long_answer, str) else None
        state.db.execute(
            """
            UPDATE client_analysis_runs
            SET status = ?, phase = ?, progress = ?, progress_floor = ?, progress_ceiling = ?, stage_label = ?,
                elapsed_ms = ?, evidence_summary_json = ?, long_answer = ?,
                structured_summary_json = ?, long_answer_status = ?, summary_status = ?, answer_mode = ?,
                llm_invoked = ?, provider_used = ?, failure_reason = ?, timing_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                next_phase,
                next_progress,
                next_floor,
                next_ceiling,
                next_stage_label,
                next_elapsed,
                to_json(next_evidence_summary),
                next_long_answer,
                to_json(next_structured_summary),
                long_answer_status or str(row["long_answer_status"]),
                summary_status or str(row["summary_status"]),
                answer_mode if answer_mode is not None else (str(row["answer_mode"]) if row["answer_mode"] else None),
                1 if (llm_invoked if llm_invoked is not None else bool(row["llm_invoked"])) else 0,
                provider_used if provider_used is not None else (str(row["provider_used"]) if row["provider_used"] else None),
                failure_reason if failure_reason is not None else (str(row["failure_reason"]) if row["failure_reason"] else None),
                to_json(next_timing),
                now_iso(),
                run_id,
            ),
        )

    def build_client_analysis_run(row) -> ClientAnalysisRunRecord:
        evidence_summary_data = from_json(row["evidence_summary_json"], {})
        structured_summary_data = from_json(row["structured_summary_json"], {})
        timing_data = from_json(row["timing_json"], {})
        assistant_message = None
        if row["assistant_message_id"]:
            assistant_row = state.db.fetchone("SELECT * FROM chat_messages WHERE id = ?", (str(row["assistant_message_id"]),))
            if assistant_row:
                assistant_message = build_chat_message(assistant_row)
        return ClientAnalysisRunRecord(
            id=str(row["id"]),
            clientId=str(row["client_id"]),
            threadId=str(row["thread_id"]),
            userMessageId=str(row["user_message_id"]),
            assistantMessageId=str(row["assistant_message_id"]),
            question=str(row["question"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            phase=str(row["phase"]),  # type: ignore[arg-type]
            progress=float(row["progress"] or 0.0),
            progressFloor=float(row["progress_floor"] or 0.0),
            progressCeiling=float(row["progress_ceiling"] or 0.0),
            stageLabel=str(row["stage_label"]) if row["stage_label"] else None,
            elapsedMs=float(row["elapsed_ms"] or 0.0),
            evidenceSummary=ClientAnalysisEvidenceSummaryRecord(**(evidence_summary_data if isinstance(evidence_summary_data, dict) else {})),
            longAnswerStatus=str(row["long_answer_status"]),  # type: ignore[arg-type]
            summaryStatus=str(row["summary_status"]),  # type: ignore[arg-type]
            longAnswer=str(row["long_answer"]) if row["long_answer"] else None,
            structuredSummary=AiStructuredResponse(**structured_summary_data) if isinstance(structured_summary_data, dict) and structured_summary_data else None,
            answerMode=str(row["answer_mode"]) if row["answer_mode"] else None,  # type: ignore[arg-type]
            llmInvoked=bool(row["llm_invoked"]),
            providerUsed=str(row["provider_used"]) if row["provider_used"] else None,
            failureReason=str(row["failure_reason"]) if row["failure_reason"] else None,
            timing=timing_data if isinstance(timing_data, dict) else {},
            assistantMessage=assistant_message,
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def fetch_analysis_run_for_client(client_id: str, run_id: str) -> ClientAnalysisRunRecord:
        row = state.db.fetchone("SELECT * FROM client_analysis_runs WHERE id = ? AND client_id = ?", (run_id, client_id))
        if not row:
            raise HTTPException(status_code=404, detail="Analysis run not found")
        return build_client_analysis_run(row)

    def is_client_analysis_run_canceled(run_id: str | None) -> bool:
        if not run_id:
            return False
        row = state.db.fetchone("SELECT status, failure_reason FROM client_analysis_runs WHERE id = ?", (run_id,))
        if not row:
            return False
        return str(row["status"] or "") == "canceled" or str(row["failure_reason"] or "") == "user_canceled"

    def cancel_analysis_run_for_client(client_id: str, run_id: str) -> ClientAnalysisRunRecord:
        run = fetch_analysis_run_for_client(client_id, run_id)
        if run.status in {"completed", "failed", "canceled"}:
            return run
        timestamp = now_iso()
        structured = AiStructuredResponse(
            content="本次回答已停止。",
            judgment="你手动停止了这次生成，因此没有继续产出正式回答。",
            analysis="当前计算已从前台中断，系统不会再继续展示这次回答结果。",
            actions="如果需要，可以直接重新提问，或换一个更明确的问题再次生成。",
            timeline=f"停止时间：{timestamp}",
        )
        state.db.execute(
            """
            UPDATE chat_messages
            SET content = ?, structured_data_json = ?, model_route = ?, llm_invoked = 0, provider_used = NULL,
                answer_mode = NULL, evidence_status = 'none', failure_reason = 'user_canceled',
                timing_json = COALESCE(timing_json, '{}'), retrieval_summary_json = COALESCE(retrieval_summary_json, '{}'),
                evidence_json = '[]', status = 'success', created_at = ?
            WHERE id = ?
            """,
            (
                structured.content,
                to_json(structured.model_dump()),
                "已手动停止",
                timestamp,
                run.assistantMessageId,
            ),
        )
        update_client_analysis_run(
            run_id,
            status="canceled",
            phase="canceled",
            progress=100.0,
            progress_floor=100.0,
            progress_ceiling=100.0,
            stage_label="已停止当前回答",
            long_answer=None,
            structured_summary=structured,
            long_answer_status="failed",
            summary_status="failed",
            answer_mode=None,
            provider_used=None,
            failure_reason="user_canceled",
            timing=run.timing,
        )
        state.db.execute("UPDATE chat_threads SET updated_at = ? WHERE id = ?", (timestamp, run.threadId))
        log_activity("chat.cancel", "chat_thread", run.threadId, {"clientId": client_id, "runId": run_id, "prompt": run.question})
        return fetch_analysis_run_for_client(client_id, run_id)

    def build_answer_memory_markdown(client_id: str, message: ChatMessageRecord) -> str:
        client_name = build_client_summary(client_id).name
        lines = [
            f"# {client_name} · 战略陪伴记忆",
            "",
            f"- 客户：{client_name}",
            f"- 生成时间：{now_iso()}",
            "",
            "## 回答摘要",
            message.content.strip() or "（无内容）",
        ]
        if message.structuredData:
            lines.extend(
                [
                    "",
                    "## 核心判断",
                    (message.structuredData.judgment or "").strip() or "【待补充】",
                    "",
                    "## 结构化分析",
                    (message.structuredData.analysis or "").strip() or "【待补充】",
                    "",
                    "## 建议动作",
                    (message.structuredData.actions or "").strip() or "【待补充】",
                    "",
                    "## 关键时间线",
                    (message.structuredData.timeline or "").strip() or "【待补充】",
                ]
            )
        if message.evidence:
            lines.extend(["", "## 证据来源"])
            for item in message.evidence:
                lines.extend(
                    [
                        f"- {item.title} | {item.sectionLabel or item.sourceType or '证据'}",
                        f"  - 摘录：{(item.excerpt or '').strip()}",
                    ]
                )
        return "\n".join(lines).strip() + "\n"

    _DOCX_UNSAFE_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

    def _sanitize_docx_text(value: str | None) -> str:
        normalized = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        return _DOCX_UNSAFE_CHAR_PATTERN.sub("", normalized)

    def register_generated_workspace_document(
        client_id: str,
        *,
        target_path: Path,
        title: str,
        kind: str,
        source: str,
        excerpt: str,
        folder_label: str = "战略陪伴",
    ) -> ClientTextDocumentResponse:
        ensure_standard_client_folders(client_id)
        folder_row = state.db.fetchone(
            "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
            (client_id, folder_label),
        )
        document_id = new_id("doc")
        timestamp_iso = now_iso()
        normalized_excerpt = (excerpt or "").strip()[:140] or f"{title} 已加入当前项目文档库。"
        state.db.execute(
            """
            INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                client_id,
                str(folder_row["id"]) if folder_row else None,
                target_path.name,
                str(target_path),
                str(target_path),
                kind,
                source,
                normalized_excerpt,
                to_json([source, kind, folder_label]),
                timestamp_iso,
            ),
        )
        ingest_document_knowledge(
            state.db,
            data_dir=state.data_dir,
            client_id=client_id,
            import_id=None,
            document_id=document_id,
            source_path=target_path,
            original_source_path=target_path,
            title=target_path.name,
            kind=kind,
            source=source,
            fallback_excerpt=normalized_excerpt,
            created_at=timestamp_iso,
            ai_service=None,
        )
        document_row = state.db.fetchone("SELECT path FROM documents WHERE id = ?", (document_id,))
        resolved_path = str(document_row["path"]) if document_row and document_row["path"] else str(target_path)
        return ClientTextDocumentResponse(
            clientId=client_id,
            documentId=document_id,
            title=title,
            fileName=Path(resolved_path).name,
            path=resolved_path,
        )

    def create_answer_memory_markdown_document(client_id: str, message: ChatMessageRecord) -> ClientTextDocumentResponse:
        folders = ensure_client_workspace(state.data_dir, client_id)
        target_dir = folders["战略陪伴"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = target_dir / f"{timestamp}_{safe_filename(message.content[:18] or '战略陪伴记忆')}.md"
        target_path.write_text(build_answer_memory_markdown(client_id, message), encoding="utf-8")
        return register_generated_workspace_document(
            client_id,
            target_path=target_path,
            title=f"{build_client_summary(client_id).name} · 战略陪伴记忆",
            kind="md",
            source="answer_memory_doc",
            excerpt=message.content,
        )

    def export_answer_to_docx(client_id: str, message: ChatMessageRecord) -> Path:
        folders = ensure_client_workspace(state.data_dir, client_id)
        target_dir = folders["战略陪伴"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = target_dir / f"{timestamp}_{safe_filename(message.content[:18] or '战略陪伴沉淀')}.docx"
        document = WordDocument()
        document.add_heading("战略陪伴沉淀", level=1)
        document.add_paragraph(_sanitize_docx_text(f"客户：{build_client_summary(client_id).name}"))
        document.add_paragraph(_sanitize_docx_text(f"生成时间：{now_iso()}"))
        document.add_paragraph("")
        document.add_heading("回答摘要", level=2)
        document.add_paragraph(_sanitize_docx_text(message.content))
        if message.structuredData:
            document.add_heading("核心判断", level=2)
            document.add_paragraph(_sanitize_docx_text(message.structuredData.judgment))
            document.add_heading("结构化分析", level=2)
            document.add_paragraph(_sanitize_docx_text(message.structuredData.analysis))
            document.add_heading("建议动作", level=2)
            document.add_paragraph(_sanitize_docx_text(message.structuredData.actions))
            document.add_heading("关键时间线", level=2)
            document.add_paragraph(_sanitize_docx_text(message.structuredData.timeline))
        if message.evidence:
            document.add_heading("证据来源", level=2)
            for item in message.evidence:
                safe_title = _sanitize_docx_text(item.title) or "未命名证据"
                safe_label = _sanitize_docx_text(item.sectionLabel or item.sourceType or "证据")
                safe_excerpt = _sanitize_docx_text(item.excerpt)
                paragraph = document.add_paragraph(style="List Bullet")
                paragraph.add_run(safe_title).bold = True
                paragraph.add_run(f" | {safe_label}")
                if safe_excerpt:
                    document.add_paragraph(safe_excerpt)
        document.save(target_path)
        return target_path

    def create_answer_export_document(client_id: str, message: ChatMessageRecord) -> ClientTextDocumentResponse:
        target_path = export_answer_to_docx(client_id, message)
        return register_generated_workspace_document(
            client_id,
            target_path=target_path,
            title="战略陪伴沉淀",
            kind="docx",
            source="answer_export_doc",
            excerpt=message.content,
        )

    def build_consultation_knowledge_title(request: ConsultationKnowledgeRequestRecord) -> str:
        for candidate in (request.question.strip(), request.answer.strip()):
            if not candidate:
                continue
            normalized = re.sub(r"\s+", " ", candidate)
            return normalized[:28]
        return "咨询沉淀"

    def build_consultation_context_lines(request: ConsultationKnowledgeRequestRecord) -> list[str]:
        lines: list[str] = []
        if request.clientName or request.clientId:
            lines.append(f"- 客户：{request.clientName or request.clientId}")
        if request.taskId:
            lines.append(f"- 关联任务：{request.taskId}")
        if request.eventLineId:
            lines.append(f"- 关联事件线：{request.eventLineId}")
        if request.requestedByName or request.requestedByUserId:
            lines.append(f"- 发起人：{request.requestedByName or request.requestedByUserId}")
        lines.append("- 来源：手机咨询助手")
        return lines

    def build_consultation_memory_markdown(request: ConsultationKnowledgeRequestRecord) -> str:
        lines = [
            "# 手机咨询沉淀记忆",
            f"生成时间：{now_iso()}",
            "",
            "## 关联上下文",
            *build_consultation_context_lines(request),
            "",
        ]
        if request.question.strip():
            lines.extend(["## 原始问题", request.question.strip(), ""])
        lines.extend(["## 答案内容", request.answer.strip(), ""])
        return "\n".join(lines).strip() + "\n"

    def build_consultation_archive_content(request: ConsultationKnowledgeRequestRecord) -> str:
        lines = ["## 关联上下文", *build_consultation_context_lines(request), ""]
        if request.question.strip():
            lines.extend(["## 原始问题", request.question.strip(), ""])
        lines.extend(["## 答案内容", request.answer.strip()])
        return "\n".join(lines).strip()

    def create_consultation_memory_document(
        client_id: str,
        request: ConsultationKnowledgeRequestRecord,
    ) -> ClientTextDocumentResponse:
        client = build_client_summary(client_id)
        folders = ensure_client_workspace(state.data_dir, client_id)
        target_dir = folders["战略陪伴"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_stem = safe_filename(build_consultation_knowledge_title(request)[:18] or "咨询沉淀记忆")
        target_path = target_dir / f"{timestamp}_{safe_stem}.md"
        if target_path.exists():
            target_path = target_dir / f"{timestamp}_{safe_stem}_{uuid4().hex[:6]}.md"
        target_path.write_text(build_consultation_memory_markdown(request), encoding="utf-8")
        return register_generated_workspace_document(
            client_id,
            target_path=target_path,
            title=f"{client.name} · 咨询沉淀记忆",
            kind="md",
            source="consultation_knowledge_memory",
            excerpt=request.answer,
        )

    def sink_consultation_knowledge_request(

```
