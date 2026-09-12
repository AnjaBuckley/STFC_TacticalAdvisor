"""
Path resolution — STFC Advisor

Two distinct kinds of paths, so the app behaves the same running from
source (`python run_app.py`) and from a frozen PyInstaller build:

  resource_path()   Read-only bundled data (ships/officers/hostiles JSON,
                     the blank profile template, app.py itself). Lives
                     inside the PyInstaller bundle (sys._MEIPASS) when
                     frozen, next to this file otherwise.

  profile_path()     Where the player's live profile is read from and
                      saved to. Must survive across runs, so it can never
                      be the bundle location (temporary/read-only when
                      frozen). Frozen: a per-user folder outside the app
                      install (%LOCALAPPDATA% on Windows, ~/.stfc-advisor
                      elsewhere). Dev: the profiles/ folder next to the
                      source, unchanged from prior behavior.
"""

import os
import shutil
import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).parent


def resource_path(*parts: str) -> Path:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else _SOURCE_ROOT
    return base.joinpath(*parts)


def _writable_dir() -> Path:
    if override := os.environ.get("STFC_ADVISOR_DATA_DIR"):
        return Path(override).expanduser().resolve()
    if not getattr(sys, "frozen", False):
        return _SOURCE_ROOT / "profiles"
    root = (
        Path(os.environ.get("LOCALAPPDATA", Path.home())) / "STFC Advisor" / "profiles"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def data_dir() -> Path:
    directory = _writable_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def profile_path() -> Path:
    """The live, writable player_profile.json — seeded from the bundled
    blank template on first run if it doesn't exist yet."""
    target = data_dir() / "player_profile.json"
    if not target.exists():
        template = resource_path("profiles", "player_profile.template.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(template, target)
    return target
