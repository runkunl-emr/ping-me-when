"""HTTP server: serves the SPA + small JSON API for the listener."""
from __future__ import annotations
import atexit
import os
import signal
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import store, notify
from .listener import Hit, Listener


REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"

# Server is bound to loopback. Anything outside loopback is rejected at the
# middleware level — defense in depth in case a future change accidentally
# binds to 0.0.0.0.
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}

app = FastAPI(title="ping-me-when", docs_url=None, redoc_url=None)

_listener: Optional[Listener] = None


@app.middleware("http")
async def csrf_and_host_guard(request: Request, call_next):
    """Lightweight CSRF + host-pinning protection.

    1. Reject anything where the Host header isn't a loopback name. This stops
       DNS-rebinding attacks where a malicious site tricks the browser into
       sending requests to our server.
    2. For state-changing methods, require a JSON Content-Type. Stops naive
       cross-origin <form> POSTs (which use application/x-www-form-urlencoded).
    """
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if host not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "host not allowed"}, status_code=400)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        ct = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
        # Allow empty body POSTs (start/stop/test-notify) too.
        cl = request.headers.get("content-length") or "0"
        if cl != "0" and ct != "application/json":
            return JSONResponse({"detail": "json required"}, status_code=415)
    return await call_next(request)


def _on_hit(h: Hit) -> None:
    cfg = store.load()
    # Title: prefer user-set label; otherwise show "<author> in #<channel-name>".
    where = f"#{h.channel_name}" if h.channel_name else f"#{h.channel_id[-6:]}"
    title = h.sub.label or f"{h.author} in {where}"
    body = h.content.strip() or "(image / embed only)"
    notify.dispatch(
        title=f"📨 {title}",
        message=body,
        mac=cfg.notify.mac,
        webhook_url=cfg.notify.webhook_url or None,
        open_url=h.discord_url(),
    )


# ---------- API ----------

class SubscriptionIn(BaseModel):
    channel_id: str = Field(min_length=1, max_length=32)
    # 30 usernames per channel is more than enough for any realistic use.
    usernames: list[str] = Field(default_factory=list, max_length=30)
    label: str = Field(default="", max_length=120)

    @field_validator("channel_id")
    @classmethod
    def _channel_digits(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("channel_id must be a numeric Discord snowflake")
        return v

    @field_validator("usernames")
    @classmethod
    def _validate_usernames(cls, v: list[str]) -> list[str]:
        cleaned = []
        for u in v:
            u = (u or "").strip()
            if not u:
                continue
            if len(u) > 64:
                raise ValueError(f"username too long: {u[:20]}…")
            cleaned.append(u)
        if not cleaned:
            raise ValueError("at least one username required")
        return cleaned


class NotifyIn(BaseModel):
    mac: bool = True
    webhook_url: str = ""

    @field_validator("webhook_url")
    @classmethod
    def _validate_webhook(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            return ""
        try:
            parsed = urllib.parse.urlparse(v)
        except Exception:
            raise ValueError("invalid URL")
        if parsed.scheme != "https":
            raise ValueError("webhook URL must be https://")
        # Discord-only — narrow surface, easy to verify.
        if not (parsed.netloc.endswith(".discord.com") or parsed.netloc == "discord.com"):
            raise ValueError("only discord.com webhooks are allowed")
        return v


class ConfigIn(BaseModel):
    token: str = Field(default="", max_length=200)
    # 50 subscriptions is plenty for personal use; cap stops accidental DoS
    # if someone pastes garbage into the API.
    subscriptions: list[SubscriptionIn] = Field(default_factory=list, max_length=50)
    notify: NotifyIn = Field(default_factory=NotifyIn)


@app.get("/api/config")
def get_config():
    cfg = store.load()
    return {
        "token_set": bool(cfg.token),
        "subscriptions": [s.__dict__ for s in cfg.subscriptions],
        "notify": cfg.notify.__dict__,
    }


@app.post("/api/config")
def post_config(payload: ConfigIn):
    existing = store.load()
    # Empty token in the payload means "don't touch the saved one" — so users
    # don't have to re-paste their token every time they edit subscriptions.
    new_token = payload.token.strip() or existing.token
    cfg = store.Config(
        token=new_token,
        subscriptions=[store.Subscription(**s.model_dump()) for s in payload.subscriptions],
        notify=store.Notify(**payload.notify.model_dump()),
    )
    store.save(cfg)
    if _listener:
        _listener.update_config(cfg)
    return {"ok": True}


@app.post("/api/start")
def start():
    global _listener
    cfg = store.load()
    if _listener and _listener._thread and _listener._thread.is_alive():
        return {"ok": True, "already_running": True}
    _listener = Listener(cfg, on_hit=_on_hit)
    _listener.start()
    return {"ok": True}


@app.post("/api/stop")
def stop():
    if _listener:
        _listener.stop()
    return {"ok": True}


@app.get("/api/status")
def status():
    if not _listener:
        return {"running": False, "connected": False, "last_error": "", "hits": []}
    s = _listener.status
    return {
        "running": _listener._thread is not None and _listener._thread.is_alive(),
        "connected": s.connected,
        "last_error": s.last_error,
        "started_at": s.started_at,
        "hits": [
            {
                "label": h.sub.label or h.author,
                "author": h.author,
                "channel_id": h.channel_id,
                "channel_name": h.channel_name,
                "content": h.content,
                "timestamp": h.timestamp,
                "message_id": h.message_id,
                "url": h.discord_url(),
            } for h in reversed(s.hits[-50:])  # newest first, last 50
        ],
    }


@app.post("/api/test-notify")
def test_notify():
    cfg = store.load()
    res = notify.dispatch(
        title="ping-me-when test",
        message="If you see this, notifications are working.",
        mac=cfg.notify.mac,
        webhook_url=cfg.notify.webhook_url or None,
    )
    return {"ok": True, "result": res}


# ---------- static UI ----------

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def root():
    f = WEB_DIR / "index.html"
    if not f.exists():
        raise HTTPException(500, "web/index.html missing")
    return f.read_text(encoding="utf-8")


def _shutdown():
    """Stop the listener cleanly so we don't leak the WebSocket on exit."""
    global _listener
    if _listener:
        try:
            _listener.stop(join_timeout=2)
        except Exception:
            pass
        _listener = None


@app.on_event("shutdown")
async def _on_shutdown():
    _shutdown()


def main():
    """Entry point for `python -m src.server`. Opens a browser tab and serves."""
    import uvicorn
    host = os.environ.get("PING_HOST", "127.0.0.1")
    port = int(os.environ.get("PING_PORT", "8765"))
    # Hard-pin to loopback. No env override here — prevents accidental exposure.
    if host not in ALLOWED_HOSTS:
        host = "127.0.0.1"
    if os.environ.get("PING_NO_BROWSER", "") != "1":
        try:
            webbrowser.open(f"http://{host}:{port}/")
        except Exception:
            pass
    # Belt + suspenders: also catch SIGTERM/SIGINT so the listener gets a chance
    # to close cleanly even if FastAPI's shutdown event doesn't fire.
    atexit.register(_shutdown)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, lambda *_: _shutdown())
        except (ValueError, OSError):
            # Can fail if not on the main thread (e.g. inside tests).
            pass
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
