"""Persist Jenkins job state and surface pause transitions for Trello."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .jenkins_client import JenkinsJob


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def monitor_jobs(
    jobs: list[JenkinsJob],
    state_path: Path,
    *,
    include_initial_paused: bool = False,
    reset_baseline: bool = False,
) -> dict[str, object]:
    previous: dict[str, object] = {}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
    old_jobs = {} if reset_baseline else (previous.get("jobs", {}) if isinstance(previous, dict) else {})
    now = datetime.now(timezone.utc).isoformat()
    current: dict[str, dict[str, object]] = {}
    pending: list[dict[str, object]] = []

    for job in jobs:
        old = old_jobs.get(job.url) if isinstance(old_jobs, dict) else None
        old_paused = old.get("paused") if isinstance(old, dict) else None
        old_pending = bool(old.get("pending_trello")) if isinstance(old, dict) else False
        became_paused = job.paused and not reset_baseline and (old_paused is False or (old is None and include_initial_paused))
        completed_build_number = job.last_completed_build_number
        completed_build_result = job.last_completed_build_result
        completed_build_url = job.last_completed_build_url
        completed_build_timestamp = job.last_completed_build_timestamp
        old_build_number = old.get("last_completed_build_number") if isinstance(old, dict) else None
        old_build_result = old.get("last_completed_build_result") if isinstance(old, dict) else None
        new_manual_abort_candidate = bool(
            not reset_baseline
            and old_build_number is not None
            and completed_build_result == "ABORTED"
            and (completed_build_number != old_build_number or old_build_result != "ABORTED")
        )
        new_signal = "JOB_DISABLED" if became_paused else ("BUILD_ABORTED" if new_manual_abort_candidate else None)
        pending_trello = bool(new_signal or old_pending)
        event_build_number = completed_build_number if new_manual_abort_candidate else (
            old.get("event_build_number") if old_pending and isinstance(old, dict) else None
        )
        event_build_url = completed_build_url if new_manual_abort_candidate else (
            old.get("event_build_url") if old_pending and isinstance(old, dict) else None
        )
        event_build_timestamp = completed_build_timestamp if new_manual_abort_candidate else (
            old.get("event_build_timestamp") if old_pending and isinstance(old, dict) else None
        )
        record = {
            **asdict(job),
            "paused": job.paused,
            "pending_trello": pending_trello,
            "pause_signal": new_signal or (old.get("pause_signal") if old_pending and isinstance(old, dict) else None),
            "paused_detected_at": now if became_paused else (old.get("paused_detected_at") if isinstance(old, dict) else None),
            "event_detected_at": now if new_signal else (old.get("event_detected_at") if old_pending and isinstance(old, dict) else None),
            "event_build_number": event_build_number,
            "event_build_url": event_build_url,
            "event_build_timestamp": event_build_timestamp,
            "trello_card_url": old.get("trello_card_url") if isinstance(old, dict) else None,
        }
        current[job.url] = record
        if pending_trello:
            pending.append(record)

    _write_state(state_path, {"updated_at": now, "jobs": current})
    return {"updated_at": now, "total_jobs": len(jobs), "paused_jobs": sum(job.paused for job in jobs), "pending_paused": pending}


def acknowledge_trello_card(state_path: Path, job_url: str, card_url: str) -> None:
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    job = payload.get("jobs", {}).get(job_url)
    if not isinstance(job, dict):
        raise KeyError("Job nao encontrado no estado")
    job["pending_trello"] = False
    job["trello_card_url"] = card_url
    job["trello_card_created_at"] = datetime.now(timezone.utc).isoformat()
    _write_state(state_path, payload)


def ignore_jenkins_event(state_path: Path, job_url: str, reason: str) -> None:
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    job = payload.get("jobs", {}).get(job_url)
    if not isinstance(job, dict):
        raise KeyError("Job nao encontrado no estado")
    job["pending_trello"] = False
    job["ignored_reason"] = reason
    job["ignored_at"] = datetime.now(timezone.utc).isoformat()
    _write_state(state_path, payload)
