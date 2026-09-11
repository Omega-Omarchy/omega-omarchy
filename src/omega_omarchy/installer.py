"""Installer parody: real deterministic world prep, completion action Play Now."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from . import INSTALLER_COMPLETION_ACTION
from .character import DAVID, FALLBACK_CHARACTER_NAME, Character, parse_character
from .character_pack import character_preload_steps
from .content import load_content
from .generation import SealedWorld, generate_world_steps
from .audio import AUDIO_FIDELITIES, DEFAULT_AUDIO, cycle_audio_fidelity, normalize_audio_settings
from .presentation import DISPLAYS, FIDELITIES, apply_presentation, cycle_display, cycle_fidelity

# Pinned Omarchy installer mapping (VM-observed 2026-08-28 on omarchy-4.0.1
# plus source checkouts omarchy 83881e97 / omarchy-iso 268bac16).

OMARCHY_BEATS = (
    "greeter: logo + tagline + Press Return to Start Install",
    "keyboard layout",
    "username",
    "password + confirm",
    "full name (skippable)",
    "email (skippable)",
    "hostname (default omarchy)",
    "timezone",
    "confirm table: Does this look right?",
    "select install disk",
    "installation mode / encryption confirm / overwrite confirm",
    "progress: Starting installation",
    "progress: Preparing live environment",
    "progress: Preparing install target",
    "progress: Installing Arch + Omarchy",
    "progress: Configuring hibernation",
    "progress: Configuring system",
    "progress: Staging provisioning",
    "progress: Finalizing Limine boot",
    "progress: Finalizing user",
    "progress: Configuring login",
    "progress: Configuring DNS resolver",
    "progress: Validating boot setup",
    "progress: Creating factory snapshot",
    "finish logo laseretch + gum confirm affirmative Reboot Now",
)

PARODY_STEPS = (
    "greeter",
    "input",
    "character",
    "seed",
    "difficulty",
    "accessibility",
    "quality",
    "sound",
    "display",
    "limitless",
    "sharing",
    "confirm",
    "progress",
    "complete",
)

# VM-observed 2026-08-28 on omarchy-4.0.1 greeter (software-emulated).
GREETER_TAGLINE = "The Revolution Will Be Customized"
GREETER_HINT = "Press Return to Start Install"
SETUP_MACHINE = "Let's setup your machine..."
SETUP_ACCOUNT = "Let's setup your user account..."
SETUP_OWNER_HINT = "Ctrl+C prepares it for another owner."
CONFIRM_PROMPT = "Does this look right?"
PROGRESS_TITLE = "Installing Omega Omarchy"
NAV_HINT = "up/down  •  enter submit"
# User-visible dashboard on 4.0.1 is a dotted bar + rotating tips, not the
# internal phase names. Those names still exist in omarchy-install-dashboard.
PROGRESS_TIPS = (
    "Super + Space is a habit, not a landlord.",
    "Conversion, not deletion.",
    "Customizations stay local until you say otherwise.",
    "The revolution will be customized.",
)

PROGRESS_PHASES = (
    ("Starting installation", "Resolving contradictory dependencies"),
    ("Preparing live environment", "Mounting imagination"),
    ("Preparing install target", "Partitioning dogma"),
    ("Installing Arch + Omarchy", "Installing good defaults"),
    ("Configuring hibernation", "Detecting forbidden fruit"),
    ("Configuring system", "Deploying optimism"),
    ("Staging provisioning", "Negotiating with the bootloader"),
    ("Finalizing Limine boot", "Sealing world identity"),
    ("Finalizing user", "Placing penguins"),
    ("Configuring login", "Calibrating BS meter"),
    ("Configuring DNS resolver", "Pointing at local names"),
    ("Validating boot setup", "Proving the boss is reachable"),
    ("Creating factory snapshot", "Writing generation receipt"),
)
PROGRESS_BASE_TICKS = 48
# The authored progress phases are deliberately followed by a three-second
# hold so the completion beat lands after the measured generation work.
INSTALL_BREATH_TICKS = 180
INSTALL_TICK_HZ = 60

QUALITY_PRESETS = ("eight-bit", "sixteen-bit", "clean-pixel", "crt", "high", "ultra")
SHARE_POLICIES = ("local-only", "manual-public", "agent-under-saved-policy")
INPUT_MODES = ("keyboard", "gamepad", "auto")
DIFFICULTIES = ("casual", "standard", "precise")
A11Y_PROFILES = ("default", "precision-assist", "reduced-motion")
SEED_PRESETS = ("omega-fixture-1", "omega-daily", "custom-42")
CHAR_KINDS = ("david", "omarch-king", "omarch-queen", "custom")


def _cycle(options: tuple[str, ...], current: str, delta: int) -> str:
    if current not in options:
        current = options[0]
    return options[(options.index(current) + delta) % len(options)]


@dataclass
class InstallerChoices:
    input_mode: str = "auto"  # keyboard | gamepad | auto
    character: Character = DAVID
    seed: str = "omega-fixture-1"
    difficulty: str = "standard"
    accessibility_profile: str = "default"
    quality: str = "ultra"
    fidelity: str = "ultra"
    audio_fidelity: str = "ultra"
    display: str = "clean"
    limitless_enabled: bool = False
    share_policy: str = "local-only"
    reduced_motion: bool = False
    precision_assist: bool = False
    crt: dict[str, float] = field(default_factory=lambda: {
        "intensity": 0.12,
        "scanline": 0.12,
        "curvatureControl": 0.12,
        "phosphor": 0.12,
        "scanlines": 0.2144,
        "scanlineSize": 0.12,
        "curvature": 0.12,
        "chromatic": 0.0,
        "bloom": 0.1456,
        "noise": 0.0,
        "vignette": 0.0744,
        "persistence": 0.032,
        "mask": 0.1304,
        "enabled": 0.0,
    })

    def to_record(self) -> dict[str, Any]:
        return {
            "accessibilityProfile": self.accessibility_profile,
            "character": self.character.to_record(),
            "crt": self.crt,
            "difficulty": self.difficulty,
            "inputMode": self.input_mode,
            "limitlessEnabled": self.limitless_enabled,
            "precisionAssist": self.precision_assist,
            "quality": self.quality,
            "fidelity": self.fidelity,
            "audioFidelity": self.audio_fidelity,
            "audio": dict(DEFAULT_AUDIO),
            "display": self.display,
            "reducedMotion": self.reduced_motion,
            "seed": self.seed,
            "sharePolicy": self.share_policy,
        }


@dataclass
class InstallerSession:
    step_index: int = 0
    choices: InstallerChoices = field(default_factory=InstallerChoices)
    generating: bool = False
    world: SealedWorld | None = None
    phase_index: int = 0
    skipped: bool = False
    force_logo: bool = True  # deterministic qualification; still optional for completion
    confirm_accept: bool = True
    play_now_armed: bool = False
    complete_ticks: int = 0
    progress_ticks: int = 0
    elapsed_s: float = 0.0
    awaiting_release: bool = False
    name_entry_started: bool = False
    content_paths: tuple[Path, ...] = ()
    character_roster: list[Character] | None = None
    character_agent_selected: bool = False
    character_help_open: bool = False
    character_notice: str = ""
    character_roots: dict[tuple[str, str], Path] = field(default_factory=dict)
    characters_ready: bool = False
    _character_work: Any = field(default=None, repr=False)
    _generation_work: Any = field(default=None, repr=False)
    progress_fraction: float = 0.0
    progress_label: str = "Preparing installation"
    completion_progress_ticks: int = 0
    _started_at: float | None = field(default=None, repr=False)
    _finished_at: float | None = field(default=None, repr=False)
    realtime: bool = False
    web_chapter_one: bool = False

    def preload_characters(self, *, files: int = 4) -> None:
        if self.characters_ready:
            return
        if self._character_work is None:
            self.character_roster = [DAVID]
            self._character_work = character_preload_steps()
        for _ in range(files):
            try:
                result = next(self._character_work)
            except StopIteration:
                self.characters_ready = True
                self._character_work = None
                break
            if isinstance(result, str):
                self.character_notice = "An incomplete character pack was skipped."
            elif result is not None:
                character, root = result
                self.character_roster.append(character)
                self.character_roots[(character.asset_pack, character.asset_digest)] = root

    def refresh_characters(self) -> list[Character]:
        self.characters_ready = False
        self._character_work = None
        self.character_roots.clear()
        while not self.characters_ready:
            self.preload_characters()
        return self.character_roster

    @property
    def character_options(self) -> list[Character]:
        return self.character_roster if self.character_roster is not None else self.refresh_characters()

    @property
    def character_index(self) -> int:
        if self.character_agent_selected:
            return len(self.character_options)
        current = self.choices.character
        return next((i for i, char in enumerate(self.character_options)
                     if (char.kind, char.asset_pack, char.asset_digest) == (current.kind, current.asset_pack, current.asset_digest)), 0)

    @property
    def step(self) -> str:
        return PARODY_STEPS[min(self.step_index, len(PARODY_STEPS) - 1)]

    @property
    def complete(self) -> bool:
        return self.step == "complete" and self.world is not None

    @property
    def completion_action(self) -> str:
        return INSTALLER_COMPLETION_ACTION

    @property
    def installed_line(self) -> str:
        return f"Installed Omega Omarchy in {self.total_elapsed_s:.2f}s"

    @property
    def total_elapsed_s(self) -> float:
        """Use the live clock in-app and the simulated 60 Hz clock headlessly."""
        if self.realtime and self._started_at is not None:
            end = self._finished_at if self._finished_at is not None else time.perf_counter()
            return max(0.0, end - self._started_at)
        return self.elapsed_s + self.progress_ticks / INSTALL_TICK_HZ

    def copy_deck(self) -> dict[str, Any]:
        return {
            "completionAction": INSTALLER_COMPLETION_ACTION,
            "notRebootNow": True,
            "omarchyAffirmativeReplaced": "Reboot Now",
            "greeterHint": GREETER_HINT,
            "confirmPrompt": CONFIRM_PROMPT,
            "progressTitle": PROGRESS_TITLE,
            "progressTips": list(PROGRESS_TIPS),
            "phases": [{"omarchy": a, "parody": b} for a, b in PROGRESS_PHASES],
            "shareDefault": "local-only",
            "limitlessOptional": True,
            "publicSharingPreselected": False,
            "diskOverwriteOmitted": True,
        }

    def set_choice(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if key == "character":
                self.choices.character = value if isinstance(value, Character) else parse_character(value)
                self.name_entry_started = False
            elif key == "share_policy":
                if value not in SHARE_POLICIES:
                    raise ValueError("unknown share policy")
                self.choices.share_policy = value
            elif key == "quality":
                if value not in QUALITY_PRESETS:
                    raise ValueError("unknown quality")
                self.choices.quality = value
            elif key == "audio_fidelity":
                if value not in AUDIO_FIDELITIES:
                    raise ValueError("unknown audio fidelity")
                self.choices.audio_fidelity = value
            elif hasattr(self.choices, key):
                setattr(self.choices, key, value)
            else:
                raise ValueError(f"unknown installer choice {key}")

    def cycle(self, delta: int) -> None:
        """Left/right on the current installer page. Writes real choices."""

        step = self.step
        c = self.choices
        if step == "input":
            c.input_mode = _cycle(INPUT_MODES, c.input_mode, delta)
        elif step == "character":
            index = (self.character_index + delta) % (len(self.character_options) + 1)
            self.character_agent_selected = index == len(self.character_options)
            self.character_help_open = False
            self.name_entry_started = False
            if not self.character_agent_selected:
                self.choices.character = self.character_options[index]
        elif step == "seed":
            c.seed = _cycle(SEED_PRESETS, c.seed if c.seed in SEED_PRESETS else SEED_PRESETS[0], delta)
        elif step == "difficulty":
            c.difficulty = _cycle(DIFFICULTIES, c.difficulty, delta)
        elif step == "accessibility":
            profile = _cycle(A11Y_PROFILES, c.accessibility_profile, delta)
            c.accessibility_profile = profile
            c.precision_assist = profile == "precision-assist"
            c.reduced_motion = profile == "reduced-motion"
        elif step == "quality":
            c.fidelity = cycle_fidelity(c.fidelity, delta)
            c.quality = c.fidelity
        elif step == "sound":
            c.audio_fidelity = cycle_audio_fidelity(c.audio_fidelity, delta)
        elif step == "display":
            c.display = cycle_display(c.display, delta)
            if c.display == "crt":
                c.crt = {**c.crt, "enabled": 1.0}
            else:
                c.crt = {**c.crt, "enabled": 0.0}
        elif step == "limitless":
            c.limitless_enabled = not c.limitless_enabled
        elif step == "sharing":
            c.share_policy = _cycle(SHARE_POLICIES, c.share_policy, delta)
        elif step == "confirm":
            self.confirm_accept = not self.confirm_accept

    def edit_character_name(self, text: str = "", *, backspace: bool = False) -> bool:
        """Edit the focused character-name field without changing the model."""
        if self.character_agent_selected:
            return False
        current = self.choices.character.name
        if backspace:
            updated = current[:-1]
            self.name_entry_started = True
        else:
            accepted = "".join(
                char for char in str(text) if char.isprintable() and char not in "\r\n\t"
            )
            if not accepted:
                return False
            if not self.name_entry_started:
                current = ""
                self.name_entry_started = True
            updated = (current + accepted)[:24]
        self.choices.character = replace(self.choices.character, name=updated)
        return True

    def _finalize_character_name(self) -> None:
        name = " ".join(self.choices.character.name.split())[:24] or FALLBACK_CHARACTER_NAME
        self.choices.character = replace(self.choices.character, name=name)

    def choice_summary(self) -> str:
        page = self.gum_page()
        if not page:
            if self.step == "complete":
                return INSTALLER_COMPLETION_ACTION
            if self.step == "progress":
                return PROGRESS_TITLE
            if self.step == "greeter":
                return GREETER_HINT
            if self.step == "confirm":
                return CONFIRM_PROMPT
            return self.step
        selected = page["options"][page["index"]] if page["options"] else ""
        return f"{page['prompt']}  {selected}"

    def gum_page(self) -> dict[str, Any] | None:
        """Gum-style list page for the current setup step. None on non-list screens."""

        c = self.choices
        machine = self.step in {"input", "quality", "sound", "display", "limitless", "sharing"}
        header = SETUP_MACHINE if machine else SETUP_ACCOUNT
        pages = {
            "input": ("Select input", list(INPUT_MODES), INPUT_MODES.index(c.input_mode) if c.input_mode in INPUT_MODES else 0),
            "character": (
                "Choose your character",
                [("David" if char.kind == "david" else char.name) for char in self.character_options] + ["Create with your agent"] if self.step == "character" else [],
                self.character_index if self.step == "character" else 0,
            ),
            "seed": (
                "Select world seed",
                list(SEED_PRESETS),
                SEED_PRESETS.index(c.seed) if c.seed in SEED_PRESETS else 0,
            ),
            "difficulty": (
                "Select difficulty",
                list(DIFFICULTIES),
                DIFFICULTIES.index(c.difficulty) if c.difficulty in DIFFICULTIES else 1,
            ),
            "accessibility": (
                "Select accessibility",
                list(A11Y_PROFILES),
                A11Y_PROFILES.index(c.accessibility_profile) if c.accessibility_profile in A11Y_PROFILES else 0,
            ),
            "quality": (
                "Select video detail",
                list(FIDELITIES),
                FIDELITIES.index(c.fidelity) if c.fidelity in FIDELITIES else 0,
            ),
            "sound": (
                "Select audio quality",
                list(AUDIO_FIDELITIES),
                AUDIO_FIDELITIES.index(c.audio_fidelity) if c.audio_fidelity in AUDIO_FIDELITIES else 2,
            ),
            "display": (
                "Select display treatment",
                list(DISPLAYS),
                DISPLAYS.index(c.display) if c.display in DISPLAYS else 0,
            ),
            "limitless": (
                "Limitless Library (optional)",
                ["off", "on"],
                1 if c.limitless_enabled else 0,
            ),
            "sharing": (
                "Select sharing",
                list(SHARE_POLICIES),
                SHARE_POLICIES.index(c.share_policy) if c.share_policy in SHARE_POLICIES else 0,
            ),
        }
        if self.step not in pages:
            return None
        prompt, options, index = pages[self.step]
        labels = {
            "sixteen-bit": "16-bit · classic pixel art",
            "high": "High · detailed pixel art",
            "ultra": "Ultra · illustrated pixel art",
            "clean": "clean pixel",
            "crt": "CRT simulation",
            "off": "off — start fresh locally",
            "on": "on — query before work",
            "local-only": "local-only",
            "manual-public": "manual-public",
            "agent-under-saved-policy": "agent-under-saved-policy",
        }
        if self.step == "sound":
            labels.update({"sixteen-bit": "16-bit · chiptunes and retro effects",
                           "high": "High · retro-filtered music and effects",
                           "ultra": "Ultra · full-range music and effects"})
        shown = [labels.get(opt, opt) for opt in options]
        footnote = ""
        if self.step == "limitless":
            footnote = "Optional. Off starts fresh locally."
        elif self.step == "sharing":
            footnote = "Public sharing is not preselected."
        elif self.step == "input":
            footnote = "Keyboard is enough. Gamepad optional."
        elif self.step == "character":
            footnote = self.character_notice or ("Preparing character art..." if not self.characters_ready and self._character_work is not None else "Same abilities. Your character, your name.")
        elif self.step == "quality":
            footnote = "Ultra adds detail. Change fidelity later in Pause."
        elif self.step == "sound":
            footnote = "Music and sound effects. Change audio later in Pause."
        elif self.step == "display":
            footnote = "CRT is a display treatment. Reduced-motion wins."
        return {
            "header": header,
            "prompt": prompt,
            "options": shown,
            "index": index,
            "footnote": footnote,
            "ownerHint": SETUP_OWNER_HINT if machine else "",
            "nav": "up/down choose · type name · enter select" if self.step == "character" else NAV_HINT,
        }

    def confirm_rows(self) -> list[tuple[str, str]]:
        c = self.choices
        return [
            ("Character", c.character.name),
            ("Seed", c.seed),
            ("Difficulty", c.difficulty),
            ("Video", c.fidelity),
            ("Audio", c.audio_fidelity),
            ("Display", c.display),
            ("Limitless Library", "on" if c.limitless_enabled else "off"),
            ("Sharing", c.share_policy),
        ]

    def next_step(self) -> None:
        if self.step == "complete":
            return
        if self.step == "character":
            if self.character_agent_selected:
                self.character_help_open = True
                import sys
                if sys.platform != "emscripten":
                    from .runtime_assets import asset_dir
                    from .save import user_data_dir
                    import shutil

                    destination = user_data_dir() / "character-agent-kit.zip"
                    try:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(asset_dir() / "character-creation/agent-kit.zip", destination)
                        self.character_notice = f"Agent kit saved: {destination}"
                    except OSError:
                        self.character_notice = "Export a kit with: ./scripts/omega character-kit PATH"
                return
            self._finalize_character_name()
        if self.step == "confirm" and not self.confirm_accept:
            self.step_index = PARODY_STEPS.index("character")
            self.confirm_accept = True
            return
        if self.step == "progress":
            self.run_generation()
            self.enter_complete()
            return
        self.step_index = min(self.step_index + 1, len(PARODY_STEPS) - 1)
        if self.step == "progress":
            self.progress_ticks = 0
            self.completion_progress_ticks = 0
            self.world = None
            self._generation_work = None
            self.elapsed_s = 0.0
            self.progress_fraction = 0.0
            self.progress_label = "Preparing installation"
            self._started_at = time.perf_counter()
            self._finished_at = None

    def prev_step(self) -> None:
        if self.step_index > 0 and self.step not in {"progress", "complete"}:
            self.step_index -= 1

    def enter_complete(self) -> None:
        if self.world is None:
            self.run_generation()
        if self._finished_at is None:
            self._finished_at = time.perf_counter()
        self.step_index = PARODY_STEPS.index("complete")
        self.play_now_armed = False
        self.complete_ticks = 0
        self.awaiting_release = True

    def skip_progress(self) -> None:
        self.skipped = True
        self.enter_complete()

    def tick_progress(self) -> None:
        """Run one preparation unit after the progress screen has been shown."""

        self.progress_ticks += 1
        if self.world is None:
            self.advance_generation()
            return
        self.completion_progress_ticks += 1
        if self.completion_progress_ticks >= PROGRESS_BASE_TICKS + INSTALL_BREATH_TICKS:
            self.enter_complete()

    def advance_generation(self) -> None:
        self.generating = True
        started = time.perf_counter()
        if self._started_at is None:
            self._started_at = started
        try:
            if self._generation_work is None:
                self._generation_work = self._prepare_world()
            fraction, self.progress_label = next(self._generation_work)
            self.progress_fraction = max(self.progress_fraction, fraction)
            self.phase_index = min(len(PROGRESS_PHASES) - 1, int(self.progress_fraction * len(PROGRESS_PHASES)))
        except StopIteration as done:
            self.world = done.value
            self._generation_work = None
            self.generating = False
            self.progress_fraction = 1.0
            self.progress_label = "Installation complete"
            self.phase_index = len(PROGRESS_PHASES) - 1
        finally:
            self.elapsed_s += max(0.0, time.perf_counter() - started)

    def _prepare_world(self):
        yield 0.01, "Loading world content"
        accessibility = self.choices.accessibility_profile
        if self.choices.precision_assist and accessibility == "default":
            accessibility = "precision-assist"
        settings = {
            "quality": self.choices.quality,
            "fidelity": self.choices.fidelity,
            "audioFidelity": self.choices.audio_fidelity,
            "audio": dict(DEFAULT_AUDIO),
            "display": self.choices.display,
            "inputMode": self.choices.input_mode,
            "limitlessEnabled": self.choices.limitless_enabled,
            "sharePolicy": self.choices.share_policy,
            "reducedMotion": self.choices.reduced_motion,
            "precisionAssist": self.choices.precision_assist,
            "crt": self.choices.crt,
            "includeOptionalChunks": True,
            "accessibilityProfile": accessibility,
        }
        settings = apply_presentation(settings, quality=self.choices.quality)
        settings = normalize_audio_settings(settings, legacy_fidelity=self.choices.fidelity)
        return (yield from generate_world_steps(
            self.choices.seed,
            difficulty=self.choices.difficulty,
            accessibility_profile=accessibility,
            character=self.choices.character.to_record(),
            settings=settings,
            force_logo=self.force_logo,
            content=load_content(self.content_paths),
            chapter_ids=("corrupted-install",) if self.web_chapter_one else None,
        ))

    def run_generation(self) -> SealedWorld:
        if self.world is not None:
            self.world = None
            self._generation_work = None
            self.elapsed_s = 0.0
            self._started_at = time.perf_counter()
            self._finished_at = None
        while self.world is None:
            self.advance_generation()
        return self.world

    def play_now(self) -> SealedWorld:
        if self.world is None:
            self.run_generation()
        self.enter_complete()
        self.play_now_armed = True
        self.awaiting_release = False
        assert self.world is not None
        return self.world


def default_fixture_world() -> SealedWorld:
    session = InstallerSession()
    session.set_choice(seed="omega-fixture-1")
    return session.play_now()
