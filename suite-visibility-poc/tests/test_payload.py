import json
from datetime import datetime

import pytest

from suite_visibility.models import SuiteEvent


def test_payload_serializes_with_timezone_and_without_secrets(paused_event):
    payload = json.loads(paused_event.to_json())
    assert payload["event"] == "SUITE_PAUSED"
    assert payload["status"] == "PAUSADA"
    assert payload["paused_at"].endswith("-03:00")
    assert paused_event.suite_id == "modo-seguro-01-ios"
    assert not any(key in payload for key in ("token", "password", "webhook_url", "api_key"))


def test_required_field_rejected(paused_event):
    values = paused_event.__dict__.copy()
    values["suite"] = ""
    with pytest.raises(ValueError, match="suite"):
        SuiteEvent(**values)


def test_naive_date_rejected(paused_event):
    values = paused_event.__dict__.copy()
    values["paused_at"] = datetime(2026, 8, 4, 10, 15)
    with pytest.raises(ValueError, match="timezone"):
        SuiteEvent(**values)


def test_invalid_status_and_event_rejected(paused_event):
    values = paused_event.__dict__.copy()
    values["status"] = "QUEBRADA"
    with pytest.raises(ValueError):
        SuiteEvent(**values)
    values = paused_event.__dict__.copy()
    values["event"] = "UNKNOWN"
    with pytest.raises(ValueError):
        SuiteEvent(**values)

