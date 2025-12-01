import base64
import datetime
from copy import deepcopy

from django.test.utils import override_settings
from django.urls import reverse

import pytest
import responses
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.models import License
from requests.auth import HTTPBasicAuth
from responses.matchers import header_matcher
from rest_framework.status import HTTP_200_OK, HTTP_402_PAYMENT_REQUIRED

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSync
from baserow.contrib.database.fields.models import TextField
from baserow.core.db import specific_iterator
from baserow_enterprise.data_sync.models import JiraIssuesDataSync

SINGLE_ISSUE = {
    "expand": "operations,versionedRepresentations,editmeta,changelog,customfield_10010.requestTypePractice,renderedFields",
    "id": "10002",
    "self": "https://test.atlassian.net/rest/api/2/issue/10002",
    "key": "CRM-5",
    "fields": {
        "statuscategorychangedate": "2024-10-13T14:02:31.892+0200",
        "issuetype": {
            "self": "https://test.atlassian.net/rest/api/2/issuetype/10001",
            "id": "10001",
            "description": "Tasks track small, distinct pieces of work.",
            "iconUrl": "https://test.atlassian.net/rest/api/2/universal_avatar/view/type/issuetype/avatar/10318?size=medium",
            "name": "Task",
            "subtask": False,
            "avatarId": 10318,
            "entityId": "99d10125-f092-48e4-9e24-dc2f32f89452",
            "hierarchyLevel": 0,
        },
        "parent": {
            "id": "10001",
            "key": "CRM-2",
            "self": "https://test.atlassian.net/rest/api/2/issue/10001",
            "fields": {
                "summary": "(Sample) Customer Interaction Tracking",
                "status": {
                    "self": "https://test.atlassian.net/rest/api/2/status/10000",
                    "description": "",
                    "iconUrl": "https://test.atlassian.net/",
                    "name": "To Do",
                    "id": "10000",
                    "statusCategory": {
                        "self": "https://test.atlassian.net/rest/api/2/statuscategory/2",
                        "id": 2,
                        "key": "new",
                        "colorName": "blue-gray",
                        "name": "To Do",
                    },
                },
                "priority": {
                    "self": "https://test.atlassian.net/rest/api/2/priority/3",
                    "iconUrl": "https://test.atlassian.net/images/icons/priorities/medium.svg",
                    "name": "Medium",
                    "id": "3",
                },
                "issuetype": {
                    "self": "https://test.atlassian.net/rest/api/2/issuetype/10002",
                    "id": "10002",
                    "description": "Epics track collections of related bugs, stories, and tasks.",
                    "iconUrl": "https://test.atlassian.net/rest/api/2/universal_avatar/view/type/issuetype/avatar/10307?size=medium",
                    "name": "Epic",
                    "subtask": False,
                    "avatarId": 10307,
                    "entityId": "285cdbde-bd17-4c8d-8f24-fdb4200ca71a",
                    "hierarchyLevel": 1,
                },
            },
        },
        "timespent": None,
        "project": {
            "self": "https://test.atlassian.net/rest/api/2/project/10000",
            "id": "10000",
            "key": "CRM",
            "name": "Bram's project",
            "projectTypeKey": "software",
            "simplified": True,
            "avatarUrls": {
                "48x48": "https://test.atlassian.net/rest/api/2/universal_avatar/view/type/project/avatar/10411",
                "24x24": "https://test.atlassian.net/rest/api/2/universal_avatar/view/type/project/avatar/10411?size=small",
                "16x16": "https://test.atlassian.net/rest/api/2/universal_avatar/view/type/project/avatar/10411?size=xsmall",
                "32x32": "https://test.atlassian.net/rest/api/2/universal_avatar/view/type/project/avatar/10411?size=medium",
            },
        },
        "customfield_10032": None,
        "fixVersions": [],
        "customfield_10033": None,
        "customfield_10034": None,
        "aggregatetimespent": None,
        "resolution": None,
        "customfield_10035": None,
        "customfield_10036": None,
        "customfield_10027": None,
        "customfield_10028": None,
        "customfield_10029": None,
        "resolutiondate": "2024-10-18T21:30:42.029+0200",
        "workratio": -1,
        "watches": {
            "self": "https://test.atlassian.net/rest/api/2/issue/CRM-5/watchers",
            "watchCount": 1,
            "isWatching": True,
        },
        "lastViewed": "2024-10-13T21:27:43.346+0200",
        "created": "2024-10-13T14:02:31.589+0200",
        "customfield_10020": None,
        "customfield_10021": None,
        "customfield_10022": None,
        "priority": {
            "self": "https://test.atlassian.net/rest/api/2/priority/3",
            "iconUrl": "https://test.atlassian.net/images/icons/priorities/medium.svg",
            "name": "Medium",
            "id": "3",
        },
        "customfield_10023": None,
        "customfield_10024": None,
        "customfield_10025": None,
        "customfield_10026": None,
        "labels": ["label2", "label3"],
        "customfield_10016": None,
        "customfield_10017": None,
        "customfield_10018": {
            "hasEpicLinkFieldDependency": False,
            "showField": False,
            "nonEditableReason": {
                "reason": "EPIC_LINK_SHOULD_BE_USED",
                "message": "To set an epic as the parent, use the epic link instead",
            },
        },
        "customfield_10019": "0|i00007:",
        "timeestimate": None,
        "aggregatetimeoriginalestimate": None,
        "versions": [],
        "issuelinks": [],
        "assignee": {
            "self": "https://test.atlassian.net/rest/api/2/user?accountId=5aaec010e78b8c2a7c88b72e",
            "accountId": "5aaec010e78b8c2a7c88b72e",
            "emailAddress": "test@test.nl",
            "avatarUrls": {
                "48x48": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "24x24": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "16x16": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "32x32": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
            },
            "displayName": "Bram W",
            "active": True,
            "timeZone": "Europe/Amsterdam",
            "accountType": "atlassian",
        },
        "updated": "2024-10-13T21:30:42.029+0200",
        "status": {
            "self": "https://test.atlassian.net/rest/api/2/status/10000",
            "description": "",
            "iconUrl": "https://test.atlassian.net/",
            "name": "To Do",
            "id": "10000",
            "statusCategory": {
                "self": "https://test.atlassian.net/rest/api/2/statuscategory/2",
                "id": 2,
                "key": "new",
                "colorName": "blue-gray",
                "name": "To Do",
            },
        },
        "components": [],
        "timeoriginalestimate": None,
        "description": 'h1. Heading 1\n\nh2. heading 21\n\nh3. heading 3\n\nh4. heading 4\n\nh5. heading 5\n\nh6. heading 5\n\nAllow {color:#0747a6}users{color} to generate reports +based+ on -logged- customer {{interactions}}, with ~filters~ for date ^range^ and interaction type.\n\nBold: *bold*\n\n_Italic_\n\n{{Some code}}\n\n* bullet 1\n* bullet 2\n\n# List 1\n# List 2\n\n\n\n[Baserow|https://baserow.io]\n\n\n\n!Screenshot 2024-09-12 at 11.21.36.png|width=884,height=213,alt="Screenshot 2024-09-12 at 11.21.36.png"!\n\n😃\n\n||*head 1*||*head 2*||*head 3*||\n|row 1|row 2|row 3|\n|row 5|row 6|row 7|\n\n{code:python}code block`\nblock block 2{code}\n\n{quote}Quote{quote}\n\n----\n\n\n\n{{2024-10-16}}\n\n*title*\n\nexpand\n\n{color:#6554C0}*[ STATUS 1 ]*{color}\n\n{panel:bgColor=#deebff}\ninfo\n{panel}\n\n[~accountid:5aaec010e78b8c2a7c88b72e] ',
        "customfield_10010": None,
        "customfield_10014": None,
        "customfield_10015": None,
        "customfield_10005": None,
        "customfield_10006": None,
        "security": None,
        "customfield_10007": None,
        "customfield_10008": None,
        "customfield_10009": None,
        "aggregatetimeestimate": None,
        "summary": "(Sample) Generate Interaction Reports",
        "creator": {
            "self": "https://test.atlassian.net/rest/api/2/user?accountId=5aaec010e78b8c2a7c88b72e",
            "accountId": "5aaec010e78b8c2a7c88b72e",
            "emailAddress": "test@test.nl",
            "avatarUrls": {
                "48x48": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "24x24": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "16x16": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "32x32": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
            },
            "displayName": "Bram W",
            "active": True,
            "timeZone": "Europe/Amsterdam",
            "accountType": "atlassian",
        },
        "subtasks": [],
        "reporter": {
            "self": "https://test.atlassian.net/rest/api/2/user?accountId=5aaec010e78b8c2a7c88b72e",
            "accountId": "5aaec010e78b8c2a7c88b72e",
            "emailAddress": "test@test.nl",
            "avatarUrls": {
                "48x48": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "24x24": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "16x16": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
                "32x32": "https://secure.gravatar.com/avatar/69c218ba78985d1a01da2dd7191411d6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FBW-3.png",
            },
            "displayName": "Bram W",
            "active": True,
            "timeZone": "Europe/Amsterdam",
            "accountType": "atlassian",
        },
        "aggregateprogress": {"progress": 0, "total": 0},
        "customfield_10001": None,
        "customfield_10002": [],
        "customfield_10003": None,
        "customfield_10004": None,
        "environment": None,
        "duedate": "2024-10-14T14:02:31.589+0200",
        "progress": {"progress": 0, "total": 0},
        "votes": {
            "self": "https://test.atlassian.net/rest/api/2/issue/CRM-5/votes",
            "votes": 0,
            "hasVoted": False,
        },
    },
}
SECOND_ISSUE = deepcopy(SINGLE_ISSUE)
SECOND_ISSUE["id"] = "10003"
SECOND_ISSUE["key"] = "CRM-6"

EMPTY_ISSUE = {
    "expand": "renderedFields,names,schema,operations,editmeta,changelog,versionedRepresentations,customfield_10010.requestTypePractice",
    "id": "10007",
    "self": "https://bram2w.atlassian.net/rest/api/2/issue/10007",
    "key": "CRM-8",
    "fields": {
        "statuscategorychangedate": "2024-10-18T13:39:02.301+0200",
        "issuetype": None,
        "timespent": None,
        "project": None,
        "customfield_10032": None,
        "fixVersions": [],
        "customfield_10034": None,
        "aggregatetimespent": None,
        "resolution": None,
        "customfield_10035": None,
        "customfield_10027": None,
        "customfield_10028": None,
        "customfield_10029": None,
        "resolutiondate": None,
        "workratio": -1,
        "watches": {
            "self": "https://bram2w.atlassian.net/rest/api/2/issue/CRM-8/watchers",
            "watchCount": 1,
            "isWatching": True,
        },
        "issuerestriction": {"issuerestrictions": {}, "shouldDisplay": True},
        "lastViewed": None,
        "created": None,
        "customfield_10020": None,
        "customfield_10021": None,
        "customfield_10022": None,
        "priority": {
            "self": "https://bram2w.atlassian.net/rest/api/2/priority/3",
            "iconUrl": "https://bram2w.atlassian.net/images/icons/priorities/medium.svg",
            "name": "Medium",
            "id": "3",
        },
        "customfield_10023": None,
        "customfield_10024": None,
        "customfield_10025": None,
        "customfield_10026": None,
        "labels": [],
        "customfield_10016": None,
        "customfield_10017": None,
        "customfield_10018": {
            "hasEpicLinkFieldDependency": False,
            "showField": False,
            "nonEditableReason": {
                "reason": "EPIC_LINK_SHOULD_BE_USED",
                "message": "To set an epic as the parent, use the epic link instead",
            },
        },
        "customfield_10019": "0|i00013:",
        "timeestimate": None,
        "aggregatetimeoriginalestimate": None,
        "versions": [],
        "issuelinks": [],
        "assignee": None,
        "updated": "",
        "status": None,
        "components": [],
        "timeoriginalestimate": None,
        "description": "",
        "customfield_10010": None,
        "customfield_10014": None,
        "timetracking": {},
        "customfield_10015": None,
        "customfield_10005": None,
        "customfield_10006": None,
        "security": None,
        "customfield_10007": None,
        "customfield_10008": None,
        "customfield_10009": None,
        "aggregatetimeestimate": None,
        "attachment": [],
        "summary": "empty",
        "creator": None,
        "subtasks": [],
        "reporter": None,
        "aggregateprogress": {"progress": 0, "total": 0},
        "customfield_10001": None,
        "customfield_10002": [],
        "customfield_10003": None,
        "customfield_10004": None,
        "environment": None,
        "duedate": None,
        "progress": {"progress": 0, "total": 0},
        "votes": {
            "self": "https://bram2w.atlassian.net/rest/api/2/issue/CRM-8/votes",
            "votes": 0,
            "hasVoted": False,
        },
        "comment": {
            "comments": [],
            "self": "https://bram2w.atlassian.net/rest/api/2/issue/10007/comment",
            "maxResults": 0,
            "total": 0,
            "startAt": 0,
        },
        "worklog": {"startAt": 0, "maxResults": 20, "total": 0, "worklogs": []},
    },
}

SINGLE_ISSUE_RESPONSE = {
    "expand": "schema,names",
    "startAt": 0,
    "maxResults": 50,
    "total": 1,
    "issues": [SINGLE_ISSUE],
}

SINGLE_ISSUE_RESPONSE_PAGE_1 = {
    "expand": "schema,names",
    "startAt": 0,
    "maxResults": 50,
    "total": 51,
    "issues": [SINGLE_ISSUE],
}
SINGLE_ISSUE_RESPONSE_PAGE_2 = {
    "expand": "schema,names",
    "startAt": 50,
    "maxResults": 50,
    "total": 51,
    "issues": [SECOND_ISSUE],
}
NO_ISSUES_RESPONSE = {
    "expand": "schema,names",
    "startAt": 0,
    "maxResults": 50,
    "total": 0,
    "issues": [],
}
EMPTY_ISSUE_RESPONSE = {
    "expand": "schema,names",
    "startAt": 0,
    "maxResults": 50,
    "total": 1,
    "issues": [EMPTY_ISSUE],
}


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
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
            "summary",
            "description",
            "assignee",
            "reporter",
            "labels",
            "created",
            "updated",
            "resolved",
            "due",
            "status",
            "project",
            "url",
        ],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
    )

    assert isinstance(data_sync, JiraIssuesDataSync)
    assert data_sync.jira_url == "https://test.atlassian.net"
    assert data_sync.jira_project_key == ""
    assert data_sync.jira_username == "test@test.nl"
    assert data_sync.jira_api_token == "test_token"

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 13
    assert fields[0].name == "Jira Issue ID"
    assert isinstance(fields[0], TextField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is True
    assert fields[1].name == "Summary"
    assert fields[1].primary is False
    assert fields[1].read_only is True
    assert fields[1].immutable_type is True
    assert fields[1].immutable_properties is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table(enterprise_data_fixture):
    credentials = "test@test.nl:test_token"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    auth_header_value = f"Basic {encoded_credentials}"

    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=0&maxResults=50",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
        match=[header_matcher({"Authorization": auth_header_value})],
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
            "summary",
            "description",
            "assignee",
            "reporter",
            "labels",
            "created",
            "updated",
            "resolved",
            "due",
            "status",
            "project",
            "url",
        ],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    jira_id_field = fields[0]
    summary_field = fields[1]
    description_field = fields[2]
    assignee_field = fields[3]
    reporter_field = fields[4]
    labels_field = fields[5]
    created_field = fields[6]
    updated_field = fields[7]
    resolved_field = fields[8]
    due_field = fields[9]
    state_field = fields[10]
    project_field = fields[11]
    url_field = fields[12]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 1
    row = model.objects.all().first()

    assert getattr(row, f"field_{jira_id_field.id}") == "10002"
    assert (
        getattr(row, f"field_{summary_field.id}")
        == "(Sample) Generate Interaction Reports"
    )
    assert (
        getattr(row, f"field_{description_field.id}")
        == """# Heading 1

## heading 21

### heading 3

#### heading 4

##### heading 5

###### heading 5

Allow <font color="#0747a6">users</font> to generate reports <u>based</u> on ~~logged~~ customer `interactions`, with <sub>filters</sub> for date <sup>range</sup> and interaction type.

Bold: **bold**

_Italic_

`Some code`

- bullet 1
- bullet 2

1. List 1
1. List 2



[Baserow](https://baserow.io)



<img src="Screenshot 2024-09-12 at 11.21.36.png" width="884" height="213" />

😃

|**head 1**|**head 2**|**head 3**|
|---|---|---|
|row 1|row 2|row 3|
|row 5|row 6|row 7|

```python
code block`
block block 2
```

> Quote

----



`2024-10-16`

**title**

expand

<font color="#6554C0">**[ STATUS 1 ]**</font>

> info

@5aaec010e78b8c2a7c88b72e """
    )
    assert getattr(row, f"field_{assignee_field.id}") == "Bram W"
    assert getattr(row, f"field_{reporter_field.id}") == "Bram W"
    assert getattr(row, f"field_{labels_field.id}") == "label2, label3"
    assert getattr(row, f"field_{created_field.id}") == datetime.datetime(
        2024, 10, 13, 12, 2, 31, 589000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{updated_field.id}") == datetime.datetime(
        2024, 10, 13, 19, 30, 42, 29000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{resolved_field.id}") == datetime.datetime(
        2024, 10, 18, 19, 30, 42, 29000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{due_field.id}") == datetime.datetime(
        2024, 10, 14, 12, 2, 31, 589000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{state_field.id}") == "To Do"
    assert getattr(row, f"field_{project_field.id}") == "Bram's project"
    assert (
        getattr(row, f"field_{url_field.id}")
        == "https://test.atlassian.net/browse/CRM-5"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table_empty_issue(enterprise_data_fixture):
    credentials = "test@test.nl:test_token"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    auth_header_value = f"Basic {encoded_credentials}"

    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=0&maxResults=50",
        status=200,
        json=EMPTY_ISSUE_RESPONSE,
        match=[header_matcher({"Authorization": auth_header_value})],
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
            "summary",
            "description",
            "assignee",
            "reporter",
            "labels",
            "created",
            "updated",
            "resolved",
            "due",
            "status",
            "project",
            "url",
        ],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    jira_id_field = fields[0]
    summary_field = fields[1]
    description_field = fields[2]
    assignee_field = fields[3]
    reporter_field = fields[4]
    labels_field = fields[5]
    created_field = fields[6]
    updated_field = fields[7]
    resolved_field = fields[8]
    due_field = fields[9]
    state_field = fields[10]
    project_field = fields[11]
    url_field = fields[12]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 1
    row = model.objects.all().first()

    assert getattr(row, f"field_{jira_id_field.id}") == "10007"
    assert getattr(row, f"field_{summary_field.id}") == "empty"
    assert getattr(row, f"field_{description_field.id}") == ""
    assert getattr(row, f"field_{assignee_field.id}") == ""
    assert getattr(row, f"field_{reporter_field.id}") == ""
    assert getattr(row, f"field_{labels_field.id}") == ""
    assert getattr(row, f"field_{created_field.id}") is None
    assert getattr(row, f"field_{updated_field.id}") is None
    assert getattr(row, f"field_{resolved_field.id}") is None
    assert getattr(row, f"field_{due_field.id}") is None
    assert getattr(row, f"field_{state_field.id}") == ""
    assert getattr(row, f"field_{project_field.id}") == ""
    assert (
        getattr(row, f"field_{url_field.id}")
        == "https://test.atlassian.net/browse/CRM-8"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table_personal_access_token(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=0&maxResults=50",
        status=200,
        json=EMPTY_ISSUE_RESPONSE,
        match=[header_matcher({"Authorization": "Bearer FAKE_PAT"})],
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
        ],
        jira_url="https://test.atlassian.net",
        jira_authentication="PERSONAL_ACCESS_TOKEN",
        jira_project_key="",
        jira_username="",
        jira_api_token="FAKE_PAT",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    jira_id_field = fields[0]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 1
    row = model.objects.all().first()

    assert getattr(row, f"field_{jira_id_field.id}") == "10007"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_pagination(enterprise_data_fixture):
    basic_auth_header = HTTPBasicAuth("test@test.nl", "test_token")
    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=0&maxResults=50",
        status=200,
        json=SINGLE_ISSUE_RESPONSE_PAGE_1,
        headers={"Authorization": f"Basic {basic_auth_header}"},
    )
    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=50&maxResults=50",
        status=200,
        json=SINGLE_ISSUE_RESPONSE_PAGE_2,
        headers={"Authorization": f"Basic {basic_auth_header}"},
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
            "summary",
            "description",
            "assignee",
            "reporter",
            "labels",
            "created",
            "updated",
            "resolved",
            "due",
            "status",
            "project",
            "url",
        ],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
    )
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_invalid_auth(enterprise_data_fixture):
    basic_auth_header = HTTPBasicAuth("test@test.nl", "test_token")
    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=0&maxResults=50",
        status=200,
        json=NO_ISSUES_RESPONSE,
        headers={"Authorization": f"Basic {basic_auth_header}"},
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
        ],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
    )
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_error == (
        "No issues found. This is usually because the authentication details are wrong."
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_jira_error_message(enterprise_data_fixture):
    basic_auth_header = HTTPBasicAuth("test@test.nl", "test_token")
    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=0&maxResults=50",
        status=400,
        json={"errorMessages": ["test error"]},
        headers={"Authorization": f"Basic {basic_auth_header}"},
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
        ],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
    )
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_error == "test error"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_with_project_key(enterprise_data_fixture):
    basic_auth_header = HTTPBasicAuth("test@test.nl", "test_token")
    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=0&maxResults=50&jql=project=TEST",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
        headers={"Authorization": f"Basic {basic_auth_header}"},
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
        ],
        jira_url="https://test.atlassian.net",
        jira_project_key="TEST",
        jira_username="test@test.nl",
        jira_api_token="test_token",
    )
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_error is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_jira_not_updated_twice(enterprise_data_fixture):
    basic_auth_header = HTTPBasicAuth("test@test.nl", "test_token")
    responses.add(
        responses.GET,
        "https://test.atlassian.net/rest/api/2/search?startAt=0&maxResults=50",
        status=200,
        json=SINGLE_ISSUE_RESPONSE,
        headers={"Authorization": f"Basic {basic_auth_header}"},
    )

    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="jira_issues",
        synced_properties=[
            "jira_id",
            "summary",
            "description",
            "assignee",
            "reporter",
            "labels",
            "created",
            "updated",
            "resolved",
            "due",
            "status",
            "project",
            "url",
        ],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows = model.objects.all()
    row_1 = rows[0]

    row_1_last_modified = row_1.updated_on

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    row_1.refresh_from_db()

    # Because none of the values have changed in the source (interesting) table,
    # we don't expect the rows to have been updated. If they have been updated,
    # it means that the `is_equal` method of `BaserowFieldDataSyncProperty` is not
    # working as expected.
    assert row_1.updated_on == row_1_last_modified


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_data_sync_properties(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "jira_issues",
            "jira_url": "https://test.atlassian.net",
            "jira_project_key": "",
            "jira_username": "test@test.nl",
            "jira_api_token": "test_token",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": True,
            "key": "jira_id",
            "name": "Jira Issue ID",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "field_type": "text",
            "key": "summary",
            "name": "Summary",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "long_text",
            "key": "description",
            "name": "Description",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "text",
            "key": "assignee",
            "name": "Assignee",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "text",
            "key": "reporter",
            "name": "Reporter",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "text",
            "key": "labels",
            "name": "Labels",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "date",
            "key": "created",
            "name": "Created Date",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "date",
            "key": "updated",
            "name": "Updated Date",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "date",
            "key": "resolved",
            "name": "Resolved Date",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "date",
            "key": "due",
            "name": "Due Date",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "text",
            "key": "status",
            "name": "State",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "text",
            "key": "project",
            "name": "Project",
            "unique_primary": False,
            "initially_selected": True,
        },
        {
            "field_type": "url",
            "key": "url",
            "name": "Issue URL",
            "unique_primary": False,
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
            "type": "jira_issues",
            "synced_properties": ["jira_id"],
            "jira_url": "https://test.atlassian.net",
            "jira_project_key": "",
            "jira_username": "test@test.nl",
            "jira_api_token": "test_token",
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
        type_name="jira_issues",
        synced_properties=["jira_id"],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
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
            "type": "jira_issues",
            "synced_properties": ["jira_id"],
            "jira_url": "https://test.atlassian.net",
            "jira_project_key": "",
            "jira_username": "test@test.nl",
            "jira_api_token": "test_token",
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
        type_name="jira_issues",
        synced_properties=["jira_id"],
        jira_url="https://test.atlassian.net",
        jira_project_key="",
        jira_username="test@test.nl",
        jira_api_token="test_token",
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
        "type": "jira_issues",
        "synced_properties": [
            {
                "field_id": data_sync.table.field_set.all().first().id,
                "key": "jira_id",
                "unique_primary": True,
            }
        ],
        "last_sync": None,
        "last_error": None,
        "auto_add_new_properties": False,
        "two_way_sync": False,
        # The `jira_api_token` should not be in here.
        "jira_url": "https://test.atlassian.net",
        "jira_authentication": "API_TOKEN",
        "jira_project_key": "",
        "jira_username": "test@test.nl",
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_personal_access_token(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "jira_issues",
            "synced_properties": ["jira_id"],
            "jira_url": "https://test.atlassian.net",
            "jira_authentication": "PERSONAL_ACCESS_TOKEN",
            "jira_project_key": "",
            "jira_username": "",
            "jira_api_token": "test_pat",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]
    data_sync = DataSync.objects.get(pk=data_sync_id)

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "id": data_sync_id,
        "type": "jira_issues",
        "synced_properties": [
            {
                "field_id": data_sync.table.field_set.all().first().id,
                "key": "jira_id",
                "unique_primary": True,
            }
        ],
        "last_sync": None,
        "last_error": None,
        "auto_add_new_properties": False,
        "two_way_sync": False,
        "jira_url": "https://test.atlassian.net",
        "jira_authentication": "PERSONAL_ACCESS_TOKEN",
        "jira_project_key": "",
        "jira_username": "",
    }
