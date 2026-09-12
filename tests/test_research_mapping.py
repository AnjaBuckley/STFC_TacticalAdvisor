"""Public catalogue and synthetic progression fixtures only."""

import copy
import json
from pathlib import Path

from engine.ship_builds import build_ship
from engine.sources import source_effects, validate_sources
from ingest.research_csv import (
    apply_to_profile,
    compute_research_buffs,
    parse_research_csv,
)


def test_current_is_completed_and_highest_level_is_used_once():
    rows = parse_research_csv(
        b"Name,Level,Done,id,\nTest,1,Yes,331012121,\nTest,2,Current,331012121,\nTest,3,No,331012121,\n"
    )
    report = compute_research_buffs(rows)
    assert report["progress"][0]["level"] == 2
    assert report["current_rows"] == 1
    assert report["sources"] == compute_research_buffs([rows[1]])["sources"]


def test_public_registry_exact_descriptions_and_units():
    registry = json.loads(Path("data/research_effects.json").read_text())
    mappings = registry["mappings"]
    for entry in mappings:
        rows = [
            {
                "id": str(entry["node_id"]),
                "level": 1,
                "done": True,
                "name": "Synthetic",
                "description": entry["description"],
            }
        ]
        report = compute_research_buffs(rows)
        mapped = [s for s in report["sources"] if s["status"] == "reviewed"]
        assert {s["effect"] for s in mapped} == set(entry["effects"])
        assert all(s["enabled"] is False for s in mapped)
        validate_sources(mapped)
        rows[0]["description"] = "Changed upstream description"
        assert compute_research_buffs(rows)["mapped_sources"] == 0


def test_progress_only_change_and_reimport_idempotence():
    report = {"sources": [], "progress": [{"node_id": "synthetic", "level": 2}]}
    profile, diff = apply_to_profile({}, report)
    assert diff
    assert not apply_to_profile(copy.deepcopy(profile), report)[1]


def test_grade_and_faction_scopes_fail_closed():
    source = {
        "id": "synthetic",
        "effect": "hull_health",
        "value": 0.4,
        "unit": "fraction",
        "status": "reviewed",
        "contexts": ["pve"],
        "conditions": {"ship_grade_min": 4, "ship_faction": "Romulan"},
    }
    validate_sources([source])
    profile = {"combat_sources": [source]}
    assert source_effects(profile, {"grade": 4, "faction": "Romulan"}, "hostile", {})[
        0
    ] == {"hull_health": 0.4}
    for ship in (
        {"grade": 3, "faction": "Romulan"},
        {"grade": 4, "faction": "Federation"},
        {},
    ):
        assert source_effects(profile, ship, "hostile", {})[0] == {}
    assert (
        source_effects(
            profile,
            {"grade": 4, "faction": "Romulan"},
            "hostile",
            {"encounter_context": "pvp"},
        )[0]
        == {}
    )


def test_vengeance_reference_preserves_effect_boundaries():
    data = build_ship("U.S.S. VENGEANCE", 1, 1)
    reference = data["catalogue_reference"]
    assert len(reference["abilities"]) == 2
    assert len(reference["refits"]) == 6
    assert len(reference["active_abilities"]) == 2
    assert reference["abilities"][0]["level_value"]["value"] == 0.25
    assert "Non-Armada" in reference["abilities"][0]["description"]
    assert "<color" not in str(reference)
    assert "combat_sources" not in data["ship"]
