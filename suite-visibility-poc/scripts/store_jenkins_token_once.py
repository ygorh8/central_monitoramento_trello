"""Receive one Jenkins token on loopback and store it in Windows Credential Manager."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from suite_visibility.secret_store import store_jenkins_token


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "http://147.93.6.174:8080")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(min(length, 512)).decode("utf-8").strip()
            token = parse_qs(body).get("token", [body])[0].strip()
            if self.path != "/store" or not 16 <= len(token) <= 256 or any(ch.isspace() for ch in token):
                self.send_response(400)
                self.end_headers()
                return
            store_jenkins_token(args.username, token)
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "http://147.93.6.174:8080")
            self.end_headers()
            self.server.stored = True

        def log_message(self, *_args):
            return

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.timeout = 30
    server.stored = False
    while not server.stored:
        server.handle_request()


if __name__ == "__main__":
    main()
