from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.integrations.models import Integration
from baserow.core.services.models import Service

JIRA_AUTHENTICATION_API_TOKEN = "API_TOKEN"  # nosec B105
JIRA_AUTHENTICATION_PERSONAL_ACCESS_TOKEN = "PERSONAL_ACCESS_TOKEN"  # nosec B105


class JiraIntegration(Integration):
    """
    A Jira site reached with an account's API token (Jira Cloud) or a
    personal access token (Jira Server and Data Center), as the Jira data
    sync does.
    """

    url = models.URLField(
        max_length=2000,
        blank=True,
        default="",
        help_text="The base URL of the Jira site, e.g. https://your-domain.atlassian.net.",
    )
    authentication = models.CharField(
        max_length=32,
        choices=[
            (JIRA_AUTHENTICATION_API_TOKEN, "API token"),
            (JIRA_AUTHENTICATION_PERSONAL_ACCESS_TOKEN, "Personal access token"),
        ],
        default=JIRA_AUTHENTICATION_API_TOKEN,
        db_default=JIRA_AUTHENTICATION_API_TOKEN,
    )
    username = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The email address of the account, used with an API token.",
    )
    api_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The API token or personal access token.",
    )


class JiraListIssuesService(Service):
    jql = FormulaField(
        default="",
        help_text="The JQL query, e.g. project = PROJ AND status != Done ORDER BY "
        "created DESC.",
    )
    max_results = models.PositiveIntegerField(
        default=50, help_text="The most issues to return (1-100)."
    )


class JiraIssueFieldsMixin(models.Model):
    summary = FormulaField(default="", help_text="The issue title.")
    description = FormulaField(
        default="", help_text="The description, in Jira wiki markup or plain text."
    )
    issue_type = FormulaField(
        default="", help_text="The issue type name, e.g. Task, Bug or Story."
    )
    priority = FormulaField(default="", help_text="The priority name, e.g. High.")
    labels = FormulaField(
        default="", help_text="Labels separated by commas; a label holds no spaces."
    )
    assignee = FormulaField(
        default="",
        help_text="The assignee's account id (Cloud) or username (Server).",
    )

    class Meta:
        abstract = True


class JiraCreateIssueService(Service, JiraIssueFieldsMixin):
    project_key = FormulaField(default="", help_text="The project key, e.g. PROJ.")


class JiraUpdateIssueService(Service, JiraIssueFieldsMixin):
    issue_key = FormulaField(
        default="", help_text="The key of the issue to change, e.g. PROJ-12."
    )


class JiraDeleteIssueService(Service):
    issue_key = FormulaField(
        default="", help_text="The key of the issue to delete, e.g. PROJ-12."
    )
