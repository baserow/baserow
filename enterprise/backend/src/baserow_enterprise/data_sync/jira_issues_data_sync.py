from datetime import datetime
from typing import Any, Dict, List, Optional

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.registries import DataSyncProperty, DataSyncType
from baserow.contrib.database.data_sync.utils import compare_date
from baserow.contrib.database.fields.models import (
    DateField,
    LongTextField,
    TextField,
    URLField,
)
from baserow.core.utils import ChildProgressBuilder, get_value_at_path
from baserow_enterprise.features import DATA_SYNC
from baserow_premium.license.handler import LicenseHandler

from .jira_client import fetch_issues
from .models import JiraIssuesDataSync


class JiraIDDataSyncProperty(DataSyncProperty):
    unique_primary = True
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class JiraSummaryDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class JiraDescriptionDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> LongTextField:
        return LongTextField(name=self.name, long_text_enable_rich_text=True)


class JiraAssigneeDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class JiraReporterDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class JiraLabelsDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class JiraCreatedDateDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> DateField:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=True,
            date_time_format="24",
            date_show_tzinfo=True,
        )

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)


class JiraUpdatedDateDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> DateField:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=True,
            date_time_format="24",
            date_show_tzinfo=True,
        )

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)


class JiraResolvedDateDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> DateField:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=True,
            date_time_format="24",
            date_show_tzinfo=True,
        )

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)


class JiraDueDateDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> DateField:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=True,
            date_time_format="24",
            date_show_tzinfo=True,
        )

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)


class JiraStateDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class JiraProjectDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class JiraURLDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> URLField:
        return URLField(name=self.name)


class JiraIssuesDataSyncType(DataSyncType):
    type = "jira_issues"
    model_class = JiraIssuesDataSync
    allowed_fields = [
        "jira_url",
        "jira_project_key",
        "jira_authentication",
        "jira_username",
        "jira_api_token",
    ]
    request_serializer_field_names = [
        "jira_url",
        "jira_project_key",
        "jira_authentication",
        "jira_username",
        "jira_api_token",
    ]
    # The `jira_api_token` should not be included because it's a secret value that must
    # only be possible to set and not get.
    serializer_field_names = [
        "jira_url",
        "jira_project_key",
        "jira_authentication",
        "jira_username",
    ]

    def prepare_sync_job_values(self, instance):
        # Raise the error so that the job doesn't start and the user is informed with
        # the correct error.
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            DATA_SYNC, instance.table.database.workspace
        )

    def get_properties(self, instance) -> List[DataSyncProperty]:
        # The `table_id` is not set if when just listing the properties using the
        # `DataSyncTypePropertiesView` endpoint, but it will be set when creating the
        # view.
        if instance.table_id:
            LicenseHandler.raise_if_workspace_doesnt_have_feature(
                DATA_SYNC, instance.table.database.workspace
            )
        return [
            JiraIDDataSyncProperty("jira_id", "Jira Issue ID"),
            JiraSummaryDataSyncProperty("summary", "Summary"),
            JiraDescriptionDataSyncProperty("description", "Description"),
            JiraAssigneeDataSyncProperty("assignee", "Assignee"),
            JiraReporterDataSyncProperty("reporter", "Reporter"),
            JiraLabelsDataSyncProperty("labels", "Labels"),
            JiraCreatedDateDataSyncProperty("created", "Created Date"),
            JiraUpdatedDateDataSyncProperty("updated", "Updated Date"),
            JiraResolvedDateDataSyncProperty("resolved", "Resolved Date"),
            JiraDueDateDataSyncProperty("due", "Due Date"),
            JiraStateDataSyncProperty("status", "State"),
            JiraStateDataSyncProperty("project", "Project"),
            JiraURLDataSyncProperty("url", "Issue URL"),
        ]

    def _parse_datetime(self, value):
        if not value:
            return None

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise SyncError(f"The date {value} could not be parsed.")

    def get_all_rows(
        self,
        instance,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict]:
        from jira2markdown import convert

        if instance.jira_project_key:
            jql = f"project={instance.jira_project_key} ORDER BY created DESC"
        else:
            jql = "created IS NOT EMPTY ORDER BY created DESC"

        issue_list = []
        progress = ChildProgressBuilder.build(progress_builder, child_total=10)
        fetched_issues = fetch_issues(
            instance,
            jql,
            progress_builder=progress.create_child_builder(represents_progress=9),
        )
        for issue in fetched_issues:
            try:
                jira_id = issue["id"]
                issue_url = f"{instance.jira_url}/browse/{issue['key']}"
            except KeyError:
                raise SyncError(
                    "The `id` and `key` are not found in the issue. This is likely the "
                    "result of an invalid response from Jira."
                )
            summary = get_value_at_path(issue, "fields.summary", "")
            description = get_value_at_path(issue, "fields.description", "") or ""
            assignee = get_value_at_path(issue, "fields.assignee.displayName", "")
            reporter = get_value_at_path(issue, "fields.reporter.displayName", "")
            project = get_value_at_path(issue, "fields.project.name", "")
            status = get_value_at_path(issue, "fields.status.name", "")
            labels = ", ".join(issue["fields"].get("labels", []))
            created = self._parse_datetime(issue["fields"].get("created"))
            updated = self._parse_datetime(issue["fields"].get("updated"))
            resolved = self._parse_datetime(issue["fields"].get("resolutiondate"))
            due = self._parse_datetime(issue["fields"].get("duedate"))
            issue_dict = {
                "jira_id": jira_id,
                "summary": summary,
                "description": convert(description),
                "assignee": assignee,
                "reporter": reporter,
                "labels": labels,
                "created": created,
                "updated": updated,
                "resolved": resolved,
                "due": due,
                "status": status,
                "project": project,
                "url": issue_url,
            }
            issue_list.append(issue_dict)
        progress.increment(by=1)

        return issue_list
