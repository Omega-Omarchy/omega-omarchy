from dataclasses import replace
from math import dist

from PIL import Image
import pytest

from omega_omarchy.articulation import custodian_pose
from omega_omarchy.campaign import BOSSES
from omega_omarchy.character_pack import available_characters
from omega_omarchy.physics import InputState, TILE
from omega_omarchy.presentation import FIDELITIES
from omega_omarchy.reachability import _clear_arc, reachable_from
from omega_omarchy.runtime_assets import asset_dir
from omega_omarchy.sim import GameSim, NETWORK_TICKS


def test_standing_paths_need_headroom_and_low_tunnels_need_a_slide_floor():
    tiles = [".....#####....."] * 6 + [".S...........X.", "###############"]
    assert (13, 6) in reachable_from(tiles, (1, 6)), "grounded low tunnel permits a slide"
    assert not reachable_from(tiles, (7, 6)), "a standing spawn inside a one-tile tunnel is invalid"
    broken_floor = tiles[:-1] + ["#######.#######"]
    assert (13, 6) not in reachable_from(broken_floor, (1, 6)), "cannot certify an unsupported low slide"
    wall = tiles.copy()
    wall[6] = wall[6][:7] + "#" + wall[6][8:]
    assert (13, 6) not in reachable_from(wall, (1, 6))


def test_jump_arc_uses_head_clearance_and_normal_or_double_jump_limits():
    open_map = ["................"] * 14 + ["################"]
    assert _clear_arc(open_map, 3, 13, 6, 11), "ordinary reachable platform"
    assert _clear_arc(open_map, 3, 13, 6, 8), "early double jump gains extra height"
    assert not _clear_arc(open_map, 3, 13, 6, 5), "cannot invent an eight-tile jump"
    roof = open_map.copy()
    roof[11] = "################"
    assert not _clear_arc(roof, 3, 13, 8, 13), "feet fit, but the head cannot clear the arc"
    solid_deck = open_map.copy()
    solid_deck[12] = "================"
    assert not _clear_arc(solid_deck, 3, 13, 8, 13), "normal platforms block an ascending body"


def test_portal_overlap_uses_normal_network_rearm_without_an_up_press():
    sim = GameSim.from_play_now()
    sim.tiles = ["........................"] * 8 + ["########################"]
    sim.entities = sim._skyway_lift_pair({"lower": [4, 7], "upper": [15, 7]})
    sim.body = replace(sim.body, x=4 * TILE + 3, y=8 * TILE - 18, vx=0, vy=0, on_ground=True)
    sim.network_armed = True
    sim.step(InputState())
    assert sim.scene == "network" and sim.network_protocol == "skyway"
    for _ in range(NETWORK_TICKS):
        sim.step(InputState())
    assert sim.scene == "action" and not sim.network_armed
    for _ in range(10):
        sim.step(InputState())
    assert sim.scene == "action", "arrival overlap cannot bounce straight back"
    for _ in range(25):
        sim.step(InputState(right=True))
    assert sim.network_armed
    for _ in range(40):
        sim.step(InputState(left=True))
        if sim.scene == "network":
            break
    assert sim.scene == "network", "walk back into the portal; no Up key"


@pytest.mark.parametrize("fid", FIDELITIES)
def test_royal_slide_alpha_baselines_match_david_exactly(fid):
    root = asset_dir()
    david = Image.open(root / "fidelity" / fid / "characters/david_side-slide.png")
    bottom = david.getchannel("A").getbbox()[3]
    for pack_id in ("omarch-king", "omarch-queen"):
        image = Image.open(root / "character-packs" / pack_id / fid / "side-slide.png")
        assert image.getchannel("A").getbbox()[3] == bottom


@pytest.mark.parametrize("fid", FIDELITIES)
def test_bosses_have_distinct_active_and_visibly_lower_defeated_frames(fid):
    for boss in (*BOSSES, "goliath-cyborg-penguin"):
        folder = asset_dir() / "fidelity" / fid / "bosses"
        images = [Image.open(folder / f"{boss}{suffix}.png").convert("RGBA") for suffix in ("", "-active", "-defeated")]
        assert len({im.size for im in images}) == 1
        assert len({im.tobytes() for im in images}) == 3
        boxes = [im.getchannel("A").getbbox() for im in images]
        assert boxes[2][1] > boxes[0][1], (boss, boxes)
        assert abs(boxes[2][3] - boxes[0][3]) <= 2, (boss, boxes)


def test_articulated_robot_links_keep_their_lengths_and_reduced_motion_is_still():
    for right in (False, True):
        poses = [custodian_pose(94, 122, tick, right=right) for tick in range(0, 480, 11)]
        assert len({p.wrist for p in poses}) > 10
        assert {p.closed for p in poses} == {True, False}
        for pose in poses:
            assert dist(pose.shoulder, pose.elbow) == pytest.approx(27)
            assert dist(pose.elbow, pose.wrist) == pytest.approx(24)
        assert custodian_pose(94, 122, 0, right=right, reduced=True) == custodian_pose(94, 122, 999, right=right, reduced=True)


def test_selector_calls_the_default_character_david():
    from omega_omarchy.installer import InstallerSession, PARODY_STEPS
    session = InstallerSession()
    session.step_index = PARODY_STEPS.index("character")
    assert session.gum_page()["options"][0] == "David"
    assert available_characters()[0][0].name == "David"


def test_builtin_art_fixes_apply_to_existing_saves_but_custom_versions_stay_pinned():
    from omega_omarchy.character_pack import resolve_pack
    record = available_characters()[0][1].to_record()
    record["assetDigest"] = "sha256:" + "0" * 64
    assert resolve_pack(record) == asset_dir() / "character-packs/omarch-king"
    record["kind"] = "custom"
    with pytest.raises(ValueError, match="unavailable"):
        resolve_pack(record)
