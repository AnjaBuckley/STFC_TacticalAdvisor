"""
Unit tests for engine/isolytic.py
"""
import pytest
from engine.isolytic import calc_isolytic_damage


class TestCalcIsolyticDamage:
    def test_zero_iso_bonus_returns_zero(self):
        result = calc_isolytic_damage(100000, 0.0, 0.45)
        assert result["iso_damage"] == 0
        assert result["iso_effective"] is False

    def test_negative_iso_bonus_returns_zero(self):
        result = calc_isolytic_damage(100000, -0.1, 0.45)
        assert result["iso_damage"] == 0
        assert result["iso_effective"] is False

    def test_positive_iso_bonus_is_effective(self):
        result = calc_isolytic_damage(100000, 0.25, 0.0)
        assert result["iso_effective"] is True
        assert result["iso_damage"] > 0

    def test_no_iso_defense_formula(self):
        """With 0 iso defense, iso_damage = total_standard_damage * iso_bonus."""
        std_damage = 50000.0
        iso_bonus = 0.25
        result = calc_isolytic_damage(std_damage, iso_bonus, 0.0)
        expected = std_damage * iso_bonus / (1 + 0.0)
        assert abs(result["iso_damage"] - expected) < 0.01

    def test_iso_defense_reduces_damage(self):
        """Higher iso defense should reduce iso damage."""
        result_low = calc_isolytic_damage(100000, 0.25, 0.10)
        result_high = calc_isolytic_damage(100000, 0.25, 0.80)
        assert result_low["iso_damage"] > result_high["iso_damage"]

    def test_iso_reduction_percent_correct(self):
        """iso_reduction_from_defense should reflect the defense fraction."""
        result = calc_isolytic_damage(100000, 0.25, 1.0)
        # With iso_defense=1.0: reduction = (1 - 1/2) * 100 = 50%
        assert abs(result["iso_reduction_from_defense"] - 50.0) < 0.01

    def test_zero_iso_defense_zero_reduction(self):
        result = calc_isolytic_damage(100000, 0.25, 0.0)
        assert result["iso_reduction_from_defense"] == 0.0

    def test_iso_scales_with_standard_damage(self):
        """Double standard damage should double iso damage."""
        r1 = calc_isolytic_damage(50000, 0.20, 0.30)
        r2 = calc_isolytic_damage(100000, 0.20, 0.30)
        assert abs(r2["iso_damage"] - r1["iso_damage"] * 2) < 0.1
