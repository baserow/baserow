import pytest

from baserow.contrib.dashboard.actions import (
    RotateDashboardSlugActionType,
    UpdateDashboardSharingActionType,
)
from baserow.contrib.dashboard.models import Dashboard
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import (
    ApplicationActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.actions import UpdateApplicationActionType
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_dashboard_application(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Dashboard 1", description="Description 1", user=user
    )

    # update dashboard description
    action_type_registry.get_by_type(UpdateApplicationActionType).do(
        user, dashboard, name="Updated name", description="Updated description"
    )

    dashboard.refresh_from_db()
    assert dashboard.name == "Updated name"
    assert dashboard.description == "Updated description"

    # undo
    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    dashboard.refresh_from_db()
    assert dashboard.name == "Dashboard 1"
    assert dashboard.description == "Description 1"

    # redo
    actions_redone = ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [UpdateApplicationActionType])

    dashboard.refresh_from_db()
    assert dashboard.name == "Updated name"
    assert dashboard.description == "Updated description"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_rotate_dashboard_slug(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    dashboard = data_fixture.create_dashboard_application(user=user, public=True)
    original_slug = dashboard.slug

    dashboard = action_type_registry.get_by_type(RotateDashboardSlugActionType).do(
        user, dashboard.id
    )
    rotated_slug = dashboard.slug
    assert rotated_slug != original_slug

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(dashboard.id)], session_id
    )

    dashboard.refresh_from_db()
    assert dashboard.slug == original_slug

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(dashboard.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [RotateDashboardSlugActionType])

    dashboard.refresh_from_db()
    assert dashboard.slug == rotated_slug


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_dashboard_sharing(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    dashboard = data_fixture.create_dashboard_application(user=user)

    action_type_registry.get_by_type(UpdateDashboardSharingActionType).do(
        user,
        dashboard.id,
        public=True,
        public_password=Dashboard.make_password("secret-password"),
    )

    dashboard.refresh_from_db()
    assert dashboard.public is True
    assert dashboard.check_public_password("secret-password")

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(dashboard.id)], session_id
    )

    dashboard.refresh_from_db()
    assert dashboard.public is False
    assert dashboard.public_password == ""

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(dashboard.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        actions_redone, [UpdateDashboardSharingActionType]
    )

    dashboard.refresh_from_db()
    assert dashboard.public is True
    assert dashboard.check_public_password("secret-password")


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_update_dashboard_sharing_only_restores_the_provided_fields(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    dashboard = data_fixture.create_dashboard_application(
        user=user, public=True, show_logo=True
    )

    action_type_registry.get_by_type(UpdateDashboardSharingActionType).do(
        user, dashboard.id, show_logo=False
    )
    # A change made in between must survive the undo of the logo change.
    dashboard.refresh_from_db()
    dashboard.public = False
    dashboard.save()

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(dashboard.id)], session_id
    )

    dashboard.refresh_from_db()
    assert dashboard.show_logo is True
    assert dashboard.public is False


@pytest.mark.django_db
def test_update_dashboard_sharing_action_description(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(
        user=user, name="Ada's dashboard"
    )

    action_type_registry.get_by_type(UpdateDashboardSharingActionType).do(
        user,
        dashboard.id,
        public=True,
        public_password=Dashboard.make_password("secret-password"),
    )

    action = Action.objects.get(type=UpdateDashboardSharingActionType.type)
    description = UpdateDashboardSharingActionType.get_long_description(action.params)
    assert description == (
        "Sharing settings updated (made public, password set) "
        f'in dashboard "Ada\'s dashboard" ({dashboard.id}).'
    )
    # Neither the password nor its hash may ever reach the audit log.
    assert "secret-password" not in description
    assert action.params["data"]["public_password"] not in description


HASH = Dashboard.make_password("secret-password")
OTHER_HASH = Dashboard.make_password("other-password")


@pytest.mark.parametrize(
    "data,original_data,expected",
    [
        (
            {"public": True, "public_password": ""},
            {"public": False, "public_password": ""},
            "made public",
        ),
        (
            {"public": False, "public_password": ""},
            {"public": True, "public_password": HASH},
            "made private, password removed",
        ),
        ({"public_password": HASH}, {"public_password": ""}, "password set"),
        (
            {"public_password": OTHER_HASH},
            {"public_password": HASH},
            "password changed",
        ),
        ({"public_password": HASH}, {"public_password": HASH}, "nothing changed"),
        ({"show_logo": False}, {"show_logo": True}, "Baserow logo hidden"),
        ({"show_logo": True}, {"show_logo": False}, "Baserow logo shown"),
        ({"public": True}, {"public": True}, "nothing changed"),
        ({}, {}, "nothing changed"),
    ],
)
def test_update_dashboard_sharing_action_describe_changes(
    data, original_data, expected
):
    changes = UpdateDashboardSharingActionType.describe_changes(data, original_data)
    assert ", ".join(str(change) for change in changes) == expected
