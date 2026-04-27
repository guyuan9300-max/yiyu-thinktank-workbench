# backend/app/main.py (lines 7411-7851)

```python
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
```
