from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.artifact_utils import stamp_artifact


@dataclass
class CommandSpec:
    name: str
    cmd: list[str]
    cwd: Path
    kind: str  # pytest | eval | build


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _run_command(spec: CommandSpec) -> dict[str, object]:
    started = datetime.now()
    process = subprocess.run(
        spec.cmd,
        cwd=str(spec.cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    completed = datetime.now()
    output_text = (process.stdout or "").strip()
    error_text = (process.stderr or "").strip()
    duration_ms = int((completed - started).total_seconds() * 1000)
    return {
        "name": spec.name,
        "cmd": " ".join(spec.cmd),
        "cwd": str(spec.cwd),
        "kind": spec.kind,
        "returnCode": int(process.returncode),
        "durationMs": duration_ms,
        "stdout": output_text[-8000:],
        "stderr": error_text[-4000:],
        "passed": bool(process.returncode == 0),
    }


def _parse_eval_payload(command_result: dict[str, object]) -> dict[str, object]:
    stdout = str(command_result.get("stdout") or "").strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except Exception:
        pass
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start >= 0 and end > start:
        chunk = stdout[start : end + 1]
        try:
            return json.loads(chunk)
        except Exception:
            return {}
    return {}


def build_specs(repo_root: Path) -> list[CommandSpec]:
    backend_root = repo_root / "backend"
    return [
        CommandSpec("test_analysis_context_p0", ["uv", "run", "pytest", "tests/test_analysis_context_p0.py"], backend_root, "pytest"),
        CommandSpec("test_workspace_chat_regression", ["uv", "run", "pytest", "tests/test_workspace_chat_regression.py"], backend_root, "pytest"),
        CommandSpec("test_data_center_kernel_p1", ["uv", "run", "pytest", "tests/test_data_center_kernel_p1.py"], backend_root, "pytest"),
        CommandSpec("test_data_center_shadow_p2", ["uv", "run", "pytest", "tests/test_data_center_shadow_p2.py"], backend_root, "pytest"),
        CommandSpec("test_data_center_search_mode_p2", ["uv", "run", "pytest", "tests/test_data_center_search_mode_p2.py"], backend_root, "pytest"),
        CommandSpec("test_data_center_prep_mode_p2", ["uv", "run", "pytest", "tests/test_data_center_prep_mode_p2.py"], backend_root, "pytest"),
        CommandSpec("test_data_center_proposal_mode_p2", ["uv", "run", "pytest", "tests/test_data_center_proposal_mode_p2.py"], backend_root, "pytest"),
        CommandSpec("test_generation_runtime_policy_p21_probe", ["uv", "run", "pytest", "tests/test_generation_runtime_policy_cooldown_expired_probe_p21.py"], backend_root, "pytest"),
        CommandSpec("test_answer_fact_slots_p22", ["uv", "run", "pytest", "tests/test_answer_fact_slots_p22.py"], backend_root, "pytest"),
        CommandSpec("test_official_candidate_boundary_p22", ["uv", "run", "pytest", "tests/test_official_candidate_boundary_p22.py"], backend_root, "pytest"),
        CommandSpec("test_meeting_followup_proposal_p22", ["uv", "run", "pytest", "tests/test_meeting_followup_proposal_p22.py"], backend_root, "pytest"),
        CommandSpec("test_data_center_realistic_eval_p22", ["uv", "run", "pytest", "tests/test_data_center_realistic_eval_p22.py"], backend_root, "pytest"),
        CommandSpec("test_proposal_approval_p23", ["uv", "run", "pytest", "tests/test_proposal_approval_p23.py"], backend_root, "pytest"),
        CommandSpec("test_proposal_execution_ticket_p23", ["uv", "run", "pytest", "tests/test_proposal_execution_ticket_p23.py"], backend_root, "pytest"),
        CommandSpec("test_meeting_followup_execution_p23", ["uv", "run", "pytest", "tests/test_meeting_followup_execution_p23.py"], backend_root, "pytest"),
        CommandSpec("test_workspace_chat_kernel_primary_p23", ["uv", "run", "pytest", "tests/test_workspace_chat_kernel_primary_p23.py"], backend_root, "pytest"),
        CommandSpec("test_evidence_quality_annotations_p23", ["uv", "run", "pytest", "tests/test_evidence_quality_annotations_p23.py"], backend_root, "pytest"),
        CommandSpec("test_external_evidence_review_p23", ["uv", "run", "pytest", "tests/test_external_evidence_review_p23.py"], backend_root, "pytest"),
        CommandSpec("test_execution_ticket_idempotency_p24", ["uv", "run", "pytest", "tests/test_execution_ticket_idempotency_p24.py"], backend_root, "pytest"),
        CommandSpec("test_execution_ticket_retry_p24", ["uv", "run", "pytest", "tests/test_execution_ticket_retry_p24.py"], backend_root, "pytest"),
        CommandSpec("test_execution_ticket_logs_p24", ["uv", "run", "pytest", "tests/test_execution_ticket_logs_p24.py"], backend_root, "pytest"),
        CommandSpec("test_evidence_quality_feedback_selector_p24", ["uv", "run", "pytest", "tests/test_evidence_quality_feedback_selector_p24.py"], backend_root, "pytest"),
        CommandSpec("test_evidence_quality_feedback_rerank_p24", ["uv", "run", "pytest", "tests/test_evidence_quality_feedback_rerank_p24.py"], backend_root, "pytest"),
        CommandSpec("eval_retrieval_p0", ["uv", "run", "python", "scripts/eval_retrieval_p0.py", "--mode", "baseline"], backend_root, "eval"),
        CommandSpec("eval_data_center_answer_p1", ["uv", "run", "python", "scripts/eval_data_center_answer_p1.py", "--mode", "baseline"], backend_root, "eval"),
        CommandSpec("eval_data_center_p2", ["uv", "run", "python", "scripts/eval_data_center_p2.py", "--mode", "baseline"], backend_root, "eval"),
        CommandSpec("eval_data_center_p21", ["uv", "run", "python", "scripts/eval_data_center_p21.py", "--mode", "baseline"], backend_root, "eval"),
        CommandSpec("eval_data_center_realistic_p22_strict", ["uv", "run", "python", "scripts/eval_data_center_realistic_p22.py", "--mode", "baseline", "--strict"], backend_root, "eval"),
        CommandSpec("eval_data_center_p23_strict", ["uv", "run", "python", "scripts/eval_data_center_p23.py", "--mode", "baseline", "--strict"], backend_root, "eval"),
        CommandSpec("build_main", ["npm", "run", "build:main"], repo_root, "build"),
        CommandSpec("build_renderer", ["npm", "run", "build:renderer"], repo_root, "build"),
        CommandSpec("build_backend_check", ["npm", "run", "build:backend-check"], repo_root, "build"),
    ]


def _render_markdown(report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# P2.5 Full Regression Report")
    lines.append("")
    lines.append(f"- startedAt: `{report.get('startedAt')}`")
    lines.append(f"- completedAt: `{report.get('completedAt')}`")
    lines.append(f"- verdict: `{report.get('verdict')}`")
    lines.append("")
    pytest_section = report.get("pytest", {})
    eval_section = report.get("eval", {})
    build_section = report.get("frontendBuild", {})
    lines.append("## Pytest")
    lines.append(f"- passedSuites: {len(pytest_section.get('passedSuites', []))}")
    lines.append(f"- failedSuites: {len(pytest_section.get('failedSuites', []))}")
    lines.append(f"- durationMs: {pytest_section.get('durationMs', 0)}")
    lines.append("")
    lines.append("## Eval")
    for key, value in (eval_section.items() if isinstance(eval_section, dict) else []):
        lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=False)}`")
    lines.append("")
    lines.append("## Frontend Build")
    for key, value in (build_section.items() if isinstance(build_section, dict) else []):
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    script_path = Path(__file__).resolve()
    backend_root = script_path.parents[1]
    repo_root = script_path.parents[2]
    output_dir = backend_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    started_at = _now_iso()
    specs = build_specs(repo_root)
    results = [_run_command(spec) for spec in specs]
    completed_at = _now_iso()

    pytest_results = [item for item in results if item["kind"] == "pytest"]
    eval_results = [item for item in results if item["kind"] == "eval"]
    build_results = [item for item in results if item["kind"] == "build"]

    passed_pytest = [item["name"] for item in pytest_results if item["passed"]]
    failed_pytest = [item["name"] for item in pytest_results if not item["passed"]]
    eval_payloads = {
        item["name"]: _parse_eval_payload(item)
        for item in eval_results
    }
    frontend_build = {
        item["name"].replace("build_", ""): ("pass" if item["passed"] else "fail")
        for item in build_results
    }

    verdict = "pass" if all(bool(item["passed"]) for item in results) else "fail"
    report = {
        "startedAt": started_at,
        "completedAt": completed_at,
        "pytest": {
            "passedSuites": passed_pytest,
            "failedSuites": failed_pytest,
            "durationMs": sum(int(item.get("durationMs") or 0) for item in pytest_results),
            "details": pytest_results,
        },
        "eval": eval_payloads,
        "frontendBuild": frontend_build,
        "commands": results,
        "verdict": verdict,
    }
    report = stamp_artifact(report, "p25_full_regression")

    json_path = output_dir / "P2.5-full-regression-report.json"
    md_path = output_dir / "P2.5-full-regression-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps({"reportJson": str(json_path), "reportMarkdown": str(md_path), "verdict": verdict}, ensure_ascii=False))
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
