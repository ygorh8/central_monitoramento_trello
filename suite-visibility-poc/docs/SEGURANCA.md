# Seguranca

## Credenciais

- Windows local: tokens podem ser armazenados pelo `keyring` no Gerenciador de Credenciais;
- servidor/container: use variaveis protegidas ou o secret manager da plataforma;
- nunca grave `.env`, tokens, webhooks ou passwords no Git;
- use um usuario Jenkins somente leitura e uma conta Trello com acesso apenas ao quadro necessario.

## Controles implementados

- Jenkins recebe apenas `GET` e `HEAD`;
- URLs com credenciais embutidas sao rejeitadas;
- erros HTTP nao incluem tokens nas mensagens da aplicacao;
- `.env`, `runtime/`, logs, caches e artefatos sao ignorados pelo Git;
- imagem Docker executa com usuario sem privilegios;
- unidade systemd usa `NoNewPrivileges`, `ProtectSystem` e diretorio gravavel restrito;
- eventos somente sao confirmados depois da resposta do Trello.

## Producao

- proteja `/etc/suite-visibility.env` com modo `0600` quando usar systemd;
- monte o repositorio de suites como somente leitura;
- mantenha `runtime/` em volume persistente e protegido;
- habilite logs centralizados sem payloads secretos;
- defina rotacao/revogacao para os tokens Jenkins e Trello;
- nao execute duas instancias com o mesmo fluxo sem lock distribuido.

## Teams

Microsoft Teams permanece em standby. Uma integracao futura deve usar Microsoft Graph com permissao minima e credenciais separadas; nao reutilize tokens do Jenkins ou Trello.
