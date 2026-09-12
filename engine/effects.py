"""Seat-aware effects with explicit omissions and timed effect plans."""

from collections import defaultdict

from engine.abilities import load_abilities, record_relevance
from engine.synergy import calc_synergy

SUPPORTED = {
    "isolytic_damage",
    "isolytic_cascade",
    "crit_chance",
    "crit_damage",
    "apex_barrier",
    "isolytic_defense",
    "weapon_damage",
    "crit_mitigation",
    "apex_shred",
    "loot",
    "hull_health",
    "shield_health",
    "armor",
    "shield_deflection",
    "dodge",
    "accuracy",
    "armor_piercing",
    "shield_piercing",
    "shield_mitigation",
    "enemy_shield_mitigation_down",
}
TIMED = {
    ("Hugh", "bda"),
    ("Seska", "bda"),
    ("Suder", "bda"),
    ("Seska", "oa"),
    ("Suder", "oa"),
    ("PIC Hugh", "bda"),
}


def ability_plan(bridge, below_deck, task_type, target):
    static = defaultdict(float)
    timed, omissions = [], []
    for index, officer in enumerate(bridge + below_deck):
        entry = load_abilities().get(officer["name"])
        if entry is None:
            omissions.append(f"{officer['name']}: ability data unavailable")
            continue
        slots = ("cm", "oa") if index == 0 and bridge else ("oa",)
        if index >= len(bridge):
            slots = ("bda",)
        for slot in slots:
            rec = entry.get(slot)
            if not rec:
                continue
            if rec.get("identity_review_required"):
                omissions.append(
                    f"{officer['name']}: confirm post-Update-94 identity/rank before using abilities"
                )
                continue
            level = target.get("level", target.get("real_hostile", {}).get("level", 0))
            if rec.get("cap_review_level", 1000) <= level and task_type not in {
                "pvp",
                "pvp_station",
                "station_raid",
            }:
                omissions.append(
                    f"{officer['name']}: legacy ability cap at level {level} requires calibration; omitted rather than reduced by an invented percentage"
                )
                continue
            if record_relevance(rec, task_type, target) < 1:
                continue
            effect = rec.get("effect")
            rank = max(
                0,
                min(
                    int(officer.get("rank") or officer.get("tier") or 1) - 1,
                    len(rec.get("values", [])) - 1,
                ),
            )
            value = rec.get("values", [0])[rank] if rec.get("values") else 0
            if (officer["name"], slot) in TIMED:
                timed.append(
                    {
                        **rec,
                        "value": value,
                        "chance": rec.get("proc_chances", [1] * 5)[rank],
                        "name": officer["name"],
                    }
                )
                continue
            if slot == "cm":
                if len(bridge) == 3 and officer["name"] in {
                    "SNW James Kirk",
                    "SNW Pike",
                }:
                    value = calc_synergy(*bridge)["maneuver_value"]
                    if value is not None:
                        static[
                            "enemy_shield_mitigation_down"
                            if officer["name"] == "SNW James Kirk"
                            else "shield_mitigation"
                        ] += value
                        continue
                omissions.append(
                    f"{officer['name']}: captain maneuver not numerically supported"
                )
                continue
            if (
                rec.get("conditional")
                or effect not in SUPPORTED
                or not rec.get("values")
            ):
                if rec.get("role") != "util":
                    omissions.append(
                        f"{officer['name']}: {effect} ({slot.upper()}) requires an unsupported condition/effect"
                    )
                continue
            static[effect] += max(0, value)
    return dict(static), timed, sorted(set(omissions))


def crew_effects(bridge, below_deck, task_type, target):
    static, timed, omissions = ability_plan(bridge, below_deck, task_type, target)
    # Callers that only ask for static effects cannot silently flatten timed procs.
    return static, sorted(
        set(
            omissions
            + [f"{r['name']}: timed {r['effect']} (simulated per event)" for r in timed]
        )
    )
