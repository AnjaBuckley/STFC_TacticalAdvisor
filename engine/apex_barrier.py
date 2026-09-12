"""
Apex Barrier Calculator — STFC

The Apex Barrier provides TRUE damage reduction AFTER all other calculations.
It is not part of the standard mitigation formula.

A value of 10,000 in Apex Barrier doubles the effective HP of the ship.
Formula: effective_hp = base_hp × (1 + apex_barrier_value / 10000)

Sources of Apex Barrier:
- Mirror Research Tree (primary source)
- E-Picard officer ability
- IST (Interceptor Strike Team) passive buffs
- Specific ship passives

Priority: In PvP and Gorn encounters, Apex Barrier often outperforms
all other survivability investments combined.
"""

def calc_effective_hp(
    base_hp: float,
    apex_barrier_value: float
) -> dict:
    multiplier = 1 + (apex_barrier_value / 10000)
    effective_hp = base_hp * multiplier

    return {
        "base_hp": base_hp,
        "apex_barrier_value": apex_barrier_value,
        "multiplier": round(multiplier, 3),
        "effective_hp": round(effective_hp, 2),
        "hp_gain_percent": round((multiplier - 1) * 100, 2)
    }
