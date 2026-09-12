"""API flows use isolated profiles; no writes touch the player's account."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

import paths
from app import TOKEN, app
from tests.test_rules_regressions import small_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    profile = tmp_path / "player_profile.json"
    profile.write_text(json.dumps(small_profile()))
    monkeypatch.setattr(paths, "profile_path", lambda: profile)
    with TestClient(app) as c:
        c.headers.update({"X-STFC-Token": TOKEN})
        yield c


def test_bootstrap_and_assets(client):
    r = client.get("/api/bootstrap")
    assert r.status_code == 200
    assert r.json()["profile"]["ops_level"] == 71
    assert r.json()["token"] == TOKEN
    assert len(r.json()["tasks"]) == 9
    for route in ["/", "/assets/app.js", "/assets/style.css", "/api/health"]:
        assert client.get(route).status_code == 200


def test_sheet_sync_status_pause_and_validation(client):
    assert client.get("/api/sync").json()["enabled"] is False
    url = "https://docs.google.com/spreadsheets/d/1234567890abcdefghijklmnopqrstuv_TEST_SHEET/edit"
    response = client.put("/api/sync", json={"url": url, "enabled": False})
    assert response.status_code == 200
    assert response.json()["interval_seconds"] == 300
    assert client.post("/api/sync/run").json()["enabled"] is False
    assert (
        client.put(
            "/api/sync", json={"url": "https://example.com/not-a-sheet"}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/sync", json={"url": url}, headers={"X-STFC-Token": ""}
        ).status_code
        == 403
    )


def test_write_requires_local_token(client):
    assert (
        client.post("/api/recommend", json={}, headers={"X-STFC-Token": ""}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/recommend", json={}, headers={"Origin": "https://example.org"}
        ).status_code
        == 403
    )


def test_profile_save_is_atomic_backed_up_and_conflict_checked(client, tmp_path):
    initial = client.get("/api/bootstrap").json()
    changed = copy.deepcopy(initial["profile"])
    changed["ops_level"] = 72
    saved = client.put(
        "/api/profile", json={"profile": changed, "revision": initial["revision"]}
    )
    assert saved.status_code == 200
    assert client.get("/api/bootstrap").json()["profile"]["ops_level"] == 72
    backups = list(tmp_path.glob("player_profile.backup-*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == initial["profile"]
    assert (
        client.put(
            "/api/profile", json={"profile": changed, "revision": initial["revision"]}
        ).status_code
        == 409
    )
    assert not list(tmp_path.glob("*.tmp"))


def test_profile_import_preview_does_not_save(client):
    before = client.get("/api/bootstrap").json()
    updated = {**before["profile"], "ops_level": 75}
    r = client.post(
        "/api/import/preview?kind=profile",
        files={"file": ("account.json", json.dumps(updated), "application/json")},
    )
    assert r.status_code == 200
    assert r.json()["profile"]["ops_level"] == 75
    assert client.get("/api/bootstrap").json()["revision"] == before["revision"]
    body = {"profile": r.json()["profile"], "revision": r.json()["revision"]}
    assert client.put("/api/profile", json=body).status_code == 200
    assert client.get("/api/bootstrap").json()["profile"]["ops_level"] == 75


def test_invalid_import_leaves_profile_untouched(client):
    before = client.get("/api/bootstrap").json()["revision"]
    assert (
        client.post(
            "/api/import/preview?kind=profile", files={"file": ("broken.json", "{")}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/import/preview?kind=officers",
            files={"file": ("broken.xlsx", "not a workbook")},
        ).status_code
        == 422
    )
    assert client.get("/api/bootstrap").json()["revision"] == before


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(ops_level=0),
        lambda p: p["ships"][0]["base_stats"].update(health=-1),
        lambda p: p["officers"].append(p["officers"][0]),
    ],
)
def test_invalid_profile_is_not_saved(client, change):
    initial = client.get("/api/bootstrap").json()
    profile = copy.deepcopy(initial["profile"])
    change(profile)
    assert (
        client.put(
            "/api/profile", json={"profile": profile, "revision": initial["revision"]}
        ).status_code
        == 422
    )
    assert client.get("/api/bootstrap").json()["revision"] == initial["revision"]


def test_end_to_end_recommendation(client):
    r = client.post(
        "/api/recommend", json={"target_name": "Borg Probe", "level": 35, "top_n": 3}
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["recommendations"]) == 3
    assert data["warnings"]
    assert "unmodelled_abilities" in data["recommendations"][0]["simulation"]
    assert data["recommendations"][0]["ship"] == "Test Explorer"


def test_unknown_ship_is_not_replaced_by_fabricated_ship(client):
    r = client.post("/api/recommend", json={"ship_name": "Unowned Enterprise"})
    assert r.status_code == 422
    assert "owned combat ship" in r.json()["detail"]


def test_pvp_requires_opponent_input(client):
    r = client.post("/api/recommend", json={"task_type": "pvp"})
    assert r.status_code == 422
    assert "opponent" in r.json()["detail"]
    r = client.post(
        "/api/recommend",
        json={"task_type": "pvp", "target_stats": {"hp": 500000, "base_damage": 5000}},
    )
    assert r.status_code == 200


def test_duo_without_source_is_blocked(client):
    r = client.post(
        "/api/recommend",
        json={"task_type": "duo_wave_defense", "target_name": "Duo Wave Defense"},
    )
    assert r.status_code == 422
    assert "Critical Mitigation" in r.json()["detail"]


def test_wrong_mission_target_pair_rejected(client):
    assert (
        client.post(
            "/api/recommend",
            json={"task_type": "duo_wave_defense", "target_name": "Solo Wave Defense"},
        ).status_code
        == 422
    )


def test_academy_ops_gate(client):
    initial = client.get("/api/bootstrap").json()
    initial["profile"]["ops_level"] = 50
    client.put(
        "/api/profile",
        json={"profile": initial["profile"], "revision": initial["revision"]},
    )
    r = client.post(
        "/api/recommend",
        json={
            "task_type": "pve_academy_drone",
            "target_name": "Academy Training Drone",
        },
    )
    assert r.status_code == 422
    assert "Operations level 61" in r.json()["detail"]


def test_profile_export(client):
    r = client.get("/api/profile/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.json()["ops_level"] == 71


@pytest.mark.parametrize(
    "payload",
    [
        {"task_type": "unknown"},
        {"level": 0},
        {"top_n": 100},
        {"target_stats": {"crit_chance": 50}},
        {"target_stats": {"hp": -1}},
    ],
)
def test_invalid_mission_inputs_are_actionable(client, payload):
    assert client.post("/api/recommend", json=payload).status_code == 422


@pytest.mark.parametrize("value", ["bad", -2, True])
def test_bad_research_values_cannot_corrupt_saved_profile(client, value):
    initial = client.get("/api/bootstrap").json()
    initial["profile"]["research"]["combat"] = {"ship_weapon_damage": value}
    r = client.put(
        "/api/profile",
        json={"profile": initial["profile"], "revision": initial["revision"]},
    )
    assert r.status_code == 422
    assert client.get("/api/bootstrap").json()["revision"] == initial["revision"]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://example.org/spreadsheets/d/abcdefghijklmnopqrst",
        "http://docs.google.com/spreadsheets/d/abcdefghijklmnopqrst",
    ],
)
def test_sheet_preview_rejects_non_google_https_sources(client, url):
    assert (
        client.post("/api/import/sheet-preview", json={"url": url}).status_code == 422
    )


def test_missing_operations_level_cannot_be_saved(client):
    initial = client.get("/api/bootstrap").json()
    del initial["profile"]["ops_level"]
    assert (
        client.put(
            "/api/profile",
            json={"profile": initial["profile"], "revision": initial["revision"]},
        ).status_code
        == 422
    )


@pytest.mark.parametrize("target", ["Academy Training Drone", "Duo Wave Defense"])
def test_general_pve_cannot_bypass_special_mission_rules(client, target):
    assert (
        client.post(
            "/api/recommend", json={"task_type": "pve_hostile", "target_name": target}
        ).status_code
        == 422
    )


def test_updated_schema_accepts_real_profile_and_blank_template():
    from pathlib import Path

    import jsonschema

    base = Path(__file__).resolve().parents[1] / "profiles"
    schema = json.loads((base / "player_profile.schema.json").read_text())
    for name in ["player_profile.json", "player_profile.template.json"]:
        jsonschema.validate(json.loads((base / name).read_text()), schema)
