"""
Unit tests for engine/apex_barrier.py
"""
from engine.apex_barrier import calc_effective_hp


class TestCalcEffectiveHp:
    def test_zero_apex_no_boost(self):
        """Zero apex barrier should leave HP unchanged (multiplier = 1.0)."""
        result = calc_effective_hp(100000, 0)
        assert result["effective_hp"] == 100000.0
        assert result["multiplier"] == 1.0
        assert result["hp_gain_percent"] == 0.0

    def test_ten_thousand_apex_doubles_hp(self):
        """Apex barrier of 10,000 should double effective HP."""
        result = calc_effective_hp(100000, 10000)
        assert result["effective_hp"] == 200000.0
        assert result["multiplier"] == 2.0
        assert result["hp_gain_percent"] == 100.0

    def test_eighteen_thousand_apex(self):
        """Apex 18,000 → multiplier = 1 + 18000/10000 = 2.8"""
        result = calc_effective_hp(96000, 18000)
        assert abs(result["multiplier"] - 2.8) < 0.001
        assert abs(result["effective_hp"] - 96000 * 2.8) < 0.01

    def test_returns_all_expected_keys(self):
        result = calc_effective_hp(50000, 5000)
        assert "base_hp" in result
        assert "apex_barrier_value" in result
        assert "multiplier" in result
        assert "effective_hp" in result
        assert "hp_gain_percent" in result

    def test_base_hp_preserved_in_output(self):
        result = calc_effective_hp(75000, 3000)
        assert result["base_hp"] == 75000
        assert result["apex_barrier_value"] == 3000

    def test_effective_hp_greater_than_base(self):
        """Effective HP should always be >= base HP for non-negative apex values."""
        result = calc_effective_hp(50000, 500)
        assert result["effective_hp"] >= 50000

    def test_hp_gain_percent_formula(self):
        """hp_gain_percent = (multiplier - 1) * 100"""
        result = calc_effective_hp(100000, 5000)
        expected_multiplier = 1 + 5000 / 10000
        expected_gain = (expected_multiplier - 1) * 100
        assert abs(result["hp_gain_percent"] - expected_gain) < 0.01
