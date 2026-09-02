"""
Reproduction of a customer report: builder pages with several data sources over
tables that are heavily linked together take seconds to dispatch on *every* request,
because `Table.get_model()` rebuilds the model class (and every link-row related
model) per request.

Run with:

    just b test tests/baserow/contrib/builder/api/data_sources/\
test_data_source_dispatch_link_row_perf.py -s --run-disabled-in-ci
"""

import time
from collections import Counter
from contextlib import contextmanager

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import LinkRowField
from baserow.contrib.database.table import models as table_models
from baserow.contrib.database.table.models import Table

ROWS_PER_TABLE = 25
LINKS_PER_ROW = 2
# A CRM table typically has a few dozen fields. The cost of a field attrs cache miss
# scales with the number of fields, so this matters for the numbers.
EXTRA_FIELDS_PER_TABLE = 20
WARMUP_REQUESTS = 1
MEASURED_REQUESTS = 10


@contextmanager
def instrument_model_generation():
    """
    Wraps `Table._get_model` and the field attrs cache lookup so that we can count,
    per request, how many model classes were built, how many of those were nested
    "related model" builds triggered by link row fields, and how much wall time
    was spent inside the top level builds.
    """

    stats = Counter()
    depth = {"value": 0}

    original_get_model = Table._get_model
    original_cached_attrs = table_models.get_cached_model_field_attrs

    def wrapped_get_model(self, *args, **kwargs):
        stats["_get_model_calls"] += 1
        if kwargs.get("manytomany_models") is not None:
            stats["nested_related_builds"] += 1
        else:
            stats["top_level_builds"] += 1
        stats[f"built_table_{self.id}"] += 1

        depth["value"] += 1
        started = time.perf_counter()
        try:
            return original_get_model(self, *args, **kwargs)
        finally:
            depth["value"] -= 1
            if depth["value"] == 0:
                stats["top_level_build_seconds"] += time.perf_counter() - started

    def wrapped_cached_attrs(table, *args, **kwargs):
        result = original_cached_attrs(table, *args, **kwargs)
        stats["field_attrs_cache_hits" if result else "field_attrs_cache_misses"] += 1
        return result

    Table._get_model = wrapped_get_model
    table_models.get_cached_model_field_attrs = wrapped_cached_attrs
    try:
        yield stats
    finally:
        Table._get_model = original_get_model
        table_models.get_cached_model_field_attrs = original_cached_attrs


def _create_table(data_fixture, user, database, name):
    table = data_fixture.create_database_table(user=user, database=database, name=name)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    creators = [
        data_fixture.create_text_field,
        data_fixture.create_long_text_field,
        data_fixture.create_number_field,
        data_fixture.create_boolean_field,
        data_fixture.create_date_field,
    ]
    for index in range(EXTRA_FIELDS_PER_TABLE):
        creators[index % len(creators)](table=table, name=f"Field {index}")
    return table


def _link(user, table, other, name):
    # `FieldHandler.create_field` also creates the reverse link row field in the
    # other table, which is what happens when a customer links tables in the UI.
    return FieldHandler().create_field(
        user, table, "link_row", name=name, link_row_table=other
    )


def _fill_rows(tables):
    rows_by_table = {}
    for table in tables:
        model = table.get_model()
        primary = table.field_set.get(primary=True)
        rows_by_table[table.id] = model.objects.bulk_create(
            [
                model(**{primary.db_column: f"{table.name} row {i}"})
                for i in range(ROWS_PER_TABLE)
            ]
        )

    for table in tables:
        model = table.get_model()
        link_fields = list(LinkRowField.objects.filter(table=table))
        for row in model.objects.all():
            for link_field in link_fields:
                target_rows = rows_by_table[link_field.link_row_table_id]
                offset = row.id % len(target_rows)
                targets = [
                    target_rows[(offset + i) % len(target_rows)].id
                    for i in range(LINKS_PER_ROW)
                ]
                getattr(row, link_field.db_column).set(targets)


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
def test_dispatch_page_data_sources_with_many_link_rows_perf(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    contacts = _create_table(data_fixture, user, database, "Contacts")
    companies = _create_table(data_fixture, user, database, "Companies")
    deals = _create_table(data_fixture, user, database, "Deals")
    tasks = _create_table(data_fixture, user, database, "Tasks")
    notes = _create_table(data_fixture, user, database, "Notes")
    products = _create_table(data_fixture, user, database, "Products")
    tables = [contacts, companies, deals, tasks, notes, products]

    # The customer's heaviest table has 12 link row fields. Spread them over the
    # five other tables (each `_link` also creates the reverse field there).
    link_targets = [companies] * 3 + [deals] * 3 + [tasks] * 2 + [notes] * 2
    link_targets += [products] * 2
    for index, target in enumerate(link_targets):
        _link(user, contacts, target, f"Contacts to {target.name} {index}")

    # Plus some links between the other tables so they all reference each other.
    _link(user, companies, deals, "Company deals")
    _link(user, deals, products, "Deal products")
    _link(user, tasks, deals, "Task deal")
    _link(user, notes, companies, "Note company")
    _link(user, products, tasks, "Product tasks")

    _fill_rows(tables)

    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    # 9 data sources across the 6 tables: a list on every table and a single row
    # lookup on the three most connected ones.
    for table in tables:
        data_fixture.create_builder_local_baserow_list_rows_data_source(
            user=user, page=page, integration=integration, table=table
        )
    for table in (contacts, companies, deals):
        first_row_id = table.get_model().objects.order_by("id").first().id
        data_fixture.create_builder_local_baserow_get_row_data_source(
            user=user,
            page=page,
            integration=integration,
            table=table,
            row_id=f"'{first_row_id}'",
        )

    link_row_counts = {
        table.name: table.field_set.filter(content_type__model="linkrowfield").count()
        for table in tables
    }

    url = reverse("api:builder:data_source:dispatch-all", kwargs={"page_id": page.id})

    def dispatch():
        with (
            instrument_model_generation() as stats,
            CaptureQueriesContext(connection) as queries,
        ):
            started = time.perf_counter()
            response = api_client.post(
                url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
            )
            elapsed = time.perf_counter() - started
        assert response.status_code == 200, response.json()
        # The endpoint reports per data source errors inside a 200 response.
        errors = {k: v for k, v in response.json().items() if "_error" in v}
        assert not errors, errors
        stats["request_seconds"] = elapsed
        stats["queries"] = len(queries)
        return stats

    for _ in range(WARMUP_REQUESTS):
        dispatch()

    runs = [dispatch() for _ in range(MEASURED_REQUESTS)]

    print("\n\nLink row fields per table:", link_row_counts)
    print(
        f"{'request ms':>11} {'in get_model ms':>16} {'builds':>7} "
        f"{'top':>4} {'nested':>7} {'attrs hit':>10} {'attrs miss':>11} "
        f"{'queries':>8}"
    )
    for stats in runs:
        print(
            f"{stats['request_seconds'] * 1000:>11.0f} "
            f"{stats['top_level_build_seconds'] * 1000:>16.0f} "
            f"{stats['_get_model_calls']:>7} "
            f"{stats['top_level_builds']:>4} "
            f"{stats['nested_related_builds']:>7} "
            f"{stats['field_attrs_cache_hits']:>10} "
            f"{stats['field_attrs_cache_misses']:>11} "
            f"{stats['queries']:>8}"
        )

    request_ms = sorted(stats["request_seconds"] * 1000 for stats in runs)
    print(
        f"request ms over {len(runs)} requests: "
        f"min {request_ms[0]:.0f} / median {request_ms[len(runs) // 2]:.0f} / "
        f"max {request_ms[-1]:.0f}"
    )

    last = runs[-1]
    per_table = {table.name: last[f"built_table_{table.id}"] for table in tables}
    print("Model builds per table in the last request:", per_table)

    # The first two assertions document the current behaviour rather than a
    # target: every request rebuilds every model class, and each table's model is
    # rebuilt once per table that links to it. The last one is a regression check:
    # the field attrs cache must hit for every build once it has been warmed up.
    assert last["top_level_builds"] == len(tables)
    assert last["nested_related_builds"] > len(tables)
    assert last["field_attrs_cache_misses"] == 0
