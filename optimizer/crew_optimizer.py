"""Bounded crew search: supported-effects shortlist, then combat outcome ranking."""

from heapq import nlargest
from itertools import combinations

from engine.abilities import (
    load_abilities,
    officer_available,
)
from engine.combat_simulator import simulate_combat
from engine.critical_mitigation import aggregate_crit_mitigation_sources
from engine.stat_calculator import detect_dilution_warning
from engine.synergy import calc_synergy
from optimizer.below_deck import optimize_below_deck
from optimizer.scorer import score_combination

# Pre-filter: max bridge candidates before brute-force combo search.
# C(40,3) = 9,880 combos vs C(278,3) = 3.5M — keeps runtime under 1s.
_MAX_BRIDGE_CANDIDATES = 40

# Simulation pass: how many heuristic finalists get Monte Carlo simulated,
# how many runs each, and how heuristic vs simulated scores blend.
_SIM_TOP_K = 50
_SIM_RUNS = 150
_SIM_SEED = 42  # same random sequence for every candidate — fair ranking


def _prefilter_bridge_candidates(
    officers: list[dict], task_type: str, target: dict | None = None
) -> list[dict]:
    """Bounded candidate pool from supported effects and raw-stat tie breaks."""
    from math import log1p

    from engine.effects import ability_plan

    def _rank(o):
        static, timed, _ = ability_plan([o], [], task_type, target or {})
        supported = sum(
            log1p(v / (10000 if k in {"crit_mitigation", "apex_barrier"} else 1))
            for k, v in static.items()
        )
        supported += sum(log1p(r["value"] * r.get("chance", 1)) for r in timed)
        if o["name"] in {"SNW Pike", "SNW James Kirk"}:
            supported += 1
        return (
            supported,
            o.get("attack", 0) + o.get("defense", 0) + o.get("health", 0),
            o["name"],
        )

    ranked = sorted(officers, key=_rank, reverse=True)
    return ranked[:_MAX_BRIDGE_CANDIDATES]


def find_optimal_crew(
    player_profile: dict, task_profile: dict, top_n: int = 5
) -> list[dict]:

    if not 1 <= top_n <= 10:
        raise ValueError("Request between 1 and 10 recommendations.")
    all_officers = list(
        {
            o["name"]: o for o in player_profile["officers"] if officer_available(o)
        }.values()
    )
    if len(all_officers) < 3:
        raise ValueError(
            "At least three available officers are needed for a bridge crew."
        )
    available_ships = [
        s for s in player_profile["ships"] if _ship_valid_for_task(s, task_profile)
    ]
    ops_level = player_profile["ops_level"]
    task_type = task_profile.get("task_type", "pve_general")
    target = task_profile.get("target", {})
    if target.get("type") == "Academy Drone" and task_type not in {
        "pve_academy_drone",
        "duo_wave_defense",
    }:
        raise ValueError("Use the Academy drones mission type for this target.")
    if target.get("name") == "Duo Wave Defense" and task_type != "duo_wave_defense":
        raise ValueError("Use the Duo Wave Defense mission type for this target.")
    if task_type in {"pve_academy_drone", "duo_wave_defense"} and ops_level < 61:
        raise ValueError("Academy content requires Operations level 61 or above.")

    if not available_ships:
        raise ValueError("Add an owned combat ship before requesting recommendations.")
    # Pre-filter to a manageable bridge candidate pool
    bridge_candidates = _prefilter_bridge_candidates(
        all_officers, task_type, task_profile.get("target", {})
    )

    # Detect buff dilution for this account (ship-independent)
    research = player_profile.get("research", {})
    combat = research.get("combat", {}) if isinstance(research, dict) else {}
    total_buff = combat.get("total_officer_bonus", 0.0)
    dilution = detect_dilution_warning(total_buff, 0.10)

    recommendations = []

    finalists = []
    for ship in available_ships:
        recommendations = []
        below_deck_slots = _below_deck_slot_count(ship)

        crews = (
            (captain, *companions)
            for captain in bridge_candidates
            for companions in combinations(
                [o for o in bridge_candidates if o["name"] != captain["name"]], 2
            )
        )
        for captain, o1, o2 in crews:
            synergy = calc_synergy(captain, o1, o2)
            captain_kit = load_abilities().get(captain["name"])
            if captain_kit is not None and not captain_kit.get("cm"):
                synergy = {
                    "synergy_label": "NO CAPTAIN MANEUVER",
                    "maneuver_multiplier": 1.0,
                    "full_synergy": False,
                    "partial_synergy": False,
                }
            bridge_crew = [captain, o1, o2]

            score, reasoning = score_combination(
                ship=ship,
                bridge_crew=bridge_crew,
                synergy=synergy,
                task_profile=task_profile,
                player_profile=player_profile,
                ops_level=ops_level,
                dilution=dilution,
            )

            recommendations.append(
                {
                    "ship": ship["name"],
                    "captain": captain["name"],
                    "officer_1": o1["name"],
                    "officer_2": o2["name"],
                    "synergy": synergy["synergy_label"],
                    "score": score,
                    "reasoning": reasoning,
                    "_ship": ship,
                    "_bridge_crew": bridge_crew,
                    "_below_deck_slots": below_deck_slots,
                }
            )

            if len(recommendations) > 2000:
                recommendations = nlargest(
                    max(_SIM_TOP_K, top_n), recommendations, key=lambda r: r["score"]
                )
        finalists.extend(
            nlargest(max(_SIM_TOP_K, top_n), recommendations, key=lambda r: r["score"])
        )

    # Simulation pass: the heuristic score selects finalists, the combat
    # simulator re-ranks them by measured outcome (survival, kill speed).
    officers_by_name = {o["name"]: o for o in all_officers}

    for rec in finalists:
        ship = rec.pop("_ship")
        bridge_crew = rec.pop("_bridge_crew")

        # Below-deck optimization is a separate pass (CLAUDE.md rule 3)
        rec["below_deck"] = optimize_below_deck(
            ship=ship,
            available_officers=all_officers,
            bridge_crew=bridge_crew,
            num_slots=rec.pop("_below_deck_slots"),
            task_profile=task_profile,
            player_profile=player_profile,
        )
        below_deck_officers = [
            officers_by_name[s["name"]]
            for s in rec["below_deck"]
            if s["name"] in officers_by_name
        ]

        sim = simulate_combat(
            ship,
            bridge_crew,
            below_deck_officers,
            player_profile,
            task_profile.get("target", {}),
            task_type,
            num_simulations=_SIM_RUNS,
            rng_seed=_SIM_SEED,
        )
        sim_score = _sim_score(sim)

        rec["critical_mitigation"] = aggregate_crit_mitigation_sources(
            player_profile, task_type, ship, target=target
        )
        if sim["crew_scoped_critical_points"]:
            rec["critical_mitigation"]["sources"].append(
                {
                    "source": "Active crew and scoped inputs (initial round)",
                    "points": sim["crew_scoped_critical_points"],
                }
            )
        rec["critical_mitigation"]["total_crit_mitigation"] = sim[
            "initial_critical_mitigation"
        ]
        rec["search"] = {
            "bridge_candidates": len(bridge_candidates),
            "available_officers": len(all_officers),
            "method": "All captain assignments within shortlist; greedy marginal below-deck selection; model outcomes",
            "globally_optimal": False,
            "validated": False,
        }
        rec["heuristic_score"] = rec["score"]
        rec["simulation"] = sim
        rec["score"] = round(sim_score, 4)
        rec["reasoning"].append(
            f"Simulated ({_SIM_RUNS} runs): {sim['survival_probability']:.0f}% survival, "
            f"{sim['kill_probability']:.0f}% kill rate, "
            f"{sim['avg_combat_rounds']:.1f} avg rounds."
        )

        # Ship economics (CLAUDE.md rule 6): estimated repair cost per kill —
        # full repair cost scaled by the hull fraction lost, per successful kill
        repair_total = ship.get("repair_cost_total", 0)
        if repair_total and sim["hull_max"] and sim["kill_probability"] > 0:
            damage_fraction = min(1.0, sim["avg_hull_lost"] / sim["hull_max"])
            kill_rate = max(sim["kill_probability"] / 100, 0.01)
            cost_per_kill = repair_total * damage_fraction / kill_rate
            rec["cost_per_kill"] = round(cost_per_kill)
            rec["reasoning"].append(
                f"Economics: ~{cost_per_kill:,.0f} repair cost per kill "
                f"({damage_fraction:.0%} hull damage per fight)."
            )

    if task_profile.get("target", {}).get("standard_damage_immune"):
        finalists = [
            r
            for r in finalists
            if r["simulation"]["isolytic_bonus"] > 0
            or r["simulation"].get("isolytic_cascade_bonus", 0) > 0
        ]
        if not finalists:
            raise ValueError(
                "This target is immune to standard damage. No modelled Isolytic Damage "
                "source was found in the candidate builds. Add a supported isolytic officer "
                "or enter your ship/research isolytic bonus."
            )
    finalists.sort(
        key=lambda x: (
            x["simulation"]["kill_probability"],
            x["simulation"]["survival_probability"],
            -len(x["simulation"]["unmodelled_abilities"]),
            x["score"],
        ),
        reverse=True,
    )
    return finalists[:top_n]


def _sim_score(sim: dict) -> float:
    """Collapse simulation results into a 0–1 score.

    Survival dominates (a dead ship grinds nothing), then kill reliability,
    then speed (5 rounds or fewer = full marks)."""
    survival = sim["survival_probability"] / 100
    kill = sim["kill_probability"] / 100
    speed = (
        min(1.0, 5.0 / sim["avg_rounds_to_kill"]) if sim["avg_rounds_to_kill"] else 0.0
    )
    return kill * (survival * 0.5 + 0.3 + speed * 0.2)


def tier_for_level(level: int, max_tier: int) -> int:
    """Tier unlocks every 5 ship levels (verified: max_level/max_tier == 5
    across the stfc.space export)."""
    return max(1, min(max_tier, -(-level // 5)))


def _below_deck_slot_count(ship: dict) -> int:
    """
    An explicit "below_deck_slots" value on the ship (user override, set in
    the UI or hand-edited into the profile) always wins — the imported
    unlock tables are not reliable for every ship, and the player can just
    count the slots in their drydock.

    Otherwise, below-deck slots unlock by ship LEVEL (authoritative:
    data.stfc.space crew_slots). The table counts BELOW-DECK slots directly,
    NOT total officer slots: the 3 bridge seats are usable from level 1,
    while 112/114 ships in the export unlock their first crew_slots entry
    at level 5 — the table cannot be including the bridge. Verified in game:
    U.S.S. Athena at level 20 shows 3 below-deck slots, exactly the number
    of crew_slots entries unlocked at that level.
    Falls back to the legacy per-tier table for ships without that data.
    Syndicate levels grant stat buffs and presets, NO below-deck slots
    (verified against spocks.club/syndicate).
    """
    override = ship.get("below_deck_slots")
    if override is not None:
        return max(0, int(override))
    by_level = ship.get("below_deck_slots_by_level")
    if by_level:
        level = ship.get("level", 1)
        return sum(1 for unlock in by_level.values() if unlock <= level)
    return ship.get("below_deck_slots_by_tier", {}).get(str(ship.get("tier", 1)), 0)


def _ship_valid_for_task(ship: dict, task_profile: dict) -> bool:
    # A suggested combat-triangle class is a preference, never an ownership gate.
    return ship.get("available", True) and ship.get("ship_class") in {
        "Explorer",
        "Battleship",
        "Interceptor",
        "Survey",
    }
