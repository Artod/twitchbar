from pathlib import Path

from twitchbar.lock import acquire


def test_second_acquire_fails_while_first_is_held(tmp_path: Path) -> None:
    first = acquire(tmp_path / "x.lock")
    assert first is not None
    assert acquire(tmp_path / "x.lock") is None
    first.close()
    again = acquire(tmp_path / "x.lock")
    assert again is not None
    again.close()
