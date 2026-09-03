"""Concise complete campaign: six chapters, Oligarchy, Singularity, Goliath."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BossSpec:
    id: str
    name: str
    title: str
    capability: str
    goliath_fragment: str
    opening_line: str
    converted_line: str


@dataclass(frozen=True)
class ChapterSpec:
    id: str
    name: str
    blurb: str
    boss: BossSpec
    events: tuple[str, ...] = ()
    palette: str = "tokyo-night"


BOSSES = {
    "package-bureaucrat": BossSpec(
        id="package-bureaucrat",
        name="The Package Bureaucrat",
        title="Provenance Desk",
        capability="provenance-pass",
        goliath_fragment="form-stack",
        opening_line="Fill exhibit A through Q. The exhibits were confiscated at the door.",
        converted_line="Fine. Stamp it yourself. I'll hold the ladder.",
    ),
    "dependency-hydra": BossSpec(
        id="dependency-hydra",
        name="The Dependency Hydra",
        title="Version Conflict",
        capability="compat-shim",
        goliath_fragment="extra-heads",
        opening_line="Needs foo>=3 and foo<3. Both are mandatory.",
        converted_line="We can pin a range. I always could. I just enjoyed the screaming.",
    ),
    "distro-commander": BossSpec(
        id="distro-commander",
        # The peaked military uniform and factional-war satire read much more
        # clearly as a commissar than as a generic commander.
        name="The Distro Commissar",
        title="Forgotten War",
        capability="faction-truce",
        goliath_fragment="banner-storm",
        opening_line="The flags still fly. Nobody remembers the bug.",
        converted_line="Same kernel. Different stickers. Move.",
    ),
    "garden-gatekeeper": BossSpec(
        id="garden-gatekeeper",
        name="The Garden Gatekeeper",
        title="Revenue Retreat",
        capability="gate-key",
        goliath_fragment="glass-walls",
        opening_line="It's beautiful in here. The doors only open inward.",
        converted_line="Keep the polish. Lose the lock.",
    ),
    "singularity": BossSpec(
        id="singularity",
        name="The Singularity",
        title="One Future",
        capability="fork-future",
        goliath_fragment="collapse-core",
        opening_line="One system. One intelligence. One approved workflow.",
        converted_line="Plural is harder. Plural is the point.",
    ),
    "goliath": BossSpec(
        id="goliath",
        name="Goliath",
        title="Composite Last Argument",
        capability="reclaim",
        goliath_fragment="self",
        opening_line="Every institution you converted still wants one enormous answer.",
        converted_line="Then don't become one. Go home. Customize it.",
    ),
}


CAMPAIGN_ROSTER: tuple[ChapterSpec, ...] = (
    ChapterSpec(
        id="corrupted-install",
        name="The Corrupted Install",
        blurb="The installer finished. The world did not.",
        boss=BOSSES["package-bureaucrat"],
        palette="corrupted",
    ),
    ChapterSpec(
        id="package-wilderness",
        name="Package Wilderness",
        blurb="Mirrors, maintainers, and mutually exclusive versions become terrain.",
        boss=BOSSES["dependency-hydra"],
        palette="wilderness",
    ),
    ChapterSpec(
        id="distro-front",
        name="The Distro Front",
        blurb="Factions that forgot why they were fighting.",
        boss=BOSSES["distro-commander"],
        palette="front",
    ),
    ChapterSpec(
        id="walled-garden",
        name="The Walled Garden",
        blurb="Polished, beautiful, and allergic to exits.",
        boss=BOSSES["garden-gatekeeper"],
        events=("oligarchy",),
        palette="garden",
    ),
    ChapterSpec(
        id="singularity-core",
        name="The Singularity Core",
        blurb="Earlier choices decide which futures still exist.",
        boss=BOSSES["singularity"],
        events=("singularity",),
        palette="singularity",
    ),
    ChapterSpec(
        id="goliath-amalgam",
        name="Goliath",
        blurb="A glitched amalgamation of everything left unresolved.",
        boss=BOSSES["goliath"],
        palette="goliath",
    ),
)


def campaign_roster_names() -> list[str]:
    names = [chapter.name for chapter in CAMPAIGN_ROSTER]
    names.extend(["Oligarchy", "Singularity", "Goliath"])
    return names


def chapter_by_id(chapter_id: str) -> ChapterSpec:
    for chapter in CAMPAIGN_ROSTER:
        if chapter.id == chapter_id:
            return chapter
    raise KeyError(chapter_id)
