from unittest.mock import MagicMock

import pytest
import responses

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow_enterprise.data_sync.jira_client import (
    _is_cloud_from_server_info,
    fetch_issues,
)
from baserow_enterprise.data_sync.models import (
    JIRA_ISSUES_DATA_SYNC_API_TOKEN,
    JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN,
)

BASE_URL = "https://jira.example.com"


def _make_instance(auth_type=JIRA_ISSUES_DATA_SYNC_API_TOKEN, url=BASE_URL):
    instance = MagicMock()
    instance.jira_url = url
    instance.jira_authentication = auth_type
    instance.jira_username = "user@test.com"
    instance.jira_api_token = "token123"
    instance.jira_personal_access_token = "token123"
    return instance


def test_is_cloud_from_server_info_cloud():
    assert (
        _is_cloud_from_server_info({"deploymentType": "Cloud", "version": "1001.0.0"})
        is True
    )


def test_is_cloud_from_server_info_server():
    assert (
        _is_cloud_from_server_info({"deploymentType": "Server", "version": "9.4.0"})
        is False
    )


def test_is_cloud_from_server_info_old_version_on_prem():
    assert _is_cloud_from_server_info({"version": "8.20.0"}) is False


def test_is_cloud_from_server_info_high_version_cloud():
    assert _is_cloud_from_server_info({"version": "1001.5.0"}) is True


def test_is_cloud_from_server_info_no_data():
    assert _is_cloud_from_server_info(None) is False


def test_is_cloud_from_server_info_empty_dict():
    assert _is_cloud_from_server_info({}) is False


@responses.activate
def test_fetch_issues_detection_failure_falls_back_to_on_prem():
    instance = _make_instance()
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=500,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search",
        status=200,
        json={
            "issues": [{"id": "1", "key": "TEST-1", "fields": {}}],
            "startAt": 0,
            "maxResults": 50,
            "total": 1,
        },
    )
    issues = fetch_issues(instance, "project=TEST")
    assert len(issues) == 1


@responses.activate
def test_fetch_issues_cloud_single_page():
    instance = _make_instance()
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Cloud"},
    )
    responses.add(
        responses.POST,
        f"{BASE_URL}/rest/api/2/search/approximate-count",
        status=200,
        json={"count": 1},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search/jql",
        status=200,
        json={"issues": [{"id": "1", "key": "TEST-1", "fields": {}}]},
    )
    issues = fetch_issues(instance, "project=TEST")
    assert len(issues) == 1
    assert issues[0]["id"] == "1"


@responses.activate
def test_fetch_issues_cloud_pagination():
    instance = _make_instance()
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Cloud"},
    )
    responses.add(
        responses.POST,
        f"{BASE_URL}/rest/api/2/search/approximate-count",
        status=200,
        json={"count": 2},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search/jql",
        status=200,
        json={
            "issues": [{"id": "1", "key": "TEST-1", "fields": {}}],
            "nextPageToken": "page2",
        },
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search/jql",
        status=200,
        json={"issues": [{"id": "2", "key": "TEST-2", "fields": {}}]},
    )
    issues = fetch_issues(instance, "project=TEST")
    assert len(issues) == 2
    assert issues[1]["id"] == "2"


@responses.activate
def test_fetch_issues_cloud_no_issues_error():
    instance = _make_instance()
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Cloud"},
    )
    responses.add(
        responses.POST,
        f"{BASE_URL}/rest/api/2/search/approximate-count",
        status=200,
        json={"count": 0},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search/jql",
        status=200,
        json={"issues": []},
    )
    with pytest.raises(SyncError, match="No issues found"):
        fetch_issues(instance, "project=TEST")
    assert len(responses.calls) == 3  # serverInfo + approximate-count + search/jql


@responses.activate
def test_fetch_issues_cloud_error_response():
    instance = _make_instance()
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Cloud"},
    )
    responses.add(
        responses.POST,
        f"{BASE_URL}/rest/api/2/search/approximate-count",
        status=200,
        json={"count": 1},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search/jql",
        status=401,
        json={"errorMessages": ["Unauthorized"]},
    )
    with pytest.raises(SyncError, match="Unauthorized"):
        fetch_issues(instance, "project=TEST")


@responses.activate
def test_fetch_issues_on_prem_single_page():
    instance = _make_instance(auth_type=JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN)
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Server"},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search",
        status=200,
        json={
            "issues": [{"id": "1", "key": "TEST-1", "fields": {}}],
            "startAt": 0,
            "maxResults": 50,
            "total": 1,
        },
    )
    issues = fetch_issues(instance, "project=TEST")
    assert len(issues) == 1
    assert issues[0]["id"] == "1"


@responses.activate
def test_fetch_issues_on_prem_pagination():
    instance = _make_instance(auth_type=JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN)
    page1_issues = [
        {"id": str(i), "key": f"TEST-{i}", "fields": {}} for i in range(1, 51)
    ]
    page2_issues = [{"id": "51", "key": "TEST-51", "fields": {}}]
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Server"},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search",
        status=200,
        json={
            "issues": page1_issues,
            "startAt": 0,
            "maxResults": 50,
            "total": 51,
        },
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search",
        status=200,
        json={
            "issues": page2_issues,
            "startAt": 50,
            "maxResults": 50,
            "total": 51,
        },
    )
    issues = fetch_issues(instance, "project=TEST")
    assert len(issues) == 51
    assert issues[0]["id"] == "1"
    assert issues[-1]["id"] == "51"


@responses.activate
def test_fetch_issues_on_prem_no_issues_error():
    instance = _make_instance(auth_type=JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN)
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Server"},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search",
        status=200,
        json={
            "issues": [],
            "startAt": 0,
            "maxResults": 50,
            "total": 0,
        },
    )
    with pytest.raises(SyncError, match="No issues found"):
        fetch_issues(instance, "project=TEST")


@responses.activate
def test_fetch_issues_on_prem_error_response():
    instance = _make_instance(auth_type=JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN)
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Server"},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search",
        status=400,
        json={"errorMessages": ["JQL query is invalid"]},
    )
    with pytest.raises(SyncError, match="JQL query is invalid"):
        fetch_issues(instance, "invalid jql")


@responses.activate
def test_fetch_issues_cloud_basic_auth():
    instance = _make_instance(auth_type=JIRA_ISSUES_DATA_SYNC_API_TOKEN)
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Cloud"},
    )
    responses.add(
        responses.POST,
        f"{BASE_URL}/rest/api/2/search/approximate-count",
        status=200,
        json={"count": 1},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search/jql",
        status=200,
        json={"issues": [{"id": "1", "key": "TEST-1", "fields": {}}]},
    )
    fetch_issues(instance, "project=TEST")
    search_request = responses.calls[2].request
    assert search_request.headers["Authorization"].startswith("Basic ")


@responses.activate
def test_fetch_issues_on_prem_bearer_auth():
    instance = _make_instance(auth_type=JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN)
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/serverInfo",
        status=200,
        json={"deploymentType": "Server"},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/rest/api/2/search",
        status=200,
        json={
            "issues": [{"id": "1", "key": "TEST-1", "fields": {}}],
            "startAt": 0,
            "maxResults": 50,
            "total": 1,
        },
    )
    fetch_issues(instance, "project=TEST")
    search_request = responses.calls[1].request
    assert search_request.headers["Authorization"] == "Bearer token123"
