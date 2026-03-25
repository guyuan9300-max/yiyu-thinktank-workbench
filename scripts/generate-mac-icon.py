#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_RESOURCES = PROJECT_ROOT / "build-resources"
ICONSET_DIR = BUILD_RESOURCES / "icon.iconset"
ICON_PATH = BUILD_RESOURCES / "icon.icns"
BASE_SIZE = 1024


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode MS.ttf",
    ]
    for candidate in candidates:
        font_path = Path(candidate)
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def build_base_icon() -> Image.Image:
    image = Image.new("RGBA", (BASE_SIZE, BASE_SIZE), "#F4F7FF")
    draw = ImageDraw.Draw(image)

    shadow = Image.new("RGBA", (BASE_SIZE, BASE_SIZE), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((132, 132, 892, 892), radius=210, fill=(31, 64, 173, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(36))
    image.alpha_composite(shadow)

    draw.rounded_rectangle((112, 112, 912, 912), radius=210, fill="#5B7BFE")
    draw.rounded_rectangle((170, 170, 854, 854), radius=170, outline=(255, 255, 255, 48), width=6)
    draw.ellipse((744, 178, 848, 282), fill="#F9FBFF")
    draw.rounded_rectangle((214, 724, 358, 772), radius=24, fill=(255, 255, 255, 64))

    font = load_font(420)
    text = "益"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (BASE_SIZE - text_width) / 2 - bbox[0]
    text_y = (BASE_SIZE - text_height) / 2 - bbox[1] - 10
    draw.text((text_x, text_y), text, font=font, fill="#FFFFFF")
    return image


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


def main() -> None:
    BUILD_RESOURCES.mkdir(parents=True, exist_ok=True)
    base_icon = build_base_icon()
    write_iconset(base_icon)
    build_icns()
    print(f"generated {ICON_PATH}")


if __name__ == "__main__":
    main()
