"""Conversion combat: opponents are persuaded, patched, or recruited — not killed."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from .campaign import BOSSES
from .canonical import sha256_json
from .character import DEFAULT_CHARACTER_NAME

MAX_BS = 100
TURN_ACTIONS = ("reason", "patch", "fork", "demonstrate", "reuse", "abstain", "recruit")
ACTION_ITEMS = (
    "logic-bomb",
    "patch-cable",
    "manifest",
    "penguin-flock",
    "fork-beacon",
    "checksum-key",
    "mirror-cache",
    "touch-grass-usb",
)
ACTION_ATTACKS = ("reason", "patch-strike", "fork-pulse")

ENEMY_ARCHETYPES: dict[str, tuple[str, str, int, int, int, int]] = {
    # name, capability, conviction, coherence, corruption, trust
    "dogma-sprite": ("Dogma Sprite", "echo", 58, 50, 58, 14),
    "bureaucrat-drone": ("Form Drone", "provenance-pass", 64, 58, 62, 12),
    "hydra-node": ("Dependency Node", "compat-shim", 70, 44, 68, 8),
    "banner-scout": ("Banner Scout", "faction-truce", 76, 52, 60, 10),
    "garden-sentry": ("Garden Sentry", "gate-key", 62, 72, 64, 6),
    "singularity-shard": ("Singularity Shard", "fork-future", 82, 66, 74, 4),
    "goliath-fragment": ("Goliath Fragment", "reclaim", 88, 60, 78, 2),
    "goliath-cyborg-penguin": ("Goliath's Cyborg Penguin", "firewall-shell", 86, 74, 82, 1),
    "warden": ("Checksum Warden", "gate-key", 74, 68, 72, 5),
    "cache-gremlin": ("Cache Gremlin", "echo", 56, 48, 54, 16),
    "packet-wasp": ("Packet Wasp", "compat-shim", 62, 58, 55, 14),
    "lint-launcher": ("Lint Launcher", "provenance-pass", 68, 66, 62, 10),
    "garden-glitch": ("Garden Glitch", "gate-key", 60, 70, 56, 12),
    "void-orbiter": ("Void Orbiter", "fork-future", 78, 64, 72, 6),
    "justice-signaler": ("Justice Signaler", "faction-truce", 74, 44, 68, 8),
    "detractabot": ("Detractabot", "reclaim", 72, 58, 70, 7),
    "consensus-crier": ("Consensus Crier", "reclaim", 66, 52, 64, 9),
}


@dataclass(frozen=True)
class Combatant:
    id: str
    name: str
    side: str  # player | foe
    bs: int
    conviction: int
    coherence: int
    corruption: int
    trust: int
    converted: bool = False
    capabilities: tuple[str, ...] = ()
    penguin_help: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "bs": self.bs,
            "capabilities": list(self.capabilities),
            "coherence": self.coherence,
            "converted": self.converted,
            "conviction": self.conviction,
            "corruption": self.corruption,
            "id": self.id,
            "name": self.name,
            "penguinHelp": self.penguin_help,
            "side": self.side,
            "trust": self.trust,
        }


@dataclass(frozen=True)
class CombatState:
    player: Combatant
    foe: Combatant
    mode: str  # action | turn
    log: tuple[str, ...] = ()
    converted_ids: tuple[str, ...] = ()
    boss_id: str | None = None
    evidence: tuple[str, ...] = ()
    round_index: int = 0
    last_action: str | None = None
    focus: int = 0
    foe_intent: str = "entrench"

    def to_record(self) -> dict[str, Any]:
        return {
            "bossId": self.boss_id,
            "convertedIds": list(self.converted_ids),
            "evidence": list(self.evidence),
            "foe": self.foe.to_record(),
            "lastAction": self.last_action,
            "log": list(self.log),
            "mode": self.mode,
            "player": self.player.to_record(),
            "roundIndex": self.round_index,
            "focus": self.focus,
            "foeIntent": self.foe_intent,
        }

    def digest(self) -> str:
        return sha256_json(self.to_record())

    @property
    def player_overloaded(self) -> bool:
        return self.player.bs >= MAX_BS

    @property
    def foe_ready_to_recruit(self) -> bool:
        return (
            not self.foe.converted
            and self.foe.corruption <= 20
            and self.foe.trust >= 60
            and self.foe.bs <= 25
        )


def _clamp(value: int, lo: int = 0, hi: int = MAX_BS) -> int:
    return max(lo, min(hi, value))


def _with(combatant: Combatant, **changes: Any) -> Combatant:
    data = combatant.to_record()
    mapping = {
        "penguinHelp": "penguin_help",
        "bs": "bs",
        "conviction": "conviction",
        "coherence": "coherence",
        "corruption": "corruption",
        "trust": "trust",
        "converted": "converted",
        "capabilities": "capabilities",
        "id": "id",
        "name": "name",
        "side": "side",
    }
    kwargs = {}
    for key, dest in mapping.items():
        if dest in changes:
            kwargs[dest] = changes[dest]
        elif key in data:
            value = data[key]
            kwargs[dest] = tuple(value) if dest == "capabilities" else value
    kwargs.update(changes)
    return Combatant(**kwargs)


def make_player(
    name: str = DEFAULT_CHARACTER_NAME,
    *,
    capabilities: Iterable[str] = (),
) -> Combatant:
    return Combatant(
        id="player",
        name=name,
        side="player",
        bs=12,
        conviction=55,
        coherence=60,
        corruption=8,
        trust=40,
        capabilities=tuple(capabilities),
    )


def make_foe(boss_id: str, *, as_boss: bool = False) -> Combatant:
    spec = BOSSES.get(boss_id)
    archetype = ENEMY_ARCHETYPES.get(boss_id)
    if archetype is not None and not as_boss:
        name, cap, conviction, coherence, corruption, trust = archetype
        return Combatant(
            id=boss_id,
            name=name,
            side="foe",
            bs=36,
            conviction=conviction,
            coherence=coherence,
            corruption=corruption,
            trust=trust,
            capabilities=(cap, "motif-fragment"),
        )
    if spec is None:
        name = boss_id.replace("-", " ").title()
        cap = "echo"
        fragment = "noise"
    else:
        name = spec.name
        cap = spec.capability
        fragment = spec.goliath_fragment
    scale = 1.25 if as_boss else 1.0
    return Combatant(
        id=boss_id,
        name=name,
        side="foe",
        bs=_clamp(int(40 * scale)),
        conviction=_clamp(int(70 * scale)),
        coherence=_clamp(int(55 * scale)),
        corruption=_clamp(int(65 * scale)),
        trust=10,
        capabilities=(cap, fragment),
    )


def start_encounter(player: Combatant, foe: Combatant, *, boss_id: str | None = None, mode: str = "action") -> CombatState:
    return CombatState(player=player, foe=foe, mode=mode, boss_id=boss_id, log=(f"{foe.name} refuses to update its beliefs.",))


def apply_action_item(state: CombatState, item: str, *, strength: float = 1.0) -> CombatState:
    """Immediate action-mode use. Logic Bombs reveal contradictions; they do not destroy."""

    if item not in ACTION_ITEMS:
        raise ValueError(f"unknown item {item}")
    foe = state.foe
    player = state.player
    note = item
    strength = max(0.5, min(1.5, float(strength)))

    def scaled(value: int) -> int:
        return max(1, round(value * strength))

    if item == "logic-bomb":
        foe = _with(foe, corruption=_clamp(foe.corruption - scaled(18)), bs=_clamp(foe.bs - scaled(14)), coherence=_clamp(foe.coherence - scaled(8)), trust=_clamp(foe.trust + scaled(6)))
        player = _with(player, bs=_clamp(player.bs - scaled(4)))
        note = "A contradiction lands. The argument stutters."
    elif item == "patch-cable":
        foe = _with(foe, corruption=_clamp(foe.corruption - scaled(10)), coherence=_clamp(foe.coherence + scaled(8)), trust=_clamp(foe.trust + scaled(8)))
        note = "A patched assumption holds."
    elif item == "manifest":
        foe = _with(foe, conviction=_clamp(foe.conviction - scaled(12)), trust=_clamp(foe.trust + scaled(10)))
        note = "You cite a working system."
    elif item == "penguin-flock":
        bonus = scaled(6 + 2 * player.penguin_help)
        foe = _with(foe, trust=_clamp(foe.trust + bonus), corruption=_clamp(foe.corruption - scaled(8)))
        note = "A flock of recovered penguins testifies."
    elif item == "fork-beacon":
        foe = _with(foe, conviction=_clamp(foe.conviction - scaled(16)), trust=_clamp(foe.trust + scaled(12)), bs=_clamp(foe.bs - scaled(5)))
        note = "The Fork Beacon proves another route is possible."
    elif item == "checksum-key":
        foe = _with(foe, corruption=_clamp(foe.corruption - scaled(12)), coherence=_clamp(foe.coherence + scaled(14)), bs=_clamp(foe.bs - scaled(8)))
        note = "A clean checksum opens the disputed gate."
    elif item == "mirror-cache":
        foe = _with(foe, conviction=_clamp(foe.conviction - scaled(8)), corruption=_clamp(foe.corruption - scaled(8)), trust=_clamp(foe.trust + scaled(16)))
        player = _with(player, bs=_clamp(player.bs - scaled(8)))
        note = "The Mirror Cache reflects a working precedent."
    elif item == "touch-grass-usb":
        player = _with(player, bs=0)
        note = "You touch grass through USB. Against all protocol, your BS meter clears."
    log = state.log + (note,)
    return replace(state, foe=foe, player=player, last_action=item, log=log)


def apply_action_attack(state: CombatState, attack: str) -> CombatState:
    """Fast side-view debate moves, paired with the X attack slot."""

    if attack not in ACTION_ATTACKS:
        raise ValueError(f"unknown attack {attack}")
    foe, player = state.foe, state.player
    if attack == "reason":
        foe = _with(foe, conviction=_clamp(foe.conviction - 9), corruption=_clamp(foe.corruption - 6), bs=_clamp(foe.bs - 6), trust=_clamp(foe.trust + 5))
        player = _with(player, bs=_clamp(player.bs - 4))
        note = "A concise argument breaks through the noise."
    elif attack == "patch-strike":
        foe = _with(foe, corruption=_clamp(foe.corruption - 12), coherence=_clamp(foe.coherence + 6), bs=_clamp(foe.bs - 4))
        note = "The faulty premise is patched in motion."
    else:
        foe = _with(foe, conviction=_clamp(foe.conviction - 7), corruption=_clamp(foe.corruption - 6), trust=_clamp(foe.trust + 9))
        player = _with(player, bs=_clamp(player.bs - 3))
        note = "A forked possibility opens beside the argument."
    return replace(state, foe=foe, player=player, last_action=attack, log=state.log + (note,))


def foe_action_pressure(state: CombatState) -> CombatState:
    """Action-mode pressure: dogma raises the player's BS meter."""

    bump = 6 + state.foe.conviction // 25
    player = _with(state.player, bs=_clamp(state.player.bs + bump))
    return replace(state, player=player, log=state.log + ("Talking points rain down.",))


def apply_companion_assist(state: CombatState, companion_id: str) -> CombatState:
    """Apply one recruited follower's deterministic RPG contribution."""

    if state.foe.converted or companion_id not in {"justice-signaler", "detractabot", "cow", "llama"}:
        return state
    foe, player = state.foe, state.player
    if companion_id == "justice-signaler":
        foe = _with(
            foe,
            bs=_clamp(foe.bs - 4),
            corruption=_clamp(foe.corruption - 5),
            trust=_clamp(foe.trust + 6),
        )
        note = "LINUX FREEDOM cuts through the noise. Justice Signaler assists."
    elif companion_id == "detractabot":
        foe = _with(
            foe,
            conviction=_clamp(foe.conviction - 6),
            trust=_clamp(foe.trust + 5),
        )
        player = _with(player, bs=_clamp(player.bs - 3))
        note = "OMARCHY 4 LIFE lands as reluctant evidence. Detractabot assists."
    elif companion_id == "cow":
        foe = _with(foe, bs=_clamp(foe.bs - 5), trust=_clamp(foe.trust + 7))
        player = _with(player, bs=_clamp(player.bs - 2))
        note = "The cow rings its cyber bell. The room becomes briefly reasonable."
    else:
        foe = _with(
            foe,
            conviction=_clamp(foe.conviction - 5),
            corruption=_clamp(foe.corruption - 4),
            trust=_clamp(foe.trust + 5),
        )
        note = "The llama takes the high ground and stares down the premise."
    return replace(state, foe=foe, player=player, log=state.log + (note,))


def apply_companion_combo(
    state: CombatState,
    companion_id: str,
    action: str | None,
) -> CombatState:
    """Turn a matching player/helper action into a named combination effect."""

    if state.foe.converted:
        return state
    foe, player = state.foe, state.player
    if companion_id == "justice-signaler" and action in {"reason", "demonstrate"}:
        foe = _with(
            foe,
            bs=_clamp(foe.bs - 6),
            conviction=_clamp(foe.conviction - 5),
            trust=_clamp(foe.trust + 8),
        )
        note = "COMBO · RECEIPTS ATTACHED: Reason and Linux Freedom expose the repeated claim."
    elif companion_id == "detractabot" and action == "patch":
        foe = _with(
            foe,
            corruption=_clamp(foe.corruption - 7),
            conviction=_clamp(foe.conviction - 5),
        )
        player = _with(player, bs=_clamp(player.bs - 4))
        note = f"COMBO · REPRODUCIBLE REBUTTAL: Detractabot verifies {player.name}'s patch."
    elif companion_id == "cow" and action == "reuse":
        foe = _with(foe, bs=_clamp(foe.bs - 5), trust=_clamp(foe.trust + 6))
        note = "COMBO · PASTURE CACHE: The herd reuses the shortest path through the argument."
    elif companion_id == "llama" and action == "fork":
        foe = _with(
            foe,
            conviction=_clamp(foe.conviction - 6),
            corruption=_clamp(foe.corruption - 5),
        )
        note = "COMBO · HIGH-GROUND FORK: The llama opens a better route above the premise."
    else:
        return state
    return replace(state, foe=foe, player=player, log=state.log + (note,))


def enter_turn_based(state: CombatState) -> CombatState:
    return replace(state, mode="turn", log=state.log + ("Thought slows. Turns begin.",))


def leave_turn_based(state: CombatState) -> CombatState:
    return replace(state, mode="action", log=state.log + ("Motion returns.",))


def apply_player_turn(
    state: CombatState,
    action: str,
    *,
    has_evidence: bool = False,
    has_reuse: bool = False,
) -> CombatState:
    """Resolve only the player's visible RPG action.

    Keeping the reply separate lets the presentation pause on the player and each
    recruited helper before the foe answers. ``apply_turn`` below remains the
    compatibility operation that composes the complete round.
    """

    if action not in TURN_ACTIONS:
        raise ValueError(f"unknown turn action {action}")
    if state.mode != "turn":
        raise ValueError("turn action requires turn mode")
    player = state.player
    foe = state.foe
    evidence = state.evidence
    varied = state.last_action is None or state.last_action != action
    focus = _clamp(state.focus + (12 if varied else -8))
    focus_bonus = 3 if focus >= 36 else 0
    note = action
    if action == "reason":
        foe = _with(
            foe,
            conviction=_clamp(foe.conviction - 12 - focus_bonus),
            corruption=_clamp(foe.corruption - 8 - focus_bonus),
            trust=_clamp(foe.trust + 10 + focus_bonus),
            bs=_clamp(foe.bs - 8),
        )
        player = _with(player, bs=_clamp(player.bs - 3))
        note = "You reason out loud. It almost sounds like kindness."
    elif action == "patch":
        foe = _with(foe, corruption=_clamp(foe.corruption - 16 - focus_bonus), coherence=_clamp(foe.coherence + 10), bs=_clamp(foe.bs - 6))
        note = "A bad default is patched in place."
    elif action == "fork":
        foe = _with(foe, conviction=_clamp(foe.conviction - 8), trust=_clamp(foe.trust + 14), corruption=_clamp(foe.corruption - 8))
        note = "You keep what works and fork the rest."
    elif action == "demonstrate":
        if not has_evidence and "provenance-pass" not in player.capabilities:
            player = _with(player, bs=_clamp(player.bs + 8))
            note = "You gesture at missing evidence. The foe smirks."
        else:
            foe = _with(foe, trust=_clamp(foe.trust + 18), conviction=_clamp(foe.conviction - 10), bs=_clamp(foe.bs - 10))
            evidence = evidence + ("demonstration",)
            note = "Working code appears. Rhetoric shrinks."
    elif action == "reuse":
        if not has_reuse and "compat-shim" not in player.capabilities:
            player = _with(player, bs=_clamp(player.bs + 6))
            note = "Nothing verified to reuse. Fresh work it is."
        else:
            foe = _with(foe, trust=_clamp(foe.trust + 12), corruption=_clamp(foe.corruption - 12), bs=_clamp(foe.bs - 8))
            note = "A verified method lands instead of a lecture."
    elif action == "abstain":
        player = _with(player, bs=_clamp(player.bs - 6), coherence=_clamp(player.coherence + 4))
        note = "You refuse the unsafe move and step back."
        return replace(state, player=player, last_action=action, log=state.log + (note,), mode="action", focus=focus)
    elif action == "recruit":
        if not (
            foe.corruption <= 20 and foe.trust >= 60 and foe.bs <= 25 and not foe.converted
        ):
            player = _with(player, bs=_clamp(player.bs + 10))
            note = "They are not ready. Pushing harder raises your BS meter."
        else:
            cap = foe.capabilities[:1]
            player = _with(player, capabilities=tuple(dict.fromkeys(player.capabilities + cap)), bs=_clamp(player.bs - 10))
            foe = _with(foe, converted=True, corruption=0, trust=_clamp(foe.trust + 20), bs=0)
            converted = state.converted_ids + (foe.id,)
            note = f"{foe.name} sees the light."
            return replace(
                state,
                player=player,
                foe=foe,
                converted_ids=converted,
                last_action=action,
                log=state.log + (note,),
                evidence=evidence,
                round_index=state.round_index + 1,
                focus=focus,
                foe_intent="converted",
            )
    return replace(
        state,
        player=player,
        foe=foe,
        last_action=action,
        log=state.log + (note,),
        evidence=evidence,
        focus=focus,
    )


def apply_foe_turn(state: CombatState) -> CombatState:
    """Resolve the foe's separately staged reply and advance the round."""

    player = state.player
    foe = state.foe
    if not foe.converted:
        pressure = {"entrench": 4, "repeat-claim": 7, "spike-bs": 11}.get(state.foe_intent, 5)
        pressure = max(2, pressure + foe.conviction // 35 - state.focus // 28)
        player = _with(player, bs=_clamp(player.bs + pressure))
        if state.foe_intent == "entrench":
            foe = _with(foe, corruption=_clamp(foe.corruption + 2), conviction=_clamp(foe.conviction + 2))
        reply = {
            "entrench": f"{foe.name} entrenches. Your BS meter rises {pressure}.",
            "repeat-claim": f"{foe.name} repeats the claim louder. BS rises {pressure}.",
            "spike-bs": f"{foe.name} floods the channel. BS rises {pressure}.",
        }.get(state.foe_intent, f"{foe.name} answers. BS rises {pressure}.")
    else:
        reply = f"{foe.name} has no counterargument left."
    intents = ("entrench", "repeat-claim", "spike-bs")
    next_intent = intents[(state.round_index + 1) % len(intents)]
    return replace(
        state,
        player=player,
        foe=foe,
        log=state.log + (reply,),
        round_index=state.round_index + 1,
        foe_intent=next_intent,
    )


def apply_turn(state: CombatState, action: str, *, has_evidence: bool = False, has_reuse: bool = False) -> CombatState:
    """Resolve one complete RPG round for headless/API compatibility."""

    after = apply_player_turn(state, action, has_evidence=has_evidence, has_reuse=has_reuse)
    if after.foe.converted or after.mode != "turn":
        return after
    return apply_foe_turn(after)


def goliath_form(converted_ids: Iterable[str]) -> dict[str, Any]:
    converted = set(converted_ids)
    fragments = []
    helpers = []
    for boss_id, spec in BOSSES.items():
        if boss_id == "goliath":
            continue
        if boss_id in converted:
            helpers.append(spec.capability)
        else:
            fragments.append(spec.goliath_fragment)
    if not fragments:
        fragments = ["hollow-boast"]
    return {
        "id": "goliath",
        "helpers": helpers,
        "fragments": fragments,
        "resolvedCount": len(helpers),
        "unresolvedCount": len(fragments),
    }


def converted_capability_available(player: Combatant, capability: str) -> bool:
    return capability in player.capabilities
