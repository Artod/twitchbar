from datetime import UTC, datetime

from twitchbar.demo import script
from twitchbar.stats import SessionStats


def test_demo_script_plays_through_the_stats() -> None:
    stats = SessionStats()
    alerts = [alert for _, event in script(datetime.now(UTC)) for alert in stats.apply(event)]
    kinds = {alert.kind for alert in alerts}
    assert {"online", "message", "follow", "sub", "cheer", "raid", "join", "offline"} <= kinds
    assert stats.live is False
