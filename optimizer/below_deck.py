"""
Below-Deck Optimizer — STFC

Below-deck slots serve TWO distinct functions — both must be evaluated:
  1. Stat contribution (raises ship stats toward mitigation cap)
  2. Below-Deck Ability (BDA) activation (Hugh, Seven, Paris, The Doctor, etc.)

Key BDA officers:
  Hugh        → Critical Hit Chance boost (universal — almost always worth a slot)
  Seven of Nine → Isolytic Damage boost (Gorn, PvP, high-level PvE)
  Paris       → Damage Mitigation increase (long fights, PvP defense)
  The Doctor  → Loot + XP bonus (grinding efficiency)
  Ghalenar    → Borg loot optimization (Borg Probe/Sphere missions)

Decision logic:
  - Calculate current mitigation with bridge crew stats
  - If mitigation < 65% cap: fill remaining slots with high-stat officers
  - If mitigation >= 65% cap: BDA officers score higher than stat officers
  - Isolytic task: Seven of Nine gets +0.5 priority score
  - Duo Wave Defense: require crit mitigation source in profile before recommending
  - Grinding task: The Doctor gets +0.3 priority score

Saladin special rule:
  Stat cap for Saladin is ~4200 per stat (Shipyard 28).
  Values above this only justified if officer abilities scale with total ship stats
  (e.g. Beverly Crusher, Marcus). Flag this in reasoning output.
"""

import re

from engine.abilities import bda_combat_score, officer_available, officer_has_effect
from engine.abilities import parse_pct as _parse_pct
from optimizer.scorer import _DEFENSE_KEYWORDS, _OFFENSE_KEYWORDS

BDA_PRIORITY = {
    "Hugh": {"base_priority": 0.8, "task_bonus": {"any": 0.0, "pvp": 0.1}},
    "Seven of Nine": {
        "base_priority": 0.6,
        "task_bonus": {"gorn": 0.5, "pvp": 0.4, "isolytic": 0.5},
    },
    "Paris": {"base_priority": 0.5, "task_bonus": {"pvp": 0.3, "long_fight": 0.3}},
    "The Doctor": {"base_priority": 0.4, "task_bonus": {"grinding": 0.3}},
    "Ghalenar": {"base_priority": 0.2, "task_bonus": {"borg": 0.6}},
}


def _bda_text(officer: dict) -> str:
    """Extract the Below-Deck Ability portion of an officer's description.

    Roster descriptions look like 'BDA: <text> OA: <text>' or 'CM: <text> ...'.
    Returns '' when the officer has no BDA."""
    desc = officer.get("description", "") or ""
    m = re.search(r"BDA:\s*(.*?)(?:\s+(?:OA|CM):|$)", desc, re.DOTALL)
    return m.group(1).strip().lower() if m else ""


def _officer_stats_total(officer: dict) -> float:
    total = (
        officer.get("attack", 0) + officer.get("defense", 0) + officer.get("health", 0)
    )
    if not total:
        stats = officer.get("stats", {})
        total = (
            stats.get("attack", 0) + stats.get("defense", 0) + stats.get("health", 0)
        )
    return total


def _task_keywords(task_type: str, target_name: str) -> list[str]:
    keywords: list[str] = []
    for table in (_OFFENSE_KEYWORDS, _DEFENSE_KEYWORDS):
        for key, kws in table.items():
            if key in target_name or key in task_type:
                keywords.extend(kws)
    if not keywords:
        keywords = _OFFENSE_KEYWORDS["pve_hostile"] + _DEFENSE_KEYWORDS["pve_hostile"]
    return keywords


def optimize_below_deck(
    ship: dict,
    available_officers: list[dict],
    bridge_crew: list[dict],
    num_slots: int,
    task_profile: dict,
    player_profile: dict,
) -> list[dict]:
    if num_slots <= 0:
        return []

    bridge_names = {o["name"] for o in bridge_crew}
    candidates = [
        o
        for o in available_officers
        if o["name"] not in bridge_names and officer_available(o)
    ]
    task_type = task_profile.get("task_type", "pve_general")
    target_name = task_profile.get("target", {}).get("name", "").lower()

    # Normalize stat contribution against the strongest candidate so stats
    # and BDA relevance compete on the same 0–1 scale.
    max_stats = max((_officer_stats_total(o) for o in candidates), default=0) or 1
    keywords = _task_keywords(task_type, target_name)

    target = task_profile.get("target", {})

    scored = []
    for officer in candidates:
        score = _score_below_deck_officer(
            officer, task_type, target_name, keywords, max_stats, target
        )
        if target.get("standard_damage_immune") and officer_has_effect(
            officer["name"], {"isolytic_damage"}, task_type, target, slots=("bda",)
        ):
            score += 2.0
        scored.append({"officer": officer, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)

    return [
        {"name": s["officer"]["name"], "function": _get_bda_description(s["officer"])}
        for s in scored[:num_slots]
    ]


def _score_below_deck_officer(
    officer: dict,
    task_type: str,
    target_name: str,
    keywords: list[str],
    max_stats: float,
    target: dict | None = None,
) -> float:
    stat_score = _officer_stats_total(officer) / max_stats

    # Task-relevant BDA: structured knowledge base first, description
    # keyword fallback for officers not in it
    bda_score = bda_combat_score(officer, task_type, target or {"name": target_name})
    if bda_score is None:
        bda = _bda_text(officer)
        bda_score = 0.0
        if bda:
            hits = sum(1 for kw in keywords if kw in bda)
            strength = _parse_pct(officer.get("cm_bda_value", ""))
            bda_score = min(hits * 0.4, 1.0) * 0.6 + strength * 0.4

    score = bda_score * 0.7 + stat_score * 0.3

    # Known high-value BDA officers keep their curated boost on top
    name = officer["name"]
    if name in BDA_PRIORITY and bda_score > 0:
        score += BDA_PRIORITY[name]["base_priority"]
        for key, val in BDA_PRIORITY[name]["task_bonus"].items():
            if key == "any" or key in task_type or key in target_name:
                score += val

    return score


def _get_bda_description(officer: dict) -> str:
    descriptions = {
        "Hugh": "BDA: Critical Hit Chance",
        "Seven of Nine": "BDA: Isolytic Damage Boost",
        "Paris": "BDA: Damage Mitigation",
        "The Doctor": "BDA: Loot + XP Bonus",
        "Ghalenar": "BDA: Borg Loot Optimization",
    }
    if officer["name"] in descriptions:
        return descriptions[officer["name"]]
    bda = _bda_text(officer)
    if bda:
        return f"BDA: {bda[:60].capitalize()}"
    return "Stat Contribution"
