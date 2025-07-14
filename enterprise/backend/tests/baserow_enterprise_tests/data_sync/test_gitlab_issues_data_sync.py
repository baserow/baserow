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
from baserow_enterprise.data_sync.models import GitLabIssuesDataSync

SINGLE_ISSUE = {
    "id": 1,
    "iid": 2,
    "project_id": 3,
    "title": "A bug",
    "description": "### Description\n The description",
    "state": "closed",
    "created_at": "2024-10-24T09:44:32.863Z",
    "updated_at": "2024-10-30T11:54:14.372Z",
    "closed_at": "2024-10-30T11:54:14.234Z",
    "closed_by": {
        "id": 1,
        "username": "user",
        "name": "Firstname Lastname",
        "state": "active",
        "locked": False,
        "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/1/avatar.png",
        "web_url": "https://gitlab.com/user",
    },
    "labels": ["database", "bug"],
    "milestone": {
        "id": 1,
        "iid": 1,
        "project_id": 2,
        "title": "1.0",
        "description": "Milestone for version 1.0",
        "state": "active",
        "created_at": "2024-10-03T14:45:13.332Z",
        "updated_at": "2024-10-03T14:45:13.332Z",
        "due_date": "2024-12-11",
        "start_date": "2024-11-13",
        "expired": False,
        "web_url": "https://gitlab.com/baserow/baserow/-/milestones/1",
    },
    "assignees": [
        {
            "id": 1,
            "username": "user",
            "name": "Firstname Lastname",
            "state": "active",
            "locked": False,
            "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/1/avatar.png",
            "web_url": "https://gitlab.com/user",
        }
    ],
    "author": {
        "id": 1,
        "username": "user",
        "name": "Firstname Lastname",
        "state": "active",
        "locked": False,
        "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/1/avatar.png",
        "web_url": "https://gitlab.com/user",
    },
    "type": "ISSUE",
    "assignee": {
        "id": 1,
        "username": "user",
        "name": "Firstname Lastname",
        "state": "active",
        "locked": False,
        "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/1/avatar.png",
        "web_url": "https://gitlab.com/user",
    },
    "user_notes_count": 0,
    "merge_requests_count": 1,
    "upvotes": 10,
    "downvotes": 2,
    "due_date": "2024-10-24T09:44:32.863Z",
    "confidential": False,
    "discussion_locked": None,
    "issue_type": "issue",
    "web_url": "https://gitlab.com/baserow/baserow/-/issues/1",
    "time_stats": {
        "time_estimate": 0,
        "total_time_spent": 0,
        "human_time_estimate": None,
        "human_total_time_spent": None,
    },
    "task_completion_status": {"count": 0, "completed_count": 0},
    "weight": None,
    "blocking_issues_count": 0,
    "has_tasks": True,
    "task_status": "0 of 0 checklist items completed",
    "_links": {
        "self": "https://gitlab.com/api/v4/projects/1/issues/1",
        "notes": "https://gitlab.com/api/v4/projects/1/issues/1/notes",
        "award_emoji": "https://gitlab.com/api/v4/projects/1/issues/1/award_emoji",
        "project": "https://gitlab.com/api/v4/projects/1",
        "closed_as_duplicate_of": None,
    },
    "references": {"short": "#1", "relative": "#1", "full": "baserow/baserow#1"},
    "severity": "UNKNOWN",
    "moved_to_id": None,
    "imported": False,
    "imported_from": "none",
    "service_desk_reply_to": None,
    "epic_iid": None,
    "epic": None,
    "iteration": None,
    "health_status": None,
}

SECOND_ISSUE = deepcopy(SINGLE_ISSUE)
SECOND_ISSUE["id"] = 2
SECOND_ISSUE["iid"] = 3
SECOND_ISSUE["title"] = "Another bug"

SINGLE_ISSUE_RESPONSE = [SINGLE_ISSUE]

NO_ISSUES_RESPONSE = []

EMPTY_ISSUE = {
    "id": 1,
    "iid": 2,
    "project_id": 3,
    "title": "Empty",
    "description": None,
    "state": "open",
    "created_at": "2024-10-24T09:44:32.863Z",
    "updated_at": None,
    "closed_at": None,
    "closed_by": None,
    "labels": [],
    "milestone": None,
    "assignees": [],
    "author": None,
    "type": "ISSUE",
    "assignee": None,
    "user_notes_count": 0,
    "merge_requests_count": 1,
    "upvotes": 0,
    "downvotes": 0,
    "due_date": None,
    "confidential": False,
    "discussion_locked": None,
    "issue_type": "issue",
    "web_url": "https://gitlab.com/baserow/baserow/-/issues/1",
    "time_stats": {
        "time_estimate": 0,
        "total_time_spent": 0,
        "human_time_estimate": None,
        "human_total_time_spent": None,
    },
    "task_completion_status": {"count": 0, "completed_count": 0},
    "weight": None,
    "blocking_issues_count": 0,
    "has_tasks": True,
    "task_status": "0 of 0 checklist items completed",
    "_links": {
        "self": "https://gitlab.com/api/v4/projects/1/issues/1",
        "notes": "https://gitlab.com/api/v4/projects/1/issues/1/notes",
        "award_emoji": "https://gitlab.com/api/v4/projects/1/issues/1/award_emoji",
        "project": "https://gitlab.com/api/v4/projects/1",
        "closed_as_duplicate_of": None,
    },
    "references": None,
    "severity": "UNKNOWN",
    "moved_to_id": None,
    "imported": False,
    "imported_from": "none",
    "service_desk_reply_to": None,
    "epic_iid": None,
    "epic": None,
    "iteration": None,
    "health_status": None,
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
        type_name="gitlab_issues",
        synced_properties=[
            "id",
            "iid",
            "project_id",
            "title",
            "description",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "labels",
            "assignees",
            "author",
            "upvotes",
            "downvotes",
            "due_date",
            "milestone",
            "url",
        ],
        gitlab_url="https://gitlab.com",
        gitlab_project_id="1",
        gitlab_access_token="test",
    )

    assert isinstance(data_sync, GitLabIssuesDataSync)
    assert data_sync.gitlab_url == "https://gitlab.com"
    assert data_sync.gitlab_project_id == "1"
    assert data_sync.gitlab_access_token == "test"

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 18
    assert fields[0].name == "Internal unique ID"
    assert isinstance(fields[0], NumberField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is True
    assert fields[0].number_decimal_places == 0
    assert fields[1].name == "Issue ID"
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
        "https://gitlab.com/api/v4/projects/1/issues?page=1&per_page=50&state=all",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects/1/issues?page=2&per_page=50&state=all",
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
        type_name="gitlab_issues",
        synced_properties=[
            "id",
            "iid",
            "project_id",
            "title",
            "description",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "labels",
            "assignees",
            "author",
            "upvotes",
            "downvotes",
            "due_date",
            "milestone",
            "url",
        ],
        gitlab_url="https://gitlab.com",
        gitlab_project_id="1",
        gitlab_access_token="test",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))

    internal_id_field = fields[0]
    issue_id_field = fields[1]
    project_id_field = fields[2]
    title_field = fields[3]
    description_field = fields[4]
    state_field_field = fields[5]
    created_at_field = fields[6]
    updated_at_field = fields[7]
    closed_at_field = fields[8]
    closed_by_field = fields[9]
    labels_field = fields[10]
    assignees_field = fields[11]
    author_field = fields[12]
    upvotes_field = fields[13]
    downvotes_field = fields[14]
    due_date_field = fields[15]
    milestone_field = fields[16]
    url_field = fields[17]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 1
    row = model.objects.all().first()

    assert getattr(row, f"field_{internal_id_field.id}") == Decimal("1")
    assert getattr(row, f"field_{issue_id_field.id}") == Decimal("2")
    assert getattr(row, f"field_{project_id_field.id}") == Decimal("3")
    assert getattr(row, f"field_{title_field.id}") == "A bug"
    assert (
        getattr(row, f"field_{description_field.id}")
        == "### Description\n The description"
    )
    assert getattr(row, f"field_{state_field_field.id}") == "closed"
    assert getattr(row, f"field_{created_at_field.id}") == datetime.datetime(
        2024, 10, 24, 9, 44, 32, 863000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{updated_at_field.id}") == datetime.datetime(
        2024, 10, 30, 11, 54, 14, 372000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{closed_at_field.id}") == datetime.datetime(
        2024, 10, 30, 11, 54, 14, 234000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{closed_by_field.id}") == "Firstname Lastname"
    assert getattr(row, f"field_{labels_field.id}") == "database, bug"
    assert getattr(row, f"field_{assignees_field.id}") == "Firstname Lastname"
    assert getattr(row, f"field_{author_field.id}") == "Firstname Lastname"
    assert getattr(row, f"field_{upvotes_field.id}") == Decimal("10")
    assert getattr(row, f"field_{downvotes_field.id}") == Decimal("2")
    assert getattr(row, f"field_{due_date_field.id}") == datetime.datetime(
        2024, 10, 24, 9, 44, 32, 863000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{milestone_field.id}") == "1.0"
    assert (
        getattr(row, f"field_{url_field.id}")
        == "https://gitlab.com/baserow/baserow/-/issues/1"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table_empty_issue(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects/1/issues?page=1&per_page=50&state=all",
        status=200,
        json=EMPTY_ISSUE_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects/1/issues?page=2&per_page=50&state=all",
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
        type_name="gitlab_issues",
        synced_properties=[
            "id",
            "iid",
            "project_id",
            "title",
            "description",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "labels",
            "assignees",
            "author",
            "upvotes",
            "downvotes",
            "due_date",
            "milestone",
            "url",
        ],
        gitlab_url="https://gitlab.com",
        gitlab_project_id="1",
        gitlab_access_token="test",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    internal_id_field = fields[0]
    issue_id_field = fields[1]
    project_id_field = fields[2]
    title_field = fields[3]
    description_field = fields[4]
    state_field_field = fields[5]
    created_at_field = fields[6]
    updated_at_field = fields[7]
    closed_at_field = fields[8]
    closed_by_field = fields[9]
    labels_field = fields[10]
    assignees_field = fields[11]
    author_field = fields[12]
    upvotes_field = fields[13]
    downvotes_field = fields[14]
    due_date_field = fields[15]
    milestone_field = fields[16]
    url_field = fields[17]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 1
    row = model.objects.all().first()

    assert getattr(row, f"field_{internal_id_field.id}") == Decimal("1")
    assert getattr(row, f"field_{issue_id_field.id}") == Decimal("2")
    assert getattr(row, f"field_{project_id_field.id}") == Decimal("3")
    assert getattr(row, f"field_{title_field.id}") == "Empty"
    assert getattr(row, f"field_{description_field.id}") is None
    assert getattr(row, f"field_{state_field_field.id}") == "open"
    assert getattr(row, f"field_{created_at_field.id}") == datetime.datetime(
        2024, 10, 24, 9, 44, 32, 863000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{updated_at_field.id}") is None
    assert getattr(row, f"field_{closed_at_field.id}") is None
    assert getattr(row, f"field_{closed_by_field.id}") == ""
    assert getattr(row, f"field_{labels_field.id}") == ""
    assert getattr(row, f"field_{assignees_field.id}") == ""
    assert getattr(row, f"field_{author_field.id}") == ""
    assert getattr(row, f"field_{upvotes_field.id}") == Decimal("0")
    assert getattr(row, f"field_{downvotes_field.id}") == Decimal("0")
    assert getattr(row, f"field_{due_date_field.id}") is None
    assert getattr(row, f"field_{milestone_field.id}") == ""
    assert (
        getattr(row, f"field_{url_field.id}")
        == "https://gitlab.com/baserow/baserow/-/issues/1"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_pagination(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects/1/issues?page=1&per_page=50&state=all",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects/1/issues?page=2&per_page=50&state=all",
        status=200,
        json=[SECOND_ISSUE],
    )
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects/1/issues?page=3&per_page=50&state=all",
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
        type_name="gitlab_issues",
        synced_properties=[
            "id",
            "project_id",
            "title",
            "description",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "labels",
            "assignees",
            "author",
            "upvotes",
            "downvotes",
            "due_date",
            "milestone",
            "url",
        ],
        gitlab_url="https://gitlab.com",
        gitlab_project_id="1",
        gitlab_access_token="test",
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
        "https://gitlab.com/api/v4/projects/1/issues?page=1&per_page=50&state=all",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/projects/1/issues?page=2&per_page=50&state=all",
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
        type_name="gitlab_issues",
        synced_properties=[
            "id",
            "iid",
            "project_id",
            "title",
            "description",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "closed_by",
            "labels",
            "assignees",
            "author",
            "upvotes",
            "downvotes",
            "due_date",
            "milestone",
            "url",
        ],
        gitlab_url="https://gitlab.com",
        gitlab_project_id="1",
        gitlab_access_token="test",
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
        "https://gitlab.com/api/v4/projects/1/issues?page=1&per_page=50&state=all",
        status=401,
        json={"message": "401 Unauthorized"},
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="gitlab_issues",
        synced_properties=["id"],
        gitlab_url="https://gitlab.com",
        gitlab_project_id="1",
        gitlab_access_token="test",
    )
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_error == "401 Unauthorized"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_data_sync_properties(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "gitlab_issues",
            "gitlab_url": "https://gitlab.com",
            "gitlab_project_id": "1",
            "gitlab_access_token": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": True,
            "key": "id",
            "name": "Internal unique ID",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "iid",
            "name": "Issue ID",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "project_id",
            "name": "Project ID",
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
            "key": "description",
            "name": "Description",
            "field_type": "long_text",
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
            "key": "labels",
            "name": "Labels",
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
            "key": "author",
            "name": "Author",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "upvotes",
            "name": "Upvotes",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "downvotes",
            "name": "Downvotes",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "due_date",
            "name": "Due date",
            "field_type": "date",
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
            "type": "gitlab_issues",
            "synced_properties": ["id"],
            "gitlab_url": "https://gitlab.com",
            "gitlab_project_id": "1",
            "gitlab_access_token": "test",
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
        type_name="gitlab_issues",
        synced_properties=["id"],
        gitlab_url="https://gitlab.com",
        gitlab_project_id="1",
        gitlab_access_token="test",
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
            "type": "gitlab_issues",
            "synced_properties": ["id"],
            "gitlab_url": "https://gitlab.com",
            "gitlab_project_id": "1",
            "gitlab_access_token": "test",
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
        type_name="gitlab_issues",
        synced_properties=["id"],
        gitlab_url="https://gitlab.com",
        gitlab_project_id="1",
        gitlab_access_token="test",
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
        "type": "gitlab_issues",
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
        # The `gitlab_access_token` should not be in here.
        "gitlab_url": "https://gitlab.com",
        "gitlab_project_id": "1",
    }
