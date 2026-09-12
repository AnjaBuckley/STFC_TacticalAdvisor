"""
Crew Combination Scorer — STFC

Scoring formula:
  score = (defense_ability_score × 0.25)
        + (offense_ability_score × 0.25)
        + (synergy_bonus         × 0.20)
        + (task_bonus            × 0.30)

At Ops 70+, ship base stats are always maxed — scoring them against a static
threshold produces identical scores for every crew (the old bug). Instead, we
score officers on the RELEVANCE of their abilities to the specific task and
target, weighted by their ability strength (cm_bda/oa values).

Task bonuses (from CLAUDE.md section 5.1):
  - Hyperthermic Decay target  → +0.3 to fast-kill crews
  - Gorn target                → +0.4 to isolytic-capable officers
  - Borg target                → +0.4 to Borg-group officers
  - PvP Battleship enemy       → +0.3 to Explorer Strike Team
  - Academy Drone / Duo Wave   → +0.4 to crit mitigation sources
  - Ops >= 40                  → +0.2 ONLY to crews with task-relevant abilities,
                                  -0.2 to crews with only generic stat abilities
"""

from engine.abilities import (
    load_abilities,
    officer_combat_scores,
    officer_has_effect,
)
from engine.abilities import (
    parse_pct as _parse_pct,
)

# ── Per-officer ability relevance ─────────────────────────────────────────────

# Keywords that indicate OFFENSIVE value, grouped by target context
_OFFENSE_KEYWORDS: dict[str, list[str]] = {
    "gorn": ["isolytic", "apex shred", "hull breach", "critical hit", "crit damage"],
    "borg": ["critical hit", "crit damage", "hull breach", "attack", "borg"],
    "swarm": ["swarm", "hyperthermic", "burning", "critical hit", "attack"],
    "xindi": ["xindi", "critical hit", "hull breach", "attack"],
    "species 8472": ["critical hit", "hull breach", "attack"],
    "dreadnought": ["critical hit", "hull breach", "isolytic", "apex shred"],
    "pve_hostile": [
        "critical hit",
        "crit damage",
        "hull breach",
        "attack bonus",
        "increase attack",
        "weapon damage",
        "damage bonus",
    ],
    "pvp": [
        "hull breach",
        "apex shred",
        "isolytic",
        "critical hit",
        "player",
        "pvp",
        "attack piercing",
        "armor piercing",
    ],
    "wave_defense": ["critical hit", "crit damage", "attack", "hull breach"],
}

# Keywords that indicate DEFENSIVE / SURVIVABILITY value
_DEFENSE_KEYWORDS: dict[str, list[str]] = {
    "gorn": [
        "apex barrier",
        "shield mitigation",
        "mitigation",
        "dodge",
        "armor",
        "hull repair",
        "repair",
    ],
    "borg": ["borg", "shield", "mitigation", "armor", "hull repair"],
    "swarm": ["mitigation", "armor", "shield", "hull repair"],
    "pve_hostile": [
        "mitigation",
        "armor",
        "shield deflection",
        "dodge",
        "hull repair",
        "repair",
        "defense",
    ],
    "pvp": [
        "apex barrier",
        "mitigation",
        "shield",
        "armor",
        "dodge",
        "hull repair",
        "defense",
    ],
    "wave_defense": [
        "crit mitigation",
        "critical mitigation",
        "apex barrier",
        "mitigation",
        "armor",
        "shield",
        "defense",
    ],
    "duo_wave_defense": [
        "crit mitigation",
        "critical mitigation",
        "apex barrier",
        "mitigation",
        "defense",
    ],
    "academy_drone": [
        "crit mitigation",
        "critical mitigation",
        "mitigation",
        "armor",
        "shield",
    ],
}


def _officer_offense_score(
    officer: dict,
    task_type: str,
    target_name: str,
    target: dict | None = None,
    slots: tuple = ("cm", "oa"),
) -> float:
    """Score officer's offensive ability relevance for the given task.

    Prefers the structured knowledge base (data/abilities.json); falls back
    to keyword matching on the raw description for unknown officers."""
    structured = officer_combat_scores(
        officer, task_type, target or {"name": target_name}, slots=slots
    )
    if structured is not None:
        return structured["offense"]

    desc = (officer.get("description", "") or "").lower()

    # Build keyword set from target name + task type
    keywords: list[str] = []
    for key, kws in _OFFENSE_KEYWORDS.items():
        if key in target_name or key in task_type:
            keywords.extend(kws)
    if not keywords:
        keywords = _OFFENSE_KEYWORDS.get("pve_hostile", [])

    # Each keyword match adds relevance; cap at 1.0
    hits = sum(1 for kw in keywords if kw in desc)
    max_possible = max(len(set(keywords)) * 0.4, 1)
    relevance = min(hits / max_possible, 1.0)

    # Weight by how strong the ability value actually is
    cm_str = _parse_pct(officer.get("cm_bda_value", ""))
    oa_str = _parse_pct(officer.get("oa_value", ""))
    strength = max(cm_str, oa_str)

    return relevance * 0.65 + strength * 0.35


def _officer_defense_score(
    officer: dict,
    task_type: str,
    target_name: str,
    target: dict | None = None,
    slots: tuple = ("cm", "oa"),
) -> float:
    """Score officer's defensive ability relevance for the given task.

    Prefers the structured knowledge base (data/abilities.json); falls back
    to keyword matching on the raw description for unknown officers."""
    structured = officer_combat_scores(
        officer, task_type, target or {"name": target_name}, slots=slots
    )
    if structured is not None:
        return structured["defense"]

    desc = (officer.get("description", "") or "").lower()

    keywords: list[str] = []
    for key, kws in _DEFENSE_KEYWORDS.items():
        if key in target_name or key in task_type:
            keywords.extend(kws)
    if not keywords:
        keywords = _DEFENSE_KEYWORDS.get("pve_hostile", [])

    hits = sum(1 for kw in keywords if kw in desc)
    max_possible = max(len(set(keywords)) * 0.4, 1)
    relevance = min(hits / max_possible, 1.0)

    cm_str = _parse_pct(officer.get("cm_bda_value", ""))
    oa_str = _parse_pct(officer.get("oa_value", ""))
    strength = max(cm_str, oa_str)

    return relevance * 0.65 + strength * 0.35


def _has_task_relevant_ability(
    officer: dict,
    task_type: str,
    target_name: str,
    target: dict | None = None,
    slots: tuple = ("cm", "oa"),
) -> bool:
    """Return True only if this officer's ability is meaningfully relevant to the task."""
    structured = officer_combat_scores(
        officer, task_type, target or {"name": target_name}, slots=slots
    )
    if structured is not None:
        return max(structured["offense"], structured["defense"]) >= 0.5

    desc = (officer.get("description", "") or "").lower()
    for key, kws in {**_OFFENSE_KEYWORDS, **_DEFENSE_KEYWORDS}.items():
        if (key in target_name or key in task_type) and any(kw in desc for kw in kws):
            return True
    return False


# ── Level 71+ PvE officer caps ─────────────────────────────────────────────────
# Against PvE targets of level 71+, the game hard-caps these legacy
# mitigation/bypass officers (their reductions are disabled or negligible).
# They remain fully functional vs level <=70 PvE and in all PvP.
_L71_CAPPED_OFFICERS = {
    "Pike",
    "Moreau",
    "Jean-Luc Picard",
    "Harrison",
    "Harry Mudd",
    "Mudd",
    "Eurydice",
    "Bones",
    "Gaila",
}
# Frank Leslie's hull-regen maneuver only works vs hostiles level 51 and below
_LESLIE_MAX_LEVEL = 51
_CAP_FACTOR = 0.1


def _target_level(target: dict) -> int:
    real = target.get("real_hostile")
    if real and real.get("level"):
        return real["level"]
    return target.get("level") or target.get("level_range", [0, 0])[1]


# ── Main scorer ────────────────────────────────────────────────────────────────


def score_combination(
    ship: dict,
    bridge_crew: list[dict],
    synergy: dict,
    task_profile: dict,
    player_profile: dict,
    ops_level: int,
    dilution: dict,
) -> tuple[float, list[str]]:
    """
    Score a bridge crew combination for the given ship and task.

    Returns:
        (score: float, reasoning: list[str])
    """
    reasoning: list[str] = []
    task_type = task_profile.get("task_type", "pve_general")
    target = task_profile.get("target", {})
    target_name = target.get("name", "").lower()

    # ── Defense Ability Score (0.25 weight) ───────────────────────────────────
    defense_scores = [
        _officer_defense_score(
            o, task_type, target_name, target, ("cm", "oa") if i == 0 else ("oa",)
        )
        for i, o in enumerate(bridge_crew)
    ]

    # ── Offense Ability Score (0.25 weight) ───────────────────────────────────
    offense_scores = [
        _officer_offense_score(
            o, task_type, target_name, target, ("cm", "oa") if i == 0 else ("oa",)
        )
        for i, o in enumerate(bridge_crew)
    ]

    # Core strike-team bridge kits are restricted to the player's ship class.
    for i, officer in enumerate(bridge_crew):
        group = officer.get("group", "")
        if "Strike" in group:
            required = next(
                (c for c in ("Explorer", "Interceptor", "Battleship") if c in group),
                None,
            )
            if required and ship.get("ship_class") != required:
                offense_scores[i] = defense_scores[i] = 0.0
                reasoning.append(
                    f"{officer['name']}: strike-team kit requires a {required}; not credited on this ship."
                )

    # ── Level 71+ PvE caps on legacy officers ─────────────────────────────────
    tgt_level = _target_level(target)
    if task_type not in {"pvp", "pvp_station", "station_raid"}:
        for i, o in enumerate(bridge_crew):
            capped = (tgt_level >= 71 and o["name"] in _L71_CAPPED_OFFICERS) or (
                tgt_level > _LESLIE_MAX_LEVEL and o["name"] == "Leslie"
            )
            if capped:
                defense_scores[i] *= _CAP_FACTOR
                offense_scores[i] *= _CAP_FACTOR
                reasoning.append(
                    f"WARNING: {o['name']} is hard-capped vs level {tgt_level} PvE "
                    "targets (legacy officer cap, works vs L<=70 and in PvP)."
                )

    defense_ability_score = sum(defense_scores) / len(defense_scores)
    offense_ability_score = sum(offense_scores) / len(offense_scores)

    # Add reasoning about top ability contributors
    for officer, d_sc, o_sc in zip(bridge_crew, defense_scores, offense_scores):
        best = max(d_sc, o_sc)
        if best >= 0.5:
            role = "offense" if o_sc >= d_sc else "defense"
            reasoning.append(
                f"{officer['name']}: strong {role} ability relevance ({best:.2f})."
            )

    # ── Synergy Bonus (0.20 weight) ────────────────────────────────────────────
    synergy_multiplier = synergy.get("maneuver_multiplier", 1.0)
    # Map 1.0 → 0.30, 1.5 → 0.65, 2.0 → 1.0
    synergy_bonus = (synergy_multiplier - 1.0) / 1.0 * 0.7 + 0.3
    synergy_bonus = min(synergy_bonus, 1.0)
    captain_entry = load_abilities().get(bridge_crew[0]["name"])
    if captain_entry is not None and not captain_entry.get("cm"):
        synergy_bonus = 0.0
        synergy = {}

    if synergy.get("full_synergy"):
        reasoning.append(
            f"Full synergy active ({synergy['synergy_label']}). "
            "Maneuver effectiveness doubled."
        )
    elif synergy.get("partial_synergy"):
        reasoning.append(f"Partial synergy ({synergy['synergy_label']}).")

    # ── Task Bonus (0.30 weight) ───────────────────────────────────────────────
    task_bonus = 0.0
    crew_groups = {o.get("group", "").lower() for o in bridge_crew}

    # Gorn: reward isolytic-capable officers (structured effect lookup,
    # falls back to description text for officers not in the knowledge base)
    if "gorn" in target_name:

        def _brings_isolytic(o: dict) -> bool:
            if o["name"] in load_abilities():
                return officer_has_effect(
                    o["name"],
                    {"isolytic_damage"},
                    task_type,
                    target,
                    slots=("cm", "oa") if o is bridge_crew[0] else ("oa",),
                )
            return "isolytic" in (o.get("description", "") or "").lower()

        iso_in_crew = any(_brings_isolytic(o) for o in bridge_crew)
        if iso_in_crew:
            task_bonus += 0.4
            reasoning.append("Gorn target: +0.4 — isolytic ability detected in crew.")
        else:
            reasoning.append(
                "Gorn target: no isolytic ability in bridge crew — suboptimal."
            )

    # Borg: reward Borg-group officers
    if "borg" in target_name or "probe" in target_name or "sphere" in target_name:
        borg_in_crew = "unimatrix twelve" in crew_groups or any(
            "borg" in (o.get("description", "") or "").lower() for o in bridge_crew
        )
        if borg_in_crew:
            task_bonus += 0.4
            reasoning.append("Borg target: +0.4 — Borg-relevant officer in crew.")

    # Swarm / Hyperthermic Decay
    if "swarm" in target_name or target.get("hyperthermic_decay"):
        fast_kill = any(
            "hyperthermic" in (o.get("description", "") or "").lower()
            or o.get("attack_bonus", 0) > 0.2
            for o in bridge_crew
        )
        if fast_kill:
            task_bonus += 0.3
            reasoning.append("Hyperthermic target: +0.3 — fast-kill officer in crew.")

    # Respect the actual combat triangle and the player's ship requirement.
    if task_type == "pvp":
        from optimizer.pvp_logic import COUNTER_MAP, STRIKE_TEAMS

        counter_class = COUNTER_MAP.get(target.get("ship_class"))
        if ship.get("ship_class") == counter_class:
            task_bonus += 0.1
            reasoning.append(
                f"Combat triangle: {counter_class} is favored against {target.get('ship_class')}."
            )
        team = STRIKE_TEAMS.get(ship.get("ship_class"), {})
        overlap = set(team.get("officers", [])) & {o["name"] for o in bridge_crew}
        if len(overlap) >= 2:
            task_bonus += 0.2
            reasoning.append(
                f"Matching {team['name']}: {len(overlap)}/3 baseline officers available on this bridge."
            )

    # Academy Drone / Duo Wave: crit mitigation sources
    if task_type in ["pve_academy_drone", "duo_wave_defense"]:
        from engine.critical_mitigation import aggregate_crit_mitigation_sources

        has_crit_source = (
            aggregate_crit_mitigation_sources(
                player_profile, task_type, active_ship=ship
            )["total_crit_mitigation"]
            > 0
        )
        if has_crit_source:
            task_bonus += 0.4
            reasoning.append(f"{task_type}: +0.4 — crit mitigation source present.")
        else:
            reasoning.append(
                f"WARNING: {task_type} — no crit mitigation source found. "
                "Research Starfleet Academy Remote Campus urgently."
            )

    # Ops >= 40: reward task-relevant abilities, penalise generic-stat-only crews
    if ops_level >= 40:
        relevant_count = sum(
            1
            for i, o in enumerate(bridge_crew)
            if _has_task_relevant_ability(
                o, task_type, target_name, target, ("cm", "oa") if i == 0 else ("oa",)
            )
        )
        if relevant_count >= 2:
            task_bonus += 0.2
            reasoning.append(
                f"Ops {ops_level} (>=40): +0.2 — {relevant_count}/3 officers have "
                "task-relevant abilities (buff dilution makes generic stats poor value)."
            )
        elif dilution.get("dilution_detected") and relevant_count == 0:
            task_bonus -= 0.2
            reasoning.append(
                f"Ops {ops_level} (>=40): -0.2 — no task-relevant abilities found, "
                f"only generic stats. Real gain from stat buffs: "
                f"{dilution['real_gain_percent']}%."
            )

    # Dilution warning (informational only, no score impact here)
    if dilution.get("dilution_detected"):
        reasoning.append(
            f"Buff dilution: adding stat officers yields only "
            f"{dilution['real_gain_percent']}% real gain. "
            "Ability-based officers strongly preferred."
        )

    # ── Final Score ────────────────────────────────────────────────────────────
    score = (
        defense_ability_score * 0.25
        + offense_ability_score * 0.25
        + synergy_bonus * 0.20
        + task_bonus * 0.30
    )

    return round(score, 4), reasoning
