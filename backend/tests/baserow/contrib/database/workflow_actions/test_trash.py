import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.workflow_actions.models import (
    CreateRowWorkflowAction,
    DatabaseWorkflowAction,
)
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_actions_survive_trashing_and_restoring_the_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field
    )

    FieldHandler().delete_field(user, button_field)

    assert DatabaseWorkflowAction.objects.filter(id=action.id).exists()

    TrashHandler.restore_item(user, "field", button_field.id)

    assert DatabaseWorkflowAction.objects.filter(id=action.id).exists()
