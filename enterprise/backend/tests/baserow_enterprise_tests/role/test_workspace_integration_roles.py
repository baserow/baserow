import pytest

from baserow.core.exceptions import PermissionException
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


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
