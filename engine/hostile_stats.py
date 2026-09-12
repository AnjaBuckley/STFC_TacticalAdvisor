"""
Real Hostile Stats — STFC

Enriches the curated targets in data/hostiles.json with real per-level combat
stats from data/hostile_stats.json (built by fetch_stfc_space.py
--hostile-stats from the data.stfc.space game database).

The curated entry stays the task template (type, counters, crit-mitigation
requirements, notes); this module overwrites its combat numbers with the
real hostile variant closest to the requested level.
"""

import json
from functools import lru_cache
from pathlib import Path

_STATS_PATH = Path(__file__).parent.parent / "data" / "hostile_stats.json"


@lru_cache(maxsize=1)
def load_hostile_stats() -> dict:
    if not _STATS_PATH.exists():
        return {}
    return json.loads(_STATS_PATH.read_text(encoding="utf-8")).get("targets", {})


def enrich_target(target: dict, level: int | None = None) -> dict:
    """
    Return a copy of the curated target with real combat stats merged in.

    Picks the variant closest to `level`; defaults to the top of the
    curated level_range (grinders typically farm the highest level they
    can handle). Targets without real data are returned unchanged.
    """
    target = dict(target)
    if target.get("name") == "Gorn Hunter":
        target["standard_damage_immune"] = True
    if target.get("type") == "Academy Drone" and target.get("ship_class") == "Explorer":
        target["standard_damage_immune"] = True
    variants = load_hostile_stats().get(target.get("name", ""))
    if not variants:
        return target

    if level is None:
        level = target.get("level_range", [0, 60])[1]
    best = min(variants, key=lambda v: abs(v["level"] - level))

    enriched = dict(target)
    enriched.update(
        {
            "hp": best["hull_hp"] + best["shield_hp"],
            "base_damage": best["dpr"],
            "armor_piercing": best["armor_piercing"],
            "shield_piercing": best["shield_piercing"],
            "accuracy": best["accuracy"],
            "crit_chance": best["critical_chance"],
            "crit_multiplier": best["critical_damage"],
            "defense_stats": {
                "armor": best["armor"],
                "shield_deflection": best["absorption"],
                "dodge": best["dodge"],
            },
            "real_hostile": {
                "name": best["real_name"],
                "level": best["level"],
                "strength": best["strength"],
            },
        }
    )
    return enriched
