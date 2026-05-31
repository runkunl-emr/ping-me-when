"""Listener filtering logic — the part that decides which Discord messages
trigger a notification. Doesn't connect to a real socket."""
from src.listener import Listener
from src.store import Config, Subscription


def make_listener(subs):
    cfg = Config(token="t" * 40, subscriptions=subs)
    hits = []
    L = Listener(cfg, on_hit=lambda h: hits.append(h))
    return L, hits


def msg(channel_id="c1", author_name="alice", content="hi"):
    return {
        "id": "m1",
        "channel_id": channel_id,
        "author": {"username": author_name, "id": "u1"},
        "content": content,
        "timestamp": "2026-05-30T12:00:00",
    }


def test_match_channel_and_username():
    L, hits = make_listener([Subscription(channel_id="c1", usernames=["alice"], label="A")])
    L._handle_message(msg(channel_id="c1", author_name="alice"))
    assert len(hits) == 1
    assert hits[0].sub.label == "A"


def test_username_is_case_insensitive():
    L, hits = make_listener([Subscription(channel_id="c1", usernames=["Alice"])])
    L._handle_message(msg(author_name="alice"))
    assert len(hits) == 1


def test_multiple_usernames_in_same_sub():
    """A single subscription may list multiple users; any match fires."""
    L, hits = make_listener([Subscription(channel_id="c1", usernames=["alice", "bob", "carol"])])
    L._handle_message(msg(author_name="bob"))
    L._handle_message(msg(author_name="carol"))
    L._handle_message(msg(author_name="dan"))  # no match
    assert len(hits) == 2


def test_wrong_channel_no_match():
    L, hits = make_listener([Subscription(channel_id="c1", usernames=["alice"])])
    L._handle_message(msg(channel_id="c2", author_name="alice"))
    assert hits == []


def test_wrong_user_no_match():
    L, hits = make_listener([Subscription(channel_id="c1", usernames=["alice"])])
    L._handle_message(msg(author_name="bob"))
    assert hits == []


def test_history_capped():
    L, hits = make_listener([Subscription(channel_id="c1", usernames=["alice"])])
    L.MAX_HISTORY = 5
    for i in range(10):
        L._handle_message(msg(content=f"#{i}"))
    assert len(L.status.hits) == 5
    assert L.status.hits[-1].content == "#9"


def test_channel_meta_populates_from_guild_create():
    """Names + guild_id flow into hits when GUILD_CREATE is seen first."""
    L, hits = make_listener([Subscription(channel_id="c1", usernames=["alice"])])
    L._learn_channel_names({
        "id": "g42",
        "channels": [{"id": "c1", "name": "general"}, {"id": "c2", "name": "off-topic"}],
    })
    L._handle_message(msg())
    assert hits[0].channel_name == "general"
    assert hits[0].guild_id == "g42"
    url = hits[0].discord_url()
    assert url == "https://discord.com/channels/g42/c1/m1"


def test_legacy_username_field_migrates():
    """Old config with `username` (singular) should still load."""
    s = Subscription._from_legacy({"channel_id": "c1", "username": "alice", "label": "A"})
    assert s.usernames == ["alice"]
    assert s.label == "A"
