from copy import deepcopy
from io import BytesIO

import pytest
from genson import SchemaBuilder

from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.utils import sanitize_sample_data

SAMPLE = {
    "data": {
        "body": {
            "people": [
                {"name": "Alice", "age": 42, "score": 1.5, "active": True},
                {"name": "Bob", "age": None, "tags": ["private", 7, False]},
            ],
            "empty_object": {},
            "empty_list": [],
        },
        "headers": {"authorization": "Bearer secret"},
    },
    "status": 201,
    "output_uid": "private-id",
}
CLEAN_SAMPLE = {
    "data": {
        "body": {
            "people": [
                {"name": "Example", "age": 0, "score": 0.0, "active": False},
                {"name": "Example", "age": None, "tags": ["Example", 0, False]},
            ],
            "empty_object": {},
            "empty_list": [],
        },
        "headers": {"authorization": "Example"},
    },
    "status": 0,
    "output_uid": "Example",
}


def test_sanitize_sample_data_preserves_shape_without_mutating_input():
    original = deepcopy(SAMPLE)
    sanitized = sanitize_sample_data(original)

    assert sanitized == CLEAN_SAMPLE
    assert original == SAMPLE
    original_schema, sanitized_schema = SchemaBuilder(), SchemaBuilder()
    original_schema.add_object(original)
    sanitized_schema.add_object(sanitized)
    assert original_schema.to_schema() == sanitized_schema.to_schema()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "sample", [SAMPLE, {"_error": "Private URL and credentials"}, None]
)
@pytest.mark.parametrize("is_user_template", [True, False])
def test_service_export_sanitizes_only_user_templates(
    data_fixture, sample, is_user_template
):
    """Templates discard captured values/errors without changing live samples."""

    service = data_fixture.create_core_http_request_service(
        sample_data=deepcopy(sample)
    )
    service_type = service.get_type()
    original_schema = service_type.generate_schema(service)
    exported = ServiceHandler().export_service(
        service,
        ImportExportConfig(
            include_permission_data=False,
            is_user_template=is_user_template,
            exclude_sensitive_data=False,
        ),
    )
    expected = CLEAN_SAMPLE if sample == SAMPLE else None
    assert exported["sample_data"] == (expected if is_user_template else sample)
    service.refresh_from_db()
    assert service.sample_data == sample
    if sample == SAMPLE:
        service.sample_data = exported["sample_data"]
        assert service_type.generate_schema(service) == original_schema


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["builder", "automation", "dashboard"])
@pytest.mark.parametrize("is_user_template", [True, False])
def test_application_exports_sanitize_service_samples(
    data_fixture, surface, is_user_template
):
    """All application export paths forward template config to shared services."""

    user = data_fixture.create_user()
    service = data_fixture.create_core_http_request_service(
        integration=None, sample_data=deepcopy(SAMPLE)
    )
    if surface == "builder":
        page = data_fixture.create_builder_page(user=user)
        data_fixture.create_builder_data_source(page=page, service=service)
        application = page.builder
        path = ["data_sources", 0, "service"]
    elif surface == "automation":
        workflow = data_fixture.create_automation_workflow(
            user=user, create_trigger=False
        )
        data_fixture.create_automation_node(
            workflow=workflow, type="http_request", service=service
        )
        application = workflow.automation
        path = ["workflows", 0, "nodes", 0, "service"]
    else:
        source = data_fixture.create_dashboard_data_source(user=user, service=service)
        application = source.dashboard
        path = ["data_sources", 0, "service"]

    exported = CoreHandler().export_workspace_applications(
        application.workspace,
        BytesIO(),
        ImportExportConfig(
            include_permission_data=False, is_user_template=is_user_template
        ),
    )[0]
    if surface == "builder":
        exported = next(item for item in exported["pages"] if item["id"] == page.id)
    for key in path:
        exported = exported[key]
    assert exported["sample_data"] == (CLEAN_SAMPLE if is_user_template else SAMPLE)
    service.refresh_from_db()
    assert service.sample_data == SAMPLE
