"""Two notification channels: macOS desktop notifications + Discord webhook."""
from __future__ import annotations
import json
import platform
import subprocess
import urllib.request
from typing import Optional


def _sanitize(s: str, max_len: int = 500) -> str:
    """Strip control characters that could break downstream consumers.

    - Null bytes break Python's subprocess (and most C-level APIs).
    - Other control chars like backspace / VT can interfere with AppleScript /
      terminal display.
    - Truncate to `max_len` so we don't get an unbounded title/body.

    Whitelist: keep printable text + tab + newline + everything Unicode >= 0x20.
    """
    if not s:
        return ""
    out = []
    for ch in s:
        cp = ord(ch)
        if cp == 0x09 or cp == 0x0A or cp >= 0x20:  # tab, LF, or printable
            out.append(ch)
        # else: drop (\x00..\x08, \x0B..\x1F)
    cleaned = "".join(out).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1] + "…"
    return cleaned


def _ascript_str(s: str) -> str:
    """Quote a string for embedding inside an AppleScript literal.

    AppleScript needs `"..."` even for simple words. Inside, escape `\\` and `"`.
    Caller is responsible for sanitizing control chars first via _sanitize.
    """
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def mac_notify(title: str, message: str, sound: str = "Submarine",
               open_url: Optional[str] = None) -> bool:
    """Send a macOS notification.

    Prefer terminal-notifier when present (it shows a richer notification that
    stays in Notification Center, AND supports click-to-open via `-open <url>`).
    Fall back to osascript display notification (no click action).
    """
    if platform.system() != "Darwin":
        return False

    tn = subprocess.run(["which", "terminal-notifier"], capture_output=True, text=True)
    if tn.returncode == 0:
        try:
            cmd = ["terminal-notifier", "-title", title, "-message", message,
                   "-sound", sound, "-group", "ping-me-when"]
            if open_url:
                cmd += ["-open", open_url]
            subprocess.run(cmd, check=True, timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"[notify/mac/terminal-notifier] failed: {e}")
            # fall through to osascript

    # Path 2: AppleScript via osascript (built in, no install needed).
    # AppleScript requires `"..."` literals for every string argument, including
    # the sound name. shlex.quote is the wrong tool here — it omits quotes for
    # bare words. Use _ascript_str to always emit `"foo"`.
    script = (
        f"display notification {_ascript_str(message)} "
        f"with title {_ascript_str(title)} "
        f"sound name {_ascript_str(sound)}"
    )
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"[notify/mac/osascript] failed: {e}")
        return False


def webhook_send(url: str, content: str) -> bool:
    """POST to a Discord webhook (or compatible endpoint that accepts {"content": ...})."""
    if not url:
        return False
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"content": content[:1900]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        return True
    except Exception as e:
        print(f"[notify/webhook] failed: {e}")
        return False


def dispatch(*, title: str, message: str,
             mac: bool = True, webhook_url: Optional[str] = None,
             open_url: Optional[str] = None) -> dict:
    """Send notification through every enabled channel.

    Both `title` and `message` are sanitized centrally here so that every
    downstream channel (subprocess argv, AppleScript literal, JSON, etc.)
    sees only safe printable characters.

    `open_url`, if set, makes a macOS notification clickable (only via
    terminal-notifier — falls back gracefully when not installed).
    """
    title = _sanitize(title, max_len=200)
    message = _sanitize(message, max_len=500)
    results = {}
    if mac:
        results["mac"] = mac_notify(title, message, open_url=open_url)
    if webhook_url:
        # Append the jump link into the webhook so users can click through.
        body = f"**{title}**\n{message}"
        if open_url:
            body += f"\n{open_url}"
        results["webhook"] = webhook_send(webhook_url, body)
    return results
