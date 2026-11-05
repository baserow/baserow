import json

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
)
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.handler import CoreHandler
from baserow.core.job_types import DuplicateApplicationJobType
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Agent
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress

INTERNAL_COPY = {"is_duplicate": True, "exclude_sensitive_data": False}
INTERNAL_CONFIG = ImportExportConfig(include_permission_data=False, **INTERNAL_COPY)


def export_internal(agent: AgentApplication) -> dict:
    serialized = AgentApplicationType().export_serialized(agent, INTERNAL_CONFIG)
    return json.loads(json.dumps(serialized))


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
        data_fixture.create_agent_message(
            conversation=conversation,
            role=AgentMessage.Role.ASSISTANT,
            status=ChatRunStatus.FAILED,
            error_code="timeout",
        )

    copied = CoreHandler().duplicate_application(copier, agent).specific

    assert conversation_values(copied) == conversation_values(agent)
    assert uuids(copied).isdisjoint(uuids(agent))


@pytest.mark.django_db
@pytest.mark.parametrize("trashed", [False, True])
def test_run_as_is_kept_only_by_copies_in_the_same_workspace(
    data_fixture, configured_agent, trashed
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    identity = Agent.objects.create(
        workspace=agent.workspace, name="Investor", trashed=trashed
    )
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    agent.save()

    duplicate = CoreHandler().duplicate_application(user, agent).specific
    imported = AgentApplicationType().import_serialized(
        data_fixture.create_workspace(user=user),
        export_internal(agent),
        INTERNAL_CONFIG,
        {},
    )

    assert duplicate.run_as_subject_id == identity.id
    assert (imported.run_as_subject_type, imported.run_as_subject_id) == (None, None)
    assert (
        AgentHandler().is_run_as_subject_usable(
            duplicate.run_as_subject_type,
            duplicate.run_as_subject_id,
            duplicate.workspace,
        )
        is not trashed
    )


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["missing", "foreign", "unsupported", "unknown"])
def test_run_as_copy_clears_invalid_references(data_fixture, configured_agent, state):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    if state == "missing":
        identity.delete()
    elif state == "foreign":
        identity.workspace = data_fixture.create_workspace()
        identity.save()
    elif state == "unsupported":
        agent.run_as_subject_type, agent.run_as_subject_id = "auth.User", user.id
    else:
        agent.run_as_subject_type = "unknown.subject"
    agent.save()

    copied = CoreHandler().duplicate_application(user, agent).specific

    assert (copied.run_as_subject_type, copied.run_as_subject_id) == (None, None)


@pytest.mark.django_db
@pytest.mark.parametrize("trashed_at_creation", [False, True])
def test_snapshot_preserves_run_as_through_identity_trash_and_restore(
    data_fixture, configured_agent, use_tmp_media_root, trashed_at_creation
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    identity = Agent.objects.create(
        workspace=agent.workspace, name="Investor", trashed=trashed_at_creation
    )
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    agent.save()
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=agent, name=agent.name, created_by=user
    )
    snapshots = SnapshotHandler()

    snapshots.perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    archived = snapshot.snapshot_to_application.specific
    assert archived.workspace_id is None
    assert (archived.run_as_subject_type, archived.run_as_subject_id) == (
        "core.Agent",
        identity.id,
    )

    identity.trashed = True
    identity.save()
    restored = snapshots.perform_restore(snapshot, Progress(total=100)).specific
    assert (restored.run_as_subject_type, restored.run_as_subject_id) == (
        "core.Agent",
        identity.id,
    )
    handler = AgentHandler()
    assert not handler.is_run_as_subject_usable(
        restored.run_as_subject_type, restored.run_as_subject_id, restored.workspace
    )

    identity.trashed = False
    identity.save()
    assert handler.is_run_as_subject_usable(
        restored.run_as_subject_type, restored.run_as_subject_id, restored.workspace
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "config_values,keeps_identity",
    [
        ({}, False),
        ({"exclude_sensitive_data": False}, False),
        ({"is_duplicate": True}, False),
        ({**INTERNAL_COPY, "is_template": True}, False),
        ({"is_user_template": True}, False),
        (INTERNAL_COPY, True),
        ({**INTERNAL_COPY, "only_structure": True}, True),
    ],
    ids=[
        "portable",
        "portable-with-sensitive-data",
        "sensitive-excluded",
        "template",
        "user-template",
        "internal",
        "internal-structure-only",
    ],
)
def test_run_as_is_exported_only_for_internal_copies(
    data_fixture, configured_agent, config_values, keeps_identity
):
    agent = configured_agent()
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    config = ImportExportConfig(include_permission_data=False, **config_values)

    serialized = AgentApplicationType().export_serialized(agent, config)

    if keeps_identity:
        assert serialized["run_as_subject_type"] == "core.Agent"
        assert serialized["run_as_subject_id"] == identity.id
    else:
        assert "run_as_subject_type" not in serialized
        assert "run_as_subject_id" not in serialized


@pytest.mark.django_db
def test_portable_import_clears_run_as_even_when_identity_exists(
    data_fixture, configured_agent
):
    agent = configured_agent()
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id

    imported = AgentApplicationType().import_serialized(
        agent.workspace,
        export_internal(agent),
        ImportExportConfig(include_permission_data=False),
        {},
    )

    assert (imported.run_as_subject_type, imported.run_as_subject_id) == (None, None)


@pytest.mark.django_db
def test_template_install_clears_run_as_with_a_destination_identity_collision(
    data_fixture, configured_agent, tmp_path, settings
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    template = data_fixture.create_template(slug="agent-identity-collision")
    settings.APPLICATION_TEMPLATES_DIR = str(tmp_path)
    # Old or crafted templates can contain an id that is valid in the destination.
    # Installing into that workspace proves the template guard, not the workspace
    # check, prevents binding the identity.
    (tmp_path / "agent-identity-collision.json").write_text(
        json.dumps({"export": [export_internal(agent)]})
    )

    applications, _ = CoreHandler().install_template(user, agent.workspace, template)

    installed = applications[0].specific
    assert (installed.run_as_subject_type, installed.run_as_subject_id) == (None, None)


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
    )

    copied = CoreHandler().duplicate_application(owner, agent).specific

    reply = AgentMessage.objects.get(conversation__agent=copied)
    assert (reply.status, reply.error_code) == ("failed", "interrupted")
