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
