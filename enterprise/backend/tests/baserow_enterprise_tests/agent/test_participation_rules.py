from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.urls import reverse

import pytest
from rest_framework.response import Response

from baserow.contrib.agent.exceptions import (
    AgentConversationWaitingForApproval,
    AgentNotReady,
)
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentMessage,
    AgentReplyStatus,
    AgentTrigger,
)
from baserow.contrib.agent.operations import (
    ApproveAgentToolCallsOperationType,
    ContinueAgentTriggeredConversationOperationType,
    CreateAgentMessageOperationType,
)
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.ai_provider.resolution import clear_ai_provider_state_cache
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig, OperationType
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
    assert response.json()["continue"] == {"role": "NOBODY", "subjects": []}

    def put(cap: str, role: str, subjects: list[dict] | None = None) -> Response:
        return api_client.put(
            base + cap + "/",
            {"role": role, "subjects": subjects or []},
            format="json",
            **auth,
        )

    def allowed(user: AbstractUser, operation: type[OperationType]) -> bool:
        return CoreHandler().check_permissions(
            user,
            operation.type,
            context=agent,
            workspace=workspace,
            raise_permission_exceptions=False,
        )

    assert put("chat", "NOBODY").status_code == 200
    trigger = fixture.create_agent_trigger(agent=agent)
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
    assert agent.pk in permissions["denied"][CreateAgentMessageOperationType.type]
    assert ApproveAgentToolCallsOperationType.type not in permissions["denied"]
    AgentTriggerService().delete_trigger(admin, agent.pk, trigger.pk)
    assert not AgentTrigger.objects.filter(agent=agent).exists()
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


@pytest.mark.django_db
def test_removing_approval_permission_keeps_history_but_blocks_resume(
    enterprise_data_fixture, synced_roles, api_client, settings
):
    settings.DEBUG = True
    fixture = enterprise_data_fixture
    author, token = fixture.create_user_and_token()
    reviewer = fixture.create_user()
    workspace = fixture.create_workspace(user=author, members=[reviewer])
    agent = fixture.create_agent_application(workspace=workspace)
    conversation = fixture.create_agent_conversation(agent=agent, user=author)
    approval = fixture.create_agent_tool_approval(conversation=conversation)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    url = reverse("api:enterprise:agent_rules", args=[agent.pk]) + "approve/"
    custom = {
        "role": "CUSTOM",
        "subjects": [{"subject_type": "auth.User", "subject_id": reviewer.pk}],
    }

    assert api_client.put(url, custom, format="json", **headers).status_code == 402
    fixture.enable_enterprise()
    RoleAssignmentHandler().assign_role(
        reviewer, workspace, Role.objects.get(uid="EDITOR")
    )
    assert api_client.put(url, custom, format="json", **headers).status_code == 200
    service = AgentService()
    service.request_approval(
        author, agent.pk, conversation.uuid, approval.reply.uuid, [reviewer.pk]
    )
    response = api_client.put(url, {"role": "ADMIN"}, format="json", **headers)
    assert response.status_code == 200
    assert service.can_follow_conversation(reviewer, conversation.pk)
    with pytest.raises(PermissionDenied):
        service.decide_approvals(
            reviewer,
            agent.pk,
            conversation.uuid,
            [{"id": approval.pk, "approved": True}],
        )
    with pytest.raises(PermissionDenied):
        service.prepare_reply(approval.reply.pk, approval_actor_id=reviewer.pk)
    approval.refresh_from_db()
    assert approval.status == approval.Status.PENDING


def configure(agent: AgentApplication) -> None:
    agent.instructions = "Help with research."
    agent.provider_type, agent.model_identifier = "openai", "test-model"
    agent.save()
    provider = AIProviderConfig.objects.create(
        workspace=agent.workspace, provider_type="openai", api_key="test-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="test-model"
    )
    # Earlier readiness checks cached the workspace without a provider.
    clear_ai_provider_state_cache()


def check(
    user: AbstractUser, operation: type[OperationType], agent: AgentApplication
) -> bool:
    return CoreHandler().check_permissions(
        user,
        operation.type,
        context=agent,
        workspace=agent.workspace,
        raise_permission_exceptions=False,
    )


@pytest.mark.django_db
def test_continuing_trigger_runs_has_its_own_rule_that_defaults_to_nobody(
    enterprise_data_fixture, enable_enterprise, synced_roles, api_client
):
    fixture = enterprise_data_fixture
    admin, token = fixture.create_user_and_token()
    editor, viewer, member = [fixture.create_user() for _ in range(3)]
    workspace = fixture.create_workspace(user=admin, members=[editor, viewer, member])
    for user, role in [(editor, "EDITOR"), (viewer, "VIEWER"), (member, "EDITOR")]:
        RoleAssignmentHandler().assign_role(user, workspace, Role.objects.get(uid=role))
    agent = fixture.create_agent_application(workspace=workspace)
    team = fixture.create_team(workspace=workspace, members=[member])
    url = reverse("api:enterprise:agent_rules", args=[agent.pk])
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    users = [admin, editor, viewer, member]
    operation = ContinueAgentTriggeredConversationOperationType

    def put(cap: str, role: str, subjects: list[dict] | None = None) -> Response:
        return api_client.put(
            url + cap + "/",
            {"role": role, "subjects": subjects or []},
            format="json",
            **auth,
        )

    def allowed_in_permissions(user: AbstractUser) -> bool:
        permissions = next(
            item["permissions"]
            for item in CoreHandler().get_permissions(user, workspace)
            if item["name"] == "agent_participation"
        )
        return agent.pk in permissions["allowed"][operation.type]

    assert [check(user, operation, agent) for user in users] == [False] * 4
    assert [allowed_in_permissions(user) for user in users] == [False] * 4
    assert put("continue", "EDITOR").status_code == 200
    assert [check(user, operation, agent) for user in users] == [
        True,
        True,
        False,
        True,
    ]
    assert [allowed_in_permissions(user) for user in users] == [
        True,
        True,
        False,
        True,
    ]
    team_subject = {"subject_type": "baserow_enterprise.Team", "subject_id": team.pk}
    assert put("continue", "CUSTOM", [team_subject]).status_code == 200
    assert [check(user, operation, agent) for user in users] == [
        False,
        False,
        False,
        True,
    ]
    assert put("continue", "NOBODY").status_code == 200
    assert not AgentParticipationRule.objects.filter(agent=agent).exists()
    assert api_client.get(url, **auth).json()["continue"]["role"] == "NOBODY"
    response = put("approve", "NOBODY")
    assert response.status_code == 400
    assert "Someone must be able to approve tool calls." in str(response.json())


@pytest.mark.django_db
def test_held_calls_follow_approve_and_messages_follow_continue_in_trigger_runs(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    fixture = enterprise_data_fixture
    admin, editor = fixture.create_user(), fixture.create_user()
    workspace = fixture.create_workspace(user=admin, members=[editor])
    RoleAssignmentHandler().assign_role(
        editor, workspace, Role.objects.get(uid="EDITOR")
    )
    agent = fixture.create_agent_application(workspace=workspace)
    conversation = fixture.create_shared_agent_conversation(agent=agent)
    sent = fixture.create_agent_message(
        conversation=conversation,
        role=AgentMessage.Role.ASSISTANT,
        sender=editor,
        unattended=False,
    )
    approval = fixture.create_agent_tool_approval(conversation=conversation)
    service = AgentService()

    # An unconfigured agent fails only once the permission checks pass.
    with pytest.raises(AgentNotReady):
        service.prepare_reply(approval.reply.pk, approval_actor_id=editor.pk)
    with pytest.raises(PermissionDenied):
        service.prepare_reply(sent.pk)
    with pytest.raises(PermissionDenied):
        service.create_message(editor, agent.pk, conversation.uuid, uuid4(), "Hi")
    AgentParticipationRule.objects.create(
        agent=agent, capability="continue", role="EDITOR"
    )
    AgentParticipationRule.objects.create(
        agent=agent, capability="approve", role="ADMIN"
    )
    with pytest.raises(AgentNotReady):
        service.prepare_reply(sent.pk)
    with pytest.raises(PermissionDenied):
        service.prepare_reply(approval.reply.pk, approval_actor_id=editor.pk)
    with pytest.raises(AgentConversationWaitingForApproval):
        service.create_message(editor, agent.pk, conversation.uuid, uuid4(), "Hi")
    approval.reply.status = AgentReplyStatus.COMPLETED
    approval.reply.save(update_fields=["status"])
    configure(agent)
    result = service.create_message(editor, agent.pk, conversation.uuid, uuid4(), "Hi")
    assert (result.created, result.message.sender) == (True, editor)


@pytest.mark.django_db
def test_without_the_licence_rules_are_kept_but_only_core_defaults_apply(
    enterprise_data_fixture, synced_roles, settings
):
    settings.DEBUG = True
    fixture = enterprise_data_fixture
    admin, editor = fixture.create_user(), fixture.create_user()
    workspace = fixture.create_workspace(user=admin, members=[editor])
    agent = fixture.create_agent_application(workspace=workspace)
    fixture.enable_enterprise()
    RoleAssignmentHandler().assign_role(
        editor, workspace, Role.objects.get(uid="EDITOR")
    )
    for capability, role in [
        ("chat", "NOBODY"),
        ("approve", "ADMIN"),
        ("continue", "EDITOR"),
    ]:
        AgentParticipationRule.objects.create(
            agent=agent, capability=capability, role=role
        )
    assert not check(editor, CreateAgentMessageOperationType, agent)
    assert not check(editor, ApproveAgentToolCallsOperationType, agent)
    assert check(editor, ContinueAgentTriggeredConversationOperationType, agent)

    fixture.delete_all_licenses()

    assert AgentParticipationRule.objects.filter(agent=agent).count() == 3
    for user in [admin, editor]:
        assert check(user, CreateAgentMessageOperationType, agent)
        assert check(user, ApproveAgentToolCallsOperationType, agent)
        assert not check(user, ContinueAgentTriggeredConversationOperationType, agent)


@pytest.mark.django_db
def test_imports_keep_continue_rules_and_skip_approve_rules_for_nobody(
    enterprise_data_fixture,
):
    fixture = enterprise_data_fixture
    user = fixture.create_user()
    workspace = fixture.create_workspace(user=user)
    agent = fixture.create_agent_application(workspace=workspace)
    AgentParticipationRule.objects.create(
        agent=agent, capability="continue", role="BUILDER"
    )
    config = ImportExportConfig(include_permission_data=True)
    processor = AgentParticipationSerializationProcessorType()
    data = processor.export_serialized(workspace, agent, config)
    data[processor.type].append(
        {
            "capability": "approve",
            "role": "NOBODY",
            "users": [],
            "teams": [],
            "workspace_id": workspace.pk,
        }
    )
    duplicate = fixture.create_agent_application(workspace=workspace)

    processor.import_serialized(workspace, duplicate, data, config)

    assert list(
        AgentParticipationRule.objects.filter(agent=duplicate).values_list(
            "capability", "role"
        )
    ) == [("continue", "BUILDER")]
