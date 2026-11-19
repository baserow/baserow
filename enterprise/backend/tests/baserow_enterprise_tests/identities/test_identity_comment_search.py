import pytest
from baserow_premium_tests.row_comments.utils import (
    create_comment,
    create_comment_scenario,
    found_comments,
)

from baserow.contrib.database.rows.operations import ReadDatabaseRowOperationType
from baserow.core.exceptions import PermissionDenied
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_premium.row_comments.tools import search_row_comments


@pytest.mark.django_db
def test_search_as_an_identity_finds_the_comments_mentioning_it(
    enterprise_data_fixture, synced_roles, enable_enterprise
):
    scenario = create_comment_scenario(enterprise_data_fixture)
    identity = enterprise_data_fixture.create_identity(
        workspace=scenario.ctx.workspace, role_uid="ADMIN", name="Helper"
    )
    scenario.comments.append(
        create_comment(scenario.bob, scenario.task_rows[0], "Help", [identity], day=5)
    )
    scenario.ctx.user = identity

    result = search_row_comments(
        scenario.ctx, scenario.database.id, mentioned_users=[0]
    )

    assert [comment["id"] for comment in result["comments"]] == [
        scenario.comments[4].id
    ]
    assert result["comments"][0]["mentions"] == [{"id": identity.id, "name": "Helper"}]
    assert found_comments(scenario, mentioned_users=["help"]) == [5]


@pytest.mark.django_db
@pytest.mark.parametrize("without_row_read", [False, True])
def test_search_requires_both_row_and_comment_read_permissions(
    enterprise_data_fixture, synced_roles, enable_enterprise, without_row_read
):
    scenario = create_comment_scenario(enterprise_data_fixture)
    workspace = scenario.ctx.workspace
    builder = Role.objects.get(uid="BUILDER")
    if without_row_read:
        table_role = Role.objects.create(
            uid="no_row_read", name="No row read", workspace=workspace
        )
        table_role.operations.set(
            builder.operations.exclude(name=ReadDatabaseRowOperationType.type)
        )
    else:
        table_role = Role.objects.get(uid="VIEWER")
    roles = RoleAssignmentHandler()
    roles.assign_role(scenario.bob, workspace, role=builder)
    roles.assign_role(scenario.bob, workspace, role=table_role, scope=scenario.tasks)
    scenario.ctx.user = scenario.bob

    assert found_comments(scenario) == [2, 1]
    with pytest.raises(PermissionDenied):
        found_comments(scenario, table_ids=[scenario.tasks.id])
