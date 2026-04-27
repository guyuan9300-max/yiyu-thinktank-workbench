from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import RetrievalModelSettingsRecord
from app.services.workspace_chat_kernel_bridge import decide_kernel_primary_gate


def _settings(**overrides) -> RetrievalModelSettingsRecord:
    return RetrievalModelSettingsRecord().model_copy(update=overrides)


def test_kernel_primary_gate_workspace_switch_disabled():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=False,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="client_1",
    )
    assert enabled is False
    assert reason == "workspace_chat_data_center_primary_disabled"


def test_kernel_primary_gate_chat_kernel_disabled():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=False, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="client_1",
    )
    assert enabled is False
    assert reason == "chat_kernel_primary_disabled"


def test_kernel_primary_gate_empty_allowlist_denied():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=[]),
        client_id="client_1",
    )
    assert enabled is False
    assert reason == "client_allowlist_empty"


def test_kernel_primary_gate_missing_client_id_denied():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="",
    )
    assert enabled is False
    assert reason == "client_id_missing"


def test_kernel_primary_gate_client_in_allowlist_enabled():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="client_1",
    )
    assert enabled is True
    assert reason == "enabled"


def test_kernel_primary_gate_client_not_in_allowlist_denied():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["client_1"]),
        client_id="client_2",
    )
    assert enabled is False
    assert reason == "client_not_in_allowlist"


def test_kernel_primary_gate_star_allowlist_enabled():
    enabled, reason = decide_kernel_primary_gate(
        workspace_switch_enabled=True,
        settings=_settings(chatKernelPrimaryEnabled=True, chatKernelPrimaryClientAllowlist=["*"]),
        client_id="any_client",
    )
    assert enabled is True
    assert reason == "enabled"
