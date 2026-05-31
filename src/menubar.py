"""macOS menu-bar app wrapper.

Runs the rumps event loop on the main thread and starts the FastAPI/uvicorn
server in a background thread. Auto-starts the listener on launch if a config
already exists, so users with a saved config don't have to click anything.

Quit from the menu cleanly stops both the listener and uvicorn.
"""
from __future__ import annotations
import os
import platform
import subprocess
import threading
import time
import webbrowser

if platform.system() != "Darwin":
    raise RuntimeError("menubar.py is macOS-only; use `python -m src.server` elsewhere")

import rumps
import uvicorn

from . import store, server
from .listener import Listener


PORT = int(os.environ.get("PING_PORT", "8765"))
URL = f"http://127.0.0.1:{PORT}/"


class PingMeWhenApp(rumps.App):
    def __init__(self):
        super().__init__("📨", quit_button=None)
        self.menu = [
            rumps.MenuItem("Status: stopped", callback=None),
            rumps.separator,
            rumps.MenuItem("Start listening", callback=self.on_start),
            rumps.MenuItem("Stop", callback=self.on_stop),
            rumps.separator,
            rumps.MenuItem("Open settings…", callback=self.on_settings),
            rumps.MenuItem("Send test notification", callback=self.on_test),
            rumps.separator,
            rumps.MenuItem("Quit", callback=self.on_quit),
        ]
        # Periodic status refresh (every 2s)
        rumps.Timer(self._refresh_status, 2).start()

    @property
    def _status_item(self) -> rumps.MenuItem:
        return self.menu["Status: stopped"] if "Status: stopped" in self.menu else None

    def _refresh_status(self, _timer):
        listener = server._listener  # access the live module-level instance
        if listener and listener._thread and listener._thread.is_alive():
            label = "● connected" if listener.status.connected else "● starting…"
            self.title = "📨"  # could also use a colored variant
        elif listener and listener.status.last_error:
            label = f"✗ {listener.status.last_error[:40]}"
            self.title = "📨"
        else:
            label = "Status: stopped"
            self.title = "📨"
        # Update first item's text
        for item in self.menu.values():
            if hasattr(item, "title") and item.title.startswith(("Status:", "●", "✗")):
                item.title = label
                break

    # ---- menu callbacks ----

    def on_start(self, _):
        try:
            cfg = store.load()
            if not cfg.token or not cfg.subscriptions:
                rumps.alert(
                    title="ping-me-when",
                    message="Please configure your token and at least one subscription first.",
                    ok="Open settings",
                )
                webbrowser.open(URL)
                return
            if server._listener and server._listener._thread and server._listener._thread.is_alive():
                rumps.notification("ping-me-when", "Already running", "")
                return
            server._listener = Listener(cfg, on_hit=server._on_hit)
            server._listener.start()
            rumps.notification("ping-me-when", "Started", "Listening for new messages.")
        except Exception as e:
            rumps.alert(title="ping-me-when", message=f"Could not start: {e}")

    def on_stop(self, _):
        if server._listener:
            server._listener.stop()
        rumps.notification("ping-me-when", "Stopped", "")

    def on_settings(self, _):
        webbrowser.open(URL)

    def on_test(self, _):
        from . import notify as notify_mod
        notify_mod.dispatch(
            title="ping-me-when test",
            message="If you see this, notifications are working.",
            mac=True,
        )

    def on_quit(self, _):
        # Stop listener cleanly so we don't leave a dangling Discord WS session.
        if server._listener:
            try:
                server._listener.stop(join_timeout=2)
            except Exception:
                pass
        rumps.quit_application()


# ---------- background server thread ----------

def _run_server():
    """Run uvicorn in a thread so the main thread can run the rumps loop."""
    try:
        uvicorn.run(server.app, host="127.0.0.1", port=PORT, log_level="warning")
    except Exception as e:
        print(f"[menubar] server thread crashed: {e}")


def _maybe_autostart():
    """Wait for the server to be reachable, then auto-start the listener if a
    saved token + subscriptions are present. Lets returning users skip the
    'Start listening' click each launch."""
    for _ in range(50):  # up to 5s
        time.sleep(0.1)
        cfg = store.load()
        if cfg.token and cfg.subscriptions:
            try:
                server._listener = Listener(cfg, on_hit=server._on_hit)
                server._listener.start()
            except Exception as e:
                print(f"[menubar] autostart failed: {e}")
            return


def main():
    threading.Thread(target=_run_server, daemon=True).start()
    threading.Thread(target=_maybe_autostart, daemon=True).start()
    PingMeWhenApp().run()


if __name__ == "__main__":
    main()
