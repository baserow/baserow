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

from .models import GitHubIssuesDataSync


class GitHubIDDataSyncProperty(DataSyncProperty):
    unique_primary = True
    immutable_properties = True

    def to_baserow_field(self) -> NumberField:
        return NumberField(
            name=self.name, number_decimal_places=0, number_negative=False
        )


class GitHubTitleDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitHubBodyDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> LongTextField:
        return LongTextField(name=self.name, long_text_enable_rich_text=True)


class GitHubUserDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitHubAssigneeDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitHubAssigneesDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitHubLabelsDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitHubStateDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitHubCreatedAtDataSyncProperty(DataSyncProperty):
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


class GitHubUpdatedAtDataSyncProperty(DataSyncProperty):
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


class GitHubClosedAtDataSyncProperty(DataSyncProperty):
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


class GitHubClosedByDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitHubMilestoneDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class GitHubUrlDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> URLField:
        return URLField(name=self.name)


class GitHubIssuesDataSyncType(DataSyncType):
    type = "github_issues"
    model_class = GitHubIssuesDataSync
    allowed_fields = [
        "github_issues_owner",
        "github_issues_repo",
        "github_issues_api_token",
    ]
    request_serializer_field_names = [
        "github_issues_owner",
        "github_issues_repo",
        "github_issues_api_token",
    ]
    # The `github_issues_api_token` should not be included because it's a secret value
    # that must only be possible to set and not get.
    serializer_field_names = [
        "github_issues_owner",
        "github_issues_repo",
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
            GitHubIDDataSyncProperty("id", "GitHub Issue ID"),
            GitHubTitleDataSyncProperty("title", "Title"),
            GitHubBodyDataSyncProperty("body", "Body"),
            GitHubUserDataSyncProperty("user", "User"),
            GitHubAssigneeDataSyncProperty("assignee", "Assignee"),
            GitHubAssigneesDataSyncProperty("assignees", "Assignees"),
            GitHubLabelsDataSyncProperty("labels", "Labels"),
            GitHubStateDataSyncProperty("state", "State"),
            GitHubCreatedAtDataSyncProperty("created_at", "Created At"),
            GitHubUpdatedAtDataSyncProperty("updated_at", "Updated At"),
            GitHubClosedAtDataSyncProperty("closed_at", "Closed At"),
            GitHubClosedByDataSyncProperty("closed_by", "Closed By"),
            GitHubMilestoneDataSyncProperty("milestone", "Milestone"),
            GitHubUrlDataSyncProperty("url", "URL to Issue"),
        ]

    def _parse_datetime(self, value):
        if not value:
            return None

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise SyncError(f"The date {value} could not be parsed.")

    def _get_total_pages(self, response):
        if "Link" not in response.headers:
            return 1
        else:
            link_header = response.headers["Link"]
            links = link_header.split(",")
            last_link = next((link for link in links if 'rel="last"' in link), None)

            if last_link:
                last_page_url = last_link[last_link.find("<") + 1 : last_link.find(">")]
                last_page_number = int(last_page_url.split("page=")[1].split("&")[0])
                return last_page_number
            else:
                return 1

    def _fetch_issues(
        self,
        instance,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        url = f"https://api.github.com/repos/{instance.github_issues_owner}/{instance.github_issues_repo}/issues"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {instance.github_issues_api_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
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
                        "The request to GitHub did not return an OK response."
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
            raise SyncError(f"Error fetching GitHub Issues: {str(e)}")

        return issues

    def get_all_rows(
        self,
        instance,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict]:
        issues = []
        for issue in self._fetch_issues(instance, progress_builder):
            issue_id = get_value_at_path(issue, "number")
            created_at = self._parse_datetime(get_value_at_path(issue, "created_at"))
            updated_at = self._parse_datetime(get_value_at_path(issue, "updated_at"))
            closed_at = self._parse_datetime(get_value_at_path(issue, "closed_at"))
            assignees = ", ".join(
                [a["login"] for a in get_value_at_path(issue, "assignees", [])]
            )
            labels = ", ".join(
                [label["name"] for label in get_value_at_path(issue, "labels", [])]
            )
            url = (
                f"https://github.com/{instance.github_issues_owner}/"
                f"{instance.github_issues_repo}/issues/"
                f"{issue_id}"
            )

            issues.append(
                {
                    "id": issue_id,
                    "title": get_value_at_path(issue, "title", ""),
                    "body": get_value_at_path(issue, "body", ""),
                    "user": get_value_at_path(issue, "user.login", ""),
                    "assignee": get_value_at_path(issue, "assignee.login", ""),
                    "assignees": assignees,
                    "labels": labels,
                    "state": get_value_at_path(issue, "state", ""),
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "closed_at": closed_at,
                    "closed_by": get_value_at_path(issue, "closed_by.login", ""),
                    "milestone": get_value_at_path(issue, "milestone.title", ""),
                    "url": url,
                }
            )

        return issues
