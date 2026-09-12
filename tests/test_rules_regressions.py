"""Behavior regressions found during the current-rules/frontend migration."""

import copy

import pytest

from engine.abilities import officer_combat_scores, record_relevance
from engine.combat_simulator import simulate_combat
from engine.critical_mitigation import (
    aggregate_crit_mitigation_sources,
    points_to_reduction,
)
from engine.effects import crew_effects
from engine.synergy import calc_synergy
from optimizer.crew_optimizer import find_optimal_crew
from service import mission_target
from tests.test_combat_simulator import _profile, _ship, _target


def small_profile():
    return {
        **_profile(),
        "ops_level": 71,
        "ships": [_ship()],
        "officers": [
            {
                "name": name,
                "group": "Test",
                "class": cls,
                "attack": 1000,
                "health": 1000,
            }
            for name, cls in zip(
                ["Alpha", "Bravo", "Charlie"], ["Command", "Science", "Engineering"]
            )
        ],
    }


def test_points_match_scopely_worked_example():
    assert points_to_reduction(83000) == pytest.approx(0.62406, abs=0.00001)
    assert points_to_reduction(50000) == 0.5
    assert 0 < points_to_reduction(2000000) < 1


def test_point_sources_add_before_resolving_curve():
    p = {"research": {"critical_mitigation": {"remote_campus_points": 50000}}}
    ship = {
        "name": "USS Vengeance",
        "simulacrum_refit": True,
        "crit_mitigation_points": 33000,
    }
    result = aggregate_crit_mitigation_sources(p, "duo_wave_defense", ship)
    assert result["total_points"] == 83000
    assert result["total_crit_mitigation"] == pytest.approx(
        points_to_reduction(83000), abs=1e-6
    )


def test_explicit_zero_points_replaces_legacy_percentage():
    p = {
        "research": {
            "critical_mitigation": {
                "remote_campus_points": 0,
                "remote_campus_bonus": 0.9,
            }
        }
    }
    assert (
        aggregate_crit_mitigation_sources(p, "duo_wave_defense")[
            "total_crit_mitigation"
        ]
        == 0
    )


@pytest.mark.parametrize("points", [-1, float("nan"), float("inf")])
def test_invalid_mitigation_points_rejected(points):
    with pytest.raises(ValueError):
        points_to_reduction(points)


def test_ship_name_substring_cannot_grant_refit():
    ship = {
        "name": "Not USS Vengeance",
        "simulacrum_refit": True,
        "crit_mitigation_points": 50000,
    }
    assert aggregate_crit_mitigation_sources({}, "pvp", ship)["total_points"] == 0


def test_enemy_target_mismatch_has_zero_ability_relevance():
    assert (
        record_relevance(
            {"scope": "pve", "targets": ["borg"]},
            "pve_hostile",
            {"name": "Gorn Hunter"},
        )
        == 0
    )


def test_below_deck_ability_cannot_score_as_bridge_offense():
    assert officer_combat_scores({"name": "Hugh"}, "pve_hostile", {})["offense"] == 0
    effect, _ = crew_effects([], [{"name": "Hugh", "rank": 1}], "pve_hostile", {})
    assert "crit_chance" not in effect  # Hugh procs per received weapon, never a permanent buff.
    assert crew_effects([{"name": "Hugh"}], [], "pve_hostile", {})[0] == {}


def test_isolytic_ability_respects_rank_and_seat():
    janeway = {"name": "Kathryn Janeway", "rank": 1}
    assert crew_effects([janeway], [], "pve_hostile", {})[0]["isolytic_cascade"] == 0.1
    assert crew_effects([], [janeway], "pve_hostile", {})[0] == {}
    assert crew_effects([janeway], [], "pvp", {})[0] == {}


def test_gorn_hunter_cannot_be_killed_by_ordinary_damage():
    target = mission_target(
        "pve_hostile", "Gorn Hunter", 71, "Battleship", {"hp": 100, "shield_hp":0, "base_damage": 1}
    )
    result = simulate_combat(_ship(), [], [], _profile(), target, "pve_hostile", 2, 1)
    assert result["kill_probability"] == 0
    p = _profile()
    p["research"]["star_path"]["isolytic_damage_bonus"] = 1
    assert (
        simulate_combat(_ship(), [], [], p, target, "pve_hostile", 2, 1)[
            "kill_probability"
        ]
        == 100
    )


def test_enemy_mitigation_changes_standard_but_not_iso_output():
    target = {
        **_target(),
        "ship_class": "Explorer",
        "defense_stats": {"armor": 1e9, "shield_deflection": 1e9, "dodge": 1e9},
    }
    basic = simulate_combat(_ship(), [], [], _profile(), _target(), "pve_hostile", 2, 1)
    defended = simulate_combat(_ship(), [], [], _profile(), target, "pve_hostile", 2, 1)
    assert defended["avg_combat_rounds"] > basic["avg_combat_rounds"]


def test_apex_once_and_critical_reduction_only_on_critical_hits():
    p = _profile()
    p["research"]["mirror_tree"]["apex_barrier"] = 10000
    p["research"]["critical_mitigation"] = {"remote_campus_points": 50000}
    target = {**_target(), "type":"Academy Drone", "hp": 1e9, "crit_chance": 1, "crit_multiplier": 2}
    result = simulate_combat(_ship(), [], [], p, target, "pve_academy_drone", 1, 1)
    trace = result["damage_trace"]
    assert trace["after_apex"] == pytest.approx(trace["after_standard"] / 2)
    assert trace["after_critical"] == pytest.approx(trace["after_apex"] * 0.5, abs=0.01)
    target["crit_chance"] = 0
    normal = simulate_combat(_ship(), [], [], p, target, "pve_academy_drone", 1, 1)[
        "damage_trace"
    ]
    assert normal["after_critical"] == pytest.approx(normal["after_apex"], abs=0.01)


def test_optimizer_evaluates_all_captain_assignments_and_keeps_officers_unique(
    monkeypatch,
):
    import optimizer.crew_optimizer as optimizer

    monkeypatch.setattr(optimizer, "_SIM_RUNS", 1)
    p = small_profile()
    results = find_optimal_crew(p, {"task_type": "pve_hostile", "target": _target()}, 3)
    assert {r["captain"] for r in results} == {"Alpha", "Bravo", "Charlie"}
    for r in results:
        crew = [r["captain"], r["officer_1"], r["officer_2"]] + [
            o["name"] for o in r["below_deck"]
        ]
        assert len(set(crew)) == len(crew)


def test_no_unowned_fallback_ship():
    p = small_profile()
    p["ships"] = []
    with pytest.raises(ValueError, match="owned combat ship"):
        find_optimal_crew(p, {"task_type": "pve_hostile", "target": {}})


def test_class_preference_does_not_discard_owned_ship():
    p = small_profile()
    r = find_optimal_crew(
        p,
        {
            "task_type": "pve_hostile",
            "target": {**_target(), "recommended_ship_class": "Battleship"},
        },
        1,
    )
    assert r[0]["ship"] == p["ships"][0]["name"]


def test_unavailable_officers_do_not_fill_seats():
    p = small_profile()
    p["officers"][0]["available"] = False
    with pytest.raises(ValueError, match="three available officers"):
        find_optimal_crew(p, {"task_type": "pve_hostile", "target": {}})


def test_duo_blocks_pvp_only_source():
    p = small_profile()
    p["research"]["critical_mitigation"] = {
        "programmable_matter_beam": True,
        "programmable_matter_beam_points": 50000,
    }
    result = find_optimal_crew(p, {"task_type": "duo_wave_defense", "target": {}})
    assert result[0]["critical_mitigation"]["total_points"] == 0
    assert result[0]["critical_mitigation"]["warnings"]


def test_missing_class_cannot_claim_full_synergy():
    assert not calc_synergy(*[{"name": n, "group": "Test"} for n in "ABC"])[
        "full_synergy"
    ]
    crew = small_profile()["officers"]
    crew[1]["class"] = crew[0]["class"]
    assert not calc_synergy(*crew)["full_synergy"]


def test_simulation_does_not_mutate_inputs():
    args = (_ship(), [], [], _profile(), _target(), "pve_hostile")
    original = copy.deepcopy(args)
    simulate_combat(*args, 2, 1)
    assert args == original


def test_zero_simulations_rejected():
    with pytest.raises(ValueError, match="Simulation count"):
        simulate_combat(_ship(), [], [], _profile(), _target(), "pve_hostile", 0)


def test_finalists_from_each_owned_ship_are_simulated(monkeypatch):
    import optimizer.crew_optimizer as optimizer

    monkeypatch.setattr(optimizer, "_SIM_TOP_K", 1)
    monkeypatch.setattr(optimizer, "_SIM_RUNS", 1)
    p = small_profile()
    p["ships"].append({**_ship(), "name": "Second ship"})
    results = find_optimal_crew(p, {"task_type": "pve_hostile", "target": _target()}, 6)
    assert {r["ship"] for r in results} == {"Test Explorer", "Second ship"}


def test_immunity_without_any_iso_source_is_an_actionable_error():
    p = small_profile()
    with pytest.raises(ValueError, match="Isolytic Damage"):
        find_optimal_crew(
            p,
            {
                "task_type": "pve_hostile",
                "target": {**_target(), "standard_damage_immune": True},
            },
            1,
        )


def test_zero_kill_outcome_does_not_report_finite_cost_per_kill():
    p = small_profile()
    p["ships"][0]["repair_cost_total"] = 1000
    results = find_optimal_crew(
        p, {"task_type": "pve_hostile", "target": {**_target(), "hp": 1e19}}, 1
    )
    assert results[0]["simulation"]["kill_probability"] == 0
    assert "cost_per_kill" not in results[0]


def test_cli_hostile_enrichment_applies_gorn_immunity():
    from engine.hostile_stats import enrich_target

    assert enrich_target({"name": "Gorn Hunter"}, 71)["standard_damage_immune"] is True


def test_pvp_counter_direction_and_strike_team_identity():
    from optimizer.pvp_logic import suggest_pvp_counter

    officers = [{"name": n} for n in ["Weyoun", "Pon", "Ikat'ika"]]
    result = suggest_pvp_counter("Interceptor", officers)
    assert result["recommended_ship_class"] == "Explorer"
    assert result["completeness"] == "3/3"
    assert (
        suggest_pvp_counter("Battleship", officers)["recommended_ship_class"]
        == "Interceptor"
    )
    assert (
        suggest_pvp_counter("Explorer", officers)["recommended_ship_class"]
        == "Battleship"
    )


def test_unavailable_strike_team_member_is_reported_missing():
    from optimizer.pvp_logic import suggest_pvp_counter

    result = suggest_pvp_counter(
        "Interceptor", [{"name": "Weyoun", "available": False}]
    )
    assert "Weyoun" in result["missing"]


def test_lethal_start_of_round_decay_prevents_player_shot():
    result = simulate_combat(
        _ship(),
        [],
        [],
        _profile(),
        {**_target(), "hp": 1, "hyperthermic_decay_fraction": 1},
        "pve_hostile",
        1,
        1,
    )
    assert result["kill_probability"] == 0
    assert result["survival_probability"] == 0
    assert result["damage_trace"]["raw"] == 0


def test_locked_zero_rank_officers_cannot_be_recommended():
    p = small_profile()
    p["officers"][0].update(rank=0, level=0)
    with pytest.raises(ValueError, match="three available officers"):
        find_optimal_crew(p, {"task_type": "pve_hostile", "target": _target()}, 1)
