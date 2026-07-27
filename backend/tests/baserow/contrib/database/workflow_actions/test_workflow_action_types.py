import pytest

from baserow.contrib.database.workflow_actions.models import (
    CreateRowWorkflowAction,
    DeleteRowWorkflowAction,
    UpdateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)


def test_the_three_types_are_registered():
    types = {t.type for t in database_workflow_action_type_registry.get_all()}

    assert types == {"create_row", "update_row", "delete_row"}


def test_types_map_to_their_models_and_services():
    registry = database_workflow_action_type_registry

    assert registry.get("create_row").model_class is CreateRowWorkflowAction
    assert registry.get("create_row").service_type == "local_baserow_upsert_row"
    assert registry.get("update_row").model_class is UpdateRowWorkflowAction
    assert registry.get("update_row").service_type == "local_baserow_upsert_row"
    assert registry.get("delete_row").model_class is DeleteRowWorkflowAction
    assert registry.get("delete_row").service_type == "local_baserow_delete_row"


@pytest.mark.django_db
def test_preparing_values_creates_the_backing_service(data_fixture):
    user = data_fixture.create_user()
    action_type = database_workflow_action_type_registry.get("create_row")

    prepared = action_type.prepare_values({}, user)

    assert prepared["service"] is not None
    assert prepared["service"].get_type().type == "local_baserow_upsert_row"


@pytest.mark.django_db
def test_preparing_values_updates_an_existing_service(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    action = data_fixture.create_database_workflow_action(CreateRowWorkflowAction)
    action_type = database_workflow_action_type_registry.get("create_row")

    action_type.prepare_values({"service": {"table_id": table.id}}, user, action)
    action.service.refresh_from_db()

    assert action.service.specific.table_id == table.id
