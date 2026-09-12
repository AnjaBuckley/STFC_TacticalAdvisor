"""Exercise the built executable with an isolated, blank user directory."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener


def check(executable):
    executable = Path(executable).resolve()
    command = (
        [sys.executable, str(executable)]
        if executable.suffix == ".py"
        else [str(executable)]
    )
    with tempfile.TemporaryDirectory(prefix="stfc-bundle-check-") as folder:
        directory = Path(folder)
        env = {**os.environ, "STFC_ADVISOR_DATA_DIR": folder}
        process = subprocess.Popen(
            [*command, "--headless", "--port", "0"], env=env, cwd=folder
        )
        opener = build_opener(ProxyHandler({}))
        try:
            deadline = time.monotonic() + 60
            while not (directory / "desktop.json").exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    log = directory / "app.log"
                    raise RuntimeError(
                        log.read_text()
                        if log.exists()
                        else "Packaged server did not start"
                    )
                time.sleep(0.2)
            runtime = json.loads((directory / "desktop.json").read_text())
            base = f"http://127.0.0.1:{runtime['port']}"

            def get(route):
                with opener.open(base + route, timeout=15) as response:
                    return response.read()

            health = json.loads(get("/api/health"))
            assert health["desktop_instance"] == runtime["instance"]
            boot = json.loads(get("/api/bootstrap"))
            assert boot["profile"]["ships"] == []
            assert boot["profile"]["officers"] == []
            assert json.loads(get("/api/sync"))["enabled"] is False
            for route in [
                "/",
                "/assets/app.js",
                "/assets/style.css",
                "/assets/desktop-icon.png",
            ]:
                assert get(route)
            second = subprocess.run(
                [*command, "--headless"], env=env, cwd=folder, timeout=30, check=True
            )
            assert second.returncode == 0
            assert process.poll() is None
            print(
                "PASS: packaged startup, clean account, local API/assets, sync disabled, second launch reuses instance."
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=50)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    check(sys.argv[1])
