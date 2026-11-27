from django.core.management.base import BaseCommand, CommandError

from baserow.core.user_templates.handler import UserTemplateHandler


class Command(BaseCommand):
    help = (
        "Copies the content of user templates again with what a copy leaves out "
        "now, replacing their previews and clearing their downloads. Run it after a "
        "fix of the copy, so that templates created before it are cleaned too."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--template",
            type=int,
            action="append",
            dest="template_ids",
            help="The id of a user template to rebuild. Can be repeated.",
        )
        target.add_argument(
            "--all",
            action="store_true",
            help="Rebuild all user templates not marked for deletion.",
        )

    def handle(self, *args, **options):
        template_ids = options["template_ids"]
        rebuilt, failed = UserTemplateHandler().rebuild_templates(template_ids)
        missing = sorted(set(template_ids or []) - set(rebuilt) - set(failed))
        self.stdout.write(f"Rebuilt {len(rebuilt)} user template(s).")
        if missing:
            self.stdout.write(
                self.style.WARNING(f"Not found or marked for deletion: {missing}")
            )
        if failed:
            raise CommandError(f"Rebuilding failed, see the logs: {failed}")
