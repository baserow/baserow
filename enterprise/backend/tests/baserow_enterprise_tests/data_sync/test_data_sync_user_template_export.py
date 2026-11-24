import pytest

from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.core.registries import ImportExportConfig
from baserow.core.user_templates.handler import user_template_copy_config
from baserow_enterprise.data_sync.models import (
    GitHubIssuesDataSync,
    GitLabIssuesDataSync,
    JiraIssuesDataSync,
    LocalBaserowTableDataSync,
)

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
