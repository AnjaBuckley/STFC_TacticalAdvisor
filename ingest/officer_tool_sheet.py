"""
STFC Officers Tool (Google Sheet) Ingestion — STFC Tactical Advisor

Fetches the player's live "STFC Officers Tool" spreadsheet (by StewieDøø) and
merges the Roster (officer levels/ranks/stats) and Bonuses (ops level, Orion
Syndicate, Emerald Chain) sections into the player profile.

The sheet must be shared as "Anyone with the link -> Viewer" for the plain
HTTP export fetch to work (no Google auth is performed here).

Cells are located via the workbook's own named ranges (OpsLevel, RosterOfficer,
RosterLevel, ...) rather than hardcoded row/column offsets, since those survive
the author adding/removing rows elsewhere in the sheet. A few Roster columns
(rarity, group, CM/BDA, OA, description) have no named range and are addressed
by fixed column letters relative to the officer-name column.

Usage (CLI):
  python3 -m ingest.officer_tool_sheet "<sheet URL or ID>"           # preview
  python3 -m ingest.officer_tool_sheet "<sheet URL or ID>" --apply   # update profile
"""

import io
import json
import re
import shutil
import sys
import time
from pathlib import Path

import openpyxl
import requests

import paths

_BASE = Path(__file__).parent.parent
_PROFILE_PATH = paths.profile_path()

_SHEET_ID_RE = re.compile(r"/d/([a-zA-Z0-9_-]{20,})")

# Roster columns without a named range, given relative to the RosterOfficer column.
_ROSTER_EXTRA_COLS = {"rarity": -1, "group": 6, "cm_bda_value": 7, "oa_value": 8, "description": 12}

_PVP_KEYWORDS = (
    "player", "pvp", "strike team", "battleship", "explorer", "interceptor",
    "hull breach", "burning", "isolytic", "apex shred",
)
_PVE_KEYWORDS = (
    "hostile", "borg", "gorn", "swarm", "xindi", "mining", "cargo",
    "armada", "wave", "drone", "romulan", "klingon", "federation",
)


def _sheet_id(source: str) -> str:
    match = _SHEET_ID_RE.search(source)
    return match.group(1) if match else source.strip()


def fetch_workbook(source, timeout: int = 30):
    """Accepts a Google Sheet URL/ID, a local path, or raw xlsx bytes."""
    if isinstance(source, bytes):
        content = source
    elif isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
        content = Path(source).read_bytes()
    else:
        sheet_id = _sheet_id(source)
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        resp = requests.get(url, timeout=timeout)
        if resp.status_code != 200 or b"accounts.google.com" in resp.content[:2000]:
            raise RuntimeError(
                "Could not fetch the sheet. Make sure it's shared as "
                "'Anyone with the link -> Viewer' in Google Sheets."
            )
        content = resp.content
    return openpyxl.load_workbook(io.BytesIO(content), data_only=True)


def _named_cell(wb, name):
    dn = wb.defined_names[name]
    title, coord = next(iter(dn.destinations))
    return wb[title][coord].value


def _named_column(wb, name):
    """Returns (sheet, col_letter, min_row, max_row, values) for a single-column named range."""
    dn = wb.defined_names[name]
    title, coord = next(iter(dn.destinations))
    ws = wb[title]
    cells = ws[coord]
    col_letter = cells[0][0].coordinate.rstrip("0123456789")
    min_row = cells[0][0].row
    max_row = cells[-1][0].row
    values = [c[0].value for c in cells]
    return ws, col_letter, min_row, max_row, values


def parse_bonuses(wb) -> dict:
    return {
        "ops_level": int(_named_cell(wb, "OpsLevel") or 0),
        "syndicate_level": int(_named_cell(wb, "OrionLevel") or 0),
        "syndicate_officer_bonus": {
            "attack": float(_named_cell(wb, "OrionAttack") or 0),
            "defense": float(_named_cell(wb, "OrionDefence") or 0),
            "health": float(_named_cell(wb, "OrionHealth") or 0),
        },
        "emerald_chain": {
            "level": int(_named_cell(wb, "EmeraldChainLevel") or 0),
            "attack": float(_named_cell(wb, "EmeraldAttack") or 0),
            "defense": float(_named_cell(wb, "EmeraldDefence") or 0),
            "health": float(_named_cell(wb, "EmeraldHealth") or 0),
        },
    }


def parse_roster(wb) -> list[dict]:
    ws, name_col, min_row, max_row, names = _named_column(wb, "RosterOfficer")
    _, _, _, _, levels = _named_column(wb, "RosterLevel")
    _, _, _, _, ranks = _named_column(wb, "RosterRank")
    _, _, _, _, attacks = _named_column(wb, "RosterAttack")
    _, _, _, _, defenses = _named_column(wb, "RosterDefence")
    _, _, _, _, healths = _named_column(wb, "RosterHealth")

    from openpyxl.utils import column_index_from_string, get_column_letter
    name_idx = column_index_from_string(name_col)
    extra_cols = {
        field: get_column_letter(name_idx + offset)
        for field, offset in _ROSTER_EXTRA_COLS.items()
    }
    extra_values = {
        field: [ws.cell(row=r, column=column_index_from_string(col)).value
                for r in range(min_row, max_row + 1)]
        for field, col in extra_cols.items()
    }

    officers = []
    for i, name in enumerate(names):
        level = levels[i]
        if not (isinstance(name, str) and name.strip() and isinstance(level, (int, float))):
            continue

        description = extra_values["description"][i]
        desc_lower = str(description).lower() if description else ""
        pvp_relevant = any(kw in desc_lower for kw in _PVP_KEYWORDS)
        pve_relevant = any(kw in desc_lower for kw in _PVE_KEYWORDS) or not pvp_relevant

        rarity = extra_values["rarity"][i]
        group = extra_values["group"][i]
        cm_bda = extra_values["cm_bda_value"][i]
        oa = extra_values["oa_value"][i]

        officers.append({
            "name": name.strip(),
            "rarity": str(rarity).strip() if rarity else "U",
            "level": int(level),
            "rank": int(ranks[i]) if isinstance(ranks[i], (int, float)) else 1,
            "attack": round(float(attacks[i]), 2) if isinstance(attacks[i], (int, float)) else 0,
            "defense": round(float(defenses[i]), 2) if isinstance(defenses[i], (int, float)) else 0,
            "health": round(float(healths[i]), 2) if isinstance(healths[i], (int, float)) else 0,
            "group": str(group).strip() if group else "",
            "cm_bda_value": str(cm_bda).strip() if cm_bda else "",
            "oa_value": str(oa).strip() if oa else "",
            "description": str(description).strip() if description else "",
            "pvp_relevant": pvp_relevant,
            "pve_relevant": pve_relevant,
        })
    return officers


def apply_to_profile(profile: dict, bonuses: dict, roster: list[dict]) -> tuple[dict, list[str]]:
    """Merge sheet data into the profile. Returns (profile, diff).

    Officers are upserted by name: sheet-derived fields (level, rank, stats,
    group, CM/BDA, OA, description) are overwritten, but fields the sheet
    doesn't provide (class, attack_bonus, and any other manual enrichment)
    are preserved for officers that already exist in the profile.
    """
    diff = []

    for key in ("ops_level", "syndicate_level"):
        old = profile.get(key)
        new = bonuses[key]
        if old != new:
            diff.append(f"{key}: {old} -> {new}")
        profile[key] = new

    by_name = {o["name"]: o for o in profile.setdefault("officers", [])}
    added, updated, refreshed = [], [], []

    for sheet_officer in roster:
        name = sheet_officer["name"]
        sheet_fields = {
            "rarity": sheet_officer["rarity"], "level": sheet_officer["level"],
            "rank": sheet_officer["rank"], "attack": sheet_officer["attack"],
            "defense": sheet_officer["defense"], "health": sheet_officer["health"],
            "group": sheet_officer["group"], "cm_bda_value": sheet_officer["cm_bda_value"],
            "oa_value": sheet_officer["oa_value"], "description": sheet_officer["description"],
            "stats": {"attack": sheet_officer["attack"], "defense": sheet_officer["defense"],
                      "health": sheet_officer["health"]},
        }

        existing = by_name.get(name)
        if existing is None:
            new_officer = {
                **sheet_fields,
                "name": name,
                "class": "",
                "attack_bonus": 0.0,
                "pvp_relevant": sheet_officer["pvp_relevant"],
                "pve_relevant": sheet_officer["pve_relevant"],
            }
            profile["officers"].append(new_officer)
            by_name[name] = new_officer
            added.append(name)
        else:
            leveled = (existing.get("level") != sheet_fields["level"]
                       or existing.get("rank") != sheet_fields["rank"])
            # Any sheet-derived field counts as a change: stats shift whenever a
            # global bonus (Orion, buildings) changes, even at unchanged level/rank.
            changed = any(existing.get(k) != v for k, v in sheet_fields.items())
            existing.update(sheet_fields)
            if leveled:
                updated.append(name)
            elif changed:
                refreshed.append(name)

    if added:
        diff.append(f"officers added: {', '.join(added)}")
    if updated:
        diff.append(f"officers leveled/ranked up: {', '.join(updated)}")
    if refreshed:
        diff.append(f"officers with updated stats/details: {len(refreshed)}")

    return profile, diff


def apply_report(report: dict) -> dict:
    """Write a previously previewed report's parsed data to the profile.

    Re-merges against the profile as it is on disk right now, so the exact
    data the user previewed is what gets applied — no second network fetch.
    """
    profile = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    profile, diff = apply_to_profile(profile, report["bonuses"], report["roster"])

    backup = _PROFILE_PATH.with_suffix(f".json.bak-{int(time.time())}")
    shutil.copy(_PROFILE_PATH, backup)
    _PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    return {**report, "diff": diff, "applied": True, "backup": str(backup)}


def ingest_officer_sheet(source, apply: bool = False) -> dict:
    """Full pipeline. Returns a report dict; writes the profile when apply=True."""
    wb = fetch_workbook(source)
    bonuses = parse_bonuses(wb)
    roster = parse_roster(wb)

    profile = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    _, diff = apply_to_profile(profile, bonuses, roster)
    report = {
        "ops_level": bonuses["ops_level"],
        "syndicate_level": bonuses["syndicate_level"],
        "officers_in_sheet": len(roster),
        "diff": diff,
        "applied": False,
        "bonuses": bonuses,
        "roster": roster,
    }

    if apply:
        report = apply_report(report)
    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    report = ingest_officer_sheet(sys.argv[1], apply="--apply" in sys.argv)
    print(f"ops_level: {report['ops_level']}  syndicate_level: {report['syndicate_level']}")
    print(f"officers in sheet: {report['officers_in_sheet']}")
    print("profile changes:" if report["diff"] else "no profile changes")
    for d in report["diff"]:
        print(f"  {d}")
    if report["applied"]:
        print(f"APPLIED. Backup: {report['backup']}")
