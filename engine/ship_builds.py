"""Reproducible uncrewed ship builds from the bundled public component snapshot."""

import json
import re
from functools import lru_cache

from engine.catalogue import BASE, CLASSES, identity, ship_record


@lru_cache(maxsize=1)
def reference_data():
    path = BASE.parent / "ship_sheet_reference.json"
    return (
        json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"ships": {}}
    )


@lru_cache(maxsize=1)
def ability_texts():
    return {
        (row["id"], row["key"]): re.sub(r"<[^>]+>", "", row["text"]).replace(
            "\\n", "\n"
        )
        for row in json.loads((BASE / "en_ship_buffs.json").read_text(encoding="utf-8"))
    }


def catalogue_reference(record, level):
    texts = ability_texts()

    def describe(item, selected=False):
        loca = item.get("loca_id")
        values = item.get("values", [])
        return {
            "id": item["id"],
            "name": texts.get((loca, "ship_ability_name"), str(item["id"])),
            "description": texts.get(
                (loca, "ship_ability_desc"), "Description unavailable in snapshot."
            ),
            "level_value": values[level - 1]
            if selected and len(values) >= level
            else None,
        }

    return {
        "abilities": [describe(item, True) for item in record.get("ability", [])],
        "active_abilities": [describe(item) for item in record.get("asa", [])],
        "refits": [describe(item) for item in record.get("refits", [])],
        "crew_slots": record.get("crew_slots", []),
        "officer_bonus": record.get("officer_bonus", {}),
        "coverage": "Catalogue references do not establish ownership or automatically enable ability/refit effects. Values retain native export units; placeholders are not interpreted as combat formulas.",
    }


def build_ship(name, level, tier, component_tiers=None):
    record = ship_record({"name": name})
    if not record:
        raise ValueError("Ship is not in the bundled catalogue; use manual stats.")
    levels = {r["level"]: r for r in record["levels"]}
    tiers = {r["tier"]: r for r in record["tiers"]}
    if level not in levels or tier not in tiers:
        raise ValueError(
            "Select an exact catalogue level and tier; values are not extrapolated."
        )
    overrides = component_tiers or {}
    components = tiers[tier]["components"]
    if any(str(i) not in {str(n) for n in range(len(components))} for i in overrides):
        raise ValueError("Unknown component slot.")
    chosen, slots = [], []
    for index, component in enumerate(components):
        selected = overrides.get(str(index), tier)
        choices = [tier]
        next_parts = tiers.get(tier + 1, {}).get("components", [])
        if (
            len(next_parts) == len(components)
            and next_parts[index]["data"]["tag"] == component["data"]["tag"]
            and next_parts[index]["id"] != component["id"]
        ):
            choices.append(tier + 1)
        if selected not in choices:
            raise ValueError(
                "Component upgrade must belong to the selected tier or its next upgrade."
            )
        part = tiers[selected]["components"][index]
        chosen.append(part["data"])
        slots.append(
            {
                "slot": str(index),
                "label": f"{component['data']['tag']} {index + 1}",
                "tiers": choices,
                "selected": selected,
            }
        )

    def part(tag):
        return next((p for p in chosen if p["tag"] == tag), {})

    weapons = []
    for w in chosen:
        if w["tag"] != "Weapon":
            continue
        if w.get("weapon_type") not in (1, 2) or w["warm_up"] < 1 or w["cool_down"] < 1:
            raise ValueError(
                "Unsupported weapon schedule; enter a reviewed manual build."
            )
        weapons.append(
            {
                "damage": (w["minimum_damage"] + w["maximum_damage"]) / 2,
                "shots": w["shots"],
                "warmup": w["warm_up"] - 1,
                "cooldown": w["cool_down"],
                "type": "energy" if w["weapon_type"] == 1 else "kinetic",
                "crit_chance": w["crit_chance"],
                "crit_multiplier": w["crit_modifier"],
            }
        )
    weapon_parts = [p for p in chosen if p["tag"] == "Weapon"]

    def average(key):
        return (
            sum(p[key] for p in weapon_parts) / len(weapon_parts) if weapon_parts else 0
        )

    stats = {
        "attack": sum(w["damage"] * w["shots"] / w["cooldown"] for w in weapons),
        "health": part("Armor").get("hp", 0) + levels[level]["health"],
        "shield_health": part("Shield").get("hp", 0) + levels[level]["shield"],
        "armor": part("Armor").get("plating", 0),
        "shield_deflection": part("Shield").get("absorption", 0),
        "dodge": part("Impulse").get("dodge", 0),
        "accuracy": average("accuracy"),
        "armor_piercing": average("penetration"),
        "shield_piercing": average("modulation"),
    }
    manifest_path = BASE / "SHIP_SNAPSHOT.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    ref = reference_data()["ships"].get(identity(record["name"]), {})
    if not ref:
        key = re.sub(r"^(uss|iks|iss|ecs)", "", identity(record["name"]))
        ref = reference_data()["ships"].get(key, {})
    ability = ref.get("ability", {})
    factions = {
        r["id"]: r["text"]
        for r in json.loads((BASE / "en_factions.json").read_text(encoding="utf-8"))
        if r["key"] == "faction_name"
    }
    result = {
        "name": record["name"],
        "catalogue_id": record["id"],
        "grade": record["grade"],
        "faction": factions.get((record.get("faction") or {}).get("loca_id"), ""),
        "rarity": record["rarity"],
        "ship_class": CLASSES[record["hull_type"]],
        "level": level,
        "tier": tier,
        "stat_basis": "base",
        "base_stats": stats,
        "component_tiers": {s["slot"]: s["selected"] for s in slots},
        "crit_chance": average("crit_chance"),
        "crit_multiplier": average("crit_modifier"),
        "shield_mitigation": part("Shield").get("mitigation", 0.8),
        "warp_range": part("Warp").get("distance", 0),
        "warp_speed": part("Warp").get("speed", 0),
        "impulse_speed": part("Impulse").get("impulse", 0),
        "cargo_capacity": part("Cargo").get("max_resources", 0)
        + sum(t["buffs"].get("cargo", 0) for t in record["tiers"] if t["tier"] <= tier),
        "protected_cargo": part("Cargo").get("protected", 0)
        + sum(
            t["buffs"].get("protected", 0) for t in record["tiers"] if t["tier"] <= tier
        ),
        "stat_source": {
            "provider": "STFC Space",
            "version": manifest.get("version", "legacy snapshot"),
            "url": f"https://stfc.space/ships/{record['id']}",
            "build": {"level": level, "tier": tier},
            "basis": "components plus exported level health/shield bonuses",
        },
        "below_deck_slots_by_level": {
            str(s["slots"]): s["unlock_level"] for s in record.get("crew_slots", [])
        },
    }
    if weapons:
        result["weapons"] = weapons
    return {
        "ship": result,
        "components": slots,
        "catalogue_reference": catalogue_reference(record, level),
        "reference": {
            "ability": ability.get("description"),
            "level_value": ability.get("values", {}).get(str(level)),
            "source": "Officers Tool Ship Stats (reference only)" if ref else None,
        },
        "notes": [
            "Base weapon damage excludes criticals; it is not the Attack power rating.",
            "Account research, buildings and equipment are separate. Level health/shield additions follow the export; live-game calibration remains required.",
            "Ship ability text is reference information, not an automatically enabled combat effect.",
        ],
    }
