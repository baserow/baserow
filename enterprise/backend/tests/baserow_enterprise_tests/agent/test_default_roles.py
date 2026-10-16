import pytest

from baserow.contrib.agent.operations import ReadAgentSettingsOperationType
from baserow.core.handler import CoreHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

CONFIGURE = {ReadAgentSettingsOperationType.type}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,granted",
    [
        ("VIEWER", set()),
        ("COMMENTER", set()),
        ("EDITOR", set()),
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
