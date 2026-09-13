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
        assert compute_research_buffs(rows)["mapped_sources"] == len(entry["effects"])


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


def test_padding_beyond_real_max_level_is_not_imported():
    rows = [
        {
            "id": "176472186",
            "level": 3,
            "done": True,
            "name": "Synthetic",
            "description": "",
        }
    ]
    report = compute_research_buffs(rows)
    assert report["invalid_levels"] and not report["sources"]


def test_registry_change_quarantines_saved_effect():
    rows = [
        {
            "id": "3016411865",
            "level": 1,
            "done": True,
            "name": "Synthetic",
            "description": "",
        }
    ]
    source = compute_research_buffs(rows)["sources"][0]
    source["enabled"] = True
    profile = {"combat_sources": [source]}
    assert source_effects(profile, {}, "pve_hostile", {})[0]["weapon_damage"] == 1
    source["mapping_version"] = "obsolete"
    effects, warnings = source_effects(profile, {}, "pve_hostile", {})
    assert effects == {} and warnings


def test_changed_detail_hash_prevents_mapping(tmp_path, monkeypatch):
    import ingest.research_csv as mod

    raw = json.loads((mod._RESEARCH_DIR / "3016411865.json").read_text())
    raw["buffs"][0]["values"][0]["value"] = 42
    (tmp_path / "3016411865.json").write_text(json.dumps(raw))
    monkeypatch.setattr(mod, "_RESEARCH_DIR", tmp_path)
    report = compute_research_buffs(
        [
            {
                "id": "3016411865",
                "level": 1,
                "done": True,
                "name": "Synthetic",
                "description": "",
            }
        ]
    )
    assert report["mapped_sources"] == 0
    assert all(
        s["status"] == "unreviewed" and not s["enabled"] for s in report["sources"]
    )


def test_reimport_updates_scopes_and_disables_unresolved_old_records():
    report = compute_research_buffs(
        [
            {
                "id": "3016411865",
                "level": 1,
                "done": True,
                "name": "Synthetic",
                "description": "",
            }
        ]
    )
    old = copy.deepcopy(report["sources"][0])
    old["conditions"] = {"ship_class": "Survey"}
    old["enabled"] = True
    profile, _ = apply_to_profile({"combat_sources": [old]}, report)
    assert profile["combat_sources"][0]["conditions"] == {}
    assert profile["combat_sources"][0]["enabled"]
    profile, _ = apply_to_profile(profile, {"sources": []})
    assert not profile["combat_sources"][0]["enabled"]


def test_imported_research_does_not_double_buff_displayed_stats():
    source = compute_research_buffs(
        [
            {
                "id": "3016411865",
                "level": 1,
                "done": True,
                "name": "Synthetic",
                "description": "",
            }
        ]
    )["sources"][0]
    source["enabled"] = True
    effects, warnings = source_effects(
        {"combat_sources": [source]}, {"stat_basis": "displayed"}, "pve_hostile", {}
    )
    assert effects == {} and warnings


def test_scoped_weapon_bonus_matches_manual_total_once():
    from engine.combat_simulator import simulate_combat
    from tests.test_combat_simulator import _ship, _target

    for explicit in (False, True):
        ship = _ship()
        ship["crit_chance"] = 0
        if explicit:
            ship["weapons"] = [
                {
                    "damage": 50000,
                    "shots": 1,
                    "warmup": 0,
                    "cooldown": 1,
                    "type": "energy",
                }
            ]
        target = _target()
        target["hp"] = 2000000
        manual = {"research": {"combat": {"ship_weapon_damage": 1}}}
        imported = {
            "combat_sources": [
                {
                    "id": "synthetic",
                    "effect": "weapon_damage",
                    "value": 1,
                    "unit": "fraction",
                    "contexts": ["pve"],
                    "status": "manual",
                }
            ]
        }
        a = simulate_combat(
            ship, [], [], manual, target, "pve_hostile", num_simulations=10, rng_seed=42
        )
        b = simulate_combat(
            ship,
            [],
            [],
            imported,
            target,
            "pve_hostile",
            num_simulations=10,
            rng_seed=42,
        )
        for key in [
            "avg_rounds_to_kill",
            "avg_damage_taken",
            "avg_combat_rounds",
            "kill_probability",
        ]:
            assert a[key] == b[key], (explicit, key, a[key], b[key])


def test_full_catalogue_coverage_and_snapshot_integrity():
    import hashlib

    from audit_research_database import audit
    from engine.catalogue import BASE

    manifest = json.loads((BASE / "RESEARCH_SNAPSHOT.json").read_text())
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    report = audit()
    assert report["node_count"] == manifest["research_count"]
    assert report["counts"].get("data_issue", 0) == 0
    assert len({r["node_id"] for r in report["nodes"]}) == report["node_count"]
    assert all(r["tree_type"] == 0 for r in report["nodes"] if r["status"] == "mapped")
