import uuid

from django.contrib.auth.models import AnonymousUser

import pytest

from baserow.contrib.integrations.mcp.service import MCPServerService
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import (
    ApplicationActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.exceptions import PermissionException
from baserow.core.integrations.actions import (
    CreateIntegrationActionType,
    DeleteIntegrationActionType,
    MoveIntegrationActionType,
    UpdateIntegrationActionType,
)
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.models import Application, TrashEntry
from baserow.core.trash.handler import TrashHandler


def _workspace_with_a_member(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    return admin, member, workspace, shared_application


@pytest.mark.django_db
def test_is_shared_application(data_fixture):
    workspace = data_fixture.create_workspace()
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    handler = IntegrationHandler()

    assert handler.is_shared_application(shared_application)
    assert handler.is_shared_application(
        Application.objects.get(id=shared_application.id)
    )
    assert not handler.is_shared_application(builder)
    assert not handler.is_shared_application(Application.objects.get(id=builder.id))


@pytest.mark.django_db
def test_workspace_members_can_list_the_workspace_integrations(data_fixture):
    admin, member, _, shared_application = _workspace_with_a_member(data_fixture)
    integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )

    integrations = IntegrationService().get_integrations(member, shared_application)

    assert [i.id for i in integrations] == [integration.id]


@pytest.mark.django_db
def test_only_admins_can_create_a_workspace_integration(data_fixture):
    admin, member, _, shared_application = _workspace_with_a_member(data_fixture)
    integration_type = integration_type_registry.get("local_baserow")

    with pytest.raises(PermissionException):
        IntegrationService().create_integration(
            member, integration_type, shared_application, name="By member"
        )

    integration = IntegrationService().create_integration(
        admin, integration_type, shared_application, name="By admin"
    )

    assert list(
        Integration.objects.filter(application=shared_application).values_list(
            "id", flat=True
        )
    ) == [integration.id]


@pytest.mark.django_db
def test_only_admins_can_update_a_workspace_integration(data_fixture):
    admin, member, _, shared_application = _workspace_with_a_member(data_fixture)
    integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin, name="Original"
    )
    handler = IntegrationHandler()

    with pytest.raises(PermissionException):
        IntegrationService().update_integration(
            member, handler.get_integration_for_update(integration.id), name="Member"
        )

    IntegrationService().update_integration(
        admin, handler.get_integration_for_update(integration.id), name="Admin"
    )

    integration.refresh_from_db()
    assert integration.name == "Admin"


@pytest.mark.django_db
def test_only_admins_can_delete_a_workspace_integration(data_fixture):
    admin, member, _, shared_application = _workspace_with_a_member(data_fixture)
    integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    handler = IntegrationHandler()

    with pytest.raises(PermissionException):
        IntegrationService().delete_integration(
            member, handler.get_integration_for_update(integration.id)
        )
    assert Integration.objects.filter(id=integration.id).exists()

    IntegrationService().delete_integration(
        admin, handler.get_integration_for_update(integration.id)
    )
    assert not Integration.objects.filter(id=integration.id).exists()


@pytest.mark.django_db
def test_a_workspace_integration_is_trashed_in_the_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, name="Acme")
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace, name="App")
    workspace_integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=user
    )
    application_integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    handler = IntegrationHandler()

    for integration in [workspace_integration, application_integration]:
        IntegrationService().delete_integration(
            user, handler.get_integration_for_update(integration.id)
        )

    entries = {
        entry.trash_item_id: entry
        for entry in TrashEntry.objects.filter(trash_item_type="integration")
    }
    # Shown as coming from the workspace, never from the hidden shared application.
    workspace_entry = entries[workspace_integration.id]
    assert workspace_entry.workspace_id == workspace.id
    assert workspace_entry.application_id is None
    assert workspace_entry.parent_name == "Acme"
    application_entry = entries[application_integration.id]
    assert application_entry.application_id == builder.id
    assert application_entry.parent_name == "App"

    in_shared_application = TrashHandler.get_trash_contents(
        user, workspace.id, shared_application.id
    )
    assert list(in_shared_application) == []
    assert {
        entry.trash_item_id
        for entry in TrashHandler.get_trash_contents(user, workspace.id, None)
    } == {workspace_integration.id, application_integration.id}

    # Emptying an application's trash leaves the workspace integration, emptying
    # the workspace's deletes it.
    TrashHandler.empty(user, workspace.id, builder.id)
    TrashHandler.permanently_delete_marked_trash()
    assert Integration.objects_and_trash.filter(id=workspace_integration.id).exists()

    TrashHandler.empty(user, workspace.id, None)
    TrashHandler.permanently_delete_marked_trash()
    assert not Integration.objects_and_trash.filter(
        id=workspace_integration.id
    ).exists()


@pytest.mark.django_db
def test_only_admins_can_restore_a_workspace_integration(data_fixture):
    admin, member, _, shared_application = _workspace_with_a_member(data_fixture)
    integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    IntegrationService().delete_integration(
        admin, IntegrationHandler().get_integration_for_update(integration.id)
    )

    with pytest.raises(PermissionException):
        TrashHandler.restore_item(member, "integration", integration.id)
    assert not Integration.objects.filter(id=integration.id).exists()

    TrashHandler.restore_item(admin, "integration", integration.id)
    assert Integration.objects.filter(id=integration.id).exists()


@pytest.mark.django_db
def test_only_admins_can_move_a_workspace_integration(data_fixture):
    admin, member, _, shared_application = _workspace_with_a_member(data_fixture)
    first = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    second = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    handler = IntegrationHandler()

    def order():
        return list(
            Integration.objects.filter(application=shared_application)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    with pytest.raises(PermissionException):
        IntegrationService().move_integration(
            member, handler.get_integration_for_update(second.id), before=first
        )
    assert order() == [first.id, second.id]

    IntegrationService().move_integration(
        admin, handler.get_integration_for_update(second.id), before=first
    )
    assert order() == [second.id, first.id]


@pytest.mark.django_db
def test_members_still_manage_the_integrations_of_an_application(data_fixture):
    _, member, workspace, _ = _workspace_with_a_member(data_fixture)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration_type = integration_type_registry.get("local_baserow")
    service = IntegrationService()
    handler = IntegrationHandler()

    first = service.create_integration(member, integration_type, builder, name="A")
    second = service.create_integration(member, integration_type, builder, name="B")
    service.update_integration(
        member, handler.get_integration_for_update(first.id), name="Renamed"
    )
    service.move_integration(
        member, handler.get_integration_for_update(second.id), before=first
    )
    service.delete_integration(member, handler.get_integration_for_update(first.id))

    assert [i.id for i in service.get_integrations(member, builder)] == [second.id]

    TrashHandler.restore_item(member, "integration", first.id)

    assert [i.id for i in service.get_integrations(member, builder)] == [
        second.id,
        first.id,
    ]


@pytest.mark.django_db
def test_the_workspace_integrations_of_a_template_can_be_listed(data_fixture):
    workspace = data_fixture.create_workspace()
    data_fixture.create_template(workspace=workspace)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=shared_application
    )
    outsider = data_fixture.create_user()

    for user in [outsider, AnonymousUser()]:
        integrations = IntegrationService().get_integrations(user, shared_application)
        assert [i.id for i in integrations] == [integration.id]

        with pytest.raises(PermissionException):
            IntegrationService().update_integration(
                user,
                IntegrationHandler().get_integration_for_update(integration.id),
                name="Changed",
            )


@pytest.mark.django_db
def test_only_admins_can_change_a_workspace_mcp_server(data_fixture):
    admin, member, workspace, shared_application = _workspace_with_a_member(
        data_fixture
    )
    workspace_server = data_fixture.create_mcp_server_integration(
        application=shared_application
    )
    agent_application = data_fixture.create_agent_application(workspace=workspace)
    application_server = data_fixture.create_mcp_server_integration(
        application=agent_application
    )

    with pytest.raises(PermissionException):
        MCPServerService().get_server_for_update(member, workspace_server.id)

    assert (
        MCPServerService().get_server_for_update(admin, workspace_server.id).id
        == workspace_server.id
    )
    assert (
        MCPServerService().get_server_for_update(member, application_server.id).id
        == application_server.id
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_workspace_integration_actions_are_in_the_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, name="Acme")
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace, name="App")
    integration_type = integration_type_registry.get("local_baserow")
    handler = IntegrationHandler()

    first = CreateIntegrationActionType.do(
        user, integration_type, shared_application, name="First"
    )
    second = CreateIntegrationActionType.do(
        user, integration_type, shared_application, name="Second"
    )
    UpdateIntegrationActionType.do(
        user, handler.get_integration_for_update(first.id), name="Renamed"
    )
    MoveIntegrationActionType.do(
        user, handler.get_integration_for_update(second.id), before=first
    )
    DeleteIntegrationActionType.do(user, handler.get_integration_for_update(first.id))
    own = CreateIntegrationActionType.do(user, integration_type, builder, name="Own")

    workspace_scope = WorkspaceActionScopeType.value(workspace.id)
    application_scope = ApplicationActionScopeType.value(builder.id)
    actions = list(Action.objects.order_by("id"))
    assert [(action.type, action.scope) for action in actions] == [
        (CreateIntegrationActionType.type, workspace_scope),
        (CreateIntegrationActionType.type, workspace_scope),
        (UpdateIntegrationActionType.type, workspace_scope),
        (MoveIntegrationActionType.type, workspace_scope),
        (DeleteIntegrationActionType.type, workspace_scope),
        (CreateIntegrationActionType.type, application_scope),
    ]

    # Described in the workspace, never in the hidden shared application.
    in_workspace = f'in group "Acme" ({workspace.id}).'
    in_application = f'in application "App" ({builder.id}).'
    assert [
        action_type_registry.get(action.type).get_long_description(action.params)
        for action in actions
    ] == [
        f"Integration ({first.id}) created {in_workspace}",
        f"Integration ({second.id}) created {in_workspace}",
        f"Integration ({first.id}) updated {in_workspace}",
        f"Integration ({second.id}) moved {in_workspace}",
        f"Integration ({first.id}) deleted {in_workspace}",
        f"Integration ({own.id}) created {in_application}",
    ]

    # Actions recorded before the workspace params existed.
    assert (
        CreateIntegrationActionType.get_long_description(
            {
                "application_id": builder.id,
                "application_name": "App",
                "integration_id": own.id,
                "integration_type": "local_baserow",
            }
        )
        == f"Integration ({own.id}) created {in_application}"
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_workspace_integration_actions_can_be_undone_from_an_application(
    data_fixture,
):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration_type = integration_type_registry.get("local_baserow")
    # The scopes the frontend sends from inside an application of the workspace.
    scopes = [
        WorkspaceActionScopeType.value(workspace.id),
        ApplicationActionScopeType.value(builder.id),
    ]

    integration = CreateIntegrationActionType.do(
        user, integration_type, shared_application, name="Integration"
    )

    ActionHandler.undo(user, scopes, session_id)
    assert not Integration.objects.filter(id=integration.id).exists()

    ActionHandler.redo(user, scopes, session_id)
    assert Integration.objects.filter(id=integration.id).exists()
