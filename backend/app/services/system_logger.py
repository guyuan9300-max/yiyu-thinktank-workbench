"""
System-wide structured logging service.

Writes JSON-lines log files to {data_dir}/logs/, one file per day.
Captures API requests, errors, business operations, and system events.
Supports querying and exporting to Markdown for debugging.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal

LogLevel = Literal["DEBUG", "INFO", "WARN", "ERROR"]

_CST = timezone(timedelta(hours=8))


def _now_cst() -> datetime:
    return datetime.now(_CST)


def _today_cst() -> date:
    return _now_cst().date()


class SystemLogger:
    """Thread-safe structured logger that writes JSON lines to daily log files."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._current_date: date | None = None
        self._current_file: Any = None

    def _ensure_file(self) -> Any:
        today = _today_cst()
        if self._current_date != today or self._current_file is None:
            if self._current_file is not None:
                try:
                    self._current_file.close()
                except Exception:
                    pass
            file_path = self.log_dir / f"{today.isoformat()}.jsonl"
            self._current_file = open(file_path, "a", encoding="utf-8")
            self._current_date = today
        return self._current_file

    def write(self, level: LogLevel, source: str, message: str, **extra: Any) -> None:
        entry = {
            "ts": _now_cst().isoformat(),
            "level": level,
            "source": source,
            "message": message,
            **{k: v for k, v in extra.items() if v is not None},
        }
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock:
            try:
                f = self._ensure_file()
                f.write(line + "\n")
                f.flush()
            except Exception:
                pass

    def info(self, source: str, message: str, **extra: Any) -> None:
        self.write("INFO", source, message, **extra)

    def warn(self, source: str, message: str, **extra: Any) -> None:
        self.write("WARN", source, message, **extra)

    def error(self, source: str, message: str, **extra: Any) -> None:
        self.write("ERROR", source, message, **extra)

    def api_request(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        user: str = "",
        error_msg: str | None = None,
        error_traceback: str | None = None,
    ) -> None:
        level: LogLevel = "INFO" if status < 400 else ("WARN" if status < 500 else "ERROR")
        self.write(
            level,
            "api",
            f"{method} {path} → {status} ({duration_ms:.0f}ms)",
            method=method,
            path=path,
            status=status,
            duration_ms=round(duration_ms, 1),
            user=user or None,
            error=error_msg,
            traceback=error_traceback,
        )

    def activity(self, action: str, entity_type: str, entity_id: str, actor: str, detail: dict | None = None) -> None:
        self.write(
            "INFO",
            "activity",
            f"{actor}: {action} on {entity_type}/{entity_id}",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            detail=detail,
        )

    # ── Query & Export ──────────────────────────────────────────────

    def list_log_dates(self) -> list[str]:
        """Return available log dates (YYYY-MM-DD), newest first."""
        dates = []
        for f in sorted(self.log_dir.glob("*.jsonl"), reverse=True):
            stem = f.stem
            if len(stem) == 10:
                dates.append(stem)
        return dates

    def query(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        level: str | None = None,
        source: str | None = None,
        keyword: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Query log entries from files. Returns newest first."""
        if not start_date:
            start_date = _today_cst().isoformat()
        if not end_date:
            end_date = start_date

        results: list[dict] = []
        target_dates = self._date_range(start_date, end_date)

        for d in reversed(target_dates):
            file_path = self.log_dir / f"{d}.jsonl"
            if not file_path.exists():
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue

                if level and entry.get("level") != level:
                    continue
                if source and entry.get("source") != source:
                    continue
                if keyword and keyword.lower() not in line.lower():
                    continue

                results.append(entry)
                if len(results) >= limit:
                    return results

        return results

    def export_markdown(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        level: str | None = None,
        keyword: str | None = None,
    ) -> str:
        """Export logs as a readable Markdown document."""
        entries = self.query(start_date=start_date, end_date=end_date, level=level, keyword=keyword, limit=5000)

        if not start_date:
            start_date = _today_cst().isoformat()
        if not end_date:
            end_date = start_date

        lines: list[str] = []
        lines.append(f"# 系统日志导出")
        lines.append(f"")
        lines.append(f"- 日期范围：{start_date} ~ {end_date}")
        lines.append(f"- 条目数量：{len(entries)}")
        if level:
            lines.append(f"- 级别筛选：{level}")
        if keyword:
            lines.append(f"- 关键词：{keyword}")
        lines.append(f"- 导出时间：{_now_cst().isoformat()}")
        lines.append(f"")

        # Stats
        level_counts = {}
        source_counts = {}
        error_entries = []
        for e in entries:
            lv = e.get("level", "INFO")
            level_counts[lv] = level_counts.get(lv, 0) + 1
            src = e.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
            if lv == "ERROR":
                error_entries.append(e)

        lines.append("## 概览")
        lines.append("")
        lines.append(f"| 级别 | 数量 |")
        lines.append(f"|------|------|")
        for lv in ["ERROR", "WARN", "INFO", "DEBUG"]:
            if lv in level_counts:
                lines.append(f"| {lv} | {level_counts[lv]} |")
        lines.append("")

        lines.append(f"| 来源 | 数量 |")
        lines.append(f"|------|------|")
        for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {src} | {cnt} |")
        lines.append("")

        # Errors section (most important for debugging)
        if error_entries:
            lines.append("## 错误详情")
            lines.append("")
            for e in error_entries[:50]:
                ts = e.get("ts", "")
                msg = e.get("message", "")
                lines.append(f"### {ts}")
                lines.append(f"")
                lines.append(f"**{msg}**")
                if e.get("error"):
                    lines.append(f"")
                    lines.append(f"错误信息：`{e['error']}`")
                if e.get("traceback"):
                    lines.append(f"")
                    lines.append(f"```")
                    lines.append(e["traceback"])
                    lines.append(f"```")
                if e.get("path"):
                    lines.append(f"")
                    lines.append(f"- 请求：`{e.get('method', '')} {e['path']}`")
                    lines.append(f"- 状态码：{e.get('status', '')}")
                    lines.append(f"- 耗时：{e.get('duration_ms', '')}ms")
                if e.get("user"):
                    lines.append(f"- 用户：{e['user']}")
                lines.append("")
            lines.append("")

        # Full log
        lines.append("## 完整日志")
        lines.append("")
        lines.append("```")
        for e in entries:
            ts = e.get("ts", "")[11:19]
            lv = e.get("level", "INFO")
            msg = e.get("message", "")
            marker = "🔴" if lv == "ERROR" else "🟡" if lv == "WARN" else "  "
            lines.append(f"{marker} [{ts}] [{lv:5}] {msg}")
        lines.append("```")

        return "\n".join(lines)

    def _date_range(self, start: str, end: str) -> list[str]:
        try:
            s = date.fromisoformat(start)
            e = date.fromisoformat(end)
        except ValueError:
            return [_today_cst().isoformat()]
        result = []
        current = s
        while current <= e:
            result.append(current.isoformat())
            current += timedelta(days=1)
        return result

    def close(self) -> None:
        with self._lock:
            if self._current_file:
                try:
                    self._current_file.close()
                except Exception:
                    pass
                self._current_file = None
