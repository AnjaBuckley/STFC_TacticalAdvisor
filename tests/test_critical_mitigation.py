"""
Unit tests for engine/critical_mitigation.py
"""
import pytest
from engine.critical_mitigation import calc_critical_mitigation, aggregate_crit_mitigation_sources


class TestCalcCriticalMitigation:
    def test_zero_mitigation_no_change(self):
        result = calc_critical_mitigation(10000, 0.0)
        assert result["final_crit_damage"] == 10000.0
        assert result["damage_prevented"] == 0.0

    def test_full_mitigation_zeroes_damage(self):
        result = calc_critical_mitigation(10000, 1.0)
        assert result["final_crit_damage"] == 0.0
        assert result["damage_prevented"] == 10000.0

    def test_50_percent_mitigation(self):
        result = calc_critical_mitigation(8000, 0.50)
        assert abs(result["final_crit_damage"] - 4000.0) < 0.01
        assert abs(result["damage_prevented"] - 4000.0) < 0.01

    def test_mitigation_capped_at_100_percent(self):
        """Values above 1.0 should be clamped to 1.0."""
        result = calc_critical_mitigation(5000, 1.5)
        assert result["final_crit_damage"] == 0.0
        assert result["crit_mitigation_value"] == 100.0

    def test_returns_expected_keys(self):
        result = calc_critical_mitigation(10000, 0.30)
        assert "incoming_crit_damage" in result
        assert "crit_mitigation_value" in result
        assert "final_crit_damage" in result
        assert "damage_prevented" in result

    def test_crit_mitigation_value_in_percent(self):
        """crit_mitigation_value should be stored as percent (e.g. 35.0 not 0.35)."""
        result = calc_critical_mitigation(10000, 0.35)
        assert abs(result["crit_mitigation_value"] - 35.0) < 0.01


class TestAggregateCritMitigationSources:
    def _base_profile(self):
        return {
            "research": {
                "critical_mitigation": {
                    "remote_campus_bonus": 0.30,
                    "programmable_matter_beam": True,
                    "programmable_matter_beam_value": 0.20,
                }
            }
        }

    def test_remote_campus_not_applied_in_pvp(self):
        profile = self._base_profile()
        result = aggregate_crit_mitigation_sources(profile, "pvp")
        sources = [s["source"] for s in result["sources"]]
        assert "Remote Campus" not in sources

    def test_remote_campus_applied_in_duo_wave(self):
        profile = self._base_profile()
        result = aggregate_crit_mitigation_sources(profile, "duo_wave_defense")
        sources = [s["source"] for s in result["sources"]]
        assert "Remote Campus" in sources

    def test_remote_campus_applied_in_academy_drone(self):
        profile = self._base_profile()
        result = aggregate_crit_mitigation_sources(profile, "pve_academy_drone")
        sources = [s["source"] for s in result["sources"]]
        assert "Remote Campus" in sources

    def test_programmable_matter_beam_pvp_scope(self):
        profile = self._base_profile()
        for task_type in ["pvp", "pve_general", "duo_wave_defense", "pve_academy_drone"]:
            result = aggregate_crit_mitigation_sources(profile, task_type)
            sources = [s["source"] for s in result["sources"]]
            assert ("Programmable Matter Beam" in sources) == (task_type == "pvp")

    def test_total_additive(self):
        profile = self._base_profile()
        result = aggregate_crit_mitigation_sources(profile, "duo_wave_defense")
        # Beam is PvP-only; only Remote Campus applies here.
        assert abs(result["total_crit_mitigation"] - 0.30) < 0.001

    def test_warning_for_duo_wave_no_sources(self):
        profile = {"research": {}}
        result = aggregate_crit_mitigation_sources(profile, "duo_wave_defense")
        assert len(result["warnings"]) > 0
        assert "coverage warning" in result["warnings"][0]

    def test_no_warning_when_sources_present(self):
        profile = self._base_profile()
        result = aggregate_crit_mitigation_sources(profile, "duo_wave_defense")
        assert len(result["warnings"]) == 0

    def test_simulacrum_refit_applied(self):
        profile = {
            "research": {},
            "active_ship": {
                "name": "U.S.S. Vengeance",
                "simulacrum_refit": True,
                "crit_mitigation_bonus": 0.15,
            }
        }
        result = aggregate_crit_mitigation_sources(profile, "pvp")
        sources = [s["source"] for s in result["sources"]]
        assert "Simulacrum Refit" in sources

    def test_simulacrum_refit_not_applied_in_pve_general(self):
        profile = {
            "research": {},
            "active_ship": {
                "name": "U.S.S. Vengeance",
                "simulacrum_refit": True,
                "crit_mitigation_bonus": 0.15,
            }
        }
        result = aggregate_crit_mitigation_sources(profile, "pve_general")
        sources = [s["source"] for s in result["sources"]]
        assert "Simulacrum Refit" not in sources


class TestSimulacrumRefitShipMatching:
    """Regression tests: refit must match ship names without punctuation
    and follow the ship passed as active_ship, not only a profile key."""

    def _refit_ship(self, name):
        return {
            "name": name,
            "simulacrum_refit": True,
            "crit_mitigation_bonus": 0.15,
        }

    def test_refit_matches_name_without_dots(self):
        profile = {"research": {}, "active_ship": self._refit_ship("USS Vengeance")}
        result = aggregate_crit_mitigation_sources(profile, "pvp")
        assert "Simulacrum Refit" in [s["source"] for s in result["sources"]]

    def test_active_ship_param_overrides_profile(self):
        profile = {"research": {}}
        result = aggregate_crit_mitigation_sources(
            profile, "pvp", active_ship=self._refit_ship("U.S.S. Vengeance")
        )
        assert "Simulacrum Refit" in [s["source"] for s in result["sources"]]

    def test_ineligible_ship_gets_no_refit(self):
        profile = {"research": {}}
        result = aggregate_crit_mitigation_sources(
            profile, "pvp", active_ship=self._refit_ship("Eviscerator")
        )
        assert "Simulacrum Refit" not in [s["source"] for s in result["sources"]]
