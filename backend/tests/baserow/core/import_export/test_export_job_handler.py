import pytest

from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_create_export_file(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    cli_import_export_config = ImportExportConfig(
        include_permission_data=False, reduce_disk_space_usage=False
    )

    file_name = ImportExportHandler().export_workspace_applications(
        applications=[database],
        import_export_config=cli_import_export_config,
    )

    assert file_name is not None
