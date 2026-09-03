from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from baserow_enterprise.assistant.evals.export import export_foreign_examples
from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.registry import load_all


class Command(BaseCommand):
    help = "Export UI-added Phoenix dataset examples as ready-to-paste eval code."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--dataset",
            default="kuma-docs",
            help="Phoenix dataset name to export UI-added examples from.",
        )
        parser.add_argument(
            "--out",
            default=None,
            help="Write the snippets to this file instead of stdout.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        load_all()
        client = get_phoenix_client()
        output = export_foreign_examples(client, options["dataset"])

        if options["out"]:
            with open(options["out"], "w") as f:
                f.write(output)
            self.stdout.write(self.style.SUCCESS(f"Wrote snippets to {options['out']}"))
        else:
            self.stdout.write(output)
