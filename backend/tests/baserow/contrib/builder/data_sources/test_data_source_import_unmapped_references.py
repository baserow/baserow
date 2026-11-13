import json
from io import BytesIO

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    EventTypes,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.models import Database
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


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


def _install_as_template(data_fixture, settings, tmpdir, applications):
    """
    Writes the applications as an official template file, like one written on
    another installation, and installs it into a new workspace of another user.
    """

    config = ImportExportConfig(include_permission_data=False)
    workspace = applications[0].workspace
    exported = CoreHandler().export_workspace_applications(workspace, BytesIO(), config)
    application_ids = {app.id for app in applications}
    template_apps = [app for app in exported if app["id"] in application_ids]
    tmpdir.join("unmapped-references.json").write(json.dumps({"export": template_apps}))
    settings.APPLICATION_TEMPLATES_DIR = str(tmpdir)
    template = data_fixture.create_template(slug="unmapped-references")

    user = data_fixture.create_user()
    target_workspace = data_fixture.create_workspace(user=user)
    imported, _ = CoreHandler().install_template(user, target_workspace, template)
    return imported


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

    imported = data_fixture.export_and_import_workspace_applications(
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
    export_path = data_fixture.export_workspace_applications_file([source["builder"]])

    # Like a file written on another instance, the filter names a field id that
    # doesn't exist here.
    source["field"].delete()

    imported = data_fixture.import_workspace_applications_file(export_path)

    service = _imported_service(imported)
    assert service.table_id is None
    assert service.service_filters.count() == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_with_the_database_remaps_the_references_to_it(
    data_fixture, use_tmp_media_root
):
    source = _create_builder_reading_a_table(data_fixture)

    imported = data_fixture.export_and_import_workspace_applications(
        [source["database"], source["builder"]]
    )

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
def test_template_install_without_the_database_clears_the_references_to_it(
    data_fixture, settings, tmpdir, use_tmp_media_root
):
    source = _create_builder_reading_a_table(data_fixture)

    imported = _install_as_template(data_fixture, settings, tmpdir, [source["builder"]])

    # A template install is a duplicate, but the ids in the file come from the
    # installation it was written on, so they aren't kept.
    service = _imported_service(imported)
    assert service.table_id is None
    assert service.view_id is None
    assert service.service_filters.count() == 0
    assert service.service_sorts.count() == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_template_install_clears_a_field_mapping_to_a_field_outside_it(
    data_fixture, settings, tmpdir, use_tmp_media_root
):
    # Like some shipped templates, the file holds the database of the action's
    # table, but one field mapping names a field that isn't part of it. The field
    # still exists on this instance, in another table.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    other_database = data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    other_table = data_fixture.create_database_table(user=user, database=other_database)
    other_field = data_fixture.create_text_field(table=other_table, name="Order")
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration, table=table
    )
    service.field_mappings.create(field=name_field, value="'Name'", enabled=True)
    service.field_mappings.create(field=other_field, value="'1'", enabled=True)
    data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value, service=service
    )

    imported = _install_as_template(data_fixture, settings, tmpdir, [database, builder])

    [imported_builder] = [app for app in imported if isinstance(app.specific, Builder)]
    [imported_database] = [
        app for app in imported if isinstance(app.specific, Database)
    ]
    action = BuilderWorkflowAction.objects.get(page__builder_id=imported_builder.id)
    imported_service = action.specific.service.specific
    imported_name_field = Field.objects.get(
        table__database_id=imported_database.id, name="Name"
    )
    # A duplicate would keep the other field, as it stays in the same workspace.
    assert [m.field_id for m in imported_service.field_mappings.all()] == [
        imported_name_field.id
    ]
