"""Typed, attributed combat sources. Unknown import rules stay quarantined."""

from collections import defaultdict

from engine.abilities import TASK_CONTEXT


def source_effects(profile, ship, task_type, target, round_number=1):
    result = defaultdict(float)
    omissions = []
    context = target.get("encounter_context") or TASK_CONTEXT.get(task_type, "pve")
    for source in profile.get("combat_sources", []) + ship.get("combat_sources", []):
        if source.get("enabled", True) is False:
            continue
        if source.get("status") not in {"manual", "reviewed"}:
            omissions.append(
                f"Source {source.get('name', source.get('id', '?'))}: unreviewed"
            )
            continue
        scopes = source.get("contexts", [])
        if not scopes or context not in scopes:
            continue
        conditions = source.get("conditions", {})
        checks = {
            "ship_class": ship.get("ship_class"),
            "ship_name": ship.get("name"),
            "ship_faction": ship.get("faction"),
            "target_class": target.get("ship_class"),
            "target_family": target.get("catalogue_family", target.get("name")),
            "target_id": target.get("hostile_id"),
            "target_faction": target.get("faction_id"),
        }
        minimum_grade = conditions.get("ship_grade_min")
        if minimum_grade is not None and (
            not isinstance(ship.get("grade"), (int, float))
            or ship["grade"] < minimum_grade
        ):
            continue
        if any(
            key not in checks
            or checks[key] not in (values if isinstance(values, list) else [values])
            for key, values in conditions.items()
            if key != "ship_grade_min"
        ):
            continue
        if source.get("duration") and round_number > source["duration"]:
            continue
        result[source["effect"]] += source["value"]
    return dict(result), omissions


SOURCE_EFFECTS = {
    "weapon_damage",
    "hull_health",
    "shield_health",
    "armor",
    "shield_deflection",
    "dodge",
    "armor_piercing",
    "shield_piercing",
    "accuracy",
    "crit_chance",
    "crit_damage",
    "apex_barrier",
    "crit_mitigation",
    "apex_shred",
    "isolytic_damage",
    "isolytic_cascade",
    "isolytic_defense",
    "hyperthermic_stabilizer",
    "loot",
}


def validate_sources(sources):
    import math

    if not isinstance(sources, list) or len(sources) > 20000:
        raise ValueError("Combat sources must be a list of at most 20000 records.")
    ids = set()
    for source in sources:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("id"), str)
            or source["id"] in ids
        ):
            raise ValueError("Every combat source needs a unique string id.")
        ids.add(source["id"])
        value = source.get("value")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 1e15
        ):
            raise ValueError("Source values must be finite, nonnegative numbers.")
        if source.get("status") not in {"manual", "reviewed", "unreviewed"}:
            raise ValueError("Source status must be manual, reviewed or unreviewed.")
        if source.get("status") == "unreviewed":
            continue
        effect = source.get("effect")
        if effect not in SOURCE_EFFECTS:
            raise ValueError("Unsupported source effect: " + str(effect))
        expected = (
            "points" if effect in {"apex_barrier", "crit_mitigation"} else "fraction"
        )
        if source.get("unit") != expected:
            raise ValueError(f"{effect} requires unit {expected}.")
        scopes = source.get("contexts")
        if (
            not isinstance(scopes, list)
            or not scopes
            or any(
                x not in {"pve", "pvp", "station", "armada", "wave_defense"}
                for x in scopes
            )
        ):
            raise ValueError("Enabled sources need explicit combat contexts.")
        if not isinstance(source.get("conditions", {}), dict) or any(
            k
            not in {
                "ship_class",
                "ship_name",
                "ship_faction",
                "ship_grade_min",
                "target_class",
                "target_family",
                "target_id",
                "target_faction",
            }
            for k in source.get("conditions", {})
        ):
            raise ValueError("Unsupported source condition.")
        if "ship_grade_min" in source.get("conditions", {}):
            grade = source["conditions"]["ship_grade_min"]
            if (
                isinstance(grade, bool)
                or not isinstance(grade, int)
                or not 1 <= grade <= 10
            ):
                raise ValueError("Minimum ship grade must be an integer 1–10.")
        if "duration" in source:
            duration = source["duration"]
            if (
                isinstance(duration, bool)
                or not isinstance(duration, int)
                or not 1 <= duration <= 100
            ):
                raise ValueError("Source duration must be 1–100 rounds.")
            if effect in {
                "weapon_damage",
                "hull_health",
                "shield_health",
                "armor",
                "shield_deflection",
                "dodge",
                "armor_piercing",
                "shield_piercing",
                "accuracy",
            }:
                raise ValueError(
                    "Timed base-stat sources are not supported; retain them as unreviewed."
                )
