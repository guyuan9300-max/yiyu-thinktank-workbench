from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.database_guard import open_database_with_migration_guard
from app.services.knowledge_v2 import backfill_workspace_import


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill documents from an existing client_workspace directory into imports/documents/knowledge tables.")
    parser.add_argument("--db", required=True, help="Absolute path to app.db")
    parser.add_argument("--data-dir", required=True, help="Absolute path to app data dir")
    parser.add_argument("--client-id", required=True, help="Client id to backfill")
    parser.add_argument("--source-root", help="Optional absolute path to scan instead of data-dir/client_workspace/{client-id}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db, _ = open_database_with_migration_guard(
        Path(args.db),
        data_dir=Path(args.data_dir),
    )
    summary = backfill_workspace_import(
        db,
        data_dir=Path(args.data_dir),
        client_id=args.client_id,
        source_root=Path(args.source_root) if args.source_root else None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
