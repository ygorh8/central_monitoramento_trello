from datetime import datetime

import requests
import pytest

from suite_visibility.models import EventType, Status, SuiteEvent
from suite_visibility.teams_client import TeamsClient, TeamsError, format_teams_message


class Response:
    def __init__(self, status_code):
        self.status_code = status_code


class Session:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return Response(self.outcome)


@pytest.mark.parametrize("code", [200, 202])
def test_success(paused_event, code):
    result = TeamsClient("https://example.invalid/hook", session=Session(code)).send(paused_event)
    assert result == {"sent": True, "status_code": code}


@pytest.mark.parametrize("code,expected", [(400, "rejeitou"), (401, "rejeitou"), (429, "rejeitou"), (500, "indisponível"), (302, "inesperada")])
def test_http_errors(paused_event, code, expected):
    with pytest.raises(TeamsError, match=expected):
        TeamsClient("https://example.invalid/hook", session=Session(code)).send(paused_event)


@pytest.mark.parametrize("error,expected", [(requests.Timeout(), "Timeout"), (requests.ConnectionError("DNS"), "DNS")])
def test_network_errors(paused_event, error, expected):
    with pytest.raises(TeamsError, match=expected):
        TeamsClient("https://example.invalid/hook", session=Session(error)).send(paused_event)


def test_dry_run_does_not_require_url(paused_event):
    result = TeamsClient(None).send(paused_event, dry_run=True)
    assert result["dry_run"] is True
    assert "SUÍTE PAUSADA" in result["payload"]["text"]


def test_resume_message_contains_duration_and_solution(paused_event):
    values = paused_event.__dict__.copy()
    values.update(
        event=EventType.SUITE_RESUMED,
        status=Status.ACTIVE,
        returned_at=datetime.fromisoformat("2026-08-04T13:50:00-03:00"),
        notes="WebDriverAgent reinstalado e validado",
    )
    message = format_teams_message(SuiteEvent(**values))
    assert "SUÍTE RETOMADA" in message
    assert "3h35min" in message
    assert "WebDriverAgent reinstalado" in message
