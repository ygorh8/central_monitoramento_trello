# Arquitetura

## Decisao

A aplicacao externa Python e o componente operacional principal. Ela substitui o polling feito por um agente de IA e pode rodar em Windows, Linux, Docker ou plataforma de containers.

## Componentes

- `JenkinsReadOnlyClient`: inventario e logs via REST, sem alterar jobs/builds;
- `jenkins_monitor`: compara snapshots e persiste transicoes;
- `SuiteVisibilityService`: confirma eventos, resolve bots e orquestra Trello;
- `TrelloClient`: busca por marcadores exatos e cria cartoes idempotentes;
- `APScheduler`: dispara o fluxo no intervalo configurado;
- `service_status.json`: healthcheck observavel para container/systemd.

## Estado

`runtime/jenkins_job_state.json` e a fonte de idempotencia. A primeira execucao cria uma linha de base sem importar os jobs historicamente desabilitados nem builds antigas. O arquivo deve ficar em volume persistente e ter backup operacional.

## Deteccao

O monitor considera dois sinais:

1. `JOB_DISABLED`: `buildable` muda de verdadeiro para falso;
2. `BUILD_ABORTED`: `lastCompletedBuild` muda para uma build `ABORTED` e o console contem `Aborted by`.

O uso de `lastCompletedBuild` evita perder um cancelamento quando uma build nova comeca antes da proxima consulta.

## Idempotencia e falhas

- URL do job e URL da build sao marcadores exatos no cartao;
- cartao existente e reconhecido antes de qualquer criacao;
- acknowledgement ocorre somente depois que o Trello retorna uma URL;
- falhas Jenkins/Trello mantem o evento pendente para a proxima execucao;
- `max_instances=1` impede polls concorrentes no mesmo processo.

## Limites

- o repositorio de suites deve estar disponivel para resolver os bots;
- o estado JSON pressupoe uma unica instancia ativa;
- para alta disponibilidade com varias replicas, migrar o estado para PostgreSQL/Redis e usar lock distribuido.
