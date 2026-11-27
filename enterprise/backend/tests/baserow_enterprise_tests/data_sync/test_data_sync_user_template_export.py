from unittest.mock import patch

import pytest
import responses

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import (
    ICalCalendarDataSync,
    PostgreSQLDataSync,
)
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.models import Application
from baserow.core.registries import ImportExportConfig
from baserow.core.user_templates.handler import user_template_copy_config
from baserow_enterprise.data_sync.models import (
    GitHubIssuesDataSync,
    GitLabIssuesDataSync,
    JiraIssuesDataSync,
    LocalBaserowTableDataSync,
)
from tests.baserow.core.user_templates.utils import install, start_job

SOURCE = {
    "two_way_sync": True,
    "last_error": "Connection refused",
}
CLEARED = {"two_way_sync": False, "last_error": None}


def _local_baserow(data_fixture, user):
    source_table = data_fixture.create_database_table(user=user)
    return (
        {"source_table_id": source_table.id, "authorized_user_id": user.id},
        {"source_table_id": source_table.id, "authorized_user_id": user.id},
    )


CASES = [
    (
        JiraIssuesDataSync,
        {
            "jira_url": "https://acme.atlassian.net",
            "jira_project_key": "ACME",
            "jira_authentication": "PERSONAL_ACCESS_TOKEN",
            "jira_username": "ada@acme.example",
        },
        {
            "jira_url": "",
            "jira_project_key": "",
            "jira_authentication": "API_TOKEN",
            "jira_username": "",
        },
    ),
    (
        GitHubIssuesDataSync,
        {"github_issues_owner": "acme", "github_issues_repo": "crm"},
        {"github_issues_owner": "", "github_issues_repo": ""},
    ),
    (
        GitLabIssuesDataSync,
        {"gitlab_url": "https://gitlab.acme.example", "gitlab_project_id": "42"},
        {"gitlab_url": "https://gitlab.com", "gitlab_project_id": ""},
    ),
    (LocalBaserowTableDataSync, _local_baserow, None),
]


@pytest.mark.django_db
@pytest.mark.parametrize("model,values,cleared", CASES)
@pytest.mark.parametrize("is_user_template", [True, False])
def test_user_template_export_clears_connection_settings(
    data_fixture, model, values, cleared, is_user_template
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    if callable(values):
        values, cleared = values(data_fixture, user)
    data_sync = model.objects.create(table=table, **values, **SOURCE)
    config = (
        user_template_copy_config()
        if is_user_template
        else ImportExportConfig(include_permission_data=True)
    )

    serialized = data_sync_type_registry.get_by_model(data_sync).export_serialized(
        data_sync, config
    )

    expected = {**cleared, **CLEARED} if is_user_template else {**values, **SOURCE}
    assert {key: serialized[key] for key in expected} == expected


CONNECTED = [
    (ICalCalendarDataSync, {"ical_url": "https://cal.acme.example/basic.ics"}),
    (
        PostgreSQLDataSync,
        {
            "postgresql_host": "db.acme.example",
            "postgresql_username": "admin",
            "postgresql_password": "secret",
            "postgresql_database": "crm",
            "postgresql_table": "people",
        },
    ),
    (
        JiraIssuesDataSync,
        {
            "jira_url": "https://acme.atlassian.net",
            "jira_project_key": "ACME",
            "jira_username": "ada@acme.example",
            "jira_api_token": "secret",
        },
    ),
    (
        GitHubIssuesDataSync,
        {
            "github_issues_owner": "acme",
            "github_issues_repo": "crm",
            "github_issues_api_token": "secret",
        },
    ),
    (
        GitLabIssuesDataSync,
        {
            "gitlab_url": "https://gitlab.acme.example",
            "gitlab_project_id": "42",
            "gitlab_access_token": "secret",
        },
    ),
]


def _install_copy(data_fixture, model, values):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Synced")
    key = data_fixture.create_text_field(table=table, primary=True, name="Key")
    data_sync = model.objects.create(table=table, **values)
    data_sync.synced_properties.create(key="id", field=key, unique_primary=True)
    job = start_job(user, workspace, [database])
    root = data_fixture.set_user_template_state(job.template, "public")
    installer = data_fixture.create_user()
    target = data_fixture.create_workspace(user=installer)
    assert install(installer, target, root).state == JOB_FINISHED
    table_copy = Application.objects.get(workspace=target).specific.table_set.get()
    return installer, table_copy.data_sync.specific


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("use_tmp_media_root", "enable_enterprise", "synced_roles")
@pytest.mark.parametrize("model,values", CONNECTED)
def test_installed_copy_asks_to_fill_in_the_connection_before_syncing(
    data_fixture, model, values
):
    installer, data_sync_copy = _install_copy(data_fixture, model, values)

    with (
        responses.RequestsMock() as requests_out,
        patch(
            "baserow.contrib.database.data_sync.postgresql_data_sync_type.psycopg"
        ) as postgresql,
    ):
        synced = DataSyncHandler().sync_data_sync_table(installer, data_sync_copy)

    assert synced.last_error == "Fill in the connection settings to sync this table."
    assert len(requests_out.calls) == 0
    assert postgresql.connect.call_count == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("use_tmp_media_root", "enable_enterprise", "synced_roles")
def test_installed_postgresql_copy_asks_to_fill_in_the_connection_for_properties(
    data_fixture,
):
    _, data_sync_copy = _install_copy(
        data_fixture, PostgreSQLDataSync, dict(CONNECTED)[PostgreSQLDataSync]
    )

    with (
        patch(
            "baserow.contrib.database.data_sync.postgresql_data_sync_type.psycopg"
        ) as postgresql,
        pytest.raises(SyncError, match="Fill in the connection settings"),
    ):
        data_sync_type_registry.get_by_model(data_sync_copy).get_properties(
            data_sync_copy
        )

    assert postgresql.connect.call_count == 0
