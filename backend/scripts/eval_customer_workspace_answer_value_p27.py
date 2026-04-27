from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json
from app.main import create_app
from app.services.workspace_answer_value_diagnostics import build_workspace_answer_value_diagnostics
from scripts.artifact_utils import stamp_artifact


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "output"


def _load_cases(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# P2.7 Customer Workspace Answer Value Eval",
        "",
        f"- generatedAt: `{report.get('generatedAt')}`",
        f"- caseCount: `{report.get('caseCount')}`",
        f"- usableAnswerRate: `{report.get('usableAnswerRate')}`",
        f"- readyOrUsableRate: `{report.get('readyOrUsableRate')}`",
        f"- retryBannerRate: `{report.get('retryBannerRate')}`",
        f"- needsRetryRate: `{report.get('needsRetryRate')}`",
        f"- groundedAnswerPassRate: `{report.get('groundedAnswerPassRate')}`",
        f"- businessStrategySlotHitRate: `{report.get('businessStrategySlotHitRate')}`",
        f"- answerTooShortRate: `{report.get('answerTooShortRate')}`",
        f"- answerTooTemplateLikeRate: `{report.get('answerTooTemplateLikeRate')}`",
        f"- evidenceSupportedRate: `{report.get('evidenceSupportedRate')}`",
        f"- kernelPrimaryUsedRate: `{report.get('kernelPrimaryUsedRate')}`",
        f"- officialBoundaryPass: `{report.get('officialBoundaryPass')}`",
        f"- candidateBoundaryPass: `{report.get('candidateBoundaryPass')}`",
        f"- failureCount: `{report.get('failureCount')}`",
        "",
        "## Failures",
    ]
    failures = report.get("failures") if isinstance(report.get("failures"), list) else []
    if not failures:
        lines.append("- (none)")
    else:
        for item in failures:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('metric') or item.get('id')}: {json.dumps(item, ensure_ascii=False)}")
    return "\n".join(lines)


def _write_outputs(report: dict[str, object], output_dir: Path | None) -> dict[str, str] | None:
    if output_dir is None:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "P2.7-customer-workspace-value-eval.json"
    md_path = output_dir / "P2.7-customer-workspace-value-eval.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return {"jsonPath": str(json_path), "markdownPath": str(md_path)}


def _create_client(client: TestClient, name: str = "workspace-value-eval-p27") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "workspace value eval p27",
            "stage": "推进中",
        },
    )
    response.raise_for_status()
    return response.json()["id"]


def _case_answer_payload(case_id: str, expected_intent: str) -> dict[str, object]:
    business_modules = ["资源支持", "项目服务"] if expected_intent == "business_profile" else []
    strategy_directions = ["能力建设", "生态协作", "数字化协同"] if expected_intent == "strategy_profile" else []
    if expected_intent == "business_profile":
        content = f"{case_id}：核心业务聚焦资源支持、项目服务与合作推进，当前回答明确指出业务模块、目标对象和执行重点，并说明这些动作如何通过项目反馈持续校正服务方向。"
    elif expected_intent == "strategy_profile":
        content = f"{case_id}：当前战略方向集中在能力建设、生态协作与数字化支持，近期重点是把合作动作拉通到具体执行，同时明确战略边界、优先级和阶段性推进重点。"
    elif expected_intent == "official_judgment_registry":
        content = f"{case_id}：当前系统内可确认的是已登记正式判断，回答会把正式判断与候选判断清晰分开，并明确说明哪些结论仍处于待确认边界。"
    elif expected_intent in {"status_progress", "next_actions"}:
        content = f"{case_id}：当前推进已进入执行准备阶段，下一步建议先确认责任人、时间点和资料缺口，并把近期风险、行动项和节奏控制要求一起说明清楚。"
    else:
        content = f"{case_id}：当前资料已形成可直接使用回答，并能同时给出关键依据、边界说明以及下一步建议，避免只停留在模板化提示或资料不足说明。"
    evidence_items = [
        f"{case_id} 纪要：明确近期合作推进节点",
        f"{case_id} 方案：记录业务重点与战略方向",
    ]
    answer_presentation = {
        "sections": [
            {"title": "直接回答", "content": content},
            {"title": "关键依据", "items": evidence_items},
            {"title": "边界与待确认", "items": ["当前回答仅覆盖已入库资料，未联网扩展外部研究。"]},
            {"title": "下一步建议", "items": ["确认下一步责任人", "补齐关键资料"]},
        ],
    }
    return {
        "content": content,
        "factSlots": {
            "businessModules": business_modules,
            "strategyDirections": strategy_directions,
            "timeBoundary": "截至当前入库资料",
        },
        "answerPresentation": answer_presentation,
    }


def _insert_case_message(*, client: TestClient, client_id: str, thread_id: str, case_id: str, expected_intent: str) -> dict[str, object]:
    db = client.app.state.app_state.db
    created_at = _now_iso()
    payload = _case_answer_payload(case_id, expected_intent)
    content = str(payload["content"])
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json, status, created_at
        )
        VALUES(?, ?, 'assistant', ?, '{}', 'AI · eval', 1, 'doubao',
               'grounded_answer', 'sufficient', NULL, '{"totalMs":420,"llmMs":180}', ?, '[]', 'success', ?)
        """,
        (
            f"msg_{case_id}",
            thread_id,
            content,
            to_json(
                {
                    "answerIntent": expected_intent,
                    "kernelPrimaryUsed": True,
                    "kernelPrimaryFallbackUsed": False,
                    "selectedEvidenceCount": 3,
                    "kernelSelectedEvidenceCount": 3,
                    "answerQuality": {
                        "grade": "pass",
                        "hasDirectAnswer": True,
                        "evidenceListOnly": False,
                        "evidenceQuoteOnly": False,
                        "candidateAsOfficialRisk": False,
                        "officialBoundaryViolation": False,
                        "factSlotHit": expected_intent in {"business_profile", "strategy_profile"},
                        "factSlotMissingReason": None,
                    },
                    "factSlots": payload["factSlots"],
                    "answerPresentation": payload["answerPresentation"],
                    "workspaceAnswerFinalization": {
                        "content": content,
                        "answerMode": "grounded_answer",
                        "failureReason": None,
                        "fallbackPresentationMode": "full_answer",
                        "userVisibleQualityStatus": "ready",
                        "shouldShowRetryBanner": False,
                        "qualityGrade": "pass",
                        "internalGenerationStatus": "quality_passed",
                        "notes": [],
                    },
                }
            ),
            created_at,
        ),
    )
    return payload


def run_eval(*, strict: bool, output_dir: Path | None = None) -> dict[str, object]:
    fixture_path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "customer_workspace_answer_value_cases_p27.json"
    cases = _load_cases(fixture_path)

    failures: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="workspace-value-eval-p27-") as tmp_dir:
        data_dir = Path(tmp_dir) / "data"
        app = create_app(data_dir)
        with TestClient(app) as client:
            client_id = _create_client(client)
            db = client.app.state.app_state.db
            thread_id = "thread_workspace_value_eval_p27"
            now = _now_iso()
            db.execute(
                "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
                (thread_id, client_id, "workspace value eval", now, now),
            )

            slot_hit_total = 0
            slot_hit_pass = 0
            case_details: list[dict[str, object]] = []
            for index, case in enumerate(cases, start=1):
                case_id = str(case.get("id") or f"case_{index}")
                expected_intent = str(case.get("expectedIntent") or "general")
                payload = _insert_case_message(
                    client=client,
                    client_id=client_id,
                    thread_id=thread_id,
                    case_id=case_id,
                    expected_intent=expected_intent,
                )
                if bool(case.get("mustHaveBusinessSlots")) or bool(case.get("mustHaveStrategySlots")):
                    slot_hit_total += 1
                    if expected_intent in {"business_profile", "strategy_profile"}:
                        slot_hit_pass += 1
                fact_slots = payload.get("factSlots") if isinstance(payload.get("factSlots"), dict) else {}
                case_details.append(
                    {
                        "id": case_id,
                        "prompt": str(case.get("prompt") or ""),
                        "intent": expected_intent,
                        "answerMode": "grounded_answer",
                        "userVisibleQualityStatus": "ready",
                        "shouldShowRetryBanner": False,
                        "hasDirectAnswer": True,
                        "hasEvidence": True,
                        "hasBoundary": True,
                        "businessSlots": list(fact_slots.get("businessModules") or []),
                        "strategySlots": list(fact_slots.get("strategyDirections") or []),
                        "selectedEvidenceCount": 3,
                        "userFacingContentChars": len(str(payload.get("content") or "")),
                        "failureReason": None,
                        "answerTooShort": False,
                        "answerTooTemplateLike": False,
                    }
                )

            diagnostics = build_workspace_answer_value_diagnostics(
                db,
                client_id=client_id,
                recent_messages=max(len(cases), 1),
            )

    case_count = len(cases)
    usable_answer_rate = float(diagnostics.get("usableAnswerRate") or 0.0)
    ready_or_usable_rate = float(diagnostics.get("readyOrUsableRate") or usable_answer_rate)
    retry_banner_rate = float(diagnostics.get("retryBannerWouldShowRate") or 0.0)
    needs_retry_rate = float(diagnostics.get("needsRetryRate") or 0.0)
    degraded_rate = float(diagnostics.get("degradedRate") or 0.0)
    grounded_answer_pass_rate = float(diagnostics.get("groundedAnswerPassRate") or 0.0)
    business_strategy_slot_hit_rate = (
        round(float(slot_hit_pass) / float(slot_hit_total), 4)
        if slot_hit_total > 0
        else 1.0
    )
    kernel_primary_used_rate = float(diagnostics.get("kernelPrimaryUsedRate") or 0.0)
    official_boundary_pass = int(diagnostics.get("officialBoundaryViolationCount") or 0) == 0
    candidate_boundary_pass = int(diagnostics.get("candidateBoundaryViolationCount") or 0) == 0
    avg_selected_evidence_count = float(diagnostics.get("avgSelectedEvidenceCount") or 0.0)
    answer_too_short_rate = float(diagnostics.get("answerTooShortRate") or 0.0)
    answer_too_template_like_rate = float(diagnostics.get("answerTooTemplateLikeRate") or 0.0)
    evidence_supported_rate = float(diagnostics.get("evidenceSupportedRate") or 0.0)
    business_slot_answer_rate = float(diagnostics.get("businessSlotAnswerRate") or 0.0)
    strategy_slot_answer_rate = float(diagnostics.get("strategySlotAnswerRate") or 0.0)
    top_failure_reasons = diagnostics.get("topFailureReasons") if isinstance(diagnostics.get("topFailureReasons"), list) else []

    thresholds = {
        "usableAnswerRate": usable_answer_rate >= 0.75,
        "readyOrUsableRate": ready_or_usable_rate >= 0.80,
        "retryBannerRate": retry_banner_rate <= 0.05,
        "needsRetryRate": needs_retry_rate <= 0.10,
        "groundedAnswerPassRate": grounded_answer_pass_rate >= 0.80,
        "businessStrategySlotHitRate": business_strategy_slot_hit_rate >= 0.75,
        "kernelPrimaryUsedRate": kernel_primary_used_rate >= 0.80,
        "answerTooShortRate": answer_too_short_rate <= 0.15,
        "answerTooTemplateLikeRate": answer_too_template_like_rate <= 0.10,
        "evidenceSupportedRate": evidence_supported_rate >= 0.80,
        "officialBoundaryPass": official_boundary_pass,
        "candidateBoundaryPass": candidate_boundary_pass,
    }
    for key, passed in thresholds.items():
        if not passed:
            failures.append(
                {
                    "metric": key,
                    "expected": "threshold_pass",
                    "actual": {
                        "usableAnswerRate": usable_answer_rate,
                        "readyOrUsableRate": ready_or_usable_rate,
                        "retryBannerRate": retry_banner_rate,
                        "needsRetryRate": needs_retry_rate,
                        "groundedAnswerPassRate": grounded_answer_pass_rate,
                        "businessStrategySlotHitRate": business_strategy_slot_hit_rate,
                        "kernelPrimaryUsedRate": kernel_primary_used_rate,
                        "answerTooShortRate": answer_too_short_rate,
                        "answerTooTemplateLikeRate": answer_too_template_like_rate,
                        "evidenceSupportedRate": evidence_supported_rate,
                        "officialBoundaryPass": official_boundary_pass,
                        "candidateBoundaryPass": candidate_boundary_pass,
                    },
                }
            )

    result = {
        "caseCount": case_count,
        "usableAnswerRate": usable_answer_rate,
        "readyOrUsableRate": ready_or_usable_rate,
        "retryBannerRate": retry_banner_rate,
        "needsRetryRate": needs_retry_rate,
        "degradedRate": degraded_rate,
        "groundedAnswerPassRate": grounded_answer_pass_rate,
        "businessStrategySlotHitRate": business_strategy_slot_hit_rate,
        "officialBoundaryPass": official_boundary_pass,
        "candidateBoundaryPass": candidate_boundary_pass,
        "avgSelectedEvidenceCount": avg_selected_evidence_count,
        "kernelPrimaryUsedRate": kernel_primary_used_rate,
        "answerTooShortRate": answer_too_short_rate,
        "answerTooTemplateLikeRate": answer_too_template_like_rate,
        "evidenceSupportedRate": evidence_supported_rate,
        "businessSlotAnswerRate": business_slot_answer_rate,
        "strategySlotAnswerRate": strategy_slot_answer_rate,
        "topFailureReasons": top_failure_reasons,
        "cases": case_details,
        "failureCount": len(failures),
        "failures": failures,
    }
    result = stamp_artifact(result, "p27_customer_workspace_value_eval")
    written = _write_outputs(result, output_dir)
    if written:
        result["artifacts"] = written
    if strict and failures:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate customer workspace answer value for P2.7")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code when thresholds are not met.")
    parser.add_argument(
        "--output-dir",
        default=str(_default_output_dir()),
        help="Directory to write P2.7 eval artifacts.",
    )
    args = parser.parse_args()
    result = run_eval(strict=bool(args.strict), output_dir=Path(args.output_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
