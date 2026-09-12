"""
Recommendation Renderer — STFC Tactical Advisor

Formats and prints crew recommendations in the box-drawing output style
described in claude.md section 7.
"""

_WIDTH = 62
_BOX_TOP = "╔" + "═" * _WIDTH + "╗"
_BOX_BTM = "╚" + "═" * _WIDTH + "╝"
_BOX_DIV = "╠" + "═" * _WIDTH + "╣"


def _line(text: str = "") -> str:
    """Left-pad a line inside the box."""
    return f"║  {text:<{_WIDTH - 2}}║"


def _centre(text: str) -> str:
    return f"║{text.center(_WIDTH)}║"


def render_recommendations(
    recommendations: list[dict],
    task_profile: dict,
    player_profile: dict | None = None,
) -> None:
    """
    Print all recommendations to stdout in the STFC Tactical Advisor style.
    """
    if not recommendations:
        print("\nNo recommendations generated. Check player profile ships/officers.")
        return

    task_type = task_profile.get("task_type", "pve_general")
    target = task_profile.get("target", {})
    target.get("name", "Unknown Target")
    target.get("ship_class", "Unknown")

    for idx, rec in enumerate(recommendations, start=1):
        _render_single(idx, rec, task_type, target, player_profile)
        if idx < len(recommendations):
            print()


def _render_single(
    idx: int,
    rec: dict,
    task_type: str,
    target: dict,
    player_profile: dict | None,
) -> None:
    target_name = target.get("name", "Unknown Target")
    target_class = target.get("ship_class", "Unknown")
    print(_BOX_TOP)
    title = f"STFC TACTICAL ADVISOR — RECOMMENDATION #{idx}"
    print(_centre(title))
    print(_BOX_BTM)
    print()

    # TASK
    print(f"  TASK:     {target_name} ({target_class}) — Task: {task_type}")
    real = target.get("real_hostile")
    if real:
        print(
            f"            Stats from: {real['name']} L{real['level']} "
            f"(strength {real['strength']:,}) [data.stfc.space]"
        )
    print()

    # SHIP
    print(f"  SHIP:     {rec['ship']}")

    sim = rec.get("simulation", {})
    print(f"  MODEL HULL: {sim.get('hull_max', 'unknown')}")
    print()

    # BRIDGE
    print("  BRIDGE:")
    synergy_tag = f"  [{rec['synergy']}]" if rec.get("synergy") != "NO SYNERGY" else ""
    print(f"    Captain:   {rec['captain']}{synergy_tag}")
    print(f"    Officer 1: {rec['officer_1']}")
    print(f"    Officer 2: {rec['officer_2']}")
    print()

    # BELOW DECK
    below = rec.get("below_deck", [])
    if below:
        print(f"  BELOW DECK ({len(below)} slots):")
        for i, slot in enumerate(below, start=1):
            print(f"    {i}. {slot['name']:<20} → {slot['function']}")
    else:
        print("  BELOW DECK: (no slots / not configured)")
    print()

    # COMBAT SCORES
    print("  COMBAT SCORES:")

    print(f"    Standard Mitigation: {sim.get('standard_mitigation', 0) * 100:.1f}%")
    print(
        f"    Model kill rate: {sim.get('kill_probability', 0):.1f}% (95% sampling interval {sim.get('kill_interval_95')})"
    )
    print(f"    Kill rounds (successful runs only): {sim.get('avg_rounds_to_kill')}")
    print(f"    Timeouts: {sim.get('timeout_probability', 0):.1f}%")
    for warning in sim.get("limitations", []):
        print(f"    MODEL LIMITATION: {warning}")

    print(f"    Score:               {rec['score']:.4f}")
    print()

    # REASONING
    reasoning = rec.get("reasoning", [])
    if reasoning:
        print("  REASONING:")
        for line in reasoning:
            # Wrap long lines
            if len(line) > 56:
                words = line.split()
                current = "    → "
                for word in words:
                    if len(current) + len(word) + 1 > 62:
                        print(current)
                        current = "      " + word + " "
                    else:
                        current += word + " "
                if current.strip():
                    print(current.rstrip())
            else:
                print(f"    → {line}")
    print()

    # WARNINGS
    warnings = []
    if rec["score"] < 0.4:
        warnings.append("Low overall score — consider alternative officers.")
    if rec.get("synergy") == "NO SYNERGY":
        warnings.append(
            "No synergy detected. Consider grouping captain with same-group officers."
        )

    if warnings:
        print("  WARNINGS:")
        for w in warnings:
            print(f"    → {w}")
        print()

    # LINKS
    print("  LINKS:")
    print("    Validate mitigation: https://stfc-toolbox.vercel.app")
    print("    Officer details:     https://stfc.space")
    print("    Crew combos:         https://stfc.phd")
    print()
    print("─" * (_WIDTH + 4))
