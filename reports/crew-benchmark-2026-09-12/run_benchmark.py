"""Reproducible, controlled crew benchmark against published STFC examples.

This does not read or modify the user's profile. Every scenario gives officers
identical rank, level, and stats so that the optimizer is tested mainly on its
ability model and encounter scoping. Ship strength is scaled to the selected
real hostile record to keep the simulated fight informative.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from optimizer.crew_optimizer import find_optimal_crew
from service import catalog, mission_target


OUT = Path(__file__).with_name("results.json")
ALL_HOSTILES = catalog()["hostiles"]

OFFICER_META = {
    "Pike": ("Command", "Shakedown Cruise"),
    "Moreau": ("Science", "Shakedown Cruise"),
    "T'Laan": ("Science", "Starfleet Academy"),
    "Chen": ("Engineering", "Starfleet Academy"),
    "Jaylah": ("Command", "Jaylah"),
    "SNW Pike": ("Command", "Strange New Worlds"),
    "SNW Spock": ("Science", "Strange New Worlds"),
    "SNW Uhura": ("Engineering", "Strange New Worlds"),
    "SNW Hemmer": ("Engineering", "Strange New Worlds"),
    "Five Of Eleven": ("Engineering", "Borg"),
    "Seven Of Eleven": ("Science", "Borg"),
    "Eight Of Eleven": ("Engineering", "Borg"),
    "Nine Of Eleven": ("Command", "Borg"),
    "Kathryn Janeway": ("Command", "Voyager"),
    "Ent-E Picard": ("Command", "Enterprise-E"),
    "Ent-E Data": ("Science", "Enterprise-E"),
    "SNW Nurse Chapel": ("Science", "Strange New Worlds"),
    "Jonathan Archer": ("Command", "Enterprise NX-01"),
    "Trip Tucker": ("Engineering", "Enterprise NX-01"),
    "Ghalenar": ("Science", "Enterprise NX-01"),
    "The Doctor": ("Science", "Voyager"),
    "Beverly Crusher": ("Science", "Next Generation"),
    "Weyoun": ("Command", "Explorer Strike Team"),
    "Pon": ("Engineering", "Explorer Strike Team"),
    "Ikat'ika": ("Science", "Explorer Strike Team"),
    "Jack Ransom": ("Science", "Explorer Strike Team"),
    "Khan": ("Command", "Khan's Crew"),
}


SCENARIOS = [
    {
        "id": "swarm_35",
        "label": "Level 35 Swarm Cluster",
        "task": "pve_hostile",
        "target": "Swarm Cluster",
        "level": 35,
        "ship": ("USS Franklin", "Explorer"),
        "published": ["Pike", "Moreau", "T'Laan"],
        "roster": ["Pike", "Moreau", "T'Laan", "Chen", "Jaylah", "SNW Pike", "SNW Spock", "The Doctor"],
    },
    {
        "id": "borg_40",
        "label": "Level 40 Borg Assailant",
        "task": "pve_hostile",
        "target": "Borg Assailant",
        "level": 40,
        "ship": ("Vi'Dar Talios", "Interceptor"),
        "published": ["Five Of Eleven", "Eight Of Eleven", "Nine Of Eleven"],
        "roster": ["Five Of Eleven", "Seven Of Eleven", "Eight Of Eleven", "Nine Of Eleven", "Pike", "Moreau", "T'Laan", "SNW Pike", "SNW Uhura", "Hugh"],
    },
    {
        "id": "gorn_60",
        "label": "Level 60 Gorn Hunter",
        "task": "pve_hostile",
        "target": "Gorn Hunter",
        "level": 60,
        "ship": ("Gorn Eviscerator", "Explorer"),
        "published": ["Kathryn Janeway", "Ent-E Picard", "Ent-E Data"],
        "roster": ["Kathryn Janeway", "Ent-E Picard", "Ent-E Data", "SNW Nurse Chapel", "Pike", "Moreau", "T'Laan", "The Doctor"],
        "ship_iso": 0.50,
    },
    {
        "id": "actian_40",
        "label": "Level 40 Actian Apex",
        "task": "pve_hostile",
        "target": "Actian Apex",
        "level": 40,
        "ship": ("Mantis", "Battleship"),
        "published": ["SNW Pike", "SNW Spock", "SNW Hemmer"],
        "roster": ["SNW Pike", "SNW Spock", "SNW Uhura", "SNW Hemmer", "Pike", "Moreau", "T'Laan", "Chen", "Ghalenar"],
    },
    {
        "id": "xindi_48",
        "label": "Level 48 Xindi-Aquatic Cruiser",
        "task": "pve_hostile",
        "target": "Xindi-Aquatic Cruiser",
        "level": 48,
        "ship": ("Enterprise NX-01", "Explorer"),
        "published": ["Jonathan Archer", "Trip Tucker", "Chen"],
        "roster": ["Jonathan Archer", "Trip Tucker", "Chen", "Pike", "Moreau", "T'Laan", "SNW Pike", "SNW Spock", "The Doctor"],
    },
    {
        "id": "pvp_explorer",
        "label": "Explorer PvP versus a Battleship",
        "task": "pvp",
        "level": 50,
        "enemy_class": "Battleship",
        "ship": ("USS Enterprise", "Explorer"),
        "published": ["Weyoun", "Jack Ransom", "Pon"],
        "roster": ["Weyoun", "Pon", "Ikat'ika", "Jack Ransom", "Khan", "Pike", "Moreau", "Beverly Crusher"],
        "pvp_overrides": {"hp": 12_000_000, "shield_hp": 8_000_000, "base_damage": 1_200_000, "armor": 900_000, "shield_deflection": 900_000, "dodge": 900_000, "armor_piercing": 800_000, "shield_piercing": 800_000, "accuracy": 800_000},
    },
]


def officer(name):
    cls, group = OFFICER_META.get(name, ("Command", "Benchmark"))
    return {"name": name, "class": cls, "group": group, "rank": 5, "level": 30,
            "attack": 5_000, "defense": 5_000, "health": 5_000,
            "stat_basis": "account-adjusted", "available": True}


def choose_variant(name, level):
    record = next(h for h in ALL_HOSTILES if h["name"] == name)
    exact = [v for v in record["variants"] if v["level"] == level]
    return exact[0]["id"] if exact else None


def make_target(s):
    if s["task"] == "pvp":
        return mission_target("pvp", "", s["level"], s["enemy_class"], s["pvp_overrides"])
    return mission_target(s["task"], s["target"], s["level"], "Battleship", {}, choose_variant(s["target"], s["level"]))


def make_ship(s, target):
    total_enemy_hp = target.get("hull_hp", target.get("hp", 100_000)) + target.get("shield_hp", 0)
    enemy_damage = target.get("base_damage", 10_000)
    enemy_attack = {k: target.get(k, enemy_damage) for k in ("armor_piercing", "shield_piercing", "accuracy")}
    attack = max(10_000, total_enemy_hp / 7)
    hull = max(100_000, enemy_damage * 12)
    ship = {
        "name": s["ship"][0], "ship_class": s["ship"][1], "tier": 8, "level": 40,
        "below_deck_slots": 3, "stat_basis": "base", "available": True,
        "officer_bonus": {k: [{"value": 100000, "bonus": 1}] for k in ("attack", "defense", "health")},
        "base_stats": {
            "attack": attack, "health": hull, "shield_health": hull * 0.7,
            "armor": max(enemy_attack.values()), "shield_deflection": max(enemy_attack.values()),
            "dodge": max(enemy_attack.values()), "armor_piercing": attack / 2,
            "shield_piercing": attack / 2, "accuracy": attack / 2,
        },
    }
    if s.get("ship_iso"):
        ship["isolytic_damage_bonus"] = s["ship_iso"]
    return ship


def crew_key(rec):
    return [rec["captain"], rec["officer_1"], rec["officer_2"]]


# Encounter-context checks do not claim to simulate an entire wave.
SCENARIOS += [{**SCENARIOS[0], "id": "swarm_wave", "label": "Swarm in Wave Defense", "task": "wave_defense"}]
SCENARIOS += [{**SCENARIOS[i], "id": SCENARIOS[i]["id"] + "_loot", "label": SCENARIOS[i]["label"] + " (loot priority)", "objective": "loot"} for i in (1, 4)]
results = []
for s in SCENARIOS:
    target = make_target(s)
    profile = {
        "ops_level": 65,
        "syndicate_level": 0,
        "officers": [officer(n) for n in s["roster"]],
        "ships": [make_ship(s, target)],
        "research": {"combat": {"total_officer_bonus": 9.0}, "star_path": {}, "mirror_tree": {}},
        "buildings": {}, "equipment": {},
    }
    task_profile = {"task_type": s["task"], "target": target, "objective": s.get("objective", "combat")}
    recs = find_optimal_crew(profile, task_profile, top_n=10)
    wanted = s["published"]
    published_rank = next((i + 1 for i, r in enumerate(recs) if crew_key(r)[0] == wanted[0] and set(crew_key(r)[1:]) == set(wanted[1:])), None)
    published_members_rank = next((i + 1 for i, r in enumerate(recs) if set(crew_key(r)) == set(wanted)), None)
    results.append({
        "id": s["id"], "label": s["label"], "task": s["task"],
        "target": {k: target.get(k) for k in ("name", "type", "level", "ship_class", "hostile_id", "source")},
        "ship": s["ship"][0], "published_crew": wanted, "published_rank_in_top_10": published_rank,
        "published_members_rank_in_top_10": published_members_rank,
        "top_recommendations": [{
            "rank": i + 1, "crew": crew_key(r), "below_deck": [x["name"] for x in r["below_deck"]],
            "kill_probability": r["simulation"]["kill_probability"],
            "survival_probability": r["simulation"]["survival_probability"],
            "avg_rounds": r["simulation"]["avg_combat_rounds"],
            "unmodelled": r["simulation"]["unmodelled_abilities"],
            "avg_hull_lost": r["simulation"]["avg_hull_lost"],
        } for i, r in enumerate(recs[:5])],
    })

OUT.write_text(json.dumps({"method": "controlled equal-rank/equal-stat synthetic roster; real hostile records", "scenarios": results}, indent=2), encoding="utf-8")
print(OUT)
for r in results:
    print(r["id"], "published rank", r["published_rank_in_top_10"], "top", r["top_recommendations"][0]["crew"])
