import pytest

from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.operations import (
    CancelAgentChatOperationType,
    CreateAgentToolOperationType,
    DecideAgentToolApprovalOperationType,
    DeleteAgentChatOperationType,
    ListAgentChatsOperationType,
    ReadAgentChatChannelOperationType,
    ReadAgentChatOperationType,
    ReadAgentDefinitionOperationType,
    ReadAgentTriggerOperationType,
    ReadAgentUsageOperationType,
    RunAgentChatOperationType,
    UpdateAgentChatChannelOperationType,
    UpdateAgentDefinitionOperationType,
    UpdateAgentTriggerOperationType,
)

READ_OPS = [
    ReadAgentDefinitionOperationType,
    ReadAgentTriggerOperationType,
    ListAgentChatsOperationType,
    ReadAgentChatOperationType,
    ReadAgentUsageOperationType,
]
RUN_OPS = [
    RunAgentChatOperationType,
    CancelAgentChatOperationType,
    DecideAgentToolApprovalOperationType,
]
CONFIGURE_OPS = [
    UpdateAgentDefinitionOperationType,
    UpdateAgentTriggerOperationType,
    CreateAgentToolOperationType,
    DeleteAgentChatOperationType,
    ReadAgentChatChannelOperationType,
    UpdateAgentChatChannelOperationType,
]


@pytest.mark.django_db
def test_agent_application_role_matrix(
    data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user(email="agent-admin@test.net")
    builder = data_fixture.create_user(email="agent-builder@test.net")
    editor = data_fixture.create_user(email="agent-editor@test.net")
    commenter = data_fixture.create_user(email="agent-commenter@test.net")
    viewer = data_fixture.create_user(email="agent-viewer@test.net")
    no_access = data_fixture.create_user(email="agent-no-access@test.net")

    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[
            (builder, "BUILDER"),
            (editor, "EDITOR"),
            (commenter, "COMMENTER"),
            (viewer, "VIEWER"),
            (no_access, "NO_ACCESS"),
        ],
    )
    application = CoreHandler().create_application(
        admin, workspace, "agent", init_with_data=True, name="Agent"
    )

    expectations = [
        (admin, READ_OPS + RUN_OPS + CONFIGURE_OPS, []),
        (builder, READ_OPS + RUN_OPS + CONFIGURE_OPS, []),
        (editor, READ_OPS + RUN_OPS, CONFIGURE_OPS),
        (commenter, READ_OPS, RUN_OPS + CONFIGURE_OPS),
        (viewer, READ_OPS, RUN_OPS + CONFIGURE_OPS),
        (no_access, [], READ_OPS + RUN_OPS + CONFIGURE_OPS),
    ]

    for user, allowed, denied in expectations:
        for operation in allowed:
            assert CoreHandler().check_permissions(
                user,
                operation.type,
                workspace=workspace,
                context=application,
            ), f"{user.email} should be allowed {operation.type}"
        for operation in denied:
            with pytest.raises(PermissionException):
                CoreHandler().check_permissions(
                    user,
                    operation.type,
                    workspace=workspace,
                    context=application,
                )
