"""
Tests for grouped service filters on Local Baserow services. Filter groups let
service filters be nested and combined with their own AND/OR operator, mirroring the
database grid view. Ungrouped filters must keep behaving exactly as before.
"""

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowListRowsUserServiceType,
)
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext, fake_import_formula


def _build_ingredient_cost_table(data_fixture, user):
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    database = data_fixture.create_database_application(workspace=builder.workspace)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
            ("Cost", "number", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")
    cost = table.field_set.get(name="Cost")
    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{ingredient.id}": "Duck", f"field_{cost.id}": 50},
                {f"field_{ingredient.id}": "Goose", f"field_{cost.id}": 150},
                {f"field_{ingredient.id}": "Beef", f"field_{cost.id}": 250},
            ],
        )
        .created_rows
    )
    return integration, table, ingredient, cost, rows


@pytest.mark.django_db
def test_dispatch_with_filter_groups(data_fixture):
    """
    (ingredient=Duck AND cost=50) OR (ingredient=Goose AND cost=150) should match
    the first two rows, but not Beef.
    """

    user = data_fixture.create_user()
    integration, table, ingredient, cost, rows = _build_ingredient_cost_table(
        data_fixture, user
    )
    [duck, goose, _beef] = rows

    service = data_fixture.create_local_baserow_list_rows_service(
        table=table, integration=integration, filter_type="OR"
    )

    group_duck = data_fixture.create_local_baserow_table_service_filter_group(
        service=service, filter_type="AND"
    )
    group_goose = data_fixture.create_local_baserow_table_service_filter_group(
        service=service, filter_type="AND"
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=ingredient, value="Duck", order=0, group=group_duck
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=cost, value="50", order=1, group=group_duck
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=ingredient, value="Goose", order=2, group=group_goose
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=cost, value="150", order=3, group=group_goose
    )

    service_type = LocalBaserowListRowsUserServiceType()
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    assert [r.id for r in dispatch_data["results"]] == [duck.id, goose.id]


@pytest.mark.django_db
def test_dispatch_with_nested_filter_groups(data_fixture):
    """
    ingredient=Beef OR (cost=50 OR cost=150). A subgroup nested under a group, both OR,
    with the root AND-ing a single (always-true here) condition. Matches all 3 rows.
    """

    user = data_fixture.create_user()
    integration, table, ingredient, cost, rows = _build_ingredient_cost_table(
        data_fixture, user
    )
    [duck, goose, beef] = rows

    service = data_fixture.create_local_baserow_list_rows_service(
        table=table, integration=integration, filter_type="OR"
    )

    outer = data_fixture.create_local_baserow_table_service_filter_group(
        service=service, filter_type="OR"
    )
    inner = data_fixture.create_local_baserow_table_service_filter_group(
        service=service, filter_type="OR", parent_group=outer
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=ingredient, value="Beef", order=0, group=outer
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=cost, value="50", order=1, group=inner
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=cost, value="150", order=2, group=inner
    )

    service_type = LocalBaserowListRowsUserServiceType()
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    assert sorted(r.id for r in dispatch_data["results"]) == sorted(
        [duck.id, goose.id, beef.id]
    )


@pytest.mark.django_db
def test_dispatch_ungrouped_filters_unchanged(data_fixture):
    """
    Backward-compat: filters without a group are combined under the service's
    top-level filter_type, exactly as before groups existed.
    """

    user = data_fixture.create_user()
    integration, table, ingredient, cost, rows = _build_ingredient_cost_table(
        data_fixture, user
    )
    [duck, goose, _beef] = rows

    service = data_fixture.create_local_baserow_list_rows_service(
        table=table, integration=integration, filter_type="OR"
    )
    # ingredient=Duck OR ingredient=Goose, no groups.
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=ingredient, value="Duck", order=0
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=ingredient, value="Goose", order=1
    )

    service_type = LocalBaserowListRowsUserServiceType()
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    assert sorted(r.id for r in dispatch_data["results"]) == sorted([duck.id, goose.id])


@pytest.mark.django_db
def test_export_import_preserves_filter_groups(data_fixture):
    user = data_fixture.create_user()
    integration, table, ingredient, cost, _rows = _build_ingredient_cost_table(
        data_fixture, user
    )
    service = data_fixture.create_local_baserow_list_rows_service(
        table=table, integration=integration, filter_type="OR"
    )
    outer = data_fixture.create_local_baserow_table_service_filter_group(
        service=service, filter_type="AND"
    )
    inner = data_fixture.create_local_baserow_table_service_filter_group(
        service=service, filter_type="OR", parent_group=outer
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=ingredient, value="'Duck'", order=0, group=outer
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=cost, value="'50'", order=1, group=inner
    )

    service_type = service_type_registry.get("local_baserow_list_rows")
    exported = service_type.export_serialized(service)

    assert len(exported["filter_groups"]) == 2
    assert len(exported["filters"]) == 2

    imported_service = service_type.import_serialized(
        integration, exported, {}, import_formula=fake_import_formula
    )

    groups = list(imported_service.service_filter_groups.order_by("id"))
    assert len(groups) == 2
    imported_outer, imported_inner = groups
    assert imported_outer.filter_type == "AND"
    assert imported_outer.parent_group_id is None
    assert imported_inner.filter_type == "OR"
    # The nested group's parent was remapped to the newly-created outer group.
    assert imported_inner.parent_group_id == imported_outer.id

    filters = list(imported_service.service_filters.order_by("order"))
    assert filters[0].group_id == imported_outer.id
    assert filters[1].group_id == imported_inner.id


@pytest.mark.django_db
def test_update_service_filters_with_groups_via_correlation_ids(data_fixture):
    """
    The PATCH path deletes and recreates all filters and groups, linking them via
    opaque correlation ids (client-generated strings for new items).
    """

    user = data_fixture.create_user()
    integration, table, ingredient, cost, _rows = _build_ingredient_cost_table(
        data_fixture, user
    )
    service = data_fixture.create_local_baserow_list_rows_service(
        table=table, integration=integration, filter_type="AND"
    )
    service_type = LocalBaserowListRowsUserServiceType()

    service_filter_groups = [
        {"id": "group-a", "filter_type": "OR", "parent_group_id": None},
        {"id": "group-b", "filter_type": "AND", "parent_group_id": "group-a"},
    ]
    service_filters = [
        {
            "field": ingredient,
            "type": "equal",
            "value": {"formula": "Duck", "mode": "raw", "version": "0.1"},
            "value_is_formula": False,
            "group_id": "group-a",
        },
        {
            "field": cost,
            "type": "equal",
            "value": {"formula": "50", "mode": "raw", "version": "0.1"},
            "value_is_formula": False,
            "group_id": "group-b",
        },
    ]

    service_type.update_service_filters(
        service,
        service_filters=service_filters,
        service_filter_groups=service_filter_groups,
    )

    groups = list(service.service_filter_groups.order_by("id"))
    assert len(groups) == 2
    group_a, group_b = groups
    assert group_a.parent_group_id is None
    assert group_b.parent_group_id == group_a.id

    filters = list(service.service_filters.order_by("order"))
    assert filters[0].group_id == group_a.id
    assert filters[1].group_id == group_b.id
