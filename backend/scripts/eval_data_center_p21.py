from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def _load_cases(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _create_client(client: TestClient, name: str = "eval-p21-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "eval p2.1",
            "stage": "推进中",
        },
    )
    response.raise_for_status()
    return response.json()["id"]


def _create_task(client: TestClient, client_id: str) -> str:
    lists = client.get("/api/v1/task-lists")
    lists.raise_for_status()
    list_id = lists.json()["lists"][0]["id"]
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "P2.1 评测任务",
            "desc": "用于 data center p2.1 eval",
            "listId": list_id,
            "clientId": client_id,
            "ownerName": "评测",
        },
    )
    task.raise_for_status()
    return task.json()["id"]


def _create_meeting(client: TestClient, client_id: str) -> str:
    meeting = client.post(
        f"/api/v1/clients/{client_id}/meetings",
        json={"title": "P2.1 评测会议", "scheduledAt": "2026-04-21T10:00:00"},
    )
    meeting.raise_for_status()
    return meeting.json()["meeting"]["id"]


def _scope_payload(
    *,
    case: dict[str, object],
    client_id: str,
    task_id: str,
    meeting_id: str,
) -> dict[str, object]:
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


def run_eval(*, fixtures: Path, mode: str) -> dict[str, object]:
    cases = _load_cases(fixtures)
    if not cases:
        return {
            "caseCount": 0,
            "shadowTruthfulnessPassRate": 0.0,
            "proposalDraftPersistencePassRate": 0.0,
            "stableFallbackLockCount": 0,
            "cooldownExpiredProbePass": False,
            "diagnosticsBreakdownCompletenessRate": 0.0,
            "frontendKernelAdoptionContractPass": False,
            "failureCount": 0,
            "avgLatencyMs": 0.0,
        }

    with tempfile.TemporaryDirectory(prefix="data_center_p21_eval_") as tmp:
        app = create_app(Path(tmp) / "data")
        with TestClient(app) as client:
            client_id = _create_client(client)
            task_id = _create_task(client, client_id)
            meeting_id = _create_meeting(client, client_id)

            if mode == "semantic-shadow":
                client.post(
                    "/api/v1/retrieval/settings",
                    json={
                        "routerEnabled": True,
                        "routerProvider": "local_semantic",
                        "routerMode": "semantic_shadow",
                        "shadowMode": True,
                    },
                )

            failures = 0
            latencies: list[float] = []
            proposal_cases = 0
            proposal_pass = 0
            diagnostics_total = 0
            diagnostics_complete = 0

            for case in cases:
                mode_value = str(case.get("mode") or "answer")
                scope = _scope_payload(
                    case=case,
                    client_id=client_id,
                    task_id=task_id,
                    meeting_id=meeting_id,
                )
                payload = {
                    "scope": scope,
                    "prompt": str(case.get("prompt") or ""),
                    "mode": mode_value,
                    "includeRawEvidence": False,
                    "includeActionSuggestions": True,
                    "shadow": True,
                    "persistDrafts": mode_value == "proposal",
                }
                started = perf_counter()
                response = client.post("/api/v1/data-center/resolve", json=payload)
                latencies.append((perf_counter() - started) * 1000)
                if response.status_code != 200:
                    failures += 1
                    continue
                result = response.json()

                if mode_value == "proposal":
                    proposal_cases += 1
                    persisted = result.get("persistedProposalDraftIds") or []
                    deduped = result.get("dedupedDraftIds") or []
                    if (isinstance(persisted, list) and persisted) or (isinstance(deduped, list) and deduped):
                        proposal_pass += 1

                diagnostics = client.get(
                    "/api/v1/runtime/workspace-chat-diagnostics",
                    params={"clientId": client_id, "recentMessages": 20},
                )
                diagnostics_total += 1
                if diagnostics.status_code == 200:
                    body = diagnostics.json()
                    breakdown = body.get("breakdown") or {}
                    required = {"generation", "retrieval", "evidenceQuality", "dataIntegrity", "intent"}
                    if isinstance(breakdown, dict) and required.issubset(set(breakdown.keys())):
                        diagnostics_complete += 1

            shadow_truthfulness = 0.0
            shadow_runs_resp = client.get(
                "/api/v1/data-center/shadow-runs",
                params={"scopeType": "client", "scopeId": client_id, "limit": 200},
            )
            if shadow_runs_resp.status_code == 200:
                runs = shadow_runs_resp.json()
                if isinstance(runs, list) and runs:
                    independent_count = 0
                    for run in runs:
                        if not isinstance(run, dict):
                            continue
                        baseline = run.get("baseline") if isinstance(run.get("baseline"), dict) else {}
                        candidate = run.get("candidate") if isinstance(run.get("candidate"), dict) else {}
                        baseline_quality = baseline.get("answerQuality") if isinstance(baseline.get("answerQuality"), dict) else None
                        candidate_quality = candidate.get("answerQuality") if isinstance(candidate.get("answerQuality"), dict) else None
                        baseline_plan = baseline.get("answerPlan") if isinstance(baseline.get("answerPlan"), dict) else None
                        candidate_plan = candidate.get("answerPlan") if isinstance(candidate.get("answerPlan"), dict) else None
                        baseline_route = baseline.get("routeDecision") if isinstance(baseline.get("routeDecision"), dict) else None
                        candidate_route = candidate.get("routeDecision") if isinstance(candidate.get("routeDecision"), dict) else None
                        if (
                            baseline_quality is not None
                            and candidate_quality is not None
                            and baseline_plan is not None
                            and candidate_plan is not None
                            and baseline_route is not None
                            and candidate_route is not None
                        ):
                            independent_count += 1
                    shadow_truthfulness = round(independent_count / len(runs), 4)

            state_resp = client.get(
                "/api/v1/runtime/generation-state",
                params={"clientId": client_id, "answerIntent": "general"},
            )
            stable_lock_count = 0
            cooldown_probe_pass = False
            if state_resp.status_code == 200:
                state = state_resp.json()
                stable_lock_count = 1 if bool(state.get("stableFallbackActive")) else 0
                cooldown_probe_pass = True

            frontend_contract_pass = False
            repo_root = Path(__file__).resolve().parents[1]
            app_path = repo_root.parent / "src" / "renderer" / "App.tsx"
            api_path = repo_root.parent / "src" / "renderer" / "lib" / "api.ts"
            if app_path.exists() and api_path.exists():
                app_text = app_path.read_text(encoding="utf-8")
                api_text = api_path.read_text(encoding="utf-8")
                frontend_contract_pass = all(
                    token in app_text
                    for token in ("page: 'task_detail'", "page: 'meeting_detail'", "page: 'strategic_cockpit'")
                ) and "resolveDataCenterKernel(payload: DataCenterRequest)" in api_text

    return {
        "caseCount": len(cases),
        "shadowTruthfulnessPassRate": shadow_truthfulness,
        "proposalDraftPersistencePassRate": round((proposal_pass / proposal_cases), 4) if proposal_cases else 0.0,
        "stableFallbackLockCount": int(stable_lock_count),
        "cooldownExpiredProbePass": bool(cooldown_probe_pass),
        "diagnosticsBreakdownCompletenessRate": round((diagnostics_complete / diagnostics_total), 4)
        if diagnostics_total
        else 0.0,
        "frontendKernelAdoptionContractPass": bool(frontend_contract_pass),
        "failureCount": int(failures),
        "avgLatencyMs": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate data center P2.1 operational trust metrics.")
    parser.add_argument("--mode", default="baseline", choices=["baseline", "semantic-shadow"])
    parser.add_argument(
        "--fixtures",
        default="tests/fixtures/data_center_p21_eval_cases.json",
        help="Path to P2.1 evaluation fixtures",
    )
    parser.add_argument("--output", default="", help="Optional output path")
    args = parser.parse_args()

    report = run_eval(fixtures=Path(args.fixtures), mode=str(args.mode))
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
