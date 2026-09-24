import pytest

from baserow.contrib.database.data_providers.registries import (
    database_data_provider_type_registry,
)
from baserow.contrib.database.rows.data_providers import RowDataProviderType
from baserow.contrib.database.workflow_actions.data_providers import (
    PreviousActionDataProviderType,
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
def test_it_requires_a_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    row = table.get_model().objects.create()

    with pytest.raises(TypeError):
        DatabaseDispatchContext(user, None, row)


@pytest.mark.django_db
def test_it_requires_a_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")

    with pytest.raises(TypeError):
        DatabaseDispatchContext(user, button_field, None)


@pytest.mark.django_db
def test_the_guard_does_not_break_clone(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    # `clone()` rebuilds via `own_properties`, which always supplies field and
    # row, so the constructor's guard must not reject it.
    cloned = DatabaseDispatchContext(user, button_field, row).clone()

    assert cloned.field == button_field
    assert cloned.row == row


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


@pytest.mark.django_db
def test_previous_action_results_are_shared_with_a_clone(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    dispatch_context = DatabaseDispatchContext(user, button_field, row)
    cloned = dispatch_context.clone()

    # A service clones the context, and an action dispatched through the clone
    # must land its result where the next action reads it.
    cloned.cache[PreviousActionDataProviderType.CACHE_KEY][1] = {"id": 7}

    assert dispatch_context.cache[PreviousActionDataProviderType.CACHE_KEY] == {
        1: {"id": 7}
    }


@pytest.mark.django_db
def test_start_action_keeps_previous_action_results(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    dispatch_context = DatabaseDispatchContext(user, button_field, row)
    dispatch_context.cache[RowDataProviderType.CACHE_KEY]["row"] = row
    dispatch_context.cache[PreviousActionDataProviderType.CACHE_KEY][1] = {"id": 7}

    dispatch_context.start_action()

    # The row is re-read per action, results are not: they are what the rest of
    # the sequence chains from.
    assert dispatch_context.cache[RowDataProviderType.CACHE_KEY] == {}
    assert dispatch_context.cache[PreviousActionDataProviderType.CACHE_KEY] == {
        1: {"id": 7}
    }
