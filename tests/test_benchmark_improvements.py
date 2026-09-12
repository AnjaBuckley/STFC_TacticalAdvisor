"""Behaviour regressions for reviewed legacy effects and ranking bias."""

from engine.combat_simulator import simulate_combat
from engine.effects import ability_plan
from optimizer.crew_optimizer import _sim_score


def officer(name, group="Starfleet Academy", cls="Science"):
    return {"name": name, "rank": 5, "group": group, "class": cls}


def target(kind="kinetic", level=35):
    return {
        "name": "Synthetic hostile",
        "level": level,
        "hp": 100000,
        "base_damage": 100,
        "weapons": [{"type": kind, "damage": 100, "shots": 1}],
        "crit_chance": 0,
        "max_rounds": 1,
    }


def test_legacy_defense_seat_scope_and_level():
    for name in ["Chen", "T'Laan"]:
        assert ability_plan([officer(name)], [], "pve_hostile", target())[0]
        assert not ability_plan([], [officer(name)], "pve_hostile", target())[0]
        assert not ability_plan([officer(name)], [], "pvp", target())[0]
        assert not ability_plan([officer(name)], [], "pve_hostile", target(level=52))[0]


def test_pike_boost_requires_captain_and_cap():
    crew = [
        officer("Pike", "Shakedown Cruise", "Command"),
        officer("Moreau", "Shakedown Cruise"),
        officer("T'Laan"),
    ]
    boosted = ability_plan(crew, [], "pve_hostile", target())[0]
    side = ability_plan([crew[2], crew[1], crew[0]], [], "pve_hostile", target())[0]
    assert boosted["enemy_kinetic_damage_down"] > side["enemy_kinetic_damage_down"]
    assert boosted["enemy_piercing_down"] > side["enemy_piercing_down"]
    assert not ability_plan(crew, [], "pve_hostile", target(level=71))[0]


def test_reduction_only_applies_to_matching_weapon():
    ship = {
        "name": "Synthetic",
        "ship_class": "Explorer",
        "base_stats": {"attack": 1, "health": 1000, "shield_health": 0},
    }

    def damage(kind, crew):
        return simulate_combat(
            ship,
            crew,
            [],
            {},
            target(kind),
            "pve_hostile",
            num_simulations=1,
            rng_seed=42,
        )["avg_damage_taken"]

    assert damage("energy", [officer("Chen")]) < damage("energy", [])
    assert damage("kinetic", [officer("Chen")]) == damage("kinetic", [])
    assert damage("aggregate", [officer("Chen")]) == damage("aggregate", [])


def test_unknown_weapon_type_is_disclosed():
    _, _, omissions = ability_plan(
        [officer("Chen")], [], "pve_hostile", target("aggregate")
    )
    assert any("unknown weapon types" in x for x in omissions)


def test_supported_captain_uses_seat_and_synergy_not_rank():
    crew = [officer("Ent-E Picard"), officer("Ent-E Data"), officer("Kathryn Janeway")]
    effects = ability_plan(crew, [], "pve_hostile", target())[0]
    assert effects["loot"] > 0
    assert (
        "loot"
        not in ability_plan([crew[1], crew[0], crew[2]], [], "pve_hostile", target())[0]
    )


def test_ranking_retains_speed_resolution_and_values_hull():
    base = {
        "kill_probability": 100,
        "survival_probability": 100,
        "avg_rounds_to_kill": 2,
        "hull_max": 1000,
        "avg_hull_lost": 500,
    }
    assert _sim_score(base) > _sim_score({**base, "avg_rounds_to_kill": 4})
    assert _sim_score({**base, "avg_hull_lost": 100}) > _sim_score(base)
    assert _sim_score({**base, "kill_probability": 0, "avg_rounds_to_kill": None}) == 0


def test_nx01_deflects_nine_aquatic_shots_only_with_explicit_schedule():
    ship = {
        "name": "Enterprise NX-01",
        "ship_class": "Explorer",
        "base_stats": {"attack": 1, "health": 100000, "shield_health": 0},
    }
    aquatic = {
        **target(),
        "name": "Xindi-Aquatic Cruiser",
        "weapons": [{"type": "energy", "damage": 100, "shots": 10}],
    }

    def damage(enemy, player):
        return simulate_combat(
            player, [], [], {}, enemy, "pve_hostile", num_simulations=1, rng_seed=42
        )["avg_damage_taken"]

    assert (
        abs(damage(aquatic, ship) * 10 - damage(aquatic, {**ship, "name": "Other"}))
        < 0.1
    )
    aggregate = {k: v for k, v in aquatic.items() if k != "weapons"}
    assert damage(aggregate, ship) == damage(aggregate, {**ship, "name": "Other"})
