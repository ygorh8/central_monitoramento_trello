import requests

from suite_visibility.jenkins_client import JenkinsApiError, JenkinsReadOnlyClient


class Response:
    def __init__(self, code, headers=None, url="http://jenkins.invalid/"):
        self.status_code = code
        self.headers = headers or {}
        self.url = url


class Session:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def head(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_403_confirms_jenkins_with_access_control():
    session = Session(Response(403, {"Server": "Jetty", "X-Jenkins": "2.528.1"}))
    result = JenkinsReadOnlyClient(session=session).diagnose("http://jenkins.invalid/")
    assert result.classification == "ACESSÍVEL_COM_AUTENTICAÇÃO"
    assert result.status_code == 403
    assert result.x_jenkins == "2.528.1"
    assert result.access_control_detected is True
    assert session.calls[0][1]["allow_redirects"] is False


def test_redirect_is_not_followed():
    result = JenkinsReadOnlyClient(session=Session(Response(302, {"Location": "https://jenkins.invalid/"}))).diagnose("http://jenkins.invalid/")
    assert result.classification == "REDIRECIONAMENTO"
    assert result.redirected is True
    assert result.final_url == "https://jenkins.invalid/"


def test_timeout_is_classified_without_retry():
    result = JenkinsReadOnlyClient(session=Session(requests.ConnectTimeout())).diagnose("http://jenkins.invalid/")
    assert result.classification == "TIMEOUT"
    assert result.status_code is None


def test_userinfo_in_url_is_rejected():
    try:
        JenkinsReadOnlyClient().diagnose("http://identity@jenkins.invalid/")
    except ValueError as exc:
        assert "Credenciais" in str(exc)
    else:
        raise AssertionError("URL com credenciais deveria ser rejeitada")


class ApiResponse:
    def __init__(self, code, data=None, text=""):
        self.status_code = code
        self._data = data
        self.text = text

    def json(self):
        return self._data


class ApiSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_list_jobs_counts_disabled_as_paused():
    session = ApiSession(ApiResponse(200, {"jobs": [
        {"name": "Suite A", "url": "http://jenkins/job/a/", "color": "blue", "buildable": True},
        {"name": "Suite B", "url": "http://jenkins/job/b/", "color": "disabled", "buildable": False},
    ]}))
    jobs = JenkinsReadOnlyClient(session=session, username="user", api_token="token").list_jobs("http://jenkins.invalid/")
    assert len(jobs) == 2
    assert jobs[0].paused is False
    assert jobs[1].paused is True
    assert session.calls[0][1]["auth"] == ("user", "token")
    assert "token" not in session.calls[0][0]


def test_list_jobs_rejects_partial_credentials():
    try:
        JenkinsReadOnlyClient(session=ApiSession(None), username="user").list_jobs("http://jenkins.invalid/")
    except JenkinsApiError as exc:
        assert "configurados juntos" in str(exc)
    else:
        raise AssertionError("Credenciais parciais deveriam ser rejeitadas")


def test_get_abort_info_confirms_manual_abort_actor():
    session = ApiSession(ApiResponse(200, text="Started\nAborted by Ygor Oliveira\nFinished: ABORTED\n"))
    result = JenkinsReadOnlyClient(session=session, username="user", api_token="token").get_abort_info(
        "http://jenkins.invalid/job/a/11/"
    )
    assert result["confirmed_manual_abort"] is True
    assert result["aborted_by"] == "Ygor Oliveira"
    assert session.calls[0][0].endswith("/consoleText")


def test_get_abort_info_rejects_automatic_abort_as_manual():
    session = ApiSession(ApiResponse(200, text="Finished: ABORTED\n"))
    result = JenkinsReadOnlyClient(session=session, username="user", api_token="token").get_abort_info(
        "http://jenkins.invalid/job/a/11/"
    )
    assert result["confirmed_manual_abort"] is False
    assert result["aborted_by"] is None
