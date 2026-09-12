"""
Unit tests for engine/combat_simulator.py
"""
from engine.combat_simulator import simulate_combat


def _ship():
    return {
        "name": "Test Explorer",
        "ship_class": "Explorer",
        "base_stats": {
            "attack": 50000, "defense": 40000, "health": 60000,
            "armor": 15000, "shield_deflection": 20000, "dodge": 10000,
            "armor_piercing": 18000, "shield_piercing": 22000, "accuracy": 12000,
        },
    }


def _target():
    return {
        "name": "Test Hostile", "hp": 300000, "base_damage": 8000,
        "armor_piercing": 5000, "shield_piercing": 5000, "accuracy": 5000,
        "crit_chance": 0.2, "crit_multiplier": 1.5, "iso_defense": 0.3,
    }


def _profile():
    return {
        "research": {
            "mirror_tree": {"apex_barrier": 0},
            "star_path": {"isolytic_damage_bonus": 0.0},
            "critical_mitigation": {},
        }
    }


def _officer(attack=1000, health=1000, name="Officer"):
    return {"name": name, "attack": attack, "health": health, "attack_bonus": 0.0}


class TestSimulateCombat:
    def test_returns_expected_keys(self):
        result = simulate_combat(
            _ship(), [_officer()], [], _profile(), _target(),
            "pve_hostile", num_simulations=20, rng_seed=1,
        )
        for key in ("avg_rounds_to_kill", "survival_probability",
                    "kill_probability", "avg_damage_taken", "simulation_count"):
            assert key in result

    def test_seed_makes_runs_reproducible(self):
        args = (_ship(), [_officer()], [], _profile(), _target(), "pve_hostile")
        a = simulate_combat(*args, num_simulations=50, rng_seed=7)
        b = simulate_combat(*args, num_simulations=50, rng_seed=7)
        assert a == b

    def test_crew_attack_speeds_up_kills(self):
        weak = simulate_combat(
            _ship(), [_officer(attack=0, health=0)], [], _profile(), _target(),
            "pve_hostile", num_simulations=30, rng_seed=3,
        )
        strong = simulate_combat(
            _ship(), [_officer(attack=60000, health=0)], [], _profile(), _target(),
            "pve_hostile", num_simulations=30, rng_seed=3,
        )
        assert strong["avg_rounds_to_kill"] < weak["avg_rounds_to_kill"]

    def test_below_deck_stats_count_toward_hull(self):
        fragile = simulate_combat(
            _ship(), [], [], _profile(),
            {**_target(), "base_damage": 60000}, "pve_hostile",
            num_simulations=30, rng_seed=5,
        )
        tanky = simulate_combat(
            _ship(), [], [_officer(health=500000)], _profile(),
            {**_target(), "base_damage": 60000}, "pve_hostile",
            num_simulations=30, rng_seed=5,
        )
        assert tanky["survival_probability"] >= fragile["survival_probability"]
        assert tanky["avg_damage_taken"] >= 0

    def test_isolytic_research_speeds_up_kills(self):
        profile_iso = _profile()
        profile_iso["research"]["star_path"]["isolytic_damage_bonus"] = 1.0
        base = simulate_combat(
            _ship(), [], [], _profile(), _target(),
            "pve_hostile", num_simulations=30, rng_seed=9,
        )
        iso = simulate_combat(
            _ship(), [], [], profile_iso, _target(),
            "pve_hostile", num_simulations=30, rng_seed=9,
        )
        assert iso["avg_rounds_to_kill"] <= base["avg_rounds_to_kill"]
