"""Configuração exclusivamente por ambiente, sem imprimir segredos."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .secret_store import get_jenkins_token, get_trello_credentials


@dataclass(frozen=True)
class Settings:
    jenkins_url: str | None
    jenkins_username: str | None
    jenkins_api_token: str | None
    teams_webhook_url: str | None
    trello_api_key: str | None
    trello_api_token: str | None
    trello_board_id: str | None
    trello_paused_list_id: str | None
    trello_maintenance_list_id: str | None
    trello_resumed_list_id: str | None
    http_timeout_seconds: float = 15.0
    run_external_tests: bool = False
    suite_repository_path: str = ""
    monitor_state_file: str = "runtime/jenkins_job_state.json"
    monitor_status_file: str = "runtime/service_status.json"
    reconciliation_status_file: str = "runtime/reconciliation_status.json"
    monitor_interval_seconds: int = 30
    reconciliation_interval_seconds: int = 3600
    monitor_timezone: str = "America/Sao_Paulo"
    monitor_start_hour: int = 7
    monitor_end_hour: int = 19
    health_max_age_seconds: int = 180
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        # Variaveis do processo prevalecem sobre os valores locais do .env.
        load_dotenv(override=False)
        jenkins_username = os.getenv("JENKINS_USERNAME") or None
        stored_trello_key, stored_trello_token = get_trello_credentials()
        return cls(
            jenkins_url=os.getenv("JENKINS_URL") or None,
            jenkins_username=jenkins_username,
            jenkins_api_token=os.getenv("JENKINS_API_TOKEN") or get_jenkins_token(jenkins_username),
            teams_webhook_url=os.getenv("TEAMS_WEBHOOK_URL") or None,
            trello_api_key=os.getenv("TRELLO_API_KEY") or stored_trello_key,
            trello_api_token=os.getenv("TRELLO_API_TOKEN") or stored_trello_token,
            trello_board_id=os.getenv("TRELLO_BOARD_ID") or None,
            trello_paused_list_id=os.getenv("TRELLO_PAUSED_LIST_ID") or None,
            trello_maintenance_list_id=os.getenv("TRELLO_MAINTENANCE_LIST_ID") or None,
            trello_resumed_list_id=os.getenv("TRELLO_RESUMED_LIST_ID") or None,
            http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")),
            run_external_tests=os.getenv("RUN_EXTERNAL_TESTS", "false").lower() == "true",
            suite_repository_path=os.getenv("SUITE_REPOSITORY_PATH", ""),
            monitor_state_file=os.getenv("MONITOR_STATE_FILE", "runtime/jenkins_job_state.json"),
            monitor_status_file=os.getenv("MONITOR_STATUS_FILE", "runtime/service_status.json"),
            reconciliation_status_file=os.getenv("RECONCILIATION_STATUS_FILE", "runtime/reconciliation_status.json"),
            monitor_interval_seconds=int(os.getenv("MONITOR_INTERVAL_SECONDS", "30")),
            reconciliation_interval_seconds=int(os.getenv("RECONCILIATION_INTERVAL_SECONDS", "3600")),
            monitor_timezone=os.getenv("MONITOR_TIMEZONE", "America/Sao_Paulo"),
            monitor_start_hour=int(os.getenv("MONITOR_START_HOUR", "7")),
            monitor_end_hour=int(os.getenv("MONITOR_END_HOUR", "19")),
            health_max_age_seconds=int(os.getenv("HEALTH_MAX_AGE_SECONDS", "180")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate_monitor(self) -> list[str]:
        missing = []
        for name, value in (
            ("JENKINS_URL", self.jenkins_url),
            ("JENKINS_USERNAME", self.jenkins_username),
            ("JENKINS_API_TOKEN", self.jenkins_api_token),
            ("TRELLO_API_KEY", self.trello_api_key),
            ("TRELLO_API_TOKEN", self.trello_api_token),
            ("TRELLO_BOARD_ID", self.trello_board_id),
            ("TRELLO_PAUSED_LIST_ID", self.trello_paused_list_id),
        ):
            if not value:
                missing.append(name)
        if self.monitor_interval_seconds < 5:
            missing.append("MONITOR_INTERVAL_SECONDS>=5")
        if self.reconciliation_interval_seconds < 60:
            missing.append("RECONCILIATION_INTERVAL_SECONDS>=60")
        if not 0 <= self.monitor_start_hour < self.monitor_end_hour <= 24:
            missing.append("MONITOR_START_HOUR/MONITOR_END_HOUR")
        return missing
