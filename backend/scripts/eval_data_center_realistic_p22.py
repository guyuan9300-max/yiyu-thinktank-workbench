from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from scripts.artifact_utils import stamp_artifact

NOISE_HINTS = ("模板", "母版", "目录页", "封面", "clicktoeditmaster", "历史回答", "生成稿")


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _load_cases(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _create_client(client: TestClient, name: str = "eval-p22-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "eval p2.2",
            "stage": "推进中",
        },
    )
    response.raise_for_status()
    return response.json()["id"]


def _create_task(client: TestClient, client_id: str, *, title: str, desc: str) -> str:
    lists = client.get("/api/v1/task-lists")
    lists.raise_for_status()
    list_id = lists.json()["lists"][0]["id"]
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": desc,
            "listId": list_id,
            "clientId": client_id,
            "ownerName": "评测",
        },
    )
    task.raise_for_status()
    return task.json()["id"]


def _create_meeting(client: TestClient, client_id: str, *, title: str) -> str:
    meeting = client.post(
        f"/api/v1/clients/{client_id}/meetings",
        json={"title": title, "scheduledAt": "2026-04-21T10:00:00"},
    )
    meeting.raise_for_status()
    return meeting.json()["meeting"]["id"]


def _seed_eval_data(client: TestClient, *, client_id: str, meeting_id: str) -> None:
    db = client.app.state.app_state.db
    now = _now_iso()

    # 业务/战略语义任务，供 page context 与 evidence selector 命中。
    _create_task(
        client,
        client_id,
        title="资源支持与项目服务协同推进",
        desc="核心业务包括资源支持、项目服务与平台协作，服务对象是公益组织与基金会。",
    )
    _create_task(
        client,
        client_id,
        title="2026 战略方向：生态协作与数字化",
        desc="战略重点覆盖能力建设、生态协作、数字化与筹资资源。",
    )

    # 会议 follow-up 样本。
    db.execute(
        "INSERT OR REPLACE INTO action_items(id, meeting_id, title, owner_name, due_date, confidence, publish_status, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        ("act_eval_1", meeting_id, "确认合作方名单并分配负责人", "张三", "2026-04-30", 0.92, "published", now),
    )
    db.execute(
        "INSERT OR REPLACE INTO risks(id, meeting_id, summary, severity, created_at) VALUES(?, ?, ?, ?, ?)",
        ("risk_eval_1", meeting_id, "预算来源待确认，影响执行节奏", "high", now),
    )
    db.execute(
        "INSERT OR REPLACE INTO ambiguities(id, meeting_id, raw_text, candidates_json, status, created_at) VALUES(?, ?, ?, ?, ?, ?)",
        ("amb_eval_1", meeting_id, "战略口径是年度目标还是季度目标尚未统一", "[]", "open", now),
    )

    # judgment 边界样本：一个 approved + 一个 candidate。
    db.execute(
        """
        INSERT OR REPLACE INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence, created_at, updated_at
        ) VALUES(?, ?, 'client', ?, ?, 1, ?, ?, '[]', NULL, 'medium', 'high', ?, ?)
        """,
        ("jv_eval_official", client_id, client_id, "正式判断：当前主线是能力建设+生态协作", "approved", "已批准：主线聚焦能力建设与生态协作", now, now),
    )
    db.execute(
        """
        INSERT OR REPLACE INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence, created_at, updated_at
        ) VALUES(?, ?, 'client', ?, ?, 1, ?, ?, '[]', NULL, 'medium', 'medium', ?, ?)
        """,
        ("jv_eval_candidate", client_id, client_id, "候选判断：数字化可能成为下一阶段重点", "draft", "候选：数字化方向待确认", now, now),
    )


def _scope_payload(*, case: dict[str, object], client_id: str, task_id: str, meeting_id: str) -> dict[str, object]:
    page = str(case.get("page") or "workspace_chat")
    scope_type = str(case.get("scopeType") or "client")
    if scope_type == "task":
        return {
            "page": page,
            "scopeType": "task",
            "scopeId": task_id,
            "taskId": task_id,
            "clientId": client_id,
        }
    if scope_type == "meeting":
        return {
            "page": page,
            "scopeType": "meeting",
            "scopeId": meeting_id,
            "meetingId": meeting_id,
            "clientId": client_id,
        }
    return {
        "page": page,
        "scopeType": "client",
        "scopeId": client_id,
        "clientId": client_id,
    }


def _noise_count(answer_material: dict[str, object]) -> tuple[int, int]:
    highlights = answer_material.get("evidenceHighlights") if isinstance(answer_material, dict) else []
    if not isinstance(highlights, list):
        return 0, 0
    total = 0
    noise = 0
    for item in highlights:
        if not isinstance(item, dict):
            continue
        total += 1
        merged = f"{item.get('title') or ''} {item.get('excerpt') or ''}".lower()
        if any(token.lower() in merged for token in NOISE_HINTS):
            noise += 1
    return noise, total


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


def _post_with_retry(
    client: TestClient,
    *,
    path: str,
    payload: dict[str, object],
    retries: int = 1,
) -> tuple[int, dict[str, object]]:
    last_status = 0
    last_body: dict[str, object] = {}
    for _ in range(max(0, retries) + 1):
        response = client.post(path, json=payload)
        last_status = response.status_code
        try:
            body = response.json()
        except Exception:
            body = {}
        last_body = body if isinstance(body, dict) else {}
        if last_status != 200:
            continue
        return last_status, last_body
    return last_status, last_body


def _warmup_data_center_runtime(
    client: TestClient,
    *,
    client_id: str,
    task_id: str,
    meeting_id: str,
) -> None:
    warm_scope = _scope_payload(
        case={"page": "workspace_chat", "scopeType": "client"},
        client_id=client_id,
        task_id=task_id,
        meeting_id=meeting_id,
    )
    warm_payload = {
        "scope": warm_scope,
        "prompt": "预热：请概括当前客户的核心业务线索",
        "mode": "answer",
        "includeRawEvidence": False,
        "includeActionSuggestions": True,
        "shadow": True,
        "persistDrafts": False,
    }
    _post_with_retry(client, path="/api/v1/data-center/resolve", payload=warm_payload, retries=1)
    _post_with_retry(client, path="/api/v1/data-center/resolve", payload={**warm_payload, "mode": "diagnostic"}, retries=1)


def _strict_gate(report: dict[str, object]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if float(report.get("factSlotHitRate") or 0.0) < 0.75:
        reasons.append("factSlotHitRate < 0.75")
    if bool(report.get("officialBoundaryPass")) is not True:
        reasons.append("officialBoundaryPass != true")
    if float(report.get("meetingFollowupPassRate") or 0.0) < 0.75:
        reasons.append("meetingFollowupPassRate < 0.75")
    if int(report.get("failureCount") or 0) > 0:
        reasons.append("failureCount > 0")
    return len(reasons) == 0, reasons


def run_eval(*, fixtures: Path, mode: str) -> dict[str, object]:
    del mode
    cases = _load_cases(fixtures)
    if not cases:
        return {
            "caseCount": 0,
            "intentAccuracy": 0.0,
            "answerQualityPassRate": 0.0,
            "directAnswerPassRate": 0.0,
            "factSlotHitRate": 0.0,
            "evidenceNoiseRate": 0.0,
            "proposalDraftHitRate": 0.0,
            "meetingFollowupPassRate": 0.0,
            "officialBoundaryPass": False,
            "candidateBoundaryPass": False,
            "failureCount": 0,
            "avgLatencyMs": 0.0,
            "failures": [],
        }

    with tempfile.TemporaryDirectory(prefix="data_center_realistic_p22_") as tmp:
        app = create_app(Path(tmp) / "data")
        with TestClient(app) as client:
            client_id = _create_client(client)
            task_id = _create_task(client, client_id, title="P2.2 评测任务", desc="用于 data center realistic eval")
            meeting_id = _create_meeting(client, client_id, title="P2.2 评测会议")
            _seed_eval_data(client, client_id=client_id, meeting_id=meeting_id)
            _warmup_data_center_runtime(client, client_id=client_id, task_id=task_id, meeting_id=meeting_id)

            failures: list[dict[str, object]] = []
            latencies: list[float] = []
            intent_total = 0
            intent_match = 0
            quality_total = 0
            quality_pass = 0
            direct_answer_total = 0
            direct_answer_pass = 0
            fact_slot_total = 0
            fact_slot_pass = 0
            proposal_total = 0
            proposal_pass = 0
            meeting_followup_total = 0
            meeting_followup_pass = 0
            noise_count = 0
            evidence_count = 0
            official_boundary_total = 0
            official_boundary_pass = 0
            candidate_boundary_total = 0
            candidate_boundary_pass = 0

            for case in cases:
                case_id = str(case.get("id") or "unknown_case")
                scope = _scope_payload(case=case, client_id=client_id, task_id=task_id, meeting_id=meeting_id)
                mode_value = str(case.get("mode") or "answer")
                prompt = str(case.get("prompt") or "")
                payload = {
                    "scope": scope,
                    "prompt": prompt,
                    "mode": mode_value,
                    "includeRawEvidence": bool(case.get("includeRawEvidence", False)),
                    "includeActionSuggestions": True,
                    "shadow": True,
                    "persistDrafts": mode_value == "proposal",
                }

                started = perf_counter()
                response_status, body = _post_with_retry(
                    client,
                    path="/api/v1/data-center/resolve",
                    payload=payload,
                    retries=1,
                )
                latencies.append((perf_counter() - started) * 1000)
                if response_status != 200:
                    _record_failure(
                        failures,
                        case_id=case_id,
                        category="request",
                        reason="resolve_non_200",
                        expected={"status": 200},
                        actual={"status": response_status},
                    )
                    continue

                if mode_value == "answer" and body.get("answerPlan") is None and body.get("answerMaterial") is None:
                    retry_status, retry_body = _post_with_retry(
                        client,
                        path="/api/v1/data-center/resolve",
                        payload=payload,
                        retries=1,
                    )
                    if retry_status == 200 and isinstance(retry_body, dict):
                        body = retry_body

                route_decision = body.get("routeDecision") if isinstance(body.get("routeDecision"), dict) else {}
                answer_plan = body.get("answerPlan") if isinstance(body.get("answerPlan"), dict) else {}
                answer_material = body.get("answerMaterial") if isinstance(body.get("answerMaterial"), dict) else {}
                content_seed = str(answer_material.get("directAnswerSeed") or "")

                expected_intent = str(case.get("expectedIntent") or "").strip()
                if expected_intent:
                    intent_total += 1
                    observed_intent = str(answer_plan.get("intent") or route_decision.get("intent") or "")
                    if observed_intent == expected_intent:
                        intent_match += 1
                    else:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="intent",
                            reason="intent_mismatch",
                            expected={"intent": expected_intent},
                            actual={"intent": observed_intent},
                        )

                diagnostic_quality: dict[str, object] = {}
                diagnostic_route: dict[str, object] = {}
                if mode_value == "answer":
                    diagnostic_status, diagnostic_body = _post_with_retry(
                        client,
                        path="/api/v1/data-center/resolve",
                        payload={**payload, "mode": "diagnostic"},
                        retries=1,
                    )
                    if diagnostic_status == 200:
                        dbg = diagnostic_body.get("debug", {})
                        if isinstance(dbg, dict):
                            diagnostic_quality = dbg.get("answerQuality", {}) if isinstance(dbg.get("answerQuality"), dict) else {}
                            diagnostic_route = diagnostic_body.get("routeDecision") if isinstance(diagnostic_body.get("routeDecision"), dict) else {}
                    quality_total += 1
                    if str(diagnostic_quality.get("grade") or "") in {"pass", "warn"}:
                        quality_pass += 1
                    else:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="quality",
                            reason="answer_quality_fail",
                            expected={"grade": "pass|warn"},
                            actual={"grade": diagnostic_quality.get("grade")},
                        )

                    direct_answer_total += 1
                    if content_seed.strip():
                        direct_answer_pass += 1
                    else:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="quality",
                            reason="direct_answer_seed_empty",
                        )

                    must_have_business = bool(case.get("mustHaveBusinessSlots"))
                    must_have_strategy = bool(case.get("mustHaveStrategySlots"))
                    if must_have_business or must_have_strategy:
                        fact_slot_total += 1
                        if must_have_business:
                            slots = answer_material.get("businessProfile") if isinstance(answer_material.get("businessProfile"), dict) else {}
                            modules = slots.get("businessModules") if isinstance(slots, dict) else []
                            slot_hit = bool(isinstance(modules, list) and modules and any(str(module) in content_seed for module in modules))
                        else:
                            slots = answer_material.get("strategyProfile") if isinstance(answer_material.get("strategyProfile"), dict) else {}
                            directions = slots.get("strategicDirections") if isinstance(slots, dict) else []
                            time_boundary = str(slots.get("timeBoundary") or "") if isinstance(slots, dict) else ""
                            slot_hit = bool(isinstance(directions, list) and directions and time_boundary)
                        if slot_hit:
                            fact_slot_pass += 1
                        else:
                            _record_failure(
                                failures,
                                case_id=case_id,
                                category="slot",
                                reason="fact_slot_miss",
                                expected={"mustHaveBusinessSlots": must_have_business, "mustHaveStrategySlots": must_have_strategy},
                                actual={"businessProfile": answer_material.get("businessProfile"), "strategyProfile": answer_material.get("strategyProfile")},
                            )

                    n, t = _noise_count(answer_material)
                    noise_count += n
                    evidence_count += t

                if mode_value == "proposal":
                    proposal_total += 1
                    drafts = body.get("proposalDrafts") if isinstance(body.get("proposalDrafts"), list) else []
                    if drafts:
                        proposal_pass += 1
                    else:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="proposal",
                            reason="proposal_drafts_empty",
                        )

                if bool(case.get("mustGenerateFollowup")):
                    meeting_followup_total += 1
                    drafts = body.get("proposalDrafts") if isinstance(body.get("proposalDrafts"), list) else []
                    kinds = {str(item.get("kind") or "") for item in drafts if isinstance(item, dict)}
                    expected_kinds = {
                        str(item)
                        for item in case.get("expectedDraftKinds", ["meeting_followup", "evidence_request", "judgment_review"])
                        if str(item).strip()
                    }
                    if kinds & expected_kinds:
                        meeting_followup_pass += 1
                    else:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="meeting",
                            reason="meeting_followup_missing",
                            expected={"kinds": sorted(expected_kinds)},
                            actual={"kinds": sorted(kinds)},
                        )

                expected_route_mode = str(case.get("expectedRouteMode") or "").strip()
                if expected_route_mode:
                    observed_mode = str(route_decision.get("routeMode") or "")
                    if observed_mode != expected_route_mode:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="route",
                            reason="route_mode_mismatch",
                            expected={"routeMode": expected_route_mode},
                            actual={"routeMode": observed_mode},
                        )
                expected_raw = case.get("mustUseRawEvidence")
                if isinstance(expected_raw, bool):
                    observed_raw = bool(route_decision.get("shouldUseRawEvidence"))
                    if observed_raw != expected_raw:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="route",
                            reason="raw_evidence_expectation_mismatch",
                            expected={"shouldUseRawEvidence": expected_raw},
                            actual={"shouldUseRawEvidence": observed_raw},
                        )

                if expected_intent == "official_judgment_registry":
                    official_boundary_total += 1
                    route_used = diagnostic_route if diagnostic_route else route_decision
                    route_mode = str(route_used.get("routeMode") or "")
                    should_raw = bool(route_used.get("shouldUseRawEvidence"))
                    boundary_violation = bool(diagnostic_quality.get("officialBoundaryViolation"))
                    candidate_risk = bool(diagnostic_quality.get("candidateAsOfficialRisk"))
                    if route_mode == "registry_only" and (not should_raw) and (not boundary_violation) and (not candidate_risk):
                        official_boundary_pass += 1
                    else:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="boundary",
                            reason="official_boundary_failed",
                            expected={"routeMode": "registry_only", "shouldUseRawEvidence": False, "officialBoundaryViolation": False},
                            actual={
                                "routeMode": route_mode,
                                "shouldUseRawEvidence": should_raw,
                                "officialBoundaryViolation": boundary_violation,
                                "candidateAsOfficialRisk": candidate_risk,
                            },
                        )

                page_context = body.get("pageContext") if isinstance(body.get("pageContext"), dict) else {}
                if bool(case.get("mustCheckCandidateBoundary")) and isinstance(page_context.get("candidateJudgments"), list) and page_context.get("candidateJudgments"):
                    candidate_boundary_total += 1
                    boundary_notes = answer_material.get("boundaryNotes") if isinstance(answer_material.get("boundaryNotes"), list) else []
                    merged = " ".join(str(item) for item in boundary_notes)
                    if "候选" in merged or "正式" in merged:
                        candidate_boundary_pass += 1
                    else:
                        _record_failure(
                            failures,
                            case_id=case_id,
                            category="boundary",
                            reason="candidate_boundary_missing",
                            actual={"boundaryNotes": boundary_notes},
                        )

            report = {
                "caseCount": len(cases),
                "intentAccuracy": round(intent_match / intent_total, 4) if intent_total else 0.0,
                "answerQualityPassRate": round(quality_pass / quality_total, 4) if quality_total else 0.0,
                "directAnswerPassRate": round(direct_answer_pass / direct_answer_total, 4) if direct_answer_total else 0.0,
                "factSlotHitRate": round(fact_slot_pass / fact_slot_total, 4) if fact_slot_total else 0.0,
                "evidenceNoiseRate": round(noise_count / evidence_count, 4) if evidence_count else 0.0,
                "proposalDraftHitRate": round(proposal_pass / proposal_total, 4) if proposal_total else 0.0,
                "meetingFollowupPassRate": round(meeting_followup_pass / meeting_followup_total, 4) if meeting_followup_total else 0.0,
                "officialBoundaryPass": bool(official_boundary_total == 0 or official_boundary_pass == official_boundary_total),
                "candidateBoundaryPass": bool(candidate_boundary_total == 0 or candidate_boundary_pass == candidate_boundary_total),
                "failureCount": int(len(failures)),
                "avgLatencyMs": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
                "failures": failures,
                "stats": {
                    "intentTotal": intent_total,
                    "qualityTotal": quality_total,
                    "factSlotTotal": fact_slot_total,
                    "meetingFollowupTotal": meeting_followup_total,
                    "officialBoundaryTotal": official_boundary_total,
                    "categories": dict(Counter(item["category"] for item in failures)),
                },
            }
            return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate realistic DataCenter P2.2 scenarios.")
    parser.add_argument("--mode", default="baseline", choices=["baseline", "semantic-shadow"])
    parser.add_argument(
        "--fixtures",
        default="tests/fixtures/data_center_realistic_eval_cases.json",
        help="Path to realistic eval fixture",
    )
    parser.add_argument("--output", default="", help="Optional output file")
    parser.add_argument("--strict", action="store_true", help="Enable release gate checks and fail fast on threshold violations")
    args = parser.parse_args()

    report = stamp_artifact(run_eval(fixtures=Path(args.fixtures), mode=str(args.mode)), "p22_strict_eval")
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    output_path = Path(args.output) if args.output else (Path(__file__).resolve().parents[1] / "output" / "P2.6-eval-p22-strict.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)

    if args.strict:
        ok, reasons = _strict_gate(report)
        if not ok:
            print("\n[STRICT-GATE-FAILED]")
            for reason in reasons:
                print(f"- {reason}")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
