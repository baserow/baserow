from django.urls import reverse

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.operations import (
    ApproveAgentToolCallsOperationType,
    CreateAgentMessageOperationType,
)
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.agent_permissions.models import AgentParticipationRule
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.structure_types import (
    AgentParticipationSerializationProcessorType,
)


@pytest.mark.django_db
def test_paid_rules_and_custom_team_are_independent(
    enterprise_data_fixture, synced_roles, api_client, settings
):
    settings.DEBUG = True
    fixture = enterprise_data_fixture
    admin, token = fixture.create_user_and_token()
    editor, other, viewer = [fixture.create_user() for _ in range(3)]
    workspace = fixture.create_workspace(user=admin, members=[editor, other, viewer])
    agent = fixture.create_agent_application(workspace=workspace)
    team = fixture.create_team(workspace=workspace, members=[editor, viewer])
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    base = reverse("api:enterprise:agent_rules", args=[agent.pk])
    assert api_client.get(base, **auth).status_code == 402
    fixture.enable_enterprise()
    for user, role in [(editor, "EDITOR"), (other, "EDITOR"), (viewer, "VIEWER")]:
        RoleAssignmentHandler().assign_role(user, workspace, Role.objects.get(uid=role))
    response = api_client.get(base, **auth)
    assert response.status_code == 200, response.json()
    assert response.json()["chat"]["role"] == "EDITOR"

    def put(cap, role, subjects=None):
        return api_client.put(
            base + cap + "/",
            {"role": role, "subjects": subjects or []},
            format="json",
            **auth,
        )

    def allowed(user, operation):
        return CoreHandler().check_permissions(
            user,
            operation.type,
            context=agent,
            workspace=workspace,
            raise_permission_exceptions=False,
        )

    assert put("chat", "NOBODY").status_code == 400
    trigger = fixture.create_agent_trigger(agent=agent)
    assert put("chat", "NOBODY").status_code == 200
    assert not allowed(admin, CreateAgentMessageOperationType)
    assert (
        put(
            "approve",
            "CUSTOM",
            [{"subject_type": "baserow_enterprise.Team", "subject_id": team.pk}],
        ).status_code
        == 200
    )
    assert allowed(editor, ApproveAgentToolCallsOperationType)
    assert not allowed(viewer, ApproveAgentToolCallsOperationType)
    assert not allowed(other, ApproveAgentToolCallsOperationType)
    assert not allowed(admin, ApproveAgentToolCallsOperationType)
    identity = fixture.create_identity(workspace=workspace)
    response = api_client.get(base + "options/", **auth)
    assert response.status_code == 200
    assert identity.id not in {
        item["subject_id"]
        for item in response.json()["results"]
        if item["subject_type"] == "auth.User"
    }
    conversation = fixture.create_agent_conversation(agent=agent, user=admin)
    approval = fixture.create_agent_tool_approval(conversation=conversation)
    recipients = reverse(
        "api:agent:approval_recipients", args=[agent.pk, conversation.uuid]
    )
    response = api_client.get(recipients, **auth)
    assert response.status_code == 200
    assert [person["id"] for person in response.json()["results"]] == [editor.pk]
    response = api_client.post(
        recipients,
        {"reply_uuid": str(approval.reply.uuid), "user_ids": [editor.pk, other.pk]},
        format="json",
        **auth,
    )
    assert response.status_code == 400
    assert list(conversation.participants.all()) == [admin]
    assert put("chat", "BUILDER").status_code == 200
    assert not allowed(editor, CreateAgentMessageOperationType)
    RoleAssignmentHandler().assign_role(
        other, workspace, Role.objects.get(uid="BUILDER"), scope=agent.application_ptr
    )
    assert allowed(other, CreateAgentMessageOperationType)
    assert put("chat", "ADMIN").status_code == 200
    assert not allowed(other, CreateAgentMessageOperationType)
    assert allowed(admin, CreateAgentMessageOperationType)
    assert put("chat", "NOBODY").status_code == 200
    permissions = next(
        item["permissions"]
        for item in CoreHandler().get_permissions(editor, workspace)
        if item["name"] == "agent_participation"
    )
    assert agent.pk in permissions[CreateAgentMessageOperationType.type]
    assert ApproveAgentToolCallsOperationType.type not in permissions
    with pytest.raises(ValidationError):
        AgentTriggerService().delete_trigger(admin, agent.pk, trigger.pk)
    assert put("chat", "EDITOR").status_code == 200
    assert allowed(other, CreateAgentMessageOperationType)


@pytest.mark.django_db
def test_internal_agent_copies_preserve_rules_and_scope_subjects(
    enterprise_data_fixture,
):
    fixture = enterprise_data_fixture
    user = fixture.create_user()
    workspace = fixture.create_workspace(user=user)
    agent = fixture.create_agent_application(workspace=workspace)
    team = fixture.create_team(workspace=workspace)
    rule = AgentParticipationRule.objects.create(
        agent=agent, capability="approve", role="CUSTOM"
    )
    rule.users.add(user)
    rule.teams.add(team)
    config = ImportExportConfig(include_permission_data=True)
    processor = AgentParticipationSerializationProcessorType()
    data = processor.export_serialized(workspace, agent, config)
    for target in [workspace, fixture.create_workspace(user=user)]:
        duplicate = fixture.create_agent_application(workspace=target)
        processor.import_serialized(target, duplicate, data, config)
        copied = AgentParticipationRule.objects.get(agent=duplicate)
        assert copied.role == "CUSTOM"
        assert list(copied.users.all()) == ([user] if target == workspace else [])
        assert list(copied.teams.all()) == ([team] if target == workspace else [])
    assert (
        processor.export_serialized(
            workspace, agent, ImportExportConfig(include_permission_data=False)
        )
        is None
    )
