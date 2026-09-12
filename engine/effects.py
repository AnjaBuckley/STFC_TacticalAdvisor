"""Resolve explicitly modelled ability effects at their actual station and rank.

Conditional and unmodelled effects are disclosed, never silently simulated.
The imported CM values include synergy entries, not promotion-rank values;
we deliberately do not misinterpret that array as a rank progression.
"""

from collections import defaultdict

from engine.abilities import load_abilities, record_relevance

SUPPORTED = {
    "isolytic_damage",
    "crit_chance",
    "crit_damage",
    "apex_barrier",
    "isolytic_defense",
    "weapon_damage",
}


def crew_effects(bridge, below_deck, task_type, target):
    effects = defaultdict(float)
    omissions = []
    for index, officer in enumerate(bridge + below_deck):
        entry = load_abilities().get(officer["name"], {})
        slots = ("cm", "oa") if index == 0 and bridge else ("oa",)
        if index >= len(bridge):
            slots = ("bda",)
        for slot in slots:
            rec = entry.get(slot)
            if not rec or record_relevance(rec, task_type, target) < 1:
                continue
            effect = rec.get("effect")
            if rec.get("role") == "util":
                continue
            if (
                rec.get("conditional")
                or effect not in SUPPORTED
                or slot == "cm"
                or not rec.get("values")
            ):
                omissions.append(
                    f"{officer['name']}: {effect.replace('_', ' ')} ({slot.upper()})"
                )
                continue
            values = rec["values"]
            rank = max(
                1,
                min(int(officer.get("rank") or officer.get("tier") or 1), len(values)),
            )
            effects[effect] += max(0.0, float(values[rank - 1]))
    return dict(effects), sorted(set(omissions))
