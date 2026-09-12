"""Launch the local tactical console; packaged Windows builds use a tray icon."""

import argparse
import sys

from desktop_launcher import launch, show_failure


def main():
    parser = argparse.ArgumentParser(description="STFC Tactical Advisor")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without a tray icon or browser (diagnostics).",
    )
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    try:
        launch(
            port=args.port,
            open_browser=not (args.no_browser or args.headless),
            tray=sys.platform == "win32" and not args.headless,
        )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception("Desktop startup failed")
        show_failure(
            f"{exc}\n\nYour saved account has been retained. Check app.log in the app data folder."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
