from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import PageContextPackRecord, RetrievalModelSettingsRecord
from app.services.analysis_context import infer_page_intent
from app.services.query_router import route_page_query


def _load_cases(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _settings_for_mode(mode: str) -> RetrievalModelSettingsRecord:
    if mode == "shadow":
        return RetrievalModelSettingsRecord(
            embeddingProvider="local_fastembed",
            embeddingModel="BAAI/bge-small-zh-v1.5",
            embeddingDimension=256,
            embeddingMode="local",
            routerEnabled=True,
            routerProvider="doubao",
            routerModel="doubao-smart-router",
            rerankEnabled=True,
            rerankProvider="rules",
            shadowMode=True,
            updatedAt="",
        )
    if mode == "doubao-embedding-large":
        return RetrievalModelSettingsRecord(
            embeddingProvider="doubao",
            embeddingModel="doubao-embedding-large",
            embeddingDimension=1024,
            embeddingMode="doubao",
            routerEnabled=False,
            routerProvider="rules",
            routerModel="",
            rerankEnabled=True,
            rerankProvider="rules",
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
            "rawFallbackAccuracy": 0.0,
            "registryProtectionPass": True,
            "avgLatencyMs": 0.0,
            "failureCount": 1,
        }
    with tempfile.TemporaryDirectory(prefix="retrieval_eval_") as tmp:
        db = Database(Path(tmp) / "eval.db")
        settings = _settings_for_mode(mode)
        intent_hits = 0
        route_hits = 0
        raw_hits = 0
        raw_cases = 0
        registry_ok = True
        failures = 0
        latencies: list[float] = []
        for case in cases:
            try:
                page = str(case.get("page") or "workspace_chat")
                prompt = str(case.get("prompt") or "")
                expected_intent = str(case.get("expectedIntent") or "")
                expected_mode = str(case.get("expectedRetrievalMode") or "")
                expected_registry_mode = str(case.get("expectedJudgmentQueryMode") or "")
                must_use_raw = bool(case.get("mustUseRawEvidence", False))

                inferred_intent = infer_page_intent(prompt, page)
                context_pack = PageContextPackRecord(
                    page=page,  # type: ignore[arg-type]
                    scopeType="client",
                    scopeId=client_id,
                    clientId=client_id,
                    intent=inferred_intent.intent,
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

                if decision.intent == expected_intent:
                    intent_hits += 1
                if decision.retrievalMode == expected_mode:
                    route_hits += 1
                if must_use_raw:
                    raw_cases += 1
                    if decision.shouldUseRawEvidence:
                        raw_hits += 1
                if expected_registry_mode:
                    if str(decision.judgmentQueryMode or "") != expected_registry_mode:
                        registry_ok = False
            except Exception:
                failures += 1

    case_count = len(cases)
    return {
        "caseCount": case_count,
        "intentAccuracy": round(intent_hits / case_count, 4),
        "routeAccuracy": round(route_hits / case_count, 4),
        "rawFallbackAccuracy": round(raw_hits / raw_cases, 4) if raw_cases else 1.0,
        "registryProtectionPass": registry_ok,
        "avgLatencyMs": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "failureCount": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval-router P0 decisions.")
    parser.add_argument("--client-id", default="eval_client")
    parser.add_argument("--mode", default="baseline", choices=["baseline", "shadow", "doubao-embedding-large"])
    parser.add_argument(
        "--fixtures",
        default="tests/fixtures/retrieval_eval_cases.json",
        help="Path to retrieval evaluation cases JSON",
    )
    parser.add_argument("--output", default="", help="Optional path to write JSON report")
    args = parser.parse_args()

    report = run_eval(
        fixtures=Path(args.fixtures),
        mode=args.mode,
        client_id=str(args.client_id),
    )
    output_json = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json + "\n", encoding="utf-8")
    print(output_json)


if __name__ == "__main__":
    main()
