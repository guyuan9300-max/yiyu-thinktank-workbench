from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from app.db import Database
from app.models import AiStructuredResponse

logger = logging.getLogger(__name__)


# Tier1 优化:LLM 调用瞬时错误判定 — 锁竞争 / 429 / 5xx / 网络抖动都算瞬时,
# 上层加退避重试可大幅降低失败率(尤其是 openclaw session file 锁竞争场景)。
_TRANSIENT_TOKENS = (
    "session file locked",
    "rate limit",
    "too many",
    "timeout",
    "timed out",
    "connection",
    "econnreset",
    "429",
    "502",
    "503",
    "504",
)


def _is_transient_llm_error(message: str) -> bool:
    lowered = (message or "").lower()
    return any(token in lowered for token in _TRANSIENT_TOKENS)


DEFAULT_PROVIDER = "openai_compatible"
OPENAI_COMPATIBLE_PROVIDER = "openai_compatible"
MOCK_PROVIDER = "mock"
OPENCLAW_PROVIDER = "openclaw"
QWEN_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_OPENAI_COMPATIBLE_LABEL = "豆包 Seed 2.0 Pro"
DEFAULT_OPENAI_COMPATIBLE_BASE_URL = DOUBAO_BASE_URL
OPENCLAW_DEFAULT_MODEL = "openai-codex/gpt-5.4"
OPENCLAW_DEFAULT_CLI = "openclaw"
OPENCLAW_DEFAULT_AGENT = "main"
OPENCLAW_STARTUP_OVERHEAD_SECONDS = 30.0
DEFAULT_MODELS = {
    "mock": "mock-summarizer",
    "openai_compatible": "doubao-seed-2-0-pro-260215",
    "qwen": "qwen3.5-plus",
    "doubao": "doubao-seed-2-0-pro-260215",
    "openclaw": OPENCLAW_DEFAULT_MODEL,
}
DEFAULT_MODEL = DEFAULT_MODELS[DEFAULT_PROVIDER]
PROVIDER_LABELS = {
    "qwen": "Qwen 3.5",
    "doubao": "豆包 Seed 2.0 Pro",
    "openai_compatible": DEFAULT_OPENAI_COMPATIBLE_LABEL,
    "mock": "Mock",
    "openclaw": "GPT 5.4",
}
LEGACY_PROVIDER_PRESETS = {
    "qwen": {
        "label": "Qwen 3.5",
        "base_url": QWEN_BASE_URL,
        "model": DEFAULT_MODELS["qwen"],
    },
    "doubao": {
        "label": DEFAULT_OPENAI_COMPATIBLE_LABEL,
        "base_url": DOUBAO_BASE_URL,
        "model": DEFAULT_MODELS["doubao"],
    },
}
HTTP_TIMEOUT_GRACE_SECONDS = 15.0
LOCAL_OPENAI_COMPATIBLE_HOSTS = {"localhost", "127.0.0.1", "::1"}
ADVANCED_AI_ROUTING_SETTING = "settings.advanced_ai_routing_enabled"
AI_MODEL_MODE_SETTING = "settings.ai_model_mode"
AI_MODEL_PROFILES_SETTING = "settings.ai_model_profiles"
AI_MODEL_MODES = {"auto", "online_first", "local_first", "local_only"}
AI_MODEL_PROFILE_KEYS = ("online_primary", "local_text_deep", "local_vision_ocr", "local_fast")
AI_MODEL_PROFILE_SECRET_PREFIX = "ai_profile:"
AI_MODEL_PROFILE_CAPABILITIES = {
    "online_primary": "online_primary",
    "local_text_deep": "deep_analysis",
    "local_vision_ocr": "vision_ocr",
    "local_fast": "fast_structured",
}
AI_TASK_KINDS = {"default", "deep_analysis", "vision_ocr", "fast_structured"}


def llm_display_label(provider: str | None, model: str | None = None, provider_label: str | None = None) -> str:
    provider_value = str(provider or "").strip()
    model_value = str(model or "").strip()
    configured_label = str(provider_label or "").strip()
    if provider_value == "mock":
        return PROVIDER_LABELS["mock"]
    if configured_label:
        return configured_label
    if provider_value == OPENAI_COMPATIBLE_PROVIDER:
        return model_value or PROVIDER_LABELS[OPENAI_COMPATIBLE_PROVIDER]
    if provider_value == "doubao" and (not model_value or model_value == DEFAULT_MODELS["doubao"]):
        return PROVIDER_LABELS["doubao"]
    if provider_value == "qwen" and (not model_value or model_value == DEFAULT_MODELS["qwen"]):
        return PROVIDER_LABELS["qwen"]
    if model_value:
        return model_value
    return PROVIDER_LABELS.get(provider_value, provider_value or "AI")


def classify_llm_error_kind(detail: str | None) -> str:
    text = str(detail or "").strip().lower()
    if not text:
        return "unknown"
    if (
        "ssl" in text
        or "handshake" in text
        or "_ssl.c" in text
    ) and ("timeout" in text or "timed out" in text):
        return "ssl_handshake_timeout"
    if "read timeout" in text or "read operation timed out" in text:
        return "read_timeout"
    if ("connect timeout" in text or "connection timed out" in text) and "read" not in text:
        return "connect_timeout"
    if "401" in text or "unauthorized" in text or "invalid api key" in text or "api key" in text:
        return "auth_error"
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return "rate_limit"
    if "timeout" in text or "timed out" in text:
        return "read_timeout"
    return "unknown"


@dataclass
class AiHealth:
    provider: str
    provider_label: str
    base_url: str
    model: str
    ready: bool
    detail: str
    credential_source: str
    fingerprint: str | None = None
    profile_key: str = "unified"
    mode: str = "auto"


class AiInvocationError(RuntimeError):
    def __init__(self, provider: str, detail: str):
        super().__init__(detail)
        self.provider = provider
        self.detail = detail


@dataclass(frozen=True)
class ChatGenerationProfile:
    primary_context: str
    primary_timeout_seconds: float
    primary_max_tokens: int
    primary_enable_thinking: bool
    fallback_context: str
    fallback_timeout_seconds: float
    fallback_max_tokens: int
    fallback_enable_thinking: bool


@dataclass(frozen=True)
class AiResolvedProfile:
    profile_key: str
    provider: str
    provider_label: str
    base_url: str
    model: str
    api_key: str
    credential_source: str
    fingerprint: str | None
    capability: str
    is_local: bool


class AiService:
    def __init__(self, db: Database, secret_stores: dict[str, object]):
        self.db = db
        self.secret_stores = secret_stores
        self._last_model_snapshot: dict[str, str] = {}
        self._initialize_settings()

    def _initialize_settings(self) -> None:
        provider = self.db.get_setting("ai_provider", "").strip()
        if provider in LEGACY_PROVIDER_PRESETS:
            self._migrate_legacy_provider(provider)
            return
        if provider not in DEFAULT_MODELS:
            provider = DEFAULT_PROVIDER
        self.db.set_setting("ai_provider", provider)
        if not self.db.get_setting("ai_model", ""):
            self.db.set_setting("ai_model", DEFAULT_MODELS.get(provider, DEFAULT_MODEL))
        if provider == OPENAI_COMPATIBLE_PROVIDER:
            self.db.set_setting(
                "ai_provider_label",
                self.db.get_setting("ai_provider_label", DEFAULT_OPENAI_COMPATIBLE_LABEL) or DEFAULT_OPENAI_COMPATIBLE_LABEL,
            )
            self.db.set_setting(
                "ai_base_url",
                self.db.get_setting("ai_base_url", DEFAULT_OPENAI_COMPATIBLE_BASE_URL) or DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
            )

    def _migrate_legacy_provider(self, legacy_provider: str) -> None:
        preset = LEGACY_PROVIDER_PRESETS[legacy_provider]
        self.db.set_setting("ai_provider", OPENAI_COMPATIBLE_PROVIDER)
        self.db.set_setting("ai_provider_label", self.db.get_setting("ai_provider_label", str(preset["label"])) or str(preset["label"]))
        self.db.set_setting("ai_base_url", self.db.get_setting("ai_base_url", str(preset["base_url"])) or str(preset["base_url"]))
        self.db.set_setting("ai_model", self.db.get_setting("ai_model", str(preset["model"])) or str(preset["model"]))
        self._copy_legacy_api_key(legacy_provider)

    def _copy_legacy_api_key(self, legacy_provider: str) -> None:
        target_store = self._store_for(OPENAI_COMPATIBLE_PROVIDER)
        legacy_store = self._store_for(legacy_provider)
        if not target_store or not legacy_store:
            return
        try:
            if str(target_store.get_api_key() or "").strip():
                return
            legacy_key = str(legacy_store.get_api_key() or "").strip()
            if legacy_key:
                target_store.set_api_key(legacy_key)
        except Exception:
            return

    @staticmethod
    def _normalize_bool(value: object, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if not text:
            return default
        return text in {"1", "true", "yes", "on", "enabled"}

    @staticmethod
    def _normalize_model_mode(value: object | None) -> str:
        mode = str(value or "auto").strip()
        return mode if mode in AI_MODEL_MODES else "auto"

    @staticmethod
    def _profile_store_key(profile_key: str) -> str:
        return f"{AI_MODEL_PROFILE_SECRET_PREFIX}{profile_key}"

    def advanced_ai_routing_enabled(self) -> bool:
        return self._normalize_bool(self.db.get_setting(ADVANCED_AI_ROUTING_SETTING, "0"), False)

    def current_ai_model_mode(self) -> str:
        return self._normalize_model_mode(self.db.get_setting(AI_MODEL_MODE_SETTING, "auto"))

    def _read_profile_settings(self) -> dict[str, dict[str, object]]:
        raw = self.db.get_setting(AI_MODEL_PROFILES_SETTING, "")
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {
            str(key): dict(value)
            for key, value in parsed.items()
            if str(key) in AI_MODEL_PROFILE_KEYS and isinstance(value, dict)
        }

    def _normalize_profile_config(self, profile_key: str, payload: dict[str, object] | None) -> dict[str, object]:
        profile = dict(payload or {})
        provider = str(profile.get("provider") or OPENAI_COMPATIBLE_PROVIDER).strip()
        provider = OPENAI_COMPATIBLE_PROVIDER if provider in LEGACY_PROVIDER_PRESETS else provider
        if provider not in DEFAULT_MODELS:
            provider = OPENAI_COMPATIBLE_PROVIDER
        base_url = self._normalize_base_url(str(profile.get("baseUrl") or profile.get("base_url") or ""))
        model = str(profile.get("model") or "").strip()
        provider_label = str(profile.get("providerLabel") or profile.get("provider_label") or "").strip()
        capability = str(profile.get("capability") or AI_MODEL_PROFILE_CAPABILITIES.get(profile_key, "deep_analysis")).strip()
        if capability not in {"online_primary", "deep_analysis", "vision_ocr", "fast_structured"}:
            capability = AI_MODEL_PROFILE_CAPABILITIES.get(profile_key, "deep_analysis")
        return {
            "enabled": self._normalize_bool(profile.get("enabled"), False),
            "provider": provider,
            "providerLabel": provider_label,
            "baseUrl": base_url,
            "model": model,
            "capability": capability,
            "isLocal": self._is_local_base_url(base_url),
        }

    def current_ai_model_profiles(self) -> dict[str, dict[str, object]]:
        settings = self._read_profile_settings()
        return {
            key: self._normalize_profile_config(key, settings.get(key))
            for key in AI_MODEL_PROFILE_KEYS
        }

    def configure_advanced_ai(
        self,
        *,
        advanced_enabled: bool | None = None,
        model_mode: str | None = None,
        profiles: dict[str, object] | None = None,
        profile_api_keys: dict[str, str] | None = None,
        clear_profile_api_keys: list[str] | None = None,
    ) -> None:
        if advanced_enabled is not None:
            self.db.set_setting(ADVANCED_AI_ROUTING_SETTING, "1" if bool(advanced_enabled) else "0")
        if model_mode is not None:
            self.db.set_setting(AI_MODEL_MODE_SETTING, self._normalize_model_mode(model_mode))
        if profiles is not None:
            current = self.current_ai_model_profiles()
            for key, value in profiles.items():
                profile_key = str(key)
                if profile_key not in AI_MODEL_PROFILE_KEYS or not isinstance(value, dict):
                    continue
                current[profile_key] = self._normalize_profile_config(profile_key, value)
            self.db.set_setting(AI_MODEL_PROFILES_SETTING, json.dumps(current, ensure_ascii=False))
        for key in clear_profile_api_keys or []:
            store = self._store_for(self._profile_store_key(str(key)))
            if store:
                store.delete_api_key()
        for key, value in (profile_api_keys or {}).items():
            profile_key = str(key)
            if profile_key not in AI_MODEL_PROFILE_KEYS:
                continue
            clean_key = str(value or "").strip()
            if not clean_key:
                continue
            store = self._store_for(self._profile_store_key(profile_key))
            if store:
                store.set_api_key(clean_key)

    def configure_cloud_online_profile(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        provider_label: str | None = None,
        base_url: str | None = None,
    ) -> None:
        profile = {
            "enabled": True,
            "provider": provider or OPENAI_COMPATIBLE_PROVIDER,
            "providerLabel": provider_label or "线上主模型",
            "baseUrl": base_url or "",
            "model": model or "",
            "capability": "online_primary",
        }
        self.configure_advanced_ai(
            profiles={"online_primary": profile},
            profile_api_keys={"online_primary": api_key} if api_key else None,
        )

    def current_provider(self) -> str:
        provider = self.db.get_setting("ai_provider", DEFAULT_PROVIDER)
        return provider if provider in DEFAULT_MODELS else DEFAULT_PROVIDER

    def current_provider_label(self) -> str:
        provider = self.current_provider()
        if provider == OPENAI_COMPATIBLE_PROVIDER:
            return self.db.get_setting("ai_provider_label", DEFAULT_OPENAI_COMPATIBLE_LABEL) or DEFAULT_OPENAI_COMPATIBLE_LABEL
        return PROVIDER_LABELS.get(provider, provider or "AI")

    def current_base_url(self) -> str:
        provider = self.current_provider()
        if provider == OPENAI_COMPATIBLE_PROVIDER:
            return self._normalize_base_url(self.db.get_setting("ai_base_url", ""))
        if provider in LEGACY_PROVIDER_PRESETS:
            return str(LEGACY_PROVIDER_PRESETS[provider]["base_url"])
        return ""

    def current_model(self) -> str:
        model = self.db.get_setting("ai_model", "")
        return model or DEFAULT_MODELS[self.current_provider()]

    def current_model_label(self) -> str:
        return llm_display_label(self.current_provider(), self.current_model(), self.current_provider_label())

    def export_current_api_key(self) -> str:
        """Return the active API key for the current provider.

        Intended for trusted local callers that need to forward the key to a
        cloud sync endpoint (e.g. admin pushing org AI config). Must never be
        returned through a public HTTP response or logged.
        """
        store = self._store_for(self.current_provider())
        if not store:
            return ""
        return str(store.get_api_key() or "").strip()

    def model_label(self, provider: str | None = None, model: str | None = None) -> str:
        target_provider = provider or self.current_provider()
        target_model = model or (
            self.current_model() if target_provider == self.current_provider() else DEFAULT_MODELS.get(target_provider, DEFAULT_MODEL)
        )
        configured_label = self.current_provider_label() if target_provider == self.current_provider() else None
        return llm_display_label(target_provider, target_model, configured_label)

    @staticmethod
    def _normalize_base_url(value: str | None) -> str:
        return str(value or "").strip().rstrip("/")

    @classmethod
    def _is_local_base_url(cls, value: str | None) -> bool:
        base_url = cls._normalize_base_url(value)
        if not base_url:
            return False
        candidate = base_url if "://" in base_url else f"http://{base_url}"
        try:
            parsed = urlparse(candidate)
        except Exception:
            return False
        return str(parsed.hostname or "").strip().lower() in LOCAL_OPENAI_COMPATIBLE_HOSTS

    @staticmethod
    def _build_openai_compatible_headers(api_key: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        clean_key = str(api_key or "").strip()
        if clean_key:
            headers["Authorization"] = f"Bearer {clean_key}"
        return headers

    def configure(
        self,
        provider: str | None,
        model: str | None,
        api_key: str | None,
        clear_api_key: bool,
        *,
        provider_label: str | None = None,
        base_url: str | None = None,
    ) -> None:
        raw_provider = (provider or self.current_provider()).strip()
        target_provider = OPENAI_COMPATIBLE_PROVIDER if raw_provider in LEGACY_PROVIDER_PRESETS else raw_provider
        if target_provider not in DEFAULT_MODELS:
            target_provider = DEFAULT_PROVIDER
        if provider:
            self.db.set_setting("ai_provider", target_provider)
            if not model:
                self.db.set_setting("ai_model", DEFAULT_MODELS[target_provider])
        if model is not None:
            self.db.set_setting("ai_model", model.strip())
        if target_provider == OPENAI_COMPATIBLE_PROVIDER:
            if raw_provider in LEGACY_PROVIDER_PRESETS:
                preset = LEGACY_PROVIDER_PRESETS[raw_provider]
                if provider_label is None:
                    provider_label = str(preset["label"])
                if base_url is None:
                    base_url = str(preset["base_url"])
            if provider_label is not None:
                self.db.set_setting("ai_provider_label", provider_label.strip())
            elif provider:
                self.db.set_setting(
                    "ai_provider_label",
                    self.db.get_setting("ai_provider_label", DEFAULT_OPENAI_COMPATIBLE_LABEL) or DEFAULT_OPENAI_COMPATIBLE_LABEL,
                )
            if base_url is not None:
                self.db.set_setting("ai_base_url", self._normalize_base_url(base_url))
            elif provider:
                self.db.set_setting(
                    "ai_base_url",
                    self.db.get_setting("ai_base_url", DEFAULT_OPENAI_COMPATIBLE_BASE_URL) or DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
                )
        store = self._store_for(target_provider)
        if clear_api_key and store:
            store.delete_api_key()
        if api_key and store:
            store.set_api_key(api_key)

    def _unified_profile(self) -> AiResolvedProfile:
        provider = self.current_provider()
        model = self.current_model()
        provider_label = self.current_provider_label()
        base_url = self.current_base_url()
        store = self._store_for(provider)
        api_key = store.get_api_key() if store else ""
        return AiResolvedProfile(
            profile_key="unified",
            provider=provider,
            provider_label=provider_label,
            base_url=base_url,
            model=model,
            api_key=api_key,
            credential_source=store.get_source_label() if store else "unavailable",
            fingerprint=store.get_api_key_fingerprint() if store else None,
            capability="default",
            is_local=self._is_local_base_url(base_url),
        )

    def _profile_from_config(self, profile_key: str, profile: dict[str, object]) -> AiResolvedProfile | None:
        normalized = self._normalize_profile_config(profile_key, profile)
        if not bool(normalized.get("enabled")):
            return None
        provider = str(normalized.get("provider") or OPENAI_COMPATIBLE_PROVIDER)
        base_url = str(normalized.get("baseUrl") or "")
        model = str(normalized.get("model") or "")
        provider_label = str(normalized.get("providerLabel") or "")
        store = self._store_for(self._profile_store_key(profile_key))
        api_key = store.get_api_key() if store else ""
        return AiResolvedProfile(
            profile_key=profile_key,
            provider=provider,
            provider_label=provider_label,
            base_url=base_url,
            model=model,
            api_key=api_key,
            credential_source=store.get_source_label() if store else "unavailable",
            fingerprint=store.get_api_key_fingerprint() if store else None,
            capability=str(normalized.get("capability") or AI_MODEL_PROFILE_CAPABILITIES.get(profile_key, "default")),
            is_local=bool(normalized.get("isLocal")) or self._is_local_base_url(base_url),
        )

    def _resolve_deep_read_local_candidate(self) -> "AiResolvedProfile | None":
        """深度解析「本地」档：直接构造 local_text_deep 解析 profile（qwen3-vl:32b），
        忽略 advanced-routing 的 enabled 门——用户在解析卡里显式选「本地」本身就是启用信号，
        不要求他再去高级路由里把 profile enable。无 baseUrl/model 时返回 None（调用方回退主模型）。"""
        cfg = self.current_ai_model_profiles().get("local_text_deep") or {}
        normalized = self._normalize_profile_config("local_text_deep", cfg)
        base_url = str(normalized.get("baseUrl") or "")
        model = str(normalized.get("model") or "")
        if not base_url or not model:
            return None
        store = self._store_for(self._profile_store_key("local_text_deep"))
        return AiResolvedProfile(
            profile_key="local_text_deep",
            provider=str(normalized.get("provider") or OPENAI_COMPATIBLE_PROVIDER),
            provider_label=str(normalized.get("providerLabel") or ""),
            base_url=base_url,
            model=model,
            api_key=store.get_api_key() if store else "",
            credential_source=store.get_source_label() if store else "local",
            fingerprint=store.get_api_key_fingerprint() if store else None,
            capability="deep_analysis",
            is_local=bool(normalized.get("isLocal")) or self._is_local_base_url(base_url),
        )

    def _profile_is_usable(self, profile: AiResolvedProfile) -> bool:
        if profile.provider == MOCK_PROVIDER:
            return True
        if not profile.base_url or not profile.model:
            return False
        if profile.api_key:
            return True
        return profile.is_local

    def _profile_to_health(self, profile: AiResolvedProfile) -> AiHealth:
        label = llm_display_label(profile.provider, profile.model, profile.provider_label)
        if profile.provider == MOCK_PROVIDER:
            return AiHealth(
                provider=profile.provider,
                provider_label=profile.provider_label or PROVIDER_LABELS["mock"],
                base_url="",
                model=profile.model or DEFAULT_MODELS["mock"],
                ready=True,
                detail="本地 Mock 模式可用于流程联调，不调用真实模型。",
                credential_source="local",
                fingerprint=None,
                profile_key=profile.profile_key,
                mode=self.current_ai_model_mode(),
            )
        if not profile.base_url:
            detail = f"{label} 接口地址 Base URL 未配置，无法调用兼容接口。"
            ready = False
        elif not profile.model:
            detail = f"{label} 模型名未配置，无法调用兼容接口。"
            ready = False
        elif not profile.api_key and not profile.is_local:
            detail = f"{label} API Key 未配置，无法调用兼容接口。"
            ready = False
        elif not profile.api_key:
            detail = f"{label} 本地接口已配置，可用于结构化问答与分析。"
            ready = True
        else:
            detail = f"{label} 凭证已配置，可用于结构化问答与分析。"
            ready = True
        return AiHealth(
            provider=profile.provider,
            provider_label=profile.provider_label,
            base_url=profile.base_url,
            model=profile.model,
            ready=ready,
            detail=detail,
            credential_source=("local" if profile.is_local and not profile.api_key else profile.credential_source),
            fingerprint=profile.fingerprint,
            profile_key=profile.profile_key,
            mode=self.current_ai_model_mode(),
        )

    def _ordered_profile_keys_for_task(self, task_kind: str) -> list[str]:
        mode = self.current_ai_model_mode()
        if mode == "auto":
            mode = "online_first"
        online_then_local = ["online_primary", "local_text_deep"]
        local_then_online = ["local_text_deep", "online_primary"]
        if task_kind == "vision_ocr":
            return ["local_vision_ocr", "local_text_deep", "online_primary"]
        if task_kind == "fast_structured":
            base = local_then_online if mode in {"local_first", "local_only"} else online_then_local
            return ["local_fast"] + base
        if task_kind == "deep_analysis":
            return local_then_online if mode in {"local_first", "local_only"} else online_then_local
        return local_then_online if mode in {"local_first", "local_only"} else online_then_local

    def _resolve_llm_candidates(
        self,
        *,
        task_kind: str = "default",
        provider_override: str | None = None,
        model_override: str | None = None,
    ) -> list[AiResolvedProfile]:
        normalized_task = task_kind if task_kind in AI_TASK_KINDS else "default"
        if provider_override is not None or model_override is not None:
            profile = self._unified_profile()
            requested_provider = provider_override or profile.provider
            provider = OPENAI_COMPATIBLE_PROVIDER if requested_provider in LEGACY_PROVIDER_PRESETS else requested_provider
            if provider not in DEFAULT_MODELS:
                provider = profile.provider
            model = model_override or (profile.model if provider == profile.provider else DEFAULT_MODELS.get(provider, DEFAULT_MODEL))
            if provider == profile.provider:
                base_url = profile.base_url
                provider_label = profile.provider_label
                api_key = profile.api_key
                source = profile.credential_source
                fingerprint = profile.fingerprint
            else:
                preset = LEGACY_PROVIDER_PRESETS.get(requested_provider or "")
                base_url = str(preset["base_url"]) if preset else ""
                provider_label = str(preset["label"]) if preset else llm_display_label(provider, model)
                store = self._store_for(provider)
                api_key = store.get_api_key() if store else ""
                source = store.get_source_label() if store else "unavailable"
                fingerprint = store.get_api_key_fingerprint() if store else None
            resolved = AiResolvedProfile(
                profile_key="override",
                provider=provider,
                provider_label=provider_label,
                base_url=self._normalize_base_url(base_url),
                model=model,
                api_key=api_key,
                credential_source=source,
                fingerprint=fingerprint,
                capability=normalized_task,
                is_local=self._is_local_base_url(base_url),
            )
            if self.current_ai_model_mode() == "local_only" and not resolved.is_local and resolved.provider != MOCK_PROVIDER:
                return []
            return [resolved]
        mode = self.current_ai_model_mode()
        if not self.advanced_ai_routing_enabled():
            return [self._unified_profile()]
        settings = self.current_ai_model_profiles()
        candidates: list[AiResolvedProfile] = []
        seen: set[str] = set()
        for key in self._ordered_profile_keys_for_task(normalized_task):
            if key in seen:
                continue
            seen.add(key)
            profile = self._profile_from_config(key, settings.get(key, {}))
            if profile is None:
                continue
            if mode == "local_only" and not profile.is_local:
                continue
            candidates.append(profile)
        unified = self._unified_profile()
        if mode != "local_only" or unified.is_local or unified.provider == MOCK_PROVIDER:
            candidates.append(unified)
        return candidates

    def get_health(self, *, task_kind: str = "default") -> AiHealth:
        if self.current_provider() == OPENCLAW_PROVIDER:
            return self._openclaw_health()
        candidates = self._resolve_llm_candidates(task_kind=task_kind)
        if not candidates:
            unified = self._unified_profile()
            return AiHealth(
                provider=unified.provider,
                provider_label=unified.provider_label,
                base_url=unified.base_url,
                model=unified.model,
                ready=False,
                detail="仅本地模式已启用，但没有可用的本地模型 profile。",
                credential_source=unified.credential_source,
                fingerprint=unified.fingerprint,
                profile_key="unavailable",
                mode=self.current_ai_model_mode(),
            )
        profile = next((item for item in candidates if self._profile_is_usable(item)), candidates[0])
        return self._profile_to_health(profile)

    def _health_for_task(self, task_kind: str) -> AiHealth:
        try:
            return self.get_health(task_kind=task_kind)
        except TypeError:
            # Some focused tests monkeypatch get_health() with a zero-arg stub.
            return self.get_health()

    def get_profile_health_map(self) -> dict[str, AiHealth]:
        profiles = {"unified": self._unified_profile()}
        for key, value in self.current_ai_model_profiles().items():
            profile = self._profile_from_config(key, value)
            if profile is not None:
                profiles[key] = profile
        return {key: self._profile_to_health(profile) for key, profile in profiles.items()}

    def resolved_model_snapshot(self, *, task_kind: str = "default") -> dict[str, str]:
        health = self._health_for_task(task_kind)
        return {
            "profileKey": health.profile_key,
            "provider": health.provider,
            "model": health.model,
            "modelLabel": llm_display_label(health.provider, health.model, health.provider_label),
            "mode": health.mode,
        }

    def _record_resolved_profile(self, profile: AiResolvedProfile) -> None:
        self._last_model_snapshot = {
            "profileKey": profile.profile_key,
            "provider": profile.provider,
            "model": profile.model,
            "modelLabel": llm_display_label(profile.provider, profile.model, profile.provider_label),
            "mode": self.current_ai_model_mode(),
        }

    def last_model_snapshot(self) -> dict[str, str]:
        return dict(self._last_model_snapshot)

    def reset_last_model_snapshot(self) -> None:
        self._last_model_snapshot = {}

    def test_connection(self) -> AiHealth:
        health = self.get_health()
        if health.provider == "mock" or not health.ready:
            return health
        self._qwen_generate(
            prompt="请用一句中文确认连接成功。",
            system_instruction="你是系统健康检查助手。只返回纯文本。",
            response_schema=None,
        )
        return AiHealth(
            provider=health.provider,
            provider_label=health.provider_label,
            base_url=health.base_url,
            model=health.model,
            ready=True,
            detail=f"{llm_display_label(health.provider, health.model, health.provider_label)} 联通测试成功。",
            credential_source=health.credential_source,
            fingerprint=health.fingerprint,
            profile_key=health.profile_key,
            mode=health.mode,
        )

    def healthcheck(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        prompt: str | None = None,
    ) -> dict[str, object]:
        requested_provider = provider or self.current_provider()
        target_provider = OPENAI_COMPATIBLE_PROVIDER if requested_provider in LEGACY_PROVIDER_PRESETS else requested_provider
        if target_provider not in DEFAULT_MODELS:
            target_provider = self.current_provider()
        target_model = model or (
            self.current_model() if target_provider == self.current_provider() else DEFAULT_MODELS[target_provider]
        )
        target_label = self.current_provider_label() if target_provider == self.current_provider() else (
            str(LEGACY_PROVIDER_PRESETS[requested_provider]["label"]) if requested_provider in LEGACY_PROVIDER_PRESETS else None
        )
        start = perf_counter()
        if target_provider == "mock":
            return {
                "provider": target_provider,
                "model": target_model,
                "providerLabel": PROVIDER_LABELS["mock"],
                "baseUrl": "",
                "success": True,
                "latencyMs": 0,
                "error": None,
                "errorKind": None,
            }
        if target_provider == OPENCLAW_PROVIDER:
            cli_path = self._openclaw_cli_path()
            resolved = shutil.which(cli_path) if not cli_path.startswith("/") else cli_path
            if not resolved:
                return {
                    "provider": target_provider,
                    "model": target_model,
                    "providerLabel": PROVIDER_LABELS["openclaw"],
                    "baseUrl": "",
                    "success": False,
                    "latencyMs": 0,
                    "error": f"未检测到本机 OpenClaw CLI（命令：{cli_path}）。",
                    "errorKind": "auth_error",
                }
            try:
                self._qwen_generate(
                    prompt=(prompt or "请只回复：连接成功。"),
                    system_instruction="你是系统健康检查助手。只返回纯文本。",
                    response_schema=None,
                    timeout_seconds=90.0,
                    max_tokens=60,
                    temperature=0.0,
                    top_p=1.0,
                    enable_thinking=False,
                    provider_override=target_provider,
                    model_override=target_model,
                )
                return {
                    "provider": target_provider,
                    "model": target_model,
                    "providerLabel": PROVIDER_LABELS["openclaw"],
                    "baseUrl": "",
                    "success": True,
                    "latencyMs": int(round((perf_counter() - start) * 1000)),
                    "error": None,
                    "errorKind": None,
                }
            except Exception as error:
                detail = str(getattr(error, "detail", error) or "").strip() or str(error)
                return {
                    "provider": target_provider,
                    "model": target_model,
                    "providerLabel": PROVIDER_LABELS["openclaw"],
                    "baseUrl": "",
                    "success": False,
                    "latencyMs": int(round((perf_counter() - start) * 1000)),
                    "error": detail,
                    "errorKind": classify_llm_error_kind(detail),
                }
        target_base_url = self.current_base_url() if target_provider == self.current_provider() else (
            str(LEGACY_PROVIDER_PRESETS[requested_provider]["base_url"]) if requested_provider in LEGACY_PROVIDER_PRESETS else ""
        )
        if not target_base_url:
            return {
                "provider": target_provider,
                "model": target_model,
                "providerLabel": target_label or llm_display_label(target_provider, target_model),
                "baseUrl": target_base_url,
                "success": False,
                "latencyMs": 0,
                "error": f"{llm_display_label(target_provider, target_model, target_label)} 接口地址 Base URL 未配置。",
                "errorKind": "config_error",
            }
        store = self._store_for(target_provider)
        api_key = store.get_api_key() if store else ""
        if not api_key and not self._is_local_base_url(target_base_url):
            return {
                "provider": target_provider,
                "model": target_model,
                "providerLabel": target_label or llm_display_label(target_provider, target_model),
                "baseUrl": target_base_url,
                "success": False,
                "latencyMs": 0,
                "error": f"{llm_display_label(target_provider, target_model, target_label)} API Key 未配置。",
                "errorKind": "auth_error",
            }
        try:
            self._qwen_generate(
                prompt=(prompt or "请只回复：连接成功。"),
                system_instruction="你是系统健康检查助手。只返回纯文本。",
                response_schema=None,
                timeout_seconds=12.0,
                max_tokens=60,
                temperature=0.0,
                top_p=1.0,
                enable_thinking=False,
                provider_override=target_provider,
                model_override=target_model,
            )
            return {
                "provider": target_provider,
                "model": target_model,
                "providerLabel": target_label or llm_display_label(target_provider, target_model),
                "baseUrl": target_base_url,
                "success": True,
                "latencyMs": int(round((perf_counter() - start) * 1000)),
                "error": None,
                "errorKind": None,
            }
        except Exception as error:
            detail = str(getattr(error, "detail", error) or "").strip() or str(error)
            return {
                "provider": target_provider,
                "model": target_model,
                "providerLabel": target_label or llm_display_label(target_provider, target_model),
                "baseUrl": target_base_url,
                "success": False,
                "latencyMs": int(round((perf_counter() - start) * 1000)),
                "error": detail,
                "errorKind": classify_llm_error_kind(detail),
            }

    def provider_probe(
        self,
        *,
        client_id: str | None = None,
        providers: list[str] | None = None,
        prompt: str | None = None,
    ) -> dict[str, object]:
        ordered_providers: list[str] = []
        for item in (providers or [self.current_provider()]):
            provider_name = str(item or "").strip()
            if provider_name in DEFAULT_MODELS and provider_name not in ordered_providers:
                ordered_providers.append(provider_name)
        if not ordered_providers:
            ordered_providers = [self.current_provider()]
        return {
            "clientId": client_id,
            "prompt": prompt or "请只回复：连接成功。",
            "generatedAt": datetime.now().replace(microsecond=0).isoformat(),
            "results": [
                self.healthcheck(provider=provider_name, prompt=prompt)
                for provider_name in ordered_providers
            ],
        }

    def generate_structured(self, prompt: str, system_instruction: str, context_summary: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider != "mock" and health.ready:
            return self._qwen_generate_structured_with_retry(prompt, system_instruction, context_summary)
        return self._mock_generate(prompt, context_summary)

    def generate_general_fallback(self, prompt: str, note: str = "", *, subject_name: str = "") -> AiStructuredResponse:
        health = self.get_health()
        if health.provider != "mock" and health.ready:
            try:
                return self._qwen_generate_general_fallback(prompt, note, subject_name=subject_name)
            except Exception:
                subject_hint = f"{subject_name} 的通用背景初步判断。" if subject_name else "当前问题的通用背景初步判断。"
                background_note = (
                    f"{subject_hint} "
                    + (
                        note.strip()
                        if note and note.strip()
                        else "当前没有命中足够的原始材料，以下只保留保守、非正式的背景判断。"
                    )
                )
                return self._mock_generate(prompt, background_note)
        return self._mock_generate(prompt, note or "当前资料回答阶段失败，以下为本地保守兜底判断。")

    def generate_workspace_state_response(
        self,
        prompt: str,
        state_context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        health = self.get_health()
        compact_context = self._compact_context_summary(state_context_summary, max_chars=2600)
        if health.provider != "mock" and health.ready:
            if on_partial is not None:
                opening = "正在优先整理客户状态池，先生成一版边界清晰的结构化状态回答。"
                on_partial(
                    {
                        "stageLabel": "正在生成状态回答",
                        "progress": 54.0,
                        "content": opening,
                        "structured": {
                            "content": opening,
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            instruction = (
                "你是益语智库的客户状态顾问。"
                "请优先基于客户状态池直接回答，不要退回成资料摘要。"
                "回答必须明确区分：正式判断、待确认判断、本周动作、风险提醒、缺失信息。"
                "candidate、risk、unknown 不能改写成已证实事实。"
                "不要解释系统过程，不要输出 JSON，不要输出 Markdown 代码块。"
                "先求稳定、清楚、可执行，再求长。"
            )
            prompt_text = (
                f"用户问题：{prompt}\n\n"
                f"客户状态池：\n{compact_context or state_context_summary}\n\n"
                "请直接给出一版可展示的状态回答。"
            )
            first_error: Exception | None = None
            try:
                text = self._qwen_generate(
                    prompt=prompt_text,
                    system_instruction=instruction,
                    response_schema=None,
                    timeout_seconds=14.0,
                    max_tokens=1400,
                    temperature=0.22,
                    top_p=0.88,
                    enable_thinking=False,
                )
                return self._structured_from_plain_answer(str(text))
            except Exception as error:
                first_error = error
            retry_context = self._compact_context_summary(state_context_summary, max_chars=1600)
            try:
                text = self._qwen_generate(
                    prompt=(
                        f"用户问题：{prompt}\n\n"
                        f"客户状态池：\n{retry_context or compact_context or state_context_summary}\n\n"
                        "请只保留最重要的状态判断和下一步动作，直接回答。"
                    ),
                    system_instruction=instruction,
                    response_schema=None,
                    timeout_seconds=10.0,
                    max_tokens=900,
                    temperature=0.18,
                    top_p=0.85,
                    enable_thinking=False,
                )
                return self._structured_from_plain_answer(str(text))
            except Exception as retry_error:
                detail = "；".join(
                    part
                    for part in (
                        f"状态回答主调用失败：{self._format_provider_error(first_error)}" if first_error else "",
                        f"状态回答紧凑重试失败：{self._format_provider_error(retry_error)}",
                    )
                    if part
                )
                raise AiInvocationError(health.provider, detail) from retry_error
        return self._mock_generate(prompt, compact_context or state_context_summary)

    def generate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        health = self._health_for_task("deep_analysis")
        if health.provider != "mock" and health.ready:
            provider = health.provider
            chat_profile = self._build_chat_generation_profile(context_summary)
            if on_partial is not None:
                opening = "正在围绕核心判断、关键张力和潜在风险整合原始证据，准备输出连续长文分析。"
                on_partial(
                    {
                        "stageLabel": "正在整合长文分析",
                        "progress": 58.0,
                        "content": opening,
                        "structured": {
                            "content": opening,
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            try:
                return self._qwen_generate_chat_response(
                    prompt,
                    system_instruction,
                    chat_profile.primary_context,
                    timeout_seconds=chat_profile.primary_timeout_seconds,
                    max_tokens=chat_profile.primary_max_tokens,
                    enable_thinking=chat_profile.primary_enable_thinking,
                    on_partial=on_partial,
                )
            except Exception as error:
                primary_error = error
                try:
                    return self._qwen_generate_textual_fallback(
                        prompt,
                        system_instruction,
                        chat_profile.fallback_context or chat_profile.primary_context or context_summary,
                        timeout_seconds=chat_profile.fallback_timeout_seconds,
                        max_tokens=chat_profile.fallback_max_tokens,
                        enable_thinking=chat_profile.fallback_enable_thinking,
                    )
                except Exception as retry_error:
                    detail = "；".join(
                        part
                        for part in (
                            f"主长文生成失败：{self._format_provider_error(primary_error)}",
                            f"快速兜底失败：{self._format_provider_error(retry_error)}",
                        )
                        if part
                    )
                    raise AiInvocationError(provider, detail) from retry_error
        return self._mock_generate(prompt, context_summary)

    def generate_raw_evidence_response(
        self,
        prompt: str,
        system_instruction: str,
        raw_evidence_pack: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
        timeout_seconds: float = 300.0,
        max_tokens: int = 3000,
        enable_thinking: bool = True,
        strategic_pack: str = "",
        depth_mode: bool = False,
        writing_skill_md: str = "",
        creativity_mode: str = "strict",
        task_mode: bool = False,
    ) -> AiStructuredResponse:
        """Generate a structured answer from a raw evidence pack via single LLM call.

        ``strategic_pack``: 可选的"战略素材包"（组织 DNA / 已采纳判断 / 项目演进 / 历史 chat 沉淀），
        非空时拼到 raw_evidence_pack 前面作为前置高亮，让单次调用也能扎进战略层判断。
        ``depth_mode``: 普通问答（False）控制在 600-1200 字；深度问答（True）展开到 1500-2500 字，
        并强制要求挖具体项目名、数字、时间节点。
        """
        health = self._health_for_task("deep_analysis")
        if health.provider != "mock" and health.ready:
            if on_partial is not None:
                opening = "模型正在直接阅读原始文档资料包并生成回答。"
                on_partial(
                    {
                        "stageLabel": "正在读取原始文档资料并生成回答",
                        "progress": 62.0,
                        "content": opening,
                        "structured": {
                            "content": opening,
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            length_rule = (
                "7. 全文控制在 1500-2500 字之间。普通回答也要有内容深度，不要为了短而短；"
                "写不出来的部分直接说「资料中未见」，不要套通用模板。"
                if depth_mode
                else "7. 全文控制在 600～1200 字之间，宁缺毋滥；"
                "写不出来的部分直接说「资料中未见」，不要套通用模板。"
            )
            detail_rule = (
                "10. 必须落到具体的项目名（如「心灵魔法学院」「心盛计划」「繁星计划」）、"
                "合作方、活动名、关键数字、时间节点、人物角色——这些细节都在战略素材或原始资料里，"
                "必须主动挖出来，不要满足于在画像层面做抽象总结。\n"
                if depth_mode
                else ""
            )
            style_prefix = ""
            if (writing_skill_md or "").strip():
                style_prefix = (
                    "【写作风格约束 —— 必须遵守，优先级最高】\n"
                    f"{writing_skill_md.strip()}\n"
                    "【写作风格约束结束】\n\n"
                    "下面是常规的角色和段落写作规范，与上面的风格约束冲突时以风格约束为准（除事实准确性外）。\n\n"
                )
            # R8：任务型 prompt 强制结构化输出（R8.13 缩短至 ~700 字降低 prompt 长度）
            task_prefix = ""
            if task_mode:
                task_prefix = (
                    "【任务执行模式】\n"
                    "用户在要一个**具体产物**（表/列表/草稿）。**直接产出这个产物**，禁止写「数据源说明 / 字段提取规则 / 待补全场景说明 / 优化建议 / 更新机制」之类的方法论文档。\n"
                    "\n"
                    "## 客户资源索引的使用（R9 关键）\n"
                    "如果资料中出现「客户资源索引 · 全集元数据视图」段，里面覆盖 5 个域：\n"
                    "- **文档（documents）**：客户全部已上传文件的目录\n"
                    "- **项目模块（projectModules）**：客户的项目列表\n"
                    "- **已采纳判断（latestJudgments）**：客户已被确认的判断\n"
                    "- **会议（meetings）**：客户的会议历史\n"
                    "- **目标（goals）**：客户的目标清单\n"
                    "\n"
                    "**核心规则**：当用户要求「列出所有 X」「做一张包含全部 Y 的表」「客户有几个 Z」时：\n"
                    "1. 先看资源索引对应域有多少条目，**索引覆盖客户全集**（不是检索 top-K 命中）\n"
                    "2. **必须列出索引里所有相关条目**，不要只挑检索命中的前几条\n"
                    "3. 文档域的文件名通常含结构化信息（如「姓名-岗位-日期.pdf」），可以从文件名直接解析字段，**不需要等检索命中文件内容**\n"
                    "4. 索引里的条目都是真实存在的资源，可以放心引用\n"
                    "5. 索引提供全集元数据；需要内容细节时再依赖下面的检索命中片段\n"
                    "\n"
                    "## 表格格式硬约束（违反 = 前端不渲染）\n"
                    "1. 每行 `| ... |` **独立一行**（行尾换行符），禁止全塞一行\n"
                    "2. **表格行之间不允许空行**，header / 分隔行 / 数据行必须紧邻\n"
                    "3. **禁止用 ``` 包裹表格**（不要写 ```markdown ... ``` 这种），裸 markdown 直接输出\n"
                    "4. 所有列填充，缺失填「待补全」\n"
                    "\n"
                    "正确格式（裸 markdown）：\n"
                    "| 序号 | 姓名 | 岗位 |\n"
                    "| --- | --- | --- |\n"
                    "| 1 | 张三 | 顾问 |\n"
                    "| 2 | 待补全 | 待补全 |\n"
                    "\n"
                    "## 说明长度\n"
                    "产物前后说明**≤80 字**。禁止写章节式元文档。\n"
                    "\n"
                    "## 列表/草稿/信件\n"
                    "用 `- ` 或 `1. ` 编号清单，每条独立一行；草稿直接出正文不要加「以下是草稿」开头。\n"
                    "【任务执行模式结束】\n\n"
                )
            # R7：创意度三档 prompt 头部
            creativity_block = ""
            if creativity_mode == "creative":
                creativity_block = (
                    "【创意优先 · 自由创作模式】\n"
                    "等同于通用 LLM 对话窗口（如豆包通用窗口）：仅基于用户的问题和当前对话框中的内容回答。\n"
                    "**不需要**引用任何「客户资料」「文档库」「数据库」之类的素材——后面也不会提供这些。\n"
                    "完全释放想象力和语言能力，按用户的诉求和选定的写作风格自由创作。\n\n"
                )
            elif creativity_mode == "balanced":
                creativity_block = (
                    "【兼顾资料 · 默认创作模式】\n"
                    "下面提供的客户资料是**事实底色和背景**，不是直接复述对象。\n"
                    "硬事实必须真：数字、人名、产品名、机构名、时间节点 **绝对不能编造**——资料里没有的就别提。\n"
                    "**但**：叙事结构、句式、修辞、表达质感、措辞、隐喻、整体气质——**完全自由发挥**。\n"
                    "目标是写出一篇**有作者意识**的文章：事实是骨头，语言是血肉。\n"
                    "**不要**写「[资料1]」「[来源:XX]」这种来源标记，不要被资料的逐条罗列引诱去复述，要做创造性组织。\n"
                    "如果选了写作风格 skill，**风格完全生效**，按 skill 引导发挥。\n\n"
                )
            else:  # strict
                creativity_block = (
                    "【完全客观 · 严格模式】\n"
                    "所有数据、人名、产品名、机构名、时间节点 **必须能在下面提供的资料中找到出处**，零编造容忍。\n"
                    "关键判断后面必须带溯源标记（如「[资料 1]」「(见 XX.pdf)」），让用户能核对。\n"
                    "**不允许**文学修辞、隐喻、戏谑、夸张句式——句式严谨保守，宁可拙朴不要花哨。\n"
                    "如果选了写作风格 skill，**风格让位于事实约束**：句式可参考 skill 的偏好，但内容必须严格基于资料、不发挥不延伸。\n"
                    "资料中未见的部分，明确写「资料中未见」，禁止补全猜测。\n\n"
                )
            base_instruction = (
                task_prefix +
                creativity_block +
                style_prefix +
                f"{system_instruction}\n"
                "你现在直接基于后面的原始文档资料包回答用户问题。\n"
                # R8 全局：禁止元描述 —— 用户要分析就给分析，要任务就给产物
                "**直接给出用户要求的结果或回答**。\n"
                "不要描述「你打算如何完成这个任务」、不要写「以下是我的方法论」「按以下步骤执行」「数据源覆盖范围说明」「字段提取规则」式的元文档。\n"
                "用户要分析就直接给分析；用户要表格/列表/草稿就直接给产物；数据不足时直接说缺什么，不要写「应该建立 X 提取规则」这种规划。\n"
                "不要把回答写成摘要器、系统说明或文件目录。\n"
                "不要暴露系统过程、路由、检索、命中规则或技术细节。\n"
                "只基于提供资料判断，不要编造资料里没有的硬事实、数字、会议结论、人物身份或项目状态。\n"
                "\n"
                "【排版规则——必须严格遵守】\n"
                "1. 用「一、二、三」或 Markdown「## 」作为一级小标题分层；每个主题一个标题。\n"
                "2. 并列要点必须用「- 」无序列表或「1. 2. 3.」有序列表，不要写成一长串逗号连缀的句子。\n"
                "3. 关键结论用 **加粗**。\n"
                "4. **段落之间必须用空行隔开（即输出连续两个换行符 \\n\\n）**。禁止用单换行堆段落。\n"
                "5. 每段不超过 4 句话；每句不超过 60 字。禁止 200 字以上的逗号长句。\n"
                "6. 不要用「首先/其次/第三/第四/最后」这种口语过渡词来组织主结构；要分点时直接用列表。\n"
                "\n"
                "【内容规则】\n"
                f"{length_rule}\n"
                "8. 关键判断后面尽量带上来源标记（如「[资料 1]」「（见 XX.pdf）」），让用户能核对。\n"
                "9. 多用「不是 X，而是 Y」「核心在于」「区别于…在于」等判断句式，避免空话和正确的废话。\n"
                f"{detail_rule}"
            )

            # 战略素材拼到原始资料包前面作为前置高亮 —— 让单次 LLM 调用能扎进战略层判断，
            # 而不是只看命中的几条文档片段。
            # R7：creative 档完全不喂客户资料（strategic_pack 和 raw_evidence_pack 都忽略）
            # R8.13/R8.15：task_mode 时，调用方应该传精简的「客户文件目录」作为 strategic_pack
            # （不再是 13k 字的战略全景），让 LLM 知道客户都有哪些文件 → 能从文件名解析结构化信息
            if creativity_mode == "creative":
                effective_pack = ""
                user_prompt_text = f"用户问题：{prompt}"
            elif task_mode:
                # 任务型：调用方传的 strategic_pack 应是精简的文件目录（build_client_file_catalog 输出）
                effective_pack = str(raw_evidence_pack or "").strip()
                if (strategic_pack or "").strip():
                    effective_pack = (
                        f"{strategic_pack.strip()}\n\n"
                        "【检索命中的文档原文片段（评估字段值时优先用这里的实际内容）】\n"
                        f"{effective_pack}"
                    )
                user_prompt_text = f"用户问题：{prompt}\n\n{effective_pack}"
            else:
                effective_pack = str(raw_evidence_pack or "").strip()
                if (strategic_pack or "").strip():
                    effective_pack = (
                        "【战略素材包 —— 组织级定位/判断/演进/历史观点，这是回答深度的主要来源】\n"
                        f"{strategic_pack.strip()}\n\n"
                        "【原始文档资料包】\n"
                        f"{effective_pack}"
                    )
                user_prompt_text = f"用户问题：{prompt}\n\n{effective_pack}"

            # R8.13：task_mode 关闭 thinking，加快首字延迟和整体生成速度
            effective_enable_thinking = enable_thinking and not task_mode

            try:
                text = self._qwen_generate(
                    prompt=user_prompt_text,
                    system_instruction=base_instruction,
                    response_schema=None,
                    timeout_seconds=timeout_seconds,
                    max_tokens=max_tokens,
                    temperature=0.5,
                    top_p=0.97,
                    enable_thinking=effective_enable_thinking,
                    task_kind="deep_analysis",
                )
                # R8.8：任务模式下兜底修复"单行表格"退化输出
                final_text = str(text)
                if task_mode:
                    from app.services.chat_intent import normalize_markdown_table
                    final_text = normalize_markdown_table(final_text)
                return self._structured_from_plain_answer(final_text)
            except Exception as error:
                raise AiInvocationError(health.provider, self._format_provider_error(error)) from error
        return self._mock_generate(prompt, raw_evidence_pack)

    def _build_chat_generation_profile(self, context_summary: str) -> ChatGenerationProfile:
        context = str(context_summary or "").strip()
        context_length = len(context)
        evidence_count = context.count("[原始证据 ")
        high_load = context_length >= 22000 or evidence_count >= 10
        extreme_load = context_length >= 52000 or evidence_count >= 22

        primary_context = context if not high_load else self._compact_context_summary(context, max_chars=32000)
        # P2.10 hotfix: prioritize first-answer success over long-form expansion.
        # Real failures show the model can read ~5k context quickly, but long-form
        # generation often overruns a 22s read timeout. Use a shorter generation
        # budget with a slightly wider read window so users get a stable answer.
        primary_timeout_seconds = 300.0
        primary_max_tokens = 2400
        primary_enable_thinking = False

        if high_load:
            # 统一口径：
            # - primary_timeout_seconds 是 provider read timeout
            # - _build_http_timeout 会在此基础上追加固定 grace，形成 provider hard limit
            # - primary + fallback 构成 workspace generation budget
            primary_timeout_seconds = 300.0
            primary_max_tokens = 2600
            primary_enable_thinking = True
        if extreme_load:
            primary_context = self._compact_context_summary(context, max_chars=26000)
            primary_timeout_seconds = max(primary_timeout_seconds, 300.0)
            primary_max_tokens = 2200
            primary_enable_thinking = False

        fallback_max_chars = 10000 if high_load else 7000
        fallback_context = self._compact_context_summary(context, max_chars=fallback_max_chars)
        if high_load:
            primary_context_for_compare = primary_context or context
            if len(fallback_context) >= len(primary_context_for_compare):
                tighter_max_chars = max(600, int(len(primary_context_for_compare) * 0.6))
                fallback_context = self._compact_context_summary(
                    context,
                    max_chars=min(fallback_max_chars, tighter_max_chars),
                )
        fallback_timeout_seconds = 20.0 if high_load else 16.0
        fallback_max_tokens = 1000 if high_load else 800

        return ChatGenerationProfile(
            primary_context=primary_context or context,
            primary_timeout_seconds=primary_timeout_seconds,
            primary_max_tokens=primary_max_tokens,
            primary_enable_thinking=primary_enable_thinking,
            fallback_context=fallback_context,
            fallback_timeout_seconds=fallback_timeout_seconds,
            fallback_max_tokens=fallback_max_tokens,
            fallback_enable_thinking=False,
        )

    def generate_topic_candidate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
    ) -> AiStructuredResponse:
        health = self.get_health()
        compact_context = self._compact_context_summary(context_summary, max_chars=8000)
        quick_instruction = (
            f"{system_instruction}\n"
            "请只回答用户这一次问的问题，不要复述情报卡片已有内容。"
            "如果用户问成本，就拆时间成本、材料成本、合作沟通成本、机会成本和最小核验动作；如果问风险、匹配度、路径、负责人或材料准备，也按问题本身展开。"
            "回答结构可以自然使用：结论、拆解、缺口、下一步；但不要机械套模板。"
            "材料不足时要明确说“不足以判断什么”，同时给出最小核验动作。"
            "语言要像资深顾问在给同事判断，不要像系统摘要。"
            "不要输出 JSON 或 Markdown 代码块。"
        )
        if health.provider != "mock" and health.ready:
            try:
                text = self._qwen_generate(
                    prompt=f"用户问题：{prompt}\n\n当前情报背景：\n{compact_context}",
                    system_instruction=quick_instruction,
                    response_schema=None,
                    timeout_seconds=16.0,
                    max_tokens=3000,
                    temperature=0.5,
                    top_p=0.9,
                    enable_thinking=True,
                )
                return self._structured_from_plain_answer(str(text))
            except Exception as error:
                try:
                    return self._qwen_generate_brief_grounded_rescue(prompt, compact_context or context_summary)
                except Exception as rescue_error:
                    detail = "；".join(
                        part
                        for part in (
                            f"资讯快答失败：{self._format_provider_error(error)}",
                            f"简短兜底失败：{self._format_provider_error(rescue_error)}",
                        )
                        if part
                    )
                    raise AiInvocationError(health.provider, detail) from rescue_error
        return self._mock_generate(prompt, compact_context or context_summary)

    def generate_template_field_value(
        self,
        *,
        field_label: str,
        template_name: str,
        client_name: str,
        context_summary: str,
        field_type: str | None = None,
        client_id: str | None = None,
    ) -> str:
        health = self.get_health()
        field_rule = self._template_field_rule(field_type)
        # P-E.1: 注入字典权威包 — 模板字段填写是用户最终交付物，必须基于人审事实
        glossary_block = ""
        if client_id:
            try:
                from app.services.glossary_attributes_pack import build_verified_attributes_pack
                pack = build_verified_attributes_pack(self.db, client_id) or ""
                if pack:
                    glossary_block = f"{pack}\n\n---\n\n"
            except Exception:
                pass
        system_instruction = (
            "你正在为客户资料模板填写单个字段。"
            "请只输出可以直接粘贴进 Word 文档的最终内容，不要解释过程，不要写'根据资料'、'建议填写'、'可写为'这类前缀。"
            "如果资料不足，请只输出“【待确认】”开头的一句简短提示。"
            "不要输出“可从……进一步梳理”“建议补充”“可填写为”这类过程性提示。"
            "不要输出 Markdown 代码块，不要输出 JSON。"
            "涉及具体数字/日期/金额/姓名时，必须优先用上方字典权威值（如有）。"
        )
        prompt = (
            f"{glossary_block}"
            f"客户：{client_name}\n"
            f"模板：{template_name}\n"
            f"待填写字段：{field_label}\n\n"
            f"字段类型：{field_type or 'general'}\n"
            f"字段要求：{field_rule}\n\n"
            f"可参考材料：\n{context_summary.strip()}\n\n"
            "请直接给出这个字段应填写的内容。"
        )
        if health.provider != "mock" and health.ready:
            try:
                text = self._qwen_generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_schema=None,
                    timeout_seconds=26.0,
                    max_tokens=700,
                    temperature=0.28,
                    top_p=0.9,
                    enable_thinking=False,
                )
                return self._clean_template_field_value(str(text), field_type=field_type)
            except Exception as first_error:
                compact_context = context_summary.strip()[:2400]
                try:
                    text = self._qwen_generate(
                        prompt=(
                            f"客户：{client_name}\n"
                            f"模板：{template_name}\n"
                            f"待填写字段：{field_label}\n\n"
                            f"字段类型：{field_type or 'general'}\n"
                            f"字段要求：{field_rule}\n\n"
                            f"可参考材料：\n{compact_context}\n\n"
                            "请直接给出这个字段应填写的内容。"
                        ),
                        system_instruction=system_instruction,
                        response_schema=None,
                        timeout_seconds=14.0,
                        max_tokens=420,
                        temperature=0.22,
                        top_p=0.88,
                        enable_thinking=False,
                    )
                    return self._clean_template_field_value(str(text), field_type=field_type)
                except Exception as second_error:
                    raise AiInvocationError(
                        health.provider,
                        "；".join(
                            part
                            for part in (
                                f"字段填写主调用失败：{self._format_provider_error(first_error)}",
                                f"字段填写紧凑重试失败：{self._format_provider_error(second_error)}",
                            )
                            if part
                        ),
                    ) from second_error
        fallback = context_summary.strip().splitlines()
        best_line = next((line.strip() for line in fallback if line.strip()), "")
        return self._clean_template_field_value(best_line or "【待确认】当前缺少可直接填写该字段的资料。", field_type=field_type)

    def generate_template_field_values_batch(
        self,
        *,
        template_name: str,
        client_name: str,
        field_contexts: list[tuple[str, str]],
        field_types: dict[str, str] | None = None,
        client_id: str | None = None,
    ) -> dict[str, str]:
        if not field_contexts:
            return {}
        health = self.get_health()
        labels = [label for label, _ in field_contexts]
        # P-E.1: 注入字典权威包到批量填写 prompt
        glossary_block = ""
        if client_id:
            try:
                from app.services.glossary_attributes_pack import build_verified_attributes_pack
                _pack = build_verified_attributes_pack(self.db, client_id) or ""
                if _pack:
                    glossary_block = f"{_pack}\n\n---\n\n"
            except Exception:
                pass
        schema = {
            "type": "OBJECT",
            "properties": {label: {"type": "STRING"} for label in labels},
            "required": labels,
        }
        system_instruction = (
            "你正在为客户资料模板批量填写多个字段。"
            "每个字段都带有它自己的参考材料。"
            "请严格返回一个 JSON 对象，键必须和字段名完全一致。"
            "每个值都必须是可直接粘贴进 Word 文档的最终内容，不要加解释或前缀。"
            "\n"
            "【填写要求】\n"
            "1. 这是民政/年报/合规类规范模板，绝大多数字段都能从客户资料的检索片段、"
            "已采纳判断、客户 DNA、组织基本面里直接抽出来——不要懒。\n"
            "2. 字段说明（hint）告诉你期望的形态（如『18 位代码』、『姓名+电话+邮箱』），"
            "请按这个形态输出。\n"
            "3. 只有当所有参考材料里都明确不包含这个字段的事实时，才输出『【待确认】xxx』"
            "（其中 xxx 要写清楚需要哪类资料补齐）。\n"
            "4. 字段类型『单行文本』/『姓名』/『日期』/『货币』之类的，**只要资料里有相关线索，"
            "就给出最贴合的具体值**，不要因为'拿不到 100% 确定数据'就回退到待确认。\n"
            "5. 字段类型『多选』/『下拉』要从 hint 给的候选里挑，不要写成长段说明。\n"
            "6. 不要输出 Markdown 代码块，不要输出 JSON 以外的任何内容。"
        )
        prompt_blocks: list[str] = []
        for index, (label, context_summary) in enumerate(field_contexts, start=1):
            current_type = str((field_types or {}).get(label) or "general")
            prompt_blocks.append(
                (
                    f"[字段 {index}]\n"
                    f"字段名：{label}\n"
                    f"字段类型：{current_type}\n"
                    f"字段要求：{self._template_field_rule(current_type)}\n"
                    "只填写这个字段，不要引用其他字段。\n"
                    f"{context_summary.strip()}"
                ).strip()
            )
        prompt = (
            f"{glossary_block}"
            f"客户：{client_name}\n"
            f"模板：{template_name}\n"
            f"字段总数：{len(field_contexts)}\n\n"
            "请分别填写以下字段，并返回 JSON 对象：\n\n"
            + "\n\n".join(prompt_blocks)
        )
        if health.provider != "mock" and health.ready:
            try:
                # 民政年报/规范字段表这类批量填写：每个字段都需要从客户资料中检索 + 推理，
                # 旧默认 18s timeout / max_tokens=360×N 在豆包深度推理下会大量回退到「【待确认】」。
                # 放大到合理范围（45s + 600 tokens/字段 + 启用 thinking），让 LLM 有空间真正给出答案。
                payload = self._qwen_generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_schema=schema,
                    timeout_seconds=min(120.0, max(45.0, 18.0 + 8.0 * len(field_contexts))),
                    max_tokens=min(6000, max(2400, 600 * len(field_contexts))),
                    temperature=0.28,
                    top_p=0.9,
                    enable_thinking=True,
                )
            except Exception as error:
                raise AiInvocationError(health.provider, self._format_provider_error(error)) from error
            if isinstance(payload, dict):
                return {
                    label: self._clean_template_field_value(
                        str(payload.get(label) or "【待确认】当前缺少可直接填写该字段的资料。"),
                        field_type=str((field_types or {}).get(label) or "general"),
                    )
                    for label in labels
                }
        return {
            label: self.generate_template_field_value(
                field_label=label,
                template_name=template_name,
                client_name=client_name,
                context_summary=context_summary,
                field_type=str((field_types or {}).get(label) or "general"),
                client_id=client_id,
            )
            for label, context_summary in field_contexts
        }

    def _qwen_generate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        timeout_seconds: float = 22.0,
        max_tokens: int = 3600,
        enable_thinking: bool = True,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        detailed_context = str(context_summary or "").strip()
        base_instruction = (
            f"{system_instruction}\n"
            "你现在是在直接回答用户，不要把答案写成系统产物。"
            "请把后面的原始材料当作你已经完整读过的材料直接使用。"
            "不要解释检索过程、系统过程、命中规则或技术细节。"
            "优先输出可执行、可读的回答，不要凑篇幅。"
            "可以做综合判断，但不要把未证实事实写成确定结论。\n\n"
            "【输出约束】\n"
            "1. 回答结构由问题复杂度和资料密度决定，不要机械收成 3-4 个小节。\n"
            "2. 如果问题本身适合长回答，请充分展开；优先把机构定位、核心问题、方法、业务线、升级方向讲透。\n"
            "3. 不要为了节省篇幅省掉关键结构，也不要为了凑篇幅重复表达。\n"
            "4. 待确认或边界信息只有在确实影响结论时才自然说明，不要机械单列为固定板块。\n"
        )
        try:
            if on_partial is not None:
                on_partial(
                    {
                        "stageLabel": "正在直接生成长文回答",
                        "progress": 62.0,
                        "content": f"{self.current_model_label()}正在基于完整材料直接生成长文回答。",
                        "structured": {
                            "content": f"{self.current_model_label()}正在基于完整材料直接生成长文回答。",
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            text = self._qwen_generate(
                prompt=f"用户问题：{prompt}\n\n参考材料：\n{detailed_context}",
                system_instruction=base_instruction,
                response_schema=None,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                temperature=0.48,
                top_p=0.96,
                enable_thinking=enable_thinking,
                task_kind="deep_analysis",
            )
            return self._structured_from_plain_answer(str(text))
        except Exception as error:
            raise AiInvocationError(self.current_provider(), self._format_provider_error(error)) from error

    def _qwen_generate_progressive_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        focus_context = self._compact_context_summary(context_summary, max_chars=20000)
        analysis_context = self._compact_context_summary(context_summary, max_chars=40000)
        action_context = self._compact_context_summary(context_summary, max_chars=20000)
        base_instruction = (
            f"{system_instruction}\n"
            "你现在要分阶段写成一版完整顾问回答。"
            "每个阶段都直接服务最终成文，不要解释系统过程，也不要输出技术细节。"
            "优先写得深、清楚、有判断。\n"
            "【排版规则——必须严格遵守】\n"
            "1. 用「一、二、三」作为一级小标题分层\n"
            "2. 并列要点用「- 」列表\n"
            "3. 关键结论用 **加粗**\n"
            "4. 禁止全篇连续长段落\n"
            "5. 多用「不是X，而是Y」「核心在于」等判断句式\n"
        )

        def emit_partial(stage_label: str, progress: float, content: str, *, judgment: str = "", analysis: str = "", actions: str = "") -> None:
            if on_partial is None:
                return
            on_partial(
                {
                    "stageLabel": stage_label,
                    "progress": progress,
                    "content": content.strip(),
                    "structured": {
                        "content": content.strip(),
                        "judgment": judgment.strip(),
                        "analysis": analysis.strip(),
                        "actions": actions.strip(),
                        "timeline": "",
                    },
                }
            )

        errors: list[str] = []
        opener_text = ""
        title = ""
        judgment = ""
        analysis_text = ""
        actions_text = ""

        try:
            opener_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{focus_context}\n\n"
                        "请先写出回答的开场部分。"
                        "如果你觉得需要标题就写，不需要就直接进入正文。"
                        "这部分要直接回答问题，并自然点出最重要的主线、判断或观察。不要为了格式而格式化。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责把回答开头写出来。"
                    ),
                    response_schema=None,
                    timeout_seconds=12.0,
                    max_tokens=1200,
                    temperature=0.42,
                    top_p=0.96,
                    enable_thinking=True,
                )
            ).strip()
        except Exception as error:
            errors.append(f"开场判断失败：{self._format_provider_error(error)}")
        if not opener_text:
            raise AiInvocationError(self.current_provider(), "；".join(errors) or "分阶段生成未返回开场判断")

        extracted_title = self._extract_segment_field(opener_text, ("标题", "题目"))
        title = re.sub(r"\s+", " ", extracted_title or "").strip()[:24]
        judgment = self._extract_segment_field(opener_text, ("总判断", "判断")) or opener_text
        partial_content = "\n\n".join(part for part in [title, judgment] if part.strip())
        emit_partial("正在形成开场判断", 62.0, partial_content, judgment=judgment)

        try:
            analysis_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{analysis_context}\n\n"
                        f"当前总判断：\n{judgment}\n\n"
                        "请继续完成主体分析。"
                        "由你自己判断最适合这道问题的展开方式，可以用自然段，也可以用小标题。"
                        "尽量把真正值得展开的部分讲透，而不是把所有可能方向平均铺开。"
                        "不要复述材料标题，不要把回答写成资料摘要。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责把主体内容写深、写透。"
                    ),
                    response_schema=None,
                    timeout_seconds=30.0,
                    max_tokens=3200,
                    temperature=0.42,
                    top_p=0.95,
                    enable_thinking=True,
                )
            ).strip()
        except Exception as error:
            errors.append(f"主体分析失败：{self._format_provider_error(error)}")

        analysis_density = len(re.sub(r"\s+", "", analysis_text))
        if analysis_density < 260:
            try:
                rescue_text = str(
                    self._qwen_generate(
                        prompt=(
                            f"问题：{prompt}\n\n"
                            f"顾问底稿：\n{analysis_context}\n\n"
                            f"已有总判断：\n{judgment}\n\n"
                        "请补写主体分析。"
                        "如果已有主体内容偏短，就继续把最值得展开的部分补深。"
                        "不需要机械补齐固定小节，也不要反复围绕同一个判断来回改写。"
                        "你可以自由决定是继续展开已有主线，还是补进新的关键分析面。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段是主体内容补写。"
                    ),
                    response_schema=None,
                    timeout_seconds=10.0,
                    max_tokens=1200,
                    temperature=0.4,
                    top_p=0.95,
                    enable_thinking=False,
                )
            ).strip()
                if len(re.sub(r"\s+", "", rescue_text)) > analysis_density:
                    analysis_text = rescue_text
                    analysis_density = len(re.sub(r"\s+", "", analysis_text))
            except Exception as error:
                errors.append(f"主体分析补写失败：{self._format_provider_error(error)}")

        if analysis_text:
            partial_content = "\n\n".join(part for part in [title, judgment, analysis_text] if part.strip())
            emit_partial("正在展开主体分析", 79.0, partial_content, judgment=judgment, analysis=analysis_text)

        try:
            actions_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{action_context}\n\n"
                        f"已有总判断：\n{judgment}\n\n"
                        "请完成回答的收束部分。"
                        "由你自己判断最自然的结束方式。"
                        "如果适合给建议、优先级或下一步，就写出来；如果不适合，就自然收束，不要强行加动作。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责完成回答的结尾。"
                    ),
                    response_schema=None,
                    timeout_seconds=14.0,
                    max_tokens=1200,
                    temperature=0.38,
                    top_p=0.94,
                    enable_thinking=True,
                )
            ).strip()
        except Exception as error:
            errors.append(f"建议动作失败：{self._format_provider_error(error)}")

        if not analysis_text and not actions_text:
            raise AiInvocationError(self.current_provider(), "；".join(errors) or "分阶段生成只返回了开场判断")

        assembled_parts = [title, judgment]
        if analysis_text:
            assembled_parts.append(analysis_text)
        if actions_text:
            assembled_parts.append(actions_text)
        content = "\n\n".join(part.strip() for part in assembled_parts if part and part.strip())
        emit_partial("正在整理最终成文", 91.0, content, judgment=judgment, analysis=analysis_text, actions=actions_text)
        return self._structured_from_plain_answer(content)

    def generate_compact_grounded_fallback(self, prompt: str, note: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider != "mock" and health.ready:
            try:
                return self._qwen_generate_compact_grounded_fallback(prompt, note)
            except Exception as error:
                raise AiInvocationError(health.provider, self._format_provider_error(error)) from error
        return self._mock_generate(prompt, note or "基于已命中资料的紧凑综述。")

    def generate_brief_grounded_rescue(self, prompt: str, note: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider != "mock" and health.ready:
            try:
                return self._qwen_generate_brief_grounded_rescue(prompt, note)
            except Exception as error:
                raise AiInvocationError(health.provider, self._format_provider_error(error)) from error
        return self._mock_generate(prompt, note or "基于已命中资料的一版简短保守回答。")

    def suggest_short_title(self, prompt: str) -> str:
        health = self.get_health()
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt=f"请将以下追踪规则提炼为 3 到 6 个字的中文标签，只返回标签本身：{prompt}",
                    system_instruction="你是中文编辑，擅长压缩标题。",
                    response_schema=None,
                    timeout_seconds=12.0,
                )
                title = str(result).strip().replace("“", "").replace("”", "")
                if title:
                    return title[:8]
        except Exception:
            pass
        cleaned = re.sub(r"[，。；：、,.!?！？\\s]+", "", prompt)
        cleaned = re.sub(r"^(关注|跟踪|追踪|围绕|关于)", "", cleaned)
        return (cleaned[:6] or "自定义雷达").strip()

    def suggest_topic_search_queries(self, *, title: str, prompt: str, time_range: str) -> list[str]:
        health = self.get_health()
        fallback = self._fallback_topic_search_queries(title=title, prompt=prompt, time_range=time_range)
        schema = {
            "type": "OBJECT",
            "properties": {
                "queries": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                }
            },
        }
        query_prompt = (
            "请把下面的资讯追踪需求提炼成 2 到 3 条适合新闻/信息搜索的中文查询词。"
            "要求：保留核心对象、行业和技术关键词，避免空泛词。"
            "返回 JSON：{\"queries\": [\"查询1\", \"查询2\"]}。\n"
            f"雷达标题：{title}\n"
            f"追踪说明：{prompt}\n"
            f"时间范围：{time_range}\n"
        )
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    query_prompt,
                    "你是检索词生成助手。只返回 JSON。",
                    schema,
                    timeout_seconds=18.0,
                    max_tokens=600,
                )
                if isinstance(result, dict):
                    queries = [str(item).strip() for item in result.get("queries", []) if str(item).strip()]
                    if queries:
                        return queries[:3]
        except Exception:
            pass
        return fallback

    def shortlist_topic_search_hits(
        self,
        *,
        title: str,
        prompt: str,
        hits: list[dict[str, str]],
        max_items: int = 4,
    ) -> list[dict[str, object]]:
        if not hits:
            return []
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "items": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "index": {"type": "INTEGER"},
                            "title": {"type": "STRING"},
                            "summary": {"type": "STRING"},
                        },
                    },
                }
            },
        }
        entries = []
        for index, hit in enumerate(hits, start=1):
            entries.append(
                "\n".join(
                    [
                        f"[{index}] 标题：{hit.get('title', '')}",
                        f"来源：{hit.get('source', '')}",
                        f"发布时间：{hit.get('publishedAt', '') or '未知'}",
                        f"摘要：{hit.get('summary', '')}",
                    ]
                )
            )
        joined_entries = "\n\n".join(entries)
        screening_prompt = (
            "你是资讯情报筛选助手。请根据雷达标题和追踪说明，从候选结果中挑选最相关的结果。"
            f"最多返回 {max_items} 条，优先保留真正相关、可转成选题候选的条目，明显跑题的不要选。"
            "title 要写成 10 到 28 个字的中文标题；如果原文不是中文，要准确翻译成中文。"
            "summary 要写成 40 到 90 字的中文摘要，适合直接落到候选池。"
            "返回 JSON：{\"items\": [{\"index\": 1, \"title\": \"...\", \"summary\": \"...\"}]}\n"
            f"雷达标题：{title}\n"
            f"追踪说明：{prompt}\n"
            f"候选结果：\n{joined_entries}"
        )
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    screening_prompt,
                    "你是资讯情报筛选助手。只返回 JSON。",
                    schema,
                    timeout_seconds=25.0,
                    max_tokens=1400,
                )
                if isinstance(result, dict):
                    items = result.get("items", [])
                    if isinstance(items, list):
                        return [item for item in items if isinstance(item, dict)][:max_items]
        except Exception:
            pass
        return []

    def localize_topic_hit(
        self,
        *,
        title: str,
        summary: str,
        radar_title: str,
        radar_prompt: str,
    ) -> dict[str, str]:
        cleaned_title = str(title or "").strip()
        cleaned_summary = str(summary or cleaned_title).strip() or cleaned_title
        if self._has_sufficient_cjk(cleaned_title) and self._has_sufficient_cjk(cleaned_summary):
            return {
                "title": cleaned_title[:60],
                "summary": cleaned_summary[:140],
            }
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "summary": {"type": "STRING"},
            },
        }
        prompt = (
            "请把下面这条资讯候选整理成适合内部候选池展示的中文标题和中文摘要。"
            "如果原文不是中文，请准确翻译成中文；不要编造没有出现过的事实。"
            "title 保持 10 到 28 个中文字符；summary 保持 40 到 90 个中文字符。"
            "返回 JSON：{\"title\": \"中文标题\", \"summary\": \"中文摘要\"}\n"
            f"雷达标题：{radar_title}\n"
            f"雷达说明：{radar_prompt}\n"
            f"原始标题：{cleaned_title}\n"
            f"原始摘要：{cleaned_summary}\n"
        )
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是资讯翻译编辑助手。只返回 JSON。",
                    schema,
                    timeout_seconds=20.0,
                    max_tokens=800,
                )
                if isinstance(result, dict):
                    localized_title = str(result.get("title") or "").strip()
                    localized_summary = str(result.get("summary") or "").strip()
                    if localized_title and localized_summary:
                        return {
                            "title": localized_title[:60],
                            "summary": localized_summary[:140],
                        }
        except Exception:
            pass
        fallback_title = cleaned_title[:60]
        if not self._has_sufficient_cjk(fallback_title):
            fallback_title = f"{radar_title}相关机会"
        fallback_summary = cleaned_summary[:140]
        if not self._has_sufficient_cjk(fallback_summary):
            fallback_summary = f"原始来源提到“{cleaned_title[:40]}”，建议打开原文核对后再决定是否跟进。"
        return {"title": fallback_title, "summary": fallback_summary}

    def build_topic_candidate_insight(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        organization_context: str = "",
    ) -> dict[str, object]:
        health = self.get_health()
        prompt = (
            "请直接写成一份给公益组织顾问团队看的情报 memo，不要返回 JSON，不要解释系统过程。\n\n"
            "必须使用三个固定标题：\n"
            "【情报速览】\n"
            "【情报研判】\n"
            "【行动建议】\n\n"
            "写作要求：\n"
            "1. 总体篇幅要丰满，约 900 到 1500 个中文字符；不要把每节压成一两句话。\n"
            "2. 情报速览负责讲清外部信息本身，尽量保留关键事实密度：发布主体、时间窗口、支持方向、金额/条件/地域、申报主体、可疑或待核验点。\n"
            "3. 情报研判要像资深顾问的判断：结合给定组织/客户/项目背景，分析机会、风险、成本、边界。可以做推断，但必须区分事实、推断、待核验。\n"
            "4. 行动建议要具体到下一步能做什么：先核验什么、准备哪些材料、谁适合初筛、什么条件下止损或转为合作线索。\n"
            "5. 每一节都先写一行 **结论：**。情报研判后续必须包含 **机会：**、**风险：**、**成本：**、**边界：**。行动建议后续必须包含 **先核验：**、**先找人：**、**先备料：**、**止损条件：**。\n"
            "6. 情报速览至少展开 4 行事实或待核验点；情报研判至少展开 4 行判断；行动建议至少展开 4 行动作。\n"
            "7. 语言要像人写给同事的顾问 memo，不要写“建议关注/建议跟进/高度相关”这类空话；也不要把内部字段名、命中规则、画像标签写给用户看。\n"
            "8. 如果材料不足，就直接说不足以判断哪些关键事项，同时给出最小核验动作。\n"
            "9. 不要为了显得完整而编造金额、日期、主体资格、伙伴关系；不确定的内容写入待核验。\n\n"
            "风格参考：\n"
            "【情报研判】\n"
            "**结论：**这条线索的价值，不是“马上申报”，而是可能提供一个把既有服务能力转成本地联合方案的入口。\n"
            "**机会：**如果议题方向与客户已有服务积累贴合，可以包装成课程、督导、学校/社区服务经验的联合方案。\n"
            "**风险：**如果存在本地注册、驻点队伍或执行主体限制，独立申报竞争力会偏弱。\n"
            "**成本：**真正投入前，要先确认本地伙伴、材料量、专职人员和资金额度是否值得。\n"
            "**边界：**这类线索应先作为本地合作入口评估，不要直接上升为完整申报任务。\n\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n\n"
            f"组织/客户/项目背景：\n{organization_context[:2400] or '未提供。若背景不足，请明确说明判断边界。'}\n\n"
            f"原文摘录：\n{(source_content or '未抓到原文全文，只有标题和摘要。')[:5200]}"
        )
        try:
            if health.provider != "mock" and health.ready:
                memo = str(self._qwen_generate(
                    prompt,
                    (
                        "你是益语智库的资深公益战略顾问。"
                        "你面对的是内部顾问团队和公益组织负责人，目标是把外部公开信息转化成可判断、可行动的顾问 memo。"
                        "不要输出 JSON，不要写系统字段，不要把材料机械拼接。"
                    ),
                    None,
                    timeout_seconds=36.0,
                    max_tokens=2400,
                    temperature=0.62,
                    top_p=0.95,
                )).strip()
                if self._topic_advisor_memo_has_consultant_depth(memo):
                    payload = self._advisor_memo_to_topic_insight_payload(
                        memo,
                        candidate_title=candidate_title,
                        candidate_summary=candidate_summary,
                        source=source,
                        published_at=published_at,
                        source_url=source_url,
                        source_content=source_content,
                    )
                    if payload.get("overview") and payload.get("editorialNote") and payload.get("practicalUses"):
                        return payload
        except Exception:
            pass
        fallback = self._fallback_topic_candidate_insight(
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
        )
        localized = self._localize_topic_insight_payload(
            fallback,
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
        )
        memo = self._fallback_topic_advisor_memo(
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
            localized=localized,
            organization_context=organization_context,
        )
        return self._advisor_memo_to_topic_insight_payload(
            memo,
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
        )

    def _advisor_memo_to_topic_insight_payload(
        self,
        memo: str,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
    ) -> dict[str, object]:
        sections = self._extract_topic_advisor_memo_sections(memo)
        overview = sections.get("情报速览") or candidate_summary or candidate_title
        assessment = sections.get("情报研判") or "这条线索需要结合当前客户/项目语境继续判断；现有材料还不足以形成稳定研判。"
        action = sections.get("行动建议") or "先核验来源原文、时间窗口、主体条件和资源投入，再决定是否转为任务。"
        key_points = self._split_memo_points(overview, max_items=5) or [overview[:180]]
        reasons = self._split_memo_points(assessment, max_items=5) or [assessment[:180]]
        uses = self._split_memo_points(action, max_items=6) or [action[:180]]
        return {
            "overview": overview.strip(),
            "keyPoints": key_points,
            "recommendationReasons": reasons,
            "practicalUses": uses,
            "editorialNote": assessment.strip(),
            "discussionPrompts": [
                "这个机会的硬条件和成本是否值得进入正式初筛？",
                "如果转任务，负责人第一步应该核验什么？",
                "它与当前客户或项目近期工作重点的关系是什么？",
            ],
            "advisorMemo": memo.strip(),
            "deepAnalysis": {
                "advisorMemo": memo.strip(),
                "intelligenceBrief": overview.strip(),
                "advisorAssessment": assessment.strip(),
                "actionPlan": uses,
            },
        }

    def _extract_topic_advisor_memo_sections(self, memo: str) -> dict[str, str]:
        text = str(memo or "").strip()
        labels = ("情报速览", "情报研判", "行动建议")
        sections: dict[str, str] = {}
        for index, label in enumerate(labels):
            next_labels = labels[index + 1 :]
            next_pattern_parts: list[str] = []
            for item in next_labels:
                next_pattern_parts.extend([
                    rf"【{re.escape(item)}】",
                    rf"{re.escape(item)}[:：]",
                    rf"^\s*{re.escape(item)}\s*$",
                ])
            pattern = rf"(?:【{re.escape(label)}】|{re.escape(label)}[:：]|^\s*{re.escape(label)}\s*$)\s*([\s\S]+?)"
            if next_pattern_parts:
                pattern += rf"(?=\n\s*(?:{'|'.join(next_pattern_parts)})|\Z)"
            else:
                pattern += r"\Z"
            match = re.search(pattern, text, flags=re.MULTILINE)
            if match:
                sections[label] = match.group(1).strip()
        if not sections and text:
            sections["情报速览"] = text
        return sections

    def _topic_advisor_memo_has_consultant_depth(self, memo: str) -> bool:
        text = str(memo or "").strip()
        if len(text) < 450:
            return False
        if re.search(r"一、这篇内容主要讲什么|文章里最值得抓住的观点|它对团队的实际价值|大模型安全|风险治理前置|coreInfo|opportunityOrRisk", text):
            return False
        sections = self._extract_topic_advisor_memo_sections(text)
        if not all(sections.get(label, "").strip() for label in ("情报速览", "情报研判", "行动建议")):
            return False
        for label, section in sections.items():
            lines = [line.strip() for line in section.splitlines() if line.strip()]
            if len(lines) < 3:
                return False
            if "结论" not in section[:120]:
                return False
        assessment = sections.get("情报研判", "")
        action = sections.get("行动建议", "")
        if not all(label in assessment for label in ("机会", "风险", "成本", "边界")):
            return False
        return all(label in action for label in ("先核验", "先找人", "先备料", "止损"))

    def _split_memo_points(self, text: str, *, max_items: int) -> list[str]:
        cleaned = str(text or "").strip()
        if not cleaned:
            return []
        lines = [line.strip(" \t-•") for line in cleaned.splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[:max_items]
        parts = re.split(r"(?<=[。！？；])\s*", cleaned)
        return [part.strip() for part in parts if part.strip()][:max_items]

    def _fallback_topic_advisor_memo(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        localized: dict[str, object],
        organization_context: str = "",
    ) -> str:
        overview = str(localized.get("overview") or candidate_summary or candidate_title).strip()
        context_text = f"{organization_context}\n{candidate_title}\n{candidate_summary}\n{source_content}"
        # 机制化: target_name 不再用客户名硬编码匹配, 仅按机构类型 fallback
        if "基金会" in context_text:
            target_name = "目标基金会"
        else:
            target_name = "目标客户"
        funding_like = bool(re.search(r"公益创投|申报|资助|征集|项目申报|资金|扶持|补助", context_text))
        youth_mental = bool(re.search(r"青少年|未成年人|儿童|心理", context_text))
        if funding_like:
            assessment = (
                f"**结论：**这条线索对{target_name}的价值，不是“马上投入申报”，而是先判断它能不能成为一个本地联合方案入口。\n"
                f"**机会：**如果议题方向与{target_name}已有服务积累贴合，可以把课程、督导、学校/社区服务经验包装成本地合作方案。\n"
                "**风险：**当前最需要防的是主体资格、地域注册、驻点执行和本地伙伴要求；这些条件不清楚时，独立推进容易误判。\n"
                "**成本：**正式申报前要先估算材料准备量、协调成本、人员驻点和资金规模，否则可能挤占现有项目精力。\n"
                "**边界：**这不是泛泛的行业机会，而是一个有地域和时间窗口的政策入口；应先做硬条件初筛，再决定是否升级为任务。"
            )
            action_text = (
                "**结论：**先用 1-2 天做硬条件初筛；只有主体、伙伴、资金额度和材料成本都过线，才转成正式任务。\n"
                "**先核验：**核对正式通知里的申报主体、联合申报规则、截止时间、材料清单、资助额度和执行地域。\n"
                "**先找人：**如果允许联合申报，先筛 2-3 家本地社会组织、学校、社区或服务平台，确认谁具备资质和场景。\n"
                f"**先备料：**{target_name}只需先准备一页初筛材料：服务对象、过往案例、课程/督导能力、可落地服务包、预算大纲。\n"
                "**止损条件：**如果本地伙伴找不到、资助额度不足以覆盖协调成本，或材料要求明显超出当前承载，就不进入正式申报。"
            )
        else:
            assessment = (
                f"**结论：**这条线索暂时只能作为顾问初筛材料，价值取决于它能否和{target_name}的当前任务、对象或地域形成真实连接。\n"
                "**机会：**如果它能补足客户正在推进的服务、合作、传播或政策判断，就可以转成小范围核验任务。\n"
                "**风险：**如果只有主题相似、缺少主体条件和落地场景，就容易变成泛泛信息，消耗团队注意力。\n"
                "**成本：**当前只适合低成本核验，不适合直接组织完整方案、会议或材料生产。\n"
                "**边界：**先把事实、推断和待核验项分开；只有行动入口清楚后，再进入任务系统。"
            )
            action_text = (
                "**结论：**先核验事实和匹配条件，再决定是否转任务。\n"
                "**先核验：**确认来源原文、发布日期、主体、对象、地域、时间窗口和可执行条件。\n"
                "**先找人：**找到内部最接近该议题的负责人或项目同事，问清它是否对应当前真实需求。\n"
                "**先备料：**整理一页材料，列出已知事实、可能价值、待核验问题和下一步判断口径。\n"
                "**止损条件：**如果无法指向具体机会、风险、合作或政策窗口，就只归档为弱线索。"
            )
        fact_lines = [
            f"**结论：**{overview or candidate_title}",
            f"来源为{source or '公开来源'}，发布时间为{published_at or '未知'}；需要以原文链接和正式附件为准。",
        ]
        if youth_mental:
            fact_lines.append("已知内容涉及儿童、未成年人或青少年心理相关方向，和公益服务项目设计可能存在连接。")
        if source_content and source_content.strip():
            fact_lines.append(str(source_content).strip().splitlines()[0][:180])
        fact_lines.append("仍需核验：资助金额、主体限制、联合申报规则、截止日期、评审细则和落地要求。")
        return (
            "【情报速览】\n"
            f"{chr(10).join(fact_lines)}\n\n"
            "【情报研判】\n"
            f"{assessment}\n\n"
            "【行动建议】\n"
            f"{action_text}\n\n"
            f"参考来源：{source}；发布时间：{published_at or '未知'}；链接：{source_url or '无'}。"
        ).strip()

    # ── Growth insight quote distillation ────────────────────────────────
    def distill_growth_insight_quote(
        self,
        *,
        task_title: str,
        task_desc: str = "",
        client_name: str = "",
        event_line_name: str = "",
        blocker: str = "",
        next_action: str = "",
        recent_decision: str = "",
        context_summary: str = "",
        evidence_refs: list[str] | None = None,
    ) -> dict[str, str]:
        """Distil raw task/review context into a concise, quotable 金句 (insight quote).

        Returns {"quote": "...", "source_label": "..."}.
        The quote should be a standalone insight sentence (≤80 chars ideally)
        that captures transferable work wisdom — like the preview mock data:
          "让客户先交完整方案再提问题，比直接帮改方案更有效——陪伴的核心是不代偿。"
        """
        health = self.get_health()
        raw_material = "\n".join(
            part
            for part in [
                f"任务标题：{task_title}",
                f"任务描述：{task_desc}" if task_desc else "",
                f"客户名称：{client_name}" if client_name else "",
                f"事件线名称：{event_line_name}" if event_line_name else "",
                f"当前阻碍：{blocker}" if blocker else "",
                f"下一步行动：{next_action}" if next_action else "",
                f"最近判断：{recent_decision}" if recent_decision else "",
                f"背景摘要：{context_summary}" if context_summary else "",
                f"证据参考：{'、'.join(evidence_refs)}" if evidence_refs else "",
            ]
            if part
        )

        schema = {
            "type": "OBJECT",
            "properties": {
                "quote": {"type": "STRING"},
                "sourceLabel": {"type": "STRING"},
            },
        }

        prompt = (
            "你是一位经验萃取专家。请从下面的任务工作材料中，提炼出一句经验金句。\n\n"
            "要求：\n"
            "1. 金句必须是一句完整的、可独立引用的话，30~80个字为佳，最多不超过100字。\n"
            '2. 金句要传达一个可迁移的工作智慧或判断，而非陈述事实（不要写「完成了XX」「推进了XX」）。\n'
            "3. 风格参考：\n"
            "   - 让客户先交完整方案再提问题，比直接帮改方案更有效——陪伴的核心是不代偿。\n"
            "   - 数字化理解快的客户，效率瓶颈往往不在技术而在项目设计。\n"
            "   - 月捐人流失率最高的阶段不是首月，而是第三个月——这是承诺感消退的临界点。\n"
            "   - 合作方的节奏感比能力更重要，节奏对不上的合作最终都会变成消耗。\n"
            "4. 金句应该像一个有经验的从业者的口头心得，朴实直接，不要写成口号或鸡汤。\n"
            "5. 如果材料信息不足以提炼出有价值的洞察，就从任务的核心动作中找到一个可迁移的方法论视角。\n"
            "6. sourceLabel 写一个简短的来源标注，格式如「客户名·阶段」或「事件线名·W周数」，5~15字。\n\n"
            f"原始工作材料：\n{raw_material}"
        )

        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是组织经验萃取助手。只返回 JSON。",
                    schema,
                    timeout_seconds=15.0,
                    max_tokens=300,
                    temperature=0.7,
                )
                if isinstance(result, dict):
                    quote = str(result.get("quote") or "").strip().strip('"')
                    source_label = str(result.get("sourceLabel") or "").strip()
                    if quote and len(quote) >= 10:
                        return {"quote": quote, "sourceLabel": source_label}
        except Exception:
            pass

        # Fallback: use task_title as-is
        return {"quote": "", "sourceLabel": ""}

    def generate_task_context_brief(
        self,
        *,
        material_pack: dict[str, object],
    ) -> dict[str, object]:
        """Generate an assistant-style project context reminder for a task."""
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "shouldDisplay": {"type": "BOOLEAN"},
                "brief": {"type": "STRING"},
                "usedProjectSignals": {"type": "ARRAY", "items": {"type": "STRING"}},
                "materialBoundary": {"type": "STRING"},
                "qualityFlags": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        # P-D.4: 字典权威包从 material_pack 抽出来，作为 prompt 头部（事实底座）
        glossary_pack = str(material_pack.get("glossaryAuthorityPack") or "").strip()
        material_for_dump = {k: v for k, v in material_pack.items() if k != "glossaryAuthorityPack"}
        raw_material = json.dumps(material_for_dump, ensure_ascii=False, sort_keys=True, default=str)
        if len(raw_material) > 16000:
            raw_material = raw_material[:16000]
        glossary_block = f"{glossary_pack}\n\n---\n\n" if glossary_pack else ""
        prompt = (
            f"{glossary_block}"
            "请基于项目级三层材料包生成一条「任务前情提要」。\n\n"
            "产品目标：用户点开一个执行了一段时间的任务时，系统像一位可靠助理，帮助他恢复判断现场："
            "这件事从哪里来，前面哪些项目材料会影响现在，接下来最容易漏掉什么判断、边界或动作。\n\n"
            "三层材料：\n"
            "A 当前任务：任务说明、阻塞、下一步、近期决策、任务笔记、任务附件。\n"
            "B 同事件线：前后任务、活动、会议、附件、事件线记录。\n"
            "C 同客户/项目：同客户任务链、复盘、数据中心全文片段。\n\n"
            "写作要求：\n"
            "1. brief 120-190 个中文字符，直接成段，不要标题。\n"
            "2. 不要写「本任务为」「截止时间」「过往 N 项记录」，不要复述系统字段。\n"
            "3. 必须吸收项目级材料，而不只是当前任务碎片；要体现为什么这件事现在这样做。\n"
            "4. 必须点出下一步最容易遗漏的判断、边界或动作。\n"
            "5. 不虚构材料里没有的人名、数字、承诺、结果和因果。\n"
            "6. 涉及具体数字/日期/金额时，**优先引用上方字典权威值**（如有），并用 [📚 term.attribute] 标记。\n"
            "7. 材料不足时 shouldDisplay=false，brief 留空，并在 qualityFlags 说明原因。\n"
            "8. usedProjectSignals 列出真正用到的 3-5 条项目信号；materialBoundary 简述材料边界。\n\n"
            f"材料包：\n{raw_material}"
        )
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是益语智库的项目级任务前情提要助手。只返回 JSON。",
                    schema,
                    timeout_seconds=35.0,
                    max_tokens=900,
                    temperature=0.38,
                    top_p=0.88,
                    enable_thinking=False,
                )
                if isinstance(result, dict):
                    return {
                        "shouldDisplay": bool(result.get("shouldDisplay", True)),
                        "brief": str(result.get("brief") or "").strip(),
                        "usedProjectSignals": [
                            str(item).strip()
                            for item in (result.get("usedProjectSignals") or [])
                            if str(item).strip()
                        ][:6]
                        if isinstance(result.get("usedProjectSignals"), list)
                        else [],
                        "materialBoundary": str(result.get("materialBoundary") or "").strip(),
                        "qualityFlags": [
                            str(item).strip()
                            for item in (result.get("qualityFlags") or [])
                            if str(item).strip()
                        ]
                        if isinstance(result.get("qualityFlags"), list)
                        else [],
                    }
        except Exception:
            pass
        return {
            "shouldDisplay": False,
            "brief": "",
            "usedProjectSignals": [],
            "materialBoundary": "后台模型不可用，未生成任务前情提要。",
            "qualityFlags": ["generation_failed"],
        }

    def build_topic_task_plan(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        candidate_insight: dict[str, object] | None = None,
        organization_context: str = "",
    ) -> dict[str, object]:
        health = self.get_health()
        today_iso = datetime.now().date().isoformat()
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "tasks": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "desc": {"type": "STRING"},
                            "dueDate": {"type": "STRING"},
                            "ddl": {"type": "STRING"},
                            "note": {"type": "STRING"},
                            "priority": {"type": "STRING"},
                            "tags": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                            },
                        },
                    },
                },
            },
        }
        prompt = (
            "请根据下面的资讯候选，拆成可以直接派给同事执行的中文任务清单。"
            "输出要求：\n"
            "1. overview 用 40 到 90 字中文说明这条机会为什么值得跟进。\n"
            "2. tasks 返回 1 到 6 条可执行任务，title 必须是具体动作，不要写空泛标题。\n"
            "3. desc 用一句中文说明交付物或动作标准。\n"
            "4. dueDate 只有在材料里出现明确截止日期或时间时才填写 YYYY-MM-DD，否则留空字符串。\n"
            "5. ddl 用中文简短表达，如“3月17日前”“本周内”“待确认”。\n"
            "6. note 写补充说明，包含来源线索、限制条件或需要特别注意的点，并明确这条任务对应的推荐理由或判断依据。\n"
            "7. priority 只能是 low、normal、high。\n"
            "8. tags 返回 1 到 3 个中文标签。\n"
            "9. 任务优先从 recommendationReasons 和 practicalUses 延展开来，避免与推荐理由无关的空泛动作。\n"
            "请只根据已知材料输出，不要编造不存在的要求。\n"
            f"今天日期：{today_iso}\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n"
            f"组织 DNA：{organization_context[:1400] or '未提供'}\n"
            f"候选解析综述：{str((candidate_insight or {}).get('overview') or '无')}\n"
            f"主要内涵：{'；'.join(str(item) for item in (candidate_insight or {}).get('keyPoints', [])[:6]) or '无'}\n"
            f"推荐理由：{'；'.join(str(item) for item in (candidate_insight or {}).get('recommendationReasons', [])[:4]) or '无'}\n"
            f"实用方向：{'；'.join(str(item) for item in (candidate_insight or {}).get('practicalUses', [])[:4]) or '无'}\n"
            f"原文摘录：{(source_content or '未抓到原文全文，只有标题和摘要。')[:3600]}"
        )
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是项目执行拆解助手。只返回 JSON。",
                    schema,
                    timeout_seconds=28.0,
                    max_tokens=1800,
                )
                if isinstance(result, dict):
                    normalized = self._normalize_topic_task_plan_payload(result)
                    if normalized["tasks"]:
                        return normalized
        except Exception:
            pass
        return self._fallback_topic_task_plan(
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
            candidate_insight=candidate_insight,
        )

    def suggest_task_tags(
        self,
        *,
        title: str,
        desc: str,
        collaborator_names: list[str],
        due_date: str | None,
        module: str,
    ) -> list[str]:
        health = self.get_health()
        prompt = (
            "请根据下面的任务信息，提炼 1 到 3 个简短中文标签。"
            "标签必须具体可读，不要输出“事务、工作、内容、处理”这种空泛词。"
            "只返回 JSON，格式为 {\"tags\": [\"标签1\", \"标签2\"]}。\n"
            f"标题：{title}\n"
            f"描述：{desc or '无'}\n"
            f"协作对象：{'、'.join(collaborator_names) or '无'}\n"
            f"截止日期：{due_date or '未设置'}\n"
            f"所属模块：{module}\n"
        )
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt=prompt,
                    system_instruction="你是任务标签编辑助手。只返回 JSON。",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "tags": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                            }
                        },
                    },
                    timeout_seconds=18.0,
                )
                if isinstance(result, dict):
                    tags = [str(item).strip() for item in result.get("tags", []) if str(item).strip()]
                    if tags:
                        return tags[:3]
        except Exception:
            pass

        fallback_tags: list[str] = []
        text = f"{title} {desc}"
        mapping = [
            ("会议", ["会议", "复盘", "纪要"]),
            ("客户沟通", ["客户", "沟通", "访谈"]),
            ("材料整理", ["材料", "文档", "整理", "汇总"]),
            ("审核", ["审核", "审批", "确认"]),
            ("汇报", ["汇报", "报告", "简报", "ppt"]),
            ("高优先级", ["紧急", "高优", "优先"]),
            ("本周完成", ["本周", "周五", "周内"]),
        ]
        for label, keywords in mapping:
            if any(keyword.lower() in text.lower() for keyword in keywords) and label not in fallback_tags:
                fallback_tags.append(label)
        if due_date and not fallback_tags:
            fallback_tags.append("待确认")
        if not fallback_tags:
            fallback_tags = ["跟进中"]
        return fallback_tags[:3]

    def _normalize_topic_task_plan_payload(self, payload: dict[str, object]) -> dict[str, object]:
        overview = str(payload.get("overview") or "").strip()
        raw_tasks = payload.get("tasks", [])
        tasks: list[dict[str, object]] = []
        if isinstance(raw_tasks, list):
            for item in raw_tasks:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                due_date = self._normalize_due_date_value(item.get("dueDate"))
                ddl = str(item.get("ddl") or "").strip()
                tasks.append(
                    {
                        "title": title[:60],
                        "desc": str(item.get("desc") or "").strip()[:180],
                        "dueDate": due_date,
                        "ddl": ddl or (self._label_due_date(due_date) if due_date else "待确认"),
                        "note": str(item.get("note") or "").strip()[:280],
                        "priority": self._normalize_priority(item.get("priority")),
                        "tags": [
                            str(tag).strip()[:16]
                            for tag in item.get("tags", [])
                            if str(tag).strip()
                        ][:3]
                        if isinstance(item.get("tags"), list)
                        else [],
                    }
                )
        return {
            "overview": overview[:140],
            "tasks": tasks,
        }

    def _normalize_topic_candidate_insight_payload(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "overview": str(payload.get("overview") or "").strip()[:420],
            "keyPoints": self._normalize_string_list(payload.get("keyPoints"), max_items=6, max_length=220),
            "recommendationReasons": self._normalize_string_list(payload.get("recommendationReasons"), max_items=4, max_length=180),
            "practicalUses": self._normalize_string_list(payload.get("practicalUses"), max_items=4, max_length=160),
            "editorialNote": str(payload.get("editorialNote") or "").strip()[:520],
            "discussionPrompts": self._normalize_string_list(payload.get("discussionPrompts"), max_items=4, max_length=180),
        }

    def _enrich_topic_insight_payload(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        if self._looks_like_weak_topic_material(candidate_title, candidate_summary, source_content):
            source_hint = self._extract_topic_source_hint(candidate_title, candidate_summary)
            normalized["overview"] = (
                f"一、当前判断：这条候选暂时不能被当成一篇有效行业文章来解读。现有材料只显示原始来源提到了“{source_hint}”，"
                "更像是搜索结果误抓到的索引页、行情页或无关网页，而不是围绕当前雷达主题展开的正文内容。\n"
                "二、为什么不能直接使用：现在没有足够可靠的正文信息可供提炼，因此无法负责任地总结它的主要观点，也无法证明它对团队真的有实际价值。"
                "如果继续基于这条候选拆任务，后续执行方向很容易被带偏。\n"
                "三、对团队最有价值的动作：先复核来源链接、确认是否误抓取，并在必要时删除、归档或重新抓取更相关的中文文章；这比继续围绕一条错候选展开讨论更重要。"
            )[:420]
            normalized["keyPoints"] = [
                "当前没有抓到足够可靠的正文内容，现有信息不足以支持严肃的主题研判。",
                "候选里出现的线索更像搜索误抓到的索引页或无关页面，不像真正围绕雷达主题展开的文章。",
                "如果继续基于这条结果拆任务，后续执行方向很容易被带偏。",
            ]
            normalized["recommendationReasons"] = [
                "先识别并拦住误抓取结果，本身就是保证情报质量的重要一步。",
                "这条结果反过来说明当前雷达关键词或过滤规则还需要继续收紧。",
            ]
            normalized["practicalUses"] = [
                "把这次误抓取写成一篇“为什么情报系统容易被噪音带偏”的方法反思。",
                "围绕“如何判断一条线索是否值得进入候选池”整理一套内部筛选标准。",
                "把这条错候选当成案例，讨论应该怎样收紧雷达描述、时间窗和优先网址策略。",
            ]
            normalized["editorialNote"] = (
                "真正值得警惕的不是这条候选本身，而是它暴露出的情报系统误抓风险。"
                "当抓取链路把索引页、无关页或弱线索误当成正文时，团队后续的判断、讨论甚至任务安排都会建立在错误底稿上。"
                "这提醒我们：高质量情报站不仅要会抓，还要会及时识别噪音、收紧规则，并把“为什么这条内容不值得看”也沉淀成方法论。"
            )[:520]
            normalized["discussionPrompts"] = [
                "这条候选是因为搜索词过宽、时间窗失效，还是站点解析规则不准才进入候选池？",
                "如果以后再遇到类似噪音，系统应该在哪一层把它挡掉，而不是等人工兜底？",
                "哪些判断信号可以帮助我们更早识别“看起来像资讯、其实不是正文”的结果？",
            ]
            return normalized

        overview = str(normalized.get("overview") or "").strip()
        filtered_key_points = [
            item for item in normalized["keyPoints"]
            if not self._looks_like_topic_noise(item, candidate_title)
        ]
        if not filtered_key_points:
            filtered_key_points = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        if filtered_key_points:
            normalized["keyPoints"] = filtered_key_points[:6]

        summary_text = ""
        if self._has_sufficient_cjk(candidate_summary) and not self._looks_like_topic_noise(candidate_summary, candidate_title):
            summary_text = self._compact_topic_sentence(candidate_summary, 180)
        elif filtered_key_points:
            summary_text = "；".join(self._compact_topic_sentence(item, 90) for item in filtered_key_points[:2])
        elif overview and not self._looks_generic_topic_overview(overview):
            summary_text = self._compact_topic_sentence(overview, 180)
        else:
            summary_text = f"这篇内容围绕“{candidate_title[:32]}”展开，当前抓到的材料显示它更关注该主题背后的关键事实、方法线索或可执行信息。"

        key_points = normalized["keyPoints"][:3]
        point_text = "；".join(self._compact_topic_sentence(item, 110) for item in key_points) if key_points else "当前提炼结果尚未形成足够具体的文章观点。"

        reasons = normalized["recommendationReasons"][:2]
        reason_text = "；".join(self._compact_topic_sentence(item, 90) for item in reasons) if reasons else "需要进一步核对原文后再决定是否值得跟进。"

        normalized["overview"] = (
            f"一、这篇内容主要讲什么：{summary_text}\n"
            f"二、文章里最值得抓住的观点：{point_text}\n"
            f"三、它对团队的实际价值：{reason_text}"
        )[:420]
        focus_text = f"{candidate_title} {candidate_summary} {source_content}".lower()
        source_sentences = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        editorial_note = str(normalized.get("editorialNote") or "").strip()
        generic_editorial_note = self._looks_generic_topic_editorial_note(editorial_note)
        needs_grounded_editorial_note = not editorial_note or len(editorial_note) < 120 or generic_editorial_note
        if needs_grounded_editorial_note:
            if re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                editorial_note = (
                    "如果把这类信息当成一个产品线索来看，它解决的不是“有没有机会”这么简单，而是告诉你：外部资方现在到底按什么标准筛人。"
                    "它真正的价值，是帮团队少走弯路，早点看清楚申请方最看重的是项目逻辑、执行证据，还是机构叙事。"
                    "所以大周更在意的不是窗口又多了一个，而是这篇内容有没有把评估口径讲明白；如果讲明白了，它就能直接反过来指导我们准备材料、补能力、改表达。"
                )
            elif re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇东西当成产品问题来看，它在提醒你的不是“又多了几个风险名词”，而是这类系统一旦碰真实业务，治理就是产品的一部分。"
                    "换句话说，它解决不了安全和责任边界之前，功能再强也很难真的落地。"
                    "所以它的实用价值，是帮团队提前想清楚哪些权限、流程和兜底机制必须先配上；不然项目很容易卡在试用可以、上线不行。"
                )
            elif re.search(r"(github|开源|repo|仓库|star|stars)", focus_text, re.I):
                editorial_note = (
                    "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。"
                    "它真正值钱的地方，通常也不是功能清单有多长，而是把原来很重、很慢、很专业的一段流程，压缩成普通人也能先跑起来的一套用法。"
                    "所以大周更关心的是：这个项目到底解决了什么具体问题，能让谁少花时间、少踩坑、少依赖专家；如果这些答案说得清，它才不是“又一个开源仓库”，而是真有可能接进真实工作流的东西。"
                )
                discussion_prompts = [
                    "这个项目最核心是在替用户省哪一步麻烦？",
                    "它带来的价值更像提效工具，还是会直接改掉一段工作流？",
                    "如果真要落进团队或客户场景，最大的使用门槛会卡在哪？",
                ]
            elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇内容当成一个增长问题来看，它在讲的其实不是“文案怎么写得更好看”，而是组织怎么更稳定地拿到注意力和信任。"
                    "它的价值在于把那些真正影响转化和关系维护的环节说具体了，比如内容怎么组织、渠道怎么选、关系怎么接住。"
                    "所以大周不会只把它当技巧贴，而会看它到底是在修一个短期转化问题，还是在帮组织建立更长期的筹资和品牌能力。"
                )
            elif re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇东西当成产品在看，它真正解决的通常不是“AI 能不能再炫一点”，而是某个原本又慢又重的工作环节能不能被直接做薄。"
                    "它最值得看的价值，也不是多了一个新功能，而是把谁的时间省下来了、把哪段流程缩短了、让哪些原本做不到的人也能先把事做起来。"
                    "所以大周会更关心它是不是已经从演示玩具变成了能接进真实业务的工具：如果答案是可以，那它改的就不只是效率，而是团队以后怎么交付、客户以后会期待什么。"
                )
                discussion_prompts = [
                    "这个工具最直接替人省掉的是哪一步，而不是哪句概念？",
                    "它创造的价值更像提效插件，还是会直接改掉一段业务流程？",
                    "如果真要落地，最可能卡在数据、流程、权限还是使用门槛？",
                ]
            else:
                editorial_note = (
                    "如果把这篇内容当成一个产品线索来看，最值得先讲清楚的不是新闻本身，而是它到底把哪个老问题说透了。"
                    "它有没有把一个原本模糊的痛点讲具体，有没有告诉你谁会直接受益、谁会被迫调整、或者哪一步流程会因此被改写。"
                    "对大周来说，这才是它的实用价值：不是把新闻再复述一遍，而是把“这东西到底有啥用、为什么值得花时间看”讲成人能马上听懂的话。"
                )
        if needs_grounded_editorial_note:
            editorial_note = self._build_grounded_topic_editorial_note(
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                key_points=normalized["keyPoints"],
                recommendation_reasons=normalized["recommendationReasons"],
                source_sentences=source_sentences,
                fallback=editorial_note,
            )
        normalized["editorialNote"] = editorial_note[:520]

        writing_angles = normalized["practicalUses"][:4]
        if not writing_angles:
            if re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                writing_angles = [
                    "从这篇文章切入，讨论资助方正在通过哪些信号重新定义“值得支持的机构能力”。",
                    "围绕机会线索背后的门槛变化，写一篇“为什么现在的申报竞争越来越像能力审计”的评论。",
                    "把文章中的项目要求、叙事方式和材料标准拆开，整理成机构如何准备外部合作窗口的参考框架。",
                ]
            elif re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                writing_angles = [
                    "以这篇案例为切口，分析 AI 工具正在怎样改写咨询、研发或知识工作的专业分工。",
                    "围绕“从提效工具到业务机会”的跃迁，写一篇 AI 落地为何开始重塑服务边界的评论。",
                    "把文中的落地案例拆成组织能力、流程变化和商业价值三层，形成内部分享主题。",
                ]
            elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
                writing_angles = [
                    "围绕文章中的筹资或传播案例，写一篇公众注意力变化如何倒逼组织改写叙事方式的评论。",
                    "把文中方法放进更长的品牌建设周期里，讨论短期转化与长期关系之间的张力。",
                    "从捐赠人或公众视角重写这篇内容，分析他们真正被什么样的组织表达打动。",
                ]
            else:
                writing_angles = [
                    "以这篇文章为起点，写一篇“表面信息之下更值得关注的结构性变化”评论。",
                    "把文章中的案例、判断和门槛拆开，形成一篇更适合团队内部讨论的前哨短文。",
                    "围绕文中最容易被忽略的一条信号，展开成更完整的行业观察或方法反思。",
                ]
        normalized["practicalUses"] = writing_angles[:4]

        discussion_prompts = normalized["discussionPrompts"][:4]
        if not discussion_prompts or generic_editorial_note:
            if re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                discussion_prompts = [
                    "这篇文章提到的能力变化，哪些会真正改变团队的服务方式，哪些只是表层提效？",
                    "如果这些案例持续增多，团队的专业壁垒未来应该建立在什么地方？",
                    "文章里的落地路径是否依赖特定组织条件，还是已经具备可迁移性？",
                ]
            elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                discussion_prompts = [
                    "这篇内容反映的资助偏好变化，和我们当前项目准备方式之间有哪些错位？",
                    "如果要把这类窗口真正抓住，机构最缺的是材料、证据、叙事能力还是执行能力？",
                    "文章里的要求是一次性门槛，还是说明外部评估标准正在长期变化？",
                ]
            else:
                discussion_prompts = [
                    "这篇文章表面的信息背后，真正值得继续追问的结构性变化是什么？",
                    "如果把这条线索放进更长的时间线上看，它说明判断标准正在怎样变化？",
                    "文章里的观点对团队当前工作最有启发的一层，不是事实本身，而是什么？",
                ]
        if generic_editorial_note or not discussion_prompts:
            discussion_prompts = self._build_grounded_topic_discussion_prompts(
                candidate_title=candidate_title,
                key_points=normalized["keyPoints"],
                recommendation_reasons=normalized["recommendationReasons"],
                source_sentences=source_sentences,
            )
        normalized["discussionPrompts"] = discussion_prompts[:4]
        return normalized

    def _localize_topic_insight_payload(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        if self._topic_insight_is_chinese(normalized):
            return self._enrich_topic_insight_payload(
                normalized,
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                source=source,
                source_content=source_content,
            )

        health = self.get_health()
        if not health.ready or health.provider == "mock":
            return self._fallback_localized_topic_insight(
                normalized,
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                source=source,
                source_content=source_content,
            )

        schema = {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "keyPoints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "recommendationReasons": {"type": "ARRAY", "items": {"type": "STRING"}},
                "practicalUses": {"type": "ARRAY", "items": {"type": "STRING"}},
                "editorialNote": {"type": "STRING"},
                "discussionPrompts": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        prompt = (
            "请把下面这份资讯解析改写成自然、准确、完整的中文版本。"
            "要求：\n"
            "1. overview、keyPoints、recommendationReasons、practicalUses、editorialNote、discussionPrompts 必须全部是中文。\n"
            "1a. overview 必须展开写，至少 140 字，清楚交代文章主旨、主要观点和对团队的价值，不要只写一句结论。\n"
            "1b. editorialNote 必须改成口语化、像产品经理跟同事解释价值的说法。至少 180 字，优先讲清楚它解决什么问题、给谁省了什么、为什么现在值得看，以及落地会卡在哪。不要写成新闻评论、官样文章或宏大社论。\n"
            "1c. 如果内容是 GitHub 开源项目、技术工具或新产品，直接用“它到底替用户省了哪一步麻烦、为什么这一步值钱”来改写，不要先讲行业趋势或大词判断。\n"
            "2. 可以结合候选标题、摘要和原文摘录，把过于泛的地方改得更具体，但不能编造事实。\n"
            "3. keyPoints 重点提炼文章真正有价值的信息点；recommendationReasons 要写得更像“这个东西到底有啥用”；practicalUses 改写成可直接成文的角度；discussionPrompts 改写成值得继续追问的问题。\n"
            "4. 返回 JSON，不要输出解释。\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n"
            f"原文摘录：{(source_content or '暂无原文摘录。')[:3600]}\n"
            f"当前解析 overview：{normalized['overview']}\n"
            f"当前解析 keyPoints：{'；'.join(normalized['keyPoints']) or '无'}\n"
            f"当前解析 recommendationReasons：{'；'.join(normalized['recommendationReasons']) or '无'}\n"
            f"当前解析 practicalUses：{'；'.join(normalized['practicalUses']) or '无'}\n"
            f"当前解析 editorialNote：{normalized['editorialNote'] or '无'}\n"
            f"当前解析 discussionPrompts：{'；'.join(normalized['discussionPrompts']) or '无'}"
        )
        try:
            result = self._qwen_generate(
                prompt,
                "你是资讯翻译与提炼助手。只返回 JSON。",
                schema,
                timeout_seconds=24.0,
                max_tokens=1600,
            )
            if isinstance(result, dict):
                localized = self._normalize_topic_candidate_insight_payload(result)
                if self._topic_insight_is_chinese(localized):
                    return self._enrich_topic_insight_payload(
                        localized,
                        candidate_title=candidate_title,
                        candidate_summary=candidate_summary,
                        source=source,
                        source_content=source_content,
                    )
        except Exception:
            pass
        return self._fallback_localized_topic_insight(
            normalized,
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            source_content=source_content,
        )

    def _normalize_string_list(self, value: object, *, max_items: int, max_length: int) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if not text or text in items:
                continue
            items.append(text[:max_length])
            if len(items) >= max_items:
                break
        return items

    def _fallback_topic_candidate_insight(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
    ) -> dict[str, object]:
        raw_text = "\n".join(part for part in [candidate_summary, source_content] if part).strip() or candidate_title
        sentences = [
            segment.strip(" -")
            for segment in re.split(r"[\n。！？!?；;]+", raw_text)
            if segment.strip()
        ]
        key_points: list[str] = []
        for sentence in sentences:
            text = sentence.strip()
            if len(text) < 8:
                continue
            if self._looks_like_topic_noise(text, candidate_title):
                continue
            if text not in key_points:
                key_points.append(text[:150])
            if len(key_points) >= 4:
                break
        if not key_points:
            key_points = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        if not key_points:
            summary_candidate = candidate_summary[:150] if candidate_summary and not self._looks_like_topic_noise(candidate_summary, candidate_title) else ""
            key_points = [summary_candidate or candidate_title]

        focus_text = f"{candidate_title} {candidate_summary} {source_content}".lower()
        recommendation_reasons: list[str] = []
        practical_uses: list[str] = []
        if re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容直接对应大模型落地中的真实安全与合规问题，适合帮助团队判断哪些风险需要在项目推进前就前置处理。",
                "如果文章把风险场景、防护机制和治理路径讲得足够具体，就能为团队制定内部安全要求、供应商评估标准或试点边界提供参考。",
            ]
            practical_uses = [
                "围绕风险治理前置这件事，写一篇大模型项目为何不能只看功能上线的评论。",
                "把文章中的风险案例拆成“场景、后果、治理动作”，形成一篇安全观察短文。",
                "从供应商评估或项目边界切入，讨论安全要求如何变成业务落地门槛。",
            ]
        elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容可能对应真实的资金、合作或项目申报窗口，值得尽快判断是否匹配当前机构需求。",
                "文章里通常会带出申请条件、截止时间或所需资料，对团队推进资源争取有直接帮助。",
            ]
            practical_uses = [
                "从这条线索切入，写一篇资助窗口背后正在怎样重写机构能力评估标准的评论。",
                "把文中的门槛、主题和材料要求拆开，形成一篇“为什么申报越来越像能力审计”的文章提纲。",
                "围绕外部机会与内部准备之间的错位，整理成一次团队内部讨论分享。",
            ]
        elif re.search(r"(ai|大模型|模型|copilot|自动化|数字化|工具)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容更像方法或案例信号，可以帮助团队快速理解同类组织在技术上的真实落地方式。",
                "如果文章提到具体做法、流程或产品选择，适合沉淀成内部学习资料或试点清单。",
            ]
            practical_uses = [
                "以这篇案例为切口，分析 AI 工具为什么开始改变专业工作的交付边界。",
                "把文中的落地路径拆成能力变化、流程变化和商业变化，形成一篇前哨观察。",
                "围绕“AI 从提效走向重构工作流”写一篇更适合对外分享的评论框架。",
            ]
        elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容可能反映筹资或传播领域的新打法，适合用于调整当前团队的外部沟通策略。",
                "如果文章包含案例和结果数据，能直接帮助判断哪些动作值得试做或复盘。",
            ]
            practical_uses = [
                "从公众注意力变化切入，写一篇筹资与传播为什么正在失去旧有默认打法的评论。",
                "把文章中的案例放进更长的品牌建设周期里，形成一篇方法反思。",
                "围绕捐赠人关系如何被重新定义，整理成团队内部研讨的切口。",
            ]
        else:
            recommendation_reasons = [
                "这条内容提供了可继续追踪的行业线索，值得先判断它是否与当前项目方向相关。",
                "如果文中包含可验证的信息点或案例，适合先沉淀成内部参考，再决定是否进一步投入。",
            ]
            practical_uses = [
                "把文章里最值得抓住的一条变化展开，写成一篇前哨式短评。",
                "从案例背后的结构性变化切入，整理成一次团队内部讨论发言。",
                "围绕文中最容易被忽略的一条判断，形成后续选题角度。",
            ]

        overview_seed = ""
        if self._has_sufficient_cjk(candidate_summary):
            overview_seed = candidate_summary[:90]
        elif key_points and self._has_sufficient_cjk(key_points[0]):
            overview_seed = key_points[0][:90]

        if overview_seed:
            overview = f"这篇内容主要围绕“{candidate_title[:28]}”展开，重点提到：{overview_seed}"
        else:
            overview = (
                f"这条内容来自 {source}，核心价值在于它不只是提供资讯本身，"
                f"还带出了可供团队学习、判断机会或补充资源的具体线索。"
            )
            if published_at:
                overview += f" 发布时间为 {published_at[:10]}。"
        if source_url and not practical_uses:
            practical_uses.append("把原文里的关键信号和边界条件拆开，形成一篇更完整的评论角度。")

        editorial_note = ""
        discussion_prompts: list[str] = []
        if re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
            editorial_note = (
                "如果把这篇东西当成产品问题来看，它在提醒你的不是“又多了几个风险名词”，而是这类系统一旦碰真实业务，治理就是产品的一部分。"
                "换句话说，它解决不了安全和责任边界之前，功能再强也很难真的落地。"
                "所以它的实用价值，是帮团队提前想清楚哪些权限、流程和兜底机制必须先配上；不然项目很容易卡在试用可以、上线不行。"
            )
            discussion_prompts = [
                "这里提到的风险，哪些已经是我们当前项目必须先回答的？",
                "如果真要落地，最容易卡住的会是权限、流程还是责任归属？",
                "哪些治理要求应该在项目启动前就讲清楚，而不是等出事后再补？",
            ]
        elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
            editorial_note = (
                "如果把这类信息当成一个产品线索来看，它解决的不是“有没有机会”这么简单，而是告诉你：外部资方现在到底按什么标准筛人。"
                "它真正的价值，是帮团队少走弯路，早点看清楚申请方最看重的是项目逻辑、执行证据，还是机构叙事。"
                "所以大周更在意的不是窗口又多了一个，而是这篇内容有没有把评估口径讲明白；如果讲明白了，它就能直接反过来指导我们准备材料、补能力、改表达。"
            )
            discussion_prompts = [
                "这篇内容真正告诉我们的，是机会本身，还是资方的筛选标准？",
                "如果要去争取这类窗口，我们最缺的是材料、证据，还是项目逻辑？",
                "这里面哪些要求是一次性门槛，哪些是长期的能力要求？",
            ]
        elif re.search(r"(github|开源|repo|仓库|star|stars)", focus_text, re.I):
            editorial_note = (
                "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。"
                "它真正值钱的地方，通常也不是功能清单有多长，而是把原来很重、很慢、很专业的一段流程，压缩成普通人也能先跑起来的一套用法。"
                "所以大周更关心的是：这个项目到底解决了什么具体问题，能让谁少花时间、少踩坑、少依赖专家；如果这些答案说得清，它才不是“又一个开源仓库”，而是真有可能接进真实工作流的东西。"
            )
            discussion_prompts = [
                "这个项目最核心是在替用户省哪一步麻烦？",
                "它带来的价值更像提效工具，还是会直接改掉一段工作流？",
                "如果真要落进团队或客户场景，最大的使用门槛会卡在哪？",
            ]
        elif re.search(r"(ai|大模型|模型|copilot|自动化|数字化|工具)", focus_text, re.I):
            editorial_note = (
                "如果把这篇东西当成产品在看，它真正解决的通常不是“AI 能不能再炫一点”，而是某个原本又慢又重的工作环节能不能被直接做薄。"
                "它最值得看的价值，也不是多了一个新功能，而是把谁的时间省下来了、把哪段流程缩短了、让哪些原本做不到的人也能先把事做起来。"
                "所以大周会更关心它是不是已经从演示玩具变成了能接进真实业务的工具：如果答案是可以，那它改的就不只是效率，而是团队以后怎么交付、客户以后会期待什么。"
            )
            discussion_prompts = [
                "这个工具最直接替人省掉的是哪一步，而不是哪句概念？",
                "它创造的价值更像提效插件，还是会直接改掉一段业务流程？",
                "如果真要落地，最可能卡在数据、流程、权限还是使用门槛？",
            ]
        elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
            editorial_note = (
                "如果把这篇内容当成一个增长问题来看，它在讲的其实不是“文案怎么写得更好看”，而是组织怎么更稳定地拿到注意力和信任。"
                "它的价值在于把那些真正影响转化和关系维护的环节说具体了，比如内容怎么组织、渠道怎么选、关系怎么接住。"
                "所以大周不会只把它当技巧贴，而会看它到底是在修一个短期转化问题，还是在帮组织建立更长期的筹资和品牌能力。"
            )
            discussion_prompts = [
                "它解决的更像短期转化问题，还是长期关系问题？",
                "如果真照着做，最先要改的是内容、渠道，还是关系维护方式？",
                "这篇内容背后真正变了的，是传播动作，还是公众判断标准？",
            ]
        else:
            editorial_note = (
                "如果把这篇内容当成一个产品线索来看，最值得先讲清楚的不是新闻本身，而是它到底把哪个老问题说透了。"
                "它有没有把一个原本模糊的痛点讲具体，有没有告诉你谁会直接受益、谁会被迫调整、或者哪一步流程会因此被改写。"
                "对大周来说，这才是它的实用价值：不是把新闻再复述一遍，而是把“这东西到底有啥用、为什么值得花时间看”讲成人能马上听懂的话。"
            )
            discussion_prompts = [
                "它真正解决的问题到底是什么，而不是表面在说什么？",
                "如果真把它用起来，最先会改掉的是哪一步旧流程？",
                "这条线索最值得继续核实的，不是新闻本身，而是哪种实际价值？",
            ]

        return {
            "overview": overview[:180],
            "keyPoints": key_points[:4],
            "recommendationReasons": recommendation_reasons[:4],
            "practicalUses": practical_uses[:4],
            "editorialNote": editorial_note[:520],
            "discussionPrompts": discussion_prompts[:4],
        }

    def _fallback_localized_topic_insight(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        overview = normalized["overview"]
        if not self._has_sufficient_cjk(overview):
            summary_hint = candidate_summary if self._has_sufficient_cjk(candidate_summary) else ""
            overview = (
                summary_hint
                or f"这条内容来自 {source}，主题围绕“{candidate_title[:40]}”，建议结合原文继续核对关键细节与可执行线索。"
            )[:180]

        key_points = [item for item in normalized["keyPoints"] if self._has_sufficient_cjk(item)]
        if not key_points:
            if self._has_sufficient_cjk(candidate_summary):
                key_points = [candidate_summary[:150]]
            else:
                key_points = [f"文章主要围绕“{candidate_title[:40]}”展开，建议结合原文核对更具体的信息点。"]

        recommendation_reasons = [item for item in normalized["recommendationReasons"] if self._has_sufficient_cjk(item)]
        if not recommendation_reasons:
            recommendation_reasons = [
                "这条内容提到了值得继续核实的信息点，适合先判断是否与当前工作方向相关。",
                "如果原文包含具体案例、门槛或资源线索，适合沉淀成内部参考后再决定是否推进。",
            ]

        practical_uses = [item for item in normalized["practicalUses"] if self._has_sufficient_cjk(item)]
        if not practical_uses:
            practical_uses = [
                "把文章里最有价值的一条观点展开成一篇短评，解释它为什么不只是个案。",
                "围绕文中提到的方法或案例，写一篇更适合团队内部分享的前哨观察。",
                "从文章最容易被忽略的一条信号切入，形成一个可继续讨论的写作角度。",
            ]

        editorial_note = str(normalized.get("editorialNote") or "").strip()
        if not self._has_sufficient_cjk(editorial_note):
            editorial_note = (
                "如果把这篇内容当成一个产品线索来看，最有用的地方不是再复述一遍新闻，而是先说清楚它到底解决什么问题。"
                "它有没有帮人省步骤、降门槛、提效率，或者把原来很难做的一件事变得更容易，这些才是大周更在意的。"
                "所以比起写成评论稿，我更想把它讲成人话：这东西值不值得看，关键就看它到底有没有把某个具体麻烦真的做薄。"
            )[:520]

        discussion_prompts = [item for item in normalized["discussionPrompts"] if self._has_sufficient_cjk(item)]
        if not discussion_prompts:
            discussion_prompts = [
                "这篇文章最值得继续追问的变化，不是事实本身，而是什么？",
                "如果把文章里的案例放进更长时间线里看，它预示了怎样的结构性变化？",
                "文中的观点对团队当前判断最有用的一层，究竟是方法、趋势，还是门槛变化？",
            ]

        return self._enrich_topic_insight_payload(
            {
                "overview": overview,
                "keyPoints": key_points[:6],
                "recommendationReasons": recommendation_reasons[:4],
                "practicalUses": practical_uses[:4],
                "editorialNote": editorial_note,
                "discussionPrompts": discussion_prompts[:4],
            },
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            source_content=source_content,
        )

    def _fallback_topic_task_plan(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        candidate_insight: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raw_text = "\n".join(
            part for part in [candidate_title, candidate_summary, source_content] if part
        )
        due_date = self._extract_due_date_from_text(raw_text)
        deadline_label = self._label_due_date(due_date) if due_date else ("待确认" if re.search(r"(截止|deadline|due|截至|报名时间)", raw_text, re.I) else "本周内")
        insight_overview = str((candidate_insight or {}).get("overview") or "").strip()
        recommendation_reasons = self._normalize_string_list((candidate_insight or {}).get("recommendationReasons"), max_items=4, max_length=160)
        practical_uses = self._normalize_string_list((candidate_insight or {}).get("practicalUses"), max_items=4, max_length=100)
        overview = insight_overview or f"这条线索来自 {source}，建议先核对机会要求、准备材料，并尽快确认是否进入正式推进。"
        note_prefix = f"来源：{source}"
        if published_at:
            note_prefix += f"；发布时间：{published_at[:10]}"
        if source_url:
            note_prefix += f"；链接：{source_url}"

        if practical_uses:
            tasks: list[dict[str, object]] = []
            for index, action in enumerate(practical_uses[:3]):
                reason = recommendation_reasons[min(index, len(recommendation_reasons) - 1)] if recommendation_reasons else "这条内容值得继续跟进。"
                due = due_date if index == len(practical_uses[:3]) - 1 else None
                tasks.append(
                    {
                        "title": action[:60],
                        "desc": f"围绕“{reason[:36]}”完成这项动作，并把结论回写到任务记录里。",
                        "dueDate": due,
                        "ddl": deadline_label if due else ("今天" if index == 0 else "本周内"),
                        "note": f"{note_prefix}；关联理由：{reason}",
                        "priority": "high" if index == 0 else "normal",
                        "tags": ["资讯跟进", "选题解析"][:2],
                    }
                )
            return {
                "overview": overview,
                "tasks": tasks,
            }

        funding_like = bool(re.search(r"(资助|申报|申请|基金|grant|征集|招募|报名)", raw_text, re.I))
        if funding_like:
            tasks = [
                {
                    "title": "核对资助要求并确认申报策略",
                    "desc": "确认申请条件、资助方向、所需材料和内部是否值得申报。",
                    "dueDate": None,
                    "ddl": "今天",
                    "note": f"{note_prefix}；先判断这条机会与机构当前项目是否匹配。",
                    "priority": "high",
                    "tags": ["机会评估", "资助申报"],
                },
                {
                    "title": "整理机构资料与证明材料",
                    "desc": "准备机构简介、项目案例、预算说明和过往成果等申报材料。",
                    "dueDate": None,
                    "ddl": "本周内",
                    "note": f"{note_prefix}；把历史案例和证明文件统一整理成可提交版本。",
                    "priority": "normal",
                    "tags": ["材料准备"],
                },
                {
                    "title": "撰写并提交申请材料",
                    "desc": "根据要求完成申请表和附件填写，并在截止前完成提交。",
                    "dueDate": due_date,
                    "ddl": deadline_label,
                    "note": f"{note_prefix}；若原文有明确截止时间，请以原文时间为准。",
                    "priority": "high",
                    "tags": ["申请提交"],
                },
            ]
        else:
            tasks = [
                {
                    "title": "确认这条机会的适配性与优先级",
                    "desc": "梳理核心要求、适用对象和推进价值，判断是否值得继续投入。",
                    "dueDate": None,
                    "ddl": "今天",
                    "note": f"{note_prefix}；先完成机会评估，再决定后续动作。",
                    "priority": "normal",
                    "tags": ["机会评估"],
                },
                {
                    "title": "整理对外沟通或执行所需材料",
                    "desc": "准备介绍材料、案例、联系人信息或内部决策依据，形成可执行包。",
                    "dueDate": None,
                    "ddl": "本周内",
                    "note": f"{note_prefix}；把分散资料归并成一份可交接材料。",
                    "priority": "normal",
                    "tags": ["材料整理"],
                },
                {
                    "title": "安排后续跟进并记录下一步",
                    "desc": "明确谁来推进、何时反馈，以及是否需要在截止前提交或报名。",
                    "dueDate": due_date,
                    "ddl": deadline_label,
                    "note": f"{note_prefix}；如果原文没有明确截止时间，请在备注里补齐。",
                    "priority": "normal",
                    "tags": ["后续跟进"],
                },
            ]
        return {
            "overview": overview,
            "tasks": tasks,
        }

    def _normalize_due_date_value(self, value: object) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            return text
        return self._extract_due_date_from_text(text)

    def _extract_due_date_from_text(self, text: str) -> str | None:
        today = datetime.now().date()
        direct = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        if direct:
            return direct.group(1)
        zh_match = re.search(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日", text)
        if zh_match:
            year = int(zh_match.group(1) or today.year)
            month = int(zh_match.group(2))
            day = int(zh_match.group(3))
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                return None
        en_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:,\s*(20\d{2}))?",
            text,
            re.I,
        )
        if en_match:
            month_map = {
                "jan": 1,
                "january": 1,
                "feb": 2,
                "february": 2,
                "mar": 3,
                "march": 3,
                "apr": 4,
                "april": 4,
                "may": 5,
                "jun": 6,
                "june": 6,
                "jul": 7,
                "july": 7,
                "aug": 8,
                "august": 8,
                "sep": 9,
                "sept": 9,
                "september": 9,
                "oct": 10,
                "october": 10,
                "nov": 11,
                "november": 11,
                "dec": 12,
                "december": 12,
            }
            month = month_map[en_match.group(1).lower()]
            day = int(en_match.group(2))
            year = int(en_match.group(3) or today.year)
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                return None
        return None

    def _label_due_date(self, due_date: str | None) -> str:
        if not due_date:
            return "待确认"
        try:
            date = datetime.fromisoformat(due_date).date()
        except ValueError:
            return due_date
        return f"{date.month}月{date.day}日前"

    def _normalize_priority(self, value: object) -> str:
        text = str(value or "normal").strip().lower()
        return text if text in {"low", "normal", "high"} else "normal"

    def _has_sufficient_cjk(self, text: str) -> bool:
        matches = re.findall(r"[\u4e00-\u9fff]", text or "")
        return len(matches) >= 4

    def _topic_insight_is_chinese(self, payload: dict[str, object]) -> bool:
        overview = str(payload.get("overview") or "").strip()
        if not self._has_sufficient_cjk(overview):
            return False
        editorial_note = str(payload.get("editorialNote") or "").strip()
        if not self._has_sufficient_cjk(editorial_note):
            return False
        for key in ("keyPoints", "recommendationReasons", "practicalUses", "discussionPrompts"):
            values = payload.get(key)
            if not isinstance(values, list) or not values:
                return False
            if any(not self._has_sufficient_cjk(str(item)) for item in values):
                return False
        return True

    def _looks_like_topic_noise(self, text: str, candidate_title: str) -> bool:
        compact = re.sub(r"\s+", "", text)
        title_compact = re.sub(r"\s+", "", candidate_title or "")
        noise_patterns = (
            "点赞",
            "收藏",
            "评论",
            "关注",
            "打开知乎",
            "下载app",
            "下载App",
            "APP",
            "上一页",
            "下一页",
        )
        if self._is_title_like_topic_text(text, candidate_title):
            return True
        if any(pattern.lower() in compact.lower() for pattern in noise_patterns):
            return True
        if re.search(r"(?:https?://|www\.|\.com\b|\.net\b|\.cn\b)", text.lower()) and len(compact) < 140:
            return True
        if title_compact and compact.count(title_compact[:12]) >= 2:
            return True
        return False

    def _is_title_like_topic_text(self, text: str, candidate_title: str) -> bool:
        compact = re.sub(r"\s+", "", text or "")
        title_compact = re.sub(r"\s+", "", candidate_title or "")
        if not compact or not title_compact:
            return False
        if compact == title_compact:
            return True
        if title_compact in compact and abs(len(compact) - len(title_compact)) <= 18:
            return True
        return False

    def _extract_topic_source_sentences(self, source_content: str, candidate_title: str, *, max_items: int) -> list[str]:
        sentences = [
            segment.strip(" -")
            for segment in re.split(r"[\n。！？!?；;]+", source_content or "")
            if segment.strip()
        ]
        items: list[str] = []
        for sentence in sentences:
            text = sentence.strip()
            if len(text) < 10:
                continue
            if self._looks_like_topic_noise(text, candidate_title):
                continue
            if text in items:
                continue
            items.append(text[:180])
            if len(items) >= max_items:
                break
        return items

    def _looks_like_weak_topic_material(self, candidate_title: str, candidate_summary: str, source_content: str) -> bool:
        summary = (candidate_summary or "").strip()
        title = (candidate_title or "").strip()
        if "原始来源提到" in summary:
            return True
        if "相关机会" in title and not source_content:
            return True
        if not source_content and not self._has_sufficient_cjk(summary) and re.search(r"[A-Za-z]{8,}", title):
            return True
        return False

    def _extract_topic_source_hint(self, candidate_title: str, candidate_summary: str) -> str:
        match = re.search(r"原始来源提到“([^”]+)”", candidate_summary or "")
        if match:
            return match.group(1).strip()[:80]
        return (candidate_title or "未知来源").strip()[:80]

    def _looks_generic_topic_overview(self, overview: str) -> bool:
        text = (overview or "").strip()
        generic_phrases = (
            "核心价值在于它不只是提供资讯本身",
            "带出了可供团队学习",
            "建议结合原文继续核对关键细节",
            "值得继续跟进",
        )
        if len(text) < 90:
            return True
        return any(phrase in text for phrase in generic_phrases)

    def _looks_generic_topic_editorial_note(self, editorial_note: str) -> bool:
        text = (editorial_note or "").strip()
        if not text:
            return True
        generic_phrases = (
            "如果把这个 GitHub 项目当成一个产品来看",
            "如果把这篇东西当成产品在看",
            "如果把这篇内容当成一个产品线索来看",
            "如果把这类信息当成一个产品线索来看",
            "如果把这篇内容当成一个增长问题来看",
            "如果把这篇东西当成产品问题来看",
            "它真正值钱的地方，通常也不是功能清单有多长",
            "它最值得看的价值，也不是多了一个新功能",
            "对大周来说，这才是它的实用价值",
        )
        return any(phrase in text for phrase in generic_phrases)

    def _looks_stale_topic_editorial_note(self, editorial_note: str) -> bool:
        text = (editorial_note or "").strip()
        stale_phrases = (
            "这篇内容背后更重要的信号",
            "真正值得深想的",
            "更深层的意义",
            "结构性变化",
            "默认做法正在被重写",
            "专业能力民主化",
            "大周自己的写作因此不会停留在复述新闻",
            "背后不仅是工具的流行",
            "更折射出",
            "深层趋势",
            "意味着双重挑战",
            "我们不应只关注工具本身",
            "组织的竞争壁垒",
            "组织需要重新审视",
        )
        if len(text) < 120:
            return True
        return self._looks_generic_topic_editorial_note(text) or any(phrase in text for phrase in stale_phrases)

    def _build_grounded_topic_editorial_note(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        key_points: list[str],
        recommendation_reasons: list[str],
        source_sentences: list[str],
        fallback: str = "",
    ) -> str:
        material_facts: list[str] = []
        for item in list(key_points or []) + list(source_sentences or []):
            text = self._compact_topic_sentence(str(item or ""), 96)
            if not text or text in material_facts:
                continue
            material_facts.append(text)
            if len(material_facts) >= 3:
                break

        value_points: list[str] = []
        for item in recommendation_reasons or []:
            text = self._compact_topic_sentence(str(item or ""), 96)
            if not text or text in value_points:
                continue
            value_points.append(text)
            if len(value_points) >= 2:
                break

        lead_fact = material_facts[0] if material_facts else self._compact_topic_sentence(candidate_summary or candidate_title, 96)
        value_fact = value_points[0] if value_points else (material_facts[1] if len(material_facts) > 1 else "")
        follow_fact = material_facts[1] if len(material_facts) > 1 else ""

        note_parts = [
            f"先别把它当成一条泛新闻，这篇材料真正值得抓住的是：{lead_fact or candidate_title[:48]}。",
        ]
        if value_fact:
            note_parts.append(f"对团队来说，它有用不是因为“又多了一条资讯”，而是因为{value_fact}。")
        elif fallback.strip():
            note_parts.append(self._compact_topic_sentence(fallback.strip(), 120) + "。")
        else:
            note_parts.append("对团队来说，更重要的是先把它到底解决了什么问题、能给谁省事这件事讲具体。")
        if follow_fact:
            note_parts.append(
                f"接下来最该继续核对的是：{follow_fact}。这部分如果原文里讲得足够具体，才能判断它到底只是热度信号，还是已经能接进真实工作流。"
            )
        else:
            note_parts.append("接下来最该继续核对的，是它的适用场景、落地门槛和边界条件有没有被原文讲清楚；这决定了它到底能不能真的拿来用。")
        return "".join(note_parts)[:520]

    def _build_grounded_topic_discussion_prompts(
        self,
        *,
        candidate_title: str,
        key_points: list[str],
        recommendation_reasons: list[str],
        source_sentences: list[str],
    ) -> list[str]:
        prompts: list[str] = []

        fact = self._compact_topic_sentence((key_points or source_sentences or [candidate_title])[0], 32)
        if fact:
            prompts.append(f"文里提到的“{fact}”到底已经在哪些真实场景里成立了？")

        reason = self._compact_topic_sentence((recommendation_reasons or [candidate_title])[0], 32)
        if reason:
            prompts.append(f"如果它最有价值的是“{reason}”，那这件事对我们现在哪类项目最直接？")

        follow = self._compact_topic_sentence((source_sentences[1] if len(source_sentences) > 1 else key_points[1] if len(key_points) > 1 else candidate_title), 32)
        if follow:
            prompts.append(f"原文里还没讲透的“{follow}”，会不会正好就是它能不能落地的关键门槛？")

        if len(prompts) < 3:
            prompts.append("如果把这条线索真的拿来用，最先需要补证据、补案例，还是补具体使用条件？")
        return prompts[:4]

    def _compact_topic_sentence(self, text: str, max_length: int) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        cleaned = cleaned.rstrip("。；;，,、")
        return cleaned[:max_length]

    def generate_knowledge_surrogate(
        self,
        *,
        title: str,
        kind: str,
        primary_category: str,
        secondary_category: str,
        raw_text: str,
        source_path: str,
        fallback: dict[str, object],
    ) -> dict[str, object]:
        health = self.get_health()
        prompt = (
            "请为知识底座生成一个给 AI 检索使用的代理文档摘要。"
            "不要写空泛总结，必须突出未来搜索时最可能使用的线索。"
            "请返回 JSON，对象字段固定为：overview_summary, retrieval_summary, document_role, core_questions, query_hints, distinct_findings, entities, time_markers。\n"
            f"标题：{title}\n类型：{kind}\n一级分类：{primary_category}\n二级分类：{secondary_category}\n原路径：{source_path}\n正文：{raw_text[:5000]}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview_summary": {"type": "STRING"},
                "retrieval_summary": {"type": "STRING"},
                "document_role": {"type": "STRING"},
                "core_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "query_hints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(prompt, "你是知识底座加工助手。只返回 JSON。", schema, timeout_seconds=25.0, task_kind="fast_structured")
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return fallback

    def generate_visual_markdown(
        self,
        *,
        title: str,
        image_base64: str,
        mime_type: str = "image/png",
        page_number: int | None = None,
        source_kind: str = "视觉资料",
        mode: str = "strict",
    ) -> str:
        """视觉 OCR。mode='strict' 默认严格模式；mode='exhaustive' 穷尽模式
        用于含印章/手写/图章的边缘页面，要求 LLM 尽力提取所有可见字符。
        """
        health = self._health_for_task("vision_ocr")
        if not health.ready or not image_base64:
            return ""
        if mode == "exhaustive":
            # R13.P3：穷尽模式 — 对印章/手写/混合图页强制输出所有可见字符
            system_instruction = (
                "你是文档 OCR 和版面还原助手（穷尽抓取模式）。\n"
                "任务：把视觉资料截图转成 markdown 原文，**穷尽**提取每一个可见的字符。\n"
                "**关键规则（严格遵守）**：\n"
                "1. 即使页面含印章、公章、红色图章、手写签字、手写日期、图章遮挡，"
                "仍必须尽力识别并输出所有可见文字（包括被印章部分遮挡的、模糊的、手写的）。\n"
                "2. 公章/印章的文字内容也要提取，格式如「[印章：XX 公司 财务专用章]」。\n"
                "3. 手写日期/签字识别为「[手写：2025年6月15日]」「[签字：张三]」等格式。\n"
                "4. 即使页面主要是图章、签字、年月日，**也禁止返回空字符串**，"
                "至少输出可见的少量正文 + 图章描述 + 手写描述。\n"
                "5. 如果页面真完全空白（连印章都没有），输出「[空白页]」字串。\n"
                "6. 不要总结、不要改写、不要补充页面没有的信息。\n"
            )
            page_line = f"页码：{page_number}\n" if page_number is not None else ""
            prompt = (
                f"文件名：{title}\n"
                f"资料类型：{source_kind}（穷尽模式 — 含印章/手写/图）\n"
                f"{page_line}\n"
                "请穷尽提取页面上**每一个可见字符**：正文段落、印章文字、手写日期、签字、表格行列、"
                "页眉页脚（保留含信息的）。即使被印章遮挡的文字也尽力还原。\n"
                "输出格式：markdown 正文 + 必要的 [印章：...] / [手写：...] / [签字：...] 标记。"
            )
        else:
            system_instruction = (
                "你是文档 OCR 和版面还原助手。"
                "你的任务是把视觉资料截图转成 clean markdown 原文。"
                "不要总结，不要改写，不要补充页面上没有的信息。"
                "如果页面几乎没有可读正文，只返回空字符串。"
            )
            page_line = f"页码：{page_number}\n" if page_number is not None else ""
            prompt = (
                f"文件名：{title}\n"
                f"资料类型：{source_kind}\n"
                f"{page_line}\n"
                "请按阅读顺序提取图像中的文字，尽量保留标题、项目符号、表格行列关系。"
                "删除页码、装饰线、明显水印和重复页眉页脚。"
                "只输出 markdown 正文。"
            )
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

        for profile in self._resolve_llm_candidates(task_kind="vision_ocr"):
            if not self._profile_is_usable(profile):
                continue
            payload = {
                "model": profile.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                            },
                        ],
                    },
                ],
                "temperature": 0.05,
                "top_p": 0.8,
                "max_tokens": 2500,
                "stream": False,
            }

            def _do_request() -> dict:
                with httpx.Client(timeout=self._build_http_timeout(45.0)) as _client:
                    _resp = _client.post(
                        f"{profile.base_url}/chat/completions",
                        headers=self._build_openai_compatible_headers(profile.api_key),
                        json=payload,
                    )
                    _resp.raise_for_status()
                    return _resp.json()

            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(_do_request)
            try:
                result = future.result(timeout=60.0)
            except FutureTimeout:
                future.cancel()
                continue
            except Exception:
                continue
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
            text = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            cleaned = str(text or "").strip()
            cleaned = re.sub(r"^```(?:markdown|md)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
            if cleaned:
                self._record_resolved_profile(profile)
                return cleaned
        return ""

    def summarize_recording_to_meeting_minutes(
        self,
        *,
        transcript: str,
        task_title_hint: str = "",
        language_hint: str = "",
        dialogue_text: str = "",
        num_speakers: int = 0,
    ) -> dict[str, str]:
        """把一段录音转写的 transcript 浓缩成会议纪要。

        - 若提供 ``dialogue_text``（"说话人A：…\\n说话人B：…\\n"），优先用它作为 LLM 输入，
          这样纪要能在行动项里点名"说话人A 要做 X"
        - 否则退回到无说话人 transcript

        返回 ``{"title": str, "minutes_md": str}``：
        - title：3-20 字的主题，用于回填任务标题
        - minutes_md：markdown 纪要（含参与方/议题/决议/行动项/未决）

        失败 / LLM 不可用时返回空字符串字段，由上层兜底。
        """
        text = (dialogue_text or transcript or "").strip()
        has_dialogue = bool((dialogue_text or "").strip())
        if not text:
            return {"title": "", "minutes_md": ""}

        health = self._health_for_task("default")
        if not health.ready:
            return {"title": "", "minutes_md": ""}

        # 4h 录音的 transcript 可能动辄几万字，给 LLM 截短：保头部 12000 字 + 尾部 1500 字
        head_limit = 12000
        tail_limit = 1500
        prepared = text
        if len(text) > head_limit + tail_limit + 200:
            prepared = f"{text[:head_limit]}\n\n[…中间省略 {len(text) - head_limit - tail_limit} 字…]\n\n{text[-tail_limit:]}"

        # 关键：说话人编号（说话人A/B/C）依赖硬件 diarization 结果，硬件不好时分得很乱。
        # 这种"软件层面无法兜底"的错乱写到产出里会被误以为是软件问题，所以**输出中绝对不
        # 出现说话人编号**——它只能作为 LLM 内部理解上下文的辅助信号。
        diarization_hint = (
            "下面是按说话人分段的对话稿，每行格式为 \"说话人X：内容\"。"
            "说话人编号只是给你做语义分段的内部辅助，可能因为录音质量被分错。"
            "**绝对不要**在你的输出里出现「说话人A」「说话人B」「说话人1/2/3」「Speaker X」"
            "或任何类似的编号标记。"
            "如果对话稿里有真实姓名（如「张总」「小李」），可以使用；"
            "否则用「与会者」「有人提出」「另一方回应」等泛指表达。"
            if has_dialogue
            else "下面是录音转写原文（无说话人分段，请基于内容自行总结）。"
        )
        system_instruction = (
            "你是经验丰富的会议纪要助手。任务：把一段录音转写文本浓缩成一份结构化会议纪要。"
            "严格输出一个 JSON 对象，字段固定为 \"title\" 和 \"minutes_md\"，禁止任何其他内容、解释或 markdown 代码块包裹。"
            "title：3-20 字，能概括这段录音核心议题，不要写日期、不要写'会议纪要'四个字。"
            "minutes_md：标准 Markdown，按以下结构组织："
            "## 概要、## 关键议题、## 决议事项、"
            "## 行动项（含责任人/截止时间；若转写里没有真实姓名，责任人写「未指派」，"
            "**严禁**写「说话人A」「说话人1」等编号）、## 未决问题。"
            "找不到某个 section 就略过该 section，不要凭空捏造内容。"
        )
        hint_lines: list[str] = []
        if task_title_hint.strip():
            hint_lines.append(f"任务原标题（仅参考，纪要标题应基于转写内容自行总结）：{task_title_hint.strip()}")
        if language_hint.strip():
            hint_lines.append(f"原音频语言：{language_hint.strip()}")
        hint_lines.append(diarization_hint)
        hint_block = "\n".join(hint_lines) + "\n\n"
        boundary_tag = "DIALOGUE" if has_dialogue else "TRANSCRIPT"
        prompt = (
            f"{hint_block}"
            f"<<<{boundary_tag}>>>\n"
            f"{prepared}\n"
            f"<<<END {boundary_tag}>>>\n\n"
            "请按系统指令输出 JSON。"
        )

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

        for profile in self._resolve_llm_candidates(task_kind="default"):
            if not self._profile_is_usable(profile):
                continue
            payload = {
                "model": profile.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "top_p": 0.8,
                "max_tokens": 2500,
                "stream": False,
            }

            def _do_request() -> dict:
                with httpx.Client(timeout=self._build_http_timeout(60.0)) as _client:
                    _resp = _client.post(
                        f"{profile.base_url}/chat/completions",
                        headers=self._build_openai_compatible_headers(profile.api_key),
                        json=payload,
                    )
                    _resp.raise_for_status()
                    return _resp.json()

            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(_do_request)
            try:
                result = future.result(timeout=90.0)
            except FutureTimeout:
                future.cancel()
                continue
            except Exception:
                continue
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

            raw_text = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            cleaned = str(raw_text or "").strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
            if not cleaned:
                continue
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                # 尝试抽出第一个 { ... } 块
                match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
                if not match:
                    continue
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue
            if not isinstance(parsed, dict):
                continue
            title = str(parsed.get("title") or "").strip()
            minutes_md = str(parsed.get("minutes_md") or "").strip()
            if not title and not minutes_md:
                continue
            # 标题兜底长度
            if len(title) > 40:
                title = title[:40]
            self._record_resolved_profile(profile)
            return {"title": title, "minutes_md": minutes_md}

        return {"title": "", "minutes_md": ""}

    def generate_pdf_page_markdown(
        self,
        *,
        title: str,
        page_number: int,
        image_base64: str,
        mime_type: str = "image/png",
    ) -> str:
        return self.generate_visual_markdown(
            title=title,
            page_number=page_number,
            image_base64=image_base64,
            mime_type=mime_type,
            source_kind="PDF 页面",
        )

    def generate_memory_surrogate(
        self,
        *,
        title: str,
        content: str,
        analysis: str,
        actions: str,
        fallback: dict[str, object],
    ) -> dict[str, object]:
        health = self.get_health()
        prompt = (
            "请把下面这条 AI 回答沉淀为可复用的战略陪伴记忆。"
            "输出必须适合未来检索和复用，不要写空话。"
            "请返回 JSON，对象字段固定为：overview_summary, retrieval_summary, document_role, core_questions, query_hints, distinct_findings, entities, time_markers。\n"
            f"标题：{title}\n回答内容：{content}\n分析：{analysis}\n建议动作：{actions}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview_summary": {"type": "STRING"},
                "retrieval_summary": {"type": "STRING"},
                "document_role": {"type": "STRING"},
                "core_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "query_hints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(prompt, "你是战略陪伴记忆整理助手。只返回 JSON。", schema, timeout_seconds=25.0)
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return fallback

    def generate_strategic_insights(
        self,
        *,
        context_pack: dict[str, object],
        limit: int = 8,
        client_id: str | None = None,
    ) -> dict[str, object]:
        health = self.get_health()
        if not health.ready:
            return {"insights": []}
        # P-E.2: 字典权威包注入战略洞察
        _glossary_pack_si = ""
        if client_id:
            try:
                from app.services.glossary_attributes_pack import build_verified_attributes_pack
                _glossary_pack_si = build_verified_attributes_pack(self.db, client_id) or ""
            except Exception:
                _glossary_pack_si = ""
        schema = {
            "type": "OBJECT",
            "properties": {
                "insights": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "insightType": {
                                "type": "STRING",
                                "enum": [
                                    "strategic_shift",
                                    "risk_signal",
                                    "opportunity_window",
                                    "execution_bottleneck",
                                    "narrative_upgrade",
                                    "operating_model",
                                ],
                            },
                            "insightText": {"type": "STRING"},
                            "futureJudgment": {"type": "STRING"},
                            "recommendedAction": {"type": "STRING"},
                            "evidenceSummary": {"type": "STRING"},
                            "evidenceLabels": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "sourceRefs": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "sourceId": {"type": "STRING"},
                                        "label": {"type": "STRING"},
                                        "detail": {"type": "STRING"},
                                    },
                                },
                            },
                            "signalScore": {"type": "NUMBER"},
                        },
                    },
                }
            },
        }
        system_instruction = (
            "你是资深战略顾问，负责从客户资料中生成少量高价值、未来导向的思考与研判。"
            "你只能基于输入材料判断，不能套用固定模板，不能照搬示例标题，不能输出泛泛而谈的管理建议。"
            "每条洞察必须同时包含当前判断、形成原因、未来可能性和下一步动作。"
            "如果已经同时存在稳定底座和动态材料，就应该尽量形成审慎洞察；资料不完美时请写清判断边界、限制条件和下一步观察点，不要直接返回空。"
            "只有 stableBase 或 dynamicSignals 完全为空，或材料内容几乎为空时，才返回空 insights。"
            "如果 stableBase 和 dynamicSignals 均非空，至少输出 1 条最有把握的洞察。"
            "不要把碎片任务直接当主轴；任务、会议、事件线和附件只能作为证据或动态信号。"
        )
        _gloss_block = f"{_glossary_pack_si}\n\n---\n\n" if _glossary_pack_si else ""
        prompt = (
            f"{_gloss_block}"
            f"请生成 1 到 {max(1, min(12, int(limit or 8)))} 条洞察。"
            "标题必须是客户/项目专属表达，不能使用固定通用标题。"
            "insightText 用 220-450 个中文字符写成完整顾问式分析；futureJudgment 写未来可能性或判断条件；"
            "recommendedAction 写清晰下一步动作；sourceRefs 必须引用输入材料中的 sourceId。\n\n"
            "生成方法：先同时阅读 stableBase 和 dynamicSignals；每条洞察都要把长期背景、近期变化、限制条件和未来动作放在同一段判断里。"
            "不要只摘关键词，也不要因为证据还不完美就放弃判断；可以用“如果……则……”说明未来条件。"
            "本次请求已经由系统做过最低证据检查，只要 stableBase 和 dynamicSignals 非空，就不要返回空数组。\n\n"
            "涉及具体数字/姓名/日期/金额时，优先用上方字典权威值（如有），并用 [📚 term.attribute] 标记。\n\n"
            f"上下文资料包：\n{json.dumps(context_pack, ensure_ascii=False)}"
        )
        try:
            result = self._qwen_generate(
                prompt,
                system_instruction,
                schema,
                timeout_seconds=75.0,
                max_tokens=5200,
                temperature=0.35,
            )
            return result if isinstance(result, dict) else {"insights": []}
        except Exception:
            return {"insights": []}

    def enrich_retrieval_summary(
        self,
        *,
        title: str,
        overview_summary: str,
        distinct_findings: list[str],
        document_role: str,
        folder_category: str,
    ) -> str | None:
        """Rewrite a template-based retrieval_summary into a semantic, use-case oriented description."""
        health = self.get_health()
        findings_text = "\n".join(f"- {f}" for f in distinct_findings) if distinct_findings else "无"
        prompt = (
            "请为以下文档重写一段检索摘要（retrieval_summary），200字以内。\n"
            "要求：\n"
            "1. 描述这份文档能回答什么类型的问题，而不是描述它属于什么分类\n"
            "2. 用具体的场景和关键词，不要用“相关的问题”这类泛化表述\n"
            "3. 让向量嵌入能捕捉到这份文档的核心语义\n\n"
            f"标题：{title}\n"
            f"分类：{folder_category}\n"
            f"角色：{document_role}\n"
            f"概要：{overview_summary[:1200]}\n"
            f"关键发现：\n{findings_text}\n\n"
            "请直接输出检索摘要文本，不要包裹引号或其他格式。"
        )
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是知识检索优化助手。只输出检索摘要文本，不要加任何前缀或解释。",
                    None,
                    timeout_seconds=20.0,
                    max_tokens=300,
                )
                if isinstance(result, str) and len(result.strip()) > 20:
                    return result.strip()[:220]
        except Exception:
            pass
        return None

    def diagnose_profile_dimensions(
        self,
        *,
        client_name: str,
        client_type: str,
        client_stage: str,
        category_distribution: dict[str, int],
        top_titles_per_category: dict[str, list[str]],
        existing_memory_count: int,
    ) -> dict[str, Any] | None:
        """Analyze client data and recommend which profile blocks to generate."""
        health = self.get_health()
        dist_text = "\n".join(f"- {cat}: {count}份" for cat, count in category_distribution.items())
        titles_text = "\n".join(
            f"- {cat}: {', '.join(titles[:3])}"
            for cat, titles in top_titles_per_category.items()
            if titles
        )
        total_docs = sum(category_distribution.values())
        prompt = (
            "请根据以下客户资料盘点，判断应该生成哪些客户画像块。\n\n"
            "规则：\n"
            "1. 只建议有充分数据支撑的画像块，不要凭空生成\n"
            "2. 每个块必须标注依据哪些分类的资料\n"
            "3. 块数量根据资料丰富度自适应：\n"
            f"   - 资料 < 10 份：最多 1-2 块\n"
            f"   - 资料 10-50 份：最多 3-4 块\n"
            f"   - 资料 > 50 份：最多 5-7 块\n"
            "4. 可选的画像维度（根据数据决定，不是必选）：\n"
            "   客户概览、核心业务与项目、战略定位与转型、治理与组织结构、"
            "   财务与可持续性、品牌与对外传播、合作关系与生态位、关键风险与挑战\n\n"
            f"客户名称：{client_name}\n"
            f"客户类型：{client_type}\n"
            f"当前阶段：{client_stage}\n"
            f"文档总数：{total_docs}份\n"
            f"分类分布：\n{dist_text}\n"
            f"各分类代表性文档：\n{titles_text}\n"
            f"已有记忆块：{existing_memory_count}条\n"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "recommended_blocks": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "dimension": {"type": "STRING"},
                            "reason": {"type": "STRING"},
                            "source_categories": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "priority": {"type": "INTEGER"},
                        },
                    },
                },
                "skipped_dimensions": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "dimension": {"type": "STRING"},
                            "reason": {"type": "STRING"},
                        },
                    },
                },
            },
        }
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是客户知识架构师。只返回 JSON。",
                    schema,
                    timeout_seconds=30.0,
                    max_tokens=1500,
                )
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return None

    def generate_profile_block(
        self,
        *,
        client_name: str,
        dimension: str,
        aggregated_summaries: str,
        client_id: str | None = None,
    ) -> dict[str, object] | None:
        """Generate a single client profile block from aggregated surrogate summaries."""
        health = self.get_health()
        # P-E.3: 字典权威包注入
        _glossary_block = ""
        if client_id:
            try:
                from app.services.glossary_attributes_pack import build_verified_attributes_pack
                _pack = build_verified_attributes_pack(self.db, client_id) or ""
                if _pack:
                    _glossary_block = f"{_pack}\n\n---\n\n"
            except Exception:
                pass
        prompt = (
            f"{_glossary_block}"
            f"请基于以下 {client_name} 的「{dimension}」相关资料摘要，"
            "生成一条可复用的客户画像记忆块。\n\n"
            "要求：\n"
            "- overview_summary：面向咨询场景的综合叙述（200-400字），不是文档摘录\n"
            "- retrieval_summary：列出这个块能回答哪些类型的问题（200字以内）\n"
            "- document_role：这个画像块的角色定位（一句话）\n"
            "- core_questions：3-5个这个维度最关键的问题\n"
            "- distinct_findings：从资料中提炼的关键结论（3-7条）\n"
            "- entities：涉及的关键实体（组织、人物、项目等）\n"
            "- time_markers：涉及的时间节点\n"
            "- 涉及具体数字/日期/姓名时，优先用上方字典权威值（如有）\n\n"
            f"资料摘要：\n{aggregated_summaries[:4000]}\n"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview_summary": {"type": "STRING"},
                "retrieval_summary": {"type": "STRING"},
                "document_role": {"type": "STRING"},
                "core_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "query_hints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        try:
            if health.provider != "mock" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是客户知识整理专家。只返回 JSON。",
                    schema,
                    timeout_seconds=30.0,
                    max_tokens=2000,
                )
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return None

    def generate_event_line_clarification_draft(
        self,
        *,
        event_line_name: str,
        conversation_text: str,
        current_summary: str = "",
        current_stage: str = "",
        current_intent: str = "",
        current_blocker: str = "",
        current_next_step: str = "",
        current_recent_decision: str = "",
        recent_activity_lines: list[str] | None = None,
        client_id: str | None = None,
    ) -> dict[str, object]:
        cleaned_conversation = str(conversation_text or "").strip()
        fallback = self._fallback_event_line_clarification_draft(
            event_line_name=event_line_name,
            conversation_text=cleaned_conversation,
            current_summary=current_summary,
            current_stage=current_stage,
            current_intent=current_intent,
            current_blocker=current_blocker,
            current_next_step=current_next_step,
            current_recent_decision=current_recent_decision,
        )
        health = self.get_health()
        if not cleaned_conversation or not health.ready or health.provider == "mock":
            return fallback

        activity_summary = "；".join(str(item).strip() for item in (recent_activity_lines or []) if str(item).strip())[:1200]
        # P-E.5: 字典权威包注入事件线澄清
        _glossary_block_elc = ""
        if client_id:
            try:
                from app.services.glossary_attributes_pack import build_verified_attributes_pack
                _pack_elc = build_verified_attributes_pack(self.db, client_id) or ""
                if _pack_elc:
                    _glossary_block_elc = f"{_pack_elc}\n\n---\n\n"
            except Exception:
                pass
        prompt = (
            f"{_glossary_block_elc}"
            "请把下面这段和客户相关的聊天记录、会议纪要或沟通摘录，整理成事件线当前态草稿。"
            "目标不是逐句复述，而是提炼出这条线现在在推进什么、卡在哪、下一步是什么、最近哪次决定改变了走向。"
            "请返回 JSON，对象字段固定为：summary, stage, intent, currentBlocker, nextStep, recentDecision, missingInfo, confidence。\n"
            "输出约束：\n"
            "1. summary 用 60-120 字中文概括这条线当前在发生什么。\n"
            "2. stage 只写一句当前阶段，如“等待确认”“资料补齐中”“执行推进中”“复盘沉淀中”。\n"
            "3. intent 用 1-3 句说明这条线当前到底在推进什么。\n"
            "4. currentBlocker 只写最关键阻塞；如果没有明确阻塞，可写空字符串。\n"
            "5. nextStep 只写最关键的一步动作；如果聊天里没有明确下一步，可写空字符串。\n"
            "6. recentDecision 只写最近真正改变走向的决定；如果没有明确决定，可写空字符串。\n"
            "7. missingInfo 返回还缺哪些信息，使用中文短句数组。\n"
            "8. confidence 只能是 low、medium、high。\n"
            "9. 不要编造没有出现的事实；不确定就放进 missingInfo。\n\n"
            f"事件线名称：{event_line_name}\n"
            f"当前已有摘要：{current_summary or '无'}\n"
            f"当前已有阶段：{current_stage or '无'}\n"
            f"当前已有事项：{current_intent or '无'}\n"
            f"当前已有阻塞：{current_blocker or '无'}\n"
            f"当前已有下一步：{current_next_step or '无'}\n"
            f"当前已有关键决策：{current_recent_decision or '无'}\n"
            f"最近活动摘要：{activity_summary or '无'}\n"
            f"聊天记录：\n{cleaned_conversation[:5000]}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "summary": {"type": "STRING"},
                "stage": {"type": "STRING"},
                "intent": {"type": "STRING"},
                "currentBlocker": {"type": "STRING"},
                "nextStep": {"type": "STRING"},
                "recentDecision": {"type": "STRING"},
                "missingInfo": {"type": "ARRAY", "items": {"type": "STRING"}},
                "confidence": {"type": "STRING", "enum": ["low", "medium", "high"]},
            },
        }
        try:
            result = self._qwen_generate(
                prompt,
                "你是事件线当前态提炼助手。只返回 JSON。",
                schema,
                timeout_seconds=28.0,
                max_tokens=1600,
            )
            if isinstance(result, dict):
                normalized = self._normalize_event_line_clarification_draft_payload(result, fallback)
                if any(
                    normalized.get(key)
                    for key in ("summary", "stage", "intent", "currentBlocker", "nextStep", "recentDecision")
                ):
                    return normalized
        except Exception:
            pass
        return fallback

    def parse_department_plan_text(
        self,
        *,
        text: str,
        organization_name: str = "",
        scope_kind: str = "department",  # "org" or "department"
        scope_name: str = "",
        period_key: str = "",
        cycle_type: str = "month",
    ) -> dict[str, object]:
        """Parse free-form plan text into structured plan items.

        Returns: { items: [{title, statement, expectedOutput}], summary: str, confidence: str }
        Falls back to simple line-splitting when AI is not ready.
        """
        cleaned = str(text or "").strip()
        if not cleaned:
            return {"items": [], "summary": "", "confidence": "low"}
        # Local fallback: split lines + strip list markers (same as current frontend behavior).
        def _fallback() -> dict[str, object]:
            import re as _re
            raw_lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
            list_marker = _re.compile(r"^\s*([\-\*•]|\d+[\.、]|[一二三四五六七八九十]+[、.])\s*", _re.UNICODE)
            items = []
            for ln in raw_lines:
                title = list_marker.sub("", ln).strip()
                if title:
                    items.append({"title": title[:120], "statement": "", "expectedOutput": ""})
            return {"items": items, "summary": "", "confidence": "low"}

        health = self.get_health()
        if not health.ready or health.provider == "mock":
            return _fallback()

        cycle_label_map = {
            "month": "月度",
            "quarter": "季度",
            "year": "年度",
            "week": "周",
            "custom": "自定义周期",
        }
        cycle_label = cycle_label_map.get(cycle_type, cycle_type or "")
        subject_line = (
            f"组织级（{organization_name or '组织'}）"
            if scope_kind == "org"
            else f"部门：{scope_name or '部门'}"
        )

        prompt = (
            "你是组织计划结构化助手。下面给你一段用户粘贴的计划原文，"
            "请把它整理成一组可执行的计划项（plan items），用于公司/部门的月度、季度或年度计划。\n\n"
            "**重要规则**：\n"
            "1. 不是逐行拆分——同一条计划即使写了多行说明，也要合并为一条。\n"
            "2. 忽略文档标题、章节小标题、序号、表头、空白段落。\n"
            "3. 把'背景说明 + 目标动作 + 期望产出'拆到不同字段：\n"
            "   - title: 一句话动作描述（10-30 字，不要带 \"1.\" \"•\" 等列表符号）\n"
            "   - statement: 这条计划的背景或说明（30-150 字，可选）\n"
            "   - expectedOutput: 这条计划做完后应该交付什么（如 \"签 20 单\" \"上线 1 个版本\"），没有就空字符串\n"
            "4. 不要编造原文没有的内容；原文只有 5 条就返回 5 条，不要凑数。\n"
            "5. 不要把同一件事拆成多条（如 '开发 + 测试 + 上线' 是同一条上线计划）。\n"
            "6. 排除明显不是'计划项'的内容：感言、总结、致谢、附录。\n"
            "7. 如果原文是季度/年度战略，标题要写得更概括（'拓展华南市场'），不要写得太细。\n"
            "8. 整体限制 1-20 条；超过 20 条说明拆得太细，请合并。\n\n"
            "请返回 JSON：{\n"
            "  \"items\": [{\"title\": \"...\", \"statement\": \"...\", \"expectedOutput\": \"...\"}],\n"
            "  \"summary\": \"30 字内描述这份计划主旨（可选）\",\n"
            "  \"confidence\": \"low|medium|high\"\n"
            "}\n\n"
            f"计划主体：{subject_line}\n"
            f"周期类型：{cycle_label}\n"
            f"周期值：{period_key or '未指定'}\n\n"
            f"原文：\n{cleaned[:6000]}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "items": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "statement": {"type": "STRING"},
                            "expectedOutput": {"type": "STRING"},
                        },
                    },
                },
                "summary": {"type": "STRING"},
                "confidence": {"type": "STRING", "enum": ["low", "medium", "high"]},
            },
        }
        try:
            result = self._qwen_generate(
                prompt,
                "你是组织计划结构化助手。严格只返回 JSON。",
                schema,
                timeout_seconds=40.0,
                max_tokens=3200,
            )
            if isinstance(result, dict):
                raw_items = result.get("items") if isinstance(result.get("items"), list) else []
                cleaned_items: list[dict[str, str]] = []
                for entry in raw_items[:20]:
                    if not isinstance(entry, dict):
                        continue
                    title = str(entry.get("title") or "").strip()[:120]
                    if not title:
                        continue
                    cleaned_items.append({
                        "title": title,
                        "statement": str(entry.get("statement") or "").strip()[:400],
                        "expectedOutput": str(entry.get("expectedOutput") or "").strip()[:200],
                    })
                if cleaned_items:
                    confidence_raw = str(result.get("confidence") or "").strip().lower()
                    confidence = confidence_raw if confidence_raw in {"low", "medium", "high"} else "medium"
                    return {
                        "items": cleaned_items,
                        "summary": str(result.get("summary") or "").strip()[:120],
                        "confidence": confidence,
                    }
        except Exception:
            pass
        return _fallback()

    def _normalize_event_line_clarification_draft_payload(
        self,
        payload: dict[str, object],
        fallback: dict[str, object],
    ) -> dict[str, object]:
        confidence_raw = str(payload.get("confidence") or "").strip().lower()
        confidence = confidence_raw if confidence_raw in {"low", "medium", "high"} else str(fallback.get("confidence") or "medium")
        return {
            "summary": str(payload.get("summary") or fallback.get("summary") or "").strip()[:180],
            "stage": str(payload.get("stage") or fallback.get("stage") or "").strip()[:40],
            "intent": str(payload.get("intent") or fallback.get("intent") or "").strip()[:240],
            "currentBlocker": str(payload.get("currentBlocker") or fallback.get("currentBlocker") or "").strip()[:240],
            "nextStep": str(payload.get("nextStep") or fallback.get("nextStep") or "").strip()[:240],
            "recentDecision": str(payload.get("recentDecision") or fallback.get("recentDecision") or "").strip()[:240],
            "missingInfo": self._normalize_string_list(payload.get("missingInfo"), max_items=5, max_length=80)
            or list(fallback.get("missingInfo") or []),
            "confidence": confidence,
        }

    def _fallback_event_line_clarification_draft(
        self,
        *,
        event_line_name: str,
        conversation_text: str,
        current_summary: str,
        current_stage: str,
        current_intent: str,
        current_blocker: str,
        current_next_step: str,
        current_recent_decision: str,
    ) -> dict[str, object]:
        lines = [
            re.sub(r"\s+", " ", segment).strip(" -•\t")
            for segment in re.split(r"[\n\r]+", conversation_text)
            if segment.strip()
        ]
        sentences: list[str] = []
        for line in lines:
            for segment in re.split(r"[。！？!?；;]+", line):
                text = re.sub(r"\s+", " ", segment).strip(" -•\t")
                if text:
                    sentences.append(text)

        def pick_sentence(keywords: list[str]) -> str:
            for sentence in sentences:
                if any(keyword in sentence for keyword in keywords):
                    return sentence[:220]
            return ""

        def pick_sentence_prefix(prefixes: list[str]) -> str:
            for sentence in sentences:
                normalized = sentence.lstrip("：:，,。 ")
                if any(normalized.startswith(prefix) for prefix in prefixes):
                    return sentence[:220]
            return ""

        stage = current_stage.strip()
        if not stage:
            if re.search(r"(等待|确认|审批|口径|回复|定稿)", conversation_text):
                stage = "等待确认"
            elif re.search(r"(补齐|整理|收集|导入|扫描|资料)", conversation_text):
                stage = "资料补齐中"
            elif re.search(r"(执行|推进|落地|跟进|排期)", conversation_text):
                stage = "执行推进中"
            elif re.search(r"(复盘|总结|沉淀)", conversation_text):
                stage = "复盘沉淀中"

        intent = pick_sentence(["推进", "沟通", "确认", "整理", "补齐", "梳理", "对齐", "发送"])
        if not intent:
            intent = current_intent.strip() or "；".join(lines[:2])[:220]

        blocker = pick_sentence(["卡", "阻塞", "等待", "没", "未", "缺", "无法", "来不及", "拖", "确认"])
        if not blocker:
            blocker = current_blocker.strip()

        next_step = (
            pick_sentence_prefix(["下一步", "接下来", "后续"])
            or pick_sentence(["安排", "同步", "跟进", "推进"])
            or pick_sentence(["需要", "先", "再"])
        )
        if not next_step:
            next_step = current_next_step.strip()

        recent_decision = (
            pick_sentence(["决定", "确定", "改成", "暂定", "拍板"])
            or pick_sentence(["统一"])
            or pick_sentence(["先"])
        )
        if not recent_decision:
            recent_decision = current_recent_decision.strip()

        summary_parts = [part for part in [intent, blocker and f"当前卡在：{blocker}", next_step and f"下一步：{next_step}"] if part]
        summary = current_summary.strip() or "；".join(summary_parts)[:160]
        if not summary:
            summary = f"{event_line_name} 当前聊天记录已导入，但还需要继续补足当前态信息。"

        missing_info: list[str] = []
        if not stage:
            missing_info.append("当前阶段还不清楚")
        if not blocker:
            missing_info.append("当前阻塞还不清楚")
        if not next_step:
            missing_info.append("下一步动作还不清楚")
        if not recent_decision:
            missing_info.append("最近关键决策还不清楚")

        filled_slots = sum(1 for item in [summary, stage, intent, blocker, next_step, recent_decision] if item)
        confidence = "high" if filled_slots >= 5 else "medium" if filled_slots >= 3 else "low"
        return {
            "summary": summary[:180],
            "stage": stage[:40],
            "intent": intent[:240],
            "currentBlocker": blocker[:240],
            "nextStep": next_step[:240],
            "recentDecision": recent_decision[:240],
            "missingInfo": missing_info[:5],
            "confidence": confidence,
        }

    def _store_for(self, provider: str) -> Any | None:
        return self.secret_stores.get(provider)

    def _mock_generate(self, prompt: str, context_summary: str) -> AiStructuredResponse:
        topic = self._short_topic(prompt)
        signals = context_summary or "当前上下文中尚无完整材料，以下为保守推演。"
        return AiStructuredResponse(
            content=f"已围绕“{topic}”整理出一版可执行的内部判断。",
            judgment=f"{topic}当前最需要的是把零散线索整合成可落地动作，而不是继续堆信息。",
            analysis="\n".join(
                [
                    f"1. 已知上下文：{signals}",
                    f"2. 问题本质：{topic}涉及客户推进、证据沉淀与任务闭环的联动。",
                    "3. 风险提醒：如果没有明确负责人和时间点，后续行动会再次散掉。",
                ]
            ),
            actions="先确认负责人，再补关键材料，最后将结论写回任务与手册。",
            timeline="建议今天完成判断，48 小时内完成任务拆解，一周内复盘一次。",
        )

    def _short_topic(self, prompt: str) -> str:
        compact = re.sub(r"\s+", "", prompt)
        return compact[:16] or "当前议题"

    def _qwen_generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        timeout_seconds: float = 60.0,
        max_tokens: int = 3500,
    ) -> AiStructuredResponse:
        payload = self._qwen_generate(
            prompt=f"问题：{prompt}\n\n上下文：{context_summary}",
            system_instruction=system_instruction,
            response_schema=self._structured_schema(),
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
        if not isinstance(payload, dict):
            raise RuntimeError(f"{self.current_model_label()}返回了非结构化数据。")
        return self._structured_from_payload(payload)

    def _structured_schema(self) -> dict[str, object]:
        return {
            "type": "OBJECT",
            "properties": {
                "content": {"type": "STRING"},
                "judgment": {"type": "STRING"},
                "analysis": {"type": "STRING"},
                "actions": {"type": "STRING"},
                "timeline": {"type": "STRING"},
            },
        }

    def _structured_from_payload(self, payload: dict[str, object]) -> AiStructuredResponse:
        return AiStructuredResponse(
            content=str(payload.get("content", "")),
            judgment=str(payload.get("judgment", "")),
            analysis=str(payload.get("analysis", "")),
            actions=str(payload.get("actions", "")),
            timeline=str(payload.get("timeline", "")),
        )

    def _build_http_timeout(self, read_timeout_seconds: float) -> httpx.Timeout:
        read_timeout = max(4.0, float(read_timeout_seconds))
        connect_timeout = min(10.0, max(5.0, read_timeout / 3))
        write_timeout = min(20.0, max(8.0, read_timeout))
        pool_timeout = min(10.0, max(5.0, read_timeout / 2))
        # 统一 provider hard limit：read timeout + 固定 grace，避免 socket 长时间悬挂。
        total_timeout = read_timeout + HTTP_TIMEOUT_GRACE_SECONDS
        return httpx.Timeout(timeout=total_timeout, connect=connect_timeout, read=read_timeout, write=write_timeout, pool=pool_timeout)

    def _resolve_llm_config(
        self,
        *,
        task_kind: str = "default",
        provider_override: str | None = None,
        model_override: str | None = None,
    ) -> tuple[str, str, str]:
        """Returns (base_url, api_key, model) for the configured OpenAI-compatible endpoint."""
        candidates = self._resolve_llm_candidates(
            task_kind=task_kind,
            provider_override=provider_override,
            model_override=model_override,
        )
        if not candidates:
            raise RuntimeError("仅本地模式已启用，但没有可用的本地模型 profile。")
        profile = next((item for item in candidates if self._profile_is_usable(item)), candidates[0])
        display_label = llm_display_label(profile.provider, profile.model, profile.provider_label)
        if profile.provider == MOCK_PROVIDER:
            raise RuntimeError("本地 Mock 模式不调用外部模型接口。")
        if not profile.base_url:
            raise RuntimeError(f"{display_label} 接口地址 Base URL 未配置。")
        if not profile.model:
            raise RuntimeError(f"{display_label} 模型名未配置。")
        if not profile.api_key and not profile.is_local:
            raise RuntimeError(f"{display_label} API Key 未配置。")
        return profile.base_url, profile.api_key, profile.model

    def _openclaw_cli_path(self) -> str:
        value = (self.db.get_setting("ai_openclaw_cli_path", "") or "").strip()
        return value or OPENCLAW_DEFAULT_CLI

    def _openclaw_agent_id(self) -> str:
        value = (self.db.get_setting("ai_openclaw_agent_id", "") or "").strip()
        return value or OPENCLAW_DEFAULT_AGENT

    def _openclaw_health(self) -> AiHealth:
        cli_path = self._openclaw_cli_path()
        resolved = shutil.which(cli_path) if not cli_path.startswith("/") else cli_path
        model = self.current_model() or OPENCLAW_DEFAULT_MODEL
        label = PROVIDER_LABELS["openclaw"]
        if not resolved:
            return AiHealth(
                provider=OPENCLAW_PROVIDER,
                provider_label=label,
                base_url="",
                model=model,
                ready=False,
                detail=f"{label} 未检测到本机 OpenClaw CLI（命令：{cli_path}）。",
                credential_source="local-binary",
                fingerprint=None,
                profile_key="openclaw",
                mode=self.current_ai_model_mode() if hasattr(self, "current_ai_model_mode") else "auto",
            )
        return AiHealth(
            provider=OPENCLAW_PROVIDER,
            provider_label=label,
            base_url="",
            model=model,
            ready=True,
            detail=f"{label} 已检测到本机 OpenClaw CLI。",
            credential_source="local-binary",
            fingerprint=None,
            profile_key="openclaw",
            mode=self.current_ai_model_mode() if hasattr(self, "current_ai_model_mode") else "auto",
        )

    def _openclaw_generate(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: dict | None,
        timeout_seconds: float = 60.0,
    ) -> object:
        user_prompt = prompt
        if response_schema:
            user_prompt = (
                "请严格返回一个 JSON 对象，不要使用 Markdown，不要添加解释。"
                "请确保返回结构满足下面这个 JSON Schema。\n"
                f"{json.dumps(response_schema, ensure_ascii=False)}\n\n"
                f"{prompt}"
            )
        if system_instruction:
            full_message = f"[System]\n{system_instruction}\n\n[User]\n{user_prompt}"
        else:
            full_message = user_prompt

        cli_path = self._openclaw_cli_path()
        agent_id = self._openclaw_agent_id()
        cli_timeout = max(30, int(timeout_seconds))
        wall_timeout = cli_timeout + OPENCLAW_STARTUP_OVERHEAD_SECONDS

        # 5/27 修: openclaw 2026.5.22 升级后, 走 gateway 会 50s 超时再 fallback 到 embedded,
        # 总耗时 > backend 75s 硬超时. 直接用 --local (embedded) 跳过 gateway 等待.
        # 同时把 user 在 UI 切的 model 显式传给 openclaw (之前依赖 agent default, 切换没生效).
        configured_model = (self.current_model() or "").strip() or OPENCLAW_DEFAULT_MODEL
        cmd = [
            cli_path,
            "agent",
            "--local",
            "--agent", agent_id,
            "--model", configured_model,
            "--message", full_message,
            "--json",
            "--timeout", str(cli_timeout),
        ]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=wall_timeout,
                check=False,
            )
        except FileNotFoundError as error:
            raise AiInvocationError("openclaw", f"未找到 OpenClaw CLI（命令：{cli_path}）：{error}")
        except subprocess.TimeoutExpired:
            raise AiInvocationError("openclaw", f"OpenClaw 调用硬超时（{wall_timeout:.0f}秒）")

        if proc.returncode != 0:
            err_tail = (proc.stdout or "")[-500:]
            raise AiInvocationError("openclaw", f"OpenClaw CLI 退出码 {proc.returncode}：{err_tail}")

        raw = proc.stdout or ""
        brace = raw.find("{")
        if brace < 0:
            raise AiInvocationError("openclaw", f"OpenClaw 未返回 JSON：{raw[:500]}")

        try:
            payload = json.loads(raw[brace:])
        except json.JSONDecodeError as error:
            raise AiInvocationError("openclaw", f"OpenClaw JSON 解析失败：{error}")

        meta = payload.get("meta") if isinstance(payload, dict) else None
        if isinstance(meta, dict):
            stop_reason = str(meta.get("stopReason") or "").lower()
            if stop_reason and stop_reason not in {"stop", "end_turn", "complete", "finished"}:
                raise AiInvocationError("openclaw", f"OpenClaw 异常停止：stopReason={stop_reason}")

        text = ""
        payloads = payload.get("payloads") if isinstance(payload, dict) else None
        if isinstance(payloads, list):
            for item in payloads:
                if isinstance(item, dict):
                    candidate = item.get("text")
                    if isinstance(candidate, str) and candidate.strip():
                        text = candidate.strip()
                        break

        if not text:
            raise AiInvocationError("openclaw", "OpenClaw 返回内容为空")

        if response_schema:
            return self._load_relaxed_json(text)
        return text

    def _openclaw_generate_with_retry(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: dict | None,
        timeout_seconds: float = 60.0,
    ) -> object:
        # 总尝试 4 次(1 次初次 + 3 次重试),退避序列 1s/2s/4s,加起来最多额外等 7s,
        # 加上每次内部 10s 锁超时 = 最多 47s。比"立刻 502"温柔得多。
        max_attempts = 4
        backoff_schedule = (1.0, 2.0, 4.0)
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self._openclaw_generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_schema=response_schema,
                    timeout_seconds=timeout_seconds,
                )
            except AiInvocationError as exc:
                last_exc = exc
                if not _is_transient_llm_error(str(exc)) or attempt >= max_attempts:
                    raise
                backoff = backoff_schedule[min(attempt - 1, len(backoff_schedule) - 1)]
                logger.warning(
                    "[openclaw] transient error attempt=%d/%d backoff=%.1fs detail=%s",
                    attempt,
                    max_attempts,
                    backoff,
                    str(exc)[:200],
                )
                time.sleep(backoff)
        # 理论上 unreachable — 上面的循环要么 return,要么 raise。但保险起见兜一手。
        if last_exc:
            raise last_exc
        raise RuntimeError("openclaw retry exhausted with no captured exception")

    def _qwen_generate(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: dict | None,
        timeout_seconds: float = 60.0,
        max_tokens: int = 3500,
        *,
        temperature: float = 0.45,
        top_p: float = 0.9,
        enable_thinking: bool = False,
        provider_override: str | None = None,
        model_override: str | None = None,
        task_kind: str = "default",
        deep_read_local: bool = False,
    ) -> object:
        active_provider = provider_override or self.current_provider()
        # deep_read_local：深度解析选了「本地」档——绕过 openclaw 短路，强制走本地 qwen3-vl:32b。
        if active_provider == OPENCLAW_PROVIDER and not deep_read_local:
            # Tier1 优化:openclaw 走 CLI 子进程 + 共享 session 文件,锁竞争是已知
            # 结构性问题(详见 docs/CODEMAPS 或排查日志)。在外层包一层短退避重试,
            # 把"必失败"压缩成"偶尔多等几秒",对普通用户的瞬时错误也一并兜底。
            return self._openclaw_generate_with_retry(
                prompt=prompt,
                system_instruction=system_instruction,
                response_schema=response_schema,
                timeout_seconds=timeout_seconds,
            )
        effective_task_kind = task_kind
        if effective_task_kind == "default" and response_schema is not None and int(max_tokens or 0) <= 2200:
            effective_task_kind = "fast_structured"
        user_prompt = prompt
        if response_schema:
            user_prompt = (
                "请严格返回一个 JSON 对象，不要使用 Markdown，不要添加解释。"
                "请确保返回结构满足下面这个 JSON Schema。\n"
                f"{json.dumps(response_schema, ensure_ascii=False)}\n\n"
                f"{prompt}"
            )
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

        if deep_read_local:
            _local = self._resolve_deep_read_local_candidate()
            # 本地 profile 配好就只用它；没配(无 baseUrl/model)则回退正常解析，不让解析失败。
            candidates = [_local] if _local else self._resolve_llm_candidates(task_kind=effective_task_kind)
        else:
            candidates = self._resolve_llm_candidates(
                task_kind=effective_task_kind,
                provider_override=provider_override,
                model_override=model_override,
            )
        errors: list[str] = []
        hard_limit = timeout_seconds + HTTP_TIMEOUT_GRACE_SECONDS
        for profile in candidates:
            display_label = llm_display_label(profile.provider, profile.model, profile.provider_label)
            if not self._profile_is_usable(profile):
                errors.append(f"{display_label} 配置不可用：{self._profile_to_health(profile).detail}")
                continue
            payload = {
                "model": profile.model,
                "messages": [
                    {"role": "system", "content": system_instruction or "你是系统助手。"},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "stream": False,
            }
            if enable_thinking:
                payload["enable_thinking"] = True

            def _do_request() -> dict:
                with httpx.Client(timeout=self._build_http_timeout(timeout_seconds)) as _client:
                    _resp = _client.post(
                        f"{profile.base_url}/chat/completions",
                        headers=self._build_openai_compatible_headers(profile.api_key),
                        json=payload,
                    )
                    _resp.raise_for_status()
                    return _resp.json()

            # Tier1 优化:同一候选最多尝试 3 次(初次 + 2 次重试),专治瞬时
            # 429 / 5xx / 网络抖动。硬超时立即跳出换下一候选,不浪费时间重试。
            candidate_attempts = 3
            candidate_backoff = (1.0, 2.0)
            for attempt in range(1, candidate_attempts + 1):
                pool = ThreadPoolExecutor(max_workers=1)
                future = pool.submit(_do_request)
                try:
                    result = future.result(timeout=hard_limit)
                    text = (
                        result.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    self._record_resolved_profile(profile)
                    if response_schema:
                        return self._load_relaxed_json(text)
                    return text
                except FutureTimeout:
                    future.cancel()
                    errors.append(f"{display_label} 硬超时（{hard_limit:.0f}秒）")
                    break  # 硬超时不重试,直接换候选
                except Exception as error:
                    detail = self._format_provider_error(error) if hasattr(self, "_format_provider_error") else str(error)
                    if _is_transient_llm_error(detail) and attempt < candidate_attempts:
                        backoff = candidate_backoff[min(attempt - 1, len(candidate_backoff) - 1)]
                        logger.warning(
                            "[%s] transient error attempt=%d/%d backoff=%.1fs detail=%s",
                            display_label,
                            attempt,
                            candidate_attempts,
                            backoff,
                            detail[:200],
                        )
                        time.sleep(backoff)
                        continue
                    errors.append(f"{display_label} 调用失败：{detail}")
                    break
                finally:
                    # 不要在超时后等待工作线程自然结束，否则外层调用会被 shutdown(wait=True)
                    # 卡死，自动填表 run 会永久停在 running。
                    pool.shutdown(wait=False, cancel_futures=True)
        raise RuntimeError("；".join(errors) or "没有可用的大模型配置。")

    def _qwen_generate_streaming(
        self,
        prompt: str,
        system_instruction: str,
        *,
        on_token: Callable[[str], None] | None = None,
        on_reasoning_heartbeat: Callable[[], None] | None = None,
        timeout_seconds: float = 180.0,
        max_tokens: int = 4500,
        temperature: float = 0.45,
        top_p: float = 0.9,
        enable_thinking: bool = False,
        provider_override: str | None = None,
        model_override: str | None = None,
        task_kind: str = "default",
    ) -> str:
        """流式版本的 ``_qwen_generate``：用 OpenAI 兼容 SSE 接口逐 token 拉回内容。

        每收到一个 delta 调用 ``on_token(delta)``；返回累计完整文本。
        不支持 response_schema —— 仅用于自由文本生成（multipass Pass 2 写每段）。

        与同步版本的区别：
        - ``stream=True`` 让接口逐 token 推送 SSE
        - ``on_token`` 让调用方在 token 流入时实时拿到（可用于 partial 推送 db / 前端打字机）
        - 失败不做 candidate fallback（中途断流难以无缝切换）；让调用方在外层 retry。
        """
        active_provider = provider_override or self.current_provider()
        if active_provider == OPENCLAW_PROVIDER:
            text = self._openclaw_generate(
                prompt=prompt,
                system_instruction=system_instruction,
                response_schema=None,
                timeout_seconds=timeout_seconds,
            )
            result_text = text if isinstance(text, str) else str(text or "")
            if on_reasoning_heartbeat:
                try:
                    on_reasoning_heartbeat()
                except Exception:
                    pass
            if on_token and result_text:
                try:
                    on_token(result_text)
                except Exception:
                    pass
            return result_text
        candidates = self._resolve_llm_candidates(
            task_kind=task_kind,
            provider_override=provider_override,
            model_override=model_override,
        )
        errors: list[str] = []
        for profile in candidates:
            display_label = llm_display_label(profile.provider, profile.model, profile.provider_label)
            if not self._profile_is_usable(profile):
                errors.append(f"{display_label} 配置不可用：{self._profile_to_health(profile).detail}")
                continue
            payload: dict[str, Any] = {
                "model": profile.model,
                "messages": [
                    {"role": "system", "content": system_instruction or "你是系统助手。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if enable_thinking:
                payload["enable_thinking"] = True

            accumulated: list[str] = []
            try:
                with httpx.stream(
                    "POST",
                    f"{profile.base_url}/chat/completions",
                    headers=self._build_openai_compatible_headers(profile.api_key),
                    json=payload,
                    timeout=self._build_http_timeout(timeout_seconds),
                ) as response:
                    response.raise_for_status()
                    for raw_line in response.iter_lines():
                        if not raw_line:
                            continue
                        # httpx 的 iter_lines 已自动去掉行尾换行
                        line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8", errors="ignore")
                        if not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if not chunk:
                            continue
                        if chunk == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        token = delta.get("content") or ""
                        # 深度思考模型（豆包 Seed 2.0 Pro / DeepSeek-R1 / Qwen3-thinking 等）
                        # 在思考阶段返回 reasoning_content，不返回 content。
                        # 如果不识别这种 chunk，思考期间 on_token 永远不会被调，上层 watchdog
                        # 会误判 LLM "卡住"——即使 SSE 实际在持续流动。
                        # 这里把 reasoning chunk 当作心跳：不累积到答案，但调一次 heartbeat
                        # 回调让上层刷新 analysis_run.updated_at。
                        if not token:
                            reasoning_token = delta.get("reasoning_content") or ""
                            if reasoning_token and on_reasoning_heartbeat is not None:
                                try:
                                    on_reasoning_heartbeat()
                                except Exception:
                                    pass
                            continue
                        accumulated.append(token)
                        if on_token is not None:
                            try:
                                on_token(token)
                            except Exception:
                                # 回调失败不应阻断 LLM 流式接收
                                pass
                self._record_resolved_profile(profile)
                return "".join(accumulated)
            except Exception as error:
                detail = self._format_provider_error(error) if hasattr(self, "_format_provider_error") else str(error)
                errors.append(f"{display_label} 流式调用失败：{detail}")
                # 流式失败不 fallback 到下一个 candidate（已经发了一半 token 切换会乱）
                break
        raise RuntimeError("；".join(errors) or "没有可用的大模型配置。")

    def _qwen_generate_structured_with_retry(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
    ) -> AiStructuredResponse:
        first_error: Exception | None = None
        second_error: Exception | None = None
        try:
            return self._qwen_generate_structured(
                prompt,
                system_instruction,
                context_summary,
                timeout_seconds=18.0,
                max_tokens=1400,
            )
        except Exception as error:
            first_error = error
        compact_context = self._compact_context_summary(context_summary)
        if compact_context:
            try:
                return self._qwen_generate_structured(
                    prompt,
                    system_instruction,
                    compact_context,
                    timeout_seconds=10.0,
                    max_tokens=900,
                )
            except Exception as error:
                second_error = error
        try:
            return self._qwen_generate_textual_fallback(prompt, system_instruction, compact_context or context_summary)
        except Exception as third_error:
            detail_parts = [self._format_provider_error(first_error)]
            if second_error is not None:
                detail_parts.append(f"缩上下文重试后仍失败：{self._format_provider_error(second_error)}")
            detail_parts.append(f"文本结构化降级仍失败：{self._format_provider_error(third_error)}")
            raise AiInvocationError(self.current_provider(), "；".join(part for part in detail_parts if part)) from third_error
        raise AiInvocationError(self.current_provider(), self._format_provider_error(first_error)) from first_error

    def _qwen_generate_general_fallback(self, prompt: str, note: str, *, subject_name: str = "") -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"补充说明：{note or '当前本地背景回答阶段失败，请直接给出通用知识下的初步回答。'}\n\n"
                f"当前讨论对象：{subject_name or '当前客户'}\n\n"
                "请直接输出一篇完整、自然、专业的中文回答。"
            ),
            system_instruction=(
                "你是益语智库的资深战略顾问。请基于通用知识给出完整、专业的初步回答。\n"
                "你面对的是一个希望迅速、全面了解这家公司的人，而不是系统管理员。\n"
                "除非问题明确问益语智库、你们、顾问方或服务方式，否则默认回答对象是当前客户。\n"
                "不要把益语智库、顾问机构、外部服务方的人名或业务介绍当成当前客户本身。\n"
                "如果确实需要，只能用一句极轻的过渡说明本地背景没有直接覆盖这个问题。\n"
                "请减少寒暄和重复句，直接进入结论与分析。\n"
                "第一段必须明确提醒：以下不是基于当前客户原始资料的正式分析，而是通用背景下的初步判断。\n\n"
                "【排版规则——必须严格遵守】\n"
                "1. 用「一、二、三、四」作为一级小标题分层\n"
                "2. 并列要点用「- 」列表\n"
                "3. 关键结论用 **双星号加粗**\n"
                "4. 每段不超过 4 句话，禁止全篇连续长段落\n"
                "5. 多用判断句：「不是X，而是Y」「核心在于」\n"
            ),
            response_schema=None,
            timeout_seconds=12.0,
            max_tokens=1200,
            temperature=0.35,
            top_p=0.92,
        )
        return self._structured_from_plain_answer(str(text))

    def _qwen_generate_compact_grounded_fallback(self, prompt: str, note: str) -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"内部观察摘要：\n{note or '当前已有部分内部观察，请基于这些观察先形成紧凑但完整的一版说明。'}\n\n"
                "请直接输出回答。由你自己决定结构、长度和结尾方式。"
            ),
            system_instruction=(
                "请只基于给定观察摘要回答。"
                "不要编造观察摘要里没有出现过的确定性事实。"
                "除此之外，不要预设固定格式、固定结构、固定段数或固定栏目。"
            ),
            response_schema=None,
            timeout_seconds=10.0,
            max_tokens=1200,
            temperature=0.42,
            top_p=0.96,
        )
        return self._structured_from_plain_answer(str(text))

    def _qwen_generate_brief_grounded_rescue(self, prompt: str, note: str) -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"顾问观察要点：\n{note or '当前已有部分观察，请基于这些要点给出一版简洁保守的回答。'}\n\n"
                "请直接输出回答。由你自己决定结构、长度和结尾方式。"
            ),
            system_instruction=(
                "请只基于给定观察要点回答。"
                "不要编造观察要点里没有出现过的确定性事实。"
                "除此之外，不要预设固定格式、固定结构、固定段数或固定栏目。"
            ),
            response_schema=None,
            timeout_seconds=8.0,
            max_tokens=900,
            temperature=0.4,
            top_p=0.95,
        )
        return self._structured_from_plain_answer(str(text))

    def _extract_segment_field(self, text: str, labels: tuple[str, ...]) -> str:
        for label in labels:
            match = re.search(
                rf"(?:^|\n){re.escape(label)}[:：]\s*([\s\S]+?)(?=\n(?:{'|'.join(re.escape(item) for item in labels)}|标题|题目|总判断|判断)[:：]|\Z)",
                str(text),
            )
            if match:
                return match.group(1).strip()
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        for line in lines:
            for label in labels:
                prefix = f"{label}:"
                alt_prefix = f"{label}："
                if line.startswith(prefix):
                    return line[len(prefix) :].strip()
                if line.startswith(alt_prefix):
                    return line[len(alt_prefix) :].strip()
        return ""

    def _qwen_generate_textual_fallback(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        timeout_seconds: float = 18.0,
        max_tokens: int = 2400,
        enable_thinking: bool = False,
    ) -> AiStructuredResponse:
        fallback_instruction = (
            f"{system_instruction}\n"
            "请继续直接回答用户，不要退化成摘要、说明书或系统提示。"
            "不要使用 JSON 或 Markdown 代码块。"
            "如果完整材料过长，请优先保留最关键的判断、推理链和支撑证据，不要把回答压扁成几段概述。"
            "除非用户明确要求简短，否则请保持足够展开。"
        )
        text = self._qwen_generate(
            prompt=f"用户问题：{prompt}\n\n参考材料：\n{context_summary}",
            system_instruction=fallback_instruction,
            response_schema=None,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=0.4,
            top_p=0.95,
            enable_thinking=enable_thinking,
        )
        return self._structured_from_plain_answer(str(text))

    def _compact_context_summary(self, context_summary: str, max_chars: int = 1800) -> str:
        text = (context_summary or "").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return text[:max_chars]
        pinned: list[str] = []
        markers = ("客户背景=", "背景底稿（仅用于理解客户）", "原始证据包（可用于正式判断）", "[证据", "顾问角色口径=", "重点维度=")
        for index, line in enumerate(lines):
            if not any(marker in line for marker in markers):
                continue
            block_end = min(len(lines), index + (5 if "[证据" in line else 2))
            for block_line in lines[index:block_end]:
                compact_line = block_line[:960]
                if compact_line not in pinned:
                    pinned.append(compact_line)
        head = [line[:960] for line in lines[:14]]
        tail = [line[:960] for line in lines[-12:]]
        compact_lines = []
        for line in head + pinned[:36]:
            if line not in compact_lines:
                compact_lines.append(line)
        for line in tail:
            if line not in compact_lines:
                compact_lines.append(line)
        compact = "\n".join(compact_lines).strip()
        if not compact:
            compact = text
        compact = compact[:max_chars]
        if compact == text[:max_chars]:
            focus = tail[0] if tail else ""
            fallback_excerpt = "\n".join(compact_lines[:8])[:max_chars]
            compact = "\n".join(part for part in [fallback_excerpt, focus] if part).strip() or text[:max_chars]
        return compact[:max_chars]

    def _structured_from_plain_answer(self, text: str) -> AiStructuredResponse:
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        paragraphs = [item.strip() for item in re.split(r"\n{2,}", cleaned) if item.strip()]
        if not paragraphs:
            paragraphs = [cleaned]
        def is_heading_like(value: str) -> bool:
            candidate = value.strip()
            if not candidate:
                return False
            if re.match(r"^#{1,6}\s+", candidate):
                return True
            if re.match(r"^\d+\.\s+[^\n]{2,42}$", candidate):
                return True
            if re.match(r"^[一二三四五六七八九十]+、", candidate):
                return False
            return len(candidate) <= 42 and not re.search(r"[。！？!?]", candidate)

        judgment_paragraph_index = 1 if len(paragraphs) >= 2 and is_heading_like(paragraphs[0]) else 0
        first_paragraph = paragraphs[judgment_paragraph_index]
        first_sentence_match = re.search(r"(.+?[。！？!?])", first_paragraph)
        judgment = first_sentence_match.group(1).strip() if first_sentence_match else first_paragraph[:180]
        analysis_source = paragraphs[judgment_paragraph_index + 1 :] if len(paragraphs) > judgment_paragraph_index + 1 else paragraphs[judgment_paragraph_index : judgment_paragraph_index + 1]
        analysis_parts = analysis_source[:4] if analysis_source else paragraphs[:1]
        analysis = "\n\n".join(analysis_parts)
        if not analysis.strip():
            analysis = cleaned[:1800]
        actions = "如有需要，可继续围绕当前判断往下追问或展开。"
        suggestion_match = re.search(r"(?:^|\n)\s*(下一步建议|建议动作)[:：]\s*([\s\S]+)$", cleaned, re.IGNORECASE)
        if suggestion_match:
            actions = suggestion_match.group(2).strip() or actions
        return AiStructuredResponse(
            content=cleaned,
            judgment=judgment,
            analysis=analysis,
            actions=actions or "如有需要，可继续围绕当前判断往下追问或展开。",
            timeline="后续可随资料和讨论继续迭代。",
        )

    def _clean_template_field_value(self, text: str, *, field_type: str | None = None) -> str:
        cleaned = str(text or "").strip()
        if cleaned.startswith("```"):
            inline_fence = re.match(r"^```(?:[a-zA-Z0-9_-]+)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
            if inline_fence:
                cleaned = inline_fence.group(1).strip()
            else:
                lines = cleaned.splitlines()
                cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        cleaned = re.sub(r"^(?:字段(?:填写)?(?:内容)?|答案|建议填写|可填写为|可直接填写为)[:：]\s*", "", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not cleaned:
            return "【待确认】当前缺少可直接填写该字段的资料。"
        return self._enforce_template_field_constraints(cleaned[:1200], field_type=field_type)

    def _template_field_rule(self, field_type: str | None) -> str:
        normalized = str(field_type or "general")
        if normalized == "precise_fact":
            return "只能填写可直接核验的精确事实；资料不够时直接输出【待确认】。"
        if normalized == "structural_summary":
            return "允许基于多份材料压缩概括，但不要夹带如何填写的解释。"
        if normalized == "governance_mechanism":
            return "强依赖章程、制度、会议纪要或党组织记录；资料不足时宁可输出【待确认】，不要写空泛套话。"
        if normalized == "quantitative_result":
            return "优先填写可引用数字；如果没有明确数字，不要用模糊描述凑数，直接输出【待确认】。"
        if normalized == "attachment_material":
            return "只判断材料是否已具备或缺失，不要输出解释性文字。"
        return "请尽量保守、可复核地填写，不要输出过程性提示。"

    def _enforce_template_field_constraints(self, text: str, *, field_type: str | None) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return "【待确认】当前缺少可直接填写该字段的资料。"
        process_hint_markers = (
            "可从",
            "进一步梳理",
            "建议补",
            "建议补充",
            "建议内部核验",
            "可填写",
            "如何填写",
        )
        if cleaned.startswith("【待确认】"):
            return cleaned
        normalized = str(field_type or "general")
        if normalized == "precise_fact":
            if any(marker in cleaned for marker in process_hint_markers) or any(marker in cleaned for marker in ("可能", "大约", "约", "左右", "公开招聘页面显示", "建设中")):
                return "【待确认】当前资料不足以直接确认该精确事实字段。"
        if normalized == "governance_mechanism":
            if any(marker in cleaned for marker in process_hint_markers):
                return "【待确认】当前缺少可直接支撑该治理/党建字段的章程、制度或会议记录。"
        if normalized == "quantitative_result":
            if not re.search(r"\d", cleaned):
                return "【待确认】当前缺少可直接引用的数量或统计口径。"
        if normalized == "attachment_material":
            if "已备" in cleaned or "待补" in cleaned:
                return cleaned
            return "【待确认】当前需进一步核验该材料是否已备齐。"
        return cleaned

    def _soften_caveat_heavy_opening(self, text: str) -> str:
        paragraphs = [item.strip() for item in re.split(r"\n{2,}", str(text).strip()) if item.strip()]
        if not paragraphs:
            return str(text).strip()
        target_index = 0
        if len(paragraphs) >= 2 and len(paragraphs[0]) <= 36 and not re.search(r"[。！？!?]", paragraphs[0]):
            target_index = 1
        first = paragraphs[target_index]
        if not any(
            marker in first
            for marker in (
                "需要首先明确",
                "需要首先说明",
                "资料主要聚焦于",
                "暂时无法确认",
                "以下分析将",
                "事实边界",
            )
        ):
            return "\n\n".join(paragraphs).strip()
        softened = first
        softened = re.sub(r"需要首先(?:明确|说明)的是，?", "", softened)
        softened = re.sub(r"现有资料主要聚焦于[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"且多呈现为[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"这意味着[^。！？!?]*暂时无法确认[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"关于[^。！？!?]*暂时无法确认[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"以下分析将[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"就事实边界而言，?[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"\s+", " ", softened).strip(" ，,。")
        if len(softened) < 24:
            softened = "已经能够勾勒出该对象当前的机构定位、战略意图与核心工作脉络，以下重点展开其中最有判断价值的部分。"
        if not re.search(r"[。！？!?]$", softened):
            softened = f"{softened}。"
        paragraphs[target_index] = softened
        refined = "\n\n".join(paragraphs).strip()
        refined = re.sub(r"基于益语智库当前掌握的[^。！？!?]*[。！？!?]", "", refined)
        refined = re.sub(r"根据现有[^。！？!?]*(?:观察|背景|底稿)[^。！？!?]*[。！？!?]", "", refined)
        refined = re.sub(r"从现有(?:资料|材料|观察)(?:交叉)?来看，?", "", refined)
        refined = re.sub(r"资料中反复出现的", "", refined)
        refined = re.sub(r"文档中(?:反复)?出现的", "", refined)
        refined = re.sub(r"工作坊记录显示", "", refined)
        refined = re.sub(r"\n{3,}", "\n\n", refined).strip()
        return refined

    def _format_provider_error(self, error: Exception | None) -> str:
        if error is None:
            return "未知模型错误"
        if isinstance(error, AiInvocationError):
            return error.detail
        message = str(error).strip() or error.__class__.__name__
        if isinstance(error, httpx.ReadTimeout):
            return f"读取超时：{message}"
        if isinstance(error, httpx.TimeoutException):
            return f"请求超时：{message}"
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code if error.response is not None else "unknown"
            return f"上游状态异常 {status}：{message}"
        return message

    def _structured_from_text_sections(self, text: str) -> AiStructuredResponse:
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        sections = self._extract_section_blocks(cleaned)
        content = sections.get("内容综述", cleaned[:900]).strip()
        analysis = sections.get("结构化分析", sections.get("支持判断的要点", cleaned[:1500])).strip()
        actions = sections.get("建议动作", sections.get("下一步建议", "建议先确认当前资料能支撑的事实，再决定下一步动作。")).strip()
        judgment = sections.get("核心判断", "").strip()
        if not judgment:
            first_line = next((line.strip(" -") for line in analysis.splitlines() if line.strip()), "")
            judgment = first_line or content[:180]
        timeline = sections.get("关键时间线", "建议今天先形成初判，后续随资料补充再更新。").strip()
        return AiStructuredResponse(
            content=content or cleaned[:900],
            judgment=judgment or content[:180],
            analysis=analysis or cleaned[:1500],
            actions=actions,
            timeline=timeline,
        )

    def _extract_section_blocks(self, text: str) -> dict[str, str]:
        pattern = re.compile(r"【(内容综述|核心判断|结构化分析|建议动作|关键时间线|支持判断的要点|下一步建议)】")
        matches = list(pattern.finditer(text))
        if not matches:
            return {}
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            label = match.group(1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            sections[label] = text[start:end].strip()
        return sections

    def _load_relaxed_json(self, text: str) -> dict[str, object]:
        stripped = str(text).strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:])
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start == -1 or end <= start:
                raise RuntimeError("模型返回了不可解析的 JSON。")
            payload = json.loads(stripped[start : end + 1])
        if not isinstance(payload, dict):
            raise RuntimeError("模型返回了非对象 JSON。")
        return payload

    def _fallback_topic_search_queries(self, *, title: str, prompt: str, time_range: str) -> list[str]:
        merged = f"{title} {prompt}".strip()
        for phrase in ("关注", "跟踪", "追踪", "最新", "案例", "信息", "新闻", "如何", "怎么", "打法"):
            merged = merged.replace(phrase, " ")
        merged = re.sub(r"[，。；：、,.!?！？\"“”‘’()（）]+", " ", merged)
        merged = re.sub(r"\s+", " ", merged).strip()
        parts = [part.strip() for part in merged.split(" ") if part.strip()]
        base = " ".join(parts[:6]).strip() or title.strip() or prompt.strip() or "行业资讯"
        compact_title = title.strip()
        window_label = {"1_day": "近一天", "3_days": "近三天", "7_days": "近七天"}.get(time_range, "")
        queries = [base]
        if compact_title and compact_title not in base:
            queries.append(f"{compact_title} {base}".strip())
        if compact_title:
            queries.append(f"{compact_title} {window_label}".strip())
        deduped: list[str] = []
        for item in queries:
            normalized = item.strip()
            if normalized and normalized not in deduped:
                deduped.append(normalized[:72])
        return deduped[:3] or ["行业资讯"]
