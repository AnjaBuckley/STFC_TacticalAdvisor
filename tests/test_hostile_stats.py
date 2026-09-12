"""
Unit tests for engine/hostile_stats.py
"""
from engine.hostile_stats import enrich_target, load_hostile_stats


class TestEnrichTarget:
    def test_known_target_gets_real_stats(self):
        target = {"name": "Gorn Hunter", "level_range": [45, 62], "hp": 1}
        e = enrich_target(target)
        assert e["real_hostile"]["name"] == "Gorn Hunter"
        assert e["hp"] > 100000            # real hull+shield, not the placeholder
        assert e["base_damage"] > 0        # dpr
        assert 0 < e["crit_chance"] <= 1
        assert "defense_stats" in e

    def test_level_selection_picks_closest(self):
        target = {"name": "Gorn Hunter", "level_range": [45, 62]}
        low = enrich_target(target, level=60)
        high = enrich_target(target, level=71)
        assert low["real_hostile"]["level"] <= high["real_hostile"]["level"]

    def test_unknown_target_unchanged(self):
        target = {"name": "Solo Wave Defense", "hp": 12345}
        assert enrich_target(target) == target

    def test_original_not_mutated(self):
        target = {"name": "Gorn Hunter", "level_range": [45, 62], "hp": 1}
        enrich_target(target)
        assert target["hp"] == 1
