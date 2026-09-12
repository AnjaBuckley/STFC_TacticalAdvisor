"""Synthetic, explicit schedules isolate specialist ability timing and scope."""

import pytest

from engine.catalogue import ship_stats
from engine.combat_simulator import simulate_combat
from engine.effects import ability_plan


def o(name, cls="Science", group="test"):
    return {
        "name": name,
        "rank": 5,
        "class": cls,
        "group": group,
        "attack": 100,
        "defense": 100,
        "health": 100,
        "stat_basis": "base",
    }


def ship(cls="Explorer"):
    return {
        "name": "Synthetic",
        "ship_class": cls,
        "crit_chance": 1,
        "base_stats": {
            "attack": 10,
            "health": 100000,
            "shield_health": 0,
            "armor": 10,
            "shield_deflection": 10,
            "dodge": 10,
        },
    }


def target(shots=1, rounds=3):
    return {
        "name": "Synthetic enemy",
        "hp": 100000,
        "crit_chance": 1,
        "crit_multiplier": 6,
        "critical_floor": 2,
        "debug_events": True,
        "firing_order": ["enemy", "player"],
        "max_rounds": rounds,
        "weapons": [{"damage": 10, "type": "energy", "shots": shots}],
    }


def sim(crew, enemy=None, player=None, context="pvp"):
    return simulate_combat(
        player or ship(),
        crew,
        [],
        {},
        enemy or target(),
        context,
        num_simulations=1,
        rng_seed=42,
    )


def test_trip_is_triggered_reduction_not_critical_points():
    result = sim([o("Trip Tucker")], target(shots=4))
    enemies = [x for x in result["event_trace"] if x["side"] == "enemy"]
    assert [x["crit_multiplier"] for x in enemies[:4]] == [6] * 4
    assert [x["crit_multiplier"] for x in enemies[4:8]] == [3.5] * 4
    multiple = target()
    multiple["weapons"] *= 3
    stacked = sim([o("Trip Tucker")], multiple)
    assert (
        min(
            e["crit_multiplier"] for e in stacked["event_trace"] if e["side"] == "enemy"
        )
        == 2
    )  # floor preserved
    assert result["crew_scoped_critical_points"] == 0


def test_archer_triggers_once_per_weapon_and_stacks():
    result = sim([o("Jonathan Archer")], target(shots=4))
    player = [x for x in result["event_trace"] if x["side"] == "player"]
    assert [x["crit_multiplier"] for x in player] == [2, 2.5, 2.5]


@pytest.mark.parametrize("name", ["Trip Tucker", "Jonathan Archer"])
def test_received_effects_excluded_from_armadas_and_below_deck(name):
    for context in ["armada", "assault"]:
        assert not ability_plan(
            [o(name)], [], context, {**target(), "encounter_context": context}, ship()
        )[1]
    assert not ability_plan([], [o(name)], "pvp", target(), ship())[1]


def test_archer_loot_requires_xindi_and_captain():
    crew = [o("Jonathan Archer"), o("Trip Tucker"), o("Chen")]
    enemy = {**target(), "name": "Xindi-Aquatic Cruiser"}
    assert ability_plan(crew, [], "pve_hostile", enemy, ship())[0]["loot"] > 0
    assert (
        "loot"
        not in ability_plan(
            [crew[1], crew[0], crew[2]], [], "pve_hostile", enemy, ship()
        )[0]
    )
    assert "loot" not in ability_plan(crew, [], "pve_hostile", target(), ship())[0]


def test_borg_stats_and_five_depend_on_officer_health():
    crew = [
        o("Five Of Eleven", "Engineering"),
        o("Seven Of Eleven"),
        o("Nine Of Eleven", "Command"),
    ]
    effects = ability_plan(crew, [], "pve_hostile", target(), ship())[0]
    stats, totals, _ = ship_stats(ship(), crew, {}, effects)
    assert totals["health"] == 600
    assert (
        stats["armor"] == 10 + totals["health"] * effects["defense_from_officer_health"]
    )
    side_effects = ability_plan(
        [crew[1], crew[0], crew[2]], [], "pve_hostile", target(), ship()
    )[0]
    assert "defense_from_officer_health" not in side_effects


def test_probe_effect_does_not_apply_to_borg_assailant():
    crew = [
        o("Seven Of Eleven"),
        o("Eight Of Eleven", "Engineering"),
        o("Nine Of Eleven", "Command"),
    ]

    def plans(name):
        return ability_plan(
            crew, [], "pve_hostile", {**target(), "name": name}, ship()
        )[1]

    assert not plans("Borg Assailant")
    assert plans("Borg Tactical Probe")[0]["chance"] == pytest.approx(0.9)


def pvp_crew():
    return [
        o("Weyoun", "Command"),
        o("Jack Ransom", "Science"),
        o("Pon", "Engineering"),
    ]


def test_morale_resolves_before_cascade_and_requires_explorer():
    result = sim(pvp_crew())
    assert all(e["morale"] for e in result["event_trace"])  # full synergy chance 100%
    assert result["event_trace"][0]["crit_chance"] < 1  # Pon active immediately
    assert (
        sim(pvp_crew(), player=ship("Battleship"))["event_trace"][0]["crit_chance"] == 1
    )
    assert not ability_plan(pvp_crew(), [], "pve_hostile", target(), ship())[1]


def test_ransom_inactive_without_morale_and_active_cascade_is_damage():
    without = sim([o("Jack Ransom")])
    plain = sim([])
    assert without["event_trace"] == plain["event_trace"]
    active = sim(pvp_crew())
    active_player = next(e for e in active["event_trace"] if e["side"] == "player")
    plain_player = next(e for e in plain["event_trace"] if e["side"] == "player")
    assert active_player["hull_damage"] > plain_player["hull_damage"]


def test_pon_delay_needs_explicit_defending():
    crew = [o("Pon", "Engineering"), o("Weyoun", "Command"), o("Ikat'ika", "Science")]
    assert not any(
        r.get("model") == "defending_delay"
        for r in ability_plan(crew, [], "pvp", target(), ship())[1]
    )
    assert any(
        r.get("model") == "defending_delay"
        for r in ability_plan(
            crew, [], "pvp", target(), {**ship(), "is_defending": True}
        )[1]
    )


def test_each_weapon_keeps_its_critical_profile_and_trip_stacks():
    enemy = target(rounds=1)
    enemy["weapons"] = [
        {"damage": 10, "crit_chance": 0, "crit_multiplier": 1.5},
        {"damage": 10, "crit_chance": 1, "crit_multiplier": 10},
        {"damage": 10, "crit_chance": None, "crit_multiplier": None},
    ]
    result = sim([o("Trip Tucker")], enemy)
    events = [e for e in result["event_trace"] if e["side"] == "enemy"]
    assert [e["critical"] for e in events] == [False, True, True]
    assert [e["crit_multiplier"] for e in events] == [2, 7.5, 2]
