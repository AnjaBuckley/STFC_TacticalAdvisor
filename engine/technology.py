"""Explicitly equipped technology; only reviewed, scoped buffs enter combat."""

import hashlib
import json
from functools import lru_cache

from engine.catalogue import BASE


@lru_cache(maxsize=1)
def technology_catalogue():
    texts = {
        (r["id"], r["key"]): r["text"]
        for r in json.loads(
            (BASE / "en_forbidden_tech.json").read_text(encoding="utf-8")
        )
    }
    return {
        r["id"]: {
            **r,
            "name": texts.get((r["loca_id"], "forbidden_tech_name"), str(r["id"])),
        }
        for r in json.loads(
            (BASE / "forbidden_tech_summary.json").read_text(encoding="utf-8")
        )
    }


@lru_cache(maxsize=1)
def technology_mappings():
    return json.loads(
        (BASE.parent / "technology_effects.json").read_text(encoding="utf-8")
    )["mappings"]


@lru_cache(maxsize=256)
def technology_record(ident):
    raw = (BASE / "forbidden_tech" / f"{ident}.json").read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=1)
def technology_descriptions():
    return {
        r["id"]: r["text"]
        for r in json.loads(
            (BASE / "en_forbidden_tech.json").read_text(encoding="utf-8")
        )
        if r["key"] == "forbidden_tech_buff_name"
    }


def validate_technologies(entries):
    if not isinstance(entries, list) or len(entries) > 2:
        raise ValueError(
            "Equip at most one Forbidden Tech and one Chaos Tech per ship."
        )
    types = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Technology must be an object.")  # noqa: TRY004
        for key in ["id", "tier", "level"]:
            if isinstance(item.get(key), bool) or not isinstance(item.get(key), int):
                raise ValueError("Technology ID, tier and level must be integers.")  # noqa: TRY004
        row = technology_catalogue().get(item["id"])
        if not row:
            raise ValueError("Technology is not in the bundled catalogue.")
        if row["tech_type"] in types:
            raise ValueError(
                "Only one technology of each type can be equipped per ship."
            )
        types.add(row["tech_type"])
        record, _ = technology_record(item["id"])
        tiers = {int(r["rank"]): r for r in record["tiers"]}
        tier, level = item["tier"], item["level"]
        if not 1 <= tier <= row["tier_max"] or tier not in tiers:
            raise ValueError("Technology tier is outside its catalogue range.")
        if not 1 <= level <= tiers[tier]["max_level"] or (
            tier > 1 and level < tiers[tier - 1]["max_level"]
        ):
            raise ValueError("Technology level does not belong to the selected tier.")
        if not isinstance(item.get("enabled", False), bool):
            raise ValueError("Technology activation must be true or false.")  # noqa: TRY004


def technology_sources(ship):
    sources, omissions = [], []
    entries = ship.get("technologies", [])
    if not entries:
        return sources, omissions
    try:
        validate_technologies(entries)
    except ValueError as exc:
        return [], [str(exc)]
    mappings = technology_mappings()
    for item in entries:
        if not item.get("enabled", False):
            continue
        meta = technology_catalogue()[item["id"]]
        if ship.get("stat_basis") == "displayed":
            omissions.append(
                f"{meta['name']}: use base ship stats to avoid duplicating equipped bonuses."
            )
            continue
        record, digest = technology_record(item["id"])
        for group in record["buffs"]:
            if group["tier"] > item["tier"]:
                continue
            for buff in group["buffs"]:
                mapping = next(
                    (
                        m
                        for m in mappings
                        if m["tech_id"] == item["id"] and m["buff_id"] == buff["id"]
                    ),
                    None,
                )
                values = buff["values"]
                index = item["level"] - 1
                if (
                    not mapping
                    or mapping["sha256"] != digest
                    or mapping["description"]
                    != technology_descriptions().get(buff["loca_id"])
                    or index >= len(values)
                    or values[index].get("chance") != 1
                ):
                    omissions.append(
                        f"{meta['name']}: buff {buff['id']} is not modelled."
                    )
                    continue
                for effect in mapping["effects"]:
                    sources.append(
                        {
                            "id": f"tech:{item['id']}:{buff['id']}:{effect}",
                            "name": meta["name"],
                            "effect": effect,
                            "unit": mapping["unit"],
                            "value": values[index]["value"],
                            "contexts": mapping["contexts"],
                            "conditions": mapping["conditions"],
                            "status": "reviewed",
                            "origin": "equipped_technology",
                        }
                    )
    return sources, omissions
