#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_RESOURCES = PROJECT_ROOT / "build-resources"
ICONSET_DIR = BUILD_RESOURCES / "icon.iconset"
ICON_PATH = BUILD_RESOURCES / "icon.icns"
WINDOWS_ICON_PATH = BUILD_RESOURCES / "icon.ico"
SOURCE_ICON_PATH = BUILD_RESOURCES / "app-logo-ai.png"
BASE_SIZE = 1024


def build_base_icon() -> Image.Image:
    if not SOURCE_ICON_PATH.exists():
        raise FileNotFoundError(f"missing source icon: {SOURCE_ICON_PATH}")
    image = Image.open(SOURCE_ICON_PATH).convert("RGBA")
    image.thumbnail((BASE_SIZE, BASE_SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (BASE_SIZE, BASE_SIZE), (255, 255, 255, 0))
    x = (BASE_SIZE - image.width) // 2
    y = (BASE_SIZE - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas


def write_iconset(image: Image.Image) -> None:
    if ICONSET_DIR.exists():
        shutil.rmtree(ICONSET_DIR)
    ICONSET_DIR.mkdir(parents=True, exist_ok=True)

    variants = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    for file_name, size in variants:
        resized = image.resize((size, size), Image.LANCZOS)
        resized.save(ICONSET_DIR / file_name)


def build_icns() -> None:
    subprocess.run(
        ["/usr/bin/iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICON_PATH)],
        check=True,
    )


def build_windows_ico(image: Image.Image) -> None:
    image.save(
        WINDOWS_ICON_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


def main() -> None:
    BUILD_RESOURCES.mkdir(parents=True, exist_ok=True)
    base_icon = build_base_icon()
    write_iconset(base_icon)
    build_icns()
    build_windows_ico(base_icon)
    print(f"generated {ICON_PATH} and {WINDOWS_ICON_PATH}")


if __name__ == "__main__":
    main()
