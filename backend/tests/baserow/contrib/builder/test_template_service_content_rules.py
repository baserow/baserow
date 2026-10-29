from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
from threading import Barrier

from django.db import connections, transaction

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    EventTypes,
)
from baserow.contrib.integrations.core.service_types import CoreHTTPRequestServiceType
from baserow.core.handler import CoreHandler
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.management.commands.export_workspace_applications import (
    cli_import_export_config,
)
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.utils import Progress
from tests.baserow.core.user_templates.utils import start_job, update_content

SAMPLE = {"data": {"body": {"name": "Alice", "active": True, "amount": 12.5}}}
CLEAN_SAMPLE = {"data": {"body": {"name": "Example", "active": False, "amount": 0.0}}}


@pytest.fixture
def app_with_captured_http_services(data_fixture):
    """Create a data source and action with credentials and captured private values."""

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user, name="Request page")
    button = data_fixture.create_builder_button_element(page=page, value="'Send'")
    services = [
        data_fixture.create_core_http_request_service(
            integration=None,
            url="'https://example.com/request'",
            http_method="POST",
            body_type="raw",
            body_content="'private-body'",
            timeout=42,
            sample_data=deepcopy(SAMPLE),
        )
        for _ in range(2)
    ]
    for service in services:
        service.headers.create(key="Authorization", value="'private-header'")
        service.query_params.create(key="api_key", value="'private-query'")
        service.form_data.create(key="token", value="'private-form'")
    data_fixture.create_builder_data_source(
        page=page, service=services[0], name="Response"
    )
    data_fixture.create_core_http_request_workflow_action(
        page=page, element=button, event=EventTypes.CLICK, service=services[1]
    )
    return user, page.builder


def assert_copied_service_content(builder, *, sanitized, redacted=None):
    """Check retained app structure, request settings and samples after a real copy."""

    if redacted is None:
        redacted = sanitized
    page = builder.page_set.get(name="Request page")
    button = page.element_set.get().specific
    assert button.value["formula"] == "'Send'"
    source = DataSource.objects.get(page=page)
    action = CoreHTTPRequestWorkflowAction.objects.get(page=page)
    assert source.name == "Response"
    assert action.element_id == button.id
    assert action.event == EventTypes.CLICK
    for service in [source.service.specific, action.service.specific]:
        assert service.sample_data == (CLEAN_SAMPLE if sanitized else SAMPLE)
        assert service.url["formula"] == "'https://example.com/request'"
        assert service.http_method == "POST"
        assert service.timeout == 42
        assert service.body_type == "raw"
        assert service.body_content["formula"] == ("" if redacted else "'private-body'")
        for relation, key, secret in [
            ("headers", "Authorization", "'private-header'"),
            ("query_params", "api_key", "'private-query'"),
            ("form_data", "token", "'private-form'"),
        ]:
            row = getattr(service, relation).get()
            assert row.key == key
            assert row.value["formula"] == ("" if redacted else secret)
        schema = service.get_type().generate_schema(service)
        assert schema["properties"]["body"]["properties"] == {
            "name": {"type": "string"},
            "active": {"type": "boolean"},
            "amount": {"type": "number"},
        }


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("update", [False, True])
def test_template_creation_update_and_install_sanitize_http_services(
    data_fixture, use_tmp_media_root, app_with_captured_http_services, update
):
    """Private values disappear from template and install without changing the source."""

    user, builder = app_with_captured_http_services
    job = start_job(user, builder.workspace, [builder])
    assert job.state == JOB_FINISHED, job.error
    handler = UserTemplateHandler()
    revision = job.template
    if update:
        job = update_content(user, revision, builder.workspace, [builder])
        assert job.state == JOB_FINISHED, job.error
        revision = handler.get_latest_revision(revision)
    template_builder = revision.workspace.application_set.get().specific
    assert_copied_service_content(template_builder, sanitized=True)
    content = handler.serialize_template_content(revision)
    assert "private-" not in str(content)
    assert "Alice" not in str(content)
    installer = data_fixture.create_user()
    target = data_fixture.create_workspace(user=installer)
    with transaction.atomic():
        installed = handler.install_template_content(
            installer, target, revision, content
        )
    assert_copied_service_content(installed[0].specific, sanitized=True)
    assert_copied_service_content(builder, sanitized=False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operation",
    [
        "duplicate",
        "workspace_copy",
        "workspace_export",
        "snapshot",
        "official_template",
    ],
)
def test_non_user_template_copies_preserve_http_services(
    data_fixture, app_with_captured_http_services, operation
):
    """Application copies, workspace roundtrips, snapshots and official installs retain samples."""

    user, builder = app_with_captured_http_services
    handler = CoreHandler()
    if operation == "duplicate":
        copied = handler.duplicate_application(user, builder)
    elif operation == "snapshot":
        snapshots = SnapshotHandler()
        snapshot = snapshots.create(builder.id, user, "Captured responses")
        snapshots.perform_create(snapshot, Progress(total=100))
        snapshot.refresh_from_db()
        copied = snapshots.perform_restore(snapshot, Progress(total=100))
    else:
        config = (
            cli_import_export_config
            if operation in ["workspace_export", "official_template"]
            else ImportExportConfig(
                include_permission_data=False,
                exclude_sensitive_data=False,
                is_duplicate=True,
            )
        )
        exported = handler.export_workspace_applications(
            builder.workspace, BytesIO(), config
        )
        if operation == "official_template":
            config = ImportExportConfig(
                include_permission_data=False,
                exclude_sensitive_data=False,
                is_template=True,
                is_duplicate=True,
            )
        copied_apps, _ = handler.import_applications_to_workspace(
            data_fixture.create_workspace(user=user), exported, BytesIO(), config
        )
        copied = copied_apps[0].specific
    assert_copied_service_content(
        copied.specific,
        sanitized=False,
        redacted=operation in ["workspace_export", "official_template"],
    )
    assert_copied_service_content(builder, sanitized=False)


@pytest.mark.django_db(transaction=True)
def test_template_and_ordinary_exports_are_isolated_when_overlapping(
    app_with_captured_http_services, monkeypatch
):
    """Pause both real exports on each sample to expose shared mutations deterministically."""

    user, builder = app_with_captured_http_services
    barrier = Barrier(2, timeout=15)
    serialize_property = CoreHTTPRequestServiceType.serialize_property

    def serialize_together(self, instance, prop_name, **kwargs):
        value = serialize_property(self, instance, prop_name, **kwargs)
        if prop_name == "sample_data":
            barrier.wait()
        return value

    monkeypatch.setattr(
        CoreHTTPRequestServiceType, "serialize_property", serialize_together
    )

    def export(is_template):
        """Export with one config on a connection owned by this worker thread."""

        try:
            return CoreHandler().export_workspace_applications(
                builder.workspace,
                BytesIO(),
                ImportExportConfig(
                    include_permission_data=False,
                    is_user_template=is_template,
                    exclude_sensitive_data=is_template,
                ),
            )[0]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        template = executor.submit(export, True)
        ordinary = executor.submit(export, False)
        template, ordinary = template.result(timeout=30), ordinary.result(timeout=30)
    for exported, sanitized in [(template, True), (ordinary, False)]:
        page = next(
            page for page in exported["pages"] if page["name"] == "Request page"
        )
        for service in [
            page["data_sources"][0]["service"],
            page["workflow_actions"][0]["service"],
        ]:
            assert service["sample_data"] == (CLEAN_SAMPLE if sanitized else SAMPLE)
            value = service["headers"][0]["value"]
            if sanitized:
                assert value is None
            else:
                assert value["formula"] == "'private-header'"
    assert_copied_service_content(builder, sanitized=False)
