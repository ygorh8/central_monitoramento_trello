"""Autonomous Jenkins-to-Trello monitoring service."""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings
from .jenkins_client import JenkinsApiError, JenkinsReadOnlyClient
from .jenkins_monitor import acknowledge_trello_card, ignore_jenkins_event, mark_trello_card_completed, monitor_jobs
from .suite_bot_mapper import bots_from_manifest, suite_manifest_from_config
from .trello_client import TrelloClient, TrelloError


LOGGER = logging.getLogger("suite_visibility.service")


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _display_time(value: str | None, timezone_name: str) -> str:
    parsed = datetime.fromisoformat(value) if value else datetime.now(timezone.utc)
    return parsed.astimezone(ZoneInfo(timezone_name)).strftime("%d/%m/%Y %H:%M:%S")


class SuiteVisibilityService:
    def __init__(
        self,
        settings: Settings,
        *,
        jenkins_client: JenkinsReadOnlyClient | None = None,
        trello_client: TrelloClient | None = None,
    ) -> None:
        self.settings = settings
        self.state_path = Path(settings.monitor_state_file)
        self.status_path = Path(settings.monitor_status_file)
        self.reconciliation_status_path = Path(settings.reconciliation_status_file)
        self._state_lock = threading.Lock()
        self.repository_path = Path(settings.suite_repository_path) if settings.suite_repository_path else None
        self.jenkins = jenkins_client or JenkinsReadOnlyClient(
            timeout=settings.http_timeout_seconds,
            username=settings.jenkins_username,
            api_token=settings.jenkins_api_token,
        )
        self.trello = trello_client or TrelloClient(
            settings.trello_api_key,
            settings.trello_api_token,
            settings.trello_board_id,
            timeout=settings.http_timeout_seconds,
        )

    def _in_operating_window(self, now: datetime | None = None) -> bool:
        local_now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(self.settings.monitor_timezone))
        return self.settings.monitor_start_hour <= local_now.hour < self.settings.monitor_end_hour

    def _write_status(self, *, ok: bool, state: str, details: dict[str, object]) -> dict[str, object]:
        payload: dict[str, object] = {
            "ok": ok,
            "state": state,
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        _write_json_atomic(self.status_path, payload)
        return payload

    def _map_bots(self, job_url: str) -> tuple[str | None, list[int], str | None]:
        try:
            manifest = suite_manifest_from_config(
                job_url,
                username=self.settings.jenkins_username,
                api_token=self.settings.jenkins_api_token,
                timeout=self.settings.http_timeout_seconds,
            )
            if self.repository_path is None:
                return manifest, [], "SUITE_REPOSITORY_PATH nao configurado"
            return manifest, bots_from_manifest(self.repository_path, manifest), None
        except JenkinsApiError as exc:
            return None, [], str(exc)

    def _process_event(self, event: dict[str, object]) -> dict[str, object]:
        job_url = str(event["url"])
        job_name = str(event["name"])
        signal = str(event.get("pause_signal") or "JOB_DISABLED")
        build_url = str(event.get("event_build_url")) if event.get("event_build_url") else None
        aborted_by: str | None = None

        if signal == "BUILD_ABORTED":
            if not build_url:
                raise JenkinsApiError("Evento BUILD_ABORTED sem URL do build")
            abort_info = self.jenkins.get_abort_info(build_url)
            if not abort_info.get("confirmed_manual_abort"):
                ignore_jenkins_event(self.state_path, job_url, "ABORT_NOT_MANUAL")
                return {"job": job_name, "action": "ignored", "reason": "ABORT_NOT_MANUAL"}
            aborted_by = str(abort_info.get("aborted_by") or "Nao identificado")

        manifest, bots, mapping_warning = self._map_bots(job_url)
        card = self.trello.find_jenkins_pause_card(job_url, build_url)
        created = card is None
        if card is None:
            card = self.trello.create_jenkins_pause_card(
                list_id=str(self.settings.trello_paused_list_id),
                job_name=job_name,
                job_url=job_url,
                signal=signal,
                detected_at=_display_time(
                    str(event.get("event_detected_at") or event.get("paused_detected_at") or ""),
                    self.settings.monitor_timezone,
                ),
                manifest=manifest,
                bots=bots,
                build_url=build_url,
                aborted_by=aborted_by,
            )
        card_url = card.get("url") or card.get("shortUrl")
        if not card_url:
            raise TrelloError("Trello nao retornou URL do cartao")
        acknowledge_trello_card(self.state_path, job_url, str(card_url))
        result: dict[str, object] = {
            "job": job_name,
            "action": "created" if created else "existing",
            "card_url": card_url,
            "bots": bots,
        }
        if mapping_warning:
            result["mapping_warning"] = mapping_warning
        return result

    def run_once(self, *, force: bool = False) -> dict[str, object]:
        with self._state_lock:
            return self._run_once_locked(force=force)

    def _run_once_locked(self, *, force: bool = False) -> dict[str, object]:
        missing = self.settings.validate_monitor()
        if missing:
            return self._write_status(
                ok=False,
                state="configuration_error",
                details={"missing": missing, "processed": [], "errors": []},
            )
        if not force and not self._in_operating_window():
            return self._write_status(ok=True, state="outside_operating_window", details={"processed": [], "errors": []})

        try:
            jobs = self.jenkins.list_jobs(str(self.settings.jenkins_url))
            monitor_result = monitor_jobs(jobs, self.state_path)
        except (JenkinsApiError, OSError, ValueError, json.JSONDecodeError) as exc:
            LOGGER.exception("Falha ao consultar o Jenkins")
            return self._write_status(
                ok=False,
                state="jenkins_error",
                details={"error": str(exc), "processed": [], "errors": []},
            )

        processed: list[dict[str, object]] = []
        errors: list[dict[str, str]] = []
        for event in monitor_result["pending_paused"]:
            try:
                processed.append(self._process_event(event))
            except (JenkinsApiError, TrelloError, OSError, ValueError, KeyError) as exc:
                LOGGER.exception("Evento pendente mantido para nova tentativa: %s", event.get("name"))
                errors.append({"job": str(event.get("name")), "error": str(exc)})

        return self._write_status(
            ok=not errors,
            state="ok" if not errors else "degraded",
            details={
                "total_jobs": monitor_result["total_jobs"],
                "disabled_jobs": monitor_result["paused_jobs"],
                "pending_events": len(monitor_result["pending_paused"]),
                "processed": processed,
                "errors": errors,
            },
        )

    @staticmethod
    def _incident_from_card(card: dict[str, object]) -> tuple[str | None, int | None, str | None]:
        description = str(card.get("desc") or "")
        signal_match = re.search(r"(?m)^Sinal:\s*(\S+)", description)
        build_match = re.search(r"(?m)^Build:\s*(\S+)", description)
        build_url = build_match.group(1) if build_match else None
        number_match = re.search(r"/(\d+)/?$", build_url or "")
        build_number = int(number_match.group(1)) if number_match else None
        return signal_match.group(1) if signal_match else None, build_number, build_url

    @staticmethod
    def _has_recovered(job, signal: str | None, event_build_number: int | None) -> bool:
        if signal == "JOB_DISABLED":
            return not job.paused
        if signal == "BUILD_ABORTED" and event_build_number is not None:
            current_number = job.last_build_number
            return bool(
                not job.paused
                and current_number is not None
                and current_number > event_build_number
                and job.last_build_result != "ABORTED"
            )
        return False

    def reconcile_cards(self, *, force: bool = False) -> dict[str, object]:
        with self._state_lock:
            if not force and not self._in_operating_window():
                result = {"ok": True, "state": "outside_operating_window", "checked": 0, "completed": [], "errors": []}
                _write_json_atomic(self.reconciliation_status_path, {"last_run_at": datetime.now(timezone.utc).isoformat(), **result})
                return result
            try:
                jobs = self.jenkins.list_jobs(str(self.settings.jenkins_url))
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (JenkinsApiError, OSError, ValueError, json.JSONDecodeError) as exc:
                result = {"ok": False, "state": "jenkins_or_state_error", "error": str(exc), "checked": 0, "completed": [], "errors": []}
                _write_json_atomic(self.reconciliation_status_path, {"last_run_at": datetime.now(timezone.utc).isoformat(), **result})
                return result

            current_by_url = {job.url: job for job in jobs}
            completed: list[dict[str, object]] = []
            errors: list[dict[str, str]] = []
            checked = 0
            for job_url, record in payload.get("jobs", {}).items():
                if not isinstance(record, dict) or not record.get("trello_card_url") or record.get("trello_completed_at"):
                    continue
                current = current_by_url.get(job_url)
                if current is None:
                    continue
                checked += 1
                try:
                    card = self.trello.get_card(str(record["trello_card_url"]))
                    signal = record.get("tracked_pause_signal")
                    build_number = record.get("tracked_event_build_number")
                    build_url = record.get("tracked_event_build_url")
                    if not signal:
                        signal, parsed_number, parsed_url = self._incident_from_card(card)
                        build_number = build_number if build_number is not None else parsed_number
                        build_url = build_url or parsed_url
                    if card.get("dueComplete") is True:
                        mark_trello_card_completed(
                            self.state_path,
                            job_url,
                            pause_signal=str(signal) if signal else None,
                            event_build_number=int(build_number) if build_number is not None else None,
                            event_build_url=str(build_url) if build_url else None,
                        )
                        completed.append({"job": current.name, "card_url": record["trello_card_url"], "action": "already_complete"})
                        continue
                    if not self._has_recovered(current, str(signal) if signal else None, int(build_number) if build_number is not None else None):
                        continue
                    trello_result = self.trello.mark_card_complete(str(record["trello_card_url"]))
                    mark_trello_card_completed(
                        self.state_path,
                        job_url,
                        pause_signal=str(signal) if signal else None,
                        event_build_number=int(build_number) if build_number is not None else None,
                        event_build_url=str(build_url) if build_url else None,
                    )
                    completed.append({
                        "job": current.name,
                        "card_url": record["trello_card_url"],
                        "action": "completed" if trello_result.get("changed") else "already_complete",
                    })
                except (TrelloError, OSError, ValueError, KeyError) as exc:
                    errors.append({"job": str(record.get("name") or job_url), "error": str(exc)})

            result = {"ok": not errors, "state": "ok" if not errors else "degraded", "checked": checked, "completed": completed, "errors": errors}
            _write_json_atomic(self.reconciliation_status_path, {"last_run_at": datetime.now(timezone.utc).isoformat(), **result})
            return result


def healthcheck(settings: Settings) -> tuple[bool, dict[str, object]]:
    path = Path(settings.monitor_status_file)
    if not path.exists():
        return False, {"ok": False, "reason": "status_file_missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        last_run = datetime.fromisoformat(str(payload["last_run_at"]))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return False, {"ok": False, "reason": "status_file_invalid", "error": str(exc)}
    age = (datetime.now(timezone.utc) - last_run.astimezone(timezone.utc)).total_seconds()
    healthy = bool(payload.get("ok")) and age <= settings.health_max_age_seconds
    return healthy, {**payload, "age_seconds": round(age, 1)}


def run_scheduler(settings: Settings) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    log_path = Path(settings.monitor_status_file).with_name("service.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(log_path, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )
    service = SuiteVisibilityService(settings)
    scheduler = BlockingScheduler(timezone=ZoneInfo(settings.monitor_timezone))

    def scheduled_run() -> None:
        result = service.run_once()
        level = logging.INFO if result.get("ok") else logging.ERROR
        LOGGER.log(level, "Monitor executado: %s", json.dumps(result, ensure_ascii=False))

    scheduler.add_job(
        scheduled_run,
        "interval",
        seconds=settings.monitor_interval_seconds,
        next_run_time=datetime.now(ZoneInfo(settings.monitor_timezone)),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=max(settings.monitor_interval_seconds, 10),
        id="jenkins-to-trello",
    )
    scheduler.add_job(
        lambda: LOGGER.info("Reconciliacao executada: %s", json.dumps(service.reconcile_cards(), ensure_ascii=False)),
        "interval",
        seconds=settings.reconciliation_interval_seconds,
        next_run_time=datetime.now(ZoneInfo(settings.monitor_timezone)) + timedelta(seconds=settings.reconciliation_interval_seconds),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=max(settings.reconciliation_interval_seconds, 60),
        id="jenkins-trello-reconciliation",
    )
    LOGGER.info("Servico iniciado; intervalo=%ss", settings.monitor_interval_seconds)
    scheduler.start()
