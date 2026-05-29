"""会议纪要全量待办抽取 (regex, 不调 LLM).

战略陪伴 narrative.next_steps 受 LLM 输出长度限制, 会舍取一些会议待办.
本模块从最近的 v2_documents 文本里直接抽出 "@人名"行 + "X 将/会/需 Y" 句式,
作为 next_steps 的补充清单 (前端折叠区块显示).

抽取规则 (按置信度从高到低):
  P0 · @标注: 行尾含 "@张真" "@用户甲" 等 → 高置信
  P1 · 将/会/需: "用户甲将牵头...", "张真需在7月..." → 中置信
  P2 · 承诺动词: "牵头XX/负责XX/承诺XX" → 中置信

消费机制 (用户素材标记方案):
  每条建议算出 fingerprint = sha1(actor + suggestion_text[:50])
  用户点 → 转任务 / ✓ 完成 / ✗ 删除 时, 把 fingerprint 写入 narrative_suggestion_log
  下次抽取时跳过日志里已存在的 fingerprint, 避免重复出现

只取最近 30 天 ingest 的文档, 默认 client_id 过滤.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class MeetingActionItem:
    actor: str               # "用户甲" / "张真,严斌" (多人逗号分隔)
    text: str                # 待办描述, 去掉 @标注的纯文本
    confidence: str          # "high" / "medium"
    source_doc_title: str
    source_doc_id: str
    source_chunk_index: int
    imported_at: str

    @property
    def fingerprint(self) -> str:
        """跨 regen 唯一指纹 — 用户对此操作过即记入日志, 下次不再抽."""
        raw = f"{self.actor.strip()}|{self.text.strip()[:50]}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "text": self.text,
            "confidence": self.confidence,
            "sourceDocTitle": self.source_doc_title,
            "sourceDocId": self.source_doc_id,
            "sourceChunkIndex": self.source_chunk_index,
            "importedAt": self.imported_at,
            "fingerprint": self.fingerprint,
        }


def make_fingerprint(actor: str, text: str) -> str:
    """统一指纹算法 (供 endpoint 写日志时复用)."""
    raw = f"{(actor or '').strip()}|{(text or '').strip()[:50]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# P0: 行末有 @人名 (一个或多个), 前面是动作描述
# 例: "撰写价值观调研问题,并组织核心团队进行线上/线下讨论。 @用户甲"
# 例: "安排品牌与设计人员对接用户甲,启动品牌更新工作。 @张真 @严斌"
_AT_LINE_RE = re.compile(
    r"([^\n@]{6,200}?)[。.\s]\s*(@[一-龥A-Za-z][一-龥A-Za-z0-9_]{1,15}(?:\s*@[一-龥A-Za-z][一-龥A-Za-z0-9_]{1,15})*)"
)

# P1: "X 将/需/牵头 Y" — X 必须是真实人名, Y 是动作短语
# 排除 "会" 作 verb (太多歧义如 "本次会议/明天开会"), 也不允许 actor 是会议/章节代词等
# 例: "用户甲将牵头在6月底前完成存量素材评估" ✓
# 例: "张真需在7月份完成..." ✓
# 例: "本次会议确立..." ✗ (actor='本次', 黑名单)
_FUTURE_VERB_RE = re.compile(
    r"([一-龥]{2,4}(?:老师|工)?)(将牵头|将完成|将启动|将撰写|将协助|将接任|将作为|需在|需要在|牵头|负责|带头)([^。\n]{6,180})"
)

# actor 黑名单 — 这些词跟 "将" 连用也不是待办
_ACTOR_BLACKLIST = frozenset({
    "本次", "上次", "下次", "最后", "首先", "最初", "今天", "明天",
    "会议", "决定", "考虑", "建议", "评估", "讨论", "我们", "他们", "大家",
    "所有", "全部", "上述", "下述", "若干", "一些", "如何", "什么",
    "如下", "包括", "其中", "另外", "同时", "随后", "之后", "之前",
    "管理", "实施", "建立", "搭建", "数据", "看板", "工作坊",
    "即使", "比如", "比如说", "当前", "现在", "现在主要", "压到", "压到具体",
    "产品", "运营", "合规", "技术", "市场", "财务", "少数", "多数",
    "专职", "兼职", "机构", "组织", "公司", "团队", "项目",
})

# 机构/角色后缀黑名单 — actor 含这些后缀就不是真人
_INSTITUTION_SUFFIX = ("公益", "基金会", "协会", "学院", "项目", "中心", "集团", "公司", "工作坊", "看板", "策略", "机制")


def _clean_actor(at_segment: str) -> str:
    """从 '@用户甲 @张真 @严斌' 提取 '用户甲,张真,严斌', 过滤机构名/章节代词."""
    names = re.findall(r"@([一-龥A-Za-z][一-龥A-Za-z0-9_]{1,15})", at_segment)
    keep: list[str] = []
    for n in names:
        if n in _ACTOR_BLACKLIST:
            continue
        if any(n.endswith(suf) for suf in _INSTITUTION_SUFFIX):
            continue
        keep.append(n)
    return ",".join(dict.fromkeys(keep))


def _looks_meaningful(text: str) -> bool:
    """过滤太短/太碎的句子."""
    t = text.strip()
    if len(t) < 6:
        return False
    # 全是标点 / 全是数字
    if re.fullmatch(r"[\d\s，。、;:.\-—]+", t):
        return False
    return True


def extract_from_chunk(
    chunk_text: str,
    *,
    source_doc_title: str,
    source_doc_id: str,
    source_chunk_index: int,
    imported_at: str,
) -> list[MeetingActionItem]:
    """从一个 chunk 抽全量待办. 不调 LLM."""
    if not chunk_text:
        return []
    out: list[MeetingActionItem] = []
    seen_keys: set[str] = set()

    # P0: @标注 (高置信)
    for m in _AT_LINE_RE.finditer(chunk_text):
        action = m.group(1).strip().lstrip("，,。\\-—•·*")
        at_seg = m.group(2)
        actor = _clean_actor(at_seg)
        if not _looks_meaningful(action) or not actor:
            continue
        key = f"{actor}|{action[:30]}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        out.append(MeetingActionItem(
            actor=actor,
            text=action,
            confidence="high",
            source_doc_title=source_doc_title,
            source_doc_id=source_doc_id,
            source_chunk_index=source_chunk_index,
            imported_at=imported_at,
        ))

    # P1: X 将/需/牵头 Y (中置信)
    for m in _FUTURE_VERB_RE.finditer(chunk_text):
        actor = m.group(1).strip()
        if actor in _ACTOR_BLACKLIST:
            continue
        verb = m.group(2)
        rest = m.group(3).strip().lstrip("，,。\\-—•·*")
        full_action = f"{verb}{rest}"
        if not _looks_meaningful(rest):
            continue
        key = f"{actor}|{rest[:30]}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        out.append(MeetingActionItem(
            actor=actor,
            text=full_action,
            confidence="medium",
            source_doc_title=source_doc_title,
            source_doc_id=source_doc_id,
            source_chunk_index=source_chunk_index,
            imported_at=imported_at,
        ))

    return out


def _load_consumed_fingerprints(db: sqlite3.Connection, client_id: str) -> set[str]:
    """读 narrative_suggestion_log 里所有该客户已操作过的 fingerprint."""
    try:
        rows = db.execute(
            "SELECT DISTINCT fingerprint FROM narrative_suggestion_log WHERE client_id = ?",
            (client_id,),
        ).fetchall()
        return {str(r["fingerprint"]) for r in rows if r["fingerprint"]}
    except sqlite3.Error:
        return set()


def extract_recent_client_actions(
    db: sqlite3.Connection,
    client_id: str,
    *,
    days: int = 30,
    max_items: int = 40,
    exclude_consumed: bool = True,
) -> list[MeetingActionItem]:
    """抽取该客户最近 N 天导入的 v2_documents 的全量待办.

    优先选会议纪要类标题 (含 '纪要/对齐会/会议/讨论会'), 其次 imported_at DESC.
    返回按 (confidence DESC, importedAt DESC) 排序的 list.

    exclude_consumed: 默认 True — 自动跳过 narrative_suggestion_log 已有的 fingerprint
                     (用户已点 → / 完成 / 删除过的建议不再出现)
    """
    consumed = _load_consumed_fingerprints(db, client_id) if exclude_consumed else set()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.execute(
        """
        SELECT vc.content, vc.chunk_index, vd.id AS doc_id,
               d.title AS doc_title,
               COALESCE(vd.imported_at, vd.updated_at, '') AS imported_at
        FROM v2_chunks vc
        JOIN v2_documents vd ON vd.id = vc.v2_document_id
        JOIN documents d ON d.id = vd.document_id
        WHERE vd.client_id = ?
          AND COALESCE(vd.imported_at, vd.updated_at, '') >= ?
        ORDER BY
            CASE WHEN d.title LIKE '%纪要%' OR d.title LIKE '%对齐会%' OR d.title LIKE '%会议%' OR d.title LIKE '%讨论会%' THEN 0 ELSE 1 END,
            COALESCE(vd.imported_at, vd.updated_at, '') DESC,
            vc.chunk_index ASC
        """,
        (client_id, cutoff),
    ).fetchall()

    items: list[MeetingActionItem] = []
    for r in rows:
        items.extend(extract_from_chunk(
            str(r["content"] or ""),
            source_doc_title=str(r["doc_title"] or ""),
            source_doc_id=str(r["doc_id"] or ""),
            source_chunk_index=int(r["chunk_index"] or 0),
            imported_at=str(r["imported_at"] or ""),
        ))
        if len(items) >= max_items * 3:  # 提前停止, 后面排序裁剪
            break

    # 跨 chunk 去重: 同 actor + 内容前 30 字 + 已消费过的整体跳过
    final: list[MeetingActionItem] = []
    final_keys: set[str] = set()
    items.sort(key=lambda x: (0 if x.confidence == "high" else 1, -len(x.imported_at), -len(x.text)))
    for it in items:
        if it.fingerprint in consumed:
            continue  # 用户已操作过, 不再呈现
        key = f"{it.actor}|{it.text[:30]}"
        if key in final_keys:
            continue
        final_keys.add(key)
        final.append(it)
        if len(final) >= max_items:
            break
    return final


__all__ = [
    "MeetingActionItem", "extract_from_chunk", "extract_recent_client_actions",
    "make_fingerprint", "_load_consumed_fingerprints",
]
