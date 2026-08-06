"""Store Trello credentials in the Windows credential manager without echoing them."""

from getpass import getpass

from suite_visibility.secret_store import get_trello_credentials, store_trello_credentials


def main() -> None:
    api_key = getpass("Trello API key: ")
    api_token = getpass("Trello API token: ")
    store_trello_credentials(api_key, api_token)
    stored_key, stored_token = get_trello_credentials()
    if stored_key != api_key.strip() or stored_token != api_token.strip():
        raise RuntimeError("Falha ao confirmar as credenciais no Gerenciador de Credenciais")
    print("Credenciais Trello armazenadas com seguranca.")


if __name__ == "__main__":
    main()
