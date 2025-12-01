import os
import random
import re
import sys
import time
from collections import defaultdict
from decimal import Decimal
from math import ceil
from typing import List, Tuple

from django.core.management.base import BaseCommand
from django.db.models import Max
from django.db.models.fields.related import ForeignKey

from faker import Faker
from tqdm import tqdm

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.models import Table
from baserow.core.handler import CoreHandler
from baserow.core.management.utils import run_command_concurrently
from baserow.core.utils import Progress, grouper


def underscore(word: str) -> str:
    word = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", word)
    word = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", word)
    word = word.replace("-", "_")
    word = word.replace(" ", "_")
    return word.lower()


class Command(BaseCommand):
    help = "Fills a table with random data."

    def add_arguments(self, parser):
        parser.add_argument(
            "table_id", type=int, help="The table that needs to be filled."
        )
        parser.add_argument(
            "limit", type=int, help="Amount of rows that need to be inserted."
        )
        parser.add_argument(
            "--replicate-to-table-ids",
            type=str,
            nargs="*",
            help="Optional, replicate the rows into other table IDs at the same time. "
            "Useful if you're trying to benchmark exact tables against one "
            "another. The tables in `replicate_to_table_ids` *must* have the "
            "exact field names and types as in `table_id`.",
        )
        parser.add_argument(
            "--concurrency",
            nargs="?",
            type=int,
            help="How many concurrent processes should be used to create rows.",
            default=1,
        )
        parser.add_argument(
            "--batch-size",
            nargs="?",
            type=int,
            help="How many rows should be inserted in a single query.",
            default=-1,
        )
        parser.add_argument(
            "--skip-tsvectors",
            action="store_true",
            help=(
                "Skip generating tsvector values for full-text search. Use only in testing/dev "
                "because search data will be out of sync and will require manual sync."
            ),
        )

    def handle(self, *args, **options):
        table_id = options["table_id"]
        replicate_to_table_ids = options["replicate_to_table_ids"] or []

        limit = options["limit"]
        concurrency = options["concurrency"]
        batch_size = options["batch_size"]
        skip_tsvectors = options["skip_tsvectors"]

        tick = time.time()
        if concurrency == 1:
            try:
                table = Table.objects.get(pk=table_id)
            except Table.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"The table with id {table_id} was not found.")
                )
                sys.exit(1)

            source_table_model = table.get_model()

            # If we've been given tables to replicate to...
            replicated_table_models = []
            if replicate_to_table_ids:
                # `run_command_concurrently` needs to receive a string, so
                # `replicate_to_table_ids` is a list of strings. To query for
                # the tables however, we need integer, so map over them and cast to int.
                replicate_to_table_ids_int = list(
                    map(lambda tbl_id: int(tbl_id), replicate_to_table_ids)
                )
                # Find all tables using their PK.
                replicated_tables = Table.objects.filter(
                    pk__in=replicate_to_table_ids_int
                )
                # Pluck out the IDs from the queryset.
                replicated_table_ids_found = list(
                    map(lambda tbl: tbl.id, replicated_tables)
                )
                # If the IDs don't match those we're expecting, then
                # one or more of those IDs couldn't be found.
                if replicate_to_table_ids_int != replicated_table_ids_found:
                    # Figure out which IDs are unknown to us and write an error.
                    replicated_table_ids_unknowns = list(
                        set(replicate_to_table_ids_int)
                        - set(replicated_table_ids_found)
                    )
                    replicated_table_ids_unknown_str = ", ".join(
                        map(lambda t: str(t), replicated_table_ids_unknowns)
                    )
                    self.stdout.write(
                        self.style.ERROR(
                            "Unable to find table(s) "
                            f"{replicated_table_ids_unknown_str} to "
                            "replicate to."
                        )
                    )
                    sys.exit(1)

                # We found all tables properly, so we'll now fetch
                # all generated table models for those tables.
                replicated_table_models = list(
                    map(lambda tbl: tbl.get_model(), replicated_tables)
                )
                # Finally, the last check is to validate that all fields
                # (by name and type) match those in the source table, `table`.
                try:
                    validate_replicated_tables(
                        source_table_model, replicated_table_models
                    )
                except ValueError as e:
                    self.stdout.write(self.style.ERROR(e.args[0]))
                    sys.exit(1)

            fill_table_rows(
                limit,
                table,
                batch_size,
                source_table_model=source_table_model,
                replicated_table_models=replicated_table_models,
                skip_tsvectors=skip_tsvectors,
            )

        else:
            concurrency_args = [
                "./baserow",
                "fill_table_rows",
                str(table_id),
                str(int(limit / concurrency)),
                "--replicate-to-table-ids",
                *replicate_to_table_ids,
                "--concurrency",
                "1",
                "--batch-size",
                str(batch_size),
            ]
            run_command_concurrently(
                concurrency_args,
                concurrency,
            )

        tock = time.time()
        self.stdout.write(
            self.style.SUCCESS(
                f"{limit} rows have been inserted in {(tock - tick):.1f} seconds."
            )
        )


def extract_table_fields(model) -> List[Tuple[str, str]]:
    """
    Given a generated table model, will return a list of tuples where
    each tuple represents a field name and field type combination. Used
    by `validate_replicated_tables` to ensure each replicated table
    matching the source table's fields.
    """

    table_field_map = []
    for _, field_object in model._field_objects.items():
        field_type = field_object["type"].type
        field_name = underscore(field_object["field"].name.lower())
        table_field_map.append(
            (
                field_name,
                field_type,
            )
        )
    return table_field_map


def validate_replicated_tables(source_table_model, replicated_table_models):
    """
    Given the source table generated model, and its replicated tables' generated
    models, will ensure that all replicated tables have the same field name/type
    pairs as in the source table. If there are any new/removed fields, an error will
    be raised. This is necessary so that we can cleanly replicate each new row in
    `source_table_model` to tables in `replicated_table_models`.
    """

    source_field_map = extract_table_fields(source_table_model)

    for model in replicated_table_models:
        model_field_map = extract_table_fields(model)
        if model_field_map != source_field_map:
            exc_msg = (
                f"The fields in table {model.baserow_table_id} do not match "
                f"those in source table {source_table_model.baserow_table_id}."
            )
            subtractive_changes = dict(set(source_field_map) - set(model_field_map))
            if subtractive_changes:
                exc_msg += f"\n\nFields missing from table {model.baserow_table_id}:\n"
                for field_name, field_type in subtractive_changes.items():
                    exc_msg += f"- {field_name} (type: {field_type})"
            additive_changes = dict(set(model_field_map) - set(source_field_map))
            if additive_changes:
                exc_msg += f"\n\nFields added in table {model.baserow_table_id}:\n"
                for field_name, field_type in additive_changes.items():
                    exc_msg += f"- {field_name} (type: {field_type})"
            raise ValueError(exc_msg)


def generate_values_for_one_or_more_tables(models, fake, cache):
    """
    Given a list of generated table models (the source table, and optionally if set,
    the replicated tables), this function will group matching fields together using
    their name and type. This is used by `fill_table_rows` to generate a random value
    for a field type *once* and re-use it across the replicated tables.
    """

    grouped_fields_by_name_and_type = defaultdict(lambda: defaultdict(list))
    for model in models:
        for _, field_object in model._field_objects.items():
            field_type = field_object["type"].type
            field_name = underscore(field_object["field"].name.lower())
            key = f"{field_type}_{field_name}"
            field_object["baserow_table_id"] = model.baserow_table_id
            grouped_fields_by_name_and_type[key]["field_objects"].append(field_object)

    fields_grouped_by_table = defaultdict(dict)
    for _, meta in grouped_fields_by_name_and_type.items():
        random_value = None
        for field_object in meta["field_objects"]:
            if field_object["type"].read_only:
                continue
            if random_value is None:
                random_value = field_object["type"].random_value(
                    field_object["field"], fake, cache
                )
            field_id = field_object["field"].id
            table_id = field_object["baserow_table_id"]
            fields_grouped_by_table[table_id][f"field_{field_id}"] = random_value

    return fields_grouped_by_table


def create_row_instance_and_relations(values, table, model, fake, cache, order):
    # Based on the random_value function we have for each type we can
    # build a dict with a random value for each field.
    values, manytomany_values = RowHandler().extract_manytomany_values(values, model)

    values["order"] = order

    workspace = table.database.workspace
    available_users = CoreHandler().get_users_in_workspace(workspace)
    values["last_modified_by"] = random.choice(available_users)  # nosec

    # Prepare an array of objects that can later be inserted all at once.
    instance = model(**values)
    relations = {
        field_name: value
        for field_name, value in manytomany_values.items()
        if value and len(value) > 0
    }
    return instance, relations


def create_many_to_many_relations(model, rows):
    # Construct an object where the key is the field name of the many to many
    # field that must be populated. The value contains the objects that must be
    # inserted in bulk.
    many_to_many = defaultdict(list)
    for row, relations in rows:
        for field_name, value in relations.items():
            through = getattr(model, field_name).through
            through_fields = through._meta.get_fields()
            value_column = None
            row_column = None

            # Figure out which field in the many to many through table holds the row
            # value and which on contains the value.
            for field in through_fields:
                if type(field) is not ForeignKey:
                    continue

                if field.remote_field.model == model and not row_column:
                    row_column = field.get_attname_column()[1]
                else:
                    value_column = field.get_attname_column()[1]

            for i in value:
                many_to_many[field_name].append(
                    getattr(model, field_name).through(
                        **{
                            row_column: row.id,
                            value_column: i,
                        }
                    )
                )

    for field_name, values in many_to_many.items():
        through = getattr(model, field_name).through
        through.objects.bulk_create(values, batch_size=1000)


def bulk_create_rows(model, rows):
    created_rows = model.objects.bulk_create(
        [row for (row, _) in rows], batch_size=1000
    )
    create_many_to_many_relations(model, rows)
    return created_rows


def fill_table_rows(
    limit,
    table,
    batch_size=-1,
    source_table_model=None,
    replicated_table_models=None,
    skip_tsvectors=False,
):
    fake = Faker()
    cache = {}

    if source_table_model:
        model = source_table_model
        models = [model] + replicated_table_models
    else:
        model = table.get_model()
        models = [model]

    # Find out what the highest order is because we want to append the new rows.
    order = ceil(model.objects.aggregate(max=Max("order")).get("max") or Decimal("0"))
    if batch_size <= 0:
        batch_size = limit

    with tqdm(
        total=limit,
        desc=f"Adding {limit} rows to table {table.pk} in worker {os.getpid()}",
    ) as pbar:
        progress = Progress(limit)

        def progress_updated(percentage, state=None):
            if state:
                pbar.set_description(state)
            pbar.update(progress.progress - pbar.n)

        progress.register_updated_event(progress_updated)

        table_row_ids_map = defaultdict(list)
        for group in grouper(batch_size, range(limit)):
            rows = defaultdict(list)
            for _ in group:
                order += Decimal("1")
                values_grouped_by_table = generate_values_for_one_or_more_tables(
                    models, fake, cache
                )

                for model in models:
                    values = values_grouped_by_table[model.baserow_table_id]
                    instance, relations = create_row_instance_and_relations(
                        values, table, model, fake, cache, order
                    )
                    rows[model.baserow_table_id].append((instance, relations))
                    progress.increment(1)

            for model in models:
                pbar.refresh()
                created_rows = bulk_create_rows(model, rows[model.baserow_table_id])
                RowHandler().update_dependencies_of_rows_created(model, created_rows)
                table_row_ids_map[model.baserow_table].extend(
                    [r.id for r in created_rows]
                )

        if not skip_tsvectors:
            for table, row_ids in table_row_ids_map.items():
                pbar.refresh()
                pbar.set_description(
                    f"Updating search data for table {table.pk} in worker {os.getpid()}"
                )
                SearchHandler.update_search_data(table, row_ids=row_ids)
