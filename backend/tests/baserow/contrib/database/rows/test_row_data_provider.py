from decimal import Decimal

import pytest

from baserow.contrib.database.rows.data_providers import (
    HumanReadableFieldsDataProviderType,
    RowDataProviderType,
)
from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.dispatch_context import (
    DatabaseDispatchContext,
)


def _dispatch_context(data_fixture, user, table, row):
    button_field = data_fixture.create_button_field(table=table, label="Go")
    return DatabaseDispatchContext(user, button_field, row)


@pytest.mark.django_db
def test_values_keep_their_real_types(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="People",
        fields=[("Name", "text", {}), ("Age", "number", {})],
    )
    name_field = table.field_set.get(name="Name")
    age_field = table.field_set.get(name="Age")
    model = table.get_model()
    created = model.objects.create(
        **{f"field_{name_field.id}": "Ada", f"field_{age_field.id}": 36}
    )
    # Refetch: a freshly `.create()`d instance keeps the raw Python values it
    # was given, unconverted. The dispatch context carries a genuinely queried
    # row, so a real fetch is what exercises the type conversion under test.
    row = model.objects.get(pk=created.pk)
    dispatch_context = _dispatch_context(data_fixture, user, table, row)

    provider = RowDataProviderType()

    assert (
        provider.get_data_chunk(dispatch_context, [f"field_{name_field.id}"]) == "Ada"
    )
    age = provider.get_data_chunk(dispatch_context, [f"field_{age_field.id}"])
    assert age == Decimal("36")
    assert not isinstance(age, str)


@pytest.mark.django_db
def test_it_differs_from_the_human_readable_provider(data_fixture):
    """The difference IS the reason this provider exists (ADR 006 section 4)."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="People",
        fields=[("Age", "number", {})],
    )
    age_field = table.field_set.get(name="Age")
    model = table.get_model()
    created = model.objects.create(**{f"field_{age_field.id}": 36})
    # Refetch for the same reason as above: only a queried instance's number
    # field is normalized to Decimal by Django.
    row = model.objects.get(pk=created.pk)

    # Each provider is exercised through the context it is actually built
    # for: `HumanReadableFieldsDataProviderType` reads
    # `human_readable_row_values` off `HumanReadableRowContext`, while
    # `RowDataProviderType` reads `row` off `DatabaseDispatchContext`. Same
    # underlying row, same field, deliberately different context types.
    human_readable_context = HumanReadableRowContext(row)
    human_readable = HumanReadableFieldsDataProviderType().get_data_chunk(
        human_readable_context, [f"field_{age_field.id}"]
    )

    dispatch_context = _dispatch_context(data_fixture, user, table, row)
    raw = RowDataProviderType().get_data_chunk(
        dispatch_context, [f"field_{age_field.id}"]
    )

    assert human_readable == "36"
    assert isinstance(human_readable, str)
    assert raw == Decimal("36")
    assert not isinstance(raw, str)


@pytest.mark.django_db
def test_an_unknown_field_resolves_to_none(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    row = table.get_model().objects.create()
    dispatch_context = _dispatch_context(data_fixture, user, table, row)

    provider = RowDataProviderType()

    assert provider.get_data_chunk(dispatch_context, ["field_999999"]) is None
    assert provider.get_data_chunk(dispatch_context, []) is None
    assert provider.get_data_chunk(dispatch_context, ["field_1", "extra"]) is None


@pytest.mark.django_db
def test_it_resolves_through_the_registry(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="People",
        fields=[("Name", "text", {})],
    )
    name_field = table.field_set.get(name="Name")
    model = table.get_model()
    row = model.objects.create(**{f"field_{name_field.id}": "Ada"})
    dispatch_context = _dispatch_context(data_fixture, user, table, row)

    assert dispatch_context[f"row.field_{name_field.id}"] == "Ada"
