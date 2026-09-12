"""Cinematic cast cards and a white-on-black, music-length credit roll."""

from __future__ import annotations

import math
import pygame

from .credits import FPS, PATRON_FONT_SIZES, ROLL_TARGET_SPEED, cast_card, credit_manifest, roll_offset

WHITE = (255, 255, 255)


class CreditsRenderer:
    def __init__(self, renderer):
        self.r = renderer
        self.fonts = {}
        self.layouts = {}
        self.glyphs = {}
        self.logos = {}
        self.seal_bakes = {}

    def font(self, size, scale):
        key = (size, scale)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.Font(str(self.r.root / "ui/credits/credits-sans.otf"), round(size * scale))
        return self.fonts[key]

    def fallback_font(self, size, scale):
        """A handful of real contributor names use Latin letters the primary
        credits font has no glyph for (e.g. c-with-acute, dotted/dotless I).
        This covers them per-character without changing the look of any
        text the primary font already renders."""
        key = ("fallback", size, scale)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.Font(str(self.r.root / "ui/credits/credits-sans-fallback.ttf"), round(size * scale))
        return self.fonts[key]

    # credits-sans.otf's cmap has no glyph for these five Latin Extended-A/B
    # codepoints used by real contributor names (Roman Frołow, Barış
    # Girişmen, Emir Beganović, ...), verified against the shipped .otf via
    # fontTools' cmap. Detecting coverage at runtime through
    # pygame.font.Font.metrics() matched this ground truth exactly on the
    # native SDL_ttf build (a missing glyph reports an all-zero bounding
    # box there), but the web build rendered these letters blank instead of
    # falling back, which only happens if metrics() disagrees under
    # pygbag's WebAssembly SDL_ttf/FreeType. A fixed, verified set
    # sidesteps that per-platform font-backend inconsistency entirely.
    _PRIMARY_FONT_GAPS = frozenset("ĆİŁŘŞ")

    def _has_glyph(self, ch):
        return ch.isspace() or ch not in self._PRIMARY_FONT_GAPS

    def _char_font(self, ch, size, scale):
        return self.font(size, scale) if self._has_glyph(ch) else self.fallback_font(size, scale)

    def _fully_covered(self, text, size, scale):
        return all(self._has_glyph(ch) for ch in text)

    def _measure_text(self, text, size, scale):
        if self._fully_covered(text, size, scale):
            return self.font(size, scale).size(text)[0]
        return sum(self._char_font(ch, size, scale).size(ch)[0] for ch in text)

    def _render_text(self, text, size, scale, color):
        if self._fully_covered(text, size, scale):
            return self.font(size, scale).render(text, True, color)
        glyphs = [self._char_font(ch, size, scale).render(ch, True, color) for ch in text]
        width = max(1, sum(g.get_width() for g in glyphs))
        height = max((g.get_height() for g in glyphs), default=1)
        combined = pygame.Surface((width, height), pygame.SRCALPHA)
        cursor = 0
        for glyph in glyphs:
            combined.blit(glyph, (cursor, 0))
            cursor += glyph.get_width()
        return combined

    def wrap(self, text, width, size=8):
        scale = 4
        lines, line = [], ""
        for word in text.split():
            candidate = (line + " " + word).strip()
            if line and self._measure_text(candidate, size, scale) > width * scale:
                lines.append(line)
                line = ""
            # Preserve every character, even in a very long username.
            for char in word:
                if self._measure_text(line + char, size, scale) > width * scale:
                    lines.append(line)
                    line = ""
                line += char
            line += " "
        if line.strip(): lines.append(line.strip())
        return lines or [""]

    def text(self, surf, text, x, y, size=8, align="center", color=WHITE):
        scale = self.r._vs
        key = (text, size, scale, color)
        if key not in self.glyphs:
            self.glyphs[key] = self._render_text(text, size, scale, color)
        image = self.glyphs[key]
        rect = image.get_rect()
        rect.top = round(y * scale)
        setattr(rect, {"left": "left", "right": "right", "center": "centerx"}[align], round(x * scale))
        surf.blit(image, rect)

    def block(self, surf, text, x, y, width, size=8, align="center", color=WHITE):
        for i, line in enumerate(self.wrap(text, width, size)):
            self.text(surf, line, x, y + i * (size + 3), size, align, color)

    def wordmark(self, surf, y, *, width=196):
        scale = self.r._vs
        key = (scale, width)
        if key not in self.logos:
            base = self.r._load("ui/omarchy-wordmark.png").copy()
            # Preserve the accepted title-screen silhouette and transparency.
            base.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
            mark_h = round(base.get_height() / base.get_width() * width * scale)
            mark = self.r._fit(base, (width * scale, mark_h))
            omega = self.font(8, scale).render("OMEGA", True, WHITE)
            gap = max(2, scale)
            line_h = max(1, scale)
            omega_top = 0
            line_top = omega.get_height() + gap
            mark_top = line_top + line_h + gap
            plate = pygame.Surface((mark.get_width(), mark_top + mark.get_height()), pygame.SRCALPHA)
            plate.blit(omega, (max(0, 4 * scale), omega_top))
            pygame.draw.rect(
                plate,
                WHITE,
                (max(0, 4 * scale), line_top, omega.get_width(), line_h),
            )
            plate.blit(mark, (0, mark_top))
            self.logos[key] = (plate, mark_top)
        image, mark_top = self.logos[key]
        left = (320 - width) / 2
        surf.blit(image, (round(left * scale), round(y * scale) - mark_top))

    def layout(self, character):
        if character in self.layouts:
            return self.layouts[character]
        manifest = credit_manifest()
        rows = manifest["rows"]
        # Measure fixed credits once. Only the extended patron group is
        # rewrapped as its font shrinks, using the pinned font at 4x scale.
        fixed = [None if row.get("compact") and row["kind"] == "names" else self.measure_row(row, character) for row in rows]
        budget = float(manifest["music"]["duration"]) * ROLL_TARGET_SPEED - 105.0
        for size in PATRON_FONT_SIZES:
            measured = [cached if cached is not None else self.measure_row(row, character, name_size=size) for row, cached in zip(rows, fixed)]
            if sum(height for _, height in measured) <= budget:
                break
        # Round each row's stored position once, here, rather than at scroll
        # time. Patron rows get fractional heights once font compaction
        # kicks in, so unrounded cumulative Y values carry different
        # fractional parts row to row; rounding independently every frame
        # (as the continuous scroll offset shifts) then made adjacent rows'
        # on-screen gap wobble by +/-1px instead of staying fixed. Rounding
        # once here makes every row's spacing a fixed integer for the whole
        # scroll, immune to whatever the offset's fractional phase is.
        entries, y = [], 0.0
        for row, height in measured:
            entries.append((round(y), height, row))
            y += height
        self.layouts[character] = (entries, y)
        return entries, y

    @staticmethod
    def _patron_columns(name_size):
        """More columns as the compacted font shrinks, real estate permitting."""
        if name_size <= 6.75:
            return 4
        if name_size <= 7.25:
            return 3
        return 2

    def measure_row(self, source, character, *, name_size=8):
        row = dict(source)
        kind = row["kind"]
        if kind == "pair":
            left = self.wrap(row["role"], 139, 7)
            right = self.wrap(row["name"].replace("{CHARACTER}", character.upper()), 139, 8)
            row["columns"] = (left, right)
            height = max(row["height"], max(len(left), len(right)) * 11 + 2)
        elif kind == "names":
            ratio = name_size / 8
            row["fontSize"], row["lineHeight"] = name_size, 11 * ratio
            cols = self._patron_columns(name_size)
            col_width = 284 / cols
            names = row["names"]
            grid_rows = [names[i:i + cols] for i in range(0, len(names), cols)]
            wrapped = [[self.wrap(name, col_width - 4, name_size) for name in grid_row] for grid_row in grid_rows]
            row["columnCount"] = cols
            row["grid"] = wrapped
            row["gridLineCounts"] = [max((len(w) for w in grid_row), default=1) for grid_row in wrapped]
            total_lines = sum(row["gridLineCounts"]) or 1
            height = max(row["height"] * ratio, total_lines * row["lineHeight"] + 2 * ratio)
        elif kind in {"heading", "text"}:
            row["lines"] = self.wrap(row["text"], 284, 11 if kind == "heading" else 8)
            if kind == "heading" and row.get("subtitle"):
                row["subtitleLines"] = self.wrap(str(row["subtitle"]), 284, 7)
                height = max(row["height"], 12 + len(row["lines"]) * 16 + len(row["subtitleLines"]) * 10 + 12)
            else:
                height = max(row["height"], len(row["lines"]) * (16 if kind == "heading" else 11) + 12)
        else:
            height = row["height"]
        return row, height

    def draw_row(self, surf, row, y):
        kind = row["kind"]
        if kind == "logo":
            self.wordmark(surf, y + 12)
        elif kind == "pair":
            for i, line in enumerate(row["columns"][0]): self.text(surf, line, 152, y + i * 11, 7, "right")
            for i, line in enumerate(row["columns"][1]): self.text(surf, line, 168, y + i * 11, 8, "left")
        elif kind == "names":
            cols = row["columnCount"]
            col_width = 284 / cols
            cursor_y = y
            for grid_row, line_count in zip(row["grid"], row["gridLineCounts"]):
                for col, lines in enumerate(grid_row):
                    x = 18 + col_width * (col + 0.5)
                    for i, line in enumerate(lines):
                        self.text(surf, line, x, cursor_y + i * row["lineHeight"], row["fontSize"])
                cursor_y += line_count * row["lineHeight"]
        elif kind in {"heading", "text"}:
            size, gap, inset = (11, 16, 12) if kind == "heading" else (8, 11, 0)
            for i, line in enumerate(row["lines"]): self.text(surf, line, 160, y + inset + i * gap, size)
            if kind == "heading" and row.get("subtitleLines"):
                sub_y = y + inset + len(row["lines"]) * gap
                for i, sub_line in enumerate(row["subtitleLines"]): self.text(surf, sub_line, 160, sub_y + i * 10, 7)
        elif kind == "seals":
            self.seals(surf, y)

    # Original badges, deliberately fictional film-industry parodies.
    _SEAL_BADGES = (
        ("I.A.T.S.E.T.", "Terminal Set Employees"),
        ("SAG / APT-RA", "Screen Agents Guild"),
        ("DOLLY STEREO", "Two channels. One chair."),
        ("M.P.A.A.A.", "Autonomous Agents Association"),
    )

    def seals(self, surf, y):
        scale = self.r._vs
        baked = self.seal_bakes.get(scale)
        if baked is None:
            baked = self._bake_seals(scale)
            self.seal_bakes[scale] = baked
        surf.blit(baked, (0, round(y * scale)))

    def _bake_seals(self, scale):
        """Render the seal badges once, supersampled, and cache the result.

        This row scrolls past every playthrough, so redrawing hand-vectored
        shapes every frame was both wasted work and visibly jagged. Baking
        at 3x and downscaling gives anti-aliased edges for free and leaves
        nothing but a plain blit while the row is on screen.
        """
        super_scale = max(1, scale) * 3
        width, height = 320 * scale, 132 * scale
        shapes = pygame.Surface((320 * super_scale, 132 * super_scale), pygame.SRCALPHA)

        def lp(x, y_):
            return (round(x * super_scale), round(y_ * super_scale))

        def lr(x, y_, w, h):
            return pygame.Rect(round(x * super_scale), round(y_ * super_scale), round(w * super_scale), round(h * super_scale))

        line_w = max(1, super_scale)
        for i, (acronym, caption) in enumerate(self._SEAL_BADGES):
            x, top = 85 + (i % 2) * 150, (i // 2) * 62
            if i in {0, 3}:
                points = [(x + math.cos(a * math.pi / 12) * (23 if a % 2 else 27), top + 21 + math.sin(a * math.pi / 12) * (18 if a % 2 else 22)) for a in range(24)]
                poly = [lp(*p) for p in points]
                pygame.draw.polygon(shapes, (255, 255, 255, 55), poly)
                pygame.draw.polygon(shapes, WHITE, poly, line_w)
            else:
                rect = lr(x - 56, top + 4, 112, 34)
                pygame.draw.rect(shapes, (255, 255, 255, 45), rect)
                pygame.draw.rect(shapes, WHITE, rect, line_w)
                if i == 2:
                    for n in range(6):
                        pygame.draw.line(shapes, WHITE, lp(x - 48 + n * 3, top + 12), lp(x - 48 + n * 3, top + 29), line_w)

        baked = pygame.transform.smoothscale(shapes, (max(1, width), max(1, height)))
        for i, (acronym, caption) in enumerate(self._SEAL_BADGES):
            x, top = 85 + (i % 2) * 150, (i // 2) * 62
            self.text(baked, acronym, x + (8 if i == 2 else 0), top + 16, 7)
            self.text(baked, caption, x, top + 44, 6)
        return baked

    def sprite(self, surf, image, x, feet_y, height, *, width=280, alpha=255):
        bounds = image.get_bounding_rect(min_alpha=8)
        if not bounds.width or not bounds.height: return
        image = image.subsurface(bounds)
        factor = min(height / bounds.height, width / bounds.width) * self.r._vs
        image = self.r._fit(image, (max(1, round(bounds.width * factor)), max(1, round(bounds.height * factor))))
        if alpha != 255:
            image = image.copy()
            image.set_alpha(alpha)
        surf.blit(image, image.get_rect(midbottom=self.r._lp(x, feet_y)))

    def draw(self, surf, sim):
        surf.fill((0, 0, 0))
        seconds = max(0.0, float(sim.credits_ticks) / FPS)
        reduced = bool(sim.settings.get("reducedMotion") or sim.accessibility.reduced_motion)
        try:
            if sim.scene == "ending":
                self.title(surf, sim, seconds, reduced)
                self.layout(sim.character_name)
            else:
                self._draw_roll(surf, sim, seconds, reduced)
        except pygame.error:
            return
        # Instructions disappear once the sequence has had time to establish.
        if seconds < 3:
            action = sim.prompt_binding("jump", compact=True)
            try:
                self.text(surf, f"{action} / Esc  {'skip to credits' if sim.scene == 'ending' else 'return'}", 310, 168, 6, "right", (150, 150, 150))
            except pygame.error:
                return

    def _draw_roll(self, surf, sim, seconds, reduced):
        duration = credit_manifest()["music"]["duration"]
        if seconds >= duration:
            return
        entries, height = self.layout(sim.character_name)
        if reduced:
            # Static pages, broken only between complete credit entries.
            pages, page, used = [], [], 0
            for _, size, row in entries:
                if page and used + size > 150:
                    pages.append(page)
                    page, used = [], 0
                page.append((used, row))
                used += size
            if page:
                pages.append(page)
            page = pages[min(len(pages) - 1, int(seconds / duration * len(pages)))]
            for y, row in page:
                self.draw_row(surf, row, y + 12)
            return
        offset = roll_offset(seconds, height)
        for y, size, row in entries:
            top = y - offset
            if top + size >= 0 and top < 180:
                self.draw_row(surf, row, top)

    def title(self, surf, sim, seconds, reduced):
        card, local = cast_card(seconds)
        kind, r = card["kind"], self.r
        t = 2.0 if reduced else local
        tick = round(t * FPS)
        if kind == "title":
            self.text(surf, "A JEREMY DIXON GAME", 160, 29, 8)
            self.wordmark(surf, 69)
            self.text(surf, "The revolution will be customized.", 160, 132, 9)
        elif kind == "player":
            self.sprite(surf, r._character_sprite(sim, "portrait"), 80, 151, 120, width=126, alpha=100)
            pose = "side-idle" if reduced or t > 4 else f"side-walk-{tick // 9 % 4}"
            self.sprite(surf, r._character_sprite(sim, pose), 205 + (0 if reduced else 8 * math.sin(t / 2)), 132, 90, width=95)
            self.text(surf, "STARRING", 209, 19, 8)
            self.block(surf, sim.character_name, 205, 143, 176, 12)
        elif kind == "royalty":
            self.text(surf, "BY ROYAL APPOINTMENT", 160, 20, 10)
            for x, identity, name in [(85, "omarch-king", "The Omarch King"), (235, "omarch-queen", "The Omarch Queen")]:
                pose = "side-idle" if reduced else f"side-walk-{tick // 16 % 4}"
                image = r._load(f"character-packs/{identity}/{r._active_fid(sim)}/{pose}.png")
                self.sprite(surf, image, x, 131, 84, width=94)
                self.text(surf, name, x, 143, 10)
        elif kind == "mobs":
            self.text(surf, "ALSO STARRING", 160, 22, 11)
            self.text(surf, "The department of mandatory resistance", 160, 41, 8)
            for i, mob in enumerate(card["cast"]):
                x = 160 + (i - (len(card["cast"]) - 1) / 2) * 74
                converted = not reduced and t > 4.2
                image = r._fid(sim, f"enemies/{mob['id']}{'-converted' if converted else ''}.png")
                self.sprite(surf, image, x, 116 + (0 if reduced else 2 * math.sin(t * 2 + i)), 47, width=61)
                self.block(surf, mob["name"], x, 133, 70, 8)
        elif kind == "boss":
            suffix = "" if reduced else ("-converted" if t >= 4.9 else "-defeated" if t >= 4 else "-active" if 1.5 < t < 3.8 and tick // 18 % 2 else "")
            self.sprite(surf, r._fid(sim, f"bosses/{card['id']}{suffix}.png"), 85, 143, 112, width=138)
            self.text(surf, "WITH", 230, 34, 8)
            self.block(surf, card["name"], 230, 54, 146, 13)
            self.block(surf, card["subtitle"], 230, 116, 143, 8)
        elif kind == "orbs":
            self.text(surf, "THE THREE ORBS", 160, 28, 14)
            r._prologue_orbs(surf, 160, 92, tick, scale=1.8)
            self.text(surf, "Your thoughts are important to us.", 160, 140, 9)
        elif kind == "robots":
            self.text(surf, "THE APPLE-CORE CUSTODIANS", 160, 17, 12)
            r._prologue_custodians(surf, sim, "transfer", tick=tick)
            self.text(surf, "Designed in a very walled garden.", 160, 145, 9)
        else:
            self.sprite(surf, r._character_sprite(sim, "side-idle"), 160, 103, 58, width=80)
            self.text(surf, "GOLIATH HAS LEFT THE CHAT.", 160, 116, 13)
            self.text(surf, "You still have the keys.", 160, 143, 9)
        if not reduced:
            alpha = round(255 * max(0, 1 - local / .7, (local - card["seconds"] + .7) / .7))
            if alpha:
                shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                shade.fill((0, 0, 0, min(255, alpha)))
                surf.blit(shade, (0, 0))
