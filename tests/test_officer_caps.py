"""
Level 71+ PvE legacy officer cap (G7 progression rules).
"""

from optimizer.scorer import score_combination


def _officer(name, desc="Increase Mitigation"):
    return {
        "name": name,
        "group": "X",
        "class": "Command",
        "description": desc,
        "cm_bda_value": "50%",
        "oa_value": "50%",
    }


def _score(crew, level):
    synergy = {"maneuver_multiplier": 1.0}
    target = {
        "name": "Forsaken Hostile (G7)",
        "real_hostile": {"level": level, "name": "FORSAKEN CRUISER", "strength": 1},
    }
    score, reasoning = score_combination(
        ship={"base_stats": {}},
        bridge_crew=crew,
        synergy=synergy,
        task_profile={"task_type": "pve_hostile", "target": target},
        player_profile={"research": {}},
        ops_level=75,
        dilution={"dilution_detected": False, "real_gain_percent": 50},
    )
    return score, reasoning


class TestL71Caps:
    def test_pike_capped_at_71_but_not_70(self):
        crew = [_officer("Pike"), _officer("Moreau"), _officer("Chen")]
        s70, r70 = _score(crew, 70)
        s71, r71 = _score(crew, 71)
        assert (
            s71 < s70
        )  # Reviewed Moreau effect is omitted at 71; no whole-officer penalty.
        assert any("legacy ability cap" in line for line in r71)
        assert not any("legacy ability cap" in line for line in r70)

    def test_uncapped_crew_unaffected(self):
        crew = [_officer("Kang"), _officer("Krell"), _officer("Mara")]
        _s70, _ = _score(crew, 70)
        _s75, r75 = _score(crew, 75)
        assert not any("legacy ability cap" in line for line in r75)

    def test_leslie_capped_above_51(self):
        crew = [_officer("Leslie"), _officer("Kang"), _officer("Mara")]
        _, r52 = _score(crew, 52)
        _, r51 = _score(crew, 51)
        assert not any("90%" in line for line in r52)
        assert not any("legacy ability cap" in line for line in r51)
