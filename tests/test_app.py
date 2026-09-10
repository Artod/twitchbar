from collections.abc import Callable

from twitchbar.app import App
from twitchbar.config import Config
from twitchbar.events import ChatMessage, Event, Follow, SourceState
from twitchbar.stats import STATE_CONNECTED, SessionStats
from twitchbar.tray.base import MenuLine, TrayView


class FakeTray:
    def __init__(self) -> None:
        self.views: list[TrayView] = []
        self.stopped = False

    def run(self, tick: Callable[[], None], interval: float) -> None:
        tick()

    def render(self, view: TrayView) -> None:
        self.views.append(view)

    def stop(self) -> None:
        self.stopped = True


class FakeNotifier:
    def __init__(self) -> None:
        self.shown: list[tuple[str, str, str | None, str | None]] = []

    def notify(
        self, title: str, body: str, sound: str | None = None, url: str | None = None
    ) -> None:
        self.shown.append((title, body, sound, url))


class FakeSource:
    def __init__(self, sink: Callable[[Event], None]) -> None:
        self.sink = sink
        self.started = self.stopped = False

    def start(self) -> None:
        self.started = True
        self.sink(SourceState(STATE_CONNECTED, "me"))
        self.sink(ChatMessage("alice", "hello"))
        self.sink(Follow("bob"))

    def stop(self) -> None:
        self.stopped = True


def build(quiet: bool = False) -> tuple[App, FakeTray, FakeNotifier, list[FakeSource]]:
    tray, notifier, sources = FakeTray(), FakeNotifier(), []
    opened: list[str] = []

    def make_source(sink: Callable[[Event], None]) -> FakeSource:
        sources.append(FakeSource(sink))
        return sources[-1]

    app = App(
        config=Config(),
        stats=SessionStats(),
        tray=tray,
        notifier=notifier,
        make_source=make_source,
        quiet=quiet,
        opener=opened.append,
    )
    app.opened = opened  # type: ignore[attr-defined]
    return app, tray, notifier, sources


def test_events_become_banners_with_configured_sounds() -> None:
    app, tray, notifier, sources = build()
    app.run()
    assert sources[0].started and sources[0].stopped
    assert notifier.shown == [
        ("💬 alice", "hello", "Pop", "https://www.twitch.tv/popout/me/chat"),
        ("❤️ New follower", "bob", "Hero", "https://www.twitch.tv/bob"),
    ]
    assert tray.views[-1].title == "⏸ · 💬 1 · ❤ 1"
    assert tray.views[-1].recent == (
        MenuLine("alice: hello", "https://www.twitch.tv/popout/me/chat"),
    )


def test_link_actions_use_the_signed_in_login() -> None:
    app, _, _, _ = build()
    app.open_channel()
    app.run()
    app.open_channel()
    app.open_chat()
    app.open_dashboard()
    app.open_url("https://example.org")
    assert app.opened == [  # type: ignore[attr-defined]
        "https://dashboard.twitch.tv/stream-manager",
        "https://www.twitch.tv/me",
        "https://www.twitch.tv/popout/me/chat",
        "https://dashboard.twitch.tv/u/me/stream-manager",
        "https://example.org",
    ]


def test_quiet_mode_keeps_stats_but_silences_banners() -> None:
    app, tray, notifier, _ = build(quiet=True)
    app.run()
    assert notifier.shown == []
    assert tray.views[-1].quiet is True
    assert tray.views[-1].title == "⏸ · 💬 1 · ❤ 1"
    app.toggle_quiet()
    assert app.quiet is False and tray.views[-1].quiet is False


def test_quit_stops_source_and_tray() -> None:
    app, tray, _, sources = build()
    app.quit()
    assert sources[0].stopped and tray.stopped
