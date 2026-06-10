"""下一步「行动闭环」对账中间层(D 指令 M2-M4-M6 核心,客户无关)。

把五源 union 出来的**原始候选行动**清洗成"真正还需要人处理的下一步":

    raw candidates
    → 质量门(挡空/时间碎片/假角色)
    → 主体归一 + 行动方向(我方做/催客户/客户给/双方确认)
    → 语义级去重(挡"换种说法"的重复)
    → 与现有任务反向比对(已进计划的不再当新候选)
    → 分层输出(candidate / possible_duplicate / needs_review / invalid)

设计原则:
- **客户无关**:我方关键词固定(益语/顾源源…,本就是本 app 的组织);客户方名字**动态**从 client.name
  取,不写死测试机构A/张真。
- **纯函数**:不碰 DB、不调 LLM、不改数据;输入原始候选 + 现有任务标题 + 客户名,输出分层结果。
  (DB 读取留在 main.py 端点;这里只做计算,便于单测与 before/after 回归。)
- **只读出侧清洗**:不动 commitments 写入(写入侧质量门是后续 P1)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

# ── 词表 ────────────────────────────────────────────────────────────────
# 我方组织(固定 —— 本 app 属于益语智库,识别"我方"不算写死客户)
_OUR_SIDE = ("我们", "我方", "乙方", "益语", "益语智库", "一语智库", "智库", "顾源源", "顾老师", "陪伴顾问")
# 双方
_BOTH_SIDE = ("双方", "共同", "一起", "联合", "协同", "彼此")
# 通用客户侧/角色词(客户具体名字另从 client.name 动态注入)
_GENERIC_CLIENT = ("客户", "甲方", "机构方", "项目方", "对方")
# 假主体 —— 抽取噪声,这些"角色"不是真人/真组织,直接判无效
_FAKE_ACTORS = frozenset({
    "客户期望", "本次会议", "上次会议", "会议", "事项", "决定", "讨论", "建议",
    "项目", "后续", "下一步", "目标", "计划", "需求", "情况", "内容", "方面",
    "如下", "以下", "其中", "另外", "none", "null", "",
})
# 时间/状态词 —— content 只剩这些 = 没有真实动作
_TIME_STATUS = frozenset({
    "下周", "本周", "上周", "下月", "本月", "近期", "尽快", "后续", "之后", "稍后",
    "待定", "待确认", "下次", "会后", "日前", "月底", "年底", "周一", "周二", "周三",
    "周四", "周五", "下周一", "下周二", "下周三", "下周二前", "下周前", "前", "尽早",
    "马上", "立刻", "随后", "届时", "暂定",
})
# 去重签名时剔除的连接/泛化词(保留区分性名词)
_STOPWORDS = frozenset({
    "完成", "进行", "推进", "落地", "确认", "提供", "组织", "相关", "以及", "并",
    "一份", "一个", "这个", "那个", "工作", "事项", "内容", "方面", "问题", "情况",
    "出具", "撰写", "起草", "发送", "提交", "安排", "明确", "补充", "形成", "整理",
    "以", "及", "等", "的", "了", "对", "与", "和", "或", "在", "为", "把", "向",
    "需", "要", "将", "请", "做", "给", "到", "于", "其", "并且", "同时", "然后",
})
_TIME_RE = re.compile(r"\d{1,4}[-/年月日号]|\d{1,2}:\d{2}|第[一二三四五六七八九十]+")
_ZH_TOKEN_RE = re.compile(r"[一-龥A-Za-z]{2,}")
# 动作动词(content 至少含一个才算"有行动")
_ACTION_VERBS = (
    "完成", "提供", "提交", "起草", "撰写", "输出", "发送", "发", "整理", "安排", "组织",
    "推进", "落地", "确认", "评估", "对接", "搭建", "建立", "制定", "梳理", "补充", "核对",
    "更新", "汇报", "沟通", "跟进", "约", "开", "做", "出具", "设计", "拟", "签", "审", "改",
)


@dataclass
class ReconciledItem:
    fingerprint: str
    kind: str
    actor: str
    text: str
    due_date: str
    severity: str
    raw_id: str
    owner_side: str = "unknown"        # us | client | both | unknown
    action_direction: str = "unknown"  # do | follow_up | wait_for | confirm | unknown
    quality_status: str = "valid"      # valid | needs_review | invalid
    reject_reason: str = ""
    reconciliation_status: str = "new_candidate"  # new_candidate | matched_existing | possible_duplicate | invalid
    matched_task_title: str = ""
    duplicate_of: str = ""             # 同组代表的 fingerprint
    members: list[str] = field(default_factory=list)  # 被合并进来的同组 fingerprint

    def to_item(self) -> dict[str, object]:
        """回前端的 NextStepItem(保持原契约 + 附加字段)。"""
        return {
            "fingerprint": self.fingerprint,
            "kind": self.kind,
            "actor": self.actor,
            "text": self.text,
            "dueDate": self.due_date,
            "severity": self.severity,
            "rawId": self.raw_id,
            "ownerSide": self.owner_side,
            "actionDirection": self.action_direction,
            "mergedCount": len(self.members),
            "matchedTaskTitle": self.matched_task_title,
        }


# ── 质量门 ──────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return (s or "").strip()


def _is_time_or_status_only(text: str) -> bool:
    """content 去掉时间/状态词后是否什么都不剩(=没有真实动作)。"""
    t = _norm(text)
    if not t or t.lower() == "none":
        return True
    stripped = _TIME_RE.sub("", t)
    toks = [x for x in _ZH_TOKEN_RE.findall(stripped) if x not in _TIME_STATUS]
    return len(toks) == 0


def _has_action_verb(text: str) -> bool:
    return any(v in text for v in _ACTION_VERBS)


def quality_gate(actor: str, text: str, raw_id: str) -> tuple[str, str]:
    """返回 (quality_status, reject_reason)。invalid 不进任何列表。"""
    a, t = _norm(actor), _norm(text)
    if (not a or a.lower() == "none") and (not t or t.lower() == "none"):
        return "invalid", "空角色+空内容"
    if not t or t.lower() == "none":
        return "invalid", "空内容"
    if len(t) < 4:
        return "invalid", "内容过短"
    if _is_time_or_status_only(t):
        return "invalid", "只有时间/状态词,无动作"
    if a in _FAKE_ACTORS or a.lower() in _FAKE_ACTORS:
        return "invalid", f"假主体({a})"
    if t == a:
        return "invalid", "内容与角色相同"
    if not _has_action_verb(t):
        return "needs_review", "未识别到动作动词"
    return "valid", ""


# ── 主体归一 + 方向 ────────────────────────────────────────────────────

# ★ ER v4 (5/28): 三档 lookup 优先级
#   Tier 2.A 人工金标 verified_canonical → 永远不被算法覆盖, 最高权重
#   Tier 2.B 人工金标 verified_noise     → 直接 return 'noise' (ASR 错误)
#   Tier 1   算法集中度 (entities.mention_count + client 分布)
#   Tier 0   字符串匹配 client_name (旧逻辑兜底)
def resolve_actor_side(name: str, client_id: str | None, db: Any | None) -> str | None:
    """ER v4: 查 entities 表用人工金标 + 频次集中度判 side.

    返回 'us' / 'client' / 'third_party' / 'noise' / None (没命中, 调用方 fallback).
    """
    if not name or not client_id or not db:
        return None
    n = name.strip()
    if not n:
        return None

    # 剥常见后缀(老师/工/总/秘书长 等)
    stripped = re.sub(r'(老师|秘书长|总监|主任|经理|总裁|工程师|工)$', '', n).strip()

    try:
        # Tier 2.A: 人工金标 verified_canonical (最高权重)
        rows = db.fetchall(
            """SELECT client_id, attributes_json
               FROM entities
               WHERE entity_type='person' AND verified_status='verified_canonical'
               AND (display_name=? OR display_name=? OR aliases_json LIKE ? OR aliases_json LIKE ?)""",
            (n, stripped, f'%"{n}"%', f'%"{stripped}"%'),
        )
        if rows:
            r0 = rows[0]
            row_cid = str(r0["client_id"])
            if row_cid == client_id:
                return "client"
            return "third_party"

        # Tier 2.B: 人工金标 verified_noise (ASR 错误等)
        noise_row = db.fetchone(
            """SELECT 1 FROM entities
               WHERE entity_type='person' AND verified_status='verified_noise'
               AND (display_name=? OR display_name=? OR aliases_json LIKE ? OR aliases_json LIKE ?)
               LIMIT 1""",
            (n, stripped, f'%"{n}"%', f'%"{stripped}"%'),
        )
        if noise_row:
            return "noise"

        # Tier 1: 算法集中度
        if len(stripped) < 2:
            return None
        active_rows = db.fetchall(
            """SELECT client_id, COALESCE(mention_count, 0) AS mc
               FROM entities
               WHERE entity_type='person' AND status='active'
               AND (display_name=? OR display_name LIKE ? OR aliases_json LIKE ?)""",
            (n, f'%{stripped}%', f'%"{stripped}"%'),
        )
        if not active_rows:
            return None

        by_client: dict[str, int] = {}
        for r in active_rows:
            c = str(r["client_id"] or "")
            by_client[c] = by_client.get(c, 0) + int(r["mc"] or 0)
        total = sum(by_client.values())
        if total < 3:
            return None

        max_client_id = max(by_client, key=lambda c: by_client[c])
        max_count = by_client[max_client_id]
        concentration = max_count / total if total > 0 else 0.0
        cross_count = len([c for c, v in by_client.items() if v >= 1])

        if cross_count >= 3 and concentration < 0.5:
            return "us"
        if max_client_id == client_id and concentration >= 0.6 and max_count >= 5:
            return "client"
        if max_client_id != client_id and concentration >= 0.7:
            return "third_party"
        return None
    except Exception:
        return None


def _side_of(name: str, client_name_tokens: frozenset[str],
             client_id: str | None = None, db: Any | None = None) -> str:
    # ★ ER v4: 优先 entities 查询 (Tier 2 + Tier 1)
    er_result = resolve_actor_side(name, client_id, db)
    if er_result is not None:
        return er_result
    # ── 旧字符串匹配(Tier 0 兜底) ──
    n = _norm(name)
    if not n:
        return "unknown"
    if any(k in n for k in _OUR_SIDE):
        return "us"
    if any(k in n for k in _BOTH_SIDE):
        return "both"
    if any(tok and tok in n for tok in client_name_tokens):
        return "client"
    if any(k in n for k in _GENERIC_CLIENT):
        return "client"
    return "unknown"


def classify_direction(actor: str, text: str, client_name_tokens: frozenset[str],
                       client_id: str | None = None, db: Any | None = None) -> tuple[str, str]:
    """从 'X 向 Y: 内容' 或 actor=committer 推断 owner_side + action_direction。

    ★ ER v4 (5/28): 加 optional client_id + db, 让 _side_of 走 entities verified + 集中度。
    """
    committer, recipient = actor, ""
    m = re.match(r"^(.+?)\s*[向→\-]+\s*(.+?)[:：]", text)
    if m:
        committer, recipient = m.group(1), m.group(2)
    cs = _side_of(committer, client_name_tokens, client_id, db)
    rs = _side_of(recipient, client_name_tokens, client_id, db) if recipient else "unknown"
    # ★ ER v4: noise = ASR 错误, 不应出现在 next-steps
    if cs == "noise" or rs == "noise":
        return "noise", "ignore"
    if "双方" in actor or "双方" in text or cs == "both":
        return "both", "confirm"
    if cs == "us":
        return "us", "do"
    if cs == "client":
        return "client", "wait_for" if rs == "us" else "follow_up"
    if cs == "third_party":
        return "third_party", "follow_up"
    return "unknown", "unknown"


# ── 语义级去重 ──────────────────────────────────────────────────────────
def action_signature(text: str, client_name_tokens: frozenset[str]) -> frozenset[str]:
    """中文无空格,用**字符 bigram**做相似度签名(中文短文本去重标准做法)。
    先去掉 'X 向 Y:' 前缀 + 时间词 + 我方/客户方/通用角色/时间状态词,再取相邻 2 字 shingle。"""
    body = text
    m = re.match(r"^.+?[:：](.+)$", text)  # 去掉 "X 向 Y:" 前缀
    if m:
        body = m.group(1)
    body = _TIME_RE.sub("", body)
    # 去掉组织/角色/时间状态词(子串移除),避免它们贡献共享 bigram 造成误并
    for w in (*_OUR_SIDE, *_GENERIC_CLIENT, *_TIME_STATUS, *client_name_tokens):
        if w:
            body = body.replace(w, "")
    chars = "".join(re.findall(r"[一-龥A-Za-z0-9]", body))
    if len(chars) < 2:
        return frozenset()
    return frozenset(chars[i:i + 2] for i in range(len(chars) - 1))


def _same_action(a: frozenset[str], b: frozenset[str]) -> bool:
    """bigram 集合:Jaccard≥0.45 或 重叠系数(交/较小集)≥0.6 判为同一行动。
    重叠系数处理"一个是另一个的改写/子集"(短句基本被长句包含)。"""
    if not a or not b:
        return False
    inter = len(a & b)
    if inter < 2:
        return False
    jac = inter / len(a | b)
    overlap = inter / min(len(a), len(b))
    return jac >= 0.45 or overlap >= 0.6


def _pick_representative(group: list[ReconciledItem]) -> ReconciledItem:
    """同组里挑代表:优先 有dueDate > 我方主体明确 > 文本更长更具体。"""
    def score(it: ReconciledItem) -> tuple:
        return (1 if it.due_date else 0, 1 if it.owner_side != "unknown" else 0, len(it.text))
    return max(group, key=score)


# ── 主流程 ──────────────────────────────────────────────────────────────
def reconcile(
    raw_candidates: list[dict],
    *,
    existing_task_titles: Iterable[str],
    client_name: str,
    medium_candidates: list[dict] | None = None,
    client_id: str | None = None,  # ★ ER v4 (5/28): 传 client_id 让 classify_direction 走 entities 查询
    db: Any | None = None,         # ★ ER v4: 传 db 让 _side_of 查 entities verified + 集中度
) -> dict[str, object]:
    """输入原始候选(dict: fingerprint/kind/actor/text/dueDate/severity/rawId),输出分层结果。

    medium_candidates: 会议抽取的 medium 项,单独走 needs_review(且仍过质量门挡碎片角色)。

    ★ ER v4 (5/28): 可选传 client_id + db, classify_direction 会走 entities 表
       优先级: 人工金标 > 频次集中度 > 字符串匹配兜底。
       不传时退回纯字符串模式(向后兼容)。
    """
    client_tokens = frozenset(t for t in _ZH_TOKEN_RE.findall(client_name or "") if t not in _GENERIC_CLIENT)

    # 1) 质量门 + 主体方向
    valid: list[ReconciledItem] = []
    invalid_count = 0
    noise_count = 0  # ★ ER v4: 标记被人工/算法判定为 ASR 错误的, 不进入 next-steps
    needs_review: list[ReconciledItem] = []
    for c in raw_candidates:
        actor, text = str(c.get("actor") or ""), str(c.get("text") or "")
        status, reason = quality_gate(actor, text, str(c.get("rawId") or ""))
        owner_side, direction = classify_direction(actor, text, client_tokens, client_id, db)
        # ★ ER v4: noise = 人工已标 verified_noise (ASR 错误), 直接过滤不走 needs_review
        if owner_side == "noise":
            noise_count += 1
            continue
        item = ReconciledItem(
            fingerprint=str(c.get("fingerprint") or ""), kind=str(c.get("kind") or ""),
            actor=actor, text=text, due_date=str(c.get("dueDate") or ""),
            severity=str(c.get("severity") or "medium"), raw_id=str(c.get("rawId") or ""),
            owner_side=owner_side, action_direction=direction,
            quality_status=status, reject_reason=reason,
        )
        if status == "invalid":
            invalid_count += 1
            continue
        if status == "needs_review":
            item.reconciliation_status = "new_candidate"
            needs_review.append(item)
            continue
        valid.append(item)

    # 2) 语义级去重(同组合并,代表留下,其余记 possible_duplicate)
    sigs = [action_signature(it.text, client_tokens) for it in valid]
    used = [False] * len(valid)
    representatives: list[ReconciledItem] = []
    possible_duplicates: list[ReconciledItem] = []
    for i in range(len(valid)):
        if used[i]:
            continue
        group = [valid[i]]
        used[i] = True
        for j in range(i + 1, len(valid)):
            if used[j]:
                continue
            if _same_action(sigs[i], sigs[j]):
                group.append(valid[j])
                used[j] = True
        rep = _pick_representative(group)
        rep.members = [g.fingerprint for g in group if g.fingerprint != rep.fingerprint]
        representatives.append(rep)
        for g in group:
            if g is not rep:
                g.reconciliation_status = "possible_duplicate"
                g.duplicate_of = rep.fingerprint
                possible_duplicates.append(g)

    # 3) 与现有任务反向比对(已进计划的不当新候选)
    task_sigs = [action_signature(str(t or ""), client_tokens) for t in existing_task_titles]
    task_titles = list(existing_task_titles)
    candidates: list[ReconciledItem] = []
    matched_existing = 0
    for rep in representatives:
        sig = action_signature(rep.text, client_tokens)
        hit = ""
        for k, tsig in enumerate(task_sigs):
            if _same_action(sig, tsig):
                hit = str(task_titles[k])
                break
        if hit:
            rep.reconciliation_status = "matched_existing"
            rep.matched_task_title = hit
            matched_existing += 1
        else:
            rep.reconciliation_status = "new_candidate"
            candidates.append(rep)

    # 4) medium → needs_review(仍过质量门挡碎片角色)
    for c in (medium_candidates or []):
        actor, text = str(c.get("actor") or ""), str(c.get("text") or "")
        status, reason = quality_gate(actor, text, str(c.get("rawId") or ""))
        if status == "invalid":
            invalid_count += 1
            continue
        owner_side, direction = classify_direction(actor, text, client_tokens)
        needs_review.append(ReconciledItem(
            fingerprint=str(c.get("fingerprint") or ""), kind="meeting", actor=actor, text=text,
            due_date="", severity="low", raw_id="", owner_side=owner_side,
            action_direction=direction, quality_status="needs_review",
            reject_reason="medium 会议待办,待人确认", reconciliation_status="new_candidate",
        ))

    # 排序:有 dueDate > severity > 我方做优先
    sev = {"high": 0, "medium": 1, "low": 2}
    dir_rank = {"do": 0, "confirm": 1, "follow_up": 2, "wait_for": 3, "unknown": 4}
    candidates.sort(key=lambda x: (0 if x.due_date else 1, sev.get(x.severity, 9), dir_rank.get(x.action_direction, 9)))

    return {
        "candidate_next_steps": [c.to_item() for c in candidates],
        "possible_duplicates": [d.to_item() for d in possible_duplicates],
        "needs_review": [n.to_item() for n in needs_review],
        "matched_existing_count": matched_existing,
        "invalid_filtered_count": invalid_count,
        "debug_summary": {
            "raw_candidates": len(raw_candidates),
            "valid_candidates": len(valid),
            "invalid_filtered": invalid_count,
            "noise_filtered": noise_count,
            "representatives": len(representatives),
            "possible_duplicates": len(possible_duplicates),
            "matched_existing": matched_existing,
            "new_candidates": len(candidates),
            "needs_review": len(needs_review),
        },
    }


__all__ = ["reconcile", "quality_gate", "classify_direction", "action_signature", "ReconciledItem"]
