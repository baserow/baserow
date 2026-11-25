from uuid import uuid4

from django.db import connection

import pytest


@pytest.mark.once_per_day_in_ci
def test_0019_clears_run_as_bindings_to_legacy_agents(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate(
        [("agent", "0018_agent_trigger_batch_size"), ("core", "0139_user_identities")]
    )
    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    AgentApplication = old_state.apps.get_model("agent", "AgentApplication")
    content_type, _ = ContentType.objects.get_or_create(
        app_label="agent", model="agentapplication"
    )
    workspace = Workspace.objects.create(name="Legacy")
    for subject_type in ("core.Agent", "auth.User"):
        AgentApplication.objects.create(
            workspace=workspace,
            name=subject_type,
            order=1,
            content_type=content_type,
            run_as_subject_type=subject_type,
            run_as_subject_id=1,
        )

    migrator.migrate([("agent", "0019_clear_legacy_agent_run_as")])

    bindings = list(
        AgentApplication.objects.order_by("id").values_list(
            "run_as_subject_type", "run_as_subject_id"
        )
    )
    # Later migration tests share this database and create rows with fixed ids.
    with connection.cursor() as cursor:
        cursor.execute(f'TRUNCATE "{Workspace._meta.db_table}" CASCADE')

    assert bindings == [(None, None), ("auth.User", 1)]


@pytest.mark.once_per_day_in_ci
def test_0022_shares_trigger_conversations_and_names_message_senders(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate(
        [("agent", "0021_agentapplication_pending_tool_choices")]
    )
    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    User = old_state.apps.get_model("auth", "User")
    Workspace = old_state.apps.get_model("core", "Workspace")
    AgentApplication = old_state.apps.get_model("agent", "AgentApplication")
    AgentConversation = old_state.apps.get_model("agent", "AgentConversation")
    AgentMessage = old_state.apps.get_model("agent", "AgentMessage")
    agent = AgentApplication.objects.create(
        workspace=Workspace.objects.create(name="Agents"),
        name="Agent",
        order=1,
        content_type=ContentType.objects.get_or_create(
            app_label="agent", model="agentapplication"
        )[0],
    )
    owner = User.objects.create(username="owner@example.com")
    for owner_user, title in [(owner, "Private"), (None, "Triggered")]:
        conversation = AgentConversation.objects.create(
            agent=agent, uuid=uuid4(), title=title, owner_user=owner_user
        )
        AgentMessage.objects.create(
            conversation=conversation, uuid=uuid4(), content=title
        )

    new_state = migrator.migrate([("agent", "0022_conversation_sharing")])

    rows = sorted(
        new_state.apps.get_model("agent", "AgentMessage").objects.values_list(
            "content",
            "conversation__shared",
            "conversation__started_by_trigger",
            "sender_id",
        )
    )
    with connection.cursor() as cursor:
        cursor.execute(f'TRUNCATE "{Workspace._meta.db_table}" CASCADE')
        cursor.execute(f'TRUNCATE "{User._meta.db_table}" CASCADE')

    assert rows == [
        ("Private", False, False, owner.id),
        ("Triggered", True, True, None),
    ]


@pytest.mark.once_per_day_in_ci
def test_0025_makes_owners_participants_and_trigger_messages_unattended(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate([("agent", "0022_conversation_sharing")])
    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    User = old_state.apps.get_model("auth", "User")
    Workspace = old_state.apps.get_model("core", "Workspace")
    AgentApplication = old_state.apps.get_model("agent", "AgentApplication")
    AgentConversation = old_state.apps.get_model("agent", "AgentConversation")
    AgentMessage = old_state.apps.get_model("agent", "AgentMessage")
    agent = AgentApplication.objects.create(
        workspace=Workspace.objects.create(name="Agents"),
        name="Agent",
        order=1,
        content_type=ContentType.objects.get_or_create(
            app_label="agent", model="agentapplication"
        )[0],
    )
    owner = User.objects.create(username="owner@example.com")
    for owner_user, title in [(owner, "Private"), (None, "Triggered")]:
        conversation = AgentConversation.objects.create(
            agent=agent,
            uuid=uuid4(),
            title=title,
            owner_user=owner_user,
            shared=owner_user is None,
            started_by_trigger=owner_user is None,
        )
        AgentMessage.objects.create(
            conversation=conversation, uuid=uuid4(), content=title
        )

    new_state = migrator.migrate([("agent", "0025_conversation_participants")])

    rows = sorted(
        new_state.apps.get_model("agent", "AgentMessage").objects.values_list(
            "content", "conversation__participants", "unattended"
        )
    )
    with connection.cursor() as cursor:
        cursor.execute(f'TRUNCATE "{Workspace._meta.db_table}" CASCADE')
        cursor.execute(f'TRUNCATE "{User._meta.db_table}" CASCADE')

    assert rows == [("Private", owner.id, False), ("Triggered", None, True)]
