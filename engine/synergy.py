"""
Synergy Evaluator — STFC

Full synergy is achieved when:
  - Both companion officers are from the SAME GROUP as the captain
  - AND they are DIFFERENT CLASSES (Command / Science / Engineering)

Synergy boosts the Captain's Maneuver effectiveness.
Full synergy = 2x maneuver effectiveness (shown as yellow lightning bolts)

The optimizer must evaluate: Is full synergy worth more than a stronger
individual ability from an off-group officer?
This depends on how powerful the captain's maneuver is when boosted.
"""

CLASSES = {"Command", "Science", "Engineering"}


def calc_synergy(captain: dict, officer_1: dict, officer_2: dict) -> dict:
    group = captain.get("group")
    same_group_1 = bool(group) and group == officer_1.get("group")
    same_group_2 = bool(group) and group == officer_2.get("group")
    classes = [o.get("class") for o in (captain, officer_1, officer_2)]
    known = all(cls in CLASSES for cls in classes)
    full_synergy = same_group_1 and same_group_2 and known and len(set(classes)) == 3
    partial_synergy = (same_group_1 or same_group_2) and not full_synergy

    if full_synergy:
        multiplier = 2.0
        label = "FULL SYNERGY"
    elif partial_synergy:
        multiplier = 1.5
        label = "PARTIAL SYNERGY"
    else:
        multiplier = 1.0
        label = "NO SYNERGY"

    return {
        "synergy_label": label,
        "maneuver_multiplier": multiplier,
        "full_synergy": full_synergy,
        "partial_synergy": partial_synergy,
        "class_data_complete": known,
        "notes": (
            "Full synergy doubles maneuver effectiveness. "
            "Verify this outweighs off-group officer abilities before switching."
            if full_synergy
            else "Consider whether full synergy crew combination is achievable."
        ),
    }
