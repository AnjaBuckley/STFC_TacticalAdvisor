"""
Unit tests for ingest/research_csv.py
"""
from ingest.research_csv import (
    parse_research_csv, _classify, apply_to_profile, is_research_csv,
)

_CSV = '''"Name","Level","Tree","Col","Row","Power","Done","Min Ops","id",""
"Apex Plating","1","MIRROR","1","2","5250","Yes","25","111","Increases Apex Barrier of all ships."
"Apex Plating","2","MIRROR","1","2","750","No","26","111","Increases Apex Barrier of all ships."
"Weapon Calibration","1","COMBAT","2","3","900","Yes","30","222","Increases weapon damage of all ships."
'''


class TestParse:
    def test_parses_rows_and_done_flags(self):
        rows = parse_research_csv(_CSV.encode())
        assert len(rows) == 3
        assert rows[0]["done"] is True and rows[1]["done"] is False
        assert rows[0]["description"].startswith("Increases Apex")

    def test_sniffer(self):
        assert is_research_csv(_CSV.encode())
        assert not is_research_csv(b"foo,bar\n1,2\n")


class TestClassify:
    def test_buckets(self):
        assert _classify("Apex Plating", "Increases Apex Barrier") == "apex_barrier"
        assert _classify("X", "Increases Isolytic Damage dealt") == "isolytic_damage"
        assert _classify("X", "Increases the Attack of all Officers") == "officer_attack"
        assert _classify("X", "Increases weapon damage of all ships") == "weapon_damage"
        assert _classify("X", "Increases parsteel production") == "other"


class TestApply:
    def test_apex_applied_and_officer_floor_respected(self):
        profile = {"research": {"combat": {"all_research": 9.0},
                                "mirror_tree": {"apex_barrier": 0}}}
        buckets = {"apex_barrier": 15000, "officer_all": 0.2}
        profile, diff = apply_to_profile(profile, buckets)
        assert profile["research"]["mirror_tree"]["apex_barrier"] == 15000
        # research-only officer value must not lower the multi-source total
        assert profile["research"]["combat"]["all_research"] == 9.0
