"""Capture the real UI with synthetic data and no connected Google Sheet."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "docs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stfc-docs-") as directory:
        shutil.copyfile(
            ROOT / "docs" / "demo-profile.json", Path(directory) / "player_profile.json"
        )
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "run_app.py"), "--headless", "--port", "0"],
            cwd=ROOT,
            env={**os.environ, "STFC_ADVISOR_DATA_DIR": directory},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            runtime = Path(directory) / "desktop.json"
            deadline = time.monotonic() + 45
            while not runtime.exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(
                        f"Demo server failed. Check {directory}/app.log before exiting."
                    )
                time.sleep(0.1)
            base = f"http://127.0.0.1:{json.loads(runtime.read_text())['port']}"
            with sync_playwright() as pw:
                launch = {"headless": True}
                if executable := os.environ.get("STFC_SCREENSHOT_BROWSER"):
                    launch["executable_path"] = executable
                browser = pw.chromium.launch(**launch)
                page = browser.new_page(
                    viewport={"width": 1440, "height": 1000}, device_scale_factor=1
                )
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                expect(page.locator("#ops-number")).to_have_text("45")
                expect(page.locator("#sheet-sync-indicator")).to_contain_text("paused")
                page.screenshot(path=str(output / "planner.png"), full_page=True)
                page.locator(".target-details summary").click()
                page.locator("#stat-hp").fill("300000")
                page.locator("#stat-base_damage").fill("5000")
                page.locator("#recommend-button").click()
                expect(page.locator(".recommendation")).to_be_visible(timeout=60000)
                page.locator(".recommendation").screenshot(
                    path=str(output / "recommendations.png")
                )
                for view in ["fleet", "roster", "account"]:
                    page.locator(f'.nav-button[data-view="{view}"]').click()
                    expect(page.locator(f"#view-{view}")).to_be_visible()
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=str(output / f"{view}.png"))
                assert not errors, errors
                browser.close()
            print(f"Captured 5 screenshots from the isolated demo account: {output}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
