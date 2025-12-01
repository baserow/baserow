import sys

from django.core.management.base import BaseCommand
from django.db import transaction

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table


class Command(BaseCommand):
    help = (
        "Given a table ID, this command will ensure all TSV data is updated for it. "
        "This will allow it to be searched against."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "table_id",
            type=int,
            help="The ID of the table to create a tsvector columns for.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not SearchHandler.full_text_enabled():
            self.stdout.write(
                self.style.ERROR(
                    "Your Baserow installation has Postgres full-text"
                    "search disabled. To use full-text, ensure that"
                    "BASEROW_USE_PG_FULLTEXT_SEARCH=true."
                )
            )

        table_id = options["table_id"]
        try:
            table = TableHandler().get_table(table_id)
        except Table.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"The table with id {table_id} was not found.")
            )
            sys.exit(1)

        # Reset the search_data_initialized_at field for all fields in the table
        # so that the search data will be re-initialized.
        Field.objects_and_trash.filter(table_id=table_id).update(
            search_data_initialized_at=None
        )

        # TODO: show a progress bar
        SearchHandler.update_search_data(table)

        self.stdout.write(
            self.style.SUCCESS(
                "The tsvector data have been successfully updated for the table."
            )
        )
