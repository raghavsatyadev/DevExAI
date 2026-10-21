"""Draw the DevExAI logo: SVG sources and transparent PNGs in assets/logo/.

The mark is the dashboard's M3 Expressive cookie shape in the primary colour, holding a terminal prompt
(the developer tool) and a spark (the idea and the AI). The wordmark's letters are converted to outlines
so the SVG looks the same everywhere without the font installed.

    uv run --with fonttools python tools/make_logo.py

PNGs are rendered by headless Chrome or Edge, so one of them must be installed.
"""

from __future__ import annotations

import math
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "logo"
FONT = Path(r"C:\Windows\Fonts\arialbd.ttf")
BROWSERS = (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

PRIMARY, SPARK = "#4355b9", "#ffd7f1"  # web/theme.py: --primary, --tertiary-container
INK, INK_DARK, PRIMARY_DARK = "#1b1b21", "#e4e1e9", "#bac3ff"


def cookie(cx: float, cy: float, size: float, lobes: int = 9, depth: float = 0.07, steps: int = 360) -> str:
    """The same cookie outline as the dashboard's header mark (web/theme.py), as an SVG path."""
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps - math.pi / 2
        r = size / 2 * (1 - depth + depth * math.cos(lobes * (t + math.pi / 2)))
        pts.append(f"{cx + r * math.cos(t):.2f},{cy + r * math.sin(t):.2f}")
    return "M" + " L".join(pts) + " Z"


def sparkle(cx: float, cy: float, r: float, waist: float = 0.16) -> str:
    """A four-point star with concave sides."""
    w = r * waist
    return (f"M{cx},{cy - r} C{cx + w},{cy - w} {cx + w},{cy - w} {cx + r},{cy} "
            f"C{cx + w},{cy + w} {cx + w},{cy + w} {cx},{cy + r} "
            f"C{cx - w},{cy + w} {cx - w},{cy + w} {cx - r},{cy} "
            f"C{cx - w},{cy - w} {cx - w},{cy - w} {cx},{cy - r} Z")


def mark(x: float = 0, y: float = 0, s: float = 1024) -> str:
    """The icon in a box of side s at (x, y). Drawn on a 1024 grid and scaled."""
    k = s / 1024
    return (f'<g transform="translate({x} {y}) scale({k:.6f})">'
            f'<path d="{cookie(512, 512, 1000)}" fill="{PRIMARY}"/>'
            f'<path d="M290 368 L436 512 L290 656" fill="none" stroke="#fff" stroke-width="92" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M514 656 H668" stroke="#fff" stroke-width="92" stroke-linecap="round"/>'
            f'<path d="{sparkle(684, 360, 150)}" fill="{SPARK}"/>'
            f'<path d="{sparkle(790, 560, 58)}" fill="{SPARK}"/></g>')


def text_paths(text: str, x: float, baseline: float, size: float) -> tuple[list[str], float]:
    """SVG paths per letter, outlined from the font and placed on the baseline, and where the text ends."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    font = TTFont(FONT)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    out = []
    for ch in text:
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        out.append(pen.getCommands())
        x += glyphs[name].width * scale
    return out, x


def svg(width: int, height: int, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" role="img" aria-label="DevExAI">\n{body}\n</svg>\n')


def wordmark(dark: bool) -> tuple[str, int, int]:
    h, size = 256, 150
    letters, end = text_paths("DevExAI", 300, 182, size)
    width = math.ceil(end + 24)
    ink, accent = (INK_DARK, PRIMARY_DARK) if dark else (INK, PRIMARY)
    body = mark(16, 16, 224) + "".join(
        f'<path d="{d}" fill="{accent if i >= 5 else ink}"/>' for i, d in enumerate(letters))
    return svg(width, h, body), width, h


def render_png(svg_path: Path, png_path: Path, width: int, height: int) -> None:
    browser = next((b for b in BROWSERS if Path(b).exists()), None) or shutil.which("chrome")
    if not browser:
        sys.exit("No Chrome or Edge found to render PNGs.")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(f'<html><body style="margin:0;background:transparent">'
                        f'<img src="{svg_path.as_uri()}" width="{width}" height="{height}" style="display:block">'
                        f'</body></html>', encoding="utf-8")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                        "--default-background-color=00000000", f"--window-size={width},{height}",
                        f"--user-data-dir={Path(tmp) / 'profile'}", f"--screenshot={png_path}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)


def write_ico(svg_path: Path, ico_path: Path, sizes: tuple[int, ...] = (16, 24, 32, 48, 64, 256)) -> None:
    """A Windows icon (exe, tray, Start menu) whose entries are PNGs, which Windows reads since Vista."""
    with tempfile.TemporaryDirectory() as tmp:
        images = []
        for px in sizes:
            png = Path(tmp) / f"{px}.png"
            render_png(svg_path, png, px, px)
            images.append((px, png.read_bytes()))
    head = struct.pack("<HHH", 0, 1, len(images))
    offset, entries = len(head) + 16 * len(images), b""
    for px, data in images:
        side = 0 if px >= 256 else px  # 0 means 256 in an icon directory
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    ico_path.write_bytes(head + entries + b"".join(data for _, data in images))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = OUT / "devexai-logo.svg"
    icon.write_text(svg(1024, 1024, mark()), encoding="utf-8")
    for px in (1024, 512, 256):
        render_png(icon, OUT / f"devexai-logo-{px}.png", px, px)
    write_ico(icon, OUT / "devexai.ico")
    for dark in (False, True):
        name = "devexai-wordmark-dark" if dark else "devexai-wordmark"
        text, w, h = wordmark(dark)
        path = OUT / f"{name}.svg"
        path.write_text(text, encoding="utf-8")
        render_png(path, OUT / f"{name}.png", w * 2, h * 2)
    for p in sorted(OUT.iterdir()):
        print(p.relative_to(ROOT), p.stat().st_size)


if __name__ == "__main__":
    main()
