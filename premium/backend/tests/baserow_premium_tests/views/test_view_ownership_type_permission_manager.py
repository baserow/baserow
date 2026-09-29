from django.contrib.auth.models import AnonymousUser

import pytest

from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.operations import (
    ListViewsOperationType,
    ReadViewOperationType,
)
from baserow.core.agents.handler import AgentHandler
from baserow.core.exceptions import PermissionDenied
from baserow.core.registries import object_scope_type_registry, operation_type_registry
from baserow.core.types import PermissionCheck
from baserow_enterprise.role.operations import (
    ReadRoleViewOperationType,
    UpdateRoleViewOperationType,
)
from baserow_enterprise.views.operations import (
    ListenToAllRestrictedViewEventsOperationType,
)
from baserow_premium.permission_manager import ViewOwnershipPermissionManagerType
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL


@pytest.mark.view_ownership
def test_all_operations_allowed_for_personal_views_have_been_checked_by_a_dev():
    view_scope_type = object_scope_type_registry.get("database_view")
    all_possible_view_operations = {
        op.type
        for op in operation_type_registry.get_all()
        if object_scope_type_registry.scope_type_includes_scope_type(
            view_scope_type, op.context_scope
        )
    }

    expected_ops_checked_by_manager = all_possible_view_operations

    assert (
        set(
            ViewOwnershipPermissionManagerType().ops_checked_by_this_manager
        ).difference(expected_ops_checked_by_manager)
        == set()
    ), (
        "You have added a new operation which works on a view or a child of a view. "
        "You must think carefully and add or ignore this new operation type to one of "
        "the lists found in ViewOwnershipPermissionManagerType.__init__ depending on "
        "if this new operation should be allowed for any viewer/commenter/editor on "
        "their own personal views or not."
    )
    assert expected_ops_checked_by_manager.difference(
        set(ViewOwnershipPermissionManagerType().ops_checked_by_this_manager)
    ) == set(
        [
            # The read and update role operation types are not related to the
            # personal views, so they don't have to be included.
            ListenToAllRestrictedViewEventsOperationType.type,
            ReadRoleViewOperationType.type,
            UpdateRoleViewOperationType.type,
        ]
    )


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_non_user_subjects_cannot_access_personal_views(data_fixture):
    """The ownership boundary applies without enumerating every subject type."""

    owner = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=workspace)
    )
    personal_view = data_fixture.create_grid_view(
        table=table,
        owned_by=owner,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )
    token = data_fixture.create_token(user=owner, workspace=workspace)
    manager = ViewOwnershipPermissionManagerType()
    check = PermissionCheck(token, ReadViewOperationType.type, personal_view)

    assert manager.actor_is_supported(token)
    result = manager.check_multiple_permissions([check], workspace)
    assert isinstance(result[check], PermissionDenied)
    assert not manager.filter_queryset(
        token,
        ListViewsOperationType.type,
        View.objects.filter(table=table),
        workspace,
    ).exists()


@pytest.mark.django_db
@pytest.mark.view_ownership
@pytest.mark.parametrize("actor_type", ["anonymous", "token", "agent"])
def test_non_user_subjects_skip_license_check_for_collaborative_views(
    data_fixture, mocker, actor_type
):
    """
    Non-user actors, like an anonymous user visiting a public view, must be left to
    the lower permission managers without checking per-user premium licenses.
    """

    owner = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=workspace)
    )
    view = data_fixture.create_grid_view(table=table, public=True)
    actor = {
        "anonymous": lambda: AnonymousUser(),
        "token": lambda: data_fixture.create_token(user=owner, workspace=workspace),
        "agent": lambda: AgentHandler().create_agent(workspace, name="Agent"),
    }[actor_type]()
    user_has_feature = mocker.patch(
        "baserow_premium.permission_manager.LicenseHandler.user_has_feature"
    )
    manager = ViewOwnershipPermissionManagerType()
    check = PermissionCheck(actor, ReadViewOperationType.type, view)

    assert manager.check_multiple_permissions([check], workspace) == {}
    user_has_feature.assert_not_called()
