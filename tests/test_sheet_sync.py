"""Sync writes only isolated test profiles; Google fetching is replaced locally."""

import json
import threading
from datetime import datetime, timedelta

import pytest

import paths
import sheet_sync
from service import read_profile, save_profile
from sheet_sync import SheetSync
from tests.test_officer_tool_sheet import _make_workbook
from tests.test_rules_regressions import small_profile

URL = "https://docs.google.com/spreadsheets/d/1234567890abcdefghijklmnopqrstuv_TEST_SHEET/edit?usp=sharing"


@pytest.fixture
def sync(tmp_path, monkeypatch):
    target = tmp_path / "player_profile.json"
    profile = small_profile()
    profile["officers"].append({"name": "0718", "available": False, "class": "Science"})
    target.write_text(json.dumps(profile))
    monkeypatch.setattr(paths, "profile_path", lambda: target)
    monkeypatch.setattr(sheet_sync, "fetch_workbook", lambda source: _make_workbook())
    service = SheetSync()
    yield service
    service.stop()


def test_sync_backups_idempotence_and_manual_field_preservation(sync, tmp_path):
    original, _ = read_profile()
    sync.configure(URL, True)
    first = sync.run()
    updated, _ = read_profile()
    assert first["last_result"] == "updated"
    assert first["officers_in_sheet"] == 2
    assert updated["ships"] == original["ships"]
    assert updated["research"] == original["research"]
    officer = next(o for o in updated["officers"] if o["name"] == "0718")
    assert officer["available"] is False
    assert officer["class"] == "Science"
    assert officer["level"] == 30
    backups = list(tmp_path.glob("player_profile.backup-*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == original
    assert sync.run()["last_result"] == "unchanged"
    assert len(list(tmp_path.glob("player_profile.backup-*.json"))) == 1
    next_check = datetime.fromisoformat(first["next_check"])
    checked = datetime.fromisoformat(first["last_checked"])
    assert next_check - checked == timedelta(minutes=5)
    assert SheetSync().status()["enabled"] is True


def test_failed_fetch_retains_account_and_last_success(sync, monkeypatch):
    sync.configure(URL, True)
    successful = sync.run()
    before = read_profile()

    def unavailable(_):
        raise RuntimeError("Sheet is no longer shared")

    monkeypatch.setattr(sheet_sync, "fetch_workbook", unavailable)
    failed = sync.run()
    assert read_profile() == before
    assert failed["last_success"] == successful["last_success"]
    assert failed["last_result"] == "error"
    assert failed["enabled"] is True
    assert failed["next_check"]
    assert "no longer shared" in failed["last_error"]


def test_pause_discards_in_flight_download(sync, monkeypatch):
    before = read_profile()

    def pause_during_fetch(_):
        sync.configure(URL, False)
        return _make_workbook()

    monkeypatch.setattr(sheet_sync, "fetch_workbook", pause_during_fetch)
    sync.configure(URL, True)
    status = sync.run()
    assert status["enabled"] is False
    assert status["syncing"] is False
    assert read_profile() == before


def test_download_merges_with_latest_local_profile(sync, monkeypatch):
    def edit_during_fetch(_):
        current, revision = read_profile()
        current["ships"][0]["available"] = False
        save_profile(current, revision)
        return _make_workbook()

    monkeypatch.setattr(sheet_sync, "fetch_workbook", edit_during_fetch)
    sync.configure(URL, True)
    sync.run()
    assert read_profile()[0]["ships"][0]["available"] is False


def test_invalid_sheet_does_not_touch_profile(sync, monkeypatch):
    before = read_profile()
    monkeypatch.setattr(sheet_sync, "parse_roster", lambda wb: [])
    sync.configure(URL, True)
    assert sync.run()["last_result"] == "error"
    assert read_profile() == before


def test_background_worker_polls_without_a_browser(sync, monkeypatch):
    monkeypatch.setattr(sheet_sync, "INTERVAL_SECONDS", 0.05)
    second_fetch = threading.Event()
    calls = []

    def fetch(_):
        calls.append(1)
        if len(calls) >= 2:
            second_fetch.set()
        return _make_workbook()

    monkeypatch.setattr(sheet_sync, "fetch_workbook", fetch)
    sync.configure(URL, True)
    sync.start()
    assert second_fetch.wait(3)
    sync.stop()
    assert not sync.thread.is_alive()


def test_paused_sync_does_not_fetch(sync, monkeypatch):
    monkeypatch.setattr(
        sheet_sync,
        "fetch_workbook",
        lambda _: pytest.fail("Unexpected network request"),
    )
    sync.configure(URL, False)
    assert sync.run()["enabled"] is False


@pytest.mark.parametrize(
    "url",
    [
        "http://docs.google.com/spreadsheets/d/abcdefghijklmopqrstuv/edit",
        "https://example.com/spreadsheets/d/abcdefghijklmopqrstuv/edit",
    ],
)
def test_reject_non_google_url(sync, url):
    with pytest.raises(ValueError):
        sync.configure(url, True)
