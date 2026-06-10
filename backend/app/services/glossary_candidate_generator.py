"""Stage 1 · 字典候选 LLM 抽取 (LightRAG 轻量思路).

业界共识 (2026): 字典/ontology 层是消除 hallucination 的关键 — 但要轻量, 不要做
Microsoft GraphRAG 那种 $33K 的全量构建。LightRAG 的思路是边用边长 + 双层检索。

Stage 1 目标 (一次性, 看质量, 不写 db):
  · 收集 client 已有 entities + atomic_facts
  · 喂给豆包做 entity resolution (跨别名合并 + 上下文消歧)
  · 输出 60-150 个候选 term, 含 canonical_name + aliases + category + definition + supporting_source_ids

Stage 2 (下一步, 若 Stage 1 质量 OK): UI 让用户确认 / 合并 / 加别名, 落库 client_glossary
Stage 3 (再下一步): narrative_generator 改用字典做锚点, prompt 元规则降为 fallback
"""
from __future__ import annotations

import json
from typing import Any

from app.db import Database
from app.services.ai import AiInvocationError, AiService


GLOSSARY_OUTPUT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "terms": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "canonical_name": {"type": "STRING"},
                    "aliases": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "category": {"type": "STRING"},
                    "definition": {"type": "STRING"},
                    "supporting_source_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                    "needs_clarification": {"type": "STRING"},
                },
                "required": ["canonical_name", "category", "definition", "confidence"],
            },
        }
    },
    "required": ["terms"],
}


SYSTEM_PROMPT = """你是企业知识管理专家, 负责为益语智库的某个客户**构建项目字典**。

== 你的目标 ==

把数据中心已经预制好的 entities (机器抽的人/组织/日期/金额) + atomic_facts (LLM 抽的业务事实) 聚合成一份**结构化字典**, 让上层 (战略陪伴/事实澄清) 不再需要从碎片化 facts 拼装。

== 字典 term 标准 ==

  · **客户机构相关的关键概念** (不是流水账内容)
  · **多次提及/多文档共用** 的对象 (单点细节不收)
  · **客户/项目专属名** (例如"测试项目A"是 term, "项目"不是)

== 字典 6 类 category ==

  · **机构**: 客户机构、合作方、监管方、竞品
  · **项目**: 客户机构内部的具体项目/产品
  · **人物**: 客户方 + 益语方关键人物
  · **业务术语**: 客户行业的专有概念 (朋辈关怀员/循证心理产品/第二曲线 等)
  · **关键节点/数字**: 真实承诺日期 / 商业金额 / 服务对象数据
  · **规则/方法**: 客户内部的运作机制 / 制度

== 跨别名合并 (Entity Resolution 4 步) ==

  1. **直接匹配**: 名字相似 + 上下文一致 → 合并
  2. **间接链接**: 通过同一 atomic_fact subject 链接的实体
  3. **上下文消歧**: 名字相同但上下文不同 → 拆开 (例如 "张老师" 可能是 N 个人)
  4. **不确定的**: 写在 needs_clarification 字段

例:
  · "测试机构A"/"测试机构A"/"测试机构A" → canonical_name="测试机构A", aliases=[其他]
  · "高老师"/"高雪梅" — 若上下文显示是同一人 → 合并; 否则 → needs_clarification

== 来源溯源 ==

每个 term 必须有 supporting_source_ids — 列出 entity_id 或 atomic_fact_id, 让用户能追溯。

== 输出标准 ==

严格 JSON, 60-150 个 term。优先收高频提及 + 多文档共用的。
"""


# 项目类名识别 — 中文常见后缀 (经验性, 不限于此)
_PROJECT_SUFFIX_PATTERNS = (
    "计划", "学院", "项目", "工作坊", "培训",
    "课程", "营", "学堂", "学校", "中心", "实验室",
    "行动", "联盟", "网络", "基金", "战略",
)


_PROJECT_NOISE_PREFIXES = (
    # 动词/连词/虚词起头, 几乎不可能是项目名
    "做", "给", "做了", "会", "说", "它", "占据", "然后", "建议", "把", "用", "可", "需",
    "本", "个", "些", "所", "更多", "团队", "我们", "你", "他", "其", "们", "审", "整个",
    "先从", "建议以", "更多的是", "团队已经", "体的", "怎么", "些改变",
    "会只有",  # OCR 错别字残片
    "助", "助力",  # "助力 X" 不是项目, 是动作
    "的", "这", "一个", "一项", "另一", "在", "对", "为", "由",  # 助词/量词起头
    "次", "亲", "本",  # 残片"次连续 X", "亲身体验 X"
)
_PROJECT_NOISE_CONTAINS = (
    "如何", "什么", "是否", "我们", "你们", "他们", "这一个", "整个",
    "做项目", "说明学校", "占据", "落到",
    "我需要", "需要定义", "我看", "我觉",
)
# 通用单词后缀 — 单独成 term 不算项目 (例: "课程"/"基金"/"项目"/"营" 本身)
_GENERIC_BARE_TERMS = frozenset((
    "课程", "项目", "基金", "战略", "营", "学院", "计划", "培训",
    "工作坊", "学堂", "中心", "实验室",
))


def _is_project_like(text: str) -> bool:
    """启发式: text 末尾是中文项目类后缀, 且 3-12 字符, 没明显流水/动词/连词."""
    text = (text or "").strip()
    if not (3 <= len(text) <= 12):
        return False
    # 整 term 是通用后缀单词 (例如 "课程" / "基金" / "项目") — 不算项目
    if text in _GENERIC_BARE_TERMS:
        return False
    # 流水词/动词/连词起头 — 几乎不可能是项目名
    for prefix in _PROJECT_NOISE_PREFIXES:
        if text.startswith(prefix):
            return False
    # 含明显的"我们/这一个/做项目"等内嵌噪音
    if any(noise in text for noise in _PROJECT_NOISE_CONTAINS):
        return False
    # 必须以项目类后缀结尾
    if not any(text.endswith(suf) for suf in _PROJECT_SUFFIX_PATTERNS):
        return False
    return True


def _extract_project_mentions(value_text: str) -> list[str]:
    """从 value_text 里 grep 出『X计划』『X学院』『X营』等子串."""
    import re as _re
    if not value_text:
        return []
    # 中文 1-8 字 + 后缀
    pattern = _re.compile(
        r"[一-鿿]{1,8}(?:" + "|".join(_PROJECT_SUFFIX_PATTERNS) + r")"
    )
    found = set()
    for m in pattern.finditer(value_text):
        cand = m.group()
        # 过滤掉太短或含流水词的
        if _is_project_like(cand):
            found.add(cand)
    return list(found)


def _collect_project_candidates(db: Database, client_id: str) -> list[dict]:
    """主动 grep atomic_facts 找『测试项目A/测试项目C』这种项目名 — 不受 mention_count/attribute 频度过滤."""
    rows = db.fetchall(
        """
        SELECT id, subject_text, attribute, value_text, confidence
        FROM atomic_facts
        WHERE client_id = ? AND status='active' AND confidence >= 0.5
        """,
        (client_id,),
    )
    # 项目名 → 支撑 fact ids
    project_map: dict[str, list[str]] = {}
    for r in rows:
        fid = str(r["id"])
        subj = str(r["subject_text"] or "")
        val = str(r["value_text"] or "")
        # 1) subject 末尾是项目类后缀
        if _is_project_like(subj):
            project_map.setdefault(subj, []).append(fid)
        # 2) value 里含项目名 (grep)
        for cand in _extract_project_mentions(val):
            project_map.setdefault(cand, []).append(fid)
        # 3) subject 含项目名子串 (例: "建议以测试项目C中" → 测试项目C)
        for cand in _extract_project_mentions(subj):
            project_map.setdefault(cand, []).append(fid)
    # 排序 + 去重
    project_list = []
    for name, fids in project_map.items():
        unique_fids = list(dict.fromkeys(fids))  # 去重保序
        if len(unique_fids) >= 1:
            project_list.append({"name": name, "support_ids": unique_fids[:6], "support_count": len(unique_fids)})
    # 按支撑频度排序
    project_list.sort(key=lambda x: -x["support_count"])
    return project_list[:30]  # top 30


def _collect_task_owners(db: Database, client_id: str) -> list[dict]:
    """从 tasks 表抽 owner_name + 任务里出现的人名 (动作执行者)."""
    rows = db.fetchall(
        "SELECT DISTINCT owner_name FROM tasks WHERE client_id = ? AND owner_name != ''",
        (client_id,),
    )
    owners = [str(r["owner_name"]) for r in rows if str(r["owner_name"] or "").strip()]

    # 从 task.title + description 里抓人名 — 严过滤
    import re as _re
    title_rows = db.fetchall(
        "SELECT title, COALESCE(description,'') as description FROM tasks WHERE client_id = ?",
        (client_id,),
    )
    # "X老师" 模式: 必须是 2-3 字中文人名 + "老师" 后缀; X 不能是动词/状语
    # "X 工" 模式: 危险 — 只接受少数明确人名 (于工/方工/付工/周工 等)
    # "X 总/秘书长/主任/总监/经理" — 严格 (前缀 2-3 字)
    person_pat_strict = _re.compile(
        r"(?:[一-鿿]{2,3}老师|"
        r"[一-鿿]{1,2}秘书长|"
        r"[一-鿿]{2,3}(?:总监|主任|经理|总))"
    )
    # 已知人名词典 (字典里有 + 任务中可见的) — 用前缀匹配后单独白名单
    known_persons_white = ("于", "方", "付", "周", "钱", "刘", "李", "陈", "赵", "孙", "杨", "胡", "黄")
    noise_words = ("的", "了", "过", "可", "整", "些", "我", "你", "他", "们", "本", "通", "落", "陪", "动", "联",
                   "跟", "让", "和", "向", "对", "给", "被", "由", "在", "把", "为", "替", "找", "请", "派")

    found_in_titles: dict[str, int] = {}
    for r in title_rows:
        text = (r["title"] or "") + " " + (r["description"] or "")
        # 1) 严格 X老师/秘书长/总监 模式 — 剥离动词前缀
        for m in person_pat_strict.finditer(text):
            name = m.group().strip()
            # 剥离起头的动词/连词噪音字 (最多剥 2 字)
            while name and name[0] in noise_words and len(name) > 2:
                name = name[1:]
            if not name or name[0] in noise_words:
                continue
            # 剥离后还需至少 3 字 (1 字名 + 老师等 2 字后缀, 或 2 字名 + 1 字后缀)
            if len(name) < 3:
                continue
            found_in_titles[name] = found_in_titles.get(name, 0) + 1
        # 2) X工 模式 — 必须前缀字在 white list
        for m in _re.finditer(r"[一-鿿]工", text):
            name = m.group()
            if name[0] in known_persons_white:
                found_in_titles[name] = found_in_titles.get(name, 0) + 1

    return [
        {"name": o, "source": "task.owner_name", "count": 1} for o in set(owners)
    ] + [
        {"name": name, "source": "task.title", "count": cnt}
        for name, cnt in found_in_titles.items()
    ]


def _collect_task_deadlines(db: Database, client_id: str) -> list[dict]:
    """从 tasks.deadline_at 抽真实承诺日期."""
    rows = db.fetchall(
        """
        SELECT t.title, substr(t.deadline_at, 1, 10) as ddl, t.owner_name
        FROM tasks t WHERE t.client_id = ? AND t.deadline_at != ''
        ORDER BY ddl
        """,
        (client_id,),
    )
    return [
        {
            "deadline": str(r["ddl"]),
            "task_title": str(r["title"])[:40],
            "owner": str(r["owner_name"] or ""),
        }
        for r in rows
        if str(r["ddl"] or "").strip()
    ]


def _collect_task_action_types(db: Database, client_id: str) -> list[dict]:
    """从 task.title 抽动作类型 (动词+宾语模式)."""
    rows = db.fetchall(
        "SELECT title FROM tasks WHERE client_id = ?",
        (client_id,),
    )
    # 识别"X 改造/沟通/对齐/核对/更新/做方案/培训/演练" 等动作模式
    import re as _re
    action_pat = _re.compile(
        r"[一-鿿]{2,6}(?:改造|沟通|对齐|核对|更新|演练|培训|发布|发起|提交|交付|审核|"
        r"梳理|讨论|策划|设计|输出|联调|跟进|报销|预算|思考|分布|核算|策略)"
    )
    found: dict[str, int] = {}
    for r in rows:
        title = str(r["title"] or "")
        for m in action_pat.finditer(title):
            action = m.group()
            found[action] = found.get(action, 0) + 1
    return [{"action": a, "count": c} for a, c in sorted(found.items(), key=lambda x: -x[1])]


def _collect_meeting_titles(db: Database, client_id: str) -> list[dict]:
    """从 meetings 表抽会议标题作为活动候选."""
    try:
        rows = db.fetchall(
            "SELECT title, stage FROM meetings WHERE client_id = ?",
            (client_id,),
        )
    except Exception:
        return []
    return [
        {"title": str(r["title"]), "stage": str(r["stage"] or "")}
        for r in rows if str(r["title"] or "").strip()
    ]


def _collect_event_line_intents(db: Database, client_id: str) -> list[dict]:
    """从 event_lines.intent/next_step/recent_decision 抽业务承诺/动作."""
    rows = db.fetchall(
        """
        SELECT name, intent, next_step, recent_decision, current_blocker
        FROM event_lines WHERE primary_client_id = ?
        """,
        (client_id,),
    )
    out = []
    for r in rows:
        out.append({
            "line_name": str(r["name"] or ""),
            "intent": str(r["intent"] or "")[:200],
            "next_step": str(r["next_step"] or "")[:120],
            "decision": str(r["recent_decision"] or "")[:120],
            "blocker": str(r["current_blocker"] or "")[:120],
        })
    return out


def _collect_candidates(db: Database, client_id: str) -> dict:
    # 必须过滤 status='active' — 排除 self_verify 合并掉的重复实体, 避免幽灵实体参与字典候选评分
    entity_rows = db.fetchall(
        """
        SELECT id, entity_type, display_name, normalized_name, mention_count
        FROM entities
        WHERE client_id = ? AND mention_count >= 2
          AND status = 'active'
        ORDER BY entity_type, mention_count DESC
        """,
        (client_id,),
    )
    entities_by_type: dict[str, list[dict]] = {}
    for r in entity_rows:
        etype = str(r["entity_type"])
        entities_by_type.setdefault(etype, []).append({
            "id": str(r["id"]),
            "name": str(r["display_name"] or ""),
            "mention_count": int(r["mention_count"] or 0),
        })

    atomic_rows = db.fetchall(
        """
        SELECT id, subject_text, attribute, value_text, confidence
        FROM atomic_facts
        WHERE client_id = ? AND status='active' AND confidence >= 0.6
        ORDER BY confidence DESC LIMIT 250
        """,
        (client_id,),
    )
    atomic_by_attr: dict[str, list[dict]] = {}
    for r in atomic_rows:
        attr = str(r["attribute"] or "其他")
        atomic_by_attr.setdefault(attr, []).append({
            "id": str(r["id"]),
            "subject": str(r["subject_text"] or "")[:80],
            "value": str(r["value_text"] or "")[:120],
        })

    # 主动 grep 项目候选 — 避免被 attribute 频度过滤掉核心项目
    project_candidates = _collect_project_candidates(db, client_id)

    # v4 新增 5 个数据源 — 任务与日程模块的人/事/日期
    task_owners = _collect_task_owners(db, client_id)
    task_deadlines = _collect_task_deadlines(db, client_id)
    task_actions = _collect_task_action_types(db, client_id)
    meetings = _collect_meeting_titles(db, client_id)
    event_line_intents = _collect_event_line_intents(db, client_id)

    return {
        "entities_by_type": entities_by_type,
        "atomic_by_attr": atomic_by_attr,
        "project_candidates": project_candidates,
        "task_owners": task_owners,
        "task_deadlines": task_deadlines,
        "task_actions": task_actions,
        "meetings": meetings,
        "event_line_intents": event_line_intents,
    }


def _build_prompt(candidates: dict, client_name: str, *, compact: bool = False) -> str:
    """v2 · 加项目候选段, 强制 LLM 收录测试项目A/测试项目C等核心项目.

    compact=True (实测发现豆包 Seed 2.0 Pro 在 prompt 大 + 输出大 时易超时 7 分钟):
      - 每数据源只取 top 5 (而不是 top 20)
      - 输出目标降到 30-50 term (而不是 80-130)
      - 总 prompt 约 1500-2500 字, 单次 LLM 调用 < 90s
      为新客户/低数据量场景设计的"快速首轮", 后续可手动追加 batches.
    """
    top_entity = 5 if compact else 20
    top_attr = 15 if compact else 30
    top_facts = 1 if compact else 2
    top_deadline = 10 if compact else 30
    top_action = 8 if compact else 20
    top_meeting = 5 if compact else 10
    output_target = "30-50" if compact else "80-130"

    lines = [f"# 客户: {client_name}\n"]

    # ⭐ 项目候选段 (主动 grep 抽出来的, 必须全部收录到字典)
    project_candidates = candidates.get("project_candidates", [])
    if project_candidates:
        max_proj = 15 if compact else len(project_candidates)
        lines.append(f"\n## ⭐ 项目候选 (必须收录, 已 grep {len(project_candidates)} 个, 显示 top {max_proj}):")
        for p in project_candidates[:max_proj]:
            ids = ", ".join(p["support_ids"][:3])
            lines.append(f"  · 项目名: {p['name']} | 支撑 {p['support_count']} 条 | source_ids=[{ids}]")
        if not compact:
            lines.append("  ⚠️ 上述项目即使别处没出现, 也必须每个独立成一个 term (跨别名合并是 OK 的, 但不允许整个砍掉)")

    for etype, items in candidates["entities_by_type"].items():
        lines.append(f"\n## entities · {etype} (top {top_entity}):")
        for e in items[:top_entity]:
            lines.append(f"  {e['id'][:12]}|{e['name']}|{e['mention_count']}")

    lines.append(f"\n## atomic_facts (top {top_attr} attrs, {top_facts} facts/attr):\n")
    sorted_attrs = sorted(candidates["atomic_by_attr"].items(), key=lambda x: -len(x[1]))
    for attr, facts in sorted_attrs[:top_attr]:
        lines.append(f"  [{attr}]")
        for f in facts[:top_facts]:
            lines.append(f"    {f['id'][:12]}|{f['subject'][:25]}={f['value'][:55]}")

    # v4 新增段: 任务与日程候选
    task_owners = candidates.get("task_owners", [])
    if task_owners:
        unique_names: dict[str, dict] = {}
        for o in task_owners:
            n = o["name"]
            if n not in unique_names:
                unique_names[n] = {"name": n, "sources": [], "count": 0}
            unique_names[n]["sources"].append(o["source"])
            unique_names[n]["count"] += o["count"]
        max_owners = 10 if compact else len(unique_names)
        lines.append(f"\n## ⭐ tasks 出现的人名 (category=人物, 显示 top {max_owners}):")
        for n_info in list(unique_names.values())[:max_owners]:
            lines.append(f"  · {n_info['name']} (count={n_info['count']})")

    task_deadlines = candidates.get("task_deadlines", [])
    if task_deadlines:
        lines.append(f"\n## ⭐ tasks 真实 deadline (top {top_deadline}, category=关键节点/数字):")
        for d in task_deadlines[:top_deadline]:
            lines.append(f"  · {d['deadline']} | 「{d['task_title']}」")

    task_actions = candidates.get("task_actions", [])
    if task_actions:
        lines.append(f"\n## ⭐ tasks 动作类型 (top {top_action}):")
        for a in task_actions[:top_action]:
            lines.append(f"  · {a['action']} ({a['count']} 次)")

    meetings = candidates.get("meetings", [])
    if meetings:
        lines.append(f"\n## ⭐ 会议标题 (top {top_meeting}):")
        for m in meetings[:top_meeting]:
            lines.append(f"  · {m['title']}")

    event_line_intents = candidates.get("event_line_intents", [])
    if event_line_intents and not compact:
        lines.append(f"\n## ⭐ event_lines 业务承诺/动作 ({len(event_line_intents)} 条主线):")
        for el in event_line_intents:
            lines.append(f"  · 主线「{el['line_name']}」")
            if el["intent"]:
                lines.append(f"      intent: {el['intent']}")
            if el["next_step"]:
                lines.append(f"      next_step: {el['next_step']}")
            if el["decision"]:
                lines.append(f"      decision: {el['decision']}")

    lines.append(f"\n生成 {output_target} 个 term, 跨别名合并, 标 source_ids")
    return "\n".join(lines)


def generate_glossary_candidates(
    db: Database,
    ai: AiService,
    client_id: str,
    *,
    persist: bool = False,
    compact: bool = False,
    timeout_seconds: float = 420.0,
    max_tokens: int = 10000,
) -> dict[str, Any]:
    """主入口: 收集 + 调 LLM + 返回字典候选.

    persist=False（默认）：仅返回 candidates JSON，不写 db（供 endpoint 让用户看质量）
    persist=True：抽出的 high-confidence terms 直接落库 client_glossary（合并已有 aliases）
                  让 ingest 后台自动建字典，新用户开箱即用
    """
    client_row = db.fetchone(
        "SELECT id, name FROM clients WHERE id = ?",
        (client_id,),
    )
    if not client_row:
        raise ValueError(f"client not found: {client_id}")
    client_name = str(client_row["name"])

    candidates = _collect_candidates(db, client_id)
    total_entities = sum(len(v) for v in candidates["entities_by_type"].values())
    total_atomic = sum(len(v) for v in candidates["atomic_by_attr"].values())
    total_attrs = len(candidates["atomic_by_attr"])

    health = ai.get_health()
    if not health.ready:
        return {
            "status": "ai_not_ready",
            "clientId": client_id,
            "clientName": client_name,
            "candidateStats": {
                "entities": total_entities,
                "atomic_facts": total_atomic,
                "attributes": total_attrs,
            },
            "terms": [],
            "error": health.detail,
        }

    prompt = _build_prompt(candidates, client_name, compact=compact)

    try:
        result = ai._qwen_generate(  # noqa: SLF001
            prompt,
            SYSTEM_PROMPT,
            GLOSSARY_OUTPUT_SCHEMA,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=0.2,
        )
    except AiInvocationError as exc:
        return {
            "status": "llm_failed",
            "clientId": client_id,
            "clientName": client_name,
            "candidateStats": {
                "entities": total_entities,
                "atomic_facts": total_atomic,
                "attributes": total_attrs,
            },
            "terms": [],
            "error": f"{type(exc).__name__}: {getattr(exc, 'detail', str(exc))[:300]}",
        }

    terms_raw = result.get("terms") if isinstance(result, dict) else []
    terms = terms_raw if isinstance(terms_raw, list) else []

    # 按 category 统计
    by_cat: dict[str, int] = {}
    by_conf: dict[str, int] = {}
    needs_clar = 0
    for t in terms:
        if not isinstance(t, dict):
            continue
        cat = str(t.get("category") or "其他")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        conf = str(t.get("confidence") or "?")
        by_conf[conf] = by_conf.get(conf, 0) + 1
        if t.get("needs_clarification"):
            needs_clar += 1

    persisted = 0
    persist_skipped = 0
    if persist and terms:
        # 仅落库 high/medium 信心 + 非 needs_clarification 的，避免噪声 term 污染字典
        import sqlite3 as _sqlite3
        from app.services.glossary_store import create_glossary_entry
        for t in terms:
            if not isinstance(t, dict):
                persist_skipped += 1
                continue
            name = str(t.get("canonical_name") or "").strip()
            if not name or len(name) < 2:
                persist_skipped += 1
                continue
            conf = str(t.get("confidence") or "low").lower()
            if conf not in ("high", "medium"):
                persist_skipped += 1
                continue
            if t.get("needs_clarification"):
                persist_skipped += 1
                continue
            try:
                create_glossary_entry(
                    db.conn,
                    client_id=client_id,
                    term=name,
                    definition=str(t.get("definition") or "")[:1000],
                    aliases=[str(a) for a in (t.get("aliases") or []) if isinstance(a, str)],
                    category=str(t.get("category") or "其他"),
                )
                persisted += 1
            except _sqlite3.IntegrityError:
                # UNIQUE 约束：同客户同名 term 已存在，不覆盖
                persist_skipped += 1
            except Exception:
                persist_skipped += 1
        # 显式 commit — create_glossary_entry 直接用 conn.execute 不自动 commit,
        # 之前 bug: Stage 1 跑完 48 个 term, 进程退出时全部丢失.
        try:
            db.conn.commit()
        except Exception:  # noqa: BLE001
            pass

    return {
        "status": "ok",
        "clientId": client_id,
        "clientName": client_name,
        "candidateStats": {
            "entities": total_entities,
            "atomic_facts": total_atomic,
            "attributes": total_attrs,
            "prompt_chars": len(prompt),
        },
        "termCount": len(terms),
        "byCategory": by_cat,
        "byConfidence": by_conf,
        "needsClarification": needs_clar,
        "persisted": persisted,
        "persistSkipped": persist_skipped,
        "terms": terms,
    }
