"""Two-pool, per-weapon estimated combat with scoped and timed effects.

The engine reports model limitations and sampling uncertainty. It does not
claim live-game calibration; missing schedules use one aggregate shot/round.
"""

import math
import random
from collections import defaultdict

from engine.catalogue import identity, ship_stats
from engine.critical_mitigation import (
    aggregate_crit_mitigation_sources,
    points_to_reduction,
)
from engine.effects import ability_plan
from engine.mitigation import calc_mitigation
from engine.sources import source_effects


def _crew_stat(officer, key):
    return officer.get(key, officer.get("stats", {}).get(key, 0))


def _wilson(successes, n):
    z = 1.96
    p = successes / n
    divisor = 1 + z * z / n
    center = (p + z * z / (2 * n)) / divisor
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / divisor
    return [
        round(max(0, center - radius) * 100, 1),
        round(min(1, center + radius) * 100, 1),
    ]


def _iso(raw, bonus, cascade, defense):
    # Community combined-Cascade model, always disclosed when used.
    return raw * (bonus * (1 + cascade) + cascade) / (1 + max(0, defense))


def _damage(pool, amount, absorption):
    """Route damage to shields/hull; overflow from depleted shields reaches hull."""
    amount = max(0, amount)
    absorbed = min(pool["shield"], amount * min(1, max(0, absorption)))
    hull_damage = min(pool["hull"], amount - absorbed)
    pool["shield"] -= absorbed
    pool["hull"] -= hull_damage
    return hull_damage, absorbed


def _mitigation(defense, attacker, ship_class):
    return calc_mitigation(
        defense.get("armor", 0),
        defense.get("shield_deflection", 0),
        defense.get("dodge", 0),
        attacker.get("armor_piercing", 0),
        attacker.get("shield_piercing", 0),
        attacker.get("accuracy", 0),
        ship_class,
    )["total_mitigation"]


def _weapons(data, damage):
    return data.get("weapons") or [
        {"damage": damage, "shots": 1, "warmup": 0, "cooldown": 1, "type": "aggregate"}
    ]


def _single_combat_run(
    ship,
    bridge_crew,
    below_deck_crew,
    player_profile,
    target,
    task_type,
    rng,
    effects=None,
    timed=None,
):
    effects = dict(effects or {})
    timed = timed or []
    scoped_stats, _ = source_effects(player_profile, ship, task_type, target)
    stat_effects = {
        key: effects.get(key, 0) + scoped_stats.get(key, 0)
        for key in set(effects) | set(scoped_stats)
    }
    stats, _, stat_warnings = ship_stats(
        ship, bridge_crew + below_deck_crew, player_profile, stat_effects
    )
    research = player_profile.get("research", {})
    star, mirror = research.get("star_path", {}), research.get("mirror_tree", {})
    player = {"hull": stats["health"], "shield": stats["shield_health"]}
    enemy = {
        "hull": target.get("hull_hp", target.get("hp", 100000)),
        "shield": target.get("shield_hp", 0),
    }
    max_hull, max_shield = player["hull"], player["shield"]
    player["hull"] = min(max_hull, ship.get("current_hull", max_hull))
    player["shield"] = min(max_shield, ship.get("current_shield", max_shield))
    weapon_damage = stats["attack"]
    weapons = {
        "player": _weapons(ship, weapon_damage),
        "enemy": _weapons(target, target.get("base_damage", 8000)),
    }
    shield_mit = min(
        1,
        max(
            0, ship.get("shield_mitigation", 0.8) + effects.get("shield_mitigation", 0)
        ),
    )
    enemy_shield_mit = min(
        1,
        max(
            0,
            target.get("shield_mitigation", 0.8)
            - effects.get("enemy_shield_mitigation_down", 0),
        ),
    )
    effective_piercing = dict(target)
    for key in ("armor_piercing", "shield_piercing", "accuracy"):
        effective_piercing[key] = target.get(key, 0) * (
            1 - min(1, effects.get("enemy_piercing_down", 0))
        )
    mitigation = _mitigation(stats, effective_piercing, ship["ship_class"])
    enemy_mit = (
        _mitigation(
            target["defense_stats"], stats, target.get("ship_class", "Battleship")
        )
        if "defense_stats" in target
        else 0
    )

    critical = aggregate_crit_mitigation_sources(
        player_profile, task_type, ship, target=target
    )
    totals = {"hull": 0.0, "shield": 0.0}
    stacks, trace, rounds = [], {}, 0
    event_log = []
    morale_until = 0
    delayed_until = 0
    probe_shots = 0
    for rec in timed:
        if rec.get("model") == "defending_delay" and rng.random() < rec["chance"]:
            delayed_until = rec["duration"]
        if rec.get("model") == "probe_extra_shots" and rng.random() < rec["chance"]:
            probe_shots += rec["value"]
    previous_hull_damage = 0
    iso_bonus = (
        star.get("isolytic_damage_bonus", 0)
        + ship.get("isolytic_damage_bonus", 0)
        + effects.get("isolytic_damage", 0)
    )
    cascade = (
        star.get("isolytic_cascade_bonus", 0)
        + ship.get("isolytic_cascade_bonus", 0)
        + effects.get("isolytic_cascade", 0)
    )
    while (
        player["hull"] > 0
        and enemy["hull"] > 0
        and rounds < target.get("max_rounds", 100)
    ):
        rounds += 1
        stacks = [
            (effect, value, expiry)
            for effect, value, expiry in stacks
            if expiry >= rounds
        ]
        scoped, _ = source_effects(player_profile, ship, task_type, target, rounds)
        current = defaultdict(float, effects)
        for key, value in scoped.items():
            current[key] += value
        for effect, value, _ in stacks:
            current[effect] += value
        # Captain's Maneuver resolves before morale-dependent officer abilities.
        for rec in timed:
            if (
                rec.get("model") == "morale_round_start"
                and rng.random() < rec["chance"]
            ):
                morale_until = rounds + rec["duration"] - 1
        for rec in timed:
            if rec.get("model") == "morale_round_effect" and morale_until >= rounds:
                stacks.append(
                    (rec["effect"], rec["value"], rounds + rec["duration"] - 1)
                )
                current[rec["effect"]] += rec["value"]
        for rec in timed:
            if rec.get("trigger") == "combat_start" and rounds <= rec.get(
                "duration", 1
            ):
                current[rec["effect"]] += rec["value"]
            if rec.get("trigger") == "round_start":
                if rec["effect"] == "hull_repair":
                    player["hull"] = min(
                        max_hull, player["hull"] + previous_hull_damage * rec["value"]
                    )
                if rec["effect"] == "shield_repair":
                    player["shield"] = min(
                        max_shield, player["shield"] + max_shield * rec["value"]
                    )
        before_hull = player["hull"]
        decay_fraction = max(
            0,
            target.get("hyperthermic_decay_fraction", 0)
            - ship.get("hyperthermic_stabilizer", 0)
            - current.get("hyperthermic_stabilizer", 0),
        )
        basis = (
            player["hull"] if target.get("decay_basis") == "current_hull" else max_hull
        )
        decay = min(player["hull"], decay_fraction * basis)
        player["hull"] -= decay
        totals["hull"] += decay
        if decay and not trace:
            trace = {
                "raw": 0,
                "after_standard": 0,
                "after_apex": 0,
                "after_critical": 0,
                "isolytic": 0,
                "decay": decay,
                "is_critical": False,
            }
        if player["hull"] <= 0:
            break
        order = target.get("firing_order", ["player", "enemy"])
        for side in order:
            for weapon in weapons[side]:
                if player["hull"] <= 0 or enemy["hull"] <= 0:
                    break
                warmup, cooldown = (
                    weapon.get("warmup", 0),
                    max(1, weapon.get("cooldown", 1)),
                )
                if rounds <= warmup or (rounds - warmup - 1) % cooldown:
                    continue
                received = False
                shots = weapon.get("shots", 1)
                if side == "enemy" and rounds <= delayed_until:
                    continue
                if side == "player":
                    # Fractional shot rounding is provisional, explicitly disclosed.
                    shots = max(
                        0, int(shots * (1 + current.get("shot_bonus", 0))) + probe_shots
                    )
                if (
                    side == "enemy"
                    and task_type in {"pve_hostile", "pve_general"}
                    and identity(ship.get("name")) == "enterprisenx01"
                    and target.get("name") == "Xindi-Aquatic Cruiser"
                    and target.get("weapons")
                ):
                    # Polarized Hull removes nine shots per Aquatic weapon.
                    # Never infer a ten-shot schedule from aggregate damage.
                    shots = max(0, shots - 9)
                for _ in range(shots):
                    if player["hull"] <= 0 or enemy["hull"] <= 0:
                        break
                    is_enemy = side == "enemy"
                    owner = target if is_enemy else ship
                    weapon_chance = weapon.get("crit_chance")
                    if weapon_chance is None:
                        weapon_chance = owner.get("crit_chance", 0.2 if is_enemy else 0)
                    weapon_multiplier = weapon.get("crit_multiplier")
                    if weapon_multiplier is None:
                        weapon_multiplier = owner.get("crit_multiplier", 1.5)
                    chance = (
                        weapon_chance - current.get("enemy_crit_down", 0)
                        if is_enemy
                        else weapon_chance
                        + ship.get("crit_chance_bonus", 0)
                        + current.get("crit_chance", 0)
                    )
                    crit = rng.random() < min(1, max(0, chance))
                    multiplier = (
                        max(
                            target.get("critical_floor", 1),
                            weapon_multiplier
                            - current.get("enemy_crit_damage_down", 0),
                        )
                        if is_enemy
                        else max(
                            ship.get("critical_floor", 1),
                            weapon_multiplier
                            + ship.get("crit_damage_bonus", 0)
                            + current.get("crit_damage", 0),
                        )
                    )
                    raw = weapon["damage"] * (multiplier if crit else 1)
                    if side == "player" and ship.get("weapons"):
                        raw *= weapon_damage / max(ship["base_stats"]["attack"], 1)
                    if side == "player":
                        raw *= 1 + ship["base_stats"]["attack"] * max(
                            0,
                            current.get("weapon_damage", 0)
                            - stat_effects.get("weapon_damage", 0),
                        ) / max(weapon_damage, 1)
                    if is_enemy:
                        raw *= 1 - min(
                            1, current.get(f"enemy_{weapon.get('type')}_damage_down", 0)
                        )
                        iso = _iso(
                            raw,
                            target.get("isolytic_damage_bonus", 0),
                            target.get("isolytic_cascade_bonus", 0),
                            star.get("isolytic_defense_bonus", 0)
                            + current.get("isolytic_defense", 0),
                        )
                        standard = raw * (1 - mitigation)
                        apex = (
                            mirror.get("apex_barrier", 0)
                            + ship.get("apex_barrier", 0)
                            + current.get("apex_barrier", 0)
                        ) * (1 - min(1, target.get("apex_shred", 0)))
                        reduction = min(
                            1,
                            points_to_reduction(
                                critical["total_points"]
                                + current.get("crit_mitigation", 0)
                            )
                            + critical["legacy_reduction"],
                        )
                        destination, absorption = player, shield_mit
                    else:
                        iso = _iso(
                            raw,
                            iso_bonus
                            + current.get("isolytic_damage", 0)
                            - effects.get("isolytic_damage", 0),
                            cascade
                            + current.get("isolytic_cascade", 0)
                            - effects.get("isolytic_cascade", 0),
                            target.get("iso_defense", 0),
                        )
                        standard = (
                            0
                            if target.get(
                                "standard_damage_immune",
                                target.get("name") == "Gorn Hunter",
                            )
                            else raw * (1 - enemy_mit)
                        )
                        apex = target.get("apex_barrier", 0) * (
                            1
                            - min(
                                1,
                                star.get("apex_shred_bonus", 0)
                                + ship.get("apex_shred", 0)
                                + current.get("apex_shred", 0),
                            )
                        )
                        reduction = target.get(
                            "critical_mitigation_reduction",
                            points_to_reduction(
                                target.get("critical_mitigation_points", 0)
                            ),
                        )
                        destination, absorption = enemy, enemy_shield_mit
                    divisor = 1 + max(0, apex) / 10000
                    after_apex = standard / divisor
                    standard = after_apex * (1 - reduction if crit else 1)
                    iso /= divisor
                    # ISO critical-mitigation interaction remains an explicit scenario option.
                    if crit and target.get("critical_mitigation_affects_iso"):
                        iso *= 1 - reduction
                    hull, shield = _damage(destination, standard + iso, absorption)
                    if target.get("debug_events"):
                        event_log.append(
                            {
                                "round": rounds,
                                "side": side,
                                "critical": crit,
                                "crit_chance": chance,
                                "crit_multiplier": multiplier,
                                "morale": morale_until >= rounds,
                                "hull_damage": hull,
                                "shield_damage": shield,
                            }
                        )
                    if is_enemy:
                        received = received or hull + shield > 0
                        totals["hull"] += hull
                        totals["shield"] += shield
                        if not trace or trace.get("raw") == 0:
                            trace = {
                                "raw": raw,
                                "after_standard": raw * (1 - mitigation),
                                "after_apex": after_apex,
                                "after_critical": standard,
                                "isolytic": iso,
                                "decay": decay,
                                "is_critical": crit,
                                "round": rounds,
                                "units": "actual damage points",
                            }
                if received:
                    for rec in timed:
                        if rec.get(
                            "trigger"
                        ) == "received_weapon" and rng.random() < rec.get("chance", 1):
                            stacks.append(
                                (
                                    rec["effect"],
                                    rec["value"],
                                    rounds + rec.get("duration", 1) - 1,
                                )
                            )
                            current[rec["effect"]] += rec["value"]
            if player["hull"] <= 0 or enemy["hull"] <= 0:
                break
        previous_hull_damage = max(0, before_hull - player["hull"])
        if player["hull"] > 0:
            for rec in timed:
                if rec.get("trigger") == "round_end" and rec["effect"] == "hull_repair":
                    player["hull"] = min(
                        max_hull, player["hull"] + previous_hull_damage * rec["value"]
                    )
    return {
        "rounds_to_kill": rounds if enemy["hull"] <= 0 else None,
        "combat_rounds": rounds,
        "survived": player["hull"] > 0,
        "killed_target": enemy["hull"] <= 0,
        "timed_out": player["hull"] > 0 and enemy["hull"] > 0,
        "total_damage_taken": sum(totals.values()),
        "hull_damage_taken": totals["hull"],
        "hull_lost": max_hull - player["hull"],
        "hull_remaining": player["hull"],
        "shield_remaining": player["shield"],
        "effective_hp": max_hull
        * (
            1
            + (
                mirror.get("apex_barrier", 0)
                + ship.get("apex_barrier", 0)
                + stat_effects.get("apex_barrier", 0)
            )
            * (1 - min(1, target.get("apex_shred", 0)))
            / 10000
        ),
        "initial_critical_mitigation": min(
            1,
            points_to_reduction(
                critical["total_points"] + stat_effects.get("crit_mitigation", 0)
            )
            + critical["legacy_reduction"],
        ),
        "crew_scoped_critical_points": stat_effects.get("crit_mitigation", 0),
        "hull_max": max_hull,
        "standard_mitigation": mitigation,
        "isolytic_bonus": iso_bonus,
        "isolytic_cascade_bonus": cascade,
        "damage_trace": trace,
        "stat_warnings": stat_warnings,
        "events": event_log,
    }


def simulate_combat(
    ship,
    bridge_crew,
    below_deck_crew,
    player_profile,
    target_hostile,
    task_type,
    num_simulations=200,
    rng_seed=None,
):
    if not 1 <= num_simulations <= 10000:
        raise ValueError("Simulation count must be between 1 and 10000.")
    effects, timed, omissions = ability_plan(
        bridge_crew, below_deck_crew, task_type, target_hostile, ship
    )
    rng = random.Random(rng_seed)
    results = [
        _single_combat_run(
            ship,
            bridge_crew,
            below_deck_crew,
            player_profile,
            target_hostile,
            task_type,
            random.Random(rng.getrandbits(64)),
            effects,
            timed,
        )
        for _ in range(num_simulations)
    ]
    kills = sum(r["killed_target"] for r in results)
    survivors = sum(r["survived"] for r in results)
    kill_rounds = [r["rounds_to_kill"] for r in results if r["killed_target"]]
    limitations = (
        list(omissions)
        + results[0]["stat_warnings"]
        + list(target_hostile.get("missing_mechanics", []))
    )
    limitations.append(
        "Ship-specific passives, status chains, fleet commanders and artifacts require explicit supported source inputs; unrepresented effects are omitted."
    )
    limitations.append(
        "Empirical mitigation and shield splitting require battle-log calibration; these are model outcomes, not live win probabilities."
    )
    if not ship.get("weapons") or not target_hostile.get("weapons"):
        limitations.append(
            "Missing weapon schedule: one aggregate attack each round; firing order defaults to player first."
        )
    if not target_hostile.get("defense_stats"):
        limitations.append(
            "Opponent defense stats missing: standard mitigation omitted."
        )
    if "crit_chance" not in ship:
        limitations.append(
            "Player critical chance missing: zero used, not inferred from ship power."
        )
    if any(
        r.get("model") in {"morale_round_effect", "probe_extra_shots"} for r in timed
    ):
        limitations.append(
            "Status-dependent shot count uses floor rounding and export durations; proc timing and stacking require live battle-log calibration."
        )
    if results[0]["isolytic_cascade_bonus"] or any(
        r.get("effect") == "isolytic_cascade" for r in timed
    ):
        limitations.append(
            "Combined Cascade formula is community-derived and provisional."
        )
    if task_type in {
        "wave_defense",
        "duo_wave_defense",
        "pvp_station",
        "station_raid",
        "dreadnought",
        "galactic_anomaly",
    }:
        limitations.append(
            "Individual encounter only: complete waves, coordinated armadas, station hauling, navigation and event rewards are not simulated."
        )
    _, source_omissions = source_effects(
        player_profile, ship, task_type, target_hostile
    )
    limitations += source_omissions
    if (
        player_profile.get("research", {}).get("critical_mitigation")
        or effects.get("crit_mitigation")
        or target_hostile.get("critical_mitigation_points")
    ):
        limitations.append(
            "Critical Mitigation curve is provisional; ISO interaction requires a validated scenario setting."
        )
    avg = lambda key: round(sum(r[key] for r in results) / len(results), 2)
    return {
        "avg_rounds_to_kill": round(sum(kill_rounds) / len(kill_rounds), 2)
        if kill_rounds
        else None,
        "avg_combat_rounds": avg("combat_rounds"),
        "survival_probability": round(survivors / len(results) * 100, 2),
        "kill_probability": round(kills / len(results) * 100, 2),
        "timeout_probability": round(
            sum(r["timed_out"] for r in results) / len(results) * 100, 2
        ),
        "kill_interval_95": _wilson(kills, len(results)),
        "survival_interval_95": _wilson(survivors, len(results)),
        "loot_bonus": effects.get("loot", 0),
        "avg_damage_taken": avg("total_damage_taken"),
        "avg_hull_damage": avg("hull_damage_taken"),
        "avg_hull_lost": avg("hull_lost"),
        "effective_hp": results[0]["effective_hp"],
        "initial_critical_mitigation": results[0]["initial_critical_mitigation"],
        "crew_scoped_critical_points": results[0]["crew_scoped_critical_points"],
        "hull_max": results[0]["hull_max"],
        "simulation_count": num_simulations,
        "standard_mitigation": results[0]["standard_mitigation"],
        "isolytic_bonus": results[0]["isolytic_bonus"],
        "isolytic_cascade_bonus": results[0]["isolytic_cascade_bonus"],
        "damage_trace": results[0]["damage_trace"],
        "event_trace": results[0]["events"],
        "unmodelled_abilities": omissions,
        "limitations": sorted(set(limitations)),
        "coverage": "partial; not battle-log validated",
        "model": "Per-weapon two-pool estimate",
    }
