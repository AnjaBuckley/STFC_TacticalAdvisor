"""Captain-specific synergy. Export arrays are base/small/large, never ranks."""

from engine.abilities import load_abilities

CLASSES = {"Command", "Science", "Engineering"}


def calc_synergy(captain, officer_1, officer_2):
    rec = load_abilities().get(captain.get("name"), {}).get("cm")
    values = (rec or {}).get("synergy_values", (rec or {}).get("values", []))
    group = captain.get("group")
    companions = [officer_1, officer_2]
    matches = [bool(group) and o.get("group") == group for o in companions]
    classes = [o.get("class") for o in [captain, *companions]]
    known = all(c in CLASSES for c in classes)
    full = all(matches) and known and len(set(classes)) == 3
    partial = any(matches) and not full
    value = None
    if values:
        value = values[0]
        if any(matches) and not known:
            value = None
        else:
            for i, matched in enumerate(matches):
                if matched:
                    large = (
                        classes[i + 1] != classes[0]
                        and classes[i + 1] != classes[2 - i]
                    )
                    value += values[2 if large else 1] if len(values) >= 3 else 0
    label = "FULL SYNERGY" if full else "PARTIAL SYNERGY" if partial else "NO SYNERGY"
    if rec is None:
        label = "NO VERIFIED CAPTAIN MANEUVER"
    return {
        "synergy_label": label,
        "maneuver_value": value,
        "maneuver_multiplier": value / values[0]
        if value is not None and values and values[0]
        else 1.0,
        "full_synergy": full,
        "partial_synergy": partial,
        "class_data_complete": known,
        "notes": "Captain-specific base and synergy increments; unknown class data leaves the value unconfirmed.",
    }
