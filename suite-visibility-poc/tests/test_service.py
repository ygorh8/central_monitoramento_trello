import json

from suite_visibility.config import Settings
from suite_visibility.jenkins_client import JenkinsJob
from suite_visibility.service import SuiteVisibilityService, healthcheck


class FakeJenkins:
    def __init__(self, inventories):
        self.inventories = list(inventories)

    def list_jobs(self, _url):
        return self.inventories.pop(0)

    def get_abort_info(self, build_url):
        return {"confirmed_manual_abort": True, "aborted_by": "Ygor", "build_url": build_url}


class FakeTrello:
    def __init__(self):
        self.created = []

    def find_jenkins_pause_card(self, _job_url, _build_url=None):
        return None

    def create_jenkins_pause_card(self, **kwargs):
        self.created.append(kwargs)
        return {"url": "https://trello/card-1"}


def settings(tmp_path):
    return Settings(
        jenkins_url="http://jenkins/",
        jenkins_username="user",
        jenkins_api_token="token",
        teams_webhook_url=None,
        trello_api_key="key",
        trello_api_token="token",
        trello_board_id="board",
        trello_paused_list_id="tasks",
        trello_maintenance_list_id=None,
        trello_resumed_list_id=None,
        suite_repository_path=str(tmp_path / "repo"),
        monitor_state_file=str(tmp_path / "state.json"),
        monitor_status_file=str(tmp_path / "status.json"),
    )


def test_service_detects_manual_abort_and_creates_card(tmp_path, monkeypatch):
    before = JenkinsJob(
        "Suite A", "http://jenkins/job/a/", "blue", True,
        10, "SUCCESS", "http://jenkins/job/a/10/", 1000,
        10, "SUCCESS", "http://jenkins/job/a/10/", 1000,
    )
    after = JenkinsJob(
        "Suite A", "http://jenkins/job/a/", "blue_anime", True,
        12, None, "http://jenkins/job/a/12/", 3000,
        11, "ABORTED", "http://jenkins/job/a/11/", 2000,
    )
    repo = tmp_path / "repo" / "suites"
    repo.mkdir(parents=True)
    (repo / "suite_a.json").write_text('[{"path":"tests/test_B101_flow.py"}]', encoding="utf-8")
    monkeypatch.setattr("suite_visibility.service.suite_manifest_from_config", lambda *args, **kwargs: "suite_a.json")
    trello = FakeTrello()
    service = SuiteVisibilityService(
        settings(tmp_path),
        jenkins_client=FakeJenkins([[before], [after]]),
        trello_client=trello,
    )

    assert service.run_once(force=True)["processed"] == []
    result = service.run_once(force=True)

    assert result["ok"] is True
    assert result["processed"][0]["action"] == "created"
    assert trello.created[0]["bots"] == [101]
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["jobs"]["http://jenkins/job/a/"]["pending_trello"] is False


def test_healthcheck_rejects_missing_status(tmp_path):
    healthy, result = healthcheck(settings(tmp_path))
    assert healthy is False
    assert result["reason"] == "status_file_missing"
