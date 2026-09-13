"""Combat-triangle preferences and baseline strike teams, not guaranteed counters.

Sources are listed in docs/RULES.md. Strike teams require the player's matching
ship class; their names do not imply that they counter that same enemy class.
"""

from engine.abilities import officer_available, officer_identity

STRIKE_TEAMS = {
    "Explorer": {
        "name": "Explorer Strike Team",
        "officers": ["Weyoun", "Pon", "Ikat'ika"],
        "strength": "Explorer crew with morale-based effects",
        "counters": "Interceptor",
    },
    "Interceptor": {
        "name": "Interceptor Strike Team",
        "officers": ["Gul Dukat", "Garak", "Damar"],
        "strength": "Interceptor crew with critical-hit and shot effects",
        "counters": "Battleship",
    },
    "Battleship": {
        "name": "Battleship Strike Team",
        "officers": ["Strike Team La'an", "Strike Team Una", "Strike Team Ortegas"],
        "strength": "Battleship crew with burning-based effects",
        "counters": "Explorer",
    },
}
COUNTER_MAP = {
    "Battleship": "Interceptor",
    "Explorer": "Battleship",
    "Interceptor": "Explorer",
}


def suggest_pvp_counter(enemy_ship_class: str, player_officers: list[dict]) -> dict:
    counter_class = COUNTER_MAP.get(enemy_ship_class)
    if not counter_class:
        return {"error": f"No combat-triangle counter for {enemy_ship_class}."}
    team = STRIKE_TEAMS[counter_class]
    owned = {officer_identity(o) for o in player_officers if officer_available(o)}
    available = [n for n in team["officers"] if officer_identity({"name": n}) in owned]
    missing = [
        n for n in team["officers"] if officer_identity({"name": n}) not in owned
    ]
    return {
        "recommended_team": team["name"],
        "recommended_ship_class": counter_class,
        "team_officers": team["officers"],
        "available": available,
        "missing": missing,
        "completeness": f"{len(available)}/3",
        "strategy": team["strength"],
        "note": "Combat-triangle preference and baseline crew only. Account stats and ability conditions can outweigh this advantage.",
    }
