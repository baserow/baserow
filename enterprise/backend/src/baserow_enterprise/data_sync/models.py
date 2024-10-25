from django.contrib.auth import get_user_model
from django.db import models

from baserow.contrib.database.data_sync.models import DataSync
from baserow.contrib.database.table.models import Table

User = get_user_model()


class LocalBaserowTableDataSync(DataSync):
    source_table = models.ForeignKey(
        Table,
        null=True,
        on_delete=models.SET_NULL,
        help_text="The source table containing the data you would like to get the data "
        "from.",
    )
    authorized_user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        help_text="The user on whose behalf the data is synchronized. The user must "
        "have permission to the table.",
    )


class JiraIssuesDataSync(DataSync):
    jira_url = models.URLField(
        max_length=2000,
        help_text="The base URL of your Jira instance (e.g., https://your-domain.atlassian.net).",
    )
    jira_project_key = models.CharField(
        blank=True,
        max_length=255,
        help_text="The project key of the Jira project (e.g., PROJ).",
    )
    jira_username = models.CharField(
        max_length=255,
        help_text="The username of the Jira account used to authenticate.",
    )
    jira_api_token = models.CharField(
        max_length=255,
        help_text="The API token of the Jira account used for authentication.",
    )


class GitHubIssuesDataSync(DataSync):
    github_issues_owner = models.CharField(
        max_length=255, help_text="The owner of the repository on GitHub."
    )
    github_issues_repo = models.CharField(
        max_length=255, help_text="The name of the repository on GitHub."
    )
    github_issues_api_token = models.CharField(
        max_length=255,
        help_text="The API token used to authenticate requests to GitHub.",
    )
