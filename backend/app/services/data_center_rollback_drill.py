from __future__ import annotations

from app.db import Database
from app.models import (
    DataCenterRollbackDrillPayloadRecord,
    DataCenterRollbackDrillResultRecord,
    RetrievalModelSettingsPayload,
)
from app.services.retrieval_model_settings import save_retrieval_model_settings


def run_data_center_rollback_drill(
    db: Database,
    *,
    payload: DataCenterRollbackDrillPayloadRecord,
) -> DataCenterRollbackDrillResultRecord:
    normalized_client_ids = [str(item).strip() for item in payload.clientIds if str(item).strip()]
    warnings: list[str] = []
    if not normalized_client_ids:
        warnings.append("未指定 clientIds，回滚动作将按全局开关处理。")

    if payload.dryRun:
        return DataCenterRollbackDrillResultRecord(
            dryRun=True,
            wouldDisableWorkspacePrimary=True,
            wouldDisableChatKernelPrimary=True,
            wouldClearAllowlist=True,
            wouldKeepDrafts=True,
            wouldKeepExecutionTickets=True,
            wouldKeepEvidenceLabels=True,
            warnings=warnings,
            affectedClientIds=normalized_client_ids,
            applied=False,
        )

    # Real rollback: keep business data, only switch off kernel-primary gate.
    db.set_setting("workspace_chat_data_center_primary", "0")
    save_retrieval_model_settings(
        db,
        RetrievalModelSettingsPayload(
            chatKernelPrimaryEnabled=False,
            chatKernelPrimaryClientAllowlist=[],
        ),
    )
    return DataCenterRollbackDrillResultRecord(
        dryRun=False,
        wouldDisableWorkspacePrimary=True,
        wouldDisableChatKernelPrimary=True,
        wouldClearAllowlist=True,
        wouldKeepDrafts=True,
        wouldKeepExecutionTickets=True,
        wouldKeepEvidenceLabels=True,
        warnings=warnings,
        affectedClientIds=normalized_client_ids,
        applied=True,
    )
