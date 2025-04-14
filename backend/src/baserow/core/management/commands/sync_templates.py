from django.conf import settings
from django.core.management.base import BaseCommand

from baserow.core.handler import CoreHandler


class Command(BaseCommand):
    help = (
        "Synchronizes all the templates stored in the database with the JSON files in "
        "the templates directory. This command must be ran every time a template "
        "changes. It can optionally sync only templates based on a naming "
        "pattern provided as an argument or sourced from env var."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            type=str,
            nargs=1,
            default="",
            help="Regular expression to match templates for sync",
        )
        parser.add_argument(
            "--from-env",
            action="store_true",
            help="If set templates will be synced based on BASEROW_SYNC_TEMPLATES_PATTERN var",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="If set force template sync even if the templates didn't change",
        )

    def handle(self, *args, **options):
        from_env = options.get("from_env", False)
        force = options.get("force", False)

        if from_env:
            CoreHandler().sync_templates(
                pattern=settings.BASEROW_SYNC_TEMPLATES_PATTERN, force=force
            )
        elif options.get("only", None):
            try:
                templates = options["only"][0]
            except (KeyError, IndexError):
                from loguru import logger

                logger.exception("Error while importing template")
                self.stdout.write(
                    self.style.ERROR("Provide a pattern to match templates")
                )

            CoreHandler().sync_templates(pattern=templates, force=force)
        else:
            CoreHandler().sync_templates(force=force)
