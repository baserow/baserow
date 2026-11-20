"""
Promoting an integration moves it from its application to the shared application
of the workspace, so every application of the workspace can use it while its own
application keeps using it.
"""

import uuid

import pytest

from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import (
    ApplicationActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.exceptions import (
    ApplicationOperationNotSupported,
    PermissionException,
)
from baserow.core.integrations.actions import UpdateIntegrationActionType
from baserow.core.integrations.exceptions import IntegrationCannotMoveToApplication
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.service import IntegrationService


def _promote(user, integration, shared_application):
    return IntegrationService().update_integration(
        user,
        IntegrationHandler().get_integration_for_update(integration.id),
        application_id=shared_application.id,
    )


def _application_id(integration):
    return Integration.objects.get(id=integration.id).application_id


def _use_in_a_data_source(data_fixture, builder, integration):
    return data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=data_fixture.create_builder_page(builder=builder),
        integration=integration,
    )


def _use_in_a_user_source(data_fixture, builder, integration):
    return data_fixture.create_user_source_with_first_type(
        application=builder, integration=integration
    )


@pytest.mark.django_db
def test_an_admin_promotes_an_integration_to_the_workspace(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    existing = data_fixture.create_local_baserow_integration(
        application=shared_application, user=admin
    )
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=admin
    )
    data_source = _use_in_a_data_source(data_fixture, builder, integration)

    updated = _promote(admin, integration, shared_application)

    assert updated.original_values == {"application_id": builder.id}
    assert updated.new_values == {"application_id": shared_application.id}
    # Placed last among the workspace integrations.
    assert list(
        Integration.objects.filter(application=shared_application)
        .order_by("order", "id")
        .values_list("id", flat=True)
    ) == [existing.id, integration.id]
    assert not builder.integrations.exists()
    # Its application keeps using it, now as a workspace integration.
    data_source.service.refresh_from_db()
    assert data_source.service.integration_id == integration.id
    assert IntegrationHandler().is_integration_usable(
        Integration.objects.get(id=integration.id), application_id=builder.id
    )


@pytest.mark.django_db
def test_only_admins_promote_an_integration(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=member
    )

    # A member manages the integrations of an application, not of the workspace.
    with pytest.raises(PermissionException):
        _promote(member, integration, shared_application)
    assert _application_id(integration) == builder.id

    _promote(admin, integration, shared_application)
    assert _application_id(integration) == shared_application.id


@pytest.mark.django_db
def test_an_integration_only_moves_between_an_application_and_its_workspace(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    other_builder = data_fixture.create_builder_application(workspace=workspace)
    other_shared_application = data_fixture.create_shared_application(
        workspace=data_fixture.create_workspace(user=user)
    )
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    workspace_integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=user
    )

    for moved, target in [
        (integration, other_builder),
        (integration, other_shared_application),
        (workspace_integration, other_shared_application),
    ]:
        with pytest.raises(IntegrationCannotMoveToApplication):
            IntegrationService().update_integration(
                user,
                IntegrationHandler().get_integration_for_update(moved.id),
                application_id=target.id,
            )

    assert _application_id(integration) == builder.id
    assert _application_id(workspace_integration) == shared_application.id


@pytest.mark.django_db
def test_an_mcp_server_stays_with_its_agent(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    agent = data_fixture.create_agent_application(workspace=workspace)
    server = data_fixture.create_mcp_server_integration(application=agent)

    # Only the agent that owns an MCP server reads it, so promoting it would take
    # it away from the agent and give it to nobody.
    with pytest.raises(ApplicationOperationNotSupported):
        _promote(user, server, shared_application)

    assert _application_id(server) == agent.id


@pytest.mark.django_db
def test_a_dashboard_keeps_its_integration(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    workspace_integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=user
    )

    # Every new data source of a dashboard takes the dashboard's own integration,
    # so promoting it would leave the dashboard's new widgets without one.
    with pytest.raises(ApplicationOperationNotSupported):
        _promote(user, integration, shared_application)

    # Only undoing a promotion moves an integration back, and no promotion
    # leaves a dashboard, so nothing moves into one either.
    with pytest.raises(ApplicationOperationNotSupported):
        IntegrationHandler().update_integration(
            workspace_integration.get_type(),
            IntegrationHandler().get_integration_for_update(workspace_integration.id),
            application=dashboard,
        )

    assert _application_id(integration) == dashboard.id
    assert _application_id(workspace_integration) == shared_application.id


@pytest.mark.django_db
def test_the_current_application_does_not_move_an_integration(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user, name="Before"
    )

    updated = IntegrationService().update_integration(
        user,
        IntegrationHandler().get_integration_for_update(integration.id),
        application_id=builder.id,
        name="After",
    )

    assert updated.original_values == {"name": "Before"}
    assert updated.new_values == {"name": "After"}


@pytest.mark.django_db
def test_promoting_a_local_baserow_integration_authorizes_it_as_the_admin(
    data_fixture,
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    identity = data_fixture.create_identity(workspace=workspace)
    as_member = data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=member
    )
    as_admin = data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=admin
    )
    as_identity = data_fixture.create_local_baserow_integration(
        application=builder, authorized_identity=identity
    )

    for integration in [as_member, as_admin, as_identity]:
        _promote(admin, integration, shared_application)

    def subject(integration):
        integration = Integration.objects.get(id=integration.id).specific
        return integration.authorized_subject_type, integration.authorized_subject_id

    # Every application of the workspace would act as the member otherwise.
    assert subject(as_member) == ("auth.User", admin.id)
    assert subject(as_admin) == ("auth.User", admin.id)
    # An identity belongs to the workspace.
    assert subject(as_identity) == ("auth.User", identity.id)


@pytest.mark.django_db
def test_promoting_a_local_baserow_integration_nobody_can_act_as(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    deleted_user = data_fixture.create_user()
    deleted_user_id = deleted_user.id
    # Deleting a user in the admin tools leaves its id on the integration.
    deleted_user.delete()
    unauthorized_subjects = [
        ("auth.User", deleted_user_id),
        # What a permanently deleted account or identity leaves.
        (None, None),
        # Integrations that had no user before subjects were typed.
        ("auth.User", None),
    ]
    unauthorized = []
    for subject_type, subject_id in unauthorized_subjects:
        integration = data_fixture.create_local_baserow_integration(
            application=builder, authorized_user=admin
        )
        LocalBaserowIntegration.objects.filter(id=integration.id).update(
            authorized_subject_type=subject_type, authorized_subject_id=subject_id
        )
        unauthorized.append(integration)
    trashed_identity = data_fixture.create_identity(workspace=workspace, trashed=True)
    as_trashed_identity = data_fixture.create_local_baserow_integration(
        application=builder, authorized_identity=trashed_identity
    )

    for integration in [*unauthorized, as_trashed_identity]:
        _promote(admin, integration, shared_application)

    def subject(integration):
        integration = Integration.objects.get(id=integration.id).specific
        return integration.authorized_subject_type, integration.authorized_subject_id

    # The promotion modal says it will run as the admin.
    for integration in unauthorized:
        assert subject(integration) == ("auth.User", admin.id)
    # An identity belongs to the workspace, so it stays even trashed.
    assert subject(as_trashed_identity) == ("auth.User", trashed_identity.id)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_promotion_can_be_undone_and_redone(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user, name="Acme")
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    # What used it before the promotion can use it again after the undo.
    _use_in_a_data_source(data_fixture, builder, integration)
    _use_in_a_user_source(data_fixture, builder, integration)
    # The scopes the frontend sends from inside the application.
    scopes = [
        WorkspaceActionScopeType.value(workspace.id),
        ApplicationActionScopeType.value(builder.id),
    ]

    UpdateIntegrationActionType.do(
        user,
        IntegrationHandler().get_integration_for_update(integration.id),
        application_id=shared_application.id,
    )

    (action,) = Action.objects.all()
    assert action.scope == WorkspaceActionScopeType.value(workspace.id)
    assert (
        action_type_registry.get(action.type).get_long_description(action.params)
        == f'Integration ({integration.id}) updated in group "Acme" ({workspace.id}).'
    )

    (undone,) = ActionHandler.undo(user, scopes, session_id)
    assert undone.error is None
    assert _application_id(integration) == builder.id

    (redone,) = ActionHandler.redo(user, scopes, session_id)
    assert redone.error is None
    assert _application_id(integration) == shared_application.id


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("start_using", [_use_in_a_data_source, _use_in_a_user_source])
def test_a_promotion_cannot_be_undone_once_something_else_uses_the_integration(
    data_fixture, start_using
):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    other_builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )

    UpdateIntegrationActionType.do(
        user,
        IntegrationHandler().get_integration_for_update(integration.id),
        application_id=shared_application.id,
    )
    start_using(data_fixture, other_builder, integration)

    (undone,) = ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace.id)], session_id
    )

    # Moving it back would leave the other application without it.
    assert "IntegrationUsedSincePromotion" in undone.error
    assert _application_id(integration) == shared_application.id
