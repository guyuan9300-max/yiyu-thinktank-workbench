from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

import httpx


EngineKey = Literal["bettafish", "mirofish"]
DiagnosisScene = Literal["fundraising", "pr", "project"]
DiagnosisAudienceType = Literal["donor", "media", "public", "key_person", "partner", "beneficiary", "staff"]


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _trim_text(value: str, *, limit: int) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _trim_record_list(records: list[dict[str, str]] | None, *, max_items: int, text_limit: int) -> list[dict[str, str]]:
    trimmed: list[dict[str, str]] = []
    for item in (records or [])[:max_items]:
        next_item = {
            "title": _trim_text(item.get("title", ""), limit=min(text_limit, 80)),
            "summary": _trim_text(item.get("summary", ""), limit=text_limit),
        }
        if next_item["title"] or next_item["summary"]:
            trimmed.append(next_item)
    return trimmed


def _extract_payload(data: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = data.get("data")
    if isinstance(nested, Mapping):
        return nested
    nested = data.get("result")
    if isinstance(nested, Mapping):
        return nested
    return data


@dataclass(frozen=True)
class DiagnosisEngineEndpoint:
    engine_key: EngineKey
    enabled: bool
    base_url: str
    analyze_path: str
    health_path: str
    timeout_seconds: float = 8.0
    connect_timeout_seconds: float = 2.0
    max_payload_chars: int = 12000
    max_response_bytes: int = 256 * 1024
    max_context_items: int = 6


@dataclass(frozen=True)
class DiagnosisEngineRequest:
    scene: DiagnosisScene
    audience_type: DiagnosisAudienceType | str
    content: str
    organization_context: dict[str, Any] | None = None
    dna_summary: dict[str, Any] | None = None
    knowledge_refs: list[dict[str, str]] | None = None
    case_refs: list[dict[str, str]] | None = None
    analysis_options: dict[str, Any] | None = None

    def to_payload(self, *, max_payload_chars: int, max_context_items: int) -> dict[str, Any]:
        return {
            "scene": self.scene,
            "audience_type": self.audience_type,
            "content": _trim_text(self.content, limit=max_payload_chars),
            "organization_context": self.organization_context or {},
            "dna_summary": self.dna_summary or {},
            "knowledge_refs": _trim_record_list(self.knowledge_refs, max_items=max_context_items, text_limit=280),
            "case_refs": _trim_record_list(self.case_refs, max_items=max_context_items, text_limit=280),
            "analysis_options": self.analysis_options or {},
        }


@dataclass(frozen=True)
class DiagnosisEngineHealth:
    engine_key: EngineKey
    enabled: bool
    reachable: bool
    status: Literal["disabled", "healthy", "unreachable", "invalid_response"]
    detail: str
    base_url: str
    latency_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BettaFishAnalysis:
    emotion: str | None
    credibility: str | None
    risk_points: list[str]
    misunderstanding_points: list[str]
    raw: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "emotion": self.emotion,
            "credibility": self.credibility,
            "risk_points": self.risk_points,
            "misunderstanding_points": self.misunderstanding_points,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class MiroFishSimulation:
    audiences: list[dict[str, str]]
    scenarios: list[dict[str, str]]
    summary: str | None
    raw: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "audiences": self.audiences,
            "scenarios": self.scenarios,
            "summary": self.summary,
            "raw": dict(self.raw),
        }


class DiagnosisEngineError(RuntimeError):
    pass


def load_diagnosis_engine_endpoints() -> dict[EngineKey, DiagnosisEngineEndpoint]:
    return {
        "bettafish": DiagnosisEngineEndpoint(
            engine_key="bettafish",
            enabled=_env_flag("YIYU_BETTAFISH_ENABLED", False),
            base_url=os.getenv("YIYU_BETTAFISH_BASE_URL", "http://127.0.0.1:18101").strip(),
            analyze_path=os.getenv("YIYU_BETTAFISH_ANALYZE_PATH", "/analyze").strip() or "/analyze",
            health_path=os.getenv("YIYU_BETTAFISH_HEALTH_PATH", "/health").strip() or "/health",
            timeout_seconds=float(os.getenv("YIYU_BETTAFISH_TIMEOUT_SECONDS", "8")),
            connect_timeout_seconds=float(os.getenv("YIYU_BETTAFISH_CONNECT_TIMEOUT_SECONDS", "2")),
            max_payload_chars=int(os.getenv("YIYU_BETTAFISH_MAX_PAYLOAD_CHARS", "12000")),
            max_response_bytes=int(os.getenv("YIYU_BETTAFISH_MAX_RESPONSE_BYTES", str(256 * 1024))),
            max_context_items=int(os.getenv("YIYU_BETTAFISH_MAX_CONTEXT_ITEMS", "6")),
        ),
        "mirofish": DiagnosisEngineEndpoint(
            engine_key="mirofish",
            enabled=_env_flag("YIYU_MIROFISH_ENABLED", False),
            base_url=os.getenv("YIYU_MIROFISH_BASE_URL", "http://127.0.0.1:18102").strip(),
            analyze_path=os.getenv("YIYU_MIROFISH_SIMULATE_PATH", "/simulate").strip() or "/simulate",
            health_path=os.getenv("YIYU_MIROFISH_HEALTH_PATH", "/health").strip() or "/health",
            timeout_seconds=float(os.getenv("YIYU_MIROFISH_TIMEOUT_SECONDS", "20")),
            connect_timeout_seconds=float(os.getenv("YIYU_MIROFISH_CONNECT_TIMEOUT_SECONDS", "2")),
            max_payload_chars=int(os.getenv("YIYU_MIROFISH_MAX_PAYLOAD_CHARS", "12000")),
            max_response_bytes=int(os.getenv("YIYU_MIROFISH_MAX_RESPONSE_BYTES", str(512 * 1024))),
            max_context_items=int(os.getenv("YIYU_MIROFISH_MAX_CONTEXT_ITEMS", "6")),
        ),
    }


class _BaseDiagnosisEngineAdapter:
    def __init__(self, endpoint: DiagnosisEngineEndpoint, *, transport: httpx.BaseTransport | None = None):
        self.endpoint = endpoint
        self.transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.endpoint.base_url,
            timeout=httpx.Timeout(self.endpoint.timeout_seconds, connect=self.endpoint.connect_timeout_seconds),
            transport=self.transport,
            headers={"Content-Type": "application/json"},
        )

    def healthcheck(self) -> DiagnosisEngineHealth:
        if not self.endpoint.enabled:
            return DiagnosisEngineHealth(
                engine_key=self.endpoint.engine_key,
                enabled=False,
                reachable=False,
                status="disabled",
                detail="Engine disabled by configuration",
                base_url=self.endpoint.base_url,
                latency_ms=None,
            )

        started_at = time.perf_counter()
        try:
            with self._client() as client:
                response = client.get(self.endpoint.health_path)
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                if response.status_code >= 400:
                    return DiagnosisEngineHealth(
                        engine_key=self.endpoint.engine_key,
                        enabled=True,
                        reachable=False,
                        status="unreachable",
                        detail=f"HTTP {response.status_code}",
                        base_url=self.endpoint.base_url,
                        latency_ms=latency_ms,
                    )
                try:
                    payload = response.json()
                except json.JSONDecodeError:
                    payload = None
                if payload is not None and not isinstance(payload, Mapping):
                    return DiagnosisEngineHealth(
                        engine_key=self.endpoint.engine_key,
                        enabled=True,
                        reachable=False,
                        status="invalid_response",
                        detail="Health endpoint returned non-object JSON",
                        base_url=self.endpoint.base_url,
                        latency_ms=latency_ms,
                    )
                detail = "ok"
                if isinstance(payload, Mapping):
                    detail = str(payload.get("detail") or payload.get("status") or "ok")
                return DiagnosisEngineHealth(
                    engine_key=self.endpoint.engine_key,
                    enabled=True,
                    reachable=True,
                    status="healthy",
                    detail=detail,
                    base_url=self.endpoint.base_url,
                    latency_ms=latency_ms,
                )
        except httpx.HTTPError as error:
            return DiagnosisEngineHealth(
                engine_key=self.endpoint.engine_key,
                enabled=True,
                reachable=False,
                status="unreachable",
                detail=str(error),
                base_url=self.endpoint.base_url,
                latency_ms=None,
            )

    def _post(self, payload: DiagnosisEngineRequest) -> Mapping[str, Any]:
        if not self.endpoint.enabled:
            raise DiagnosisEngineError(f"{self.endpoint.engine_key} is disabled by configuration")

        normalized_payload = payload.to_payload(
            max_payload_chars=self.endpoint.max_payload_chars,
            max_context_items=self.endpoint.max_context_items,
        )
        with self._client() as client:
            response = client.post(self.endpoint.analyze_path, json=normalized_payload)
            response.raise_for_status()
            response_bytes = len(response.content or b"")
            if response_bytes > self.endpoint.max_response_bytes:
                raise DiagnosisEngineError(
                    f"{self.endpoint.engine_key} response too large: {response_bytes} bytes > {self.endpoint.max_response_bytes}"
                )
            try:
                data = response.json()
            except json.JSONDecodeError as error:
                raise DiagnosisEngineError(f"{self.endpoint.engine_key} returned invalid JSON") from error
        if not isinstance(data, Mapping):
            raise DiagnosisEngineError(f"{self.endpoint.engine_key} returned non-object JSON")
        return _extract_payload(data)


class BettaFishAdapter(_BaseDiagnosisEngineAdapter):
    def analyze(self, payload: DiagnosisEngineRequest) -> BettaFishAnalysis:
        data = self._post(payload)
        risk_points = [
            _trim_text(str(item), limit=180)
            for item in (data.get("risk_points") or data.get("riskPoints") or [])
            if str(item).strip()
        ][:8]
        misunderstanding_points = [
            _trim_text(str(item), limit=180)
            for item in (data.get("misunderstanding_points") or data.get("misunderstandingPoints") or [])
            if str(item).strip()
        ][:8]
        return BettaFishAnalysis(
            emotion=str(data.get("emotion")).strip() if data.get("emotion") else None,
            credibility=str(data.get("credibility")).strip() if data.get("credibility") else None,
            risk_points=risk_points,
            misunderstanding_points=misunderstanding_points,
            raw=data,
        )


class MiroFishAdapter(_BaseDiagnosisEngineAdapter):
    def simulate(self, payload: DiagnosisEngineRequest) -> MiroFishSimulation:
        data = self._post(payload)
        audiences: list[dict[str, str]] = []
        for item in (data.get("audiences") or []):
            if not isinstance(item, Mapping):
                continue
            audiences.append(
                {
                    "role": _trim_text(str(item.get("role", "")), limit=60),
                    "reaction": _trim_text(str(item.get("reaction", "")), limit=240),
                    "risk_level": _trim_text(str(item.get("risk_level") or item.get("riskLevel") or ""), limit=40),
                }
            )
        scenarios: list[dict[str, str]] = []
        for item in (data.get("scenarios") or []):
            if not isinstance(item, Mapping):
                continue
            scenarios.append(
                {
                    "strategy": _trim_text(str(item.get("strategy", "")), limit=80),
                    "outcome": _trim_text(str(item.get("outcome", "")), limit=240),
                }
            )
        return MiroFishSimulation(
            audiences=audiences[:8],
            scenarios=scenarios[:8],
            summary=_trim_text(str(data.get("summary", "")), limit=400) if data.get("summary") else None,
            raw=data,
        )


def collect_diagnosis_engine_health(*, transport: httpx.BaseTransport | None = None) -> list[DiagnosisEngineHealth]:
    endpoints = load_diagnosis_engine_endpoints()
    return [
        BettaFishAdapter(endpoints["bettafish"], transport=transport).healthcheck(),
        MiroFishAdapter(endpoints["mirofish"], transport=transport).healthcheck(),
    ]
