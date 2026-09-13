"""Explicit development-only public snapshot refresh. Never reads player accounts.

Download and validate a complete version before replacing files. Run with the app
stopped, then audit and review mapping hashes before shipping the changed data.
"""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

BASE = "https://data.stfc.space"
DEST = Path(__file__).parent / "data/stfc_space"
CATEGORIES = ("ship", "officer", "forbidden_tech", "hostile", "pvp_bands")


def refresh():
    def get(path):
        with urlopen(f"{BASE}/{path}", timeout=60) as response:
            return response.read()

    version = get("version.txt").decode().strip()
    files = {}
    counts = {}
    tasks = []
    for category in CATEGORIES:
        raw = get(f"{category}/summary.json?version={version}")
        rows = json.loads(raw)
        if not rows or not isinstance(rows, list):
            raise ValueError("Empty or invalid summary")
        counts[category] = len(rows)
        files[f"{category}_summary.json"] = raw
        if category != "pvp_bands":
            ids = [r["id"] for r in rows]
            if len(set(ids)) != len(ids):
                raise ValueError("Duplicate catalogue IDs")
            tasks.extend((category, ident) for ident in ids)

    def detail(task):
        category, ident = task
        raw = get(f"{category}/{ident}.json?version={version}")
        data = json.loads(raw)
        if data["id"] != ident:
            raise ValueError("Detail identity mismatch")
        required = {
            "ship": ["tiers", "levels"],
            "officer": ["ability"],
            "forbidden_tech": ["tiers", "levels", "buffs"],
            "hostile": ["stats", "components"],
        }[category]
        if any(k not in data for k in required):
            raise ValueError("Incomplete detail")
        return f"{category}/{ident}.json", raw

    with ThreadPoolExecutor(max_workers=6) as pool:
        files.update(pool.map(detail, tasks))
    for name in [
        "ships",
        "ship_buffs",
        "officer_names",
        "officer_buffs",
        "forbidden_tech",
        "factions",
    ]:
        files[f"en_{name}.json"] = get(f"translations/en/{name}.json?version={version}")
    files = {
        k: json.dumps(json.loads(v), indent=1, ensure_ascii=False).encode("utf-8")
        for k, v in files.items()
    }
    if get("version.txt").decode().strip() != version:
        raise ValueError("Source changed during download; no files replaced")
    manifest = {
        "source": BASE,
        "version": version,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "sha256": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
    }
    for name, raw in files.items():
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        temp.write_bytes(raw)
        temp.replace(target)
    for category in CATEGORIES[:-1]:
        for path in (DEST / category).glob("*.json"):
            if path.relative_to(DEST).as_posix() not in files:
                path.unlink()
    (DEST / "CATALOGUE_SNAPSHOT.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    # Ship reference metadata must report this version, not the prior ship snapshot.
    path = DEST / "SHIP_SNAPSHOT.json"
    ship_manifest = json.loads(path.read_text(encoding="utf-8"))
    ship_manifest.update(version=version, fetched_at=manifest["fetched_at"])
    ship_manifest["sha256"] = {
        k: hashlib.sha256((DEST / k).read_bytes()).hexdigest()
        for k in ship_manifest["sha256"]
    }
    path.write_text(json.dumps(ship_manifest, indent=2) + "\n", encoding="utf-8")
    print("Downloaded", counts, "at", version)
    print(
        "Run audit_game_catalogues.py; review stale officer/technology mappings and curated hostile stats before release."
    )


if __name__ == "__main__":
    refresh()
