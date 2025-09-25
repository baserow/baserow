import pytest
from baserow_premium.permission_manager import ViewOwnershipPermissionManagerType

from baserow.core.registries import object_scope_type_registry, operation_type_registry
from baserow_enterprise.role.operations import (
    ReadRoleViewOperationType,
    UpdateRoleViewOperationType,
)
from baserow_enterprise.views.operations import (
    ListenToAllRestrictedViewEventsOperationType,
)


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
