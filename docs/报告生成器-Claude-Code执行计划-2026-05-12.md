# 报告生成器（事件线驱动 · 主题感知 · 两阶段生成）· Claude Code 执行计划

**起草日期：** 2026-05-12  
**对应分支：** `feature/report-generation`（新建，起点为 main）  
**适用对象：** Claude Code  
**预计工作量：** 5-6 个迭代，250-400 次工具调用，**3 周完成 MVP**

---

## Part 0 · 必读：核心理念

### 0.1 不要写死报告类型

**错误的实现思路：**

```python
if report_type == "战略陪伴":
    sections = ["本期摘要", "战略目标进展", "关键事件回顾", ...]
elif report_type == "产品复盘":
    sections = ["版本里程碑", "功能模块进展", "技术决策", ...]
elif ...
```

❌ 这种 hardcode 的报告类型枚举是错的。原因：

- 每个事件线的主题、节奏、关注点都不同
- 同一客户在不同阶段（启动 / 推进 / 收尾 / 复盘）需要不同骨架
- 未来无法预知所有报告类型（赋能 / 危机应对 / 募款汇报 / 行业洞察 ...）

### 0.2 正确思路：事件线驱动 + 两阶段生成

**报告生成 = 阶段一（推导骨架）+ 阶段二（分批填充）**

```
事件线 + 报告意图（hint）
      ↓
[阶段一] LLM 读全事件线 → 推导专属章节骨架（ReportBlueprint）
      ↓
人工或自动确认骨架
      ↓
[阶段二] 按章节并行/串行分批填充内容
      ↓
排版 → 信息图嵌入 → docx/pdf 导出 → 人工审阅
```

**关键约束：**

- 章节骨架由 LLM 基于事件线主题推导，不是从枚举挑
- 阶段一只产出"骨架 + 取数计划"，不写正文
- 阶段二每章独立调 LLM 填充，避免长 prompt 失忆
- 信息图按章节的"取数计划"自动选择类型并生成

### 0.3 实测样例参考

沙箱已生成两份 mock 报告作为参考：

- `docs/日慈战略陪伴报告-Q1-2026.docx`（甲方交付版）
- `docs/益语智库V2.0-产品开发复盘-Q1-2026.docx`（内部说明版，带信息图）

**注意：这两份不是模板，是"两种不同主题的产物"——证明同一套生成器能输出不同骨架。**

沙箱还有现成的图表生成模块原型：

- `chart_generator.py`（matplotlib，5 类图表 API）
- `generate_report.py` / `generate_internal_report.py`（python-docx 排版 helper）

Claude Code 可以**直接复用这些代码作为起点**，不要重新发明轮子。

---

## Part 1 · 全局架构

### 1.1 两阶段数据流

```
┌────────────────────────────────────────────────────────────────────┐
│                          阶段一：推导骨架                          │
│                                                                    │
│  输入：                                                            │
│    - event_line_id  或  (client_id, 报告期, 意图 hint)             │
│    - 用户偏好（可选：受众/语气/期望长度）                          │
│                                                                    │
│  ① 读取事件线全量上下文                                            │
│       事件线主题 + 客户 DNA + 主要事件 + 关键判断 + 关键人物         │
│       + 重要文档 + 任务清单 + 风险/卡点 + 上次报告（如有）          │
│                                                                    │
│  ② 调用 LLM 角色 A：报告主理人                                     │
│       prompt: "根据上下文，决定这份报告的骨架。                     │
│                输出：受众 / 语气 / 章节列表 / 每章节                │
│                的目标、取数计划、图表建议、引用证据条数预估。"       │
│                                                                    │
│  ③ 输出 ReportBlueprint                                            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                              ↓
                      （骨架确认环节）
                              ↓
┌────────────────────────────────────────────────────────────────────┐
│                       阶段二：分批填充内容                         │
│                                                                    │
│  对 ReportBlueprint 里每个 Section 独立处理：                      │
│                                                                    │
│  ① 按取数计划 fetch 该章节专属数据包                               │
│  ② 调用 LLM 角色 B：章节起草员                                     │
│       prompt: "写章节 X，目标 Y，受众 Z，可用数据 D，               │
│                约束：引用必带来源、判断必带置信度。"                │
│  ③ 起草员产出 Markdown                                             │
│  ④ 按章节图表建议调 chart_generator 生成 PNG                       │
│                                                                    │
│  并行/串行：独立章节并行（4-8 章节 ≈ 4-8 次 LLM 调用）              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────────┐
│                       阶段三：排版与导出                           │
│  ① 合并所有章节 markdown → 全文 markdown                           │
│  ② 调用 LLM 角色 C：润色员（轻量过文风、段间衔接）                 │
│  ③ docx_renderer 渲染：封面 + 章节 + 表格 + 信息图 + 引用 + 附录    │
│  ④ 转 PDF（可选）                                                  │
│  ⑤ 写入客户工作台 / 报告库                                         │
└────────────────────────────────────────────────────────────────────┘
```

### 1.2 三类 LLM 角色

| 角色 | 模型 | 职责 | 调用频次 |
|---|---|---|---|
| A · 报告主理人 | Claude Opus / GPT-4 | 决定骨架（关键判断） | 每份报告 1 次 |
| B · 章节起草员 | 豆包 Seed Pro / Claude Sonnet | 起草每章节 | 每份报告 N 次（N=章节数） |
| C · 全局润色员 | 同 B 或同 A | 段间衔接 + 风格统一 | 每份报告 1 次（可选） |

---

## Part 2 · 数据契约（Pydantic 模型）

### 2.1 ReportBlueprint（阶段一输出）

新建 `backend/app/models/report.py`：

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class ChartHint(BaseModel):
    """章节内信息图建议。"""
    kind: Literal[
        "pie",                   # 饼图（占比类）
        "progress_bar_h",        # 横向进度条（前后对比/完成度）
        "timeline",              # 时间线
        "grouped_bar",           # 分组柱状图
        "risk_bubble",           # 风险矩阵气泡
        "table_only",            # 不画图，只表格
        "callout_only",          # 不画图，只引用块
    ]
    title: str
    caption: str | None = None
    data_source_hint: str  # 自然语言描述数据从哪取，如 "git log Q1 commit 类型计数"


class SectionPlan(BaseModel):
    """单个章节计划。"""
    level: int = Field(ge=1, le=2)  # 1=H1（一级章节）2=H2（subsection）
    title: str  # 不固定文案，LLM 决定
    goal: str  # 这一章要解决什么、读者读完知道什么
    data_sources: list[str]  # 哪些数据源（自然语言列举：confirmedJudgments / events / tasks / git log 等）
    chart_hints: list[ChartHint] = Field(default_factory=list)
    citation_budget: int = Field(default=5, ge=0)  # 期望引用数
    estimated_words: int = Field(default=300, ge=50, le=2000)  # 预估字数


class ReportBlueprint(BaseModel):
    """阶段一产出的完整报告骨架。"""
    title: str           # 报告主标题，LLM 决定
    subtitle: str | None
    report_kind: str     # LLM 给出的报告类型标签，如"战略陪伴季报" / "产品复盘" / "募款汇报"
    audience: str        # 受众："客户决策层" / "集团内部决策层" / "公众"
    tone: str            # 语气："专业冷静" / "诚恳坦率" / "鼓舞性"
    period_start: str    # ISO 日期
    period_end: str
    sections: list[SectionPlan]  # 由 LLM 决定数量与顺序
    
    # 元数据
    inferred_theme: str  # LLM 总结这条事件线的主题（1-2 句）
    confidence: float = Field(default=0.8, ge=0, le=1)  # 骨架的置信度
    open_questions_for_human: list[str] = Field(default_factory=list)
    
    # 数据来源元信息
    event_line_id: str | None = None
    client_id: str
    generated_at: str  # ISO 时间戳
```

### 2.2 SectionContent（阶段二每章产物）

```python
class CitationRef(BaseModel):
    """正文内引用的源数据条目。"""
    type: Literal["judgment", "event", "task", "document", "metric", "commit"]
    id: str  # 数据库里的 ID 或 commit hash
    label: str  # 短标签（如 "20fde25" 或 "客户A 战略目标 #3"）
    excerpt: str | None = None  # 可选的引用原文


class GeneratedChart(BaseModel):
    """已生成的信息图。"""
    hint: ChartHint
    png_bytes_base64: str  # base64 编码的 PNG
    width_cm: float = 14.5


class SectionContent(BaseModel):
    """单章节填充结果。"""
    plan: SectionPlan
    markdown: str  # 章节正文 Markdown（不含章标题，标题由 plan.title 给）
    citations: list[CitationRef] = Field(default_factory=list)
    charts: list[GeneratedChart] = Field(default_factory=list)
    data_source_annotation: str  # 章节末尾"数据源"标注内容
    confidence: float = Field(default=0.7)
    warnings: list[str] = Field(default_factory=list)  # 起草中遇到的告警
```

### 2.3 ReportArtifact（阶段三最终产物）

```python
class ReportArtifact(BaseModel):
    """完整生成的报告。"""
    blueprint: ReportBlueprint
    sections: list[SectionContent]
    output_files: dict[str, str]  # {"docx": "/path/to/...", "pdf": "/path/to/...", "md": "..."}
    generated_at: str
    total_llm_tokens: int
    total_cost_usd: float = 0.0
```

---

## Part 3 · 阶段一详细规格：骨架推导

### 3.1 上下文收集（取数）

新建 `backend/app/services/report_context_builder.py`：

```python
class EventLineFullContext(BaseModel):
    """喂给阶段一 LLM 的完整事件线上下文。"""
    
    # 基础
    event_line_id: str
    client: ClientSummary
    period_start: str
    period_end: str
    
    # 事件
    events: list[EventEntry]  # 事件线上的所有 entry
    event_themes: list[str]  # 系统抽取的主题
    
    # 判断
    confirmed_judgments: list[JudgmentSummary]
    open_questions: list[str]
    
    # 关键对象
    mentioned_objects: list[str]  # 关键项目/概念/产品
    key_persons: list[PersonRef]
    
    # 行动
    tasks_open: list[TaskSummary]
    tasks_done: list[TaskSummary]
    
    # 文档
    key_documents: list[DocumentRef]  # 高相关性的文档（不含全文）
    
    # 元数据
    last_report: ReportArtifact | None = None  # 上次报告（如有）
    user_intent_hint: str | None = None  # 用户给的报告意图提示


def build_event_line_full_context(
    *, event_line_id: str | None = None,
    client_id: str | None = None,
    period_start: str, period_end: str,
    user_intent_hint: str | None = None,
) -> EventLineFullContext:
    """聚合所有相关数据。"""
    # 优先用 event_line_id；如无，用 client_id + 报告期聚合
    ...
```

### 3.2 LLM 角色 A 提示词模板

新建 `backend/app/services/report_blueprint_drafter.py`：

```python
BLUEPRINT_SYSTEM_PROMPT = """你是益语智库的"报告主理人"。你的工作不是写报告正文，
而是基于事件线的全量上下文，决定这份报告**应该长什么样**——章节怎么分、每章要回答
什么、需要哪些图表、引用预算多大。

【你的判断要遵循的原则】

1. 章节骨架不是套路。每条事件线主题不同，骨架也应该不同。
   - 战略陪伴客户的季度报告 ≠ 内部产品复盘 ≠ 募款用 ≠ 危机应对
   - 同客户不同阶段（启动 / 推进 / 收尾）也应该不同

2. 决定受众语气。基于事件线主题和上下文猜读者：客户决策层？集团内部？公众？
   选择对应语气：专业冷静 / 诚恳坦率 / 鼓舞 / 数据驱动 等。

3. 取数计划具体。每章节要写明数据从哪取——不要笼统说"事件线"，
   而是说"事件线 entry id 1-15 + 客户 A 当前 KPI"等。

4. 图表要适配章节用途。
   - 占比类（commit 类型/资料类型）→ pie
   - 前后对比 → progress_bar_h
   - 大事记 → timeline
   - 风险评估 → risk_bubble
   - 多周期对比 → grouped_bar

5. 引用预算要现实。短章节 2-3 条，深度分析章 5-8 条。

【输入上下文】

事件线主题：{theme}
报告期：{period}
用户意图：{user_intent}
事件线 entries（精选）：{events_summary}
关键判断：{judgments}
开放问题：{open_questions}
任务清单：{tasks}
主要文档：{docs}
关键人物/对象：{key_objects}
上次报告（如有）：{last_report_summary}

【你的产出】

输出 ReportBlueprint 的 JSON（schema 见接口契约），包括：
- title / subtitle / report_kind / audience / tone
- inferred_theme（1-2 句总结）
- sections: 列表，每个 section 含 level / title / goal / data_sources /
  chart_hints / citation_budget / estimated_words
- open_questions_for_human: 你想让主理人确认的事项（如有）
- confidence: 0-1

【风格约束】

- title 要具体，不要套话（避免"XX 报告"这种笼统标题）
- 每章 goal 不超过 60 字
- 章节数量 3-9 个为宜（含附录）
- 至少有一章是"行动建议"或等价物
- 至少有一张图表（数据足够时）

仅返回 JSON，不要解释。
"""


def draft_blueprint(
    context: EventLineFullContext,
    *, llm_service,  # AiService 实例
) -> ReportBlueprint:
    rendered = BLUEPRINT_SYSTEM_PROMPT.format(
        theme=context.event_themes,
        period=f"{context.period_start} ~ {context.period_end}",
        user_intent=context.user_intent_hint or "（无显式意图）",
        events_summary=_summarize_events(context.events),
        judgments=_summarize_judgments(context.confirmed_judgments),
        open_questions=context.open_questions,
        tasks=_summarize_tasks(context.tasks_open + context.tasks_done),
        docs=_summarize_docs(context.key_documents),
        key_objects=context.mentioned_objects,
        last_report_summary=_summarize_last_report(context.last_report),
    )
    raw = llm_service.generate_structured(prompt=rendered, ...)
    return ReportBlueprint.model_validate_json(raw.content)
```

### 3.3 阶段一验收

阶段一**唯一产出**是一份 `ReportBlueprint`。验收标准：

- [ ] 同一条事件线连跑 3 次，章节数 ±1（稳定性）
- [ ] 战略陪伴 vs 产品复盘 vs 危机应对 三种 hint 下，章节标题明显不同
- [ ] 每个 SectionPlan 都有 data_sources 列表非空
- [ ] 至少 1 个 chart_hint（如有数据支持）
- [ ] confidence ≥ 0.6

---

## Part 4 · 阶段二详细规格：分批填充

### 4.1 章节起草员

新建 `backend/app/services/section_drafter.py`：

```python
SECTION_DRAFTER_PROMPT = """你是益语智库"章节起草员"。你接到一个章节计划和该
章节专属的数据包，按要求起草这一章的 Markdown 正文。

【章节计划】
{section_plan_json}

【受众与语气】
受众：{audience}
语气：{tone}

【可用数据】
{section_data_pack_json}

【引用要求】
- 每个判断/数据要带 [^id] 风格引用标记，id 是 CitationRef 里的 id
- 每个引用末尾自动生成"数据源"标注
- 引用预算：{citation_budget} 条

【输出要求】

1. 仅返回 Markdown 正文（不含章标题，章标题由系统按 section_plan.title 渲染）
2. 不要使用 emoji（用文字符号或圆点替代）
3. 使用 H2 (##) 作为本章内最高层级
4. 表格用 GFM 表格语法
5. 关键判断加粗
6. 在适当位置标记 [CHART:N]，N 是 chart_hints 数组里的索引——系统会自动插入对应图表

【字数控制】
目标约 {estimated_words} 字，浮动 ±20%。

仅返回 Markdown 字符串，不要 ``` 包裹。
"""


def draft_section(
    plan: SectionPlan,
    *,
    audience: str,
    tone: str,
    data_pack: SectionDataPack,
    llm_service,
) -> SectionContent:
    ...
```

### 4.2 章节并行调度

```python
def draft_all_sections(
    blueprint: ReportBlueprint,
    *,
    context: EventLineFullContext,
    llm_service,
    parallel: bool = True,
) -> list[SectionContent]:
    """章节级并行调度。
    
    依赖关系：
    - 摘要类章节（通常第一章）依赖其他章节先出 → 单独最后写
    - 其他章节相互独立 → 并行
    """
    summary_sections, body_sections = _partition_summary(blueprint.sections)
    
    # body 章节并行
    if parallel:
        with ThreadPoolExecutor(max_workers=4) as pool:
            body_results = list(pool.map(
                lambda s: draft_section(s, ...),
                body_sections,
            ))
    else:
        body_results = [draft_section(s, ...) for s in body_sections]
    
    # 摘要章节最后写（拿到 body 全部内容做总结）
    summary_results = [
        draft_summary_section(s, body_results, ...) 
        for s in summary_sections
    ]
    
    return [*summary_results, *body_results]
```

### 4.3 图表生成对接

每个 SectionContent 在起草后调用图表生成：

```python
def materialize_charts(content: SectionContent, data_pack: SectionDataPack) -> SectionContent:
    """根据 plan.chart_hints 调 chart_generator 生成 PNG。"""
    charts = []
    for hint in content.plan.chart_hints:
        chart_data = _resolve_chart_data(hint, data_pack)  # 从数据包提取所需数据
        png = _dispatch_chart(hint.kind, chart_data)
        charts.append(GeneratedChart(
            hint=hint,
            png_bytes_base64=base64.b64encode(png).decode(),
        ))
    content.charts = charts
    return content


def _dispatch_chart(kind: str, data: ChartData) -> bytes:
    """调对应的 chart_generator 函数。"""
    import chart_generator as cg
    if kind == "pie":
        return cg.pie_commit_breakdown(**data.to_pie_kwargs())
    elif kind == "progress_bar_h":
        return cg.progress_bar_h(**data.to_progress_kwargs())
    elif kind == "timeline":
        return cg.timeline(**data.to_timeline_kwargs())
    elif kind == "grouped_bar":
        return cg.grouped_bar(**data.to_grouped_kwargs())
    elif kind == "risk_bubble":
        return cg.risk_bubble(**data.to_risk_kwargs())
    else:
        return b""  # table_only / callout_only
```

---

## Part 5 · 阶段三：排版与导出

### 5.1 docx 渲染器

新建 `backend/app/services/report_docx_renderer.py`，**直接复用沙箱里 `generate_report.py` 的 helper**：

- `add_heading` / `add_paragraph` / `add_bullet` / `add_table` / `add_callout`
- `add_data_source` / `add_horizontal_rule` / `add_page_break`
- 新增 `add_image_from_bytes`（已在 `generate_internal_report.py` 验证过）

主流程：

```python
def render_report_to_docx(
    artifact: ReportArtifact,
    *, output_path: Path,
) -> Path:
    doc = Document()
    _apply_default_style(doc)
    
    # 封面
    _render_cover(doc, artifact.blueprint)
    add_page_break(doc)
    
    # 报告说明（callout）
    _render_intro_callout(doc, artifact.blueprint)
    
    # 章节
    for section in artifact.sections:
        _render_section(doc, section)
        if section.plan.level == 1:
            add_page_break(doc)  # 一级章节分页
    
    # 附录
    _render_appendix(doc, artifact)
    
    doc.save(output_path)
    return output_path


def _render_section(doc, section: SectionContent):
    plan = section.plan
    add_heading(doc, plan.title, level=plan.level)
    
    # 解析 markdown 正文，处理 [CHART:N] 占位符
    blocks = _parse_markdown_with_chart_placeholders(section.markdown)
    for block in blocks:
        if block.type == "chart":
            chart = section.charts[block.chart_index]
            add_image_from_bytes(
                doc,
                base64.b64decode(chart.png_bytes_base64),
                width_cm=chart.width_cm,
                caption=chart.hint.caption,
            )
        elif block.type == "table":
            add_table(doc, block.headers, block.rows)
        elif block.type == "callout":
            add_callout(doc, block.text)
        elif block.type == "bullet_list":
            for item in block.items:
                add_bullet(doc, item)
        else:
            add_paragraph(doc, block.text)
    
    # 数据源标注
    if section.data_source_annotation:
        add_data_source(doc, section.data_source_annotation)
```

### 5.2 PDF 与 markdown 导出

```python
def render_to_pdf(docx_path: Path) -> Path:
    """走 LibreOffice headless 转 PDF（与沙箱演示一致）。"""
    ...

def render_to_markdown(artifact: ReportArtifact) -> str:
    """生成纯 markdown 版本（便于版本控制和邮件正文）。"""
    ...
```

---

## Part 6 · API 设计

新建 `backend/app/main.py` 路由：

```python
@app.post("/api/v1/reports/draft-blueprint")
async def draft_blueprint(req: DraftBlueprintRequest) -> ReportBlueprint:
    """阶段一：推导骨架。
    
    入参：event_line_id 或 (client_id, period, intent_hint)
    出参：ReportBlueprint（含 open_questions_for_human 供前端确认）
    """
    ...


@app.post("/api/v1/reports/{report_run_id}/draft-sections")
async def draft_sections(report_run_id: str, req: DraftSectionsRequest):
    """阶段二：填充章节（可并行）。
    
    幂等：单章节级幂等（重跑同章节用最新版替换）
    """
    ...


@app.post("/api/v1/reports/{report_run_id}/render")
async def render_report(report_run_id: str, format: Literal["docx", "pdf", "md"]) -> ReportArtifact:
    """阶段三：渲染并落盘。"""
    ...


@app.get("/api/v1/reports/{report_run_id}")
async def get_report_run(report_run_id: str) -> ReportRunStatus:
    """查询进度，包含每个章节的状态。"""
    ...


@app.post("/api/v1/reports/{report_run_id}/sections/{section_idx}/revise")
async def revise_section(report_run_id: str, section_idx: int, req: ReviseRequest):
    """主理人修订单章节后重新渲染。"""
    ...
```

数据库新表：

```sql
CREATE TABLE IF NOT EXISTS report_runs (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    event_line_id TEXT,
    period_start TEXT,
    period_end TEXT,
    intent_hint TEXT,
    status TEXT NOT NULL DEFAULT 'blueprint_pending',
    -- blueprint_pending → blueprint_confirmed → drafting → rendered → published
    blueprint_json TEXT,
    artifact_json TEXT,
    docx_path TEXT,
    pdf_path TEXT,
    md_path TEXT,
    total_llm_tokens INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_section_runs (
    id TEXT PRIMARY KEY,
    report_run_id TEXT NOT NULL REFERENCES report_runs(id),
    section_idx INTEGER NOT NULL,
    plan_json TEXT NOT NULL,
    content_json TEXT,  -- SectionContent
    status TEXT DEFAULT 'pending',  -- pending|drafting|done|failed
    error_message TEXT,
    llm_tokens INTEGER DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    UNIQUE(report_run_id, section_idx)
);
```

---

## Part 7 · 实施迭代（5 个迭代）

### 迭代 R0 · 准备工作

**目标：** 起点 + 复用现有沙箱原型

- [ ] 新分支 `feature/report-generation`（起点 main）
- [ ] 把沙箱里的两份原型搬进项目：
  - `backend/app/services/report_chart_generator.py`（来自 `chart_generator.py`）
  - `backend/app/services/report_docx_helpers.py`（来自 `generate_report.py` 的 helper）
- [ ] 装依赖：`apscheduler` 不需要（这版不用 cron）；`matplotlib>=3.10` `python-docx>=1.2` 大概率已有
- [ ] 写 progress 文档 `docs/report-generation-progress.md`

**预算：** 15-25 工具调用

### 迭代 R1 · 数据契约与骨架推导（阶段一）

**目标：** 跑通"事件线 → ReportBlueprint"

- [ ] 落地 Pydantic 模型（`ReportBlueprint / SectionPlan / ChartHint`）
- [ ] 实现 `report_context_builder` 聚合事件线全量上下文
- [ ] 实现 `report_blueprint_drafter`（LLM 角色 A）
- [ ] `report_runs` 表 + 状态机
- [ ] API: `POST /api/v1/reports/draft-blueprint`
- [ ] 测试：用日慈事件线 + 益语 V2.0 git log 两个 case 验证骨架明显不同
- [ ] 至少 5 个测试

**验收：**
- [ ] 同事件线 3 次跑章节数 ±1
- [ ] 战略陪伴 vs 产品复盘 hint 下章节标题明显不同
- [ ] 每个 section_plan 都有 chart_hints 和 data_sources

**预算：** 50-70 工具调用，派 Builder Agent

### 迭代 R2 · 章节填充（阶段二）

**目标：** 跑通"骨架 + 数据 → 章节 Markdown"

- [ ] 实现 `section_drafter`（LLM 角色 B）
- [ ] 实现 `materialize_charts`（章节级图表生成）
- [ ] 并行调度（ThreadPoolExecutor）
- [ ] `report_section_runs` 表 + 状态机
- [ ] API: `POST /api/v1/reports/{id}/draft-sections`
- [ ] 测试：用 R1 骨架填充全部章节，验证每章都能产出
- [ ] 至少 5 个测试

**验收：**
- [ ] 8 章节并行填充 < 60 秒（取决于 LLM 速度）
- [ ] 每章节有 ≥1 个 citation
- [ ] [CHART:N] 占位符与 chart_hints 数量匹配

**预算：** 50-70 工具调用

### 迭代 R3 · 排版导出（阶段三）

**目标：** 跑通"章节内容 → docx + pdf"

- [ ] 实现 `report_docx_renderer`
- [ ] 实现 markdown 解析（带 [CHART:N] 占位符）
- [ ] LibreOffice headless 转 PDF
- [ ] API: `POST /api/v1/reports/{id}/render`
- [ ] 端到端：从事件线到 .docx 全流程跑通

**验收：**
- [ ] 用日慈事件线端到端生成 .docx，肉眼对比沙箱 mock 接近
- [ ] 信息图正确嵌入
- [ ] 引用编号在文档里有效

**预算：** 40-55 工具调用

### 迭代 R4 · UI 入口

**目标：** 客户工作台能触发报告生成 + 查看进度 + 下载

- [ ] 客户工作台新增"生成报告"按钮
- [ ] 弹层：选事件线 + 报告期 + 意图提示
- [ ] 进度页：显示骨架预览 → 章节生成进度 → 渲染完成
- [ ] 主理人审阅 UI：分章节卡片可重新生成 / 编辑

**验收：**
- [ ] 用户能在 UI 上完整跑通"配置 → 骨架 → 章节 → 下载"
- [ ] 每个章节有"重新生成"按钮

**预算：** 60-80 工具调用

### 迭代 R5 · 多类型样例 + 文档

**目标：** 跑出 3-5 种不同主题的报告作为验证集

- [ ] 收集（或模拟）3-5 条不同主题的事件线（战略陪伴 / 内部产品 / 募款 / 危机 / 单项目复盘）
- [ ] 对每条事件线跑端到端，导出 docx
- [ ] 对比章节骨架的差异
- [ ] 撰写《报告生成器使用手册》
- [ ] 撰写《模板配置层指南》（运营人员怎么调骨架默认偏好）

**验收：**
- [ ] 5 种主题下章节骨架差异显著
- [ ] 使用手册让非工程人员能跑

**预算：** 30-45 工具调用

---

## Part 8 · 信息图设计规约

### 8.1 5 类图（直接复用沙箱原型）

| kind | 用途 | 参数关键字段 |
|---|---|---|
| `pie` | 占比类（commit 类型 / 资料分类 / 时间分配） | labels, counts |
| `progress_bar_h` | 完成度横向条（带前后对比 + 目标线） | items, before, after, target |
| `timeline` | 大事记 / 里程碑（带状态徽章） | events: list[(date, label, status)] |
| `grouped_bar` | 多周期或多对象对比 | categories, series_a/b values |
| `risk_bubble` | 风险矩阵（影响 × 概率，气泡大小为权重） | risks: list[(name, impact, prob, weight)] |

### 8.2 配色 token

```python
BRAND = "#2E75B6"        # 益语主蓝
BRAND_LIGHT = "#5B9BD5"
BRAND_DARK = "#1F4E79"
GREEN = "#2EA047"        # 平稳 / 完成
YELLOW = "#E69F00"       # 关注 / 进行中
RED = "#C0392B"          # 风险 / 高
GREY = "#888888"
GREY_LIGHT = "#DDDDDD"
```

### 8.3 字体配置

```python
# 跨平台中文 + ASCII 混排（沙箱已验证）
rcParams["font.family"] = ["PingFang SC", "Microsoft YaHei", "Droid Sans Fallback", "DejaVu Sans"]
```

### 8.4 不引入 AI 生图

- 不依赖 DALL-E / Midjourney / Stable Diffusion
- 战略概念图（双飞轮等）用 SVG 模板 + 文本变量替换
- 装饰性插画用一次性手工设计的 SVG / PNG 资源库

**理由见沙箱 `docs/报告生成-架构逆向工程-2026-05-12.md` Part 5。**

---

## Part 9 · 与已规划线程的关系

| 线程 | 关系 |
|---|---|
| 主动能力 A1（调度器） | 报告生成可挂载到调度器实现"周报/月报/季报"定时触发；R0 阶段不依赖 |
| 主动能力 A2（通知中心） | 报告生成完成时投递通知；R3 阶段加上 |
| 主动能力 A3（事件总线） | 报告完成发布 `report.generated` 事件供下游消费 |
| 理解深度 迭代 5（关系图谱） | 报告里"关系/依赖图"章节可以用关系图谱数据填充；R2 阶段可对接 |
| 理解深度 迭代 6（矛盾告警） | 报告里"风险"章节可显示当期未 dismiss 的矛盾告警；R2 阶段对接 |
| 生产能力 P3（PDF） | LibreOffice headless 已能转 PDF；不强依赖 P3 |

**结论：** 报告生成器**主要依赖现有数据**（events / judgments / tasks / git log / docs），新依赖很少。**可以与其他线程完全并行启动。**

---

## Part 10 · 验收（端到端 demo）

成功标准：用户在客户工作台点"生成报告" → 选某事件线 → 填意图（可选）→ 一键 → 几分钟后下载 .docx：

1. ✅ 章节骨架由事件线主题自动推导
2. ✅ 同一事件线连续 3 次跑章节稳定
3. ✅ 3-5 种不同主题事件线下章节明显不同
4. ✅ 报告含信息图（饼/进度/时间线 等至少 2 类）
5. ✅ 每段判断带引用，可追溯到源数据
6. ✅ 主理人能逐章节预览 + 重新生成 + 编辑后再渲染
7. ✅ 端到端总时长 ≤ 5 分钟（8 章节）

---

## Part 11 · 风险与权衡

| 风险 | 缓解 |
|---|---|
| LLM 角色 A 输出 JSON 格式不稳 | 用 structured output / function calling；retry + 校验 |
| 章节并行调度 LLM 速率限制 | 默认 max_workers=4；可配置 |
| 章节间事实不一致 | 阶段三引入 LLM 角色 C 润色员做事实交叉验证 |
| 大事件线（>50 entries）prompt 超长 | 阶段一对事件做摘要（保留 ID + 标题 + 摘要 + 时间），不传全文 |
| 中文字体跨平台 | 沙箱已验证：DejaVu Sans + Droid Sans Fallback / PingFang SC / Microsoft YaHei 字体链 |
| LLM 写出虚构事实 | 引用预算 + 数据源标注 + 主理人审阅；高风险结论必须有 [^id] 引用 |

---

## Part 12 · 第一步动作

1. 看完本计划全文
2. 看沙箱里 3 份原型代码：
   - `/sessions/nifty-zen-euler/mnt/outputs/chart_generator.py`（图表生成器）
   - `/sessions/nifty-zen-euler/mnt/outputs/generate_report.py`（docx helper + 战略陪伴样例）
   - `/sessions/nifty-zen-euler/mnt/outputs/generate_internal_report.py`（产品复盘样例 + 图嵌入）
3. 看两份生成出来的 docx：
   - `docs/日慈战略陪伴报告-Q1-2026.docx`
   - `docs/益语智库V2.0-产品开发复盘-Q1-2026.docx`（含图）
4. 跟用户（顾源源）确认：
   - 这份执行计划的整体方向 OK 吗？
   - 第一步切入哪个迭代（推荐 R0 + R1）
   - LLM 角色 A/B/C 各用什么模型（成本 vs 质量）
5. 进入 R0 准备工作

---

## Part 13 · 关键引用

- 本计划：`docs/报告生成器-Claude-Code执行计划-2026-05-12.md`
- 板块设计：`docs/报告生成-架构逆向工程-2026-05-12.md`
- 战略陪伴 mock 报告（md）：`docs/日慈战略陪伴报告-Q1-2026-MOCK.md`
- 战略陪伴 docx：`docs/日慈战略陪伴报告-Q1-2026.docx`
- 产品复盘 docx（含图）：`docs/益语智库V2.0-产品开发复盘-Q1-2026.docx`
- 沙箱图表生成器原型：`/sessions/nifty-zen-euler/mnt/outputs/chart_generator.py`
- 沙箱 docx helper 原型：`/sessions/nifty-zen-euler/mnt/outputs/generate_report.py`

完。
