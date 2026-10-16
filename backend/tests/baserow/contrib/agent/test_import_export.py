import json

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
)
from baserow.contrib.agent.service import AgentService
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig

INTERNAL_COPY = {"is_duplicate": True, "exclude_sensitive_data": False}


def history(agent):
    return [
        (
            conversation.title,
            conversation.source_type,
            conversation.visibility,
            conversation.owner_user_id,
            conversation.initiated_by_id,
            conversation.created_on,
            conversation.updated_on,
            [
                (message.role, message.content, message.author_user_id)
                + (message.created_on, message.updated_on)
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
def test_duplicate_copies_saved_history_with_new_identifiers(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    copier = data_fixture.create_user()
    agent = configured_agent(
        workspace=data_fixture.create_workspace(user=copier, members=[owner])
    )
    with freeze_time("2026-01-01"):
        conversation = data_fixture.create_agent_conversation(
            user=owner,
            agent=agent,
            initiated_by=copier,
            source_type="trigger",
            visibility="shared",
        )
        for role in AgentMessage.Role.values:
            data_fixture.create_agent_message(
                user=owner if role == "user" else None,
                conversation=conversation,
                role=role,
            )
    AgentService().update_configuration(copier, agent.id, instructions="Saved")

    copied = CoreHandler().duplicate_application(copier, agent).specific

    assert copied.instructions == "Saved"
    assert history(copied) == history(agent)
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
def test_private_history_is_excluded_outside_full_internal_copies(
    data_fixture, configured_agent, config_values
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    data_fixture.create_agent_message(user=user, agent=agent, content="PRIVATE HISTORY")
    application_type = AgentApplicationType()
    internal = json.loads(
        json.dumps(
            application_type.export_serialized(
                agent,
                ImportExportConfig(include_permission_data=False, **INTERNAL_COPY),
            )
        )
    )
    config = ImportExportConfig(include_permission_data=False, **config_values)

    serialized = application_type.export_serialized(agent, config)
    imported = application_type.import_serialized(
        data_fixture.create_workspace(user=user), internal, config, {}
    )

    assert "PRIVATE HISTORY" in json.dumps(internal)
    assert "PRIVATE HISTORY" not in json.dumps(serialized)
    assert imported.instructions == agent.instructions
    assert not imported.conversations.exists()


@pytest.mark.django_db
def test_internal_copy_skips_deleted_owners_and_clears_deleted_attribution(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    deleted_user = data_fixture.create_user()
    agent = configured_agent(user=owner)
    removed = data_fixture.create_agent_conversation(user=deleted_user, agent=agent)
    retained = data_fixture.create_agent_conversation(
        user=owner, agent=agent, initiated_by=deleted_user
    )
    for conversation in (removed, retained):
        data_fixture.create_agent_message(user=deleted_user, conversation=conversation)
    config = ImportExportConfig(include_permission_data=False, **INTERNAL_COPY)
    application_type = AgentApplicationType()
    serialized = json.loads(
        json.dumps(application_type.export_serialized(agent, config))
    )
    deleted_user.delete()

    copied = application_type.import_serialized(agent.workspace, serialized, config, {})

    conversation = copied.conversations.get()
    assert (conversation.owner_user_id, conversation.initiated_by_id) == (
        owner.id,
        None,
    )
    assert conversation.messages.get().author_user_id is None


@pytest.mark.django_db
def test_failed_history_import_rolls_back_the_whole_agent(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    data_fixture.create_agent_message(user=user, agent=agent)
    config = ImportExportConfig(include_permission_data=False, **INTERNAL_COPY)
    application_type = AgentApplicationType()
    serialized = application_type.export_serialized(agent, config)
    mocker.patch.object(AgentMessage.objects, "bulk_create", side_effect=RuntimeError)

    with pytest.raises(RuntimeError):
        application_type.import_serialized(agent.workspace, serialized, config, {})

    assert list(AgentApplication.objects.all()) == [agent]
    assert AgentConversation.objects.count() == 1
