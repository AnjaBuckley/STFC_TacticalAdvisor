"""Exact hostile selection: never combine a label's class with another enemy."""

import json
from functools import lru_cache
from pathlib import Path

_STATS_PATH = Path(__file__).resolve().parents[1] / "data" / "hostile_stats.json"


@lru_cache(maxsize=1)
def load_hostile_stats():
    return json.loads(_STATS_PATH.read_text(encoding="utf-8")).get("targets", {})


def enrich_target(target, level=None, hostile_id=None):
    target = dict(target)
    variants = load_hostile_stats().get(target.get("name"))
    if not variants:
        target.setdefault(
            "missing_mechanics", ["No exact hostile record; manual encounter only"]
        )
        return target
    if level is None:
        level = max(v["level"] for v in variants)
    matches = [
        v
        for v in variants
        if v["level"] == level and (hostile_id is None or v["id"] == hostile_id)
    ]
    if not matches:
        levels = ", ".join(map(str, sorted({v["level"] for v in variants})))
        raise ValueError(
            f"No exact {target['name']} at level {level}. Available levels: {levels}."
        )
    if len(matches) > 1:
        ids = ", ".join(str(v["id"]) for v in matches)
        raise ValueError(
            f"Several variants match this level. Select a hostile ID: {ids}."
        )
    best = matches[0]
    target.update(
        hp=best["hull_hp"],
        hull_hp=best["hull_hp"],
        shield_hp=best["shield_hp"],
        base_damage=best["dpr"],
        ship_class=best["ship_class"],
        level=best["level"],
        hostile_id=best["id"],
        armor_piercing=best["armor_piercing"],
        shield_piercing=best["shield_piercing"],
        accuracy=best["accuracy"],
        crit_chance=min(
            1, best["critical_chance"] + target.get("crit_chance_bonus", 0)
        ),
        crit_multiplier=max(
            target.get("critical_floor", 1),
            best["critical_damage"] + target.get("crit_damage_bonus", 0),
        ),
        defense_stats={
            "armor": best["armor"],
            "shield_deflection": best["absorption"],
            "dodge": best["dodge"],
        },
        real_hostile={
            "id": best["id"],
            "name": best["real_name"],
            "level": best["level"],
            "strength": best["strength"],
            "ship_class": best["ship_class"],
        },
        data_version="snapshot; not a live-game validation",
    )
    if best["real_name"] == "Gorn Hunter":
        target["standard_damage_immune"] = True
    return target
