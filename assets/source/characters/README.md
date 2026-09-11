# Omarch character sources

The maintainer supplied `Omarch-King.jfif` and `Omarch-Queen.jfif` from
`~/Transfer/Inbox/omega-omarchy/assets/concepts/`. They are preserved here as
`omarch-king/concept.jfif` and `omarch-queen/concept.jfif`. Source authorship or
an external license is not inferred from the filenames. These concepts and
their derivatives remain within the project's existing private asset policy.

On 2026-09-09 the built-in imagegen tool generated one 5-column × 4-row atlas
for each character, using its concept for identity/costume and the existing
David Ultra idle master only for the game's rendering style/proportions.
`generation-prompts.json` preserves the prompts. `atlas-v1.png` records the
initial outputs; their apparent transparency was a painted checkerboard.
The selected `atlas-keyed-v2.png` outputs replace that backdrop with explicit
green chroma key. No first-version checkerboard is packaged in runtime art.

`pose-corrections-v3.png` supplies a diagonal reclining transfer, a close face
portrait, and a rear workshop pose framed against David's corresponding art.
These panels override those three atlas poses. Their exact imagegen prompts
are recorded in `../refinement/generation-prompts.json`. Slide derivatives are
registered to David's lowest alpha row separately in each fidelity.

`character_build.build_builtin_characters` slices the observed row bands,
removes green, registers the bodies, and emits the complete 26-pose Ultra set.
The compiler derives the other two fidelities. Falling/hurt and compressed
landing/crouch use the existing animation approach; battle reuses idle and
turn reuses portrait. Rear climb contacts are mirrored to alternate the raised
hand/knee. The largest connected subject in each cell removes fragments from
neighboring poses. The source order is `ATLAS_POSES` in that module.

Built assets live in `assets/character-packs/{omarch-king,omarch-queen}/`, each
with an integrity manifest and all three fidelity directories. Rebuild via
`./scripts/omega assets`; inspect using `scripts/review-characters.py`.
Source references and atlases are excluded from player/browser packages.
