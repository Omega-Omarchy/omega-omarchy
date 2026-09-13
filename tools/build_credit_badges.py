"""Bake original closing-credit guild parodies with the pinned credits font.

Run .venv/bin/python tools/build_credit_badges.py [--check]. All geometry uses
the game's 320 x 132 logical row. Supersampling happens offline; the game only
loads one opaque PNG for its current detail tier. See docs/credits.md for the
official design references. No third-party logo artwork is incorporated.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/ui/credits"
SIZE = (320, 132)
SUPERSAMPLE = 12


class Artwork:
    def __init__(self):
        self.image = Image.new("RGB", tuple(n * SUPERSAMPLE for n in SIZE), "black")
        self.draw = ImageDraw.Draw(self.image)

    @staticmethod
    def point(x, y):
        return round(x * SUPERSAMPLE), round(y * SUPERSAMPLE)

    @staticmethod
    @lru_cache(maxsize=None)
    def font(size):
        return ImageFont.truetype(str(ASSETS / "credits-sans.otf"), round(size * SUPERSAMPLE))

    def line(self, points, width=0.7, fill="white"):
        self.draw.line([self.point(*p) for p in points], fill=fill,
                       width=round(width * SUPERSAMPLE), joint="curve")

    def polygon(self, points, *, fill="black", width=0.7):
        self.draw.polygon([self.point(*p) for p in points], fill=fill)
        if width:
            self.line([*points, points[0]], width)

    def ellipse(self, x, y, rx, ry=None, *, width=0.7, fill=None):
        ry = rx if ry is None else ry
        self.draw.ellipse([self.point(x - rx, y - ry), self.point(x + rx, y + ry)],
                          fill=fill, outline="white" if width else None,
                          width=round(width * SUPERSAMPLE))

    def text(self, text, x, y, size, *, tracking=0, weight=0):
        font = self.font(size)
        total = sum(font.getlength(c) for c in text) + tracking * SUPERSAMPLE * (len(text) - 1)
        cursor = x * SUPERSAMPLE - total / 2
        baseline = round(y * SUPERSAMPLE) - font.getbbox("H", anchor="ls")[1]
        for c in text:
            self.draw.text((round(cursor), baseline), c, font=font,
                           anchor="ls", fill="white", stroke_width=round(weight * SUPERSAMPLE))
            cursor += font.getlength(c) + tracking * SUPERSAMPLE

    def star(self, x, y, radius, *, points=5):
        self.polygon([(x + math.cos(a * math.pi / points - math.pi / 2) * (radius if a % 2 == 0 else radius * .43),
                       y + math.sin(a * math.pi / points - math.pi / 2) * (radius if a % 2 == 0 else radius * .43))
                      for a in range(points * 2)], fill="white", width=0)

    def curve(self, points, width=0.7):
        """One cubic Bezier, sampled only during the offline bake."""
        self.line([tuple((1-t)**3 * points[0][axis] + 3*(1-t)**2*t * points[1][axis]
                         + 3*(1-t)*t*t * points[2][axis] + t**3 * points[3][axis]
                         for axis in (0, 1)) for t in (i / 80 for i in range(81))], width)


def terminal_crest(a):
    cx, cy = 83, 26
    # Six flared craft spokes, each with a letter, surround a terminal medallion.
    # Their clipped shoulders and double outlines evoke a die-struck union bug.
    for i, letter in enumerate("IATSET"):
        angle = i * math.tau / 6 - math.pi / 2

        def spoke(radial, tangent):
            return (cx + math.cos(angle) * radial - math.sin(angle) * tangent,
                    cy + math.sin(angle) * radial + math.cos(angle) * tangent)

        a.polygon([spoke(r, t) for r, t in ((8, -3.1), (19, -7.5), (24, -6), (24, 6), (19, 7.5), (8, 3.1))], width=1)
        a.line([spoke(r, t) for r, t in ((11, -2), (20, -5.8), (22.2, -5))], width=.35)
        tx, ty = spoke(17.8, 0)
        a.text(letter, tx, ty - 3, 6.8, weight=.08)
    a.ellipse(cx, cy, 9.2, fill="black", width=1)
    a.ellipse(cx, cy, 7.4, width=.4)
    a.line([(cx - 3.8, cy - 2.9), (cx - .5, cy), (cx - 3.8, cy + 2.9)], width=1.2)
    a.line([(cx + .9, cy + 2.9), (cx + 4.3, cy + 2.9)], width=1.2)
    a.star(48, 27, 2)
    a.star(118, 27, 2)
    a.text("I.A.T.S.E.T.", cx, 52, 7.8, tracking=.45, weight=.08)
    a.text("TERMINAL SET EMPLOYEES", cx, 62, 6, tracking=.1)


def performers_emblem(a):
    # A poised agent reaches for the Super key, framed by a rising orbital arc.
    a.curve([(207, 43), (193, 19), (217, -1), (251, 8)], width=1.05)
    a.curve([(209, 42), (196, 20), (223, 3), (246, 7)], width=.35)
    a.polygon([(223, 21), (230, 21), (233, 32), (240, 46), (235, 46),
               (227, 35), (221, 47), (216, 47), (222, 31)], fill="white", width=0)
    a.ellipse(226, 15.3, 3.5, width=0, fill="white")
    a.polygon([(229, 22), (237, 15), (241, 6), (244, 7), (241, 19), (232, 28)], fill="white", width=0)
    a.polygon([(224, 22), (215, 30), (205, 29), (205, 32), (217, 34), (227, 27)], fill="white", width=0)
    a.line([(227, 26), (230, 32)], width=.7, fill="black")
    a.polygon([(240, 1), (247, 1), (247, 6), (240, 6)], width=.6)
    a.line([(242, 2.3), (243.2, 3.5), (242, 4.7)], width=.55)
    a.line([(244.4, 4.7), (245.8, 4.7)], width=.55)
    a.text("SAG / APT-RA", 237, 52, 8.9, tracking=.12, weight=.12)
    a.text("SCREEN AGENTS GUILD", 237, 62, 6, tracking=.2)


def dolly_stereo(a):
    # Paired director's chairs replace a sound-system monogram. A small dolly
    # carriage joins them; the surrounding lockup borrows cinema audio typography.
    a.polygon([(28, 83), (69, 83), (69, 111), (28, 111)], width=1)
    for x in (33, 52):
        a.polygon([(x, 88), (x + 11, 88), (x + 11, 94), (x, 94)], fill="white", width=0)
        a.line([(x - 1, 97), (x + 12, 97)], width=1.9)
        a.line([(x + 1, 94), (x + 1, 99), (x + 10, 106)], width=1.2)
        a.line([(x + 10, 94), (x + 10, 99), (x + 1, 106)], width=1.2)
    a.line([(33, 107), (63, 107)], width=1)
    for x in (37, 60):
        a.ellipse(x, 109, 1, width=0, fill="white")
    a.text("DOLLY", 103, 83, 13, tracking=.15, weight=.15)
    a.text("STEREO", 103, 99, 8.3, tracking=1.4)
    a.text("TWO CHANNELS. ONE CHAIR.", 83, 119, 6, tracking=.05)


def agents_association(a):
    cx, cy = 237, 93
    # An orbiting globe with a circuit iris and laurel-like apertures. The
    # broken meridians terminate in nodes instead of enclosing a film reel.
    a.ellipse(cx, cy, 32, 13, width=1)
    a.ellipse(cx, cy, 23, 13, width=.6)
    a.ellipse(cx, cy, 32, 5, width=.6)
    a.line([(cx - 32, cy), (cx + 32, cy)], width=.6)
    a.ellipse(cx, cy, 12, fill="black", width=1.1)
    a.ellipse(cx, cy, 9.9, width=.45)
    for i in range(6):
        angle = i * math.tau / 6
        x, y = cx + math.cos(angle) * 6.8, cy + math.sin(angle) * 6.8
        a.ellipse(x, y, 1.5, width=0, fill="white")
        a.line([(cx + math.cos(angle) * 3, cy + math.sin(angle) * 3), (x, y)], width=.6)
    a.ellipse(cx, cy, 2.9, fill="black", width=.75)
    a.star(cx, cy, 1.7, points=4)
    a.text("M.P.A.A.A.", cx, 110, 8, tracking=.65, weight=.1)
    a.text("AUTONOMOUS AGENTS ASSOCIATION", cx, 121, 6, tracking=.05)


def render_badges():
    artwork = Artwork()
    terminal_crest(artwork)
    performers_emblem(artwork)
    dolly_stereo(artwork)
    agents_association(artwork)
    return {scale: artwork.image.resize(tuple(n * scale for n in SIZE), Image.Resampling.LANCZOS)
            for scale in (1, 2, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed PNG pixels without writing")
    args = parser.parse_args()
    for scale, image in render_badges().items():
        target = ASSETS / f"guild-badges-{scale}x.png"
        if args.check:
            with Image.open(target) as existing:
                if existing.mode != image.mode or existing.size != image.size or existing.tobytes() != image.tobytes():
                    raise SystemExit(f"Stale credit badge artwork: {target}")
        else:
            image.save(target, optimize=True)
        print(f"{'Verified' if args.check else 'Wrote'} {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
