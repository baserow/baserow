import json

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
)
from baserow.core.chat_runs.models import ChatRun
from baserow.core.handler import CoreHandler
from baserow.core.job_types import DuplicateApplicationJobType
from baserow.core.jobs.handler import JobHandler
from baserow.core.registries import ImportExportConfig

INTERNAL_COPY = {"is_duplicate": True, "exclude_sensitive_data": False}
INTERNAL_CONFIG = ImportExportConfig(include_permission_data=False, **INTERNAL_COPY)


def export_internal(agent: AgentApplication) -> dict:
    serialized = AgentApplicationType().export_serialized(agent, INTERNAL_CONFIG)
    return json.loads(json.dumps(serialized))


def conversation_values(agent: AgentApplication) -> list[tuple]:
    values = []
    for conversation in agent.conversations.order_by("id"):
        values.append(
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
                        message.created_on,
                        message.updated_on,
                    )
                    for message in conversation.messages.order_by("id")
                ],
            )
        )
    return values


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
        data_fixture.create_agent_message(
            conversation=conversation,
            role=AgentMessage.Role.ASSISTANT,
            status=AgentMessage.Status.FAILED,
            error_code="timeout",
        )

    copied = CoreHandler().duplicate_application(copier, agent).specific

    assert conversation_values(copied) == conversation_values(agent)
    assert uuids(copied).isdisjoint(uuids(agent))


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


@pytest.mark.django_db
def test_internal_copy_imports_messages_copied_before_replies(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    agent = configured_agent(user=owner)
    data_fixture.create_agent_message(user=owner, agent=agent, content="Hi")
    serialized = export_internal(agent)
    for data in serialized["conversations"]:
        for message in data["messages"]:
            del message["status"], message["error_code"]

    copied = AgentApplicationType().import_serialized(
        agent.workspace, serialized, INTERNAL_CONFIG, {}
    )

    message = AgentMessage.objects.get(conversation__agent=copied)
    assert (message.content, message.status, message.error_code) == ("Hi", None, "")


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
        status=AgentMessage.Status.RUNNING,
    )

    copied = CoreHandler().duplicate_application(owner, agent).specific

    reply = AgentMessage.objects.get(conversation__agent=copied)
    assert (reply.status, reply.error_code) == ("failed", "interrupted")
    assert not ChatRun.objects.exists()
