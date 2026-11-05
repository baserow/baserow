from django.urls import reverse

import pytest

from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.core.models import Agent, Operation
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
def test_application_builder_can_choose_an_identity_without_workspace_listing(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=enterprise_data_fixture.create_user(), members=[user]
    )
    application = enterprise_data_fixture.create_agent_application(workspace=workspace)
    identity = Agent.objects.create(workspace=workspace, name="Investor")
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
        reverse("api:subjects:list"),
        {"workspace_id": workspace.id, "subject_types": "core.Agent"},
        **auth,
    )
    choices = api_client.get(
        reverse("api:agent:run_as_subjects", kwargs={"agent_id": application.id}),
        **auth,
    )
    updated = api_client.patch(
        reverse("api:agent:configuration", kwargs={"agent_id": application.id}),
        {"run_as_subject_type": "core.Agent", "run_as_subject_id": identity.id},
        format="json",
        **auth,
    )

    assert workspace_options.status_code == 401
    assert choices.status_code == 200
    assert [item["subject_id"] for item in choices.json()["results"]] == [identity.id]
    assert updated.status_code == 200
    assert updated.json()["run_as"]["id"] == identity.id


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
        reverse("api:agent:run_as_subjects", kwargs={"agent_id": application.id}),
        **auth,
    )

    assert configuration.status_code == 200
    assert choices.status_code == 401
