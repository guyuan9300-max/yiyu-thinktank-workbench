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


def _latest_snapshot(conn: sqlite3.Connection) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT id, window_start, window_end, label_counts_json,
               useful_examples_json, noise_examples_json, needs_review_examples_json,
               recommended_rules_json, created_at
        FROM evidence_quality_feedback_snapshots
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return None
    label_counts = _from_json(row[3], {})
    return {
        "id": str(row[0]),
        "windowStart": str(row[1]),
        "windowEnd": str(row[2]),
        "labelCounts": {str(k): int(v or 0) for k, v in (label_counts.items() if isinstance(label_counts, dict) else [])},
        "usefulExamples": [item for item in _from_json(row[4], []) if isinstance(item, dict)],
        "noiseExamples": [item for item in _from_json(row[5], []) if isinstance(item, dict)],
        "needsReviewExamples": [item for item in _from_json(row[6], []) if isinstance(item, dict)],
        "recommendedRules": [str(item) for item in _from_json(row[7], []) if str(item).strip()],
        "createdAt": str(row[8]),
    }


def _decision(snapshot: dict[str, object] | None) -> str:
    if snapshot is None:
        return "need_more_samples"
    label_counts = snapshot.get("labelCounts") if isinstance(snapshot.get("labelCounts"), dict) else {}
    noise_count = int((label_counts or {}).get("noise") or 0)
    useful_count = int((label_counts or {}).get("useful") or 0)
    review_count = int((label_counts or {}).get("needs_review") or 0)
    if review_count > useful_count:
        return "need_more_samples"
    if noise_count > useful_count:
        return "propose_future_adjustment"
    return "keep_current_weights"


def _render_markdown(snapshot: dict[str, object] | None, decision: str) -> str:
    lines: list[str] = []
    lines.append("# Evidence Quality Snapshot Report")
    lines.append("")
    lines.append(f"- generatedAt: `{_now_iso()}`")
    lines.append("")
    if snapshot is None:
        lines.append("## 1. Label Counts")
        lines.append("- 无快照数据")
        lines.append("")
        lines.append("## 6. Decision")
        lines.append(f"- {decision}")
        return "\n".join(lines)

    label_counts = snapshot.get("labelCounts") if isinstance(snapshot.get("labelCounts"), dict) else {}
    lines.append("## 1. Label Counts")
    lines.append(f"- useful: {int(label_counts.get('useful') or 0)}")
    lines.append(f"- noise: {int(label_counts.get('noise') or 0)}")
    lines.append(f"- needs_review: {int(label_counts.get('needs_review') or 0)}")
    lines.append(f"- unlabeled: {int(label_counts.get('unlabeled') or 0)}")
    lines.append("")

    def _render_examples(title: str, key: str) -> None:
        lines.append(title)
        examples = snapshot.get(key) if isinstance(snapshot.get(key), list) else []
        if not examples:
            lines.append("- (none)")
        else:
            for item in examples[:5]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"- {item.get('annotationId')} · {item.get('sourceType')}:{item.get('sourceId')} · {item.get('humanNote') or ''}"
                )
        lines.append("")

    _render_examples("## 2. Useful Examples", "usefulExamples")
    _render_examples("## 3. Noise Examples", "noiseExamples")
    _render_examples("## 4. Needs Review Examples", "needsReviewExamples")

    lines.append("## 5. Recommended Rules")
    rules = snapshot.get("recommendedRules") if isinstance(snapshot.get("recommendedRules"), list) else []
    if not rules:
        lines.append("- (none)")
    else:
        for rule in rules:
            lines.append(f"- {rule}")
    lines.append("")
    lines.append("## 6. Decision")
    lines.append(f"- {decision}")
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

    snapshot: dict[str, object] | None = None
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            snapshot = _latest_snapshot(conn)
        except sqlite3.Error:
            snapshot = None
        finally:
            conn.close()

    decision = _decision(snapshot)
    payload = {
        "generatedAt": _now_iso(),
        "snapshot": snapshot,
        "decision": decision,
        "snapshotExists": snapshot is not None,
    }

    json_path = output_dir / "P2.6-evidence-quality-snapshot-report.json"
    md_path = output_dir / "P2.6-evidence-quality-snapshot-report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(snapshot, decision), encoding="utf-8")
    print(json.dumps({"reportJson": str(json_path), "reportMarkdown": str(md_path), "snapshotExists": bool(snapshot)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
