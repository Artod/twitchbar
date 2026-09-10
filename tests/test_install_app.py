import plistlib
import sys
from pathlib import Path

import pytest

from twitchbar import install_app


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_build_writes_a_launchable_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install_app, "command", lambda: "/opt/bin/twitchbar")
    app = install_app.build(tmp_path)
    assert app == tmp_path / "twitchbar.app"
    plist = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert plist["CFBundleExecutable"] == "twitchbar" and plist["LSUIElement"] is True
    launcher = app / "Contents" / "MacOS" / "twitchbar"
    last = launcher.read_text().splitlines()[-1]
    assert last == '/usr/bin/nohup /opt/bin/twitchbar run "$@" >/dev/null 2>&1 &'
    assert launcher.stat().st_mode & 0o111
    assert (app / "Contents" / "Resources" / "twitchbar.icns").stat().st_size > 1000
    assert install_app.remove(tmp_path) == app
    assert install_app.remove(tmp_path) is None
