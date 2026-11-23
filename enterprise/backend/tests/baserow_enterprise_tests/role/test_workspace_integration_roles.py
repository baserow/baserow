from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_404_NOT_FOUND

from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.core.exceptions import PermissionException
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.integrations.tasks import broadcast_to_workspace_integration_users
from baserow.core.models import WorkspaceInvitation, WorkspaceInvitationLink
from baserow.core.subjects import UserSubjectType
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.exceptions import ScopeNotExist
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment
from baserow_enterprise.role.types import NewRoleAssignment


def _ordered_ids(application):
    return list(
        Integration.objects.filter(application=application)
        .order_by("order", "id")
        .values_list("id", flat=True)
    )


@pytest.mark.django_db
def test_builders_list_the_workspace_integrations_and_admins_manage_them(
    data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    editor = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[builder, editor])
    RoleAssignmentHandler().assign_role(
        builder, workspace, role=Role.objects.get(uid="BUILDER")
    )
    RoleAssignmentHandler().assign_role(
        editor, workspace, role=Role.objects.get(uid="EDITOR")
    )
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    first = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    second = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    integration_type = integration_type_registry.get("local_baserow")
    service = IntegrationService()
    handler = IntegrationHandler()

    assert [i.id for i in service.get_integrations(builder, shared_application)] == [
        first.id,
        second.id,
    ]
    with pytest.raises(PermissionException):
        service.get_integrations(editor, shared_application)

    for user in [builder, editor]:
        with pytest.raises(PermissionException):
            service.create_integration(
                user, integration_type, shared_application, name="New"
            )
        with pytest.raises(PermissionException):
            service.update_integration(
                user, handler.get_integration_for_update(first.id), name="Changed"
            )
        with pytest.raises(PermissionException):
            service.move_integration(
                user, handler.get_integration_for_update(second.id), before=first
            )
        with pytest.raises(PermissionException):
            service.delete_integration(
                user, handler.get_integration_for_update(first.id)
            )
    assert _ordered_ids(shared_application) == [first.id, second.id]

    created = service.create_integration(
        admin, integration_type, shared_application, name="New"
    )
    service.update_integration(
        admin, handler.get_integration_for_update(first.id), name="Changed"
    )
    service.move_integration(
        admin, handler.get_integration_for_update(second.id), before=first
    )
    service.delete_integration(admin, handler.get_integration_for_update(first.id))

    assert _ordered_ids(shared_application) == [second.id, created.id]


@pytest.mark.django_db
def test_builders_keep_managing_the_integrations_of_an_application(
    data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[builder])
    RoleAssignmentHandler().assign_role(
        builder, workspace, role=Role.objects.get(uid="BUILDER")
    )
    data_fixture.create_shared_application(workspace=workspace)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration_type = integration_type_registry.get("local_baserow")
    service = IntegrationService()
    handler = IntegrationHandler()

    first = service.create_integration(
        builder, integration_type, application, name="First"
    )
    second = service.create_integration(
        builder, integration_type, application, name="Second"
    )
    service.update_integration(
        builder, handler.get_integration_for_update(first.id), name="Changed"
    )
    service.move_integration(
        builder, handler.get_integration_for_update(second.id), before=first
    )
    service.delete_integration(builder, handler.get_integration_for_update(first.id))

    assert [i.id for i in service.get_integrations(builder, application)] == [second.id]


@pytest.mark.django_db
def test_only_admins_restore_a_workspace_integration(
    data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[builder])
    RoleAssignmentHandler().assign_role(
        builder, workspace, role=Role.objects.get(uid="BUILDER")
    )
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    application = data_fixture.create_builder_application(workspace=workspace)
    workspace_integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    application_integration = data_fixture.create_local_baserow_integration(
        application=application, user=builder
    )
    service = IntegrationService()
    handler = IntegrationHandler()
    for integration in [workspace_integration, application_integration]:
        service.delete_integration(
            admin, handler.get_integration_for_update(integration.id)
        )

    with pytest.raises(PermissionException):
        TrashHandler.restore_item(builder, "integration", workspace_integration.id)
    TrashHandler.restore_item(builder, "integration", application_integration.id)
    TrashHandler.restore_item(admin, "integration", workspace_integration.id)

    restored = Integration.objects.filter(
        id__in=[workspace_integration.id, application_integration.id]
    )
    assert restored.count() == 2


@pytest.mark.django_db
def test_only_admins_promote_an_integration(
    data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[builder])
    RoleAssignmentHandler().assign_role(
        builder, workspace, role=Role.objects.get(uid="BUILDER")
    )
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=application, user=builder
    )
    service = IntegrationService()
    handler = IntegrationHandler()

    # A Builder may update the integration, but not create one in the workspace.
    with pytest.raises(PermissionException):
        service.update_integration(
            builder,
            handler.get_integration_for_update(integration.id),
            application_id=shared_application.id,
        )
    service.update_integration(
        admin,
        handler.get_integration_for_update(integration.id),
        application_id=shared_application.id,
    )

    assert (
        Integration.objects.get(id=integration.id).application_id
        == shared_application.id
    )


def _application_builder(data_fixture, workspace, application, workspace_role):
    """
    Gives a new member of the workspace the given role on the workspace, and the
    Builder role on the application only.
    """

    user = data_fixture.create_user()
    data_fixture.create_user_workspace(workspace=workspace, user=user)
    RoleAssignmentHandler().assign_role(
        user, workspace, role=Role.objects.get(uid=workspace_role)
    )
    RoleAssignmentHandler().assign_role(
        user,
        workspace,
        role=Role.objects.get(uid="BUILDER"),
        scope=application.application_ptr,
    )
    return user


@pytest.mark.django_db
@pytest.mark.parametrize("workspace_role", ["NO_ACCESS", "VIEWER", "EDITOR"])
def test_application_builders_list_the_workspace_integrations_from_their_application(
    data_fixture, enable_enterprise, synced_roles, workspace_role
):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    application = data_fixture.create_builder_application(workspace=workspace)
    other_application = data_fixture.create_builder_application(workspace=workspace)
    app_builder = _application_builder(
        data_fixture, workspace, application, workspace_role
    )
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    workspace_integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    service = IntegrationService()

    shared, _, integrations = service.get_workspace_integrations(
        app_builder, application
    )

    assert shared.id == shared_application.id
    assert [i.id for i in integrations] == [workspace_integration.id]
    # Only from an application they build in.
    with pytest.raises(PermissionException):
        service.get_workspace_integrations(app_builder, other_application)
    # The workspace settings stay for the workspace Builders and Admins.
    with pytest.raises(PermissionException):
        service.get_integrations(app_builder, shared_application)


@pytest.mark.django_db
def test_database_builders_dont_see_the_workspace_integrations_it_cant_use(
    data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    app_builder = _application_builder(data_fixture, workspace, database, "NO_ACCESS")
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    # Promoted by the admin, it lists every table the admin can see, in
    # databases the builder has no role on.
    data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    slack_bot = data_fixture.create_slack_bot_integration(
        application=shared_application
    )

    shared, integration_types, integrations = (
        IntegrationService().get_workspace_integrations(app_builder, database)
    )

    assert shared.id == shared_application.id
    assert "local_baserow" not in integration_types
    assert [i.id for i in integrations] == [slack_bot.id]


@pytest.mark.django_db
def test_application_builders_use_the_workspace_integrations_from_their_application(
    data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    other_database = data_fixture.create_database_application(workspace=workspace)
    app_builder = _application_builder(data_fixture, workspace, database, "NO_ACCESS")
    editor = data_fixture.create_user()
    data_fixture.create_user_workspace(workspace=workspace, user=editor)
    RoleAssignmentHandler().assign_role(
        editor, workspace, role=Role.objects.get(uid="EDITOR")
    )
    workspace_integration = data_fixture.create_slack_bot_integration(
        application=data_fixture.create_shared_application(workspace=workspace)
    )
    own_integration = data_fixture.create_slack_bot_integration(application=database)
    service = IntegrationService()

    service.check_can_use_integration(app_builder, workspace_integration, database)
    service.check_can_use_integration(app_builder, own_integration, database)
    with pytest.raises(PermissionException):
        service.check_can_use_integration(
            app_builder, workspace_integration, other_database
        )
    # A user who builds nowhere doesn't use them.
    with pytest.raises(PermissionException):
        service.check_can_use_integration(editor, workspace_integration, database)


@pytest.mark.django_db
@patch("baserow.ws.tasks.broadcast_to_users")
def test_workspace_integration_events_reach_whoever_sees_them_from_an_application(
    mock_broadcast_to_users, data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    editor = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[builder, editor])
    RoleAssignmentHandler().assign_role(
        builder, workspace, role=Role.objects.get(uid="BUILDER")
    )
    RoleAssignmentHandler().assign_role(
        editor, workspace, role=Role.objects.get(uid="EDITOR")
    )
    application = data_fixture.create_builder_application(workspace=workspace)
    app_builder = _application_builder(
        data_fixture, workspace, application, "NO_ACCESS"
    )

    broadcast_to_workspace_integration_users(workspace.id, {"type": "test"})

    args, _ = mock_broadcast_to_users.call_args
    assert set(args[0]) == {admin.id, builder.id, app_builder.id}


@pytest.mark.django_db
@patch("baserow.ws.tasks.broadcast_to_users")
def test_workspace_integration_events_reach_the_workspace_builders_without_apps(
    mock_broadcast_to_users, data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    editor = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[builder, editor])
    RoleAssignmentHandler().assign_role(
        builder, workspace, role=Role.objects.get(uid="BUILDER")
    )
    RoleAssignmentHandler().assign_role(
        editor, workspace, role=Role.objects.get(uid="EDITOR")
    )
    data_fixture.create_shared_application(workspace=workspace)

    broadcast_to_workspace_integration_users(workspace.id, {"type": "test"})

    args, _ = mock_broadcast_to_users.call_args
    assert set(args[0]) == {admin.id, builder.id}


@pytest.mark.django_db
@patch("baserow.ws.tasks.broadcast_to_users")
def test_workspace_integration_events_reach_only_applications_using_their_type(
    mock_broadcast_to_users, data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    builder_application = data_fixture.create_builder_application(workspace=workspace)
    database_builder = _application_builder(
        data_fixture, workspace, database, "NO_ACCESS"
    )
    application_builder = _application_builder(
        data_fixture, workspace, builder_application, "NO_ACCESS"
    )
    data_fixture.create_shared_application(workspace=workspace)

    broadcast_to_workspace_integration_users(
        workspace.id, {"type": "test"}, integration_type="local_baserow"
    )
    args, _ = mock_broadcast_to_users.call_args
    # A database can't use a Local Baserow integration, so its builder isn't
    # sent the tables it lists.
    assert set(args[0]) == {admin.id, application_builder.id}

    broadcast_to_workspace_integration_users(
        workspace.id, {"type": "test"}, integration_type="slack_bot"
    )
    args, _ = mock_broadcast_to_users.call_args
    assert set(args[0]) == {admin.id, database_builder.id, application_builder.id}


@pytest.mark.django_db
def test_new_nodes_preselect_a_workspace_integration_for_application_builders(
    data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    automation = data_fixture.create_automation_application(workspace=workspace)
    # Builder on the automation only, so the workspace settings don't list them.
    app_builder = _application_builder(data_fixture, workspace, automation, "EDITOR")
    # The manual trigger has no integration, so the automation starts with none.
    workflow = data_fixture.create_automation_workflow(
        automation=automation, trigger_type="manual"
    )
    workspace_integration = data_fixture.create_local_baserow_integration(
        application=data_fixture.create_shared_application(workspace=workspace),
        user=admin,
    )

    def create_node(user, **kwargs):
        node = AutomationNodeService().create_node(
            user,
            automation_node_type_registry.get("local_baserow_create_row"),
            workflow,
            reference_node_id=workflow.get_trigger().id,
            position="south",
            output="",
            **kwargs,
        )
        node.service.refresh_from_db()
        return node.service.integration_id

    assert create_node(admin) == workspace_integration.id
    assert create_node(app_builder) == workspace_integration.id

    own = data_fixture.create_local_baserow_integration(
        application=automation, user=app_builder
    )

    assert create_node(app_builder) == own.id
    # An integration given to the node is kept, although the own one would be
    # preselected.
    assert (
        create_node(app_builder, service={"integration_id": workspace_integration.id})
        == workspace_integration.id
    )


@pytest.mark.django_db
def test_no_role_can_be_given_on_the_shared_application(
    data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    application = data_fixture.create_builder_application(workspace=workspace)
    admin_role = Role.objects.get(uid="ADMIN")
    handler = RoleAssignmentHandler()

    # The API resolves the scope as the base application, so both are refused.
    for scope in [shared_application, shared_application.application_ptr]:
        with pytest.raises(ScopeNotExist):
            handler.assign_role_batch_for_user(
                admin, workspace, [NewRoleAssignment(member, admin_role, scope)]
            )
        with pytest.raises(ScopeNotExist):
            handler.create_scoped_invitation(
                admin, workspace, "invited@example.com", admin_role, scope
            )
        with pytest.raises(ScopeNotExist):
            handler.create_scoped_invitation_link(admin, workspace, scope, admin_role)

    assert not RoleAssignment.objects.filter(subject_id=member.id).exists()
    assert not WorkspaceInvitation.objects.filter(workspace=workspace).exists()
    assert not WorkspaceInvitationLink.objects.filter(workspace=workspace).exists()

    # Any other application still gets one.
    handler.assign_role_batch_for_user(
        admin,
        workspace,
        [NewRoleAssignment(member, admin_role, application.application_ptr)],
    )
    assert (
        handler.get_current_role_assignment(
            member, workspace, scope=application.application_ptr
        ).role
        == admin_role
    )


@pytest.mark.django_db
def test_assign_a_role_on_the_shared_application(
    api_client, data_fixture, enable_enterprise, synced_roles
):
    admin, token = data_fixture.create_user_and_token()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    shared_application = data_fixture.create_shared_application(workspace=workspace)

    response = api_client.post(
        reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id}),
        {
            "scope_id": shared_application.id,
            "scope_type": "application",
            "subject_id": member.id,
            "subject_type": UserSubjectType.type,
            "role": "ADMIN",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SCOPE_DOES_NOT_EXIST"
    assert not RoleAssignment.objects.filter(subject_id=member.id).exists()
