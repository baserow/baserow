import sys

from django.core.management.base import BaseCommand
from django.db.models import Value

from tqdm import tqdm

from baserow.contrib.database.search.exceptions import (
    PostgresFullTextSearchDisabledException,
)
from baserow.contrib.database.search.handler import SearchHandlerCompat
from baserow.contrib.database.table.constants import (
    ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME,
)
from baserow.contrib.database.table.models import Table
from baserow.core.utils import Progress


class Command(BaseCommand):
    help = (
        "Given a table ID, this command will update its `tsvector` columns with"
        "the contents of all fields in your table so that it can be searched upon."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "table_id",
            type=int,
            help="The ID of the table to update.",
        )
        parser.add_argument(
            "--update-changed-rows-only",
            action="store_true",
            help="If true, it will run the update for changed rows only.",
        )
        parser.add_argument(
            "--mark-all-as-updated",
            action="store_true",
            help="If true, it will mark all rows as changed before updating them.",
        )

    def handle(self, *args, **options):
        table_id = options["table_id"]
        update_changed_rows_only = options.get("update_changed_rows_only", False)
        mark_all_as_updated = options.get("mark_all_as_updated", False)
        try:
            table = Table.objects.get(id=options["table_id"])
        except Table.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"The table with id {table_id} was not found.")
            )
            sys.exit(1)
        try:
            progress_total = 1100 if mark_all_as_updated else 1000
            with tqdm(total=progress_total) as progress_bar:
                progress = Progress(progress_total)

                def progress_updated(percentage, state=None):
                    if state:
                        progress_bar.set_description(state)
                    progress_bar.update(progress.progress - progress_bar.n)

                progress.register_updated_event(progress_updated)

                # This uses a different strategy of updating the row. Can be useful for
                # testing purposes.
                if mark_all_as_updated:
                    progress.increment(
                        0,
                        state=f"Updating {ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME} to true",
                    )
                    model = table.get_model()
                    model.objects.update(
                        **{ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME: Value(True)}
                    )
                    progress.increment(100)

                progress.increment(0, "Updating")
                SearchHandlerCompat.update_tsvector_columns_locked(
                    table,
                    update_tsvectors_for_changed_rows_only=update_changed_rows_only,
                    progress_builder=progress.create_child_builder(
                        represents_progress=1000
                    ),
                )

            self.stdout.write(
                self.style.SUCCESS("The tsvector columns were been updated.")
            )
        except PostgresFullTextSearchDisabledException:
            self.stdout.write(
                self.style.ERROR(
                    "Your Baserow installation has Postgres full-text"
                    "search disabled. To use full-text, ensure that"
                    "BASEROW_USE_PG_FULLTEXT_SEARCH=true."
                )
            )
