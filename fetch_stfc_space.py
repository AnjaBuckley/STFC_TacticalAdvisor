"""
stfc.space Data Importer — STFC Tactical Advisor

Downloads the community game database from data.stfc.space (the static JSON
backend of https://stfc.space) into data/stfc_space/, keyed by the upstream
version. Explicit detail/research refreshes replace cached values; summary-only
runs can be no-ops when the version is unchanged.

Datasets:
  summaries:     officer, ship, hostile, research, wave_defense, pvp_bands
  translations:  officer_names, officer_buffs, ships, research, factions, hostiles
  details:       per-officer and per-ship records (class, per-rank ability
                 values, crew_slots, repair costs) — fetched with --details

Usage:
  python3 fetch_stfc_space.py                  # summaries + translations
  python3 fetch_stfc_space.py --details        # also per-officer/ship details
  python3 fetch_stfc_space.py --hostile-stats  # build data/hostile_stats.json
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://data.stfc.space"
OUT_DIR = Path(__file__).parent / "data" / "stfc_space"

SUMMARIES = ["officer", "ship", "hostile", "research", "wave_defense", "pvp_bands"]
TRANSLATIONS = [
    "officer_names",
    "officer_buffs",
    "ships",
    "research",
    "factions",
    "ship_buffs",
]


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "stfc-advisor/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _fetch_json(path: str, version: str) -> object:
    return json.loads(_get(f"{BASE}/{path}.json?version={version}"))


# Hostile families and hull classes are resolved from the reviewed catalogue.
_STAT_FIELDS = [
    "hull_hp",
    "shield_hp",
    "dpr",
    "armor",
    "absorption",
    "dodge",
    "accuracy",
    "armor_piercing",
    "shield_piercing",
    "critical_chance",
    "critical_damage",
    "strength",
]


def build_hostile_stats(version: str) -> None:
    """Fetch per-variant stats for the real hostiles behind each curated target."""
    ship_names = {
        t["id"]: t["text"]
        for t in json.loads((OUT_DIR / "en_ships.json").read_text())
        if t["key"] == "ship_name"
    }
    summary = json.loads((OUT_DIR / "hostile_summary.json").read_text())

    templates = json.loads(
        (Path(__file__).parent / "data" / "hostiles.json").read_text()
    )
    classes = {0: "Interceptor", 1: "Survey", 2: "Explorer", 3: "Battleship"}
    wanted = {}
    for h in summary:
        real = ship_names.get(h["loca_id"])
        for template in templates:
            if (
                real == template.get("catalogue_family")
                and classes.get(h["hull_type"]) == template["ship_class"]
            ):
                wanted.setdefault(template["name"], []).append(
                    {**h, "real_name": real, "ship_class": classes[h["hull_type"]]}
                )

    result: dict[str, list[dict]] = {}
    total = sum(len(v) for v in wanted.values())
    done = 0
    for curated, entries in wanted.items():
        variants = []
        for e in entries:
            detail = _fetch_json(f"hostile/{e['id']}", version)
            stats = detail.get("stats", {})
            variants.append(
                {
                    "id": e["id"],
                    "real_name": e["real_name"],
                    "ship_class": e["ship_class"],
                    "level": e["level"],
                    **{k: stats.get(k) for k in _STAT_FIELDS},
                }
            )
            done += 1
            time.sleep(0.05)
            if done % 50 == 0:
                print(f"    hostiles {done}/{total}")
        variants.sort(key=lambda v: v["level"])
        result[curated] = variants

    out = Path(__file__).parent / "data" / "hostile_stats.json"
    out.write_text(
        json.dumps(
            {
                "_meta": {"source": "data.stfc.space", "version": version},
                "targets": result,
            },
            indent=1,
            ensure_ascii=False,
        )
    )
    print(f"  hostile_stats.json: {len(result)} targets, {total} variants")


def fetch_research_details(version: str) -> None:
    summary = json.loads((OUT_DIR / "research_summary.json").read_text())
    detail_dir = OUT_DIR / "research"
    detail_dir.mkdir(exist_ok=True)
    todo = [r["id"] for r in summary]
    print(f"  fetching {len(todo)} research details...")
    failed = []
    for i, rid in enumerate(todo):
        try:
            data = _fetch_json(f"research/{rid}", version)
        except urllib.error.HTTPError as e:
            failed.append((rid, e.code))
            continue
        (detail_dir / f"{rid}.json").write_text(
            json.dumps(data, indent=1, ensure_ascii=False)
        )
        time.sleep(0.03)
        if (i + 1) % 200 == 0:
            print(f"    {i + 1}/{len(todo)}")
    if failed:
        print(f"  {len(failed)} nodes failed upstream (skipped): {failed[:5]}")


def main() -> None:
    with_details = "--details" in sys.argv
    with_hostile_stats = "--hostile-stats" in sys.argv
    with_research = "--research-details" in sys.argv

    version = _get(f"{BASE}/version.txt").decode().strip()
    print(f"upstream version: {version}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    version_file = OUT_DIR / "VERSION"
    if version_file.exists() and version_file.read_text().strip() == version:
        print("summaries already up to date")
        if with_hostile_stats:
            build_hostile_stats(version)
        if with_research:
            fetch_research_details(version)
        if not with_details:
            return

    for name in SUMMARIES:
        data = _fetch_json(f"{name}/summary", version)
        (OUT_DIR / f"{name}_summary.json").write_text(
            json.dumps(data, indent=1, ensure_ascii=False)
        )
        print(f"  {name}_summary.json  ({len(data)} entries)")

    for name in TRANSLATIONS:
        try:
            data = _fetch_json(f"translations/en/{name}", version)
        except urllib.error.HTTPError as e:
            print(f"  en_{name}.json  SKIPPED ({e.code})")
            continue
        (OUT_DIR / f"en_{name}.json").write_text(
            json.dumps(data, indent=1, ensure_ascii=False)
        )
        print(f"  en_{name}.json  ({len(data)} entries)")

    if with_research:
        fetch_research_details(version)

    if with_details:
        for entity in ("officer", "ship"):
            summary = json.loads((OUT_DIR / f"{entity}_summary.json").read_text())
            detail_dir = OUT_DIR / entity
            detail_dir.mkdir(exist_ok=True)
            print(f"  fetching {len(summary)} {entity} details...")
            for i, item in enumerate(summary):
                out = detail_dir / f"{item['id']}.json"
                out.write_text(
                    json.dumps(
                        _fetch_json(f"{entity}/{item['id']}", version),
                        indent=1,
                        ensure_ascii=False,
                    )
                )
                time.sleep(0.05)  # be polite to the CDN
                if (i + 1) % 50 == 0:
                    print(f"    {i + 1}/{len(summary)}")

    if with_hostile_stats:
        build_hostile_stats(version)
    version_file.write_text(version)
    print("done")


if __name__ == "__main__":
    main()
