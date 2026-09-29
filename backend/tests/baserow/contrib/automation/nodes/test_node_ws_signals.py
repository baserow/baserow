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
        patch(
            "baserow.contrib.automation.nodes.ws.signals.broadcast_to_permitted_users"
        ) as mocked,
        django_capture_on_commit_callbacks(execute=True),
    ):
        automation_node_updated.send(None, user=None, node=node)

    payload = mocked.delay.call_args.args[4]
    assert payload["type"] == "automation_node_updated"
    assert payload["node"]["id"] == node.id
    if oversized:
        assert payload["requires_refresh"] is True
        assert payload["node"]["service"]["sample_data"] is None
    else:
        assert "requires_refresh" not in payload
        assert payload["node"]["service"]["sample_data"]["data"]["body_html"] == body
