"""Channel events as plain data.

Every source (the live Twitch connection, the demo script) turns what it sees
into one of these; the tray and the notifier never touch the Twitch SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One chat line; ``is_self`` marks the broadcaster's own messages."""

    user: str
    text: str
    is_self: bool = False
    sent_at: datetime = field(default_factory=_now)
    login: str = ""


@dataclass(frozen=True, slots=True)
class Follow:
    """Somebody pressed Follow."""

    user: str
    login: str = ""


@dataclass(frozen=True, slots=True)
class Subscribe:
    """A new subscription, paid or received as a gift; ``tier`` is Twitch's "1000"/"2000"/"3000"."""

    user: str
    tier: str
    is_gift: bool = False
    login: str = ""


@dataclass(frozen=True, slots=True)
class Resub:
    """A subscriber announced their resub, usually with a message."""

    user: str
    tier: str
    months: int
    text: str = ""
    login: str = ""


@dataclass(frozen=True, slots=True)
class GiftSubs:
    """Somebody gifted ``total`` subs to the community; ``user`` is None when anonymous."""

    user: str | None
    total: int
    tier: str
    login: str = ""


@dataclass(frozen=True, slots=True)
class Raid:
    """Another channel sent its viewers over."""

    user: str
    viewers: int
    login: str = ""


@dataclass(frozen=True, slots=True)
class Cheer:
    """Bits were cheered; ``user`` is None when anonymous."""

    user: str | None
    bits: int
    text: str = ""
    login: str = ""


@dataclass(frozen=True, slots=True)
class StreamOnline:
    """The stream went live."""

    started_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class StreamOffline:
    """The stream ended."""


@dataclass(frozen=True, slots=True)
class StreamStatus:
    """A polled snapshot of the stream: live or not, and the viewer count when live."""

    live: bool
    viewers: int = 0
    title: str = ""
    game: str = ""
    started_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Chatter:
    """One account in chat: display name and login (they differ for localized names)."""

    name: str
    login: str = ""


@dataclass(frozen=True, slots=True)
class Chatters:
    """A polled snapshot of everyone connected to chat (logged-in viewers only)."""

    users: tuple[Chatter, ...]


@dataclass(frozen=True, slots=True)
class SourceState:
    """Connection progress of the event source: connecting, authorizing, connected or error."""

    status: str
    detail: str = ""


Event = (
    ChatMessage
    | Follow
    | Subscribe
    | Resub
    | GiftSubs
    | Raid
    | Cheer
    | StreamOnline
    | StreamOffline
    | StreamStatus
    | Chatters
    | SourceState
)


def tier_label(tier: str) -> str:
    """Turn Twitch's "1000"/"2000"/"3000" into "Tier 1"/"Tier 2"/"Tier 3"; other values pass."""
    return {"1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}.get(tier, tier or "Tier 1")
