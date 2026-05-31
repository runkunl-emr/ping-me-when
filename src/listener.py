"""Discord Gateway listener. One thread per process.

Connects to wss://gateway.discord.gg, identifies as a user with the given token,
heartbeats every 41250ms (or whatever the server tells us), and routes any
MESSAGE_CREATE event whose channel + author matches a configured subscription
to the notification layer.

Scope is intentionally tiny — see README for what we deliberately don't do.
"""
from __future__ import annotations
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import websocket  # websocket-client

from .store import Config, Subscription


GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"
INTENT_GUILD_MESSAGES = 1 << 9
INTENT_MESSAGE_CONTENT = 1 << 15  # only relevant if you ever switch to bot tokens
DEFAULT_INTENTS = INTENT_GUILD_MESSAGES | INTENT_MESSAGE_CONTENT


@dataclass
class Hit:
    """One matched message worth notifying about."""
    sub: Subscription
    author: str
    content: str
    message_id: str
    channel_id: str
    timestamp: str = ""
    channel_name: str = ""  # populated from GUILD_CREATE if known
    guild_id: str = ""

    def discord_url(self) -> str:
        if self.guild_id:
            return f"https://discord.com/channels/{self.guild_id}/{self.channel_id}/{self.message_id}"
        # DM fallback (no guild)
        return f"https://discord.com/channels/@me/{self.channel_id}/{self.message_id}"


@dataclass
class Status:
    connected: bool = False
    last_error: str = ""
    last_hit: Optional[Hit] = None
    hits: list[Hit] = field(default_factory=list)
    started_at: float = 0.0


class Listener:
    """Owns the websocket loop. Public surface: start(), stop(), status."""

    MAX_HISTORY = 200

    def __init__(self, cfg: Config, on_hit: Callable[[Hit], None] | None = None):
        self.cfg = cfg
        self.on_hit = on_hit or (lambda h: None)
        self.status = Status()
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_interval_ms = 41250
        self._last_seq: Optional[int] = None
        self._stop = threading.Event()
        # channel_id -> {"name": str, "guild_id": str}
        # Populated lazily from GUILD_CREATE events.
        self._channel_meta: dict[str, dict] = {}

    # ---- public ----

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        # Reject obvious garbage tokens (empty / pure-whitespace / way-too-short).
        token = (self.cfg.token or "").strip()
        if len(token) < 30:
            raise ValueError("token looks invalid (too short)")
        if not self.cfg.subscriptions:
            raise ValueError("no subscriptions configured")
        # Reset the stop flag — important for restarts after INVALID_SESSION.
        self._stop = threading.Event()
        self._last_seq = None
        self.status = Status(started_at=time.time())
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, join_timeout: float = 5.0) -> None:
        """Signal the listener to stop and wait briefly for it to do so."""
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self.status.connected = False
        # Best-effort wait — we don't want to hang the caller (server shutdown).
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=join_timeout)
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.0)

    def update_config(self, cfg: Config) -> None:
        """Hot-swap subscriptions. Token change requires a restart."""
        self.cfg = cfg

    # ---- internals ----

    def _run(self) -> None:
        # Outer loop: reconnect on any disconnection until the user explicitly stops.
        backoff = 1
        while not self._stop.is_set():
            try:
                self._ws = websocket.WebSocketApp(
                    GATEWAY_URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=None)  # we manage our own heartbeat
            except Exception as e:
                self.status.last_error = f"socket: {e}"
            # Mark connection down so the heartbeat thread exits before we open a new one.
            self.status.connected = False
            if self._stop.is_set():
                break
            # Wait for the previous heartbeat thread to finish so we don't
            # accumulate one per reconnect attempt.
            if self._heartbeat_thread and self._heartbeat_thread.is_alive():
                self._heartbeat_thread.join(timeout=2)
            # Reconnect backoff: 1, 2, 4, 8, 16, max 60.
            time.sleep(min(backoff, 60))
            backoff = min(backoff * 2, 60)

    def _on_open(self, _ws):
        self.status.connected = True
        self.status.last_error = ""

    def _on_close(self, _ws, code, reason):
        self.status.connected = False
        if reason:
            self.status.last_error = f"closed: {code} {reason}"

    def _on_error(self, _ws, err):
        self.status.last_error = f"error: {err}"

    def _on_message(self, ws, raw):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        op = payload.get("op")
        seq = payload.get("s")
        if seq is not None:
            self._last_seq = seq

        if op == 10:  # HELLO
            self._heartbeat_interval_ms = payload["d"]["heartbeat_interval"]
            self._send_identify(ws)
            self._start_heartbeat(ws)
        elif op == 0:
            t = payload.get("t")
            if t == "MESSAGE_CREATE":
                self._handle_message(payload["d"])
            elif t in ("GUILD_CREATE", "GUILD_UPDATE", "READY"):
                self._learn_channel_names(payload["d"])
            elif t in ("CHANNEL_CREATE", "CHANNEL_UPDATE"):
                self._learn_one_channel(payload["d"])
        elif op == 11:  # HEARTBEAT_ACK — silent
            pass
        elif op == 9:  # INVALID_SESSION — token bad, don't auto-retry tightly
            self.status.last_error = "invalid session — check token"
            self._stop.set()

    def _learn_channel_names(self, data: dict) -> None:
        """Cache channel id -> {name, guild_id} from a GUILD_CREATE-shaped payload."""
        guild_id = str(data.get("id", "") or data.get("guild_id", "") or "")
        for ch in data.get("channels", []) or []:
            cid = str(ch.get("id", ""))
            if cid:
                self._channel_meta[cid] = {
                    "name": ch.get("name", "") or "",
                    "guild_id": guild_id,
                }
        # READY also includes private_channels (DMs); ignore those for guild_id.
        for dm in data.get("private_channels", []) or []:
            cid = str(dm.get("id", ""))
            if cid:
                self._channel_meta[cid] = {"name": dm.get("name") or "DM", "guild_id": ""}

    def _learn_one_channel(self, ch: dict) -> None:
        cid = str(ch.get("id", ""))
        if cid:
            self._channel_meta[cid] = {
                "name": ch.get("name", "") or "",
                "guild_id": str(ch.get("guild_id", "") or ""),
            }

    def _send_identify(self, ws):
        ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": self.cfg.token,
                "intents": DEFAULT_INTENTS,
                "properties": {"$os": "linux", "$browser": "ping-me-when", "$device": "ping-me-when"},
            },
        }))

    def _start_heartbeat(self, ws):
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        def beat():
            interval = self._heartbeat_interval_ms / 1000.0
            while not self._stop.is_set() and self.status.connected:
                try:
                    ws.send(json.dumps({"op": 1, "d": self._last_seq}))
                except Exception:
                    return
                time.sleep(interval)
        self._heartbeat_thread = threading.Thread(target=beat, daemon=True)
        self._heartbeat_thread.start()

    def _handle_message(self, msg: dict) -> None:
        channel_id = str(msg.get("channel_id", ""))
        author = msg.get("author", {}) or {}
        author_name = (author.get("username") or "").lower()
        if not channel_id or not author_name:
            return

        meta = self._channel_meta.get(channel_id, {})
        for sub in self.cfg.subscriptions:
            if sub.channel_id != channel_id:
                continue
            allowed = {u.lower() for u in (sub.usernames or []) if u}
            if author_name not in allowed:
                continue
            hit = Hit(
                sub=sub,
                author=author.get("username", ""),
                content=msg.get("content", "") or "",
                message_id=str(msg.get("id", "")),
                channel_id=channel_id,
                timestamp=msg.get("timestamp", ""),
                channel_name=meta.get("name", ""),
                guild_id=meta.get("guild_id", ""),
            )
            self.status.last_hit = hit
            self.status.hits.append(hit)
            if len(self.status.hits) > self.MAX_HISTORY:
                self.status.hits = self.status.hits[-self.MAX_HISTORY:]
            try:
                self.on_hit(hit)
            except Exception as e:
                self.status.last_error = f"on_hit: {e}"
            break  # one match per message is enough
