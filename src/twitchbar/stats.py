"""Session bookkeeping: counters, the last few messages, who is in chat, and what deserves a ping.

Pure Python with no threads and no SDK: feed it events, get back alerts and menu text.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from twitchbar import links
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
    tier_label,
)
from twitchbar.tray.base import MenuLine

KIND_MESSAGE = "message"
KIND_FOLLOW = "follow"
KIND_SUB = "sub"
KIND_RAID = "raid"
KIND_CHEER = "cheer"
KIND_JOIN = "join"
KIND_ONLINE = "online"
KIND_OFFLINE = "offline"
ALERT_KINDS = (
    KIND_MESSAGE,
    KIND_FOLLOW,
    KIND_SUB,
    KIND_RAID,
    KIND_CHEER,
    KIND_JOIN,
    KIND_ONLINE,
    KIND_OFFLINE,
)

STATE_CONNECTING = "connecting"
STATE_AUTHORIZING = "authorizing"
STATE_CONNECTED = "connected"
STATE_ERROR = "error"


@dataclass(frozen=True, slots=True)
class Alert:
    """One thing worth a notification: kind (picks the sound), title, body and a page to open."""

    kind: str
    title: str
    body: str
    url: str | None = None


def shorten(text: str, limit: int) -> str:
    """Collapse whitespace and cut ``text`` to ``limit`` characters with an ellipsis."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: max(limit - 1, 1)] + "…"


def format_duration(delta: timedelta) -> str:
    """Render an uptime like ``1h 05m`` or ``12m``."""
    minutes = int(delta.total_seconds()) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def _person(user: str | None, login: str) -> str | None:
    """The channel page of the person behind an alert, or None for anonymous ones."""
    return links.channel(links.login_of(user, login)) if user else None


class SessionStats:
    """Everything the tray shows, updated one event at a time.

    ``apply`` returns the alerts an event deserves. Counters reset when the
    stream goes live, so the numbers always mean "this stream".
    """

    def __init__(
        self,
        *,
        recent_size: int = 10,
        ignore_users: Iterable[str] = (),
        notify_own_messages: bool = False,
        notify_joins: bool = True,
        join_cooldown: timedelta = timedelta(minutes=10),
    ) -> None:
        self._ignored = {user.lower() for user in ignore_users}
        self._join_cooldown = join_cooldown
        self._last_seen: dict[str, datetime] = {}  # login -> when they were last in chat
        self._notify_own = notify_own_messages
        self._notify_joins = notify_joins
        self.state = STATE_CONNECTING
        self.state_detail = ""
        self.login = ""
        self.live = False
        self.viewers: int | None = None
        self.stream_title = ""
        self.game = ""
        self.started_at: datetime | None = None
        self.messages = 0
        self.unread = 0  # messages since the menu was last opened; the number in the bar
        self.followers = 0
        self.subs = 0
        self.raids = 0
        self.bits = 0
        self.recent: deque[ChatMessage] = deque(maxlen=recent_size)
        self.chatters: dict[str, str] = {}  # login -> display name
        self._chatters_seeded = False

    # -- events -------------------------------------------------------------

    def apply(self, event: Event) -> list[Alert]:
        """Fold one event into the session and return the alerts it earned."""
        match event:
            case SourceState(status=status, detail=detail):
                self.state, self.state_detail = status, detail
                if status == STATE_CONNECTED and detail:
                    self.login = detail
                return []
            case StreamStatus():
                return self._apply_status(event)
            case StreamOnline(started_at=started_at):
                return self._go_live(started_at)
            case StreamOffline():
                return self._go_offline()
            case ChatMessage():
                return self._apply_message(event)
            case Follow(user=user, login=login):
                self.followers += 1
                return [Alert(KIND_FOLLOW, "❤️ New follower", user, _person(user, login))]
            case Subscribe(user=user, tier=tier, is_gift=is_gift, login=login):
                self.subs += 1
                suffix = " · gifted" if is_gift else ""
                body = f"{user} · {tier_label(tier)}{suffix}"
                return [Alert(KIND_SUB, "⭐ New sub", body, _person(user, login))]
            case Resub(user=user, tier=tier, months=months, text=text, login=login):
                self.subs += 1
                body = f"{user} · {tier_label(tier)} · {months} months"
                body = f"{body}: {shorten(text, 160)}" if text else body
                return [Alert(KIND_SUB, "⭐ Resub", body, _person(user, login))]
            case GiftSubs(user=user, total=total, tier=tier, login=login):
                self.subs += total
                who = user or "Anonymous"
                noun = "sub" if total == 1 else "subs"
                body = f"{who} gifted {total} {noun} · {tier_label(tier)}"
                return [Alert(KIND_SUB, "🎁 Gifted subs", body, _person(user, login))]
            case Raid(user=user, viewers=viewers, login=login):
                self.raids += 1
                noun = "viewer" if viewers == 1 else "viewers"
                body = f"{user} brought {viewers} {noun}"
                return [Alert(KIND_RAID, "🚀 Raid", body, _person(user, login))]
            case Cheer(user=user, bits=bits, text=text, login=login):
                self.bits += bits
                who = user or "Anonymous"
                body = f"{who}: {shorten(text, 160)}" if text else who
                return [Alert(KIND_CHEER, f"💎 {bits} bits", body, _person(user, login))]
            case Chatters(users=users):
                return self._apply_chatters(users)
        return []

    def _apply_status(self, status: StreamStatus) -> list[Alert]:
        alerts: list[Alert] = []
        if status.live:
            alerts = self._go_live(status.started_at or datetime.now(UTC))
            self.viewers = status.viewers
            self.stream_title = status.title
            self.game = status.game
        else:
            alerts = self._go_offline()
        return alerts

    def _go_live(self, started_at: datetime) -> list[Alert]:
        if self.live:
            return []
        self.live = True
        self.started_at = started_at
        self.viewers = None
        self.messages = self.unread = self.followers = self.subs = self.raids = self.bits = 0
        self.recent.clear()
        return [
            Alert(
                KIND_ONLINE,
                "🟢 Live",
                "Stream is up, the session counters start now",
                self._own_channel(),
            )
        ]

    def _go_offline(self) -> list[Alert]:
        if not self.live:
            return []
        self.live = False
        self.viewers = None
        return [Alert(KIND_OFFLINE, "⚫ Offline", self.session_summary(), self._own_channel())]

    def _apply_message(self, message: ChatMessage) -> list[Alert]:
        if self._is_ignored(message.user):
            return []
        self.messages += 1
        self.recent.append(message)
        if message.is_self:
            if not self._notify_own:
                return []
        else:
            self.unread += 1
        body = shorten(message.text, 240)
        return [Alert(KIND_MESSAGE, f"💬 {message.user}", body, self._own_chat())]

    def _apply_chatters(
        self, users: tuple[Chatter, ...], now: datetime | None = None
    ) -> list[Alert]:
        now = now or datetime.now(UTC)
        current = {links.login_of(c.name, c.login): c.name for c in users}
        joined = sorted((login for login in current if login not in self.chatters), key=str.lower)
        # A viewer whose connection flaps drops out of the list and comes back a minute later;
        # that is not a new arrival, so a join only counts after ``join_cooldown`` of absence.
        fresh = [
            login
            for login in joined
            if login != self.login.lower()
            and not self._is_ignored(current[login])
            and now - self._last_seen.get(login, datetime.min.replace(tzinfo=UTC))
            > self._join_cooldown
        ]
        for login in self.chatters:
            self._last_seen[login] = now
        self.chatters = current
        if not self._chatters_seeded:
            self._chatters_seeded = True
            return []
        if not self._notify_joins:
            return []
        return [
            Alert(KIND_JOIN, "👋 Joined chat", current[login], links.channel(login))
            for login in fresh
        ]

    def _is_ignored(self, user: str) -> bool:
        return user.lower() in self._ignored

    # -- presentation ---------------------------------------------------------

    def mark_seen(self) -> None:
        """The user opened the menu: the unread count in the bar starts over."""
        self.unread = 0

    def uptime(self, now: datetime | None = None) -> timedelta | None:
        """How long the stream has been live, or None when offline."""
        if not self.live or self.started_at is None:
            return None
        return (now or datetime.now(UTC)) - self.started_at

    def badge(self) -> str:
        """The shortest status: the viewer count, a dash when offline, an ellipsis while unknown."""
        if self.state != STATE_CONNECTED:
            return "…"
        if not self.live:
            return "–"
        return "…" if self.viewers is None else str(self.viewers)

    def tray_title(self) -> str:
        """The text shown in the menu bar: viewers, unread messages, followers this stream."""
        if self.state == STATE_AUTHORIZING:
            return "🔑 login"
        if self.state == STATE_CONNECTING:
            return "⏳"
        if self.state == STATE_ERROR:
            return "⚠️ twitchbar"
        eye = f"👁 {self.badge()}" if self.live else "⏸"
        return f"{eye} · 💬 {self.unread} · ❤ {self.followers}"

    def summary_lines(self, now: datetime | None = None) -> tuple[MenuLine, ...]:
        """The block at the top of the menu: stream, uptime, chat size, session counters.

        The live line opens the channel, the chat line opens the chat popout, the counters open
        the stream manager.
        """
        lines: list[MenuLine] = []
        if self.state == STATE_AUTHORIZING:
            lines.append(MenuLine("🔑 Waiting for you to authorize in the browser"))
        elif self.state == STATE_CONNECTING:
            lines.append(MenuLine("⏳ Connecting to Twitch"))
        elif self.state == STATE_ERROR:
            lines.append(
                MenuLine(f"⚠️ {shorten(self.state_detail, 70) or 'Connection failed, see the log'}")
            )
        if self.live:
            uptime = self.uptime(now)
            viewers = "…" if self.viewers is None else str(self.viewers)
            noun = "viewer" if self.viewers == 1 else "viewers"
            up = f" · {format_duration(uptime)}" if uptime is not None else ""
            lines.append(MenuLine(f"🟢 Live{up} · {viewers} {noun}", self._own_channel()))
            headline = " — ".join(part for part in (self.game, self.stream_title) if part)
            if headline:
                lines.append(MenuLine(shorten(headline, 70), self._own_dashboard()))
        elif self.state == STATE_CONNECTED:
            lines.append(MenuLine("⚫ Offline", self._own_channel()))
        lines.append(MenuLine(f"In chat: {len(self.chatters)}", self._own_chat()))
        counters = f"Messages: {self.messages} · Followers: {self.followers} · Subs: {self.subs}"
        lines.append(MenuLine(counters, self._own_dashboard()))
        lines.append(MenuLine(f"Raids: {self.raids} · Bits: {self.bits}", self._own_dashboard()))
        return tuple(lines)

    def recent_lines(self) -> tuple[MenuLine, ...]:
        """The last messages, newest first; each opens the chat popout."""
        chat = self._own_chat()
        return tuple(
            MenuLine(f"{m.user}: {shorten(m.text, 80)}", chat) for m in reversed(self.recent)
        )

    def chatter_lines(self) -> tuple[MenuLine, ...]:
        """Everyone currently in chat, alphabetically; each opens that person's channel."""
        return tuple(
            MenuLine(name, links.channel(login))
            for login, name in sorted(self.chatters.items(), key=lambda item: item[1].lower())
        )

    def _own_channel(self) -> str | None:
        return links.channel(self.login) if self.login else None

    def _own_chat(self) -> str | None:
        return links.chat_popout(self.login) if self.login else None

    def _own_dashboard(self) -> str | None:
        return links.stream_manager(self.login) if self.login else None

    def session_summary(self) -> str:
        """One line with the session counters, used when the stream ends."""
        return (
            f"{self.messages} messages · {self.followers} followers · "
            f"{self.subs} subs · {self.raids} raids · {self.bits} bits"
        )
