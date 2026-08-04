# Suite Visibility

Servico Python autonomo que monitora o Jenkins e cria cartoes no Trello quando:

- um job ativo passa a desabilitado; ou
- uma build e cancelada manualmente (`ABORTED` + `Aborted by` no console).

O monitor consulta `lastCompletedBuild`, portanto continua detectando a build cancelada mesmo quando o Jenkins inicia uma execucao nova imediatamente. O estado persistido evita duplicidade. O Microsoft Teams permanece fora do fluxo atual.

## Fluxo

```text
APScheduler (30 segundos, 07h-19h)
        -> Jenkins REST API (somente leitura)
        -> estado persistido em runtime/
        -> confirma cancelamento manual
        -> resolve manifesto e bots
        -> procura/cria cartao via Trello REST API
        -> confirma o evento para nao duplicar
```

## Desenvolvimento no Windows

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest
```

O token Jenkins pode ser salvo no Gerenciador de Credenciais:

```powershell
.\.venv\Scripts\python.exe scripts\store_jenkins_token_once.py
```

Chave e token Trello podem ser armazenados da mesma forma:

```powershell
.\.venv\Scripts\python.exe scripts\store_trello_credentials_once.py
```

Copie `.env.example` para `.env` apenas para desenvolvimento. O arquivo `.env` e ignorado pelo Git. Em producao, use secrets do servidor ou da plataforma.

## Comandos

Executar uma verificacao completa, inclusive fora da janela de horario:

```powershell
python -m suite_visibility.cli monitor-once --force
```

Iniciar o servico em primeiro plano:

```powershell
python -m suite_visibility.cli serve
```

Verificar a saude do processo:

```powershell
python -m suite_visibility.cli healthcheck
```

Depois de validar `monitor-once --force`, instale o servico local no Agendador de Tarefas:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1
```

Ele inicia no logon do usuario e reinicia automaticamente em caso de falha. Para remover:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_windows_task.ps1
```

Os comandos antigos de diagnostico e inventario continuam disponiveis em `python -m suite_visibility.cli --help`.

## Configuracao principal

| Variavel | Descricao |
|---|---|
| `JENKINS_URL` | URL raiz do Jenkins |
| `JENKINS_USERNAME` | Usuario somente leitura |
| `JENKINS_API_TOKEN` | Token; opcional no Windows quando salvo no keyring |
| `TRELLO_API_KEY` / `TRELLO_API_TOKEN` | Credenciais da API Trello |
| `TRELLO_BOARD_ID` | ID do quadro `Poc_Suite` |
| `TRELLO_PAUSED_LIST_ID` | ID da lista `Tarefas` |
| `SUITE_REPOSITORY_PATH` | Repositorio que contem `suites/*.json` |
| `MONITOR_INTERVAL_SECONDS` | Intervalo, padrao 30 segundos |
| `MONITOR_TIMEZONE` | Padrao `America/Sao_Paulo` |
| `MONITOR_START_HOUR` / `MONITOR_END_HOUR` | Janela 07h-19h |

Consulte [docs/DEPLOY.md](docs/DEPLOY.md) para Docker, Linux/systemd e estrategia de corte.

## Seguranca

- Jenkins e acessado apenas por `GET`/`HEAD`.
- Tokens nunca sao gravados no Git, no estado ou nos logs.
- O container roda com usuario sem privilegios.
- `runtime/` precisa de volume persistente em producao.
- A aplicacao nao desabilita jobs nem cancela builds.
