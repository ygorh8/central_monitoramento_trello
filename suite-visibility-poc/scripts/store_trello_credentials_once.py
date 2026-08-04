"""Store Trello credentials in the Windows credential manager without echoing them."""

from getpass import getpass

from suite_visibility.secret_store import store_trello_credentials


def main() -> None:
    api_key = getpass("Trello API key: ")
    api_token = getpass("Trello API token: ")
    store_trello_credentials(api_key, api_token)
    print("Credenciais Trello armazenadas com seguranca.")


if __name__ == "__main__":
    main()
