import pytest

from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)


def test_the_four_types_are_registered():
    types = {t.type for t in database_workflow_action_type_registry.get_all()}

    assert types == {
        "local_baserow_create_row",
        "local_baserow_update_row",
        "local_baserow_delete_row",
        "open_url",
    }


def test_types_map_to_their_models_and_services():
    registry = database_workflow_action_type_registry

    assert (
        registry.get("local_baserow_create_row").model_class
        is LocalBaserowCreateRowWorkflowAction
    )
    assert (
        registry.get("local_baserow_create_row").service_type
        == "local_baserow_upsert_row"
    )
    assert (
        registry.get("local_baserow_update_row").model_class
        is LocalBaserowUpdateRowWorkflowAction
    )
    assert (
        registry.get("local_baserow_update_row").service_type
        == "local_baserow_upsert_row"
    )
    assert (
        registry.get("local_baserow_delete_row").model_class
        is LocalBaserowDeleteRowWorkflowAction
    )
    assert (
        registry.get("local_baserow_delete_row").service_type
        == "local_baserow_delete_row"
    )


@pytest.mark.django_db
def test_preparing_values_creates_the_backing_service(data_fixture):
    user = data_fixture.create_user()
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    prepared = action_type.prepare_values({}, user)

    assert prepared["service"] is not None
    assert prepared["service"].get_type().type == "local_baserow_upsert_row"


@pytest.mark.django_db
def test_preparing_values_updates_an_existing_service(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction
    )
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    action_type.prepare_values({"service": {"table_id": table.id}}, user, action)
    action.service.refresh_from_db()

    assert action.service.specific.table_id == table.id


@pytest.mark.django_db
def test_preparing_values_never_attaches_an_integration(data_fixture):
    # `integration_id` is resolved without a permission check, so an
    # integration the caller cannot reach would run every click as its user.
    user = data_fixture.create_user()
    victim = data_fixture.create_user()
    victim_integration = data_fixture.create_local_baserow_integration(
        user=victim, authorized_user=victim
    )
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction
    )
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    action_type.prepare_values(
        {"service": {"integration_id": victim_integration.id}}, user, action
    )
    action.service.refresh_from_db()

    assert action.service.integration_id is None


@pytest.mark.django_db
def test_dispatching_refuses_a_service_carrying_an_integration(data_fixture):
    # Defence in depth for the strip above.
    victim = data_fixture.create_user()
    victim_integration = data_fixture.create_local_baserow_integration(
        user=victim, authorized_user=victim
    )
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction
    )
    service = action.service.specific
    service.integration = victim_integration
    service.save()
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        # The guard runs before the context is used.
        action_type.dispatch(action, None)


@pytest.mark.django_db
def test_open_url_action_is_frontend_only_and_has_no_service(data_fixture):
    field = data_fixture.create_button_field()
    action = DatabaseWorkflowActionHandler().create_workflow_action(
        database_workflow_action_type_registry.get("open_url"),
        field=field,
        url={"formula": "'https://example.com'", "mode": "simple"},
    )

    assert action.get_type().is_frontend_only is True
    assert action.url["formula"] == "'https://example.com'"
    assert action.target == "self"
    assert not hasattr(action, "service")
