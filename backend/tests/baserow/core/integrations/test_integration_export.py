import pytest

from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.services.handler import ServiceHandler

FILE = ImportExportConfig(include_permission_data=False)


class NestedExporter:
    @IntegrationHandler.with_referenced_integrations
    def export_serialized(
        self, application, import_export_config, service=None, nested=None, fail=False
    ):
        """Exercise nested and failing exports using the real typed service exporter."""
        serialized = {"integrations": []}
        if service is not None:
            serialized["service"] = ServiceHandler().export_service(
                service, import_export_config
            )
        if nested is not None:
            serialized["nested"] = self.export_serialized(*nested)
        if fail:
            raise ValueError("Export failed")
        return serialized


@pytest.mark.django_db
@pytest.mark.parametrize("use_local_cache", [False, True])
def test_nested_exports_keep_their_own_references(
    data_fixture, settings, use_local_cache
):
    """Dependencies exported by a child application do not leak into its parent."""
    settings.BASEROW_USE_LOCAL_CACHE = use_local_cache
    workspace = data_fixture.create_workspace()
    shared = data_fixture.create_shared_application(workspace=workspace)
    first = data_fixture.create_local_baserow_integration(application=shared)
    second = data_fixture.create_local_baserow_integration(application=shared)
    parent = data_fixture.create_builder_application(workspace=workspace)
    child = data_fixture.create_builder_application(workspace=workspace)
    first_service = data_fixture.create_local_baserow_list_rows_service(
        integration=first
    )
    second_service = data_fixture.create_local_baserow_list_rows_service(
        integration=second
    )

    exported = NestedExporter().export_serialized(
        parent, FILE, first_service, nested=(child, FILE, second_service)
    )

    assert [item["id"] for item in exported["integrations"]] == [first.id]
    assert [item["id"] for item in exported["nested"]["integrations"]] == [second.id]


@pytest.mark.django_db
@pytest.mark.parametrize("use_local_cache", [False, True])
def test_failed_and_standalone_exports_do_not_leak_references(
    data_fixture, settings, use_local_cache
):
    """A failed export or a standalone service export cannot affect the next export."""
    settings.BASEROW_USE_LOCAL_CACHE = use_local_cache
    workspace = data_fixture.create_workspace()
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=data_fixture.create_shared_application(workspace=workspace)
    )
    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration
    )
    exporter = NestedExporter()
    with pytest.raises(ValueError, match="Export failed"):
        exporter.export_serialized(application, FILE, service, fail=True)

    ServiceHandler().export_service(service, FILE)
    exported = exporter.export_serialized(application, FILE)

    assert exported["integrations"] == []
