import typer
import json
from pathlib import Path
from engine.hostile_stats import enrich_target
from optimizer.crew_optimizer import find_optimal_crew
from output.renderer import render_recommendations

app = typer.Typer()

_HOSTILES_PATH = Path(__file__).parent / "data" / "hostiles.json"


def _load_hostile(target_name: str) -> dict:
    """Look up a hostile by name from hostiles.json. Falls back to a minimal dict."""
    if _HOSTILES_PATH.exists():
        hostiles = json.loads(_HOSTILES_PATH.read_text())
        name_lower = target_name.lower()
        for h in hostiles:
            if h["name"].lower() == name_lower:
                return h
        # Partial match
        for h in hostiles:
            if name_lower in h["name"].lower() or h["name"].lower() in name_lower:
                return h
    return {"name": target_name, "ship_class": "Battleship", "type": "Unknown"}


@app.command()
def recommend(
    task: str = typer.Option("pve_hostile", help="Task type: pve_hostile, pvp, duo_wave_defense, etc."),
    target: str = typer.Option("Gorn Hunter", help="Target hostile name (must match hostiles.json)"),
    profile: str = typer.Option("profiles/player_profile.json", help="Path to player profile"),
    top: int = typer.Option(3, help="Number of recommendations to show"),
    level: int = typer.Option(None, help="Hostile level (picks closest real variant; default: top of the target's range)"),
    list_targets: bool = typer.Option(False, "--list", help="List all available target names")
):
    if list_targets:
        if _HOSTILES_PATH.exists():
            hostiles = json.loads(_HOSTILES_PATH.read_text())
            typer.echo("\nAvailable targets:")
            for h in hostiles:
                typer.echo(f"  {h['name']:35s} [{h['type']:20s}] Lvl {h['level_range'][0]}-{h['level_range'][1]}")
        return

    profile_path = Path(profile)
    if not profile_path.exists():
        # Allow running the CLI from any working directory
        profile_path = Path(__file__).parent / profile
    if not profile_path.exists():
        typer.echo(f"Error: player profile not found: {profile}", err=True)
        raise typer.Exit(code=1)
    player_profile = json.loads(profile_path.read_text())
    hostile = enrich_target(_load_hostile(target), level=level)
    task_profile = {"task_type": task, "target": hostile}
    recommendations = find_optimal_crew(player_profile, task_profile, top_n=top)
    render_recommendations(recommendations, task_profile, player_profile)

if __name__ == "__main__":
    app()
