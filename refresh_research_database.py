"""Explicit, staged refresh of public research data; never touches player accounts."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

BASE = "https://data.stfc.space"
DEST = Path(__file__).parent / "data" / "stfc_space"


def refresh():
    def get(path):
        with urlopen(f"{BASE}/{path}", timeout=45) as response:
            return response.read()

    version = get("version.txt").decode().strip()
    summary_raw = get(f"research/summary.json?version={version}")
    summary = json.loads(summary_raw)

    def detail(row):
        raw = get(f"research/{row['id']}.json?version={version}")
        data = json.loads(raw)
        if (
            data["id"] != row["id"]
            or not isinstance(data.get("buffs"), list)
            or not data.get("levels")
        ):
            raise ValueError(f"Incomplete research {row['id']}; no files replaced")
        return str(row["id"]), raw

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = dict(pool.map(detail, summary))
    names = get(f"translations/en/research.json?version={version}")
    json.loads(names)
    if get("version.txt").decode().strip() != version:
        raise ValueError(
            "Upstream changed during download; retry without mixing versions"
        )
    files = {f"research/{key}.json": raw for key, raw in records.items()}
    files.update({"research_summary.json": summary_raw, "en_research.json": names})
    files = {
        key: json.dumps(json.loads(raw), indent=1, ensure_ascii=False).encode("utf-8")
        for key, raw in files.items()
    }
    manifest = {
        "source": BASE,
        "version": version,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "research_count": len(records),
        "sha256": {key: hashlib.sha256(raw).hexdigest() for key, raw in files.items()},
    }
    # All downloads and basic validation finish before replacement. Run only while developing.
    for key, raw in files.items():
        target = DEST / key
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        temp.write_bytes(raw)
        temp.replace(target)
    for old in (DEST / "research").glob("*.json"):
        if old.stem not in records:
            old.unlink()
    (DEST / "RESEARCH_SNAPSHOT.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print("Run audit_research_database.py and review stale mappings before release.")
    print(f"Updated {len(records)} research records at version {version}")


if __name__ == "__main__":
    refresh()
