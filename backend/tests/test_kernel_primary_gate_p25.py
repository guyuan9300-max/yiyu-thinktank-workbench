from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import RetrievalModelSettingsRecord
from app.services.workspace_chat_kernel_bridge import decide_kernel_primary_gate


def _settings(**overrides) -> RetrievalModelSettingsRecord:
    base = RetrievalModelSettingsRecord()
    return base.model_copy(update=overrides)


def test_kernel_primary_gate_requires_workspace_switch():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=False,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="client_1",
    )
    assert enabled is False
    assert reason == "workspace_chat_data_center_primary_disabled"


def test_kernel_primary_gate_requires_retrieval_switch():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=False, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="client_1",
    )
    assert enabled is False
    assert reason == "chat_kernel_primary_disabled"


def test_kernel_primary_gate_empty_allowlist_blocked():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=[]),
        client_id="client_1",
    )
    assert enabled is False
    assert reason == "client_allowlist_empty"


def test_kernel_primary_gate_allowlist_hit_and_wildcard():
    enabled_exact, reason_exact = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="client_1",
    )
    assert enabled_exact is True
    assert reason_exact == "enabled"

    enabled_wildcard, reason_wildcard = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["*"]),
        client_id="client_any",
    )
    assert enabled_wildcard is True
    assert reason_wildcard == "enabled"


def test_kernel_primary_gate_missing_client_and_mismatch():
    enabled_missing, reason_missing = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="",
    )
    assert enabled_missing is False
    assert reason_missing == "client_id_missing"

    enabled_miss, reason_miss = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="client_2",
    )
    assert enabled_miss is False
    assert reason_miss == "client_not_in_allowlist"
