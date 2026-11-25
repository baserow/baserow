import pytest

from baserow.contrib.agent.action_tools.handler import AgentActionHandler
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.handler import AgentHandler

READING = ("local_baserow_get_row", "local_baserow_list_rows")
CHANGING = (
    "local_baserow_create_row",
    "local_baserow_update_row",
    "local_baserow_delete_row",
)


@pytest.mark.django_db
def test_an_identity_that_only_reads_is_refused_the_actions_that_change_rows(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    fixture = enterprise_data_fixture
    user = fixture.create_user()
    workspace = fixture.create_workspace(user=user)
    database = fixture.create_database_application(workspace=workspace)
    table = fixture.create_database_table(database=database)
    agent = fixture.create_agent_application(user=user, workspace=workspace)
    for type_name in (*READING, *CHANGING):
        action = AgentActionService().create_action(user, agent.id, type_name)
        AgentActionService().update_action(
            user, agent.id, action.id, service_values={"table_id": table.id}
        )

    def errors_by_type(role_uid):
        identity = fixture.create_identity(workspace=workspace, role_uid=role_uid)
        AgentHandler().update_configuration(
            agent, run_as_subject_type="auth.User", run_as_subject_id=identity.id
        )
        handler = AgentActionHandler()
        actions = handler.list_actions(agent)
        errors = handler.get_configuration_errors_by_action(agent, actions)
        return {action.get_type_name(): errors[action.id] for action in actions}

    assert errors_by_type("VIEWER") == {
        **dict.fromkeys(READING, {}),
        **dict.fromkeys(CHANGING, {"table_id": "forbidden"}),
    }
    assert errors_by_type("EDITOR") == dict.fromkeys((*READING, *CHANGING), {})
