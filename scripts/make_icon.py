"""Regenerate ``src/twitchbar/assets/twitchbar.icns``: a purple tile, a speech bubble, an eye.

Run with ``uv run python scripts/make_icon.py`` on macOS (needs Pillow from the dev group and the
system ``iconutil``). The output is committed so users never need Pillow.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

PURPLE = (145, 70, 255, 255)
INK = (40, 20, 80, 255)
SIZES = {
    16: ["icon_16x16.png"],
    32: ["icon_16x16@2x.png", "icon_32x32.png"],
    64: ["icon_32x32@2x.png"],
    128: ["icon_128x128.png"],
    256: ["icon_128x128@2x.png", "icon_256x256.png"],
    512: ["icon_256x256@2x.png", "icon_512x512.png"],
    1024: ["icon_512x512@2x.png"],
}


def draw(size: int) -> Image.Image:
    """The icon at one pixel size."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(image)
    margin = size * 0.06
    canvas.rounded_rectangle(
        (margin, margin, size - margin, size - margin), radius=size * 0.22, fill=PURPLE
    )
    left, top, right, bottom = size * 0.20, size * 0.24, size * 0.80, size * 0.66
    canvas.rounded_rectangle((left, top, right, bottom), radius=size * 0.12, fill="white")
    canvas.polygon(
        [(size * 0.32, bottom - 1), (size * 0.46, bottom - 1), (size * 0.30, size * 0.80)],
        fill="white",
    )
    cx, cy, ew, eh = size * 0.50, size * 0.45, size * 0.20, size * 0.11
    canvas.ellipse((cx - ew, cy - eh, cx + ew, cy + eh), fill=PURPLE)
    canvas.ellipse((cx - eh * 0.9, cy - eh * 0.9, cx + eh * 0.9, cy + eh * 0.9), fill="white")
    canvas.ellipse((cx - eh * 0.45, cy - eh * 0.45, cx + eh * 0.45, cy + eh * 0.45), fill=INK)
    return image


def main() -> None:
    """Render every size into an iconset and pack it with iconutil."""
    target = Path(__file__).resolve().parents[1] / "src" / "twitchbar" / "assets" / "twitchbar.icns"
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "twitchbar.iconset"
        iconset.mkdir()
        for px, names in SIZES.items():
            image = draw(px)
            for name in names:
                image.save(iconset / name)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], check=True)
    print(f"wrote {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
