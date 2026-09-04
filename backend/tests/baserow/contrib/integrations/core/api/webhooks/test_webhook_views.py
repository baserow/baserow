import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_204_NO_CONTENT, HTTP_405_METHOD_NOT_ALLOWED

from baserow.core.services.registries import service_type_registry


def get_url(uid):
    return reverse("api:http_trigger", kwargs={"webhook_uid": uid})


def post_webhook(api_client, uid, body, content_type):
    """
    POSTs the given raw body to the webhook endpoint and returns the response
    together with the request_data that was forwarded to the trigger's
    on_event, or None if the trigger was never fired.
    """

    with patch.object(
        service_type_registry.get("http_trigger"), "on_event"
    ) as mock_on_event:
        resp = api_client.generic(
            "POST", get_url(uid) + "?test=true", data=body, content_type=content_type
        )

    request_data = mock_on_event.call_args[0][1] if mock_on_event.called else None
    return resp, request_data


@pytest.mark.parametrize(
    "http_method",
    ["head", "options", "trace"],
)
@pytest.mark.django_db
def test_rejects_disallowed_methods(api_client, data_fixture, http_method):
    node = data_fixture.create_http_trigger_node()

    url = get_url(node.service.uid)
    resp = getattr(api_client, http_method)(url)

    assert resp.status_code == HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_rejects_http_get_if_service_excludes_get(
    api_client, data_fixture, django_assert_num_queries
):
    node = data_fixture.create_http_trigger_node()
    node.service.exclude_get = True
    node.service.save()

    url = get_url(node.service.uid) + "?test=true"

    # 1 model query, 3 transaction management queries
    with django_assert_num_queries(4):
        resp = api_client.get(url)

    assert resp.status_code == HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
@pytest.mark.parametrize(
    "http_method",
    ["get", "post", "put", "patch", "delete"],
)
def test_allows_valid_http_methods(api_client, data_fixture, http_method):
    node = data_fixture.create_http_trigger_node()

    url = get_url(node.service.uid) + "?test=true"
    resp = getattr(api_client, http_method)(url)

    assert resp.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_non_utf8_json_body_triggers_with_replaced_raw_body(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    resp, request_data = post_webhook(
        api_client,
        node.service.uid,
        '{"name": "Hällo"}'.encode("iso-8859-1"),
        "application/json",
    )

    assert resp.status_code == HTTP_204_NO_CONTENT
    assert request_data["raw_body"] == '{"name": "H�llo"}'
    assert request_data["body"] == {}


@pytest.mark.django_db
def test_declared_charset_is_used_to_decode_the_body(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    resp, request_data = post_webhook(
        api_client,
        node.service.uid,
        "Hällo".encode("iso-8859-1"),
        "text/plain; charset=iso-8859-1",
    )

    assert resp.status_code == HTTP_204_NO_CONTENT
    assert request_data["raw_body"] == "Hällo"
    assert request_data["body"] == {}


@pytest.mark.django_db
def test_invalid_declared_charset_falls_back_to_utf8(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    resp, request_data = post_webhook(
        api_client,
        node.service.uid,
        "Hällo".encode("iso-8859-1"),
        "text/plain; charset=banana",
    )

    assert resp.status_code == HTTP_204_NO_CONTENT
    assert request_data["raw_body"] == "H�llo"


@pytest.mark.django_db
def test_binary_body_triggers(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    resp, request_data = post_webhook(
        api_client,
        node.service.uid,
        b"\x89PNG\r\n\x1a\n\x00\x01\x02",
        "application/octet-stream",
    )

    assert resp.status_code == HTTP_204_NO_CONTENT
    assert request_data["body"] == {}
    # The payload must survive the JSON serialization towards the
    # workflow's Celery task.
    json.dumps(request_data)


@pytest.mark.django_db
def test_plain_text_body_triggers_with_raw_body(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    resp, request_data = post_webhook(
        api_client, node.service.uid, b"hello world", "text/plain"
    )

    assert resp.status_code == HTTP_204_NO_CONTENT
    assert request_data["raw_body"] == "hello world"
    assert request_data["body"] == {}


@pytest.mark.django_db
def test_malformed_json_body_falls_back_to_empty_body(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    resp, request_data = post_webhook(
        api_client, node.service.uid, b'{"name": ', "application/json"
    )

    assert resp.status_code == HTTP_204_NO_CONTENT
    assert request_data["raw_body"] == '{"name": '
    assert request_data["body"] == {}


@pytest.mark.django_db
def test_valid_json_body_is_parsed(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    resp, request_data = post_webhook(
        api_client,
        node.service.uid,
        '{"name": "Müller"}'.encode(),
        "application/json",
    )

    assert resp.status_code == HTTP_204_NO_CONTENT
    assert request_data["body"] == {"name": "Müller"}
    assert request_data["raw_body"] == '{"name": "Müller"}'


@pytest.mark.django_db
def test_form_urlencoded_body_preserves_multi_value_fields(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    resp, request_data = post_webhook(
        api_client,
        node.service.uid,
        b"a=1&a=2&b=3",
        "application/x-www-form-urlencoded",
    )

    assert resp.status_code == HTTP_204_NO_CONTENT
    assert request_data["body"] == {"a": ["1", "2"], "b": "3"}


@pytest.mark.django_db
def test_multipart_body_keeps_only_serializable_form_fields(api_client, data_fixture):
    node = data_fixture.create_http_trigger_node()

    with patch.object(
        service_type_registry.get("http_trigger"), "on_event"
    ) as mock_on_event:
        resp = api_client.post(
            get_url(node.service.uid) + "?test=true",
            data={
                "name": "Müller",
                "attachment": SimpleUploadedFile(
                    "test.png", b"\x89PNG\r\n\x1a\n", content_type="image/png"
                ),
            },
            format="multipart",
        )

    assert resp.status_code == HTTP_204_NO_CONTENT
    request_data = mock_on_event.call_args[0][1]
    assert request_data["body"] == {"name": "Müller"}
    # The payload must survive the JSON serialization towards the
    # workflow's Celery task.
    json.dumps(request_data)
