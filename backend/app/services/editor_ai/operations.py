"""Editor AI Operation Registry.

每种 AI 动词的配置。新增 op 在 OPERATIONS 加一行；不在这里加业务逻辑。

faithful=True 的 op（翻译/提取要点/总结）会忽略前端传的 creativityMode，
强制走 strict 风格 + 低温度，避免「创意优先」让忠实型任务跑偏。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

OperationKey = Literal[
    # A 类 · 纯文本变换（无需 context；P13a 平移自旧 7 个 action）
    "expand",
    "rewrite_pro",
    "rewrite_short",
    "summarize",
    "extract",
    "translate",
    "style_distilled",
    # B 类 · 资料增强（P13b/c 接入，先占位）
    "insert_from_materials",
    "rewrite_by_strategy",
    "insert_data_table",
]


ContextSourceType = Literal[
    "selection_only",
    "current_doc",
    "client_materials",
    "strategy_dimension",
    "event_timeline",
]


@dataclass(frozen=True)
class OperationConfig:
    """单个 AI 动词的配置。

    Attributes:
        key: 唯一 key（与 OperationKey Literal 对齐）。
        label: 给前端 / 日志看的人话名。
        system: LLM system instruction（不含 creativityMode 注入）。
        user_prefix: 用户内容前的固定 prefix，整篇文档场景用，
                     例如「请翻译下面这份文档：\n\n」。
        user_prefix_selection: 选区场景的 prefix，例如「请翻译下面这段：\n\n」。
                               空字符串表示该 op 不支持选区，强制走全文。
        faithful: True 时强制 strict + 0.15 温度，忽略 creativityMode。
        allowed_contexts: 该 op 允许的 context source 类型。空元组 = 纯文本变换。
        output_format: 给前端的提示，默认 "markdown_replace"（替换全文）；
                       "markdown_insert" 表示插入到选区位置（B 类 op）。
    """
    key: str
    label: str
    system: str
    user_prefix: str
    user_prefix_selection: str = ""
    faithful: bool = False
    allowed_contexts: tuple[str, ...] = ()
    output_format: Literal["markdown_replace", "markdown_insert"] = "markdown_replace"
    # 资料增强类 op 可声明默认 context source（前端 UI 默认勾选）
    default_contexts: tuple[str, ...] = field(default_factory=tuple)


# ──────────────────────────────────────────────────────────────────
# A 类 · 纯文本变换（旧 7 个 action 1:1 平移；prompt 文本与原 main.py 完全一致）
# ──────────────────────────────────────────────────────────────────

_OP_EXPAND = OperationConfig(
    key="expand",
    label="扩写",
    system=(
        "你是 markdown 扩写助手。把用户给的 markdown 扩写得更详实：把简短的点扩展成完整段落、补充背景与细节、保留原意。"
        "**严格保持 markdown 格式**——原有的标题层级、列表、引用、表格、加粗、链接都要保留并自然扩展。"
        "不要添加任何「以下是扩写后的内容」之类的元话语，直接输出扩写后的 markdown。"
    ),
    user_prefix="请把下面这份文档扩写得更详实，保留 markdown 格式：\n\n",
    user_prefix_selection="请把下面这段扩写得更详实，保留 markdown 格式，**只输出扩写后的这一段**，不要重复其他内容：\n\n",
)

_OP_REWRITE_PRO = OperationConfig(
    key="rewrite_pro",
    label="改写 · 专业",
    system=(
        "你是公文改写助手。把用户给的 markdown 改写成更专业、更正式的书面语：保留原意、提升用词精度、统一句式。"
        "保持原 markdown 格式与结构。不要添加元话语，直接输出改写后的 markdown。"
    ),
    user_prefix="请把下面这份文档改写成更专业的书面表达：\n\n",
    user_prefix_selection="请把下面这段改写成更专业的书面表达，**只输出改写后的这一段**：\n\n",
)

_OP_REWRITE_SHORT = OperationConfig(
    key="rewrite_short",
    label="改写 · 简洁",
    system=(
        "你是文档精简助手。把用户给的 markdown 改写得更简洁：删冗余、并短句、保留关键信息。"
        "保持原 markdown 结构（标题层级、列表）。不要添加元话语，直接输出改写后的 markdown。"
    ),
    user_prefix="请把下面这份文档精简改写：\n\n",
    user_prefix_selection="请把下面这段精简改写，**只输出精简后的这一段**：\n\n",
)

_OP_SUMMARIZE = OperationConfig(
    key="summarize",
    label="总结",
    system=(
        "你是文档总结助手。把用户给的 markdown 内容总结成一份精炼版："
        "顶部一个 ## 标题「核心要点」，然后 3-6 条 bullet 列要点；"
        "再来一个 ## 标题「关键事实」，列出最重要的事实数据。"
        "不要添加元话语，直接输出 markdown。"
    ),
    user_prefix="请总结下面这份文档：\n\n",
    user_prefix_selection="请总结下面这段：\n\n",
    faithful=True,
)

_OP_EXTRACT = OperationConfig(
    key="extract",
    label="提取要点",
    system=(
        "你是要点提取助手。从用户给的 markdown 内容里抽取核心要点："
        "输出 markdown 列表（- 开头），每条要点一行，覆盖关键事实、判断、行动项三类。"
        "尽量保留原文中的关键短句不要改写。不要添加元话语。"
    ),
    user_prefix="请从下面这份文档抽取核心要点：\n\n",
    user_prefix_selection="请从下面这段抽取核心要点：\n\n",
    faithful=True,
)

_OP_TRANSLATE = OperationConfig(
    key="translate",
    label="翻译",
    system=(
        "你是 markdown 翻译助手。**严格保持 markdown 结构**（标题、列表、引用、表格、链接、加粗都要保留），"
        "只翻译文字内容。专有名词（人名、机构名、产品名）保留原文。"
        "默认翻译成英文；如果用户在补充要求里指明目标语言（例如「翻译成日文」），按用户要求。"
        "不要添加任何元话语，直接输出翻译后的 markdown。"
    ),
    user_prefix="请翻译下面这份文档：\n\n",
    user_prefix_selection="请翻译下面这段，**只输出翻译后的这一段**，不要重复其他内容：\n\n",
    faithful=True,
)

_OP_STYLE_DISTILLED = OperationConfig(
    key="style_distilled",
    label="风格化",
    system=(
        "你是文档风格化助手。在不改变原文事实和结构的前提下，按指定的写作风格重写措辞与句式。"
        "**严格保持 markdown 格式与所有事实/数据**。"
        "如果用户在补充要求或风格档案里给了具体风格描述，完全照办；否则用更生动、有温度的写作风格。"
        "不要添加元话语，直接输出风格化后的 markdown。"
    ),
    user_prefix="请按下面要求改写这份文档的语言风格：\n\n",
    user_prefix_selection="请按下面要求改写这段的语言风格，**只输出改写后的这一段**：\n\n",
)


# ──────────────────────────────────────────────────────────────────
# B 类 · 资料增强（P13b/c 接入，先占位 prompt；接入时根据效果再迭代）
# ──────────────────────────────────────────────────────────────────

_OP_INSERT_FROM_MATERIALS = OperationConfig(
    key="insert_from_materials",
    label="从资料生成此处段落",
    system=(
        "你是资料整合写作助手。用户在编辑一份 markdown 文档，希望在光标位置插入一段内容。"
        "你会收到：1) 当前文档全文（可能有上下文标题）；2) 一组来自客户资料库的资料块；3) 用户给出的具体要求。"
        "请基于资料块的事实写一段流畅 markdown 段落（不要列大纲，不要写元话语），"
        "**只输出要插入的那段内容**，不要重复文档已有内容。"
        "如有数据/人名/机构名，必须以资料块为准；资料没提到的内容**不要发明**。"
    ),
    user_prefix="请基于上述资料，在下面文档的光标处补写一段：\n\n",
    faithful=True,
    allowed_contexts=("client_materials", "current_doc"),
    output_format="markdown_insert",
    default_contexts=("client_materials",),
)

_OP_REWRITE_BY_STRATEGY = OperationConfig(
    key="rewrite_by_strategy",
    label="按战略方向重写",
    system=(
        "你是战略一致性改写助手。用户给你一段 markdown 内容，希望按指定的战略锚点重新调整措辞与重点。"
        "**事实和数据不能改**，只调整表达方式、详略侧重、价值取向，让段落跟战略锚点的口径一致。"
        "保持原 markdown 结构。直接输出改写后的段落，不要元话语。"
    ),
    user_prefix="请按上述战略锚点，重写下面这段：\n\n",
    allowed_contexts=("strategy_dimension", "selection_only"),
    output_format="markdown_replace",
    default_contexts=("strategy_dimension",),
)

_OP_INSERT_DATA_TABLE = OperationConfig(
    key="insert_data_table",
    label="插入数据表",
    system=(
        "你是数据整理助手。基于给定的事件线 / 事实数据，生成一份 markdown 表格。"
        "表头由你根据数据自然抽象（如「时间」「事件」「金额」「负责人」等）。"
        "**只输出表格**（一行表头 + 分隔线 + 数据行），不要前言后语。"
        "数据没出现的字段不要发明，留空或写「—」。"
    ),
    user_prefix="请把以下数据整理成 markdown 表：\n\n",
    faithful=True,
    allowed_contexts=("event_timeline", "client_materials"),
    output_format="markdown_insert",
    default_contexts=("event_timeline",),
)


OPERATIONS: dict[str, OperationConfig] = {
    op.key: op
    for op in (
        _OP_EXPAND,
        _OP_REWRITE_PRO,
        _OP_REWRITE_SHORT,
        _OP_SUMMARIZE,
        _OP_EXTRACT,
        _OP_TRANSLATE,
        _OP_STYLE_DISTILLED,
        _OP_INSERT_FROM_MATERIALS,
        _OP_REWRITE_BY_STRATEGY,
        _OP_INSERT_DATA_TABLE,
    )
}


# ──────────────────────────────────────────────────────────────────
# Creativity Mode 配置（system 文案 + temperature 映射）
# ──────────────────────────────────────────────────────────────────

CREATIVITY_HINTS: dict[str, str] = {
    "creative": (
        "【写作模式：创意优先】"
        "不必严格受限于原文事实，可以合理推断、补充背景、追求语言生动；"
        "原文中的数据/引用做装饰性陈述即可，不强调溯源。"
    ),
    "balanced": (
        "【写作模式：兼顾资料】"
        "原文中的事实、数据、引用必须保留不能编造；"
        "在事实底色上自由发挥措辞、叙事节奏与表达。"
    ),
    "strict": (
        "【写作模式：完全客观】"
        "严格基于原文已有事实，绝对不发明新数据/不臆测背景/不做文学修辞；"
        "措辞精准、保守、可溯源；如果原文未提及某事，输出里也不能出现。"
    ),
}

# faithful=False 时，creativityMode → temperature 的映射
TEMPERATURE_BY_CREATIVITY: dict[str, float] = {
    "creative": 0.55,
    "balanced": 0.4,
    "strict": 0.2,
}

# faithful=True 时统一使用的低温度
FAITHFUL_TEMPERATURE: float = 0.15
