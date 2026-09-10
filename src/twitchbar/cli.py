"""Command line entry point: ``twitchbar`` runs the tray, ``twitchbar setup`` stores credentials."""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
from collections.abc import Callable, Sequence

from twitchbar import __version__
from twitchbar.config import Paths, load, save
from twitchbar.events import Event
from twitchbar.log import setup_logging

log = logging.getLogger(__name__)

SETUP_HINT = (
    "twitchbar needs a Twitch application's Client ID and Client Secret.\n"
    "Create one at https://dev.twitch.tv/console/apps (redirect URL http://localhost:17563),\n"
    "then run:  twitchbar setup"
)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and dispatch; returns the process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args:
        print(f"twitchbar {__version__}")
        return 0
    if not args or args[0].startswith("-"):
        args.insert(0, "run")
    namespace = _parser().parse_args(args)
    handler: Callable[[argparse.Namespace], int] = namespace.handler
    return handler(namespace)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="twitchbar",
        description="Your Twitch channel in the menu bar, with a notification for everything.",
    )
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    commands = parser.add_subparsers(dest="command")

    run = commands.add_parser("run", help="show the tray (the default when no command is given)")
    run.add_argument(
        "--demo", action="store_true", help="play a scripted stream instead of connecting"
    )
    run.add_argument(
        "--tray",
        choices=["auto", "mac", "generic"],
        default="auto",
        help="tray backend (auto picks per OS)",
    )
    run.add_argument(
        "--no-notify", action="store_true", help="log alerts instead of showing banners"
    )
    run.add_argument(
        "--quiet", action="store_true", help="start in quiet mode (no banners until toggled)"
    )
    run.add_argument("-v", "--verbose", action="store_true", help="debug logging on the terminal")
    run.set_defaults(handler=cmd_run)

    setup = commands.add_parser("setup", help="store your Twitch app's Client ID and Client Secret")
    setup.set_defaults(handler=cmd_setup)

    logout = commands.add_parser(
        "logout", help="forget the stored Twitch token (next run asks again)"
    )
    logout.set_defaults(handler=cmd_logout)

    autostart = commands.add_parser("autostart", help="start twitchbar at login (macOS)")
    autostart.add_argument("state", choices=["on", "off"])
    autostart.set_defaults(handler=cmd_autostart)

    paths = commands.add_parser("paths", help="print where the config, token and log live")
    paths.set_defaults(handler=cmd_paths)
    return parser


def cmd_run(args: argparse.Namespace) -> int:
    """Run the tray until the user quits."""
    paths = Paths.default()
    log_file = setup_logging(paths.log_dir, verbose=args.verbose)
    config = load(paths.config_file)
    if not args.demo and not config.is_complete():
        print(SETUP_HINT, file=sys.stderr)
        return 2
    log.info("twitchbar %s starting, log at %s", __version__, log_file)

    from twitchbar.app import App, Source
    from twitchbar.notify import CallbackNotifier, LogNotifier, Notifier, default_notifier
    from twitchbar.stats import SessionStats
    from twitchbar.tray import build_tray
    from twitchbar.tray.base import TrayActions

    stats = SessionStats(
        recent_size=config.recent_messages,
        ignore_users=config.ignore_users,
        notify_own_messages=config.notify_own_messages,
        notify_joins=config.notify_joins,
    )
    app_ref: list[App] = []  # the tray needs its actions before the app that serves them exists
    actions = TrayActions(
        open_url=lambda url: app_ref[0].open_url(url),
        open_channel=lambda: app_ref[0].open_channel(),
        open_chat=lambda: app_ref[0].open_chat(),
        open_dashboard=lambda: app_ref[0].open_dashboard(),
        toggle_quiet=lambda: app_ref[0].toggle_quiet(),
        quit=lambda: app_ref[0].quit(),
    )
    tray = build_tray(args.tray, actions, recent_slots=config.recent_messages)
    notifier: Notifier
    if args.no_notify:
        notifier = LogNotifier()
    else:
        fallback = (
            CallbackNotifier(tray.notify, beep=_system_beep()) if hasattr(tray, "notify") else None
        )
        notifier = default_notifier(
            sys.platform, fallback, opener=lambda url: app_ref[0].open_url(url)
        )

    def make_source(sink: Callable[[Event], None]) -> Source:
        if args.demo:
            from twitchbar.demo import DemoSource

            return DemoSource(sink)
        from twitchbar.twitch_source import TwitchSource

        return TwitchSource(config, paths.token_file, sink)

    app = App(
        config=config,
        stats=stats,
        tray=tray,
        notifier=notifier,
        make_source=make_source,
        quiet=args.quiet,
    )
    app_ref.append(app)
    app.run()
    return 0


def _system_beep() -> Callable[[], None] | None:
    """The stock alert sound on Windows; None elsewhere."""
    if sys.platform != "win32":
        return None
    import winsound

    return winsound.MessageBeep


def cmd_setup(args: argparse.Namespace) -> int:
    """Ask for the credentials on the terminal and write the config file."""
    paths = Paths.default()
    config = load(paths.config_file)
    print("Twitch application credentials (https://dev.twitch.tv/console/apps)")
    config.client_id = _prompt("Client ID", config.client_id)
    config.client_secret = _prompt("Client Secret", config.client_secret, secret=True)
    if not config.is_complete():
        print("Both values are required; nothing was saved.", file=sys.stderr)
        return 2
    save(config, paths.config_file)
    print(f"Saved to {paths.config_file}")
    print("Now run:  twitchbar   (your browser opens once so you can authorize the app)")
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    """Delete the stored token."""
    paths = Paths.default()
    if paths.token_file.exists():
        paths.token_file.unlink()
        print(f"Removed {paths.token_file}")
    else:
        print("No stored token.")
    return 0


def cmd_autostart(args: argparse.Namespace) -> int:
    """Enable or disable starting at login."""
    if sys.platform != "darwin":
        print(
            "Automatic start is only wired up for macOS. On Windows, put a shortcut to\n"
            "`twitchbar` into the Startup folder (Win+R, then `shell:startup`).",
            file=sys.stderr,
        )
        return 2
    from twitchbar import autostart

    if args.state == "on":
        path = autostart.enable(Paths.default().log_dir)
        print(f"twitchbar will start at login ({path})")
    else:
        removed = autostart.disable()
        print(f"Removed {removed}" if removed else "Autostart was not enabled.")
    return 0


def cmd_paths(args: argparse.Namespace) -> int:
    """Print the config, token and log locations."""
    paths = Paths.default()
    print(f"config: {paths.config_file}")
    print(f"token:  {paths.token_file}")
    print(f"logs:   {paths.log_dir}")
    return 0


def _prompt(label: str, current: str, *, secret: bool = False) -> str:
    shown = ("*" * 8 if secret else current) if current else ""
    hint = f" [{shown}]" if shown else ""
    reader = getpass.getpass if secret else input
    value = reader(f"{label}{hint}: ").strip()
    return value or current
