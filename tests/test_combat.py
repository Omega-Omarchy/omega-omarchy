from omega_omarchy.combat import (
    apply_action_item,
    apply_companion_combo,
    apply_foe_turn,
    apply_player_turn,
    apply_turn,
    converted_capability_available,
    enter_turn_based,
    goliath_form,
    make_foe,
    make_player,
    start_encounter,
)


def test_logic_bomb_reduces_corruption_not_hp_kill():
    state = start_encounter(make_player(), make_foe("package-bureaucrat", as_boss=True), boss_id="package-bureaucrat")
    after = apply_action_item(state, "logic-bomb")
    assert after.foe.corruption < state.foe.corruption
    assert after.foe.converted is False
    assert after.foe.bs < state.foe.bs


def test_recruit_requires_conditions_then_grants_capability():
    player = make_player()
    foe = make_foe("garden-gatekeeper", as_boss=True)
    state = enter_turn_based(start_encounter(player, foe, boss_id="garden-gatekeeper", mode="action"))
    denied = apply_turn(state, "recruit")
    assert denied.foe.converted is False
    # Drive stats into the recruit window using shipped turn actions.
    ready = state
    for _ in range(8):
        ready = apply_turn(ready, "patch", has_evidence=True, has_reuse=True)
        ready = apply_turn(ready, "demonstrate", has_evidence=True, has_reuse=True)
        ready = apply_turn(ready, "reason", has_evidence=True, has_reuse=True)
        if ready.foe_ready_to_recruit:
            break
    assert ready.foe_ready_to_recruit
    recruited = apply_turn(ready, "recruit", has_evidence=True)
    assert recruited.foe.converted
    assert converted_capability_available(recruited.player, "gate-key")
    assert "garden-gatekeeper" in recruited.converted_ids or recruited.foe.id == "garden-gatekeeper"


def test_goliath_reflects_unconverted_fragments():
    form = goliath_form(["package-bureaucrat", "dependency-hydra"])
    assert "compat-shim" in form["helpers"] or "provenance-pass" in form["helpers"]
    assert form["unresolvedCount"] >= 1
    assert "goliath" not in form["fragments"]


def test_abstain_returns_to_action_mode():
    state = enter_turn_based(start_encounter(make_player(), make_foe("distro-commander"), boss_id="distro-commander", mode="action"))
    after = apply_turn(state, "abstain")
    assert after.mode == "action"


def test_staged_player_and_foe_resolution_matches_complete_round_api():
    state = enter_turn_based(start_encounter(make_player(), make_foe("cache-gremlin"), mode="action"))
    staged = apply_foe_turn(apply_player_turn(state, "reason"))
    complete = apply_turn(state, "reason")
    assert staged == complete


def test_named_companion_combinations_reward_matching_player_actions():
    state = enter_turn_based(start_encounter(make_player(), make_foe("cache-gremlin"), mode="action"))
    justice = apply_companion_combo(state, "justice-signaler", "reason")
    detractor = apply_companion_combo(state, "detractabot", "patch")
    cow = apply_companion_combo(state, "cow", "reuse")
    llama = apply_companion_combo(state, "llama", "fork")
    assert justice.foe.trust > state.foe.trust
    assert detractor.foe.corruption < state.foe.corruption
    assert cow.foe.bs < state.foe.bs
    assert llama.foe.conviction < state.foe.conviction
    for result in (justice, detractor, cow, llama):
        assert "COMBO ·" in result.log[-1]
