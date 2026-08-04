"""Resolve the Bxxx test bots listed by a Jenkins suite manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

import requests

from .jenkins_client import JenkinsApiError


BOT_PATTERN = re.compile(r"(?:^|[/_])(?:test_)?B(\d{3,4})(?:_|\b)", re.IGNORECASE)


def suite_manifest_from_config(
    job_url: str,
    *,
    username: str | None,
    api_token: str | None,
    timeout: float = 20,
    session=None,
) -> str:
    client = session or requests.Session()
    kwargs: dict[str, object] = {"timeout": timeout}
    if username and api_token:
        kwargs["auth"] = (username, api_token)
    response = client.get(f"{job_url.rstrip('/')}/config.xml", **kwargs)
    if response.status_code in (401, 403):
        raise JenkinsApiError(f"Config do job exige autorizacao (HTTP {response.status_code})")
    if not 200 <= response.status_code < 300:
        raise JenkinsApiError(f"Falha ao ler config do job (HTTP {response.status_code})")
    try:
        root = ElementTree.fromstring(response.text)
    except ElementTree.ParseError as exc:
        raise JenkinsApiError("Config XML invalida no Jenkins") from exc
    candidates: list[str] = []
    for element in root.iter():
        value = (element.text or "").strip()
        if value.lower().endswith(".json") and "/" not in value and "\\" not in value:
            candidates.append(value)
    if not candidates:
        raise JenkinsApiError("Job nao informa um manifesto JSON de suite")
    return candidates[0]


def bots_from_manifest(repo_path: Path, manifest_name: str) -> list[int]:
    safe_name = PurePosixPath(manifest_name).name
    manifest_path = repo_path / "suites" / safe_name
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise JenkinsApiError(f"Manifesto de suite nao encontrado: {safe_name}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JenkinsApiError(f"Manifesto de suite invalido: {safe_name}") from exc
    bots: list[int] = []
    for entry in entries if isinstance(entries, list) else []:
        path = str(entry.get("path", "")) if isinstance(entry, dict) else ""
        match = BOT_PATTERN.search(path)
        if match:
            bot = int(match.group(1))
            if bot not in bots:
                bots.append(bot)
    return bots
