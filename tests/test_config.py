import tomllib
from pathlib import Path

import pytest

from twitchbar import config as cfg


def test_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    original = cfg.Config(
        client_id="id", client_secret="secret", poll_seconds=12, ignore_users=["a"]
    )
    original.sounds["message"] = ""
    cfg.save(original, path)
    loaded = cfg.load(path)
    assert loaded == original
    assert loaded.is_complete()
    assert tomllib.loads(path.read_text())["sounds"]["follow"] == "Hero"


def test_missing_file_gives_defaults_and_env_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(cfg.ENV_CLIENT_ID, "env-id")
    monkeypatch.setenv(cfg.ENV_CLIENT_SECRET, "env-secret")
    loaded = cfg.load(tmp_path / "nope.toml")
    assert (loaded.client_id, loaded.client_secret) == ("env-id", "env-secret")
    assert loaded.sounds == cfg.DEFAULT_SOUNDS
    assert "nightbot" in loaded.ignore_users


def test_partial_file_keeps_defaults_and_clamps(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'client_id = "x"\npoll_seconds = 1\nrecent_messages = 0\n[sounds]\nraid = "Blow"\n'
    )
    loaded = cfg.load(path)
    assert loaded.poll_seconds == 5.0
    assert loaded.recent_messages == 1
    assert loaded.sounds["raid"] == "Blow"
    assert loaded.sounds["follow"] == "Hero"
    assert not loaded.is_complete()


def test_paths_honour_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cfg.ENV_CONFIG, str(tmp_path / "c.toml"))
    paths = cfg.Paths.default()
    assert paths.config_file == tmp_path / "c.toml"
    assert paths.token_file == tmp_path / "token.json"


def test_to_toml_starts_with_comments() -> None:
    assert cfg.to_toml(cfg.Config()).startswith("# twitchbar configuration")
