import json

from django.core.management.base import BaseCommand, CommandError

from baserow.core.ai_provider.audit import build_ai_provider_audit
from baserow.core.models import Workspace


class Command(BaseCommand):
    help = (
        "Print a read-only JSON inventory of AI provider settings and consumers. "
        "Does not expose credentials, call providers, or approve a rollout."
    )

    def add_arguments(self, parser):
        """Declare the optional workspace filter.

        :param parser: Django's command argument parser.
        :returns: None.
        """

        parser.add_argument(
            "--workspace-id",
            type=int,
            help="Include this workspace and its publications, plus instance settings.",
        )

    def handle(self, *args, **options):
        """Write the inventory to stdout without changing configuration.

        :param args: Unused positional command arguments.
        :param options: Parsed options, including the optional workspace ID.
        :returns: None.
        :raises CommandError: If the workspace does not exist.
        """

        try:
            report = build_ai_provider_audit(options["workspace_id"])
        except Workspace.DoesNotExist as exc:
            raise CommandError("The requested workspace does not exist.") from exc
        self.stdout.write(json.dumps(report, indent=2))
