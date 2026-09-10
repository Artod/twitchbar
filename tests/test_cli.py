from pathlib import Path

import pytest

from twitchbar import __version__
from twitchbar.cli import main
from twitchbar.config import ENV_CLIENT_ID, ENV_CLIENT_SECRET, ENV_CONFIG


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"twitchbar {__version__}"


def test_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(ENV_CONFIG, str(tmp_path / "config.toml"))
    assert main(["paths"]) == 0
    assert str(tmp_path / "token.json") in capsys.readouterr().out


def test_run_without_credentials_explains_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(ENV_CONFIG, str(tmp_path / "config.toml"))
    monkeypatch.delenv(ENV_CLIENT_ID, raising=False)
    monkeypatch.delenv(ENV_CLIENT_SECRET, raising=False)
    monkeypatch.setattr("twitchbar.cli.setup_logging", lambda *a, **k: tmp_path / "log")
    assert main([]) == 2
    assert "twitchbar setup" in capsys.readouterr().err


def test_setup_writes_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_CONFIG, str(tmp_path / "config.toml"))
    monkeypatch.setattr("builtins.input", lambda prompt: "my-id")
    monkeypatch.setattr("twitchbar.cli.getpass.getpass", lambda prompt: "my-secret")
    assert main(["setup"]) == 0
    text = (tmp_path / "config.toml").read_text()
    assert 'client_id = "my-id"' in text and 'client_secret = "my-secret"' in text


def test_logout_removes_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_CONFIG, str(tmp_path / "config.toml"))
    token = tmp_path / "token.json"
    token.write_text("{}")
    assert main(["logout"]) == 0
    assert not token.exists()
    assert main(["logout"]) == 0
