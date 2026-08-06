import json

from suite_visibility.jenkins_client import JenkinsJob
from suite_visibility.jenkins_monitor import acknowledge_trello_card, ignore_jenkins_event, monitor_jobs


def job(paused: bool) -> JenkinsJob:
    return JenkinsJob("Suite A", "http://jenkins/job/a/", "disabled" if paused else "blue", not paused)


def test_initial_state_does_not_emit_without_opt_in(tmp_path):
    result = monitor_jobs([job(True)], tmp_path / "state.json")
    assert result["pending_paused"] == []


def test_active_to_paused_is_pending_until_acknowledged(tmp_path):
    state = tmp_path / "state.json"
    monitor_jobs([job(False)], state)
    result = monitor_jobs([job(True)], state)
    assert len(result["pending_paused"]) == 1
    result = monitor_jobs([job(True)], state)
    assert len(result["pending_paused"]) == 1
    acknowledge_trello_card(state, "http://jenkins/job/a/", "https://trello.com/c/card")
    result = monitor_jobs([job(True)], state)
    assert result["pending_paused"] == []
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert payload["jobs"]["http://jenkins/job/a/"]["trello_card_url"] == "https://trello.com/c/card"


def test_initial_paused_can_be_imported_explicitly(tmp_path):
    result = monitor_jobs([job(True)], tmp_path / "state.json", include_initial_paused=True)
    assert len(result["pending_paused"]) == 1


def test_reset_baseline_clears_pending_initial_jobs(tmp_path):
    state = tmp_path / "state.json"
    monitor_jobs([job(True)], state, include_initial_paused=True)
    result = monitor_jobs([job(True)], state, reset_baseline=True)
    assert result["pending_paused"] == []


def test_new_aborted_build_is_pending_and_preserves_event_build(tmp_path):
    state = tmp_path / "state.json"
    active = JenkinsJob("Suite A", "http://jenkins/job/a/", "blue", True, 10, "SUCCESS", "http://jenkins/job/a/10/", 1000, 10, "SUCCESS", "http://jenkins/job/a/10/", 1000)
    aborted = JenkinsJob("Suite A", "http://jenkins/job/a/", "aborted", True, 11, "ABORTED", "http://jenkins/job/a/11/", 2000, 11, "ABORTED", "http://jenkins/job/a/11/", 2000)
    newer = JenkinsJob("Suite A", "http://jenkins/job/a/", "blue", True, 12, "SUCCESS", "http://jenkins/job/a/12/", 3000, 12, "SUCCESS", "http://jenkins/job/a/12/", 3000)

    monitor_jobs([active], state)
    result = monitor_jobs([aborted], state)
    event = result["pending_paused"][0]
    assert event["pause_signal"] == "BUILD_ABORTED"
    assert event["event_build_url"] == "http://jenkins/job/a/11/"

    result = monitor_jobs([newer], state)
    assert result["pending_paused"][0]["event_build_url"] == "http://jenkins/job/a/11/"


def test_ignored_abort_is_not_retried(tmp_path):
    state = tmp_path / "state.json"
    active = JenkinsJob("Suite A", "http://jenkins/job/a/", "blue", True, 10, "SUCCESS", "http://jenkins/job/a/10/", 1000, 10, "SUCCESS", "http://jenkins/job/a/10/", 1000)
    aborted = JenkinsJob("Suite A", "http://jenkins/job/a/", "aborted", True, 11, "ABORTED", "http://jenkins/job/a/11/", 2000, 11, "ABORTED", "http://jenkins/job/a/11/", 2000)
    monitor_jobs([active], state)
    monitor_jobs([aborted], state)
    ignore_jenkins_event(state, aborted.url, "ABORT_NOT_MANUAL")
    assert monitor_jobs([aborted], state)["pending_paused"] == []


def test_running_build_becoming_aborted_with_same_number_is_detected(tmp_path):
    state = tmp_path / "state.json"
    running = JenkinsJob("Suite A", "http://jenkins/job/a/", "blue_anime", True, 11, None, "http://jenkins/job/a/11/", 2000, 10, "SUCCESS", "http://jenkins/job/a/10/", 1000)
    aborted = JenkinsJob("Suite A", "http://jenkins/job/a/", "aborted", True, 11, "ABORTED", "http://jenkins/job/a/11/", 2000, 11, "ABORTED", "http://jenkins/job/a/11/", 2000)

    monitor_jobs([running], state)
    result = monitor_jobs([aborted], state)

    assert len(result["pending_paused"]) == 1
    assert result["pending_paused"][0]["pause_signal"] == "BUILD_ABORTED"
    assert result["pending_paused"][0]["event_build_url"] == "http://jenkins/job/a/11/"


def test_abort_is_detected_when_a_newer_build_is_already_running(tmp_path):
    state = tmp_path / "state.json"
    before = JenkinsJob("Suite A", "http://jenkins/job/a/", "blue", True, 10, "SUCCESS", "http://jenkins/job/a/10/", 1000, 10, "SUCCESS", "http://jenkins/job/a/10/", 1000)
    after = JenkinsJob("Suite A", "http://jenkins/job/a/", "blue_anime", True, 12, None, "http://jenkins/job/a/12/", 3000, 11, "ABORTED", "http://jenkins/job/a/11/", 2000)

    monitor_jobs([before], state)
    result = monitor_jobs([after], state)

    assert result["pending_paused"][0]["event_build_url"] == "http://jenkins/job/a/11/"


def test_acknowledged_incident_metadata_survives_future_monitor_cycles(tmp_path):
    state = tmp_path / "state.json"
    active = JenkinsJob("Suite A", "http://jenkins/job/a/", "blue", True)
    disabled = JenkinsJob("Suite A", "http://jenkins/job/a/", "disabled", False)
    monitor_jobs([active], state)
    monitor_jobs([disabled], state)
    acknowledge_trello_card(state, disabled.url, "https://trello.com/c/card")

    monitor_jobs([disabled], state)
    payload = json.loads(state.read_text(encoding="utf-8"))["jobs"][disabled.url]

    assert payload["tracked_pause_signal"] == "JOB_DISABLED"
    assert payload["trello_card_url"] == "https://trello.com/c/card"
    assert payload["trello_card_created_at"] is not None
