from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.database.api.fields.serializers import (
    AvailableCollaboratorsSerializer,
)
from baserow.contrib.database.fields.exceptions import (
    AllProvidedCollaboratorIdsMustBeValidUsers,
)
from baserow.contrib.database.fields.field_types import MultipleCollaboratorsFieldType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.agents.handler import AgentHandler
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceUser
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.trash.handler import TrashHandler


@pytest.fixture
def agent_collaborator_table(data_fixture):
    person = data_fixture.create_user(first_name="Person")
    table = data_fixture.create_database_table(user=person)
    workspace = table.database.workspace
    agent = data_fixture.create_agent(workspace=workspace, name="Ops")
    field = data_fixture.create_multiple_collaborators_field(
        table=table, notify_user_when_added=True
    )
    return person, table, agent, field


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state", ["inactive", "trashed", "deleting", "foreign", "multiple_memberships"]
)
def test_only_eligible_workspace_agents_are_collaborators(
    data_fixture, agent_collaborator_table, state
):
    person, table, agent, field = agent_collaborator_table
    workspace = table.database.workspace
    if state == "inactive":
        agent.is_active = False
        agent.save(update_fields=["is_active"])
    elif state == "trashed":
        agent.profile.trashed = True
        agent.profile.save(update_fields=["trashed"])
    elif state == "deleting":
        agent.profile.to_be_deleted = True
        agent.profile.save(update_fields=["to_be_deleted"])
    elif state == "foreign":
        workspace = data_fixture.create_workspace(user=person)
        field.table.database.workspace = workspace
    else:
        WorkspaceUser.objects.create(
            user=agent, workspace=data_fixture.create_workspace(trashed=True), order=0
        )
    collaborators = CoreHandler().get_workspace_collaborators(workspace)
    assert set(collaborators.values_list("id", flat=True)) == {person.id}
    with pytest.raises(AllProvidedCollaboratorIdsMustBeValidUsers):
        MultipleCollaboratorsFieldType().prepare_value_for_db(field, [{"id": agent.id}])


@pytest.mark.django_db
def test_agent_assignment_bulk_validation_and_trash_restore(agent_collaborator_table):
    person, table, agent, field = agent_collaborator_table
    field_type = MultipleCollaboratorsFieldType()
    assert field_type.prepare_value_for_db_in_bulk(field, {0: [{"id": agent.id}]}) == {
        0: [agent.id]
    }
    row = RowHandler().create_row(person, table, {field.id: [{"id": agent.id}]})
    assert not NotificationRecipient.objects.filter(recipient_id=agent.id).exists()
    model = table.get_model()
    assert list(
        getattr(model.objects.get(id=row.id), field.db_column).values_list(
            "id", flat=True
        )
    ) == [agent.id]
    AgentHandler().delete_agent(person, agent)
    assert not getattr(model.objects.get(id=row.id), field.db_column).exists()
    TrashHandler.restore_item(person, "agent", agent.profile.id)
    assert list(
        getattr(model.objects.get(id=row.id), field.db_column).values_list(
            "id", flat=True
        )
    ) == [agent.id]


@pytest.mark.django_db
def test_available_collaborator_metadata_has_identity_without_changing_cell_values(
    agent_collaborator_table,
):
    person, table, agent, field = agent_collaborator_table
    available = AvailableCollaboratorsSerializer().to_representation(field)
    assert available == [
        {"id": agent.id, "name": "Ops", "identity_type": "agent"},
        {"id": person.id, "name": "Person", "identity_type": "human"},
    ]
    row = RowHandler().create_row(person, table, {field.id: [{"id": agent.id}]})
    value = getattr(table.get_model().objects.get(id=row.id), field.db_column)
    serialized = (
        MultipleCollaboratorsFieldType()
        .get_response_serializer_field(field)
        .to_representation(value.all())
    )
    assert serialized == [{"id": agent.id, "name": "Ops"}]


@pytest.mark.django_db
def test_field_list_includes_agent_collaborators_with_constant_queries(
    agent_collaborator_table, data_fixture, api_client
):
    """Agent users test plan 8.3.1."""

    person, table, agent, field = agent_collaborator_table
    token = data_fixture.generate_token(person)
    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})

    def list_fields():
        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        return response.json(), len(queries)

    fields, _ = list_fields()
    collaborators = next(f for f in fields if f["id"] == field.id)[
        "available_collaborators"
    ]
    assert {(c["id"], c["identity_type"]) for c in collaborators} == {
        (person.id, "human"),
        (agent.id, "agent"),
    }

    query_count = list_fields()[1]
    for _ in range(3):
        data_fixture.create_user(workspace=table.database.workspace)
    assert list_fields()[1] == query_count
