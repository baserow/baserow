from io import BytesIO

import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.database.models import Database
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import get_default_storage


def _create_builder_reading_a_table(data_fixture):
    """
    A workspace with a database and a builder whose list rows data source reads a
    table of that database through a view, with a filter and a sort on a field.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    view = data_fixture.create_grid_view(user=user, table=table)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, view=view, integration=integration
    )
    service = data_source.service.specific
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=field, value="Bram", value_is_formula=False
    )
    data_fixture.create_local_baserow_table_service_sort(
        service=service, field=field, order_by="ASC", order=0
    )
    return {
        "user": user,
        "database": database,
        "table": table,
        "field": field,
        "view": view,
        "builder": builder,
        "service": service,
    }


def _export_and_import(data_fixture, applications, application_ids=None):
    """
    Exports the applications as a workspace export file, and imports it into a new
    workspace of another user, only the given applications when set.
    """

    data_fixture.create_import_export_trusted_source()
    handler = ImportExportHandler()
    storage = get_default_storage()

    resource = handler.export_workspace_applications(
        applications=applications,
        import_export_config=ImportExportConfig(
            include_permission_data=False, reduce_disk_space_usage=False
        ),
    )
    export_path = handler.get_export_storage_path(resource.get_archive_name())

    importer = data_fixture.create_user()
    target_workspace = data_fixture.create_workspace(user=importer)
    with storage.open(export_path, "rb") as archive:
        import_resource = handler.create_resource_from_file(
            importer, "export.zip", archive
        )
    return handler.import_workspace_applications(
        importer, target_workspace, import_resource, application_ids=application_ids
    )


def _imported_service(applications):
    [builder] = [app for app in applications if isinstance(app.specific, Builder)]
    data_source = DataSource.objects.get(page__builder_id=builder.id)
    return data_source.service.specific


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_without_the_database_clears_the_references_to_it(
    data_fixture, use_tmp_media_root
):
    source = _create_builder_reading_a_table(data_fixture)

    imported = _export_and_import(
        data_fixture,
        [source["database"], source["builder"]],
        application_ids=[source["builder"].id],
    )

    # The source table, view and field still exist on this instance, in another
    # workspace. Keeping their ids would point the data source at them.
    service = _imported_service(imported)
    assert service.table_id is None
    assert service.view_id is None
    assert service.service_filters.count() == 0
    assert service.service_sorts.count() == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_without_the_database_doesnt_fail_on_a_field_missing_here(
    data_fixture, use_tmp_media_root
):
    source = _create_builder_reading_a_table(data_fixture)
    data_fixture.create_import_export_trusted_source()
    handler = ImportExportHandler()
    storage = get_default_storage()
    resource = handler.export_workspace_applications(
        applications=[source["builder"]],
        import_export_config=ImportExportConfig(
            include_permission_data=False, reduce_disk_space_usage=False
        ),
    )
    export_path = handler.get_export_storage_path(resource.get_archive_name())

    # Like a file written on another instance, the filter names a field id that
    # doesn't exist here.
    source["field"].delete()

    importer = data_fixture.create_user()
    target_workspace = data_fixture.create_workspace(user=importer)
    with storage.open(export_path, "rb") as archive:
        import_resource = handler.create_resource_from_file(
            importer, "export.zip", archive
        )
    imported = handler.import_workspace_applications(
        importer, target_workspace, import_resource
    )

    service = _imported_service(imported)
    assert service.table_id is None
    assert service.service_filters.count() == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_with_the_database_remaps_the_references_to_it(
    data_fixture, use_tmp_media_root
):
    source = _create_builder_reading_a_table(data_fixture)

    imported = _export_and_import(data_fixture, [source["database"], source["builder"]])

    [database] = [app for app in imported if isinstance(app.specific, Database)]
    service = _imported_service(imported)
    assert service.table.database_id == database.id
    assert service.table.name == source["table"].name
    assert service.view.table_id == service.table_id
    [service_filter] = service.service_filters.all()
    assert service_filter.field.table_id == service.table_id
    assert service_filter.field.name == source["field"].name
    [service_sort] = service.service_sorts.all()
    assert service_sort.field_id == service_filter.field_id


@pytest.mark.django_db
def test_duplicating_a_builder_keeps_the_references_to_its_workspace_tables(
    data_fixture,
):
    source = _create_builder_reading_a_table(data_fixture)

    duplicate = CoreHandler().duplicate_application(source["user"], source["builder"])

    # A duplicate stays in the workspace, where the table is still the right one.
    service = DataSource.objects.get(page__builder_id=duplicate.id).service.specific
    assert service.table_id == source["table"].id
    assert service.view_id == source["view"].id
    [service_filter] = service.service_filters.all()
    assert service_filter.field_id == source["field"].id


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_to_workspace_without_the_database_clears_the_references_to_it(
    data_fixture, use_tmp_media_root
):
    # The path of the `import_workspace_applications` management command.
    source = _create_builder_reading_a_table(data_fixture)
    config = ImportExportConfig(include_permission_data=False)
    files_buffer = BytesIO()
    exported = CoreHandler().export_workspace_applications(
        source["builder"].workspace, files_buffer, config
    )
    exported_builder = [app for app in exported if app["type"] == "builder"]
    target_workspace = data_fixture.create_workspace(user=data_fixture.create_user())

    files_buffer.seek(0)
    imported, _ = CoreHandler().import_applications_to_workspace(
        target_workspace, exported_builder, files_buffer, config
    )

    service = _imported_service(imported)
    assert service.table_id is None
    assert service.view_id is None
    assert service.service_filters.count() == 0
    assert service.service_sorts.count() == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_of_an_automation_without_the_database_clears_the_references_to_it(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    data_fixture.create_local_baserow_create_row_action_node(
        user=user, workflow=workflow, service_kwargs={"table": table}
    )

    imported = _export_and_import(
        data_fixture, [database, automation], application_ids=[automation.id]
    )

    [imported_automation] = imported
    tables = {
        node.service.specific.table_id
        for node in AutomationNode.objects.filter(
            workflow__automation_id=imported_automation.id
        )
        if hasattr(node.service.specific, "table_id")
    }
    assert tables == {None}


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_of_a_dashboard_without_the_database_clears_the_references_to_it(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    dashboard = data_fixture.create_dashboard_application(
        user=user, workspace=workspace
    )
    data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, table=table
    )

    imported = _export_and_import(
        data_fixture, [database, dashboard], application_ids=[dashboard.id]
    )

    [imported_dashboard] = imported
    data_source = DashboardDataSource.objects.get(dashboard_id=imported_dashboard.id)
    assert data_source.service.specific.table_id is None
