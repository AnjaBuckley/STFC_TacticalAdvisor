"""Versioned research metadata; progression never implies ownership of other systems."""

import hashlib
import json
from functools import lru_cache

from engine.catalogue import BASE


@lru_cache(maxsize=1)
def research_metadata():
    texts = {
        (r["id"], r["key"]): r["text"]
        for r in json.loads((BASE / "en_research.json").read_text(encoding="utf-8"))
    }
    return {
        str(r["id"]): {
            "name": texts.get((r["loca_id"], "research_project_name"), str(r["id"])),
            "description": texts.get(
                (r["loca_id"], "research_project_description"), ""
            ),
            "tree": texts.get(
                (r["research_tree"]["loca_id"], "research_tree_name"),
                str(r["research_tree"]["loca_id"]),
            ),
            "tree_type": r["research_tree"]["type"],
            "max_level": r["max_level"],
        }
        for r in json.loads(
            (BASE / "research_summary.json").read_text(encoding="utf-8")
        )
    }


def mapping_matches(mapping, raw, metadata, buff):
    """Fail closed on upstream edits, scope changes or non-deterministic procs."""
    return bool(
        metadata.get("tree_type") == 0
        and metadata.get("description") == mapping.get("description")
        and hashlib.sha256(raw).hexdigest() == mapping.get("detail_sha256")
        and buff.get("value_is_percentage") == mapping.get("export_percentage")
        and all(
            v.get("chance") == 1
            for v in buff.get("values", [])[: metadata["max_level"]]
        )
    )


@lru_cache(maxsize=1)
def reviewed_registry():
    return json.loads(
        (BASE.parent / "research_effects.json").read_text(encoding="utf-8")
    )


@lru_cache(maxsize=2048)
def reviewed_values(node_id, buff_id):
    registry = reviewed_registry()
    mapping = next(
        (
            m
            for m in registry["mappings"]
            if m["node_id"] == node_id and m["buff_id"] == buff_id
        ),
        None,
    )
    path = BASE / "research" / f"{node_id}.json"
    if not mapping or not path.exists():
        return None
    raw = path.read_bytes()
    detail = json.loads(raw)
    buff = next((b for b in detail["buffs"] if b["id"] == buff_id), {})
    meta = research_metadata().get(node_id, {})
    if not mapping_matches(mapping, raw, meta, buff):
        return None
    return mapping, {
        r["id"]: buff["values"][r["id"] - 1]["value"] for r in detail["levels"]
    }


def source_is_current(source):
    record = reviewed_values(str(source.get("node_id")), source.get("buff_id"))
    if record is None:
        return False
    mapping, values = record
    return bool(
        source.get("mapping_version") == reviewed_registry()["reviewed"]
        and source.get("effect") in mapping["effects"]
        and source.get("unit") == mapping["unit"]
        and source.get("conditions", {}) == mapping["conditions"]
        and source.get("contexts") == mapping["contexts"]
        and source.get("value") == values.get(source.get("level"))
    )


@lru_cache(maxsize=1)
def faction_names():
    return {
        r["id"]: r["text"]
        for r in json.loads((BASE / "en_factions.json").read_text(encoding="utf-8"))
        if r["key"] == "faction_name"
    }
