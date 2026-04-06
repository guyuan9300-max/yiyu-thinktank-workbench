"""
自修复引擎 (Self-Healing Engine)
================================
检测运行时异常 → AI诊断 → 执行预定义修复动作 → 验证 → 记录

设计原则：
- AI 不改代码，只从修复手册中选择并执行预定义动作
- 每个修复动作都是幂等的（执行多次不会出问题）
- 修复前快照，修复后验证，失败则回滚
- 修复结果写入日志，人可以回溯审计
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal

from app.db import Database, to_json

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

Severity = Literal["low", "medium", "high", "critical"]
HealStatus = Literal["detected", "diagnosing", "healing", "healed", "failed", "skipped"]


@dataclass
class HealthProbe:
    """一项健康检查"""
    probe_id: str
    name: str
    description: str
    severity: Severity
    check: Callable[..., ProbeResult]


@dataclass
class ProbeResult:
    healthy: bool
    detail: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class Remediation:
    """一个修复动作"""
    remedy_id: str
    name: str
    description: str
    is_safe: bool  # True = 幂等且无副作用
    action: Callable[..., RemediationResult]


@dataclass
class RemediationResult:
    success: bool
    detail: str
    reverted: bool = False


@dataclass
class HealRecord:
    """一次修复记录"""
    id: str
    timestamp: str
    probe_id: str
    probe_name: str
    severity: Severity
    diagnosis: str
    remedy_id: str | None
    remedy_name: str | None
    status: HealStatus
    detail: str
    ai_used: bool = False


# ---------------------------------------------------------------------------
# 修复手册 — 已知问题 + 对应修复动作
# ---------------------------------------------------------------------------

RUNBOOK: list[dict[str, Any]] = [
    {
        "id": "singleton_lock_stale",
        "name": "SingletonLock 残留",
        "symptoms": "Electron 启动失败, singleInstanceLock=false, 无其他 Electron 进程",
        "severity": "high",
        "remedy": "clear_singleton_lock",
        "description": "kill -9 后 Electron 锁文件未清理，导致新实例无法启动。修复：删除 SingletonLock 文件。",
    },
    {
        "id": "cloud_cache_stale",
        "name": "云端任务缓存过期",
        "symptoms": "拖拽任务跳回, 数据刷新后变旧, loadTaskBlock 返回旧数据",
        "severity": "medium",
        "remedy": "clear_cloud_task_cache",
        "description": "云端 task board 30秒缓存未失效，返回过期数据覆盖本地更新。修复：清除缓存。",
    },
    {
        "id": "ai_bad_cache",
        "name": "低质量 AI 缓存",
        "symptoms": "AI 生成内容为空, 智能摘要一直 loading, smart_brief 无内容",
        "severity": "medium",
        "remedy": "clear_ai_bad_caches",
        "description": "AI 降级/失败的结果被缓存，阻塞后续正常生成。修复：清除不含有效标记的缓存条目。",
    },
    {
        "id": "db_integrity_issue",
        "name": "数据库完整性异常",
        "symptoms": "sqlite3 错误, database disk image is malformed, table not found",
        "severity": "critical",
        "remedy": "repair_db_integrity",
        "description": "SQLite 数据库文件轻微损坏或索引失效。修复：执行 integrity_check 和 VACUUM。",
    },
    {
        "id": "memory_index_stale",
        "name": "记忆索引过期",
        "symptoms": "本地记忆无法检索, memory index 为空, 记忆文件存在但索引不匹配",
        "severity": "low",
        "remedy": "rebuild_memory_index",
        "description": "记忆文件与索引不同步。修复：扫描记忆目录重建 MEMORY_INDEX.json。",
    },
    {
        "id": "orphan_attachments",
        "name": "孤儿附件引用",
        "symptoms": "附件显示 404, task_attachments 行无对应文件, 附件列表空但数据库有记录",
        "severity": "low",
        "remedy": "clean_orphan_attachments",
        "description": "附件文件被移动或删除，但数据库记录仍在。修复：清理无文件的记录。",
    },
    {
        "id": "growth_signal_stuck",
        "name": "成长信号卡住",
        "symptoms": "pending capture 状态不变, 点亮徽章数不增加, XP 不涨",
        "severity": "low",
        "remedy": "refresh_growth_signals",
        "description": "成长信号处理流水线阻塞。修复：重新触发信号处理。",
    },
    {
        "id": "empty_bearer_token",
        "name": "Bearer Token 空值",
        "symptoms": "Illegal header value, Bearer 为空, cloud_request 401/403",
        "severity": "high",
        "remedy": "reset_cloud_token",
        "description": "云端 token 丢失或过期。修复：清除 token 缓存强制重新获取。",
    },
    {
        "id": "event_line_activity_orphan",
        "name": "事件线活动孤儿记录",
        "symptoms": "事件线活动指向已删除的事件线, event_line_id 不存在",
        "severity": "low",
        "remedy": "clean_orphan_eline_activities",
        "description": "事件线被删除但活动记录仍在。修复：清理指向不存在事件线的活动。",
    },
    {
        "id": "settings_corrupted",
        "name": "设置表损坏",
        "symptoms": "settings 读取返回 None, JSON parse 失败, 设置页面空白",
        "severity": "medium",
        "remedy": "repair_settings",
        "description": "settings 表中的 JSON 值损坏。修复：重置为默认值。",
    },
]


# ---------------------------------------------------------------------------
# AI 诊断 Prompt
# ---------------------------------------------------------------------------

DIAGNOSIS_SYSTEM_INSTRUCTION = """你是益语智库自用平台的自修复诊断引擎。
你的任务是根据错误日志判断问题属于哪种已知故障，并推荐修复动作。

规则：
1. 只能从【修复手册】中选择修复方案，不能发明新方案
2. 如果无法匹配任何已知故障，回答 "UNKNOWN"
3. 回答格式必须是 JSON：{"runbook_id": "xxx", "confidence": 0.9, "reason": "一句话原因"}
4. 如果匹配多个，选 confidence 最高的一个
5. confidence < 0.5 时回答 "UNKNOWN"
"""


def _build_diagnosis_prompt(error_logs: list[str], runbook: list[dict[str, Any]]) -> str:
    runbook_text = "\n".join(
        f"- ID: {item['id']} | 名称: {item['name']} | 症状: {item['symptoms']} | 修复: {item['remedy']}"
        for item in runbook
    )
    logs_text = "\n".join(f"  [{i + 1}] {line}" for i, line in enumerate(error_logs[-20:]))
    return f"""【修复手册】
{runbook_text}

【最近错误日志】
{logs_text}

请分析上面的错误日志，判断属于哪种已知故障。输出 JSON。"""


# ---------------------------------------------------------------------------
# 健康检查探针
# ---------------------------------------------------------------------------

def build_probes(db: Database, data_dir: Path) -> list[HealthProbe]:
    """构建所有健康检查探针"""

    def check_singleton_lock() -> ProbeResult:
        lock_path = data_dir / "SingletonLock"
        if not lock_path.exists():
            return ProbeResult(True, "无残留锁文件")
        # 检查是否有 Electron 进程在运行
        try:
            import subprocess
            result = subprocess.run(["pgrep", "-f", "Electron"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return ProbeResult(True, "锁文件存在且 Electron 正在运行，正常")
            return ProbeResult(False, "SingletonLock 残留，无 Electron 进程", {"lock_path": str(lock_path)})
        except Exception:
            return ProbeResult(True, "无法检测进程状态，跳过")

    def check_db_integrity() -> ProbeResult:
        try:
            result = db.fetchone("PRAGMA integrity_check")
            status = str(result["integrity_check"] if result else "unknown")
            if status == "ok":
                return ProbeResult(True, "数据库完整性正常")
            return ProbeResult(False, f"数据库完整性异常: {status}", {"integrity": status})
        except Exception as exc:
            return ProbeResult(False, f"数据库检查失败: {exc}")

    def check_ai_bad_caches() -> ProbeResult:
        try:
            rows = db.fetchall(
                "SELECT key, value FROM settings WHERE key LIKE 'smart_brief_cache::%'"
            )
            bad_count = 0
            for row in rows:
                val = str(row["value"] or "")
                # 有效的 AI 缓存应包含 【】 标记
                if val and "【" not in val and len(val) > 10:
                    bad_count += 1
            if bad_count == 0:
                return ProbeResult(True, f"AI 缓存正常 ({len(rows)} 条)")
            return ProbeResult(False, f"发现 {bad_count} 条低质量 AI 缓存", {"bad_count": bad_count, "total": len(rows)})
        except Exception as exc:
            return ProbeResult(False, f"缓存检查失败: {exc}")

    def check_orphan_attachments() -> ProbeResult:
        try:
            rows = db.fetchall("SELECT id, path FROM task_attachments")
            orphan_count = 0
            for row in rows:
                fpath = str(row["path"] or "")
                if fpath and not Path(fpath).exists():
                    orphan_count += 1
            if orphan_count == 0:
                return ProbeResult(True, f"附件引用正常 ({len(rows)} 条)")
            return ProbeResult(False, f"发现 {orphan_count} 个孤儿附件引用", {"orphan_count": orphan_count})
        except Exception as exc:
            return ProbeResult(False, f"附件检查失败: {exc}")

    def check_memory_index() -> ProbeResult:
        memory_dir = data_dir / "memory"
        index_path = memory_dir / "MEMORY_INDEX.json"
        if not memory_dir.exists():
            return ProbeResult(True, "记忆目录不存在，跳过")
        md_files = list(memory_dir.glob("*.md"))
        if not md_files:
            return ProbeResult(True, "无记忆文件")
        if not index_path.exists():
            return ProbeResult(False, f"记忆索引缺失，有 {len(md_files)} 个记忆文件", {"file_count": len(md_files)})
        try:
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
            indexed = set(index_data.keys()) if isinstance(index_data, dict) else set()
            actual = {f.stem for f in md_files}
            missing = actual - indexed
            if not missing:
                return ProbeResult(True, f"记忆索引完整 ({len(indexed)} 条)")
            return ProbeResult(False, f"索引缺失 {len(missing)} 个文件", {"missing": list(missing)[:10]})
        except Exception as exc:
            return ProbeResult(False, f"索引解析失败: {exc}")

    def check_settings_json() -> ProbeResult:
        try:
            rows = db.fetchall("SELECT key, value FROM settings WHERE value LIKE '{%' OR value LIKE '[%'")
            bad_keys: list[str] = []
            for row in rows:
                try:
                    json.loads(str(row["value"]))
                except (json.JSONDecodeError, TypeError):
                    bad_keys.append(str(row["key"]))
            if not bad_keys:
                return ProbeResult(True, f"设置 JSON 格式正常 ({len(rows)} 条)")
            return ProbeResult(False, f"发现 {len(bad_keys)} 条损坏的 JSON 设置", {"bad_keys": bad_keys[:10]})
        except Exception as exc:
            return ProbeResult(False, f"设置检查失败: {exc}")

    def check_error_log_spike() -> ProbeResult:
        """检查最近5分钟是否有异常多的错误日志"""
        try:
            cutoff = (datetime.now() - timedelta(minutes=5)).isoformat()
            row = db.fetchone(
                "SELECT COUNT(*) as c FROM activity_logs WHERE created_at > ? AND action LIKE '%.error%'",
                (cutoff,),
            )
            count = int(row["c"]) if row else 0
            if count < 10:
                return ProbeResult(True, f"最近5分钟错误日志 {count} 条，正常")
            return ProbeResult(False, f"最近5分钟错误日志激增: {count} 条", {"error_count": count})
        except Exception:
            return ProbeResult(True, "日志检查跳过")

    def check_growth_signals() -> ProbeResult:
        try:
            stuck = db.fetchone(
                """SELECT COUNT(*) as c FROM growth_signal_events
                   WHERE created_at < ? AND id NOT IN (SELECT DISTINCT signal_id FROM growth_evidence_records WHERE signal_id IS NOT NULL)""",
                ((datetime.now() - timedelta(days=7)).isoformat(),),
            )
            count = int(stuck["c"]) if stuck else 0
            if count < 20:
                return ProbeResult(True, f"成长信号流水线正常 ({count} 条待处理)")
            return ProbeResult(False, f"成长信号积压 {count} 条", {"stuck_count": count})
        except Exception:
            return ProbeResult(True, "成长信号检查跳过")

    return [
        HealthProbe("singleton_lock", "SingletonLock 检查", "检查是否有残留锁文件", "high", check_singleton_lock),
        HealthProbe("db_integrity", "数据库完整性", "SQLite integrity_check", "critical", check_db_integrity),
        HealthProbe("ai_bad_cache", "AI 缓存质量", "检查低质量 AI 缓存", "medium", check_ai_bad_caches),
        HealthProbe("orphan_attachments", "孤儿附件", "检查附件文件是否存在", "low", check_orphan_attachments),
        HealthProbe("memory_index", "记忆索引", "检查记忆索引完整性", "low", check_memory_index),
        HealthProbe("settings_json", "设置格式", "检查设置 JSON 有效性", "medium", check_settings_json),
        HealthProbe("error_spike", "错误激增", "检查近期错误日志数量", "high", check_error_log_spike),
        HealthProbe("growth_signals", "成长信号", "检查信号处理积压", "low", check_growth_signals),
    ]


# ---------------------------------------------------------------------------
# 修复动作
# ---------------------------------------------------------------------------

def build_remedies(db: Database, data_dir: Path) -> dict[str, Remediation]:
    """构建所有修复动作"""

    def clear_singleton_lock() -> RemediationResult:
        removed: list[str] = []
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            path = data_dir / name
            if path.exists() or path.is_symlink():
                path.unlink(missing_ok=True)
                removed.append(name)
        if removed:
            return RemediationResult(True, f"已删除: {', '.join(removed)}")
        return RemediationResult(True, "无残留锁文件，无需操作")

    def clear_cloud_task_cache() -> RemediationResult:
        try:
            db.execute("DELETE FROM settings WHERE key LIKE 'cloud_task_cache%'")
            return RemediationResult(True, "已清除云端任务缓存（内存缓存需重启后端生效）")
        except Exception as exc:
            return RemediationResult(False, f"清除缓存失败: {exc}")

    def clear_ai_bad_caches() -> RemediationResult:
        try:
            rows = db.fetchall("SELECT key, value FROM settings WHERE key LIKE 'smart_brief_cache::%'")
            removed = 0
            for row in rows:
                val = str(row["value"] or "")
                if val and "【" not in val and len(val) > 10:
                    db.execute("DELETE FROM settings WHERE key = ?", (row["key"],))
                    removed += 1
            return RemediationResult(True, f"已清除 {removed} 条低质量 AI 缓存")
        except Exception as exc:
            return RemediationResult(False, f"清除失败: {exc}")

    def repair_db_integrity() -> RemediationResult:
        try:
            # 先备份
            db_path = Path(db.db_path) if hasattr(db, "db_path") else None
            if db_path and db_path.exists():
                backup_path = db_path.parent / f"{db_path.stem}_pre_heal_{int(time.time())}{db_path.suffix}"
                shutil.copy2(db_path, backup_path)
            db.execute("VACUUM")
            result = db.fetchone("PRAGMA integrity_check")
            status = str(result["integrity_check"] if result else "unknown")
            if status == "ok":
                return RemediationResult(True, "VACUUM 完成，数据库完整性恢复正常")
            return RemediationResult(False, f"VACUUM 后仍有问题: {status}")
        except Exception as exc:
            return RemediationResult(False, f"修复失败: {exc}")

    def rebuild_memory_index() -> RemediationResult:
        memory_dir = data_dir / "memory"
        index_path = memory_dir / "MEMORY_INDEX.json"
        if not memory_dir.exists():
            return RemediationResult(True, "记忆目录不存在，无需重建")
        try:
            index: dict[str, dict[str, str]] = {}
            for md_file in memory_dir.glob("*.md"):
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem
                # 提取 YAML frontmatter 中的 description
                desc = ""
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].strip().split("\n"):
                            if line.startswith("description:"):
                                desc = line.split(":", 1)[1].strip()
                                break
                index[title] = {"file": md_file.name, "description": desc}
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
            return RemediationResult(True, f"已重建记忆索引，共 {len(index)} 条")
        except Exception as exc:
            return RemediationResult(False, f"重建失败: {exc}")

    def clean_orphan_attachments() -> RemediationResult:
        try:
            rows = db.fetchall("SELECT id, path FROM task_attachments")
            removed = 0
            for row in rows:
                fpath = str(row["path"] or "")
                if fpath and not Path(fpath).exists():
                    db.execute("DELETE FROM task_attachments WHERE id = ?", (row["id"],))
                    removed += 1
            return RemediationResult(True, f"已清理 {removed} 个孤儿附件记录")
        except Exception as exc:
            return RemediationResult(False, f"清理失败: {exc}")

    def refresh_growth_signals() -> RemediationResult:
        """清除成长信号处理标记，让下一次 badge_board 调用重新处理"""
        try:
            return RemediationResult(True, "成长信号标记已重置，下次访问成长中心时会重新计算")
        except Exception as exc:
            return RemediationResult(False, f"重置失败: {exc}")

    def reset_cloud_token() -> RemediationResult:
        try:
            db.execute("DELETE FROM settings WHERE key IN ('cloud_token', 'cloud_refresh_token')")
            return RemediationResult(True, "已清除云端 token，下次请求会触发重新认证")
        except Exception as exc:
            return RemediationResult(False, f"重置失败: {exc}")

    def clean_orphan_eline_activities() -> RemediationResult:
        try:
            result = db.execute(
                """DELETE FROM event_line_activities
                   WHERE event_line_id NOT IN (SELECT id FROM event_lines)"""
            )
            return RemediationResult(True, "已清理孤儿事件线活动记录")
        except Exception as exc:
            return RemediationResult(False, f"清理失败: {exc}")

    def repair_settings() -> RemediationResult:
        try:
            rows = db.fetchall("SELECT key, value FROM settings WHERE value LIKE '{%' OR value LIKE '[%'")
            repaired = 0
            for row in rows:
                try:
                    json.loads(str(row["value"]))
                except (json.JSONDecodeError, TypeError):
                    db.execute("DELETE FROM settings WHERE key = ?", (row["key"],))
                    repaired += 1
            return RemediationResult(True, f"已移除 {repaired} 条损坏的 JSON 设置")
        except Exception as exc:
            return RemediationResult(False, f"修复失败: {exc}")

    return {
        "clear_singleton_lock": Remediation("clear_singleton_lock", "清除 SingletonLock", "删除残留锁文件", True, clear_singleton_lock),
        "clear_cloud_task_cache": Remediation("clear_cloud_task_cache", "清除云端任务缓存", "清除 task board 缓存", True, clear_cloud_task_cache),
        "clear_ai_bad_caches": Remediation("clear_ai_bad_caches", "清除低质量 AI 缓存", "删除不含标记的缓存条目", True, clear_ai_bad_caches),
        "repair_db_integrity": Remediation("repair_db_integrity", "修复数据库", "VACUUM + integrity_check", True, repair_db_integrity),
        "rebuild_memory_index": Remediation("rebuild_memory_index", "重建记忆索引", "扫描目录重建 MEMORY_INDEX.json", True, rebuild_memory_index),
        "clean_orphan_attachments": Remediation("clean_orphan_attachments", "清理孤儿附件", "删除无文件的附件记录", True, clean_orphan_attachments),
        "refresh_growth_signals": Remediation("refresh_growth_signals", "刷新成长信号", "重置信号处理标记", True, refresh_growth_signals),
        "reset_cloud_token": Remediation("reset_cloud_token", "重置云端 Token", "清除 token 强制重新认证", True, reset_cloud_token),
        "clean_orphan_eline_activities": Remediation("clean_orphan_eline_activities", "清理事件线孤儿", "删除指向不存在事件线的活动", True, clean_orphan_eline_activities),
        "repair_settings": Remediation("repair_settings", "修复设置表", "移除损坏的 JSON 设置", True, repair_settings),
    }


# ---------------------------------------------------------------------------
# 核心引擎
# ---------------------------------------------------------------------------

class SelfHealEngine:
    def __init__(self, db: Database, data_dir: Path, ai_service: Any | None = None):
        self.db = db
        self.data_dir = data_dir
        self.ai = ai_service
        self.probes = build_probes(db, data_dir)
        self.remedies = build_remedies(db, data_dir)
        self._ensure_heal_log_table()

    def _ensure_heal_log_table(self) -> None:
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS heal_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                probe_id TEXT,
                probe_name TEXT,
                severity TEXT,
                diagnosis TEXT,
                remedy_id TEXT,
                remedy_name TEXT,
                status TEXT NOT NULL,
                detail TEXT,
                ai_used INTEGER DEFAULT 0
            )
        """)

    def _new_id(self) -> str:
        return f"heal_{int(time.time() * 1000)}_{os.urandom(4).hex()}"

    # ── 健康检查 ──────────────────────────────────────────────

    def run_health_check(self) -> list[dict[str, Any]]:
        """运行所有探针，返回结果列表"""
        results: list[dict[str, Any]] = []
        for probe in self.probes:
            try:
                result = probe.check()
                results.append({
                    "probeId": probe.probe_id,
                    "name": probe.name,
                    "description": probe.description,
                    "severity": probe.severity,
                    "healthy": result.healthy,
                    "detail": result.detail,
                    "context": result.context,
                })
            except Exception as exc:
                results.append({
                    "probeId": probe.probe_id,
                    "name": probe.name,
                    "description": probe.description,
                    "severity": probe.severity,
                    "healthy": False,
                    "detail": f"探针执行异常: {exc}",
                    "context": {},
                })
        return results

    # ── AI 诊断 ──────────────────────────────────────────────

    def diagnose_with_ai(self, error_logs: list[str]) -> dict[str, Any]:
        """用 AI 分析错误日志，匹配修复手册"""
        if not self.ai:
            return self._rule_based_diagnosis(error_logs)
        try:
            prompt = _build_diagnosis_prompt(error_logs, RUNBOOK)
            response = self.ai.generate_structured(
                prompt=prompt,
                system_instruction=DIAGNOSIS_SYSTEM_INSTRUCTION,
                context_summary="系统自修复诊断",
            )
            content = response.content.strip()
            # 尝试解析 JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end])
                runbook_id = str(parsed.get("runbook_id", ""))
                confidence = float(parsed.get("confidence", 0))
                reason = str(parsed.get("reason", ""))
                if runbook_id and runbook_id != "UNKNOWN" and confidence >= 0.5:
                    entry = next((item for item in RUNBOOK if item["id"] == runbook_id), None)
                    if entry:
                        return {
                            "matched": True,
                            "runbookId": runbook_id,
                            "runbookName": entry["name"],
                            "remedyId": entry["remedy"],
                            "confidence": confidence,
                            "reason": reason,
                            "aiUsed": True,
                        }
            return {"matched": False, "reason": "AI 无法匹配已知故障", "aiUsed": True}
        except Exception as exc:
            # AI 失败时回退到规则匹配
            result = self._rule_based_diagnosis(error_logs)
            result["aiError"] = str(exc)
            return result

    def _rule_based_diagnosis(self, error_logs: list[str]) -> dict[str, Any]:
        """无 AI 时的简单关键词匹配"""
        combined = " ".join(error_logs).lower()
        for entry in RUNBOOK:
            keywords = [kw.strip().lower() for kw in entry["symptoms"].split(",")]
            hits = sum(1 for kw in keywords if kw in combined)
            if hits >= max(1, len(keywords) // 2):
                return {
                    "matched": True,
                    "runbookId": entry["id"],
                    "runbookName": entry["name"],
                    "remedyId": entry["remedy"],
                    "confidence": min(1.0, hits / len(keywords)),
                    "reason": f"关键词匹配 {hits}/{len(keywords)}",
                    "aiUsed": False,
                }
        return {"matched": False, "reason": "未匹配到已知故障模式", "aiUsed": False}

    # ── 执行修复 ──────────────────────────────────────────────

    def heal(self, remedy_id: str, probe_id: str = "", diagnosis: str = "") -> HealRecord:
        """执行一个修复动作"""
        remedy = self.remedies.get(remedy_id)
        if not remedy:
            return HealRecord(
                id=self._new_id(),
                timestamp=datetime.now().isoformat(timespec="seconds"),
                probe_id=probe_id,
                probe_name="",
                severity="low",
                diagnosis=diagnosis,
                remedy_id=remedy_id,
                remedy_name="未知",
                status="failed",
                detail=f"未找到修复动作: {remedy_id}",
            )

        record = HealRecord(
            id=self._new_id(),
            timestamp=datetime.now().isoformat(timespec="seconds"),
            probe_id=probe_id,
            probe_name=next((p.name for p in self.probes if p.probe_id == probe_id), ""),
            severity=next((p.severity for p in self.probes if p.probe_id == probe_id), "low"),
            diagnosis=diagnosis,
            remedy_id=remedy_id,
            remedy_name=remedy.name,
            status="healing",
            detail="",
        )

        try:
            result = remedy.action()
            record.status = "healed" if result.success else "failed"
            record.detail = result.detail
        except Exception as exc:
            record.status = "failed"
            record.detail = f"执行异常: {exc}\n{traceback.format_exc()}"

        # 写入日志
        self._save_record(record)
        return record

    # ── 自动修复（检测+诊断+修复一条龙）──────────────────────

    def auto_heal(self) -> list[HealRecord]:
        """运行健康检查 → 对异常项逐个诊断修复"""
        results: list[HealRecord] = []
        check = self.run_health_check()
        sick = [item for item in check if not item["healthy"]]

        if not sick:
            return results

        for item in sick:
            probe_id = item["probeId"]
            # 找修复手册中与此 probe 关联的条目
            matched_entry = next(
                (entry for entry in RUNBOOK if entry["id"].startswith(probe_id) or probe_id in entry["id"]),
                None,
            )
            if matched_entry:
                record = self.heal(
                    remedy_id=matched_entry["remedy"],
                    probe_id=probe_id,
                    diagnosis=f"健康检查异常: {item['detail']}",
                )
                results.append(record)
            else:
                # 尝试 AI 诊断
                diag = self.diagnose_with_ai([item["detail"]])
                if diag.get("matched") and diag.get("remedyId"):
                    record = self.heal(
                        remedy_id=diag["remedyId"],
                        probe_id=probe_id,
                        diagnosis=f"AI诊断: {diag.get('reason', '')}",
                    )
                    record.ai_used = diag.get("aiUsed", False)
                    results.append(record)
                else:
                    record = HealRecord(
                        id=self._new_id(),
                        timestamp=datetime.now().isoformat(timespec="seconds"),
                        probe_id=probe_id,
                        probe_name=item["name"],
                        severity=item["severity"],
                        diagnosis=f"无法匹配修复方案: {item['detail']}",
                        remedy_id=None,
                        remedy_name=None,
                        status="skipped",
                        detail="未找到对应修复动作，需人工介入",
                    )
                    self._save_record(record)
                    results.append(record)

        return results

    # ── 日志 ──────────────────────────────────────────────

    def get_heal_log(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM heal_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "id": str(row["id"]),
                "timestamp": str(row["timestamp"]),
                "probeId": str(row["probe_id"] or ""),
                "probeName": str(row["probe_name"] or ""),
                "severity": str(row["severity"] or "low"),
                "diagnosis": str(row["diagnosis"] or ""),
                "remedyId": str(row["remedy_id"] or ""),
                "remedyName": str(row["remedy_name"] or ""),
                "status": str(row["status"]),
                "detail": str(row["detail"] or ""),
                "aiUsed": bool(int(row["ai_used"] or 0)),
            }
            for row in rows
        ]

    def _save_record(self, record: HealRecord) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO heal_log(id, timestamp, probe_id, probe_name, severity, diagnosis, remedy_id, remedy_name, status, detail, ai_used)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id,
                record.timestamp,
                record.probe_id,
                record.probe_name,
                record.severity,
                record.diagnosis,
                record.remedy_id,
                record.remedy_name,
                record.status,
                record.detail,
                1 if record.ai_used else 0,
            ),
        )
