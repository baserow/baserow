from django.db import transaction
from django.test import TestCase
from django.urls import reverse

import pytest
from baserow_premium_tests.row_comments.utils import create_comment_scenario

from baserow.contrib.agent.models import AgentMessage
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.contrib.agent.triggers.tasks import start_trigger_conversations
from baserow.contrib.automation.api.nodes.serializers import AutomationNodeSerializer
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.prosemirror.utils import prosemirror_doc_from_plain_text
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowRowCommentPosted,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_premium.license.cache import invalidate_cached_instance_wide_licenses
from baserow_premium.row_comments.handler import RowCommentHandler

TYPE = "local_baserow_row_comment_posted"
pytestmark = pytest.mark.django_db


@pytest.fixture
def scenario(enterprise_data_fixture, enable_enterprise, synced_roles):
    return create_comment_scenario(enterprise_data_fixture)


def post(scenario, *mentions, text="Please review", row=None, author=None):
    row = scenario.task_rows[0] if row is None else row
    message = prosemirror_doc_from_plain_text(text)
    if mentions:
        message["content"].append(
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "mention",
                        "attrs": {"id": user.id, "label": user.first_name},
                    }
                    for user in mentions
                ],
            }
        )
    with TestCase.captureOnCommitCallbacks(execute=True):
        return RowCommentHandler.create_comment(
            author or scenario.ctx.user, row.get_parent().id, row.id, message
        )


def publish(fixture, scenario, only_when_mentioned):
    automation = fixture.create_automation_application(workspace=scenario.ctx.workspace)
    workflow = fixture.create_automation_workflow(
        automation=automation, create_trigger=False
    )
    integration = fixture.create_local_baserow_integration(
        application=automation, authorized_user=scenario.bob
    )
    service = LocalBaserowRowCommentPosted.objects.create(
        table=scenario.tasks,
        integration=integration,
        only_when_mentioned=only_when_mentioned,
    )
    fixture.create_automation_node(type=TYPE, workflow=workflow, service=service)
    return AutomationWorkflowHandler().publish(workflow)


def test_published_workflows_match_the_integrations_user_and_table(
    scenario, enterprise_data_fixture, mocker
):
    all_posts = publish(enterprise_data_fixture, scenario, False)
    mentions = publish(enterprise_data_fixture, scenario, True)
    start = mocker.patch.object(AutomationWorkflowHandler, "async_start_workflow")

    post(scenario, scenario.bob, row=scenario.project_rows[0])
    start.assert_not_called()
    literal = post(scenario, text="@Bob")
    assert [call.args[0] for call in start.call_args_list] == [all_posts]
    start.reset_mock()
    with TestCase.captureOnCommitCallbacks(execute=True):
        RowCommentHandler.update_comment(
            scenario.ctx.user,
            literal,
            scenario.comments[0].message,
        )
    start.assert_not_called()
    post(scenario, scenario.ctx.user)
    assert [call.args[0] for call in start.call_args_list] == [all_posts]
    start.reset_mock()
    comment = post(scenario, scenario.bob)
    assert {call.args[0].id for call in start.call_args_list} == {
        all_posts.id,
        mentions.id,
    }
    expected = {
        "comment_id": comment.id,
        "table_id": scenario.tasks.id,
        "row_id": scenario.task_rows[0].id,
        "text": "Please review\n@Bob",
        "user_id": scenario.ctx.user.id,
        "user_name": "Anna",
        "created_on": comment.created_on.isoformat(),
        "mentioned_user_ids": [scenario.bob.id],
    }
    assert [call.args[1] for call in start.call_args_list] == [expected, expected]
    service = LocalBaserowRowCommentPosted.objects.filter(
        only_when_mentioned=True
    ).first()
    service_type = service.get_type()
    assert service_type.generate_schema(service)["properties"].keys() == expected.keys()
    assert service_type.extract_properties(service, ["text"]) == ["text"]
    assert (
        service_type.get_result_value(service, expected, ["text"]) == expected["text"]
    )

    RoleAssignmentHandler().assign_role(
        scenario.bob,
        scenario.ctx.workspace,
        Role.objects.get(uid="NO_ACCESS"),
    )
    start.reset_mock()
    post(scenario, scenario.bob)
    start.assert_not_called()


@pytest.mark.parametrize("role,can_read", [("VIEWER", False), ("COMMENTER", True)])
def test_automation_reports_comment_access_for_its_integration(
    scenario, enterprise_data_fixture, role, can_read
):
    RoleAssignmentHandler().assign_role(
        scenario.bob, scenario.ctx.workspace, Role.objects.get(uid=role)
    )
    workflow = publish(enterprise_data_fixture, scenario, only_when_mentioned=True)
    trigger = workflow.get_original().get_trigger().specific
    data = AutomationNodeSerializer(trigger).data
    assert data["service"]["context_data"] == {"can_read_comments": can_read}
    if can_read:
        trigger.get_type().raise_if_misconfigured(trigger)
    else:
        with pytest.raises(
            ServiceImproperlyConfiguredDispatchException, match="read row comments"
        ):
            trigger.get_type().raise_if_misconfigured(trigger)


def test_agent_uses_the_current_run_identity_for_mentions_and_comment_access(
    scenario, enterprise_data_fixture, mocker
):
    fixture = enterprise_data_fixture
    workspace = scenario.ctx.workspace
    reviewer = fixture.create_identity(
        workspace=workspace, name="Reviewer", role_uid="EDITOR"
    )
    other = fixture.create_identity(
        workspace=workspace, name="Other reviewer", role_uid="EDITOR"
    )
    agent = fixture.create_agent_application(
        workspace=workspace,
        run_as_subject_type="auth.User",
        run_as_subject_id=reviewer.id,
    )
    host = AgentTriggerService()
    trigger = host.create_trigger(
        scenario.ctx.user,
        agent.id,
        TYPE,
        service_values={"table_id": scenario.tasks.id, "only_when_mentioned": True},
    )
    queued = mocker.patch.object(start_trigger_conversations, "delay")
    assert trigger.on_overlap == "wait"
    options = next(
        option
        for option in host.list_trigger_types(scenario.ctx.user, agent.id)
        if option.type == TYPE
    )
    assert options.form_choices["mentionName"] == "Reviewer"
    post(scenario, text="@Reviewer")
    post(scenario, other)
    queued.assert_not_called()
    post(scenario, reviewer)
    trigger_id, _, firings, _, can_read, source_id = queued.call_args.args
    assert source_id == scenario.tasks.id
    assert trigger_id == trigger.id and can_read
    assert firings[0][0].endswith(
        f"Anna commented on row {scenario.task_rows[0].id} in table {scenario.tasks.id}: Please review\n@Reviewer"
    )
    queued.reset_mock()
    agent.run_as_subject_id = other.id
    agent.save(update_fields=["run_as_subject_id"])
    post(scenario, reviewer)
    post(scenario, other, author=other)
    queued.assert_not_called()
    post(scenario, other)
    assert queued.call_args.args[4]
    RoleAssignmentHandler().assign_role(
        other, workspace, Role.objects.get(uid="NO_ACCESS"), scope=scenario.tasks
    )
    queued.reset_mock()
    post(scenario, other)
    assert queued.call_args.args[2:5] == ([], 0, False)


def test_only_committed_licensed_posts_are_dispatched(
    scenario, enterprise_data_fixture, mocker
):
    service_type = service_type_registry.get(TYPE)
    dispatch = mocker.spy(service_type, "on_event")
    LocalBaserowRowCommentPosted.objects.create(table=scenario.tasks)
    with TestCase.captureOnCommitCallbacks(execute=True):
        with transaction.atomic():
            RowCommentHandler.create_comment(
                scenario.ctx.user,
                scenario.tasks.id,
                scenario.task_rows[0].id,
                prosemirror_doc_from_plain_text("Rolled back"),
            )
            dispatch.assert_not_called()
            transaction.set_rollback(True)
    dispatch.assert_not_called()

    with TestCase.captureOnCommitCallbacks(execute=True):
        RowCommentHandler.create_comment(
            scenario.ctx.user,
            scenario.tasks.id,
            scenario.task_rows[0].id,
            prosemirror_doc_from_plain_text("Posted before the licence expired"),
        )
        enterprise_data_fixture.delete_all_licenses()
        invalidate_cached_instance_wide_licenses()
    dispatch.assert_not_called()


def test_agent_api_defaults_to_all_posts_and_can_enable_mention_filter(
    scenario, enterprise_data_fixture, api_client, mocker
):
    workspace = scenario.ctx.workspace
    identity = enterprise_data_fixture.create_identity(
        workspace=workspace, name="Reviewer", role_uid="EDITOR"
    )
    agent = enterprise_data_fixture.create_agent_application(
        workspace=workspace,
        run_as_subject_type="auth.User",
        run_as_subject_id=identity.id,
        provider_type="openai",
        model_identifier="test-model",
        instructions="Review comments.",
    )
    provider = AIProviderConfig.objects.create(
        workspace=workspace, provider_type="openai", api_key="test-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="test-model"
    )
    mocker.patch.object(ChatRunHandler, "_enqueue")
    token = enterprise_data_fixture.generate_token(scenario.ctx.user)
    api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")
    response = api_client.post(
        reverse("api:agent:triggers:list", kwargs={"agent_id": agent.id}),
        {
            "type": TYPE,
            "message": "get('trigger.text')",
            "service": {"table_id": scenario.tasks.id, "integration_id": 99999},
        },
        format="json",
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["service"]["only_when_mentioned"] is False
    assert body["service"]["integration_id"] is None
    queued = mocker.patch.object(start_trigger_conversations, "delay")
    post(scenario, text="Unfiltered")
    mocker.stop(queued)
    start_trigger_conversations(*queued.call_args.args)
    response = api_client.patch(
        reverse(
            "api:agent:triggers:item",
            kwargs={"agent_id": agent.id, "trigger_id": body["id"]},
        ),
        {"service": {"only_when_mentioned": True}},
        format="json",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["service"]["only_when_mentioned"] is True
    post(scenario, text="Unmentioned")
    post(scenario, identity, text="For you")
    assert list(
        AgentMessage.objects.filter(role="trigger")
        .order_by("id")
        .values_list("content", flat=True)
    ) == ["Unfiltered", "For you\n@Reviewer"]
