import datetime
from copy import deepcopy
from decimal import Decimal

from django.test.utils import override_settings
from django.urls import reverse

import pytest
import responses
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.models import License
from rest_framework.status import HTTP_200_OK, HTTP_402_PAYMENT_REQUIRED

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.fields.models import NumberField
from baserow.core.db import specific_iterator
from baserow_enterprise.data_sync.models import GitHubIssuesDataSync

SINGLE_ISSUE = {
    "url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1",
    "repository_url": "https://api.github.com/repos/baserow_owner/baserow_repo",
    "labels_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/labels{/name}",
    "comments_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/comments",
    "events_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/events",
    "html_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1",
    "id": 1,
    "node_id": "MDU6SXNzdWUx",
    "number": 1,
    "title": "Found a bug",
    "user": {
        "login": "octocat",
        "id": 1,
        "node_id": "U_MDU6SXNzdWUx",
        "gravatar_id": "",
        "type": "User",
        "user_view_type": "public",
        "site_admin": False,
    },
    "labels": [
        {
            "id": 1,
            "node_id": "LA_MDU6SXNzdWUx",
            "url": "https://api.github.com/repos/baserow_owner/baserow_repo/labels/bug",
            "name": "bug",
            "color": "f29513",
            "default": False,
            "description": "A bug",
        },
        {
            "id": 2,
            "node_id": "LA_MDU6SXNzdWUx",
            "url": "https://api.github.com/repos/baserow_owner/baserow_repo/labels/bug",
            "name": "feature",
            "color": "f29513",
            "default": False,
            "description": "A feature",
        },
    ],
    "state": "open",
    "locked": False,
    "assignee": {"login": "octocat", "id": 1},
    "assignees": [{"login": "octocat", "id": 1}, {"login": "bram", "id": 2}],
    "milestone": {
        "url": "https://api.github.com/repos/baserow_owner/baserow_repo/milestones/1",
        "html_url": "https://github.com/baserow_owner/baserow_repo/milestones/v1.0",
        "labels_url": "https://api.github.com/repos/baserow_owner/baserow_repo/milestones/1/labels",
        "id": 1,
        "node_id": "MDk6TWlsZXN0b25lMTAwMjYwNA==",
        "number": 1,
        "state": "open",
        "title": "v1.0",
        "description": "Tracking milestone for version 1.0",
        "creator": {
            "login": "octocat",
            "id": 1,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://github.com/images/error/octocat_happy.gif",
            "gravatar_id": "",
            "url": "https://api.github.com/users/octocat",
            "html_url": "https://github.com/octocat",
            "followers_url": "https://api.github.com/users/octocat/followers",
            "following_url": "https://api.github.com/users/octocat/following{/other_user}",
            "gists_url": "https://api.github.com/users/octocat/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/octocat/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/octocat/subscriptions",
            "organizations_url": "https://api.github.com/users/octocat/orgs",
            "repos_url": "https://api.github.com/users/octocat/repos",
            "events_url": "https://api.github.com/users/octocat/events{/privacy}",
            "received_events_url": "https://api.github.com/users/octocat/received_events",
            "type": "User",
            "site_admin": False,
        },
        "open_issues": 4,
        "closed_issues": 8,
        "created_at": "2011-04-10T20:09:31Z",
        "updated_at": "2014-03-03T18:58:10Z",
        "closed_at": "2013-02-12T13:22:01Z",
        "due_on": "2012-10-09T23:39:01Z",
    },
    "comments": 0,
    "created_at": "2024-10-12T20:04:08Z",
    "updated_at": "2024-10-12T20:22:23Z",
    "closed_at": "2024-10-14T20:10:23Z",
    "author_association": "NONE",
    "active_lock_reason": None,
    "body": "### Bug Description",
    "closed_by": {
        "login": "octocat",
        "id": 1,
    },
    "reactions": {
        "url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/reactions",
        "total_count": 0,
        "+1": 0,
        "-1": 0,
        "laugh": 0,
        "hooray": 0,
        "confused": 0,
        "heart": 0,
        "rocket": 0,
        "eyes": 0,
    },
    "timeline_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/timeline",
    "performed_via_github_app": None,
    "state_reason": None,
}

SECOND_ISSUE = deepcopy(SINGLE_ISSUE)
SECOND_ISSUE["id"] = 2
SECOND_ISSUE["number"] = 2
SECOND_ISSUE["title"] = "Another bug"

SINGLE_ISSUE_RESPONSE = [SINGLE_ISSUE]

NO_ISSUES_RESPONSE = []

EMPTY_ISSUE = {
    "url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1",
    "repository_url": "https://api.github.com/repos/baserow_owner/baserow_repo",
    "labels_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/labels{/name}",
    "comments_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/comments",
    "events_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/events",
    "html_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1",
    "id": 1,
    "node_id": "MDU6SXNzdWUx",
    "number": 1,
    "title": "",
    "user": None,
    "labels": [],
    "state": "open",
    "locked": False,
    "assignee": None,
    "assignees": [],
    "milestone": None,
    "comments": 0,
    "created_at": None,
    "updated_at": None,
    "closed_at": None,
    "author_association": "NONE",
    "active_lock_reason": None,
    "body": "",
    "closed_by": None,
    "reactions": {
        "url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/reactions",
        "total_count": 0,
        "+1": 0,
        "-1": 0,
        "laugh": 0,
        "hooray": 0,
        "confused": 0,
        "heart": 0,
        "rocket": 0,
        "eyes": 0,
    },
    "timeline_url": "https://api.github.com/repos/baserow_owner/baserow_repo/issues/1/timeline",
    "performed_via_github_app": None,
    "state_reason": None,
}
EMPTY_ISSUE_RESPONSE = [EMPTY_ISSUE]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="github_issues",
        synced_properties=[
            "id",
            "title",
            "body",
            "user",
            "assignee",
            "assignees",
            "labels",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "milestone",
            "url",
        ],
        github_issues_owner="baserow_owner",
        github_issues_repo="baserow_repo",
        github_issues_api_token="test",
    )

    assert isinstance(data_sync, GitHubIssuesDataSync)
    assert data_sync.github_issues_owner == "baserow_owner"
    assert data_sync.github_issues_repo == "baserow_repo"
    assert data_sync.github_issues_api_token == "test"

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 14
    assert fields[0].name == "GitHub Issue ID"
    assert isinstance(fields[0], NumberField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is True
    assert fields[0].number_decimal_places == 0
    assert fields[1].name == "Title"
    assert fields[1].primary is False
    assert fields[1].read_only is True
    assert fields[1].immutable_type is True
    assert fields[1].immutable_properties is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=1&per_page=50&state=all",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=2&per_page=50&state=all",
        status=200,
        json=NO_ISSUES_RESPONSE,
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="github_issues",
        synced_properties=[
            "id",
            "title",
            "body",
            "user",
            "assignee",
            "assignees",
            "labels",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "milestone",
            "url",
        ],
        github_issues_owner="baserow_owner",
        github_issues_repo="baserow_repo",
        github_issues_api_token="test",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    github_id_field = fields[0]
    title_field = fields[1]
    body_field = fields[2]
    user_field = fields[3]
    assignee_field = fields[4]
    assignees_field = fields[5]
    labels_field = fields[6]
    state_field = fields[7]
    created_field = fields[8]
    updated_field = fields[9]
    closed_field = fields[10]
    closed_by = fields[11]
    milestone_field = fields[12]
    url_field = fields[13]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 1
    row = model.objects.all().first()

    assert getattr(row, f"field_{github_id_field.id}") == Decimal("1")
    assert getattr(row, f"field_{title_field.id}") == "Found a bug"
    assert getattr(row, f"field_{body_field.id}") == "### Bug Description"
    assert getattr(row, f"field_{user_field.id}") == "octocat"
    assert getattr(row, f"field_{assignee_field.id}") == "octocat"
    assert getattr(row, f"field_{assignees_field.id}") == "octocat, bram"
    assert getattr(row, f"field_{labels_field.id}") == "bug, feature"
    assert getattr(row, f"field_{state_field.id}") == "open"
    assert getattr(row, f"field_{created_field.id}") == datetime.datetime(
        2024, 10, 12, 20, 4, 8, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{updated_field.id}") == datetime.datetime(
        2024, 10, 12, 20, 22, 23, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{closed_field.id}") == datetime.datetime(
        2024, 10, 14, 20, 10, 23, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{closed_by.id}") == "octocat"
    assert getattr(row, f"field_{milestone_field.id}") == "v1.0"
    assert (
        getattr(row, f"field_{url_field.id}")
        == "https://github.com/baserow_owner/baserow_repo/issues/1"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table_empty_issue(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=1&per_page=50&state=all",
        status=200,
        json=EMPTY_ISSUE_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=2&per_page=50&state=all",
        status=200,
        json=NO_ISSUES_RESPONSE,
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="github_issues",
        synced_properties=[
            "id",
            "title",
            "body",
            "user",
            "assignee",
            "assignees",
            "labels",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "milestone",
            "url",
        ],
        github_issues_owner="baserow_owner",
        github_issues_repo="baserow_repo",
        github_issues_api_token="test",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    github_id_field = fields[0]
    title_field = fields[1]
    body_field = fields[2]
    user_field = fields[3]
    assignee_field = fields[4]
    assignees_field = fields[5]
    labels_field = fields[6]
    state_field = fields[7]
    created_field = fields[8]
    updated_field = fields[9]
    closed_field = fields[10]
    closed_by = fields[11]
    milestone_field = fields[12]
    url_field = fields[13]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 1
    row = model.objects.all().first()

    assert getattr(row, f"field_{github_id_field.id}") == Decimal("1")
    assert getattr(row, f"field_{title_field.id}") == ""
    assert getattr(row, f"field_{body_field.id}") == ""
    assert getattr(row, f"field_{user_field.id}") == ""
    assert getattr(row, f"field_{assignee_field.id}") == ""
    assert getattr(row, f"field_{assignees_field.id}") == ""
    assert getattr(row, f"field_{labels_field.id}") == ""
    assert getattr(row, f"field_{state_field.id}") == "open"
    assert getattr(row, f"field_{created_field.id}") is None
    assert getattr(row, f"field_{updated_field.id}") is None
    assert getattr(row, f"field_{closed_field.id}") is None
    assert getattr(row, f"field_{closed_by.id}") == ""
    assert getattr(row, f"field_{milestone_field.id}") == ""
    assert (
        getattr(row, f"field_{url_field.id}")
        == "https://github.com/baserow_owner/baserow_repo/issues/1"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_pagination(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=1&per_page=50&state=all",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=2&per_page=50&state=all",
        status=200,
        json=[SECOND_ISSUE],
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=3&per_page=50&state=all",
        status=200,
        json=NO_ISSUES_RESPONSE,
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="github_issues",
        synced_properties=[
            "id",
            "title",
            "body",
            "user",
            "assignee",
            "assignees",
            "labels",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "milestone",
            "url",
        ],
        github_issues_owner="baserow_owner",
        github_issues_repo="baserow_repo",
        github_issues_api_token="test",
    )
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table_is_equal(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=1&per_page=50&state=all",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues?page=2&per_page=50&state=all",
        status=200,
        json=NO_ISSUES_RESPONSE,
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="github_issues",
        synced_properties=[
            "id",
            "title",
            "body",
            "user",
            "assignee",
            "assignees",
            "labels",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "milestone",
            "url",
        ],
        github_issues_owner="baserow_owner",
        github_issues_repo="baserow_repo",
        github_issues_api_token="test",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows = model.objects.all()
    row_1 = rows[0]

    row_1_last_modified = row_1.updated_on

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    rows = model.objects.all()
    row_1 = rows[0]

    # Because none of the values have changed, we don't expect the rows to have been
    # updated.
    assert row_1.updated_on == row_1_last_modified


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_invalid_auth(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.github.com/repos/baserow_owner/baserow_repo/issues",
        status=401,
        json={
            "message": "Bad credentials",
            "documentation_url": "https://docs.github.com/rest",
            "status": "401",
        },
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="github_issues",
        synced_properties=["id"],
        github_issues_owner="baserow_owner",
        github_issues_repo="baserow_repo",
        github_issues_api_token="test",
    )
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_error == "Bad credentials"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_data_sync_properties(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "github_issues",
            "github_issues_owner": "baserow_owner",
            "github_issues_repo": "baserow_repo",
            "github_issues_api_token": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": True,
            "key": "id",
            "name": "GitHub Issue ID",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "title",
            "name": "Title",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "body",
            "name": "Body",
            "field_type": "long_text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "user",
            "name": "User",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "assignee",
            "name": "Assignee",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "assignees",
            "name": "Assignees",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "labels",
            "name": "Labels",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "state",
            "name": "State",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "created_at",
            "name": "Created At",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "updated_at",
            "name": "Updated At",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "closed_at",
            "name": "Closed At",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "closed_by",
            "name": "Closed By",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "milestone",
            "name": "Milestone",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "url",
            "name": "URL to Issue",
            "field_type": "url",
            "initially_selected": True,
        },
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_without_license(enterprise_data_fixture, api_client):
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "github_issues",
            "synced_properties": ["github_id"],
            "github_issues_owner": "baserow_owner",
            "github_issues_repo": "baserow_repo",
            "github_issues_api_token": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sync_data_sync_table_without_license(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="github_issues",
        synced_properties=["id"],
        github_issues_owner="baserow_owner",
        github_issues_repo="baserow_repo",
        github_issues_api_token="test",
    )

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(FeaturesNotAvailableError):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_async_sync_data_sync_table_without_license(
    api_client, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "github_issues",
            "synced_properties": ["id"],
            "github_issues_owner": "baserow_owner",
            "github_issues_repo": "baserow_repo",
            "github_issues_api_token": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    License.objects.all().delete()

    response = api_client.post(
        reverse(
            "api:database:data_sync:sync_table", kwargs={"data_sync_id": data_sync_id}
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_data_sync(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="github_issues",
        synced_properties=["id"],
        github_issues_owner="baserow_owner",
        github_issues_repo="baserow_repo",
        github_issues_api_token="test",
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "id": data_sync.id,
        "type": "github_issues",
        "synced_properties": [
            {
                "field_id": data_sync.table.field_set.all().first().id,
                "key": "id",
                "unique_primary": True,
            }
        ],
        "last_sync": None,
        "last_error": None,
        "auto_add_new_properties": False,
        "two_way_sync": False,
        # The `github_issues_api_token` should not be in here.
        "github_issues_owner": "baserow_owner",
        "github_issues_repo": "baserow_repo",
    }
