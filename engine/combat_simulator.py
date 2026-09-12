"""
Round-by-Round Combat Simulator — STFC

Simulates N rounds of combat applying the full damage calculation chain:
  1. Raw Damage (base + research + officer stats)
  2. Standard Mitigation (logistic function)
  3. Apex Barrier (effective HP)
  4. Critical Mitigation (Update 90)
  5. Isolytic Damage (parallel track)

Returns: kill_count_per_flight, avg_rounds_per_kill, survival_probability,
         total_damage_taken, mitigation_efficiency
"""

import random

from engine.apex_barrier import calc_effective_hp
from engine.critical_mitigation import (
    aggregate_crit_mitigation_sources,
    calc_critical_mitigation,
)
from engine.effects import crew_effects
from engine.isolytic import calc_isolytic_damage
from engine.mitigation import calc_mitigation
from engine.stat_calculator import calc_final_stat


def _crew_stat(officer: dict, key: str) -> float:
    """Officer stat from flat key, falling back to the nested stats block."""
    return officer.get(key, 0) or officer.get("stats", {}).get(key, 0)


def simulate_combat(
    ship: dict,
    bridge_crew: list[dict],
    below_deck_crew: list[dict],
    player_profile: dict,
    target_hostile: dict,
    task_type: str,
    num_simulations: int = 200,
    rng_seed: int | None = None,
) -> dict:
    """
    Run num_simulations independent Monte Carlo combat runs.

    Pass rng_seed for reproducible results (e.g. when ranking crews —
    all candidates should face the same random sequence).

    Returns aggregated stats across all simulations.
    """
    if not 1 <= num_simulations <= 10000:
        raise ValueError("Simulation count must be between 1 and 10000.")
    effects, omissions = crew_effects(
        bridge_crew, below_deck_crew, task_type, target_hostile
    )
    rng = random.Random(rng_seed)
    results = []

    for _ in range(num_simulations):
        result = _single_combat_run(
            ship,
            bridge_crew,
            below_deck_crew,
            player_profile,
            target_hostile,
            task_type,
            random.Random(rng.getrandbits(64)),
            effects,
        )
        results.append(result)

    avg_rounds = sum(r["rounds_to_kill"] for r in results) / len(results)
    survival_pct = sum(1 for r in results if r["survived"]) / len(results)
    kill_pct = sum(1 for r in results if r["killed_target"]) / len(results)
    avg_damage = sum(r["total_damage_taken"] for r in results) / len(results)

    return {
        "avg_rounds_to_kill": round(avg_rounds, 2),
        "survival_probability": round(survival_pct * 100, 2),
        "kill_probability": round(kill_pct * 100, 2),
        "avg_damage_taken": round(avg_damage, 2),
        "effective_hp": round(results[0]["effective_hp"], 2),
        "simulation_count": num_simulations,
        "model": "Estimated round-based combat",
        "unmodelled_abilities": omissions,
        "standard_mitigation": results[0]["standard_mitigation"],
        "isolytic_bonus": results[0]["isolytic_bonus"],
        "damage_trace": results[0]["damage_trace"],
        "avg_combat_rounds": round(avg_rounds, 2),
    }


def _single_combat_run(
    ship,
    bridge_crew,
    below_deck_crew,
    player_profile,
    target,
    task_type,
    rng,
    effects=None,
) -> dict:
    """Single combat run — internal use only."""

    effects = effects or {}

    # Crew stat contribution: officer attack adds to ship attack, officer
    # health adds to hull health (both bridge and below deck, as in game).
    # Officer-stat research multiplies these raw values (additive stacking,
    # per the Stat_final formula) — at late game this dwarfs ship base stats.
    combat_research = player_profile.get("research", {}).get("combat", {})
    all_research = combat_research.get("all_research", 0.0)
    atk_research = combat_research.get("atk_only_research", 0.0)
    hth_research = combat_research.get("hth_only_research", 0.0)

    full_crew = list(bridge_crew) + list(below_deck_crew)
    crew_attack = calc_final_stat(
        sum(_crew_stat(o, "attack") for o in full_crew),
        [atk_research, all_research],
        [],
        [],
    )
    crew_health = calc_final_stat(
        sum(_crew_stat(o, "health") for o in full_crew),
        [hth_research, all_research],
        [],
        [],
    )

    # Ship stats scale with SHIP research (weapon damage / hull health),
    # tracked separately from officer research in the profile
    ship_attack = calc_final_stat(
        ship["base_stats"]["attack"],
        [combat_research.get("ship_weapon_damage", 0.0)],
        [],
        [
            effects.get("weapon_damage", 0.0)
            + sum(o.get("attack_bonus", 0) for o in bridge_crew)
        ],
    )
    ship_health = calc_final_stat(
        ship["base_stats"]["health"],
        [combat_research.get("ship_hull_health", 0.0)],
        [],
        [],
    )

    # Effective HP (with Apex Barrier)
    apex_result = calc_effective_hp(
        ship_health + crew_health,
        (
            player_profile.get("research", {})
            .get("mirror_tree", {})
            .get("apex_barrier", 0)
            + effects.get("apex_barrier", 0)
        )
        * (1 - min(1, max(0, target.get("apex_shred", 0)))),
    )
    effective_hp = apex_result["effective_hp"]

    # Mitigation
    mit_result = calc_mitigation(
        ship["base_stats"]["armor"],
        ship["base_stats"]["shield_deflection"],
        ship["base_stats"]["dodge"],
        target.get("armor_piercing", 5000),
        target.get("shield_piercing", 5000),
        target.get("accuracy", 5000),
        ship["ship_class"],
    )
    mitigation = mit_result["total_mitigation"]

    # Critical Mitigation (Update 90) — evaluated against the ship in use,
    # so Simulacrum Refit eligibility follows the recommendation, not a
    # separately maintained "active_ship" profile key.
    crit_mit = aggregate_crit_mitigation_sources(
        player_profile, task_type, active_ship=ship
    )
    crit_mitigation_value = crit_mit["total_crit_mitigation"]

    # Isolytic bonus: research + explicit ship bonus + scoped active abilities.
    iso_bonus = (
        player_profile.get("research", {})
        .get("star_path", {})
        .get("isolytic_damage_bonus", 0.0)
    )
    iso_bonus += effects.get("isolytic_damage", 0) + ship.get(
        "isolytic_damage_bonus", 0
    )
    enemy_iso_defense = target.get("iso_defense", 0.0)

    target_mitigation = 0.0
    if target.get("defense_stats") and target.get("ship_class") in {
        "Explorer",
        "Battleship",
        "Interceptor",
    }:
        defense = target["defense_stats"]
        target_mitigation = calc_mitigation(
            defense.get("armor", 0),
            defense.get("shield_deflection", 0),
            defense.get("dodge", 0),
            ship["base_stats"].get("armor_piercing", 0),
            ship["base_stats"].get("shield_piercing", 0),
            ship["base_stats"].get("accuracy", 0),
            target["ship_class"],
        )["total_mitigation"]
    target_apex = 1 + max(0, target.get("apex_barrier", 0)) / 10000
    immunity = target.get("standard_damage_immune", target.get("name") == "Gorn Hunter")
    player_crit_chance = min(
        1, max(0, ship.get("crit_chance", 0) + effects.get("crit_chance", 0))
    )
    player_crit_multiplier = max(
        1, ship.get("crit_multiplier", 1.5) + effects.get("crit_damage", 0)
    )
    player_iso_defense = player_profile.get("research", {}).get("star_path", {}).get(
        "isolytic_defense_bonus", 0
    ) + effects.get("isolytic_defense", 0)
    target_hp = target.get("hp", 100000)
    hp_remaining = effective_hp
    rounds = 0
    total_damage_taken = 0

    trace = {}
    while target_hp > 0 and hp_remaining > 0 and rounds < 100:
        rounds += 1
        decay = target.get("hyperthermic_decay_fraction", 0) * effective_hp
        hp_remaining -= decay
        total_damage_taken += decay
        if hp_remaining <= 0:
            if rounds == 1:
                trace = {
                    "raw": 0,
                    "after_standard": 0,
                    "after_apex": 0,
                    "after_critical": 0,
                    "isolytic": 0,
                    "decay": decay / apex_result["multiplier"],
                    "is_critical": False,
                }
            break

        # Player deals damage (standard track + parallel isolytic track)
        standard_damage = ship_attack + crew_attack
        if rng.random() < player_crit_chance:
            standard_damage *= player_crit_multiplier
        iso_result = calc_isolytic_damage(standard_damage, iso_bonus, enemy_iso_defense)
        standard_output = 0 if immunity else standard_damage * (1 - target_mitigation)
        target_hp -= (standard_output + iso_result["iso_damage"]) / target_apex

        # Enemy deals damage
        enemy_raw = target.get("base_damage", 8000)
        enemy_after_mitigation = enemy_raw * (1 - mitigation)

        # Apply crit (20% base crit chance for hostiles)
        is_crit = rng.random() < target.get("crit_chance", 0.20)
        if is_crit:
            crit_damage = enemy_after_mitigation * target.get("crit_multiplier", 1.5)
            crit_result = calc_critical_mitigation(crit_damage, crit_mitigation_value)
            final_damage = crit_result["final_crit_damage"]
        else:
            final_damage = enemy_after_mitigation

        enemy_iso = calc_isolytic_damage(
            enemy_raw * (target.get("crit_multiplier", 1.5) if is_crit else 1),
            target.get("isolytic_damage_bonus", 0),
            player_iso_defense,
        )["iso_damage"]
        # Effective HP encodes Apex once for both parallel incoming tracks.
        # Decay is entered as a verified per-round hull fraction, not guessed.
        final_damage += enemy_iso
        if rounds == 1:
            multiplier = apex_result["multiplier"]
            crit_raw = enemy_after_mitigation * (
                target.get("crit_multiplier", 1.5) if is_crit else 1
            )
            trace = {
                "raw": enemy_raw,
                "after_standard": enemy_after_mitigation,
                "after_apex": crit_raw / multiplier,
                "after_critical": (final_damage - enemy_iso) / multiplier,
                "isolytic": enemy_iso / multiplier,
                "decay": decay / multiplier,
                "is_critical": is_crit,
            }
        hp_remaining -= final_damage
        total_damage_taken += final_damage

    return {
        "rounds_to_kill": rounds,
        "survived": hp_remaining > 0,
        "killed_target": target_hp <= 0,
        "total_damage_taken": total_damage_taken,
        "effective_hp": effective_hp,
        "standard_mitigation": mitigation,
        "isolytic_bonus": iso_bonus,
        "damage_trace": trace,
    }
