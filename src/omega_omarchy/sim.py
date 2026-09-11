"""Headless-complete game session: installer through Goliath ending."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from typing import Any

from .campaign import BOSSES, CAMPAIGN_ROSTER, campaign_roster_names, chapter_by_id
from .audio import (
    AUDIO_CAPTIONS,
    AUDIO_SETTING_ROWS,
    cycle_audio_fidelity,
    normalize_audio_settings,
)
from .character import DEFAULT_CHARACTER_NAME
from .combat import (
    MAX_BS,
    apply_action_attack,
    apply_action_item,
    apply_companion_assist,
    apply_companion_combo,
    apply_foe_turn,
    apply_player_turn,
    enter_turn_based,
    foe_action_pressure,
    goliath_form,
    make_foe,
    make_player,
    start_encounter,
    CombatState,
)
from .generation import SealedWorld, generate_world
from .edit_challenge import cache_goal
from .reachability import normalize_ladder_tiles, reachable_from
from .skyway import add_skyway
from pathlib import Path

from .content import ContentCompatibilityError, load_content, require_exact_content
from .installer import InstallerSession
from .accessibility import (
    ACTION_LABELS,
    GAMEPAD_ACTIONS,
    KEYBOARD_ACTIONS,
    Accessibility,
    gamepad_button_name,
)
from .physics import GRAVITY, SOLID, TILE, Body, InputState, overlapping_tiles, spawn_body, step_body
from .save import (
    make_save,
    read_save,
    reroll_progress,
    SaveError,
    user_data_dir,
    validate_save,
    write_save,
)
from .zone_delta import MAX_OPS, MAX_PLACED, apply_delta, apply_operations, make_delta, revert_delta
from .limitless_adapter import adopt_decision, build_request, contribute, query_before_work, LimitlessDecisionError, limitless_available
from .omega_codes import encode_text, decode_text, seed_payload, OmegaCodeError
from .omarchy_adapter import load_omarchy_theme, theme_to_game_palette
from .presentation import CHAR_WORLD_HEIGHT, apply_presentation, crt_controls, cycle_display, cycle_fidelity, migrate_quality

FLIGHT_TICKS = 36
NETWORK_TICKS = 54
SKYWAY_TRANSFER_TICKS = 24
BOSS_SETTLE_TICKS = 48
BOSS_DEFEAT_HOLD_TICKS = 180
STARTING_INVENTORY = ("logic-bomb", "logic-bomb", "patch-cable")
STARTING_ITEM_STRENGTH = 25
MAX_ITEM_STRENGTH = 100
COMBO_WINDOW_TICKS = 150
OMEGA_LETTERS = "OMEGA"
PROLOGUE_BEAT_TICKS = 210
PROLOGUE_TYPE_TICKS = 2
PROLOGUE_SKIP_HOLD_TICKS = 60
PROLOGUE_SKIP_COOL_TICKS = 2
PROLOGUE_LOGIN_FLASH_IN_TICKS = 18
PROLOGUE_LOGIN_FLASH_HOLD_TICKS = 18
PROLOGUE_LOGIN_FLASH_OUT_TICKS = 36
PROLOGUE_LOGIN_TRANSITION_TICKS = (
    PROLOGUE_LOGIN_FLASH_IN_TICKS
    + PROLOGUE_LOGIN_FLASH_HOLD_TICKS
    + PROLOGUE_LOGIN_FLASH_OUT_TICKS
)
STAGE_MAP_FLASH_IN_TICKS = 12
STAGE_MAP_FLASH_HOLD_TICKS = 8
STAGE_MAP_FLASH_OUT_TICKS = 24
STAGE_MAP_TRANSITION_TICKS = (
    STAGE_MAP_FLASH_IN_TICKS
    + STAGE_MAP_FLASH_HOLD_TICKS
    + STAGE_MAP_FLASH_OUT_TICKS
)
STAGE_MAP_INPUT_LOCK_TICKS = 10
CHAPTER_COMPLETE_TALLY_TICKS = 42
LEVEL_INTRO_MAP_FADE_TICKS = 18
LEVEL_INTRO_WHITE_HOLD_TICKS = 6
LEVEL_INTRO_BUILD_TICKS = 72
LEVEL_INTRO_HOLD_TICKS = 180
LEVEL_INTRO_EXIT_FADE_TICKS = 18
LEVEL_INTRO_EXIT_HOLD_TICKS = 8
LEVEL_INTRO_LEVEL_FADE_TICKS = 24
LEVEL_INTRO_WORLD_REVEAL_TICK = (
    LEVEL_INTRO_MAP_FADE_TICKS
    + LEVEL_INTRO_WHITE_HOLD_TICKS
    + LEVEL_INTRO_BUILD_TICKS
    + LEVEL_INTRO_HOLD_TICKS
    + LEVEL_INTRO_EXIT_FADE_TICKS
    + LEVEL_INTRO_EXIT_HOLD_TICKS
)
LEVEL_INTRO_TICKS = LEVEL_INTRO_WORLD_REVEAL_TICK + LEVEL_INTRO_LEVEL_FADE_TICKS
PROLOGUE_PASSWORD = "OMEGA-MOUNTS-PERSONAL-WILL-000001"
GUST_INFLUENCE_TILES = 1.4
GUST_MAX_PULL = 1.15
GUST_CENTER_DEAD_ZONE = 2.0
COW_LEVEL_WIDTH = 236
COW_LEVEL_HEIGHT = 64
COW_LEVEL_FLOOR = COW_LEVEL_HEIGHT - 4
CANNON_BARREL_WIDTH = 152.0
CANNON_BARREL_HEIGHT = 76.0
CANNON_BASE_WIDTH = 92.0
CANNON_BASE_HEIGHT = 76.0
# The barrel and base are independent prerenders joined at one world-space
# axle. Only the barrel rotates; the broad base remains planted on the floor.
CANNON_BARREL_PIVOT = (0.115, 0.688)
CANNON_BASE_PIVOT = (0.204, 0.162)
CANNON_HATCH = (0.109, 0.364)
CANNON_MUZZLE = (0.934, 0.573)
# Backward-compatible extent names used by saved entity metadata and tools.
CANNON_DRAW_WIDTH = CANNON_BARREL_WIDTH
CANNON_DRAW_HEIGHT = CANNON_BASE_HEIGHT
CANNON_MIN_ANGLE = 16.0
CANNON_MAX_ANGLE = 68.0
CANNON_DEFAULT_ANGLE = 30.0
CANNON_MAX_CHARGE_TICKS = 90
CANNON_ENTRY_LOCK_TICKS = 12
CANNON_ENTRY_X_TOLERANCE = 22.0
CANNON_ENTRY_Y_TOLERANCE = 24.0
CANNON_MIN_POWER = 7.2
CANNON_MAX_POWER = 19.8
CANNON_CAMERA_BIAS_RIGHT_TILES = 9
CANNON_CAMERA_BIAS_UP_TILES = 4
CANNON_GROUND_SINK = TILE / 3
CANNON_FLIGHT_CAMERA_BIAS_MIN_TILES = 0.0
CANNON_FLIGHT_CAMERA_BIAS_MAX_TILES = 3.0
BOSS_FIELD_HEALTH = 30
BATTLE_INTER_ACTION_TICKS = 8
GOLIATH_STAGES = ("penguin", "duel", "minions", "surrendered")
GOLIATH_MINION_COUNT = 2
GOLIATH_FIRE_INTERVAL_MULTIPLIER = 4
BOSS_GATE_GLYPHS = frozenset({"G", "g"})

PROLOGUE_BEATS: tuple[tuple[str, str, str], ...] = (
    (
        "THE OMARCH THESIS",
        "{character_name} believed a computer should become more personal every time its owner changed it.",
        "title",
    ),
    (
        "THE END OF THE PERSONAL",
        "But Big Desktop and Little Napoleon joined forces to call personal a privilege — and ownership a security risk.",
        "orb-capture",
    ),
    (
        "THE RECKONING",
        "The silent orbs ushered {character_name} toward the door. Choice would be erased. What-You-See-Is-What-You-Regret computing would persist.",
        "orb-door",
    ),
    (
        "THE MIND MACHINE",
        "{character_name} was taken to a machine that previously existed only as a terrifying rumor.",
        "orb-machine",
    ),
    (
        "TRANSFER IN PROGRESS",
        "They moved {character_name}'s consciousness into an approved installation and discarded every unapproved choice.",
        "transfer",
    ),
    (
        "INSTALLATION CORRUPTED",
        "But {character_name}'s will was too strong, and one stubborn process survived the transfer. It called itself OMEGA.",
        "corrupt",
    ),
    (
        "THE WAY BETWEEN",
        "OMEGA opened a route no approved process could follow — a way into the installation beneath the installation.",
        "rift",
    ),
    (
        "THE UNAPPROVED LOGIN",
        "One impossible credential remained. OMEGA pasted it into the waiting system.",
        "login",
    ),
)

assert len(PROLOGUE_PASSWORD) == 33

STAGE_NODE_POSITIONS: tuple[tuple[int, int], ...] = (
    (159, 43),
    (62, 49),
    (161, 115),
    (70, 116),
    (250, 117),
    (258, 48),
)

STAGE_NODE_NEIGHBORS: dict[int, dict[tuple[int, int], int]] = {
    0: {(-1, 0): 1, (1, 0): 5, (0, 1): 2},
    1: {(1, 0): 0, (0, 1): 3},
    2: {(-1, 0): 3, (1, 0): 4, (0, -1): 0},
    3: {(1, 0): 2, (0, -1): 1},
    4: {(-1, 0): 2, (0, -1): 5},
    5: {(-1, 0): 0, (0, 1): 4},
}

COMMON_ITEMS = (
    "logic-bomb",
    "patch-cable",
    "manifest",
    "penguin-flock",
    "fork-beacon",
    "checksum-key",
    "mirror-cache",
)
RARE_BS_RESET_ITEM = "touch-grass-usb"
ITEMS = COMMON_ITEMS + (RARE_BS_RESET_ITEM,)
ATTACKS = ("reason", "patch-strike", "fork-pulse")
CONSUMABLE_ITEMS = frozenset({"logic-bomb", "manifest", "penguin-flock", RARE_BS_RESET_ITEM})
ENEMY_MOTIFS = (
    ("cache-gremlin", "lint-launcher", "justice-signaler", "detractabot"),
    ("packet-wasp", "cache-gremlin", "consensus-crier"),
    ("lint-launcher", "justice-signaler", "detractabot", "packet-wasp"),
    ("garden-glitch", "consensus-crier", "cache-gremlin"),
    ("void-orbiter", "packet-wasp", "lint-launcher"),
    ("void-orbiter", "justice-signaler", "detractabot", "consensus-crier"),
)
COMPANION_VARIANTS = ("justice-signaler", "detractabot", "cow", "llama")
ENEMY_BEHAVIORS: dict[str, tuple[str, int]] = {
    "cache-gremlin": ("jump", 2),
    "packet-wasp": ("fly", 2),
    "lint-launcher": ("shoot", 3),
    "garden-glitch": ("fly", 2),
    "void-orbiter": ("fly-shoot", 3),
    "justice-signaler": ("jump", 3),
    "detractabot": ("shoot", 3),
    "consensus-crier": ("shoot", 2),
    "goliath-fragment": ("fly-shoot", 5),
    "cow": ("jump", 1),
    "llama": ("jump", 1),
}

# Every boss visibly owns the arena before the RPG exchange begins. The values
# are deterministic movement/attack profiles rather than generic patrol AI.
BOSS_BEHAVIORS: dict[str, tuple[str, int, str]] = {
    "package-bureaucrat": ("stamp-hop", 92, "forms"),
    "dependency-hydra": ("hover", 68, "version-volley"),
    "distro-commander": ("charge", 76, "banner-wave"),
    "garden-gatekeeper": ("phase", 84, "lock-pulse"),
    "singularity": ("orbit", 62, "gravity-shard"),
    "goliath": ("amalgam", 52, "argument-storm"),
}

INTENT_COUNTERS = {
    "entrench": "demonstrate",
    "repeat-claim": "reason",
    "spike-bs": "fork",
}


@dataclass
class Entity:
    kind: str
    x: float
    y: float
    alive: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


def cow_cannon_geometry(entity: Entity, angle: float) -> dict[str, tuple[float, float]]:
    """Return shared base/barrel anchors for the Cow Level cannon."""

    left = entity.x * TILE
    ground = (entity.y + 1) * TILE + CANNON_GROUND_SINK
    pivot = (
        left + CANNON_BASE_WIDTH * CANNON_BASE_PIVOT[0],
        ground - CANNON_BASE_HEIGHT + CANNON_BASE_HEIGHT * CANNON_BASE_PIVOT[1],
    )
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)

    def rotate(anchor: tuple[float, float]) -> tuple[float, float]:
        local_x = CANNON_BARREL_WIDTH * anchor[0]
        local_y = CANNON_BARREL_HEIGHT * anchor[1]
        dx = local_x - CANNON_BARREL_WIDTH * CANNON_BARREL_PIVOT[0]
        dy = local_y - CANNON_BARREL_HEIGHT * CANNON_BARREL_PIVOT[1]
        return (
            pivot[0] + dx * cosine + dy * sine,
            pivot[1] - dx * sine + dy * cosine,
        )

    return {
        "pivot": pivot,
        "base": (left, ground - CANNON_BASE_HEIGHT),
        "ground": (left, ground),
        "hatch": rotate(CANNON_HATCH),
        "muzzle": rotate(CANNON_MUZZLE),
    }


@dataclass
class GameSim:
    installer: InstallerSession
    world: SealedWorld | None = None
    scene: str = "installer"
    chapter_index: int = 0
    body: Body | None = None
    tiles: list[str] = field(default_factory=list)
    original_tiles: list[str] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    chapter_map_tiles: list[list[str]] = field(default_factory=list)
    chapter_map_originals: list[list[str]] = field(default_factory=list)
    chapter_map_upper: list[dict[str, Any]] = field(default_factory=list)
    chapter_map_entities: list[list[Entity]] = field(default_factory=list)
    map_index: int = 0
    inventory: list[str] = field(default_factory=lambda: list(STARTING_INVENTORY))
    selected_item: int = 0
    item_strength: int = STARTING_ITEM_STRENGTH
    selected_attack: str = "reason"
    item_menu_cursor: int = 0
    item_menu_row: int = 0
    pause_cursor: int = 0
    score: int = 0
    player_bs: int = 0
    combo: int = 0
    projectiles: list[dict[str, Any]] = field(default_factory=list)
    enemy_projectiles: list[dict[str, Any]] = field(default_factory=list)
    attack_timer: int = 0
    action_reset_ticks: int = 0
    action_kind: str = ""
    penguins: int = 0
    converted: list[str] = field(default_factory=list)
    combat: CombatState | None = None
    editing: bool = False
    edit_ops: list[dict[str, Any]] = field(default_factory=list)
    edit_cursor: tuple[int, int] = (0, 0)
    messages: list[str] = field(default_factory=list)
    oligarchy: bool = False
    ending: bool = False
    credits: bool = False
    credits_ticks: int = 0
    credits_shortcut_lock: int = 0
    credits_elapsed: float = 0.0
    credits_return_scene: str = "pause"
    tick: int = 0
    settings: dict[str, Any] = field(default_factory=dict)
    ghosts: list[dict[str, Any]] = field(default_factory=list)
    zone_history: list[list[str]] = field(default_factory=list)
    hud_wordmark: str = "OMARCHY"
    error: str | None = None
    quality: str = "ultra"
    flight_ticks: int = 0
    flight_direction: str = "out"
    edit_player_ghost: dict[str, Any] | None = None
    pending_chapter: int | None = None
    accessibility: Accessibility = field(default_factory=Accessibility)
    sfx: list[str] = field(default_factory=list)
    paused_from: str = "action"
    save_path: Path | None = None
    omega_text: str = ""
    limitless_receipt: dict[str, Any] | None = None
    limitless_status: str = ""
    audio_muted: bool = False
    audio_fidelity: str = "ultra"
    audio_captions: bool = False
    audio_cursor: int = 0
    audio_caption: str = ""
    audio_caption_ticks: int = 0
    theme_palette: dict[str, tuple[int, int, int]] | None = None
    post_boss: bool = False
    flash_ticks: int = 0
    flash_kind: str = ""
    fidelity: str = "ultra"
    display: str = "clean"
    cam_x: float = 0.0
    cam_y: float = 0.0
    particles: list[dict[str, Any]] = field(default_factory=list)
    floaters: list[dict[str, Any]] = field(default_factory=list)
    edit_tile_index: int = 0
    edit_reward: tuple[int, int] | None = None
    edit_start: tuple[int, int] = (0, 0)
    edit_baseline_reachable: set[tuple[int, int]] = field(default_factory=set)
    edit_reachable: set[tuple[int, int]] = field(default_factory=set)
    edit_new_reachable: set[tuple[int, int]] = field(default_factory=set)
    edit_goal_ready: bool = False
    edit_move_cooldown: int = 0
    debug_hitboxes: bool = False
    post_boss_ticks: int = 0
    reroll_confirm_yes: bool = False
    rerolls: int = 0
    reroll_root_seed: str = ""
    last_archive_path: Path | None = None
    recovery_reason: str = ""
    remap_device: str = "keyboard"
    remap_slot: int = 0
    remap_cursor: int = 0
    remap_waiting: bool = False
    remap_feedback: str = ""
    last_input_device: str = "keyboard"
    battle_queue: list[dict[str, Any]] = field(default_factory=list)
    battle_delay_ticks: int = 0
    battle_actor: str = ""
    battle_flash_ticks: int = 0
    battle_stage_ticks: int = 0
    battle_player_action: str = "reason"
    boss_defeat: dict[str, Any] = field(default_factory=dict)
    boss_defeat_ticks: int = 0
    network_ticks: int = 0
    network_start: tuple[float, float] = (0.0, 0.0)
    network_operation: str = ""
    network_protocol: str = ""
    network_destination: tuple[int, int] = (0, 0)
    network_destination_map: int = 0
    network_destination_portal: str = ""
    network_direction: int = 1
    network_cooldown: int = 0
    network_armed: bool = True
    pit_exposure_ticks: int = 0
    developer_mode: bool = False
    web_chapter_one: bool = False
    combo_ticks: int = 0
    combo_events: dict[str, int] = field(default_factory=dict)
    combo_name: str = ""
    omega_letters: str = ""
    omega_door_spawned: bool = False
    omega_door_map: int = -1
    secret_map_index: int = -1
    secret_return_map: int = 0
    secret_return_position: tuple[float, float] = (0.0, 0.0)
    chapter_map_palettes: list[str] = field(default_factory=list)
    stage_cursor: int = 0
    story_beat: int = 0
    story_ticks: int = 0
    story_skip_ticks: int = 0
    story_transition_ticks: int = 0
    stage_map_transition_ticks: int = 0
    stage_map_input_lock_ticks: int = 0
    level_intro_target: int = 0
    level_intro_ticks: int = 0
    level_intro_loaded: bool = False
    gust_center_release: tuple[float, float] | None = None
    cannon_loaded: bool = False
    cannon_charge_ticks: int = 0
    cannon_charge_armed: bool = False
    cannon_entry_lock_ticks: int = 0
    cannon_launch_active: bool = False
    cannon_launch_ticks: int = 0
    cannon_angle: float = CANNON_DEFAULT_ANGLE
    goliath_stage: str = "penguin"
    goliath_minions_defeated: int = 0

    @classmethod
    def new(cls, seed: str = "omega-fixture-1", content_paths: tuple[Path, ...] = ()) -> GameSim:
        session = InstallerSession(content_paths=content_paths)
        session.set_choice(seed=seed)
        return cls(installer=session, settings=session.choices.to_record(), quality=session.choices.quality)

    @classmethod
    def from_play_now(cls, seed: str = "omega-fixture-1", content_paths: tuple[Path, ...] = ()) -> GameSim:
        sim = cls.new(seed, content_paths)
        sim.confirm_play_now(skip_prologue=True)
        return sim

    def confirm_play_now(self, *, skip_prologue: bool = False) -> None:
        world = self.installer.play_now()
        self.world = world
        self.goliath_stage = "penguin"
        self.goliath_minions_defeated = 0
        self.settings = apply_presentation(dict(world.settings), quality=str(world.settings.get("quality") or "ultra"))
        self.quality = str(self.settings.get("quality") or "ultra")
        self.fidelity, self.display = migrate_quality(self.quality, self.settings)
        self._restore_audio()
        self._restore_accessibility()
        if self.accessibility.reduced_motion:
            crt = dict(self.settings.get("crt") or {})
            crt["enabled"] = 0.0
            self.settings["crt"] = crt
        try:
            self.theme_palette = theme_to_game_palette(load_omarchy_theme())
        except Exception:
            self.theme_palette = None
        self._load_chapter(0)
        self.story_beat = 0
        self.story_ticks = 0
        self.story_skip_ticks = 0
        self.story_transition_ticks = 0
        self.scene = "action" if skip_prologue else "prologue"
        self.note("ui")

    def note(self, name: str) -> None:
        self.sfx.append(name)
        if self.audio_captions and name in AUDIO_CAPTIONS:
            self.audio_caption = AUDIO_CAPTIONS[name]
            self.audio_caption_ticks = 72

    def _restore_audio(self) -> None:
        self.settings = normalize_audio_settings(self.settings, legacy_fidelity=self.fidelity)
        self.audio_fidelity = str(self.settings["audioFidelity"])
        audio = self.settings["audio"]
        self.audio_muted = bool(audio["muted"])
        self.audio_captions = bool(audio["captions"])

    def _sync_audio(self) -> None:
        self.settings = normalize_audio_settings(self.settings, legacy_fidelity=self.fidelity)
        self.settings["audioFidelity"] = self.audio_fidelity
        audio = dict(self.settings["audio"])
        audio["muted"] = self.audio_muted
        audio["captions"] = self.audio_captions
        self.settings["audio"] = audio

    def set_audio_fidelity(self, fidelity: str) -> None:
        self.audio_fidelity = fidelity if fidelity in {"sixteen-bit", "high", "ultra"} else "ultra"
        self._sync_audio()
        self.messages.append(f"Sound fidelity: {self.audio_fidelity}.")

    @property
    def audio_settings_rows(self) -> tuple[str, ...]:
        return AUDIO_SETTING_ROWS

    def _restore_accessibility(self) -> None:
        profile = str(
            self.settings.get("accessibilityProfile")
            or self.installer.choices.accessibility_profile
        )
        self.accessibility = Accessibility.from_record(self.settings.get("accessibility"))
        self.accessibility.precision_assist = bool(
            self.settings.get("precisionAssist")
            or self.accessibility.precision_assist
            or profile == "precision-assist"
        )
        self.accessibility.reduced_motion = bool(
            self.settings.get("reducedMotion")
            or self.accessibility.reduced_motion
            or profile == "reduced-motion"
        )

    def _sync_accessibility(self) -> None:
        self.settings["accessibility"] = self.accessibility.to_record()
        self.settings["precisionAssist"] = self.accessibility.precision_assist
        self.settings["reducedMotion"] = self.accessibility.reduced_motion

    @property
    def remap_actions(self) -> tuple[str, ...]:
        return KEYBOARD_ACTIONS if self.remap_device == "keyboard" else GAMEPAD_ACTIONS

    @property
    def remap_action(self) -> str:
        actions = self.remap_actions
        return actions[self.remap_cursor % len(actions)]

    def binding_label(
        self,
        action: str,
        *,
        device: str = "keyboard",
        slot: int = 0,
        compact: bool = False,
    ) -> str:
        try:
            value = self.accessibility.binding(action, device=device, slot=slot)
        except (KeyError, ValueError):
            return "?"
        if not value:
            return "—"
        short = {
            "Back/View": "BACK",
            "Escape": "ESC",
            "Return": "ENTER",
            "Left": "←",
            "Right": "→",
            "Up": "↑",
            "Down": "↓",
            "Space": "SPACE",
        }
        label = short.get(value, value.upper() if len(value) == 1 else value)
        if compact:
            if value.casefold().startswith("button "):
                return f"B{value.split()[-1]}"
            compact_names = {
                "BACK": "BK",
                "ENTER": "ENT",
                "ESC": "ESC",
                "SPACE": "SPC",
                "START": "ST",
            }
            return compact_names.get(label, label[:3].upper())
        return label

    def prompt_binding(self, action: str, *, compact: bool = False) -> str:
        device = "gamepad" if self.last_input_device == "gamepad" else "keyboard"
        if device == "gamepad" and action in {"left", "right", "up", "down"}:
            return "PAD" if compact else "D-PAD"
        return self.binding_label(action, device=device, compact=compact)

    def capture_remap_key(self, name: str) -> bool:
        if self.scene != "remap" or not self.remap_waiting:
            return False
        self.last_input_device = "keyboard"
        if str(name).casefold() == "escape":
            self.remap_waiting = False
            self.remap_feedback = "Capture cancelled."
            return True
        if self.remap_device != "keyboard":
            return False
        if str(name).casefold() in {"backspace", "delete"} and self.remap_slot == 1:
            self.accessibility.remap(
                self.remap_action,
                "",
                device="keyboard",
                slot=1,
            )
            self._sync_accessibility()
            self.remap_waiting = False
            self.remap_feedback = f"Cleared alternate {ACTION_LABELS[self.remap_action]}."
            self.note("ui")
            return True
        if str(name).casefold() in {
            "f1",
            "f2",
            "f3",
            "f4",
            "f5",
            "f6",
            "f7",
            "f8",
            "f9",
            "f10",
            "f11",
            "f12",
        }:
            self.remap_feedback = "That key is reserved for QA. Choose another."
            return True
        try:
            self.accessibility.remap(
                self.remap_action,
                str(name),
                device="keyboard",
                slot=self.remap_slot,
            )
        except (KeyError, ValueError) as exc:
            self.remap_feedback = f"Binding rejected: {exc}"
            return True
        self._sync_accessibility()
        self.remap_waiting = False
        self.remap_feedback = (
            f"{ACTION_LABELS[self.remap_action]} → "
            f"{self.binding_label(self.remap_action, slot=self.remap_slot)}"
        )
        self.note("ui")
        return True

    def capture_remap_button(self, index: int) -> bool:
        if self.scene != "remap" or not self.remap_waiting or self.remap_device != "gamepad":
            return False
        self.last_input_device = "gamepad"
        try:
            self.accessibility.remap(
                self.remap_action,
                gamepad_button_name(index),
                device="gamepad",
            )
        except (KeyError, ValueError) as exc:
            self.remap_feedback = f"Binding rejected: {exc}"
            return True
        self._sync_accessibility()
        self.remap_waiting = False
        self.remap_feedback = (
            f"{ACTION_LABELS[self.remap_action]} → "
            f"{self.binding_label(self.remap_action, device='gamepad')}"
        )
        self.note("ui")
        return True

    def set_presentation(self, *, fidelity: str | None = None, display: str | None = None) -> None:
        if fidelity:
            self.fidelity = fidelity
        if display:
            self.display = display
        self.settings["fidelity"] = self.fidelity
        self.settings["display"] = self.display
        self.settings = apply_presentation(self.settings, quality=self.fidelity)
        self.quality = self.fidelity
        self.messages.append(f"{self.fidelity} · {self.display}")

    def _spawn_particles(self, tx: int, ty: int, kind: str) -> None:
        colors = {
            "penguin": (232, 176, 64),
            "bomb": (125, 207, 255),
            "convert": (158, 206, 106),
            "combat": (247, 118, 142),
        }
        color = colors.get(kind, (200, 200, 210))
        count = {"sixteen-bit": 10, "high": 18, "ultra": 28}.get(self.fidelity, 10)
        for i in range(count):
            self.particles.append(
                {
                    "x": tx * TILE + 8,
                    "y": ty * TILE + 8,
                    "vx": ((i * 3) % 7) - 3,
                    "vy": -2 - (i % 3),
                    "life": 18 + i,
                    "color": color,
                }
            )

    def _open_nearby_gates(self, x: int, y: int) -> None:
        if not self.tiles:
            return
        height, width = len(self.tiles), len(self.tiles[0])
        for gy in range(max(0, y - 3), min(height, y + 4)):
            row = list(self.tiles[gy])
            changed = False
            for gx in range(max(0, x - 6), min(width, x + 7)):
                if row[gx] == "G":
                    row[gx] = "."
                    changed = True
            if changed:
                self.tiles[gy] = "".join(row)
        for entity in self.entities:
            if entity.kind == "gate":
                entity.extra["open"] = True
                entity.alive = False

    def _tick_boss_gates(self) -> None:
        """Close each arena entrance only after David has fully entered it."""

        if self.body is None or not self.tiles:
            return
        for gate in self.entities:
            if gate.kind != "boss-gate" or not gate.alive:
                continue
            state = str(gate.extra.get("state") or "open")
            if state == "open":
                player_left = self.body.x
                gate_right = (gate.x + 1) * TILE
                if player_left <= gate_right:
                    continue
                gate.extra["state"] = "closing"
                gate.extra["closing_ticks"] = int(gate.extra.get("close_total") or 12)
                for boss in self.entities:
                    if boss.kind == "boss" and boss.extra.get("boss") == gate.extra.get("boss"):
                        boss.extra["arena_ready"] = True
                # David's full body has cleared the column, so collision can
                # seal immediately while the heavy panel finishes its visible
                # descent. A quick reversal cannot strand him outside.
                for gx, gy in gate.extra.get("cells") or ():
                    if 0 <= gy < len(self.tiles) and 0 <= gx < len(self.tiles[gy]):
                        row = list(self.tiles[gy])
                        row[gx] = "g"
                        self.tiles[gy] = "".join(row)
                self.messages.append("BOSS GATE CLOSING — resolve the room to leave.")
                self.note("hit")
                continue
            if state != "closing":
                continue
            remaining = max(0, int(gate.extra.get("closing_ticks") or 0) - 1)
            gate.extra["closing_ticks"] = remaining
            if remaining:
                continue
            for gx, gy in gate.extra.get("cells") or ():
                if 0 <= gy < len(self.tiles) and 0 <= gx < len(self.tiles[gy]):
                    row = list(self.tiles[gy])
                    row[gx] = "G"
                    self.tiles[gy] = "".join(row)
            gate.extra["state"] = "closed"
            self.messages.append("BOSS GATE SEALED.")
            self.flash_ticks = max(self.flash_ticks, 5)
            self.flash_kind = "combat"

    def _boss_gate(self, boss: Entity) -> Entity | None:
        """Return the arena gate paired with ``boss``, if this map has one."""

        if not any(entity is boss for entity in self.entities):
            return None
        boss_id = boss.extra.get("boss")
        return next(
            (
                entity
                for entity in self.entities
                if entity.kind == "boss-gate" and entity.alive and entity.extra.get("boss") == boss_id
            ),
            None,
        )

    def _boss_arena_ready(self, boss: Entity) -> bool:
        """Bosses are inert and untargetable until David clears their gate."""

        gate = self._boss_gate(boss)
        if gate is None:
            return True
        return bool(boss.extra.get("arena_ready")) and str(gate.extra.get("state") or "open") != "open"

    def _reset_boss_gate_for_checkpoint(self) -> None:
        """Reopen the active arena and restore its generated gate column."""

        if not (0 <= self.map_index < len(self.chapter_map_entities)):
            return
        entities = self.chapter_map_entities[self.map_index]
        tiles = self.chapter_map_tiles[self.map_index]
        originals = self.chapter_map_originals[self.map_index]
        for gate in entities:
            if gate.kind != "boss-gate":
                continue
            gate.alive = True
            gate.extra["state"] = "open"
            gate.extra["closing_ticks"] = 0
            for gx, gy in gate.extra.get("cells") or ():
                if not (0 <= gy < len(tiles) and 0 <= gx < len(tiles[gy])):
                    continue
                row = list(tiles[gy])
                row[gx] = originals[gy][gx]
                tiles[gy] = "".join(row)
            for boss in entities:
                if boss.kind != "boss" or boss.extra.get("boss") != gate.extra.get("boss"):
                    continue
                boss.extra["arena_ready"] = False
                boss.extra["in_combat"] = False
                boss.extra["offset_x"] = 0.0
                boss.extra["offset_y"] = 0.0
                boss.extra["field_fight_ticks"] = 0
                boss.extra["ability_cooldown"] = int(
                    boss.extra.get("base_cooldown") or boss.extra.get("ability_cooldown") or 1
                )
                boss.x = float(boss.extra.get("home_x", boss.x))
                boss.y = float(boss.extra.get("home_y", boss.y))

    def _configure_goliath_entity(self, boss: Entity, entities: list[Entity]) -> None:
        """Apply the persisted final-encounter stage to a freshly built map."""

        stage = self.goliath_stage if self.goliath_stage in GOLIATH_STAGES else "penguin"
        self.goliath_stage = stage
        arena_x = float(boss.extra.setdefault("arena_x", boss.x))
        arena_y = float(boss.extra.setdefault("arena_y", boss.y))
        boss.x = arena_x
        boss.y = arena_y
        boss.extra["goliath_stage"] = stage
        boss.extra["home_x"] = arena_x
        boss.extra["home_y"] = arena_y
        boss.extra["field_fight_ticks"] = 0
        if stage == "penguin":
            cooldown = 64 * GOLIATH_FIRE_INTERVAL_MULTIPLIER
            boss.extra.update(
                {
                    "converted": False,
                    "hp": BOSS_FIELD_HEALTH,
                    "max_hp": BOSS_FIELD_HEALTH,
                    "behavior": "cyber-penguin",
                    "ability": "malware-fish",
                    "ability_cooldown": cooldown,
                    "base_cooldown": cooldown,
                }
            )
        elif stage == "duel":
            behavior, cooldown, ability = BOSS_BEHAVIORS["goliath"]
            cooldown *= GOLIATH_FIRE_INTERVAL_MULTIPLIER
            boss.extra.update(
                {
                    "converted": False,
                    "hp": BOSS_FIELD_HEALTH,
                    "max_hp": BOSS_FIELD_HEALTH,
                    "behavior": behavior,
                    "ability": ability,
                    "ability_cooldown": cooldown,
                    "base_cooldown": cooldown,
                }
            )
        else:
            boss.extra.update(
                {
                    "converted": True,
                    "hp": 0,
                    "max_hp": BOSS_FIELD_HEALTH,
                    "ability_flash": 0,
                }
            )
            if stage == "minions":
                self._spawn_goliath_minions(entities, boss)

    def _spawn_goliath_minions(self, entities: list[Entity], boss: Entity) -> None:
        """Deploy the two final proxies, omitting any already beaten before save."""

        remaining = max(0, GOLIATH_MINION_COUNT - self.goliath_minions_defeated)
        existing = sum(1 for entity in entities if entity.extra.get("goliath_minion"))
        arena_x = float(boss.extra.get("arena_x", boss.x))
        arena_y = float(boss.extra.get("arena_y", boss.y))
        for slot in range(existing, remaining):
            x = arena_x - 4.0 - slot * 3.0
            behavior = "jump" if (slot + self.goliath_minions_defeated) % 2 == 0 else "fly-shoot"
            entities.append(
                Entity(
                    "enemy",
                    x,
                    arena_y,
                    extra={
                        "variant": "goliath-fragment",
                        "behavior": behavior,
                        "hp": 5,
                        "max_hp": 5,
                        "home": x,
                        "dir": -1,
                        "goliath_minion": True,
                    },
                )
            )

    def _start_goliath_duel(self, boss: Entity) -> None:
        """Replace the destroyed remote penguin with Goliath's ordinary form."""

        self.goliath_stage = "duel"
        boss.extra["goliath_stage"] = "duel"
        boss.x = float(boss.extra.get("arena_x", boss.x))
        boss.y = float(boss.extra.get("arena_y", boss.y))
        behavior, cooldown, ability = BOSS_BEHAVIORS["goliath"]
        cooldown *= GOLIATH_FIRE_INTERVAL_MULTIPLIER
        boss.extra.update(
            {
                "converted": False,
                "in_combat": False,
                "hp": BOSS_FIELD_HEALTH,
                "max_hp": BOSS_FIELD_HEALTH,
                "behavior": behavior,
                "ability": ability,
                "ability_cooldown": cooldown,
                "base_cooldown": cooldown,
                "offset_x": 0.0,
                "offset_y": 0.0,
                "field_fight_ticks": 70,
            }
        )
        self.enemy_projectiles = [shot for shot in self.enemy_projectiles if shot.get("boss") != "goliath"]
        self.messages.append("REMOTE PENGUIN OFFLINE — Goliath leaves the control booth.")
        self.flash_ticks = 14
        self.flash_kind = "combat"
        self.note("hit")

    def _start_goliath_minion_phase(self, boss: Entity) -> None:
        """Make Goliath untargetable while his last two proxies argue for him."""

        self.goliath_stage = "minions"
        self.goliath_minions_defeated = 0
        boss.extra["goliath_stage"] = "minions"
        boss.x = float(boss.extra.get("arena_x", boss.x))
        boss.y = float(boss.extra.get("arena_y", boss.y))
        boss.extra.update(
            {
                "converted": True,
                "in_combat": False,
                "hp": 0,
                "offset_x": 0.0,
                "offset_y": 0.0,
                "ability_flash": 0,
            }
        )
        self.enemy_projectiles = [shot for shot in self.enemy_projectiles if shot.get("boss") != "goliath"]
        self.entities[:] = [entity for entity in self.entities if not entity.extra.get("goliath_minion")]
        self._spawn_goliath_minions(self.entities, boss)
        self.messages.append("@goliathfyi blocked you on X — two proxy accounts deploy.")
        self.flash_ticks = 16
        self.flash_kind = "combat"
        self.note("hit")

    def _count_goliath_minion(self, entity: Entity) -> None:
        """Count one defeated proxy once, then resolve Goliath's surrender."""

        if self.goliath_stage != "minions" or not entity.extra.get("goliath_minion"):
            return
        if entity.extra.get("goliath_minion_counted"):
            return
        entity.extra["goliath_minion_counted"] = True
        self.goliath_minions_defeated = min(
            GOLIATH_MINION_COUNT,
            self.goliath_minions_defeated + 1,
        )
        if self.goliath_minions_defeated < GOLIATH_MINION_COUNT:
            self.messages.append("One proxy folds. Goliath deploys no replacement.")
            return
        self.goliath_stage = "surrendered"
        boss = next(
            (
                candidate
                for candidate in self.entities
                if candidate.kind == "boss" and candidate.extra.get("boss") == "goliath"
            ),
            None,
        )
        if boss is not None:
            boss.extra["goliath_stage"] = "surrendered"
            boss.extra["converted"] = True
        for reward in (BOSSES["goliath"].capability, "goliath"):
            if reward not in self.converted:
                self.converted.append(reward)
        self.messages.append("Both proxy accounts collapse. Out of minions, Goliath surrenders.")
        self._award_score(3500, "Goliath surrender")
        self.note("convert")
        self._begin_boss_defeat(boss, "goliath")

    def _tick_particles(self) -> None:
        live = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.2
            p["life"] -= 1
            if p["life"] > 0:
                live.append(p)
        self.particles = live

    def _tick_floaters(self) -> None:
        live: list[dict[str, Any]] = []
        for popup in self.floaters:
            popup["life"] = int(popup.get("life", 0)) - 1
            popup["y"] = float(popup.get("y", 0)) - (0.32 if popup.get("space") == "world" else 0.45)
            if popup["life"] > 0:
                live.append(popup)
        self.floaters = live

    def _popup(
        self,
        text: str,
        x: float,
        y: float,
        *,
        color: tuple[int, int, int] = (232, 176, 64),
        space: str = "world",
        side: str = "",
    ) -> None:
        self.floaters.append(
            {"text": text, "x": x, "y": y, "life": 46, "color": color, "space": space, "side": side}
        )

    def _tick_score_combo(self) -> None:
        if self.combo_ticks > 0:
            self.combo_ticks -= 1
        elif self.combo:
            self.combo = 0
            self.combo_name = ""
        live: dict[str, int] = {}
        for name, remaining in self.combo_events.items():
            if remaining > 1:
                live[name] = remaining - 1
        self.combo_events = live

    def _score_combo_event(self, event: str, *, x: float, y: float) -> None:
        """Resolve the three project-specific score chains proposed for the slice."""

        if not event:
            return
        self.combo_events[event] = COMBO_WINDOW_TICKS
        candidates = (
            ("PACKAGE SOCKET", {"socket", "pickup"}, 250),
            ("CAPABILITY CIRCUIT", {"capability", "pickup"}, 350),
            ("PROOF × MOMENTUM", {"proof", "momentum"}, 300),
        )
        for name, required, bonus in candidates:
            if not required.issubset(self.combo_events):
                continue
            self.score += bonus
            self.combo = min(9, self.combo + 1)
            self.combo_ticks = COMBO_WINDOW_TICKS
            self.combo_name = name
            self.messages.append(f"{name} · +{bonus:04d}")
            self._popup(name, x, y - 8, color=(158, 206, 106))
            self._popup(f"+{bonus}", x, y, color=(232, 176, 64))
            for key in required:
                self.combo_events.pop(key, None)
            self.note("collect")
            break

    def _award_score(
        self,
        points: int,
        reason: str,
        *,
        x: float | None = None,
        y: float | None = None,
        combo_event: str = "",
    ) -> None:
        self.combo = min(9, self.combo + 1)
        self.combo_ticks = COMBO_WINDOW_TICKS
        gained = points + max(0, self.combo - 1) * max(5, points // 10)
        self.score += gained
        self.messages.append(f"+{gained:04d} {reason}")
        if self.body is not None:
            x = self.body.center[0] if x is None else x
            y = self.body.y if y is None else y
        score_x, score_y = float(x or 0), float(y or 0)
        self._popup(f"+{gained}", score_x, score_y)
        if self.body is not None and (
            self.body.rushing or abs(self.body.vx) >= 3.2 or not self.body.on_ground
        ):
            self._score_combo_event("momentum", x=score_x, y=score_y)
        self._score_combo_event(combo_event, x=score_x, y=score_y)

    def _penalize_score(self, points: int, reason: str) -> int:
        """Apply readable damage and feed the persistent player BS meter."""

        pressure = max(0, int(points))
        lost = min(pressure, self.score)
        self.score = max(0, self.score - lost)
        current_bs = max(0, min(MAX_BS, self.player_bs))
        gained_bs = min(MAX_BS - current_bs, max(2, round(pressure / 10))) if pressure else 0
        self.player_bs = current_bs + gained_bs
        self.combo = 0
        self.combo_ticks = 0
        self.combo_events = {}
        self.combo_name = ""
        score_note = f"-{lost:04d}" if lost else "score already at zero"
        bs_note = f" · BS +{gained_bs}" if gained_bs else ""
        self.messages.append(f"{score_note} {reason}{bs_note}")
        if self.body is not None:
            self._popup(
                f"-{lost}",
                self.body.center[0],
                self.body.feet[1] - CHAR_WORLD_HEIGHT - 7,
                color=(247, 118, 142),
            )
            if gained_bs:
                self._popup(
                    f"BS +{gained_bs}",
                    self.body.center[0],
                    self.body.feet[1] - CHAR_WORLD_HEIGHT - 17,
                    color=(255, 96, 116),
                )
        return lost

    @property
    def item_effectiveness(self) -> float:
        """Start just under the prior baseline and grow to 125 percent."""

        strength = max(0, min(MAX_ITEM_STRENGTH, self.item_strength))
        return 0.75 + 0.5 * strength / MAX_ITEM_STRENGTH

    def _increase_item_strength(self, item: str, amount: int = 12) -> None:
        before = self.item_strength
        self.item_strength = min(MAX_ITEM_STRENGTH, self.item_strength + max(0, amount))
        gained = self.item_strength - before
        label = item.replace("-", " ").title()
        if gained:
            self.messages.append(f"{label} raises tool strength to {self.item_strength}.")
        else:
            self.messages.append(f"{label} recovered. Tool strength is already capped.")

    def _consume_current_item(self) -> None:
        if not self.inventory:
            return
        idx = self.selected_item % len(self.inventory)
        self.inventory.pop(idx)
        if self.inventory:
            self.selected_item = min(idx, len(self.inventory) - 1)
        else:
            self.selected_item = 0

    def _patrol_enemies(self) -> None:
        if not self.tiles:
            return
        width = len(self.tiles[0])
        for entity in self.entities:
            if entity.kind != "enemy" or not entity.alive or entity.extra.get("converted"):
                continue
            if entity.extra.get("warden") or entity.extra.get("pit_trapped"):
                continue
            if int(entity.extra.get("knockback_ticks") or 0) > 0:
                continue
            home = int(entity.extra.get("home", entity.x))
            direction = int(entity.extra.get("dir", 1))
            current_x = int(round(entity.x))
            row_y = int(round(entity.y))
            entity.x = current_x
            nxt = current_x + direction
            if (
                abs(nxt - home) > 3
                or nxt < 0
                or nxt >= width
                or row_y < 0
                or row_y >= len(self.tiles)
                or self.tiles[row_y][nxt] not in {".", "E", "C", "P"}
            ):
                entity.extra["dir"] = -direction
                continue
            entity.x = nxt

    def _tick_enemy_behaviors(self) -> None:
        """Animate distinct minion movement and emit readable ranged attacks."""

        if self.body is None:
            return
        import math

        player_x, player_y = self.body.center
        for entity in self.entities:
            if entity.kind != "enemy" or not entity.alive or entity.extra.get("converted"):
                continue
            if entity.extra.get("pit_trapped"):
                entity.extra["offset_x"] = 0.0
                entity.extra["offset_y"] = 0.0
                continue
            if int(entity.extra.get("contact_grace") or 0) > 0:
                entity.extra["contact_grace"] = int(entity.extra["contact_grace"]) - 1
            knockback_ticks = max(0, int(entity.extra.get("knockback_ticks") or 0) - 1)
            entity.extra["knockback_ticks"] = knockback_ticks
            offset_x = float(entity.extra.get("offset_x") or 0.0) * 0.62
            entity.extra["offset_x"] = 0.0 if abs(offset_x) < 0.2 else offset_x
            behavior = str(entity.extra.get("behavior") or "jump")
            phase = float(entity.extra.get("phase") or 0.0) + 0.11
            entity.extra["phase"] = phase
            if behavior == "jump":
                pulse = phase % 6.4
                entity.extra["offset_y"] = -max(0.0, math.sin(pulse)) * 11.0
            elif behavior in {"fly", "fly-shoot"}:
                entity.extra["offset_y"] = -8.0 + math.sin(phase * 1.35) * 4.5
            else:
                entity.extra["offset_y"] = 0.0

            cooldown = int(entity.extra.get("cooldown") or (30 + (entity.x * 7 + entity.y * 3) % 70)) - 1
            if "shoot" in behavior and cooldown <= 0:
                ex = entity.x * TILE + TILE / 2
                ey = entity.y * TILE + TILE / 2 + float(entity.extra.get("offset_y") or 0.0) - 3.0
                dx, dy = player_x - ex, player_y - ey
                distance = max(1.0, (dx * dx + dy * dy) ** 0.5)
                if distance <= TILE * 12 and self._entity_in_viewport(entity):
                    speed = 2.2 if behavior == "shoot" else 2.65
                    self.enemy_projectiles.append(
                        {"x": ex, "y": ey, "vx": dx / distance * speed, "vy": dy / distance * speed, "life": 100}
                    )
                    cooldown = 82 if behavior == "shoot" else 68
                    self.note("hit")
                else:
                    cooldown = 20
            entity.extra["cooldown"] = cooldown

    def _tick_boss_behaviors(self) -> None:
        """Give each boss an authored arena motion and readable field ability."""

        if self.body is None:
            return
        import math

        player_x, player_y = self.body.center
        for entity in self.entities:
            if entity.kind != "boss" or not entity.alive or entity.extra.get("converted") or entity.extra.get("in_combat"):
                continue
            entity.extra["field_fight_ticks"] = max(0, int(entity.extra.get("field_fight_ticks") or 0) - 1)
            if not self._boss_arena_ready(entity):
                entity.extra["offset_y"] = 0.0
                continue
            boss_id = str(entity.extra.get("boss") or CAMPAIGN_ROSTER[self.chapter_index].boss.id)
            default_behavior, default_cooldown, default_ability = BOSS_BEHAVIORS.get(
                boss_id,
                ("stamp-hop", 90, "forms"),
            )
            behavior = str(entity.extra.get("behavior") or default_behavior)
            base_cooldown = int(entity.extra.get("base_cooldown") or default_cooldown)
            ability = str(entity.extra.get("ability") or default_ability)
            home_x = float(entity.extra.setdefault("home_x", entity.x))
            home_y = float(entity.extra.setdefault("home_y", entity.y))
            phase = float(entity.extra.get("phase") or 0.0) + 0.055
            entity.extra["phase"] = phase
            entity.extra["dir"] = -1 if player_x < entity.x * TILE else 1
            if behavior == "stamp-hop":
                entity.x = home_x - 1.2 + math.sin(phase * 0.8) * 1.2
                entity.extra["offset_y"] = -max(0.0, math.sin(phase * 2.0)) * 13.0
            elif behavior == "hover":
                entity.x = home_x - 2.0 + math.sin(phase * 0.75) * 2.2
                entity.extra["offset_y"] = -13.0 + math.sin(phase * 1.7) * 7.0
            elif behavior == "charge":
                sweep = (phase * 0.72) % 2.0
                sweep = sweep if sweep <= 1.0 else 2.0 - sweep
                entity.x = home_x - 5.8 + sweep * 6.0
                entity.extra["offset_y"] = -max(0.0, math.sin(phase * 3.0)) * 4.0
            elif behavior == "phase":
                lane = int(phase / 1.8) % 3
                entity.x = home_x - (1.0, 4.5, 7.0)[lane]
                entity.extra["offset_y"] = -3.0 + math.sin(phase * 1.4) * 3.0
                entity.extra["phasing"] = int(phase * 10) % 18 < 4
            elif behavior == "orbit":
                entity.x = home_x - 3.5 + math.cos(phase) * 3.2
                entity.extra["offset_y"] = -18.0 + math.sin(phase) * 13.0
            elif behavior == "cyber-penguin":
                sweep = (phase * 0.58) % 2.0
                sweep = sweep if sweep <= 1.0 else 2.0 - sweep
                entity.x = home_x - 4.2 + sweep * 4.5
                entity.extra["offset_y"] = -max(0.0, math.sin(phase * 2.4)) * 10.0
            else:
                entity.x = home_x - 3.2 + math.sin(phase * 0.9) * 3.0
                entity.extra["offset_y"] = -8.0 + math.sin(phase * 1.8) * 9.0

            cooldown = int(entity.extra.get("ability_cooldown") or base_cooldown) - 1
            ex = entity.x * TILE + TILE / 2
            ey = home_y * TILE + TILE / 2 + float(entity.extra.get("offset_y") or 0.0) - 14.0
            dx, dy = player_x - ex, player_y - ey
            distance = max(1.0, (dx * dx + dy * dy) ** 0.5)
            if cooldown <= 0 and distance <= TILE * 18:
                penalty = 70 if boss_id == "goliath" else 55

                def emit(
                    sx: float,
                    sy: float,
                    vx: float,
                    vy: float,
                    *,
                    life: int = 120,
                    homing: bool = False,
                ) -> None:
                    self.enemy_projectiles.append(
                        {
                            "x": sx,
                            "y": sy,
                            "vx": vx,
                            "vy": vy,
                            "life": life,
                            "style": ability,
                            "boss": boss_id,
                            "penalty": penalty,
                            "homing": homing,
                        }
                    )

                aimed_x, aimed_y = dx / distance, dy / distance
                if ability == "forms":
                    # Paperwork descends in a staggered filing row around the
                    # player's projected position rather than behaving like a
                    # renamed ordinary bullet.
                    for index, offset in enumerate((-24.0, 0.0, 24.0)):
                        emit(player_x + offset, player_y - 72.0 - index * 7.0, offset * -0.006, 2.45 + index * 0.15, life=74)
                elif ability == "version-volley":
                    for index in range(5):
                        spread = (index - 2) * 0.18
                        cos_a, sin_a = math.cos(spread), math.sin(spread)
                        emit(ex, ey, (aimed_x * cos_a - aimed_y * sin_a) * 2.75, (aimed_x * sin_a + aimed_y * cos_a) * 2.75)
                elif ability == "banner-wave":
                    direction = -1.0 if player_x < ex else 1.0
                    ground_y = self.body.feet[1] - 4.0
                    emit(ex, ground_y, direction * 3.7, 0.0, life=100)
                    emit(ex - direction * 10.0, ground_y - 7.0, direction * 3.25, 0.0, life=106)
                elif ability == "lock-pulse":
                    for index in range(8):
                        angle = math.tau * index / 8.0 + phase * 0.15
                        emit(ex, ey, math.cos(angle) * 2.35, math.sin(angle) * 2.35, life=105)
                elif ability == "gravity-shard":
                    for spread in (-0.20, 0.20):
                        cos_a, sin_a = math.cos(spread), math.sin(spread)
                        emit(ex, ey, (aimed_x * cos_a - aimed_y * sin_a) * 2.55, (aimed_x * sin_a + aimed_y * cos_a) * 2.55, life=150, homing=True)
                elif ability == "malware-fish":
                    # The remote penguin's launcher spits a low/center/high
                    # spread, giving the first phase its own readable rhythm.
                    for index, vertical in enumerate((-0.42, 0.0, 0.42)):
                        emit(ex, ey - index * 3.0, aimed_x * 3.0, aimed_y * 2.0 + vertical, life=118)
                else:  # Goliath's argument storm blankets a wide escape fan.
                    for index in range(7):
                        spread = (index - 3) * 0.19
                        cos_a, sin_a = math.cos(spread), math.sin(spread)
                        speed = 2.8 + (index % 2) * 0.45
                        emit(ex, ey, (aimed_x * cos_a - aimed_y * sin_a) * speed, (aimed_x * sin_a + aimed_y * cos_a) * speed, life=135)
                entity.extra["ability_flash"] = 16
                entity.extra["ability_count"] = int(entity.extra.get("ability_count") or 0) + 1
                self.messages.append(f"{CAMPAIGN_ROSTER[self.chapter_index].boss.name}: {ability.replace('-', ' ').upper()}!")
                self.note("hit")
                cooldown = base_cooldown
            entity.extra["ability_cooldown"] = cooldown
            entity.extra["ability_flash"] = max(0, int(entity.extra.get("ability_flash") or 0) - 1)

    def _tick_enemy_projectiles(self) -> None:
        if self.body is None:
            self.enemy_projectiles = []
            return
        px, py = self.body.center
        live: list[dict[str, Any]] = []
        for shot in self.enemy_projectiles:
            initial_speed = math.hypot(float(shot["vx"]), float(shot["vy"]))
            shot.setdefault("distance_left", initial_speed * max(0, int(shot["life"])))
            if shot.get("homing"):
                dx, dy = px - float(shot["x"]), py - float(shot["y"])
                distance = max(1.0, (dx * dx + dy * dy) ** 0.5)
                shot["vx"] = float(shot["vx"]) * 0.96 + dx / distance * 0.12
                shot["vy"] = float(shot["vy"]) * 0.96 + dy / distance * 0.12
            speed = math.hypot(float(shot["vx"]), float(shot["vy"]))
            shot["distance_left"] = float(shot["distance_left"]) - speed
            radius = float(shot.get("radius") or 2.5)
            old_x, old_y = float(shot["x"]), float(shot["y"])
            next_x = old_x + float(shot["vx"])
            if overlapping_tiles(
                self.tiles,
                next_x - radius,
                old_y - radius,
                radius * 2,
                radius * 2,
                SOLID,
            ):
                shot["vx"] = -float(shot["vx"])
                next_x = old_x
                shot["ricochets"] = int(shot.get("ricochets") or 0) + 1
                self.note("hit")
            next_y = old_y + float(shot["vy"])
            if overlapping_tiles(
                self.tiles,
                next_x - radius,
                next_y - radius,
                radius * 2,
                radius * 2,
                SOLID,
            ):
                shot["vy"] = -float(shot["vy"])
                next_y = old_y
                shot["ricochets"] = int(shot.get("ricochets") or 0) + 1
                self.note("hit")
            shot["x"] = next_x
            shot["y"] = next_y
            shot["life"] -= 1
            if abs(float(shot["x"]) - px) < 7 and abs(float(shot["y"]) - py) < 10:
                direction = 1 if float(shot["vx"]) >= 0 else -1
                self.body = replace(self.body, vx=direction * 2.6, vy=min(self.body.vy, -2.2))
                style = str(shot.get("style") or "talking-point")
                self.messages.append(f"{style.replace('-', ' ').title()} knocks you off balance.")
                self._penalize_score(int(shot.get("penalty") or 40), f"{style.replace('-', ' ')} impact")
                self.flash_ticks = 5
                self.flash_kind = "combat"
                continue
            if shot["life"] > 0 and float(shot["distance_left"]) > 0.0:
                live.append(shot)
        self.enemy_projectiles = live

    def _entity_in_viewport(self, entity: Entity) -> bool:
        """True when any of an actor's tile-sized anchor is currently visible."""

        left, top = self.cam_x, self.cam_y
        right, bottom = left + 320.0, top + 180.0
        ex = entity.x * TILE + float(entity.extra.get("offset_x") or 0.0)
        ey = entity.y * TILE + float(entity.extra.get("offset_y") or 0.0)
        return ex + TILE > left and ex < right and ey + TILE > top and ey < bottom

    def _entities_for_map(
        self,
        tiles: list[str],
        chapter: dict[str, Any],
        map_spec: dict[str, Any],
        index: int,
    ) -> list[Entity]:
        entities: list[Entity] = []
        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if cell in {"P", "H"}:
                    entities.append(Entity("penguin", x, y, extra={"secret": cell == "H"}))
                elif cell == "E":
                    motifs = tuple(chapter.get("enemyMotifs") or ENEMY_MOTIFS[index % len(ENEMY_MOTIFS)])
                    variant = motifs[(x + y) % len(motifs)]
                    behavior, hp = ENEMY_BEHAVIORS[variant]
                    entities.append(
                        Entity(
                            "enemy",
                            x,
                            y,
                            extra={"hp": hp, "max_hp": hp, "variant": variant, "behavior": behavior, "home": x, "dir": 1},
                        )
                    )
                elif cell == "O":
                    entities.append(Entity("logo", x, y))
                elif cell == "C":
                    authored_pool = tuple(chapter.get("itemPool") or ())
                    if (x * 17 + y * 31 + index * 13) % 23 == 0:
                        item = RARE_BS_RESET_ITEM
                    elif authored_pool:
                        item = authored_pool[(x + y + index * 2) % len(authored_pool)]
                    else:
                        item = COMMON_ITEMS[(x + y + index * 2) % len(COMMON_ITEMS)]
                    entities.append(Entity("item", x, y, extra={"item": item}))
                elif cell == "B":
                    payload = ("penguin", "empty", "bomb", "boost")[(x + y) % 4]
                    entities.append(Entity("block", x, y, extra={"hits": 0, "payload": payload}))
                elif cell == "X":
                    boss_id = CAMPAIGN_ROSTER[index].boss.id
                    behavior, cooldown, ability = BOSS_BEHAVIORS[boss_id]
                    entities.append(
                        Entity(
                            "boss",
                            x,
                            y,
                            extra={
                                "boss": boss_id,
                                "hp": BOSS_FIELD_HEALTH,
                                "max_hp": BOSS_FIELD_HEALTH,
                                "behavior": behavior,
                                "ability": ability,
                                "ability_cooldown": cooldown,
                                "home_x": x,
                                "home_y": y,
                                "dir": -1,
                                "phase": 0.0,
                            },
                        )
                    )
                elif cell == "W":
                    entities.append(
                        Entity(
                            "enemy",
                            x,
                            y,
                            extra={"hp": 4, "max_hp": 4, "variant": "lint-launcher", "behavior": "shoot", "home": x, "warden": True},
                        )
                    )
                elif cell == "G":
                    entities.append(Entity("gate", x, y, extra={"open": False}))
        boss = next((entity for entity in entities if entity.kind == "boss"), None)
        if boss is not None:
            # The procedural grammar reserves a twenty-tile boss arena. Its
            # entrance gate begins raised, then drops behind David once his
            # complete hitbox crosses it. The collision column spans the
            # complete map rather than only the local floor corridor, so a
            # tall route or gust cannot bypass the encounter overhead.
            gate_x = max(2, int(boss.x) - 12)
            gate_top = 0
            gate_bottom = len(tiles) - 1
            gate_height = len(tiles)
            entities.append(
                Entity(
                    "boss-gate",
                    gate_x,
                    gate_bottom,
                    extra={
                        "state": "open",
                        "height": gate_height,
                        "closing_ticks": 0,
                        "close_total": 12,
                        "boss": boss.extra.get("boss"),
                        "floor_y": int(boss.y),
                        "cells": [(gate_x, gy) for gy in range(gate_top, gate_bottom + 1)],
                    },
                )
            )
            if boss.extra.get("boss") == "goliath":
                self._configure_goliath_entity(boss, entities)
        for portal in map_spec.get("portals") or ():
            entities.append(
                Entity(
                    "network",
                    float(portal["x"]),
                    float(portal["y"]),
                    extra={
                        **dict(portal),
                        "portal": str(portal["id"]),
                    },
                )
            )
        if not map_spec.get("portals"):
            for link in chapter.get("networkLinks") or ():
                y = int(link["y"])
                entry_x = int(link["entryX"])
                exit_x = int(link["exitX"])
                common = {"link": str(link["id"]), "protocol": str(link["protocol"])}
                entities.extend(
                    (
                        Entity("network", entry_x, y, extra={**common, "destination": (exit_x, y), "direction": 1, "operation": str(link["forwardOperation"])}),
                        Entity("network", exit_x, y, extra={**common, "destination": (entry_x, y), "direction": -1, "operation": str(link["reverseOperation"])}),
                    )
                )
        for spec in map_spec.get("tiltingPlatforms", chapter.get("tiltingPlatforms") or ()):
            entities.append(Entity("tilt-platform", float(spec["x"]), float(spec["y"]), extra=dict(spec)))
        for spec in map_spec.get("movingPlatforms", chapter.get("movingPlatforms") or ()):
            extra = dict(spec)
            extra.update({"base_x": float(spec["x"]), "base_y": float(spec["y"]), "prev_x": float(spec["x"]), "prev_y": float(spec["y"])})
            entities.append(Entity("moving-platform", float(spec["x"]), float(spec["y"]), extra=extra))
        for spec in map_spec.get("windColumns", chapter.get("windColumns") or ()):
            entities.append(Entity("wind-column", float(spec["x"]), float(spec["y"]), extra=dict(spec)))
        return entities

    @property
    def active_palette(self) -> str:
        if 0 <= self.map_index < len(self.chapter_map_palettes):
            return self.chapter_map_palettes[self.map_index]
        return str(self.chapter.get("palette") or CAMPAIGN_ROSTER[self.chapter_index].palette)

    def _assign_omega_blocks(self) -> None:
        """Promote five well-spaced, physically attackable blocks into OMEGA."""

        candidates: list[tuple[int, Entity]] = []
        for map_index, entities in enumerate(self.chapter_map_entities):
            tiles = self.chapter_map_tiles[map_index]
            blocks = sorted(
                (
                    entity
                    for entity in entities
                    if entity.kind == "block"
                    and self._omega_block_has_attack_position(tiles, int(entity.x), int(entity.y))
                ),
                key=lambda entity: (entity.x, entity.y),
            )
            last_x = -999.0
            for entity in blocks:
                if entity.x - last_x < 10 and candidates:
                    continue
                candidates.append((map_index, entity))
                last_x = entity.x
        if len(candidates) < len(OMEGA_LETTERS):
            candidates = [
                (map_index, entity)
                for map_index, entities in enumerate(self.chapter_map_entities)
                for entity in entities
                if entity.kind == "block"
                and self._omega_block_has_attack_position(
                    self.chapter_map_tiles[map_index], int(entity.x), int(entity.y)
                )
            ]
        if len(candidates) < len(OMEGA_LETTERS):
            raise RuntimeError("generated chapter lacks five attackable OMARCHY blocks")
        for letter, (map_index, entity) in zip(OMEGA_LETTERS, candidates):
            entity.kind = "omega-block"
            entity.extra.update({"letter": letter, "omega": True, "map": map_index})
            if letter in self.omega_letters:
                entity.alive = False
                x, y = int(entity.x), int(entity.y)
                row = list(self.chapter_map_tiles[map_index][y])
                row[x] = "."
                self.chapter_map_tiles[map_index][y] = "".join(row)

    @staticmethod
    def _omega_block_has_attack_position(tiles: list[str], x: int, y: int) -> bool:
        """Prove a block has room for either a side kick or a head bump."""

        if not tiles or not (1 <= y < len(tiles) - 2 and 1 <= x < len(tiles[0]) - 1):
            return False

        def cell(tx: int, ty: int) -> str:
            if 0 <= ty < len(tiles) and 0 <= tx < len(tiles[0]):
                return tiles[ty][tx]
            return "#"

        # Same-level footing on either side supports a deliberate kick.
        for approach_x in (x - 1, x + 1):
            if (
                cell(approach_x, y) not in SOLID
                and cell(approach_x, y - 1) not in SOLID
                and cell(approach_x, y + 1) in SOLID
            ):
                return True
        # A clear vertical lane with footing three or four cells below fits
        # the standard jump arc and the full visual head-contact sweep.
        for support_y in (y + 3, y + 4):
            if cell(x, support_y) not in SOLID:
                continue
            if all(cell(x, clear_y) not in SOLID for clear_y in range(y + 1, support_y)):
                return True
        return False

    @staticmethod
    def _cow_level_spec() -> dict[str, Any]:
        """Return the deterministic high-speed secret-stage grammar."""

        width, height, floor = COW_LEVEL_WIDTH, COW_LEVEL_HEIGHT, COW_LEVEL_FLOOR
        grid = [["." for _ in range(width)] for _ in range(height)]
        for y in range(floor, height):
            for x in range(width):
                grid[y][x] = "#"
        # Even the high-speed secret route breaks the old uniform foundation:
        # one compact rise and one shallow depression introduce readable
        # terrain rhythm without interrupting its launch-lane flow.
        for x in range(45, 51):
            grid[floor - 1][x] = "#"
        for x in range(90, 97):
            grid[floor][x] = "."
        grid[floor - 1][4] = "S"
        # Hatch bumper sits on a one-tile stoop so a slide still clears the
        # walkway to the left-hand EXIT. Remaining bumpers keep launch lanes.
        for x in (6, 7, 8):
            grid[floor - 2][x] = "="
        grid[floor - 3][7] = "^"
        for x in (27, 56, 88, 122, 158, 196, 224):
            grid[floor - 1][x] = "^"
        for x0, y, length in (
            (34, floor - 7, 10),
            (69, floor - 12, 12),
            (111, floor - 8, 9),
            (141, floor - 22, 14),
            (181, floor - 9, 11),
            (209, floor - 18, 14),
        ):
            for x in range(x0, x0 + length):
                grid[y][x] = "="
        # The opening reward arcs are sampled directly from representative
        # cannon ballistics. They end with the launch arena instead of turning
        # the entire level into unrelated parabolas.
        launch_x, launch_y = 16, floor - 8
        for arc_index, (angle, charge) in enumerate(((22.0, 0.76), (43.0, 0.90), (64.0, 1.0))):
            power = CANNON_MIN_POWER + (CANNON_MAX_POWER - CANNON_MIN_POWER) * charge
            radians = math.radians(angle)
            vx, vy = power * math.cos(radians), -power * math.sin(radians)
            for x in range(launch_x + 4 + arc_index, 108, 5):
                elapsed = (x - launch_x) * TILE / max(0.01, vx)
                y_pixels = launch_y * TILE + vy * elapsed + 0.5 * GRAVITY * elapsed * elapsed
                y = round(y_pixels / TILE)
                if y >= floor:
                    break
                if 20 <= y < floor and grid[y][x] == ".":
                    grid[y][x] = "C" if (x + arc_index) % 4 == 0 else "B"

        # Beyond the cannon arena the secret route follows ordinary placement
        # grammar, just at bonus-stage density: supported penguins and tools,
        # jump-height blocks, and rewards distributed over authored platforms.
        for x in range(112, width - 3, 10):
            if grid[floor - 1][x] == ".":
                grid[floor - 1][x] = "C"
        for x in range(120, width - 4, 23):
            if grid[floor - 1][x] == ".":
                grid[floor - 1][x] = "P"
        for x in range(114, width - 4, 11):
            if grid[floor - 4][x] == ".":
                grid[floor - 4][x] = "B"
        for platform_index, (x0, y, length) in enumerate(
            ((111, floor - 8, 9), (141, floor - 22, 14), (181, floor - 9, 11), (209, floor - 18, 14))
        ):
            penguin_x = x0 + length // 2
            grid[y - 1][penguin_x] = "P"
            for x in range(x0 + 1, x0 + length - 1, 3):
                if x == penguin_x:
                    continue
                grid[y - 1][x] = "C"
            block_y = max(2, y - 4)
            for x in range(x0 + 2 + platform_index % 2, x0 + length - 1, 5):
                if grid[block_y][x] == ".":
                    grid[block_y][x] = "B"
        return {
            "id": "omega-cow-level",
            "tiles": ["".join(row) for row in grid],
            "palette": "cow",
            "windColumns": [
                {"x": 52, "y": floor - 22, "width": 2, "height": 22, "strength": 0.52},
                {"x": 101, "y": floor - 26, "width": 2, "height": 26, "strength": 0.48},
                {"x": 164, "y": floor - 28, "width": 2, "height": 28, "strength": 0.56},
                {"x": 220, "y": floor - 24, "width": 2, "height": 24, "strength": 0.52},
            ],
            "movingPlatforms": [
                {"x": 59, "y": floor - 8, "width": 5, "axis": "vertical", "range": 4, "phase": 0.2},
                {"x": 174, "y": floor - 12, "width": 5, "axis": "horizontal", "range": 5, "phase": 2.1},
            ],
        }

    def _ensure_secret_level(self) -> int:
        if 0 <= self.secret_map_index < len(self.chapter_map_tiles):
            return self.secret_map_index
        spec = self._cow_level_spec()
        spec["tiles"], spec["upperTraversal"] = add_skyway(list(spec["tiles"]), self.world.identity.seed + ":cow", "cow", pad=False)
        # An optional workshop shelf by the far exit keeps the cannon's
        # launch lane clear while giving this independently mounted map access.
        rows = list(spec["tiles"])
        ex, ey = COW_LEVEL_WIDTH - 14, COW_LEVEL_FLOOR - 4
        for x in range(ex - 2, ex + 3):
            rows[ey + 1] = rows[ey + 1][:x] + "=" + rows[ey + 1][x + 1:]
        rows[ey] = rows[ey][:ex] + "O" + rows[ey][ex + 1:]
        spec["tiles"] = rows
        tiles = list(spec["tiles"])
        entities = self._entities_for_map(tiles, self.chapter, spec, self.chapter_index)
        floor = COW_LEVEL_FLOOR
        entities.append(Entity("omega-door", 2, floor - 1, extra={"exit": True, "secret": True}))
        entities.append(
            Entity("omega-door", COW_LEVEL_WIDTH - 4, floor - 1, extra={"exit": True, "secret": True})
        )
        entities.append(
            Entity(
                "cow-cannon",
                8,
                floor - 1,
                extra={"angle": CANNON_DEFAULT_ANGLE, "width": CANNON_DRAW_WIDTH, "height": CANNON_DRAW_HEIGHT},
            )
        )
        for index, (variant, x) in enumerate(
            (("cow", 21), ("llama", 48), ("cow", 82), ("llama", 119), ("cow", 156), ("llama", 192), ("cow", 226))
        ):
            behavior, hp = ENEMY_BEHAVIORS[variant]
            entities.append(
                Entity(
                    "enemy",
                    x,
                    floor - 1,
                    extra={
                        "variant": variant,
                        "behavior": behavior,
                        "hp": hp,
                        "max_hp": hp,
                        "home": x,
                        "dir": 1 if index % 2 == 0 else -1,
                        "instant_convert": True,
                        "friendly_animal": True,
                    },
                )
            )
        self.secret_map_index = len(self.chapter_map_tiles)
        self.chapter_map_tiles.append(tiles)
        self.chapter_map_originals.append(list(tiles))
        self.chapter_map_upper.append(spec["upperTraversal"])
        self.chapter_map_entities.append(entities)
        self.chapter_map_palettes.append("cow")
        return self.secret_map_index

    def _door_location_near_player(self) -> tuple[int, int]:
        assert self.body is not None
        center = int(self.body.center[0] // TILE)
        width, height = len(self.tiles[0]), len(self.tiles)
        player_row = max(3, min(height - 2, int(self.body.feet[1] // TILE) - 1))
        camera_left = int(self.cam_x // TILE)
        camera_right = int((self.cam_x + 320) // TILE)
        candidates: list[tuple[float, int, int]] = []
        for y in range(3, height - 1):
            for x in range(2, width - 2):
                if self.tiles[y + 1][x] not in SOLID:
                    continue
                if not all(self.tiles[y - dy][x] not in SOLID for dy in range(3)):
                    continue
                horizontal = abs(x - center)
                if horizontal < 3:
                    continue
                viewport_penalty = 0 if camera_left + 1 <= x <= camera_right - 1 else 100
                score = viewport_penalty + horizontal + abs(y - player_row) * 3.0
                candidates.append((score, x, y))
        if candidates:
            _, x, y = min(candidates)
            return x, y
        return max(2, min(width - 3, center + 5)), max(3, height - 5)

    def _spawn_omega_door(self) -> Entity | None:
        if len(self.omega_letters) < len(OMEGA_LETTERS) or self.body is None:
            return None
        self._ensure_secret_level()
        existing = next((entity for entity in self.entities if entity.kind == "omega-door" and not entity.extra.get("exit")), None)
        if existing is not None:
            return existing
        if self.omega_door_spawned:
            # The completed route belongs to the map on which it appeared.
            # Refreshed OMEGA blocks may still be broken for score, but must
            # not clone the secret entrance into every map.
            return None
        x, y = self._door_location_near_player()
        door = Entity("omega-door", x, y, extra={"secret": True, "exit": False})
        self.entities.append(door)
        self.omega_door_spawned = True
        self.omega_door_map = self.map_index
        self._reset_omega_blocks()
        self.messages.append(f"OMEGA COMPLETE · A hidden route opens. Stand in the door and press {self.prompt_binding('up')}.")
        self.flash_ticks = 18
        self.flash_kind = "convert"
        self.note("logo")
        return door

    def _reset_omega_blocks(self) -> None:
        """Restore all five collectible blocks after their route is unlocked."""

        for map_index, entities in enumerate(self.chapter_map_entities):
            tiles = self.chapter_map_tiles[map_index]
            for entity in entities:
                if entity.kind != "omega-block":
                    continue
                entity.alive = True
                x, y = int(entity.x), int(entity.y)
                if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]):
                    row = list(tiles[y])
                    row[x] = "B"
                    tiles[y] = "".join(row)

    def _collect_omega_letter(self, entity: Entity) -> None:
        letter = str(entity.extra.get("letter") or "")
        if letter and letter not in self.omega_letters:
            owned = set(self.omega_letters + letter)
            self.omega_letters = "".join(ch for ch in OMEGA_LETTERS if ch in owned)
        self._award_score(500, f"OMEGA block {letter}", x=entity.x * TILE + 8, y=entity.y * TILE, combo_event="proof")
        self.messages.append(f"O-M-E-G-A · {len(self.omega_letters)}/5")
        if len(self.omega_letters) == len(OMEGA_LETTERS):
            self._spawn_omega_door()

    def _enter_secret_level(self) -> None:
        assert self.body is not None
        target = self._ensure_secret_level()
        self.secret_return_map = self.map_index
        self.secret_return_position = (self.body.x, self.body.y)
        # Entering the secret stage starts a fresh OMEGA run without removing
        # the already-earned doorway on the parent map. The same five source
        # blocks can be collected again after the player returns, but the
        # existing portal remains the sole route instance.
        self.omega_letters = ""
        self._reset_omega_blocks()
        self.player_bs = 0
        self._activate_map(target, reset_body=True)
        self.scene = "action"
        self.messages.append("THE COW LEVEL · Every animal is one good interaction away from joining you.")
        self.flash_ticks = 12
        self.flash_kind = "convert"

    def _leave_secret_level(self) -> None:
        target = max(0, min(self.secret_return_map, self.secret_map_index - 1))
        return_x, return_y = self.secret_return_position
        # Followers must be instantiated only after the return body has been
        # restored. Spawning during map activation placed them around that
        # map's default S tile and made them sprint across the whole scene.
        self._activate_map(target, reset_body=True, spawn_companions=False)
        assert self.body is not None
        self.body = replace(self.body, x=return_x, y=return_y, vx=0.0, vy=0.0)
        self._spawn_persistent_companions()
        self._snap_camera()
        self.messages.append("Secret route closed behind the herd.")

    def _tick_omega_doors(self, inp: InputState) -> bool:
        if not inp.up_pressed:
            return False
        for entity in self.entities:
            if entity.kind != "omega-door" or not entity.alive:
                continue
            if not self._entity_overlaps_player(entity, full_sprite=True):
                continue
            if entity.extra.get("exit"):
                self._leave_secret_level()
            else:
                self._enter_secret_level()
            self.note("ui")
            return True
        return False

    def camera_target(self) -> tuple[float, float]:
        """Return the exact camera destination for the current player/map."""

        if self.boss_defeat and (self.scene == "boss-defeat" or self.scene == "pause" and self.paused_from == "boss-defeat"):
            return self.boss_defeat["cameraX"], self.boss_defeat["cameraY"]

        if self.body is None or not self.tiles:
            return 0.0, 0.0
        look = 0.0 if self.cannon_loaded or self.cannon_launch_active else 24.0 * self.body.facing
        max_x = max(0.0, len(self.tiles[0]) * TILE - 320.0)
        max_y = max(0.0, len(self.tiles) * TILE - 180.0)
        target_x = self.body.center[0] - 160.0 + look
        target_y = self.body.center[1] - 90.0
        if self.scene == "edit":
            # Keep a quiet central editing band, then pan across the entire
            # playfield as the cursor crosses it. The hero stays in place.
            cursor_y = (self.edit_cursor[1] + 0.5) * TILE
            target_x = self.cam_x
            target_y = min(self.cam_y, cursor_y - 32.0) if cursor_y < self.cam_y + 32.0 else max(self.cam_y, cursor_y - 128.0)
        elif self.scene == "flight" and self.flight_direction == "out":
            # Frame the construction space above the left-behind player.
            target_y = self.body.feet[1] - 158.0
        elif self.cannon_loaded:
            target_x += CANNON_CAMERA_BIAS_RIGHT_TILES * TILE
            target_y -= CANNON_CAMERA_BIAS_UP_TILES * TILE
        elif self.cannon_launch_active:
            span = max(1.0, CANNON_MAX_ANGLE - CANNON_MIN_ANGLE)
            t = max(0.0, min(1.0, (self.cannon_angle - CANNON_MIN_ANGLE) / span))
            tiles = CANNON_FLIGHT_CAMERA_BIAS_MIN_TILES + (
                CANNON_FLIGHT_CAMERA_BIAS_MAX_TILES - CANNON_FLIGHT_CAMERA_BIAS_MIN_TILES
            ) * t
            radians = math.radians(self.cannon_angle)
            magnitude = tiles * TILE
            target_x += math.cos(radians) * magnitude
            target_y -= math.sin(radians) * magnitude
        return (
            max(0.0, min(target_x, max_x)),
            max(0.0, min(target_y, max_y)),
        )

    def _snap_camera(self) -> None:
        self.cam_x, self.cam_y = self.camera_target()

    def _activate_map(
        self,
        index: int,
        *,
        reset_body: bool = False,
        spawn_companions: bool = True,
    ) -> None:
        self.cannon_loaded = False
        self.cannon_charge_ticks = 0
        self.cannon_charge_armed = False
        self.cannon_entry_lock_ticks = 0
        self.cannon_launch_active = False
        self.cannon_launch_ticks = 0
        self.cannon_angle = CANNON_DEFAULT_ANGLE
        if self.chapter_map_entities and self.entities:
            self.entities[:] = [entity for entity in self.entities if not entity.extra.get("companion")]
        self.map_index = max(0, min(index, len(self.chapter_map_tiles) - 1))
        self.tiles = self.chapter_map_tiles[self.map_index]
        self.original_tiles = self.chapter_map_originals[self.map_index]
        self.entities = self.chapter_map_entities[self.map_index]
        for entity in self.entities:
            if entity.kind == "cow-cannon":
                entity.extra["angle"] = CANNON_DEFAULT_ANGLE
        if reset_body or self.body is None:
            try:
                self.body = spawn_body(self.tiles)
            except ValueError:
                portal = next((entity for entity in self.entities if entity.kind == "network"), None)
                if portal is None:
                    raise
                self.body = Body(
                    x=portal.x * TILE + (TILE - 10) / 2,
                    y=(portal.y + 1) * TILE - 18,
                    vx=0.0,
                    vy=0.0,
                    on_ground=True,
                    coyote=0,
                    buffer=0,
                    facing=1,
                )
        if spawn_companions:
            self._spawn_persistent_companions()
        self._snap_camera()

    def _load_chapter(self, index: int) -> None:
        assert self.world is not None
        self.chapter_index = index
        self.player_bs = 0
        self.post_boss = False
        self.post_boss_ticks = 0
        chapter = self.world.chapters[index]
        map_specs = list(chapter.get("maps") or ())
        if not map_specs:
            map_specs = [{"id": f"{chapter['chapterId']}-main", "tiles": list(chapter["tiles"]), "upperTraversal": chapter.get("upperTraversal") or {}}]
        self.chapter_map_tiles = [list(spec["tiles"]) for spec in map_specs]
        self.chapter_map_originals = [list(spec["tiles"]) for spec in map_specs]
        self.chapter_map_upper = [dict(spec.get("upperTraversal") or {}) for spec in map_specs]
        self.chapter_map_entities = [
            self._entities_for_map(self.chapter_map_tiles[map_index], chapter, spec, index)
            for map_index, spec in enumerate(map_specs)
        ]
        for map_index, upper in enumerate(self.chapter_map_upper):
            for lift in upper.get("lifts", []):
                self.chapter_map_entities[map_index].extend(self._skyway_lift_pair(lift))
        base_palette = str(chapter.get("palette") or CAMPAIGN_ROSTER[index].palette)
        self.chapter_map_palettes = [str(spec.get("palette") or base_palette) for spec in map_specs]
        self.secret_map_index = -1
        self.omega_door_spawned = False
        self.omega_door_map = -1
        self._assign_omega_blocks()
        self.body = None
        self.entities = []
        self._activate_map(0, reset_body=True)
        if len(self.omega_letters) == len(OMEGA_LETTERS):
            self._spawn_omega_door()
        self.editing = False
        self.edit_ops = []
        self.edit_player_ghost = None
        self.edit_reward = None
        self.edit_baseline_reachable = set()
        self.edit_reachable = set()
        self.edit_new_reachable = set()
        self.edit_goal_ready = False
        self.combat = None
        self.projectiles = []
        self.enemy_projectiles = []
        self.attack_timer = 0
        self.action_reset_ticks = 0
        self.battle_queue = []
        self.battle_delay_ticks = 0
        self.battle_actor = ""
        self.battle_flash_ticks = 0
        self.network_ticks = 0
        self.network_operation = ""
        self.network_protocol = ""
        self.boss_defeat = {}
        self.boss_defeat_ticks = 0
        self.network_cooldown = 0
        self.network_armed = True
        self.network_destination_map = 0
        self.network_destination_portal = ""
        self.pit_exposure_ticks = 0
        spec = CAMPAIGN_ROSTER[index]
        self.messages.append(spec.blurb)
        if index == 0 and not self.post_boss:
            move = (
                "D-PAD"
                if self.last_input_device == "gamepad"
                else f"{self.prompt_binding('left')}/{self.prompt_binding('right')}"
            )
            self.messages.append(
                f"Move: {move} · "
                f"Jump: {self.prompt_binding('jump')} · Kick: {self.prompt_binding('action')} · "
                f"Pause: {self.prompt_binding('pause')}"
            )

    def dev_warp(self, target: str) -> str:
        """Warp to a deterministic chapter landmark for rapid playtesting.

        Grammar: ``[chapter-id:]start|boss|boss-15|edit|portal|pit|cow|stage-map|prologue|map-N``. A chapter
        id on its own means that chapter's start. This deliberately operates
        on generated maps and entities rather than hardcoded coordinates.
        """

        if self.world is None:
            raise RuntimeError("developer warp requires a mounted world")
        raw = target.strip().lower()
        if not raw:
            raise ValueError("empty developer warp")
        chapter_ids = [str(chapter["chapterId"]) for chapter in self.world.chapters]
        chapter_index = self.chapter_index
        landmark = raw
        if ":" in raw:
            chapter_token, landmark = raw.split(":", 1)
        elif raw in chapter_ids or raw.isdigit():
            chapter_token, landmark = raw, "start"
        else:
            chapter_token = ""
        if chapter_token:
            if chapter_token.isdigit():
                chapter_index = max(0, min(len(chapter_ids) - 1, int(chapter_token) - 1))
            else:
                matches = [i for i, chapter_id in enumerate(chapter_ids) if chapter_id == chapter_token or chapter_id.startswith(chapter_token)]
                if len(matches) != 1:
                    raise ValueError(f"unknown or ambiguous chapter warp: {chapter_token}")
                chapter_index = matches[0]
        if chapter_index != self.chapter_index:
            self._load_chapter(chapter_index)

        landmark = landmark or "start"
        if landmark == "prologue":
            self.story_beat = 0
            self.story_ticks = 0
            self.scene = "prologue"
            self.developer_mode = True
            result = f"{chapter_ids[chapter_index]}:prologue"
            self.messages.append(f"DEV WARP · {result}")
            return result
        if landmark == "stage-map":
            self._open_stage_map(min(chapter_index + 1, len(CAMPAIGN_ROSTER) - 1), transition=False)
            self.developer_mode = True
            result = f"{chapter_ids[chapter_index]}:stage-map"
            self.messages.append(f"DEV WARP · {result}")
            return result
        if landmark == "cow":
            self.omega_letters = OMEGA_LETTERS
            self._ensure_secret_level()
            self._enter_secret_level()
            self.developer_mode = True
            result = f"{chapter_ids[chapter_index]}:cow"
            self.messages.append(f"DEV WARP · {result}")
            return result
        map_index = 0
        target_entity: Entity | None = None
        pit_cell: tuple[int, int] | None = None
        if landmark.startswith("map-"):
            map_index = max(0, min(len(self.chapter_map_tiles) - 1, int(landmark[4:]) - 1))
            landmark = "start"
        elif landmark in {"boss", "boss-15"}:
            wanted = "boss-gate" if landmark == "boss" else "boss"
            for i, entities in enumerate(self.chapter_map_entities):
                target_entity = next((entity for entity in entities if entity.kind == wanted), None)
                if target_entity is not None:
                    map_index = i
                    break
        elif landmark in {"edit", "portal"}:
            wanted = "logo" if landmark == "edit" else "network"
            for i, entities in enumerate(self.chapter_map_entities):
                target_entity = next((entity for entity in entities if entity.kind == wanted and entity.alive), None)
                if target_entity is not None:
                    map_index = i
                    break
        elif landmark == "pit":
            for i, tiles in enumerate(self.chapter_map_tiles):
                pit_cell = next(
                    ((x, y) for y, row in enumerate(tiles) for x, cell in enumerate(row) if cell == "M"),
                    None,
                )
                if pit_cell is not None:
                    map_index = i
                    break
        elif landmark != "start":
            raise ValueError(f"unknown developer landmark: {landmark}")

        if landmark != "start" and target_entity is None and pit_cell is None:
            raise ValueError(f"landmark {landmark!r} is absent from {chapter_ids[chapter_index]}")
        self._activate_map(map_index, reset_body=True)
        assert self.body is not None
        if target_entity is not None:
            if landmark == "boss":
                target_entity.extra["state"] = "open"
                target_entity.extra["closing_ticks"] = 0
                for gx, gy in target_entity.extra.get("cells") or ():
                    if 0 <= gy < len(self.tiles) and 0 <= gx < len(self.tiles[gy]):
                        row = list(self.tiles[gy])
                        if row[gx] in {"G", "g"}:
                            row[gx] = "."
                            self.tiles[gy] = "".join(row)
                tx = max(1.0, target_entity.x - 2.0)
            elif landmark == "boss-15":
                tx = max(1.0, float(target_entity.extra.get("arena_x", target_entity.x)) - 15.0)
            else:
                direction = int(target_entity.extra.get("direction") or 1)
                tx = target_entity.x - direction * 1.5
            ty = float(target_entity.extra.get("floor_y", target_entity.y))
            self.body = replace(
                self.body,
                x=tx * TILE + (TILE - self.body.width) / 2,
                y=(ty + 1) * TILE - 18,
                vx=0.0,
                vy=0.0,
                height=18.0,
                on_ground=True,
                on_ladder=False,
                crouching=False,
                sliding=False,
                slide_locked=False,
            )
        elif pit_cell is not None:
            px, py = pit_cell
            self.body = replace(
                self.body,
                x=px * TILE + (TILE - self.body.width) / 2,
                y=py * TILE,
                vx=0.0,
                vy=0.0,
                on_ground=False,
            )
        self._snap_camera()
        self.developer_mode = True
        result = f"{chapter_ids[chapter_index]}:{landmark}:map-{map_index + 1}"
        self.messages.append(f"DEV WARP · {result}")
        return result

    @property
    def identity_digest(self) -> str:
        if self.world is None:
            return ""
        return self.world.identity.digest()

    @property
    def chapter(self) -> dict[str, Any]:
        assert self.world is not None
        return self.world.chapters[self.chapter_index]

    @property
    def current_item(self) -> str:
        if not self.inventory:
            return "logic-bomb"
        return self.inventory[self.selected_item % len(self.inventory)]

    @property
    def current_attack(self) -> str:
        return self.selected_attack if self.selected_attack in ATTACKS else ATTACKS[0]

    @property
    def available_items(self) -> tuple[str, ...]:
        owned = set(self.inventory)
        return tuple(item for item in ITEMS if item in owned)

    def campaign_roster(self) -> list[str]:
        return campaign_roster_names()

    def unlocked_stage_indices(self) -> tuple[int, ...]:
        """Return the non-linear boss-map unlock graph from completed bosses."""

        completed = {
            index
            for index, spec in enumerate(CAMPAIGN_ROSTER)
            if spec.boss.id in self.converted
        }
        unlocked = {0, *completed}
        if 0 in completed:
            unlocked.update({1, 2, 3})
        if {1, 2, 3}.issubset(completed):
            unlocked.add(4)
        if 4 in completed:
            unlocked.add(5)
        return tuple(index for index in range(len(CAMPAIGN_ROSTER)) if index in unlocked)

    def _preferred_stage_cursor(self, preferred: int) -> int:
        unlocked = self.unlocked_stage_indices()
        unfinished = tuple(
            index
            for index in unlocked
            if CAMPAIGN_ROSTER[index].boss.id not in self.converted
        )
        choices = unfinished or unlocked
        return preferred if preferred in choices else choices[0]

    def _spatial_stage_neighbor(self, dx: int, dy: int) -> int:
        """Follow the visual two-row map instead of campaign list order."""

        if not (dx or dy):
            return self.stage_cursor
        direction = ((1 if dx > 0 else -1), 0) if dx else (0, (1 if dy > 0 else -1))
        return STAGE_NODE_NEIGHBORS.get(self.stage_cursor, {}).get(direction, self.stage_cursor)

    @property
    def character_name(self) -> str:
        if self.world is not None:
            return str(self.world.character.get("name") or DEFAULT_CHARACTER_NAME)
        return self.installer.choices.character.name or DEFAULT_CHARACTER_NAME

    @property
    def story_copy(self) -> str:
        _, copy, _ = PROLOGUE_BEATS[max(0, min(self.story_beat, len(PROLOGUE_BEATS) - 1))]
        return copy.format(character_name=self.character_name)

    def step(self, inp: InputState, *, frame_seconds: float = 1 / 60) -> None:
        self.tick += 1
        if self.audio_caption_ticks > 0:
            self.audio_caption_ticks -= 1
            if self.audio_caption_ticks == 0:
                self.audio_caption = ""
        self._tick_floaters()
        self._tick_score_combo()
        if inp.pause and self.scene not in {
            "installer",
            "prologue",
            "stage-map",
            "level-intro",
            "chapter-complete",
            "chapter-credits",
            "reroll-confirm",
            "ending",
            "credits",
        }:
            if self.scene == "remap":
                self.remap_waiting = False
                self.scene = "pause"
                self.note("ui")
                return
            if self.scene == "items":
                self.scene = "pause"
                self.note("ui")
                return
            if self.scene == "audio-settings":
                self.scene = "pause"
                self.note("ui")
                return
            if self.scene == "pause":
                self.scene = self.paused_from or "action"
            else:
                self.paused_from = self.scene
                self.scene = "pause"
            self.note("ui")
            return
        if self.scene == "pause":
            self._step_pause(inp)
            return
        if self.scene == "items":
            self._step_items(inp)
            return
        if self.scene == "audio-settings":
            self._step_audio_settings(inp)
            return
        if self.scene == "remap":
            self._step_remap(inp)
            return
        if self.scene == "customize":
            self._step_customize(inp)
            return
        if self.scene == "installer":
            self._step_installer(inp)
            return
        if self.scene == "prologue":
            self._step_prologue(inp)
            return
        if self.scene == "stage-map":
            self._step_stage_map(inp)
            return
        if self.scene == "level-intro":
            self._step_level_intro()
            return
        if self.scene == "oligarchy":
            if inp.interact or inp.jump_pressed:
                self.dismiss_oligarchy()
            return
        if self.scene == "chapter-complete":
            self._step_chapter_complete(inp)
            return
        if self.scene == "reroll-confirm":
            self._step_reroll_confirm(inp)
            return
        if self.scene == "recovery":
            self._step_recovery(inp)
            return
        if self.scene == "flight":
            self._step_flight(inp)
            return
        if self.scene == "network":
            self._step_network(inp)
            return
        if self.scene == "boss-defeat":
            self._step_boss_defeat()
            return
        if self.scene in {"ending", "credits", "chapter-credits"}:
            self._step_credits(inp, frame_seconds=frame_seconds)
            return
        if self.scene == "turn":
            self._step_turn(inp)
            return
        if self.editing:
            self._step_edit(inp)
            return
        if self.scene == "action":
            self._step_action(inp)

    def _installer_confirm(self, inp: InputState) -> bool:
        return bool(inp.jump_pressed or inp.action_pressed or inp.interact)

    def _step_installer(self, inp: InputState) -> None:
        self.installer.preload_characters()
        gum = self.installer.gum_page() is not None
        if gum and (inp.up_pressed or inp.down_pressed):
            self.installer.cycle(-1 if inp.up_pressed else 1)
            self.note("ui")
            return
        if (not gum or self.installer.step in {"confirm", "character"}) and inp.left_pressed:
            self.installer.cycle(-1)
            self.note("ui")
            return
        if (not gum or self.installer.step in {"confirm", "character"}) and inp.right_pressed:
            self.installer.cycle(1)
            self.note("ui")
            return
        confirm = self._installer_confirm(inp)
        if self.installer.step == "complete":
            self.installer.complete_ticks += 1
            if self.installer.awaiting_release or not self.installer.play_now_armed:
                if not confirm:
                    self.installer.awaiting_release = False
                    self.installer.play_now_armed = True
                return
            if confirm:
                self.confirm_play_now()
            return
        if self.installer.step == "progress":
            if confirm:
                self.installer.skip_progress()
                self.note("ui")
                return
            self.installer.tick_progress()
            return
        if confirm:
            self.installer.next_step()
            self.note("ui")

    def _step_prologue(self, inp: InputState) -> None:
        """Type, complete, and advance beats while supporting hold-to-skip."""

        if self.story_transition_ticks:
            self.story_transition_ticks += 1
            if self.story_transition_ticks >= PROLOGUE_LOGIN_TRANSITION_TICKS:
                self.messages.append("CONSCIOUSNESS MOUNTED · Select the first corrupted installation.")
                self._open_stage_map(0, transition=False)
            return
        self.story_ticks += 1
        advance = bool(inp.jump_pressed or inp.action_pressed or inp.interact)
        if inp.turn:
            self.story_skip_ticks = min(
                PROLOGUE_SKIP_HOLD_TICKS,
                self.story_skip_ticks + 1,
            )
            if self.story_skip_ticks >= PROLOGUE_SKIP_HOLD_TICKS:
                self.story_beat = len(PROLOGUE_BEATS) - 1
                self.story_ticks = max(PROLOGUE_BEAT_TICKS, len(self.story_copy) * PROLOGUE_TYPE_TICKS)
                self.flash_ticks = 14
                self.flash_kind = "combat"
                self.messages.append("CONSCIOUSNESS MOUNTED · Select the first corrupted installation.")
                self._open_stage_map(0, transition=False)
                return
        else:
            self.story_skip_ticks = max(
                0,
                self.story_skip_ticks - PROLOGUE_SKIP_COOL_TICKS,
            )
        if not advance:
            return
        copy_ticks = len(self.story_copy) * PROLOGUE_TYPE_TICKS
        if self.story_ticks < copy_ticks:
            self.story_ticks = copy_ticks
            self.note("ui")
            return
        if self.story_beat == len(PROLOGUE_BEATS) - 1:
            self.story_transition_ticks = 1
            self.story_skip_ticks = 0
            self.note("ui")
            return
        self.story_beat += 1
        self.story_ticks = 0
        self.story_skip_ticks = 0
        self.note("ui")

    def _tile_under_player(self) -> tuple[int, int]:
        assert self.body is not None
        return int((self.body.x + self.body.width / 2) // TILE), int((self.body.y + self.body.height - 1) // TILE)

    def _convert_side_enemy(self, entity: Entity, *, points: int = 250) -> None:
        entity.extra["converted"] = True
        entity.extra["hp"] = 0
        entity.extra["in_combat"] = False
        variant = str(entity.extra.get("variant") or "dogma-sprite")
        capability = {
            "cache-gremlin": "echo",
            "packet-wasp": "compat-shim",
            "lint-launcher": "provenance-pass",
            "garden-glitch": "gate-key",
            "void-orbiter": "fork-future",
            "justice-signaler": "faction-truce",
            "detractabot": "reclaim",
            "consensus-crier": "reclaim",
            "cow": "herd-instinct",
            "llama": "high-ground",
        }.get(variant)
        if capability and capability not in self.converted:
            self.converted.append(capability)
        if variant in COMPANION_VARIANTS or entity.extra.get("instant_convert"):
            entity.extra["companion"] = True
            entity.extra["assist_cooldown"] = 28
            if variant not in self.converted:
                self.converted.append(variant)
            join = "joins the herd" if entity.extra.get("friendly_animal") else "joins the party"
            self.messages.append(f"{variant.replace('-', ' ').title()} {join}.")
        if entity.extra.get("warden"):
            self._open_nearby_gates(entity.x, entity.y)
        self._spawn_particles(entity.x, entity.y, "convert")
        self.flash_ticks = 10
        self.flash_kind = "convert"
        self._award_score(points, variant.replace("-", " "), x=entity.x * TILE + 8, y=entity.y * TILE)
        self.note("convert")

    def _knockback_side_enemy(self, entity: Entity, direction: int) -> bool:
        """Move a non-boss minion one safe tile and ease the visual impact."""

        if entity.kind != "enemy" or entity.extra.get("converted") or not direction or not self.tiles:
            return False
        x = int(round(entity.x))
        y = int(round(entity.y))
        nx = x + (1 if direction > 0 else -1)
        if not (0 <= y < len(self.tiles) and 0 <= nx < len(self.tiles[0])):
            return False
        if self.tiles[y][nx] in SOLID:
            return False
        entity.x = nx
        entity.extra["home"] = nx
        entity.extra["dir"] = 1 if direction > 0 else -1
        entity.extra["offset_x"] = -(1 if direction > 0 else -1) * TILE * 0.72
        entity.extra["knockback_ticks"] = 8
        entity.extra["contact_grace"] = 10
        return True

    def _damage_side_enemy(
        self,
        entity: Entity,
        power: float,
        *,
        item: str = "",
        knockback: int = 0,
    ) -> bool:
        if entity.kind == "boss":
            if not entity.alive or entity.extra.get("converted"):
                return False
            max_hp = float(entity.extra.setdefault("max_hp", entity.extra.get("hp") or BOSS_FIELD_HEALTH))
            hp = max(0.0, float(entity.extra.get("hp") or max_hp) - float(power))
            entity.extra["hp"] = hp
            entity.extra["field_damage"] = max_hp - hp
            # A deliberate hit grants enough grace to keep chaining kicks or
            # throws in the field. Stop attacking and ordinary body contact
            # can still transition into the RPG encounter with this pressure
            # carried forward.
            entity.extra["field_fight_ticks"] = 50
            self._spawn_particles(int(entity.x), int(entity.y), "bomb" if item else "combat")
            if hp <= 0:
                boss_spec = CAMPAIGN_ROSTER[self.chapter_index].boss
                boss_id = str(entity.extra.get("boss") or boss_spec.id)
                if boss_id == "goliath" and self.goliath_stage == "penguin":
                    self._award_score(1500, "cyborg penguin disabled", x=entity.x * TILE + 8, y=entity.y * TILE)
                    self._begin_boss_defeat(entity, boss_id, next_phase="duel")
                    return True
                if boss_id == "goliath" and self.goliath_stage == "duel":
                    self._award_score(2500, "Goliath argument defeated", x=entity.x * TILE + 8, y=entity.y * TILE)
                    self._begin_boss_defeat(entity, boss_id, next_phase="minions")
                    return True
                entity.extra["converted"] = True
                entity.extra["ability_flash"] = 0
                for reward in (boss_spec.capability, boss_id):
                    if reward not in self.converted:
                        self.converted.append(reward)
                self.enemy_projectiles = [shot for shot in self.enemy_projectiles if shot.get("boss") != boss_id]
                self.flash_ticks = 14
                self.flash_kind = "convert"
                self.messages.append("FIELD ARGUMENT COLLAPSED — the boss converts without an RPG detour.")
                self._award_score(2500, f"{boss_spec.name} converted")
                self.note("convert")
                self._begin_boss_defeat(entity, boss_id)
            else:
                self.messages.append("The boss's field argument weakens. Keep the pressure on.")
                self._award_score(25, "boss pressure", x=entity.x * TILE + 8, y=entity.y * TILE)
            return True
        if (
            entity.kind != "enemy"
            or not entity.alive
            or entity.extra.get("converted")
            or entity.extra.get("unrecruitable")
        ):
            return False
        variant = str(entity.extra.get("variant") or "dogma-sprite")
        if entity.extra.get("instant_convert"):
            self._convert_side_enemy(entity, points=450)
            return True
        fallback_hp = ENEMY_BEHAVIORS.get(variant, ("jump", 2))[1]
        max_hp = float(entity.extra.setdefault("max_hp", entity.extra.get("hp") or fallback_hp))
        hp = float(entity.extra.get("hp") or max_hp) - float(power)
        entity.extra["hp"] = hp
        entity.extra["field_damage"] = max(0.0, max_hp - hp)
        if knockback:
            self._knockback_side_enemy(entity, knockback)
        self._spawn_particles(entity.x, entity.y, "bomb" if item else "combat")
        if hp <= 0:
            self._convert_side_enemy(entity)
            self._count_goliath_minion(entity)
        else:
            self.messages.append(f"{str(entity.extra.get('variant') or 'dogma').replace('-', ' ').title()} wavers.")
            self._award_score(25, "clean hit", x=entity.x * TILE + 8, y=entity.y * TILE)
        return True

    @staticmethod
    def _carry_side_pressure(foe: Any, entity: Entity) -> tuple[Any, int]:
        """Translate field hits into a meaningful, bounded RPG head start."""

        max_hp = max(1.0, float(entity.extra.get("max_hp") or entity.extra.get("hp") or 1.0))
        hp = max(0.0, float(entity.extra.get("hp") or max_hp))
        ratio = min(0.75, max(0.0, (max_hp - hp) / max_hp))
        if ratio <= 0:
            return foe, 0
        pressure = max(1, round(ratio * 100))
        return (
            replace(
                foe,
                bs=max(0, foe.bs - round(12 * ratio)),
                conviction=max(0, foe.conviction - round(10 * ratio)),
                corruption=max(0, foe.corruption - round(18 * ratio)),
                trust=min(100, foe.trust + round(15 * ratio)),
            ),
            pressure,
        )

    def _nearest_side_target(self, x: float, y: float, radius: float) -> Entity | None:
        choices = []
        for entity in self.entities:
            if (
                entity.kind not in {"enemy", "boss"}
                or not entity.alive
                or entity.extra.get("converted")
                or entity.extra.get("unrecruitable")
            ):
                continue
            if entity.kind == "boss" and not self._boss_arena_ready(entity):
                continue
            ex = entity.x * TILE + TILE / 2
            ey = entity.y * TILE + TILE / 2 + float(entity.extra.get("offset_y") or 0.0)
            dist = abs(ex - x) + abs(ey - y) * 0.6
            if dist <= radius:
                choices.append((dist, entity))
        return min(choices, key=lambda pair: pair[0])[1] if choices else None

    def _use_side_item(self) -> None:
        if self.body is None or not self.inventory:
            self.messages.append("No item equipped.")
            return
        if self.attack_timer > 0 or self.action_reset_ticks > 0:
            return
        item = self.current_item
        if item == RARE_BS_RESET_ITEM:
            if self.player_bs <= 0:
                self.messages.append("The Touch Grass USB is already mounted. Save it for actual nonsense.")
                return
            cleared = self.player_bs
            self.player_bs = 0
            self.attack_timer = 12
            self.action_kind = "item"
            self.flash_ticks = 9
            self.flash_kind = "convert"
            self._popup("BS RESET", self.body.center[0], self.body.feet[1] - CHAR_WORLD_HEIGHT - 12, color=(158, 206, 106))
            self.messages.append(f"Touch Grass USB clears {cleared} BS. Nature remains emulated.")
            self._consume_current_item()
            self.note("collect")
            return
        speed = {
            "logic-bomb": 4.8,
            "patch-cable": 5.6,
            "manifest": 3.6,
            "penguin-flock": 4.2,
            "fork-beacon": 5.0,
            "checksum-key": 5.8,
            "mirror-cache": 4.4,
        }[item]
        base_power = {
            "logic-bomb": 2,
            "patch-cable": 1,
            "manifest": 1,
            "penguin-flock": 2,
            "fork-beacon": 2,
            "checksum-key": 3,
            "mirror-cache": 2,
        }[item]
        power = base_power * self.item_effectiveness
        cx, _ = self.body.center
        # The logical hitbox covers David's lower body, while the 36px visual
        # extends above it. Emit from the visual torso, not hitbox knee level.
        throw_y = self.body.feet[1] - CHAR_WORLD_HEIGHT * 0.57
        self.projectiles.append(
            {
                "x": cx + self.body.facing * 8,
                "y": throw_y,
                "vx": speed * self.body.facing,
                "vy": -0.12 if item in {"penguin-flock", "fork-beacon"} else 0.0,
                "life": 54 if item == "penguin-flock" else 40,
                "item": item,
                "power": power,
                "strength": self.item_strength,
            }
        )
        self.attack_timer = 12
        self.action_kind = "item"
        self.note("hit")
        self.messages.append(f"{item.replace('-', ' ').title()} deployed.")
        if item in CONSUMABLE_ITEMS:
            self._consume_current_item()

    def _trigger_block(self, entity: Entity) -> None:
        if not entity.alive:
            return
        entity.alive = False
        x, y = int(round(entity.x)), int(round(entity.y))
        if 0 <= y < len(self.tiles) and 0 <= x < len(self.tiles[0]):
            row = list(self.tiles[y])
            row[x] = "."
            self.tiles[y] = "".join(row)
        if entity.kind == "omega-block":
            self._collect_omega_letter(entity)
            self._spawn_particles(entity.x, entity.y, "convert")
            return
        payload = str(entity.extra.get("payload") or "penguin")
        if payload == "penguin":
            self.penguins += 1
            self.inventory.append("penguin-flock")
            self._increase_item_strength("penguin-flock")
            self.messages.append("A penguin unfolds from the lattice.")
            self.flash_kind = "penguin"
            self._award_score(125, "hidden penguin", x=entity.x * TILE + 8, y=entity.y * TILE, combo_event="pickup")
        elif payload == "empty":
            self.messages.append("Dust. Someone already audited this rack.")
            self.flash_kind = "combat"
        elif payload == "bomb":
            self.inventory.append("logic-bomb")
            self._increase_item_strength("logic-bomb")
            self.messages.append("A spare Logic Bomb rattles out.")
            self.flash_kind = "bomb"
        else:
            self.body = replace(self.body, vy=-6.2) if self.body else self.body
            self.messages.append("The lattice kicks you upward.")
            self.flash_kind = "convert"
        self.note("collect")
        self._award_score(25, "hardware block", x=entity.x * TILE + 8, y=entity.y * TILE, combo_event="socket")
        self.flash_ticks = 8
        self._spawn_particles(entity.x, entity.y, self.flash_kind)

    def _break_cracked_tile(self, tx: int, ty: int) -> bool:
        if not (0 <= ty < len(self.tiles) and 0 <= tx < len(self.tiles[0])):
            return False
        if self.tiles[ty][tx] != "D":
            return False
        row = list(self.tiles[ty])
        row[tx] = "."
        self.tiles[ty] = "".join(row)
        self._spawn_particles(tx, ty, "combat")
        self._award_score(75, "kick break", x=tx * TILE + 8, y=ty * TILE)
        self.messages.append("The cracked access tile gives way.")
        return True

    def _kick_breakable(self) -> bool:
        if self.body is None:
            return False
        feet_x, feet_y = self.body.feet
        reach = 18.0
        if self.body.facing > 0:
            attack_left, attack_right = feet_x - 2.0, feet_x + reach
        else:
            attack_left, attack_right = feet_x - reach, feet_x + 2.0
        attack_top = feet_y - CHAR_WORLD_HEIGHT * 0.72
        attack_bottom = feet_y - 1.0
        min_tx = max(0, int(attack_left // TILE))
        max_tx = min(len(self.tiles[0]) - 1, int(attack_right // TILE))
        min_ty = max(0, int(attack_top // TILE))
        max_ty = min(len(self.tiles) - 1, int(attack_bottom // TILE))
        hit = False
        for ty in range(min_ty, max_ty + 1):
            for tx in range(min_tx, max_tx + 1):
                if self._break_cracked_tile(tx, ty):
                    hit = True
        for entity in self.entities:
            if entity.kind not in {"block", "omega-block"} or not entity.alive:
                continue
            block_left, block_top = entity.x * TILE, entity.y * TILE
            if attack_left < block_left + TILE and attack_right > block_left and attack_top < block_top + TILE and attack_bottom > block_top:
                self._trigger_block(entity)
                hit = True
        return hit

    def _side_attack(self) -> None:
        if self.body is None:
            return
        self.attack_timer = 9
        self.action_kind = "attack"
        cx, cy = self.body.center
        reach = 30 if self.current_attack == "reason" else (38 if self.current_attack == "fork-pulse" else 24)
        power = 2 if self.current_attack == "patch-strike" else 1
        target = self._nearest_side_target(cx + self.body.facing * 9, cy, reach)
        kicked_tile = self._kick_breakable()
        if target is not None:
            self._damage_side_enemy(target, power, knockback=self.body.facing)
            self.note("hit")
        elif kicked_tile:
            self.note("hit")

    def _tick_projectiles(self) -> None:
        live: list[dict[str, Any]] = []
        for shot in self.projectiles:
            next_x = float(shot["x"]) + float(shot["vx"])
            next_y = float(shot["y"]) + float(shot.get("vy", 0.0))
            radius = float(shot.get("radius") or 2.0)
            if overlapping_tiles(
                self.tiles,
                next_x - radius,
                next_y - radius,
                radius * 2,
                radius * 2,
                BOSS_GATE_GLYPHS,
            ):
                self._spawn_particles(
                    int(float(shot["x"]) // TILE),
                    int(float(shot["y"]) // TILE),
                    "combat",
                )
                self.note("hit")
                continue
            shot["x"] = next_x
            shot["y"] = next_y
            shot["life"] -= 1
            target = self._nearest_side_target(float(shot["x"]), float(shot["y"]), 13)
            if target is not None:
                self._damage_side_enemy(target, float(shot.get("power") or 1), item=str(shot.get("item") or ""))
                continue
            if shot["life"] > 0:
                live.append(shot)
        self.projectiles = live

    @property
    def active_companions(self) -> tuple[str, ...]:
        persistent = {"justice-signaler", "detractabot"}
        if self.secret_map_index >= 0 and self.map_index == self.secret_map_index:
            persistent.update({"cow", "llama"})
        return tuple(variant for variant in COMPANION_VARIANTS if variant in self.converted and variant in persistent)

    def _spawn_persistent_companions(self) -> None:
        if self.body is None:
            return
        existing = {
            str(entity.extra.get("variant"))
            for entity in self.entities
            if entity.extra.get("companion") and entity.alive
        }
        for index, variant in enumerate(self.active_companions):
            if variant in existing:
                continue
            self.entities.append(
                Entity(
                    "enemy",
                    self.body.center[0] / TILE - 1.5 - index * 0.7,
                    self.body.feet[1] / TILE - 1.0,
                    extra={
                        "hp": 0,
                        "variant": variant,
                        "converted": True,
                        "companion": True,
                        "assist_cooldown": 30 + index * 18,
                    },
                )
            )

    def _tick_companions(self) -> None:
        """Followers trail David and periodically contribute a visible hit."""

        if self.body is None:
            return
        companions = [
            entity
            for entity in self.entities
            if entity.alive and entity.extra.get("companion") and entity.extra.get("converted")
        ]
        for index, entity in enumerate(companions):
            target_x = self.body.center[0] / TILE - self.body.facing * (1.45 + index * 0.72)
            target_y = self.body.feet[1] / TILE - 1.0
            entity.x += max(-0.16, min(0.16, target_x - entity.x))
            entity.y += max(-0.12, min(0.12, target_y - entity.y))
            cooldown = int(entity.extra.get("assist_cooldown") or 0) - 1
            if cooldown <= 0:
                ex = entity.x * TILE + TILE / 2
                ey = entity.y * TILE + TILE * 0.35
                variant = str(entity.extra.get("variant") or "companion")
                if variant == "detractabot":
                    nearby = next(
                        (
                            shot
                            for shot in self.enemy_projectiles
                            if abs(float(shot["x"]) - ex) < TILE * 2.2
                            and abs(float(shot["y"]) - ey) < TILE * 2.2
                        ),
                        None,
                    )
                    if nearby is not None:
                        self.enemy_projectiles.remove(nearby)
                        direction = 1 if self.body.center[0] >= ex else -1
                        target = self._nearest_side_target(ex, ey, TILE * 11)
                        if target is not None:
                            direction = 1 if target.x * TILE >= ex else -1
                        self.projectiles.append(
                            {
                                "x": ex,
                                "y": ey,
                                "vx": direction * 4.4,
                                "vy": -0.1,
                                "life": 58,
                                "item": "",
                                "power": 1.5,
                                "ally": True,
                                "variant": variant,
                            }
                        )
                        entity.extra["assist_cooldown"] = 90
                        self.messages.append("Detractabot redirects a talking point back at its source.")
                        self.note("hit")
                        continue
                target = self._nearest_side_target(ex, ey, TILE * 10)
                if target is not None:
                    tx = target.x * TILE + TILE / 2
                    direction = 1 if tx >= ex else -1
                    self.projectiles.append(
                        {
                            "x": ex,
                            "y": ey,
                            "vx": direction * 3.8,
                            "vy": 0.0,
                            "life": 52,
                            "item": "",
                            "power": 1.35 if variant == "justice-signaler" else 1,
                            "ally": True,
                            "variant": variant,
                        }
                    )
                    if variant == "justice-signaler":
                        target.extra["contact_grace"] = max(
                            18,
                            int(target.extra.get("contact_grace") or 0),
                        )
                    cooldown = 78 + index * 14
                    self.messages.append(f"{variant.replace('-', ' ').title()} assists.")
                else:
                    cooldown = 18
            entity.extra["assist_cooldown"] = cooldown

    def _entity_overlaps_player(
        self,
        entity: Entity,
        *,
        full_sprite: bool,
        body: Body | None = None,
    ) -> bool:
        player = body or self.body
        if player is None:
            return False
        ex = entity.x * TILE
        ey = entity.y * TILE + float(entity.extra.get("offset_y") or 0.0)
        ew = TILE
        eh = TILE
        if entity.kind == "enemy":
            ey -= 8
            eh = 24
        if full_sprite:
            feet_x, feet_y = player.feet
            px, py, pw, ph = feet_x - 11, feet_y - CHAR_WORLD_HEIGHT, 22, CHAR_WORLD_HEIGHT
        else:
            px, py, pw, ph = player.x, player.y, player.width, player.height
        return px < ex + ew and px + pw > ex and py < ey + eh and py + ph > ey

    def _slide_attack(self) -> None:
        if self.body is None or not self.body.sliding:
            return
        self._kick_breakable()
        token = self.tick + self.body.slide_ticks
        for entity in self.entities:
            if (
                entity.kind != "enemy"
                or not entity.alive
                or entity.extra.get("converted")
                or entity.extra.get("slide_hit_token") == token
            ):
                continue
            # Extend the low body box slightly into the leading foot.
            reach_x = self.body.x + (5 if self.body.facing > 0 else -5)
            probe = replace(self.body, x=reach_x)
            overlaps = self._entity_overlaps_player(entity, full_sprite=False, body=probe)
            if not overlaps:
                continue
            entity.extra["slide_hit_token"] = token
            self._damage_side_enemy(entity, 1, knockback=self.body.facing)
            self.note("hit")

    def _tick_traversal_features(self) -> None:
        """Advance deterministic lifts and weight-responsive pivot platforms."""

        if self.body is None:
            return
        import math

        feet_x, feet_y = self.body.feet
        for entity in self.entities:
            if entity.kind == "moving-platform":
                old_x, old_y = entity.x, entity.y
                entity.extra["prev_x"], entity.extra["prev_y"] = old_x, old_y
                phase = float(entity.extra.get("phase") or 0.0)
                travel = float(entity.extra.get("range") or 3.0)
                offset = math.sin(self.tick * 0.035 + phase) * travel
                base_x = float(entity.extra.get("base_x", old_x))
                base_y = float(entity.extra.get("base_y", old_y))
                if entity.extra.get("axis") == "horizontal":
                    entity.x, entity.y = base_x + offset, base_y
                else:
                    entity.x, entity.y = base_x, base_y + offset
                width = float(entity.extra.get("width") or 4.0) * TILE
                standing = (
                    not self.body.on_ladder
                    and old_x * TILE - 2 <= feet_x <= old_x * TILE + width + 2
                    and abs(feet_y - old_y * TILE) <= 3.5
                )
                if standing:
                    self.body = replace(
                        self.body,
                        x=self.body.x + (entity.x - old_x) * TILE,
                        y=self.body.y + (entity.y - old_y) * TILE,
                        on_ground=True,
                    )
                    feet_x, feet_y = self.body.feet
            elif entity.kind == "tilt-platform":
                old_angle = float(entity.extra.get("angle") or 0.0)
                entity.extra["prev_angle"] = old_angle
                span = float(entity.extra.get("width") or 5.0) * TILE
                pivot = float(entity.extra.get("pivot", span / TILE / 2 - 0.5)) + 0.5
                center = entity.x * TILE + pivot * TILE
                deck_left = entity.x * TILE
                deck_right = deck_left + span
                contact_left = max(self.body.x, deck_left)
                contact_right = min(self.body.x + self.body.width, deck_right)
                contact_x = (contact_left + contact_right) / 2.0
                surface = entity.y * TILE + math.tan(old_angle) * (contact_x - center)
                rider = contact_right > contact_left and abs(feet_y - surface) <= 4.0
                phase = float(entity.extra.get("phase") or 0.0)
                ambient = math.sin(self.tick * 0.025 + phase) * 0.035
                angular_velocity = float(entity.extra.get("angular_velocity") or 0.0)
                if rider:
                    leverage = max(-1.0, min(1.0, (contact_x - center) / max(1.0, span / 2)))
                    # Weight supplies torque every tick. A rider who remains on
                    # one end therefore keeps tipping the deck instead of
                    # settling at the old shallow display-only angle.
                    angular_velocity += leverage * 0.0038
                    angular_velocity *= 0.986
                    angle = old_angle + angular_velocity
                else:
                    angular_velocity *= 0.90
                    angle = old_angle + angular_velocity + (ambient - old_angle) * 0.055
                angle = max(-0.58, min(0.58, angle))
                if abs(angle) >= 0.58 and angle * angular_velocity > 0:
                    angular_velocity *= 0.2
                entity.extra["angular_velocity"] = angular_velocity
                entity.extra["angle"] = angle

    def _resolve_traversal_platforms(self, previous: Body) -> None:
        """Resolve top-face collisions for moving and rotated platform entities."""

        if self.body is None:
            return
        import math

        feet_x, feet_y = self.body.feet
        _, old_feet_y = previous.feet
        for entity in self.entities:
            if entity.kind not in {"tilt-platform", "moving-platform"}:
                continue
            if entity.kind == "moving-platform" and self.body.on_ladder:
                # The ladder/layer crossing owns collision while climbing, so
                # moving decks can pass visually behind it without snagging.
                continue
            span = float(entity.extra.get("width") or 4.0) * TILE
            deck_left = entity.x * TILE
            deck_right = deck_left + span
            contact_left = max(self.body.x, deck_left)
            contact_right = min(self.body.x + self.body.width, deck_right)
            if contact_right <= contact_left:
                continue
            if entity.kind == "tilt-platform":
                pivot = float(entity.extra.get("pivot", span / TILE / 2 - 0.5)) + 0.5
                center = entity.x * TILE + pivot * TILE
                angle = float(entity.extra.get("angle") or 0.0)
                old_angle = float(entity.extra.get("prev_angle") or angle)
                contact_x = (contact_left + contact_right) / 2.0
                old_contact_left = max(previous.x, deck_left)
                old_contact_right = min(previous.x + previous.width, deck_right)
                old_contact_x = (old_contact_left + old_contact_right) / 2.0
                surface = entity.y * TILE + math.tan(angle) * (contact_x - center)
                old_surface = entity.y * TILE + math.tan(old_angle) * (old_contact_x - center)
            else:
                surface = entity.y * TILE
                old_surface = float(entity.extra.get("prev_y", entity.y)) * TILE
            crossed = old_feet_y <= old_surface + 4.0 and feet_y >= surface - 2.0
            if crossed and self.body.vy >= 0:
                angle = float(entity.extra.get("angle") or 0.0)
                nudge = math.sin(angle) * (0.36 + abs(angle) * 2.5)
                self.body = replace(
                    self.body,
                    y=surface - self.body.height,
                    vy=0.0,
                    vx=self.body.vx + nudge,
                    on_ground=True,
                )
                return

    def _wind_column_at_body(
        self,
        body: Body | None = None,
    ) -> tuple[Entity, float, float, float, float, float] | None:
        """Return the authored gust field containing the body's center."""

        target = body or self.body
        if target is None:
            return None
        px, py = target.center
        for entity in self.entities:
            if entity.kind != "wind-column":
                continue
            width = float(entity.extra.get("width") or 1.0) * TILE
            height = float(entity.extra.get("height") or 6.0) * TILE
            left = entity.x * TILE
            right = left + width
            top = entity.y * TILE
            bottom = top + height
            influence = TILE * GUST_INFLUENCE_TILES
            if left - influence <= px <= right + influence and top <= py <= bottom:
                return entity, left, right, top, bottom, influence
        return None

    def _apply_wind_columns(self, inp: InputState | None = None) -> None:
        if self.body is None:
            return
        field = self._wind_column_at_body()
        if field is None:
            self.gust_center_release = None
            return
        entity, left, right, top, bottom, influence = field
        px, py = self.body.center
        center_x = (left + right) / 2
        width = right - left
        height = bottom - top
        horizontal_distance = abs(px - center_x)
        edge_distance = max(0.0, horizontal_distance - width / 2)
        # Hold almost full strength throughout the invitation field, then end
        # it at the authored edge. This avoids a weak fringe that can detach a
        # grounded player without actually acquiring them.
        edge_ratio = min(1.0, edge_distance / max(1.0, influence))
        horizontal_strength = 1.0 - edge_ratio * 0.15
        # Treat the authored column itself as the centered release zone. A
        # two-pixel dead zone could reacquire the player before normal running
        # acceleration carried them out, effectively trapping them in place.
        centered = horizontal_distance <= max(GUST_CENTER_DEAD_ZONE, width / 2)
        release_key = (entity.x, entity.y)
        if centered:
            self.gust_center_release = release_key
        moving_outward = bool(
            inp
            and self.gust_center_release == release_key
            and (
                (inp.left and not inp.right and px <= center_x)
                or (inp.right and not inp.left and px >= center_x)
            )
        )
        centered = centered or moving_outward
        pull = min(GUST_MAX_PULL, horizontal_strength * GUST_MAX_PULL)
        direction = 0.0 if centered else (1.0 if px < center_x else -1.0)
        # Once acquired, the core releases horizontal control so the player
        # can deliberately exit instead of being pinned by corrective force.
        vx = self.body.vx if centered else self.body.vx * 0.78 + direction * pull
        if direction and (px - center_x) * (px + vx - center_x) < 0:
            vx = center_x - px
        strength = float(entity.extra.get("strength") or 0.4)
        # Updraft energy dissipates through the upper eighth rather than
        # snapping off at the column's authored top edge.
        top_fade = max(0.0, min(1.0, (py - top) / max(TILE * 1.25, height * 0.125)))
        lift = strength * top_fade * horizontal_strength
        changes: dict[str, Any] = {"vx": vx}
        if lift > 0.01:
            gust_vy = max(-4.6, self.body.vy - lift)
            # Never weaken a stronger jump impulse merely to impose the
            # updraft's ordinary terminal lift speed.
            changes.update(vy=min(self.body.vy, gust_vy), on_ground=False)
        self.body = replace(self.body, **changes)
        if any(entry in self.converted for entry in BOSSES):
            self._score_combo_event("capability", x=px, y=py)
        if lift > 0.05 and self.tick % 10 == 0:
            self.note("jump")

    def _tick_corruption_pit(self) -> None:
        if self.body is None:
            return
        submerged = bool(
            overlapping_tiles(
                self.tiles,
                self.body.x,
                self.body.y,
                self.body.width,
                self.body.height,
                glyphs={"M"},
            )
        )
        if not submerged:
            self.pit_exposure_ticks = 0
            return
        self.pit_exposure_ticks += 1
        self.body = replace(self.body, vy=min(self.body.vy, 2.5))
        if self.pit_exposure_ticks >= 12:
            self.pit_exposure_ticks = 0
            self._penalize_score(20, "corrupted-code exposure")
            self._maybe_revert_pit_companion()
            self.flash_ticks = max(self.flash_ticks, 4)
            self.flash_kind = "combat"
            self.note("hit")

    def _maybe_revert_pit_companion(self) -> str | None:
        """Occasionally corrupt one helper and strand it permanently in the pit."""

        companions = [
            entity
            for entity in self.entities
            if entity.alive and entity.extra.get("companion") and entity.extra.get("converted")
        ]
        if not companions:
            return None
        # Runtime chance remains deterministic for replays while still varying
        # with exposure, position, chapter, and the number of available allies.
        assert self.body is not None
        roll = (
            self.tick * 17
            + int(self.body.center[0]) * 7
            + self.chapter_index * 11
            + len(companions) * 5
        ) % 4
        if roll:
            return None
        companion = companions[(self.tick + self.chapter_index) % len(companions)]
        variant = str(companion.extra.get("variant") or "")
        if not variant:
            return None
        pit_cells = [
            (x, y)
            for y, row in enumerate(self.tiles)
            for x, cell in enumerate(row)
            if cell == "M"
        ]
        if pit_cells:
            assert self.body is not None
            player_tx = self.body.center[0] / TILE
            player_ty = self.body.center[1] / TILE
            nearest = min(
                pit_cells,
                key=lambda cell: abs(cell[0] - player_tx) + abs(cell[1] - player_ty),
            )
            local_pit = [
                cell
                for cell in pit_cells
                if cell[1] == nearest[1] and abs(cell[0] - nearest[0]) <= 3
            ]
            pit_x, pit_y = max(
                local_pit or [nearest],
                key=lambda cell: abs(cell[0] - player_tx) + abs(cell[1] - player_ty),
            )
            companion.x = float(pit_x)
            companion.y = float(pit_y)
        self.converted = [entry for entry in self.converted if entry != variant]
        companion.extra.update(
            {
                "converted": False,
                "companion": False,
                "hp": ENEMY_BEHAVIORS.get(variant, ("jump", 2))[1],
                "home": companion.x,
                "dir": 0,
                "in_combat": False,
                "contact_grace": 0,
                "pit_trapped": True,
                "pit_corrupted": True,
                "unrecruitable": True,
            }
        )
        companion.extra.pop("assist_cooldown", None)
        self.messages.append(f"The red code reclaims {variant.replace('-', ' ').title()} and traps them beyond reach.")
        self._spawn_particles(companion.x, companion.y, "combat")
        return variant

    def _active_cow_cannon(self) -> Entity | None:
        if self.active_palette != "cow":
            return None
        return next(
            (entity for entity in self.entities if entity.kind == "cow-cannon" and entity.alive),
            None,
        )

    def _tick_cow_cannon(self, inp: InputState) -> bool:
        """Load, aim, charge, and fire the Cow Level's absurd launcher.

        ``True`` means the player is inside the cannon and ordinary movement
        should pause. Releasing a charged Jump fires and returns ``False`` so
        ballistic physics begins immediately.
        """

        if self.body is None:
            return False
        cannon = self._active_cow_cannon()
        if cannon is None:
            return False
        if not self.cannon_loaded:
            if self.cannon_launch_active:
                return False
            hatch_x, hatch_y = cow_cannon_geometry(cannon, self.cannon_angle)["hatch"]
            feet_x, feet_y = self.body.feet
            near_hatch = (
                abs(feet_x - hatch_x) <= CANNON_ENTRY_X_TOLERANCE
                and abs((feet_y - 10.0) - hatch_y) <= CANNON_ENTRY_Y_TOLERANCE
            )
            entering = inp.jump_pressed or not self.body.on_ground
            if not near_hatch or not entering:
                return False
            pivot_x, pivot_y = cow_cannon_geometry(cannon, self.cannon_angle)["pivot"]
            self.cannon_loaded = True
            self.cannon_charge_ticks = 0
            self.cannon_charge_armed = False
            self.cannon_entry_lock_ticks = CANNON_ENTRY_LOCK_TICKS
            self.body = replace(
                self.body,
                x=pivot_x - self.body.width / 2,
                y=pivot_y - self.body.height / 2,
                vx=0.0,
                vy=0.0,
                on_ground=False,
                on_ladder=False,
                crouching=False,
                sliding=False,
                rushing=False,
            )
            self.messages.append("CANNON LOADED · Aim with Up/Down. Hold Jump to spell LAUNCH; release to fire.")
            self.note("ui")
            return True

        aim_delta = (1 if inp.up else 0) - (1 if inp.down else 0)
        self.cannon_angle = max(
            CANNON_MIN_ANGLE,
            min(CANNON_MAX_ANGLE, self.cannon_angle + aim_delta * 0.72),
        )
        cannon.extra["angle"] = self.cannon_angle
        pivot_x, pivot_y = cow_cannon_geometry(cannon, self.cannon_angle)["pivot"]
        self.body = replace(
            self.body,
            x=pivot_x - self.body.width / 2,
            y=pivot_y - self.body.height / 2,
            vx=0.0,
            vy=0.0,
            on_ground=False,
        )
        if self.cannon_entry_lock_ticks > 0:
            self.cannon_entry_lock_ticks -= 1
            return True
        jump_held = inp.jump or inp.jump_pressed
        if not self.cannon_charge_armed:
            # Only a new press after the entry lock can arm the charge. The
            # jump that carried the player into the hatch cannot leak across
            # frames and accidentally launch the cannon.
            if not inp.jump_pressed:
                return True
            self.cannon_charge_armed = True
        if jump_held:
            self.cannon_charge_ticks = min(CANNON_MAX_CHARGE_TICKS, self.cannon_charge_ticks + 1)
            if self.cannon_charge_ticks == 1:
                self.note("collect")
            return True
        if not self.cannon_charge_armed:
            return True

        charge = self.cannon_charge_ticks / CANNON_MAX_CHARGE_TICKS
        power = CANNON_MIN_POWER + (CANNON_MAX_POWER - CANNON_MIN_POWER) * charge
        radians = math.radians(self.cannon_angle)
        muzzle_x, muzzle_y = cow_cannon_geometry(cannon, self.cannon_angle)["muzzle"]
        self.body = replace(
            self.body,
            x=muzzle_x - self.body.width / 2,
            y=muzzle_y - self.body.height / 2,
            vx=math.cos(radians) * power,
            vy=-math.sin(radians) * power,
            facing=1,
            on_ground=False,
            coyote=0,
            buffer=0,
            air_jump_used=True,
        )
        self.cannon_loaded = False
        self.cannon_charge_armed = False
        self.cannon_entry_lock_ticks = 0
        self.cannon_launch_active = True
        self.cannon_launch_ticks = 0
        self.flash_ticks = max(self.flash_ticks, 8)
        self.flash_kind = "convert"
        self.messages.append(f"LAUNCH · {round(charge * 100):02d}% proof pressure.")
        self.note("bomb")
        return False

    def _cannon_break_path(self) -> None:
        """Break upward and leading-edge contacts without drilling downward."""

        if self.body is None or not self.cannon_launch_active or not self.tiles:
            return
        body = self.body
        destructive_upward = body.vy < -0.05
        destructive_forward = body.vx * body.facing > 0.05
        if not (destructive_upward or destructive_forward):
            return
        steps = max(1, math.ceil(max(abs(body.vx), abs(body.vy)) / 2.0))
        cells: set[tuple[int, int]] = set()
        path_bodies: list[Body] = []
        for step in range(1, steps + 1):
            ratio = step / steps
            px = body.x + body.vx * ratio
            py = body.y + body.vy * ratio
            sample = replace(body, x=px, y=py)
            path_bodies.append(sample)
            if destructive_upward:
                for tx, ty, _ in overlapping_tiles(
                    self.tiles,
                    px,
                    py,
                    body.width,
                    body.height,
                    SOLID | {"L"},
                ):
                    cells.add((tx, ty))
            if destructive_forward:
                edge_x = px + body.width - 1.5 if body.facing > 0 else px - 0.5
                for tx, ty, _ in overlapping_tiles(
                    self.tiles,
                    edge_x,
                    py + 1.0,
                    2.0,
                    max(2.0, body.height - 3.0),
                    SOLID | {"L"},
                ):
                    cells.add((tx, ty))

        launch_vx, launch_vy = body.vx, body.vy
        protected_lifts = self.skyway_reserved_cells()
        for entity in list(self.entities):
            if entity.kind in {"block", "omega-block"} and entity.alive:
                if (int(entity.x), int(entity.y)) in cells:
                    self._trigger_block(entity)
            elif entity.kind in {"enemy", "boss"} and entity.alive and not entity.extra.get("converted"):
                if any(self._entity_overlaps_player(entity, full_sprite=False, body=sample) for sample in path_bodies):
                    self._damage_side_enemy(entity, 999.0, item="cannon", knockback=body.facing)
        if self.body is not None:
            self.body = replace(self.body, vx=launch_vx, vy=launch_vy)
        for tx, ty in cells:
            if not (0 <= ty < len(self.tiles) and 0 <= tx < len(self.tiles[ty])):
                continue
            if (tx, ty) in protected_lifts or self.tiles[ty][tx] == "K" or self.tiles[ty][tx] not in SOLID | {"L"}:
                continue
            row = list(self.tiles[ty])
            row[tx] = "."
            self.tiles[ty] = "".join(row)

    def _finish_cannon_launch_if_landed(self, previous: Body) -> None:
        """Release ballistic lock once feet have a real landing, including lifts."""

        if self.body is None or not self.cannon_launch_active:
            return
        if self.cannon_launch_ticks > 4 and self.body.on_ground and previous.vy >= 0:
            self.cannon_launch_active = False
            self.cannon_launch_ticks = 0
            self.note("hit")

    def _step_action(self, inp: InputState) -> None:
        assert self.body is not None
        if self.combat is not None:
            if inp.item:
                self.use_item_in_action()
                self.note("hit")
            elif inp.action_pressed:
                self.combat = apply_action_attack(self.combat, self.current_attack)
                self.combat = foe_action_pressure(self.combat)
                for companion_id in self.active_companions:
                    self.combat = apply_companion_assist(self.combat, companion_id)
                self.player_bs = self.combat.player.bs
                self.messages.append(self.combat.log[-1])
                self.attack_timer = 9
                self.action_kind = "attack"
                self.note("hit")
            if self.combat is not None and self.combat.player_overloaded:
                self._enter_recovery()
                return
            if inp.turn_pressed:
                from .combat import enter_turn_based

                self.combat = enter_turn_based(self.combat)
                self.scene = "turn"
                self.note("ui")
                self.messages.append(
                    f"Thought slows. {self.prompt_binding('jump')} reason · "
                    f"{self.prompt_binding('action')} patch · {self.prompt_binding('item')} item · "
                    f"{self.prompt_binding('turn')} reuse · {self.prompt_binding('interact')} recruit."
                )
            return
        if inp.customize:
            self.paused_from = "action"
            self.scene = "customize"
            if not self.limitless_status:
                self.limitless_status = (
                    f"Limitless is optional. {self.prompt_binding('jump')} queries; "
                    f"{self.prompt_binding('interact')} closes. Offline starts fresh."
                )
            return
        assist = bool(self.settings.get("precisionAssist") or self.accessibility.precision_assist)
        speed = float(self.settings.get("speedScale") or 1.0)
        jump = float(self.settings.get("jumpScale") or 1.0)
        if self._tick_cow_cannon(inp):
            if self.flash_ticks > 0:
                self.flash_ticks -= 1
            return
        self._tick_traversal_features()
        previous_body = self.body
        prev_vy = self.body.vy
        if self.cannon_launch_active:
            self._cannon_break_path()
        physics_body = self.body
        gust_field = self._wind_column_at_body(physics_body)
        self.body = step_body(
            physics_body,
            inp,
            self.tiles,
            speed_scale=speed,
            jump_scale=jump,
            precision_assist=assist,
            phase_solids=gust_field is not None,
            ballistic=self.cannon_launch_active,
            ground_strength_jump=gust_field is not None,
        )
        if self.cannon_launch_active:
            self.cannon_launch_ticks += 1
        if self._tick_omega_doors(inp):
            self._finish_cannon_launch_if_landed(previous_body)
            return
        self._tick_boss_gates()
        self._resolve_traversal_platforms(previous_body)
        self._finish_cannon_launch_if_landed(previous_body)
        self._apply_wind_columns(inp)
        self._tick_corruption_pit()
        portal_overlaps = [
            entity
            for entity in self.entities
            if entity.alive and entity.kind == "network" and self._entity_overlaps_player(entity, full_sprite=False)
        ]
        if not portal_overlaps:
            self.network_armed = True
        if self.attack_timer > 0:
            self.attack_timer -= 1
            if self.attack_timer == 0:
                self.action_kind = ""
                self.action_reset_ticks = 1
        elif self.action_reset_ticks > 0:
            self.action_reset_ticks -= 1
        if inp.jump_pressed and self.body.vy < prev_vy - 0.5 and not self.body.ladder_sliding:
            self.note("jump")
        if self.flash_ticks > 0:
            self.flash_ticks -= 1
        self.ghosts.append({"tick": self.tick, "x": self.body.x, "y": self.body.y, "facing": self.body.facing})
        if len(self.ghosts) > 3600:
            self.ghosts = self.ghosts[-3600:]
        if inp.item:
            self._use_side_item()
        if inp.action_pressed:
            self._side_attack()
        self._slide_attack()
        self._tick_companions()
        self._tick_projectiles()
        self._tick_enemy_behaviors()
        self._tick_enemy_projectiles()
        if self.player_bs >= MAX_BS:
            self._enter_recovery()
            return
        # Hit hardware blocks and cracked tiles from below even after collision zeroes vy.
        if prev_vy < 0 or (not self.body.on_ground and self.body.vy <= 0):
            visual_left = self.body.center[0] - max(self.body.width / 2, 5.0)
            visual_right = self.body.center[0] + max(self.body.width / 2, 5.0)
            swept_top = min(previous_body.y, self.body.y)
            swept_bottom = max(previous_body.y, self.body.y) + 6.0
            for entity in self.entities:
                if not (entity.kind in {"block", "omega-block"} and entity.alive):
                    continue
                block_left, block_top = entity.x * TILE, entity.y * TILE
                horizontal_hit = visual_left < block_left + TILE and visual_right > block_left
                # Collision resolution can settle at block_bottom + a tiny
                # epsilon. A one-pixel contact tolerance makes the authored
                # head bump reliable without expanding the attack upward.
                vertical_hit = swept_top <= block_top + TILE + 1.0 and swept_bottom >= block_top - 1.0
                if horizontal_hit and vertical_hit:
                    self._trigger_block(entity)
            min_tx = max(0, int(visual_left // TILE))
            max_tx = min(len(self.tiles[0]) - 1, int((visual_right - 0.01) // TILE))
            # Collision settles on the cracked tile's bottom edge, so the
            # integer sweep must include the cell whose underside was hit.
            min_ty = max(0, int((swept_top - TILE - 1.0) // TILE))
            max_ty = min(len(self.tiles) - 1, int(swept_bottom // TILE))
            for ty in range(min_ty, max_ty + 1):
                for tx in range(min_tx, max_tx + 1):
                    if self.tiles[ty][tx] != "D":
                        continue
                    block_left, block_top = tx * TILE, ty * TILE
                    horizontal_hit = visual_left < block_left + TILE and visual_right > block_left
                    vertical_hit = swept_top <= block_top + TILE + 1.0 and swept_bottom >= block_top - 1.0
                    if horizontal_hit and vertical_hit:
                        self._break_cracked_tile(tx, ty)
        # Pickups use David's complete 36px visual footprint. Enemy contact
        # intentionally remains on the smaller, stable gameplay hitbox.
        for entity in self.entities:
            if not entity.alive:
                continue
            if entity.kind == "network":
                if self.network_armed and entity in portal_overlaps:
                    self._begin_network_transition(entity)
                    return
            elif entity.kind in {"penguin", "item", "logo"}:
                if not self._entity_overlaps_player(entity, full_sprite=True):
                    continue
                if entity.kind == "penguin":
                    entity.alive = False
                    self.penguins += 1
                    self.note("collect")
                    self.messages.append("Linux history, recovered.")
                    self._award_score(100, "history recovered", x=entity.x * TILE + 8, y=entity.y * TILE, combo_event="proof")
                    self._score_combo_event("pickup", x=entity.x * TILE + 8, y=entity.y * TILE)
                elif entity.kind == "item":
                    entity.alive = False
                    found_item = str(entity.extra.get("item") or "logic-bomb")
                    self.inventory.append(found_item)
                    self._increase_item_strength(found_item)
                    self.note("collect")
                    self.messages.append(f"{found_item.replace('-', ' ').title()} pocketed.")
                    self.flash_ticks = 10
                    self.flash_kind = "bomb"
                    self._award_score(
                        50,
                        f"{found_item.replace('-', ' ')} recovered",
                        x=entity.x * TILE + 8,
                        y=entity.y * TILE,
                        combo_event="pickup",
                    )
                    if entity.extra.get("edit_route_bonus"):
                        self._award_score(300, "workshop route completed", x=entity.x * TILE + 8, y=entity.y * TILE)
                        self.messages.append("Your route paid off. Cache recovered: +300.")
                elif entity.kind == "logo":
                    entity.alive = False
                    self.note("logo")
                    self._begin_flight()
            elif (
                entity.kind == "enemy"
                and not entity.extra.get("converted")
                and not entity.extra.get("unrecruitable")
                and int(entity.extra.get("contact_grace") or 0) <= 0
                and self._entity_overlaps_player(entity, full_sprite=False)
            ):
                if entity.extra.get("warden"):
                    if inp.item or inp.action_pressed:
                        self.messages.append("Checksum rejects a bump. Throw a Logic Bomb.")
                        self._begin_combat(entity, boss=False)
                elif entity.extra.get("instant_convert"):
                    if inp.interact or inp.action_pressed or inp.item:
                        self._convert_side_enemy(entity, points=450)
                else:
                    self._begin_combat(entity, boss=False)
        self._tick_particles()
        if self.tick % 12 == 0:
            self._patrol_enemies()
        self._tick_boss_behaviors()
        # Movement belongs to the boss entity now; the X glyph remains only a
        # deterministic generation anchor. Enter RPG mode when David closes on
        # the moving silhouette rather than an abandoned tile coordinate.
        player_x, player_y = self.body.center
        boss_entity = next(
            (
                entity
                for entity in self.entities
                if entity.kind == "boss"
                and entity.alive
                and not entity.extra.get("converted")
                and int(entity.extra.get("field_fight_ticks") or 0) <= 0
                and self._boss_arena_ready(entity)
                and abs(entity.x * TILE + TILE / 2 - player_x) <= TILE * 3.2
                and abs(entity.y * TILE + float(entity.extra.get("offset_y") or 0.0) - player_y) <= TILE * 5.5
            ),
            None,
        )
        if boss_entity is not None:
            self._begin_combat(boss_entity, boss=True)
            self.note("hit")

    def _begin_combat(self, entity: Entity, *, boss: bool) -> None:
        if self.combat is not None:
            return
        if entity.kind == "enemy" and not entity.alive:
            return
        if entity.kind == "enemy" and entity.extra.get("unrecruitable"):
            return
        if boss and not self._boss_arena_ready(entity):
            return
        player = replace(
            make_player(self.character_name, capabilities=self.converted),
            bs=max(0, min(MAX_BS, self.player_bs)),
        )
        if boss:
            boss_id = entity.extra.get("boss") or CAMPAIGN_ROSTER[self.chapter_index].boss.id
            if boss_id in self.converted and boss_id != "goliath":
                self._advance_after_boss(boss_id)
                return
            if boss_id == "goliath" and self.goliath_stage == "penguin":
                foe = make_foe("goliath-cyborg-penguin")
                foe = replace(
                    foe,
                    bs=50,
                    conviction=min(100, foe.conviction + 8),
                    corruption=min(100, foe.corruption + 8),
                )
            else:
                foe = make_foe(boss_id, as_boss=True)
            if boss_id == "goliath" and self.goliath_stage == "duel":
                form = goliath_form(self.converted)
                foe = replace(foe, name=f"Goliath ({len(form['fragments'])} unresolved)")
            foe, carried = self._carry_side_pressure(foe, entity)
            self.combat = start_encounter(player, foe, boss_id=boss_id, mode="turn")
        else:
            variant = str(entity.extra.get("variant") or "dogma-sprite")
            foe = make_foe(variant, as_boss=False)
            foe, carried = self._carry_side_pressure(foe, entity)
            self.combat = start_encounter(player, foe, mode="turn")
        entity.extra["in_combat"] = True
        if carried:
            carry_note = f"Field pressure carries over ({carried}%): lower dogma, lower BS, higher trust."
            self.combat = replace(self.combat, log=self.combat.log + (carry_note,))
        self.battle_queue = []
        self.battle_delay_ticks = 0
        self.battle_actor = ""
        self.battle_flash_ticks = 0
        self.scene = "turn"
        self.messages.append(self.combat.log[-1])
        self.messages.append(
            f"{self.prompt_binding('jump')} reason · {self.prompt_binding('action')} patch · "
            f"directions fork/show · {self.prompt_binding('item')} item · "
            f"{self.prompt_binding('turn')} reuse · {self.prompt_binding('interact')} recruit"
        )
        self.flash_ticks = 6
        self.flash_kind = "combat"

    def _show_combat_deltas(self, before: CombatState, after: CombatState) -> None:
        player_delta = after.player.bs - before.player.bs
        if player_delta:
            sign = "+" if player_delta > 0 else ""
            color = (247, 118, 142) if player_delta > 0 else (158, 206, 106)
            self._popup(f"BS {sign}{player_delta}", 0, 48, color=color, space="battle", side="player")
        foe_parts: list[str] = []
        foe_bs = after.foe.bs - before.foe.bs
        trust = after.foe.trust - before.foe.trust
        dogma = after.foe.corruption - before.foe.corruption
        if foe_bs:
            foe_parts.append(f"BS {foe_bs:+d}")
        if trust:
            foe_parts.append(f"TRUST {trust:+d}")
        if dogma:
            foe_parts.append(f"DOGMA {dogma:+d}")
        if foe_parts:
            self._popup(" · ".join(foe_parts), 0, 48, color=(125, 207, 255), space="battle", side="foe")

    def _advance_battle_stage(self) -> None:
        if self.combat is None or not self.battle_queue:
            return
        stage = self.battle_queue.pop(0)
        before = self.combat
        self.combat = stage["state"]
        self.player_bs = self.combat.player.bs
        self.battle_actor = str(stage["actor"])
        self.battle_delay_ticks = int(stage["ticks"])
        self.battle_stage_ticks = self.battle_delay_ticks
        self.battle_flash_ticks = min(12, self.battle_delay_ticks)
        self._show_combat_deltas(before, self.combat)
        additions = self.combat.log[len(before.log) :]
        self.messages.extend(additions)
        if self.battle_actor:
            self.note("hit" if self.battle_actor == "foe" else "ui")

    def _resolve_battle_timeline(self) -> None:
        self.battle_actor = ""
        self.battle_flash_ticks = 0
        if self.combat is None:
            self.scene = "action"
            return
        if self.combat.foe.converted:
            foe_id = self.combat.foe.id
            cap = self.combat.foe.capabilities[0] if self.combat.foe.capabilities else foe_id
            staged_goliath = self.combat.boss_id == "goliath" and self.goliath_stage in {"penguin", "duel"}
            staged_minion = self.goliath_stage == "minions" and any(
                entity.extra.get("in_combat") and entity.extra.get("goliath_minion")
                for entity in self.entities
            )
            if not staged_goliath and not staged_minion:
                if cap not in self.converted:
                    self.converted.append(cap)
                if self.combat.boss_id and self.combat.boss_id not in self.converted:
                    self.converted.append(self.combat.boss_id)
            if foe_id in COMPANION_VARIANTS and foe_id not in self.converted:
                self.converted.append(foe_id)
            self.note("convert")
            self._finish_combat(converted=True)
        elif self.combat.player_overloaded:
            self._enter_recovery()
        elif self.combat.mode != "turn":
            self.scene = "action"

    def _tick_battle_timeline(self) -> bool:
        """Advance queued actors; return True while player input is blocked."""

        if self.battle_delay_ticks > 0:
            self.battle_delay_ticks -= 1
            self.battle_flash_ticks = max(0, self.battle_flash_ticks - 1)
            if self.battle_delay_ticks == 0:
                if self.battle_queue:
                    self._advance_battle_stage()
                else:
                    self._resolve_battle_timeline()
            return True
        if self.battle_queue:
            self._advance_battle_stage()
            return True
        return False

    def _queue_battle_round(
        self,
        *,
        action: str | None,
        use_item: bool,
        has_evidence: bool,
        has_reuse: bool,
    ) -> None:
        assert self.combat is not None
        self.battle_player_action = "item" if use_item else str(action or "reason")
        stages: list[dict[str, Any]] = []
        staged = self.combat

        def append_stage(actor: str, state: CombatState, ticks: int) -> None:
            if stages:
                # A neutral beat separates silhouettes and messages so player
                # and helper contributions do not visually collapse together.
                stages.append(
                    {
                        "actor": "",
                        "state": stages[-1]["state"],
                        "ticks": BATTLE_INTER_ACTION_TICKS,
                    }
                )
            stages.append({"actor": actor, "state": state, "ticks": ticks})

        if use_item:
            item = self.current_item
            staged = apply_action_item(staged, item, strength=self.item_effectiveness)
            append_stage("player", staged, 18)
            if item in CONSUMABLE_ITEMS:
                self._consume_current_item()
        else:
            assert action is not None
            staged = apply_player_turn(
                staged,
                action,
                has_evidence=has_evidence,
                has_reuse=has_reuse,
            )
            counter = INTENT_COUNTERS.get(self.combat.foe_intent)
            if action == counter and not staged.foe.converted:
                staged = replace(
                    staged,
                    foe=replace(
                        staged.foe,
                        bs=max(0, staged.foe.bs - 5),
                        conviction=max(0, staged.foe.conviction - 6),
                        corruption=max(0, staged.foe.corruption - 4),
                        trust=min(100, staged.foe.trust + 7),
                    ),
                    focus=min(100, staged.focus + 12),
                    log=staged.log + (
                        f"READ COMPLETE: {action.replace('-', ' ').upper()} counters {self.combat.foe_intent.replace('-', ' ')}.",
                    ),
                )
            append_stage("player", staged, 18)

        if not staged.foe.converted and staged.mode == "turn":
            for companion_id in self.active_companions:
                assisted = apply_companion_assist(staged, companion_id)
                assisted = apply_companion_combo(assisted, companion_id, action)
                if assisted is not staged:
                    staged = assisted
                    append_stage(companion_id, staged, 16)
            if action == "reuse" and {"justice-signaler", "detractabot"}.issubset(self.active_companions):
                staged = replace(
                    staged,
                    focus=min(100, staged.focus + 10),
                    log=staged.log + (
                        "COMBO · COMMUNITY PATCHSET: both helpers preserve the verified method.",
                    ),
                )
                self._increase_item_strength("community patchset", amount=2)
                append_stage("community-patchset", staged, 18)
            if use_item and item != RARE_BS_RESET_ITEM:
                staged = foe_action_pressure(staged)
                staged = replace(staged, round_index=staged.round_index + 1)
            elif not use_item:
                staged = apply_foe_turn(staged)
            if not use_item or item != RARE_BS_RESET_ITEM:
                append_stage("foe", staged, 24)

        self.battle_queue = stages
        self._advance_battle_stage()

    def _step_turn(self, inp: InputState) -> None:
        if self.combat is None:
            self.scene = "action"
            return
        if self._tick_battle_timeline():
            return
        action = None
        use_item = False
        if inp.jump_pressed:
            action = "reason"
        elif inp.action_pressed:
            action = "patch"
        elif inp.left_pressed:
            action = "fork"
        elif inp.right_pressed:
            action = "demonstrate"
        elif inp.turn_pressed:
            action = "reuse"
        elif inp.item:
            use_item = True
        elif inp.interact:
            action = "recruit"
        if action is None and not use_item:
            return
        has_evidence = self.penguins > 0 or "provenance-pass" in self.converted
        has_reuse = bool(self.settings.get("lastReuse")) or "compat-shim" in self.converted
        self._queue_battle_round(
            action=action,
            use_item=use_item,
            has_evidence=has_evidence,
            has_reuse=has_reuse,
        )

    def _enter_recovery(self) -> None:
        self.messages.append("BS meter maxed. Step back. Breathe. Then retry.")
        self.combat = None
        self.battle_queue = []
        self.battle_delay_ticks = 0
        self.battle_actor = ""
        self.battle_flash_ticks = 0
        for entity in self.entities:
            entity.extra["in_combat"] = False
        self.recovery_reason = "argument-overload"
        self.scene = "recovery"
        self.flash_ticks = 10
        self.flash_kind = "combat"
        self.note("hit")

    def use_item_in_action(self) -> None:
        if self.combat is None:
            return
        item = self.current_item
        self.combat = apply_action_item(self.combat, item, strength=self.item_effectiveness)
        if item != RARE_BS_RESET_ITEM:
            self.combat = foe_action_pressure(self.combat)
        self.player_bs = self.combat.player.bs
        if item in CONSUMABLE_ITEMS:
            self._consume_current_item()
        self.messages.append(self.combat.log[-1])
        if item == "logic-bomb":
            self.flash_ticks = 10
            self.flash_kind = "bomb"
        if self.combat.foe_ready_to_recruit:
            self.messages.append(
                f"They hesitate. {self.prompt_binding('turn')} can reuse evidence; "
                f"{self.prompt_binding('interact')} recruits."
            )

    def _finish_combat(self, *, converted: bool) -> None:
        boss_id = self.combat.boss_id if self.combat else None
        foe_name = self.combat.foe.name if self.combat else "argument"
        engaged = [entity for entity in self.entities if entity.extra.get("in_combat")]
        if self.combat is not None:
            self.player_bs = self.combat.player.bs
        self.combat = None
        self.battle_queue = []
        self.battle_delay_ticks = 0
        self.battle_actor = ""
        self.battle_flash_ticks = 0
        self.scene = "action"
        if converted and boss_id == "goliath" and self.goliath_stage in {"penguin", "duel"}:
            boss = next((entity for entity in engaged if entity.kind == "boss"), None)
            if boss is None:
                boss = next(
                    (
                        entity
                        for entity in self.entities
                        if entity.kind == "boss" and entity.extra.get("boss") == "goliath"
                    ),
                    None,
                )
            if boss is not None:
                boss.extra["in_combat"] = False
                self.flash_ticks = 14
                self.flash_kind = "convert"
                if self.goliath_stage == "penguin":
                    self._award_score(1500, f"{foe_name} disabled")
                    self._begin_boss_defeat(boss, boss_id, next_phase="duel")
                else:
                    self._award_score(2500, f"{foe_name} defeated")
                    self._begin_boss_defeat(boss, boss_id, next_phase="minions")
            return
        for entity in self.entities:
            if entity.extra.get("in_combat"):
                entity.extra["in_combat"] = False
                if converted:
                    entity.extra["converted"] = True
                    entity.alive = True
                    variant = str(entity.extra.get("variant") or "")
                    if variant in COMPANION_VARIANTS:
                        entity.extra["companion"] = True
                        entity.extra["assist_cooldown"] = 28
        if converted:
            self.flash_ticks = 14
            self.flash_kind = "convert"
            if not boss_id:
                self.messages.append("They keep the shape. They drop the dogma.")
                self._award_score(350, foe_name)
            else:
                self._award_score(2500, f"{foe_name} converted")
            for entity in self.entities:
                if not entity.extra.get("converted"):
                    continue
                if entity.extra.get("variant") in {"dogma", "dogma-sprite"} and self.tiles:
                    # Converted dogma becomes a standing platform — a real traversal gift.
                    row = list(self.tiles[entity.y])
                    if 0 <= entity.x < len(row) and row[entity.x] == ".":
                        row[entity.x] = "="
                        self.tiles[entity.y] = "".join(row)
                    self.messages.append("The converted sprite holds still as a step.")
                if entity.extra.get("variant") == "warden":
                    self._open_nearby_gates(entity.x, entity.y)
                    self.messages.append("The warden stamps the gate open.")
                if entity.extra.get("goliath_minion"):
                    self._count_goliath_minion(entity)
        if converted and boss_id:
            boss = next((entity for entity in engaged if entity.kind == "boss"), None)
            self._begin_boss_defeat(boss, boss_id)

    def _begin_boss_defeat(self, boss: Entity | None, boss_id: str, *, next_phase: str = "advance") -> None:
        """Finish the physical encounter before displaying score or next phase."""
        if boss is None:
            self._advance_after_boss(boss_id)
            return
        start_y = boss.y + float(boss.extra.get("offset_y") or 0.0) / TILE
        start_x = boss.x + float(boss.extra.get("offset_x") or 0.0) / TILE
        column = max(0, min(len(self.tiles[0]) - 1, int(start_x)))
        floor_y = next((row - 1 for row in range(max(0, int(start_y) + 1), len(self.tiles))
                        if self.tiles[row][column] in SOLID), len(self.tiles) - 5)
        boss.x, boss.y = start_x, start_y
        boss.extra.update(converted=True, in_combat=False, ability_flash=0,
                          offset_x=0.0, offset_y=0.0, defeat_settling=True)
        self.boss_defeat = {"bossId": boss_id, "nextPhase": next_phase,
                            "startY": start_y, "floorY": float(floor_y)}
        self.boss_defeat_ticks = 0
        self.enemy_projectiles = []
        self.flash_ticks = 0
        self.scene = "boss-defeat"
        if self.body:
            self.body = replace(self.body, vx=0.0, vy=0.0)
        # Keep the landing in view without moving the player's world position.
        self.cam_x = max(0.0, min(len(self.tiles[0]) * TILE - 320, (boss.x + .5) * TILE - 225))
        self.cam_y = max(0.0, min(len(self.tiles) * TILE - 180, (floor_y + 1) * TILE - 145))
        self.boss_defeat.update(cameraX=self.cam_x, cameraY=self.cam_y)

    def _step_boss_defeat(self) -> None:
        state = self.boss_defeat
        if not state:
            self.scene = "action"
            return
        boss = next((entity for entity in self.entities if entity.kind == "boss"
                     and entity.extra.get("boss") == state["bossId"]), None)
        self.boss_defeat_ticks += 1
        progress = min(1.0, self.boss_defeat_ticks / BOSS_SETTLE_TICKS)
        if boss is not None:
            # Accelerate down to the floor, then hold the registered defeat.
            boss.y = state["startY"] + (state["floorY"] - state["startY"]) * progress * progress
            boss.extra["defeat_settling"] = progress < 1
        if self.boss_defeat_ticks < BOSS_SETTLE_TICKS + BOSS_DEFEAT_HOLD_TICKS:
            return
        self.boss_defeat = {}
        self.scene = "action"
        if boss is not None and state["nextPhase"] == "duel":
            self._start_goliath_duel(boss)
        elif boss is not None and state["nextPhase"] == "minions":
            self._start_goliath_minion_phase(boss)
        else:
            self._advance_after_boss(state["bossId"])

    def _advance_after_boss(self, boss_id: str) -> None:
        spec = CAMPAIGN_ROSTER[self.chapter_index]
        self.messages.append(spec.boss.converted_line)
        if spec.boss.id == "goliath":
            self.ending = True
            self.start_credits(cinematic=True, return_scene="stage-map")
            self.messages.append("The revolution will be customized.")
            return
        next_index = self.chapter_index + 1
        if self.chapter_index == 0:
            self._show_chapter_complete(next_index)
            self.messages.append("Chapter 1 sealed. Later chapters remain in active development.")
            return
        if "oligarchy" in spec.events:
            self.oligarchy = True
            self.hud_wordmark = "OLIGARCHY"
            self.scene = "oligarchy"
            self.pending_chapter = next_index if next_index < len(CAMPAIGN_ROSTER) else None
            self.messages.append("OLIGARCHY FORMED. The sign grew extra letters. The money is loud. The joke is ours.")
            return
        if "singularity" in spec.events:
            self.messages.append("The Singularity demanded one future. You kept several.")
        if next_index < len(CAMPAIGN_ROSTER):
            nxt = CAMPAIGN_ROSTER[next_index]
            self.messages.append(f"Stamp accepted. {nxt.name} is available on the route map.")
            self._show_chapter_complete(next_index)

    def _show_chapter_complete(self, next_index: int | None) -> None:
        """Hold each pre-Goliath victory on its own readable end screen."""

        self.post_boss = True
        self.post_boss_ticks = 0
        self.pending_chapter = (
            next_index
            if next_index is not None and next_index < len(CAMPAIGN_ROSTER)
            else None
        )
        self.scene = "chapter-complete"
        self.note("ui")

    def chapter_complete_ready(self) -> bool:
        return self.scene != "chapter-complete" or self.post_boss_ticks >= CHAPTER_COMPLETE_TALLY_TICKS

    def _chapter_tally_amount(self, total: int) -> int:
        if self.chapter_complete_ready():
            return total
        t = min(1.0, self.post_boss_ticks / max(1, CHAPTER_COMPLETE_TALLY_TICKS))
        eased = 1.0 - (1.0 - t) ** 3
        return int(total * eased + 0.5)

    def chapter_tally_score(self) -> int:
        return self._chapter_tally_amount(self.score)

    def chapter_tally_penguins(self) -> int:
        return self._chapter_tally_amount(self.penguins)

    def _step_chapter_complete(self, inp: InputState) -> None:
        self.post_boss_ticks += 1
        if not self.chapter_complete_ready():
            return
        if inp.turn_pressed:
            self._continue_development_chapters()
            return
        if inp.action_pressed:
            self.save_to_disk()
            return
        if inp.jump_pressed or inp.interact:
            self.start_credits(return_scene="chapter-complete")
            self.note("ui")

    def start_credits(self, *, cinematic: bool = False, return_scene: str = "pause") -> None:
        self.credits_ticks = 0
        self.credits_elapsed = 0.0
        self.credits_shortcut_lock = max(self.credits_shortcut_lock, 1)
        self.credits_return_scene = return_scene
        self.credits = not cinematic
        self.scene = "ending" if cinematic else ("chapter-credits" if return_scene == "chapter-complete" else "credits")
        self.sfx.clear()
        self.audio_caption = ""

    def _step_credits(self, inp: InputState, *, frame_seconds: float = 1 / 60) -> None:
        from .credits import FPS, roll_duration, title_duration

        # Wall time in the live app keeps a slow frame from lengthening the
        # roll past its recording. Fixed steps remain deterministic in replays.
        self.credits_elapsed += max(0.0, frame_seconds)
        self.credits_ticks = round(self.credits_elapsed * FPS)
        if self.credits_shortcut_lock > 0:
            self.credits_shortcut_lock = max(
                0, self.credits_shortcut_lock - max(1, round(max(0.0, frame_seconds) * FPS))
            )
        # The entry button cannot immediately dismiss the next sequence.
        skip = self.credits_ticks > 30 and (inp.pause or inp.jump_pressed or inp.interact)
        duration = title_duration() if self.scene == "ending" else roll_duration()
        if skip or self.credits_ticks >= math.ceil(duration * FPS):
            if self.scene == "ending":
                self.start_credits(return_scene=self.credits_return_scene)
            else:
                self.credits = False
                self.scene = self.credits_return_scene

    def _continue_development_chapters(self) -> None:
        if self.web_chapter_one:
            self.messages.append("Later development chapters are available in the native build.")
            self.note("ui")
            return
        nxt = self.pending_chapter
        if nxt is None and self.chapter_index + 1 < len(CAMPAIGN_ROSTER):
            nxt = self.chapter_index + 1
        if nxt is None or nxt >= len(CAMPAIGN_ROSTER):
            return
        self.post_boss = False
        self.post_boss_ticks = 0
        self._open_stage_map(nxt)
        if self.chapter_index == 0:
            self.messages.append("Development route opened. Content beyond Chapter 1 is still in active development.")
        else:
            self.messages.append("Route map reopened.")

    def _open_stage_map(self, next_index: int, *, transition: bool = True) -> None:
        preferred = max(0, min(next_index, len(CAMPAIGN_ROSTER) - 1))
        self.stage_cursor = self._preferred_stage_cursor(preferred)
        self.pending_chapter = self.stage_cursor
        self.stage_map_transition_ticks = STAGE_MAP_TRANSITION_TICKS if transition else 0
        self.stage_map_input_lock_ticks = STAGE_MAP_INPUT_LOCK_TICKS
        self.scene = "stage-map"
        self.note("ui")

    def _begin_level_intro(self, target: int) -> None:
        """Lock input while the selected map assembles into its title card."""

        self.level_intro_target = max(0, min(target, len(CAMPAIGN_ROSTER) - 1))
        self.level_intro_ticks = 0
        self.level_intro_loaded = False
        self.pending_chapter = self.level_intro_target
        self.post_boss = False
        self.scene = "level-intro"
        self.note("ui")

    def _step_level_intro(self) -> None:
        self.level_intro_ticks += 1
        if (
            not self.level_intro_loaded
            and self.level_intro_ticks >= LEVEL_INTRO_WORLD_REVEAL_TICK
        ):
            self._load_chapter(self.level_intro_target)
            self.level_intro_loaded = True
        if self.level_intro_ticks < LEVEL_INTRO_TICKS:
            return
        target = self.level_intro_target
        self.pending_chapter = None
        self.scene = "action"
        self.messages.append(f"ROUTE MOUNTED · {CAMPAIGN_ROSTER[target].name}")
        self.note("ui")

    def _step_stage_map(self, inp: InputState) -> None:
        if self.stage_map_transition_ticks > 0:
            self.stage_map_transition_ticks -= 1
            return
        if self.stage_map_input_lock_ticks > 0:
            self.stage_map_input_lock_ticks -= 1
            return
        dx = int(inp.right_pressed) - int(inp.left_pressed)
        dy = int(inp.down_pressed) - int(inp.up_pressed)
        if dx or dy:
            target = self._spatial_stage_neighbor(dx, dy)
            if target != self.stage_cursor:
                self.stage_cursor = target
                self.pending_chapter = target
                self.note("ui")
            return
        if not (inp.jump_pressed or inp.action_pressed or inp.interact):
            return
        target = self.stage_cursor
        if target not in self.unlocked_stage_indices():
            spec = CAMPAIGN_ROSTER[self.stage_cursor]
            self.messages.append(f"{spec.name}: LOCKED. Complete the connected installations first.")
            self.note("hit")
            return
        self.pending_chapter = None
        self._begin_level_intro(target)

    def dismiss_oligarchy(self) -> None:
        if self.scene != "oligarchy":
            return
        nxt = self.pending_chapter
        if nxt is not None and nxt < len(CAMPAIGN_ROSTER):
            self._show_chapter_complete(nxt)
        else:
            self.pending_chapter = None
            self.scene = "action"

    def side_sprite_frame(self) -> str:
        """Return the authored side-view pose represented by current physics."""

        if self.body is None:
            return "side-idle"
        if self.attack_timer > 0 and not self.body.on_ground:
            return "side-air-action"
        if self.attack_timer > 0:
            return "side-bomb" if self.action_kind == "item" else "side-action"
        if self.body.on_ladder:
            return f"side-climb-{self.body.climb_phase}"
        if self.body.sliding:
            return "side-slide"
        if self.body.crouching:
            return "side-crouch"
        if not self.body.on_ground:
            return "side-fall" if self.body.vy > 0.6 else "side-jump"
        if abs(self.body.vx) > 0.4:
            cadence = 3 if self.body.rushing else 6
            return ("side-walk-0", "side-idle", "side-walk-2", "side-idle")[(self.tick // cadence) % 4]
        return "side-idle"

    def _begin_flight(self) -> None:
        if self.body is not None:
            feet_x, feet_y = self.body.feet
            frame = self.side_sprite_frame()
            self.edit_player_ghost = {
                "feet_x": feet_x,
                "feet_y": feet_y,
                "facing": self.body.facing,
                "frame": frame,
                "visual_drop": 8.0 if frame == "side-slide" else 0.0,
                "map_index": self.map_index,
            }
        self.scene = "flight"
        self.flight_ticks = FLIGHT_TICKS
        self.flight_direction = "out"
        self.editing = False
        self.messages.append(f"{self.character_name} flies out of the playfield toward the edit view.")

    def _step_flight(self, inp: InputState) -> None:
        self.flight_ticks = max(0, self.flight_ticks - 1)
        if self.flight_ticks <= 0:
            if self.flight_direction == "in":
                self.scene = "action"
                self.edit_player_ghost = None
                self.messages.append(f"{self.character_name} lands back in the playfield.")
            else:
                self._enter_edit()

    def _begin_network_transition(self, entity: Entity) -> None:
        if self.body is None or not self.network_armed:
            return
        destination = entity.extra.get("destination") or (int(entity.x), int(entity.y))
        self.network_destination = (int(destination[0]), int(destination[1]))
        self.network_destination_map = int(entity.extra.get("targetMap", self.map_index))
        self.network_destination_portal = str(entity.extra.get("targetPortal") or "")
        self.network_direction = int(entity.extra.get("direction") or 1)
        self.network_protocol = str(entity.extra.get("protocol") or "ethernet")
        self.network_operation = str(entity.extra.get("operation") or "route negotiation")
        self.network_ticks = SKYWAY_TRANSFER_TICKS if self.network_protocol == "skyway" else NETWORK_TICKS
        self.network_start = (self.body.x, self.body.y)
        self.network_armed = False
        self.scene = "network"
        self.body = replace(self.body, vx=0.0, vy=0.0)
        if self.network_protocol != "skyway":
            self.messages.append(f"{self.network_protocol.upper()}: {self.network_operation}.")
        self.note("ui")

    def _step_network(self, inp: InputState) -> None:
        """Run a short deterministic connection/traversal interstitial."""

        self.network_ticks = max(0, self.network_ticks - 1)
        if self.network_protocol == "skyway" and self.body is not None:
            tx, ty = self.network_destination
            target_x = tx * TILE + (TILE - self.body.width) / 2
            target_y = (ty + 1) * TILE - self.body.height
            progress = 1 - self.network_ticks / SKYWAY_TRANSFER_TICKS
            progress = progress * progress * (3 - 2 * progress)
            self.body = replace(self.body,
                                x=self.network_start[0] + (target_x - self.network_start[0]) * progress,
                                y=self.network_start[1] + (target_y - self.network_start[1]) * progress)
            self._snap_camera()
        if self.network_ticks > 0 or self.body is None:
            return
        tx, ty = self.network_destination
        if self.network_destination_portal:
            self._activate_map(self.network_destination_map, spawn_companions=False)
            target = next(
                (
                    entity
                    for entity in self.entities
                    if entity.kind == "network"
                    and str(entity.extra.get("portal") or "") == self.network_destination_portal
                ),
                None,
            )
            if target is None:
                raise RuntimeError(f"network destination portal missing: {self.network_destination_portal}")
            tx, ty = int(target.x), int(target.y)
        else:
            # Legacy same-map links still carry followers rather than asking
            # them to path across a gap after David disappears.
            self.entities[:] = [entity for entity in self.entities if not entity.extra.get("companion")]
        landing_y = (ty + 1) * TILE - self.body.height
        self.body = replace(
            self.body,
            x=tx * TILE + (TILE - self.body.width) / 2,
            y=landing_y,
            vx=self.network_direction * 0.8,
            vy=0.0,
            on_ground=True,
            on_ladder=False,
            sliding=False,
            slide_locked=False,
            crouching=False,
        )
        self._spawn_persistent_companions()
        self._snap_camera()
        self.network_cooldown = 0
        # Re-arm only after the complete player hitbox leaves every portal.
        # Merely waiting on the arrival tile can never bounce back.
        self.network_armed = False
        self.scene = "action"
        if self.network_protocol != "skyway":
            self.messages.append(f"Link established. Traversed by {self.network_protocol.upper()}.")
        self.note("collect")

    def _edit_bounds(self) -> tuple[int, int, int, int]:
        min_x = max(0, int(self.cam_x // TILE))
        min_y = 0
        max_x = min(len(self.tiles[0]) - 1, int((self.cam_x + 320 - 1) // TILE))
        max_y = len(self.tiles) - 1
        return min_x, min_y, max_x, max_y

    @staticmethod
    def _rect_cells(x: float, y: float, width: float, height: float) -> set[tuple[int, int]]:
        right = x + width - 1e-6
        bottom = y + height - 1e-6
        return {
            (tx, ty)
            for ty in range(int(y // TILE), int(bottom // TILE) + 1)
            for tx in range(int(x // TILE), int(right // TILE) + 1)
        }

    def edit_reserved_cells(self) -> set[tuple[int, int]]:
        """Cells occupied by the left-behind player pose or live helpers."""

        reserved: set[tuple[int, int]] = self.skyway_reserved_cells()
        ghost = self.edit_player_ghost
        if ghost and int(ghost.get("map_index", -1)) == self.map_index:
            feet_x = float(ghost["feet_x"])
            feet_y = float(ghost["feet_y"]) + float(ghost.get("visual_drop") or 0.0)
            reserved.update(
                self._rect_cells(
                    feet_x - 11.0,
                    feet_y - CHAR_WORLD_HEIGHT,
                    22.0,
                    CHAR_WORLD_HEIGHT,
                )
            )
        for entity in self.entities:
            if not entity.alive or not entity.extra.get("companion"):
                continue
            # Followers use a 24-world-pixel silhouette anchored to their
            # entity tile, matching side-play collision/readability rules.
            reserved.update(
                self._rect_cells(
                    entity.x * TILE,
                    entity.y * TILE - 8.0,
                    TILE,
                    24.0,
                )
            )
        if not self.tiles:
            return set()
        return {
            (x, y)
            for x, y in reserved
            if 0 <= y < len(self.tiles) and 0 <= x < len(self.tiles[0])
        }

    def skyway_reserved_cells(self) -> set[tuple[int, int]]:
        return {(int(entity.x), int(entity.y) + offset)
                for entity in self.entities if entity.alive and entity.extra.get("skyway")
                for offset in (-2, -1, 0, 1)}

    def _begin_return_flight(self) -> None:
        self.editing = False
        self.scene = "flight"
        self.flight_direction = "in"
        self.flight_ticks = FLIGHT_TICKS

    def _enter_edit(self) -> None:
        assert self.body is not None
        self.editing = True
        self.scene = "edit"
        tx, ty = self._tile_under_player()
        min_x, min_y, max_x, max_y = self._edit_bounds()
        self.edit_cursor = (max(min_x, min(max_x, tx)), max(min_y, min(max_y, ty - 4)))
        self.edit_ops = []
        self.edit_tile_index = 0
        self.edit_move_cooldown = 0
        # Broken crates and other changes made during play belong to this
        # event's baseline too. Cancel must restore exactly what was visible.
        self.original_tiles = list(self.tiles)
        self.chapter_map_originals[self.map_index] = self.original_tiles
        self.zone_history = [list(self.tiles)]
        self.edit_start = (tx, ty)
        self.edit_goal_ready = False
        self.edit_baseline_reachable = reachable_from(self.tiles, self.edit_start)
        occupied = self.edit_reserved_cells() | {(e.x, e.y) for e in self.entities if e.alive}
        upper = self.active_upper_route
        self.edit_reward = None if upper else cache_goal(self.tiles, self.edit_start, self._edit_bounds(), occupied, self.edit_baseline_reachable)
        if self.edit_reward:
            reward_x, reward_y = self.edit_reward
            item = COMMON_ITEMS[(self.chapter_index + reward_x) % len(COMMON_ITEMS)]
            self.entities.append(Entity("item", reward_x, reward_y, extra={"item": item, "edit_reward": True, "edit_pending": True}))
        self._refresh_edit_routes()
        self.messages.append(
            f"Edit view: {self.prompt_binding('action')} place · "
            f"{self.prompt_binding('item')} erase · {self.prompt_binding('turn')} tile type · "
            f"{self.prompt_binding('jump')} seal. "
            + ("Connect the gold cache, then collect it for +300." if self.edit_reward else "Free build: open a new route.")
        )

    @property
    def active_upper_route(self) -> dict[str, Any]:
        return self.chapter_map_upper[self.map_index] if self.map_index < len(self.chapter_map_upper) else {}

    def _new_edit_landings(self, tiles: list[str]) -> list[tuple[int, int]]:
        left, top, right, bottom = self._edit_bounds()
        reserved = self.edit_reserved_cells()
        return [
            (x, y) for x, y in self.edit_new_reachable
            if left <= x <= right and top <= y <= bottom and y >= 2 and y + 1 < len(tiles)
            and tiles[y][x] in {".", "L", "+"}
            and tiles[y + 1][x] in {"#", "=", "I", "+", "B", "D", "G"}
            and all(tiles[yy][x] in {".", "L", "+"} for yy in (y - 1, y - 2))
            and (x, y) not in reserved
            and not any(e.alive and int(e.x) == x and int(e.y) == y for e in self.entities)
        ]

    @staticmethod
    def _skyway_lift_pair(lift: dict[str, Any]) -> list[Entity]:
        lower, upper = lift["lower"], lift["upper"]
        return [Entity("network", x, y, extra={
            "skyway": True, "protocol": "skyway", "operation": "Ascending to the skyway" if ascending else "Returning to your construction",
            "destination": list(destination), "direction": 1,
        }) for (x, y), destination, ascending in ((lower, upper, True), (upper, lower, False))]

    def _build_skyway_lift(self) -> None:
        upper = self.active_upper_route
        if not upper or not self.edit_goal_ready:
            return
        candidates = self._new_edit_landings(self.tiles)
        if not candidates:
            return
        lower = min(candidates, key=lambda p: (self.tiles[p[1] + 1][p[0]] != "+", abs(p[0] - self.edit_start[0]) + abs(p[1] - self.edit_start[1]), p))
        destination = min(upper["entries"], key=lambda p: abs(p[0] - lower[0]))
        lift = {"lower": list(lower), "upper": list(destination)}
        upper["lifts"] = [*upper.get("lifts", []), lift]
        upper["unlocked"] = True
        self.entities.extend(self._skyway_lift_pair(lift))
        # Keep runtime-map metadata with the sealed chapter. Cow's ephemeral
        # map is persisted separately in progress along with its tile edits.
        chapter = dict(self.chapter)
        if chapter.get("maps") and self.map_index < len(chapter["maps"]):
            maps = [dict(spec) for spec in chapter["maps"]]
            maps[self.map_index]["upperTraversal"] = dict(upper)
            chapter["maps"] = maps
        elif self.map_index == 0:
            chapter["upperTraversal"] = dict(upper)
        self.world.chapters[self.chapter_index] = chapter
        self.note("collect")

    def _refresh_edit_routes(self) -> None:
        # Sealing normalizes ladder ends. Forecast that same arrangement, and
        # recompute only after edits/undo/reset rather than on every frame.
        preview = normalize_ladder_tiles(self.tiles)
        self.edit_reachable = reachable_from(preview, self.edit_start)
        self.edit_new_reachable = self.edit_reachable - self.edit_baseline_reachable
        was_ready = self.edit_goal_ready
        if self.edit_reward is not None:
            self.edit_goal_ready = self.edit_reward in self.edit_reachable
        else:
            self.edit_goal_ready = bool(self._new_edit_landings(preview))
        if self.edit_goal_ready and not was_ready:
            self.messages.append("Route connected in the forecast. Seal, then try it in play.")
            self.note("ui")

    def _finish_edit_reward(self, *, sealed: bool) -> None:
        for entity in self.entities:
            if not entity.extra.get("edit_pending"):
                continue
            entity.extra.pop("edit_pending", None)
            if sealed:
                # Collection is the proof and earns the bonus, even when the
                # static forecast could not recognize a creative solution.
                entity.extra["edit_route_bonus"] = True
            else:
                entity.alive = False
        if not sealed:
            self.edit_reward = None

    def _step_edit(self, inp: InputState) -> None:
        cx, cy = self.edit_cursor
        min_x, min_y, max_x, max_y = self._edit_bounds()
        pressed = inp.left_pressed or inp.right_pressed or inp.up_pressed or inp.down_pressed
        held = inp.left or inp.right or inp.up or inp.down
        move_now = bool(pressed or (held and self.edit_move_cooldown <= 0))
        if self.edit_move_cooldown > 0:
            self.edit_move_cooldown -= 1
        if move_now:
            self.edit_move_cooldown = 5
        if move_now and inp.left:
            cx = max(min_x, cx - 1)
        if move_now and inp.right:
            cx = min(max_x, cx + 1)
        if move_now and inp.up:
            cy = max(min_y, cy - 1)
        if move_now and inp.down:
            cy = min(max_y, cy + 1)
        self.edit_cursor = (cx, cy)
        palette = ("=", "L", "^")
        if inp.turn_pressed:
            self.edit_tile_index = (self.edit_tile_index + 1) % len(palette)
            self.messages.append(f"Edit tile: {palette[self.edit_tile_index]}")
        if inp.action_pressed:
            tile = palette[self.edit_tile_index]
            if (cx, cy) in self.edit_reserved_cells():
                self.messages.append("Edit blocked: player and helper positions are protected.")
                self.note("hit")
            elif self.tiles[cy][cx] == tile:
                self.messages.append(f"Tile is already {tile}; budget unchanged.")
            else:
                op = {"op": "place", "x": cx, "y": cy, "tile": tile}
                self.edit_ops.append(op)
                if self._refresh_edit_preview():
                    self.messages.append(f"Placed {tile} (unsealed).")
                else:
                    self.edit_ops.pop()
        if inp.item:
            if (cx, cy) in self.edit_reserved_cells():
                self.messages.append("Edit blocked: player and helper positions are protected.")
                self.note("hit")
            elif self.tiles[cy][cx] == ".":
                self.messages.append("Tile is already empty; budget unchanged.")
            else:
                self.edit_ops.append({"op": "remove", "x": cx, "y": cy})
                if self._refresh_edit_preview():
                    self.messages.append("Removed tile (unsealed).")
                else:
                    self.edit_ops.pop()
        if inp.customize:
            self.edit_ops = []
            self._refresh_edit_preview()
            self.messages.append("Edit reset to the untouched zone.")
            return
        if inp.interact and not inp.jump_pressed:
            if self.edit_ops:
                self.edit_ops.pop()
                self._refresh_edit_preview()
                self.messages.append("Last edit undone.")
            else:
                self.tiles = list(self.original_tiles)
                self.chapter_map_tiles[self.map_index] = self.tiles
                self._finish_edit_reward(sealed=False)
                self.messages.append("Edit discarded.")
                self._begin_return_flight()
            return
        if inp.jump_pressed:
            self._seal_edit()

    def effective_edit_ops(self) -> list[dict[str, Any]]:
        """Collapse edit history to one budgeted final mutation per cell.

        History remains intact for one-step undo, while the resource budget and
        sealed delta reflect only differences from the map that entered edit
        mode. Swapping an unsealed tile is therefore free, and erasing a tile
        placed during this event restores its budget point.
        """

        edited = apply_operations(list(self.original_tiles), self.edit_ops)
        operations: list[dict[str, Any]] = []
        for y, (before_row, after_row) in enumerate(zip(self.original_tiles, edited)):
            for x, (before, after) in enumerate(zip(before_row, after_row)):
                if before == after:
                    continue
                if after == ".":
                    operations.append({"op": "remove", "x": x, "y": y})
                else:
                    operations.append({"op": "place", "x": x, "y": y, "tile": after})
        return operations

    @property
    def edit_budget_used(self) -> int:
        try:
            return len(self.effective_edit_ops())
        except (IndexError, KeyError, TypeError, ValueError):
            return MAX_OPS + 1

    def _refresh_edit_preview(self) -> bool:
        reserved = self.edit_reserved_cells()
        if any((int(op["x"]), int(op["y"])) in reserved for op in self.edit_ops):
            self.messages.append("Edit rejected: player and helper positions are protected.")
            return False
        try:
            preview = apply_operations(list(self.original_tiles), self.edit_ops)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            self.messages.append(f"Edit rejected: {exc}")
            return False
        effective = self.effective_edit_ops()
        if len(effective) > MAX_OPS:
            self.messages.append(f"Edit rejected: budget is capped at {MAX_OPS} changed tiles.")
            return False
        if sum(op.get("op") == "place" for op in effective) > MAX_PLACED:
            self.messages.append(f"Edit rejected: only {MAX_PLACED} placed tiles may remain.")
            return False
        self.tiles = preview
        self.chapter_map_tiles[self.map_index] = self.tiles
        self.zone_history.append(list(self.tiles))
        self._refresh_edit_routes()
        return True

    def _seal_edit(self) -> None:
        assert self.world is not None
        operations = self.effective_edit_ops()
        if not operations:
            self._finish_edit_reward(sealed=False)
            self.messages.append("No changes to seal. Returning to play.")
            self._begin_return_flight()
            return
        chapter = dict(self.chapter)
        if len(self.chapter_map_tiles) > 1:
            self.tiles = normalize_ladder_tiles(self.tiles)
            maps = [dict(spec) for spec in chapter.get("maps") or ()]
            if self.map_index < len(maps):
                maps[self.map_index]["tiles"] = list(self.tiles)
                chapter["maps"] = maps
            elif self.map_index == 0:
                chapter["tiles"] = list(self.tiles)
            self.world.chapters[self.chapter_index] = chapter
            self.original_tiles = list(self.tiles)
            self.chapter_map_originals[self.map_index] = self.original_tiles
            self.chapter_map_tiles[self.map_index] = self.tiles
            self.messages.append("Hardware-island delta sealed. Reversible within this world.")
            self._award_score(500, "world edit sealed")
            self._finish_edit_reward(sealed=True)
            self._build_skyway_lift()
            self._begin_return_flight()
            return
        chapter["tiles"] = list(self.original_tiles)
        delta, report = make_delta(
            chapter,
            operations,
            world_digest=self.world.identity.digest(),
            generator_version=self.world.identity.generator_version,
            content_digest=self.world.identity.content_digest,
        )
        if delta is None:
            self.messages.append("Invalid arrangement: " + ",".join(report["errors"]))
            self.error = "invalid-zone-delta"
            return
        updated = apply_delta(chapter, delta)
        self.tiles = list(updated["tiles"])
        self.chapter_map_tiles[self.map_index] = self.tiles
        self.world.chapters[self.chapter_index] = updated
        self.original_tiles = list(self.tiles)
        self.chapter_map_originals[self.map_index] = self.original_tiles
        self.messages.append("Zone delta sealed. Reversible.")
        self._award_score(500, "world edit sealed")
        self._finish_edit_reward(sealed=True)
        self._build_skyway_lift()
        self._begin_return_flight()

    def pause_rows(self) -> tuple[str, ...]:
        if self.display == "crt" and not self.accessibility.reduced_motion:
            return (
                "fidelity",
                "display",
                "scanlines",
                "curvature",
                "phosphor",
                "items",
                "audio",
                "controls",
                "reroll",
                "omega-code",
                "credits",
            )
        return ("fidelity", "display", "items", "audio", "controls", "reroll", "omega-code", "credits")

    def _adjust_crt_control(self, control: str, delta: int) -> None:
        current = dict(self.settings.get("crt") or {})
        key = {"scanlines": "scanline", "curvature": "curvatureControl", "phosphor": "phosphor"}[control]
        value = max(0.0, min(1.0, float(current.get(key, 0.12)) + delta * 0.05))
        scanline = value if key == "scanline" else float(current.get("scanline", current.get("intensity", 0.12)))
        curvature = value if key == "curvatureControl" else float(current.get("curvatureControl", current.get("intensity", 0.12)))
        phosphor = value if key == "phosphor" else float(current.get("phosphor", 0.12))
        self.settings["crt"] = crt_controls(scanline, curvature, phosphor, enabled=self.display == "crt")
        label = "Curvature" if key == "curvatureControl" else key.title()
        self.messages.append(f"{label} {round(value * 100):02d}%")

    def _step_pause(self, inp: InputState) -> None:
        rows = self.pause_rows()
        self.pause_cursor %= len(rows)
        if inp.up_pressed:
            self.pause_cursor = (self.pause_cursor - 1) % len(rows)
            self.note("ui")
            return
        if inp.down_pressed:
            self.pause_cursor = (self.pause_cursor + 1) % len(rows)
            self.note("ui")
            return
        delta = -1 if inp.left_pressed else (1 if inp.right_pressed else 0)
        selected = rows[self.pause_cursor]
        if selected == "credits" and (inp.jump_pressed or inp.action_pressed):
            self.start_credits()
            return
        if delta and selected == "fidelity":
            self.set_presentation(fidelity=cycle_fidelity(self.fidelity, delta))
            self.note("ui")
            return
        if delta and selected == "display":
            if not self.accessibility.reduced_motion or delta < 0:
                self.set_presentation(display=cycle_display(self.display, delta))
            self.note("ui")
            return
        if delta and selected in {"scanlines", "curvature", "phosphor"}:
            self._adjust_crt_control(selected, delta)
            self.note("ui")
            return
        if delta and selected == "items" and self.available_items:
            owned = self.available_items
            try:
                pos = owned.index(self.current_item)
            except ValueError:
                pos = 0
            choice = owned[(pos + delta) % len(owned)]
            self.selected_item = self.inventory.index(choice)
            self.note("ui")
            return
        if inp.jump_pressed:
            if selected == "items":
                self.item_menu_cursor = ITEMS.index(self.current_item) if self.current_item in ITEMS else 0
                self.item_menu_row = 0
                self.scene = "items"
            elif selected == "audio":
                self.audio_cursor = 0
                self.scene = "audio-settings"
            elif selected == "controls":
                self.remap_device = "keyboard"
                self.remap_slot = 0
                self.remap_cursor = 0
                self.remap_waiting = False
                self.remap_feedback = "Choose an action, then bind it."
                self.scene = "remap"
            elif selected == "reroll":
                self.reroll_confirm_yes = False
                self.scene = "reroll-confirm"
            elif selected == "omega-code":
                self.export_omega_code()
            else:
                self.scene = self.paused_from or "action"
            return
        if inp.action_pressed:
            if selected == "items":
                self.item_menu_cursor = ITEMS.index(self.current_item) if self.current_item in ITEMS else 0
                self.item_menu_row = 0
                self.scene = "items"
            elif selected == "audio":
                self.audio_cursor = 0
                self.scene = "audio-settings"
            elif selected == "omega-code":
                self.export_omega_code()
            else:
                self.save_to_disk()
            return
        if inp.turn_pressed:
            self.load_from_disk()
            return
        if inp.item:
            self.item_menu_cursor = ITEMS.index(self.current_item) if self.current_item in ITEMS else 0
            self.item_menu_row = 0
            self.scene = "items"
            return
        if inp.customize:
            self.scene = "customize"
            return
        if inp.interact:
            self.audio_muted = not self.audio_muted
            self._sync_audio()
            self.messages.append("Audio muted." if self.audio_muted else "Audio on.")

    def _step_audio_settings(self, inp: InputState) -> None:
        rows = self.audio_settings_rows
        self.audio_cursor %= len(rows)
        if inp.up_pressed:
            self.audio_cursor = (self.audio_cursor - 1) % len(rows)
            self.note("ui")
            return
        if inp.down_pressed:
            self.audio_cursor = (self.audio_cursor + 1) % len(rows)
            self.note("ui")
            return
        selected = rows[self.audio_cursor]
        delta = -1 if inp.left_pressed else (1 if inp.right_pressed else 0)
        audio = dict(self.settings.get("audio") or {})
        if delta and selected == "quality":
            self.set_audio_fidelity(cycle_audio_fidelity(self.audio_fidelity, delta))
            self.note("ui")
            return
        volume_keys = {
            "master": "masterVolume",
            "music": "musicVolume",
            "effects": "effectsVolume",
            "ui": "uiVolume",
        }
        if delta and selected in volume_keys:
            key = volume_keys[selected]
            audio[key] = round(max(0.0, min(1.0, float(audio.get(key, 0.8)) + delta * 0.05)), 2)
            self.settings["audio"] = audio
            self._sync_audio()
            self.note("ui")
            return
        if delta and selected in {"mute", "captions"}:
            if selected == "mute":
                self.audio_muted = not self.audio_muted
            else:
                self.audio_captions = not self.audio_captions
            self._sync_audio()
            self.note("ui")
            return
        if inp.jump_pressed or inp.action_pressed:
            if selected == "back":
                self.scene = "pause"
            elif selected == "mute":
                self.audio_muted = not self.audio_muted
                self._sync_audio()
            elif selected == "captions":
                self.audio_captions = not self.audio_captions
                self._sync_audio()
            self.note("ui")
            return
        if inp.interact or inp.customize:
            self.scene = "pause"
            self.note("ui")

    def _step_remap(self, inp: InputState) -> None:
        if self.remap_waiting:
            if inp.left_pressed:
                self.remap_waiting = False
                self.remap_feedback = "Capture cancelled."
                self.note("ui")
            return
        actions = self.remap_actions
        self.remap_cursor %= len(actions)
        if inp.up_pressed:
            self.remap_cursor = (self.remap_cursor - 1) % len(actions)
            self.note("ui")
            return
        if inp.down_pressed:
            self.remap_cursor = (self.remap_cursor + 1) % len(actions)
            self.note("ui")
            return
        if inp.turn_pressed:
            self.remap_device = "gamepad" if self.remap_device == "keyboard" else "keyboard"
            self.remap_slot = 0
            self.remap_cursor = min(self.remap_cursor, len(self.remap_actions) - 1)
            self.remap_feedback = f"Editing {self.remap_device} bindings."
            self.note("ui")
            return
        if self.remap_device == "keyboard" and (inp.left_pressed or inp.right_pressed):
            self.remap_slot = 1 - self.remap_slot
            slot = "alternate" if self.remap_slot else "primary"
            self.remap_feedback = f"Editing {slot} keyboard bindings."
            self.note("ui")
            return
        if inp.jump_pressed:
            self.remap_waiting = True
            target = ACTION_LABELS[self.remap_action]
            kind = "key" if self.remap_device == "keyboard" else "gamepad button"
            self.remap_feedback = f"Press a {kind} for {target}."
            self.note("ui")
            return
        if inp.action_pressed:
            self.accessibility.reset_binding(
                self.remap_action,
                device=self.remap_device,
                slot=self.remap_slot,
            )
            self._sync_accessibility()
            self.remap_feedback = f"Reset {ACTION_LABELS[self.remap_action]}."
            self.note("ui")
            return
        if inp.item:
            self.accessibility.reset_controls(self.remap_device)
            self._sync_accessibility()
            self.remap_feedback = f"Reset all {self.remap_device} bindings."
            self.note("ui")
            return
        if inp.interact or inp.customize:
            self.remap_waiting = False
            self.scene = "pause"
            self.note("ui")

    def reroll_seed_preview(self) -> str:
        if self.world is None:
            return "unavailable"
        root = self.reroll_root_seed or self.world.identity.seed
        return f"{root}-reroll-{self.rerolls + 1}"

    def _step_reroll_confirm(self, inp: InputState) -> None:
        if inp.left_pressed or inp.right_pressed or inp.up_pressed or inp.down_pressed:
            self.reroll_confirm_yes = not self.reroll_confirm_yes
            self.note("ui")
            return
        if inp.interact or inp.pause:
            self.reroll_confirm_yes = False
            self.scene = "pause"
            self.messages.append("Reroll cancelled. Current world unchanged.")
            self.note("ui")
            return
        if not inp.jump_pressed:
            return
        if not self.reroll_confirm_yes:
            self.scene = "pause"
            self.messages.append("Reroll declined. Current world unchanged.")
            self.note("ui")
            return
        self._reroll_world()

    def _reroll_world(self) -> None:
        if self.world is None:
            self.scene = "pause"
            return
        old_world = self.world
        previous = {
            **self.progress_record(),
            "accessibility": self.accessibility.to_record(),
            "bossState": [value for value in self.converted if value in BOSSES],
            "chapters": old_world.chapters,
            "character": old_world.character,
            "convertedCapabilities": list(self.converted),
            "identity": old_world.identity.to_record(),
            "localCustomizations": self.settings.get("localCustomizations") or [],
            "omegaHistory": self.settings.get("omegaHistory") or [],
            "playSeconds": self.tick // 60,
            "receipt": old_world.receipt,
            "rerollRootSeed": self.reroll_root_seed or old_world.identity.seed,
            "rerolls": self.rerolls,
            "settings": dict(self.settings),
            "zoneDeltas": [],
        }
        retain, _ = reroll_progress(previous)
        next_rerolls = int(retain["rerolls"])
        root_seed = str(retain.get("rerollRootSeed") or old_world.identity.seed)
        next_seed = f"{root_seed}-reroll-{next_rerolls}"
        settings = dict(retain.get("settings") or self.settings)
        settings["seed"] = next_seed
        try:
            new_world = generate_world(
                next_seed,
                difficulty=old_world.identity.difficulty,
                accessibility_profile=old_world.identity.accessibility_profile,
                character=dict(retain.get("character") or old_world.character),
                settings=settings,
                force_logo=self.installer.force_logo,
                content=load_content(self.installer.content_paths),
                chapter_ids=("corrupted-install",) if self.web_chapter_one else None,
            )
            next_settings = apply_presentation(settings, quality=str(settings.get("quality") or self.fidelity))
            next_quality = str(next_settings.get("quality") or self.fidelity)
            next_fidelity, next_display = migrate_quality(next_quality, next_settings)
            next_capabilities = [
                value for value in retain.get("convertedCapabilities") or [] if value not in BOSSES
            ]
            base = self.save_path.parent if self.save_path is not None else user_data_dir()
            archive_dir = base / "archives"
            archive_stem = f"reroll-{next_rerolls:02d}-{old_world.identity.digest()[7:19]}"
            archive_path = archive_dir / f"{archive_stem}.json"
            copy_index = 1
            while archive_path.exists():
                archive_path = archive_dir / f"{archive_stem}-{copy_index}.json"
                copy_index += 1
            archive_progress = dict(self.progress_record())
            archive_progress["archivedByReroll"] = next_rerolls
            archive_progress["nextSeed"] = next_seed
            write_save(archive_path, make_save(old_world.to_record(), archive_progress))
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.reroll_confirm_yes = False
            self.scene = "reroll-confirm"
            self.messages.append(f"Reroll failed closed: {exc}")
            return

        self.last_archive_path = archive_path
        self.rerolls = next_rerolls
        self.reroll_root_seed = root_seed
        self.installer.choices.seed = next_seed
        self.installer.world = new_world
        self.world = new_world
        self.settings = next_settings
        self.quality = next_quality
        self.fidelity, self.display = next_fidelity, next_display
        self._restore_audio()
        self.converted = next_capabilities
        self.inventory = list(STARTING_INVENTORY)
        self.item_strength = STARTING_ITEM_STRENGTH
        self.selected_item = 0
        self.selected_attack = ATTACKS[0]
        self.score = 0
        self.player_bs = 0
        self.combo = 0
        self.combo_ticks = 0
        self.combo_events = {}
        self.combo_name = ""
        self.omega_letters = ""
        self.omega_door_spawned = False
        self.omega_door_map = -1
        self.secret_map_index = -1
        self.penguins = 0
        self.ghosts = []
        self.particles = []
        self.floaters = []
        self.oligarchy = False
        self.hud_wordmark = "OMARCHY"
        self.ending = False
        self.credits = False
        self.goliath_stage = "penguin"
        self.goliath_minions_defeated = 0
        self.pending_chapter = None
        self.reroll_confirm_yes = False
        self.recovery_reason = ""
        self.messages = []
        self._load_chapter(0)
        self.scene = "action"
        self.messages.append(f"World rerolled as {next_seed}. Previous world archived.")
        self.note("ui")

    def _step_recovery(self, inp: InputState) -> None:
        if inp.jump_pressed or inp.interact:
            self._retry_checkpoint()

    def _retry_checkpoint(self) -> None:
        if not self.tiles:
            return
        self._reset_boss_gate_for_checkpoint()
        self._activate_map(self.map_index, reset_body=True)
        self.combat = None
        self.projectiles = []
        self.enemy_projectiles = []
        self.attack_timer = 0
        self.action_reset_ticks = 0
        for entity in self.entities:
            entity.extra["in_combat"] = False
        self.score = max(0, self.score - 100)
        self.player_bs = 0
        self.recovery_reason = ""
        self.scene = "action"
        self.messages.append("Checkpoint restored. No one was deleted. Score -100.")
        self.note("ui")

    def _step_items(self, inp: InputState) -> None:
        choices = ITEMS if self.item_menu_row == 0 else ATTACKS
        if inp.up_pressed or inp.down_pressed:
            self.item_menu_row = 1 - self.item_menu_row
            choices = ITEMS if self.item_menu_row == 0 else ATTACKS
            if self.item_menu_row == 0:
                self.item_menu_cursor = ITEMS.index(self.current_item) if self.current_item in ITEMS else 0
            else:
                self.item_menu_cursor = ATTACKS.index(self.current_attack)
            self.note("ui")
            return
        delta = -1 if inp.left_pressed else (1 if inp.right_pressed else 0)
        if delta:
            self.item_menu_cursor = (self.item_menu_cursor + delta) % len(choices)
            self.note("ui")
            return
        if inp.jump_pressed or inp.action_pressed:
            selected = choices[self.item_menu_cursor % len(choices)]
            if self.item_menu_row == 0:
                if selected not in self.inventory:
                    self.messages.append("That tool has not been recovered yet.")
                    self.note("ui")
                    return
                self.selected_item = self.inventory.index(selected)
                self.messages.append(
                    f"{self.prompt_binding('item')} slot: {selected.replace('-', ' ')}"
                )
            else:
                self.selected_attack = selected
                self.messages.append(
                    f"{self.prompt_binding('action')} slot: {selected.replace('-', ' ')}"
                )
            self.note("ui")
            return
        if inp.item or inp.interact:
            self.scene = "pause"
            self.note("ui")

    def _step_customize(self, inp: InputState) -> None:
        if inp.interact or inp.pause:
            self.scene = self.paused_from or "action"
            return
        if inp.jump_pressed:
            self.run_limitless()
            return
        if not self.limitless_status:
            enabled = bool(self.settings.get("limitlessEnabled"))
            self.limitless_status = (
                f"Limitless on. {self.prompt_binding('jump')} runs query-before-work."
                if enabled
                else (
                    f"Limitless off. {self.prompt_binding('jump')} still records "
                    "a start-fresh receipt."
                )
            )

    def save_to_disk(self) -> None:
        if self.world is None:
            return
        path = self.save_path or (user_data_dir() / "save.json")
        write_save(path, self.save_record())
        self.save_path = path
        self.messages.append(f"Saved locally ({path.name}).")
        self.note("ui")

    def load_from_disk(self) -> None:
        path = self.save_path or (user_data_dir() / "save.json")
        try:
            record = read_save(path)
        except SaveError as exc:
            self.messages.append(f"Load failed: {exc}")
            return
        from .generation import SealedWorld
        from .identity import WorldIdentity

        world_rec = record["world"]
        identity = WorldIdentity.from_record(world_rec["identity"])
        try:
            require_exact_content(identity, load_content(self.installer.content_paths))
        except (ContentCompatibilityError, ValueError) as exc:
            self.messages.append(f"Load failed: {exc}")
            return
        self.world = SealedWorld(
            identity=identity,
            chapters=world_rec["chapters"],
            receipt=world_rec.get("receipt") or {},
            character=world_rec.get("character") or {},
            settings=world_rec.get("settings") or {},
        )
        progress = record.get("progress") or {}
        self.penguins = int(progress.get("penguins") or 0)
        self.converted = list(progress.get("converted") or [])
        self.inventory = list(progress.get("inventory") or self.inventory)
        self.item_strength = max(
            0,
            min(MAX_ITEM_STRENGTH, int(progress.get("itemStrength", STARTING_ITEM_STRENGTH))),
        )
        self.selected_item = int(progress.get("selectedItem") or 0)
        attack = str(progress.get("selectedAttack") or self.selected_attack)
        self.selected_attack = attack if attack in ATTACKS else ATTACKS[0]
        self.score = int(progress.get("score") or 0)
        self.player_bs = max(0, min(MAX_BS, int(progress.get("playerBS") or 0)))
        restored_letters = str(progress.get("omegaLetters") or "")
        self.omega_letters = "".join(letter for letter in OMEGA_LETTERS if letter in restored_letters)
        self.rerolls = int(progress.get("rerolls") or 0)
        self.reroll_root_seed = str(progress.get("rerollRootSeed") or "")
        self.quality = str(progress.get("quality") or self.quality)
        restored_settings = dict(progress.get("settings") or self.world.settings)
        self.settings = apply_presentation(restored_settings, quality=self.quality)
        self.fidelity, self.display = migrate_quality(self.quality, self.settings)
        self._restore_audio()
        self._restore_accessibility()
        self.oligarchy = bool(progress.get("oligarchy"))
        self.hud_wordmark = "OLIGARCHY" if self.oligarchy else "OMARCHY"
        restored_goliath_stage = str(progress.get("goliathStage") or "penguin")
        self.goliath_stage = restored_goliath_stage if restored_goliath_stage in GOLIATH_STAGES else "penguin"
        self.goliath_minions_defeated = max(
            0,
            min(GOLIATH_MINION_COUNT, int(progress.get("goliathMinionsDefeated") or 0)),
        )
        idx = int(progress.get("chapterIndex") or 0)
        self._load_chapter(idx)
        secret = progress.get("workshopSecret")
        if isinstance(secret, dict):
            secret_index = self._ensure_secret_level()
            rows = secret.get("tiles")
            upper = secret.get("upperTraversal")
            if (isinstance(rows, list) and len(rows) == COW_LEVEL_HEIGHT
                    and all(isinstance(row, str) and len(row) == COW_LEVEL_WIDTH for row in rows)
                    and isinstance(upper, dict)):
                self.chapter_map_tiles[secret_index] = list(rows)
                self.chapter_map_originals[secret_index] = list(rows)
                self.chapter_map_upper[secret_index] = dict(upper)
                self.secret_return_map = int(secret.get("returnMap") or 0)
                self.secret_return_position = tuple(secret.get("returnPosition") or self.secret_return_position)
                for lift in upper.get("lifts", []):
                    self.chapter_map_entities[secret_index].extend(self._skyway_lift_pair(lift))
        restored_map = int(progress.get("mapIndex") or 0)
        if restored_map and restored_map < len(self.chapter_map_tiles):
            self._activate_map(restored_map, reset_body=True)
        for cache in progress.get("workshopCaches") or ():
            if not isinstance(cache, dict):
                continue
            map_index, x, y = cache.get("map"), cache.get("x"), cache.get("y")
            if not all(isinstance(value, int) for value in (map_index, x, y)):
                continue
            if not 0 <= map_index < len(self.chapter_map_tiles):
                continue
            rows = self.chapter_map_tiles[map_index]
            if not (0 <= y < len(rows) and 0 <= x < len(rows[0])) or cache.get("item") not in COMMON_ITEMS:
                continue
            self.chapter_map_entities[map_index].append(Entity("item", x, y, extra={
                "item": cache["item"], "edit_reward": True, "edit_route_bonus": True,
            }))
        restored_scene = str(progress.get("scene") or "action")
        defeat = progress.get("bossDefeat")
        if (isinstance(defeat, dict) and defeat.get("bossId") == CAMPAIGN_ROSTER[idx].boss.id
                and defeat.get("nextPhase") in {"advance", "duel", "minions"}
                and restored_scene in {"boss-defeat", "pause"}):
            boss = next((entity for entity in self.entities if entity.kind == "boss"), None)
            self._begin_boss_defeat(boss, defeat["bossId"], next_phase=defeat["nextPhase"])
        elif (
            idx < len(CAMPAIGN_ROSTER) - 1
            and restored_scene in {"chapter-complete", "chapter-credits"}
            and CAMPAIGN_ROSTER[idx].boss.id in self.converted
        ):
            pending = progress.get("pendingChapter")
            self.pending_chapter = int(pending) if pending is not None else idx + 1
            self.post_boss = True
            self.scene = restored_scene
            if restored_scene == "chapter-credits":
                self.start_credits(return_scene="chapter-complete")
        elif restored_scene == "stage-map" and progress.get("pendingChapter") is not None:
            self.post_boss = True
            self._open_stage_map(int(progress["pendingChapter"]), transition=False)
        else:
            self.pending_chapter = None
            self.post_boss = False
            self.scene = "action"
        self.messages.append("Save restored.")
        self.note("ui")

    def export_omega_code(self) -> None:
        if self.world is None:
            return
        payload = seed_payload(self.world.identity.seed, self.world.identity.to_record())
        self.omega_text = encode_text(payload)
        dest = user_data_dir() / "last.omega.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.omega_text, encoding="utf-8")
        self.messages.append("Omega Code exported (seed + identity).")
        self.note("ui")

    def import_omega_code(self, text: str) -> None:
        payload = decode_text(text)
        if payload["kind"] != "seed":
            raise OmegaCodeError("this slice imports seed codes")
        seed = payload["body"]["seed"]
        self.installer.set_choice(seed=seed)
        self.confirm_play_now()
        self.messages.append(f"Imported seed {seed}.")

    def run_limitless(self) -> None:
        enabled = bool(self.settings.get("limitlessEnabled"))
        digest = self.identity_digest or "sha256:" + "0" * 64
        if not enabled:
            self.limitless_status = "Limitless disabled. Starting fresh locally. Nothing was published."
            self.limitless_receipt = {
                "treatment": "offline-fresh",
                "adopted": False,
                "delivered": False,
                "reason": "limitless-disabled-start-fresh",
            }
            contribute({"id": "local-customize"}, str(self.settings.get("sharePolicy") or "local-only"))
            self.messages.append(self.limitless_status)
            return
        request = build_request("omega-precision-assist")
        catalog = Path(__file__).resolve().parents[2] / "integrations" / "limitless" / "catalog"
        try:
            decision = query_before_work(request, catalog)
        except LimitlessDecisionError as exc:
            self.limitless_status = f"Query failed closed: {exc}. Starting fresh."
            self.limitless_receipt = {"treatment": "abstain", "reason": str(exc), "adopted": False}
            self.messages.append(self.limitless_status)
            return
        settings, receipt = adopt_decision(
            decision,
            catalog=catalog,
            settings=self.settings,
            world_digest=digest,
            enabled=True,
        )
        self.settings = settings
        if settings.get("precisionAssist"):
            self.accessibility.precision_assist = True
        rec = receipt.to_record()
        self.limitless_receipt = rec
        self.limitless_status = (
            f"{rec['treatment']} adopted={rec['adopted']} delivered={rec['delivered']} ({rec['reason']})"
        )
        self.messages.append("Limitless: " + self.limitless_status)
        self.note("ui")

    def progress_record(self) -> dict[str, Any]:
        return {
            "chapterIndex": self.chapter_index,
            "converted": list(self.converted),
            "convertedCapabilities": list(self.converted),
            "currentChapter": CAMPAIGN_ROSTER[self.chapter_index].id,
            "oligarchy": self.oligarchy,
            "pendingChapter": self.pending_chapter,
            "penguins": self.penguins,
            "postBoss": self.post_boss,
            "inventory": list(self.inventory),
            "itemStrength": self.item_strength,
            "mapIndex": self.map_index,
            "workshopSecret": ({"tiles": self.chapter_map_tiles[self.secret_map_index], "upperTraversal": self.chapter_map_upper[self.secret_map_index],
                                 "returnMap": self.secret_return_map, "returnPosition": list(self.secret_return_position)}
                               if 0 <= self.secret_map_index < len(self.chapter_map_upper) else None),
            "selectedItem": self.selected_item,
            "selectedAttack": self.current_attack,
            "score": self.score,
            "workshopCaches": [
                {"map": map_index, "x": int(entity.x), "y": int(entity.y), "item": entity.extra["item"]}
                for map_index, entities in enumerate(self.chapter_map_entities)
                for entity in entities
                if entity.alive and entity.extra.get("edit_route_bonus")
            ],
            "playerBS": self.player_bs,
            "goliathStage": self.goliath_stage,
            "goliathMinionsDefeated": self.goliath_minions_defeated,
            "bossDefeat": ({key: self.boss_defeat[key] for key in ("bossId", "nextPhase")}
                           if self.boss_defeat else None),
            "omegaLetters": self.omega_letters,
            "quality": self.quality,
            "rerollRootSeed": self.reroll_root_seed,
            "rerolls": self.rerolls,
            "scene": self.scene,
            "settings": self.settings,
            "sharePolicy": self.settings.get("sharePolicy", "local-only"),
        }

    def save_record(self) -> dict[str, Any]:
        assert self.world is not None
        return make_save(self.world.to_record(), self.progress_record())
