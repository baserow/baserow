from django.urls import reverse

import pytest

from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.core.identities.handler import IdentityHandler
from baserow.core.models import Operation
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
def test_application_builder_cannot_bind_an_identity(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=enterprise_data_fixture.create_user(), members=[user]
    )
    application = enterprise_data_fixture.create_agent_application(workspace=workspace)
    identity = IdentityHandler().create_identity(workspace=workspace, name="Investor")
    roles = RoleAssignmentHandler()
    roles.assign_role(user, workspace, Role.objects.get(uid="VIEWER"))
    roles.assign_role(
        user,
        workspace,
        Role.objects.get(uid="BUILDER"),
        scope=application.application_ptr,
    )
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    workspace_options = api_client.get(
        reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id}),
        {"for_selection": True},
        **auth,
    )
    choices = api_client.get(
        reverse("api:agent:run_as_identities", kwargs={"agent_id": application.id}),
        **auth,
    )
    updated = api_client.patch(
        reverse("api:agent:configuration", kwargs={"agent_id": application.id}),
        {"run_as_subject_type": "auth.User", "run_as_subject_id": identity.id},
        format="json",
        **auth,
    )

    assert workspace_options.status_code == 401
    assert choices.status_code == 200
    assert choices.json()["results"] == []
    assert updated.status_code == 401
    application.refresh_from_db()
    assert application.run_as_subject_id is None


@pytest.mark.django_db
def test_configuration_reader_cannot_list_editable_identity_choices(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=enterprise_data_fixture.create_user(), members=[user]
    )
    application = enterprise_data_fixture.create_agent_application(workspace=workspace)
    role = Role.objects.create(name="Configuration reader", workspace=workspace)
    role.operations.set(Role.objects.get(uid="VIEWER").operations.all())
    role.operations.add(
        Operation.objects.get(name=ReadAgentConfigurationOperationType.type)
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(user, workspace, Role.objects.get(uid="VIEWER"))
    roles.assign_role(user, workspace, role, scope=application.application_ptr)
    RoleAssignmentHandler._init = False
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    configuration = api_client.get(
        reverse("api:agent:configuration", kwargs={"agent_id": application.id}),
        **auth,
    )
    choices = api_client.get(
        reverse("api:agent:run_as_identities", kwargs={"agent_id": application.id}),
        **auth,
    )

    assert configuration.status_code == 200
    assert choices.status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,can_bind,can_create",
    [
        ("EDITOR", False, False),
        ("BUILDER", True, False),
        ("ADMIN", True, True),
    ],
)
def test_workspace_builders_bind_existing_identities_but_only_admins_create_them(
    api_client,
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    role_uid,
    can_bind,
    can_create,
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=enterprise_data_fixture.create_user(), members=[user]
    )
    RoleAssignmentHandler().assign_role(user, workspace, Role.objects.get(uid=role_uid))
    application = enterprise_data_fixture.create_agent_application(workspace=workspace)
    identity = IdentityHandler().create_identity(workspace=workspace, name="Investor")
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    choices = api_client.get(
        reverse("api:agent:run_as_identities", kwargs={"agent_id": application.id}),
        **auth,
    )
    updated = api_client.patch(
        reverse("api:agent:configuration", kwargs={"agent_id": application.id}),
        {"run_as_subject_type": "auth.User", "run_as_subject_id": identity.id},
        format="json",
        **auth,
    )
    created = api_client.post(
        reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id}),
        {"name": "New identity"},
        format="json",
        **auth,
    )

    application.refresh_from_db()
    expected_choices = [{"id": identity.id, "name": "Investor"}] if can_bind else []
    if role_uid != "EDITOR":
        assert choices.json()["results"] == expected_choices
    assert (updated.status_code == 200) is can_bind
    assert (application.run_as_subject_id == identity.id) is can_bind
    assert (created.status_code == 200) is can_create
