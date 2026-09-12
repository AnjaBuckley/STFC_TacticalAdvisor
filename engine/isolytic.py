"""Parallel Isolytic damage from pre-mitigation standard damage.

Ordinary damage follows the published formula. Combined Cascade is a
community-derived model, not an independently verified official formula.
"""

import math


def calc_isolytic_damage(
    total_standard_damage, iso_bonus, enemy_iso_defense, cascade_bonus=0
):
    if any(
        not math.isfinite(v) or v < 0
        for v in (total_standard_damage, iso_bonus, enemy_iso_defense, cascade_bonus)
    ):
        raise ValueError("Damage, bonuses and defense must be finite and nonnegative.")
    value = (
        total_standard_damage
        * (iso_bonus * (1 + cascade_bonus) + cascade_bonus)
        / (1 + enemy_iso_defense)
    )
    return {
        "iso_damage": round(value, 2),
        "iso_effective": value > 0,
        "iso_reduction_from_defense": round((1 - 1 / (1 + enemy_iso_defense)) * 100, 2),
        "formula_status": "provisional combined Cascade"
        if cascade_bonus
        else "ordinary Isolytic",
    }
