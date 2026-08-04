# Diagnóstico da integração

## Resumo executivo

Em 04/08/2026, a raiz pública `http://147.93.6.174:8080/` respondeu ao método `HEAD` com HTTP 403 em 0,354 s. A conexão TCP à porta 8080 também foi concluída. Os cabeçalhos `X-Jenkins: 2.528.1` e `X-Hudson: 1.395` confirmam que o serviço HTTP é Jenkins. Classificação: **ACESSÍVEL_COM_AUTENTICAÇÃO** — mais precisamente, acessível pela rede e protegido por controle de acesso; o mecanismo de login e as permissões do usuário não foram testados.

Arquitetura recomendada: **Jenkinsfile com `curl` para um Workflow do Teams**, inicialmente em `DRY_RUN`. Trello fica como evolução opcional para estado/histórico visual. Nenhuma integração real foi enviada.

## Resultado do acesso ao Jenkins

| Verificação | Resultado |
|---|---|
| Endereço responde | Sim |
| Código HTTP | 403 Forbidden |
| Tempo total do HEAD | 0,353614 s |
| Redirecionamentos | 0 |
| IP/porta remotos | 147.93.6.174:8080 |
| Porta TCP acessível | Sim |
| Serviço Jenkins | Confirmado por `X-Jenkins: 2.528.1` |
| Autenticação/autorização | Controle de acesso detectado; detalhes NÃO CONFIRMADOS |
| Bloqueio por VPN/firewall desta estação | Não observado |

Um 403 comprova comunicação e recusa de acesso; não comprova credencial inválida nem permite inferir acesso administrativo.

## Evidências coletadas

### HEAD público

Comando:

```text
curl.exe -I --connect-timeout 10 --max-time 20 --write-out <métricas> http://147.93.6.174:8080/
```

Resultado:

```text
HTTP/1.1 403 Forbidden
Server: Jetty(12.0.25)
Content-Type: text/html;charset=utf-8
X-Hudson: 1.395
X-Jenkins: 2.528.1
CURL_HTTP_CODE=403
CURL_TIME_TOTAL=0.353614
CURL_REDIRECTS=0
CURL_REMOTE_IP=147.93.6.174
CURL_REMOTE_PORT=8080
```

Interpretação: o servidor respondeu e os cabeçalhos identificam Jenkins; o acesso anônimo à raiz foi negado.

Impacto: diagnóstico externo e integração via API exigirão permissão/autenticação autorizada quando aplicável. Isso não impede que uma pipeline faça POST para o Teams, pois é o sentido oposto da conexão.

Próxima ação: validar recursos do agente em job isolado e aprovado.

### Porta TCP

Comando:

```text
Test-NetConnection -ComputerName 147.93.6.174 -Port 8080 -InformationLevel Detailed
```

Resultado:

```text
RemoteAddress: 147.93.6.174
RemotePort: 8080
TcpTestSucceeded: True
```

Interpretação: a porta estava alcançável a partir desta estação no momento do teste.

Impacto: não houve evidência de timeout, recusa ou bloqueio por rede local.

Próxima ação: nenhuma varredura adicional; preservar o limite somente leitura.

## Como interpretar códigos de acesso

| Resultado | Significado prático |
|---|---|
| Não acessa | Nenhuma resposta HTTP; pode ser DNS, rota, VPN, firewall, timeout ou serviço parado |
| 401 | Servidor respondeu e exige/recusou autenticação |
| 403 | Servidor respondeu, mas a requisição não tem autorização suficiente ou acesso anônimo é negado |
| 404 | Servidor respondeu; rota não existe ou pode estar ocultada por política |
| 200 | Rota respondeu com sucesso; não implica acesso administrativo |
| Timeout | Não houve resposta no limite; possível rota/firewall/proxy/serviço lento |
| Conexão recusada | Host foi alcançado, mas não aceitou a porta naquele momento |

## O que funciona sem acesso ao Ubuntu

- Editar e testar localmente esta PoC.
- Gerar/validar evento, mensagem e duração.
- Usar mocks de Teams e Trello.
- Editar Jenkinsfile no repositório, **se** a permissão existir.
- Executar `curl` no pipeline, **se** já estiver disponível e a política permitir.
- Usar credencial Jenkins de pasta/job, **se** já houver mecanismo aprovado.

## O que depende do administrador

Consulte a matriz completa em `SEGURANCA.md`. Permanecem `NÃO CONFIRMADO`: `curl` no agente, shell, Credentials Binding, HTTP Request Plugin, DNS, saída HTTPS, proxy, allowlist, cadastro/rotação do webhook e instalação de qualquer componente ausente.

## Testes realizados

- Inventário do workspace (estava vazio, exceto `.git`).
- Um HEAD público na raiz informada, sem autenticação e sem seguir redirecionamentos.
- Um teste TCP direcionado exclusivamente à porta informada.
- Testes unitários locais com mocks para modelo, duração, Teams e Trello.
- Compilação dos módulos, `29 passed` em testes unitários e execução local dos fluxos pause/resume em `dry-run`.

## Testes não realizados

- Login, API autenticada, endpoints administrativos ou enumeração do Jenkins.
- Build, alteração de job ou Jenkinsfile em produção.
- Acesso SSH ao Ubuntu.
- Saída HTTPS do agente Jenkins.
- POST para Teams, Trello ou qualquer webhook real.
- Instalação de plugins/pacotes ou mudança de firewall/proxy/DNS.
- Testes externos (`RUN_EXTERNAL_TESTS=false`).

## Riscos

- Webhook exposto em Git/log permite mensagens não autorizadas.
- Falta de saída HTTPS/proxy impede integração apesar do Jenkins estar acessível externamente.
- Teams sozinho não é armazenamento transacional; sem `PAUSADA_EM`, o tempo não pode ser reconstruído com segurança.
- Descrições podem carregar dados sensíveis; aplicar minimização e política de retenção.
- Dependência de Workflow com proprietário individual pode causar indisponibilidade futura.

## Arquitetura recomendada

Opção A (`Jenkinsfile` + `curl` + Teams), detalhada em `ARQUITETURA.md`. Não requer banco nem HTTP Request Plugin. Requer evidência de `curl`, saída HTTPS e credencial segura.

## Próximos passos

1. Revisar a PoC e manter `DRY_RUN=true`.
2. Confirmar permissão para job isolado e edição do Jenkinsfile.
3. Executar somente o estágio neutro de conectividade.
4. Solicitar ao administrador credencial secreta e allowlist do domínio do Workflow.
5. Criar Workflow e canal de teste com payload fictício.
6. Fazer uma pausa/retomada fictícia e conferir mensagem, status HTTP e ausência de segredo no log.
7. Decidir se o estado operacional justifica Trello na fase 2.

## Decisão final

**VIÁVEL COM CONDICIONANTES.** A camada local e o desenho sem plugin adicional são viáveis. A implantação no Jenkins não está confirmada até provar `curl`, shell, saída HTTPS/proxy e armazenamento seguro do webhook. Não é necessário acesso SSH ao Ubuntu se esses recursos já estiverem disponíveis no agente e a credencial puder ser cadastrada por pessoa autorizada.
