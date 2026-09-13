"""Inventory every public record and compare officer magnitudes without inferring rules."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from engine.abilities import load_abilities
from engine.catalogue import identity
from engine.technology import technology_mappings

ROOT = Path(__file__).parent
BASE = ROOT / "data/stfc_space"


def audit():
    read = lambda name: json.loads((BASE / name).read_text(encoding="utf-8"))
    manifest = read("CATALOGUE_SNAPSHOT.json")
    for name, digest in manifest["sha256"].items():
        if hashlib.sha256((BASE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Snapshot hash mismatch: {name}")
    names = {}
    for filename, key, category in [
        ("en_ships.json", "ship_name", "ship"),
        ("en_officer_names.json", "officer_name", "officer"),
        ("en_forbidden_tech.json", "forbidden_tech_name", "forbidden_tech"),
    ]:
        names[category] = {
            r["id"]: r["text"] for r in read(filename) if r["key"] == key
        }
    names["hostile"] = names["ship"]
    abilities = load_abilities()
    tech = technology_mappings()
    curated = json.loads((ROOT / "data/hostile_stats.json").read_text(encoding="utf-8"))
    curated_ids = {r["id"] for rows in curated["targets"].values() for r in rows}
    categories = {}
    comparisons = []
    counts = Counter()
    for category, route in [
        ("ship", "ships"),
        ("officer", "officers"),
        ("forbidden_tech", "forbidden_and_chaos_tech"),
        ("hostile", "hostiles"),
    ]:
        records = []
        for row in read(category + "_summary.json"):
            ident = row["id"]
            detail = read(f"{category}/{ident}.json")
            if detail["id"] != ident:
                raise ValueError(f"ID mismatch {category}/{ident}")
            name = names[category].get(row["loca_id"], str(ident))
            if category == "ship":
                assert detail["tiers"] and detail["levels"]
                coverage = "Base builds, weapon components and crew unlocks available. Abilities, refits and active powers require separate reviewed models and ownership."
            elif category == "hostile":
                assert isinstance(detail.get("stats"), dict)
                coverage = (
                    (
                        "Curated encounter stats available. "
                        if ident in curated_ids
                        else "Reference only; not a selectable verified encounter. "
                    )
                    + "Special abilities and weapon schedules are not automatically activated."
                )
                name += f" · level {row['level']}"
            elif category == "forbidden_tech":
                assert detail["tiers"] and detail["levels"]
                total = sum(len(g["buffs"]) for g in detail["buffs"])
                mapped = sum(m["tech_id"] == ident for m in tech)
                coverage = f"{mapped}/{total} buffs explicitly mapped. Requires equipped ship, tier, level and activation; other effects omitted."
            else:
                canonical = abilities.aliases.get(identity(name))
                record = abilities.get(canonical, {}) if canonical else {}
                statuses = Counter()
                for source, slot in [
                    ("captain_ability", "cm"),
                    ("ability", "oa"),
                    ("below_decks_ability", "bda"),
                ]:
                    raw = detail.get(source)
                    if not raw:
                        continue
                    current = record.get(slot, {})
                    values = current.get("synergy_values" if slot == "cm" else "values")
                    native = [v["value"] for v in raw["values"]]
                    if slot == "cm":
                        native = native[:3]
                        if current.get("model") in {
                            "probe_extra_shots",
                            "morale_round_start",
                            "defending_delay",
                        }:
                            native = [v["chance"] for v in raw["values"]][:3]
                    status = (
                        "no_maneuver"
                        if slot == "cm" and all(v == 0 for v in native)
                        else "missing_model"
                        if not current
                        else "missing_values"
                        if not values
                        else "values_match"
                        if values == native
                        else "values_differ"
                    )
                    statuses[status] += 1
                    counts[status] += 1
                    comparisons.append(
                        {
                            "officer_id": ident,
                            "name": name,
                            "canonical": canonical,
                            "slot": slot,
                            "buff_id": raw["id"],
                            "status": status,
                            "model_values": values,
                            "native_values": native,
                            "native_proc_chances": [v["chance"] for v in raw["values"]],
                            "model_proc_chances": current.get("proc_chances"),
                            "probability_review_required": any(
                                v["chance"] != 1 for v in raw["values"]
                            )
                            and not current.get("proc_chances")
                            and not current.get("model"),
                        }
                    )
                coverage = (
                    "; ".join(f"{v} {k.replace('_', ' ')}" for k, v in statuses.items())
                    + ". Numerical agreement does not verify conditions, timing or simulation support."
                )
            records.append(
                {
                    "id": ident,
                    "name": name,
                    "coverage": coverage,
                    "url": f"https://stfc.space/{route}/{ident}",
                }
            )
        categories[category] = records
    categories["pvp_bands"] = [
        {
            "id": r["level"],
            "name": f"Operations {r['level']}",
            "coverage": f"Raw standard band {r['lower']}–{r['upper']}; ship PvP starts at Ops 10, station PvP at Ops 15. Event rules excluded.",
            "url": "https://stfc.space/pvp_bands",
        }
        for r in read("pvp_bands_summary.json")
    ]
    result = {
        "version": manifest["version"],
        "categories": categories,
        "officer_value_counts": dict(counts),
        "officer_comparisons": comparisons,
    }
    (ROOT / "data/catalogue_coverage.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print({k: len(v) for k, v in categories.items()}, dict(counts))
    return result


if __name__ == "__main__":
    audit()
