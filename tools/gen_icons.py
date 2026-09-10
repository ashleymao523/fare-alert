# -*- coding: utf-8 -*-
"""v0.20 PWA icon generator (reproducible, no design tools needed).

Draws the FareAlert app icon with PIL: sky-blue vertical gradient base +
white paper plane, then exports PNG sizes for PWA/iOS/favicons.
Run from repo root:  python -X utf8 tools/gen_icons.py
Outputs to webui/static/: icon-{512,192,180,32}.png maskable-{512,192}.png
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "webui", "static")

# theme-aligned palette (webui/static/style.css --accent)
TOP = (77, 141, 255)
BOTTOM = (0, 78, 200)
WHITE = (255, 255, 255, 255)
FOLD = (255, 255, 255, 200)
TRAIL = (255, 255, 255, 150)

SS = 4  # supersample factor for smooth edges
BASE = 512


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def _gradient(w, h):
    """Vertical linear gradient TOP->BOTTOM."""
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)],
               fill=(_lerp(TOP[0], BOTTOM[0], t),
                     _lerp(TOP[1], BOTTOM[1], t),
                     _lerp(TOP[2], BOTTOM[2], t)))
    return img


def _plane(d, cx, cy, s):
    """Paper plane + speed trails centered at (cx,cy), s = half-size."""
    # main upper wing (nose points up-right)
    d.polygon([(cx - .92 * s, cy - .10 * s),
               (cx + .92 * s, cy - .80 * s),
               (cx - .04 * s, cy + .06 * s)], fill=WHITE)
    # folded lower wing, slightly translucent to suggest the fold
    d.polygon([(cx + .92 * s, cy - .80 * s),
               (cx - .04 * s, cy + .06 * s),
               (cx + .28 * s, cy + .86 * s)], fill=FOLD)
    # speed trails on the lower-left
    w = max(2, int(s * .10))
    d.line([(cx - .80 * s, cy + .34 * s),
            (cx - .34 * s, cy + .34 * s)], fill=TRAIL, width=w)
    d.line([(cx - .62 * s, cy + .60 * s),
            (cx - .28 * s, cy + .60 * s)], fill=TRAIL, width=w)


def _master(rounded, bleed):
    """Render one 4x master. bleed=True -> full-bleed maskable base,
    content kept inside the 78% safe zone (no rounding)."""
    size = BASE * SS
    img = _gradient(size, size).convert("RGBA")
    if not bleed:  # rounded corners, ~22% radius like iOS icons
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
        img.putalpha(mask)
    d = ImageDraw.Draw(img)
    scale = 0.78 if bleed else 1.0
    _plane(d, size * 0.52, size * 0.52, size * 0.40 * scale)
    return img


def _save(img, name, px):
    img.resize((px, px), Image.LANCZOS).save(os.path.join(OUT, name))
    print("wrote", name, px)


def main():
    os.makedirs(OUT, exist_ok=True)
    any_master = _master(True, False)
    mk_master = _master(False, True)
    for px in (512, 192, 180, 32):
        _save(any_master, "icon-%d.png" % px, px)
    for px in (512, 192):
        _save(mk_master, "maskable-%d.png" % px, px)


if __name__ == "__main__":
    main()
