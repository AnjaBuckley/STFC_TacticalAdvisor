"""Shared application service: validated profiles, catalogues and mission context."""

import copy
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import RLock

import paths
from engine.hostile_stats import enrich_target

PROFILE_LOCK = RLock()
TASKS = {
    "pve_hostile": "Hostile grinding",
    "pvp": "Player combat",
    "pvp_station": "Base hitting",
    "station_raid": "Station raid · combat only",
    "wave_defense": "Solo wave · individual encounter",
    "duo_wave_defense": "Duo wave · individual encounter",
    "pve_academy_drone": "Academy drones",
    "galactic_anomaly": "Anomaly · individual encounter",
    "dreadnought": "Dreadnought · individual ship estimate",
}


def read_profile():
    with PROFILE_LOCK:
        raw = paths.profile_path().read_bytes()
        return json.loads(raw), hashlib.sha256(raw).hexdigest()


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise TypeError("The profile must be a JSON object.")
    if "ops_level" not in profile:
        raise ValueError("The profile needs an Operations level (ops_level).")

    def finite_tree(value):
        if isinstance(value, float) and (not math.isfinite(value) or value < 0):
            raise ValueError("Profile numbers must be finite and nonnegative.")
        if isinstance(value, dict):
            for child in value.values():
                finite_tree(child)
        if isinstance(value, list):
            for child in value:
                finite_tree(child)

    finite_tree(profile)
    from engine.sources import validate_sources

    validate_sources(profile.get("combat_sources", []))
    for ship in profile.get("ships", []):
        validate_sources(ship.get("combat_sources", []))
    for key, lo, hi in [("ops_level", 1, 100), ("syndicate_level", 0, 200)]:
        v = profile.get(key, lo)
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise ValueError(f"{key} must be an integer between {lo} and {hi}.")
    if not isinstance(profile.get("research", {}), dict):
        raise TypeError("Research must be an object.")
    for section in ("combat", "mirror_tree", "star_path", "critical_mitigation"):
        if not isinstance(profile.get("research", {}).get(section, {}), dict):
            raise TypeError(f"Research {section} must be an object.")

    def numeric(data, fields, maximum=1e18):
        for field in fields:
            if field not in data:
                continue
            value = data[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= maximum
            ):
                raise ValueError(
                    f"{field} must be a finite nonnegative number up to {maximum:g}."
                )

    research = profile.get("research", {})
    numeric(
        research.get("combat", {}),
        (
            "all_research",
            "atk_only_research",
            "def_only_research",
            "hth_only_research",
            "total_officer_bonus",
            "ship_weapon_damage",
            "ship_hull_health",
            "ship_shield_health",
            "ship_armor",
            "ship_shield_deflection",
            "ship_dodge",
            "ship_armor_piercing",
            "ship_shield_piercing",
            "ship_accuracy",
        ),
    )
    numeric(research.get("mirror_tree", {}), ("apex_barrier",))
    numeric(
        research.get("star_path", {}),
        ("isolytic_damage_bonus", "isolytic_defense_bonus", "apex_shred_bonus"),
    )
    numeric(
        research.get("critical_mitigation", {}),
        ("remote_campus_points", "programmable_matter_beam_points"),
    )
    numeric(
        research.get("critical_mitigation", {}),
        ("remote_campus_bonus", "programmable_matter_beam_value"),
        1,
    )
    for key in ("ships", "officers"):
        entries = profile.get(key)
        if not isinstance(entries, list) or len(entries) > 1000:
            raise ValueError(f"{key} must be a list of up to 1,000 entries.")
        names = set()
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("name"), str)
                or not entry["name"].strip()
            ):
                raise ValueError(f"Each {key} entry needs a name.")
            if entry["name"] in names:
                raise ValueError(f"Duplicate {key} entry: {entry['name']}.")
            names.add(entry["name"])
            if "available" in entry and not isinstance(entry["available"], bool):
                raise TypeError("Availability must be true or false.")
            numeric(entry, ("attack", "health", "defense", "attack_bonus"))
            if key == "officers":
                if not isinstance(entry.get("stats", {}), dict):
                    raise TypeError("Officer stats must be an object.")
                numeric(entry.get("stats", {}), ("attack", "health", "defense"))
                numeric(entry, ("rank", "tier", "level"), 200)
                if entry.get("stat_basis", "unknown") not in {
                    "unknown",
                    "base",
                    "account_adjusted",
                }:
                    raise ValueError(
                        "Officer stat basis must be unknown, base or account_adjusted."
                    )
                for text_field in ("group", "class", "description", "rarity"):
                    if entry.get(text_field) is not None and not isinstance(
                        entry[text_field], str
                    ):
                        raise TypeError(f"Officer {text_field} must be text.")
            if key == "ships":
                from engine.technology import validate_technologies

                if "technologies" in entry:
                    validate_technologies(entry["technologies"])
                if not isinstance(entry.get("research_bonuses", {}), dict):
                    raise TypeError("Ship research bonuses must be an object.")
                numeric(
                    entry.get("research_bonuses", {}),
                    (
                        "ship_weapon_damage",
                        "ship_hull_health",
                        "ship_shield_health",
                        "ship_armor",
                        "ship_shield_deflection",
                        "ship_dodge",
                        "ship_armor_piercing",
                        "ship_shield_piercing",
                        "ship_accuracy",
                    ),
                )

                if not isinstance(entry.get("base_stats"), dict):
                    raise TypeError("Ship base stats must be an object.")
                numeric(
                    entry["base_stats"],
                    ("armor_piercing", "shield_piercing", "accuracy", "shield_health"),
                )
                numeric(
                    entry,
                    (
                        "crit_mitigation_points",
                        "isolytic_damage_bonus",
                        "repair_cost_total",
                    ),
                )
                numeric(
                    entry,
                    ("crit_mitigation_bonus", "crit_chance", "crit_chance_bonus"),
                    1,
                )
                numeric(
                    entry,
                    (
                        "crit_multiplier",
                        "crit_damage_bonus",
                        "critical_floor",
                        "isolytic_cascade_bonus",
                        "hyperthermic_stabilizer",
                        "apex_barrier",
                        "current_hull",
                        "current_shield",
                    ),
                )
                numeric(entry, ("shield_mitigation", "apex_shred"), 1)
                if entry.get("stat_basis", "base") not in {"base", "displayed"}:
                    raise ValueError("Ship stat basis must be base or displayed.")
                if "weapons" in entry:
                    weapons = entry["weapons"]
                    if not isinstance(weapons, list) or not 1 <= len(weapons) <= 20:
                        raise ValueError("A weapon schedule needs 1–20 weapons.")
                    for weapon in weapons:
                        if not isinstance(weapon, dict) or "damage" not in weapon:
                            raise ValueError("Each weapon requires damage.")
                        numeric(weapon, ("damage",))
                        if weapon.get("crit_chance") is not None:
                            numeric(weapon, ("crit_chance",), 1)
                        if weapon.get("crit_multiplier") is not None:
                            numeric(weapon, ("crit_multiplier",), 1000)
                            if weapon["crit_multiplier"] < 1:
                                raise ValueError(
                                    "Weapon critical multiplier must be at least one."
                                )
                        for field, minimum, maximum in [
                            ("shots", 1, 50),
                            ("warmup", 0, 100),
                            ("cooldown", 1, 100),
                        ]:
                            value = weapon.get(field, minimum)
                            if (
                                isinstance(value, bool)
                                or not isinstance(value, int)
                                or not minimum <= value <= maximum
                            ):
                                raise ValueError(
                                    f"Weapon {field} outside supported bounds."
                                )
                for table in ("below_deck_slots_by_level", "below_deck_slots_by_tier"):
                    if table in entry:
                        if not isinstance(entry[table], dict):
                            raise TypeError(f"{table} must be an object.")
                        numeric(entry[table], entry[table].keys(), 200)
                if entry.get("ship_class") not in {
                    "Explorer",
                    "Interceptor",
                    "Battleship",
                    "Survey",
                }:
                    raise ValueError(
                        "Ship class must be Explorer, Interceptor, Battleship or Survey."
                    )
                for stat in ("attack", "health", "armor", "shield_deflection", "dodge"):
                    value = entry.get("base_stats", {}).get(stat)
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or value < 0
                    ):
                        raise ValueError(
                            f"{entry['name']}: {stat} must be a nonnegative number."
                        )
                if entry["base_stats"]["health"] <= 0:
                    raise ValueError("Ship hull health must be greater than zero.")
                for field, maximum in (
                    ("level", 200),
                    ("tier", 30),
                    ("below_deck_slots", 20),
                ):
                    v = entry.get(field, 1)
                    if (
                        not isinstance(v, int)
                        or isinstance(v, bool)
                        or not 0 <= v <= maximum
                    ):
                        raise ValueError(
                            f"{field} must be an integer from 0 to {maximum}."
                        )
    return profile


def save_profile(profile, revision):
    validate_profile(profile)
    with PROFILE_LOCK:
        _, current = read_profile()
        if current != revision:
            raise FileExistsError(
                "The account changed since you opened it. Reload before saving."
            )
        path = paths.profile_path()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        backup = path.with_name(f"player_profile.backup-{stamp}.json")
        backup.write_bytes(path.read_bytes())
        fd, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(
                    profile, stream, ensure_ascii=False, indent=2, allow_nan=False
                )
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)
        return read_profile()[1]


@lru_cache(maxsize=1)
def catalog():
    hostiles = json.loads(
        paths.resource_path("data", "hostiles.json").read_text(encoding="utf-8")
    )
    for target in hostiles:
        if target["name"] == "Gorn Hunter":
            target["standard_damage_immune"] = True
            target["notes"] = (
                "Immune to standard damage. Bring Isolytic Damage; incoming isolytic magnitude needs battle-log verification."
            )
        if target["type"] == "Academy Drone":
            target["minimum_ops"] = 61
            if target.get("ship_class") == "Explorer":
                target["standard_damage_immune"] = True
    base = paths.resource_path("data", "stfc_space")
    ships = []
    factions = {
        r["id"]: r["text"]
        for r in json.loads((base / "en_factions.json").read_text(encoding="utf-8"))
        if r["key"] == "faction_name"
    }
    names = {
        r["id"]: r["text"]
        for r in json.loads((base / "en_ships.json").read_text(encoding="utf-8"))
        if r["key"] == "ship_name"
    }
    for file in sorted((base / "ship").glob("*.json")):
        d = json.loads(file.read_text(encoding="utf-8"))
        if d.get("loca_id") not in names:
            continue
        ships.append(
            {
                "name": names[d["loca_id"]],
                "catalogue_id": d["id"],
                "ship_class": {
                    0: "Interceptor",
                    1: "Survey",
                    2: "Explorer",
                    3: "Battleship",
                }.get(d["hull_type"], "Survey"),
                "grade": d["grade"],
                "rarity": d.get("rarity"),
                "faction": factions.get((d.get("faction") or {}).get("loca_id"), ""),
                "max_tier": d["max_tier"],
                "max_level": d.get("max_level", 65),
                "below_deck_slots_by_level": {
                    str(s["slots"]): s["unlock_level"] for s in d.get("crew_slots", [])
                },
            }
        )
    from engine.hostile_stats import load_hostile_stats

    for target in hostiles:
        target["variants"] = [
            {k: v[k] for k in ("id", "level", "strength")}
            for v in load_hostile_stats().get(target["name"], [])
        ]
    return {"tasks": TASKS, "hostiles": hostiles, "ships": ships}


def mission_target(task, target_name, level, enemy_class, overrides, hostile_id=None):
    if task in {"pvp", "pvp_station", "station_raid"}:
        target = {
            "name": "Enemy player" if task == "pvp" else "Player station",
            "type": "PvP",
            "ship_class": enemy_class,
            "level": level,
        }
        if (
            not overrides
            or not overrides.get("hp")
            or overrides.get("base_damage") is None
        ):
            raise ValueError(
                "Enter opponent hull health and damage per round; enter shield health separately."
            )
    else:
        target = next(
            (
                copy.deepcopy(t)
                for t in catalog()["hostiles"]
                if t["name"] == target_name
            ),
            None,
        )
        if target is None:
            raise ValueError("Choose a known target from the mission catalogue.")
        types = {"pve_academy_drone": "Academy Drone", "dreadnought": "Dreadnought"}
        if task in types and target["type"] != types[task]:
            raise ValueError("This target does not match the selected mission.")
        if task == "pve_hostile" and target["type"] in {
            "Academy Drone",
            "Wave Defense",
            "Galactic Anomaly",
            "Dreadnought",
        }:
            raise ValueError("Choose the dedicated mission type for this target.")
        target = enrich_target(target, level, hostile_id)
    if overrides:
        target.update(overrides)
        if "hp" in overrides:
            target["hull_hp"] = overrides["hp"]
        defense = {
            k: target.pop(k)
            for k in ("armor", "shield_deflection", "dodge")
            if k in target
        }
        if defense:
            target["defense_stats"] = {**target.get("defense_stats", {}), **defense}
    if task in {"wave_defense", "duo_wave_defense"}:
        target["encounter_context"] = "wave_defense"

    if target.get("standard_damage_immune") is None:
        target.pop("standard_damage_immune", None)
    return target
