import json
from unittest.mock import patch

from django.core.serializers.json import DjangoJSONEncoder

import pytest

from baserow.contrib.automation.nodes.node_types import (
    CoreInboundEmailTriggerNodeType,
)
from baserow.contrib.automation.nodes.signals import automation_node_updated
from baserow.contrib.automation.nodes.ws.signals import (
    AUTOMATION_NODE_EVENT_MAX_BYTES,
    bounded_node_event,
)


def _size(event):
    return len(
        json.dumps(
            event, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    )


def test_bounded_node_event_leaves_small_events_untouched():
    event = {
        "type": "automation_node_updated",
        "node": {"id": 1, "service": {"sample_data": {"data": {"subject": "Hi"}}}},
    }

    assert bounded_node_event(event) is event


def test_bounded_node_event_drops_sample_data_and_flags_refresh_when_too_large():
    event = {
        "type": "automation_node_updated",
        "node": {
            "id": 1,
            "label": "Email Trigger",
            "service": {
                "id": 5,
                "sample_data": {"data": {"body_html": "x" * (2 * 1024 * 1024)}},
            },
        },
    }
    assert _size(event) > AUTOMATION_NODE_EVENT_MAX_BYTES

    bounded = bounded_node_event(event)

    assert bounded["requires_refresh"] is True
    assert bounded["node"]["service"]["sample_data"] is None
    assert bounded["node"]["service"]["id"] == 5
    assert bounded["node"]["label"] == "Email Trigger"
    assert _size(bounded) <= AUTOMATION_NODE_EVENT_MAX_BYTES
    # The original is not mutated: it may still be used by the caller.
    assert event["node"]["service"]["sample_data"]["data"]["body_html"]


@pytest.mark.enable_signals(
    "baserow.contrib.automation.nodes.ws.tasks."
    "broadcast_node_event_to_permitted_users.delay"
)
@pytest.mark.django_db
@pytest.mark.parametrize("oversized", [True, False])
def test_node_updated_broadcast_is_bounded(
    data_fixture, django_capture_on_commit_callbacks, oversized
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreInboundEmailTriggerNodeType.type
    )
    node = workflow.get_trigger()
    service = node.service.specific
    body = "x" * (2 * 1024 * 1024) if oversized else "small body"
    service.sample_data = {"data": {"body_html": body}}
    service.save()

    with (
        patch("baserow.ws.tasks.broadcast_to_users") as mocked,
        django_capture_on_commit_callbacks(execute=True),
    ):
        automation_node_updated.send(None, user=None, node=node)

    user_ids, payload = mocked.call_args.args
    assert user_ids == [user.id]
    assert payload["type"] == "automation_node_updated"
    assert payload["node"]["id"] == node.id
    if oversized:
        assert payload["requires_refresh"] is True
        assert payload["node"]["service"]["sample_data"] is None
    else:
        assert "requires_refresh" not in payload
        assert payload["node"]["service"]["sample_data"]["data"]["body_html"] == body


@pytest.mark.django_db
def test_node_events_leave_the_reading_to_the_task(
    data_fixture, django_capture_on_commit_callbacks
):
    """
    A test run sends an event for every node: the request only queues them, so
    it doesn't read the workflow and its formulas again for each.
    """

    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    nodes = [
        data_fixture.create_core_router_action_node(workflow=workflow) for _ in range(5)
    ]

    with (
        patch(
            "baserow.contrib.automation.nodes.ws.signals."
            "broadcast_node_event_to_permitted_users"
        ) as task,
        patch(
            "baserow.contrib.automation.nodes.access.node_reads",
            side_effect=AssertionError("The formulas were read in the request."),
        ),
        patch(
            "baserow.contrib.automation.api.nodes.serializers."
            "AutomationNodeSerializer.to_representation",
            side_effect=AssertionError("A node was serialized in the request."),
        ),
        django_capture_on_commit_callbacks(execute=True),
    ):
        for node in nodes:
            automation_node_updated.send(None, user=None, node=node)

    assert [call.args[1:3] for call in task.delay.call_args_list] == [
        (node.id, "automation_node_updated") for node in nodes
    ]
