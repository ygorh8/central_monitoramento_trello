"""Modelo validado e serializável do evento operacional."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum

from .duration import downtime_minutes, require_timezone


class EventType(StrEnum):
    SUITE_PAUSED = "SUITE_PAUSED"
    SUITE_UPDATED = "SUITE_UPDATED"
    SUITE_RESUMED = "SUITE_RESUMED"
    RETURN_OVERDUE = "RETURN_OVERDUE"


class Status(StrEnum):
    ACTIVE = "ATIVA"
    PAUSED = "PAUSADA"
    MAINTENANCE = "EM_MANUTENCAO"
    WAITING_DATA = "AGUARDANDO_MASSA"
    WAITING_DEVICE = "AGUARDANDO_DEVICE"
    WAITING_ENVIRONMENT = "AGUARDANDO_AMBIENTE"
    WAITING_FIX = "AGUARDANDO_CORRECAO"
    WAITING_VALIDATION = "AGUARDANDO_VALIDACAO"


class Platform(StrEnum):
    ANDROID = "ANDROID"
    IOS = "IOS"
    WEB = "WEB"


SECRET_FIELD_PATTERN = re.compile(r"(token|secret|password|webhook|api[_-]?key)", re.I)


@dataclass
class SuiteEvent:
    event: EventType
    suite: str
    platform: Platform
    status: Status
    reason: str
    description: str
    responsible: str
    paused_by: str
    paused_at: datetime
    expected_return_at: datetime | None
    returned_at: datetime | None = None
    downtime_minutes: int | None = None
    jenkins_job: str | None = None
    jenkins_build: str | None = None
    jenkins_url: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        self.event = EventType(self.event)
        self.platform = Platform(self.platform)
        self.status = Status(self.status)
        for field_name in ("suite", "reason", "description", "responsible", "paused_by"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} é obrigatório")
        require_timezone(self.paused_at, "paused_at")
        for field_name in ("expected_return_at", "returned_at"):
            value = getattr(self, field_name)
            if value is not None:
                require_timezone(value, field_name)
        if self.returned_at is not None:
            calculated = downtime_minutes(self.paused_at, self.returned_at)
            if self.downtime_minutes is None:
                self.downtime_minutes = calculated
            elif self.downtime_minutes != calculated:
                raise ValueError("downtime_minutes diverge das datas informadas")
        self._reject_secret_like_values()

    @property
    def suite_id(self) -> str:
        normalized = unicodedata.normalize("NFKD", self.suite).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
        return f"{slug}-{self.platform.value.lower()}"

    def _reject_secret_like_values(self) -> None:
        for key, value in asdict(self).items():
            if value and SECRET_FIELD_PATTERN.search(key):
                raise ValueError(f"campo secreto não é permitido no payload: {key}")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in asdict(self).items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, StrEnum):
                result[key] = value.value
            else:
                result[key] = value
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

