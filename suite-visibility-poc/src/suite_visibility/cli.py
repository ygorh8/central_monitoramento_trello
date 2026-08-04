"""CLI local. Nenhum comando envia dados sem opção e configuração explícitas."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .config import Settings
from .jenkins_client import JenkinsApiError, JenkinsReadOnlyClient
from .jenkins_monitor import acknowledge_trello_card, ignore_jenkins_event, monitor_jobs
from .models import EventType, Platform, Status, SuiteEvent
from .service import SuiteVisibilityService, healthcheck, run_scheduler
from .suite_bot_mapper import bots_from_manifest, suite_manifest_from_config
from .teams_client import TeamsClient
from .trello_client import TrelloClient, TrelloError


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("a data deve conter timezone explícito")
    return parsed


def _event_from_args(args: argparse.Namespace) -> SuiteEvent:
    now = datetime.now().astimezone()
    if args.command == "pause":
        return SuiteEvent(
            event=EventType.SUITE_PAUSED,
            suite=args.suite,
            platform=Platform(args.platform),
            status=Status.PAUSED,
            reason=args.reason,
            description=args.description,
            responsible=args.responsible,
            paused_by=args.paused_by or args.responsible,
            paused_at=args.paused_at or now,
            expected_return_at=args.expected_return,
            jenkins_job=args.jenkins_job,
            jenkins_build=args.jenkins_build,
            jenkins_url=args.jenkins_url,
        )
    paused_at = args.paused_at or now
    return SuiteEvent(
        event=EventType.SUITE_RESUMED,
        suite=args.suite,
        platform=Platform(args.platform),
        status=Status.ACTIVE,
        reason="RETOMADA",
        description=args.notes,
        responsible=args.responsible,
        paused_by=args.paused_by or args.responsible,
        paused_at=paused_at,
        expected_return_at=None,
        returned_at=args.returned_at or now,
        notes=args.notes,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="suite-visibility")
    sub = parser.add_subparsers(dest="command", required=True)

    diagnose = sub.add_parser("diagnose-jenkins", help="HEAD somente leitura na URL informada")
    diagnose.add_argument("--url", required=True)
    diagnose.add_argument("--read-only", action="store_true", required=True)

    inventory = sub.add_parser("list-jenkins-suites", help="Lista jobs pela API REST somente leitura")
    inventory.add_argument("--url", help="Sobrescreve JENKINS_URL")

    monitor = sub.add_parser("monitor-jenkins", help="Detecta transicoes de job ativo para pausado")
    monitor.add_argument("--url", help="Sobrescreve JENKINS_URL")
    monitor.add_argument("--state-file", default="runtime/jenkins_job_state.json")
    monitor.add_argument("--include-initial-paused", action="store_true")
    monitor.add_argument("--reset-baseline", action="store_true")

    acknowledge = sub.add_parser("ack-jenkins-card", help="Confirma o cartao Trello de uma pausa")
    acknowledge.add_argument("--state-file", default="runtime/jenkins_job_state.json")
    acknowledge.add_argument("--job-url", required=True)
    acknowledge.add_argument("--card-url", required=True)

    bots = sub.add_parser("get-suite-bots", help="Lista bots Bxxx do manifesto associado ao job")
    bots.add_argument("--job-url", required=True)
    bots.add_argument("--repo-path", default=r"C:\Users\ygor.oliveira\PycharmProjects\appvivo_v2")

    abort_info = sub.add_parser("get-abort-info", help="Confirma se um build foi abortado manualmente")
    abort_info.add_argument("--build-url", required=True)

    ignore = sub.add_parser("ignore-jenkins-event", help="Confirma evento que nao representa manutencao")
    ignore.add_argument("--state-file", default="runtime/jenkins_job_state.json")
    ignore.add_argument("--job-url", required=True)
    ignore.add_argument("--reason", required=True)

    monitor_once = sub.add_parser("monitor-once", help="Executa o fluxo Jenkins para Trello uma vez")
    monitor_once.add_argument("--force", action="store_true", help="ignora apenas a janela de horario")

    sub.add_parser("serve", help="Inicia o monitor autonomo em primeiro plano")
    sub.add_parser("healthcheck", help="Valida a saude do servico pelo arquivo de status")

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--suite", required=True)
        target.add_argument("--platform", choices=[item.value for item in Platform], required=True)
        target.add_argument("--responsible", default="Não informado")
        target.add_argument("--paused-by")
        target.add_argument("--paused-at", type=parse_datetime)
        target.add_argument("--dry-run", action="store_true")
        target.add_argument("--send-teams", action="store_true", help="exige URL no ambiente; omita para apenas gerar o evento")
        target.add_argument("--send-trello", action="store_true", help="faz upsert no Trello REST; exige credenciais e lista no ambiente")

    pause = sub.add_parser("pause")
    add_common(pause)
    pause.add_argument("--reason", required=True)
    pause.add_argument("--description", default="Sem detalhes")
    pause.add_argument("--expected-return", type=parse_datetime)
    pause.add_argument("--jenkins-job")
    pause.add_argument("--jenkins-build")
    pause.add_argument("--jenkins-url")

    resume = sub.add_parser("resume")
    add_common(resume)
    resume.add_argument("--returned-at", type=parse_datetime)
    resume.add_argument("--notes", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    if args.command == "diagnose-jenkins":
        print("Modo: somente leitura")
        print(f"Destino: {args.url}")
        print("Métodos permitidos: HEAD e GET")
        print("Autenticação: não fornecida")
        diagnosis = JenkinsReadOnlyClient(timeout=settings.http_timeout_seconds).diagnose(args.url)
        print(json.dumps(diagnosis.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command in {"list-jenkins-suites", "monitor-jenkins"}:
        url = args.url or settings.jenkins_url
        if not url:
            print("JENKINS_URL nao configurada")
            return 2
        try:
            jobs = JenkinsReadOnlyClient(
                timeout=settings.http_timeout_seconds,
                username=settings.jenkins_username,
                api_token=settings.jenkins_api_token,
            ).list_jobs(url)
        except JenkinsApiError as exc:
            print(str(exc))
            return 2
        if args.command == "monitor-jenkins":
            payload = monitor_jobs(
                jobs,
                Path(args.state_file),
                include_initial_paused=args.include_initial_paused,
                reset_baseline=args.reset_baseline,
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        payload = {
            "total_suites": len(jobs),
            "paused_suites": sum(job.paused for job in jobs),
            "jobs": [
                {"name": job.name, "url": job.url, "color": job.color, "buildable": job.buildable, "paused": job.paused}
                for job in jobs
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "ack-jenkins-card":
        try:
            acknowledge_trello_card(Path(args.state_file), args.job_url, args.card_url)
        except (OSError, ValueError, KeyError) as exc:
            print(str(exc))
            return 2
        print(json.dumps({"acknowledged": True, "job_url": args.job_url, "card_url": args.card_url}, ensure_ascii=False))
        return 0

    if args.command == "get-suite-bots":
        try:
            manifest = suite_manifest_from_config(
                args.job_url,
                username=settings.jenkins_username,
                api_token=settings.jenkins_api_token,
                timeout=settings.http_timeout_seconds,
            )
            bot_ids = bots_from_manifest(Path(args.repo_path), manifest)
        except JenkinsApiError as exc:
            print(str(exc))
            return 2
        print(json.dumps({"job_url": args.job_url, "manifest": manifest, "bots": bot_ids}, ensure_ascii=False))
        return 0

    if args.command == "get-abort-info":
        try:
            info = JenkinsReadOnlyClient(
                timeout=settings.http_timeout_seconds,
                username=settings.jenkins_username,
                api_token=settings.jenkins_api_token,
            ).get_abort_info(args.build_url)
        except JenkinsApiError as exc:
            print(str(exc))
            return 2
        print(json.dumps(info, ensure_ascii=False))
        return 0

    if args.command == "ignore-jenkins-event":
        try:
            ignore_jenkins_event(Path(args.state_file), args.job_url, args.reason)
        except (OSError, ValueError, KeyError) as exc:
            print(str(exc))
            return 2
        print(json.dumps({"ignored": True, "job_url": args.job_url, "reason": args.reason}, ensure_ascii=False))
        return 0

    if args.command == "monitor-once":
        result = SuiteVisibilityService(settings).run_once(force=args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 2

    if args.command == "serve":
        missing = settings.validate_monitor()
        if missing:
            print(json.dumps({"ok": False, "missing": missing}, ensure_ascii=False))
            return 2
        try:
            run_scheduler(settings)
        except (KeyboardInterrupt, SystemExit):
            return 0
        return 0

    if args.command == "healthcheck":
        healthy, result = healthcheck(settings)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if healthy else 1

    event = _event_from_args(args)
    print(event.to_json())
    if args.send_trello:
        list_id = settings.trello_paused_list_id if event.status is Status.PAUSED else settings.trello_resumed_list_id
        if not list_id:
            print("Lista Trello do status nao configurada")
            return 2
        try:
            result = TrelloClient(
                settings.trello_api_key,
                settings.trello_api_token,
                settings.trello_board_id,
                timeout=settings.http_timeout_seconds,
            ).upsert(event, list_id, dry_run=args.dry_run)
        except TrelloError as exc:
            print(str(exc))
            return 2
        print(json.dumps(result, ensure_ascii=False))
    if args.send_teams:
        result = TeamsClient(settings.teams_webhook_url, settings.http_timeout_seconds).send(event, dry_run=args.dry_run)
        # ASCII escapado mantém o preview compatível com consoles Windows CP-1252.
        print(json.dumps(result, ensure_ascii=True))
    elif args.dry_run:
        result = TeamsClient(None, settings.http_timeout_seconds).send(event, dry_run=True)
        print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
