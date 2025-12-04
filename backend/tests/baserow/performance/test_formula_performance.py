from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest
from pyinstrument import Profiler
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.management.commands.fill_table_rows import fill_table_rows
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import setup_interesting_test_table


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_adding_a_formula_field_compared_to_normal_field_isnt_slow(data_fixture):
    table, user, row, _, context = setup_interesting_test_table(data_fixture)
    count = 1000
    fill_table_rows(count, table)

    profiler = Profiler()
    profiler.start()
    field = FieldHandler().create_field(
        user=user, table=table, name="perf_formula", type_name="formula", formula="'1'"
    )
    profiler.stop()
    print("--------- Adding a formula field! -------")
    print(profiler.output_text(unicode=True, color=True))

    TrashHandler.permanently_delete(field)

    profiler = Profiler()
    profiler.start()
    FieldHandler().create_field(
        user=user, table=table, name="perf_text", type_name="text"
    )
    profiler.stop()
    print("--------- Adding a normal field! -------")
    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_very_nested_formula_field_change(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[["0"]], user=user
    )

    FieldHandler().create_field(
        user=user,
        table=table,
        name=f"perf_formula0",
        type_name="formula",
        formula="field('number')+1",
    )

    # Create many formulas each referencing the field next to them and adding on one
    last_field = None
    num_formulas = 200
    for i in range(1, num_formulas):
        print(f"Creating formula {i}")
        last_field = FieldHandler().create_field(
            user=user,
            table=table,
            name=f"perf_formula{i}",
            type_name="formula",
            formula=f"field('perf_formula{i - 1}')+1",
        )
    profiler = Profiler()
    profiler.start()
    # with django_assert_num_queries(1):
    table.get_model()
    created_row = RowHandler().create_row(user, table, {f"field_{fields[0].id}": 0})
    assert getattr(created_row, f"field_{last_field.id}") == Decimal(num_formulas)
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_creating_very_nested_formula_field(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        columns=[("perf_formula0", "number")], rows=[["0"]], user=user
    )
    fill_table_rows(10000, table)
    num_formulas = 100
    profiler = Profiler()
    profiler.start()
    for i in range(1, num_formulas):
        print(f"Making formula field {i}")
        FieldHandler().create_field(
            user=user,
            table=table,
            name=f"perf_formula{i}",
            type_name="formula",
            formula=f"field('perf_formula{i - 1}')+1",
        )
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_altering_very_nested_formula_field(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        columns=[("perf_formula0", "number")], rows=[["0"]], user=user
    )
    fill_table_rows(10000, table)
    num_formulas = 100
    first_field = None
    for i in range(1, num_formulas):
        print(f"Making formula field {i}")
        field = FieldHandler().create_field(
            user=user,
            table=table,
            name=f"perf_formula{i}",
            type_name="formula",
            formula=f"field('perf_formula{i - 1}')+1",
        )
        if i == 1:
            first_field = field
    profiler = Profiler()
    profiler.start()
    FieldHandler().update_field(
        user=user,
        table=table,
        field=first_field,
        formula="field('perf_formula0')+2",
    )
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_getting_data_from_a_very_nested_formula_field(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        columns=[("perf_formula0", "number")], rows=[["0"]], user=user
    )
    grid = data_fixture.create_grid_view(table=table)
    fill_table_rows(10000, table)
    num_formulas = 100
    for i in range(1, num_formulas):
        print(f"Making formula field {i}")
        FieldHandler().create_field(
            user=user,
            table=table,
            name=f"perf_formula{i}",
            type_name="formula",
            formula=f"field('perf_formula{i - 1}')+1",
        )
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    profiler = Profiler()
    profiler.start()
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    profiler.stop()
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 10001
    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_getting_data_from_normal_table(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        columns=[("perf_formula0", "number")], rows=[["0"]], user=user
    )
    grid = data_fixture.create_grid_view(table=table)
    fill_table_rows(10000, table)
    num_fields = 100
    for i in range(1, num_fields):
        print(f"Making field {i}")
        FieldHandler().create_field(
            user=user,
            table=table,
            name=f"normal_field{i}",
            type_name="text",
        )
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    profiler = Profiler()
    profiler.start()
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    profiler.stop()
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 10001
    print(profiler.output_text(unicode=True, color=True))


def add_fan_out_of(
    api_client,
    data_fixture,
    user,
    token,
    table,
    fanout,
    depth,
    profiler=None,
):
    if depth == 0:
        return None, None
    else:
        kwargs = {}
        if table is not None:
            kwargs["database"] = table.database
        new_table = data_fixture.create_database_table(
            user=user, name=f"table {depth}", **kwargs
        )
        new_table_primary_field = data_fixture.create_text_field(
            name="p", table=new_table, primary=True
        )
        if table is not None:
            link_row_field = FieldHandler().create_field(
                user,
                new_table,
                "link_row",
                name="linkrowfield",
                link_row_table=table,
            )
            table_model = table.get_model(attribute_names=True)
            new_table_model = new_table.get_model(attribute_names=True)
            for k, row in enumerate(table_model.objects.all()):
                for i in range(fanout):
                    new_row = new_table_model.objects.create(
                        p=f"table {depth} row {k} fanout {i}"
                    )
                    new_row.linkrowfield.add(row.id)
                    new_row.save()
        else:
            new_table_model = new_table.get_model(attribute_names=True)
            link_row_field = None
            for i in range(fanout):
                new_row = new_table_model.objects.create(p=f"table {depth} row {i}")

        related_field, nested_lookup_field = add_fan_out_of(
            api_client,
            data_fixture,
            user,
            token,
            new_table,
            fanout,
            depth - 1,
            profiler=profiler,
        )
        if related_field is not None:
            if profiler:
                profiler.start()
            new_lookup_field = FieldHandler().create_field(
                user,
                new_table,
                type_name="formula",
                name="formula",
                formula=f"lookup_by_id({related_field.link_row_related_field.id}, "
                f"{nested_lookup_field.id})",
            )
            if profiler:
                profiler.stop()
            return (
                link_row_field,
                new_lookup_field,
            )
        else:
            return link_row_field, new_table_primary_field


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
def test_fanout_one_off(data_fixture, api_client, django_assert_num_queries):
    user, token = data_fixture.create_user_and_token()
    p = Profiler()
    _, lookup_field = add_fan_out_of(
        api_client, data_fixture, user, token, None, 2, 2, profiler=p
    )
    print(p.output_text(unicode=True, color=True))
    url = reverse("api:database:rows:list", kwargs={"table_id": lookup_field.table.id})
    profiler = Profiler()
    profiler.start()
    with CaptureQueriesContext(connection) as captured:
        api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    # assert response.json() == {}
    profiler.stop()
    print(len(captured.captured_queries))
    print(p.last_session.duration)
    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
def test_fanout(data_fixture, api_client, django_assert_num_queries):
    results = [
        [
            "Mode",
            "Num tables depth",
            "Row fanout",
            "Get duration",
            "Num queries",
            "Time spent creating lookup fields",
        ]
    ]
    for num_tables in range(1, 4):
        for fanout in [2, 5, 8, 10]:
            user, token = data_fixture.create_user_and_token()
            creation_profiler = Profiler()
            _, lookup_field = add_fan_out_of(
                api_client,
                data_fixture,
                user,
                token,
                None,
                num_tables,
                fanout,
                profiler=creation_profiler,
            )
            url = reverse(
                "api:database:rows:list", kwargs={"table_id": lookup_field.table.id}
            )
            profiler = Profiler()
            profiler.start()
            with CaptureQueriesContext(connection) as captured:
                api_client.get(
                    url,
                    format="json",
                    HTTP_AUTHORIZATION=f"JWT {token}",
                )
            get_session = profiler.stop()
            results.append(
                [
                    num_tables,
                    fanout,
                    get_session.duration,
                    len(captured.captured_queries),
                    creation_profiler.last_session.duration,
                ]
            )
            print(profiler.output_text(unicode=True, color=True))
    print(results)
