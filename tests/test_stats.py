from datetime import UTC, datetime, timedelta

from twitchbar.events import (
    ChatMessage,
    Chatter,
    Chatters,
    Cheer,
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
from twitchbar.stats import (
    KIND_FOLLOW,
    KIND_JOIN,
    KIND_MESSAGE,
    KIND_OFFLINE,
    KIND_ONLINE,
    STATE_AUTHORIZING,
    STATE_CONNECTED,
    SessionStats,
    format_duration,
    shorten,
)
from twitchbar.tray.base import MenuLine

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def connected() -> SessionStats:
    stats = SessionStats(ignore_users=["Nightbot"])
    stats.apply(SourceState(STATE_CONNECTED, "me"))
    return stats


def test_title_follows_connection_state() -> None:
    stats = SessionStats()
    assert stats.tray_title() == "⏳"
    stats.apply(SourceState(STATE_AUTHORIZING))
    assert stats.tray_title() == "🔑 login"
    stats.apply(SourceState(STATE_CONNECTED))
    assert stats.tray_title() == "⏸ 💬0 ❤0"
    assert stats.badge() == "–"


def test_live_status_sets_viewers_and_title() -> None:
    stats = connected()
    alerts = stats.apply(
        StreamStatus(live=True, viewers=3, title="hello", game="Chatting", started_at=NOW)
    )
    assert [a.kind for a in alerts] == [KIND_ONLINE]
    assert stats.tray_title() == "👁3 💬0 ❤0"
    assert stats.badge() == "3"
    assert stats.uptime(NOW + timedelta(minutes=65)) == timedelta(minutes=65)
    live, headline = stats.summary_lines(NOW + timedelta(minutes=65))[:2]
    assert (live.text, live.url) == ("🟢 Live · 1h 05m · 3 viewers", "https://www.twitch.tv/me")
    assert (headline.text, headline.url) == (
        "Chatting — hello",
        "https://dashboard.twitch.tv/u/me/stream-manager",
    )


def test_going_live_resets_session_counters_once() -> None:
    stats = connected()
    stats.apply(Follow("a"))
    stats.apply(ChatMessage("b", "hi"))
    assert (stats.followers, stats.messages) == (1, 1)
    assert stats.apply(StreamOnline(NOW))[0].kind == KIND_ONLINE
    assert (stats.followers, stats.messages) == (0, 0)
    stats.apply(Follow("c"))
    # A poll confirming the same live stream must not reset again or re-alert.
    assert stats.apply(StreamStatus(live=True, viewers=1, started_at=NOW)) == []
    assert stats.followers == 1


def test_offline_alert_carries_session_summary() -> None:
    stats = connected()
    stats.apply(StreamOnline(NOW))
    stats.apply(ChatMessage("a", "x"))
    stats.apply(Raid("b", 5))
    (alert,) = stats.apply(StreamOffline())
    assert alert.kind == KIND_OFFLINE
    assert alert.body == "1 messages · 0 followers · 0 subs · 1 raids · 0 bits"
    assert stats.apply(StreamOffline()) == []


def test_messages_are_counted_kept_and_alerted() -> None:
    stats = connected()
    (alert,) = stats.apply(ChatMessage("alice", "  hello   there\nfriend "))
    assert alert.kind == KIND_MESSAGE
    assert alert.title == "💬 alice"
    assert alert.body == "hello there friend"
    assert alert.url == "https://www.twitch.tv/popout/me/chat"
    (line,) = stats.recent_lines()
    assert (line.text, line.url) == (
        "alice: hello there friend",
        "https://www.twitch.tv/popout/me/chat",
    )


def test_bar_counts_unread_messages_until_the_menu_opens() -> None:
    stats = connected()
    stats.apply(ChatMessage("a", "one"))
    stats.apply(ChatMessage("b", "two"))
    stats.apply(ChatMessage("me", "mine", is_self=True))
    assert stats.tray_title() == "⏸ 💬2 ❤0"
    assert stats.messages == 3
    stats.mark_seen()
    assert stats.tray_title() == "⏸ 💬0 ❤0"
    assert [line.text for line in stats.recent_lines()] == ["me: mine", "b: two", "a: one"]
    stats.apply(ChatMessage("c", "three"))
    assert stats.unread == 1


def test_own_and_ignored_messages() -> None:
    stats = connected()
    assert stats.apply(ChatMessage("me", "testing", is_self=True)) == []
    assert stats.messages == 1
    assert stats.apply(ChatMessage("nightbot", "spam")) == []
    assert stats.messages == 1
    loud = SessionStats(notify_own_messages=True)
    loud.apply(SourceState(STATE_CONNECTED))
    assert len(loud.apply(ChatMessage("me", "testing", is_self=True))) == 1


def test_recent_is_bounded_and_newest_first() -> None:
    stats = SessionStats(recent_size=2)
    for i in range(3):
        stats.apply(ChatMessage("u", str(i)))
    assert [line.text for line in stats.recent_lines()] == ["u: 2", "u: 1"]


def chatters(*names: str) -> Chatters:
    return Chatters(tuple(Chatter(name) for name in names))


def test_chatters_seed_silently_then_alert_on_joins() -> None:
    stats = connected()
    assert stats.apply(chatters("alice", "Nightbot")) == []
    assert [line.text for line in stats.chatter_lines()] == ["alice", "Nightbot"]
    alerts = stats.apply(chatters("alice", "Nightbot", "carol", "bob"))
    assert [(a.kind, a.body, a.url) for a in alerts] == [
        (KIND_JOIN, "bob", "https://www.twitch.tv/bob"),
        (KIND_JOIN, "carol", "https://www.twitch.tv/carol"),
    ]
    assert stats.apply(chatters("alice")) == []
    assert stats.chatter_lines() == (MenuLine("alice", "https://www.twitch.tv/alice"),)


def test_localized_display_names_link_by_login() -> None:
    stats = connected()
    stats.apply(Chatters(()))
    (alert,) = stats.apply(Chatters((Chatter("アリス", "alice_jp"),)))
    assert (alert.body, alert.url) == ("アリス", "https://www.twitch.tv/alice_jp")
    assert (
        stats.apply(Follow("アリス", login="alice_jp"))[0].url == "https://www.twitch.tv/alice_jp"
    )


def test_joins_can_be_muted() -> None:
    stats = SessionStats(notify_joins=False)
    stats.apply(chatters())
    assert stats.apply(chatters("x")) == []


def test_money_events() -> None:
    stats = connected()
    assert stats.apply(Follow("f"))[0].kind == KIND_FOLLOW
    assert stats.apply(Subscribe("s", "2000", is_gift=True))[0].body == "s · Tier 2 · gifted"
    assert stats.apply(Resub("r", "1000", 4, "yay"))[0].body == "r · Tier 1 · 4 months: yay"
    assert stats.apply(GiftSubs(None, 5, "1000"))[0].body == "Anonymous gifted 5 subs · Tier 1"
    assert stats.apply(Raid("x", 1))[0].body == "x brought 1 viewer"
    assert stats.apply(Cheer("c", 250, ""))[0].title == "💎 250 bits"
    assert (stats.followers, stats.subs, stats.raids, stats.bits) == (1, 7, 1, 250)
    assert [line.text for line in stats.summary_lines(NOW)[-2:]] == [
        "Messages: 0 · Followers: 1 · Subs: 7",
        "Raids: 1 · Bits: 250",
    ]
    assert stats.apply(Raid("Friend", 3))[0].url == "https://www.twitch.tv/friend"
    assert stats.apply(Cheer(None, 1))[0].url is None


def test_helpers() -> None:
    assert shorten("a" * 10, 5) == "aaaa…"
    assert shorten("short", 10) == "short"
    assert format_duration(timedelta(minutes=7)) == "7m"
    assert format_duration(timedelta(hours=2, minutes=3)) == "2h 03m"


def test_join_alerts_skip_yourself_and_flapping_viewers() -> None:
    stats = connected()  # signed in as "me"
    stats.apply(chatters("alice"))
    assert stats.apply(chatters("alice", "me")) == []
    (alert,) = stats.apply(chatters("alice", "me", "bob"))
    assert alert.body == "bob"
    # bob drops out and is back on the next poll: no second ping within the cooldown
    stats.apply(chatters("alice", "me"))
    assert stats.apply(chatters("alice", "me", "bob")) == []


def test_join_alert_returns_after_the_cooldown() -> None:
    stats = SessionStats(join_cooldown=timedelta(minutes=10))
    stats.apply(SourceState(STATE_CONNECTED, "me"))
    stats._apply_chatters((Chatter("bob"),), now=NOW)
    stats._apply_chatters((), now=NOW + timedelta(minutes=1))
    assert stats._apply_chatters((Chatter("bob"),), now=NOW + timedelta(minutes=5)) == []
    stats._apply_chatters((), now=NOW + timedelta(minutes=6))
    assert len(stats._apply_chatters((Chatter("bob"),), now=NOW + timedelta(minutes=20))) == 1
