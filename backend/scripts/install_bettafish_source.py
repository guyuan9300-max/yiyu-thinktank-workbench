from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path


ARCHIVE_URL = "https://github.com/666ghj/BettaFish/archive/refs/heads/main.tar.gz"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_target_dir() -> Path:
    return project_root() / "external" / "BettaFish"


def download_archive(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(ARCHIVE_URL) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def extract_archive(archive_path: Path, destination: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="bettafish-extract-") as temp_dir:
        temp_path = Path(temp_dir)
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(temp_path)

        extracted_root = temp_path / "BettaFish-main"
        if not extracted_root.exists():
            raise RuntimeError("Archive extracted but BettaFish-main was not found")

        if destination.exists() and any(destination.iterdir()):
            backup_dir = destination.parent / f"{destination.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            destination.rename(backup_dir)
            print(f"Backed up existing directory to {backup_dir}")
        elif destination.exists():
            destination.rmdir()

        shutil.move(str(extracted_root), str(destination))


def main() -> int:
    parser = argparse.ArgumentParser(description="Install BettaFish source into external/BettaFish")
    parser.add_argument("--target", type=Path, default=default_target_dir(), help="Target directory for BettaFish source")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bettafish-download-") as temp_dir:
        archive_path = Path(temp_dir) / "bettafish-main.tar.gz"
        print(f"Downloading BettaFish archive from {ARCHIVE_URL}")
        download_archive(archive_path)
        print(f"Downloaded to {archive_path}")
        extract_archive(archive_path, target)

    print(f"BettaFish source installed at {target}")
    print("Next step:")
    print("  1. Create a dedicated venv for BettaFish")
    print("  2. Install only the dependencies needed for your chosen startup path")
    print("  3. Configure YIYU_BETTAFISH_ENABLED / AUTOSTART / START_COMMAND")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - script entrypoint
        print(f"BettaFish install failed: {exc}", file=sys.stderr)
        raise
