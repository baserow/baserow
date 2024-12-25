from django.core.management.base import BaseCommand

from baserow.core.user_sources.handler import UserSourceHandler


class Command(BaseCommand):
    help = (
        "A management command which counts and caches all user source external "
        "users. It's possible to reduce the scope by providing a user source type."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            type=str,
            default=None,
            help="Optionally choose a user source type to update, "
            "instead of all of them.",
        )
        parser.add_argument(
            "--in-chunks",
            action="store_true",
            default=False,
            help="Optionally choose if we should update the user counts in chunks,"
            "instead of all configured user sources at once.",
        )

    def handle(self, *args, **options):
        user_source_type = options["type"]
        UserSourceHandler().update_all_user_source_counts(
            user_source_type, update_in_chunks=options["in_chunks"]
        )
        self.stdout.write(
            self.style.SUCCESS(
                "All configured user sources have been "
                f"updated{' in chunks' if options['in_chunks'] else ''}."
                if not user_source_type
                else f"All configured {user_source_type} user sources have "
                f"been updated{' in chunks' if options['in_chunks'] else ''}."
            )
        )
