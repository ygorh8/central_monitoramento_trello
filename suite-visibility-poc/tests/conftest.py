from datetime import datetime

import pytest

from suite_visibility.models import EventType, Platform, Status, SuiteEvent


@pytest.fixture
def paused_event():
    return SuiteEvent(
        event=EventType.SUITE_PAUSED,
        suite="Modo Seguro 01",
        platform=Platform.IOS,
        status=Status.PAUSED,
        reason="Falha no WebDriverAgent",
        description="WDA não iniciou no device I002",
        responsible="Ygor",
        paused_by="Ygor",
        paused_at=datetime.fromisoformat("2026-08-04T10:15:00-03:00"),
        expected_return_at=datetime.fromisoformat("2026-08-04T14:00:00-03:00"),
        jenkins_job="Suite Modo Seguro 01 IOS",
        jenkins_build="4784",
        jenkins_url="http://jenkins/job/exemplo/4784/",
    )

