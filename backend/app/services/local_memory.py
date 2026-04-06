"""
Local project memory system — file-based memory for AI context.

Structure:
    {data_dir}/memory/
    ├── org_memory.md                   # Organization-level memory index
    ├── projects/
    │   ├── {client_id}/
    │   │   ├── project_memory.md       # Project-level memory (key insights, decisions, risks)
    │   │   └── event_lines/
    │   │       └── {eline_id}.md       # Event line memory (timeline, blockers, decisions)
    │   └── ...
    └── weekly/
        └── 2026-W14.md                # Weekly snapshot

Each .md file has YAML frontmatter with metadata for future cloud sync.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


# ── Directory helpers ──

def memory_root(data_dir: str | Path) -> Path:
    root = Path(data_dir) / "memory"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_memory_dir(data_dir: str | Path, client_id: str) -> Path:
    d = memory_root(data_dir) / "projects" / client_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def event_line_memory_dir(data_dir: str | Path, client_id: str) -> Path:
    d = project_memory_dir(data_dir, client_id) / "event_lines"
    d.mkdir(parents=True, exist_ok=True)
    return d


def weekly_memory_dir(data_dir: str | Path) -> Path:
    d = memory_root(data_dir) / "weekly"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Read / Write helpers ──

def read_memory_file(path: Path) -> str:
    """Read a memory .md file. Returns empty string if not exists."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def write_memory_file(path: Path, content: str) -> None:
    """Write a memory .md file with sync metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _frontmatter(metadata: dict[str, Any]) -> str:
    """Generate YAML frontmatter."""
    lines = ["---"]
    for k, v in metadata.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


# ── Project Memory ──

def read_project_memory(data_dir: str | Path, client_id: str) -> str:
    path = project_memory_dir(data_dir, client_id) / "project_memory.md"
    return read_memory_file(path)


def write_project_memory(
    data_dir: str | Path,
    client_id: str,
    client_name: str,
    content: str,
) -> Path:
    path = project_memory_dir(data_dir, client_id) / "project_memory.md"
    full = _frontmatter({
        "project": client_name,
        "client_id": client_id,
        "updated": _now_iso(),
        "syncedAt": "",  # Reserved for cloud sync
    }) + "\n\n" + content
    write_memory_file(path, full)
    logger.info("[local-memory] wrote project_memory for %s (%d chars)", client_name, len(content))
    try:
        update_memory_index(data_dir)
        record_memory_operation(data_dir)
    except Exception:
        pass
    return path


# ── Event Line Memory ──

def read_event_line_memory(data_dir: str | Path, client_id: str, eline_id: str) -> str:
    path = event_line_memory_dir(data_dir, client_id) / f"{eline_id}.md"
    return read_memory_file(path)


def write_event_line_memory(
    data_dir: str | Path,
    client_id: str,
    eline_id: str,
    eline_name: str,
    client_name: str,
    content: str,
) -> Path:
    path = event_line_memory_dir(data_dir, client_id) / f"{eline_id}.md"
    full = _frontmatter({
        "event_line": eline_name,
        "event_line_id": eline_id,
        "project": client_name,
        "client_id": client_id,
        "updated": _now_iso(),
        "syncedAt": "",
    }) + "\n\n" + content
    write_memory_file(path, full)
    logger.info("[local-memory] wrote event_line memory for %s/%s (%d chars)", client_name, eline_name, len(content))
    try:
        update_memory_index(data_dir)
        record_memory_operation(data_dir)
    except Exception:
        pass
    return path


# ── Weekly Snapshot ──

def read_weekly_memory(data_dir: str | Path, week_label: str) -> str:
    path = weekly_memory_dir(data_dir) / f"{week_label}.md"
    return read_memory_file(path)


def write_weekly_memory(
    data_dir: str | Path,
    week_label: str,
    content: str,
) -> Path:
    path = weekly_memory_dir(data_dir) / f"{week_label}.md"
    full = _frontmatter({
        "week": week_label,
        "updated": _now_iso(),
        "syncedAt": "",
    }) + "\n\n" + content
    write_memory_file(path, full)
    logger.info("[local-memory] wrote weekly memory for %s (%d chars)", week_label, len(content))
    try:
        update_memory_index(data_dir)
        record_memory_operation(data_dir)
    except Exception:
        pass
    return path


# ── Quote extraction ──

QUOTE_EXTRACTION_PROMPT = """从以下工作内容中提取经验金句。

来源类型：{source_type}
内容：{content}

提炼规则：
1. 像名人名言格式——精炼、有力、一读就记住
2. 必须有具体场景支撑（不要空洞的大道理）
3. 必须是可迁移的（别人遇到类似情况能用）
4. 保留原作者的判断视角（不要改到认不出来）
5. 每条不超过 50 字
6. 只提取真正有价值的，宁可不提也不凑数

返回 JSON：{{"quotes": [{{"text": "金句", "source": "来源简述"}}]}}
如果没有值得提取的金句，返回 {{"quotes": []}}"""


def extract_quotes_from_text(
    ai_service: Any,
    content: str,
    source_type: str,
    *,
    max_quotes: int = 2,
) -> list[dict[str, str]]:
    """Extract golden quotes from text using AI. Returns list of {text, source}."""
    if not content or len(content) < 50:
        return []
    health = ai_service.get_health()
    if health.provider == "mock" or not health.ready:
        return []
    try:
        prompt = QUOTE_EXTRACTION_PROMPT.format(
            source_type=source_type,
            content=content[:3000],
        )
        raw = ai_service._qwen_generate(
            prompt=prompt,
            system_instruction="你是益语智库的经验提炼助手。只返回 JSON，不要解释。",
            response_schema={"type": "object", "properties": {"quotes": {"type": "array", "items": {"type": "object", "properties": {"text": {"type": "string"}, "source": {"type": "string"}}, "required": ["text", "source"]}}}, "required": ["quotes"]},
            timeout_seconds=20.0,
            max_tokens=300,
            temperature=0.4,
            top_p=0.9,
            enable_thinking=False,
        )
        if isinstance(raw, dict):
            quotes = raw.get("quotes", [])
            return [q for q in quotes[:max_quotes] if isinstance(q, dict) and q.get("text")]
        return []
    except Exception:
        return []


def save_pending_quotes(
    db: Any,
    quotes: list[dict[str, str]],
    user_id: str = "user_guyuan",
    user_name: str = "顾源源",
) -> int:
    """Save extracted quotes as pending captures in growth system."""
    from uuid import uuid4 as _uuid4
    saved = 0
    now = _now_iso()
    for q in quotes:
        text = str(q.get("text", "")).strip()
        source = str(q.get("source", "")).strip()
        if not text:
            continue
        sig_id = f"gse_{_uuid4().hex[:10]}"
        try:
            db.execute(
                """INSERT INTO growth_signal_events(id, user_id, user_name, source_type, source_id, raw_text, context_json, dedupe_key, created_at)
                VALUES(?, ?, ?, 'review_insight_pending', ?, ?, ?, ?, ?)""",
                (sig_id, user_id, user_name, source, text,
                 json.dumps({"insightQuote": text, "insightSourceLabel": f"来源：{source}", "contextSummary": f"来源：{source}", "enriched": True}, ensure_ascii=False),
                 f"quote_{text[:30]}", now),
            )
            db.execute(
                """INSERT OR IGNORE INTO growth_capture_states(id, user_id, signal_id, status, reason, created_at, updated_at)
                VALUES(?, ?, ?, 'open', ?, ?, ?)""",
                (f"gc_{_uuid4().hex[:10]}", user_id, sig_id, f"AI从{source}中提炼", now, now),
            )
            saved += 1
        except Exception:
            pass
    return saved


# ── Memory Index ──

def update_memory_index(data_dir: str | Path) -> None:
    """Rebuild MEMORY_INDEX.md from current memory files."""
    from datetime import datetime as _dt
    root = memory_root(data_dir)
    lines = [
        "# 益语智库本地记忆索引",
        f"更新时间：{_dt.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 组织",
    ]
    org_path = root / "org_memory.md"
    if org_path.exists():
        lines.append("- [组织记忆](org_memory.md) — 益语定位、团队、市场、业务")

    lines.extend(["", "## 项目"])
    proj_dir = root / "projects"
    has_projects = False
    if proj_dir.exists():
        for cid_dir in sorted(proj_dir.iterdir()):
            if not cid_dir.is_dir():
                continue
            pm = cid_dir / "project_memory.md"
            if pm.exists():
                has_projects = True
                lines.append(f"- [{cid_dir.name}](projects/{cid_dir.name}/project_memory.md)")
                el_dir = cid_dir / "event_lines"
                if el_dir.exists():
                    for el_file in sorted(el_dir.glob("*.md")):
                        lines.append(f"  - [{el_file.stem}](projects/{cid_dir.name}/event_lines/{el_file.name})")
    if not has_projects:
        lines.append("- （尚无项目记忆）")

    lines.extend(["", "## 周快照"])
    weekly_dir = root / "weekly"
    has_weekly = False
    if weekly_dir.exists():
        for wf in sorted(weekly_dir.glob("*.md"), reverse=True)[:8]:
            has_weekly = True
            lines.append(f"- [{wf.stem}](weekly/{wf.name})")
    if not has_weekly:
        lines.append("- （尚无周快照）")

    (root / "MEMORY_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("[local-memory] updated MEMORY_INDEX.md")


# ── Dream (memory consolidation) ──

def should_dream(data_dir: str | Path) -> bool:
    """Check if it's time to consolidate memories (24h since last + 3 meaningful operations)."""
    root = memory_root(data_dir)
    dream_state_path = root / ".dream_state.json"
    try:
        if dream_state_path.exists():
            state = json.loads(dream_state_path.read_text(encoding="utf-8"))
            last_dream = state.get("lastDreamAt", "")
            ops_since = state.get("opsSinceDream", 0)
            if last_dream:
                from datetime import datetime as _dt
                last = _dt.fromisoformat(last_dream)
                hours_ago = (_dt.now() - last).total_seconds() / 3600
                return hours_ago >= 1 and ops_since >= 3
            return ops_since >= 3
        return False  # No state yet, wait for first operations
    except Exception:
        return False


def record_memory_operation(data_dir: str | Path) -> None:
    """Record that a meaningful memory operation happened (for dream trigger)."""
    root = memory_root(data_dir)
    dream_state_path = root / ".dream_state.json"
    try:
        state = {}
        if dream_state_path.exists():
            state = json.loads(dream_state_path.read_text(encoding="utf-8"))
        state["opsSinceDream"] = state.get("opsSinceDream", 0) + 1
        state["lastOpAt"] = _now_iso()
        if "lastDreamAt" not in state:
            state["lastDreamAt"] = _now_iso()  # Initialize
        dream_state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def run_dream_cycle(data_dir: str | Path, ai_service: Any = None, db: Any = None) -> dict[str, int]:
    """
    记忆整理周期 — "做梦"。

    借鉴 Claude Code AutoDream 的做法：
    - 不重读原始文档（成本太高）
    - 用定向搜索从已有记忆中找信号
    - 合并重复、解决矛盾、升级认知

    Phase 1: Orient — 扫描所有记忆文件
    Phase 2: Cross-pollinate — 从周记忆中提取关键判断，写回 project_memory
    Phase 3: DB sync — 把本地文件中的关键判断同步到 memory_facts
    Phase 4: Trim — 裁剪超长文件
    Phase 5: Index — 更新索引
    """
    root = memory_root(data_dir)
    stats = {
        "files_scanned": 0, "files_trimmed": 0, "index_updated": False,
        "cross_pollinated": 0, "facts_synced": 0,
    }

    all_memory_files: list[Path] = list(root.glob("**/*.md"))
    stats["files_scanned"] = len(all_memory_files)

    # ── Phase 2: Cross-pollinate — 从周记忆提取信号写回项目记忆 ──
    weekly_dir = root / "weekly"
    if weekly_dir.exists():
        # 找最新的周记忆
        weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)
        for wf in weekly_files[:2]:  # 只处理最近 2 周
            weekly_content = wf.read_text(encoding="utf-8")
            if len(weekly_content) < 100:
                continue

            # 定向搜索：提取"需要关注"、"卡点汇总"、"下周提示"部分
            signals: dict[str, list[str]] = {"关注": [], "卡点": [], "提示": []}
            current_section = ""
            for line in weekly_content.split("\n"):
                stripped = line.strip()
                if "需要关注" in stripped or "风险" in stripped:
                    current_section = "关注"
                elif "卡点" in stripped or "阻塞" in stripped:
                    current_section = "卡点"
                elif "下周" in stripped or "提示" in stripped:
                    current_section = "提示"
                elif "正常推进" in stripped or "## " in stripped:
                    current_section = ""
                elif current_section and stripped.startswith("•"):
                    signals[current_section].append(stripped.lstrip("• ").strip())

            # 把信号写回对应的项目记忆
            proj_root = root / "projects"
            if proj_root.exists():
                for cid_dir in proj_root.iterdir():
                    if not cid_dir.is_dir() or cid_dir.name in ("general", "."):
                        continue
                    pm_path = cid_dir / "project_memory.md"
                    if not pm_path.exists():
                        continue
                    pm_content = pm_path.read_text(encoding="utf-8")
                    # 检查该项目名是否出现在周记忆的信号中
                    client_signals = []
                    for section, items in signals.items():
                        for item in items:
                            # 简单匹配：如果信号中包含项目文件夹对应的客户关键词
                            if cid_dir.name in weekly_content and any(kw in item for kw in _extract_keywords_from_path(pm_content)):
                                client_signals.append(f"[{section}] {item}")

                    if client_signals and "## 做梦整理" not in pm_content:
                        # 追加到项目记忆末尾
                        week_label = wf.stem
                        addition = f"\n\n## 做梦整理（{week_label}）\n" + "\n".join(f"- {s}" for s in client_signals[:5])
                        pm_path.write_text(pm_content + addition, encoding="utf-8")
                        stats["cross_pollinated"] += 1

    # ── Phase 3: DB sync — 把周记忆的关键判断写入 memory_facts ──
    if db is not None and weekly_dir.exists():
        weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)
        for wf in weekly_files[:1]:  # 只处理最新一周
            weekly_content = wf.read_text(encoding="utf-8")
            week_label = wf.stem

            # 提取结构化段落
            sections_to_sync = {
                "weekly_attention": "",  # 需要关注
                "weekly_blockers": "",   # 卡点汇总
                "weekly_next": "",       # 下周提示
            }
            current_key = ""
            current_lines: list[str] = []
            for line in weekly_content.split("\n"):
                stripped = line.strip()
                if "需要关注" in stripped:
                    if current_key and current_lines:
                        sections_to_sync[current_key] = "\n".join(current_lines)
                    current_key = "weekly_attention"
                    current_lines = []
                elif "卡点" in stripped:
                    if current_key and current_lines:
                        sections_to_sync[current_key] = "\n".join(current_lines)
                    current_key = "weekly_blockers"
                    current_lines = []
                elif "下周" in stripped:
                    if current_key and current_lines:
                        sections_to_sync[current_key] = "\n".join(current_lines)
                    current_key = "weekly_next"
                    current_lines = []
                elif stripped.startswith("##") or stripped.startswith("【正常推进"):
                    if current_key and current_lines:
                        sections_to_sync[current_key] = "\n".join(current_lines)
                    current_key = ""
                    current_lines = []
                elif current_key and stripped:
                    current_lines.append(stripped)
            if current_key and current_lines:
                sections_to_sync[current_key] = "\n".join(current_lines)

            # 写入 memory_facts（用 product scope 代表组织级记忆）
            from app.services.memory_foundation import upsert_memory_fact
            for fact_key, fact_value in sections_to_sync.items():
                if fact_value.strip():
                    try:
                        upsert_memory_fact(
                            db,
                            scope_type="product",
                            scope_id="org_weekly",
                            fact_key=f"{fact_key}:{week_label}",
                            fact_value=fact_value[:800],
                            source_type="dream_cycle",
                            source_id=f"weekly/{week_label}",
                            confidence=0.8,
                            freshness=0.9,
                        )
                        stats["facts_synced"] += 1
                    except Exception:
                        pass

    # ── Phase 4: Trim — 裁剪超长文件 ──
    SIZE_LIMITS = {
        "org_memory.md": 4000,
        "project_memory.md": 3000,
        "MEMORY_INDEX.md": 5000,
    }
    DEFAULT_LIMIT = 2000

    for mf in all_memory_files:
        if mf.name.startswith("."):
            continue
        limit = SIZE_LIMITS.get(mf.name, DEFAULT_LIMIT)
        content = mf.read_text(encoding="utf-8")
        if len(content) > limit * 1.5:
            if "---" in content:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = f"---{parts[1]}---"
                    body = parts[2].strip()
                    if len(body) > limit:
                        body = body[:limit].rsplit("\n", 1)[0] + "\n\n（记忆已自动精简，保留核心内容）"
                        mf.write_text(f"{frontmatter}\n\n{body}\n", encoding="utf-8")
                        stats["files_trimmed"] += 1

    # ── Phase 5: Update index ──
    try:
        update_memory_index(data_dir)
        stats["index_updated"] = True
    except Exception:
        pass

    # Update dream state
    dream_state_path = root / ".dream_state.json"
    try:
        dream_state_path.write_text(json.dumps({
            "lastDreamAt": _now_iso(),
            "opsSinceDream": 0,
            "lastStats": stats,
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    logger.info("[local-memory] dream cycle complete: %s", stats)
    return stats


def _extract_keywords_from_path(content: str) -> list[str]:
    """从项目记忆内容中提取关键词用于匹配。"""
    keywords = []
    for line in content.split("\n")[:10]:
        stripped = line.strip()
        if stripped.startswith("project:") or stripped.startswith("event_line:"):
            val = stripped.split(":", 1)[1].strip()
            if val:
                keywords.append(val)
                # 也加入短名
                for part in val.split():
                    if len(part) >= 2:
                        keywords.append(part)
    return keywords[:10] if keywords else ["_no_match_"]


# ── Aggregate reader for AI context ──

def gather_project_context_for_ai(
    data_dir: str | Path,
    client_ids: list[str],
    event_line_ids: list[str] | None = None,
) -> str:
    """
    Gather all relevant memory into a single text block for AI consumption.
    This replaces real-time cloud API calls — reads only local files.
    """
    parts: list[str] = []
    # Organization memory
    org_path = memory_root(data_dir) / "org_memory.md"
    org_text = read_memory_file(org_path)
    if org_text:
        parts.append(f"【组织记忆】\n{org_text}")

    # Scan ALL project directories (not just specified client_ids)
    proj_root = memory_root(data_dir) / "projects"
    all_cids = list(client_ids) + ["general"]
    if proj_root.exists():
        for cid_dir in proj_root.iterdir():
            if cid_dir.is_dir() and cid_dir.name not in all_cids:
                all_cids.append(cid_dir.name)

    for cid in all_cids:
        pm = read_project_memory(data_dir, cid)
        if pm:
            parts.append(f"【项目记忆】\n{pm}")

        # Event line memories under this project
        el_dir = event_line_memory_dir(data_dir, cid)
        if el_dir.exists():
            for md_file in sorted(el_dir.glob("*.md")):
                eid = md_file.stem
                if event_line_ids and eid not in event_line_ids:
                    continue
                el_text = read_memory_file(md_file)
                if el_text:
                    parts.append(f"【事件线记忆】\n{el_text}")

    # Attachment texts from cache
    att_cache_dir = Path(data_dir) / "Cache" / "event-line-attachments"
    if att_cache_dir.exists():
        for text_file in sorted(att_cache_dir.glob("*.text.json"))[:10]:
            try:
                td = json.loads(text_file.read_bytes())
                t = str(td.get("text", "")).strip()
                title = str(td.get("title", "")).strip()
                if t and len(t) > 100 and "提取失败" not in t and "No module" not in t:
                    parts.append(f"【附件全文：{title}】\n{t}")
            except Exception:
                continue

    return "\n\n".join(parts)
