"""
Spock's Club Research CSV Ingestion — STFC Tactical Advisor

Reads a "Research Management" export from spocks.club (one row per research
node level, with a Done flag and the stfc.space node id), joins it against
the per-node buff values in data/stfc_space/research/, and computes the
attributed research values for explicit scope review; manual totals are preserved.

CSV columns: Name, Level, Tree, Col, Row, Power, Done, Min Ops, id, <description>

Usage (CLI):
  python3 -m ingest.research_csv "<path to csv>"           # preview only
  python3 -m ingest.research_csv "<path to csv>" --apply   # update profile
"""

import csv
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import paths
from engine.research_catalogue import mapping_matches, research_metadata

_BASE = Path(__file__).parent.parent
_RESEARCH_DIR = _BASE / "data" / "stfc_space" / "research"
_PROFILE_PATH = paths.profile_path()

# Ordered classifiers: first match on the node's name+description wins.
# bucket -> regex (matched against lowercase "name :: description")
_CLASSIFIERS = [
    ("apex_shred", r"apex shred"),
    ("apex_barrier", r"apex barrier"),
    ("isolytic_defense", r"isolytic (defense|defence|mitigation)"),
    ("isolytic_damage", r"isolytic (damage|cascade)"),
    ("remote_campus", r"remote campus"),
    (
        "crit_mitigation",
        r"(critical mitigation|reduc\w* critical damage taken|decreas\w* critical damage (taken|received))",
    ),
    ("officer_all", r"(all (officer|bridge officer) stats|officer stats)"),
    ("officer_attack", r"officer\w*'? attack|attack of (all )?officers"),
    (
        "officer_defense",
        r"officer\w*'? (defense|defence)|(defense|defence) of (all )?officers",
    ),
    ("officer_health", r"officer\w*'? health|health of (all )?officers"),
    (
        "weapon_damage",
        r"(weapon damage|damage of (all )?(ships|weapons)|(energy|kinetic) (weapon )?damage)",
    ),
    ("hull_health", r"hull health"),
    ("shield_health", r"shield health"),
    (
        "mitigation_stats",
        r"(armor|shield deflection|dodge)(?!.*(piercing|penetration))",
    ),
    ("piercing", r"(piercing|penetration|accuracy)"),
]

# Buckets whose values are flat stat points, not percentage decimals
_FLAT_BUCKETS = {"apex_barrier"}

# Nodes scoped to a specific enemy, mode, or ship must NOT count toward the
# player's global combat buffs (e.g. "+4000% Isolytic Damage vs I.S.S.").
_CONDITIONAL_MARKERS = re.compile(
    r"(\bvs\.?\s|against (enemy )?players?|\bpvp\b|i\.s\.s\.|eclipse|augment"
    r"|actian|aggregation|krenim|wave defense|when defending|mirror universe"
    r"|defense platform|station combat)",
    re.IGNORECASE,
)
_SHIP_SCOPED = re.compile(
    r"(serene squall|gs-31|stella\b|mantis|borg cube|vi'dar|relativity"
    r"|excelsior|voyager|botany bay|d'vor|amalgam|monaveen|defiant"
    r"|discovery|franklin|cerritos|newgrange|grishnar|divitae|selkie)",
    re.IGNORECASE,
)


def parse_research_csv(source) -> list[dict]:
    """Accepts a path, bytes, or file-like object; returns normalized rows."""
    if isinstance(source, (str, Path)):
        text = Path(source).read_text(encoding="utf-8-sig")
    elif isinstance(source, bytes):
        text = source.decode("utf-8-sig")
    else:
        raw = source.read()
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw

    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    if not {"Name", "Level", "Done", "id"}.issubset(header):
        return []
    rows = []
    for raw_row in reader:
        row = dict(zip(header, raw_row))
        # the description column has an empty header
        desc = raw_row[len(header) - 1] if len(raw_row) >= len(header) else ""
        if not row.get("id"):
            continue
        rows.append(
            {
                "id": row["id"].strip(),
                "name": row.get("Name", "").strip(),
                "level": int(row.get("Level", 0) or 0),
                "tree": row.get("Tree", "").strip(),
                "done": row.get("Done", "").strip().lower() in {"yes", "current"},
                "status": row.get("Done", "").strip().lower(),
                "description": desc.strip(),
            }
        )
    return rows


def is_research_csv(source) -> bool:
    """Header sniff used by the upload UI to route files."""
    try:
        rows = parse_research_csv(source)
    except (ValueError, TypeError, OSError, StopIteration, UnicodeError, csv.Error):
        return False
    return len(rows) > 0


def _classify(name: str, description: str) -> str:
    hay = f"{name} :: {description}".lower()
    for bucket, pattern in _CLASSIFIERS:
        if re.search(pattern, hay):
            return bucket
    return "other"


def compute_research_buffs(rows: list[dict]) -> dict:
    """
    Aggregate completed research into buff buckets.

    For each node, the highest completed level's buff value counts (research
    values are cumulative per level in the game data).
    """
    done_level: dict[str, int] = defaultdict(int)
    node_info: dict[str, dict] = {}
    for r in rows:
        node_info[r["id"]] = r
        if r["done"]:
            done_level[r["id"]] = max(done_level[r["id"]], r["level"])

    # Preserve each buff's identity and native unit. Text classification is a
    # review hint, never authority to apply several distinct buffs globally.
    sources = []
    metadata = research_metadata()
    invalid_levels = []
    no_buffs = 0
    registry = json.loads(
        (_BASE / "data" / "research_effects.json").read_text(encoding="utf-8")
    )
    mappings = {(m["node_id"], m["buff_id"]): m for m in registry["mappings"]}
    missing_detail = 0
    missing_values = 0
    for node_id, level in done_level.items():
        detail_path = _RESEARCH_DIR / f"{node_id}.json"
        if not detail_path.exists():
            missing_detail += 1
            continue
        raw = detail_path.read_bytes()
        detail = json.loads(raw)
        info = node_info[node_id]
        meta = metadata.get(node_id, {})
        valid_levels = {r["id"] for r in detail.get("levels", [])}
        if valid_levels and level not in valid_levels:
            invalid_levels.append(
                {
                    "node_id": node_id,
                    "level": level,
                    "reason": "Level is not defined by the catalogue.",
                }
            )
            continue
        if not detail.get("buffs"):
            no_buffs += 1
        for index, buff in enumerate(detail.get("buffs", [])):
            values = buff.get("values", [])
            if not 1 <= level <= len(values):
                missing_values += 1
                continue
            value = values[level - 1].get("value")
            if value is None:
                missing_values += 1
                continue
            mapping = mappings.get((node_id, buff.get("id")))
            verified = bool(mapping and mapping_matches(mapping, raw, meta, buff))
            sources.append(
                {
                    "id": f"research:{node_id}:{buff.get('id', index)}",
                    "name": meta.get("name", info["name"]),
                    "node_id": node_id,
                    "buff_id": buff.get("id", index),
                    "level": level,
                    "value": value,
                    "unit": mapping["unit"]
                    if verified
                    else ("fraction" if buff.get("value_is_percentage") else "points"),
                    "mapping_verified": verified,
                    "export_percentage": buff.get("value_is_percentage"),
                    "chance": values[level - 1].get("chance"),
                    "enabled": False,
                    "effect": "unreviewed",
                    "contexts": [],
                    "status": "unreviewed",
                    "description": meta.get("description", info["description"]),
                    "origin": "research_csv",
                    "review_hint": _classify(info["name"], info["description"]),
                }
            )
    expanded = []
    for source in sources:
        mapping = mappings.get((source["node_id"], source["buff_id"]))
        if mapping and source.pop("mapping_verified", False):
            for effect in mapping["effects"]:
                expanded.append(
                    {
                        **source,
                        "id": source["id"] + ":" + effect,
                        "effect": effect,
                        "contexts": mapping["contexts"],
                        "conditions": mapping["conditions"],
                        "status": "reviewed",
                        "enabled": False,
                        "mapping_source": mapping["source"],
                        "mapping_version": registry["reviewed"],
                    }
                )
        else:
            source.pop("mapping_verified", None)
            expanded.append(source)
    sources = expanded
    return {
        "buckets": {},
        "conditional": {},
        "sources": sources,
        "nodes_done": len(done_level),
        "nodes_counted": len(done_level) - missing_detail - len(invalid_levels),
        "invalid_levels": invalid_levels,
        "nodes_without_buffs": no_buffs,
        "nodes_missing_detail": missing_detail,
        "buffs_missing_values": missing_values,
        "mapped_sources": sum(s["status"] == "reviewed" for s in sources),
        "unreviewed_sources": sum(s["status"] == "unreviewed" for s in sources),
        "current_rows": sum(r.get("status") == "current" for r in rows),
        "progress": [
            {
                "node_id": key,
                "name": node_info[key]["name"],
                "tree": metadata.get(key, {}).get(
                    "tree", node_info[key].get("tree", "")
                ),
                "level": level,
            }
            for key, level in sorted(done_level.items())
        ],
        "warning": "Yes and Current count as completed; the highest completed level is used once. Mapped bonuses start disabled to prevent overlap with manual totals. Unsupported conditions remain unreviewed.",
    }


def apply_to_profile(profile: dict, buckets: dict) -> tuple[dict, list[str]]:
    """Map buff buckets onto the profile's research fields. Returns (profile, diff)."""
    if "sources" in buckets:
        existing = profile.get("combat_sources", [])
        reviewed = {s["id"]: s for s in existing if s.get("origin") == "research_csv"}
        merged = []
        for source in buckets["sources"]:
            old = reviewed.get(source["id"], {})
            if source.get("mapping_source"):
                # Refresh reviewed registry scopes rather than restoring stale imported rules.
                old = {"enabled": old["enabled"]} if "enabled" in old else {}
            elif old.get("mapping_source") or old.get("description") != source.get(
                "description"
            ):
                old = {}
            # A changed level keeps reviewed scope/effect but takes the new value.
            merged.append(
                {
                    **source,
                    **{
                        k: old[k]
                        for k in (
                            "effect",
                            "contexts",
                            "conditions",
                            "status",
                            "enabled",
                        )
                        if k in old
                    },
                }
            )
        # If an upstream detail/value is missing, retain the old record but disable it;
        # silently dropping a reviewed source would hide the coverage regression.
        new_ids = {s["id"] for s in merged}
        for old in existing:
            if old.get("origin") == "research_csv" and old["id"] not in new_ids:
                merged.append(
                    {
                        **old,
                        "enabled": False,
                        "import_warning": "Not resolved by latest import; retained disabled for review.",
                    }
                )
        updated = [s for s in existing if s.get("origin") != "research_csv"] + merged
        profile["combat_sources"] = updated
        old_summary = profile.get("research_import_summary", {})
        old_progress = profile.get("research_progress", [])
        profile["research_progress"] = buckets.get("progress", [])
        profile["research_import_summary"] = {
            k: buckets[k]
            for k in (
                "nodes_done",
                "mapped_sources",
                "unreviewed_sources",
                "nodes_missing_detail",
                "buffs_missing_values",
                "invalid_levels",
                "nodes_without_buffs",
            )
            if k in buckets
        }
        return profile, (
            [
                f"Imported {len(merged)} attributed research buffs; {buckets.get('mapped_sources', 0)} mapped, {buckets.get('unreviewed_sources', 0)} need review. Yes and Current included; manual totals preserved. Skipped {len(buckets.get('invalid_levels', []))} invalid levels, {buckets.get('nodes_missing_detail', 0)} missing records and {buckets.get('buffs_missing_values', 0)} missing values."
            ]
            if updated != existing
            or old_progress != profile["research_progress"]
            or old_summary != profile["research_import_summary"]
            else []
        )
    diff = []
    research = profile.setdefault("research", {})
    combat = research.setdefault("combat", {})
    mirror = research.setdefault("mirror_tree", {})
    star = research.setdefault("star_path", {})
    crit = research.setdefault("critical_mitigation", {})

    def _set(container, key, new, fmt="{:.2f}"):
        old = container.get(key, 0)
        if round(new, 4) != round(old if isinstance(old, (int, float)) else 0, 4):
            diff.append(f"{key}: {old} -> {fmt.format(new)}")
        container[key] = round(new, 4)

    b = buckets

    # Officer stat totals also come from NON-research sources (Orion Syndicate
    # bonuses, buildings, Fleet Commanders, Emerald Chain) that this CSV does
    # not track — never lower an existing officer value based on research alone.
    def _set_floor(container, key, new):
        old = container.get(key, 0) or 0
        _set(container, key, max(old, new))

    _set_floor(combat, "atk_only_research", b.get("officer_attack", 0.0))
    _set_floor(combat, "def_only_research", b.get("officer_defense", 0.0))
    _set_floor(combat, "hth_only_research", b.get("officer_health", 0.0))
    _set_floor(combat, "all_research", b.get("officer_all", 0.0))
    _set_floor(
        combat,
        "total_officer_bonus",
        b.get("officer_all", 0.0)
        + (
            b.get("officer_attack", 0.0)
            + b.get("officer_defense", 0.0)
            + b.get("officer_health", 0.0)
        )
        / 3,
    )
    _set_floor(combat, "ship_weapon_damage", b.get("weapon_damage", 0.0))
    _set_floor(combat, "ship_hull_health", b.get("hull_health", 0.0))
    _set_floor(combat, "ship_shield_health", b.get("shield_health", 0.0))
    _set(mirror, "apex_barrier", b.get("apex_barrier", 0.0), fmt="{:,.0f}")
    _set(star, "isolytic_damage_bonus", b.get("isolytic_damage", 0.0))
    _set(star, "isolytic_defense_bonus", b.get("isolytic_defense", 0.0))
    _set(star, "apex_shred_bonus", b.get("apex_shred", 0.0))
    _set(
        crit,
        "remote_campus_bonus",
        b.get("remote_campus", 0.0) or b.get("crit_mitigation", 0.0),
    )

    return profile, diff


def ingest_research_csv(source, apply: bool = False) -> dict:
    """Full pipeline. Returns a report dict; writes the profile when apply=True."""
    rows = parse_research_csv(source)
    if not rows:
        raise ValueError("No research rows found; account unchanged.")
    result = compute_research_buffs(rows)
    from service import read_profile, save_profile

    profile, revision = read_profile()
    profile, diff = apply_to_profile(profile, result)
    report = {**result, "diff": diff, "applied": False}
    if apply:
        report["revision"] = save_profile(profile, revision)
        report["applied"] = True
    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    report = ingest_research_csv(sys.argv[1], apply="--apply" in sys.argv)
    print(
        f"nodes done: {report['nodes_done']} (counted {report['nodes_counted']}, "
        f"missing detail {report['nodes_missing_detail']})"
    )
    print("buckets:")
    for k, v in sorted(report["buckets"].items()):
        print(f"  {k:20s} {v:,.3f}")
    print("profile changes:" if report["diff"] else "no profile changes")
    for d in report["diff"]:
        print(f"  {d}")
    if report["applied"]:
        print("APPLIED using revision-checked save and automatic backup.")
