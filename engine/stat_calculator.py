"""
Stat Calculator — STFC
Formula: Stat_final = Stat_base × (1 + Σ research_buffs + Σ building_buffs + Σ officer_stats)

CRITICAL: All buffs are ADDITIVE on the base value, NOT multiplicative on each other.
This means late-game buff dilution must be modeled explicitly.

Dilution example:
  Existing research: 900% → multiplier = 10.0
  Adding 100% buff  → multiplier = 11.0
  Actual gain = (11.0 - 10.0) / 10.0 = only 10% real increase
  The optimizer must use marginal_gain, not raw buff values.
"""

def calc_final_stat(
    base_stat: float,
    research_buffs: list[float],
    building_buffs: list[float],
    officer_stats: list[float]
) -> float:
    total_buff = sum(research_buffs) + sum(building_buffs) + sum(officer_stats)
    return base_stat * (1 + total_buff)


def calc_marginal_gain(
    current_total_buff: float,
    new_buff: float
) -> float:
    """
    Returns the actual percentage gain of adding a new buff
    given the existing total buff level. Used to detect dilution.
    """
    current_multiplier = 1 + current_total_buff
    new_multiplier = 1 + current_total_buff + new_buff
    return (new_multiplier - current_multiplier) / current_multiplier


def detect_dilution_warning(
    current_total_buff: float,
    new_buff: float,
    threshold: float = 0.05
) -> dict:
    """
    Returns a warning if adding the new buff yields less than
    threshold (default 5%) real gain.
    """
    gain = calc_marginal_gain(current_total_buff, new_buff)
    return {
        "dilution_detected": gain < threshold,
        "real_gain_percent": round(gain * 100, 2),
        "recommendation": (
            "Deprioritize stat-based officers. Use ability-based officers instead."
            if gain < threshold else "Buff still provides meaningful gain."
        )
    }
