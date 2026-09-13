"""Standard Operations-based PvP reference, separate from ship combat level."""

import json
from functools import lru_cache

from engine.catalogue import BASE


@lru_cache(maxsize=1)
def bands():
    return {
        r["level"]: r
        for r in json.loads(
            (BASE / "pvp_bands_summary.json").read_text(encoding="utf-8")
        )
    }


def check_band(player_ops, opponent_ops, task):
    station = task in {"pvp_station", "station_raid"}
    minimum = 15 if station else 10
    row = bands().get(player_ops)
    result = {
        "player_ops": player_ops,
        "opponent_ops": opponent_ops,
        "minimum_ops": minimum,
        "source": "https://stfc.space/pvp_bands",
        "status": "unknown",
        "note": "Standard PvP reference only. Incursions and other event-specific rules are not modelled.",
    }
    if row:
        result.update(lower=max(minimum, row["lower"]), upper=row["upper"])
    if player_ops < minimum or (opponent_ops is not None and opponent_ops < minimum):
        result.update(
            status="protected",
            message=f"Standard {'station' if station else 'ship'} PvP starts at Operations {minimum}; this encounter is below that threshold.",
        )
    elif not row:
        result["message"] = (
            "No PvP band exists for your Operations level in the snapshot; no range is extrapolated."
        )
    elif opponent_ops is None:
        result["message"] = (
            f"Your standard target Operations range is {result['lower']}–{result['upper']}. Enter opponent Operations to check this encounter; ship level is not Operations level."
        )
    else:
        valid = result["lower"] <= opponent_ops <= result["upper"]
        result.update(
            status="within_band" if valid else "outside_band",
            message=f"Opponent Operations {opponent_ops} is {'within' if valid else 'outside'} your standard target range {result['lower']}–{result['upper']}.",
        )
    return result
