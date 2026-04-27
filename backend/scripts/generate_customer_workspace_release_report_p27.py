from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from json import JSONDecoder
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.eval_data_center_operational_p26 import run_eval as run_operational_eval_p26
from scripts.artifact_utils import stamp_artifact


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "output"


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except Exception:
        pass

    # Some strict-eval artifacts are appended as multiple JSON objects
    # (report first, strictGate summary second). Prefer the first dict payload.
    decoder = JSONDecoder()
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        try:
            payload, next_index = decoder.raw_decode(text, index)
        except Exception:
            return None
        if isinstance(payload, dict):
            return payload
        index = next_index
    return None


def _strict_report_from_full(full_report: dict[str, object] | None, key: str) -> dict[str, object] | None:
    if not isinstance(full_report, dict):
        return None
    eval_payload = full_report.get("eval")
    if not isinstance(eval_payload, dict):
        return None
    candidate = eval_payload.get(key)
    return candidate if isinstance(candidate, dict) else None


def _p22_strict_pass(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    return bool(
        bool(payload.get("officialBoundaryPass"))
        and bool(payload.get("candidateBoundaryPass"))
        and int(payload.get("failureCount") or 0) == 0
    )


def _p23_strict_pass(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    checks = [
        float(payload.get("proposalApprovalPassRate") or 0.0) >= 0.9,
        float(payload.get("executionTicketPassRate") or 0.0) >= 0.9,
        float(payload.get("executionRetryPassRate") or 0.0) >= 0.8,
        float(payload.get("meetingFollowupExecutionPassRate") or 0.0) >= 0.8,
        float(payload.get("kernelChatPrimaryPassRate") or 0.0) >= 0.85,
        float(payload.get("evidenceQualityFeedbackPassRate") or 0.0) >= 0.75,
        float(payload.get("externalEvidenceReviewPassRate") or 0.0) >= 0.8,
        bool(payload.get("opsPanelContractPass")) is True,
        bool(payload.get("officialBoundaryPass")) is True,
        bool(payload.get("candidateBoundaryPass")) is True,
        bool(payload.get("noAutoExecutionViolation")) is True,
        bool(payload.get("kernelPrimaryGateEmptyAllowlistPass")) is True,
        int(payload.get("failureCount") or 0) == 0,
    ]
    return all(checks)


def _p27_value_pass(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    retry_banner_rate_raw = payload.get("retryBannerRate")
    retry_banner_rate = 1.0 if retry_banner_rate_raw is None else float(retry_banner_rate_raw)
    checks = [
        float(payload.get("usableAnswerRate") or 0.0) >= 0.75,
        float(payload.get("readyOrUsableRate") or 0.0) >= 0.80,
        retry_banner_rate <= 0.05,
        float(payload.get("needsRetryRate") or 0.0) <= 0.10,
        float(payload.get("groundedAnswerPassRate") or 0.0) >= 0.80,
        float(payload.get("businessStrategySlotHitRate") or 0.0) >= 0.75,
        float(payload.get("kernelPrimaryUsedRate") or 0.0) >= 0.80,
        float(payload.get("answerTooTemplateLikeRate") or 0.0) <= 0.10,
        float(payload.get("evidenceSupportedRate") or 0.0) >= 0.80,
        bool(payload.get("officialBoundaryPass")) is True,
        bool(payload.get("candidateBoundaryPass")) is True,
        int(payload.get("failureCount") or 0) == 0,
    ]
    return all(checks)


def build_release_report(output_dir: Path) -> dict[str, object]:
    baseline = _read_json(output_dir / "P2.7-baseline.json")
    value_eval = _read_json(output_dir / "P2.7-customer-workspace-value-eval.json")
    value_summary = _read_json(output_dir / "P2.7-workspace-answer-value-summary.json")
    alignment = _read_json(output_dir / "P2.9-runtime-value-alignment-report.json")
    if alignment is None:
        alignment = _read_json(output_dir / "P2.7-repo-package-alignment-report.json")
    full_regression = _read_json(output_dir / "P2.5-full-regression-report.json")
    p26_operational = _read_json(output_dir / "P2.6-operational-eval.json")
    if p26_operational is None:
        p26_operational = run_operational_eval_p26(output_dir)

    p22_strict = _read_json(output_dir / "P2.6-eval-p22-strict.json")
    p23_strict = _read_json(output_dir / "P2.6-eval-p23-strict.json")
    if p22_strict is None:
        p22_strict = _strict_report_from_full(full_regression, "eval_data_center_realistic_p22_strict")
    if p23_strict is None:
        p23_strict = _strict_report_from_full(full_regression, "eval_data_center_p23_strict")

    summary_payload = value_summary if isinstance(value_summary, dict) else {}
    eval_payload = value_eval if isinstance(value_eval, dict) else {}
    alignment_verdict = str((alignment or {}).get("verdict") or "")
    manual_review_count = int(summary_payload.get("reviewCount") or 0)
    estimated_time_saved_rate = float(summary_payload.get("estimatedTimeSavedRate") or 0.0)
    average_manual_minutes = float(summary_payload.get("averageManualBaselineMinutes") or 0.0)
    average_review_minutes = float(summary_payload.get("averageDataCenterReviewMinutes") or 0.0)
    has_time_measurement = average_manual_minutes > 0 and average_review_minutes >= 0
    ready_or_usable_rate = float(eval_payload.get("readyOrUsableRate") or 0.0)
    usable_answer_rate = float(eval_payload.get("usableAnswerRate") or 0.0)
    retry_banner_rate_raw = eval_payload.get("retryBannerRate")
    retry_banner_rate = 1.0 if retry_banner_rate_raw is None else float(retry_banner_rate_raw)
    needs_retry_rate = float(eval_payload.get("needsRetryRate") or 0.0)
    answer_too_template_like_rate = float(eval_payload.get("answerTooTemplateLikeRate") or 0.0)
    evidence_supported_rate = float(eval_payload.get("evidenceSupportedRate") or 0.0)
    business_strategy_slot_hit_rate = float(eval_payload.get("businessStrategySlotHitRate") or 0.0)
    proposal_created_from_answer_count = int(summary_payload.get("proposalCreatedFromAnswerCount") or 0)
    execution_ticket_created_from_answer_count = int(summary_payload.get("executionTicketCreatedFromAnswerCount") or 0)
    top_failure_reasons = (
        eval_payload.get("topFailureReasons") if isinstance(eval_payload.get("topFailureReasons"), list) else []
    )
    official_boundary_known = "officialBoundaryPass" in eval_payload
    candidate_boundary_known = "candidateBoundaryPass" in eval_payload
    official_boundary_pass = bool(eval_payload.get("officialBoundaryPass")) is True
    candidate_boundary_pass = bool(eval_payload.get("candidateBoundaryPass")) is True

    required_artifacts = {
        "baseline": baseline is not None,
        "valueEval": _p27_value_pass(value_eval),
        "runtimeValueAlignment": bool(alignment and alignment_verdict == "pass"),
        "p22Strict": _p22_strict_pass(p22_strict),
        "p23Strict": _p23_strict_pass(p23_strict),
        "manualReviews": manual_review_count >= 10,
    }
    operational_artifacts_ready = bool(
        p26_operational
        and bool(p26_operational.get("rollbackDrillPass"))
        and bool(p26_operational.get("executionRetryMetricsAvailable"))
        and bool(p26_operational.get("opsPanelContractPass"))
    )

    blocking_issues: list[str] = []
    if not required_artifacts["baseline"]:
        blocking_issues.append("P2.7 baseline artifact missing")
    if not required_artifacts["valueEval"]:
        blocking_issues.append("P2.7 customer workspace value eval missing or below threshold")
    if not required_artifacts["runtimeValueAlignment"]:
        blocking_issues.append("runtime value alignment missing or not pass")
    if not required_artifacts["p22Strict"]:
        blocking_issues.append("P2.2 strict eval missing or not pass")
    if not required_artifacts["p23Strict"]:
        blocking_issues.append("P2.3 strict eval missing or not pass")
    if manual_review_count < 10:
        blocking_issues.append("missing workspace answer human review")
    if value_eval and retry_banner_rate > 0.10:
        blocking_issues.append("retry banner rate too high")
    if value_eval and ready_or_usable_rate < 0.75:
        blocking_issues.append("ready or usable rate below threshold")
    if value_eval and answer_too_template_like_rate > 0.15:
        blocking_issues.append("answer too template-like rate too high")
    if value_eval and (
        (official_boundary_known and not official_boundary_pass)
        or (candidate_boundary_known and not candidate_boundary_pass)
    ):
        blocking_issues.append("official/candidate boundary violation detected")
    if manual_review_count >= 10 and not has_time_measurement:
        blocking_issues.append("hold_missing_time_measurement")
    elif manual_review_count >= 10 and has_time_measurement and estimated_time_saved_rate < 0.30:
        blocking_issues.append("estimated time saved rate below threshold")

    verdict = (
        "fail"
        if value_eval
        and (
            (official_boundary_known and not official_boundary_pass)
            or (candidate_boundary_known and not candidate_boundary_pass)
        )
        else ("pass" if not blocking_issues else "hold")
    )
    return stamp_artifact(
        {
        "generatedAt": _now_iso(),
        "requiredArtifacts": required_artifacts,
        "operationalArtifactsReady": operational_artifacts_ready,
        "blockingIssues": blocking_issues,
        "verdict": verdict,
        "baseline": baseline or {},
        "valueEval": value_eval or {},
        "valueSummary": value_summary or {},
        "runtimeValueAlignment": alignment or {},
        "operationalEval": p26_operational or {},
        "p22Strict": p22_strict or {},
        "p23Strict": p23_strict or {},
        "workspaceMetrics": {
            "workspaceRetryBannerRate": retry_banner_rate,
            "readyOrUsableRate": ready_or_usable_rate,
            "usableAnswerRate": usable_answer_rate,
            "needsRetryRate": needs_retry_rate,
            "groundedAnswerPassRate": float(eval_payload.get("groundedAnswerPassRate") or 0.0),
            "businessStrategySlotHitRate": business_strategy_slot_hit_rate,
            "kernelPrimaryUsedRate": float(eval_payload.get("kernelPrimaryUsedRate") or 0.0),
            "answerTooTemplateLikeRate": answer_too_template_like_rate,
            "evidenceSupportedRate": evidence_supported_rate,
            "estimatedTimeSavedRate": estimated_time_saved_rate,
            "manualReviewCount": manual_review_count,
            "proposalCreatedFromAnswerCount": proposal_created_from_answer_count,
            "executionTicketCreatedFromAnswerCount": execution_ticket_created_from_answer_count,
            "topFailureReasons": top_failure_reasons,
        },
        },
        "p29_customer_workspace_value_report",
    )


def _render_markdown(payload: dict[str, object]) -> str:
    metrics = payload.get("workspaceMetrics") if isinstance(payload.get("workspaceMetrics"), dict) else {}
    lines = [
        "# Data Center P2.9 Customer Workspace Value Report",
        "",
        f"- generatedAt: `{payload.get('generatedAt')}`",
        f"- verdict: `{payload.get('verdict')}`",
        "",
        "## Customer Workspace Value Summary",
        f"- workspaceRetryBannerRate: `{metrics.get('workspaceRetryBannerRate')}`",
        f"- readyOrUsableRate: `{metrics.get('readyOrUsableRate')}`",
        f"- usableAnswerRate: `{metrics.get('usableAnswerRate')}`",
        f"- needsRetryRate: `{metrics.get('needsRetryRate')}`",
        f"- groundedAnswerPassRate: `{metrics.get('groundedAnswerPassRate')}`",
        f"- businessStrategySlotHitRate: `{metrics.get('businessStrategySlotHitRate')}`",
        f"- kernelPrimaryUsedRate: `{metrics.get('kernelPrimaryUsedRate')}`",
        f"- answerTooTemplateLikeRate: `{metrics.get('answerTooTemplateLikeRate')}`",
        f"- evidenceSupportedRate: `{metrics.get('evidenceSupportedRate')}`",
        f"- estimatedTimeSavedRate: `{metrics.get('estimatedTimeSavedRate')}`",
        f"- humanReviewCount: `{metrics.get('manualReviewCount')}`",
        f"- proposalCreatedFromAnswerCount: `{metrics.get('proposalCreatedFromAnswerCount')}`",
        f"- executionTicketCreatedFromAnswerCount: `{metrics.get('executionTicketCreatedFromAnswerCount')}`",
        f"- topFailureReasons: `{metrics.get('topFailureReasons')}`",
        "",
        "## Required Artifacts",
    ]
    required = payload.get("requiredArtifacts") if isinstance(payload.get("requiredArtifacts"), dict) else {}
    for key, value in required.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Blocking Issues")
    blocking = payload.get("blockingIssues") if isinstance(payload.get("blockingIssues"), list) else []
    if not blocking:
        lines.append("- (none)")
    else:
        for item in blocking:
            lines.append(f"- {item}")
    return "\n".join(lines)


def write_release_report(payload: dict[str, object], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "P2.7-customer-workspace-release-report.json"
    md_path = output_dir / "P2.7-customer-workspace-release-report.md"
    p29_json_path = output_dir / "P2.9-customer-workspace-value-report.json"
    p29_md_path = output_dir / "P2.9-customer-workspace-value-report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    p29_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    p29_md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return {
        "jsonPath": str(json_path),
        "markdownPath": str(md_path),
        "p29JsonPath": str(p29_json_path),
        "p29MarkdownPath": str(p29_md_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate P2.7 customer workspace release report.")
    parser.add_argument(
        "--output-dir",
        default=str(_default_output_dir()),
        help="Directory containing P2.7/P2.6/P2.5 output artifacts.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    payload = build_release_report(output_dir)
    artifacts = write_release_report(payload, output_dir)
    print(json.dumps({"artifacts": artifacts, "verdict": payload["verdict"]}, ensure_ascii=False))
    return 0 if payload["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
