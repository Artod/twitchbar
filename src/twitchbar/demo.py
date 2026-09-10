"""A scripted stream: see the tray and hear the sounds without a Twitch account (``--demo``)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from twitchbar.events import (
    ChatMessage,
    Chatter,
    Chatters,
    Cheer,
    Event,
    Follow,
    Raid,
    Resub,
    SourceState,
    StreamOffline,
    StreamOnline,
    StreamStatus,
    Subscribe,
)
from twitchbar.stats import STATE_AUTHORIZING, STATE_CONNECTED, STATE_CONNECTING

Sink = Callable[[Event], None]


def script(now: datetime) -> list[tuple[float, Event]]:
    """The demo timeline as (seconds to wait before, event) pairs."""
    live = StreamStatus(
        live=True,
        viewers=3,
        title="Building a desk robot live",
        game="Software and Game Development",
        started_at=now,
    )
    return [
        (0.0, SourceState(STATE_CONNECTING)),
        (0.8, SourceState(STATE_AUTHORIZING)),
        (1.2, SourceState(STATE_CONNECTED, "demo_streamer")),
        (0.5, StreamOnline(now)),
        (0.3, live),
        (0.5, Chatters((Chatter("alice"), Chatter("bob"), Chatter("Nightbot")))),
        (3.0, ChatMessage("alice", "hi! what are you working on today?")),
        (4.0, Follow("bob")),
        (3.0, Chatters((Chatter("alice"), Chatter("bob"), Chatter("Nightbot"), Chatter("carol")))),
        (2.0, ChatMessage("carol", "first time here, this looks cool")),
        (4.0, Subscribe("alice", "1000")),
        (4.0, Cheer("bob", 100, "take my bits")),
        (5.0, Raid("friendly_streamer", 12)),
        (
            1.0,
            StreamStatus(live=True, viewers=15, title=live.title, game=live.game, started_at=now),
        ),
        (3.0, ChatMessage("dave", "raid squad reporting in 🎉")),
        (3.0, Resub("carol", "1000", 3, "three months already")),
        (6.0, ChatMessage("alice", "ok I need to go, see you next stream")),
        (4.0, StreamStatus(live=True, viewers=9, title=live.title, game=live.game, started_at=now)),
        (8.0, StreamOffline()),
    ]


class DemoSource:
    """Plays ``script`` once, on a background thread, then stays quiet."""

    def __init__(self, sink: Sink, *, speed: float = 1.0) -> None:
        self._sink = sink
        self._speed = speed
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="demo-source", daemon=True)

    def start(self) -> None:
        """Start playing the script; returns immediately."""
        self._thread.start()

    def stop(self) -> None:
        """Stop between two steps."""
        self._stop.set()

    def _run(self) -> None:
        for delay, event in script(datetime.now(UTC)):
            if self._stop.wait(delay / self._speed):
                return
            if isinstance(event, ChatMessage):  # stamp at send time so the latency log stays honest
                event = replace(event, sent_at=datetime.now(UTC))
            self._sink(event)
