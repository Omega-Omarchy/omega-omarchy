"""Software renderer for play, stills, and headless inspection."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pygame
from pygame import Surface

from . import INSTALLER_COMPLETION_ACTION
from .runtime_assets import BRONZE, PALETTE, asset_dir
from .accessibility import ACTION_LABELS
from .campaign import CAMPAIGN_ROSTER
from .installer import (
    CONFIRM_PROMPT,
    GREETER_HINT,
    GREETER_TAGLINE,
    NAV_HINT,
    PROGRESS_TIPS,
    PROGRESS_TITLE,
    SETUP_ACCOUNT,
    SETUP_MACHINE,
)

LIME_MARK = (158, 206, 106)
SHIFT_CYAN = (125, 207, 255)
GUM_PURPLE = (173, 142, 230)
BAR_FILL = (164, 172, 214)
BAR_DOT = (80, 86, 112)
from .physics import TILE
from .presentation import (
    CHAR_WORLD_HEIGHT,
    FIDELITIES,
    canvas_size,
    migrate_quality,
    view_scale,
)
from .sim import (
    ATTACKS,
    BOSS_FIELD_HEALTH,
    CANNON_BARREL_HEIGHT,
    CANNON_BARREL_PIVOT,
    CANNON_BARREL_WIDTH,
    CANNON_BASE_HEIGHT,
    CANNON_BASE_WIDTH,
    CANNON_MAX_CHARGE_TICKS,
    ITEMS,
    INTENT_COUNTERS,
    NETWORK_TICKS,
    OMEGA_LETTERS,
    PROLOGUE_BEATS,
    PROLOGUE_LOGIN_FLASH_HOLD_TICKS,
    PROLOGUE_LOGIN_FLASH_IN_TICKS,
    PROLOGUE_LOGIN_FLASH_OUT_TICKS,
    PROLOGUE_PASSWORD,
    PROLOGUE_SKIP_HOLD_TICKS,
    PROLOGUE_TYPE_TICKS,
    STAGE_MAP_FLASH_HOLD_TICKS,
    STAGE_MAP_FLASH_IN_TICKS,
    STAGE_MAP_FLASH_OUT_TICKS,
    STAGE_MAP_TRANSITION_TICKS,
    STAGE_NODE_POSITIONS,
    GameSim,
    cow_cannon_geometry,
)

INTERNAL = (320, 180)  # logical camera in world pixels; fidelity only changes raster density
# Kept for save/inspect compatibility. Collision never reads this.
QUALITY_SCALE = {
    "eight-bit": 2,
    "sixteen-bit": 2,
    "clean-pixel": 2,
    "crt": 2,
    "high": 3,
    "ultra": 4,
}
BOSS_WORLD_HEIGHT = 52
ENEMY_WORLD_HEIGHT = 24
SLIDE_WORLD_DROP = 8
PROLOGUE_MIND_HERO_X = 164
PROLOGUE_MIND_HERO_FEET_Y = 122
PROLOGUE_MIND_HERO_HEIGHT = 38
PROLOGUE_MIND_HERO_ANGLE = -8.0
PROLOGUE_MIND_BRAIN = (181, 92)
PROLOGUE_DOOR_END_SCALE = 0.435


def parallax_offset(layer_width: int, viewport_width: int, camera_x: float, max_camera_x: float, depth: float) -> int:
    """Reveal one finite panorama without wrapping or duplicating its bitmap."""

    travel = max(0, layer_width - viewport_width)
    progress = 0.0 if max_camera_x <= 0 else max(0.0, min(1.0, camera_x / max_camera_x))
    return -round(travel * progress * max(0.0, min(1.0, depth)))


def foreground_parallax_y(camera_y: float, max_camera_y: float, raster_scale: int) -> int:
    """Keep ground-affixed foreground art in exact vertical world lockstep."""

    vertical_ascent = max(0.0, max_camera_y - camera_y)
    return round(vertical_ascent * raster_scale)


def background_parallax_y(
    camera_y: float,
    max_camera_y: float,
    depth: float,
    raster_scale: int,
) -> int:
    """Ground-register a structural scenery plane without adding time drift."""

    vertical_ascent = max(0.0, max_camera_y - camera_y)
    factor = max(0.0, min(0.28, 0.08 + depth * 0.13))
    return round(min(40.0, vertical_ascent * factor) * raster_scale)


class Renderer:
    def __init__(self, *, ensure_assets: bool = True):
        self.root = asset_dir()
        if ensure_assets and not (self.root / "characters" / "david_sixteen-bit_ots.png").exists():
            # Asset generation depends on Pillow and NumPy and belongs to the
            # developer build, not the browser runtime.
            from .assets import build_assets

            build_assets(self.root)
        pygame.font.init()
        self.font = pygame.font.SysFont("monospace", 10)
        self.font_big = pygame.font.SysFont("monospace", 16)
        self._font_cache: dict[tuple[int, int, bool], pygame.font.Font] = {}
        self._omarchy_font_cache: dict[tuple[int, int], pygame.font.Font] = {}
        self.cache: dict[str, Surface] = {}
        self._persist: Surface | None = None
        self._curve_cache: dict[tuple[int, int, int, int], tuple[tuple[int, int, int], ...]] = {}
        self._crt_overlay_cache: dict[tuple[int, ...], Surface] = {}
        self._actor_transform_cache: dict[tuple[Any, ...], Surface] = {}
        self._vs = 1
        self._fid_cur = "ultra"
        self._iw, self._ih = INTERNAL
        self._last_frame: Surface | None = None
        self._stage_transition_source: Surface | None = None
        self._stage_transition_active = False

    def _load(self, rel: str) -> Surface:
        if rel not in self.cache:
            path = self.root / rel
            self.cache[rel] = pygame.image.load(str(path)).convert_alpha()
        return self.cache[rel]

    def _fid(self, sim: GameSim, rel: str) -> Surface:
        fid = self._active_fid(sim)
        candidate = self.root / "fidelity" / fid / rel
        if candidate.is_file():
            key = f"fidelity/{fid}/{rel}"
            return self._load(key)
        return self._load(rel)

    def _active_fid(self, sim: GameSim) -> str:
        if sim.scene == "installer":
            step = sim.installer.step
            page = sim.installer.gum_page()
            if step == "quality" and page:
                idx = int(page.get("index") or 0)
                if 0 <= idx < len(FIDELITIES):
                    return FIDELITIES[idx]
            return getattr(sim.installer.choices, "fidelity", "ultra") or "ultra"
        fid, _ = migrate_quality(sim.quality, sim.settings)
        return getattr(sim, "fidelity", None) or fid

    def _layout(self, sim: GameSim) -> tuple[str, int, int, int]:
        fid = self._active_fid(sim)
        vs = view_scale(fid)
        w, h = canvas_size(fid)
        return fid, vs, w, h

    def _font(self, *, big: bool = False, logical_size: int | None = None, bold: bool = False) -> pygame.font.Font:
        vs = self._vs
        size = logical_size or (16 if big else 10)
        key = (vs, size, bold)
        if key not in self._font_cache:
            self._font_cache[key] = pygame.font.SysFont("monospace", size * vs, bold=bold)
        return self._font_cache[key]

    def _omarchy_font(self, logical_size: int) -> pygame.font.Font:
        """Load the vendored vectorized wordmark alphabet for display titles."""

        key = (self._vs, logical_size)
        if key not in self._omarchy_font_cache:
            source = self.root / "ui" / "omarchy-font.ttf"
            if source.is_file():
                self._omarchy_font_cache[key] = pygame.font.Font(
                    str(source), logical_size * self._vs
                )
            else:
                self._omarchy_font_cache[key] = self._font(logical_size=logical_size, bold=True)
        return self._omarchy_font_cache[key]

    def _lp(self, x: int, y: int) -> tuple[int, int]:
        return x * self._vs, y * self._vs

    def _lr(self, x: int, y: int, w: int, h: int) -> pygame.Rect:
        v = self._vs
        return pygame.Rect(x * v, y * v, w * v, h * v)

    def _fit(self, img: Surface, size: tuple[int, int]) -> Surface:
        if img.get_size() == size:
            return img
        if img.get_width() > size[0] or img.get_height() > size[1]:
            return pygame.transform.smoothscale(img, size)
        return pygame.transform.scale(img, size)

    @staticmethod
    def _binding_pair(sim: GameSim, action: str) -> str:
        keyboard = sim.binding_label(action, compact=True)
        gamepad = sim.binding_label(action, device="gamepad", compact=True)
        return f"{keyboard}/{gamepad}"

    def _legible_text_color(self, color: tuple[int, int, int]) -> tuple[int, int, int]:
        """Lift dark 16-bit glyphs without changing panel or world colors."""

        if self._fid_cur != "sixteen-bit":
            return color
        luminance = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
        if luminance >= 160:
            return color
        return tuple(min(255, round(channel * 1.15)) for channel in color)

    def blit_text(self, surf: Surface, text: str, xy: tuple[int, int], color: tuple[int, int, int] | None = None, *, fid: str | None = None) -> None:
        color = self._legible_text_color(color or PALETTE["bright_green"])
        img = self._font().render(text, True, color)
        surf.blit(img, self._lp(*xy))

    def fit_text(
        self,
        surf: Surface,
        text: str,
        rect: tuple[int, int, int, int],
        color: tuple[int, int, int] | None = None,
        *,
        align: str = "left",
        max_size: int = 10,
        min_size: int = 6,
        bold: bool = False,
    ) -> pygame.Rect:
        """Fit, then ellipsize, a UI label inside a logical rectangle."""

        color = self._legible_text_color(color or PALETTE["bright_green"])
        x, y, w, h = rect
        limit = max(1, w * self._vs)
        chosen = self._font(logical_size=min_size, bold=bold)
        for size in range(max_size, min_size - 1, -1):
            candidate = self._font(logical_size=size, bold=bold)
            if candidate.size(str(text))[0] <= limit:
                chosen = candidate
                break
        shown = str(text)
        if chosen.size(shown)[0] > limit:
            ellipsis = "…"
            while shown and chosen.size(shown + ellipsis)[0] > limit:
                shown = shown[:-1]
            shown = shown.rstrip() + ellipsis
        image = chosen.render(shown, True, color)
        px = x * self._vs
        if align == "center":
            px += (w * self._vs - image.get_width()) // 2
        elif align == "right":
            px += w * self._vs - image.get_width()
        py = y * self._vs + max(0, (h * self._vs - image.get_height()) // 2)
        return surf.blit(image, (px, py))

    def wrapped_text(
        self,
        surf: Surface,
        text: str,
        rect: tuple[int, int, int, int],
        color: tuple[int, int, int],
        *,
        max_lines: int = 2,
        logical_size: int = 8,
    ) -> tuple[str, ...]:
        x, y, w, h = rect
        words = str(text).split()
        lines: list[str] = []
        font = self._font(logical_size=logical_size)
        while words and len(lines) < max_lines:
            line = words.pop(0)
            while words and font.size(f"{line} {words[0]}")[0] <= w * self._vs:
                line += " " + words.pop(0)
            lines.append(line)
        if words and lines:
            lines[-1] += " …"
        line_h = max(1, h // max(1, max_lines))
        for i, line in enumerate(lines):
            self.fit_text(surf, line, (x, y + i * line_h, w, line_h), color, max_size=logical_size, min_size=6)
        return tuple(lines)

    def _panel(self, surf: Surface, rect: tuple[int, int, int, int], *, fill: tuple[int, int, int] = (8, 10, 18)) -> None:
        pygame.draw.rect(surf, fill, self._lr(*rect))
        try:
            frame = self._load(f"fidelity/{self._fid_cur}/ui/panel.png")
            surf.blit(self._fit(frame, (rect[2] * self._vs, rect[3] * self._vs)), self._lp(rect[0], rect[1]))
        except Exception:
            pygame.draw.rect(surf, BRONZE if self._fid_cur == "ultra" else LIME_MARK, self._lr(*rect), max(1, self._vs))

    def frame(self, sim: GameSim) -> Surface:
        fid, vs, iw, ih = self._layout(sim)
        self._fid_cur = fid
        self._vs = vs
        self._iw, self._ih = iw, ih
        transition_active = sim.scene == "stage-map" and sim.stage_map_transition_ticks > 0
        if transition_active and not self._stage_transition_active:
            self._stage_transition_source = self._last_frame.copy() if self._last_frame is not None else None
        self._stage_transition_active = transition_active
        surf = Surface((iw, ih))
        if sim.scene == "installer":
            surf.fill(PALETTE.get("bg", PALETTE["dark"]))
        else:
            surf.fill(PALETTE["dark"])
        if sim.scene == "installer":
            self._installer(surf, sim)
        elif sim.scene == "prologue":
            self._prologue(surf, sim)
        elif sim.scene == "stage-map":
            self._stage_map(surf, sim)
        elif sim.scene == "pause":
            self._world(surf, sim)
            self._pause(surf, sim)
        elif sim.scene == "items":
            self._world(surf, sim)
            self._items(surf, sim)
        elif sim.scene == "remap":
            self._world(surf, sim)
            self._remap(surf, sim)
        elif sim.scene == "customize":
            self._world(surf, sim)
            self._customize(surf, sim)
        elif sim.scene == "flight":
            self._world(surf, sim)
            self._flight(surf, sim)
        elif sim.scene == "network":
            self._network(surf, sim)
        elif sim.scene == "edit":
            self._world(surf, sim)
            self._ots(surf, sim)
        elif sim.scene == "turn":
            self._world(surf, sim)
            self._turn(surf, sim)
        elif sim.scene == "reroll-confirm":
            self._world(surf, sim)
            self._reroll_confirm(surf, sim)
        elif sim.scene == "recovery":
            self._world(surf, sim)
            self._recovery(surf, sim)
        elif sim.scene == "chapter-complete":
            self._world(surf, sim)
            self._chapter_complete(surf, sim)
        elif sim.scene == "chapter-credits":
            self._chapter_credits(surf, sim)
        elif sim.scene == "oligarchy":
            self._oligarchy(surf, sim)
        elif sim.scene in {"ending", "credits"}:
            self._ending(surf, sim)
        else:
            self._world(surf, sim)
            self._hud(surf, sim)
            if sim.combat and sim.scene == "action":
                self._combat_action(surf, sim)
            if sim.flash_ticks > 0:
                self._flash(surf, sim)
        fid, disp = migrate_quality(sim.quality, sim.settings)
        fid = self._active_fid(sim)
        disp = getattr(sim, "display", None) or disp
        crt = (sim.settings.get("crt") or {}) if sim.settings else {}
        reduced = bool(sim.settings.get("reducedMotion") or sim.accessibility.reduced_motion)
        if disp == "crt" and not reduced:
            surf = self._crt(surf, crt)
        else:
            self._persist = None
        self._last_frame = surf.copy()
        if not transition_active:
            self._stage_transition_source = None
        return surf

    def _posterize(self, surf: Surface, colors: int) -> Surface:
        arr = pygame.surfarray.array3d(surf)
        factor = max(1, 256 // max(2, int(colors ** (1 / 3))))
        arr = (arr // factor) * factor
        out = Surface(surf.get_size())
        pygame.surfarray.blit_array(out, arr)
        return out

    def _curve(self, surf: Surface, amount: float) -> Surface:
        """Fast curved-screen approximation using SDL-accelerated row bands.

        The former implementation copied the full framebuffer into NumPy and
        performed an allocating advanced-index remap every frame. This keeps
        work in pygame/SDL's compiled scaling paths and caches only a tiny row
        geometry table when the slider or fidelity changes.
        """

        amount = max(0.0, min(1.0, float(amount)))
        if amount <= 0.0:
            return surf
        w, h = surf.get_size()
        key = (w, h, round(amount * 1000), self._vs)
        cached = self._curve_cache.get(key)
        if cached is None:
            band_h = max(2, 2 * self._vs)
            max_inset = max(1, round(w * 0.065 * amount))
            geometry: list[tuple[int, int, int]] = []
            for y in range(0, h, band_h):
                height = min(band_h, h - y)
                normalized_y = abs((y + height * 0.5) - h * 0.5) / max(1.0, h * 0.5)
                inset = round(max_inset * normalized_y * normalized_y)
                # Integer-pixel inset changes are sparse at the deliberately
                # subtle end of the slider. Merge equal neighboring bands so
                # the normal 12% setting needs only a handful of transforms.
                if geometry and geometry[-1][2] == inset:
                    previous_y, previous_h, _ = geometry[-1]
                    geometry[-1] = (previous_y, previous_h + height, inset)
                else:
                    geometry.append((y, height, inset))
            cached = tuple(geometry)
            if len(self._curve_cache) >= 48:
                self._curve_cache.clear()
            self._curve_cache[key] = cached

        curved = Surface((w, h))
        curved.fill((0, 0, 0))
        for y, height, inset in cached:
            row = surf.subsurface((0, y, w, height))
            if inset:
                row = pygame.transform.smoothscale(row, (max(1, w - inset * 2), height))
            curved.blit(row, (inset, y))
        return curved

    def _crt_overlay(
        self,
        size: tuple[int, int],
        *,
        scan: float,
        scan_size: float,
        mask: float,
        vignette: float,
    ) -> Surface:
        """Cache the static scanline, phosphor-mask, and vignette treatment."""

        w, h = size
        key = (
            w,
            h,
            self._vs,
            round(scan * 1000),
            round(scan_size * 1000),
            round(mask * 1000),
            round(vignette * 1000),
        )
        cached = self._crt_overlay_cache.get(key)
        if cached is not None:
            return cached
        overlay = Surface((w, h), pygame.SRCALPHA)
        scan_step = max(2, round((2.0 + 0.6 * scan_size) * self._vs))
        scan_h = max(1, round((0.25 + 0.75 * scan_size) * self._vs))
        darkness = max(0, min(86, round(78 * scan)))
        if darkness:
            for y in range(scan_step - scan_h, h, scan_step):
                pygame.draw.rect(overlay, (0, 0, 0, darkness), (0, y, w, scan_h))
        if mask:
            mask_layer = Surface((w, h), pygame.SRCALPHA)
            spacing = max(3, 3 * self._vs)
            mask_darkness = max(1, min(32, round(mask * 38)))
            for x in range(spacing - 1, w, spacing):
                pygame.draw.line(mask_layer, (0, 0, 0, mask_darkness), (x, 0), (x, h))
            overlay.blit(mask_layer, (0, 0))
        if vignette:
            vignette_layer = Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(
                vignette_layer,
                (0, 0, 0, int(72 * vignette)),
                vignette_layer.get_rect(),
                max(2, 12 * self._vs),
            )
            overlay.blit(vignette_layer, (0, 0))
        if len(self._crt_overlay_cache) >= 48:
            self._crt_overlay_cache.clear()
        self._crt_overlay_cache[key] = overlay
        return overlay

    def _crt(self, surf: Surface, crt: dict[str, Any]) -> Surface:
        w, h = surf.get_size()
        persist = float(crt.get("persistence", 0.08))
        # A tier switch changes the framebuffer density. Never composite a
        # previous tier's pixels into the new canvas.
        if self._persist is not None and self._persist.get_size() != (w, h):
            self._persist = None
        if self._persist is not None and persist:
            mix = surf.copy()
            mix.set_alpha(int(255 * (1.0 - persist)))
            out = self._persist.copy()
            out.blit(mix, (0, 0))
        else:
            out = surf.copy()
        self._persist = out.copy()

        # Bloom is luminance-preserving: a low-resolution copy softly adds the
        # image's own colors instead of misaligning red/blue channels.
        bloom = float(crt.get("bloom", 0.22))
        if bloom:
            divisor = max(2, 4 * self._vs)
            small = pygame.transform.smoothscale(out, (max(1, w // divisor), max(1, h // divisor)))
            glow = pygame.transform.smoothscale(small, (w, h))
            # Special additive blits ignore per-surface alpha on some pygame
            # backends. Pre-dim RGB so bloom stays subtle instead of doubling
            # the framebuffer into a pink/white wash.
            strength = max(1, min(48, int(128 * bloom)))
            glow.fill((strength, strength, strength), special_flags=pygame.BLEND_RGB_MULT)
            out.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        scan = float(crt.get("scanlines", 0.35))
        scan_size = float(crt.get("scanlineSize", 0.12))
        mask = float(crt.get("mask", 0.0))
        vig = float(crt.get("vignette", 0.2))
        out.blit(self._crt_overlay((w, h), scan=scan, scan_size=scan_size, mask=mask, vignette=vig), (0, 0))
        noise = float(crt.get("noise", 0.04))
        if noise:
            speck = Surface((w, h), pygame.SRCALPHA)
            import random

            for _ in range(int((w * h / (320 * 180)) * 90 * noise)):
                speck.set_at((random.randrange(w), random.randrange(h)), (255, 255, 255, 12))
            out.blit(speck, (0, 0))
        return self._curve(out, float(crt.get("curvature", 0.0)))

    def _center(self, surf: Surface, text: str, y: int, color: tuple[int, int, int], big: bool = False) -> None:
        self.fit_text(surf, text, (8, y, 304, 20 if big else 12), color, align="center", max_size=16 if big else 10, min_size=7, bold=big)

    def _wordmark(self, surf: Surface, y: int = 8, pulse: bool = False, tick: int = 0) -> None:
        try:
            base = self._load("ui/omarchy-wordmark.png")
        except Exception:
            mark = pygame.font.SysFont("monospace", 28, bold=True)
            base = mark.render("OMARCHY", True, LIME_MARK)
        img = base
        if pulse:
            img = base.copy()
            w, h = img.get_size()
            band = 10
            center = (tick * 2) % (w + band * 2) - band
            for px in range(max(0, center - band), min(w, center + band)):
                falloff = 1.0 - abs(px - center) / max(1, band)
                for py in range(h):
                    color = img.get_at((px, py))
                    if color.a < 16:
                        continue
                    img.set_at(
                        (px, py),
                        (
                            int(color.r + (SHIFT_CYAN[0] - color.r) * falloff),
                            int(color.g + (SHIFT_CYAN[1] - color.g) * falloff),
                            int(color.b + (SHIFT_CYAN[2] - color.b) * falloff),
                            color.a,
                        ),
                    )
        if self._vs != 1:
            img = pygame.transform.scale(img, (img.get_width() * self._vs, img.get_height() * self._vs))
        x = (self._iw - img.get_width()) // 2
        self._omega_modifier(surf, x + 4 * self._vs, max(0, (y - 7) * self._vs))
        surf.blit(img, (x, y * self._vs))
        return img.get_height()

    def _omega_modifier(self, surf: Surface, x: int, y: int, owned: str | None = None) -> None:
        """Draw the installer/title OMEGA modifier, optionally as progress."""

        font = self._font(logical_size=8, bold=True)
        if owned is None or owned == OMEGA_LETTERS:
            omega = font.render(OMEGA_LETTERS, True, BRONZE)
            surf.blit(omega, (x, y))
            width = omega.get_width()
        else:
            cursor = x
            owned_set = set(owned)
            for letter in OMEGA_LETTERS:
                color = BRONZE if letter in owned_set else PALETTE.get("muted", (100, 104, 122))
                glyph = font.render(letter, True, color)
                surf.blit(glyph, (cursor, y))
                cursor += glyph.get_width()
            width = cursor - x
        line_y = y + 8 * self._vs
        pygame.draw.line(surf, SHIFT_CYAN, (x, line_y), (x + width, line_y), max(1, self._vs))

    def _prologue_backdrop(
        self,
        surf: Surface,
        sim: GameSim,
        rel: str,
        shade_alpha: int = 44,
    ) -> None:
        try:
            backdrop = self._fid(sim, rel)
            surf.blit(pygame.transform.smoothscale(backdrop, (self._iw, self._ih)), (0, 0))
        except Exception:
            surf.fill((8, 14, 24))
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((0, 0, 10, shade_alpha))
        surf.blit(shade, (0, 0))

    def _prologue_hero(
        self,
        surf: Surface,
        sim: GameSim,
        frame: str,
        x: float,
        feet_y: float,
        logical_height: float,
        *,
        flip: bool = False,
        alpha: int = 255,
        angle: float = 0.0,
    ) -> None:
        hero = self._fid(sim, f"characters/david_{frame}.png")
        height = max(1, round(logical_height * self._vs))
        width = max(1, round(hero.get_width() / max(1, hero.get_height()) * height))
        hero = self._fit(hero, (width, height))
        if flip:
            hero = pygame.transform.flip(hero, True, False)
        if angle:
            hero = pygame.transform.rotozoom(hero, angle, 1.0)
        if alpha < 255:
            hero = hero.copy()
            hero.set_alpha(max(0, alpha))
        if angle:
            center = (round(x * self._vs), round((feet_y - logical_height / 2) * self._vs))
            surf.blit(hero, hero.get_rect(center=center))
        else:
            surf.blit(hero, (round(x * self._vs - width / 2), round(feet_y * self._vs - height)))

    def _prologue_orbs(
        self,
        surf: Surface,
        anchor_x: float,
        anchor_y: float,
        tick: int,
        *,
        scale: float = 1.0,
        tether: tuple[float, float] | None = None,
    ) -> None:
        """Keep the same three black-orb custodians across story beats."""

        for index in range(3):
            phase = tick / 17.0 + index * 2.1
            orb_x = anchor_x + (index - 1) * 18 * scale + math.sin(phase) * 5 * scale
            orb_y = anchor_y + (index % 2) * 12 * scale + math.cos(phase) * 5 * scale
            if tether is not None:
                pygame.draw.line(
                    surf,
                    (38, 51, 66),
                    self._lp(*tether),
                    self._lp(orb_x, orb_y),
                    max(1, self._vs),
                )
            radius = max(3, round((7 + index) * scale))
            pygame.draw.circle(surf, (0, 1, 3), self._lp(orb_x, orb_y), radius * self._vs)
            pygame.draw.circle(
                surf,
                SHIFT_CYAN,
                self._lp(orb_x, orb_y),
                radius * self._vs,
                max(1, self._vs),
            )

    def _prologue_sled(self, surf: Surface, x: float, feet_y: float, scale: float = 1.0) -> None:
        """Ground the captured pose while its intentionally still feet travel."""

        width = max(18.0, 38.0 * scale)
        height = max(4.0, 6.0 * scale)
        left = x - width / 2
        top = feet_y - height * 0.42
        pygame.draw.ellipse(
            surf,
            (0, 0, 2),
            pygame.Rect(
                round(left * self._vs),
                round(top * self._vs),
                round(width * self._vs),
                round(height * self._vs),
            ),
        )
        pygame.draw.arc(
            surf,
            (54, 70, 82),
            pygame.Rect(
                round(left * self._vs),
                round(top * self._vs),
                round(width * self._vs),
                round(height * self._vs),
            ),
            math.pi,
            math.tau,
            max(1, self._vs),
        )
        pygame.draw.line(
            surf,
            SHIFT_CYAN,
            (round((left + width * 0.18) * self._vs), round((top + height) * self._vs)),
            (round((left + width * 0.82) * self._vs), round((top + height) * self._vs)),
            max(1, self._vs),
        )

    def _prologue_mind_waves(
        self,
        surf: Surface,
        tick: int,
        *,
        corrupt: bool,
        brain: tuple[float, float] = (193, 85),
    ) -> None:
        color = PALETTE["red"] if corrupt else SHIFT_CYAN
        brain_x, brain_y = brain
        for ring in range(4):
            radius = 5 + ((tick * 0.42 + ring * 9) % 36)
            pygame.draw.ellipse(
                surf,
                color,
                self._lr(brain_x - radius, brain_y - radius * 0.46, radius * 2, radius * 0.92),
                max(1, self._vs),
            )

    def _prologue_transit(self, surf: Surface, sim: GameSim) -> None:
        """Animate a first-person rush through the dimensional tunnel."""

        try:
            tunnel = self._fid(sim, "ui/prologue-rift.png")
            base = pygame.transform.smoothscale(tunnel, (self._iw, self._ih))
            cycle = (sim.story_ticks % 36) / 36.0
            zoom = 1.07 + cycle * 0.09 + math.sin(sim.story_ticks / 7.0) * 0.015
            size = (round(self._iw * zoom), round(self._ih * zoom))
            tunnel = pygame.transform.smoothscale(base, size)
            drift_x = round(math.sin(sim.story_ticks / 10.0) * 3 * self._vs)
            drift_y = round(math.cos(sim.story_ticks / 13.0) * 2 * self._vs)
            surf.blit(
                tunnel,
                (
                    (self._iw - size[0]) // 2 + drift_x,
                    (self._ih - size[1]) // 2 + drift_y,
                ),
            )
        except Exception:
            surf.fill((7, 14, 48))

        effect = Surface((self._iw, self._ih), pygame.SRCALPHA)
        center_x, center_y = 160 * self._vs, 89 * self._vs
        max_radius = 190 * self._vs
        for index in range(42):
            angle = index * 2.399963 + math.sin(sim.story_ticks / 31.0 + index) * 0.08
            distance = (12 + (sim.story_ticks * 4 + index * 23) % 178) * self._vs
            length = (8 + distance / max(1, 18 * self._vs)) * self._vs
            x0 = center_x + math.cos(angle) * distance
            y0 = center_y + math.sin(angle) * distance * 0.54
            x1 = center_x + math.cos(angle) * min(max_radius, distance + length)
            y1 = center_y + math.sin(angle) * min(max_radius, distance + length) * 0.54
            color = (198, 239, 255, 180) if index % 5 else (238, 175, 255, 180)
            pygame.draw.line(effect, color, (x0, y0), (x1, y1), max(1, self._vs))
        for ring in range(5):
            phase = ((sim.story_ticks * 3 + ring * 43) % 215) / 215.0
            radius = (5 + phase * 178) * self._vs
            pygame.draw.ellipse(
                effect,
                (125, 207, 255, max(20, round(170 * (1.0 - phase)))),
                pygame.Rect(
                    center_x - radius,
                    center_y - radius * 0.54,
                    radius * 2,
                    radius * 1.08,
                ),
                max(1, self._vs),
            )
        surf.blit(effect, (0, 0))
        if sim.story_ticks >= 168:
            whiteout = Surface((self._iw, self._ih), pygame.SRCALPHA)
            whiteout.fill((220, 242, 255, min(232, (sim.story_ticks - 168) * 6)))
            surf.blit(whiteout, (0, 0))

    def _prologue_login(self, surf: Surface, sim: GameSim) -> None:
        # Omarchy's real post-install SDDM theme is deliberately spare: the
        # official mark, a lock, one outlined entry field, and image bullets.
        surf.fill((26, 27, 38))
        try:
            logo = self._load("ui/omarchy-wordmark.png")
            logo = pygame.transform.smoothscale(logo, (256 * self._vs, 60 * self._vs))
            logo_x = (self._iw - logo.get_width()) // 2
            self._omega_modifier(surf, logo_x + 5 * self._vs, 1 * self._vs)
            surf.blit(logo, (logo_x, 9 * self._vs))
        except Exception:
            self._wordmark(surf, 9, pulse=False, tick=sim.story_ticks)

        lock_color = (190, 198, 255)
        pygame.draw.rect(surf, lock_color, self._lr(78, 80, 24, 18), border_radius=3 * self._vs)
        pygame.draw.rect(surf, lock_color, self._lr(82, 71, 16, 17), border_radius=8 * self._vs)
        pygame.draw.rect(surf, (26, 27, 38), self._lr(86, 75, 8, 10), border_radius=4 * self._vs)
        pygame.draw.circle(surf, (2, 5, 11), self._lp(90, 88), 2 * self._vs)
        pygame.draw.rect(surf, (2, 5, 11), self._lr(89, 88, 2, 5), border_radius=self._vs)

        pygame.draw.rect(surf, (2, 5, 11), self._lr(108, 77, 143, 24))
        pygame.draw.rect(surf, lock_color, self._lr(108, 77, 143, 24), max(1, self._vs))
        count = max(0, min(len(PROLOGUE_PASSWORD), (sim.story_ticks - 12) // 2))
        for index in range(min(count, 21)):
            pygame.draw.circle(surf, lock_color, self._lp(118 + index * 6, 89), 2 * self._vs)

    def _prologue_login_transition(self, surf: Surface, sim: GameSim) -> None:
        """White through the submitted login, then fade it off the world map."""

        tick = sim.story_transition_ticks
        opaque_at = PROLOGUE_LOGIN_FLASH_IN_TICKS
        reveal_at = opaque_at + PROLOGUE_LOGIN_FLASH_HOLD_TICKS
        if tick <= reveal_at:
            self._prologue_login(surf, sim)
        else:
            self._stage_map(surf, sim)
        if tick <= opaque_at:
            alpha = round(255 * tick / max(1, opaque_at))
        elif tick <= reveal_at:
            alpha = 255
        else:
            elapsed = tick - reveal_at
            alpha = round(255 * (1.0 - elapsed / max(1, PROLOGUE_LOGIN_FLASH_OUT_TICKS)))
        whiteout = Surface((self._iw, self._ih), pygame.SRCALPHA)
        whiteout.fill((255, 255, 255, max(0, min(255, alpha))))
        surf.blit(whiteout, (0, 0))

    def _prologue(self, surf: Surface, sim: GameSim) -> None:
        """Input-paced exposition with deterministic in-engine choreography."""

        beat_index = max(0, min(sim.story_beat, len(PROLOGUE_BEATS) - 1))
        heading, _, staging = PROLOGUE_BEATS[beat_index]
        copy = sim.story_copy

        if staging == "login" and sim.story_transition_ticks:
            self._prologue_login_transition(surf, sim)
            return

        if staging == "title":
            surf.fill((3, 5, 12))
            for ring in range(7):
                radius = (18 + ring * 18 + sim.story_ticks // 3) % 150
                pygame.draw.circle(
                    surf,
                    (18, 34 + ring * 4, 48),
                    self._lp(160, 76),
                    radius * self._vs,
                    max(1, self._vs),
                )
            self._wordmark(surf, 52, pulse=True, tick=sim.story_ticks)
        elif staging == "login":
            self._prologue_login(surf, sim)
        elif staging == "rift":
            self._prologue_transit(surf, sim)
        else:
            campus = staging in {"orb-capture", "orb-door"}
            self._prologue_backdrop(
                surf,
                sim,
                "ui/prologue-campus.png" if campus else "ui/prologue-transfer.png",
                92 if staging == "corrupt" else 44,
            )
            try:
                if staging == "orb-capture":
                    hero_x = 66 + min(1.0, sim.story_ticks / 150.0) * 62
                    self._prologue_hero(surf, sim, "prologue-captured", hero_x, 116, 45)
                    self._prologue_sled(surf, hero_x, 116)
                    self._prologue_orbs(
                        surf,
                        hero_x + 38,
                        78,
                        sim.tick,
                        tether=(hero_x + 4, 92),
                    )
                elif staging == "orb-door":
                    travel = min(1.0, sim.story_ticks / 175.0)
                    # Preserve continuity at the start, then finish 25%
                    # smaller than the prior destination scale as the party
                    # recedes through the distant doorway.
                    scale = 1.0 - travel * (1.0 - PROLOGUE_DOOR_END_SCALE)
                    x = 128 + 120 * travel
                    feet_y = 116
                    self._prologue_hero(
                        surf,
                        sim,
                        "prologue-captured",
                        x,
                        feet_y,
                        44 * scale,
                    )
                    self._prologue_sled(surf, x, feet_y, scale)
                    self._prologue_orbs(
                        surf,
                        x + 38 * scale,
                        feet_y - 38 * scale,
                        sim.tick,
                        scale=scale,
                        tether=(x + 4 * scale, feet_y - 24 * scale),
                    )
                elif staging == "orb-machine":
                    pull_ticks = 84
                    if sim.story_ticks < pull_ticks:
                        travel = sim.story_ticks / pull_ticks
                        x = 24 + 152 * travel
                        self._prologue_hero(surf, sim, "prologue-captured", x, 116, 42)
                        self._prologue_sled(surf, x, 116)
                        self._prologue_orbs(
                            surf,
                            x + 38,
                            78,
                            sim.tick,
                            tether=(x + 4, 92),
                        )
                    else:
                        turned = sim.story_ticks >= 144
                        # Once the sled withdraws, David drops its six-pixel
                        # height so his feet remain planted on the floor.
                        self._prologue_hero(surf, sim, "side-idle", 176, 122, 44, flip=turned)
                        orb_x = 214 if not turned else 214 - (sim.story_ticks - 144) * 2.5
                        if orb_x > -30:
                            self._prologue_orbs(
                                surf,
                                orb_x,
                                78,
                                sim.tick,
                            )
                elif staging in {"transfer", "corrupt"}:
                    self._prologue_mind_waves(
                        surf,
                        sim.story_ticks,
                        corrupt=staging == "corrupt",
                        brain=PROLOGUE_MIND_BRAIN,
                    )
                    if staging == "corrupt":
                        for index in range(28):
                            x = (index * 47 + sim.story_ticks * 3) % 320
                            y = (index * 29 + sim.story_ticks * 2) % 132
                            pygame.draw.rect(surf, PALETTE["red"], self._lr(x, y, 2, 5))
                    self._prologue_hero(
                        surf,
                        sim,
                        "prologue-transfer",
                        PROLOGUE_MIND_HERO_X,
                        PROLOGUE_MIND_HERO_FEET_Y,
                        PROLOGUE_MIND_HERO_HEIGHT,
                        angle=PROLOGUE_MIND_HERO_ANGLE,
                    )
            except Exception:
                pass

        box = Surface((300 * self._vs, 55 * self._vs), pygame.SRCALPHA)
        box.fill((3, 5, 12, 232))
        pygame.draw.rect(box, BRONZE, box.get_rect(), max(1, self._vs))
        surf.blit(box, self._lp(10, 118))
        self.fit_text(surf, heading, (20, 124, 280, 12), PALETTE["bright_green"], max_size=9, min_size=6, bold=True)
        revealed_count = max(1, sim.story_ticks // PROLOGUE_TYPE_TICKS)
        revealed = copy[:revealed_count]
        self.wrapped_text(surf, revealed, (20, 138, 280, 25), PALETTE["fg"], max_lines=3, logical_size=7)
        copy_complete = revealed_count >= len(copy)
        if copy_complete:
            self.fit_text(
                surf,
                f"PRESS {sim.prompt_binding('jump', compact=True)} OR ENTER TO CONTINUE",
                (20, 164, 162, 7),
                PALETTE["yellow"],
                max_size=5,
                min_size=4,
            )
        else:
            bob = (sim.story_ticks // 8) % 2
            pygame.draw.polygon(
                surf,
                PALETTE["yellow"],
                [self._lp(75, 164 + bob), self._lp(83, 164 + bob), self._lp(79, 169 + bob)],
            )
        skip_center = self._lp(218, 166)
        skip_radius = 5 * self._vs
        pygame.draw.circle(surf, PALETTE.get("muted", (90, 94, 110)), skip_center, skip_radius, max(1, self._vs))
        if sim.story_skip_ticks:
            ratio = sim.story_skip_ticks / PROLOGUE_SKIP_HOLD_TICKS
            pygame.draw.arc(
                surf,
                SHIFT_CYAN,
                pygame.Rect(
                    skip_center[0] - skip_radius,
                    skip_center[1] - skip_radius,
                    skip_radius * 2,
                    skip_radius * 2,
                ),
                -math.pi / 2,
                -math.pi / 2 + math.tau * ratio,
                max(1, 2 * self._vs),
            )
        self.fit_text(
            surf,
            sim.prompt_binding("turn", compact=True),
            (215, 163, 6, 6),
            SHIFT_CYAN if sim.story_skip_ticks else PALETTE.get("muted", PALETTE["fg"]),
            align="center",
            max_size=5,
            min_size=4,
            bold=True,
        )
        self.fit_text(
            surf,
            "HOLD TO SKIP",
            (227, 162, 70, 8),
            SHIFT_CYAN if sim.story_skip_ticks else PALETTE.get("muted", PALETTE["fg"]),
            align="left",
            max_size=5,
            min_size=4,
        )

    def _stage_map(self, surf: Surface, sim: GameSim) -> None:
        """Render boss nodes directly over their distinct world regions."""

        transition = max(0, int(getattr(sim, "stage_map_transition_ticks", 0)))
        elapsed = STAGE_MAP_TRANSITION_TICKS - transition
        source_until = STAGE_MAP_FLASH_IN_TICKS + STAGE_MAP_FLASH_HOLD_TICKS
        if transition and elapsed < source_until and self._stage_transition_source is not None:
            source = self._stage_transition_source
            if source.get_size() != surf.get_size():
                source = pygame.transform.smoothscale(source, surf.get_size())
            surf.blit(source, (0, 0))
            alpha = (
                round(255 * elapsed / max(1, STAGE_MAP_FLASH_IN_TICKS))
                if elapsed < STAGE_MAP_FLASH_IN_TICKS
                else 255
            )
            whiteout = Surface((self._iw, self._ih), pygame.SRCALPHA)
            whiteout.fill((255, 255, 255, max(0, min(255, alpha))))
            surf.blit(whiteout, (0, 0))
            return

        try:
            world = self._fid(sim, "ui/stage-world-map.png")
            surf.blit(pygame.transform.smoothscale(world, (self._iw, self._ih)), (0, 0))
        except Exception:
            surf.fill((3, 5, 13))
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((0, 0, 8, 30))
        surf.blit(shade, (0, 0))
        title_font = self._omarchy_font(12)
        title = title_font.render("Omega Omarchy", True, PALETTE["bright_green"])
        max_title = self._lr(18, 4, 284, 15)
        if title.get_width() > max_title.width or title.get_height() > max_title.height:
            ratio = min(
                max_title.width / title.get_width(),
                max_title.height / title.get_height(),
            )
            title = pygame.transform.smoothscale(
                title,
                (
                    max(1, round(title.get_width() * ratio)),
                    max(1, round(title.get_height() * ratio)),
                ),
            )
        surf.blit(title, (max_title.centerx - title.get_width() // 2, max_title.y))
        unlocked = set(sim.unlocked_stage_indices())
        for index, (spec, (x, y)) in enumerate(zip(CAMPAIGN_ROSTER, STAGE_NODE_POSITIONS)):
            selected = index == sim.stage_cursor
            available = index in unlocked
            converted = spec.boss.id in sim.converted
            ring = LIME_MARK if converted else (PALETTE["yellow"] if available else BRONZE)
            radius = 17 if selected else 14
            pygame.draw.circle(surf, (4, 7, 12), self._lp(x, y), radius * self._vs)
            pygame.draw.circle(surf, ring, self._lp(x, y), radius * self._vs, max(1, self._vs))
            if selected:
                pulse = radius + 3 + ((sim.tick // 5) % 3)
                try:
                    emblem = self._load("ui/omega-omarchy-icon.png")
                    bounds = emblem.get_bounding_rect(min_alpha=8)
                    if bounds.width and bounds.height:
                        emblem = emblem.subsurface(bounds).copy()
                    diameter = pulse * 2 * self._vs
                    emblem = self._fit(emblem, (diameter, diameter))
                    surf.blit(emblem, (x * self._vs - diameter // 2, y * self._vs - diameter // 2))
                except Exception:
                    pygame.draw.circle(
                        surf,
                        SHIFT_CYAN,
                        self._lp(x, y),
                        pulse * self._vs,
                        max(1, self._vs),
                    )
            try:
                suffix = "-converted" if converted else ""
                boss = self._fid(sim, f"bosses/{spec.boss.id}{suffix}.png")
                bh = (27 if selected else 23) * self._vs
                bw = max(1, round(boss.get_width() / max(1, boss.get_height()) * bh))
                boss = self._fit(boss, (bw, bh))
                if not available:
                    boss = pygame.transform.grayscale(boss)
                surf.blit(boss, (x * self._vs - bw // 2, y * self._vs - bh // 2))
            except Exception:
                pass
        selected = CAMPAIGN_ROSTER[sim.stage_cursor]
        if selected.boss.id in sim.converted:
            state = "CONVERTED"
        elif sim.stage_cursor in unlocked:
            state = "AVAILABLE"
        else:
            state = "LOCKED"
        panel = Surface((304 * self._vs, 25 * self._vs), pygame.SRCALPHA)
        panel.fill((2, 5, 11, 226))
        pygame.draw.rect(panel, BRONZE, panel.get_rect(), max(1, self._vs))
        surf.blit(panel, self._lp(8, 151))
        self.fit_text(
            surf,
            f"{selected.name} · {selected.boss.title} · {state}",
            (14, 155, 292, 9),
            PALETTE["yellow"],
            align="center",
            max_size=6,
            min_size=4,
            bold=True,
        )
        hint = f"MOVE · PRESS {sim.prompt_binding('jump', compact=True)} TO MOUNT"
        self.fit_text(surf, hint, (14, 166, 292, 6), SHIFT_CYAN, align="center", max_size=5, min_size=4)
        if transition:
            fade_elapsed = max(0, elapsed - source_until)
            alpha = round(255 * (1.0 - fade_elapsed / max(1, STAGE_MAP_FLASH_OUT_TICKS)))
            whiteout = Surface((self._iw, self._ih), pygame.SRCALPHA)
            whiteout.fill((255, 255, 255, max(0, min(255, alpha))))
            surf.blit(whiteout, (0, 0))

    def _installer(self, surf: Surface, sim: GameSim) -> None:
        step = sim.installer.step
        reduced = bool(sim.settings.get("reducedMotion") or sim.accessibility.reduced_motion)
        pulse = (not reduced) and step == "greeter"
        if step == "greeter":
            self._wordmark(surf, 54, pulse=pulse, tick=sim.tick)
            self._center(surf, GREETER_TAGLINE, 105, PALETTE["fg"])
            self._center(surf, GREETER_HINT, 122, PALETTE.get("muted", PALETTE["fg"]))
            return
        if step == "progress":
            self._wordmark(surf, 36, pulse=pulse, tick=sim.tick)
            self._center(surf, PROGRESS_TITLE, 84, PALETTE["fg"])
            self._progress_bar(surf, sim)
            tip = PROGRESS_TIPS[(sim.tick // 90) % len(PROGRESS_TIPS)]
            self._center(surf, f"Tip: {tip}", 112, LIME_MARK)
            return
        if step == "complete":
            self._wordmark(surf, 44, pulse=pulse, tick=sim.tick)
            self._center(surf, sim.installer.installed_line, 94, PALETTE["fg"])
            label = INSTALLER_COMPLETION_ACTION
            text = self._font().render(label, True, self._legible_text_color(PALETTE["dark"]))
            pad_x, pad_y = 6 * self._vs, 3 * self._vs
            bw, bh = text.get_width() + pad_x * 2, text.get_height() + pad_y * 2
            bx = (self._iw - bw) // 2
            by = 108 * self._vs
            pygame.draw.rect(surf, LIME_MARK, pygame.Rect(bx, by, bw, bh))
            if self._fid_cur != "sixteen-bit":
                pygame.draw.rect(surf, (245, 245, 248), pygame.Rect(bx, by, bw, bh), self._vs)
            surf.blit(text, (bx + pad_x, by + pad_y))
            tip = PROGRESS_TIPS[(sim.tick // 90) % len(PROGRESS_TIPS)]
            self._center(surf, f"Tip: {tip}", 138, LIME_MARK)
            return
        # Setup pages: wordmark pins to the top, like the live configurator.
        self._wordmark(surf, 8, pulse=False)
        try:
            from .installer import PARODY_STEPS

            self.fit_text(surf, f"{sim.installer.step_index + 1:02d}/{len(PARODY_STEPS):02d}", (270, 8, 38, 9), PALETTE.get("muted", PALETTE["fg"]), align="right", max_size=7, min_size=6)
        except Exception:
            pass
        if step == "confirm":
            self._confirm_table(surf, sim)
            return
        page = sim.installer.gum_page()
        if page is None:
            return
        fid = self._active_fid(sim)
        row_h = 13 if fid == "ultra" else 12 if fid == "high" else 11
        self.fit_text(surf, page["header"], (24, 54, 270, 12), PALETTE["fg"], max_size=10, min_size=7, bold=True)
        if page.get("ownerHint"):
            self.fit_text(surf, str(page["ownerHint"]), (24, 65, 270, 10), PALETTE.get("muted", PALETTE["fg"]), max_size=8, min_size=6)
        prompt_y = 76 if page.get("ownerHint") else 68
        self.fit_text(surf, page["prompt"], (24, prompt_y, 270, 11), GUM_PURPLE, max_size=9, min_size=7)
        selected = int(page["index"])
        for i, option in enumerate(page["options"]):
            y = prompt_y + 12 + i * row_h
            if i == selected:
                pygame.draw.rect(surf, LIME_MARK, self._lr(20, y - 1, 280, row_h))
                if fid != "sixteen-bit":
                    pygame.draw.rect(surf, (245, 245, 248), self._lr(20, y - 1, 280, row_h), self._vs)
                self.fit_text(surf, f"> {option}", (24, y, 270, row_h), PALETTE["dark"], max_size=9, min_size=6)
            else:
                self.fit_text(surf, f"  {option}", (32, y, 262, row_h), (116, 122, 148), max_size=9, min_size=6)
        if page.get("footnote"):
            self.fit_text(surf, str(page["footnote"]), (24, 150, 272, 10), PALETTE["yellow"], max_size=8, min_size=6)
        self.fit_text(surf, page.get("nav") or NAV_HINT, (24, 164, 272, 10), PALETTE.get("muted", PALETTE["fg"]), max_size=8, min_size=6)

    def _progress_bar(self, surf: Surface, sim: GameSim) -> None:
        width = 88
        x = (320 - width) // 2
        y = 96
        ticks = sim.installer.progress_ticks
        if sim.installer.world is not None:
            filled = min(width, 8 + ticks * 2)
        else:
            filled = min(width, 4 + sim.installer.phase_index * 6)
        pygame.draw.rect(surf, BAR_FILL, self._lr(x, y, max(2, filled), 6))
        for i in range(filled + 2, width, 3):
            pygame.draw.rect(surf, BAR_DOT, self._lr(x + i, y + 2, 1, 1))

    def _confirm_table(self, surf: Surface, sim: GameSim) -> None:
        self.fit_text(surf, SETUP_ACCOUNT, (24, 56, 270, 11), PALETTE["fg"], max_size=9, min_size=7, bold=True)
        rows = sim.installer.confirm_rows()
        pygame.draw.rect(surf, PALETTE["accent"], self._lr(20, 68, 280, 74), self._vs)
        if self._fid_cur != "sixteen-bit":
            pygame.draw.rect(surf, (20, 22, 32), self._lr(21, 69, 278, 72))
        self.fit_text(surf, "Field", (26, 69, 78, 10), PALETTE["fg"], max_size=8, min_size=6)
        self.fit_text(surf, "Value", (112, 69, 180, 10), PALETTE["fg"], max_size=8, min_size=6)
        pygame.draw.line(surf, PALETTE["accent"], self._lp(20, 79), self._lp(300, 79), self._vs)
        pygame.draw.line(surf, PALETTE["accent"], self._lp(108, 68), self._lp(108, 142), self._vs)
        for i, (field, value) in enumerate(rows):
            self.fit_text(surf, field, (26, 80 + i * 8, 78, 8), PALETTE["fg"], max_size=7, min_size=6)
            self.fit_text(surf, str(value), (112, 80 + i * 8, 180, 8), PALETTE["fg"], max_size=7, min_size=6)
        self.fit_text(surf, CONFIRM_PROMPT, (24, 143, 270, 10), PALETTE["cyan"], max_size=8, min_size=6)
        yes = sim.installer.confirm_accept
        if yes:
            pygame.draw.rect(surf, LIME_MARK, self._lr(24, 154, 28, 11))
            self.fit_text(surf, "Yes", (28, 154, 22, 11), PALETTE["dark"], max_size=8, min_size=6)
            self.fit_text(surf, "No, change it", (60, 154, 90, 11), PALETTE["fg"], max_size=8, min_size=6)
        else:
            self.fit_text(surf, "Yes", (28, 154, 22, 11), PALETTE["fg"], max_size=8, min_size=6)
            pygame.draw.rect(surf, LIME_MARK, self._lr(56, 154, 84, 11))
            self.fit_text(surf, "No, change it", (60, 154, 76, 11), PALETTE["dark"], max_size=8, min_size=6)
        self.fit_text(surf, "toggle  •  enter submit", (24, 167, 272, 9), PALETTE.get("muted", PALETTE["fg"]), max_size=7, min_size=6)

    def _flash(self, surf: Surface, sim: GameSim) -> None:
        kind = sim.flash_kind
        alpha = min(90, 8 * sim.flash_ticks)
        color = {
            "bomb": (125, 207, 255, alpha),
            "convert": (158, 206, 106, alpha),
            "penguin": (232, 176, 64, alpha),
            "combat": (247, 118, 142, alpha),
        }.get(kind, (255, 255, 255, alpha))
        overlay = Surface((self._iw, self._ih), pygame.SRCALPHA)
        overlay.fill(color)
        surf.blit(overlay, (0, 0))

    def _goliath_arena_story_layer(self, surf: Surface, sim: GameSim, cam_x: int, cam_y: int) -> None:
        """Affix Goliath's booth or placeholder X notice to the arena wall."""

        boss = next(
            (
                entity
                for entity in sim.entities
                if entity.kind == "boss" and entity.extra.get("boss") == "goliath"
            ),
            None,
        )
        if boss is None:
            return
        stage = str(boss.extra.get("goliath_stage") or "duel")
        arena_x = float(boss.extra.get("arena_x", boss.x)) * TILE
        floor_y = (float(boss.extra.get("arena_y", boss.y)) + 1.0) * TILE
        if stage == "penguin":
            x = round(arena_x - 84.0 - cam_x)
            y = round(floor_y - 112.0 - cam_y)
            if x > 320 or x + 84 < 0 or y > 180 or y + 48 < 0:
                return
            pygame.draw.rect(surf, (3, 5, 9), self._lr(x - 3, y - 3, 90, 54))
            pygame.draw.rect(surf, BRONZE, self._lr(x - 3, y - 3, 90, 54), max(1, 2 * self._vs))
            glass = Surface((78 * self._vs, 38 * self._vs), pygame.SRCALPHA)
            glass.fill((19, 43, 48, 210))
            pygame.draw.rect(glass, (86, 170, 152, 180), glass.get_rect(), max(1, self._vs))
            surf.blit(glass, self._lp(x + 3, y + 3))
            try:
                operator = self._fid(sim, "bosses/goliath.png")
                oh = 34 * self._vs
                ow = max(1, round(operator.get_width() / max(1, operator.get_height()) * oh))
                operator = self._fit(operator, (ow, oh))
                surf.blit(operator, (round((x + 46) * self._vs - ow / 2), (y + 42) * self._vs - oh))
            except Exception:
                pass
            pygame.draw.rect(surf, (35, 27, 25), self._lr(x, y + 42, 84, 9))
            pygame.draw.rect(surf, PALETTE["red"], self._lr(x + 5, y + 44, 21, 3))
            pygame.draw.rect(surf, LIME_MARK, self._lr(x + 30, y + 44, 13, 3))
            pygame.draw.line(surf, PALETTE["red"], self._lp(x + 84, y + 23), self._lp(x + 101, y + 36), max(1, self._vs))
            self.fit_text(
                surf,
                "REMOTE CONTROL",
                (x + 4, y - 1, 76, 7),
                PALETTE["red"],
                align="center",
                max_size=5,
                min_size=4,
                bold=True,
            )
            return
        if stage not in {"minions", "surrendered"}:
            return

        # A world-locked placeholder can later be replaced with the genuine
        # account while preserving the scene's geometry and phase trigger.
        x = round(arena_x - 154.0 - cam_x)
        y = round(floor_y - 112.0 - cam_y)
        if x > 320 or x + 148 < 0 or y > 180 or y + 83 < 0:
            return
        pygame.draw.rect(surf, (8, 8, 10), self._lr(x - 3, y - 3, 154, 89), border_radius=4 * self._vs)
        pygame.draw.rect(surf, (246, 247, 248), self._lr(x, y, 148, 83), border_radius=4 * self._vs)
        self.fit_text(surf, "X", (x + 8, y + 5, 15, 14), (15, 18, 20), max_size=12, min_size=9, bold=True)
        self.fit_text(
            surf,
            "@goliath_placeholder",
            (x + 25, y + 7, 112, 10),
            (92, 99, 106),
            max_size=6,
            min_size=4,
        )
        self.fit_text(surf, "You are blocked", (x + 10, y + 25, 128, 13), (15, 18, 20), max_size=10, min_size=7, bold=True)
        self.wrapped_text(
            surf,
            "You can't follow or view this account's posts.",
            (x + 10, y + 40, 128, 19),
            (83, 91, 98),
            max_lines=2,
            logical_size=6,
        )
        pygame.draw.rect(surf, (207, 214, 219), self._lr(x + 10, y + 64, 128, 12), max(1, self._vs), border_radius=6 * self._vs)
        self.fit_text(surf, "View profile", (x + 15, y + 65, 118, 10), (15, 18, 20), align="center", max_size=6, min_size=5, bold=True)

    def _world(self, surf: Surface, sim: GameSim) -> None:
        if not sim.tiles or sim.body is None:
            return
        fid = self._active_fid(sim)
        skies = {
            "sixteen-bit": (48, 64, 120),
            "high": (18, 16, 36),
            "ultra": (10, 12, 28),
        }
        surf.fill(skies.get(fid, PALETTE["dark"]))
        target_x, target_y = sim.camera_target()
        max_x = max(0, len(sim.tiles[0]) * TILE - INTERNAL[0])
        max_y = max(0, len(sim.tiles) * TILE - INTERNAL[1])
        sim.cam_x += (target_x - sim.cam_x) * 0.14
        sim.cam_y += (target_y - sim.cam_y) * 0.14
        cam_x, cam_y = int(sim.cam_x), int(sim.cam_y)
        pal = sim.active_palette if sim.world else CAMPAIGN_ROSTER[sim.chapter_index].palette
        vs = self._vs
        tw = TILE * vs
        layers = {"sixteen-bit": 2, "high": 3, "ultra": 4}.get(fid, 2)
        for i in range(layers):
            try:
                layer = self._fid(sim, f"bg/{pal}/parallax-{i}.png")
            except Exception:
                try:
                    layer = self._fid(sim, f"bg/parallax-{i}.png")
                except Exception:
                    break
            if layer.get_height() != self._ih:
                scaled_w = max(self._iw, round(layer.get_width() * self._ih / max(1, layer.get_height())))
                layer = pygame.transform.smoothscale(layer, (scaled_w, self._ih))
            # Keep the smoothed camera's fractional position for scenery. The
            # world grid remains integer-aligned, while wide authored planes
            # advance regularly instead of holding on a truncated camera value.
            depth = 0.40 + i * 0.18
            ox = parallax_offset(layer.get_width(), self._iw, sim.cam_x, max_x, depth)
            oy = 0 if i == 0 else background_parallax_y(sim.cam_y, max_y, depth, vs)
            surf.blit(layer, (ox, oy))
        if pal == "goliath":
            self._goliath_arena_story_layer(surf, sim, cam_x, cam_y)
        try:
            corruption_effect = self._fid(sim, "effects/corruption-code.png")
        except Exception:
            corruption_effect = None
        deferred_ladders: list[tuple[int, int, int, int, str]] = []
        for y, row in enumerate(sim.tiles):
            for x, cell in enumerate(row):
                px, py = int(x * tw - cam_x * vs), int(y * tw - cam_y * vs)
                if px < -tw or py < -tw or px > self._iw or py > self._ih:
                    continue
                if cell in {"L", "+"}:
                    deferred_ladders.append((x, y, px, py, cell))
                if cell == "M":
                    if corruption_effect is not None:
                        max_sx = max(0, corruption_effect.get_width() - tw)
                        max_sy = max(0, corruption_effect.get_height() - tw)
                        sample_x = (x * 29 + y * 11) * vs % (max_sx + 1)
                        sample_y = ((y * 37 - sim.tick) * max(1, vs)) % (max_sy + 1)
                        surf.blit(
                            corruption_effect,
                            (px, py),
                            pygame.Rect(sample_x, sample_y, min(tw, corruption_effect.get_width()), min(tw, corruption_effect.get_height())),
                        )
                    else:
                        pygame.draw.rect(surf, (32, 0, 4), (px, py, tw, tw))
                    # Ultra keeps literal binary readable even after a 1254px
                    # effect master is sampled into a 16-world-pixel hazard.
                    if fid == "ultra":
                        for stream in range(2):
                            digit = (sim.tick // 9 + x + y * 3 + stream) & 1
                            dx = px + (3 + stream * 7) * vs
                            dy = py + ((sim.tick // 3 + x * 5 + stream * 7) % 9) * vs
                            color = (255, 86, 54) if stream else (222, 30, 40)
                            if digit:
                                pygame.draw.line(surf, color, (dx + vs, dy), (dx + vs, dy + 4 * vs), max(1, vs))
                                pygame.draw.line(surf, color, (dx, dy + vs), (dx + vs, dy), max(1, vs))
                            else:
                                pygame.draw.rect(surf, color, (dx, dy, 3 * vs, 5 * vs), max(1, vs))
                if cell in {"#", "=", "^", "D", "G"}:
                    key = f"tiles/{pal}_{cell}.png"
                    try:
                        tile = self._fid(sim, key)
                    except Exception:
                        try:
                            tile = self._load(f"tiles/{pal}_{cell}.png")
                        except Exception:
                            pygame.draw.rect(surf, PALETTE["brown"], (px, py, tw, tw))
                            continue
                    tile = self._fit(tile, (tw, tw))
                    variant = (x * 17 + y * 31 + sim.chapter_index * 13) % 4
                    if cell in {"#", "="} and variant:
                        tile = pygame.transform.flip(tile, variant in {1, 3}, variant == 2 and cell == "#")
                    surf.blit(tile, (px, py))
                    if fid != "sixteen-bit" and cell == "#" and variant in {2, 3}:
                        pygame.draw.line(
                            surf,
                            (*PALETTE["accent"], 110),
                            (px + (4 + variant) * vs, py + 6 * vs),
                            (px + (9 + variant) * vs, py + 11 * vs),
                            max(1, vs),
                        )
                if cell == "B":
                    block = self._fid(sim, "items/block.png")
                    surf.blit(self._fit(block, (tw, tw)), (px, py))
        for entity in sim.entities:
            if not entity.alive or entity.kind != "wind-column":
                continue
            px = int(entity.x * tw - cam_x * vs)
            py = int(entity.y * tw - cam_y * vs)
            width = int(float(entity.extra.get("width") or 1) * tw)
            height = int(float(entity.extra.get("height") or 6) * tw)
            try:
                wind = self._fid(sim, "effects/wind-column.png")
                draw_width = max(width + 8 * vs, round(width * 1.9))
                gust = self._fit(wind, (draw_width, max(1, height)))
                # A slow alternating mirror gives the modeled ribbons a
                # second silhouette without inventing a duplicate asset.
                if ((sim.tick + int(entity.x) * 7) // 9) % 2:
                    gust = pygame.transform.flip(gust, True, False)
                sway = round(__import__("math").sin((sim.tick + int(entity.x) * 7) / 12.0) * vs)
                surf.blit(gust, (px - (draw_width - width) // 2 + sway, py))
            except Exception:
                veil = Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
                for line in range(4):
                    lx = int((line + 1) * width / 5)
                    offset = int((sim.tick * (2 + line) + line * 13) % max(1, height))
                    pygame.draw.line(veil, (*SHIFT_CYAN, 190), (lx, height - offset), (lx, max(0, height - offset - 10 * vs)), max(1, vs))
                surf.blit(veil, (px, py))
            pygame.draw.arc(surf, BRONZE, (px, py + height - 5 * vs, width, 8 * vs), 0.0, 3.14, max(1, vs))
        for entity in sim.entities:
            if not entity.alive or entity.kind not in {"tilt-platform", "moving-platform"}:
                continue
            span = max(4, int(entity.extra.get("width") or 4))
            plank = Surface((span * tw, 7 * vs), pygame.SRCALPHA)
            try:
                deck_tile = self._fit(self._fid(sim, f"tiles/{pal}_=.png"), (tw, 7 * vs))
                for segment in range(span):
                    plank.blit(deck_tile, (segment * tw, 0))
                pygame.draw.rect(plank, BRONZE, plank.get_rect(), max(1, vs))
            except Exception:
                plank.fill((48, 40, 35, 255))
                pygame.draw.rect(plank, BRONZE, plank.get_rect(), max(1, vs))
            angle = -__import__("math").degrees(float(entity.extra.get("angle") or 0.0))
            if entity.kind == "tilt-platform":
                plank = pygame.transform.rotate(plank, angle)
            pivot = float(entity.extra.get("pivot", span / 2 - 0.5)) + 0.5
            center_x = int((entity.x * TILE + pivot * TILE - cam_x) * vs)
            center_y = int((entity.y * TILE - cam_y) * vs)
            surf.blit(plank, (center_x - plank.get_width() // 2, center_y - plank.get_height() // 2))
            if entity.kind == "tilt-platform":
                pygame.draw.circle(surf, PALETTE["yellow"], (center_x, center_y), 3 * vs)
                pygame.draw.circle(surf, PALETTE["dark"], (center_x, center_y), max(1, vs))
        # Ladder rails must remain readable where a lift or seesaw crosses
        # their route. Draw both ordinary and walkable-deck ladder glyphs in a
        # small foreground tile pass, after dynamic platforms but before actors.
        for _x, _y, px, py, cell in deferred_ladders:
            key = f"tiles/{pal}_{cell}.png"
            try:
                tile = self._fid(sim, key)
            except Exception:
                try:
                    tile = self._load(key)
                except Exception:
                    pygame.draw.rect(surf, PALETTE["brown"], (px, py, tw, tw))
                    continue
            surf.blit(self._fit(tile, (tw, tw)), (px, py))
        for entity in sim.entities:
            if not entity.alive:
                continue
            px = int(entity.x * tw - cam_x * vs + float(entity.extra.get("offset_x") or 0.0) * vs)
            py = int(entity.y * tw - cam_y * vs + float(entity.extra.get("offset_y") or 0.0) * vs)
            if entity.kind == "penguin":
                surf.blit(self._fit(self._fid(sim, "items/penguin.png"), (tw, tw)), (px, py))
            elif entity.kind == "logo":
                bob = int(vs * __import__("math").sin(sim.tick / 8))
                logo = self._fid(sim, "items/omarchy-logo.png")
                if fid != "sixteen-bit":
                    glow = pygame.Surface((tw + 4 * vs, tw + 4 * vs), pygame.SRCALPHA)
                    glow.fill((158, 206, 106, 40))
                    surf.blit(glow, (px - 2 * vs, py - 2 * vs + bob))
                surf.blit(self._fit(logo, (tw, tw)), (px, py + bob))
            elif entity.kind == "item":
                try:
                    item_name = str(entity.extra.get("item") or "logic-bomb")
                    icon = self._fid(sim, f"items/{item_name}.png")
                    surf.blit(self._fit(icon, (tw, tw)), (px, py))
                except Exception:
                    pygame.draw.rect(surf, PALETTE["cyan"], (px + 4 * vs, py + 4 * vs, 8 * vs, 8 * vs))
            elif entity.kind == "network":
                protocol = str(entity.extra.get("protocol") or "ethernet")
                rel = "items/patch-cable.png" if protocol == "ethernet" else "items/fork-beacon.png"
                try:
                    hardware = self._fid(sim, rel)
                    size = 20 * vs
                    surf.blit(self._fit(hardware, (size, size)), (px + tw // 2 - size // 2, py + tw - size))
                except Exception:
                    pygame.draw.rect(surf, SHIFT_CYAN, (px + 3 * vs, py + 3 * vs, 10 * vs, 10 * vs), max(1, vs))
                pulse = 5 * vs + int(2 * vs * __import__("math").sin(sim.tick / 5))
                pygame.draw.circle(surf, SHIFT_CYAN, (px + tw // 2, py + tw // 2), max(vs, pulse), max(1, vs))
            elif entity.kind == "omega-block":
                letter = str(entity.extra.get("letter") or "?")
                plate = Surface((12 * vs, 10 * vs), pygame.SRCALPHA)
                plate.fill((5, 8, 14, 226))
                pygame.draw.rect(plate, BRONZE, plate.get_rect(), max(1, vs))
                surf.blit(plate, (px + 2 * vs, py + 3 * vs))
                self.fit_text(
                    surf,
                    letter,
                    (px // vs + 2, py // vs + 2, 12, 11),
                    PALETTE["bright_green"],
                    align="center",
                    max_size=9,
                    min_size=7,
                    bold=True,
                )
            elif entity.kind == "omega-door":
                try:
                    door = self._fid(sim, "items/omega-door.png")
                    dh = 52 * vs
                    dw = max(24 * vs, round(door.get_width() / max(1, door.get_height()) * dh))
                    door = self._fit(door, (dw, dh))
                    bob = round(__import__("math").sin(sim.tick / 11.0) * vs)
                    surf.blit(door, (px + tw // 2 - dw // 2, py + tw - dh + bob))
                    pygame.draw.ellipse(surf, (*LIME_MARK, 150), (px - 6 * vs, py + 11 * vs, tw + 12 * vs, 7 * vs), max(1, vs))
                except Exception:
                    pygame.draw.rect(surf, LIME_MARK, (px - 4 * vs, py - 30 * vs, tw + 8 * vs, 46 * vs), max(2, vs))
            elif entity.kind == "cow-cannon":
                try:
                    barrel_width = round(CANNON_BARREL_WIDTH * vs)
                    barrel_height = round(CANNON_BARREL_HEIGHT * vs)
                    base_width = round(CANNON_BASE_WIDTH * vs)
                    base_height = round(CANNON_BASE_HEIGHT * vs)
                    barrel = self._fit(
                        self._fid(sim, "items/cow-cannon-barrel.png"),
                        (barrel_width, barrel_height),
                    ).copy()
                    base = self._fit(
                        self._fid(sim, "items/cow-cannon-base.png"),
                        (base_width, base_height),
                    )
                    panel = pygame.Rect(
                        round(barrel_width * 0.42),
                        round(barrel_height * 0.49),
                        round(barrel_width * 0.32),
                        round(barrel_height * 0.20),
                    )
                    pygame.draw.rect(barrel, (7, 10, 15, 242), panel, border_radius=max(1, 2 * vs))
                    pygame.draw.rect(barrel, BRONZE, panel, max(1, vs), border_radius=max(1, 2 * vs))
                    if sim.cannon_loaded:
                        count = min(
                            6,
                            math.ceil(sim.cannon_charge_ticks * 6 / max(1, CANNON_MAX_CHARGE_TICKS)),
                        )
                        label = "LAUNCH"[:count]
                        if label:
                            full_power = sim.cannon_charge_ticks >= CANNON_MAX_CHARGE_TICKS
                            label_color = (
                                (255, 255, 255)
                                if full_power and (sim.tick // 6) % 2
                                else LIME_MARK
                            )
                            glyph = self._font(logical_size=6, bold=True).render(label, True, label_color)
                            if glyph.get_width() > panel.width - 4 * vs:
                                glyph = pygame.transform.smoothscale(
                                    glyph,
                                    (panel.width - 4 * vs, max(vs, panel.height - 4 * vs)),
                                )
                            barrel.blit(glyph, glyph.get_rect(center=panel.center))
                    else:
                        mark = self._load("ui/omarchy-wordmark.png")
                        mark = self._fit(mark, (max(1, panel.width - 8 * vs), max(1, panel.height - 6 * vs)))
                        barrel.blit(mark, mark.get_rect(center=panel.center))

                    angle = float(entity.extra.get("angle", sim.cannon_angle))
                    rotated = pygame.transform.rotozoom(barrel, angle, 1.0)
                    geometry = cow_cannon_geometry(entity, angle)
                    pivot_x, pivot_y = geometry["pivot"]
                    center_dx = CANNON_BARREL_WIDTH / 2 - CANNON_BARREL_WIDTH * CANNON_BARREL_PIVOT[0]
                    center_dy = CANNON_BARREL_HEIGHT / 2 - CANNON_BARREL_HEIGHT * CANNON_BARREL_PIVOT[1]
                    radians = math.radians(angle)
                    rotated_dx = center_dx * math.cos(radians) + center_dy * math.sin(radians)
                    rotated_dy = -center_dx * math.sin(radians) + center_dy * math.cos(radians)
                    center = (
                        round((pivot_x + rotated_dx - cam_x) * vs),
                        round((pivot_y + rotated_dy - cam_y) * vs),
                    )
                    ground_y = round(((entity.y + 1) * TILE - cam_y) * vs)
                    shadow_x = round((entity.x * TILE + 35 - cam_x) * vs)
                    pygame.draw.ellipse(
                        surf,
                        (0, 0, 3, 155),
                        (shadow_x - 34 * vs, ground_y - 5 * vs, 68 * vs, 7 * vs),
                    )
                    # The barrel rotates behind a stationary, ground-locked
                    # carriage. Drawing the base second also masks the axle.
                    surf.blit(rotated, rotated.get_rect(center=center))
                    base_x, base_y = geometry["base"]
                    surf.blit(
                        base,
                        (
                            round((base_x - cam_x) * vs),
                            round((base_y - cam_y) * vs),
                        ),
                    )
                    if sim.cannon_launch_active and sim.cannon_launch_ticks < 8:
                        muzzle_x, muzzle_y = geometry["muzzle"]
                        flare = (
                            round((muzzle_x - cam_x) * vs),
                            round((muzzle_y - cam_y) * vs),
                        )
                        pygame.draw.circle(surf, (255, 238, 174), flare, (10 - sim.cannon_launch_ticks) * vs)
                        pygame.draw.circle(surf, SHIFT_CYAN, flare, max(2, (7 - sim.cannon_launch_ticks) * vs))
                except Exception:
                    pygame.draw.rect(surf, BRONZE, (px, py - 5 * tw, 9 * tw, 6 * tw), max(2, vs))
            elif entity.kind == "boss-gate":
                state = str(entity.extra.get("state") or "open")
                height_cells = int(entity.extra.get("height") or 6)
                total = max(1, int(entity.extra.get("close_total") or 12))
                remaining = max(0, int(entity.extra.get("closing_ticks") or 0))
                closed = 1.0 if state == "closed" else (0.0 if state == "open" else 1.0 - remaining / total)
                top_y = (entity.y - height_cells + 1) * tw - cam_y * vs
                gate_y = round(top_y - (1.0 - closed) * height_cells * tw)
                try:
                    panel = self._fit(self._fid(sim, f"tiles/{pal}_G.png"), (tw, tw))
                    for segment in range(height_cells):
                        surf.blit(panel, (px, gate_y + segment * tw))
                except Exception:
                    pygame.draw.rect(surf, BRONZE, (px, gate_y, tw, height_cells * tw))
                opening_h = height_cells * tw
                rail_w = max(2 * vs, tw // 7)
                # The raised door still needs an unmistakable frame; otherwise
                # a fully open panel vanishes into the modeled background.
                pygame.draw.rect(surf, (40, 30, 24), (px - rail_w, int(top_y), rail_w, opening_h))
                pygame.draw.rect(surf, (232, 186, 124), (px - rail_w, int(top_y), rail_w, opening_h), max(1, vs))
                pygame.draw.rect(surf, (40, 30, 24), (px + tw, int(top_y), rail_w, opening_h))
                pygame.draw.rect(surf, (232, 186, 124), (px + tw, int(top_y), rail_w, opening_h), max(1, vs))
                pygame.draw.rect(surf, PALETTE["yellow"], (px - rail_w, int(top_y) - 3 * vs, tw + rail_w * 2, 4 * vs))
                lamp = (158, 206, 106) if state == "open" else (247, 118, 142)
                pygame.draw.circle(surf, lamp, (px + tw // 2, int(top_y) - vs), max(2 * vs, tw // 9))
            elif entity.kind in {"enemy", "boss"}:
                if entity.kind == "boss":
                    boss_id = entity.extra.get("boss") or CAMPAIGN_ROSTER[sim.chapter_index].boss.id
                    goliath_stage = str(entity.extra.get("goliath_stage") or "")
                    if boss_id == "goliath" and goliath_stage == "penguin":
                        rel = "bosses/goliath-cyborg-penguin.png"
                    elif boss_id == "goliath" and goliath_stage == "minions":
                        rel = "bosses/goliath.png"
                    else:
                        rel = f"bosses/{boss_id}-converted.png" if entity.extra.get("converted") else f"bosses/{boss_id}.png"
                else:
                    variant = str(entity.extra.get("variant") or "dogma-sprite")
                    suffix = "-converted" if entity.extra.get("converted") else ""
                    rel = f"enemies/{variant}{suffix}.png"
                try:
                    image = self._fid(sim, rel)
                except Exception:
                    try:
                        image = self._load(rel)
                    except Exception:
                        continue
                variant = str(entity.extra.get("variant") or "")
                animal_height = 30 if variant == "cow" else (34 if variant == "llama" else ENEMY_WORLD_HEIGHT)
                boss_height = 72 if entity.extra.get("goliath_stage") == "penguin" else BOSS_WORLD_HEIGHT
                eh = int(animal_height * vs) if entity.kind == "enemy" else int(boss_height * vs)
                ew = max(1, int(image.get_width() / max(1, image.get_height()) * eh))
                image = self._fit(image, (ew, eh))
                phase = float(entity.extra.get("phase") or (sim.tick + int(entity.x) * 5) * 0.08)
                angle = 0.0
                scale_x = 1.0
                scale_y = 1.0
                if entity.kind == "enemy":
                    behavior = str(entity.extra.get("behavior") or "jump")
                    cadence = math.sin(phase * 2.2)
                    if behavior == "jump":
                        airborne = float(entity.extra.get("offset_y") or 0.0) < -1.0
                        scale_x = 0.96 if airborne else 1.0 + max(0.0, cadence) * 0.07
                        scale_y = 1.05 if airborne else 1.0 - max(0.0, cadence) * 0.06
                        angle = cadence * 1.7
                    elif "fly" in behavior:
                        scale_x = 1.0 + cadence * 0.035
                        scale_y = 1.0 - cadence * 0.035
                        angle = math.sin(phase * 1.35) * 5.0
                    else:
                        recoil = max(0.0, (int(entity.extra.get("cooldown") or 0) - 68) / 18.0)
                        scale_x = 1.0 + min(0.08, recoil * 0.04)
                        scale_y = 1.0 - min(0.06, recoil * 0.03)
                        angle = cadence * 2.2
                    if entity.extra.get("converted"):
                        scale_y += math.sin((sim.tick + int(entity.x) * 9) / 8.0) * 0.025
                else:
                    behavior = str(entity.extra.get("behavior") or "stamp-hop")
                    pulse = math.sin(phase * (2.6 if behavior == "charge" else 1.7))
                    scale_x = 1.0 + pulse * (0.045 if behavior != "amalgam" else 0.065)
                    scale_y = 1.0 - pulse * (0.035 if behavior != "hover" else 0.055)
                    angle = {
                        "stamp-hop": math.sin(phase * 2.0) * 2.5,
                        "hover": math.sin(phase * 1.4) * 4.5,
                        "charge": math.sin(phase * 3.0) * 3.5,
                        "phase": math.sin(phase * 2.2) * 7.0,
                        "orbit": math.sin(phase) * 9.0,
                        "amalgam": math.sin(phase * 1.8) * 5.0,
                        "cyber-penguin": math.sin(phase * 2.4) * 3.0,
                    }.get(behavior, 0.0)
                    if int(entity.extra.get("ability_flash") or 0) > 0:
                        scale_x += 0.07
                        scale_y += 0.07
                # Quantized transforms create readable authored beats without
                # resampling every Ultra sprite every frame. A bounded cache
                # keeps the animation inexpensive on the same modest hardware
                # targeted by the optimized CRT path.
                scale_x = round(scale_x * 50) / 50
                scale_y = round(scale_y * 50) / 50
                angle = round(angle)
                animated_size = (max(1, round(ew * scale_x)), max(1, round(eh * scale_y)))
                flip = entity.kind == "boss" and int(entity.extra.get("dir") or -1) > 0
                transform_key = (fid, rel, animated_size, angle, flip)
                transformed = self._actor_transform_cache.get(transform_key)
                if transformed is None:
                    transformed = (
                        pygame.transform.scale(image, animated_size)
                        if fid == "sixteen-bit"
                        else pygame.transform.smoothscale(image, animated_size)
                    )
                    if abs(angle) >= 1:
                        transformed = pygame.transform.rotate(transformed, angle)
                    if flip:
                        transformed = pygame.transform.flip(transformed, True, False)
                    if len(self._actor_transform_cache) >= 1024:
                        self._actor_transform_cache.clear()
                    self._actor_transform_cache[transform_key] = transformed
                image = transformed
                ew, eh = image.get_size()
                if entity.extra.get("phasing"):
                    image = image.copy()
                    image.set_alpha(105)
                if entity.extra.get("pit_corrupted"):
                    image = image.copy()
                    image.fill((255, 56, 64, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    pygame.draw.circle(
                        surf,
                        (150, 8, 18),
                        (px + tw // 2, py + tw // 2),
                        max(5 * vs, ew // 3),
                    )
                draw_at = (px + tw // 2 - ew // 2, py + tw - eh)
                if entity.kind == "boss" and int(entity.extra.get("ability_flash") or 0) > 0:
                    radius = max(12 * vs, ew // 2 + 4 * vs)
                    center = (px + tw // 2, py + tw - eh // 2)
                    pygame.draw.circle(surf, (*PALETTE["yellow"], 48), center, radius)
                    pygame.draw.circle(surf, PALETTE["yellow"], center, radius, max(1, vs))
                    ghost = image.copy()
                    ghost.set_alpha(62)
                    spread = (17 - int(entity.extra.get("ability_flash") or 0)) * vs
                    surf.blit(ghost, (draw_at[0] - spread, draw_at[1]))
                    surf.blit(ghost, (draw_at[0] + spread, draw_at[1]))
                surf.blit(image, draw_at)
        for p in getattr(sim, "particles", []):
            pygame.draw.rect(
                surf,
                p["color"],
                (int((p["x"] - cam_x) * vs), int((p["y"] - cam_y) * vs), 2 * vs, 2 * vs),
            )
        for popup in getattr(sim, "floaters", []):
            if popup.get("space") != "world":
                continue
            sx = int((float(popup["x"]) - cam_x) * vs)
            sy = int((float(popup["y"]) - cam_y) * vs)
            self.fit_text(surf, str(popup["text"]), (sx // vs - 24, sy // vs, 48, 10), tuple(popup.get("color") or PALETTE["yellow"]), align="center", max_size=8, min_size=6, bold=True)
        for shot in getattr(sim, "projectiles", []):
            item_name = str(shot.get("item") or "logic-bomb")
            sh = (12 if item_name == "penguin-flock" else 9) * vs
            try:
                icon = self._fid(sim, f"items/{item_name}.png")
                icon = self._fit(icon, (sh, sh))
                sx = int((shot["x"] - cam_x) * vs - sh / 2)
                sy = int((shot["y"] - cam_y) * vs - sh / 2)
                surf.blit(icon, (sx, sy))
                pygame.draw.line(surf, SHIFT_CYAN, (sx - int(shot.get("vx", 0) * vs), sy + sh // 2), (sx, sy + sh // 2), max(1, vs))
            except Exception:
                if shot.get("ally"):
                    sx = int((float(shot["x"]) - cam_x) * vs)
                    sy = int((float(shot["y"]) - cam_y) * vs)
                    pygame.draw.circle(surf, (18, 38, 30), (sx, sy), 5 * vs)
                    pygame.draw.circle(surf, LIME_MARK, (sx, sy), 3 * vs)
                    pygame.draw.circle(surf, SHIFT_CYAN, (sx, sy), max(1, vs))
        for shot in getattr(sim, "enemy_projectiles", []):
            sx = int((float(shot["x"]) - cam_x) * vs)
            sy = int((float(shot["y"]) - cam_y) * vs)
            radius = max(2, 3 * vs)
            style = str(shot.get("style") or "")
            outer, inner = {
                "forms": ((100, 74, 42), PALETTE["yellow"]),
                "version-volley": ((22, 84, 52), LIME_MARK),
                "banner-wave": ((102, 30, 40), PALETTE["accent"]),
                "lock-pulse": ((34, 72, 118), SHIFT_CYAN),
                "gravity-shard": ((68, 28, 102), GUM_PURPLE),
                "argument-storm": ((116, 20, 28), PALETTE["red"]),
                "malware-fish": ((62, 24, 84), (214, 92, 255)),
            }.get(style, ((50, 110, 150), SHIFT_CYAN))
            pygame.draw.circle(surf, outer, (sx, sy), radius + 2 * vs)
            pygame.draw.circle(surf, inner, (sx, sy), radius)
            pygame.draw.circle(surf, (245, 245, 248), (sx, sy), max(1, vs))
        if sim.scene in {"flight", "edit"}:
            self._edit_ghost(surf, sim, cam_x, cam_y)
        if sim.scene in {"flight", "edit", "turn"} or sim.combat is not None or sim.cannon_loaded:
            return
        who = "custom" if sim.world and sim.world.character.get("kind") == "custom" else "david"
        frame = sim.side_sprite_frame()
        try:
            sprite = self._fid(sim, f"characters/{who}_{frame}.png")
        except Exception:
            legacy = "sixteen-bit"
            sprite = self._load(f"characters/{who}_{legacy}_side-idle.png")
        target_h = CHAR_WORLD_HEIGHT * vs
        nh = target_h
        nw = max(1, int(sprite.get_width() / max(1, sprite.get_height()) * nh))
        sprite = self._fit(sprite, (nw, nh))
        if sim.body.facing < 0:
            sprite = pygame.transform.flip(sprite, True, False)
        feet_x, feet_y = sim.body.feet
        px = int((feet_x - cam_x) * vs - nw / 2)
        py = int((feet_y - cam_y) * vs - nh)
        if frame == "side-slide":
            # The low authored silhouette contains canvas breathing room. Drop
            # it into the platform plane so the bracing hand/hip read as a
            # surface slide rather than a low airborne kick.
            py += SLIDE_WORLD_DROP * vs
        surf.blit(sprite, (px, py))
        if sim.debug_hitboxes:
            pygame.draw.rect(
                surf,
                (80, 255, 120),
                (
                    int((sim.body.x - cam_x) * vs),
                    int((sim.body.y - cam_y) * vs),
                    int(sim.body.width * vs),
                    int(sim.body.height * vs),
                ),
                max(1, vs),
            )
        if pal == "front":
            try:
                # Each hardware island owns a complete foreground plane. No
                # runtime subsurface cut can expose an interior source seam.
                piece_index = min(3, int(getattr(sim, "map_index", 0)))
                foreground = self._fid(sim, f"bg/front/foreground-{piece_index + 1}.png")
                if foreground.get_size() != (self._iw, self._ih):
                    foreground = pygame.transform.smoothscale(foreground, (self._iw, self._ih))
                world_w = len(sim.tiles[0]) * TILE
                anchor = world_w * (0.44 + 0.08 * (piece_index % 2))
                ox = round((anchor - cam_x * 1.22) * vs - foreground.get_width() / 2)
                # This is a viewport-side foreground plane, not a floating
                # world prop. It stays registered at the ground camera and
                # descends only as the player/camera climbs above that datum.
                oy = foreground_parallax_y(cam_y, max_y, vs)
                surf.blit(foreground, (ox, oy))
            except Exception:
                pass

    def _edit_ghost(self, surf: Surface, sim: GameSim, cam_x: int, cam_y: int) -> None:
        ghost_data = sim.edit_player_ghost
        if not ghost_data or int(ghost_data.get("map_index", -1)) != sim.map_index:
            return
        who = "custom" if sim.world and sim.world.character.get("kind") == "custom" else "david"
        frame = str(ghost_data.get("frame") or "side-idle")
        try:
            sprite = self._fid(sim, f"characters/{who}_{frame}.png")
        except Exception:
            sprite = self._load(f"characters/{who}_sixteen-bit_side-idle.png")
        nh = CHAR_WORLD_HEIGHT * self._vs
        nw = max(1, int(sprite.get_width() / max(1, sprite.get_height()) * nh))
        sprite = self._fit(sprite, (nw, nh))
        if int(ghost_data.get("facing") or 1) < 0:
            sprite = pygame.transform.flip(sprite, True, False)
        sprite = pygame.transform.grayscale(sprite)
        sprite.set_alpha(138)
        feet_x = float(ghost_data["feet_x"])
        feet_y = float(ghost_data["feet_y"])
        px = int((feet_x - cam_x) * self._vs - nw / 2)
        py = int((feet_y - cam_y) * self._vs - nh)
        py += round(float(ghost_data.get("visual_drop") or 0.0) * self._vs)
        surf.blit(sprite, (px, py))

    def _hud(self, surf: Surface, sim: GameSim) -> None:
        bar = Surface((self._iw, 28 * self._vs), pygame.SRCALPHA)
        bar.fill((10, 12, 20, 200 if self._fid_cur == "sixteen-bit" else 220))
        surf.blit(bar, (0, 0))
        if self._fid_cur != "sixteen-bit":
            pygame.draw.line(surf, LIME_MARK, (0, 28 * self._vs), (self._iw, 28 * self._vs), self._vs)
        try:
            logo_name = "oligarchy-logo-hud.png" if sim.hud_wordmark == "OLIGARCHY" else "omarchy-logo-hud.png"
            logo = self._load(f"ui/{logo_name}")
            bounds = logo.get_bounding_rect(min_alpha=8)
            if bounds.width and bounds.height:
                logo = logo.subsurface(bounds).copy()
            target_w = 64 * self._vs
            target_h = 11 * self._vs
            scale = min(target_w / logo.get_width(), target_h / logo.get_height())
            logo = self._fit(logo, (max(1, round(logo.get_width() * scale)), max(1, round(logo.get_height() * scale))))
            surf.blit(logo, self._lp(5, 14))
        except Exception:
            self.fit_text(surf, sim.hud_wordmark, (5, 14, 64, 10), PALETTE["bright_green"], max_size=7, min_size=5, bold=True)
        self._omega_modifier(surf, 6 * self._vs, 2 * self._vs, sim.omega_letters)
        self.blit_text(surf, f"{sim.score:07d}", (76, 8), PALETTE["yellow"])
        if sim.combo_name and sim.combo_ticks > 0:
            self.fit_text(surf, sim.combo_name, (76, 18, 104, 7), LIME_MARK, max_size=5, min_size=4, bold=True)
        try:
            penguin = self._fid(sim, "items/penguin.png")
            surf.blit(self._fit(penguin, (14 * self._vs, 14 * self._vs)), self._lp(146, 6))
            self.blit_text(surf, f"{sim.penguins:02d}", (162, 8), PALETTE["fg"])
        except Exception:
            self.blit_text(surf, f"p{sim.penguins:02d}", (148, 8), PALETTE["fg"])

        # Two boxed loadout slots echo Zelda's immediately readable item/action
        # treatment while retaining Omarchy's own bronze terminal framing.
        for x, label in (
            (194, sim.prompt_binding("item", compact=True)),
            (252, sim.prompt_binding("action", compact=True)),
        ):
            pygame.draw.rect(surf, (42, 47, 64), self._lr(x, 3, 52, 22))
            pygame.draw.rect(surf, BRONZE if self._fid_cur == "ultra" else LIME_MARK, self._lr(x, 3, 52, 22), max(1, self._vs))
            self.fit_text(
                surf,
                label,
                (x + 2, 7, 14, 13),
                PALETTE["yellow"],
                align="center",
                max_size=7,
                min_size=4,
                bold=True,
            )
        try:
            item = sim.current_item
            icon = self._fid(sim, f"items/{item}.png")
            surf.blit(self._fit(icon, (16 * self._vs, 16 * self._vs)), self._lp(208, 6))
            pygame.draw.rect(surf, (20, 24, 31), self._lr(226, 8, 15, 10))
            pygame.draw.rect(surf, SHIFT_CYAN, self._lr(227, 9 + (8 - round(8 * sim.item_strength / 100)), 13, max(1, round(8 * sim.item_strength / 100))))
            pygame.draw.rect(surf, BRONZE, self._lr(226, 8, 15, 10), max(1, self._vs))
        except Exception:
            self.blit_text(surf, "--", (216, 9), PALETTE["fg"])
        try:
            kick = self._fid(sim, "items/kick.png")
            surf.blit(self._fit(kick, (17 * self._vs, 17 * self._vs)), self._lp(269, 6))
        except Exception:
            self.blit_text(surf, "K", (271, 8), PALETTE["cyan"])

        # Mega Man-style field telemetry stays at the viewport edges instead
        # of consuming another header slot. Player BS rises from the bottom;
        # an arena boss's resolve falls as direct side-view hits land.
        self._side_meter(surf, 3, 37, sim.player_bs, 100, "BS", PALETTE["red"])
        active_boss = next(
            (
                entity
                for entity in sim.entities
                if entity.kind == "boss"
                and entity.alive
                and not entity.extra.get("converted")
                and sim._boss_arena_ready(entity)
            ),
            None,
        )
        if active_boss is not None:
            hp = float(active_boss.extra.get("hp") or 0.0)
            maximum = max(1.0, float(active_boss.extra.get("max_hp") or BOSS_FIELD_HEALTH))
            label = "PENGUIN" if active_boss.extra.get("goliath_stage") == "penguin" else "BOSS"
            self._side_meter(surf, 310, 37, hp, maximum, label, PALETTE["yellow"], label_left=True)
        elif getattr(sim, "goliath_stage", "") == "minions":
            minions = [entity for entity in sim.entities if entity.extra.get("goliath_minion")]
            hp = sum(max(0.0, float(entity.extra.get("hp") or 0.0)) for entity in minions)
            maximum = sum(max(1.0, float(entity.extra.get("max_hp") or 5.0)) for entity in minions)
            self._side_meter(surf, 310, 37, hp, maximum, "MINIONS", PALETTE["yellow"], label_left=True)
        if sim.messages:
            foot = Surface((self._iw, 14 * self._vs), pygame.SRCALPHA)
            foot.fill((10, 12, 20, 220))
            surf.blit(foot, (0, 166 * self._vs))
            self.fit_text(surf, sim.messages[-1], (8, 167, 304, 12), PALETTE["yellow"], max_size=9, min_size=6)

    def _side_meter(
        self,
        surf: Surface,
        x: int,
        y: int,
        value: float,
        maximum: float,
        label: str,
        color: tuple[int, int, int],
        *,
        label_left: bool = False,
    ) -> None:
        # Fifteen four-pixel segments make the visible bar almost exactly 25%
        # shorter than the original 20-segment telemetry without changing its
        # width, anchoring, or fill direction.
        segments = 15
        segment_h = 4
        height = segments * segment_h + 3
        pygame.draw.rect(surf, (3, 5, 11), self._lr(x, y, 7, height))
        pygame.draw.rect(surf, BRONZE, self._lr(x, y, 7, height), max(1, self._vs))
        filled = max(0, min(segments, math.ceil(segments * float(value) / max(1.0, float(maximum)))))
        for index in range(filled):
            sy = y + height - 3 - (index + 1) * segment_h
            pygame.draw.rect(surf, color, self._lr(x + 2, sy, 3, segment_h - 1))
        label_x = x - 27 if label_left else x - 2
        label_w = 27 if label_left else 12
        self.fit_text(
            surf,
            label,
            (label_x, y - 8, label_w, 7),
            color,
            align="right" if label_left else "center",
            max_size=5,
            min_size=4,
            bold=True,
        )

    def _combat_action(self, surf: Surface, sim: GameSim) -> None:
        if not sim.combat:
            return
        self._battle_ui(surf, sim, tactical=False)

    def _battle_actor_blit(
        self,
        surf: Surface,
        sim: GameSim,
        image: Surface,
        xy: tuple[int, int],
        actor_id: str,
    ) -> None:
        """Ground and pulse the sprite whose queued turn is resolving."""

        active = sim.battle_actor == actor_id and sim.battle_flash_ticks > 0
        if active:
            pygame.draw.ellipse(
                surf,
                (96, 104, 52),
                pygame.Rect(
                    xy[0] - 5 * self._vs,
                    xy[1] + image.get_height() - 8 * self._vs,
                    image.get_width() + 10 * self._vs,
                    12 * self._vs,
                ),
            )
        surf.blit(image, xy)
        if active and (sim.battle_flash_ticks // 2) % 2 == 0:
            flash = image.copy()
            flash.fill((110, 100, 62, 0), special_flags=pygame.BLEND_RGBA_ADD)
            flash.set_alpha(150)
            surf.blit(flash, xy)

    def _battle_ui(self, surf: Surface, sim: GameSim, *, tactical: bool) -> None:
        """A staged, windowed JRPG encounter rather than portrait telemetry."""

        if not sim.combat:
            return
        battle = sim.combat
        foe = battle.foe
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((2, 4, 12, 112 if self._fid_cur == "ultra" else 142))
        surf.blit(shade, (0, 0))

        # Scenic battle stage: distant line, modeled floor, grounding shadows.
        stage_tint = Surface((self._iw, 88 * self._vs), pygame.SRCALPHA)
        stage_tint.fill((3, 6, 16, 88))
        surf.blit(stage_tint, (0, 24 * self._vs))
        for row, color in enumerate(((25, 34, 50), (22, 29, 42), (17, 22, 34), (12, 16, 26))):
            pygame.draw.polygon(
                surf,
                color,
                [self._lp(0, 78 + row * 9), self._lp(320, 70 + row * 10), self._lp(320, 112), self._lp(0, 112)],
            )
        pygame.draw.ellipse(surf, (4, 6, 12), self._lr(20, 96, 70, 12))
        pygame.draw.ellipse(surf, (4, 6, 12), self._lr(198, 94, 112, 14))

        self._panel(surf, (8, 5, 304, 20), fill=(7, 9, 17))
        title = f"{foe.name}  ·  ROUND {battle.round_index + 1:02d}"
        self.fit_text(surf, title, (18, 8, 224, 13), PALETTE["bright_green"], max_size=9, min_size=6, bold=True)
        self.fit_text(surf, f"FOCUS {battle.focus:02d}", (244, 8, 58, 13), SHIFT_CYAN, align="right", max_size=8, min_size=6)
        intent = str(battle.foe_intent or "entrench")
        counter = INTENT_COUNTERS.get(intent, "reason")
        self._panel(surf, (78, 27, 164, 15), fill=(11, 7, 16))
        self.fit_text(
            surf,
            f"INTENT: {intent.replace('-', ' ').upper()}  ·  READ: {counter.upper()}",
            (83, 30, 154, 9),
            PALETTE["yellow"],
            align="center",
            max_size=6,
            min_size=4,
            bold=True,
        )

        try:
            if battle.boss_id and foe.id == "goliath-cyborg-penguin":
                foe_rel = "bosses/goliath-cyborg-penguin.png"
            else:
                foe_rel = f"bosses/{battle.boss_id}.png" if battle.boss_id else f"enemies/{foe.id}.png"
            foe_img = self._fid(sim, foe_rel)
            fh = (82 if battle.boss_id else 58) * self._vs
            fw = max(1, round(foe_img.get_width() / max(1, foe_img.get_height()) * fh))
            foe_img = self._fit(foe_img, (fw, fh))
            self._battle_actor_blit(
                surf,
                sim,
                foe_img,
                (250 * self._vs - fw // 2, 104 * self._vs - fh),
                "foe",
            )
        except Exception:
            pass
        try:
            who = "custom" if sim.world and sim.world.character.get("kind") == "custom" else "david"
            # The battle asset is baked directly from the idle master.
            hero = self._fid(sim, f"characters/{who}_battle.png")
            hh = 66 * self._vs
            hw = max(1, round(hero.get_width() / max(1, hero.get_height()) * hh))
            hero = self._fit(hero, (hw, hh))
            # The player begins at the far-left of the formation, leaving the rest
            # of the player's field for recruited helpers.
            self._battle_actor_blit(
                surf,
                sim,
                hero,
                (52 * self._vs - hw // 2, 106 * self._vs - hh),
                "player",
            )
        except Exception:
            pass
        # Recruited sign carriers remain present in the encounter instead of
        # turning into invisible passive stat bonuses.
        companions = tuple(getattr(sim, "active_companions", ()))
        if len(companions) == 1:
            anchors = (126,)
        else:
            anchors = tuple(
                round(108 + index * 52 / max(1, len(companions) - 1))
                for index in range(len(companions))
            )
        for index, companion_id in enumerate(companions):
            try:
                ally = self._fid(sim, f"enemies/{companion_id}-converted.png")
                ah = 34 * self._vs
                aw = max(1, round(ally.get_width() / max(1, ally.get_height()) * ah))
                ally = self._fit(ally, (aw, ah))
                anchor_x = anchors[index] * self._vs
                anchor_y = (106 - (index % 2) * 5) * self._vs
                self._battle_actor_blit(
                    surf,
                    sim,
                    ally,
                    (anchor_x - aw // 2, anchor_y - ah),
                    companion_id,
                )
            except Exception:
                pass

        if sim.battle_actor:
            actor_label = {
                "player": f"{battle.player.name.upper()} ACTS",
                "foe": f"{foe.name.upper()} REPLIES",
                "justice-signaler": "JUSTICE SIGNALER ASSISTS",
                "detractabot": "DETRACTABOT ASSISTS",
                "cow": "COW ASSISTS",
                "llama": "LLAMA ASSISTS",
            }.get(sim.battle_actor, sim.battle_actor.replace("-", " ").upper())
            self.fit_text(
                surf,
                actor_label,
                (76, 44, 168, 10),
                PALETTE["yellow"],
                align="center",
                max_size=7,
                min_size=5,
                bold=True,
            )

        timeline = ("player",) + tuple(companions) + ("foe",)
        segment_w = max(18, 174 // max(1, len(timeline)))
        start_x = 73
        for index, actor in enumerate(timeline):
            active = sim.battle_actor == actor
            queued = any(str(stage.get("actor")) == actor for stage in getattr(sim, "battle_queue", []))
            color = PALETTE["yellow"] if active else (SHIFT_CYAN if queued else (52, 57, 72))
            x = start_x + index * segment_w
            pygame.draw.rect(surf, color, self._lr(x, 107, segment_w - 2, 4))
            if active and sim.battle_delay_ticks:
                remaining = max(1, round((segment_w - 3) * min(1.0, sim.battle_delay_ticks / 24)))
                pygame.draw.rect(surf, PALETTE["fg"], self._lr(x + 1, 108, remaining, 2))

        for popup in getattr(sim, "floaters", []):
            if popup.get("space") != "battle":
                continue
            x = 72 if popup.get("side") == "player" else 250
            y = int(popup.get("y", 42))
            self.fit_text(surf, str(popup["text"]), (x - 34, y, 68, 11), tuple(popup.get("color") or PALETTE["yellow"]), align="center", max_size=9, min_size=6, bold=True)

        self._panel(surf, (8, 114, 194, 61), fill=(7, 9, 18))
        self._panel(surf, (205, 114, 107, 61), fill=(7, 9, 18))
        self.fit_text(
            surf,
            battle.player.name.upper(),
            (18, 117, 168, 8),
            PALETTE["fg"],
            max_size=7,
            min_size=4,
            bold=True,
        )
        self.fit_text(surf, "BS METER", (18, 126, 50, 8), PALETTE["red"], max_size=7, min_size=5)
        pygame.draw.rect(surf, (38, 22, 32), self._lr(70, 127, 114, 6))
        pygame.draw.rect(surf, PALETTE["red"], self._lr(70, 127, max(1, round(114 * battle.player.bs / 100)), 6))
        meters = (("TRUST", foe.trust, LIME_MARK), ("DOGMA", foe.corruption, PALETTE["yellow"]))
        for i, (label, value, color) in enumerate(meters):
            y = 135 + i * 7
            self.fit_text(surf, label, (18, y, 38, 8), color, max_size=7, min_size=6)
            pygame.draw.rect(surf, (28, 32, 46), self._lr(58, y + 1, 126, 6))
            pygame.draw.rect(surf, color, self._lr(58, y + 1, max(1, round(126 * value / 100)), 6))
        log = battle.log[-1] if battle.log else f"{foe.name} is weighing the argument."
        self.wrapped_text(
            surf,
            log,
            (18, 151, 166, 21),
            PALETTE["fg"],
            max_lines=3,
            logical_size=6,
        )

        commands = (
            (sim.prompt_binding("jump", compact=True), "REASON"),
            (sim.prompt_binding("action", compact=True), "PATCH"),
            ("<", "FORK"),
            (">", "SHOW"),
            (sim.prompt_binding("item", compact=True), "ITEM"),
            (sim.prompt_binding("turn", compact=True), "REUSE"),
            (sim.prompt_binding("interact", compact=True), "RECRUIT"),
        )
        for i, (key, name) in enumerate(commands):
            col, row = divmod(i, 4)
            x = 211 + col * 48
            y = 122 + row * 11
            ready = name == "RECRUIT" and battle.foe_ready_to_recruit
            if ready:
                pygame.draw.rect(surf, LIME_MARK, self._lr(x - 1, y, 46, 10))
            color = PALETTE["dark"] if ready else PALETTE["cyan"]
            self.fit_text(surf, key, (x, y, 8, 10), PALETTE["yellow"] if not ready else color, align="center", max_size=7, min_size=5, bold=True)
            self.fit_text(surf, name, (x + 9, y, 36, 10), color, max_size=6, min_size=4)

    def _pause(self, surf: Surface, sim: GameSim) -> None:
        fid = self._fid_cur
        self._panel(surf, (36, 18, 248, 146), fill=(8, 10, 18) if fid != "sixteen-bit" else PALETTE["dark"])
        self.blit_text(surf, "PAUSED", (58, 32), PALETTE["bright_green"], fid=fid)
        disp = getattr(sim, "display", "clean")
        row_ids = sim.pause_rows()
        self.blit_text(surf, "SYSTEM + LOADOUT", (58, 44 if len(row_ids) > 4 else 47), GUM_PURPLE, fid=fid)
        crt = dict(sim.settings.get("crt") or {})
        values = {
            "fidelity": ("FIDELITY", fid),
            "display": ("DISPLAY", disp),
            "items": ("ITEMS", sim.current_item.replace("-", " ")),
            "controls": ("CONTROLS", "remap"),
            "reroll": ("NEW WORLD", "confirm"),
            "omega-code": ("OMEGA CODE", "export"),
        }
        row_h = 8 if len(row_ids) > 4 else 14
        start_y = 54 if len(row_ids) > 4 else 60
        for i, row_id in enumerate(row_ids):
            y = start_y + i * row_h
            active = sim.pause_cursor == i
            if active:
                pygame.draw.rect(surf, LIME_MARK, self._lr(56, y, 150, 8 if len(row_ids) > 4 else 12))
            color = PALETTE["dark"] if active else PALETTE["fg"]
            if row_id in {"scanlines", "curvature", "phosphor"}:
                key = {"scanlines": "scanline", "curvature": "curvatureControl", "phosphor": "phosphor"}[row_id]
                label = {"scanlines": "SCANLINES", "curvature": "CURVE", "phosphor": "PHOSPHOR"}[row_id]
                fallback = crt.get("intensity", 0.12) if key != "phosphor" else 0.12
                amount = max(0.0, min(1.0, float(crt.get(key, fallback))))
                self.fit_text(surf, f"> {label}" if active else f"  {label}", (59, y, 47, 8), color, max_size=7, min_size=5)
                pygame.draw.rect(surf, (28, 32, 46), self._lr(108, y + 2, 65, 4))
                pygame.draw.rect(surf, PALETTE["dark"] if active else SHIFT_CYAN, self._lr(108, y + 2, max(1, round(65 * amount)), 4))
                self.fit_text(surf, f"{round(amount * 100):02d}%", (176, y, 27, 8), color, align="right", max_size=6, min_size=5)
            else:
                label, value = values[row_id]
                compact = len(row_ids) > 4
                self.fit_text(
                    surf,
                    f"> {label}: {value}" if active else f"  {label}: {value}",
                    (59, y, 144, 8 if compact else 12),
                    color,
                    max_size=7 if compact else 8,
                    min_size=5,
                )
        try:
            who = "custom" if sim.world and sim.world.character.get("kind") == "custom" else "david"
            try:
                port = self._fid(sim, f"characters/{who}_portrait.png")
            except Exception:
                port = self._fid(sim, "characters/david_portrait.png")
            ph = 38 * self._vs
            portrait_box = self._lr(226, 38, 42, 44)
            pygame.draw.rect(surf, (18, 20, 32), portrait_box)
            pygame.draw.rect(surf, BRONZE if fid == "ultra" else LIME_MARK, portrait_box, self._vs)
            bounds = port.get_bounding_rect(min_alpha=16)
            if bounds.width and bounds.height:
                port = port.subsurface(bounds).copy()
            surf.blit(self._fit(port, (ph, ph)), (228 * self._vs, 41 * self._vs))
        except Exception:
            pass
        help_y = 128 if len(row_ids) > 8 else 119
        select_key = sim.prompt_binding("jump", compact=True)
        pause_key = sim.prompt_binding("pause", compact=True)
        directions = "D-pad" if sim.last_input_device == "gamepad" else "Arrows"
        self.fit_text(
            surf,
            f"{directions} change · {select_key} select · {pause_key} resume",
            (58, help_y, 204, 11),
            PALETTE["fg"],
            max_size=7,
            min_size=5,
        )
        if len(row_ids) <= 8:
            self.fit_text(
                surf,
                "Item menu · save/load · customize · mute",
                (58, help_y + 13, 204, 11),
                PALETTE["cyan"],
                max_size=7,
                min_size=5,
            )
        if sim.omega_text:
            self.fit_text(surf, "code ready", (198, 145, 64, 8), PALETTE["cyan"], align="right", max_size=6, min_size=5)

    def _remap(self, surf: Surface, sim: GameSim) -> None:
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((2, 4, 10, 190))
        surf.blit(shade, (0, 0))
        self._panel(surf, (10, 10, 300, 160), fill=(7, 9, 18))
        self.blit_text(surf, "CONTROL BINDINGS", (22, 20), PALETTE["bright_green"])
        device = "KEYBOARD" if sim.remap_device == "keyboard" else "GAMEPAD BUTTONS"
        slot = "ALT" if sim.remap_device == "keyboard" and sim.remap_slot else "PRIMARY"
        self.fit_text(
            surf,
            f"{device} · {slot}" if sim.remap_device == "keyboard" else device,
            (22, 34, 276, 11),
            PALETTE["cyan"],
            max_size=8,
            min_size=6,
            bold=True,
        )
        actions = sim.remap_actions
        rows_per_column = 6 if sim.remap_device == "keyboard" else 4
        for index, action in enumerate(actions):
            column, row = divmod(index, rows_per_column)
            x = 18 + column * 146
            y = 47 + row * 12
            selected = index == sim.remap_cursor
            if selected:
                pygame.draw.rect(surf, LIME_MARK, self._lr(x, y, 138, 11))
            color = PALETTE["dark"] if selected else PALETTE["fg"]
            label = ACTION_LABELS[action]
            binding = sim.binding_label(
                action,
                device=sim.remap_device,
                slot=sim.remap_slot,
                compact=True,
            )
            self.fit_text(
                surf,
                label,
                (x + 3, y, 100, 10),
                color,
                max_size=7,
                min_size=5,
            )
            self.fit_text(
                surf,
                binding,
                (x + 104, y, 30, 10),
                color,
                align="right",
                max_size=7,
                min_size=5,
                bold=True,
            )
        feedback = sim.remap_feedback or "Choose an action, then bind it."
        self.fit_text(
            surf,
            feedback,
            (20, 121, 280, 10),
            PALETTE["yellow"] if sim.remap_waiting else PALETTE["fg"],
            align="center",
            max_size=7,
            min_size=5,
        )
        if sim.remap_waiting:
            help_text = (
                (
                    "ESC cancels · Backspace clears alternate"
                    if sim.remap_slot == 1
                    else "ESC cancels capture"
                )
                if sim.remap_device == "keyboard"
                else "D-pad Left cancels capture"
            )
        else:
            help_text = (
                "Reuse: device · Left/Right: slot · Confirm: bind"
                if sim.remap_device == "keyboard"
                else "Reuse: device · Confirm: bind"
            )
        self.fit_text(
            surf,
            help_text,
            (18, 133, 284, 9),
            PALETTE["cyan"],
            align="center",
            max_size=6,
            min_size=4,
        )
        self.fit_text(
            surf,
            "Action: reset one · Item: reset all · Interact/Pause: back",
            (18, 142, 284, 9),
            PALETTE["accent"],
            align="center",
            max_size=6,
            min_size=4,
        )

    def _items(self, surf: Surface, sim: GameSim) -> None:
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((2, 4, 10, 176))
        surf.blit(shade, (0, 0))
        self._panel(surf, (14, 16, 292, 148))
        self.blit_text(surf, "SELECT LOADOUT", (34, 29), PALETTE["bright_green"])
        item_key = sim.prompt_binding("item", compact=True)
        action_key = sim.prompt_binding("action", compact=True)
        confirm_key = sim.prompt_binding("jump", compact=True)
        interact_key = sim.prompt_binding("interact", compact=True)
        self.blit_text(
            surf,
            f"{item_key} ITEM",
            (34, 44),
            PALETTE["cyan"] if sim.item_menu_row == 0 else PALETTE["fg"],
        )
        for i, item in enumerate(ITEMS):
            x = 34 + i * 31
            selected = sim.item_menu_row == 0 and sim.item_menu_cursor % len(ITEMS) == i
            owned = item in sim.inventory
            pygame.draw.rect(surf, (22, 25, 38), self._lr(x, 55, 28, 33))
            pygame.draw.rect(surf, LIME_MARK if selected else (70, 76, 96), self._lr(x, 55, 28, 33), max(1, self._vs))
            try:
                icon = self._fid(sim, f"items/{item}.png")
                if not owned:
                    icon = icon.copy()
                    icon.set_alpha(45)
                surf.blit(self._fit(icon, (20 * self._vs, 20 * self._vs)), self._lp(x + 4, 58))
            except Exception:
                pass
            self.blit_text(surf, str(sim.inventory.count(item)) if owned else "-", (x + 10, 78), PALETTE["yellow"] if owned else PALETTE.get("muted", (100, 104, 122)))
        item_name = ITEMS[sim.item_menu_cursor % len(ITEMS)].replace("-", " ") if sim.item_menu_row == 0 else sim.current_item.replace("-", " ")
        self.fit_text(surf, item_name, (34, 90, 252, 12), PALETTE["yellow"], max_size=9, min_size=6)

        self.blit_text(
            surf,
            f"{action_key} ATTACK",
            (34, 106),
            PALETTE["cyan"] if sim.item_menu_row == 1 else PALETTE["fg"],
        )
        for i, attack in enumerate(ATTACKS):
            x = 88 + i * 68
            selected = sim.item_menu_row == 1 and sim.item_menu_cursor % len(ATTACKS) == i
            if selected:
                pygame.draw.rect(surf, LIME_MARK, self._lr(x - 3, 105, 64, 14))
            self.fit_text(surf, attack.replace("-", " "), (x, 106, 58, 13), PALETTE["dark"] if selected else PALETTE["fg"], max_size=8, min_size=6)
        selected_name = (
            ATTACKS[sim.item_menu_cursor % len(ATTACKS)]
            if sim.item_menu_row == 1
            else ITEMS[sim.item_menu_cursor % len(ITEMS)]
        )
        self.fit_text(
            surf,
            f"equipped: {item_key} {sim.current_item.replace('-', ' ')} / {action_key} {sim.current_attack.replace('-', ' ')}",
            (34, 127, 252, 12),
            PALETTE["fg"],
            max_size=8,
            min_size=5,
        )
        self.fit_text(
            surf,
            f"{confirm_key} equip {selected_name}   {interact_key}/{item_key} back",
            (34, 137, 252, 11),
            PALETTE["cyan"],
            max_size=7,
            min_size=5,
        )

    def _customize(self, surf: Surface, sim: GameSim) -> None:
        pygame.draw.rect(surf, PALETTE["dark"], self._lr(16, 24, 288, 130))
        pygame.draw.rect(surf, PALETTE["cyan"], self._lr(16, 24, 288, 130), self._vs)
        self.blit_text(surf, "LIMITLESS", (24, 32), PALETTE["bright_green"])
        enabled = bool(sim.settings.get("limitlessEnabled"))
        self.fit_text(surf, "enabled" if enabled else "offline start-fresh", (24, 47, 270, 12), PALETTE["yellow"], max_size=9, min_size=6)
        status = sim.limitless_status or (
            f"{sim.prompt_binding('jump', compact=True)} query   "
            f"{sim.prompt_binding('interact', compact=True)} close"
        )
        self.fit_text(surf, status, (24, 67, 270, 12), PALETTE["fg"], max_size=9, min_size=6)
        receipt = sim.limitless_receipt or {}
        if receipt:
            self.fit_text(surf, f"adopted={receipt.get('adopted')} {receipt.get('treatment', '')}", (24, 87, 270, 12), PALETTE["cyan"], max_size=8, min_size=6)
            self.wrapped_text(surf, str(receipt.get("reason", "")), (24, 102, 270, 28), PALETTE["fg"], max_lines=2, logical_size=8)

    def _network(self, surf: Surface, sim: GameSim) -> None:
        """Multimedia interstitial for deterministic hardware traversal."""

        progress = max(0.0, min(1.0, 1.0 - sim.network_ticks / max(1, NETWORK_TICKS)))
        protocol_name = sim.network_protocol if sim.network_protocol in {"ethernet", "wifi"} else "ethernet"
        try:
            backdrop = self._fid(sim, f"ui/network-{protocol_name}.png")
            zoom = 1.0 + progress * 0.065
            scaled = self._fit(
                backdrop,
                (max(self._iw, round(self._iw * zoom)), max(self._ih, round(self._ih * zoom))),
            )
            wobble = round(__import__("math").sin(progress * 18.0) * self._vs) if protocol_name == "wifi" else 0
            surf.blit(scaled, ((self._iw - scaled.get_width()) // 2 + wobble, (self._ih - scaled.get_height()) // 2))
            shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
            shade.fill((0, 4, 10, 44))
            surf.blit(shade, (0, 0))
        except Exception:
            surf.fill((2, 5, 12))
        # The Ultra-derived foreground plate carries the dimensional socket or
        # radio hardware. Only packets remain live, preserving visual motion
        # without laying primitive geometry over the prerendered treatment.
        try:
            overlay = self._fid(sim, f"ui/network-{protocol_name}-overlay.png")
            pulse = 1.0 + __import__("math").sin(progress * 12.0) * 0.012
            overlay = self._fit(
                overlay,
                (max(1, round(self._iw * pulse)), max(1, round(self._ih * pulse))),
            )
            surf.blit(overlay, ((self._iw - overlay.get_width()) // 2, (self._ih - overlay.get_height()) // 2))
        except Exception:
            pass
        for index in range(12):
            phase = (progress * 1.8 + index / 12) % 1.0
            x = round(18 + phase * 284)
            wave = __import__("math").sin((phase + index * 0.17) * 6.283)
            y = round(88 + wave * (28 if sim.network_protocol == "wifi" else 13))
            color = PALETTE["yellow"] if index % 3 == 0 else SHIFT_CYAN
            pygame.draw.rect(surf, color, self._lr(x, y, 3, 3))
        self._panel(surf, (18, 10, 284, 24), fill=(5, 8, 17))
        protocol = sim.network_protocol.upper() or "NETWORK"
        phase_label = "NEGOTIATING" if progress < 0.34 else ("ROUTING" if progress < 0.68 else "TRAVERSING")
        self.fit_text(surf, f"{protocol} · {phase_label}", (26, 15, 268, 14), PALETTE["bright_green"], align="center", max_size=10, min_size=6, bold=True)
        self._panel(surf, (28, 136, 264, 32), fill=(5, 8, 17))
        self.fit_text(surf, sim.network_operation, (38, 140, 244, 12), PALETTE["fg"], align="center", max_size=8, min_size=5)
        pygame.draw.rect(surf, (24, 30, 44), self._lr(40, 156, 240, 5))
        pygame.draw.rect(surf, SHIFT_CYAN, self._lr(40, 156, max(2, round(240 * progress)), 5))

    def _flight(self, surf: Surface, sim: GameSim) -> None:
        preset = sim.quality if sim.quality in {"eight-bit", "sixteen-bit", "clean-pixel", "crt", "high"} else "clean-pixel"
        who = "david"
        if sim.world and sim.world.character.get("kind") == "custom":
            who = "custom"
        try:
            sprite = self._fid(sim, f"characters/{who}_flight.png")
        except Exception:
            sprite = self._load(f"characters/{who}_{preset}_flight.png")
        from .sim import FLIGHT_TICKS

        remaining = max(1, sim.flight_ticks)
        progress = (FLIGHT_TICKS - remaining) / max(1, FLIGHT_TICKS - 1)
        if getattr(sim, "flight_direction", "out") == "in":
            progress = 1.0 - progress
        base_h = CHAR_WORLD_HEIGHT * self._vs
        ots, ots_x, ots_y = self._ots_layout(sim)
        ots_bounds = ots.get_bounding_rect(min_alpha=8)
        end_x = ots_x + ots_bounds.centerx
        end_y = ots_y + ots_bounds.bottom
        nh = max(8, round(base_h + (ots.get_height() - base_h) * progress))
        nw = max(8, int(sprite.get_width() / max(1, sprite.get_height()) * nh))
        sprite = self._fit(sprite, (nw, nh))
        sprite_bounds = sprite.get_bounding_rect(min_alpha=8)
        if sim.body is not None:
            feet_x, feet_y = sim.body.feet
            start_x = int((feet_x - sim.cam_x) * self._vs)
            start_y = int((feet_y - sim.cam_y) * self._vs)
        else:
            start_x, start_y = self._iw // 2, self._ih // 2
        cx = round(start_x + (end_x - start_x) * progress)
        cy = round(start_y + (end_y - start_y) * progress)
        # Anchor the visible silhouette, not its transparent source canvas.
        # The final flight frame and the OTS edit frame now share the exact
        # same centerline and bottom edge, eliminating their former snap.
        surf.blit(sprite, (cx - sprite_bounds.centerx, cy - sprite_bounds.bottom))
        label = "flying back into play" if getattr(sim, "flight_direction", "out") == "in" else "flying into edit view"
        self.blit_text(surf, label, (8, 164), PALETTE["bright_green"])

    def _ots(self, surf: Surface, sim: GameSim) -> None:
        fid = self._active_fid(sim)
        ots = self._ots_sprite(sim)
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 50 if fid == "sixteen-bit" else 80))
        surf.blit(shade, (0, 0))
        max_h = 96 * self._vs
        if ots.get_height() > max_h:
            scale = max_h / ots.get_height()
            ots = pygame.transform.smoothscale(ots, (int(ots.get_width() * scale), max_h))
        _, ots_x, ots_y = self._ots_layout(sim, ots)
        surf.blit(ots, (ots_x, ots_y))
        tile = ("=", "L", "^")[getattr(sim, "edit_tile_index", 0) % 3]
        try:
            pal = str(sim.chapter.get("palette") or CAMPAIGN_ROSTER[sim.chapter_index].palette)
            preview = self._fid(sim, f"tiles/{pal}_{tile}.png")
            preview = self._fit(preview, (16 * self._vs, 16 * self._vs))
            surf.blit(preview, self._lp(88, 146))
            pygame.draw.rect(surf, PALETTE["bright_green"], self._lr(88, 146, 16, 16), max(1, self._vs))
        except Exception:
            pass
        self.fit_text(
            surf,
            f"EDIT {tile}  {sim.prompt_binding('turn', compact=True)} tile · "
            f"{sim.prompt_binding('action', compact=True)} place · "
            f"{sim.prompt_binding('item', compact=True)} erase · "
            f"{sim.prompt_binding('jump', compact=True)} seal",
            (108, 149, 204, 13),
            PALETTE["bright_green"],
            max_size=8,
            min_size=6,
        )
        self.fit_text(
            surf,
            f"{sim.prompt_binding('interact', compact=True)} undo/cancel · "
            f"{sim.prompt_binding('customize', compact=True)} reset · {sim.edit_budget_used}/24",
            (90, 163, 222, 12),
            PALETTE["cyan"],
            max_size=7,
            min_size=6,
        )
        cx, cy = sim.edit_cursor
        if sim.body:
            cam_x = int(sim.cam_x)
            cam_y = int(sim.cam_y)
            vs = self._vs
            tw = TILE * vs
            rx = int(cx * tw - cam_x * vs)
            ry = int(cy * tw - cam_y * vs)
            blocked = (cx, cy) in sim.edit_reserved_cells()
            cursor_color = PALETTE["red"] if blocked else PALETTE["bright_green"]
            pygame.draw.rect(surf, cursor_color, (rx, ry, tw, tw), vs)
            if fid != "sixteen-bit":
                overlay = Surface((tw, tw), pygame.SRCALPHA)
                overlay.fill((247, 118, 142, 82) if blocked else (158, 206, 106, 60))
                surf.blit(overlay, (rx, ry))
            if blocked:
                pygame.draw.line(surf, cursor_color, (rx + 3 * vs, ry + 3 * vs), (rx + tw - 3 * vs, ry + tw - 3 * vs), max(1, vs))
                pygame.draw.line(surf, cursor_color, (rx + tw - 3 * vs, ry + 3 * vs), (rx + 3 * vs, ry + tw - 3 * vs), max(1, vs))

    def _ots_sprite(self, sim: GameSim) -> Surface:
        who = "custom" if sim.world and sim.world.character.get("kind") == "custom" else "david"
        try:
            return self._fid(sim, f"characters/{who}_ots.png")
        except Exception:
            return self._load(f"characters/{who}_sixteen-bit_ots.png")

    def _ots_layout(self, sim: GameSim, ots: Surface | None = None) -> tuple[Surface, int, int]:
        ots = ots or self._ots_sprite(sim)
        max_h = 96 * self._vs
        if ots.get_height() > max_h:
            scale = max_h / ots.get_height()
            ots = self._fit(ots, (max(1, int(ots.get_width() * scale)), max_h))
        return ots, 4 * self._vs, self._ih - ots.get_height()

    def _turn(self, surf: Surface, sim: GameSim) -> None:
        self._battle_ui(surf, sim, tactical=True)

    def _oligarchy(self, surf: Surface, sim: GameSim) -> None:
        surf.fill(PALETTE["dark"])
        try:
            logo = self._load("ui/oligarchy-logo-hud.png")
            bounds = logo.get_bounding_rect(min_alpha=8)
            if bounds.width and bounds.height:
                logo = logo.subsurface(bounds).copy()
            max_w, max_h = 240 * self._vs, 44 * self._vs
            scale = min(max_w / logo.get_width(), max_h / logo.get_height())
            logo = self._fit(logo, (max(1, round(logo.get_width() * scale)), max(1, round(logo.get_height() * scale))))
            surf.blit(logo, ((self._iw - logo.get_width()) // 2, 54 * self._vs))
        except Exception:
            self.blit_text(surf, "OLIGARCHY", (90, 70), PALETTE["bright_green"])
        self.blit_text(surf, "FORMED", (130, 102), PALETTE["cyan"])
        self.blit_text(surf, "Elite capital. Public code.", (70, 114), PALETTE["fg"])
        self.fit_text(surf, "The extra letters arrived as packages.", (28, 138, 264, 14), PALETTE["yellow"], max_size=9, min_size=6, align="center")

    def _chapter_complete(self, surf: Surface, sim: GameSim) -> None:
        spec = CAMPAIGN_ROSTER[sim.chapter_index]
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surf.blit(shade, (0, 0))
        self._panel(surf, (27, 17, 266, 146), fill=(7, 9, 16))
        self.fit_text(
            surf,
            f"CHAPTER {sim.chapter_index + 1} COMPLETE",
            (46, 33, 228, 18),
            PALETTE["bright_green"],
            align="center",
            max_size=13,
            min_size=8,
            bold=True,
        )
        self.fit_text(
            surf,
            spec.name.upper(),
            (46, 54, 228, 12),
            PALETTE["cyan"],
            align="center",
            max_size=9,
            min_size=6,
        )
        self.wrapped_text(
            surf,
            spec.boss.converted_line,
            (46, 70, 228, 20),
            PALETTE["fg"],
            max_lines=2,
            logical_size=7,
        )
        self.fit_text(
            surf,
            f"SCORE {sim.score:07d}   PENGUINS {sim.penguins:02d}",
            (46, 92, 228, 12),
            PALETTE["yellow"],
            align="center",
            max_size=9,
            min_size=6,
        )
        jump = self._binding_pair(sim, "jump")
        action = self._binding_pair(sim, "action")
        turn = self._binding_pair(sim, "turn")
        self.fit_text(
            surf,
            f"{jump} credits   {action} save",
            (46, 109, 228, 11),
            PALETTE["fg"],
            align="center",
            max_size=8,
            min_size=6,
        )
        self.fit_text(
            surf,
            (
                "NATIVE BUILD HAS DEVELOPMENT CHAPTERS"
                if sim.web_chapter_one
                else f"{turn} {'CONTINUE DEVELOPMENT CHAPTERS' if sim.chapter_index == 0 else 'RETURN TO ROUTE MAP'}"
            ),
            (42, 123, 236, 11),
            PALETTE["accent"],
            align="center",
            max_size=8,
            min_size=6,
        )

    def _reroll_confirm(self, surf: Surface, sim: GameSim) -> None:
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 165))
        surf.blit(shade, (0, 0))
        self._panel(surf, (34, 22, 252, 136), fill=(7, 9, 16))
        self.fit_text(surf, "REROLL WORLD?", (48, 36, 224, 17), PALETTE["yellow"], align="center", max_size=12, min_size=8, bold=True)
        self.wrapped_text(
            surf,
            "Archive this world. Keep character, settings and converted capabilities. Reset chapter progress, score, items and penguins.",
            (51, 58, 218, 31),
            PALETTE["fg"],
            max_lines=3,
            logical_size=7,
        )
        self.fit_text(surf, sim.reroll_seed_preview(), (49, 92, 222, 11), PALETTE["cyan"], align="center", max_size=8, min_size=5)
        for yes, x, label in ((False, 83, "NO"), (True, 179, "YES")):
            active = bool(sim.reroll_confirm_yes) == yes
            fill = LIME_MARK if active else (31, 36, 49)
            color = PALETTE["dark"] if active else PALETTE["fg"]
            pygame.draw.rect(surf, fill, self._lr(x, 106, 58, 19))
            pygame.draw.rect(surf, BRONZE, self._lr(x, 106, 58, 19), max(1, self._vs))
            self.fit_text(surf, label, (x, 110, 58, 10), color, align="center", max_size=8, min_size=6, bold=True)
        jump = self._binding_pair(sim, "jump")
        interact = self._binding_pair(sim, "interact")
        self.fit_text(
            surf,
            f"Arrows/D-pad choose · {jump} confirm · {interact} cancel",
            (45, 132, 230, 10),
            PALETTE["accent"],
            align="center",
            max_size=7,
            min_size=5,
        )

    def _recovery(self, surf: Surface, sim: GameSim) -> None:
        shade = Surface((self._iw, self._ih), pygame.SRCALPHA)
        shade.fill((20, 4, 12, 175))
        surf.blit(shade, (0, 0))
        self._panel(surf, (38, 32, 244, 116), fill=(12, 8, 14))
        self.fit_text(surf, "BS METER MAXED", (52, 49, 216, 18), PALETTE["accent"], align="center", max_size=13, min_size=8, bold=True)
        self.fit_text(surf, "The argument overloaded. Nobody was deleted.", (52, 76, 216, 12), PALETTE["fg"], align="center", max_size=8, min_size=6)
        self.fit_text(surf, "Retry from the chapter checkpoint. Score -100.", (52, 94, 216, 12), PALETTE["yellow"], align="center", max_size=8, min_size=6)
        jump = self._binding_pair(sim, "jump")
        interact = self._binding_pair(sim, "interact")
        self.fit_text(
            surf,
            f"{jump} or {interact}  RETRY",
            (52, 121, 216, 12),
            PALETTE["bright_green"],
            align="center",
            max_size=10,
            min_size=7,
            bold=True,
        )

    def _chapter_credits(self, surf: Surface, sim: GameSim) -> None:
        surf.fill(PALETTE["dark"])
        self.fit_text(surf, "OMEGA OMARCHY", (30, 28, 260, 18), PALETTE["bright_green"], align="center", max_size=14, min_size=8, bold=True)
        self.fit_text(surf, "OPEN DEVELOPMENT ALPHA", (30, 50, 260, 12), PALETTE["cyan"], align="center", max_size=9, min_size=6)
        self.wrapped_text(
            surf,
            "Chapter 1: design, code, original art and audio by the Omega Omarchy project.",
            (42, 72, 236, 28),
            PALETTE["fg"],
            max_lines=2,
            logical_size=8,
        )
        self.wrapped_text(
            surf,
            "Unofficial parody project. Omarchy marks and real-person likeness rights are not granted by the code license.",
            (42, 106, 236, 30),
            PALETTE["yellow"],
            max_lines=3,
            logical_size=7,
        )
        jump = self._binding_pair(sim, "jump")
        turn = self._binding_pair(sim, "turn")
        self.fit_text(
            surf,
            (
                f"{jump} back   Chapter 1 browser boundary"
                if sim.web_chapter_one
                else f"{jump} back   {turn} development chapters"
            ),
            (32, 153, 256, 11),
            PALETTE["accent"],
            align="center",
            max_size=8,
            min_size=6,
        )

    def _ending(self, surf: Surface, sim: GameSim) -> None:
        surf.fill(PALETTE["dark"])
        self.blit_text(surf, "GOLIATH CONVERTED", (80, 40), PALETTE["bright_green"])
        self.fit_text(surf, "The Singularity demanded one future.", (28, 69, 264, 12), PALETTE["fg"], max_size=9, min_size=6)
        self.fit_text(surf, "Omarchy lets its users make their own.", (28, 83, 264, 12), PALETTE["cyan"], max_size=9, min_size=6)
        self.fit_text(surf, "The revolution will be customized.", (28, 107, 264, 12), PALETTE["yellow"], max_size=9, min_size=6)
        self.fit_text(surf, "Credits — original art, audio, and code.", (28, 139, 264, 12), PALETTE["fg"], max_size=9, min_size=6)
        self.fit_text(surf, "Private likeness refs were not shipped.", (28, 153, 264, 12), PALETTE["accent"], max_size=9, min_size=6)


def save_surface(surf: Surface, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(path))
