"""Seat-aware effects with explicit omissions and timed effect plans."""

from collections import defaultdict

from engine.abilities import load_abilities, record_relevance
from engine.synergy import calc_synergy

SUPPORTED = {
    "isolytic_damage",
    "isolytic_cascade",
    "crit_chance",
    "crit_damage",
    "enemy_crit_down",
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
    ("Trip Tucker", "oa"),
    ("Jonathan Archer", "oa"),
    ("Seska", "bda"),
    ("Suder", "bda"),
    ("Seska", "oa"),
    ("Suder", "oa"),
    ("PIC Hugh", "bda"),
}


def ability_plan(bridge, below_deck, task_type, target, ship=None):
    static = defaultdict(float)
    timed, omissions = [], []
    # Pike amplification is restricted to the reviewed legacy effects below.
    # Other triggered/status abilities remain omitted until their rules are known.
    amplifier = 1.0
    if len(bridge) == 3 and load_abilities().get(
        bridge[0]["name"]
    ) is load_abilities().get("Pike"):
        cm = load_abilities().get("Pike")["cm"]
        level = target.get("level", target.get("real_hostile", {}).get("level", 0))
        if record_relevance(cm, task_type, target) == 1 and level < cm.get(
            "cap_review_level", 71
        ):
            boost = calc_synergy(*bridge)["maneuver_value"]
            if boost is not None:
                amplifier += boost
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
            required_class = rec.get("ship_class")
            if required_class and (ship or {}).get("ship_class") != required_class:
                if ship is None:
                    omissions.append(
                        f"{officer['name']}: player ship class needed to evaluate ability"
                    )
                continue
            if (
                rec.get("target_names")
                and target.get("name") not in rec["target_names"]
            ):
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
            model = rec.get("model")
            if model == "officer_stat_bonus" and slot == "oa":
                static[effect] += value
                continue
            if (
                model
                in {
                    "officer_health_defense",
                    "defense_fraction",
                    "morale_round_start",
                    "defending_delay",
                    "probe_extra_shots",
                }
                and slot == "cm"
            ):
                magnitude = (
                    calc_synergy(*bridge)["maneuver_value"]
                    if len(bridge) == 3
                    else calc_synergy(officer, {}, {})["maneuver_value"]
                )
                if magnitude is None:
                    omissions.append(
                        f"{officer['name']}: complete captain synergy data required"
                    )
                    continue
                if model == "officer_health_defense":
                    static["defense_from_officer_health"] += magnitude
                elif model == "defense_fraction":
                    for stat in ("armor", "shield_deflection", "dodge"):
                        static[stat] += magnitude
                elif (
                    model == "defending_delay"
                    and (ship or {}).get("is_defending") is not True
                ):
                    if (ship or {}).get("is_defending") is None:
                        omissions.append(
                            "Pon: defending status unknown; weapon delay omitted"
                        )
                else:
                    timed.append(
                        {
                            **rec,
                            "value": rec.get("shots", 1),
                            "chance": min(1, magnitude),
                            "name": officer["name"],
                        }
                    )
                    if model == "morale_round_start":
                        omissions.append(
                            "Weyoun: using export round-start/3-round morale; original Update 48 specifies combat-start/8 rounds; current battle-log confirmation needed"
                        )
                continue
            if model == "morale_round_effect" and slot == "oa":
                timed.append(
                    {**rec, "value": value, "chance": 1, "name": officer["name"]}
                )
                continue
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
            if slot == "oa" and rec.get("model") == "legacy_hostile_defense":
                if effect == "enemy_piercing_down":
                    static[effect] += value * amplifier
                else:
                    weapon_type = rec["weapon_type"]
                    if not target.get("weapons") or any(
                        w.get("type") not in {"energy", "kinetic"}
                        for w in target["weapons"]
                    ):
                        omissions.append(
                            f"{officer['name']}: unknown weapon types; reduction applies only to explicitly typed weapons"
                        )
                    static[f"enemy_{weapon_type}_damage_down"] += value * amplifier
                continue
            if slot == "cm":
                if rec.get("model") == "legacy_amplifier":
                    omissions.append(
                        f"{officer['name']}: amplification model covers Chen, T'Laan and Moreau only; other triggered abilities require calibration"
                    )
                    continue
                if (
                    not rec.get("conditional")
                    and effect in SUPPORTED
                    and len(bridge) == 3
                ):
                    maneuver = calc_synergy(*bridge)["maneuver_value"]
                    if maneuver is not None:
                        static[effect] += max(0, maneuver)
                        continue
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
