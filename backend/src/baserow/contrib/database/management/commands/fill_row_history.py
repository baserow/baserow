import dataclasses
import itertools
import sys
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from faker import Faker
from tqdm import tqdm

from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.history import RowHistoryHandler
from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.table.models import Table
from baserow.core.action.signals import ActionCommandType
from baserow.core.models import WorkspaceUser

# for cache
rows_values = None


class Command(BaseCommand):
    help = "Fills a row history with random changes."

    def add_arguments(self, parser):
        parser.add_argument(
            "table_id", type=int, help="The table that contains the row."
        )
        parser.add_argument(
            "row_id", type=int, help="The row id for which to generate history entries."
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="The number of history entries to generate.",
            default=20,
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="If provided, will remove previous entries for the row.",
        )
        parser.add_argument(
            "--randomize-timestamps",
            action="store_true",
            help="If true, will create entries with various timestamps.",
        )
        parser.add_argument(
            "--cache",
            action="store_true",
            help="If provided, will be inserting the same generated values over and over.",
        )
        parser.add_argument(
            "--skip-action",
            action="store_true",
            help="If provided, will be inserting the data without invoking UpdateRowsActionType.",
        )

    def handle(self, *args, **options):
        table_id = options["table_id"]
        row_id = options["row_id"]
        limit = options["limit"]
        clean = options.get("clean", False)
        use_cache = options.get("cache", False)
        skip_action = options.get("skip_action", False)
        randomize_timestamps = options.get("randomize_timestamps", False)

        try:
            table = Table.objects.get(pk=table_id)
        except Table.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"The table with id {table_id} was not found.")
            )
            sys.exit(1)

        model = table.get_model()

        try:
            row = model.objects.get(pk=row_id)
        except model.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"The row with id {row_id} was not found in table {table_id}."
                )
            )
            sys.exit(1)

        workspace = table.database.workspace
        workspace_users = WorkspaceUser.objects.filter(workspace=workspace)
        wk_admin = workspace_users.filter(permissions="ADMIN").first()

        if clean:
            RowHistory.objects.filter(row_id=row.id, table=table).delete()
            self.stdout.write(self.style.SUCCESS(f"History cleared."))

        model = table.get_model()

        with transaction.atomic():
            with tqdm(
                total=limit,
                desc=f"Adding {limit} entries to row history for row {row_id}",
            ) as progress:
                for _ in range(limit):
                    record_row_history(
                        table,
                        model,
                        row,
                        user=wk_admin.user,
                        use_cache=use_cache,
                        skip_action=skip_action,
                    )
                    progress.update(1)

        if randomize_timestamps:
            overwrite_timestamps(table, row, limit)

        self.stdout.write(self.style.SUCCESS(f"History recorded successfully."))


def record_row_history(table, model, row, user, use_cache=False, skip_action=False):
    global rows_values
    fake = Faker()
    cache = {}
    row_random_values = {}
    row_random_values["id"] = row.id

    if use_cache is False or rows_values is None:
        for _, field_object in model._field_objects.items():
            if not field_object["type"].read_only:
                random_value = field_object["type"].random_value(
                    field_object["field"], fake, cache
                )
                serialized_random_value = field_object["type"].random_to_input_value(
                    field_object["field"], random_value
                )
                row_random_values[f"field_{field_object['field'].id}"] = (
                    serialized_random_value
                )

        rows_values = [row_random_values]

    if skip_action:
        row_handler = RowHandler()
        result = row_handler.update_rows(user, table, rows_values, model=model)
        updated_rows = result.updated_rows
        params = UpdateRowsActionType.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            [row.id for row in updated_rows],
            rows_values,
            result.original_rows_values_by_id,
            result.updated_fields_metadata_by_row_id,
        )

        RowHistoryHandler().record_history_from_update_rows_action(
            user,
            "uuid",
            dataclasses.asdict(params),
            datetime.now(tz=timezone.utc),
            ActionCommandType.DO,
        )
    else:
        UpdateRowsActionType.do(user, table, rows_values, model)


def overwrite_timestamps(table, row, limit):
    now = datetime.now(tz=timezone.utc)
    day_ago = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)
    three_days_ago = now - timedelta(days=3)
    unique_timestamps = [now, day_ago, two_days_ago, three_days_ago]
    timestamps = list(
        itertools.chain.from_iterable(itertools.repeat(x, 3) for x in unique_timestamps)
    )
    entries = RowHistory.objects.filter(row_id=row.id, table=table).all()[:limit]

    for entry in entries:
        entry.action_timestamp = (
            timestamps.pop(0) if len(timestamps) > 0 else three_days_ago
        )

    RowHistory.objects.bulk_update(entries, ["action_timestamp"])
