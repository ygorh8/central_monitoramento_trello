"""Credential storage backed by the operating-system keyring."""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError


JENKINS_SERVICE_NAME = "suite-visibility-poc/jenkins"
TRELLO_SERVICE_NAME = "suite-visibility-poc/trello"


def store_jenkins_token(username: str, token: str) -> None:
    if not username.strip() or not token.strip():
        raise ValueError("Usuario e token Jenkins sao obrigatorios")
    keyring.set_password(JENKINS_SERVICE_NAME, username, token.strip())


def get_jenkins_token(username: str | None) -> str | None:
    if not username:
        return None
    try:
        return keyring.get_password(JENKINS_SERVICE_NAME, username)
    except KeyringError:
        return None


def store_trello_credentials(api_key: str, api_token: str) -> None:
    if not api_key.strip() or not api_token.strip():
        raise ValueError("Chave e token Trello sao obrigatorios")
    keyring.set_password(TRELLO_SERVICE_NAME, "api_key", api_key.strip())
    keyring.set_password(TRELLO_SERVICE_NAME, "api_token", api_token.strip())


def get_trello_credentials() -> tuple[str | None, str | None]:
    try:
        return (
            keyring.get_password(TRELLO_SERVICE_NAME, "api_key"),
            keyring.get_password(TRELLO_SERVICE_NAME, "api_token"),
        )
    except KeyringError:
        return None, None
