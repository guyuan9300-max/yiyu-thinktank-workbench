"""本地推理调度门控（Phase 0）。

唯一职责：回答「现在能不能跑下一个本地推理任务」。

所有本地模型推理在执行前都过这一道门：
- ★ SoC 温度（macOS sysctl machdep.xcpm.cpu_thermal_state，0-5，>=3 时暂停）
- ★ CPU 是否已降频散热（pmset -g therm CPU_Speed_Limit < 100 时暂停）
- ★ 用户空闲时间（ioreg HIDIdleTime，白天有人用就让位）
- ★ 电池电量 + 是否插电（pmset -g batt）
- ★ macOS 内存压力（memory_pressure 命令）
- ★ Ollama 健康（HTTP /api/tags 探活）

设计原则：
- 跨平台：非 macOS 上硬件类 gate 直接返回 OK，不阻塞
- 无副作用：纯采集 + 决策，不写 DB
- 超时保护：所有子进程 2 秒超时，失败容忍
- 这是基础设施层，不绑定云/本地，云推理也可调（用于失败回退判断）

调用方应当先 `collect_machine_health()`，再 `decide_run(health, ...)`。
"""
from __future__ import annotations

import logging
import platform
import re
import subprocess
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

_IS_MACOS = platform.system() == "Darwin"

# 子进程超时（秒）。所有硬件探活都要快，否则调度延迟会变大
_PROBE_TIMEOUT = 2.0


# ──────────────────────────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MachineHealth:
    """一次性采集到的机器健康快照。-1 / unknown 表示读取失败或当前平台不支持。"""

    thermal_state: int = -1            # 0-5（macOS），-1 = 未知
    cpu_speed_limit: int = 100         # 0-100，100=未限速，<100=已散热降频
    user_idle_seconds: float = -1.0    # macOS HIDIdleTime；-1 = 未知
    battery_percent: int = -1          # 0-100，-1 = 无电池/未知
    on_ac_power: bool = True           # 默认假设插电
    ollama_reachable: bool = True      # 默认假设可达（防止 import 时探活）
    memory_pressure: str = "unknown"   # normal | warn | critical | unknown


@dataclass(frozen=True)
class Decision:
    """门控决策结果。"""

    verdict: Literal["go", "wait", "skip"]
    reason: str = ""
    retry_after_seconds: int = 0


# ──────────────────────────────────────────────────────────────────
# 平台探活
# ──────────────────────────────────────────────────────────────────


def _run_cmd(args: list[str]) -> str:
    """安全跑子进程，超时/失败返回空串。"""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    except Exception as exc:  # noqa: BLE001
        logger.debug("governor probe %s failed: %s", args, exc)
    return ""


def _read_thermal_state() -> int:
    """估计热感等级 0-5。

    Intel Mac：sysctl machdep.xcpm.cpu_thermal_state 直接给出 0-5。
    Apple Silicon：该 sysctl 不存在，回退到 pmset -g therm：
      - "No thermal warning level has been recorded" → 0（凉）
      - 否则保守判 3（已记录热警告）
    其他平台：-1（未知，调用方应跳过此 gate）。

    更精确的散热信号在 cpu_speed_limit；本字段仅作辅助。
    """
    if not _IS_MACOS:
        return -1
    # Intel Mac 路径
    out = _run_cmd(["sysctl", "-n", "machdep.xcpm.cpu_thermal_state"])
    try:
        return int(out.strip())
    except (TypeError, ValueError):
        pass
    # Apple Silicon 回退：pmset -g therm
    therm = _run_cmd(["pmset", "-g", "therm"]).lower()
    if therm:
        if "no thermal warning" in therm:
            return 0
        if "thermal warning level" in therm:
            return 3
    return -1


def _read_cpu_speed_limit() -> int:
    """macOS: pmset -g therm 里 CPU_Speed_Limit。100=未限速。"""
    if not _IS_MACOS:
        return 100
    out = _run_cmd(["pmset", "-g", "therm"])
    match = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", out)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return 100


def _read_idle_seconds() -> float:
    """macOS: ioreg HIDIdleTime（自上次键鼠输入的纳秒）。"""
    if not _IS_MACOS:
        return -1.0
    out = _run_cmd(["ioreg", "-c", "IOHIDSystem"])
    match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
    if match:
        try:
            return int(match.group(1)) / 1_000_000_000
        except ValueError:
            pass
    return -1.0


def _read_battery() -> tuple[int, bool]:
    """macOS: pmset -g batt → (percent, on_ac)。无电池返回 (-1, True)。"""
    if not _IS_MACOS:
        return -1, True
    out = _run_cmd(["pmset", "-g", "batt"])
    if not out:
        return -1, True
    percent_match = re.search(r"(\d+)%", out)
    percent = int(percent_match.group(1)) if percent_match else -1
    on_ac = "AC Power" in out or "charged" in out.lower()
    return percent, on_ac


def _read_memory_pressure() -> str:
    """macOS: 优先解析 memory_pressure 旧文本档位；
    macOS 26+ 新格式只输出统计数字，则用 free pages 比例反推。"""
    if not _IS_MACOS:
        return "unknown"
    out = _run_cmd(["memory_pressure"])
    if not out:
        return "unknown"
    lower = out.lower()
    # 旧格式：含明确档位
    for level in ("critical", "warn", "normal"):
        if f"system-wide memory free percentage" in lower:
            if level in lower:
                return level
        elif f"memory pressure: {level}" in lower:
            return level
    # 新格式：用统计数字算 free 比例
    total_match = re.search(r"\((\d+) pages", out)
    free_match = re.search(r"Pages free:\s*(\d+)", out)
    if total_match and free_match:
        try:
            total = int(total_match.group(1))
            free = int(free_match.group(1))
            if total > 0:
                free_pct = free / total * 100
                if free_pct < 5:
                    return "critical"
                if free_pct < 15:
                    return "warn"
                return "normal"
        except ValueError:
            pass
    return "unknown"


def _check_ollama(base_url: str | None, timeout: float = 1.5) -> bool:
    """探活 Ollama。base_url 为空则不探（兼容用云端 profile 的场景）。"""
    if not base_url:
        return True
    try:
        import httpx  # noqa: PLC0415

        url = base_url.rstrip("/")
        if url.endswith("/v1"):
            url = url[:-3]
        url = url + "/api/tags"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            return resp.status_code == 200
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────
# 公开 API
# ──────────────────────────────────────────────────────────────────


def collect_machine_health(ollama_base_url: str | None = None) -> MachineHealth:
    """一次采集所有指标。~50ms（macOS）/ ~5ms（其他平台）。"""
    percent, on_ac = _read_battery()
    return MachineHealth(
        thermal_state=_read_thermal_state(),
        cpu_speed_limit=_read_cpu_speed_limit(),
        user_idle_seconds=_read_idle_seconds(),
        battery_percent=percent,
        on_ac_power=on_ac,
        ollama_reachable=_check_ollama(ollama_base_url),
        memory_pressure=_read_memory_pressure(),
    )


def decide_run(
    *,
    health: MachineHealth,
    max_thermal_state: int = 3,
    min_idle_seconds: float = 0.0,
    min_battery_percent: int = 30,
    require_ac_power: bool = False,
    require_ollama: bool = True,
) -> Decision:
    """根据硬件健康 + 策略阈值，决定是否能跑下一个任务。

    Args:
        max_thermal_state: 0-5；当前 thermal_state >= 该值时暂停（默认 3）
        min_idle_seconds: 用户连续无输入需达到的秒数（默认 0 = 不强制空闲）
        min_battery_percent: 电池低于此值时暂停（默认 30%）
        require_ac_power: True 时仅插电运行（默认 False）
        require_ollama: True 时 Ollama 不可达就暂停（默认 True）
    """
    # 温度（最重要，先判定）
    if 0 <= health.thermal_state < 99 and health.thermal_state >= max_thermal_state:
        return Decision(
            "wait",
            f"SoC thermal_state={health.thermal_state} ≥ {max_thermal_state}（散热中）",
            retry_after_seconds=120,
        )

    # CPU 已被系统降频（明确散热信号）
    if health.cpu_speed_limit < 100:
        return Decision(
            "wait",
            f"CPU 已限速 {health.cpu_speed_limit}%（系统散热中）",
            retry_after_seconds=120,
        )

    # 内存压力
    if health.memory_pressure == "critical":
        return Decision(
            "wait",
            "内存压力 critical（系统将杀进程）",
            retry_after_seconds=120,
        )

    # 用户活跃中（仅当配置了 min_idle_seconds > 0）
    if min_idle_seconds > 0 and 0 <= health.user_idle_seconds < min_idle_seconds:
        return Decision(
            "wait",
            f"用户活跃中（idle={health.user_idle_seconds:.0f}s < {min_idle_seconds:.0f}s）",
            retry_after_seconds=60,
        )

    # 电源策略
    if require_ac_power and not health.on_ac_power:
        return Decision(
            "wait",
            "未插电（策略要求 AC Power）",
            retry_after_seconds=300,
        )

    if 0 <= health.battery_percent < min_battery_percent:
        return Decision(
            "wait",
            f"电池 {health.battery_percent}% < {min_battery_percent}%",
            retry_after_seconds=300,
        )

    # Ollama 不可达（本地推理无法继续）
    if require_ollama and not health.ollama_reachable:
        return Decision(
            "wait",
            "Ollama 不可达（http://127.0.0.1:11434 探活失败）",
            retry_after_seconds=60,
        )

    return Decision("go")


def health_summary(health: MachineHealth) -> str:
    """单行人话总结，给日志/UI 用。"""
    parts: list[str] = []
    if health.thermal_state >= 0:
        parts.append(f"温度档位 {health.thermal_state}/5")
    if health.cpu_speed_limit < 100:
        parts.append(f"CPU 限速 {health.cpu_speed_limit}%")
    if health.user_idle_seconds >= 0:
        parts.append(f"空闲 {int(health.user_idle_seconds)}s")
    if health.battery_percent >= 0:
        ac_tag = "插电" if health.on_ac_power else "电池"
        parts.append(f"电量 {health.battery_percent}%/{ac_tag}")
    if health.memory_pressure != "unknown":
        parts.append(f"内存 {health.memory_pressure}")
    parts.append("Ollama " + ("✓" if health.ollama_reachable else "✗"))
    return " · ".join(parts)


__all__ = [
    "Decision",
    "MachineHealth",
    "collect_machine_health",
    "decide_run",
    "health_summary",
]
