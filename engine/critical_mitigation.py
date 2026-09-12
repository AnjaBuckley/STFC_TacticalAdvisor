"""Scoped critical mitigation; sources and legacy units are in docs/RULES.md.

The points curve reproduces Scopely's worked 83,000 → 62.41% example.
Old decimal fields remain explicit effective-reduction overrides.
"""

import math
import re

PVP_TASKS = {"pvp", "pvp_station", "station_raid"}
ACADEMY_TASKS = {"pve_academy_drone", "duo_wave_defense"}
SIMULACRUM_ELIGIBLE_SHIPS = ["Epic G6 FKR", "Uncommon G7 FKR", "U.S.S. Vengeance"]


def points_to_reduction(points: float) -> float:
    if not math.isfinite(points) or points < 0:
        raise ValueError("Critical Mitigation points must be finite and nonnegative.")
    return points / (points + 50000.0)


def _normalize_ship_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def calc_critical_mitigation(
    incoming_crit_damage: float, crit_mitigation_value: float
) -> dict:
    """Apply a resolved decimal reduction after mitigation and Apex."""
    if not all(
        math.isfinite(v) and v >= 0
        for v in (incoming_crit_damage, crit_mitigation_value)
    ):
        raise ValueError(
            "Critical damage and mitigation must be finite and nonnegative."
        )
    reduction = min(crit_mitigation_value, 1.0)
    final = incoming_crit_damage * (1 - reduction)
    return {
        "incoming_crit_damage": round(incoming_crit_damage, 2),
        "crit_mitigation_value": round(reduction * 100, 2),
        "final_crit_damage": round(final, 2),
        "damage_prevented": round(incoming_crit_damage - final, 2),
    }


def aggregate_crit_mitigation_sources(
    player_profile: dict, task_type: str, active_ship: dict | None = None
) -> dict:
    research = player_profile.get("research", {}).get("critical_mitigation", {})
    sources, warnings = [], []
    points = legacy = 0.0

    def add(name, data, points_key, legacy_key):
        nonlocal points, legacy
        if points_key in data:
            value = float(data[points_key])
            points_to_reduction(value)
            if value:
                points += value
                sources.append({"source": name, "points": value})
        else:
            value = float(data.get(legacy_key, 0))
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} legacy reduction must be between 0 and 1.")
            if value:
                legacy += value
                sources.append({"source": name, "value": value, "legacy": True})

    if task_type in ACADEMY_TASKS:
        add("Remote Campus", research, "remote_campus_points", "remote_campus_bonus")
    if task_type in PVP_TASKS and research.get("programmable_matter_beam"):
        add(
            "Programmable Matter Beam",
            research,
            "programmable_matter_beam_points",
            "programmable_matter_beam_value",
        )
    ship = (
        active_ship
        if active_ship is not None
        else player_profile.get("active_ship", {})
    )
    name = _normalize_ship_name(ship.get("name", ""))
    eligible = name in {_normalize_ship_name(n) for n in SIMULACRUM_ELIGIBLE_SHIPS}
    eligible |= ship.get("faction") in {"Federation", "Klingon", "Romulan"} and (
        (ship.get("grade") == 6 and ship.get("rarity") in {"Epic", "E"})
        or (ship.get("grade") == 7 and ship.get("rarity") in {"Uncommon", "U"})
    )
    if (
        ship.get("simulacrum_refit")
        and eligible
        and task_type in PVP_TASKS | ACADEMY_TASKS
    ):
        add("Simulacrum Refit", ship, "crit_mitigation_points", "crit_mitigation_bonus")
    total = min(1.0, points_to_reduction(points) + legacy)
    if task_type == "duo_wave_defense" and total == 0:
        warnings.append(
            "CRITICAL WARNING: Duo Wave Defense needs an applicable Critical Mitigation source."
        )
    elif task_type == "pve_academy_drone" and total == 0:
        warnings.append(
            "Academy drones deal heavy critical damage. Enter Remote Campus mitigation points."
        )
    return {
        "total_crit_mitigation": round(total, 6),
        "total_points": points,
        "sources": sources,
        "warnings": warnings,
        "legacy_override": legacy > 0,
    }
