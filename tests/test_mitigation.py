"""
Unit tests for engine/mitigation.py
"""
import pytest
from engine.mitigation import logistic, calc_mitigation, MITIGATION_CAP, SATURATION_WARNING_THRESHOLD


class TestLogistic:
    def test_logistic_at_1_1_equals_half(self):
        """logistic(1.1) should equal 0.5 exactly (where 4^0 = 1)."""
        result = logistic(1.1)
        assert abs(result - 0.5) < 1e-9

    def test_logistic_at_one_below_half(self):
        """logistic(1.0) uses 4^0.1 > 1, so result < 0.5."""
        import math
        result = logistic(1.0)
        expected = 1 / (1 + math.pow(4, 0.1))
        assert abs(result - expected) < 1e-9

    def test_logistic_zero_approaches_zero(self):
        """logistic(0) should be small (less than 0.25)."""
        result = logistic(0)
        assert result < 0.25

    def test_logistic_large_approaches_one(self):
        """logistic(large value) should approach 1."""
        result = logistic(10)
        assert result > 0.99

    def test_logistic_monotone(self):
        """logistic should be strictly increasing."""
        values = [logistic(x) for x in [0.5, 1.0, 1.5, 2.0, 2.5]]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1]


class TestCalcMitigation:
    def _default_kwargs(self):
        return dict(
            armor=22000,
            shield_deflection=34000,
            dodge=18000,
            armor_piercing=5000,
            shield_piercing=5000,
            accuracy=5000,
            ship_class="Explorer",
        )

    def test_returns_dict_with_expected_keys(self):
        result = calc_mitigation(**self._default_kwargs())
        assert "total_mitigation" in result
        assert "breakdown" in result
        assert "approaching_cap" in result
        assert "cap_warning" in result

    def test_mitigation_capped(self):
        """Total mitigation must never exceed MITIGATION_CAP."""
        result = calc_mitigation(
            armor=999999, shield_deflection=999999, dodge=999999,
            armor_piercing=1, shield_piercing=1, accuracy=1,
            ship_class="Explorer"
        )
        assert result["total_mitigation"] <= MITIGATION_CAP

    def test_mitigation_non_negative(self):
        result = calc_mitigation(**self._default_kwargs())
        assert result["total_mitigation"] >= 0.0

    def test_saturation_warning_triggered(self):
        """High stats should trigger saturation warning."""
        result = calc_mitigation(
            armor=999999, shield_deflection=999999, dodge=999999,
            armor_piercing=1, shield_piercing=1, accuracy=1,
            ship_class="Battleship"
        )
        assert result["approaching_cap"] is True
        assert result["cap_warning"] is not None

    def test_no_saturation_warning_for_low_stats(self):
        """Very low defensive stats should not trigger saturation warning."""
        result = calc_mitigation(
            armor=100, shield_deflection=100, dodge=100,
            armor_piercing=100000, shield_piercing=100000, accuracy=100000,
            ship_class="Explorer"
        )
        assert result["approaching_cap"] is False
        assert result["cap_warning"] is None

    def test_battleship_armor_heavy(self):
        """Battleship coefficients weight armor more heavily."""
        result_bs = calc_mitigation(30000, 5000, 5000, 5000, 5000, 5000, "Battleship")
        result_ex = calc_mitigation(30000, 5000, 5000, 5000, 5000, 5000, "Explorer")
        # Battleship should get more mitigation from armor than Explorer
        assert result_bs["breakdown"]["armor_component"] > result_ex["breakdown"]["armor_component"]

    def test_unknown_ship_class_raises(self):
        with pytest.raises(KeyError):
            calc_mitigation(1000, 1000, 1000, 1000, 1000, 1000, "Destroyer")

    def test_zero_piercing_handled(self):
        """Zero piercing stats should not cause division by zero."""
        result = calc_mitigation(
            armor=10000, shield_deflection=10000, dodge=10000,
            armor_piercing=0, shield_piercing=0, accuracy=0,
            ship_class="Explorer"
        )
        # With ratio=999, logistic approaches 1.0; mitigation should hit cap
        assert result["total_mitigation"] == MITIGATION_CAP
