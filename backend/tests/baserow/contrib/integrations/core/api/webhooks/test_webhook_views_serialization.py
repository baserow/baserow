"""
Tests for HTTP trigger view payload normalization.

These tests verify that the HTTP trigger view normalizes incoming request
bodies containing oversized integers before they enter the workflow system.
This is the input boundary normalization that prevents OverflowError during
subsequent websocket broadcasts.
"""

import json

import pytest
from django.urls import reverse
from rest_framework.status import HTTP_204_NO_CONTENT
from unittest.mock import patch


def get_url(uid):
    return reverse("api:http_trigger", kwargs={"webhook_uid": uid})


@pytest.mark.django_db
def test_http_trigger_normalizes_overflow_integer_in_body(api_client, data_fixture):
    """
    Verify that POST data containing an integer exceeding msgpack's uint64
    max is normalized to a string in the request_data body before being
    passed to process_webhook_request.

    Without this normalization, the integer would flow through the workflow
    system and eventually cause OverflowError during websocket broadcast.
    """

    node = data_fixture.create_http_trigger_node()
    url = get_url(node.service.uid) + "?test=true"

    # Capture the request_data that gets passed to process_webhook_request
    captured_data = {}

    original_process = None

    def capture_request_data(self_svc, webhook_uid, request_data, simulate):
        captured_data.update(request_data)
        return original_process(webhook_uid, request_data, simulate)

    from baserow.core.services.registries import service_type_registry

    service_type = service_type_registry.get("http_trigger")
    original_process = service_type.process_webhook_request

    with patch.object(
        type(service_type),
        "process_webhook_request",
        side_effect=capture_request_data,
        autospec=True,
    ):
        resp = api_client.post(
            url,
            data=json.dumps({"overflow": 18446744073709551616, "safe": 42}),
            content_type="application/json",
        )

    assert resp.status_code == HTTP_204_NO_CONTENT
    # The overflow integer must have been normalized to string at the input boundary
    assert captured_data["body"]["overflow"] == "18446744073709551616"
    # Safe integers must remain as integers
    assert captured_data["body"]["safe"] == 42


@pytest.mark.django_db
def test_http_trigger_normalizes_nested_overflow_integers(api_client, data_fixture):
    """
    Verify that deeply nested overflow integers in the request body
    are normalized throughout the structure.
    """

    node = data_fixture.create_http_trigger_node()
    url = get_url(node.service.uid) + "?test=true"

    captured_data = {}
    original_process = None

    def capture_request_data(self_svc, webhook_uid, request_data, simulate):
        captured_data.update(request_data)
        return original_process(webhook_uid, request_data, simulate)

    from baserow.core.services.registries import service_type_registry

    service_type = service_type_registry.get("http_trigger")
    original_process = service_type.process_webhook_request

    with patch.object(
        type(service_type),
        "process_webhook_request",
        side_effect=capture_request_data,
        autospec=True,
    ):
        resp = api_client.post(
            url,
            data=json.dumps(
                {
                    "level1": {
                        "big": 18446744073709551616,
                        "items": [1, 18446744073709551616],
                    }
                }
            ),
            content_type="application/json",
        )

    assert resp.status_code == HTTP_204_NO_CONTENT
    body = captured_data["body"]
    assert body["level1"]["big"] == "18446744073709551616"
    assert body["level1"]["items"][0] == 1
    assert body["level1"]["items"][1] == "18446744073709551616"


@pytest.mark.django_db
def test_http_trigger_safe_integers_unaffected(api_client, data_fixture):
    """
    Verify that payloads containing only safe integers pass through
    normalization without any changes.
    """

    node = data_fixture.create_http_trigger_node()
    url = get_url(node.service.uid) + "?test=true"

    captured_data = {}
    original_process = None

    def capture_request_data(self_svc, webhook_uid, request_data, simulate):
        captured_data.update(request_data)
        return original_process(webhook_uid, request_data, simulate)

    from baserow.core.services.registries import service_type_registry

    service_type = service_type_registry.get("http_trigger")
    original_process = service_type.process_webhook_request

    with patch.object(
        type(service_type),
        "process_webhook_request",
        side_effect=capture_request_data,
        autospec=True,
    ):
        resp = api_client.post(
            url,
            data=json.dumps(
                {"integer": 42, "negative": -100, "float": 3.14, "string": "hello"}
            ),
            content_type="application/json",
        )

    assert resp.status_code == HTTP_204_NO_CONTENT
    body = captured_data["body"]
    assert body["integer"] == 42
    assert isinstance(body["integer"], int)
    assert body["negative"] == -100
    assert isinstance(body["negative"], int)
    assert body["float"] == 3.14
    assert body["string"] == "hello"
