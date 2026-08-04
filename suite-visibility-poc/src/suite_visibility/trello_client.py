"""Cliente Trello opcional, injetável e testável com mocks."""

from __future__ import annotations

import json

import requests

from .models import Status, SuiteEvent


class TrelloError(RuntimeError):
    pass


class TrelloClient:
    def __init__(self, api_key: str | None, token: str | None, board_id: str | None, *, timeout: float = 15, base_url: str = "https://api.trello.com/1", session=None):
        self._key = api_key
        self._token = token
        self._board_id = board_id
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()

    def _auth(self) -> dict[str, str]:
        if not self._key or not self._token:
            raise TrelloError("Credenciais Trello não configuradas")
        return {"key": self._key, "token": self._token}

    def _request(self, method: str, path: str, **kwargs):
        params = {**self._auth(), **kwargs.pop("params", {})}
        try:
            response = self._session.request(method, f"{self._base_url}{path}", params=params, timeout=self._timeout, **kwargs)
        except requests.Timeout as exc:
            raise TrelloError("Timeout ao acessar o Trello") from exc
        except requests.ConnectionError as exc:
            raise TrelloError("Falha de DNS ou conexão ao acessar o Trello") from exc
        if response.status_code == 429:
            raise TrelloError("Limite de requisições do Trello excedido (HTTP 429)")
        if response.status_code in (401, 403):
            raise TrelloError(f"Autenticação Trello inválida (HTTP {response.status_code})")
        if response.status_code == 404:
            raise TrelloError("Recurso Trello não encontrado (HTTP 404)")
        if not 200 <= response.status_code < 300:
            raise TrelloError(f"Falha no Trello (HTTP {response.status_code})")
        try:
            return response.json()
        except ValueError as exc:
            raise TrelloError("Resposta JSON inválida do Trello") from exc

    def find_card(self, suite_id: str) -> dict | None:
        if not self._board_id:
            raise TrelloError("TRELLO_BOARD_ID não configurado")
        cards = self._request("GET", f"/boards/{self._board_id}/cards", params={"fields": "name,desc,idList"})
        marker = f"suite_id={suite_id}"
        return next((card for card in cards if marker in card.get("desc", "")), None)

    def find_jenkins_pause_card(self, job_url: str, build_url: str | None = None) -> dict | None:
        """Find an open card using exact Jenkins URL lines as idempotency keys."""
        if not self._board_id:
            raise TrelloError("TRELLO_BOARD_ID nao configurado")
        cards = self._request(
            "GET",
            f"/boards/{self._board_id}/cards",
            params={"fields": "name,desc,idList,url", "filter": "open"},
        )
        job_marker = f"Jenkins: {job_url}"
        build_marker = f"Build: {build_url}" if build_url else None
        for card in cards:
            lines = {line.strip() for line in str(card.get("desc", "")).splitlines()}
            if job_marker in lines and (build_marker is None or build_marker in lines):
                return card
        return None

    def create_jenkins_pause_card(
        self,
        *,
        list_id: str,
        job_name: str,
        job_url: str,
        signal: str,
        detected_at: str,
        manifest: str | None,
        bots: list[int],
        build_url: str | None = None,
        aborted_by: str | None = None,
    ) -> dict:
        bots_text = ", ".join(str(bot) for bot in bots) if bots else "NAO IDENTIFICADOS"
        lines = [
            "Status: PAUSADA",
            f"Sinal: {signal}",
            f"Bots impactados: {bots_text}",
            f"Manifesto: {manifest or 'NAO IDENTIFICADO'}",
            f"Jenkins: {job_url}",
        ]
        if build_url:
            lines.append(f"Build: {build_url}")
        lines.append(f"Pausa detectada em: {detected_at}")
        if aborted_by:
            lines.append(f"Interrompida por: {aborted_by}")
        return self._request(
            "POST",
            "/cards",
            params={
                "idList": list_id,
                "name": f"[PAUSADA] {job_name}",
                "desc": "\n".join(lines),
                "pos": "bottom",
            },
        )

    def create_card(self, event: SuiteEvent, list_id: str) -> dict:
        title = f"[{event.status.value}][{event.platform.value}] {event.suite}"
        description = f"suite_id={event.suite_id}\n\n```json\n{json.dumps(event.to_dict(), ensure_ascii=False, indent=2)}\n```"
        return self._request("POST", "/cards", params={"idList": list_id, "name": title, "desc": description})

    def update_card(self, card_id: str, event: SuiteEvent, list_id: str | None = None) -> dict:
        params = {
            "name": f"[{event.status.value}][{event.platform.value}] {event.suite}",
            "desc": f"suite_id={event.suite_id}\n\n```json\n{json.dumps(event.to_dict(), ensure_ascii=False, indent=2)}\n```",
        }
        if list_id:
            params["idList"] = list_id
        return self._request("PUT", f"/cards/{card_id}", params=params)

    def add_comment(self, card_id: str, text: str) -> dict:
        return self._request("POST", f"/cards/{card_id}/actions/comments", params={"text": text})

    def upsert(self, event: SuiteEvent, list_id: str, *, dry_run: bool = False) -> dict:
        if dry_run:
            return {"changed": False, "dry_run": True, "suite_id": event.suite_id}
        card = self.find_card(event.suite_id)
        if card:
            result = self.update_card(card["id"], event, list_id)
            return {"created": False, "card": result}
        result = self.create_card(event, list_id)
        return {"created": True, "card": result}
