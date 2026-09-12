"""
Standard Mitigation Calculator — STFC

Uses logistic function: f(x) = 1 / (1 + 4^(1.1 - x))
where x = defender_stat / attacker_piercing_stat

Theoretical saturation cap: ~71.2%
Practical optimization target: 65% (flag above this as diminishing returns)

Coefficients by ship class (defender):
  Battleship:   cA=0.55, cS=0.25, cD=0.20
  Explorer:     cA=0.20, cS=0.55, cD=0.25
  Interceptor:  cA=0.25, cS=0.20, cD=0.55
"""

import math

SHIP_CLASS_COEFFICIENTS = {
    "Battleship":   {"armor": 0.55, "shield": 0.25, "dodge": 0.20},
    "Explorer":     {"armor": 0.20, "shield": 0.55, "dodge": 0.25},
    "Interceptor":  {"armor": 0.25, "shield": 0.20, "dodge": 0.55},
}

MITIGATION_CAP = 0.712
SATURATION_WARNING_THRESHOLD = 0.65


def logistic(x: float) -> float:
    return 1 / (1 + math.pow(4, 1.1 - x))


def calc_mitigation(
    armor: float,
    shield_deflection: float,
    dodge: float,
    armor_piercing: float,
    shield_piercing: float,
    accuracy: float,
    ship_class: str
) -> dict:
    coeffs = SHIP_CLASS_COEFFICIENTS[ship_class]

    ratio_armor  = armor / armor_piercing if armor_piercing > 0 else 999
    ratio_shield = shield_deflection / shield_piercing if shield_piercing > 0 else 999
    ratio_dodge  = dodge / accuracy if accuracy > 0 else 999

    m_armor  = coeffs["armor"]  * logistic(ratio_armor)
    m_shield = coeffs["shield"] * logistic(ratio_shield)
    m_dodge  = coeffs["dodge"]  * logistic(ratio_dodge)

    total_mitigation = 1 - (1 - m_armor) * (1 - m_shield) * (1 - m_dodge)
    total_mitigation = min(total_mitigation, MITIGATION_CAP)

    return {
        "total_mitigation": round(total_mitigation, 4),
        "breakdown": {
            "armor_component": round(m_armor, 4),
            "shield_component": round(m_shield, 4),
            "dodge_component": round(m_dodge, 4),
        },
        "approaching_cap": total_mitigation >= SATURATION_WARNING_THRESHOLD,
        "cap_warning": (
            "Mitigation near saturation. Switch to offensive officers."
            if total_mitigation >= SATURATION_WARNING_THRESHOLD else None
        )
    }
