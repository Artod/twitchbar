"""Where twitchbar keeps its settings, token and logs, and what the config file looks like."""

from __future__ import annotations

import contextlib
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w
from platformdirs import user_config_dir, user_log_dir

APP_NAME = "twitchbar"
ENV_CONFIG = "TWITCHBAR_CONFIG"
ENV_CLIENT_ID = "TWITCHBAR_CLIENT_ID"
ENV_CLIENT_SECRET = "TWITCHBAR_CLIENT_SECRET"

DEFAULT_SOUNDS: dict[str, str] = {
    "message": "Pop",
    "follow": "Hero",
    "sub": "Glass",
    "raid": "Funk",
    "cheer": "Purr",
    "join": "Tink",
    "online": "Ping",
    "offline": "Basso",
}
DEFAULT_IGNORED_USERS = (
    "nightbot",
    "streamelements",
    "streamlabs",
    "moobot",
    "fossabot",
    "wizebot",
)

_HEADER = """\
# twitchbar configuration. Edit and restart twitchbar to apply.
#
# client_id / client_secret  your Twitch application (https://dev.twitch.tv/console/apps)
# poll_seconds               how often the viewer count and the chatter list are refreshed
# recent_messages            how many messages the menu keeps
# notify_own_messages        ping on your own chat messages too
# notify_joins               ping when a logged-in viewer appears in chat
# ignore_users               bots and people you never want a ping for
# [sounds]                   macOS sound name per alert kind, or "" for silent
#                            (Basso Blow Bottle Frog Funk Glass Hero Morse Ping Pop Purr
#                            Sosumi Submarine Tink)
"""


@dataclass(slots=True)
class Config:
    """Everything the user can tune; only ``client_id`` and ``client_secret`` are required."""

    client_id: str = ""
    client_secret: str = ""
    poll_seconds: float = 30.0
    recent_messages: int = 10
    notify_own_messages: bool = False
    notify_joins: bool = True
    ignore_users: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORED_USERS))
    sounds: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SOUNDS))

    def is_complete(self) -> bool:
        """True once both Twitch credentials are present."""
        return bool(self.client_id and self.client_secret)


@dataclass(frozen=True, slots=True)
class Paths:
    """Where twitchbar writes: config, token, the single-instance lock, and logs."""

    config_file: Path
    token_file: Path
    lock_file: Path
    log_dir: Path

    @classmethod
    def default(cls) -> Paths:
        """Per-OS defaults (``~/Library/Application Support/twitchbar`` on macOS).

        ``TWITCHBAR_CONFIG`` overrides the config file; the token always sits next to it.
        """
        override = os.environ.get(ENV_CONFIG)
        config_file = (
            Path(override).expanduser()
            if override
            else Path(user_config_dir(APP_NAME)) / "config.toml"
        )
        return cls(
            config_file=config_file,
            token_file=config_file.with_name("token.json"),
            lock_file=config_file.with_name("twitchbar.lock"),
            log_dir=Path(user_log_dir(APP_NAME)),
        )


def load(path: Path) -> Config:
    """Read ``path`` if it exists; the ``TWITCHBAR_CLIENT_ID``/``_SECRET`` variables override it."""
    config = Config()
    if path.exists():
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        config = _from_dict(raw)
    config.client_id = os.environ.get(ENV_CLIENT_ID, config.client_id)
    config.client_secret = os.environ.get(ENV_CLIENT_SECRET, config.client_secret)
    return config


def save(config: Config, path: Path) -> None:
    """Write ``config`` to ``path`` (creating parent folders), readable by the user only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_toml(config), encoding="utf-8")
    with contextlib.suppress(OSError):  # Windows has no POSIX modes
        path.chmod(0o600)


def to_toml(config: Config) -> str:
    """Render the config as commented TOML."""
    body = tomli_w.dumps(
        {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "poll_seconds": float(config.poll_seconds),
            "recent_messages": int(config.recent_messages),
            "notify_own_messages": bool(config.notify_own_messages),
            "notify_joins": bool(config.notify_joins),
            "ignore_users": list(config.ignore_users),
            "sounds": dict(config.sounds),
        }
    )
    return _HEADER + "\n" + body


def _from_dict(raw: dict[str, object]) -> Config:
    config = Config()
    config.client_id = str(raw.get("client_id", config.client_id))
    config.client_secret = str(raw.get("client_secret", config.client_secret))
    config.poll_seconds = max(5.0, float(_number(raw.get("poll_seconds"), config.poll_seconds)))
    config.recent_messages = max(
        1, int(_number(raw.get("recent_messages"), config.recent_messages))
    )
    config.notify_own_messages = bool(raw.get("notify_own_messages", config.notify_own_messages))
    config.notify_joins = bool(raw.get("notify_joins", config.notify_joins))
    users = raw.get("ignore_users")
    if isinstance(users, list):
        config.ignore_users = [str(user) for user in users]
    sounds = raw.get("sounds")
    if isinstance(sounds, dict):
        config.sounds = {**DEFAULT_SOUNDS, **{str(k): str(v) for k, v in sounds.items()}}
    return config


def _number(value: object, default: float) -> float:
    return (
        float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
    )
