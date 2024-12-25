from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from baserow_premium.license.handler import LicenseHandler
from requests.exceptions import JSONDecodeError, RequestException

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.registries import DataSyncProperty, DataSyncType
from baserow.contrib.database.data_sync.utils import compare_date
from baserow.contrib.database.fields.models import (
    DateField,
    LongTextField,
    NumberField,
    TextField,
    URLField,
)
from baserow.core.utils import ChildProgressBuilder, get_value_at_path
from baserow_enterprise.features import DATA_SYNC

from .models import GitLabIssuesDataSync


class GitLabIDDataSyncProperty(DataSyncProperty):
    unique_primary = True
    immutable_properties = True

    def to_baserow_field(self) -> NumberField:
        return NumberField(
            name=self.name, number_decimal_places=0, number_negative=False
        )


class GitLabIIDDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> NumberField:
        return NumberField(
            name=self.name, number_decimal_places=0, number_negative=False
        )


class GitLabProjectIDDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> NumberField:
        return NumberField(
            name=self.name, number_decimal_places=0, number_negative=False
        )


class GitLabTitleDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitLabDescriptionDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> LongTextField:
        return LongTextField(name=self.name, long_text_enable_rich_text=True)


class GitLabStateDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> LongTextField:
        return TextField(name=self.name)


class GitLabCreatedAtDataSyncProperty(DataSyncProperty):
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


class GitLabUpdatedAtDataSyncProperty(DataSyncProperty):
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


class GitLabClosedAtDataSyncProperty(DataSyncProperty):
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


class GitLabLabelsDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitLabAssigneesDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitLabAuthorDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitLabUpvotesDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return NumberField(
            name=self.name, number_decimal_places=0, number_negative=False
        )


class GitLabDownvotesDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return NumberField(
            name=self.name, number_decimal_places=0, number_negative=False
        )


class GitLabDueDateDataSyncProperty(DataSyncProperty):
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


class GitLabIssueURLDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return URLField(name=self.name)


class GitLabClosedByDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitLabMilestoneDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitLabIssuesDataSyncType(DataSyncType):
    type = "gitlab_issues"
    model_class = GitLabIssuesDataSync
    allowed_fields = [
        "gitlab_url",
        "gitlab_project_id",
        "gitlab_access_token",
    ]
    request_serializer_field_names = [
        "gitlab_url",
        "gitlab_project_id",
        "gitlab_access_token",
    ]
    # The `gitlab_access_token` should not be included because it's a secret value
    # that must only be possible to set and not get.
    serializer_field_names = [
        "gitlab_url",
        "gitlab_project_id",
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
            GitLabIDDataSyncProperty("id", "Internal unique ID"),
            GitLabIIDDataSyncProperty("iid", "Issue ID"),
            GitLabProjectIDDataSyncProperty("project_id", "Project ID"),
            GitLabTitleDataSyncProperty("title", "Title"),
            GitLabDescriptionDataSyncProperty("description", "Description"),
            GitLabStateDataSyncProperty("state", "State"),
            GitLabCreatedAtDataSyncProperty("created_at", "Created At"),
            GitLabUpdatedAtDataSyncProperty("updated_at", "Updated At"),
            GitLabClosedAtDataSyncProperty("closed_at", "Closed At"),
            GitLabClosedByDataSyncProperty("closed_by", "Closed By"),
            GitLabLabelsDataSyncProperty("labels", "Labels"),
            GitLabAssigneesDataSyncProperty("assignees", "Assignees"),
            GitLabAuthorDataSyncProperty("author", "Author"),
            GitLabUpvotesDataSyncProperty("upvotes", "Upvotes"),
            GitLabDownvotesDataSyncProperty("downvotes", "Downvotes"),
            GitLabDueDateDataSyncProperty("due_date", "Due date"),
            GitLabMilestoneDataSyncProperty("milestone", "Milestone"),
            GitLabIssueURLDataSyncProperty("url", "URL to Issue"),
        ]

    def _parse_datetime(self, value):
        if not value:
            return None

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise SyncError(f"The date {value} could not be parsed.")

    def _get_total_pages(self, response):
        if "X-TOTAL-PAGES" in response.headers:
            return int(response.headers["X-TOTAL-PAGES"])
        else:
            return 1

    def _fetch_issues(
        self,
        instance,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        url = (
            f"{instance.gitlab_url}/api/v4/projects/{instance.gitlab_project_id}/issues"
        )
        headers = {"PRIVATE-TOKEN": f"{instance.gitlab_access_token}"}
        page, per_page = 1, 50
        issues = []
        progress = None
        try:
            while True:
                response = requests.get(
                    url,
                    headers=headers,
                    params={"page": page, "per_page": per_page, "state": "all"},
                    timeout=20,
                )
                if not response.ok:
                    try:
                        json = response.json()
                        if "message" in json:
                            raise SyncError(json["message"])
                    except JSONDecodeError:
                        pass

                    raise SyncError(
                        "The request to GitLab did not return an OK response."
                    )

                # The response of any request gives us the total number of pages,
                # allowing us to properly construct a progress bar.
                if progress is None:
                    progress = ChildProgressBuilder.build(
                        progress_builder,
                        child_total=self._get_total_pages(response),
                    )
                if progress:
                    progress.increment(by=1)

                data = response.json()
                if not data:
                    break

                issues.extend(data)
                page += 1
        except RequestException as e:
            raise SyncError(f"Error fetching GitLab Issues: {str(e)}")

        return issues

    def get_all_rows(
        self,
        instance,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict]:
        issues = []
        for issue in self._fetch_issues(instance, progress_builder):
            issue_id = get_value_at_path(issue, "id")
            created_at = self._parse_datetime(get_value_at_path(issue, "created_at"))
            updated_at = self._parse_datetime(get_value_at_path(issue, "updated_at"))
            closed_at = self._parse_datetime(get_value_at_path(issue, "closed_at"))
            due_date = self._parse_datetime(get_value_at_path(issue, "due_date"))
            assignees = ", ".join(
                [a["name"] for a in get_value_at_path(issue, "assignees", [])]
            )
            labels = ", ".join(
                [label for label in get_value_at_path(issue, "labels", [])]
            )

            issues.append(
                {
                    "id": issue_id,
                    "iid": get_value_at_path(issue, "iid", ""),
                    "project_id": get_value_at_path(issue, "project_id", ""),
                    "title": get_value_at_path(issue, "title", ""),
                    "description": get_value_at_path(issue, "description", ""),
                    "state": get_value_at_path(issue, "state", ""),
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "closed_at": closed_at,
                    "closed_by": get_value_at_path(issue, "closed_by.name", ""),
                    "labels": labels,
                    "assignees": assignees,
                    "author": get_value_at_path(issue, "author.name", ""),
                    "upvotes": get_value_at_path(issue, "upvotes", ""),
                    "downvotes": get_value_at_path(issue, "downvotes", ""),
                    "due_date": due_date,
                    "milestone": get_value_at_path(issue, "milestone.title", ""),
                    "url": get_value_at_path(issue, "web_url", ""),
                }
            )

        return issues
