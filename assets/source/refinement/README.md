# September 2026 game refinement assets

Generated with the built-in imagegen tool from existing project boss art and
the maintainer's robot, portal and EXIT-sign concepts. Exact prompts, original
generated filenames, chosen repository paths and SHA-256 values are recorded
in `generation-prompts.json`. No CLI API fallback was used. Project artwork
terms remain in ASSET-LICENSE.md.

Each boss sheet supplies ready, active and defeated poses. `refinement_art.py`
removes the cyan key and registers a shared scale/baseline before deriving all
fidelities. Defeated poses are not enlarged to standing height. Legacy converted
filenames also use the defeated artwork.

The robot separates body, upper arm, forearm, open claw, closed claw and joint
cap. A second sheet replaces the initial external haze with a clean green key.
`articulation.py` provides three-joint kinematics. The renderer rotates parts
around measured sockets and overlays hinge caps. Two instances operate out of
phase around the prologue table, with a still reduced-motion pose.

Portal art supplies a pad and separate ascending ring. The EXIT sign has genuine
transparency and pre-rendered lettering. Royal correction sheets are saved in
`../characters/<id>/pose-corrections-v3.png`; their prompts are included here.
They supply the diagonal transfer, face closeup and rear workshop compositions.
