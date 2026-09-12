"""Stable catalogue identities; no player ownership is inferred here."""

import json
import re
from functools import lru_cache
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data" / "stfc_space"
CLASSES = {0: "Interceptor", 1: "Survey", 2: "Explorer", 3: "Battleship"}


def identity(name):
    return re.sub(r"[^a-z0-9]", "", str(name).casefold())


@lru_cache(maxsize=1)
def ship_catalogue():
    names = {
        r["id"]: r["text"]
        for r in json.loads((BASE / "en_ships.json").read_text(encoding="utf-8"))
        if r["key"] == "ship_name"
    }
    result = {}
    for file in (BASE / "ship").glob("*.json"):
        data = json.loads(file.read_text(encoding="utf-8"))
        data["name"] = names.get(data["loca_id"], str(data["id"]))
        result[identity(data["name"])] = data
    return result


def ship_record(ship):
    if ship.get("catalogue_id") is not None:
        return next(
            (s for s in ship_catalogue().values() if s["id"] == ship["catalogue_id"]),
            {},
        )
    key = identity(ship.get("name"))
    key = {"eviscerator": "gorneviscerator"}.get(key, key)
    if key in ship_catalogue():
        return ship_catalogue()[key]
    matches = [
        v
        for k, v in ship_catalogue().items()
        if re.sub(r"^(uss|iks|iss)", "", k) == key
    ]
    return matches[0] if len(matches) == 1 else {}


def officer_bonus(points, table):
    """Piecewise-linear catalogue curve, capped at the final threshold.

    Interpolation is an explicit model assumption until calibrated in-game.
    The thresholds themselves are retained from the versioned ship export.
    """
    lower_x = lower_y = 0.0
    for row in sorted(table, key=lambda r: r["value"]):
        x, y = float(row["value"]), float(row["bonus"])
        if points <= x:
            return lower_y + (y - lower_y) * max(0, points - lower_x) / max(
                x - lower_x, 1
            )
        lower_x, lower_y = x, y
    return lower_y


def crew_stats(crew, profile):
    research = profile.get("research", {}).get("combat", {})
    totals = dict.fromkeys(("attack", "defense", "health"), 0.0)
    warnings = []
    for officer in crew:
        provenance = officer.get("stat_basis", "unknown")
        if provenance == "unknown":
            warnings.append(
                "Officer stat provenance is unknown; treating supplied values as account-adjusted (no second research multiplier)."
            )
        for stat, key in [
            ("attack", "atk_only_research"),
            ("defense", "def_only_research"),
            ("health", "hth_only_research"),
        ]:
            raw = officer.get(stat, officer.get("stats", {}).get(stat, 0))
            multiplier = (
                1 + research.get("all_research", 0) + research.get(key, 0)
                if provenance == "base"
                else 1
            )
            totals[stat] += raw * multiplier
    return totals, sorted(set(warnings))


def ship_stats(ship, crew, profile, effects=None):
    effects = effects or {}
    totals, warnings = crew_stats(crew, profile)
    record = ship_record(ship)
    tables = ship.get("officer_bonus", record.get("officer_bonus", {}))
    bonuses = {k: officer_bonus(v, tables.get(k, [])) for k, v in totals.items()}
    if not tables and crew:
        warnings.append(
            "Ship officer-bonus table unavailable; officer stat-to-ship bonuses are omitted, not added as raw damage or HP."
        )
    c = profile.get("research", {}).get("combat", {})
    b = ship["base_stats"]
    displayed = ship.get("stat_basis") == "displayed"
    result = {}
    for stat, research, officer_stat, effect in [
        ("attack", "ship_weapon_damage", "attack", "weapon_damage"),
        ("health", "ship_hull_health", "health", "hull_health"),
        ("shield_health", "ship_shield_health", "health", "shield_health"),
        ("armor", "ship_armor", "defense", "armor"),
        ("shield_deflection", "ship_shield_deflection", "defense", "shield_deflection"),
        ("dodge", "ship_dodge", "defense", "dodge"),
        ("armor_piercing", "ship_armor_piercing", "attack", "armor_piercing"),
        ("shield_piercing", "ship_shield_piercing", "attack", "shield_piercing"),
        ("accuracy", "ship_accuracy", "attack", "accuracy"),
    ]:
        multiplier = (
            1 if displayed else 1 + c.get(research, 0) + bonuses.get(officer_stat, 0)
        )
        result[stat] = b.get(stat, 0) * max(0, multiplier + effects.get(effect, 0))
    if displayed:
        warnings.append(
            "Displayed ship stats include the existing crew; comparisons cannot reconstruct an uncrewed base. Enter base stats for crew comparisons."
        )
    if "shield_health" not in b:
        warnings.append("Player shield health is missing; a zero shield pool is used.")
    return result, totals, sorted(set(warnings))
