#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
import runpy


def main() -> int:
    script_path = Path(__file__).resolve().parent / "smoke_workspace_chat_generation.py"
    argv = [str(script_path), "--mode", "async", *sys.argv[1:]]
    old_argv = sys.argv
    try:
        sys.argv = argv
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            return code
    finally:
        sys.argv = old_argv
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
