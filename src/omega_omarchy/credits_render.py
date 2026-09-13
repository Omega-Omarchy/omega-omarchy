"""Cinematic cast cards and a white-on-black, music-length credit roll."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import OrderedDict
import pygame

from .credits import FPS, PATRON_FONT_SIZES, ROLL_OPENING_HOLD, ROLL_TARGET_SPEED, cast_card, credit_manifest, roll_offset, roll_opening_offset

WHITE = (255, 255, 255)


class CreditsRenderer:
    def __init__(self, renderer):
        self.r = renderer
        self.fonts = {}
        self.layouts = {}
        self.openings = {}
        self.glyphs = {}
        self.logos = {}
        self.seal_bakes = {}
        self.wraps = OrderedDict()
        self.pages = {}
        self.scrub_status = None
        self.roll_glyphs = {}
        self._roll_text = False

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

    @staticmethod
    def control_label(sim, action):
        # The subset font has no arrow symbols. Keep remapped bindings, but
        # spell arrow keys out instead of emitting an invisible character.
        label = sim.prompt_binding(action, compact=True)
        return {"↑": "Up", "↓": "Down", "←": "Left", "→": "Right"}.get(label, label)

    def _measure_text(self, text, size, scale):
        if self._fully_covered(text, size, scale):
            return self.font(size, scale).size(text)[0]
        return sum(self._char_font(ch, size, scale).size(ch)[0] for ch in text)

    def _render_text(self, text, size, scale, color):
        if self._fully_covered(text, size, scale):
            return self.font(size, scale).render(text, True, color)
        primary = self.font(size, scale)
        glyphs = []
        for ch in text:
            font = self._char_font(ch, size, scale)
            # Font surfaces have different ascents. Align their baselines,
            # retaining enough space for accents and descenders after shifting.
            offset = max(0, primary.get_ascent() - font.get_ascent())
            glyphs.append((font.render(ch, True, color), offset))
        width = max(1, sum(g.get_width() for g, _ in glyphs))
        height = max((g.get_height() + offset for g, offset in glyphs), default=1)
        combined = pygame.Surface((width, height), pygame.SRCALPHA)
        cursor = 0
        for glyph, offset in glyphs:
            combined.blit(glyph, (cursor, offset))
            cursor += glyph.get_width()
        return combined

    def wrap(self, text, width, size=8):
        key = (text, width, size)
        if key in self.wraps:
            self.wraps.move_to_end(key)
            return self.wraps[key]
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
        result = lines or [""]
        self.wraps[key] = result
        if len(self.wraps) > 512:
            self.wraps.popitem(last=False)
        return result

    def text(self, surf, text, x, y, size=8, align="center", color=WHITE):
        scale = self.r._vs
        key = (text, size, scale, color)
        if key not in self.glyphs:
            self.glyphs[key] = self._render_text(text, size, scale, color)
        image = self.glyphs[key]
        rect = image.get_rect()
        rect.top = round(y * scale)
        setattr(rect, {"left": "left", "right": "right", "center": "centerx"}[align], round(x * scale))
        if self._roll_text:
            if key not in self.roll_glyphs:
                bounds = image.get_bounding_rect()
                # Accepted roll text sits on black. Crop to actual ink so
                # opaque padding cannot wipe out a neighboring line. Unusual
                # tall custom glyphs retain alpha if their ink exceeds the
                # normal line spacing; cast cards always retain alpha too.
                pitch = (16 if size > 8 else 11 * size / 8) * scale
                baked = None
                if bounds.width and bounds.height <= pitch:
                    baked = pygame.Surface(bounds.size).convert()
                    baked.blit(image, (0, 0), bounds)
                self.roll_glyphs[key] = (baked, bounds.topleft)
            baked, offset = self.roll_glyphs[key]
            if baked is not None:
                surf.blit(baked, (rect.x + offset[0], rect.y + offset[1]))
                return
        surf.blit(image, rect)

    def block(self, surf, text, x, y, width, size=8, align="center", color=WHITE):
        for i, line in enumerate(self.wrap(text, width, size)):
            self.text(surf, line, x, y + i * (size + 3), size, align, color)

    def _wordmark_image(self, width=196):
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
        return self.logos[key]

    def wordmark(self, surf, y, *, width=196):
        scale = self.r._vs
        image, mark_top = self._wordmark_image(width)
        left = (320 - width) / 2
        surf.blit(image, (round(left * scale), round(y * scale) - mark_top))

    def opening(self, character):
        key = (character, self.r._vs)
        if key not in self.openings:
            entries, height = self.layout(character)
            logo = next((y for y, _, row in entries if row["kind"] == "logo"), None)
            first_text = next((y for y, _, row in entries if row["kind"] != "logo"), None)
            starring = next((y for y, _, row in entries if row.get("text") == "STARRING"), None)
            opening = None
            if logo is not None and first_text is not None and starring is not None:
                speed = (height + 105.0) / float(credit_manifest()["music"]["duration"])
                join = max(0.0, (starring - 180 + 105) / speed)
                image, mark_top = self._wordmark_image()
                ink = image.get_bounding_rect()
                center = (ink.y + ink.height / 2 - mark_top) / self.r._vs
                opening = {"join": join, "hold": min(ROLL_OPENING_HOLD, join / 2),
                           "logoStart": logo + 12 + center - 90, "textStart": first_text - 180}
            self.openings[key] = opening
        return self.openings[key]

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
            offsets, offset = [], 0.0
            for count in row["gridLineCounts"]:
                offsets.append(offset)
                offset += count * row["lineHeight"]
            row["gridOffsets"] = offsets
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
            # One patron group can span many screens. Visit only its
            # visible rows, including font-height spill across the top edge.
            font_height = max(self.font(row["fontSize"], self.r._vs).get_height(),
                              self.fallback_font(row["fontSize"], self.r._vs).get_height()) / self.r._vs
            start = max(0, bisect_right(row["gridOffsets"], -y - font_height) - 1)
            viewport = surf.get_height() / self.r._vs
            for index in range(start, len(row["grid"])):
                cursor_y = y + row["gridOffsets"][index]
                if cursor_y >= viewport:
                    break
                grid_row = row["grid"][index]
                for col, lines in enumerate(grid_row):
                    x = 18 + col_width * (col + 0.5)
                    for i, line in enumerate(lines):
                        self.text(surf, line, x, cursor_y + i * row["lineHeight"], row["fontSize"])
        elif kind in {"heading", "text"}:
            size, gap, inset = (11, 16, 12) if kind == "heading" else (8, 11, 0)
            for i, line in enumerate(row["lines"]): self.text(surf, line, 160, y + inset + i * gap, size)
            if kind == "heading" and row.get("subtitleLines"):
                sub_y = y + inset + len(row["lines"]) * gap
                for i, sub_line in enumerate(row["subtitleLines"]): self.text(surf, sub_line, 160, sub_y + i * 10, 7)
        elif kind == "seals":
            self.seals(surf, y)

    def seals(self, surf, y):
        # Rich vector-style artwork is baked offline at each detail tier. The
        # row is black-backed, so scrolling needs one opaque blit and no alpha
        # blending, font rasterization, or geometric drawing.
        scale = self.r._vs
        if scale not in self.seal_bakes:
            path = self.r.root / f"ui/credits/guild-badges-{scale}x.png"
            self.seal_bakes[scale] = pygame.image.load(str(path)).convert()
        surf.blit(self.seal_bakes[scale], (0, round(y * scale)))

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
                self._roll_text = True
                try:
                    self._draw_roll(surf, sim, seconds, reduced)
                finally:
                    self._roll_text = False
        except pygame.error:
            return
        # Instructions disappear once the sequence has had time to establish.
        opening = self.opening(sim.character_name) if sim.scene != "ending" else None
        if seconds < (opening["hold"] if opening else 3):
            action = self.control_label(sim, "jump")
            try:
                self.text(surf, f"{action} / Esc  {'skip to credits' if sim.scene == 'ending' else 'return'}", 310, 168, 6, "right", (150, 150, 150))
                up, down = self.control_label(sim, "up"), self.control_label(sim, "down")
                directions = "D-pad Up/Down" if sim.last_input_device == "gamepad" else f"{up}/{down}"
                self.text(surf, f"{directions} scrub (hold to accelerate)", 10, 168, 6, "left", (150, 150, 150))
            except pygame.error:
                return
        if sim.credits_scrub_direction:
            label = "REWIND" if sim.credits_scrub_direction < 0 else "FORWARD"
            # Draw only during scrubbing, leaving normal playback untouched.
            pygame.draw.rect(surf, (0, 0, 0), self.r._lr(0, 164, 320, 16))
            key = (label, int(seconds), self.r._vs)
            if self.scrub_status is None or self.scrub_status[0] != key:
                status = f"{label}   {int(seconds) // 60}:{int(seconds) % 60:02d}"
                self.scrub_status = (key, self._render_text(status, 7, self.r._vs, (190, 190, 190)))
            image = self.scrub_status[1]
            surf.blit(image, image.get_rect(midtop=self.r._lp(160, 168)))

    def _draw_roll(self, surf, sim, seconds, reduced):
        duration = credit_manifest()["music"]["duration"]
        if seconds >= duration:
            return
        entries, height = self.layout(sim.character_name)
        opening = self.opening(sim.character_name)
        if reduced:
            if opening and seconds < opening["hold"]:
                self.wordmark(surf, 12 - opening["logoStart"])
                return
            # Static pages, broken only between complete credit entries.
            if sim.character_name not in self.pages:
                pages, page, used = [], [], 0
                for _, size, row in entries:
                    if page and used + size > 150:
                        pages.append(page)
                        page, used = [], 0
                    page.append((used, row))
                    used += size
                if page:
                    pages.append(page)
                self.pages[sim.character_name] = pages
            pages = self.pages[sim.character_name]
            page = pages[min(len(pages) - 1, int(seconds / duration * len(pages)))]
            for y, row in page:
                self.draw_row(surf, row, y + 12)
            return
        offset = roll_offset(seconds, height)
        logo_offset = offset
        if opening and seconds < opening["join"]:
            offset = roll_opening_offset(seconds, height, opening["textStart"], opening["join"])
            logo_offset = roll_opening_offset(seconds, height, opening["logoStart"], opening["join"])
        for y, size, row in entries:
            top = y - (logo_offset if row["kind"] == "logo" else offset)
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
                image = r._load(f"character-packs/{identity}/{r._fid_cur}/{pose}.png")
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
