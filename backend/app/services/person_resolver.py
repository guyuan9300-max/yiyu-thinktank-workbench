"""meeting-spine Phase0: 人物身份解析。

把会议纪要抽到的"说话人 / 负责人"文本名, 解析成稳定身份并锚定到本地
entities(person) 行(身份从 entity 行透出, 一处真相):
  - 益语员工  → 命中 mirror_users  → resolved_kind='internal', mirror_user_id
  - 客户方人物 → 命中 cloud_external_persons → resolved_kind='client', external_person_id
                (客户方花名册需本地镜像, 留作 Phase0.b; 当前未镜像则保持 unknown)
  - 其余      → resolved_kind='unknown'

atomic_facts.speaker_entity_id 只指向本地 entities 行。

复用现有 ER: 优先 FIND 已存在的 person 实体(精确归一 → 模糊相似度), 找不到才创建,
避免与 entity_extractor 抽取侧重复造实体或灌高 mention_count。
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from app.services.entity_merger import _score_pair

logger = logging.getLogger(__name__)

# 匹配 mirror_users 时, 容忍的中文称谓后缀(只用于匹配 key, 不改写存储名)
_TITLE_SUFFIXES = (
    "老师", "校长", "院长", "部长", "秘书长", "董事长", "总监", "总经理",
    "经理", "主任", "主管", "总", "先生", "女士", "同学", "博士", "教授",
)

# 益语员工模糊匹配阈值(高门槛, 避免把客户方人误判成内部员工)
_INTERNAL_MATCH_THRESHOLD = 0.85
# 复用已有 person 实体的模糊阈值
_ENTITY_REUSE_THRESHOLD = 0.85


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_name(name: str) -> str:
    return " ".join(str(name or "").split()).strip()


def _match_key(name: str) -> str:
    """去掉一个尾部称谓后缀做匹配 key(不改写存储名)。"""
    key = _normalize_name(name)
    for suffix in _TITLE_SUFFIXES:
        if len(key) > len(suffix) and key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def match_mirror_user(conn: sqlite3.Connection, name: str) -> str | None:
    """文本名 → mirror_users.id(益语员工)。精确归一优先, 再高门槛模糊。"""
    key = _match_key(name)
    if not key:
        return None
    try:
        rows = conn.execute(
            "SELECT id, full_name FROM mirror_users WHERE full_name IS NOT NULL AND full_name <> ''"
        ).fetchall()
    except sqlite3.Error:
        return None
    best_id: str | None = None
    best_sim = 0.0
    for row in rows:
        full = _normalize_name(str(row["full_name"]))
        if not full:
            continue
        full_key = _match_key(full)
        if full_key == key or full == key:
            return str(row["id"])
        sim, _reason = _score_pair(full_key, key)
        if sim > best_sim:
            best_sim, best_id = sim, str(row["id"])
    if best_id is not None and best_sim >= _INTERNAL_MATCH_THRESHOLD:
        return best_id
    return None


def _find_person_entity(conn: sqlite3.Connection, client_id: str, name: str) -> str | None:
    """在该客户的 person 实体里找匹配的(精确归一 → 模糊), 返回 entity_id 或 None。"""
    norm = _normalize_name(name)
    if not norm:
        return None
    row = conn.execute(
        "SELECT id FROM entities WHERE client_id = ? AND entity_type = 'person' AND normalized_name = ?",
        (client_id, norm),
    ).fetchone()
    if row is not None:
        return str(row["id"])
    key = _match_key(norm)
    best_id: str | None = None
    best_sim = 0.0
    for cand in conn.execute(
        "SELECT id, normalized_name FROM entities WHERE client_id = ? AND entity_type = 'person' AND status = 'active'",
        (client_id,),
    ).fetchall():
        cand_key = _match_key(str(cand["normalized_name"]))
        sim, _r = _score_pair(cand_key, key)
        if sim > best_sim:
            best_sim, best_id = sim, str(cand["id"])
    if best_id is not None and best_sim >= _ENTITY_REUSE_THRESHOLD:
        return best_id
    return None


def _create_person_entity(conn: sqlite3.Connection, client_id: str, name: str, now: str) -> str:
    norm = _normalize_name(name)
    entity_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO entities (id, client_id, entity_type, normalized_name, display_name, "
        "aliases_json, attributes_json, mention_count, confidence, first_seen_at, last_seen_at, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'person', ?, ?, ?, '{}', 0, 0.5, ?, ?, 'active', ?, ?)",
        (
            entity_id,
            client_id,
            norm,
            norm,
            f'["{norm}"]',
            now,
            now,
            now,
            now,
        ),
    )
    return entity_id


def resolve_person_name(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    name: str,
    now: str | None = None,
) -> str | None:
    """把人名文本解析成稳定的本地 entities(person) id, 并回填身份锚点。

    幂等; 不会下调已人工标 verified_noise 的实体。返回 entity_id, 名字为空返回 None。
    """
    norm = _normalize_name(name)
    if not norm:
        return None
    timestamp = now or _now_iso()

    entity_id = _find_person_entity(conn, client_id, norm)
    if entity_id is None:
        entity_id = _create_person_entity(conn, client_id, norm, timestamp)

    # 已人工判噪的实体不改其身份归类
    verified = conn.execute(
        "SELECT verified_status FROM entities WHERE id = ?", (entity_id,)
    ).fetchone()
    if verified is not None and str(verified["verified_status"]) == "verified_noise":
        return entity_id

    mirror_user_id = match_mirror_user(conn, norm)
    if mirror_user_id:
        conn.execute(
            "UPDATE entities SET resolved_kind = 'internal', mirror_user_id = ?, updated_at = ? "
            "WHERE id = ? AND verified_status <> 'verified_noise'",
            (mirror_user_id, timestamp, entity_id),
        )
    # 客户方花名册(cloud_external_persons)本地镜像就绪后, 在此补 'client' 分支(Phase0.b)。
    return entity_id


def build_client_roster_hint(
    conn: sqlite3.Connection,
    client_id: str,
    *,
    max_employees: int = 30,
    max_persons: int = 20,
) -> str:
    """组织员工 + 该客户已知人物名册, 注入抽取 prompt。

    目的: 让 LLM 把 owner / speaker / 承诺人尽量对齐到已知人名的规范写法,
    提高 owner 解析率与说话人归属准确度(meeting-spine Phase1 ③)。
    拿不准时保留原文名, 不编造。无名册返回空串(prompt 不加该段)。
    """
    lines: list[str] = []
    try:
        rows = conn.execute(
            "SELECT full_name, primary_role FROM mirror_users "
            "WHERE full_name IS NOT NULL AND full_name <> '' ORDER BY full_name"
        ).fetchall()
    except sqlite3.OperationalError:
        try:
            rows = conn.execute(
                "SELECT full_name FROM mirror_users "
                "WHERE full_name IS NOT NULL AND full_name <> '' ORDER BY full_name"
            ).fetchall()
        except sqlite3.Error:
            rows = []
    except sqlite3.Error:
        rows = []
    if rows:
        names = []
        for r in rows[:max_employees]:
            full = str(r["full_name"]).strip()
            role = str(r["primary_role"]).strip() if "primary_role" in r.keys() and r["primary_role"] else ""
            names.append(f"{full}({role})" if role else full)
        lines.append("益语团队成员: " + "、".join(names))

    try:
        persons = conn.execute(
            "SELECT display_name FROM entities "
            "WHERE client_id = ? AND entity_type = 'person' AND status = 'active' "
            "ORDER BY mention_count DESC LIMIT ?",
            (client_id, int(max_persons)),
        ).fetchall()
    except sqlite3.Error:
        persons = []
    known = [str(r["display_name"]).strip() for r in persons if str(r["display_name"] or "").strip()]
    if known:
        lines.append("该客户已知人物: " + "、".join(known))

    if not lines:
        return ""
    return (
        "# 已知相关人物名册\n"
        "把 owner / speaker_person_id / 承诺人(committer/recipient) 尽量对齐到下列人名的规范写法;\n"
        "拿不准就保留原文名, 不要编造名册里没有的人:\n"
        + "\n".join(f"- {line}" for line in lines)
    )


def backfill_speaker_entity_ids(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    limit: int | None = None,
) -> int:
    """把该客户 atomic_facts 里有 speaker_person_id 文本、却无 speaker_entity_id 的行,
    解析并回填 speaker_entity_id。返回回填条数。非阻塞调用方应自行 try/except。"""
    sql = (
        "SELECT id, speaker_person_id FROM atomic_facts "
        "WHERE client_id = ? AND speaker_person_id IS NOT NULL AND speaker_person_id <> '' "
        "AND (speaker_entity_id IS NULL OR speaker_entity_id = '')"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql, (client_id,)).fetchall()
    now = _now_iso()
    count = 0
    for row in rows:
        entity_id = resolve_person_name(
            conn, client_id=client_id, name=str(row["speaker_person_id"]), now=now
        )
        if entity_id:
            conn.execute(
                "UPDATE atomic_facts SET speaker_entity_id = ? WHERE id = ?",
                (entity_id, str(row["id"])),
            )
            count += 1
    return count
