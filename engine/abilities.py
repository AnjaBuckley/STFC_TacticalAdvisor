"""
Structured Ability Knowledge Base — STFC

Loads data/abilities.json (LLM-compiled from the free-text officer
descriptions) and answers the questions the optimizer actually asks:

  - How relevant is this officer's kit to this task, offensively/defensively?
  - Does this officer bring a specific effect (isolytic, apex barrier, ...)?
  - How good is this officer's below-deck ability for this task?

Each officer has a captain maneuver ("cm") OR below-deck ability ("bda"),
plus an officer ability ("oa"). Each record carries:
  effect  - controlled vocabulary (crit_chance, isolytic_damage, ...)
  role    - "off" | "def" | "amp" | "util"
  scope   - "any" | "pvp" | "pve" | "armada" | "station" | "node"
            | "mining" | "wave_defense"
  targets - optional conditions (hostile types, factions, enemy ship classes)
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_ABILITIES_PATH = Path(__file__).parent.parent / "data" / "abilities.json"

# Which ability scopes are active for each task type
TASK_SCOPES = {
    "pvp": {"any", "pvp"},
    "pve_hostile": {"any", "pve"},
    "pve_general": {"any", "pve"},
    "pve_academy_drone": {"any", "pve"},
    "wave_defense": {"any", "pve", "wave_defense"},
    "duo_wave_defense": {"any", "pve", "wave_defense"},
}

# Task type -> ground-truth context key used in a record's works_in list
# (works_in comes from the M92 Cheat Sheet game-data export)
TASK_CONTEXT = {
    "pvp": "pvp",
    "pve_hostile": "pve",
    "pve_general": "pve",
    "pve_academy_drone": "pve",
    "wave_defense": "wave_defense",
    "duo_wave_defense": "wave_defense",
}

for _task in ("pvp_station", "station_raid"):
    TASK_SCOPES[_task] = {"any", "pvp", "station"}
    TASK_CONTEXT[_task] = "station"
for _task in ("galactic_anomaly", "dreadnought"):
    TASK_SCOPES[_task] = {"any", "pve"}
    TASK_CONTEXT[_task] = "pve"

# Relevance for a record whose targets don't match the current target:
# the ability still exists but is unlikely to trigger.
_TARGET_MISS_RELEVANCE = 0.0


class AbilityCatalogue(dict):
    def __init__(self, records):
        super().__init__(records)
        from engine.catalogue import identity

        self.aliases = {identity(n): n for n in records}
        self.aliases.update(
            {
                identity(a): b
                for a, b in {
                    "Paris": "Tom Paris",
                    "Christopher Pike": "Pike",
                    "Marlena Moreau": "Moreau",
                    "Kathryn Janeway": "Janeway",
                }.items()
                if b in records
            }
        )

    def get(self, key, default=None):
        from engine.catalogue import identity

        return super().get(self.aliases.get(identity(key), key), default)


@lru_cache(maxsize=1)
def load_abilities() -> dict:
    return AbilityCatalogue(
        json.loads(_ABILITIES_PATH.read_text(encoding="utf-8"))["officers"]
    )


def parse_pct(val_str: str) -> float:
    """
    Parse '40%' -> 0.40, '120%' -> 1.0 (capped).
    Values like '120000%' are absolute stats (e.g. Apex Barrier points) -
    treat as max strength (1.0) since they're clearly high-value.
    """
    if not val_str:
        return 0.0
    m = re.search(r"[\d]+\.?\d*", str(val_str).replace(",", ""))
    if not m:
        return 0.0
    raw = float(m.group())
    if raw > 500:
        return 1.0
    return min(raw / 100.0, 1.0)


def record_relevance(record: dict, task_type: str, target: dict) -> float:
    """0..1 relevance of a single ability record for the task/target.

    Prefers the ground-truth works_in list (exported game data) over the
    inferred scope; scope is the fallback for records without it."""
    if record.get("identity_review_required"):
        return 0.0
    level = target.get("level", target.get("real_hostile", {}).get("level", 0))
    if (
        record.get("max_hostile_level")
        and task_type not in {"pvp", "pvp_station", "station_raid"}
        and level > record["max_hostile_level"]
    ):
        return 0.0
    works_in = record.get("works_in")
    if works_in is not None:
        context = target.get("encounter_context") or TASK_CONTEXT.get(task_type, "pve")
        if context not in works_in:
            return 0.0
    else:
        scopes = TASK_SCOPES.get(task_type, {"any"})
        if record.get("scope", "any") not in scopes:
            return 0.0
    targets = record.get("targets", [])
    if not targets:
        return 1.0
    hay = (
        f"{target.get('name', '')} {target.get('type', '')} "
        f"{target.get('ship_class', '')}"
    ).lower()
    matched = any(t.replace("_", " ") in hay for t in targets)
    return 1.0 if matched else _TARGET_MISS_RELEVANCE


def _slot_records(officer_name: str) -> list[tuple[str, dict]]:
    entry = load_abilities().get(officer_name)
    if not entry:
        return []
    return [(slot, rec) for slot, rec in entry.items() if rec]


def ability_strength(officer: dict, slot: str, record: dict) -> float:
    values = record.get("values", [])
    if not values:
        return 0.0
    index = (
        0
        if slot == "cm"
        else max(
            0,
            min(
                int(officer.get("rank") or officer.get("tier") or 1) - 1,
                len(values) - 1,
            ),
        )
    )
    return min(1.0, abs(float(values[index])))


def officer_combat_scores(
    officer: dict, task_type: str, target: dict, slots: tuple = ("cm", "oa")
) -> dict | None:
    """
    Offense/defense relevance (0..1 each) of an officer's full kit for the
    task, weighted by ability strength. Returns None when the officer is
    not in the knowledge base (caller should fall back to text matching).
    """
    records = _slot_records(officer["name"])
    if not records:
        return None

    offense = defense = 0.0
    for slot, rec in records:
        if slot not in slots:
            continue
        rel = record_relevance(rec, task_type, target)
        if rel == 0.0:
            continue
        strength = ability_strength(officer, slot, rec)
        score = rel * (0.6 + 0.4 * strength)

        role = rec.get("role")
        if role == "off":
            offense = max(offense, score)
        elif role == "def":
            defense = max(defense, score)
        elif role == "amp":
            # Amplifiers help the whole crew, both directions
            offense = max(offense, score * 0.7)
            defense = max(defense, score * 0.5)
        # "util" contributes nothing to combat

    return {"offense": offense, "defense": defense}


def officer_has_effect(
    officer_name: str,
    effects: set[str],
    task_type: str,
    target: dict,
    slots: tuple = ("cm", "oa"),
) -> bool:
    """True if the officer brings one of the given effects, relevant to task."""
    for _slot, rec in _slot_records(officer_name):
        if _slot not in slots:
            continue
        if (
            rec.get("effect") in effects
            and record_relevance(rec, task_type, target) >= 1.0
        ):
            return True
    return False


def bda_combat_score(officer: dict, task_type: str, target: dict) -> float | None:
    """
    0..1 combat value of an officer's below-deck ability for the task.
    None when the officer has no structured entry; 0.0 when they have no
    BDA or it's pure utility for this task.
    """
    entry = load_abilities().get(officer["name"])
    if entry is None:
        return None
    rec = entry.get("bda")
    if not rec:
        return 0.0
    rel = record_relevance(rec, task_type, target)
    if rel == 0.0 or rec.get("role") == "util":
        return 0.0
    strength = ability_strength(officer, "bda", rec)
    return rel * (0.6 + 0.4 * strength)


def officer_available(officer: dict) -> bool:
    """Imported rosters can contain locked zero-rank/zero-level officers."""
    return (
        officer.get("available", True)
        and officer.get("level", 1) > 0
        and officer.get("rank", officer.get("tier", 1)) > 0
    )
