import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa only")


def test_terminal_notifier_command_carries_the_link() -> None:
    from twitchbar.notify_mac import terminal_notifier_command

    assert terminal_notifier_command("/opt/tn", "💬 alice", "hi", "https://x") == [
        "/opt/tn",
        "-title",
        "💬 alice",
        "-message",
        "hi",
        "-group",
        "twitchbar",
        "-open",
        "https://x",
    ]
    assert terminal_notifier_command("/opt/tn", "t", "b", None)[-2:] == ["-group", "twitchbar"]


def test_banner_goes_through_terminal_notifier_when_present() -> None:
    from twitchbar.notify_mac import MacNotifier

    spawned: list[list[str]] = []
    notifier = MacNotifier(terminal_notifier="/opt/tn", spawn=lambda c: spawned.append(list(c)))
    notifier.notify("t", "b", None, "https://x")
    assert spawned == [
        ["/opt/tn", "-title", "t", "-message", "b", "-group", "twitchbar", "-open", "https://x"]
    ]
