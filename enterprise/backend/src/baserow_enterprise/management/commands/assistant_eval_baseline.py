from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from baserow_enterprise.assistant.evals.baseline import (
    capture_baseline,
    import_baseline,
)
from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.registry import load_all


class Command(BaseCommand):
    help = (
        "Capture the committed eval baseline snapshot from Phoenix, or import "
        "it into the configured Phoenix instance."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("action", choices=["capture", "import"])
        parser.add_argument(
            "--experiment-name",
            default=None,
            help="capture only: restrict the pick to experiments with this "
            "name instead of taking the newest per dataset.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        load_all()
        client = get_phoenix_client()

        if options["action"] == "capture":
            results = capture_baseline(client, options["experiment_name"])
        else:
            results = import_baseline(client)

        for key, value in results.items():
            self.stdout.write(f"{key}: {value}")
