"""Inventory every bundled node and report coverage without inventing effects."""

import json
import math
from collections import Counter
from pathlib import Path

from engine.catalogue import BASE
from engine.research_catalogue import (
    mapping_matches,
    research_metadata,
    reviewed_registry,
)


def audit():
    metadata = research_metadata()
    mappings = {
        (m["node_id"], m["buff_id"]): m for m in reviewed_registry()["mappings"]
    }
    rows = []
    for node_id, meta in metadata.items():
        path = BASE / "research" / f"{node_id}.json"
        issues, effects = [], []
        buffs = []
        if not path.exists():
            issues.append("missing_detail")
        else:
            raw = path.read_bytes()
            detail = json.loads(raw)
            levels = [r["id"] for r in detail.get("levels", [])]
            if levels != list(range(1, meta["max_level"] + 1)):
                issues.append("level_table_mismatch")
            buffs = detail.get("buffs", [])
            for buff in buffs:
                values = buff.get("values", [])
                if any(
                    l > len(values)
                    or not isinstance(values[l - 1].get("value"), (int, float))
                    or not math.isfinite(values[l - 1]["value"])
                    for l in levels
                ):
                    issues.append("missing_or_invalid_value")
                mapping = mappings.get((node_id, buff["id"]))
                if mapping and mapping_matches(mapping, raw, meta, buff):
                    effects.extend(mapping["effects"])
                elif mapping:
                    issues.append("stale_mapping")
        if issues:
            status, reason = "data_issue", ", ".join(sorted(set(issues)))
        elif effects:
            status, reason = (
                "mapped",
                "Explicit reviewed ID/buff/unit/scope mapping; activation requires excluding overlapping manual totals.",
            )
        elif meta["tree_type"] != 0:
            status, reason = (
                "other_progression",
                "Not a standard research tree; ownership, selection or activation cannot be established by a research level alone.",
            )
        elif not buffs:
            status, reason = (
                "no_numeric_buff",
                "Unlock, reward or progression record with no numeric combat buff in the export.",
            )
        else:
            status, reason = (
                "not_modelled",
                "Numeric data retained; effect, stacking, units or encounter/activation conditions require an explicit mapping.",
            )
        rows.append(
            {
                "node_id": node_id,
                **meta,
                "status": status,
                "reason": reason,
                "effects": effects,
                "buff_count": len(buffs),
                "source": f"https://stfc.space/researches/{node_id}",
            }
        )
    return {
        "checked": "2026-09-13",
        "counts": dict(Counter(r["status"] for r in rows)),
        "node_count": len(rows),
        "effect_count": sum(len(r["effects"]) for r in rows),
        "nodes": rows,
    }


if __name__ == "__main__":
    report = audit()
    destination = Path(__file__).parent / "data" / "research_coverage.json"
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print({k: v for k, v in report.items() if k != "nodes"})
