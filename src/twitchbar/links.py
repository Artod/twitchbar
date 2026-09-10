"""The Twitch pages a click can open."""

from __future__ import annotations


def login_of(user: str, login: str = "") -> str:
    """The account login behind a display name, or the lower-cased name (equal for most users)."""
    return login or user.lower()


def channel(login: str) -> str:
    """A channel's public page."""
    return f"https://www.twitch.tv/{login}"


def chat_popout(login: str) -> str:
    """The chat of ``login`` in its own window, the fastest place to answer from."""
    return f"https://www.twitch.tv/popout/{login}/chat"


def stream_manager(login: str = "") -> str:
    """The creator dashboard's stream manager (activity feed, stream info, chat)."""
    return (
        f"https://dashboard.twitch.tv/u/{login}/stream-manager"
        if login
        else "https://dashboard.twitch.tv/stream-manager"
    )
