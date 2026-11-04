import pytest

from baserow.core.agents.service import AgentService as IdentityService
from baserow.core.models import Agent
from baserow.ws.tasks import broadcast_to_permitted_users
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
def test_identity_invalidation_reaches_application_builders_without_workspace_listing(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    mocker,
    django_capture_on_commit_callbacks,
):
    admin = enterprise_data_fixture.create_user()
    builder = enterprise_data_fixture.create_user()
    viewer = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[builder, viewer]
    )
    application = enterprise_data_fixture.create_agent_application(workspace=workspace)
    other_application = enterprise_data_fixture.create_agent_application(
        workspace=workspace
    )
    identity = Agent.objects.create(workspace=workspace, name="PRIVATE IDENTITY")
    application.run_as_subject_type = "core.Agent"
    application.run_as_subject_id = identity.id
    application.save()
    roles = RoleAssignmentHandler()
    for user in [builder, viewer]:
        roles.assign_role(user, workspace, Role.objects.get(uid="VIEWER"))
    roles.assign_role(
        builder,
        workspace,
        Role.objects.get(uid="BUILDER"),
        scope=application.application_ptr,
    )
    # Execute the real recipient permission check, stopping at the channel send.
    mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_permitted_users.delay",
        side_effect=broadcast_to_permitted_users,
    )
    sent = mocker.patch("baserow.ws.tasks.broadcast_to_users")

    with django_capture_on_commit_callbacks(execute=True):
        IdentityService().update_agent(admin, identity, name="PRIVATE NEW NAME")

    refreshes = {
        entry.args[1]["agent_id"]: (set(entry.args[0]), entry.args[1])
        for entry in sent.call_args_list
        if entry.args[1]["type"] == "agent_run_as_updated"
    }
    assert refreshes == {
        application.id: (
            {admin.id, builder.id},
            {
                "type": "agent_run_as_updated",
                "agent_id": application.id,
                "selected_identity_changed": True,
            },
        ),
        other_application.id: (
            {admin.id},
            {
                "type": "agent_run_as_updated",
                "agent_id": other_application.id,
                "selected_identity_changed": False,
            },
        ),
    }
    management = [
        entry
        for entry in sent.call_args_list
        if entry.args[1]["type"] == "agent_updated"
    ]
    assert len(management) == 1
    assert set(management[0].args[0]) == {admin.id}
