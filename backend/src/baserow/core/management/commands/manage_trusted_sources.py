from django.core.management.base import BaseCommand

from baserow.core.import_export.handler import ImportExportHandler


class Command(BaseCommand):
    help = (
        "Provides management commands for handling trusted sources used in the "
        "application's import and export processes. This includes listing all trusted "
        "sources, adding new ones, deleting existing ones by name, and displaying the "
        "public key of a trusted source."
    )

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            dest="action", help="Action to perform (list, add, remove)"
        )

        # Subparser for 'list'
        subparsers.add_parser("list", help="List all trusted public keys.")

        # Subparser for 'add'
        add_parser = subparsers.add_parser("add", help="Add a new trusted public key.")
        add_parser.add_argument(
            "name", type=str, help="Name of the trusted public key."
        )
        add_parser.add_argument(
            "public_key_data", type=str, help="Base64 encoded public key data."
        )

        # Subparser for 'remove'
        remove_parser = subparsers.add_parser(
            "remove", help="Remove an existing trusted public key."
        )
        remove_parser.add_argument(
            "source_id", type=str, help="ID of the trusted public key to remove."
        )

    def handle(self, *args, **options):
        handler = ImportExportHandler()
        action = options.get("action")

        if action == "list":
            handler.list_trusted_public_keys()
        elif action == "add":
            name = options.get("name")
            public_key_data = options.get("public_key_data")
            handler.add_trusted_public_key(name, public_key_data)
        elif action == "remove":
            source_id = options.get("source_id")
            handler.delete_trusted_public_key(source_id)
        else:
            self.stdout.write(
                self.style.ERROR("Invalid action. Use 'list', 'add', or 'remove'.")
            )
