from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.platform_dna import extract_platform_dna_text, supported_platform_dna_extensions


def main() -> int:
    if len(sys.argv) != 2:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "usage: extract_platform_dna_text.py <path>",
                    "supportedExtensions": list(supported_platform_dna_extensions()),
                },
                ensure_ascii=False,
            )
        )
        return 1

    target_path = Path(sys.argv[1]).expanduser().resolve()
    if not target_path.exists() or not target_path.is_file():
        print(json.dumps({"success": False, "error": "file_not_found"}, ensure_ascii=False))
        return 1

    try:
        text = extract_platform_dna_text(target_path)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "supportedExtensions": list(supported_platform_dna_extensions()),
                },
                ensure_ascii=False,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "success": True,
                "path": str(target_path),
                "text": text,
                "fileName": target_path.name,
                "extension": target_path.suffix.lower(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
