import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from django.core.management.base import BaseCommand, CommandError

from baserow_enterprise.assistant.chatgpt_plan import (
    CALLBACK_PATH,
    PLAN_SCOPE,
    ChatGPTPlanError,
    build_authorization,
    finish_authorization,
    get_credentials_path,
)


class Command(BaseCommand):
    help = (
        "Proof of concept: sign in with ChatGPT so Kuma can use your ChatGPT plan "
        "through the `chatgpt:<model>` assistant model. Run it on the machine whose "
        "browser signs in, because OpenAI only redirects to 127.0.0.1."
    )

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=1455)
        parser.add_argument(
            "--no-browser",
            action="store_true",
            help="Print the sign-in URL instead of opening a browser.",
        )

    def handle(self, *args, **options):
        url, pending = build_authorization(options["port"])
        outcome = {}

        class Callback(BaseHTTPRequestHandler):
            def do_GET(self):
                if not self.path.startswith(CALLBACK_PATH):
                    self.send_response(404)
                    self.end_headers()
                    return
                try:
                    outcome["record"] = finish_authorization(
                        f"http://127.0.0.1{self.path}", pending
                    )
                    message = "Signed in. You can close this window."
                except ChatGPTPlanError as exc:
                    outcome["error"] = str(exc)
                    message = f"Sign-in failed: {exc}"
                self.send_response(200)
                self.send_header("content-type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(message.encode())

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", options["port"]), Callback)
        self.stdout.write(f"Open this URL to sign in with ChatGPT:\n\n{url}\n")
        if not options["no_browser"]:
            webbrowser.open(url)
        while not outcome:
            server.handle_request()
        server.server_close()

        if "error" in outcome:
            raise CommandError(outcome["error"])
        record = outcome["record"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Signed in as {record.get('email')}. Saved to "
                f"{get_credentials_path()}."
            )
        )
        if PLAN_SCOPE not in record["scopes"]:
            self.stdout.write(
                self.style.WARNING("ChatGPT plan usage was not granted; sign in again.")
            )
