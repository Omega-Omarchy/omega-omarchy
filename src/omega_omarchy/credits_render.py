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

    def font(self, size, scale):
        key = (size, scale)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.Font(str(self.r.root / "ui/credits/credits-sans.otf"), round(size * scale))
        return self.fonts[key]

    def wrap(self, text, width, size=8):
        font = self.font(size, 4)
        lines, line = [], ""
        for word in text.split():
            candidate = (line + " " + word).strip()
            if line and font.size(candidate)[0] > width * 4:
                lines.append(line)
                line = ""
            # Preserve every character, even in a very long username.
            for char in word:
                if font.size(line + char)[0] > width * 4:
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
            self.glyphs[key] = self.font(size, scale).render(text, True, color)
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
        entries, y = [], 0.0
        for row, height in measured:
            entries.append((y, height, row))
            y += height
        self.layouts[character] = (entries, y)
        return entries, y

    def measure_row(self, source, character, *, name_size=8):
        row = dict(source)
        kind = row["kind"]
        if kind == "pair":
            left = self.wrap(row["role"], 139, 7)
            right = self.wrap(row["name"].replace("{character}", character), 139, 8)
            row["columns"] = (left, right)
            height = max(row["height"], max(len(left), len(right)) * 11 + 2)
        elif kind == "names":
            ratio = name_size / 8
            row["fontSize"], row["lineHeight"] = name_size, 11 * ratio
            row["columns"] = [self.wrap(name, 135, name_size) for name in row["names"]]
            height = max(row["height"] * ratio, max(map(len, row["columns"])) * row["lineHeight"] + 2 * ratio)
        elif kind in {"heading", "text"}:
            row["lines"] = self.wrap(row["text"], 284, 12 if kind == "heading" else 8)
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
            for col, lines in enumerate(row["columns"]):
                for i, line in enumerate(lines): self.text(surf, line, 86 + col * 148, y + i * row["lineHeight"], row["fontSize"])
        elif kind in {"heading", "text"}:
            size, gap, inset = (12, 16, 12) if kind == "heading" else (8, 11, 0)
            for i, line in enumerate(row["lines"]): self.text(surf, line, 160, y + inset + i * gap, size)
        elif kind == "seals":
            self.seals(surf, y)

    def seals(self, surf, y):
        r, scale = self.r, self.r._vs
        # Original badges, deliberately fictional film-industry parodies.
        for i, (acronym, caption) in enumerate([
            ("I.A.T.S.E.T.", "Terminal Set Employees"),
            ("SAG / APT-RA", "Screen Agents Guild"),
            ("DOLLY STEREO", "Two channels. One chair."),
            ("M.P.A.A.A.", "Autonomous Agents Association"),
        ]):
            x, top = 85 + (i % 2) * 150, y + (i // 2) * 62
            if i in {0, 3}:
                points = [(x + math.cos(a * math.pi / 12) * (23 if a % 2 else 27), top + 21 + math.sin(a * math.pi / 12) * (18 if a % 2 else 22)) for a in range(24)]
                pygame.draw.polygon(surf, WHITE, [r._lp(*p) for p in points], max(1, scale))
            else:
                pygame.draw.rect(surf, WHITE, r._lr(x - 56, top + 4, 112, 34), max(1, scale))
                if i == 2:
                    for n in range(6):
                        pygame.draw.line(surf, WHITE, r._lp(x - 48 + n * 3, top + 12), r._lp(x - 48 + n * 3, top + 29), max(1, scale))
            self.text(surf, acronym, x + (8 if i == 2 else 0), top + 16, 7)
            self.text(surf, caption, x, top + 44, 6)

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
        seconds = sim.credits_ticks / FPS
        reduced = bool(sim.settings.get("reducedMotion") or sim.accessibility.reduced_motion)
        if sim.scene == "ending":
            self.title(surf, sim, seconds, reduced)
        else:
            duration = credit_manifest()["music"]["duration"]
            if seconds >= duration: return
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
                if page: pages.append(page)
                page = pages[min(len(pages) - 1, int(seconds / duration * len(pages)))]
                for y, row in page: self.draw_row(surf, row, y + 12)
            else:
                offset = roll_offset(seconds, height)
                for y, size, row in entries:
                    top = y - offset
                    if top + size >= 0 and top < 180:
                        self.draw_row(surf, row, top)
        # Instructions disappear once the sequence has had time to establish.
        if seconds < 3:
            action = sim.prompt_binding("jump", compact=True)
            self.text(surf, f"{action} / Esc  {'skip to credits' if sim.scene == 'ending' else 'return'}", 310, 168, 6, "right", (150, 150, 150))

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
