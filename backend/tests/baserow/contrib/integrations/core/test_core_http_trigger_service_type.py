from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

from django.test import override_settings

import pytest

from baserow.contrib.integrations.core.exceptions import (
    CoreHTTPTriggerServiceDoesNotExist,
    CoreHTTPTriggerServiceMethodNotAllowed,
)
from baserow.contrib.integrations.core.models import CoreHTTPTriggerService
from baserow.contrib.integrations.core.service_types import CoreHTTPTriggerServiceType
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.pytest_conftest import fake_import_formula


@override_settings(AUTOMATION_WORKFLOW_RESPONSE_TIMEOUT_MAX_SECONDS=42)
def test_response_timeout_serializer_uses_configured_maximum():
    field = CoreHTTPTriggerServiceType().serializer_field_overrides[
        "response_timeout_seconds"
    ]

    assert field.default == 10
    assert field.max_value == 42


@pytest.mark.django_db
def test_generate_schema(data_fixture):
    trigger_node = data_fixture.create_core_http_trigger_node(
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
        "destination_service_id": None,
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
    trigger_node = data_fixture.create_core_http_trigger_node(
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
    trigger_node = data_fixture.create_core_http_trigger_node(
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
    trigger_node = data_fixture.create_core_http_trigger_node(
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
    trigger_node = data_fixture.create_core_http_trigger_node()
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
    if is_publishing:
        # Publishing must keep the same uid so the published URL keeps working.
        assert str(instance.uid) == str(service.uid)
    else:
        # Any other import is a new trigger and gets its own URL.
        assert str(instance.uid) != str(service.uid)


@pytest.mark.django_db
@pytest.mark.parametrize("is_duplicate", [True, False])
def test_import_serialized_regenerates_uid_unless_publishing(
    data_fixture, is_duplicate
):
    trigger_node = data_fixture.create_core_http_trigger_node()
    service = trigger_node.service

    service_type = CoreHTTPTriggerServiceType()
    serialized_service = service_type.export_serialized(service)

    import_export_config = ImportExportConfig(
        include_permission_data=True,
        reduce_disk_space_usage=False,
        exclude_sensitive_data=False,
        is_duplicate=is_duplicate,
    )
    instance = service_type.import_serialized(
        None,
        serialized_service,
        {},
        import_export_config,
        import_formula=fake_import_formula,
    )

    assert str(instance.uid) != str(service.uid)


@pytest.mark.django_db
def test_imported_application_trigger_has_its_own_url(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        automation=automation,
        trigger_type=CoreHTTPTriggerServiceType.type,
    )
    service = CoreHTTPTriggerService.objects.get(
        automation_workflow_node__workflow=workflow
    )

    config = ImportExportConfig(include_permission_data=False)
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    core_handler.import_applications_to_workspace(
        workspace, exported, BytesIO(), config, None
    )

    imported_service = CoreHTTPTriggerService.objects.exclude(id=service.id).get(
        automation_workflow_node__workflow__automation__workspace=workspace
    )
    assert imported_service.uid != service.uid

    service_type = CoreHTTPTriggerServiceType()
    service_type.on_event = MagicMock()
    found_service, _ = service_type.process_webhook_request(
        service.uid, {"method": "POST"}, True
    )
    assert found_service.id == service.id
