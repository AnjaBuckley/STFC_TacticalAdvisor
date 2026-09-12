"""
Isolytic Damage Calculator — STFC

Isolytic damage is a parallel damage track, independent of standard damage.
It bypasses standard mitigation entirely and is only reduced by ISO defense.
Especially effective against targets with high standard mitigation (e.g. Gorn).

Formula: ISO_damage = (total_standard_damage × iso_bonus) / (1 + enemy_iso_defense)

Sources of ISO bonus:
- Seven of Nine (Below Deck Ability)
- Eviscerator ship passive
- Star Path research tree nodes
- Janeway captain maneuver (context-dependent)

Note: Isolytic damage scales with TOTAL standard damage, not base damage.
Always calculate standard damage first, then apply ISO bonus.
"""

def calc_isolytic_damage(
    total_standard_damage: float,
    iso_bonus: float,
    enemy_iso_defense: float
) -> dict:
    if iso_bonus <= 0:
        return {"iso_damage": 0, "iso_effective": False}

    iso_damage = (total_standard_damage * iso_bonus) / (1 + enemy_iso_defense)

    return {
        "iso_damage": round(iso_damage, 2),
        "iso_effective": True,
        "iso_reduction_from_defense": round(
            (1 - 1 / (1 + enemy_iso_defense)) * 100, 2
        )
    }
