"""Credential storage backed by the operating-system keyring."""

from __future__ import annotations

import re

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
    clean_key = api_key.strip()
    clean_token = api_token.strip()
    if not clean_key or not clean_token:
        raise ValueError("Chave e token Trello sao obrigatorios")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", clean_key):
        raise ValueError("A API key Trello deve conter exatamente 32 caracteres hexadecimais; nao cole uma URL")
    keyring.set_password(TRELLO_SERVICE_NAME, "api_key", clean_key)
    keyring.set_password(TRELLO_SERVICE_NAME, "api_token", clean_token)


def get_trello_credentials() -> tuple[str | None, str | None]:
    try:
        return (
            keyring.get_password(TRELLO_SERVICE_NAME, "api_key"),
            keyring.get_password(TRELLO_SERVICE_NAME, "api_token"),
        )
    except KeyringError:
        return None, None
