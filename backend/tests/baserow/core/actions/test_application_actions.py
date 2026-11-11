from django.db import transaction

import pytest
from pytest_unordered import unordered

from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.actions import (
    CreateApplicationActionType,
    DeleteApplicationActionType,
    DuplicateApplicationActionType,
    InstallTemplateActionType,
    OrderApplicationsActionType,
    UpdateApplicationActionType,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import Application
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_order_applications(data_fixture, django_assert_num_queries):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace, order=1
    )
    application_2 = data_fixture.create_database_application(
        workspace=workspace, order=2
    )

    action_type_registry.get_by_type(OrderApplicationsActionType).do(
        user, workspace, [application_2.id, application_1.id]
    )

    def check_queryset():
        return list(
            Application.objects.all().order_by("order").values_list("id", flat=True)
        )

    assert check_queryset() == [application_2.id, application_1.id]

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert check_queryset() == [application_1.id, application_2.id]

    ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert check_queryset() == [application_2.id, application_1.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_create_application(data_fixture, django_assert_num_queries):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_type = "database"
    application_name = "My Application"

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace, application_type, name=application_name
    )

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    assert Application.objects.filter(pk=application.id).count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_create_application(data_fixture, django_assert_num_queries):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_type = "database"
    application_name = "My Application"

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace, application_type, name=application_name
    )

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    assert Application.objects.filter(pk=application.id).count() == 1


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_delete_application(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_type = "database"
    application_name = "My Application"

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace, application_type, name=application_name
    )

    action_type_registry.get_by_type(DeleteApplicationActionType).do(user, application)

    assert Application.objects.filter(pk=application.id).count() == 0

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    assert Application.objects.filter(pk=application.id).count() == 1


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_delete_application(data_fixture, django_assert_num_queries):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_type = "database"
    application_name = "My Application"

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace, application_type, name=application_name
    )

    action_type_registry.get_by_type(DeleteApplicationActionType).do(user, application)

    assert Application.objects.filter(pk=application.id).count() == 0

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    assert Application.objects.filter(pk=application.id).count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_update_application(data_fixture, django_assert_num_queries):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_type = "database"
    application_name = "My Application"
    application_name_new = "New application name"

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace, application_type, name=application_name
    )

    action_type_registry.get_by_type(UpdateApplicationActionType).do(
        user, application, name=application_name_new
    )

    assert Application.objects.get(pk=application.id).name == application_name_new

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    assert Application.objects.get(pk=application.id).name == application_name


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_application(data_fixture, django_assert_num_queries):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_type = "database"
    application_name = "My Application"
    application_name_new = "New application name"

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace, application_type, name=application_name
    )

    action_type_registry.get_by_type(UpdateApplicationActionType).do(
        user, application, name=application_name_new
    )

    assert Application.objects.get(pk=application.id).name == application_name_new

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    assert Application.objects.get(pk=application.id).name == application_name_new


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_duplicate_simple_application(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_name = "My Application"

    application = data_fixture.create_database_application(
        user, workspace=workspace, name=application_name
    )

    new_application = action_type_registry.get_by_type(
        DuplicateApplicationActionType
    ).do(user, application)

    assert new_application.name.startswith(application_name)
    assert Application.objects.count() == 2

    actions_undone = ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    assert_undo_redo_actions_are_valid(actions_undone, [DuplicateApplicationActionType])
    assert Application.objects.count() == 1
    assert Application.objects.first().name == application_name


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_duplicate_simple_application(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    application_name = "My Application"

    application = data_fixture.create_database_application(
        user, workspace=workspace, name=application_name
    )

    new_application = action_type_registry.get_by_type(
        DuplicateApplicationActionType
    ).do(user, application)

    assert new_application.name.startswith(application_name)
    assert Application.objects.count() == 2

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    actions_redone = ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [DuplicateApplicationActionType])
    assert Application.objects.count() == 2
    assert list(Application.objects.values_list("name", flat=True)) == unordered(
        [application_name, f"{application_name} 2"]
    )


# The builder registers no actions, see `test_can_redo_builder_creation`.
TYPES_WITH_ACTIONS = ["database", "automation", "dashboard"]


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("application_type", TYPES_WITH_ACTIONS)
def test_can_undo_redo_create_application_of_each_type(data_fixture, application_type):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    scopes = [WorkspaceActionScopeType.value(workspace_id=workspace.id)]

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace, application_type, name="Created"
    )

    with transaction.atomic():
        ActionHandler.undo(user, scopes, session_id)
    assert not Application.objects.filter(id=application.id).exists()

    with transaction.atomic():
        redone = ActionHandler.redo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(redone, [CreateApplicationActionType])
    assert Application.objects.filter(id=application.id).exists()


@pytest.mark.django_db
def test_can_redo_builder_creation(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = CreateApplicationActionType.do(user, workspace, "builder", name="Site")
    params = CreateApplicationActionType.Params(
        workspace.id, workspace.name, "builder", builder.id, builder.name, False
    )

    CreateApplicationActionType.undo(user, params, None)
    assert not Application.objects.filter(id=builder.id).exists()

    CreateApplicationActionType.redo(user, params, None)
    assert Application.objects.filter(id=builder.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("application_type", [*TYPES_WITH_ACTIONS, "builder"])
def test_can_undo_redo_delete_application_of_each_type(data_fixture, application_type):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    scopes = [WorkspaceActionScopeType.value(workspace_id=workspace.id)]
    application = CoreHandler().create_application(
        user, workspace, application_type, name="To delete"
    )

    action_type_registry.get_by_type(DeleteApplicationActionType).do(user, application)
    assert not Application.objects.filter(id=application.id).exists()

    with transaction.atomic():
        undone = ActionHandler.undo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(undone, [DeleteApplicationActionType])
    assert Application.objects.filter(id=application.id).exists()

    with transaction.atomic():
        redone = ActionHandler.redo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(redone, [DeleteApplicationActionType])
    assert not Application.objects.filter(id=application.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_duplicate_automation(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    scopes = [WorkspaceActionScopeType.value(workspace_id=workspace.id)]
    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Original"
    )

    duplicate = action_type_registry.get_by_type(DuplicateApplicationActionType).do(
        user, automation
    )

    with transaction.atomic():
        ActionHandler.undo(user, scopes, session_id)
    assert not Application.objects.filter(id=duplicate.id).exists()

    with transaction.atomic():
        redone = ActionHandler.redo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(redone, [DuplicateApplicationActionType])
    assert Application.objects.filter(id=duplicate.id).exists()


@pytest.mark.django_db
def test_can_redo_install_template_holding_an_automation(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    automation = data_fixture.create_automation_application(workspace=workspace)
    params = InstallTemplateActionType.Params(
        workspace.id, workspace.name, 1, "Template", [database.id, automation.id]
    )

    InstallTemplateActionType.undo(user, params, None)
    assert Application.objects.filter(workspace=workspace).count() == 0

    InstallTemplateActionType.redo(user, params, None)
    assert Application.objects.filter(workspace=workspace).count() == 2


def test_update_application_action_long_description():
    params = {
        "workspace_id": 1,
        "workspace_name": "Workspace",
        "application_type": "dashboard",
        "application_id": 2,
        "application_name": "Dashboard",
        "original_application_name": "Dashboard",
        "data": {"description": "New"},
        "original_data": {"description": "Old"},
    }

    # Nothing was renamed, so the description must not claim it was.
    assert UpdateApplicationActionType.get_long_description(params) == (
        'Application (2) of type dashboard "Dashboard" updated '
        'in group "Workspace" (1).'
    )

    params["original_application_name"] = "Old dashboard"
    assert UpdateApplicationActionType.get_long_description(params) == (
        'Application (2) of type dashboard renamed from "Old dashboard" to '
        '"Dashboard" in group "Workspace" (1).'
    )
