import requests
import pytest

from suite_visibility.trello_client import TrelloClient, TrelloError


class Response:
    def __init__(self, status_code, data=None, invalid_json=False):
        self.status_code = status_code
        self.data = data
        self.invalid_json = invalid_json

    def json(self):
        if self.invalid_json:
            raise ValueError("invalid")
        return self.data


class QueueSession:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def client(session):
    return TrelloClient("key", "token", "board", base_url="https://trello.invalid/1", session=session)


def test_create_when_card_does_not_exist(paused_event):
    session = QueueSession(Response(200, []), Response(200, {"id": "new"}))
    result = client(session).upsert(paused_event, "paused-list")
    assert result["created"] is True


def test_update_existing_card_and_move_list(paused_event):
    session = QueueSession(Response(200, [{"id": "card-1", "desc": "suite_id=modo-seguro-01-ios"}]), Response(200, {"id": "card-1", "idList": "paused-list"}))
    result = client(session).upsert(paused_event, "paused-list")
    assert result["created"] is False
    assert session.calls[1][0] == "PUT"


@pytest.mark.parametrize("outcome,expected", [(Response(401, {}), "Autenticação"), (Response(429, {}), "Limite"), (Response(404, {}), "não encontrado"), (requests.Timeout(), "Timeout")])
def test_trello_errors(paused_event, outcome, expected):
    with pytest.raises(TrelloError, match=expected):
        client(QueueSession(outcome)).find_card(paused_event.suite_id)


def test_card_not_found_returns_none(paused_event):
    assert client(QueueSession(Response(200, []))).find_card(paused_event.suite_id) is None


def test_dry_run_never_calls_network(paused_event):
    session = QueueSession()
    assert client(session).upsert(paused_event, "list", dry_run=True)["dry_run"] is True
    assert session.calls == []


def test_find_jenkins_pause_card_requires_exact_job_and_build_lines():
    session = QueueSession(Response(200, [
        {"id": "wrong", "desc": "Jenkins: http://jenkins/job/a/\nBuild: http://jenkins/job/a/10/extra"},
        {"id": "right", "desc": "Status: PAUSADA\nJenkins: http://jenkins/job/a/\nBuild: http://jenkins/job/a/10/", "url": "https://trello/card"},
    ]))
    card = client(session).find_jenkins_pause_card("http://jenkins/job/a/", "http://jenkins/job/a/10/")
    assert card["id"] == "right"


def test_find_jenkins_pause_card_ignores_completed_card():
    session = QueueSession(Response(200, [
        {"id": "complete", "desc": "Jenkins: http://jenkins/job/a/", "dueComplete": True},
        {"id": "active", "desc": "Jenkins: http://jenkins/job/a/", "dueComplete": False},
    ]))
    assert client(session).find_jenkins_pause_card("http://jenkins/job/a/")["id"] == "active"


def test_create_jenkins_pause_card_formats_operational_description():
    session = QueueSession(Response(200, {"id": "new", "url": "https://trello/card"}))
    result = client(session).create_jenkins_pause_card(
        list_id="tasks",
        job_name="Suite A",
        job_url="http://jenkins/job/a/",
        signal="BUILD_ABORTED",
        detected_at="04/08/2026 13:30:00 (-03)",
        manifest="suite_a.json",
        bots=[101, 102],
        build_url="http://jenkins/job/a/10/",
        aborted_by="Ygor",
    )
    assert result["id"] == "new"
    params = session.calls[0][2]["params"]
    assert params["name"] == "[PAUSADA] Suite A"
    assert "Bots impactados: 101, 102" in params["desc"]
    assert "Build: http://jenkins/job/a/10/" in params["desc"]


def test_diagnose_validates_member_board_and_list_with_get_only():
    session = QueueSession(
        Response(200, {"username": "user"}),
        Response(200, {"name": "Poc_Suite"}),
        Response(200, {"name": "Tarefas", "idBoard": "board"}),
    )
    result = client(session).diagnose("tasks")
    assert result == {"ok": True, "member": "user", "board": "Poc_Suite", "list": "Tarefas"}
    assert [call[0] for call in session.calls] == ["GET", "GET", "GET"]


def test_diagnose_rejects_list_from_another_board():
    session = QueueSession(
        Response(200, {"username": "user"}),
        Response(200, {"name": "Poc_Suite"}),
        Response(200, {"name": "Tarefas", "idBoard": "other"}),
    )
    with pytest.raises(TrelloError, match="nao pertence"):
        client(session).diagnose("tasks")


def test_mark_card_complete_updates_due_complete_without_moving_card():
    session = QueueSession(
        Response(200, {"id": "card-1", "dueComplete": False}),
        Response(200, {"id": "card-1", "dueComplete": True}),
    )
    result = client(session).mark_card_complete("https://trello.com/c/abc123/card-name")
    assert result["changed"] is True
    assert session.calls[1][0] == "PUT"
    assert session.calls[1][2]["params"]["dueComplete"] == "true"
    assert "idList" not in session.calls[1][2]["params"]
