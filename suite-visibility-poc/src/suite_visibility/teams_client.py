"""Cliente mínimo para um Workflow do Microsoft Teams."""

from __future__ import annotations

from datetime import datetime

import requests

from .duration import format_duration
from .models import EventType, SuiteEvent


class TeamsError(RuntimeError):
    pass


def _format_datetime(value: datetime | None) -> str:
    return value.strftime("%d/%m/%Y %H:%M") if value else "Não informada"


def format_teams_message(event: SuiteEvent) -> str:
    if event.event == EventType.SUITE_RESUMED:
        duration = format_duration(event.downtime_minutes or 0)
        return "\n".join(
            [
                "🟢 SUÍTE RETOMADA",
                "",
                f"Suíte: {event.suite}",
                f"Plataforma: {event.platform.value}",
                f"Retomada em: {_format_datetime(event.returned_at)}",
                f"Tempo total parada: {duration}",
                f"Responsável: {event.responsible}",
                f"Solução: {event.notes or 'Não informada'}",
            ]
        )
    return "\n".join(
        [
            "🔴 SUÍTE PAUSADA",
            "",
            f"Suíte: {event.suite}",
            f"Plataforma: {event.platform.value}",
            f"Motivo: {event.reason}",
            f"Responsável: {event.responsible}",
            f"Pausada em: {_format_datetime(event.paused_at)}",
            f"Previsão de retorno: {_format_datetime(event.expected_return_at)}",
            f"Build: #{event.jenkins_build or 'N/A'}",
        ]
    )


class TeamsClient:
    def __init__(self, webhook_url: str | None, timeout: float = 15, session=None):
        self._url = webhook_url
        self._timeout = timeout
        self._session = session or requests.Session()

    def send(self, event: SuiteEvent, *, dry_run: bool = False) -> dict[str, object]:
        payload = {"text": format_teams_message(event)}
        if dry_run:
            return {"sent": False, "dry_run": True, "payload": payload}
        if not self._url:
            raise TeamsError("TEAMS_WEBHOOK_URL não configurada")
        try:
            response = self._session.post(self._url, json=payload, timeout=self._timeout)
        except requests.Timeout as exc:
            raise TeamsError("Timeout ao notificar o Teams") from exc
        except requests.ConnectionError as exc:
            reason = "Falha de DNS ou conexão ao notificar o Teams"
            raise TeamsError(reason) from exc
        if 200 <= response.status_code < 300:
            return {"sent": True, "status_code": response.status_code}
        if 400 <= response.status_code < 500:
            raise TeamsError(f"Teams rejeitou a mensagem (HTTP {response.status_code})")
        if 500 <= response.status_code < 600:
            raise TeamsError(f"Teams indisponível (HTTP {response.status_code})")
        raise TeamsError(f"Resposta HTTP inesperada do Teams ({response.status_code})")

