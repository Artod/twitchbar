from twitchbar import links


def test_login_falls_back_to_lowercase_name() -> None:
    assert links.login_of("Alice") == "alice"
    assert links.login_of("アリス", "alice_jp") == "alice_jp"


def test_pages() -> None:
    assert links.channel("me") == "https://www.twitch.tv/me"
    assert links.chat_popout("me") == "https://www.twitch.tv/popout/me/chat"
    assert links.stream_manager("me") == "https://dashboard.twitch.tv/u/me/stream-manager"
    assert links.stream_manager() == "https://dashboard.twitch.tv/stream-manager"
