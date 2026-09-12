"""Synthetic regression cases, not calibration against live battle logs."""

import copy
import json

import pytest

from engine.catalogue import officer_bonus, ship_record, ship_stats
from engine.combat_simulator import _damage, _iso, _single_combat_run, simulate_combat
from engine.effects import ability_plan
from engine.hostile_stats import load_hostile_stats
from engine.mitigation import calc_mitigation
from engine.sources import source_effects, validate_sources
from ingest.research_csv import apply_to_profile, compute_research_buffs


def ship():
    return {
        "name": "Synthetic",
        "ship_class": "Explorer",
        "crit_chance": 0,
        "base_stats": {
            "attack": 100,
            "health": 10000,
            "shield_health": 1000,
            "armor": 0,
            "shield_deflection": 0,
            "dodge": 0,
        },
        "officer_bonus": {
            k: [{"value": 100, "bonus": 1}] for k in ("attack", "defense", "health")
        },
    }


def target():
    return {
        "name": "Synthetic",
        "hp": 1000,
        "shield_hp": 0,
        "base_damage": 100,
        "crit_chance": 0,
        "armor_piercing": 1,
        "shield_piercing": 1,
        "accuracy": 1,
        "max_rounds": 5,
    }


def run(s=None, t=None, p=None, b=None):
    return simulate_combat(
        s or ship(), [], b or [], p or {}, t or target(), "pve_hostile", 10, 42
    )


def test_stat_conversion_is_capped_and_never_adds_raw_points():
    stats, _, _ = ship_stats(
        ship(), [{"name": "Unknown", "attack": 1000000, "health": 1000000}], {}
    )
    assert stats["attack"] == 200
    assert stats["health"] == 20000
    assert officer_bonus(1000000, [{"value": 100, "bonus": 1}]) == 1


def test_known_short_ship_alias_resolves_same_table():
    assert (
        ship_record({"name": "Saladin"})["id"]
        == ship_record({"name": "U.S.S. Saladin"})["id"]
    )


def test_sheet_adjusted_stats_are_not_rebuffed():
    officer = {"name": "Test", "attack": 10, "stat_basis": "account_adjusted"}
    p = {"research": {"combat": {"all_research": 9}}}
    assert ship_stats(ship(), [officer], p)[1]["attack"] == 10
    officer["stat_basis"] = "base"
    assert ship_stats(ship(), [officer], p)[1]["attack"] == 100


def test_shield_absorption_and_overflow_preserve_damage_units():
    pool = {"shield": 20, "hull": 100}
    assert _damage(pool, 100, 0.8) == (80, 20)
    assert pool == {"shield": 0, "hull": 20}


def test_dead_enemy_does_not_fire():
    t = {**target(), "hp": 1}
    assert run(t=t)["avg_damage_taken"] == 0


def test_timeout_has_no_fabricated_time_to_kill():
    r = run(t={**target(), "hp": 1e12, "base_damage": 0})
    assert r["avg_rounds_to_kill"] is None
    assert r["timeout_probability"] == 100
    assert r["kill_interval_95"][0] == 0


def test_weapon_warmup_is_observed():
    s = {
        **ship(),
        "weapons": [{"damage": 10000, "shots": 1, "warmup": 2, "cooldown": 1}],
    }
    assert run(s=s)["avg_rounds_to_kill"] == 3


def test_hugh_is_a_rank_dependent_proc_not_static_chance():
    static, timed, _ = ability_plan(
        [], [{"name": "Hugh", "rank": 1}], "pve_hostile", {}
    )
    assert "crit_chance" not in static
    assert timed[0]["chance"] == 0.45
    assert timed[0]["duration"] == 2
    assert (
        ability_plan([], [{"name": "Hugh", "rank": 5}], "pve_hostile", {})[1][0][
            "chance"
        ]
        == 1
    )


def test_cascade_has_a_separate_combined_formula():
    assert _iso(100, 1, 1, 0) == 300
    assert _iso(100, 0, 1, 0) == 100


def test_outgoing_shred_reduces_enemy_barrier():
    t = {**target(), "hp": 600, "apex_barrier": 10000}
    without = run(t=t)
    with_shred = run(s={**ship(), "apex_shred": 1}, t=t)
    assert with_shred["avg_combat_rounds"] <= without["avg_combat_rounds"]


def test_stabilizer_offsets_decay():
    t = {**target(), "hyperthermic_decay_fraction": 0.1, "base_damage": 0}
    assert (
        run(s={**ship(), "hyperthermic_stabilizer": 0.1}, t=t)["avg_hull_damage"] == 0
    )
    assert run(t=t)["avg_hull_damage"] > 0


def test_standard_mitigation_saturation_matches_coefficients():
    r = calc_mitigation(1e9, 1e9, 1e9, 1, 1, 1, "Explorer")
    assert r["total_mitigation"] == pytest.approx(0.712)
    r = calc_mitigation(1e9, 1e9, 1e9, 1, 1, 1, "Survey")
    assert r["total_mitigation"] == pytest.approx(0.657)


def source(**kwargs):
    return dict(
        {
            "id": "test",
            "name": "Test",
            "status": "manual",
            "effect": "crit_mitigation",
            "unit": "points",
            "value": 50000,
            "contexts": ["pve"],
            "conditions": {},
        },
        **kwargs,
    )


def test_source_scope_and_duration():
    p = {
        "combat_sources": [source(duration=2, conditions={"target_class": "Explorer"})]
    }
    validate_sources(p["combat_sources"])
    t = {"ship_class": "Explorer"}
    assert source_effects(p, {}, "pve_hostile", t, 1)[0]["crit_mitigation"] == 50000
    assert source_effects(p, {}, "pve_hostile", t, 3)[0] == {}
    assert source_effects(p, {}, "pvp", t, 1)[0] == {}


@pytest.mark.parametrize(
    "change",
    [
        {"unit": "fraction"},
        {"value": -1},
        {"contexts": []},
        {"effect": "made_up"},
        {"duration": 0},
    ],
)
def test_invalid_sources_rejected(change):
    with pytest.raises(ValueError):
        validate_sources([source(**change)])


def test_unknown_imports_are_quarantined_and_manual_totals_survive(
    tmp_path, monkeypatch
):
    import ingest.research_csv as mod

    monkeypatch.setattr(mod, "_RESEARCH_DIR", tmp_path)
    (tmp_path / "1.json").write_text(
        json.dumps(
            {
                "buffs": [
                    {"id": 10, "value_is_percentage": True, "values": [{"value": 0.4}]},
                    {
                        "id": 11,
                        "value_is_percentage": False,
                        "values": [{"value": 50000}],
                    },
                ]
            }
        )
    )
    report = compute_research_buffs(
        [
            {
                "id": "1",
                "done": True,
                "level": 1,
                "name": "Mixed",
                "description": "Critical mitigation and damage",
            }
        ]
    )
    assert [(s["value"], s["unit"]) for s in report["sources"]] == [
        (0.4, "fraction"),
        (50000, "points"),
    ]
    p = {"research": {"mirror_tree": {"apex_barrier": 999}}}
    updated, _ = apply_to_profile(copy.deepcopy(p), report)
    assert updated["research"] == p["research"]
    assert source_effects(updated, {}, "pve_hostile", {})[0] == {}
    assert apply_to_profile(updated, report)[1] == []


def test_catalogue_never_relabels_actian_as_gorn():
    data = load_hostile_stats()
    assert "Gorn Apex" not in data
    for records in data.values():
        for r in records:
            assert r["ship_class"] in {
                "Explorer",
                "Battleship",
                "Interceptor",
                "Survey",
            }
    assert all(r["real_name"] == "Actian Apex" for r in data["Actian Apex"])


def test_hugh_weapon_proc_expires_before_round_three_with_no_second_hit():
    class ZeroRng:
        def random(self):
            return 0

    t = {
        **target(),
        "hp": 1e12,
        "max_rounds": 4,
        "debug_events": True,
        "weapons": [{"damage": 1, "shots": 3, "warmup": 0, "cooldown": 3}],
    }
    static, timed, _ = ability_plan([], [{"name": "Hugh", "rank": 5}], "pve_hostile", t)
    r = _single_combat_run(
        ship(), [], [], {}, t, "pve_hostile", ZeroRng(), static, timed
    )
    shots = [e for e in r["events"] if e["side"] == "player"]
    assert [e["crit_chance"] for e in shots] == [0, 0.25, 0, 0]
    assert [e["critical"] for e in shots] == [False, True, False, False]
