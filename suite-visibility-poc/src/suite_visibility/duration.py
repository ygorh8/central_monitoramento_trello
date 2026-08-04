"""Cálculo de indisponibilidade com datas conscientes de timezone."""

from __future__ import annotations

from datetime import datetime


def require_timezone(value: datetime, field_name: str = "datetime") -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} deve conter timezone explícito")


def downtime_minutes(paused_at: datetime, returned_at: datetime) -> int:
    require_timezone(paused_at, "paused_at")
    require_timezone(returned_at, "returned_at")
    seconds = (returned_at - paused_at).total_seconds()
    if seconds < 0:
        raise ValueError("returned_at não pode ser anterior a paused_at")
    return int(seconds // 60)


def format_duration(minutes: int) -> str:
    if minutes < 0:
        raise ValueError("minutes não pode ser negativo")
    hours, remainder = divmod(minutes, 60)
    if hours:
        return f"{hours}h{remainder:02d}min"
    return f"{remainder}min"

