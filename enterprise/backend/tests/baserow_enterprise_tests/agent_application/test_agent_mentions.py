"""
"Only run when the agent is mentioned": the row comment trigger option, the
agent mention in comments it reacts to, and the picker that lists it.
"""

from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.exceptions import PermissionException
from baserow.core.prosemirror.schema import schema
from baserow.core.prosemirror.utils import (
    extract_mention_ids,
    extract_mentioned_user_ids,
)
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.agent_application.application_types import (
    AgentApplicationType,
)
from baserow_enterprise.agent_application.mention_types import (
    AgentApplicationMentionTargetType,
)
from baserow_enterprise.agent_application.models import AgentChat, AgentChatMessage
from baserow_enterprise.agent_application.triggers.handler import (
    AgentTriggerHandler,
)

from .test_agent_triggers import agent_with_table  # noqa: F401

PATCHES = (
    "baserow_enterprise.agent_application.tasks.run_agent_chat.delay",
    "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group",
)


def _message(*mentions):
    """A one-paragraph comment with the given `(kind, id, label)` mentions."""

    return schema.node(
        "doc",
        {},
        [
            schema.node(
                "paragraph",
                {},
                [schema.text("Hello ")]
                + [
                    schema.node("mention", {"id": id_, "label": label, "kind": kind})
                    for kind, id_, label in mentions
                ],
            )
        ],
    ).to_json()


def _comment_trigger(user, application, table, only_when_mentioned):
    integration = application.integrations.first().specific
    return AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_row_comment_created",
        service_values={"table_id": table.id, "integration_id": integration.id},
        config={"only_when_mentioned": only_when_mentioned},
    )


def test_user_and_application_mentions_are_told_apart():
    doc = _message(("user", 7, "Ann"), ("application", 42, "Support agent"))
    assert extract_mentioned_user_ids(doc) == {7}
    assert extract_mention_ids(doc, "application") == {42}
    # Older documents have no kind and only ever mentioned users.
    legacy = _message(("user", 7, "Ann"))
    legacy["content"][0]["content"][1]["attrs"].pop("kind")
    assert extract_mentioned_user_ids(legacy) == {7}


@pytest.mark.django_db
def test_trigger_options_are_validated_and_kept(agent_with_table):  # noqa: F811
    user, token, workspace, application, agent, table, field = agent_with_table
    trigger = _comment_trigger(user, application, table, True)
    assert trigger.config == {"only_when_mentioned": True}

    with pytest.raises(DRFValidationError):
        AgentTriggerHandler().update_trigger(
            user, trigger, config={"only_when_mentioned": "yes"}
        )
    # Unknown keys are dropped, a missing option means off.
    AgentTriggerHandler().update_trigger(user, trigger, config={"unknown": 1})
    trigger.refresh_from_db()
    assert trigger.config == {"only_when_mentioned": False}

    serialized = AgentApplicationType().export_serialized(
        application, ImportExportConfig(include_permission_data=False)
    )
    assert serialized["triggers"][0]["config"] == {"only_when_mentioned": False}


# The comment signal reaches the trigger on commit.
@pytest.mark.django_db(transaction=True)
def test_a_mention_only_trigger_runs_for_its_own_mentions(
    premium_data_fixture,
    agent_with_table,  # noqa: F811
):
    from baserow_premium.row_comments.handler import RowCommentHandler

    user, token, workspace, application, agent, table, field = agent_with_table
    premium_data_fixture.create_active_premium_license_for_user(user)
    row = table.get_model().objects.create()
    _comment_trigger(user, application, table, True)

    with override_settings(DEBUG=True), patch(PATCHES[0]), patch(PATCHES[1]):
        # No mention, and a mention of someone else: nothing runs.
        RowCommentHandler.create_comment(user, table.id, row.id, _message())
        RowCommentHandler.create_comment(
            user, table.id, row.id, _message(("user", user.id, user.first_name))
        )
        assert not AgentChat.objects.filter(agent=agent).exists()

        comment = RowCommentHandler.create_comment(
            user,
            table.id,
            row.id,
            _message(("application", application.id, application.name)),
        )

    assert list(comment.mentioned_applications.values_list("id", flat=True)) == [
        application.id
    ]
    assert not comment.mentions.exists()
    chat = AgentChat.objects.get(agent=agent)
    system_message = chat.messages.get(role=AgentChatMessage.Role.SYSTEM)
    assert "you were mentioned" in system_message.content
    assert chat.event_payload["mentioned_application_ids"] == [application.id]


@pytest.mark.django_db
def test_mentionable_agents_are_listed_per_table(
    api_client,
    premium_data_fixture,
    enterprise_data_fixture,
    agent_with_table,  # noqa: F811
):
    from baserow_premium.row_comments.handler import RowCommentHandler

    user, token, workspace, application, agent, table, field = agent_with_table
    premium_data_fixture.create_active_premium_license_for_user(user)
    other_table = enterprise_data_fixture.create_database_table(
        user=user, database=table.database
    )
    target = {"type": "application", "id": application.id, "name": application.name}

    # Without the option the agent reacts to every comment; a mention would
    # mean nothing, so it is not offered.
    trigger = _comment_trigger(user, application, table, False)
    assert AgentApplicationMentionTargetType().list_mentionable(user, table) == []

    AgentTriggerHandler().update_trigger(
        user, trigger, config={"only_when_mentioned": True}
    )
    application.refresh_from_db()
    assert RowCommentHandler.get_mentionable_targets(user, table.id) == [target]
    assert RowCommentHandler.get_mentionable_targets(user, other_table.id) == []

    response = api_client.get(
        reverse(
            "api:premium:row_comments:mentionables",
            kwargs={"table_id": table.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    assert response.json() == [target]

    # A paused agent or a disabled trigger drops out of the picker.
    AgentTriggerHandler().update_trigger(user, trigger, enabled=False)
    assert RowCommentHandler.get_mentionable_targets(user, table.id) == []
    AgentTriggerHandler().update_trigger(user, trigger, enabled=True)
    application.active = False
    application.save(update_fields=["active"])
    assert RowCommentHandler.get_mentionable_targets(user, table.id) == []

    stranger = enterprise_data_fixture.create_user()
    with pytest.raises(PermissionException):
        RowCommentHandler.get_mentionable_targets(stranger, table.id)


@pytest.mark.django_db(transaction=True)
def test_the_agent_replies_on_the_row_and_does_not_trigger_itself(
    premium_data_fixture,
    agent_with_table,  # noqa: F811
):
    import asyncio
    from types import SimpleNamespace

    from baserow_enterprise.agent_application.tools.row_comment_reply import (
        reply_to_row_comment,
    )
    from baserow_premium.api.row_comments.serializers import RowCommentSerializer
    from baserow_premium.row_comments.handler import RowCommentHandler
    from baserow_premium.row_comments.models import RowComment

    user, token, workspace, application, agent, table, field = agent_with_table
    premium_data_fixture.create_active_premium_license_for_user(user)
    row = table.get_model().objects.create()
    # Reacts to every comment, which is where a reply could loop.
    _comment_trigger(user, application, table, False)

    with override_settings(DEBUG=True), patch(PATCHES[0]), patch(PATCHES[1]):
        RowCommentHandler.create_comment(user, table.id, row.id, _message())
        chat = AgentChat.objects.get(agent=agent)
        ctx = SimpleNamespace(deps=SimpleNamespace(chat=chat, agent=agent))
        result = asyncio.run(reply_to_row_comment(ctx, "On it, give me a minute."))

    reply = RowComment.objects.get(id=result["comment_id"])
    assert reply.user_id is None
    assert reply.author_application_id == application.id
    assert reply.message["content"][0]["content"][0]["text"] == (
        "On it, give me a minute."
    )
    serialized = RowCommentSerializer(reply).data
    assert serialized["first_name"] == application.name
    assert serialized["author_application_id"] == application.id
    # The agent's own comment started no second run.
    assert AgentChat.objects.filter(agent=agent).count() == 1

    manual = AgentChat.objects.create(agent=agent, user=user)
    ctx = SimpleNamespace(deps=SimpleNamespace(chat=manual, agent=agent))
    assert "error" in asyncio.run(reply_to_row_comment(ctx, "hi"))
