import os
from argparse import ArgumentParser
from typing import Any
from wsgiref.simple_server import make_server

from django.core.management import call_command
from django.core.management.base import BaseCommand

from loguru import logger

from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.prompt_sync import sync_prompts
from baserow_enterprise.assistant.evals.registry import load_all
from baserow_enterprise.assistant.evals.runner import make_wsgi_app, start_worker
from baserow_enterprise.assistant.evals.sync import sync_datasets
from baserow_enterprise.assistant.telemetry import setup_instrumentation


class Command(BaseCommand):
    help = "Serve the assistant eval runner: a small page to trigger eval experiments."

    def add_arguments(self, parser: ArgumentParser) -> None:
        default_port = int(os.getenv("BASEROW_EVAL_RUNNER_PORT", "8090"))
        parser.add_argument("--port", type=int, default=default_port)
        parser.add_argument(
            "--host",
            default="127.0.0.1",
            help="Interface to bind. Use 0.0.0.0 to expose outside a container.",
        )
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="Skip running migrations against the eval runner's database.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["skip_migrate"]:
            call_command("migrate", interactive=False, verbosity=0)

        setup_instrumentation()
        load_all()

        try:
            sync_datasets(get_phoenix_client())
        except Exception:
            logger.exception("Failed to sync eval datasets to Phoenix on startup")

        try:
            sync_prompts(get_phoenix_client())
        except Exception:
            logger.exception("Failed to sync eval prompts to Phoenix on startup")

        start_worker()

        host = options["host"]
        port = options["port"]
        self.stdout.write(
            self.style.SUCCESS(f"Assistant eval runner listening on {host}:{port}")
        )
        make_server(host, port, make_wsgi_app()).serve_forever()
