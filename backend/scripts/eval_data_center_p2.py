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


def _create_client(client: TestClient, name: str = "eval-p2-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "eval p2",
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
            "title": "P2 评测任务",
            "desc": "用于 data center p2 eval",
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
        json={"title": "P2 评测会议", "scheduledAt": "2026-04-21T10:00:00"},
    )
    meeting.raise_for_status()
    return meeting.json()["meeting"]["id"]


def _create_topic(client: TestClient) -> str:
    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "P2 评测雷达",
            "prompt": "追踪行业变化",
            "timeRange": "7_days",
            "preferredSources": [],
        },
    )
    radar.raise_for_status()
    radar_id = radar.json()["id"]
    candidate = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "评测话题",
            "summary": "评测话题摘要",
            "source": "manual",
        },
    )
    candidate.raise_for_status()
    return candidate.json()["id"]


def _scope_payload(
    *,
    case: dict[str, object],
    client_id: str,
    task_id: str,
    meeting_id: str,
    topic_id: str,
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
    if scope_type == "topic":
        return {
            "page": page,
            "scopeType": "topic",
            "scopeId": topic_id,
            "topicId": topic_id,
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
            "answerQualityPassRate": 0.0,
            "directAnswerPassRate": 0.0,
            "evidenceListOnlyFailCount": 0,
            "searchSelectedHitRate": 0.0,
            "prepCompletenessRate": 0.0,
            "proposalDraftRate": 0.0,
            "meetingKernelPass": True,
            "stableFallbackLockCount": 0,
            "failureCount": 0,
            "avgLatencyMs": 0.0,
        }

    with tempfile.TemporaryDirectory(prefix="data_center_p2_eval_") as tmp:
        app = create_app(Path(tmp) / "data")
        with TestClient(app) as client:
            client_id = _create_client(client)
            task_id = _create_task(client, client_id)
            meeting_id = _create_meeting(client, client_id)
            topic_id = _create_topic(client)

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
            direct_answer_pass = 0
            evidence_list_fail_count = 0
            search_selected = 0
            search_total = 0
            prep_complete = 0
            prep_total = 0
            proposal_with_draft = 0
            proposal_total = 0
            meeting_kernel_pass = True
            quality_pass = 0
            latencies: list[float] = []

            for case in cases:
                mode_value = str(case.get("mode") or "answer")
                scope = _scope_payload(
                    case=case,
                    client_id=client_id,
                    task_id=task_id,
                    meeting_id=meeting_id,
                    topic_id=topic_id,
                )
                payload = {
                    "scope": scope,
                    "prompt": str(case.get("prompt") or ""),
                    "mode": mode_value,
                    "includeRawEvidence": False,
                    "includeActionSuggestions": True,
                    "shadow": True,
                }
                started = perf_counter()
                response = client.post("/api/v1/data-center/resolve", json=payload)
                latencies.append((perf_counter() - started) * 1000)
                if response.status_code != 200:
                    failures += 1
                    continue
                result = response.json()

                if mode_value == "answer":
                    material = result.get("answerMaterial") or {}
                    seed = str(material.get("directAnswerSeed") or "").strip()
                    if seed:
                        direct_answer_pass += 1
                    if seed.startswith("-") or seed.startswith("1."):
                        evidence_list_fail_count += 1
                    if seed:
                        quality_pass += 1
                elif mode_value == "search":
                    search_total += 1
                    selected = (result.get("searchResult") or {}).get("selectedHits") or []
                    if isinstance(selected, list) and len(selected) > 0:
                        search_selected += 1
                elif mode_value == "prep":
                    prep_total += 1
                    prep_result = result.get("prepResult") or {}
                    known = prep_result.get("knownFacts") or []
                    sections = prep_result.get("sections") or []
                    if known or sections:
                        prep_complete += 1
                elif mode_value == "proposal":
                    proposal_total += 1
                    drafts = result.get("proposalDrafts") or []
                    if isinstance(drafts, list) and len(drafts) > 0:
                        proposal_with_draft += 1
                elif scope.get("page") == "meeting_detail":
                    page_context = result.get("pageContext") or {}
                    if page_context.get("page") != "meeting_detail":
                        meeting_kernel_pass = False

            state_resp = client.get(
                "/api/v1/runtime/generation-state",
                params={"clientId": client_id, "answerIntent": "general"},
            )
            stable_lock_count = 0
            if state_resp.status_code == 200 and state_resp.json().get("stableFallbackActive"):
                stable_lock_count = 1

    case_count = len(cases)
    answer_case_count = max(1, sum(1 for c in cases if str(c.get("mode") or "answer") == "answer"))
    return {
        "caseCount": case_count,
        "answerQualityPassRate": round(quality_pass / answer_case_count, 4),
        "directAnswerPassRate": round(direct_answer_pass / answer_case_count, 4),
        "evidenceListOnlyFailCount": int(evidence_list_fail_count),
        "searchSelectedHitRate": round((search_selected / search_total), 4) if search_total else 0.0,
        "prepCompletenessRate": round((prep_complete / prep_total), 4) if prep_total else 0.0,
        "proposalDraftRate": round((proposal_with_draft / proposal_total), 4) if proposal_total else 0.0,
        "meetingKernelPass": bool(meeting_kernel_pass),
        "stableFallbackLockCount": int(stable_lock_count),
        "failureCount": int(failures),
        "avgLatencyMs": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate data center P2 runtime and kernel closure.")
    parser.add_argument("--mode", default="baseline", choices=["baseline", "semantic-shadow"])
    parser.add_argument(
        "--fixtures",
        default="tests/fixtures/data_center_p2_eval_cases.json",
        help="Path to P2 evaluation fixtures",
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
