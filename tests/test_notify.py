"""Notification escaper + sanitizer.

These tests lock down the boundary where Discord-controlled message content
flows into AppleScript / subprocess argv. The actual osascript subprocess
is not exercised here.
"""
from src.notify import _ascript_str, _sanitize


def test_simple_word():
    # Bare words MUST get wrapped in double quotes — AppleScript requires it.
    assert _ascript_str("Submarine") == '"Submarine"'


def test_with_spaces():
    assert _ascript_str("hello world") == '"hello world"'


def test_with_internal_quotes():
    assert _ascript_str('say "hi"') == '"say \\"hi\\""'


def test_with_backslash():
    assert _ascript_str("a\\b") == '"a\\\\b"'


def test_unicode():
    assert _ascript_str("测试") == '"测试"'


# ---- _sanitize: defense vs Discord-controlled content ----

def test_sanitize_strips_null_byte():
    assert "\x00" not in _sanitize("hello\x00world")


def test_sanitize_strips_other_controls():
    # Vertical tab, form feed, BEL, etc. should all be removed.
    out = _sanitize("a\x07b\x0bc\x0cd\x1be")
    assert out == "abcde"


def test_sanitize_keeps_tab_and_newline():
    out = _sanitize("a\tb\nc")
    assert out == "a\tb\nc"


def test_sanitize_keeps_unicode_and_emoji():
    out = _sanitize("hi 你好 🎉")
    assert out == "hi 你好 🎉"


def test_sanitize_truncates_long():
    long_msg = "x" * 1000
    out = _sanitize(long_msg, max_len=100)
    assert len(out) == 100
    assert out.endswith("…")


def test_sanitize_apple_script_escape_attempts_become_inert():
    """Even if the user types AppleScript syntax, _ascript_str will escape it."""
    payloads = [
        '"; do shell script "echo PWNED"',
        '\\"; do shell script "rm -rf /"',
        'normal then\n"; tell application "Terminal" to do script "x"',
    ]
    for p in payloads:
        sanitized = _sanitize(p)
        quoted = _ascript_str(sanitized)
        # Must start and end with our outer ", and any internal " must be \"
        assert quoted.startswith('"') and quoted.endswith('"')
        # Re-parse the inside: every " inside must be preceded by \
        inner = quoted[1:-1]
        i = 0
        while i < len(inner):
            if inner[i] == '"':
                # bare " inside the literal is the escape leak we're checking against
                assert i > 0 and inner[i - 1] == "\\", f"unescaped quote in: {quoted}"
            i += 1

