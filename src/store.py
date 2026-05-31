"""Local JSON config store. Single file, atomic writes."""
from __future__ import annotations
import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


CONFIG_PATH = Path(os.environ.get("PING_ME_CONFIG", "config.json"))


@dataclass
class Subscription:
    channel_id: str
    # Comma-or-space-separated list of Discord usernames to match.
    # Stored as a list internally; case-insensitive when matched.
    usernames: list[str] = field(default_factory=list)
    label: str = ""  # user-facing reminder text, e.g. "Alice's market calls"

    @classmethod
    def _from_legacy(cls, data: dict) -> "Subscription":
        """Migrate old single-`username` field to `usernames`."""
        if "username" in data and "usernames" not in data:
            data = dict(data)
            u = data.pop("username")
            data["usernames"] = [u] if u else []
        return cls(**data)


@dataclass
class Notify:
    mac: bool = True
    webhook_url: str = ""  # if set, also POST {"content": "..."} to this URL


@dataclass
class Config:
    token: str = ""
    subscriptions: list[Subscription] = field(default_factory=list)
    notify: Notify = field(default_factory=Notify)

    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "subscriptions": [asdict(s) for s in self.subscriptions],
            "notify": asdict(self.notify),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        return cls(
            token=data.get("token", ""),
            subscriptions=[Subscription._from_legacy(s) for s in data.get("subscriptions", [])],
            notify=Notify(**data.get("notify", {})),
        )


def load(path: Optional[Path] = None) -> Config:
    p = path or CONFIG_PATH
    if not p.exists():
        return Config()
    return Config.from_dict(json.loads(p.read_text(encoding="utf-8")))


def save(cfg: Config, path: Optional[Path] = None) -> None:
    p = path or CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: temp file + rename, so a crash mid-write can't corrupt.
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".config-", suffix=".tmp")
    try:
        # File contains the Discord token — restrict to owner read/write only.
        os.chmod(tmp, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg.to_dict(), f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
