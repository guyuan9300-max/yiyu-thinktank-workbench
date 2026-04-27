from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _from_json(raw: str | None, default):
    if not raw:
        return default
    try:
        parsed = json.loads(raw)
    except Exception:
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _collect_rollout_rows(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT id, stage, status, client_ids_json, metrics_before_json, metrics_after_json,
               verdict, recommended_action, rollback_reason, started_at, completed_at, created_at, updated_at
        FROM kernel_primary_rollout_runs
        ORDER BY created_at ASC
        """
    ).fetchall()
    result: list[dict[str, object]] = []
    for row in rows:
        metrics_before = _from_json(row[4], {})
        metrics_after = _from_json(row[5], {})
        verdict = str(row[6]) if row[6] else None
        recommended_action = str(row[7]) if row[7] else None
        status = str(row[2] or "")
        if not verdict:
            if status == "completed":
                verdict = "pass"
            elif status in {"failed", "rolled_back"}:
                verdict = "fail"
            else:
                verdict = "watch"
        if not recommended_action:
            recommended_action = "rollback" if verdict == "fail" else "keep"
        result.append(
            {
                "id": str(row[0]),
                "stage": str(row[1]),
                "status": status,
                "clientIds": [str(item) for item in _from_json(row[3], []) if str(item).strip()],
                "metricsBefore": metrics_before,
                "metricsAfter": metrics_after,
                "verdict": verdict,
                "recommendedAction": recommended_action,
                "rollbackReason": str(row[8]) if row[8] else None,
                "startedAt": str(row[9]) if row[9] else None,
                "completedAt": str(row[10]) if row[10] else None,
                "createdAt": str(row[11]),
                "updatedAt": str(row[12]),
            }
        )
    return result


def _global_summary(stage_rows: list[dict[str, object]]) -> dict[str, object]:
    completed_rows = [row for row in stage_rows if str(row.get("status") or "") == "completed"]
    if not completed_rows:
        return {
            "kernelPrimaryFallbackRate": 0.0,
            "answerQualityFailRate": 0.0,
            "officialBoundaryViolation": 0,
            "candidateBoundaryViolation": 0,
            "p95LatencyMs": 0.0,
            "rolloutNotStarted": True,
        }
    latest = completed_rows[-1]
    after = latest.get("metricsAfter") if isinstance(latest.get("metricsAfter"), dict) else {}
    return {
        "kernelPrimaryFallbackRate": float((after or {}).get("kernelPrimaryFallbackRate") or 0.0),
        "answerQualityFailRate": float((after or {}).get("answerQualityFailRate") or 0.0),
        "officialBoundaryViolation": int((after or {}).get("officialBoundaryViolation") or 0),
        "candidateBoundaryViolation": int((after or {}).get("candidateBoundaryViolation") or 0),
        "p95LatencyMs": float((after or {}).get("p95LatencyMs") or 0.0),
        "rolloutNotStarted": False,
    }


def _decide(global_summary: dict[str, object], stage_rows: list[dict[str, object]]) -> str:
    if bool(global_summary.get("rolloutNotStarted")):
        return "hold"
    if not any(str(row.get("status") or "") == "completed" for row in stage_rows):
        return "hold"

    fallback_rate = float(global_summary.get("kernelPrimaryFallbackRate") or 0.0)
    quality_fail_rate = float(global_summary.get("answerQualityFailRate") or 0.0)
    official_boundary = int(global_summary.get("officialBoundaryViolation") or 0)
    candidate_boundary = int(global_summary.get("candidateBoundaryViolation") or 0)

    if (
        fallback_rate > 0.2
        or quality_fail_rate > 0.1
        or official_boundary > 0
        or candidate_boundary > 0
    ):
        return "rollback"

    return "continue"


def _render_markdown(payload: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# P2.6 Kernel Primary Rollout Report")
    lines.append("")
    lines.append(f"- generatedAt: `{payload.get('generatedAt')}`")
    lines.append("")
    lines.append("## Stage Summary")
    stage_summary = payload.get("stageSummary")
    if isinstance(stage_summary, list) and stage_summary:
        for row in stage_summary:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- "
                f"{row.get('stage')} / {row.get('status')} / "
                f"verdict={row.get('verdict')} / recommended={row.get('recommendedAction')}"
            )
    else:
        lines.append("- rolloutNotStarted=true")
    lines.append("")
    lines.append("## Global Summary")
    global_summary = payload.get("globalSummary")
    if isinstance(global_summary, dict):
        for key in [
            "kernelPrimaryFallbackRate",
            "answerQualityFailRate",
            "officialBoundaryViolation",
            "candidateBoundaryViolation",
            "p95LatencyMs",
            "rolloutNotStarted",
        ]:
            lines.append(f"- {key}: `{global_summary.get(key)}`")
    lines.append("")
    lines.append("## Decision")
    lines.append(f"- decision: `{payload.get('decision')}`")
    return "\n".join(lines)


def main() -> int:
    script_path = Path(__file__).resolve()
    backend_root = script_path.parents[1]
    output_dir = backend_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    default_data_dir = Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR")
        or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench")
    )
    db_path = default_data_dir / "app.db"

    stage_rows: list[dict[str, object]] = []
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            stage_rows = _collect_rollout_rows(conn)
        except sqlite3.Error:
            stage_rows = []
        finally:
            conn.close()

    global_summary = _global_summary(stage_rows)
    decision = _decide(global_summary, stage_rows)

    payload = {
        "generatedAt": _now_iso(),
        "stageSummary": stage_rows,
        "globalSummary": global_summary,
        "decision": decision,
    }

    json_path = output_dir / "P2.6-kernel-primary-rollout-report.json"
    md_path = output_dir / "P2.6-kernel-primary-rollout-report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps({"reportJson": str(json_path), "reportMarkdown": str(md_path), "decision": decision}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
