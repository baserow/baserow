import json

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentReplyTranscript,
)
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.handler import CoreHandler
from baserow.core.job_types import DuplicateApplicationJobType
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Agent
from baserow.core.registries import ImportExportConfig

INTERNAL_COPY = {"is_duplicate": True, "exclude_sensitive_data": False}
INTERNAL_CONFIG = ImportExportConfig(include_permission_data=False, **INTERNAL_COPY)


def export_internal(agent: AgentApplication) -> dict:
    serialized = AgentApplicationType().export_serialized(agent, INTERNAL_CONFIG)
    return json.loads(json.dumps(serialized))


def transcript_values(message: AgentMessage) -> tuple | None:
    transcript = getattr(message, "transcript", None)
    return transcript and (
        transcript.provider_type,
        transcript.model_identifier,
        transcript.model_messages,
        transcript.usage,
    )


def conversation_values(agent: AgentApplication) -> list[tuple]:
    return [
        (
            conversation.title,
            conversation.owner_user_id,
            conversation.created_on,
            conversation.updated_on,
            [
                (
                    message.role,
                    message.content,
                    message.status,
                    message.error_code,
                    message.steps,
                    transcript_values(message),
                    message.created_on,
                    message.updated_on,
                )
                for message in conversation.messages.order_by("id")
            ],
        )
        for conversation in agent.conversations.order_by("id")
    ]


def uuids(agent):
    return set(agent.conversations.values_list("uuid", flat=True)) | set(
        AgentMessage.objects.filter(conversation__agent=agent).values_list(
            "uuid", flat=True
        )
    )


@pytest.mark.django_db
def test_duplicate_copies_conversations_with_new_identifiers(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    copier = data_fixture.create_user()
    agent = configured_agent(
        workspace=data_fixture.create_workspace(user=copier, members=[owner])
    )
    with freeze_time("2026-01-01"):
        conversation = data_fixture.create_agent_conversation(user=owner, agent=agent)
        for role in AgentMessage.Role.values:
            data_fixture.create_agent_message(conversation=conversation, role=role)
        reply = data_fixture.create_agent_message(
            conversation=conversation,
            role=AgentMessage.Role.ASSISTANT,
            status=ChatRunStatus.FAILED,
            error_code="timeout",
            steps=[
                {
                    "id": "call_1",
                    "tool": "list_tables",
                    "presentation_type": "list_tables",
                    "status": "done",
                    "changes_data": False,
                    "input": {},
                    "facts": {},
                }
            ],
        )
        AgentReplyTranscript.objects.create(
            reply=reply,
            provider_type="openai",
            model_identifier="test-model",
            model_messages=[{"kind": "request"}],
            usage={"requests": 1},
        )

    copied = CoreHandler().duplicate_application(copier, agent).specific

    assert conversation_values(copied) == conversation_values(agent)
    assert uuids(copied).isdisjoint(uuids(agent))


@pytest.mark.django_db
def test_copies_keep_the_tools_and_only_same_workspace_copies_keep_run_as(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    agent.save()
    AgentHandler().set_allowed_tools(agent, ["list_tables", "create_rows"])

    duplicate = CoreHandler().duplicate_application(user, agent).specific
    imported = AgentApplicationType().import_serialized(
        data_fixture.create_workspace(user=user),
        export_internal(agent),
        INTERNAL_CONFIG,
        {},
    )

    assert duplicate.run_as_subject_id == identity.id
    assert (imported.run_as_subject_type, imported.run_as_subject_id) == (None, None)
    assert [
        AgentHandler().get_allowed_tool_names(copy) for copy in (duplicate, imported)
    ] == [["list_tables", "create_rows"]] * 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "config_values",
    [
        {},
        {**INTERNAL_COPY, "is_template": True},
        {**INTERNAL_COPY, "is_publishing": True},
        {**INTERNAL_COPY, "only_structure": True},
        {"is_duplicate": True},
    ],
    ids=["portable", "template", "publishing", "structure-only", "sensitive-excluded"],
)
def test_conversations_are_excluded_outside_full_internal_copies(
    data_fixture, configured_agent, config_values
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    data_fixture.create_agent_message(user=user, agent=agent, content="PRIVATE MESSAGE")
    internal = export_internal(agent)
    application_type = AgentApplicationType()
    config = ImportExportConfig(include_permission_data=False, **config_values)

    serialized = application_type.export_serialized(agent, config)
    imported = application_type.import_serialized(
        data_fixture.create_workspace(user=user), internal, config, {}
    )

    assert "PRIVATE MESSAGE" in json.dumps(internal)
    assert "PRIVATE MESSAGE" not in json.dumps(serialized)
    assert imported.instructions == agent.instructions
    assert not imported.conversations.exists()


@pytest.mark.django_db
def test_internal_copy_skips_conversations_of_deleted_owners(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    deleted_user = data_fixture.create_user()
    agent = configured_agent(user=owner)
    for user in (owner, deleted_user):
        data_fixture.create_agent_message(user=user, agent=agent)
    serialized = export_internal(agent)
    deleted_user.delete()

    copied = AgentApplicationType().import_serialized(
        agent.workspace, serialized, INTERNAL_CONFIG, {}
    )

    assert copied.conversations.get().owner_user_id == owner.id


@pytest.mark.django_db(transaction=True)
def test_duplicate_agent_job_rolls_back_failed_conversation_import(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    data_fixture.create_agent_message(user=user, agent=agent)
    mocker.patch.object(
        AgentMessage.objects,
        "bulk_create",
        side_effect=RuntimeError("Message import failed"),
    )

    with pytest.raises(RuntimeError, match="Message import failed"):
        JobHandler().create_and_start_job(
            user,
            DuplicateApplicationJobType.type,
            application_id=agent.id,
            sync=True,
        )

    assert list(AgentApplication.objects.all()) == [agent]
    assert AgentConversation.objects.count() == 1
    assert AgentMessage.objects.count() == 1


@pytest.mark.django_db
def test_a_copy_never_carries_a_reply_in_progress(data_fixture, configured_agent):
    owner = data_fixture.create_user()
    agent = configured_agent(user=owner)
    data_fixture.create_agent_message(
        user=owner,
        agent=agent,
        role=AgentMessage.Role.ASSISTANT,
        status=ChatRunStatus.RUNNING,
        steps=[{"id": "call_1", "status": "running"}],
    )

    copied = CoreHandler().duplicate_application(owner, agent).specific

    reply = AgentMessage.objects.get(conversation__agent=copied)
    assert (reply.status, reply.error_code) == ("failed", "interrupted")
    assert reply.steps == [{"id": "call_1", "status": "stopped"}]


@pytest.mark.django_db
def test_old_conversation_payloads_without_steps_still_import(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    agent = configured_agent(user=owner)
    data_fixture.create_agent_message(user=owner, agent=agent)
    serialized = export_internal(agent)
    for conversation in serialized["conversations"]:
        for message in conversation["messages"]:
            del message["steps"]

    copied = AgentApplicationType().import_serialized(
        agent.workspace, serialized, INTERNAL_CONFIG, {}
    )

    assert AgentMessage.objects.get(conversation__agent=copied).steps is None
