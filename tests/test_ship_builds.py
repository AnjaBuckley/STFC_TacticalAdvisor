"""Catalogue build regressions use public data and synthetic accounts."""

import pytest
from fastapi.testclient import TestClient

import app
from engine.catalogue import ship_catalogue, ship_stats
from engine.ship_builds import build_ship, reference_data
from service import validate_profile


def test_all_bundled_ships_produce_valid_base_builds():
    assert len(ship_catalogue()) >= 115
    for record in ship_catalogue().values():
        ship = build_ship(record["name"], 1, 1)["ship"]
        validate_profile({"ops_level": 1, "officers": [], "ships": [ship]})
        assert ship["stat_basis"] == "base"
        assert ship["stat_source"]["version"] != "legacy snapshot"


def test_level_affects_hull_not_weapon_component_damage():
    first = build_ship("Centurion", 1, 1)["ship"]
    second = build_ship("Centurion", 2, 1)["ship"]
    assert second["base_stats"]["health"] > first["base_stats"]["health"]
    assert second["base_stats"]["attack"] == first["base_stats"]["attack"]
    assert second["weapons"] == first["weapons"]


def test_component_upgrade_changes_only_that_component():
    base = build_ship("Centurion", 1, 1)
    slot = next(
        s
        for s in base["components"]
        if s["label"].startswith("Weapon") and len(s["tiers"]) > 1
    )
    upgraded = build_ship("Centurion", 1, 1, {slot["slot"]: 2})
    assert (
        upgraded["ship"]["base_stats"]["attack"] > base["ship"]["base_stats"]["attack"]
    )
    assert (
        upgraded["ship"]["base_stats"]["health"] == base["ship"]["base_stats"]["health"]
    )


def test_unknown_build_is_not_extrapolated():
    for args in [
        ("unknown", 1, 1),
        ("Centurion", 200, 1),
        ("Centurion", 1, 30),
        ("Centurion", 1, 1, {"999": 2}),
        ("Centurion", 1, 1, {"0": 9}),
    ]:
        with pytest.raises(ValueError):
            build_ship(*args)


def test_ship_research_is_additive_and_displayed_totals_not_rebuffed():
    ship = build_ship("Centurion", 1, 1)["ship"]
    base = ship["base_stats"]["armor"]
    ship["research_bonuses"] = {"ship_armor": 0.5}
    result, _, _ = ship_stats(ship, [], {"research": {"combat": {"ship_armor": 2}}})
    assert result["armor"] == base * 3.5
    ship["stat_basis"] = "displayed"
    result, _, _ = ship_stats(ship, [], {"research": {"combat": {"ship_armor": 2}}})
    assert result["armor"] == base


def test_ship_build_api_validates_exact_inputs():
    client = TestClient(app.app)
    headers = {"x-stfc-token": app.TOKEN}
    response = client.post(
        "/api/ships/build",
        headers=headers,
        json={"name": "Centurion", "level": 1, "tier": 1},
    )
    assert response.status_code == 200
    assert response.json()["ship"]["catalogue_id"]
    assert (
        client.post(
            "/api/ships/build",
            headers=headers,
            json={"name": "Centurion", "level": 200, "tier": 1},
        ).status_code
        == 422
    )


def test_sheet_reference_is_static_not_an_owned_fleet():
    data = reference_data()
    assert len(data["ships"]) >= 100
    assert "officers" not in data and "research" not in data
    assert data["ships"]["augur"]["ability"]["values"]["1"] == 0.5


def test_extra_critical_bonuses_apply_to_explicit_weapons():
    from engine.combat_simulator import simulate_combat

    ship = build_ship("Centurion", 1, 1)["ship"]
    ship["crit_chance_bonus"] = 1
    ship["crit_damage_bonus"] = 2
    result = simulate_combat(
        ship,
        [],
        [],
        {},
        {
            "name": "Synthetic",
            "hp": 1e12,
            "base_damage": 0,
            "max_rounds": 1,
            "debug_events": True,
        },
        "pve_hostile",
        num_simulations=1,
    )
    events = [e for e in result["event_trace"] if e["side"] == "player"]
    assert events and all(e["critical"] for e in events)
    assert all(e["crit_multiplier"] == 3.5 for e in events)
