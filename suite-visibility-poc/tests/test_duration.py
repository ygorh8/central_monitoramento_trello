from datetime import datetime

import pytest

from suite_visibility.duration import downtime_minutes, format_duration


def test_duration_215_minutes_and_human_format():
    paused = datetime.fromisoformat("2026-08-04T10:15:00-03:00")
    returned = datetime.fromisoformat("2026-08-04T13:50:00-03:00")
    assert downtime_minutes(paused, returned) == 215
    assert format_duration(215) == "3h35min"


def test_duration_requires_timezone():
    with pytest.raises(ValueError, match="timezone"):
        downtime_minutes(datetime(2026, 8, 4, 10), datetime.now().astimezone())

