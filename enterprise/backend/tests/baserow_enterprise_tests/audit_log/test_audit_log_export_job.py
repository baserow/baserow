from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test.utils import override_settings

import pytest
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from freezegun import freeze_time

from baserow.contrib.database.export.handler import ExportHandler
from baserow.core.actions import CreateApplicationActionType, CreateWorkspaceActionType
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow_enterprise.audit_log.job_types import AuditLogExportJobType


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.storage.get_default_storage")
def test_audit_log_export_csv_correctly(
    get_storage_mock, enterprise_data_fixture, synced_roles
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    with freeze_time("2023-01-01 12:00:00"):
        workspace_1 = CreateWorkspaceActionType.do(user, "workspace 1").workspace

    with freeze_time("2023-01-01 12:00:10"):
        workspace_2 = CreateWorkspaceActionType.do(user, "workspace 2").workspace

    csv_settings = {
        "csv_column_separator": ",",
        "csv_first_row_header": True,
        "export_charset": "utf-8",
    }

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user, AuditLogExportJobType.type, **csv_settings, sync=True
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED

    data = stub_file.getvalue().decode(csv_settings["export_charset"])
    bom = "\ufeff"

    assert data == (
        bom
        + "User Email,User ID,Group Name,Group ID,Action Type,Description,Timestamp,IP Address\r\n"
        + f"{user.email},{user.id},{workspace_2.name},{workspace_2.id},Create group,"
        f'"Group ""{workspace_2.name}"" ({workspace_2.id}) created.",2023-01-01 12:00:10+00:00,\r\n'
        + f"{user.email},{user.id},{workspace_1.name},{workspace_1.id},Create group,"
        f'"Group ""{workspace_1.name}"" ({workspace_1.id}) created.",2023-01-01 '
        f"12:00:00+00:00,\r\n"
    )

    close()

    # With a different separator and wihout header
    csv_settings = {
        "csv_column_separator": "|",
        "csv_first_row_header": False,
        "export_charset": "utf-8",
    }

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user, AuditLogExportJobType.type, **csv_settings, sync=True
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED

    data = stub_file.getvalue().decode(csv_settings["export_charset"])
    bom = "\ufeff"

    assert data == (
        bom + f"{user.email}|{user.id}|{workspace_2.name}|{workspace_2.id}|Create "
        f'group|"Group ""{workspace_2.name}"" ({workspace_2.id}) '
        f'created."|2023-01-01 12:00:10+00:00|\r\n'
        + f"{user.email}|{user.id}|{workspace_1.name}|{workspace_1.id}|Create "
        f'group|"Group ""{workspace_1.name}"" ({workspace_1.id}) '
        f'created."|2023-01-01 12:00:00+00:00|\r\n'
    )

    close()


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
@override_settings(DEBUG=True)
@pytest.mark.skip("Need to re-build the translations first.")
def test_audit_log_export_csv_in_the_user_language(
    get_storage_mock, enterprise_data_fixture, synced_roles
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token(
        language="it"
    )

    with freeze_time("2023-01-01 12:00:00"):
        workspace_1 = CreateWorkspaceActionType.do(user, "workspace 1").workspace

    csv_settings = {
        "csv_column_separator": ",",
        "csv_first_row_header": False,
        "export_charset": "utf-8",
    }

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user, AuditLogExportJobType.type, **csv_settings, sync=True
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED

    data = stub_file.getvalue().decode(csv_settings["export_charset"])
    bom = "\ufeff"

    assert data == (
        bom
        + f'{user.email},{user.id},{workspace_1.name},{workspace_1.id},Crea progetto,"Progetto ""{workspace_1.name}"" ({workspace_1.id}) creato.",2023-01-01 12:00:00+00:00,\r\n'
    )

    close()


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
@override_settings(DEBUG=True)
def test_deleting_audit_log_export_job_also_delete_exported_file(
    get_storage_mock, enterprise_data_fixture, synced_roles
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    csv_settings = {
        "csv_column_separator": ",",
        "csv_first_row_header": True,
        "export_charset": "utf-8",
    }
    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user, AuditLogExportJobType.type, **csv_settings, sync=True
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED

    close()

    # ensure the clean_job method will delete the file
    assert csv_export_job.exported_file_name is not None

    with patch(
        "baserow_enterprise.audit_log.job_types.get_default_storage"
    ) as get_remove_mock:
        remove_mock = storage_mock
        get_remove_mock.return_value = remove_mock
        AuditLogExportJobType().before_delete(csv_export_job)
        remove_mock.delete.assert_called_once_with(
            ExportHandler.export_file_path(csv_export_job.exported_file_name)
        )


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
@override_settings(DEBUG=True)
def test_audit_log_export_filters_work_correctly(
    get_storage_mock, enterprise_data_fixture, synced_roles
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    with freeze_time("2023-01-01 12:00:00"):
        workspace_1 = CreateWorkspaceActionType.do(user, "workspace 1").workspace

    with freeze_time("2023-01-01 12:00:10"):
        workspace_2 = CreateWorkspaceActionType.do(user, "workspace 2").workspace

    csv_settings = {
        "csv_column_separator": ",",
        "csv_first_row_header": True,
        "export_charset": "utf-8",
    }

    job = JobHandler().create_and_start_job(
        user, AuditLogExportJobType.type, **csv_settings, sync=True
    )
    job.refresh_from_db()
    job_type = AuditLogExportJobType()

    assert job_type.get_filtered_queryset(job).count() == 2

    job.filter_user_id = user.id + 1
    assert job_type.get_filtered_queryset(job).count() == 0
    job.filter_user_id = None

    job.filter_workspace_id = workspace_1.id
    assert job_type.get_filtered_queryset(job).count() == 1
    job.filter_workspace_id = None

    job.filter_action_type = "delete_workspace"
    assert job_type.get_filtered_queryset(job).count() == 0
    job.filter_action_type = None

    job.filter_from_timestamp = datetime.strptime(
        "2023-01-01 12:00:05", "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=timezone.utc)
    assert job_type.get_filtered_queryset(job).count() == 1

    job.filter_to_timestamp = datetime.strptime(
        "2023-01-01 12:00:08", "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=timezone.utc)

    assert job_type.get_filtered_queryset(job).count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.storage.get_default_storage")
def test_audit_log_export_workspace_csv_correctly(
    get_storage_mock, enterprise_data_fixture, synced_roles
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    with freeze_time("2023-01-01 12:00:00"):
        app_1 = CreateApplicationActionType.do(
            user, workspace, "database", name="App 1"
        )

    with freeze_time("2023-01-01 12:00:10"):
        app_2 = CreateApplicationActionType.do(
            user, workspace, "database", name="App 2"
        )

    csv_settings = {
        "csv_column_separator": ",",
        "csv_first_row_header": True,
        "export_charset": "utf-8",
        "filter_workspace_id": workspace.id,
        "exclude_columns": "workspace_id,workspace_name",
    }

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user, AuditLogExportJobType.type, **csv_settings, sync=True
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED

    data = stub_file.getvalue().decode(csv_settings["export_charset"])
    bom = "\ufeff"

    assert data == (
        bom
        + "User Email,User ID,Action Type,Description,Timestamp,IP Address\r\n"
        + f'{user.email},{user.id},Create application,"""{app_2.name}"" ({app_2.id}) database created '
        + f'in group ""{workspace.name}"" ({workspace.id}).",2023-01-01 12:00:10+00:00,\r\n'
        + f'{user.email},{user.id},Create application,"""{app_1.name}"" ({app_1.id}) database created '
        + f'in group ""{workspace.name}"" ({workspace.id}).",2023-01-01 12:00:00+00:00,\r\n'
    )

    close()


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.storage.get_default_storage")
def test_audit_log_export_workspace_csv_correctly_if_feature_is_enable_for_the_user(
    get_storage_mock, enterprise_data_fixture, synced_roles
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    with freeze_time("2023-01-01 12:00:00"):
        app_1 = CreateApplicationActionType.do(
            user, workspace, "database", name="App 1"
        )

    with freeze_time("2023-01-01 12:00:10"):
        app_2 = CreateApplicationActionType.do(
            user, workspace, "database", name="App 2"
        )

    csv_settings = {
        "csv_column_separator": ",",
        "csv_first_row_header": True,
        "export_charset": "utf-8",
        "exclude_columns": "workspace_id,workspace_name",
    }

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    # The user cannot use the feature without a license, both instance-wide and for a
    # specific workspace.
    with pytest.raises(FeaturesNotAvailableError):
        csv_export_job = JobHandler().create_and_start_job(
            user, AuditLogExportJobType.type, sync=True, **csv_settings
        )

    with pytest.raises(FeaturesNotAvailableError):
        csv_export_job = JobHandler().create_and_start_job(
            user,
            AuditLogExportJobType.type,
            sync=True,
            filter_workspace_id=workspace.id,
            **csv_settings,
        )

    # Patch only the workspace feature, the instance-wide feature should still raise an
    # exception.
    with patch(
        "baserow_enterprise.audit_log.utils.LicenseHandler.raise_if_user_doesnt_have_feature"
    ):
        with pytest.raises(FeaturesNotAvailableError):
            csv_export_job = JobHandler().create_and_start_job(
                user, AuditLogExportJobType.type, sync=True, **csv_settings
            )

        # Providing the workspace id should work as it checks if the feature is enabled
        # for the workspace.
        csv_export_job = JobHandler().create_and_start_job(
            user,
            AuditLogExportJobType.type,
            sync=True,
            filter_workspace_id=workspace.id,
            **csv_settings,
        )
        csv_export_job.refresh_from_db()
        assert csv_export_job.state == JOB_FINISHED

        data = stub_file.getvalue().decode(csv_settings["export_charset"])
        bom = "\ufeff"

        assert data == (
            bom
            + "User Email,User ID,Action Type,Description,Timestamp,IP Address\r\n"
            + f'{user.email},{user.id},Create application,"""{app_2.name}"" ({app_2.id}) database created '
            + f'in group ""{workspace.name}"" ({workspace.id}).",2023-01-01 12:00:10+00:00,\r\n'
            + f'{user.email},{user.id},Create application,"""{app_1.name}"" ({app_1.id}) database created '
            + f'in group ""{workspace.name}"" ({workspace.id}).",2023-01-01 12:00:00+00:00,\r\n'
        )

        close()
