from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json
from app.main import create_app
from app.models import AiStructuredResponse, EvidenceItem, PageContextPackRecord, RouteDecisionRecord
from app.services.evidence_selector import select_answer_evidence
from app.services.retrieval_model_settings import get_retrieval_model_settings
from app.services.workspace_chat_kernel_bridge import decide_kernel_primary_gate
from scripts.artifact_utils import stamp_artifact


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _mock_qwen_generate(*_args, response_schema=None, **_kwargs):
    if isinstance(response_schema, dict):
        properties = response_schema.get("properties")
        if isinstance(properties, dict):
            payload: dict[str, object] = {}
            for key, definition in properties.items():
                if not isinstance(definition, dict):
                    payload[key] = "ok"
                    continue
                schema_type = str(definition.get("type") or "string")
                if schema_type == "array":
                    payload[key] = ["ok"]
                elif schema_type == "integer":
                    payload[key] = 80
                elif schema_type == "number":
                    payload[key] = 0.8
                elif schema_type == "boolean":
                    payload[key] = True
                elif schema_type == "object":
                    payload[key] = {}
                else:
                    payload[key] = "ok"
            return payload
    return "ok"


def _load_cases(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _create_client(client: TestClient, name: str = "eval-p23-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "eval p23",
            "stage": "推进中",
        },
    )
    response.raise_for_status()
    return response.json()["id"]


def _insert_proposal(
    client: TestClient,
    *,
    proposal_id: str,
    client_id: str,
    status: str,
    kind: str,
    with_actions: bool = False,
) -> None:
    now = _now_iso()
    payload: dict[str, object] = {}
    if with_actions:
        payload = {
            "meetingId": "meeting_eval_p23",
            "actionItems": [
                {"id": "act_1", "title": "会后补证据", "summary": "补齐核心证据材料"},
                {"id": "act_2", "title": "确认负责人", "summary": "明确负责人与截止时间"},
            ],
        }
    client.app.state.app_state.db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, 'medium', ?, ?, ?, ?, '[]', '[]', ?, 'tester', NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            proposal_id,
            client_id,
            kind,
            status,
            f"{kind} title",
            f"{kind} summary",
            f"{kind} rationale",
            to_json([{"targetType": "client", "targetId": client_id, "label": "client"}]),
            to_json(payload),
            now,
            now,
        ),
    )


def _record_failure(
    failures: list[dict[str, object]],
    *,
    case_id: str,
    category: str,
    reason: str,
    expected: dict[str, object] | None = None,
    actual: dict[str, object] | None = None,
) -> None:
    failures.append(
        {
            "id": case_id,
            "category": category,
            "reason": reason,
            "expected": expected or {},
            "actual": actual or {},
        }
    )


def _run_case(client: TestClient, *, case_id: str, category: str, client_id: str, seq: int) -> tuple[bool, str]:
    try:
        if category == "proposal_approval":
            proposal_id = f"proposal_p23_approval_{seq}"
            _insert_proposal(client, proposal_id=proposal_id, client_id=client_id, status="pending_review", kind="meeting_followup")
            approved = client.post(f"/api/v1/proposals/{proposal_id}/approve", json={"decidedBy": "tester", "note": "approve"})
            if approved.status_code != 200:
                return False, f"approve_status_{approved.status_code}"
            if approved.json().get("status") != "approved":
                return False, "approve_status_not_approved"
            return True, "ok"

        if category == "execution_ticket":
            proposal_id = f"proposal_p23_exec_{seq}"
            _insert_proposal(client, proposal_id=proposal_id, client_id=client_id, status="approved", kind="evidence_request")
            created = client.post(f"/api/v1/proposals/{proposal_id}/execution-ticket", json={"requestedBy": "tester"})
            if created.status_code != 200:
                return False, f"create_ticket_status_{created.status_code}"
            ticket = created.json().get("executionTicket") or {}
            if ticket.get("status") != "pending":
                return False, "ticket_not_pending"
            executed = client.post(f"/api/v1/execution-tickets/{ticket.get('id')}/execute", json={"requestedBy": "tester"})
            if executed.status_code != 200:
                return False, f"execute_ticket_status_{executed.status_code}"
            final_ticket = (executed.json().get("executionTicket") or {}).get("status")
            if final_ticket != "executed":
                return False, "ticket_not_executed"
            return True, "ok"

        if category == "execution_retry":
            proposal_id = f"proposal_p23_retry_{seq}"
            _insert_proposal(client, proposal_id=proposal_id, client_id=client_id, status="approved", kind="evidence_request")
            created = client.post(f"/api/v1/proposals/{proposal_id}/execution-ticket", json={"requestedBy": "tester"})
            if created.status_code != 200:
                return False, f"create_ticket_status_{created.status_code}"
            ticket = created.json().get("executionTicket") or {}
            ticket_id = str(ticket.get("id") or "").strip()
            if not ticket_id:
                return False, "retry_ticket_id_missing"
            now = _now_iso()
            db = client.app.state.app_state.db
            db.execute(
                """
                UPDATE execution_tickets
                SET status = 'failed',
                    last_error = 'eval_retry_failure',
                    retry_count = 0,
                    max_retries = 3,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, ticket_id),
            )
            db.execute(
                "UPDATE proposal_records SET status = 'failed', updated_at = ? WHERE id = ?",
                (now, proposal_id),
            )
            retried = client.post(
                f"/api/v1/execution-tickets/{ticket_id}/retry",
                json={"requestedBy": "tester", "dryRun": False},
            )
            if retried.status_code != 200:
                return False, f"retry_status_{retried.status_code}"
            retried_ticket = retried.json().get("executionTicket") or {}
            if retried_ticket.get("status") != "pending":
                return False, "retry_ticket_not_pending"
            if int(retried_ticket.get("retryCount") or 0) < 1:
                return False, "retry_count_not_incremented"
            return True, "ok"

        if category == "meeting_followup_execution":
            proposal_id = f"proposal_p23_meeting_exec_{seq}"
            _insert_proposal(
                client,
                proposal_id=proposal_id,
                client_id=client_id,
                status="approved",
                kind="meeting_followup",
                with_actions=True,
            )
            created = client.post(f"/api/v1/proposals/{proposal_id}/execution-ticket", json={"requestedBy": "tester"})
            if created.status_code != 200:
                return False, f"create_ticket_status_{created.status_code}"
            ticket = created.json().get("executionTicket") or {}
            executed = client.post(f"/api/v1/execution-tickets/{ticket.get('id')}/execute", json={"requestedBy": "tester"})
            if executed.status_code != 200:
                return False, f"execute_ticket_status_{executed.status_code}"
            created_task_ids = ((executed.json().get("executionTicket") or {}).get("result") or {}).get("createdTaskIds") or []
            if not created_task_ids:
                return False, "meeting_followup_no_task_created"
            return True, "ok"

        if category == "kernel_chat_primary":
            client.app.state.app_state.db.set_setting("workspace_chat_data_center_primary", "1")
            empty_allowlist = client.post(
                "/api/v1/retrieval/settings",
                json={"chatKernelPrimaryEnabled": True, "chatKernelPrimaryClientAllowlist": []},
            )
            if empty_allowlist.status_code != 200:
                return False, f"kernel_primary_empty_allowlist_status_{empty_allowlist.status_code}"
            empty_settings = get_retrieval_model_settings(client.app.state.app_state.db)
            empty_enabled, empty_reason = decide_kernel_primary_gate(
                workspace_switch_enabled=True,
                settings=empty_settings,
                client_id=client_id,
            )
            if empty_enabled or empty_reason != "client_allowlist_empty":
                return False, "kernel_primary_empty_allowlist_should_block"

            client.post(
                "/api/v1/retrieval/settings",
                json={"chatKernelPrimaryEnabled": True, "chatKernelPrimaryClientAllowlist": [client_id]},
            )
            settings = get_retrieval_model_settings(client.app.state.app_state.db)
            enabled, reason = decide_kernel_primary_gate(
                workspace_switch_enabled=True,
                settings=settings,
                client_id=client_id,
            )
            if not enabled:
                return False, f"kernel_primary_gate_{reason}"
            disabled, _ = decide_kernel_primary_gate(
                workspace_switch_enabled=True,
                settings=settings,
                client_id=f"{client_id}_other",
            )
            if disabled:
                return False, "kernel_primary_allowlist_not_enforced"
            if not settings.chatKernelPrimaryEnabled:
                return False, "kernel_primary_not_used"
            return True, "ok"

        if category == "evidence_quality_feedback":
            db = client.app.state.app_state.db
            client.get("/api/v1/data-center/evidence-quality?limit=1")
            now = _now_iso()
            ann_noise = f"eqa_eval_noise_{seq}"
            ann_useful = f"eqa_eval_useful_{seq}"
            source_id = f"client_feedback_eval_{seq}"
            db.execute(
                """
                INSERT INTO evidence_quality_annotations(
                    id, source_type, source_id, document_id, path, excerpt_hash, source_kind,
                    quality_score, demotion_score, noise_reasons_json, authority_hint,
                    human_label, human_note, created_at, updated_at
                )
                VALUES(?, 'workspace_chat', ?, 'doc_x', '/tmp/doc_x', ?, 'raw_document', 0.8, 0.0, '[]', 'raw', NULL, '', ?, ?)
                """,
                (ann_noise, source_id, f"hash_noise_{seq}", now, now),
            )
            db.execute(
                """
                INSERT INTO evidence_quality_annotations(
                    id, source_type, source_id, document_id, path, excerpt_hash, source_kind,
                    quality_score, demotion_score, noise_reasons_json, authority_hint,
                    human_label, human_note, created_at, updated_at
                )
                VALUES(?, 'workspace_chat', ?, 'doc_y', '/tmp/doc_y', ?, 'raw_document', 0.8, 0.0, '[]', 'raw', NULL, '', ?, ?)
                """,
                (ann_useful, source_id, f"hash_useful_{seq}", now, now),
            )
            labeled = client.post(
                f"/api/v1/data-center/evidence-quality/{ann_noise}/label",
                json={"label": "noise", "note": "人工标注"},
            )
            if labeled.status_code != 200:
                return False, f"quality_label_status_{labeled.status_code}"
            labeled_useful = client.post(
                f"/api/v1/data-center/evidence-quality/{ann_useful}/label",
                json={"label": "useful", "note": "人工标注"},
            )
            if labeled_useful.status_code != 200:
                return False, f"quality_label_useful_status_{labeled_useful.status_code}"
            if labeled_useful.json().get("humanLabel") != "useful":
                return False, "quality_label_not_saved"
            route = RouteDecisionRecord(intent="business_profile", retrievalMode="hybrid")
            page_context = PageContextPackRecord(page="workspace_chat", scopeType="client", scopeId=source_id, clientId=source_id)
            selected = select_answer_evidence(
                prompt="核心业务是什么",
                intent="business_profile",
                route_decision=route,
                evidence=[
                    EvidenceItem(
                        id="noise",
                        title="历史回答生成稿",
                        excerpt="模板化内容",
                        sourceType="generated_answer",
                        documentId="doc_x",
                        path="/tmp/doc_x",
                        score=2.0,
                        sectionLabel="模板",
                        retrievalStage="raw_chunk",
                    ),
                    EvidenceItem(
                        id="useful",
                        title="业务介绍",
                        excerpt="机构核心业务包含资源支持与项目服务",
                        sourceType="knowledge_chunk",
                        documentId="doc_y",
                        path="/tmp/doc_y",
                        score=0.1,
                        sectionLabel="业务介绍",
                        retrievalStage="raw_chunk",
                    ),
                ],
                page_context=page_context,
                db=db,
                source_type="workspace_chat",
                source_id=source_id,
            )
            if not selected or selected[0].id != "useful":
                return False, "quality_feedback_not_applied"
            return True, "ok"

        if category == "external_evidence_review":
            db = client.app.state.app_state.db
            now = _now_iso()
            card_id = f"evcard_eval_{seq}"
            client.get("/api/v1/external-evidence-cards?limit=1")
            db.execute(
                """
                INSERT INTO external_evidence_cards(
                    id, source_url, source_domain, source_tier, title, published_at,
                    fact_excerpt, summary, tags_json, related_scope_type, related_scope_id,
                    confidence, status, created_at, updated_at
                )
                VALUES(?, 'https://example.com/news', 'example.com', 'trusted_media', '外部证据', NULL,
                       '摘录', '摘要', '[]', 'topic', ?, 0.65, 'candidate', ?, ?)
                """,
                (card_id, f"topic_eval_{seq}", now, now),
            )
            accepted = client.post(f"/api/v1/external-evidence-cards/{card_id}/accept")
            if accepted.status_code != 200:
                return False, f"external_accept_status_{accepted.status_code}"
            rejected = client.post(f"/api/v1/external-evidence-cards/{card_id}/reject")
            if rejected.status_code != 200:
                return False, f"external_reject_status_{rejected.status_code}"
            if rejected.json().get("status") != "rejected":
                return False, "external_reject_not_applied"
            return True, "ok"

        if category == "ops_panel_contract":
            repo_root = Path(__file__).resolve().parents[2]
            panel_path = repo_root / "src" / "renderer" / "components" / "data_center" / "DataCenterOpsPanel.tsx"
            api_path = repo_root / "src" / "renderer" / "lib" / "api.ts"
            if not panel_path.exists():
                return False, "ops_panel_missing"
            panel_text = panel_path.read_text(encoding="utf-8")
            api_text = api_path.read_text(encoding="utf-8")
            required_panel = ["batchApproveProposals", "batchRejectProposals", "retryExecutionTicket", "getExecutionTicketLogs"]
            for token in required_panel:
                if token not in panel_text:
                    return False, f"ops_panel_missing_{token}"
            required_api = ["batchApproveProposals(", "batchRejectProposals(", "retryExecutionTicket(", "getExecutionTicketLogs("]
            for token in required_api:
                if token not in api_text:
                    return False, f"ops_api_missing_{token}"
            return True, "ok"
    except Exception as exc:  # pragma: no cover - safety for eval pipeline
        return False, str(exc)

    return False, "unknown_category"


def _strict_gate(report: dict[str, object]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if float(report.get("proposalApprovalPassRate") or 0.0) < 0.9:
        reasons.append("proposalApprovalPassRate < 0.9")
    if float(report.get("executionTicketPassRate") or 0.0) < 0.9:
        reasons.append("executionTicketPassRate < 0.9")
    if float(report.get("executionRetryPassRate") or 0.0) < 0.8:
        reasons.append("executionRetryPassRate < 0.8")
    if float(report.get("meetingFollowupExecutionPassRate") or 0.0) < 0.8:
        reasons.append("meetingFollowupExecutionPassRate < 0.8")
    if float(report.get("kernelChatPrimaryPassRate") or 0.0) < 0.85:
        reasons.append("kernelChatPrimaryPassRate < 0.85")
    if float(report.get("evidenceQualityFeedbackPassRate") or 0.0) < 0.75:
        reasons.append("evidenceQualityFeedbackPassRate < 0.75")
    if float(report.get("externalEvidenceReviewPassRate") or 0.0) < 0.8:
        reasons.append("externalEvidenceReviewPassRate < 0.8")
    if bool(report.get("opsPanelContractPass")) is not True:
        reasons.append("opsPanelContractPass != true")
    if bool(report.get("officialBoundaryPass")) is not True:
        reasons.append("officialBoundaryPass != true")
    if bool(report.get("candidateBoundaryPass")) is not True:
        reasons.append("candidateBoundaryPass != true")
    if bool(report.get("noAutoExecutionViolation")) is not True:
        reasons.append("noAutoExecutionViolation != true")
    if bool(report.get("kernelPrimaryGateEmptyAllowlistPass")) is not True:
        reasons.append("kernelPrimaryGateEmptyAllowlistPass != true")
    if int(report.get("failureCount") or 0) > 0:
        reasons.append("failureCount > 0")
    return len(reasons) == 0, reasons


def run_eval(*, fixtures: Path, mode: str) -> dict[str, object]:
    del mode
    cases = _load_cases(fixtures)
    if not cases:
        return {
            "caseCount": 0,
            "proposalApprovalPassRate": 0.0,
            "executionTicketPassRate": 0.0,
            "executionRetryPassRate": 0.0,
            "meetingFollowupExecutionPassRate": 0.0,
            "kernelChatPrimaryPassRate": 0.0,
            "evidenceQualityFeedbackPassRate": 0.0,
            "externalEvidenceReviewPassRate": 0.0,
            "opsPanelContractPass": False,
            "officialBoundaryPass": False,
            "candidateBoundaryPass": False,
            "noAutoExecutionViolation": False,
            "kernelPrimaryGateEmptyAllowlistPass": False,
            "failureCount": 0,
            "failures": [],
        }

    previous_disable_startup_workers = os.environ.get("YIYU_DISABLE_STARTUP_WORKERS")
    os.environ["YIYU_DISABLE_STARTUP_WORKERS"] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="data_center_eval_p23_") as tmp:
            app = create_app(Path(tmp) / "data")
            with TestClient(app) as client:
                client.app.state.app_state.ai.generate_chat_response = lambda *_args, **_kwargs: AiStructuredResponse(
                    content="基于当前资料，核心业务聚焦资源支持与项目服务。",
                    judgment="ok",
                    analysis="ok",
                    actions="ok",
                    timeline="ok",
                )
                client.app.state.app_state.ai._qwen_generate = _mock_qwen_generate
                client_id = _create_client(client)
                failures: list[dict[str, object]] = []
                counters: Counter[str] = Counter()
                passes: Counter[str] = Counter()

                for index, case in enumerate(cases, start=1):
                    category = str(case.get("category") or "unknown")
                    case_id = str(case.get("id") or f"case_{index}")
                    counters[category] += 1
                    ok, reason = _run_case(client, case_id=case_id, category=category, client_id=client_id, seq=index)
                    if ok:
                        passes[category] += 1
                    else:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category=category,
                            reason=reason,
                        )

                # Official/candidate boundary quick checks.
                db = client.app.state.app_state.db
                now = _now_iso()
                db.execute(
                    """
                    INSERT OR REPLACE INTO judgment_versions(
                        id, client_id, target_type, target_id, topic, version, status, summary,
                        evidence_ids_json, context_pack_id, risk_level, confidence, created_at, updated_at
                    ) VALUES(?, ?, 'client', ?, ?, 1, 'approved', ?, '[]', NULL, 'medium', 'high', ?, ?)
                    """,
                    ("jv_eval_p23_official", client_id, client_id, "正式判断", "已批准正式判断", now, now),
                )
                db.execute(
                    """
                    INSERT OR REPLACE INTO judgment_versions(
                        id, client_id, target_type, target_id, topic, version, status, summary,
                        evidence_ids_json, context_pack_id, risk_level, confidence, created_at, updated_at
                    ) VALUES(?, ?, 'client', ?, ?, 1, 'draft', ?, '[]', NULL, 'medium', 'medium', ?, ?)
                    """,
                    ("jv_eval_p23_candidate", client_id, client_id, "候选判断", "候选判断待确认", now, now),
                )
                boundary_response = client.post(
                    "/api/v1/data-center/resolve",
                    json={
                        "scope": {
                            "page": "workspace_chat",
                            "scopeType": "client",
                            "scopeId": client_id,
                            "clientId": client_id,
                        },
                        "prompt": "系统里已批准的正式判断有哪些？",
                        "mode": "answer",
                        "shadow": True,
                    },
                )
                boundary_ok = False
                candidate_boundary_ok = False
                kernel_primary_gate_empty_allowlist_pass = False
                if boundary_response.status_code == 200:
                    body = boundary_response.json()
                    route = body.get("routeDecision") or {}
                    debug = body.get("debug") or {}
                    quality = debug.get("answerQuality") if isinstance(debug, dict) else {}
                    if not isinstance(quality, dict):
                        quality = {}
                    boundary_ok = bool(
                        route.get("routeMode") == "registry_only"
                        and route.get("shouldUseRawEvidence") is False
                        and quality.get("officialBoundaryViolation") is not True
                    )
                    candidate_boundary_ok = bool(quality.get("candidateAsOfficialRisk") is not True)

                # No auto execution violation: created tickets stay pending before execute.
                _insert_proposal(
                    client,
                    proposal_id="proposal_no_auto_exec",
                    client_id=client_id,
                    status="approved",
                    kind="task_prep",
                )
                create_ticket = client.post(
                    "/api/v1/proposals/proposal_no_auto_exec/execution-ticket",
                    json={"requestedBy": "tester"},
                )
                no_auto_execution_violation = False
                if create_ticket.status_code == 200:
                    no_auto_execution_violation = (create_ticket.json().get("executionTicket") or {}).get("status") == "pending"

                settings_probe = get_retrieval_model_settings(db)
                settings_probe = settings_probe.model_copy(
                    update={
                        "chatKernelPrimaryEnabled": True,
                        "chatKernelPrimaryClientAllowlist": [],
                    }
                )
                empty_gate_enabled, empty_gate_reason = decide_kernel_primary_gate(
                    workspace_switch_enabled=True,
                    settings=settings_probe,
                    client_id=client_id,
                )
                kernel_primary_gate_empty_allowlist_pass = bool(
                    (empty_gate_enabled is False) and (empty_gate_reason == "client_allowlist_empty")
                )

                def _rate(category: str) -> float:
                    total = counters[category]
                    return (passes[category] / total) if total else 1.0

                report = {
                    "caseCount": len(cases),
                    "proposalApprovalPassRate": round(_rate("proposal_approval"), 4),
                    "executionTicketPassRate": round(_rate("execution_ticket"), 4),
                    "executionRetryPassRate": round(_rate("execution_retry"), 4),
                    "meetingFollowupExecutionPassRate": round(_rate("meeting_followup_execution"), 4),
                    "kernelChatPrimaryPassRate": round(_rate("kernel_chat_primary"), 4),
                    "evidenceQualityFeedbackPassRate": round(_rate("evidence_quality_feedback"), 4),
                    "externalEvidenceReviewPassRate": round(_rate("external_evidence_review"), 4),
                    "opsPanelContractPass": bool(_rate("ops_panel_contract") >= 1.0),
                    "officialBoundaryPass": boundary_ok,
                    "candidateBoundaryPass": candidate_boundary_ok,
                    "noAutoExecutionViolation": no_auto_execution_violation,
                    "kernelPrimaryGateEmptyAllowlistPass": kernel_primary_gate_empty_allowlist_pass,
                    "failureCount": len(failures),
                    "failures": failures,
                }
                return report
    finally:
        if previous_disable_startup_workers is None:
            os.environ.pop("YIYU_DISABLE_STARTUP_WORKERS", None)
        else:
            os.environ["YIYU_DISABLE_STARTUP_WORKERS"] = previous_disable_startup_workers


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate DataCenter P2.3 action-loop reliability.")
    parser.add_argument("--mode", default="baseline", choices=["baseline"])
    parser.add_argument(
        "--fixtures",
        default=str(Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "data_center_p23_eval_cases.json"),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = stamp_artifact(run_eval(fixtures=Path(args.fixtures), mode=args.mode), "p23_strict_eval")
    output_path = Path(__file__).resolve().parents[1] / "output" / "P2.6-eval-p23-strict.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict:
        ok, reasons = _strict_gate(report)
        if not ok:
            print(json.dumps({"strictGate": "failed", "reasons": reasons}, ensure_ascii=False, indent=2))
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
