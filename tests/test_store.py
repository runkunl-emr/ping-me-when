"""Round-trip the config through disk and verify nothing changes."""
from pathlib import Path

from src import store


def test_save_load_empty(tmp_path: Path):
    cfg = store.Config()
    p = tmp_path / "config.json"
    store.save(cfg, p)
    loaded = store.load(p)
    assert loaded.token == ""
    assert loaded.subscriptions == []
    assert loaded.notify.mac is True
    assert loaded.notify.webhook_url == ""


def test_save_load_with_subs(tmp_path: Path):
    cfg = store.Config(
        token="t-123",
        subscriptions=[store.Subscription(channel_id="c1", usernames=["alice", "bob"], label="A")],
        notify=store.Notify(mac=False, webhook_url="https://x"),
    )
    p = tmp_path / "config.json"
    store.save(cfg, p)
    loaded = store.load(p)
    assert loaded.token == "t-123"
    assert len(loaded.subscriptions) == 1
    assert loaded.subscriptions[0].usernames == ["alice", "bob"]
    assert loaded.notify.mac is False
    assert loaded.notify.webhook_url == "https://x"


def test_legacy_config_with_singular_username_migrates(tmp_path: Path):
    """A config.json from an old version (with `username`, no `usernames`) must still load."""
    p = tmp_path / "config.json"
    p.write_text('{"token":"t","subscriptions":[{"channel_id":"c1","username":"alice","label":"A"}],"notify":{"mac":true,"webhook_url":""}}')
    loaded = store.load(p)
    assert loaded.subscriptions[0].usernames == ["alice"]


def test_config_file_permissions_are_owner_only(tmp_path: Path):
    import os, stat
    p = tmp_path / "config.json"
    store.save(store.Config(token="secret"), p)
    mode = stat.S_IMODE(os.stat(p).st_mode)
    # 0o600 = owner read/write only. World-readable token would be a leak.
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_load_missing_file(tmp_path: Path):
    p = tmp_path / "does-not-exist.json"
    cfg = store.load(p)
    assert cfg.token == ""
