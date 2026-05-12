"""关系词典（迭代 5）。

按"主语 关系词 宾语"模板抽取，每个 predicate 配一组中文关键短语。
所有关系按客户隔离，subject/object 优先是 entities，object 可降级为
自由文本。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

# 17 类业务关系——覆盖客户战略陪伴场景里最高频的关联类型。
RelationPredicate = Literal[
    "cooperates_with",      # 合作 / 携手 / 联合
    "competes_with",        # 竞争 / 对手 / 抢
    "invests_in",           # 投资 / 注资
    "acquires",             # 收购 / 兼并
    "belongs_to",           # 隶属 / 属于 / 旗下
    "works_at",             # 任职 / 就职 / 担任
    "founded",              # 创立 / 创办
    "responsible_for",      # 负责 / 主管 / 牵头
    "supplies_to",          # 供应 / 供货 / 提供给
    "located_in",           # 位于 / 设在 / 驻
    "supersedes",           # 取代 / 替代
    "supports",             # 支持 / 赞同
    "opposes",              # 反对 / 拒绝
    "depends_on",           # 依赖 / 需要 / 取决于
    "produces",             # 生产 / 推出 / 发布
    "evaluates",            # 评价 / 认为 / 觉得
    "related_to",           # 关联 / 相关 / 涉及（兜底）
]

ALL_PREDICATES: Final[tuple[RelationPredicate, ...]] = (
    "cooperates_with",
    "competes_with",
    "invests_in",
    "acquires",
    "belongs_to",
    "works_at",
    "founded",
    "responsible_for",
    "supplies_to",
    "located_in",
    "supersedes",
    "supports",
    "opposes",
    "depends_on",
    "produces",
    "evaluates",
    "related_to",
)


@dataclass(frozen=True)
class RelationPattern:
    """关系抽取的模板：用一组 regex 表达"S ... predicate_word ... O"。

    每个 pattern 必须有 (?P<subject>...) 和 (?P<object>...) 两个命名捕获。
    """

    predicate: RelationPredicate
    pattern: re.Pattern[str]
    confidence: float


def _make(predicate: RelationPredicate, regex: str, confidence: float = 0.7) -> RelationPattern:
    return RelationPattern(
        predicate=predicate,
        pattern=re.compile(regex),
        confidence=confidence,
    )


# 用 [^，。\n]+? 匹配主/宾——避免跨句吃；用 {1,30} 限长避免暴走。
_NOUN = r"[一-龥A-Za-z0-9·]{2,30}"

RELATION_PATTERNS: Final[tuple[RelationPattern, ...]] = (
    # 合作
    _make("cooperates_with", rf"(?P<subject>{_NOUN})\s*(?:与|和|跟)\s*(?P<object>{_NOUN})\s*(?:合作|携手|联合|共同|签约)", 0.8),
    # 竞争
    _make("competes_with", rf"(?P<subject>{_NOUN})\s*(?:与|和|跟)\s*(?P<object>{_NOUN})\s*(?:竞争|对抗|争夺)", 0.8),
    _make("competes_with", r"(?P<subject>[一-龥A-Za-z0-9·]{2,15}?)(?:的)?\s*(?:主要|核心|直接)?\s*竞品(?:是|为)\s*(?P<object>[一-龥A-Za-z0-9·]{2,30})", 0.85),
    # 投资
    _make("invests_in", rf"(?P<subject>{_NOUN})\s*(?:投资|注资|入股)\s*(?:了)?\s*(?P<object>{_NOUN})", 0.85),
    # 收购
    _make("acquires", rf"(?P<subject>{_NOUN})\s*(?:收购|并购|兼并|拿下)\s*(?:了)?\s*(?P<object>{_NOUN})", 0.85),
    # 隶属（旗下/子公司）
    _make("belongs_to", rf"(?P<subject>{_NOUN})\s*(?:是)?\s*(?P<object>{_NOUN})\s*(?:旗下|的子公司|的母公司|的下属)", 0.8),
    # 任职
    _make("works_at", rf"(?P<subject>{_NOUN})\s*(?:在|于|是)\s*(?P<object>{_NOUN})\s*(?:任职|工作|就职|担任|出任)", 0.85),
    _make("works_at", rf"(?P<subject>{_NOUN})\s*(?:任|担任)\s*(?P<object>{_NOUN})\s*(?:总监|经理|总裁|董事长|CEO|CTO|CFO|COO|主任)", 0.7),
    # 创立
    _make("founded", rf"(?P<subject>{_NOUN})\s*(?:创立|创办|成立|创建|发起)\s*(?:了)?\s*(?P<object>{_NOUN})", 0.85),
    # 负责
    _make("responsible_for", rf"(?P<subject>{_NOUN})\s*(?:负责|主管|牵头|主导|分管)\s*(?P<object>{_NOUN})", 0.8),
    # 供应
    _make("supplies_to", rf"(?P<subject>{_NOUN})\s*(?:为|向|给)\s*(?P<object>{_NOUN})\s*(?:供应|供货|提供)", 0.8),
    # 位于
    _make("located_in", rf"(?P<subject>{_NOUN})\s*(?:位于|设在|总部在|注册在)\s*(?P<object>{_NOUN})", 0.85),
    # 取代
    _make("supersedes", rf"(?P<subject>{_NOUN})\s*(?:取代|替代|代替)\s*(?:了)?\s*(?P<object>{_NOUN})", 0.85),
    # 支持
    _make("supports", rf"(?P<subject>{_NOUN})\s*(?:支持|赞同|认可|背书)\s*(?P<object>{_NOUN})", 0.75),
    # 反对
    _make("opposes", rf"(?P<subject>{_NOUN})\s*(?:反对|拒绝|否决|不同意)\s*(?P<object>{_NOUN})", 0.85),
    # 依赖
    _make("depends_on", rf"(?P<subject>{_NOUN})\s*(?:依赖|取决于|需要|靠)\s*(?P<object>{_NOUN})", 0.7),
    # 生产
    _make("produces", rf"(?P<subject>{_NOUN})\s*(?:生产|推出|发布|上线|开发)\s*(?:了)?\s*(?P<object>{_NOUN})", 0.75),
    # 评价
    _make("evaluates", rf"(?P<subject>{_NOUN})\s*(?:评价|认为|觉得|表示)\s*(?P<object>{_NOUN})", 0.7),
)


# Predicate 中文展示名（用于 UI 标签）
PREDICATE_LABELS: Final[dict[str, str]] = {
    "cooperates_with": "合作",
    "competes_with": "竞争",
    "invests_in": "投资",
    "acquires": "收购",
    "belongs_to": "隶属",
    "works_at": "任职",
    "founded": "创立",
    "responsible_for": "负责",
    "supplies_to": "供应",
    "located_in": "位于",
    "supersedes": "取代",
    "supports": "支持",
    "opposes": "反对",
    "depends_on": "依赖",
    "produces": "生产",
    "evaluates": "评价",
    "related_to": "关联",
}


def label_for_predicate(predicate: str) -> str:
    return PREDICATE_LABELS.get(predicate, predicate)


__all__ = [
    "ALL_PREDICATES",
    "PREDICATE_LABELS",
    "RELATION_PATTERNS",
    "RelationPattern",
    "RelationPredicate",
    "label_for_predicate",
]
