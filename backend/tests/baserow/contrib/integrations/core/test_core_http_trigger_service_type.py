from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from baserow.contrib.integrations.core.exceptions import (
    CoreHTTPTriggerServiceDoesNotExist,
    CoreHTTPTriggerServiceMethodNotAllowed,
)
from baserow.contrib.integrations.core.service_types import CoreHTTPTriggerServiceType
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.pytest_conftest import fake_import_formula


@pytest.mark.django_db
def test_generate_schema(data_fixture):
    trigger_node = data_fixture.create_http_trigger_node(
        service_kwargs={"is_public": True},
    )
    service = trigger_node.service
    service.sample_data = {
        "data": {
            "body": {"foo": "bar"},
            "method": "GET",
            "headers": {
                "Host": "localhost:8000",
                "User-Agent": "PostmanRuntime/7.48.0",
                "X-Custom-Header": "baz",
            },
            "raw_body": '{"foo": "bar"}',
            "user_agent": "PostmanRuntime/7.48.0",
            "remote_addr": "172.24.0.1",
            "query_params": {"test": "true"},
        },
        "status": 200,
        "output_uid": "",
    }
    service.save()

    json_schema = "http://json-schema.org/schema#"
    assert CoreHTTPTriggerServiceType().generate_schema(service) == {
        "properties": {
            "body": {
                "$schema": json_schema,
                "properties": {"foo": {"type": "string"}},
                "required": ["foo"],
                "title": "Body",
                "type": "object",
            },
            "headers": {
                "$schema": json_schema,
                "properties": {
                    "Host": {"type": "string"},
                    "User-Agent": {"type": "string"},
                    "X-Custom-Header": {"type": "string"},
                },
                "required": [
                    "Host",
                    "User-Agent",
                    "X-Custom-Header",
                ],
                "title": "Headers",
                "type": "object",
            },
            "query_params": {
                "$schema": json_schema,
                "properties": {"test": {"type": "string"}},
                "required": ["test"],
                "title": "Query parameters",
                "type": "object",
            },
            "raw_body": {
                "title": "Raw body",
                "type": "string",
            },
        },
        "title": f"Service{service.id}Schema",
        "type": "object",
    }


@pytest.mark.django_db
def test_process_webhook_request_raises_if_invalid_service(data_fixture):
    invalid_uid = uuid4()
    with pytest.raises(CoreHTTPTriggerServiceDoesNotExist) as e:
        CoreHTTPTriggerServiceType().process_webhook_request(invalid_uid, {}, True)

    assert str(e.value) == f"The webhook service {invalid_uid} does not exist."


@pytest.mark.django_db
def test_process_webhook_request_raises_if_exclude_get(data_fixture):
    trigger_node = data_fixture.create_http_trigger_node(
        service_kwargs={"is_public": True, "exclude_get": True},
    )
    service = trigger_node.service

    with pytest.raises(CoreHTTPTriggerServiceMethodNotAllowed) as e:
        CoreHTTPTriggerServiceType().process_webhook_request(
            service.uid, {"method": "GET"}, False
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_public,simulate",
    [
        (True, True),
        (False, False),
    ],
)
def test_process_webhook_request_raises_if_missing_service(
    data_fixture, is_public, simulate
):
    trigger_node = data_fixture.create_http_trigger_node(
        service_kwargs={"is_public": is_public},
    )
    service = trigger_node.service

    service_type = CoreHTTPTriggerServiceType()

    with pytest.raises(CoreHTTPTriggerServiceDoesNotExist):
        service_type.process_webhook_request(service.uid, {"method": "GET"}, simulate)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_public,simulate",
    [
        (True, False),
        (False, True),
    ],
)
def test_process_webhook_request_calls_on_event(data_fixture, is_public, simulate):
    trigger_node = data_fixture.create_http_trigger_node(
        service_kwargs={"is_public": is_public},
    )
    service = trigger_node.service

    service_type = CoreHTTPTriggerServiceType()
    service_type.on_event = MagicMock()

    service_type.process_webhook_request(service.uid, {"method": "GET"}, simulate)

    service_type.on_event.assert_called_once_with(
        [service],
        {"method": "GET"},
    )


@pytest.mark.django_db
def test_process_webhook_request_normalizes_msgpack_unsafe_payload(data_fixture):
    trigger_node = data_fixture.create_http_trigger_node(service_kwargs={"is_public": True})
    service = trigger_node.service

    service_type = CoreHTTPTriggerServiceType()
    service_type.on_event = MagicMock()

    request_data = {
        "method": "POST",
        "body": {"overflow": 18446744073709551616},
    }

    service_type.process_webhook_request(service.uid, request_data, simulate=False)

    service_type.on_event.assert_called_once_with(
        [service],
        {
            "method": "POST",
            "body": {"overflow": "18446744073709551616"},
        },
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_publishing",
    [True, False],
)
def test_import_serialized_sets_is_public(data_fixture, is_publishing):
    trigger_node = data_fixture.create_http_trigger_node()
    service = trigger_node.service

    service_type = CoreHTTPTriggerServiceType()

    serialized_service = service_type.export_serialized(service)
    assert serialized_service["is_public"] is False

    import_export_config = ImportExportConfig(
        include_permission_data=True,
        reduce_disk_space_usage=False,
        exclude_sensitive_data=False,
        is_publishing=is_publishing,
    )
    instance = service_type.import_serialized(
        None,
        serialized_service,
        {},
        import_export_config,
        import_formula=fake_import_formula,
    )

    assert instance.is_public is is_publishing


@pytest.mark.django_db
def test_export_prepared_values_casts_uid_to_str(data_fixture):
    trigger_node = data_fixture.create_http_trigger_node()
    service = trigger_node.service

    assert isinstance(service.uid, UUID)

    values = CoreHTTPTriggerServiceType().export_prepared_values(service)

    assert values["uid"] == str(service.uid)


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
def test_http_trigger_handles_integer_overflow_in_payload(api_client, data_fixture):
    """
    Regression test for issue #4309: HTTP trigger with integer overflow.
    
    Test that HTTP trigger can handle payloads containing integers that exceed
    msgpack's serialization limits without raising OverflowError.
    
    WITHOUT THE FIX, this test would FAIL with:
    OverflowError: Python int too large to convert to C unsigned long
    
    The error would occur in the celery task broadcast_to_permitted_users when
    trying to serialize the websocket message with msgpack:
    
    Traceback (most recent call last):
      File "msgpack/_packer.pyx", line 171, in msgpack._cmsgpack.Packer._pack_inner
    OverflowError: Python int too large to convert to C unsigned long
    
    During handling of the above exception, another exception occurred:
    
    Traceback (most recent call last):
      File "/baserow/backend/src/baserow/ws/tasks.py", line 162, in broadcast_to_permitted_users
        broadcast_to_users(user_ids, payload, ignore_web_socket_id=ignore_web_socket_id)
      ...
      File "msgpack/_packer.pyx", line 180, in msgpack._cmsgpack.Packer._pack_inner
    OverflowError: Integer value out of range
    
    WITH THE FIX, the out-of-range integers are converted to strings before
    msgpack serialization, preventing the OverflowError.
    """
    from rest_framework.status import HTTP_204_NO_CONTENT
    from django.urls import reverse
    
    from baserow.contrib.automation.workflows.models import WorkflowState
    
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        automation=automation,
        state=WorkflowState.LIVE,
        create_trigger=False,
    )
    
    trigger_node = data_fixture.create_http_trigger_node(
        workflow=workflow,
        service_kwargs={"is_public": True},
    )
    
    url = reverse("api:http_trigger", kwargs={"webhook_uid": trigger_node.service.uid})
    
    # Test payload with various overflow scenarios that would cause OverflowError
    # without the normalization fix
    payload = {
        "overflow_unsigned_64bit": 18446744073709551616,  # 2^64 (exact value from bug report #4309)
        "overflow_large": 2**100,  # Very large positive integer
        "underflow_signed_64bit": -(2**63) - 1,  # Below min signed 64-bit
        "underflow_large": -(2**100),  # Very large negative integer
        "nested": {
            "overflow": 2**65,
            "normal": 42,
            "list_with_overflow": [1, 2**64, 3],
        },
        "normal_values": {
            "int": 123,
            "string": "test",
            "bool": True,
            "null": None,
        },
    }
    
    # WITHOUT THE FIX: This would raise OverflowError during websocket broadcast
    # WITH THE FIX: This succeeds because integers are normalized before msgpack serialization
    resp = api_client.post(url, payload, format="json")
    
    # The request should succeed (no OverflowError)
    assert resp.status_code == HTTP_204_NO_CONTENT
    
    # If we got here without an OverflowError, the fix is working correctly.
    # The workflow was triggered and the broadcast succeeded with normalized integers.
