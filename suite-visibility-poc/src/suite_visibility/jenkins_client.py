"""Diagnóstico HTTP estritamente de leitura para a raiz do Jenkins."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import requests


class JenkinsApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class JenkinsJob:
    name: str
    url: str
    color: str | None
    buildable: bool | None
    last_build_number: int | None = None
    last_build_result: str | None = None
    last_build_url: str | None = None
    last_build_timestamp: int | None = None
    last_completed_build_number: int | None = None
    last_completed_build_result: str | None = None
    last_completed_build_url: str | None = None
    last_completed_build_timestamp: int | None = None

    @property
    def paused(self) -> bool:
        return self.buildable is False or self.color == "disabled"


@dataclass(frozen=True)
class JenkinsDiagnosis:
    classification: str
    status_code: int | None
    elapsed_seconds: float
    final_url: str | None
    redirected: bool
    server: str | None
    x_jenkins: str | None
    access_control_detected: bool | None
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class JenkinsReadOnlyClient:
    def __init__(self, timeout: float = 20, session=None, username: str | None = None, api_token: str | None = None):
        self._timeout = timeout
        self._session = session or requests.Session()
        self._username = username
        self._api_token = api_token

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("URL HTTP(S) válida é obrigatória")
        if parsed.username or parsed.password:
            raise ValueError("Credenciais na URL não são permitidas")

    def list_jobs(self, url: str) -> list[JenkinsJob]:
        """List top-level Jenkins jobs using only the documented read API."""
        self._validate_url(url)
        if bool(self._username) != bool(self._api_token):
            raise JenkinsApiError("JENKINS_USERNAME e JENKINS_API_TOKEN devem ser configurados juntos")
        endpoint = f"{url.rstrip('/')}/api/json"
        kwargs: dict[str, object] = {
            "params": {"tree": "jobs[name,url,color,buildable,lastBuild[number,result,url,timestamp,building],lastCompletedBuild[number,result,url,timestamp]]"},
            "timeout": self._timeout,
        }
        if self._username and self._api_token:
            kwargs["auth"] = (self._username, self._api_token)
        try:
            response = self._session.get(endpoint, **kwargs)
        except requests.Timeout as exc:
            raise JenkinsApiError("Timeout ao consultar a API do Jenkins") from exc
        except requests.ConnectionError as exc:
            raise JenkinsApiError("Falha de DNS ou conexao ao consultar a API do Jenkins") from exc
        if response.status_code in (401, 403):
            raise JenkinsApiError(f"API do Jenkins exige autorizacao (HTTP {response.status_code})")
        if not 200 <= response.status_code < 300:
            raise JenkinsApiError(f"Falha na API do Jenkins (HTTP {response.status_code})")
        try:
            payload = response.json()
        except ValueError as exc:
            raise JenkinsApiError("Resposta JSON invalida da API do Jenkins") from exc
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise JenkinsApiError("Resposta da API do Jenkins nao contem uma lista de jobs")
        return [
            JenkinsJob(
                name=str(job.get("name", "")),
                url=str(job.get("url", "")),
                color=job.get("color"),
                buildable=job.get("buildable"),
                last_build_number=(job.get("lastBuild") or {}).get("number"),
                last_build_result=(job.get("lastBuild") or {}).get("result"),
                last_build_url=(job.get("lastBuild") or {}).get("url"),
                last_build_timestamp=(job.get("lastBuild") or {}).get("timestamp"),
                last_completed_build_number=(job.get("lastCompletedBuild") or {}).get("number"),
                last_completed_build_result=(job.get("lastCompletedBuild") or {}).get("result"),
                last_completed_build_url=(job.get("lastCompletedBuild") or {}).get("url"),
                last_completed_build_timestamp=(job.get("lastCompletedBuild") or {}).get("timestamp"),
            )
            for job in jobs
            if isinstance(job, dict) and job.get("name")
        ]

    def get_abort_info(self, build_url: str) -> dict[str, object]:
        self._validate_url(build_url)
        kwargs: dict[str, object] = {"timeout": self._timeout}
        if self._username and self._api_token:
            kwargs["auth"] = (self._username, self._api_token)
        try:
            response = self._session.get(f"{build_url.rstrip('/')}/consoleText", **kwargs)
        except requests.RequestException as exc:
            raise JenkinsApiError("Falha ao consultar log do build") from exc
        if not 200 <= response.status_code < 300:
            raise JenkinsApiError(f"Falha ao consultar log do build (HTTP {response.status_code})")
        import re

        matches = re.findall(r"(?im)^.*Aborted by\s+([^\r\n]+)", response.text)
        aborted_by = matches[-1].strip() if matches else None
        return {"confirmed_manual_abort": aborted_by is not None, "aborted_by": aborted_by, "build_url": build_url}

    def diagnose(self, url: str) -> JenkinsDiagnosis:
        self._validate_url(url)
        started = time.monotonic()
        try:
            response = self._session.head(url, allow_redirects=False, timeout=self._timeout)
        except requests.ConnectTimeout:
            return JenkinsDiagnosis("TIMEOUT", None, time.monotonic() - started, None, False, None, None, None, "Tempo de conexão esgotado")
        except requests.ConnectionError as exc:
            text = str(exc).lower()
            classification = "ERRO_DNS" if "name" in text or "resolve" in text else "CONEXÃO_RECUSADA"
            return JenkinsDiagnosis(classification, None, time.monotonic() - started, None, False, None, None, None, "Falha de conexão")
        except requests.Timeout:
            return JenkinsDiagnosis("TIMEOUT", None, time.monotonic() - started, None, False, None, None, None, "Tempo total esgotado")
        elapsed = time.monotonic() - started
        code = response.status_code
        redirected = 300 <= code < 400
        if redirected:
            classification = "REDIRECIONAMENTO"
        elif code in (401, 403):
            classification = "ACESSÍVEL_COM_AUTENTICAÇÃO"
        elif code in (200, 404):
            classification = "ACESSÍVEL_PUBLICAMENTE"
        else:
            classification = "INCONCLUSIVO"
        return JenkinsDiagnosis(
            classification,
            code,
            elapsed,
            response.headers.get("Location") or response.url,
            redirected,
            response.headers.get("Server"),
            response.headers.get("X-Jenkins"),
            code in (401, 403),
            "Servidor HTTP respondeu ao método HEAD",
        )
