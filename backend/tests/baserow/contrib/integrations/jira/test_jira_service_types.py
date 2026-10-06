import base64
from unittest.mock import patch

import pytest

from baserow.contrib.integrations.jira.models import (
    JIRA_AUTHENTICATION_PERSONAL_ACCESS_TOKEN,
)
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from tests.baserow.contrib.integrations.external_api_test_utils import fake_response

SEND = "baserow.contrib.integrations.external_api.send_http_request"
SITE = "https://example.atlassian.net"
BASIC = "Basic " + base64.b64encode(b"u@example.com:t").decode()


@pytest.mark.django_db
def test_jira_auth_headers_follow_the_authentication_choice(data_fixture):
    jira_type = integration_type_registry.get("jira")
    cloud = data_fixture.create_jira_integration(username="me@x.nl", api_token="tok")
    credentials = base64.b64encode(b"me@x.nl:tok").decode()
    assert jira_type.auth_headers(cloud) == {"Authorization": f"Basic {credentials}"}

    server = data_fixture.create_jira_integration(
        authentication=JIRA_AUTHENTICATION_PERSONAL_ACCESS_TOKEN, api_token="pat"
    )
    assert jira_type.auth_headers(server) == {"Authorization": "Bearer pat"}


@pytest.mark.django_db
def test_jira_list_issues_falls_back_to_the_server_endpoint(data_fixture):
    service = data_fixture.create_jira_list_issues_service(
        jql="'project = PROJ ORDER BY created DESC'", max_results=20
    )
    issue = {
        "id": "10001",
        "key": "PROJ-1",
        "fields": {
            "summary": "Broken login",
            "description": "h1. Title\n*bold*",
            "status": {"name": "To Do"},
            "issuetype": {"name": "Bug"},
            "priority": {"name": "High"},
            "assignee": {"displayName": "Ann"},
            "reporter": None,
            "labels": ["auth", "urgent"],
            "project": {"name": "Project"},
            "created": "2026-10-01T10:00:00.000+0000",
            "updated": "2026-10-02T10:00:00.000+0000",
            "duedate": None,
        },
    }
    with patch(SEND, return_value=fake_response(200, {"issues": [issue]})) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert send.call_args.args == ("GET", f"{SITE}/rest/api/2/search/jql")
    assert send.call_args.kwargs["headers"]["Authorization"] == BASIC
    assert send.call_args.kwargs["params"]["jql"] == (
        "project = PROJ ORDER BY created DESC"
    )
    assert send.call_args.kwargs["params"]["maxResults"] == 20
    assert result.data["count"] == 1
    listed = result.data["issues"][0]
    assert listed["key"] == "PROJ-1"
    assert listed["url"] == f"{SITE}/browse/PROJ-1"
    assert listed["status"] == "To Do"
    assert listed["labels"] == "auth, urgent"
    assert listed["assignee"] == "Ann"
    assert listed["reporter"] == ""
    assert "**bold**" in listed["description"]

    # Jira Server has no `/search/jql`: 404 there, then the classic search.
    responses = [
        fake_response(404, {"errorMessages": ["null for uri"]}),
        fake_response(200, {"issues": []}),
    ]
    with patch(SEND, side_effect=responses) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())
    assert send.call_args_list[1].args == ("GET", f"{SITE}/rest/api/2/search")
    assert send.call_args_list[1].kwargs["params"]["startAt"] == 0
    assert result.data == {"issues": [], "count": 0}


@pytest.mark.django_db
def test_jira_create_issue(data_fixture):
    service = data_fixture.create_jira_create_issue_service(
        project_key="'PROJ'",
        summary="'New bug'",
        description="'Steps'",
        priority="'High'",
        labels="'a, b'",
        assignee="'5b10ac8d82e05b22cc7d4ef5'",
    )
    with patch(
        SEND, return_value=fake_response(201, {"id": "10002", "key": "PROJ-2"})
    ) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert send.call_args.args == ("POST", f"{SITE}/rest/api/2/issue")
    assert send.call_args.kwargs["json"] == {
        "fields": {
            "summary": "New bug",
            "description": "Steps",
            "priority": {"name": "High"},
            "labels": ["a", "b"],
            "assignee": {"accountId": "5b10ac8d82e05b22cc7d4ef5"},
            "project": {"key": "PROJ"},
            "issuetype": {"name": "Task"},
        }
    }
    assert result.data == {
        "id": "10002",
        "key": "PROJ-2",
        "url": f"{SITE}/browse/PROJ-2",
    }

    with patch(
        SEND,
        return_value=fake_response(
            400, {"errorMessages": [], "errors": {"summary": "Required"}}
        ),
    ):
        with pytest.raises(RemoteRefusedDispatchException) as exc:
            service.get_type().dispatch(service, FakeDispatchContext())
    assert str(exc.value) == "Jira answered 400: summary: Required."


@pytest.mark.django_db
def test_jira_update_and_delete_issue(data_fixture):
    update = data_fixture.create_jira_update_issue_service(
        issue_key="'PROJ-2'", summary="'Renamed'", assignee="'jdoe'"
    )
    with patch(SEND, return_value=fake_response(204)) as send:
        result = update.get_type().dispatch(update, FakeDispatchContext())
    assert send.call_args.args == ("PUT", f"{SITE}/rest/api/2/issue/PROJ-2")
    assert send.call_args.kwargs["json"] == {
        "fields": {"summary": "Renamed", "assignee": {"name": "jdoe"}}
    }
    assert result.data == {
        "key": "PROJ-2",
        "url": f"{SITE}/browse/PROJ-2",
        "updated": True,
    }

    nothing = data_fixture.create_jira_update_issue_service(issue_key="'PROJ-2'")
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        nothing.get_type().dispatch(nothing, FakeDispatchContext())

    delete = data_fixture.create_jira_delete_issue_service(issue_key="'PROJ-2'")
    with patch(SEND, return_value=fake_response(204)) as send:
        result = delete.get_type().dispatch(delete, FakeDispatchContext())
    assert send.call_args.args == ("DELETE", f"{SITE}/rest/api/2/issue/PROJ-2")
    assert send.call_args.kwargs["params"] == {"deleteSubtasks": "false"}
    assert result.data == {"key": "PROJ-2", "deleted": True}


@pytest.mark.django_db
def test_jira_integration_needs_a_site_and_keeps_its_token_private(data_fixture):
    service = data_fixture.create_jira_delete_issue_service(
        integration_args={"api_token": ""}, issue_key="'PROJ-2'"
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        service.get_type().dispatch(service, FakeDispatchContext())

    integration = service.integration.specific
    jira_type = integration_type_registry.get("jira")
    data = jira_type.get_serializer(integration).data
    assert data["url"] == SITE
    assert data["has_api_token"] is False
    assert "api_token" not in data

    integration.api_token = "secret"  # nosec B105
    integration.save()
    exported = jira_type.export_serialized(
        integration,
        import_export_config=ImportExportConfig(include_permission_data=False),
    )
    assert exported["api_token"] is None
    imported = jira_type.import_serialized(
        integration.application,
        exported,
        {},
        import_export_config=ImportExportConfig(include_permission_data=False),
    )
    assert imported.url == SITE
    assert imported.api_token == ""
