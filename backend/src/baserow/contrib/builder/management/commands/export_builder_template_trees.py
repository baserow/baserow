import json
import logging
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from loguru import logger

from baserow.contrib.builder.application_types import BuilderApplicationType
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.management.commands.install_builder_templates import (
    create_temp_user_and_workspace,
    get_builder_templates,
)
from baserow.core.handler import CoreHandler
from baserow.core.utils import Progress

User = get_user_model()


def build_element_tree(elements) -> list:
    def children_of(parent_id):
        return [
            {
                "type": el.get_type().type,
                "children": children_of(el.id),
            }
            for el in elements
            if el.parent_element_id == parent_id
        ]

    return children_of(None)


def _page_slug(page) -> str:
    return re.sub(r"[^a-z0-9]+", "-", page.name.lower()).strip("-")


class Command(BaseCommand):
    help = (
        "Installs all builder templates and exports their element trees as JSON "
        "fixture files for the Vitest regression snapshot tests."
    )

    def add_arguments(self, parser):
        default_output = str(
            Path(settings.APPLICATION_TEMPLATES_DIR).resolve().parent.parent
            / "web-frontend/test/unit/builder/fixtures/templates"
        )
        parser.add_argument(
            "--output-dir",
            default=default_output,
            help=f"Directory to write per-template JSON files. Default: {default_output}",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Regenerate all templates, even those with existing fixture files.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "This command is intended for development use only "
                "and must not be run in production."
            )

        # Disable the celery/base log entries, for extra visibility...
        logger.disable("baserow")
        logging.getLogger("celery").setLevel(logging.WARNING)

        output_dir = Path(options["output_dir"])
        force = options["force"]

        all_templates = list(get_builder_templates())
        if not all_templates:
            self.stdout.write("No builder templates found.")
            return

        pending = (
            all_templates
            if force
            else [
                t for t in all_templates if not (output_dir / f"{t.slug}.json").exists()
            ]
        )

        skipped = len(all_templates) - len(pending)
        if not pending:
            self.stdout.write(
                f"All {len(all_templates)} template(s) already generated — nothing to do. "
                "Use --force to regenerate."
            )
            return

        if skipped:
            self.stdout.write(
                f"Generating {len(pending)} template(s) "
                f"({skipped} already exist, skipping)."
            )
        else:
            self.stdout.write(f"Generating {len(pending)} template(s).")

        output_dir.mkdir(parents=True, exist_ok=True)

        def _report(pct, state):
            self.stdout.write(f"\r  [{pct:3d}%] {state:<50}", ending="")
            self.stdout.flush()

        progress = Progress(total=len(pending))
        progress.register_updated_event(_report)

        user, workspace = create_temp_user_and_workspace()
        try:
            for template in pending:
                apps, _ = CoreHandler().install_template(
                    user=user, workspace=workspace, template=template
                )
                pages_output = {}

                for app in apps:
                    if app.get_type().type != BuilderApplicationType.type:
                        continue
                    builder = app.specific
                    for page in builder.page_set.order_by("order"):
                        elements = list(
                            Element.objects.filter(page=page).order_by("order", "id")
                        )
                        pages_output[_page_slug(page)] = build_element_tree(elements)

                dest = output_dir / f"{template.slug}.json"
                dest.write_text(json.dumps(pages_output))
                progress.increment(state=template.slug)

        finally:
            workspace.delete()
            User.objects.filter(pk=user.pk).delete()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Done."))
