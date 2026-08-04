# Teste de conectividade do agente Jenkins

O estágio `Diagnosticar conectividade` de `examples/Jenkinsfile.curl` é separado, opt-in e usa `example.com`. Ele não testa Teams ou Trello e não altera dados. `ping` não é evidência suficiente: ICMP pode estar bloqueado e HTTPS permitido.

| Evidência | Interpretação | Próxima ação segura |
|---|---|---|
| `Could not resolve host` | DNS do agente não resolveu o nome | Administrador verifica DNS/proxy |
| `Connection timed out` | rota, firewall ou proxy silenciosamente bloqueou | Confirmar allowlist e proxy |
| `Connection refused` | destino alcançado, mas porta recusou | Confirmar host/porta/serviço |
| `SSL certificate problem` | cadeia CA, inspeção TLS ou hostname inválido | Administrador fornece CA corporativa; não usar `-k` em produção |
| `Proxy Authentication Required` / HTTP 407 | proxy exige autenticação | Administrador configura proxy com segredo protegido |
| HTTP 200 | HTTPS chegou ao destino e foi aceito | Testar endpoint autorizado em job isolado |
| HTTP 301 | comunicação ocorreu; destino redireciona | Validar `Location` antes de seguir |
| HTTP 401 | comunicação ocorreu; autenticação faltou/falhou | Usar credencial autorizada |
| HTTP 403 | comunicação ocorreu; identidade/origem sem permissão | Revisar permissão/allowlist; não tentar contornar |

## Confirmações ainda necessárias no agente

1. Executar o estágio diagnóstico em um job de teste autorizado.
2. Confirmar `curl --version`.
3. Confirmar DNS e HTTPS para domínio neutro.
4. Só depois, solicitar allowlist do domínio do Workflow do Teams.
5. Fazer POST apenas em Workflow de teste e com payload fictício.

Todos esses itens estão `NÃO CONFIRMADO` até existir log do agente Jenkins.

