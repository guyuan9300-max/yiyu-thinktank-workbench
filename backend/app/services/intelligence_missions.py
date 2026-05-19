"""资讯情报站 Standing Missions（P9-Mission）。

定位：情报站的**自有任务清单**，不是数据中心派的活。
  - 每个 mission 代表情报站永久站岗的一个监控维度
  - 用数据中心的客户档案"定向"——知道每个站岗具体盯哪几个名字
  - 每次抓取时按激活的 mission 生成对应 query

这是把「为搜而搜」变成「为任务而搜」的核心数据结构。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────────────────────────────────
# 6 个 standing missions（情报站永久任务清单）
# ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MissionSpec:
    """单个 mission 的定义 — 这是产品语言，用户能看见。"""
    key: str                       # 程序内识别（key_persons_voice / negative_signals 等）
    name: str                      # 显示名（关键人物追踪 / 负面预警）
    intent: str                    # 单句描述：这个站岗在抓什么信号
    value_criteria: str            # 这个 mission 的「什么算高价值」
    target_count: int              # 该 mission 期望生成的 query 数
    requires_signals: tuple[str, ...]  # 依赖的客户档案信号（找不到则跳过）
    priority_base: int             # 该 mission query 的基准 priority


# 6 个 mission — 顺序是默认权重顺序
MISSIONS: tuple[MissionSpec, ...] = (
    MissionSpec(
        key="key_persons_voice",
        name="关键人物追踪",
        intent="监控客户核心人物（创始人/秘书长/首席研究员）的公开发声、被报道、被引用",
        value_criteria="必须含人物姓名 + 公开发声场景词（演讲/专访/署名文章/接受采访）",
        target_count=12,
        requires_signals=("glossaryPersons",),
        priority_base=85,
    ),
    MissionSpec(
        key="core_projects_reception",
        name="核心项目口碑",
        intent="监控客户旗下具体项目的反馈/评价/学员声音/合作方反馈",
        value_criteria="必须含具体项目名 + 评价/反馈/学员/口碑/参与体验",
        target_count=10,
        requires_signals=("glossaryProjects", "projectModules"),
        priority_base=80,
    ),
    MissionSpec(
        key="negative_signals",
        name="负面预警",
        intent="主动扫客户的投诉/质疑/曝光/争议/危机信号",
        value_criteria="含投诉/质疑/曝光/维权/举报等关键词 + target 出现",
        target_count=8,
        requires_signals=(),  # 主名+别名就够
        priority_base=90,
    ),
    MissionSpec(
        key="brand_impression",
        name="品牌印象 vs 自我定位",
        intent="搜公众怎么形容客户，对比客户自我定位算 gap",
        value_criteria="含品牌形容词 / 印象标签 / 形象描述类内容",
        target_count=8,
        requires_signals=("brandProposition",),
        priority_base=75,
    ),
    MissionSpec(
        key="funding_opportunities",
        name="时效机会扫描",
        intent="扫客户可申报的资助/招标/政府购买/合作机会",
        value_criteria="含资助/招标/购买/申报/征集 + 业务域匹配",
        target_count=10,
        requires_signals=("domain",),
        priority_base=70,
    ),
    MissionSpec(
        key="industry_context",
        name="行业语境追踪",
        intent="跟踪客户所在行业的同行/标杆/政策走向/讨论焦点",
        value_criteria="含业务域 + 行业/同行/标杆/比较 类内容",
        target_count=6,
        requires_signals=("domain",),
        priority_base=60,
    ),
)


def get_mission_by_key(key: str) -> MissionSpec | None:
    for m in MISSIONS:
        if m.key == key:
            return m
    return None


# ──────────────────────────────────────────────────────────────────────────
# 客户级 mission 激活配置
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class ClientMissionConfig:
    """客户级别哪些 mission 激活。

    默认全开。后续 UI 让用户按客户调（如某客户不想开负面预警就关掉）。
    """
    client_id: str
    activated_keys: set[str] = field(default_factory=lambda: {m.key for m in MISSIONS})

    def is_active(self, key: str) -> bool:
        return key in self.activated_keys


def default_mission_config(client_id: str) -> ClientMissionConfig:
    """新客户默认全开 6 个 mission。"""
    return ClientMissionConfig(client_id=client_id)


# ──────────────────────────────────────────────────────────────────────────
# 根据客户档案信号过滤可激活的 mission
# ──────────────────────────────────────────────────────────────────────────


def effective_missions(
    config: ClientMissionConfig,
    signals: dict[str, Any],
) -> list[MissionSpec]:
    """返回当前能跑的 mission 列表（按 priority_base 倒序）。

    跳过条件：
      - mission 未激活
      - mission 依赖的 signals 全空（如「关键人物追踪」但客户没有 glossaryPersons）
    """
    out: list[MissionSpec] = []
    for m in MISSIONS:
        if not config.is_active(m.key):
            continue
        # 依赖的 signals 至少有一个非空才上
        if m.requires_signals:
            has_any_signal = any(
                bool(signals.get(req))
                for req in m.requires_signals
            )
            if not has_any_signal:
                continue
        out.append(m)
    out.sort(key=lambda x: x.priority_base, reverse=True)
    return out


# ──────────────────────────────────────────────────────────────────────────
# Mission 健康度报告（给用户看）
# ──────────────────────────────────────────────────────────────────────────


def mission_readiness_report(
    config: ClientMissionConfig,
    signals: dict[str, Any],
) -> dict[str, Any]:
    """生成 mission-level 的"准备度"报告。

    {
      "totalMissions": 6,
      "activatedCount": 6,
      "readyCount": 4,
      "blockedCount": 2,
      "missions": [
        {key, name, status: 'ready'|'inactive'|'blocked_no_signals',
         expectedQueries, blockedReason?}
      ]
    }
    """
    items: list[dict[str, Any]] = []
    ready = 0
    blocked = 0
    for m in MISSIONS:
        if not config.is_active(m.key):
            items.append({
                "key": m.key,
                "name": m.name,
                "status": "inactive",
                "expectedQueries": 0,
            })
            continue
        if m.requires_signals:
            missing = [req for req in m.requires_signals if not signals.get(req)]
            if missing == list(m.requires_signals):
                # 所有依赖信号都缺
                items.append({
                    "key": m.key,
                    "name": m.name,
                    "status": "blocked_no_signals",
                    "blockedReason": f"客户档案缺少：{', '.join(missing)}",
                    "expectedQueries": 0,
                })
                blocked += 1
                continue
        ready += 1
        items.append({
            "key": m.key,
            "name": m.name,
            "status": "ready",
            "expectedQueries": m.target_count,
        })
    return {
        "totalMissions": len(MISSIONS),
        "activatedCount": sum(1 for m in MISSIONS if config.is_active(m.key)),
        "readyCount": ready,
        "blockedCount": blocked,
        "missions": items,
    }
