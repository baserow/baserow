from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
import responses
from pytest_unordered import unordered
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.webhooks.models import TableWebhook, TableWebhookEvent
from baserow.core.utils import truncate_middle


@pytest.mark.django_db
def test_list_webhooks(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    user_2, jwt_token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    webhook_1 = data_fixture.create_table_webhook(
        table=table, headers={"Baserow-add-1": "Value 1"}
    )
    call_1 = data_fixture.create_table_webhook_call(webhook=webhook_1)
    webhook_2 = data_fixture.create_table_webhook(
        table=table, include_all_events=False, events=["rows.created"]
    )
    data_fixture.create_table_webhook()

    response = api_client.get(
        reverse("api:database:webhooks:list", kwargs={"table_id": 0}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2
    assert response_json[0]["id"] == webhook_1.id
    assert response_json[0]["use_user_field_names"] == webhook_1.use_user_field_names
    assert response_json[0]["url"] == webhook_1.url
    assert response_json[0]["request_method"] == webhook_1.request_method
    assert response_json[0]["name"] == webhook_1.name
    assert response_json[0]["include_all_events"] == webhook_1.include_all_events
    assert response_json[0]["failed_triggers"] == 0
    assert response_json[0]["events"] == []
    assert response_json[0]["headers"] == {"Baserow-add-1": "Value 1"}
    assert response_json[0]["active"] is True
    del response_json[0]["calls"][0]["called_time"]
    assert response_json[0]["calls"][0] == {
        "id": call_1.id,
        "event_id": str(call_1.event_id),
        "event_type": call_1.event_type,
        "called_url": call_1.called_url,
        "request": call_1.request,
        "response": call_1.response,
        "response_status": call_1.response_status,
        "error": None,
    }

    assert response_json[1]["id"] == webhook_2.id
    assert response_json[1]["events"] == ["rows.created"]


@pytest.mark.django_db
def test_list_webhooks_truncated_calls(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    webhook_1 = data_fixture.create_table_webhook(
        table=table, headers={"Baserow-add-1": "Value 1"}
    )
    call_1 = data_fixture.create_table_webhook_call(
        webhook=webhook_1, request="s" * 100010, response="s" * 100010
    )

    response = api_client.get(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json[0]["calls"][0]["request"] == truncate_middle(
        "s" * 100010, 100000, "\n...(truncated)\n"
    )
    assert response_json[0]["calls"][0]["response"] == truncate_middle(
        "s" * 100010, 100000, "\n...(truncated)\n"
    )


@pytest.mark.django_db
def test_list_webhooks_empty_request_and_response(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    webhook_1 = data_fixture.create_table_webhook(
        table=table, headers={"Baserow-add-1": "Value 1"}
    )
    call_1 = data_fixture.create_table_webhook_call(
        webhook=webhook_1, request=None, response=None
    )

    response = api_client.get(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json[0]["calls"][0]["request"] == ""
    assert response_json[0]["calls"][0]["response"] == ""


@pytest.mark.django_db
def test_create_webhooks(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    user_2, jwt_token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": 0}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook",
            "include_all_events": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook",
            "include_all_events": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook",
            "include_all_events": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["use_user_field_names"] is True
    assert response_json["url"] == "https://mydomain.com/endpoint"
    assert response_json["request_method"] == "POST"
    assert response_json["name"] == "My Webhook"
    assert response_json["include_all_events"] is True
    assert response_json["failed_triggers"] == 0
    assert response_json["events"] == []
    assert response_json["headers"] == {}
    assert response_json["calls"] == []
    assert TableWebhook.objects.all().count() == 1

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook 2",
            "include_all_events": False,
            "events": ["rows.created"],
            "headers": {"Baserow-add-1": "Value 1"},
            "request_method": "PATCH",
            "use_user_field_names": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["use_user_field_names"] is False
    assert response_json["url"] == "https://mydomain.com/endpoint"
    assert response_json["request_method"] == "PATCH"
    assert response_json["name"] == "My Webhook 2"
    assert response_json["include_all_events"] is False
    assert response_json["failed_triggers"] == 0
    assert response_json["events"] == ["rows.created"]
    assert response_json["headers"] == {"Baserow-add-1": "Value 1"}
    assert response_json["calls"] == []
    assert TableWebhook.objects.all().count() == 2

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook 2",
            "events": ["rows.created"],
            "headers": {"Test:": "Value 1"},
            "request_method": "PATCH",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["headers"][0]["code"] == "invalid_http_header_name"

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook 2",
            "events": ["INVALID"],
            "request_method": "PATCH",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["events"]["0"][0]["code"] == "invalid_choice"

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://mydomain.com:8a/endpoint",
            "name": "My Webhook 2",
            "events": ["rows.created"],
            "request_method": "PATCH",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["url"][0]["code"] == "invalid_url"

    # Testing too long URL
    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://md.com/" + (2001 - len("https://md.com/")) * "a",
            "name": "My Webhook 2",
            "events": ["rows.created"],
            "request_method": "PATCH",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["url"][0]["code"] == "max_length"


@pytest.mark.django_db
def test_create_webhook_with_event_config(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    field_3 = data_fixture.create_text_field(table=table)

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook",
            "include_all_events": False,
            "events": ["rows.updated"],
            "event_config": [
                {"event_type": "rows.updated", "fields": [field_1.id, field_2.id]},
                # Will be omitted from the response because it's not included in the
                # `events` property.
                {"event_type": "rows.deleted", "fields": [field_2.id, field_3.id]},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["use_user_field_names"] is True
    assert response_json["url"] == "https://mydomain.com/endpoint"
    assert response_json["request_method"] == "POST"
    assert response_json["name"] == "My Webhook"
    assert response_json["include_all_events"] is False
    assert response_json["failed_triggers"] == 0
    assert response_json["events"] == ["rows.updated"]
    assert response_json["event_config"] == [
        {"event_type": "rows.updated", "fields": unordered([field_1.id, field_2.id])}
    ]
    assert response_json["headers"] == {}
    assert response_json["calls"] == []

    events = list(TableWebhookEvent.objects.all())
    assert len(events) == 1
    event_fields = list(events[0].fields.all().order_by("id"))
    assert event_fields[0].id == field_1.id
    assert event_fields[1].id == field_2.id


@pytest.mark.django_db
def test_create_webhook_with_event_config_unrelated_fields(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field_3 = data_fixture.create_text_field()

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook",
            "include_all_events": False,
            "events": ["rows.updated"],
            "event_config": [
                {"event_type": "rows.updated", "fields": [field_3.id]},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response_json["error"] == "ERROR_TABLE_WEBHOOK_EVENT_CONFIG_FIELD_NOT_IN_TABLE"
    )


@pytest.mark.django_db
def test_get_webhook(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    user_2, jwt_token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    webhook = data_fixture.create_table_webhook(table=table)

    response = api_client.get(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": 0}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_WEBHOOK_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == webhook.id
    assert response_json["use_user_field_names"] == webhook.use_user_field_names
    assert response_json["url"] == webhook.url
    assert response_json["request_method"] == webhook.request_method
    assert response_json["name"] == webhook.name
    assert response_json["include_all_events"] == webhook.include_all_events
    assert response_json["failed_triggers"] == 0
    assert response_json["events"] == []
    assert response_json["headers"] == {}
    assert response_json["calls"] == []


@pytest.mark.django_db
def test_update_webhook(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    user_2, jwt_token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    webhook = data_fixture.create_table_webhook(table=table)

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": 0}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_WEBHOOK_DOES_NOT_EXIST"

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == webhook.id
    assert response_json["use_user_field_names"] == webhook.use_user_field_names
    assert response_json["url"] == webhook.url
    assert response_json["request_method"] == webhook.request_method
    assert response_json["name"] == webhook.name
    assert response_json["include_all_events"] == webhook.include_all_events
    assert response_json["failed_triggers"] == 0
    assert response_json["events"] == []
    assert response_json["event_config"] == []
    assert response_json["headers"] == {}
    assert response_json["calls"] == []

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook 2",
            "include_all_events": False,
            "events": ["rows.created"],
            "headers": {"Baserow-add-1": "Value 1"},
            "request_method": "PATCH",
            "use_user_field_names": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == webhook.id
    assert response_json["use_user_field_names"] is False
    assert response_json["url"] == "https://mydomain.com/endpoint"
    assert response_json["request_method"] == "PATCH"
    assert response_json["name"] == "My Webhook 2"
    assert response_json["include_all_events"] is False
    assert response_json["failed_triggers"] == 0
    assert response_json["events"] == ["rows.created"]
    assert response_json["event_config"] == [{"event_type": "rows.created"}]
    assert response_json["headers"] == {"Baserow-add-1": "Value 1"}
    assert response_json["calls"] == []

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        {
            "events": ["INVALUID"],
            "headers": {"Test:": "Value 1"},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["headers"][0]["code"] == "invalid_http_header_name"
    assert response_json["detail"]["events"]["0"][0]["code"] == "invalid_choice"


@pytest.mark.django_db
def test_update_webhook_with_event_config(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    webhook = data_fixture.create_table_webhook(table=table)
    field_1 = data_fixture.create_text_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    field_3 = data_fixture.create_text_field(table=table)

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        {
            "url": "https://mydomain.com/endpoint",
            "name": "My Webhook 2",
            "include_all_events": False,
            "events": ["rows.updated"],
            "event_config": [
                {"event_type": "rows.updated", "fields": [field_1.id, field_2.id]}
            ],
            "request_method": "PATCH",
            "use_user_field_names": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == webhook.id
    assert response_json["events"] == ["rows.updated"]
    assert response_json["event_config"] == [
        {"event_type": "rows.updated", "fields": unordered([field_1.id, field_2.id])}
    ]

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        {
            "events": ["rows.updated", "rows.deleted"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["events"] == ["rows.updated", "rows.deleted"]
    assert response_json["event_config"] == [
        {"event_type": "rows.updated", "fields": unordered([field_1.id, field_2.id])},
        {"event_type": "rows.deleted"},
    ]

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        {
            "events": ["rows.deleted"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["events"] == ["rows.deleted"]
    assert response_json["event_config"] == [
        {"event_type": "rows.deleted"},
    ]

    response = api_client.patch(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["events"] == ["rows.deleted"]
    assert response_json["event_config"] == [
        {"event_type": "rows.deleted"},
    ]


@pytest.mark.django_db
def test_delete_webhook(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    user_2, jwt_token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    webhook = data_fixture.create_table_webhook(table=table)

    response = api_client.delete(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": 0}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_WEBHOOK_DOES_NOT_EXIST"

    response = api_client.delete(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.delete(
        reverse("api:database:webhooks:item", kwargs={"webhook_id": webhook.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert TableWebhook.objects.all().count() == 0


@pytest.mark.django_db
@responses.activate
@override_settings(DEBUG=True)
def test_trigger_test_call(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    user_2, jwt_token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    responses.add(responses.POST, "http://baserow.io", json={}, status=200)

    response = api_client.post(
        reverse("api:database:webhooks:test", kwargs={"table_id": 0}),
        {
            "url": "http://baserow.io",
            "event_type": "rows.created",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:webhooks:test", kwargs={"table_id": table.id}),
        {
            "url": "http://baserow.io",
            "event_type": "rows.created",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse("api:database:webhooks:test", kwargs={"table_id": table.id}),
        {
            "url": "http://baserow.io",
            "event_type": "rows.created",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["request"]) > 1
    assert response_json["response"] == "Content-Type: application/json\r\n\r\n{}"
    assert response_json["status_code"] == 200
    assert response_json["is_unreachable"] is False

    response = api_client.post(
        reverse("api:database:webhooks:test", kwargs={"table_id": table.id}),
        {
            "url": "http://baserow.io/invalid",
            "event_type": "rows.created",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert len(response_json["request"]) > 1
    assert response_json["response"] == ""
    assert response_json["status_code"] is None
    assert response_json["is_unreachable"] is True


@pytest.mark.django_db
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS=True,
)
def test_can_query_private_http_addresses_when_env_var_on(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    user_2, jwt_token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    url = "http://internal"
    responses.add(responses.POST, url, json={}, status=200)

    response = api_client.post(
        reverse("api:database:webhooks:test", kwargs={"table_id": table.id}),
        {
            "url": url,
            "event_type": "rows.created",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["request"]) > 1
    assert response_json["is_unreachable"] is False

    response = api_client.post(
        reverse("api:database:webhooks:list", kwargs={"table_id": table.id}),
        {
            "url": url,
            "name": "My Webhook 2",
            "include_all_events": False,
            "events": ["rows.created"],
            "headers": {"Baserow-add-1": "Value 1"},
            "request_method": "PATCH",
            "use_user_field_names": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    response = api_client.patch(
        reverse(
            "api:database:webhooks:item", kwargs={"webhook_id": response_json["id"]}
        ),
        {"url": url},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK, response_json
