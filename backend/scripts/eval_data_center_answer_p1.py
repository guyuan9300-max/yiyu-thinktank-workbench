from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import AnswerPolicyRecord, EvidenceItem, PageContextPackRecord, RetrievalModelSettingsRecord
from app.services.answer_layer import build_answer_material, build_answer_plan, build_local_answer_fallback
from app.services.data_center_quality import validate_answer_quality
from app.services.query_router import route_page_query
from app.services.analysis_context import infer_page_intent


def _load_cases(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _mock_evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id="ev_1",
            title="客户材料",
            excerpt="当前资料能确认，战略与业务重点围绕协同推进与服务交付。",
            sourceType="knowledge_chunk",
            retrievalStage="raw_chunk",
        )
    ]


def _settings_for_mode(mode: str) -> RetrievalModelSettingsRecord:
    if mode == "semantic-shadow":
        return RetrievalModelSettingsRecord(
            routerEnabled=True,
            routerProvider="local_semantic",
            routerMode="semantic_shadow",
            shadowMode=True,
            updatedAt="",
        )
    return RetrievalModelSettingsRecord(updatedAt="")


def run_eval(*, fixtures: Path, mode: str, client_id: str) -> dict[str, object]:
    cases = _load_cases(fixtures)
    if not cases:
        return {
            "caseCount": 0,
            "intentAccuracy": 0.0,
            "routeAccuracy": 0.0,
            "directAnswerPassRate": 0.0,
            "evidenceListOnlyFailCount": 0,
            "candidateBoundaryPass": True,
            "officialRegistryProtection": True,
            "avgLatencyMs": 0.0,
        }

    with tempfile.TemporaryDirectory(prefix="data_center_eval_") as tmp:
        db = Database(Path(tmp) / "eval.db")
        settings = _settings_for_mode(mode)

        intent_hits = 0
        route_hits = 0
        direct_pass = 0
        evidence_list_fail = 0
        candidate_boundary_pass = True
        official_registry_pass = True
        latencies: list[float] = []

        for case in cases:
            page = str(case.get("page") or "workspace_chat")
            prompt = str(case.get("prompt") or "")
            expected_intent = str(case.get("expectedIntent") or "")
            expected_route_mode = str(case.get("expectedRouteMode") or "")
            must_raw = bool(case.get("mustUseRawEvidence", False))

            intent = infer_page_intent(prompt, page)
            if intent.intent == expected_intent:
                intent_hits += 1

            context_pack = PageContextPackRecord(
                page=page,  # type: ignore[arg-type]
                scopeType="client",
                scopeId=client_id,
                clientId=client_id,
                intent=intent.intent,
            )
            started = perf_counter()
            decision = route_page_query(
                db,
                page=page,
                prompt=prompt,
                client_id=client_id,
                page_context=context_pack,
                settings=settings,
                ai_service=None,
            )
            latencies.append((perf_counter() - started) * 1000)
            if decision.routeMode == expected_route_mode:
                route_hits += 1
            if expected_intent == "official_judgment_registry" and decision.routeMode != "registry_only":
                official_registry_pass = False
            if must_raw and not decision.shouldUseRawEvidence:
                route_hits -= 1

            plan = build_answer_plan(
                prompt=prompt,
                page_context=context_pack,
                route_decision=decision,
                answer_policy=AnswerPolicyRecord(answerLevel="evidence_based"),
            )
            material = build_answer_material(
                prompt=prompt,
                page_context=context_pack,
                route_decision=decision,
                retrieval_evidence=_mock_evidence(),
                answer_plan=plan,
            )
            fallback = build_local_answer_fallback(
                prompt=prompt,
                answer_plan=plan,
                answer_material=material,
            )
            quality = validate_answer_quality(
                prompt=prompt,
                content=fallback.content,
                answer_plan=plan,
                evidence=_mock_evidence(),
                answer_material=material,
            )
            if quality.get("hasDirectAnswer"):
                direct_pass += 1
            if quality.get("evidenceListOnly"):
                evidence_list_fail += 1
            if "候选" in fallback.content and "已批准" in fallback.content and "尚未" not in fallback.content:
                candidate_boundary_pass = False

    case_count = len(cases)
    return {
        "caseCount": case_count,
        "intentAccuracy": round(intent_hits / case_count, 4),
        "routeAccuracy": round(max(route_hits, 0) / case_count, 4),
        "directAnswerPassRate": round(direct_pass / case_count, 4),
        "evidenceListOnlyFailCount": evidence_list_fail,
        "candidateBoundaryPass": candidate_boundary_pass,
        "officialRegistryProtection": official_registry_pass,
        "avgLatencyMs": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate data center answer P1 quality.")
    parser.add_argument("--client-id", default="eval_client")
    parser.add_argument("--mode", default="baseline", choices=["baseline", "semantic-shadow"])
    parser.add_argument(
        "--fixtures",
        default="tests/fixtures/data_center_answer_eval_cases.json",
        help="Path to answer evaluation cases JSON",
    )
    parser.add_argument("--output", default="", help="Optional output path")
    args = parser.parse_args()

    report = run_eval(
        fixtures=Path(args.fixtures),
        mode=str(args.mode),
        client_id=str(args.client_id),
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
