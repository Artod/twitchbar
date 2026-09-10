from collections.abc import Sequence

from twitchbar.notify import CallbackNotifier, LogNotifier, NotifySendNotifier, default_notifier


def test_notify_send_command() -> None:
    calls: list[Sequence[str]] = []
    NotifySendNotifier(runner=calls.append).notify("💬 alice", "hi", "Pop", "https://x")
    assert calls == [["notify-send", "--app-name=twitchbar", "💬 alice", "hi"]]


def test_callback_notifier_beeps_only_with_a_sound() -> None:
    shown: list[tuple[str, str]] = []
    beeps: list[int] = []
    notifier = CallbackNotifier(lambda t, b: shown.append((t, b)), beep=lambda: beeps.append(1))
    notifier.notify("t", "b", "Pop")
    notifier.notify("t2", "b2", None)
    assert shown == [("t", "b"), ("t2", "b2")]
    assert beeps == [1]


def test_default_notifier_falls_back_off_mac() -> None:
    fallback = LogNotifier()
    assert default_notifier("win32", fallback) is fallback
    assert isinstance(default_notifier("win32"), LogNotifier)
