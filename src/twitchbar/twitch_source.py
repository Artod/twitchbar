"""The live event source: EventSub over WebSocket for pushes, Helix polling for the rest.

Runs on its own thread with its own asyncio loop and hands every event to a
thread-safe ``sink``; the UI thread never blocks on the network.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path

from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import (
    ChannelChatMessageEvent,
    ChannelCheerEvent,
    ChannelFollowEvent,
    ChannelRaidEvent,
    ChannelSubscribeEvent,
    ChannelSubscriptionGiftEvent,
    ChannelSubscriptionMessageEvent,
    StreamOfflineEvent,
    StreamOnlineEvent,
)
from twitchAPI.twitch import Twitch

from twitchbar.auth import connect
from twitchbar.config import Config
from twitchbar.events import (
    ChatMessage,
    Chatter,
    Chatters,
    Cheer,
    Event,
    Follow,
    GiftSubs,
    Raid,
    Resub,
    SourceState,
    StreamOffline,
    StreamOnline,
    StreamStatus,
    Subscribe,
)
from twitchbar.stats import STATE_AUTHORIZING, STATE_CONNECTED, STATE_ERROR

log = logging.getLogger(__name__)

Sink = Callable[[Event], None]
MAX_CHATTERS_PAGE = 1000


class TwitchSource:
    """Connects to the broadcaster's own channel and streams its events into ``sink``."""

    def __init__(self, config: Config, token_file: Path, sink: Sink) -> None:
        self._config = config
        self._token_file = token_file
        self._sink = sink
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._me_id = ""
        self._thread = threading.Thread(target=self._thread_main, name="twitch-source", daemon=True)

    def start(self) -> None:
        """Start the background thread; returns immediately."""
        self._thread.start()

    def stop(self) -> None:
        """Ask the background loop to shut down cleanly."""
        if self._loop is not None and self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    # -- background thread ----------------------------------------------------

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as error:
            log.exception("twitch source stopped: %s", error)
            self._sink(SourceState(STATE_ERROR, str(error)))

    async def _run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        self._sink(SourceState(STATE_AUTHORIZING))
        twitch = await connect(self._config, self._token_file)
        try:
            me = await anext(twitch.get_users())
            self._me_id = me.id
            log.info("signed in as %s (%s)", me.display_name, me.id)
            self._sink(SourceState(STATE_CONNECTED, me.login))
            eventsub = EventSubWebsocket(twitch)
            eventsub.start()  # type: ignore[no-untyped-call]
            try:
                await self._subscribe(eventsub)
                while not self._stop_event.is_set():
                    await self._poll(twitch)
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(self._stop_event.wait(), self._config.poll_seconds)
            finally:
                await eventsub.stop()  # type: ignore[no-untyped-call]
        finally:
            await twitch.close()  # type: ignore[no-untyped-call]

    async def _subscribe(self, eventsub: EventSubWebsocket) -> None:
        me = self._me_id
        subscriptions: list[tuple[str, Callable[[], Awaitable[str]]]] = [
            ("chat messages", lambda: eventsub.listen_channel_chat_message(me, me, self._on_chat)),
            ("follows", lambda: eventsub.listen_channel_follow_v2(me, me, self._on_follow)),
            ("subs", lambda: eventsub.listen_channel_subscribe(me, self._on_subscribe)),
            ("resubs", lambda: eventsub.listen_channel_subscription_message(me, self._on_resub)),
            ("gift subs", lambda: eventsub.listen_channel_subscription_gift(me, self._on_gift)),
            (
                "raids",
                lambda: eventsub.listen_channel_raid(self._on_raid, to_broadcaster_user_id=me),
            ),
            ("cheers", lambda: eventsub.listen_channel_cheer(me, self._on_cheer)),
            ("stream online", lambda: eventsub.listen_stream_online(me, self._on_online)),
            ("stream offline", lambda: eventsub.listen_stream_offline(me, self._on_offline)),
        ]
        for name, subscribe in subscriptions:
            try:
                await subscribe()
                log.info("subscribed to %s", name)
            except Exception as error:
                log.warning("could not subscribe to %s: %s", name, error)

    async def _poll(self, twitch: Twitch) -> None:
        try:
            stream = await anext(twitch.get_streams(user_id=[self._me_id], first=1), None)
            if stream is None:
                self._sink(StreamStatus(live=False))
            else:
                self._sink(
                    StreamStatus(
                        live=True,
                        viewers=stream.viewer_count,
                        title=stream.title,
                        game=stream.game_name,
                        started_at=stream.started_at,
                    )
                )
        except Exception as error:
            log.warning("stream poll failed: %s", error)
        try:
            response = await twitch.get_chatters(self._me_id, self._me_id, first=MAX_CHATTERS_PAGE)
            self._sink(Chatters(tuple(Chatter(c.user_name, c.user_login) for c in response.data)))
        except Exception as error:
            log.warning("chatters poll failed: %s", error)

    # -- EventSub callbacks ---------------------------------------------------

    async def _on_chat(self, event: ChannelChatMessageEvent) -> None:
        data = event.event
        self._sink(
            ChatMessage(
                user=data.chatter_user_name,
                text=data.message.text,
                is_self=data.chatter_user_id == self._me_id,
                sent_at=event.metadata.message_timestamp,
                login=data.chatter_user_login,
            )
        )

    async def _on_follow(self, event: ChannelFollowEvent) -> None:
        self._sink(Follow(event.event.user_name, login=event.event.user_login))

    async def _on_subscribe(self, event: ChannelSubscribeEvent) -> None:
        data = event.event
        self._sink(Subscribe(data.user_name, data.tier, data.is_gift, login=data.user_login))

    async def _on_resub(self, event: ChannelSubscriptionMessageEvent) -> None:
        data = event.event
        months = data.cumulative_months or data.duration_months
        self._sink(
            Resub(data.user_name, data.tier, months, data.message.text, login=data.user_login)
        )

    async def _on_gift(self, event: ChannelSubscriptionGiftEvent) -> None:
        data = event.event
        user = None if data.is_anonymous else data.user_name
        self._sink(GiftSubs(user, data.total, data.tier, login=data.user_login or ""))

    async def _on_raid(self, event: ChannelRaidEvent) -> None:
        data = event.event
        self._sink(
            Raid(
                data.from_broadcaster_user_name,
                data.viewers,
                login=data.from_broadcaster_user_login,
            )
        )

    async def _on_cheer(self, event: ChannelCheerEvent) -> None:
        data = event.event
        user = None if data.is_anonymous else data.user_name
        self._sink(Cheer(user, data.bits, data.message, login=data.user_login or ""))

    async def _on_online(self, event: StreamOnlineEvent) -> None:
        self._sink(StreamOnline(event.event.started_at))

    async def _on_offline(self, event: StreamOfflineEvent) -> None:
        self._sink(StreamOffline())
