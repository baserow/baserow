from django.urls import reverse

import pytest

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.operations import (
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
    DeleteAgentConversationOperationType,
    ReadAgentConfigurationOperationType,
    ReadAgentConversationsOperationType,
    RestoreAgentConversationOperationType,
    UpdateAgentConversationOperationType,
)
from baserow.contrib.agent.service import AgentService
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.identities.handler import IdentityHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

READ = {
    ReadAgentConversationsOperationType.type,
    DeleteAgentConversationOperationType.type,
    RestoreAgentConversationOperationType.type,
}
WRITE = READ | {
    CreateAgentConversationOperationType.type,
    CreateAgentMessageOperationType.type,
    UpdateAgentConversationOperationType.type,
}
CONFIGURE = WRITE | {ReadAgentConfigurationOperationType.type}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,granted",
    [
        ("VIEWER", READ),
        ("COMMENTER", READ),
        ("EDITOR", WRITE),
        ("BUILDER", CONFIGURE),
        ("ADMIN", CONFIGURE),
    ],
)
def test_default_roles_grant_agent_operations(
    enterprise_data_fixture, enable_enterprise, synced_roles, role_uid, granted
):
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=enterprise_data_fixture.create_user(), members=[member]
    )
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    RoleAssignmentHandler().assign_role(
        member, workspace, Role.objects.get(uid=role_uid)
    )

    allowed = {
        operation
        for operation in CONFIGURE
        if CoreHandler().check_permissions(
            member,
            operation,
            workspace=workspace,
            context=agent,
            raise_permission_exceptions=False,
        )
    }

    assert allowed == granted


@pytest.mark.django_db
def test_an_editor_cannot_always_allow_and_nothing_is_decided(
    enterprise_data_fixture, enable_enterprise, synced_roles, mocker
):
    editor = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=enterprise_data_fixture.create_user(), members=[editor]
    )
    RoleAssignmentHandler().assign_role(
        editor, workspace, Role.objects.get(uid="EDITOR")
    )
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    identity = IdentityHandler().create_identity(workspace=workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "auth.User", identity.id
    agent.save()
    AgentHandler().set_allowed_tools(agent, ["create_rows"], ["create_rows"])
    approval = enterprise_data_fixture.create_agent_tool_approval(
        conversation=enterprise_data_fixture.create_agent_conversation(
            user=editor, agent=agent
        )
    )
    decide = mocker.spy(AgentHandler, "decide_approvals")

    with pytest.raises(PermissionException):
        AgentService().decide_approvals(
            editor,
            agent.id,
            approval.reply.conversation.uuid,
            [{"id": approval.id, "approved": True}],
            always_allow=True,
        )

    assert decide.call_count == 0
    approval.refresh_from_db()
    assert approval.status == "pending"
    assert AgentHandler().get_tool_configuration(agent)["ask_first_tools"] == [
        "create_rows"
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("role_uid", ["VIEWER", "EDITOR", "BUILDER", "ADMIN"])
def test_tool_diagnostics_require_build_access_on_this_agent(
    enterprise_data_fixture, enable_enterprise, synced_roles, api_client, role_uid
):
    user = enterprise_data_fixture.create_user()
    owner = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[user])
    roles = RoleAssignmentHandler()
    roles.assign_role(user, workspace, Role.objects.get(uid="VIEWER"))
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    roles.assign_role(
        user, workspace, Role.objects.get(uid=role_uid), scope=agent.application_ptr
    )
    api_client.force_authenticate(user)

    def history(shared):
        conversation = enterprise_data_fixture.create_agent_conversation(
            user=owner, agent=agent, shared=shared
        )
        enterprise_data_fixture.create_agent_message(
            conversation=conversation,
            role="assistant",
            status="completed",
            tool_errors={"step": "PRIVATE_DIAGNOSIS"},
        )
        return api_client.get(
            reverse(
                "api:agent:messages",
                kwargs={"agent_id": agent.id, "conversation_uuid": conversation.uuid},
            )
        )

    response = history(shared=True)
    assert response.status_code == 200
    message = response.json()["results"][0]
    if role_uid in ("BUILDER", "ADMIN"):
        assert message["tool_errors"] == {"step": "PRIVATE_DIAGNOSIS"}
    else:
        assert "tool_errors" not in message
        assert b"PRIVATE_DIAGNOSIS" not in response.content
    assert history(shared=False).status_code == 404
