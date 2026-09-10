"""Twitch sign-in: a user token with the scopes twitchbar needs.

The token is cached on disk and refreshed silently; the browser opens only when there is none.
"""

from __future__ import annotations

import logging
from pathlib import Path

from twitchAPI.oauth import UserAuthenticationStorageHelper, UserAuthenticator
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope

from twitchbar.config import Config

log = logging.getLogger(__name__)

SCOPES = [
    AuthScope.USER_READ_CHAT,  # channel.chat.message
    AuthScope.MODERATOR_READ_FOLLOWERS,  # channel.follow
    AuthScope.MODERATOR_READ_CHATTERS,  # Get Chatters (who is in chat)
    AuthScope.CHANNEL_READ_SUBSCRIPTIONS,  # channel.subscribe & friends
    AuthScope.BITS_READ,  # channel.cheer
]
REDIRECT_PORT = 17563


async def connect(config: Config, token_file: Path) -> Twitch:
    """Return an authenticated client, opening the browser once if no valid token is stored."""
    twitch = await Twitch(config.client_id, config.client_secret)
    helper = UserAuthenticationStorageHelper(
        twitch, SCOPES, storage_path=token_file, auth_generator_func=_authorize_in_browser
    )
    await helper.bind()  # type: ignore[no-untyped-call]
    return twitch  # type: ignore[no-any-return]


async def _authorize_in_browser(twitch: Twitch, scopes: list[AuthScope]) -> tuple[str, str]:
    log.info("no valid token stored, opening the browser for Twitch authorization")
    authenticator = UserAuthenticator(twitch, scopes, host="127.0.0.1", port=REDIRECT_PORT)
    result = await authenticator.authenticate()
    if result is None:
        raise RuntimeError("Twitch authorization was cancelled")
    return result  # type: ignore[no-any-return]
