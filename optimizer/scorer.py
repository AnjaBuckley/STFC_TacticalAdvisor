"""Supported-effects shortlist proxy; final ranking uses combat outcomes."""


def score_combination(
    ship, bridge_crew, synergy, task_profile, player_profile, ops_level, dilution
):
    """Shortlist proxy using only effects the simulator can represent.

    This is not a game formula. Final ranking uses simulated outcomes.
    Unknown effects, group names and Operations level confer no bonus.
    """
    from math import log1p

    from engine.catalogue import ship_stats
    from engine.effects import ability_plan

    effects, timed, omissions = ability_plan(
        bridge_crew,
        [],
        task_profile.get("task_type", "pve_general"),
        task_profile.get("target", {}),
    )
    stats, _, _ = ship_stats(ship, bridge_crew, player_profile, effects)
    base = ship.get("base_stats", {})
    score = sum(
        log1p(stats.get(k, 0) / max(1, base.get(k, 0)))
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
        score += log1p(
            value / (10000 if effect in {"apex_barrier", "crit_mitigation"} else 1)
        )
    for event in timed:
        score += log1p(event["value"] * event.get("chance", 1))
    return score, [
        "Shortlisted using modelled ability values and capped officer-stat conversion. Final rank uses estimated combat outcomes.",
        *omissions,
    ]
