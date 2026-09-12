"""Persistent, one-way Google Sheet polling for the local application server."""

import copy
import json
import logging
import os
import re
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import paths
from ingest.officer_tool_sheet import (
    apply_to_profile,
    fetch_workbook,
    parse_bonuses,
    parse_roster,
)
from service import PROFILE_LOCK, read_profile, save_profile, validate_profile

INTERVAL_SECONDS = 300


def utcnow():
    return datetime.now(timezone.utc)


def sheet_url(value):
    parsed = urlparse(value)
    match = re.fullmatch(r"/spreadsheets/d/([a-zA-Z0-9_-]{20,})(?:/.*)?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "docs.google.com" or not match:
        raise ValueError("Use a shared https://docs.google.com/spreadsheets/d/ link.")
    return f"https://docs.google.com/spreadsheets/d/{match.group(1)}/edit"


class SheetSync:
    def __init__(self):
        self.lock = threading.RLock()
        self.run_lock = threading.Lock()
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.thread = None
        self.busy = False
        self.generation = 0
        self.state = {"enabled": False, "url": "", "last_error": None}
        self.path = paths.profile_path().with_name("google_sheet_sync.json")
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                saved["url"] = sheet_url(saved["url"])
                self.state.update(saved)
            except (ValueError, KeyError, TypeError):
                self.state["last_error"] = (
                    "Saved connection is invalid. Reconnect your sheet."
                )

    def _persist(self):
        fd, name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.state, stream, indent=2, allow_nan=False)
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)

    def status(self):
        with self.lock:
            return {
                **copy.deepcopy(self.state),
                "syncing": self.busy,
                "interval_seconds": INTERVAL_SECONDS,
                "profile_revision": read_profile()[1],
            }

    def configure(self, url, enabled):
        canonical = sheet_url(url)
        with self.lock:
            self.generation += 1
            if canonical != self.state["url"]:
                self.state = {"url": canonical, "enabled": False, "last_error": None}
            self.state.update(enabled=enabled, next_check=None)
            self._persist()
        self.wake.set()
        return self.status()

    def run(self):
        if not self.run_lock.acquire(blocking=False):
            return self.status()
        try:
            with self.lock:
                if not self.state["enabled"]:
                    return self.status()
                url, generation = self.state["url"], self.generation
                self.busy = True
            try:
                # Network I/O never holds the profile lock or blocks local edits.
                workbook = fetch_workbook(url.split("/d/", 1)[1].split("/", 1)[0])
                try:
                    bonuses, roster = parse_bonuses(workbook), parse_roster(workbook)
                finally:
                    workbook.close()
                if not roster:
                    raise ValueError("The sheet has no readable officer rows.")
                # Ignore a result fetched before the user paused/replaced the connection.
                with self.lock:
                    if generation != self.generation or not self.state["enabled"]:
                        self.busy = False
                        return self.status()
                    with PROFILE_LOCK:
                        current, revision = read_profile()
                        updated, diff = apply_to_profile(
                            copy.deepcopy(current), bonuses, roster
                        )
                        validate_profile(updated)
                        changed = updated != current
                        if changed:
                            save_profile(updated, revision)
                    now = utcnow().isoformat()
                    self.state.update(
                        last_success=now,
                        last_error=None,
                        officers_in_sheet=len(roster),
                        last_result="updated" if changed else "unchanged",
                        last_diff=diff,
                    )
                    if changed:
                        self.state["last_changed"] = now
            except Exception as exc:
                logging.getLogger(__name__).exception("Google Sheet sync failed")
                with self.lock:
                    if generation == self.generation:
                        self.state["last_error"] = (
                            f"Sync failed; your saved account is unchanged. {str(exc)[:250]}"
                        )
                        self.state["last_result"] = "error"
            finally:
                with self.lock:
                    self.busy = False
                    if generation == self.generation:
                        now = utcnow()
                        self.state["last_checked"] = now.isoformat()
                        self.state["next_check"] = (
                            now + timedelta(seconds=INTERVAL_SECONDS)
                        ).isoformat()
                        self._persist()
                self.wake.set()
            return self.status()
        finally:
            self.run_lock.release()

    def _loop(self):
        while not self.stop_event.is_set():
            self.wake.clear()
            with self.lock:
                enabled = self.state["enabled"]
                due = self.state.get("next_check")
                delay = (
                    max(0, (datetime.fromisoformat(due) - utcnow()).total_seconds())
                    if due
                    else 0
                )
            if enabled and delay <= 0:
                self.run()
                # A concurrent manual sync may hold run_lock; avoid a busy loop.
                self.wake.wait(1)
            else:
                self.wake.wait(
                    min(delay, INTERVAL_SECONDS) if enabled else INTERVAL_SECONDS
                )

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._loop, name="google-sheet-sync", daemon=True
        )
        self.thread.start()

    def stop(self):
        with self.lock:
            self.generation += 1
        self.stop_event.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=40)
