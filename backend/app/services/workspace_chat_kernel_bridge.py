from __future__ import annotations

from app.models import RetrievalModelSettingsRecord


def decide_kernel_primary_gate(
    *,
    workspace_switch_enabled: bool,
    settings: RetrievalModelSettingsRecord,
    client_id: str,
) -> tuple[bool, str]:
    if not workspace_switch_enabled:
        return False, "workspace_chat_data_center_primary_disabled"
    if not bool(settings.chatKernelPrimaryEnabled):
        return False, "chat_kernel_primary_disabled"
    allowlist = [str(item or "").strip() for item in (settings.chatKernelPrimaryClientAllowlist or []) if str(item or "").strip()]
    if not allowlist:
        return False, "client_allowlist_empty"
    normalized_client = str(client_id or "").strip()
    if not normalized_client:
        return False, "client_id_missing"
    if "*" in allowlist or normalized_client in allowlist:
        return True, "enabled"
    return False, "client_not_in_allowlist"
