from __future__ import annotations

from time import perf_counter


class DataCenterProfiler:
    def __init__(self) -> None:
        self._started = perf_counter()
        self._last_mark = self._started
        self._stages: dict[str, float] = {}

    def mark(self, name: str) -> None:
        now = perf_counter()
        elapsed_ms = (now - self._last_mark) * 1000.0
        self._stages[name] = round(float(elapsed_ms), 2)
        self._last_mark = now

    def summary(self) -> dict[str, float]:
        total_ms = (perf_counter() - self._started) * 1000.0
        payload = {key: round(float(value), 2) for key, value in self._stages.items()}
        payload["totalMs"] = round(float(total_ms), 2)
        return payload

