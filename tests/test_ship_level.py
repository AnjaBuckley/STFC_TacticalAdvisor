"""
Unit tests for ship-level-dependent crew logic:
tier_for_level and _below_deck_slot_count (crew_slots semantics).
"""
from optimizer.crew_optimizer import tier_for_level, _below_deck_slot_count

# Gorn Eviscerator crew_slots (data/stfc_space/ship/1273528452.json):
# BELOW-DECK slots by unlock level (bridge seats are NOT in this table —
# verified in game: U.S.S. Athena level 20 shows 3 below-deck slots).
_EVISCERATOR_SLOTS = {"1": 5, "2": 10, "3": 20, "4": 30, "5": 40, "6": 45, "7": 55}

# Realta-style starter ship: maxes out at 2 below-deck slots.
_REALTA_SLOTS = {"1": 1, "2": 10}

# U.S.S. Athena (data/stfc_space/ship/3091911492.json) — the in-game
# ground truth that pinned down the table semantics.
_ATHENA_SLOTS = {"1": 5, "2": 10, "3": 20, "4": 35, "5": 55, "6": 65, "7": 70}


class TestTierForLevel:
    def test_five_levels_per_tier(self):
        assert tier_for_level(1, 15) == 1
        assert tier_for_level(5, 15) == 1
        assert tier_for_level(6, 15) == 2
        assert tier_for_level(45, 15) == 9
        assert tier_for_level(75, 15) == 15

    def test_capped_at_max_tier(self):
        assert tier_for_level(75, 9) == 9

    def test_floor_at_tier_one(self):
        assert tier_for_level(0, 15) == 1


class TestBelowDeckSlotCount:
    def test_athena_level_20_matches_game(self):
        # In-game ground truth: Athena at level 20 shows 3 below-deck slots
        ship = {"below_deck_slots_by_level": _ATHENA_SLOTS, "level": 20}
        assert _below_deck_slot_count(ship) == 3

    def test_table_counts_below_deck_directly(self):
        # Level 45: slots 1-6 unlocked -> 6 below deck (no bridge subtraction)
        ship = {"below_deck_slots_by_level": _EVISCERATOR_SLOTS, "level": 45}
        assert _below_deck_slot_count(ship) == 6

    def test_max_level_unlocks_all(self):
        ship = {"below_deck_slots_by_level": _EVISCERATOR_SLOTS, "level": 75}
        assert _below_deck_slot_count(ship) == 7

    def test_level_below_first_unlock(self):
        ship = {"below_deck_slots_by_level": _EVISCERATOR_SLOTS, "level": 4}
        assert _below_deck_slot_count(ship) == 0

    def test_starter_ship_caps_at_two(self):
        ship = {"below_deck_slots_by_level": _REALTA_SLOTS, "level": 20}
        assert _below_deck_slot_count(ship) == 2

    def test_legacy_tier_table_fallback(self):
        ship = {"below_deck_slots_by_tier": {"9": 6}, "tier": 9,
                "syndicate_slot_bonus": 1}
        assert _below_deck_slot_count(ship) == 7

    def test_explicit_override_beats_level_table(self):
        # Player counted 5 slots in the drydock; the table would say 6
        ship = {"below_deck_slots": 5,
                "below_deck_slots_by_level": _EVISCERATOR_SLOTS, "level": 45}
        assert _below_deck_slot_count(ship) == 5

    def test_override_of_zero_is_respected(self):
        # 0 is a real answer (no below deck), not "fall back to derivation"
        ship = {"below_deck_slots": 0,
                "below_deck_slots_by_level": _EVISCERATOR_SLOTS, "level": 75}
        assert _below_deck_slot_count(ship) == 0

    def test_negative_override_floored_at_zero(self):
        ship = {"below_deck_slots": -2,
                "below_deck_slots_by_level": _EVISCERATOR_SLOTS, "level": 75}
        assert _below_deck_slot_count(ship) == 0
