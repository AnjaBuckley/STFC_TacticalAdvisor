"""
Spock's Club Research CSV Ingestion — STFC Tactical Advisor

Reads a "Research Management" export from spocks.club (one row per research
node level, with a Done flag and the stfc.space node id), joins it against
the per-node buff values in data/stfc_space/research/, and computes the
player's REAL research buffs — replacing the estimates in the profile.

CSV columns: Name, Level, Tree, Col, Row, Power, Done, Min Ops, id, <description>

Usage (CLI):
  python3 -m ingest.research_csv "<path to csv>"           # preview only
  python3 -m ingest.research_csv "<path to csv>" --apply   # update profile
"""

import csv
import io
import json
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

import paths

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
                "done": row.get("Done", "").strip().lower() == "yes",
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
    missing_detail = 0
    for node_id, level in done_level.items():
        detail_path = _RESEARCH_DIR / f"{node_id}.json"
        if not detail_path.exists():
            missing_detail += 1
            continue
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        info = node_info[node_id]
        for index, buff in enumerate(detail.get("buffs", [])):
            values = buff.get("values", [])
            if not 1 <= level <= len(values):
                continue
            value = values[level - 1].get("value", 0) or 0
            sources.append(
                {
                    "id": f"research:{node_id}:{buff.get('id', index)}",
                    "name": info["name"],
                    "node_id": node_id,
                    "buff_id": buff.get("id", index),
                    "level": level,
                    "value": value,
                    "unit": "fraction" if buff.get("value_is_percentage") else "points",
                    "effect": "unreviewed",
                    "contexts": [],
                    "status": "unreviewed",
                    "description": info["description"],
                    "origin": "research_csv",
                    "review_hint": _classify(info["name"], info["description"]),
                }
            )
    return {
        "buckets": {},
        "conditional": {},
        "sources": sources,
        "nodes_done": len(done_level),
        "nodes_counted": len(done_level) - missing_detail,
        "nodes_missing_detail": missing_detail,
        "warning": "Research values retained per buff in native units. Confirm exact effect and conditions before enabling; existing account totals are preserved.",
    }


def apply_to_profile(profile: dict, buckets: dict) -> tuple[dict, list[str]]:
    """Map buff buckets onto the profile's research fields. Returns (profile, diff)."""
    if "sources" in buckets:
        existing = profile.get("combat_sources", [])
        reviewed = {s["id"]: s for s in existing if s.get("origin") == "research_csv"}
        merged = []
        for source in buckets["sources"]:
            old = reviewed.get(source["id"], {})
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
        updated = [s for s in existing if s.get("origin") != "research_csv"] + merged
        profile["combat_sources"] = updated
        return profile, (
            [
                f"Imported {len(merged)} attributed research buffs; manual totals preserved."
            ]
            if updated != existing
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
    result = compute_research_buffs(rows)
    profile = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    profile, diff = apply_to_profile(profile, result)
    report = {**result, "diff": diff, "applied": False}

    if apply:
        backup = _PROFILE_PATH.with_suffix(f".json.bak-{int(time.time())}")
        shutil.copy(_PROFILE_PATH, backup)
        _PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
        report["applied"] = True
        report["backup"] = str(backup)
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
        print(f"APPLIED. Backup: {report['backup']}")
