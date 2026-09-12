"""
Unit tests for ingest/officer_tool_sheet.py
"""
import io

import openpyxl
from openpyxl.workbook.defined_name import DefinedName

from ingest.officer_tool_sheet import parse_bonuses, parse_roster, apply_to_profile, _sheet_id


def _make_workbook():
    wb = openpyxl.Workbook()
    bonuses = wb.active
    bonuses.title = "Bonuses"
    bonuses["E5"] = 71       # OpsLevel
    bonuses["E21"] = 58      # OrionLevel
    bonuses["E22"] = 21.4    # OrionAttack
    bonuses["E23"] = 21.4    # OrionDefence
    bonuses["E24"] = 21.4    # OrionHealth
    bonuses["E26"] = 3       # EmeraldChainLevel
    bonuses["E27"] = 1.5     # EmeraldAttack
    bonuses["E28"] = 1.2     # EmeraldDefence
    bonuses["E29"] = 0.5     # EmeraldHealth

    roster = wb.create_sheet("Roster")
    # columns: B=rarity C=name D=level E=rank F=attack G=defense H=health
    #          I=group J=cm/bda K=oa ... O=description
    rows = [
        ("U", "0718", 30, 5, 14302.21, 19069.61, 23807.22, "Auxiliary Controls", "4%", "15%", "", "", "", "", "CM: something OA: increase defence"),
        ("R", "Ahvix", 10, 5, 5644.09, 8466.14, 19729.63, "Mudd's Crew", "20%", "50%", "", "", "", "", "CM: increase hit chance vs Eclipse hostile"),
    ]
    for i, row in enumerate(rows):
        r = 20 + i
        for j, val in enumerate(row):
            roster.cell(row=r, column=2 + j, value=val)

    defs = {
        "OpsLevel": "Bonuses!$E$5", "OrionLevel": "Bonuses!$E$21",
        "OrionAttack": "Bonuses!$E$22", "OrionDefence": "Bonuses!$E$23", "OrionHealth": "Bonuses!$E$24",
        "EmeraldChainLevel": "Bonuses!$E$26", "EmeraldAttack": "Bonuses!$E$27",
        "EmeraldDefence": "Bonuses!$E$28", "EmeraldHealth": "Bonuses!$E$29",
        "RosterOfficer": "Roster!$C$20:$C$21", "RosterLevel": "Roster!$D$20:$D$21",
        "RosterRank": "Roster!$E$20:$E$21", "RosterAttack": "Roster!$F$20:$F$21",
        "RosterDefence": "Roster!$G$20:$G$21", "RosterHealth": "Roster!$H$20:$H$21",
    }
    for name, ref in defs.items():
        wb.defined_names[name] = DefinedName(name, attr_text=ref)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return openpyxl.load_workbook(buf, data_only=True)


class TestParseBonuses:
    def test_reads_named_ranges(self):
        wb = _make_workbook()
        b = parse_bonuses(wb)
        assert b["ops_level"] == 71
        assert b["syndicate_level"] == 58
        assert b["syndicate_officer_bonus"]["attack"] == 21.4
        assert b["emerald_chain"]["level"] == 3


class TestParseRoster:
    def test_extracts_officer_rows(self):
        wb = _make_workbook()
        roster = parse_roster(wb)
        assert len(roster) == 2
        first = roster[0]
        assert first["name"] == "0718"
        assert first["rarity"] == "U"
        assert first["level"] == 30
        assert first["rank"] == 5
        assert first["attack"] == 14302.21
        assert first["group"] == "Auxiliary Controls"

    def test_pvp_pve_relevance_from_description(self):
        wb = _make_workbook()
        roster = parse_roster(wb)
        eclipse = next(o for o in roster if o["name"] == "Ahvix")
        assert eclipse["pvp_relevant"] is False
        assert eclipse["pve_relevant"] is True


class TestApplyToProfile:
    def test_upserts_new_officer_and_updates_existing(self):
        profile = {
            "ops_level": 70, "syndicate_level": 57,
            "officers": [
                {"name": "0718", "level": 25, "rank": 4, "class": "Science", "attack_bonus": 0.1},
            ],
        }
        bonuses = {
            "ops_level": 71, "syndicate_level": 58,
            "syndicate_officer_bonus": {"attack": 0, "defense": 0, "health": 0},
            "emerald_chain": {"level": 0, "attack": 0, "defense": 0, "health": 0},
        }
        roster = [
            {"name": "0718", "rarity": "U", "level": 30, "rank": 5, "attack": 14302.21,
             "defense": 19069.61, "health": 23807.22, "group": "Auxiliary Controls",
             "cm_bda_value": "4%", "oa_value": "15%", "description": "x",
             "pvp_relevant": False, "pve_relevant": True},
            {"name": "New Officer", "rarity": "R", "level": 1, "rank": 1, "attack": 100,
             "defense": 100, "health": 100, "group": "", "cm_bda_value": "", "oa_value": "",
             "description": "", "pvp_relevant": False, "pve_relevant": True},
        ]

        profile, diff = apply_to_profile(profile, bonuses, roster)

        existing = next(o for o in profile["officers"] if o["name"] == "0718")
        assert existing["level"] == 30
        # manual enrichment must survive the merge
        assert existing["class"] == "Science"
        assert existing["attack_bonus"] == 0.1

        new = next(o for o in profile["officers"] if o["name"] == "New Officer")
        assert new["class"] == ""

        assert any("officers added" in d for d in diff)
        assert any("leveled/ranked up" in d for d in diff)

    def test_stat_only_change_shows_in_diff(self):
        """A global-bonus shift changes stats at unchanged level/rank — the
        diff must not be empty, or the UI would refuse to apply the update."""
        profile = {
            "ops_level": 71, "syndicate_level": 58,
            "officers": [
                {"name": "0718", "rarity": "U", "level": 30, "rank": 5,
                 "attack": 14302.21, "defense": 19069.61, "health": 23807.22,
                 "group": "Auxiliary Controls", "cm_bda_value": "4%", "oa_value": "15%",
                 "description": "x",
                 "stats": {"attack": 14302.21, "defense": 19069.61, "health": 23807.22}},
            ],
        }
        bonuses = {
            "ops_level": 71, "syndicate_level": 58,
            "syndicate_officer_bonus": {"attack": 0, "defense": 0, "health": 0},
            "emerald_chain": {"level": 0, "attack": 0, "defense": 0, "health": 0},
        }
        roster = [
            {"name": "0718", "rarity": "U", "level": 30, "rank": 5,
             "attack": 14350.00, "defense": 19069.61, "health": 23807.22,
             "group": "Auxiliary Controls", "cm_bda_value": "4%", "oa_value": "15%",
             "description": "x", "pvp_relevant": False, "pve_relevant": True},
        ]

        profile, diff = apply_to_profile(profile, bonuses, roster)
        assert any("updated stats" in d for d in diff)
        assert profile["officers"][0]["attack"] == 14350.00

    def test_identical_data_produces_empty_diff(self):
        profile = {
            "ops_level": 71, "syndicate_level": 58,
            "officers": [
                {"name": "0718", "rarity": "U", "level": 30, "rank": 5,
                 "attack": 14302.21, "defense": 19069.61, "health": 23807.22,
                 "group": "Auxiliary Controls", "cm_bda_value": "4%", "oa_value": "15%",
                 "description": "x",
                 "stats": {"attack": 14302.21, "defense": 19069.61, "health": 23807.22}},
            ],
        }
        bonuses = {
            "ops_level": 71, "syndicate_level": 58,
            "syndicate_officer_bonus": {"attack": 0, "defense": 0, "health": 0},
            "emerald_chain": {"level": 0, "attack": 0, "defense": 0, "health": 0},
        }
        roster = [
            {"name": "0718", "rarity": "U", "level": 30, "rank": 5,
             "attack": 14302.21, "defense": 19069.61, "health": 23807.22,
             "group": "Auxiliary Controls", "cm_bda_value": "4%", "oa_value": "15%",
             "description": "x", "pvp_relevant": False, "pve_relevant": True},
        ]

        _, diff = apply_to_profile(profile, bonuses, roster)
        assert diff == []


class TestSheetId:
    def test_extracts_id_from_url(self):
        url = "https://docs.google.com/spreadsheets/d/1234567890abcdefghijklmnopqrstuv_TEST_SHEET/edit?gid=1"
        assert _sheet_id(url) == "1234567890abcdefghijklmnopqrstuv_TEST_SHEET"

    def test_passes_through_bare_id(self):
        assert _sheet_id("bareid123") == "bareid123"
