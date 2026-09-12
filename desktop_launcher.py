"""Local desktop lifecycle: one instance, tray menu and writable diagnostics."""

import json
import logging
import os
import socket
import sys
import threading
import time
import uuid
import webbrowser
from logging.handlers import RotatingFileHandler
from urllib.request import ProxyHandler, build_opener

import paths


class InstanceLock:
    """OS-owned lock; released automatically if the process crashes."""

    def __init__(self, directory):
        self.stream = (directory / "desktop.lock").open("a+b")
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)

    def acquire(self):
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def close(self):
        self.stream.close()


def bind_local_port(preferred):
    """Keep the socket reserved through server startup; fall back if occupied."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            sock.bind(("127.0.0.1", preferred))
        except OSError:
            if preferred == 0:
                raise
            sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        sock.setblocking(False)
        return sock
    except BaseException:
        sock.close()
        raise


def existing_instance(directory, timeout=20):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            info = json.loads((directory / "desktop.json").read_text())
            port = int(info["port"])
            if not 0 < port < 65536:
                raise ValueError("Invalid local port")
            url = f"http://127.0.0.1:{port}"
            with opener.open(url + "/api/health", timeout=1) as response:
                health = json.load(response)
            if health.get("desktop_instance") == info["instance"]:
                return url
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.2)
    raise RuntimeError(
        "The app is already starting or shutting down. Try again in a moment."
    )


def configure_logging(directory):
    handler = RotatingFileHandler(
        directory / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handlers = [handler]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def show_failure(message):
    logging.getLogger(__name__).error(message)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "STFC Advisor", 0x10)
    elif sys.stderr is not None:
        print(message, file=sys.stderr)


def launch(port=8000, open_browser=True, tray=False):
    directory = paths.data_dir()
    configure_logging(directory)
    lock = InstanceLock(directory)
    server = worker = sock = None
    runtime = directory / "desktop.json"
    try:
        if not lock.acquire():
            url = existing_instance(directory)
            if open_browser:
                webbrowser.open(url)
            return
        # Import only after taking the lock so a second launch cannot start syncing.
        import uvicorn

        from app import app

        sock = bind_local_port(port)
        actual_port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{actual_port}"
        instance = uuid.uuid4().hex
        app.state.desktop_instance = instance
        server = uvicorn.Server(
            uvicorn.Config(app, log_config=None, host="127.0.0.1", port=actual_port)
        )
        worker = threading.Thread(
            target=server.run,
            kwargs={"sockets": [sock]},
            name="stfc-server",
            daemon=True,
        )
        worker.start()
        deadline = time.monotonic() + 30
        while not server.started:
            if not worker.is_alive() or time.monotonic() > deadline:
                raise RuntimeError(
                    "The local server could not start. See app.log for details."
                )
            time.sleep(0.05)
        runtime.write_text(
            json.dumps({"port": actual_port, "instance": instance}), encoding="utf-8"
        )
        if tray:
            run_tray(url, server, worker, directory, open_browser)
        else:
            if open_browser:
                webbrowser.open(url)
            while worker.is_alive():
                worker.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.should_exit = True
            if worker is not None:
                worker.join(timeout=45)
            runtime.unlink(missing_ok=True)
        if sock is not None:
            sock.close()
        lock.close()


def run_tray(url, server, worker, directory, open_browser):
    import pystray
    from PIL import Image

    def open_app(icon, item):
        webbrowser.open(url)

    def open_data(icon, item):
        os.startfile(str(directory))

    def quit_app(icon, item):
        server.should_exit = True
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open app", open_app, default=True),
        pystray.MenuItem("Open data and logs", open_data),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )
    with Image.open(paths.resource_path("web", "desktop-icon.png")) as source:
        icon = pystray.Icon(
            "STFC-Advisor", source.copy(), "STFC Advisor — running", menu
        )

    def ready(icon):
        icon.visible = True
        if open_browser:
            webbrowser.open(url)
        while worker.is_alive() and not server.should_exit:
            worker.join(timeout=0.5)
        icon.stop()

    icon.run(setup=ready)
