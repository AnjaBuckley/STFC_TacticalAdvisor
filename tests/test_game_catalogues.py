"""Public game data plus synthetic ships; no player accounts are used."""

import copy
import json
from pathlib import Path

import pytest

from engine.abilities import load_abilities, officer_source_current
from engine.effects import ability_plan
from engine.pvp_bands import bands, check_band
from engine.sources import source_effects, validate_sources
from engine.technology import (
    technology_catalogue,
    technology_record,
    technology_sources,
    validate_technologies,
)


def equipment(ident=482782456, tier=1, level=1, enabled=True):
    return {"id": ident, "tier": tier, "level": level, "enabled": enabled}


def test_technology_requires_activation_and_uses_actual_tier_level():
    ship = {"technologies": [equipment(enabled=False)]}
    assert technology_sources(ship) == ([], [])
    ship["technologies"] = [equipment()]
    effects, omissions = source_effects({}, ship, "pve_hostile", {})
    assert effects == {"hull_health": 0.05}
    assert not omissions
    ship["technologies"] = [equipment(tier=2, level=6)]
    assert source_effects({}, ship, "pve_hostile", {})[0] == {
        "hull_health": 0.17,
        "shield_health": 0.08,
    }
    ship["stat_basis"] = "displayed"
    assert technology_sources(ship)[0] == []
    assert "duplicating" in technology_sources(ship)[1][0]


def test_technology_scopes_and_separate_equipment_slots():
    # S31 Torpedo Pods' hull health belongs to Battleships only.
    ship = {
        "technologies": [equipment(473132032, tier=3, level=11)],
        "ship_class": "Explorer",
    }
    assert "hull_health" not in source_effects({}, ship, "pve_hostile", {})[0]
    ship["ship_class"] = "Battleship"
    assert source_effects({}, ship, "pve_hostile", {})[0]["hull_health"] > 0
    with pytest.raises(ValueError):
        validate_technologies([equipment(), equipment()])
    with pytest.raises(ValueError):
        validate_technologies([equipment(level=6)])
    with pytest.raises(ValueError):
        validate_technologies([equipment(tier=5, level=21)])
    with pytest.raises(ValueError):
        validate_technologies([equipment(tier=2, level=1)])
    with pytest.raises(ValueError):
        validate_technologies([equipment(level=True)])


def test_every_technology_tier_endpoint_has_valid_typed_sources():
    for ident, meta in technology_catalogue().items():
        raw, _ = technology_record(ident)
        for tier in raw["tiers"]:
            rank = int(tier["rank"])
            if rank > meta["tier_max"]:
                continue
            entries = [equipment(ident, rank, tier["max_level"])]
            validate_technologies(entries)
            sources, _ = technology_sources({"technologies": entries})
            validate_sources(sources)


def test_stale_technology_mapping_is_omitted(monkeypatch):
    from engine import technology

    mappings = copy.deepcopy(technology.technology_mappings())
    for row in mappings:
        row["sha256"] = "changed"
    monkeypatch.setattr(technology, "technology_mappings", lambda: mappings)
    sources, omissions = technology_sources({"technologies": [equipment()]})
    assert not sources and omissions


def test_standard_pvp_ops_is_separate_and_does_not_extrapolate():
    for level, row in bands().items():
        if level < 10:
            continue
        assert (
            check_band(level, max(10, row["lower"]), "pvp")["status"] == "within_band"
        )
        assert check_band(level, row["upper"] + 1, "pvp")["status"] == "outside_band"
    assert check_band(9, 10, "pvp")["status"] == "protected"
    assert check_band(14, 15, "station_raid")["status"] == "protected"
    assert check_band(81, 80, "pvp")["status"] == "unknown"
    assert check_band(40, None, "pvp")["status"] == "unknown"


def test_full_officer_names_resolve_without_merging_mudd_variants():
    cat = load_abilities()
    assert cat.get("Grace Chen") is cat.get("Chen")
    assert cat.get("SNW Christopher Pike") is cat.get("SNW Pike")
    assert cat.get("Harcourt Fenton Mudd") is not cat.get("Harry Mudd")
    assert cat.get("Mudd") is cat.get("Harry Mudd")
    assert cat["Harry Mudd"]["oa"]["effect"] == "weapon_damage"
    assert cat["Harcourt Fenton Mudd"]["oa"]["effect"] == "shots"
    for name in ["Harry Kim", "Neelix"]:
        assert cat[name]["oa"]["identity_review_required"]
    args = ("pve_hostile", {"level": 30, "weapons": [{"type": "energy"}]})
    short = ability_plan([{"name": "Chen", "rank": 3}], [], *args)
    full = ability_plan([{"name": "Grace Chen", "rank": 3}], [], *args)
    assert short == full
    rec = copy.deepcopy(cat["Chen"]["oa"])
    assert officer_source_current(rec)
    rec["catalogue_reference"]["sha256"] = "changed"
    assert not officer_source_current(rec)


def test_public_inventory_and_comparison_are_complete():
    data = json.loads(Path("data/catalogue_coverage.json").read_text())
    assert {k: len(v) for k, v in data["categories"].items()} == {
        "ship": 115,
        "officer": 292,
        "forbidden_tech": 71,
        "hostile": 5513,
        "pvp_bands": 80,
    }
    assert not data["officer_value_counts"].get("values_differ")
    assert data["officer_value_counts"]["missing_model"] > 0


def test_aliases_cannot_fill_two_bridge_seats():
    from optimizer.crew_optimizer import find_optimal_crew
    from tests.test_rules_regressions import small_profile

    profile = small_profile()
    profile["officers"] = [{"name": "Chen"}, {"name": "Grace Chen"}, {"name": "Moreau"}]
    with pytest.raises(ValueError, match="three available officers"):
        find_optimal_crew(profile, {"task_type": "pve_hostile", "target": {}})
