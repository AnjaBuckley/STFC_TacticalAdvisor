"""Greedy marginal below-deck selection with ship-specific officer stat caps.

This bounded search does not prove a globally optimal crew.
"""

from engine.abilities import load_abilities, officer_available


def optimize_below_deck(
    ship: dict,
    available_officers: list[dict],
    bridge_crew: list[dict],
    num_slots: int,
    task_profile: dict,
    player_profile: dict,
) -> list[dict]:
    if num_slots <= 0:
        return []

    bridge_names = {o["name"] for o in bridge_crew}
    candidates = [
        o
        for o in available_officers
        if o["name"] not in bridge_names and officer_available(o)
    ]
    task_type = task_profile.get("task_type", "pve_general")
    task_profile.get("target", {}).get("name", "").lower()

    from math import log1p

    from engine.catalogue import ship_stats
    from engine.effects import ability_plan

    selected = []
    target = task_profile.get("target", {})

    def utility(crew):
        effects, timed, _ = ability_plan(bridge_crew, crew, task_type, target, ship)
        stats, _, _ = ship_stats(ship, bridge_crew + crew, player_profile, effects)
        total = sum(
            log1p(stats.get(k, 0) / max(1, ship.get("base_stats", {}).get(k, 0)))
            for k in (
                "attack",
                "health",
                "shield_health",
                "armor",
                "shield_deflection",
                "dodge",
            )
        )
        for effect, value in effects.items():
            if effect == "loot" and task_profile.get("objective") != "loot":
                continue
            total += log1p(
                value / (10000 if effect in {"apex_barrier", "crit_mitigation"} else 1)
            )
        total += sum(log1p(r["value"] * r.get("chance", 1)) for r in timed)
        return total

    # Re-evaluate after every slot: officers above the catalogue cap cannot
    # displace a useful BDA merely because their raw stats are larger.
    for _ in range(min(num_slots, len(candidates))):
        best = max(candidates, key=lambda o: (utility(selected + [o]), o["name"]))
        selected.append(best)
        candidates.remove(best)
    return [{"name": o["name"], "function": _get_bda_description(o)} for o in selected]


def _get_bda_description(officer):
    rec = load_abilities().get(officer["name"], {}).get("bda")
    return (
        "BDA: " + rec["effect"].replace("_", " ") if rec else "Capped stat contribution"
    )
