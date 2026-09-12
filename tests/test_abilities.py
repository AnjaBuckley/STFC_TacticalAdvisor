"""
Unit tests for engine/abilities.py and data/abilities.json integrity.
"""
import json
from pathlib import Path

from engine.abilities import (
    load_abilities, record_relevance, officer_combat_scores,
    officer_has_effect, bda_combat_score,
)

_PROFILE = Path(__file__).parent.parent / "profiles" / "player_profile.json"

VALID_ROLES = {"off", "def", "amp", "util"}
VALID_SCOPES = {"any", "pvp", "pve", "armada", "station", "node", "mining", "wave_defense"}


class TestKnowledgeBaseIntegrity:
    def test_every_profile_officer_is_compiled(self):
        profile = json.loads(_PROFILE.read_text())
        compiled = set(load_abilities())
        missing = {o["name"] for o in profile["officers"]} - compiled
        assert not missing, f"officers missing from abilities.json: {missing}"

    def test_all_records_use_valid_vocabulary(self):
        for name, entry in load_abilities().items():
            assert ("cm" in entry) != ("bda" in entry), name
            assert "oa" in entry, name
            for rec in entry.values():
                assert rec["role"] in VALID_ROLES, name
                assert rec["scope"] in VALID_SCOPES, name


class TestRelevance:
    def test_pvp_ability_scores_zero_in_pve(self):
        rec = {"effect": "isolytic_damage", "role": "off", "scope": "pvp"}
        assert record_relevance(rec, "pve_hostile", {"name": "Gorn Hunter"}) == 0.0
        assert record_relevance(rec, "pvp", {"name": "Enemy"}) == 1.0

    def test_target_condition_downweights_mismatches(self):
        rec = {"effect": "crit_chance", "role": "off", "scope": "pve", "targets": ["eclipse"]}
        assert record_relevance(rec, "pve_hostile", {"name": "Eclipse Raider"}) == 1.0
        assert record_relevance(rec, "pve_hostile", {"name": "Gorn Hunter"}) < 0.5

    def test_mining_officer_has_no_combat_value(self):
        # Arrock: both abilities are mining_speed
        officer = {"name": "Arrock", "cm_bda_value": "50%", "oa_value": "50%"}
        scores = officer_combat_scores(officer, "pve_hostile", {"name": "Gorn Hunter"})
        assert scores == {"offense": 0.0, "defense": 0.0}

    def test_borg_queen_pvp_bda_not_credited_in_pve(self):
        # The regression that motivated this module: her BDA is PvP-only
        officer = {"name": "Borg Queen", "cm_bda_value": "50%", "oa_value": "50%"}
        assert bda_combat_score(officer, "pve_hostile", {"name": "Gorn Hunter"}) == 0.0
        assert bda_combat_score(officer, "pvp", {"name": "Enemy"}) > 0.0

    def test_laliari_bda_scores_in_wave_defense_only(self):
        officer = {"name": "Laliari", "cm_bda_value": "40%", "oa_value": "10%"}
        assert bda_combat_score(officer, "duo_wave_defense", {"name": "Duo Wave Defense"}) > 0.0
        assert bda_combat_score(officer, "pvp", {"name": "Enemy"}) == 0.0

    def test_effect_lookup(self):
        assert officer_has_effect(
            "Kathryn Janeway", {"isolytic_damage"}, "pve_hostile", {"name": "Gorn Hunter"}
        )
        assert not officer_has_effect(
            "Arrock", {"isolytic_damage"}, "pve_hostile", {"name": "Gorn Hunter"}
        )

    def test_unknown_officer_returns_none(self):
        assert officer_combat_scores({"name": "Nonexistent"}, "pvp", {}) is None
        assert bda_combat_score({"name": "Nonexistent"}, "pvp", {}) is None


class TestPerRankValues:
    def test_rank_scales_strength(self):
        from engine.abilities import ability_strength, load_abilities
        rec = load_abilities()["Kathryn Janeway"]["oa"]
        if "values" not in rec:
            return  # ground-truth values not injected in this environment
        low = ability_strength({"name": "Kathryn Janeway", "rank": 1}, "oa", rec)
        high = ability_strength({"name": "Kathryn Janeway", "rank": 5}, "oa", rec)
        assert high >= low

    def test_absolute_values_cap_at_one(self):
        from engine.abilities import ability_strength
        rec = {"values": [120000.0, 130000.0, 140000.0, 150000.0, 160000.0]}
        assert ability_strength({"rank": 3}, "bda", rec) == 1.0

    def test_fallback_to_display_value(self):
        from engine.abilities import ability_strength
        rec = {}  # no values from export
        officer = {"name": "X", "rank": 5, "oa_value": "40%"}
        assert ability_strength(officer, "oa", rec) == 0.40
