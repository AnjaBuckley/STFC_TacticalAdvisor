"""
Unit tests for engine/synergy.py
"""
import pytest
from engine.synergy import calc_synergy


def _make_officer(name, group, cls):
    return {"name": name, "group": group, "class": cls}


class TestCalcSynergy:
    def test_full_synergy_same_group_different_classes(self):
        captain = _make_officer("Pike", "SNW Crew", "Command")
        o1 = _make_officer("Spock", "SNW Crew", "Science")
        o2 = _make_officer("Uhura", "SNW Crew", "Engineering")
        result = calc_synergy(captain, o1, o2)
        assert result["full_synergy"] is True
        assert result["partial_synergy"] is False
        assert result["maneuver_multiplier"] == 5.0
        assert "FULL SYNERGY" in result["synergy_label"]

    def test_no_synergy_different_group(self):
        captain = _make_officer("Janeway", "Voyager Crew", "Command")
        o1 = _make_officer("Hugh", "Borg Crew", "Engineering")
        o2 = _make_officer("Spock", "SNW Crew", "Science")
        result = calc_synergy(captain, o1, o2)
        assert result["full_synergy"] is False
        assert result["partial_synergy"] is False
        assert result["maneuver_multiplier"] == 1.0
        assert result["synergy_label"] == "NO VERIFIED CAPTAIN MANEUVER"

    def test_partial_synergy_one_same_group(self):
        captain = _make_officer("Pike", "SNW Crew", "Command")
        o1 = _make_officer("Spock", "SNW Crew", "Science")
        o2 = _make_officer("Janeway", "Voyager Crew", "Command")
        result = calc_synergy(captain, o1, o2)
        assert result["full_synergy"] is False
        assert result["partial_synergy"] is True
        assert result["maneuver_multiplier"] == pytest.approx(3.0)
        assert "PARTIAL SYNERGY" in result["synergy_label"]

    def test_full_synergy_requires_different_classes_among_companions(self):
        """Same class companions cannot achieve full synergy."""
        captain = _make_officer("Pike", "SNW Crew", "Command")
        o1 = _make_officer("Spock", "SNW Crew", "Science")
        o2 = _make_officer("Chapel", "SNW Crew", "Science")  # Same class as o1
        result = calc_synergy(captain, o1, o2)
        assert result["full_synergy"] is False

    def test_returns_notes_string(self):
        captain = _make_officer("Pike", "SNW Crew", "Command")
        o1 = _make_officer("Spock", "SNW Crew", "Science")
        o2 = _make_officer("Uhura", "SNW Crew", "Engineering")
        result = calc_synergy(captain, o1, o2)
        assert isinstance(result["notes"], str)
        assert len(result["notes"]) > 0

    def test_unknown_captain_has_no_invented_full_multiplier(self):
        captain = _make_officer("A", "Group1", "Command")
        o1 = _make_officer("B", "Group1", "Science")
        o2 = _make_officer("C", "Group1", "Engineering")
        result = calc_synergy(captain, o1, o2)
        assert result["maneuver_multiplier"] == 1.0

    def test_unknown_captain_has_no_invented_partial_multiplier(self):
        captain = _make_officer("A", "Group1", "Command")
        o1 = _make_officer("B", "Group1", "Science")
        o2 = _make_officer("C", "Group2", "Engineering")
        result = calc_synergy(captain, o1, o2)
        assert result["maneuver_multiplier"] == 1.0

    def test_no_synergy_multiplier_is_1x(self):
        captain = _make_officer("A", "Group1", "Command")
        o1 = _make_officer("B", "Group2", "Science")
        o2 = _make_officer("C", "Group3", "Engineering")
        result = calc_synergy(captain, o1, o2)
        assert result["maneuver_multiplier"] == 1.0


class TestUnknownClassHandling:
    """Regression tests: extracted rosters have no class data — unknown
    classes must not produce a false full-synergy claim."""

    def test_unknown_classes_cannot_confirm_full_synergy(self):
        captain = _make_officer("Pike", "SNW Crew", "")
        o1 = _make_officer("Spock", "SNW Crew", "")
        o2 = _make_officer("Uhura", "SNW Crew", "")
        result = calc_synergy(captain, o1, o2)
        assert result["full_synergy"] is False
        assert result["maneuver_multiplier"] == 1.0

    def test_known_same_class_still_blocks_full_synergy(self):
        captain = _make_officer("Pike", "SNW Crew", "Command")
        o1 = _make_officer("Spock", "SNW Crew", "Science")
        o2 = _make_officer("Chapel", "SNW Crew", "Science")
        result = calc_synergy(captain, o1, o2)
        assert result["full_synergy"] is False

    def test_one_unknown_class_leaves_synergy_unconfirmed(self):
        captain = _make_officer("Pike", "SNW Crew", "Command")
        o1 = _make_officer("Spock", "SNW Crew", "Science")
        o2 = _make_officer("Uhura", "SNW Crew", "")
        result = calc_synergy(captain, o1, o2)
        assert result["full_synergy"] is False
