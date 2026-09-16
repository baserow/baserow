from unittest.mock import patch

import pytest

from baserow.core.agents.service import AgentService
from baserow.core.trash.handler import TrashHandler
from baserow.ws.tasks import broadcast_to_permitted_users
from baserow_enterprise.role.handler import RoleAssignmentHandler


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@pytest.mark.parametrize("event", ["create", "update", "delete", "restore"])
def test_agent_events_only_reach_users_allowed_to_list_agents(
    data_fixture, enable_enterprise, synced_roles, event
):
    """Lifecycle events use real RBAC checks before reaching the user transport."""

    admin = data_fixture.create_user()
    admin.web_socket_id = "origin"
    members = [data_fixture.create_user() for _ in range(4)]
    workspace = data_fixture.create_workspace(user=admin, members=members)
    handler = RoleAssignmentHandler()
    for member, role_uid in zip(members, ["BUILDER", "EDITOR", "VIEWER", "NO_ACCESS"]):
        handler.assign_role(member, workspace, handler.get_role_by_uid(role_uid))

    service = AgentService()
    agent = service.create_agent(admin, workspace, name="Private agent")
    if event == "restore":
        service.delete_agent(admin, agent)

    with (
        patch(
            "baserow.ws.signals.broadcast_to_permitted_users.delay",
            side_effect=broadcast_to_permitted_users,
        ),
        patch("baserow.ws.tasks.broadcast_to_users") as broadcast,
        patch("baserow.ws.signals.broadcast_to_group") as workspace_broadcast,
    ):
        if event == "create":
            agent = service.create_agent(admin, workspace, name="Private agent")
        elif event == "update":
            service.update_agent(admin, agent, name="Updated private agent")
        elif event == "delete":
            service.delete_agent(admin, agent)
        else:
            TrashHandler.restore_item(admin, "agent", agent.id)

    broadcast.assert_called_once()
    user_ids, payload = broadcast.call_args.args
    # Admins and Builders can list agents; Editors, Viewers and No access cannot.
    assert set(user_ids) == {admin.id, members[0].id}
    expected_type = {
        "create": "agent_created",
        "update": "agent_updated",
        "delete": "agent_deleted",
        "restore": "agent_created",
    }[event]
    assert payload["type"] == expected_type
    assert payload["workspace_id"] == workspace.id
    assert broadcast.call_args.kwargs["ignore_web_socket_id"] == (
        None if event == "restore" else "origin"
    )
    workspace_broadcast.delay.assert_not_called()
