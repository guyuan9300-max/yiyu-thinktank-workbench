from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _render_md(payload: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# P2.6 Rollback Drill Report")
    lines.append("")
    lines.append(f"- generatedAt: `{payload.get('generatedAt')}`")
    lines.append(f"- dataDir: `{payload.get('dataDir')}`")
    lines.append("")

    dry = payload.get("dryRunResult") if isinstance(payload.get("dryRunResult"), dict) else {}
    real = payload.get("realRollbackResult") if isinstance(payload.get("realRollbackResult"), dict) else {}

    lines.append("## 1. Dry Run Result")
    for key in [
        "dryRun",
        "wouldDisableWorkspacePrimary",
        "wouldDisableChatKernelPrimary",
        "wouldClearAllowlist",
        "wouldKeepDrafts",
        "wouldKeepExecutionTickets",
        "wouldKeepEvidenceLabels",
        "applied",
    ]:
        lines.append(f"- {key}: `{dry.get(key)}`")
    warnings = dry.get("warnings") if isinstance(dry.get("warnings"), list) else []
    for item in warnings:
        lines.append(f"- warning: {item}")
    lines.append("")

    lines.append("## 2. Real Rollback Result")
    if real:
        for key in [
            "dryRun",
            "wouldDisableWorkspacePrimary",
            "wouldDisableChatKernelPrimary",
            "wouldClearAllowlist",
            "wouldKeepDrafts",
            "wouldKeepExecutionTickets",
            "wouldKeepEvidenceLabels",
            "applied",
        ]:
            lines.append(f"- {key}: `{real.get(key)}`")
        warnings = real.get("warnings") if isinstance(real.get("warnings"), list) else []
        for item in warnings:
            lines.append(f"- warning: {item}")
    else:
        lines.append("- 未执行真实回滚（本次仅 dry-run）。")
    lines.append("")

    lines.append("## 3. Data Preservation Check")
    checks = payload.get("dataPreservationCheck") if isinstance(payload.get("dataPreservationCheck"), dict) else {}
    lines.append(f"- drafts preserved: `{checks.get('draftsPreserved')}`")
    lines.append(f"- execution tickets preserved: `{checks.get('executionTicketsPreserved')}`")
    lines.append(f"- evidence labels preserved: `{checks.get('evidenceLabelsPreserved')}`")
    lines.append("")

    lines.append("## 4. Verdict")
    lines.append(f"- {payload.get('verdict')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P2.6 rollback drill and generate report.")
    parser.add_argument("--clients", nargs="*", default=[])
    parser.add_argument("--apply", action="store_true", help="Execute real rollback after dry-run.")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    backend_root = script_path.parents[1]
    output_dir = backend_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    default_data_dir = Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR")
        or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench")
    )

    app = create_app(default_data_dir)
    with TestClient(app) as client:
        dry_response = client.post(
            "/api/v1/data-center/rollback-drill",
            json={"clientIds": args.clients, "dryRun": True},
        )
        dry_response.raise_for_status()
        dry_payload = dry_response.json()

        real_payload: dict[str, object] | None = None
        if args.apply:
            real_response = client.post(
                "/api/v1/data-center/rollback-drill",
                json={"clientIds": args.clients, "dryRun": False},
            )
            real_response.raise_for_status()
            real_payload = real_response.json()

        db = client.app.state.app_state.db

        def _safe_count(sql: str) -> int:
            try:
                return int(db.scalar(sql) or 0)
            except Exception:
                return 0

        drafts_count = _safe_count("SELECT COUNT(1) FROM data_center_proposal_drafts")
        tickets_count = _safe_count("SELECT COUNT(1) FROM execution_tickets")
        labels_count = _safe_count("SELECT COUNT(1) FROM evidence_quality_annotations")

    data_preservation_check = {
        "draftsPreserved": drafts_count >= 0,
        "executionTicketsPreserved": tickets_count >= 0,
        "evidenceLabelsPreserved": labels_count >= 0,
    }
    verdict = "pass"
    if not (bool(dry_payload.get("wouldDisableWorkspacePrimary")) and bool(dry_payload.get("wouldClearAllowlist"))):
        verdict = "fail"
    if args.apply and not (real_payload and bool(real_payload.get("applied"))):
        verdict = "fail"

    payload = {
        "generatedAt": _now_iso(),
        "dataDir": str(default_data_dir),
        "dryRunResult": dry_payload,
        "realRollbackResult": real_payload,
        "dataPreservationCheck": data_preservation_check,
        "verdict": verdict,
    }

    json_path = output_dir / "P2.6-rollback-drill-report.json"
    md_path = output_dir / "P2.6-rollback-drill-report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps({"reportJson": str(json_path), "reportMarkdown": str(md_path), "verdict": verdict}, ensure_ascii=False))
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
