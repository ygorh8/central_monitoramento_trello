# Implantacao

## Pre-requisitos

- Python 3.11+ ou Docker;
- acesso de rede do servidor ao Jenkins e ao Trello;
- usuario/token Jenkins somente leitura;
- chave/token da API Trello;
- copia ou clone somente leitura do repositorio que contem `suites/*.json`;
- diretorio persistente para `runtime/`.

## Docker

1. Copie `.env.example` para `.env` e preencha os valores no servidor.
2. Nao versione `.env`.
3. Em `compose.yaml`, monte o repositorio de suites em `/suite-repo:ro`.
4. Execute:

```bash
docker compose build
docker compose up -d
docker compose logs -f suite-visibility
docker compose ps
```

O volume `./runtime:/app/runtime` preserva a linha de base e os acknowledgements. Em uma plataforma gerenciada, substitua `.env` pelo mecanismo de secrets e use um volume persistente equivalente.

## Linux com systemd

```bash
sudo useradd --system --home /opt/suite-visibility suite-visibility
sudo mkdir -p /opt/suite-visibility/runtime
sudo chown -R suite-visibility:suite-visibility /opt/suite-visibility
python3 -m venv /opt/suite-visibility/.venv
/opt/suite-visibility/.venv/bin/pip install /opt/suite-visibility
sudo install -m 0644 deploy/systemd/suite-visibility.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now suite-visibility
```

Crie `/etc/suite-visibility.env` com permissao `0600` e proprietario `root`. Nao coloque esse arquivo no repositorio.

## Primeiro start e corte

1. Execute `monitor-once --force`. Sem estado anterior, a primeira execucao cria apenas a linha de base e nao importa jobs/builds antigos.
2. Cancele manualmente uma suite de teste.
3. Confirme o cartao, bots, URL da build e responsavel.
4. Reinicie o processo e confirme que o cartao nao duplica.
5. Verifique `healthcheck` e os logs.
6. Somente depois pause a automacao equivalente no Codex.

Durante a validacao, evite manter os dois monitores criando cartoes simultaneamente. A URL exata da build reduz duplicidade, mas o corte deve ser feito logo apos o teste aprovado.

## Backup e atualizacao

- Inclua `runtime/jenkins_job_state.json` no backup operacional.
- Nunca inclua `.env` em imagens, artefatos ou backups nao criptografados.
- Antes de atualizar, rode os testes e mantenha a versao anterior da imagem para rollback.
