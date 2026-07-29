import pytest

from baserow.contrib.database.data_providers.registries import (
    database_data_provider_type_registry,
)
from baserow.contrib.database.workflow_actions.dispatch_context import (
    DatabaseDispatchContext,
)


@pytest.mark.django_db
def test_the_actor_is_the_clicking_user(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    dispatch_context = DatabaseDispatchContext(user, button_field, row)

    assert dispatch_context.actor == user
    assert dispatch_context.field == button_field
    assert dispatch_context.row == row


@pytest.mark.django_db
def test_the_actor_survives_a_clone(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    cloned = DatabaseDispatchContext(user, button_field, row).clone()

    assert cloned.actor == user
    assert cloned.field == button_field
    assert cloned.row == row


@pytest.mark.django_db
def test_nothing_about_it_is_public(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    dispatch_context = DatabaseDispatchContext(user, button_field, row)

    assert dispatch_context.is_publicly_searchable is False
    assert dispatch_context.is_publicly_filterable is False
    assert dispatch_context.is_publicly_sortable is False
    assert dispatch_context.search_query() is None
    assert dispatch_context.searchable_fields() == []
    assert dispatch_context.filters() is None
    assert dispatch_context.sortings() is None
    assert dispatch_context.public_allowed_properties is None


@pytest.mark.django_db
def test_it_uses_the_database_data_provider_registry(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    dispatch_context = DatabaseDispatchContext(user, button_field, row)

    assert (
        dispatch_context.data_provider_registry is database_data_provider_type_registry
    )
