import math

from atlassian import Jira
from requests.exceptions import HTTPError, RequestException

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.core.utils import ChildProgressBuilder

from .models import (
    JIRA_ISSUES_DATA_SYNC_API_TOKEN,
    JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN,
)

JIRA_MAX_RESULTS_PER_PAGE = 50


def _first_error_message(http_error):
    response = http_error.response
    if response is not None:
        try:
            data = response.json()
            messages = data.get("errorMessages", [])
            if messages:
                return messages[0]
        except Exception:
            pass
    return str(http_error)


JIRA_NO_ISSUES_ERROR = (
    "No issues found. This is usually because the authentication details are wrong."
)


def _create_jira(instance):
    kwargs = {
        "url": instance.jira_url,
        "cloud": False,
        "timeout": 10,
    }

    if instance.jira_authentication == JIRA_ISSUES_DATA_SYNC_API_TOKEN:
        kwargs["username"] = instance.jira_username
        kwargs["password"] = instance.jira_api_token
    elif instance.jira_authentication == JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN:
        kwargs["token"] = instance.jira_api_token

    jira = Jira(**kwargs)

    try:
        server_info = jira.get("rest/api/2/serverInfo")
        if _is_cloud_from_server_info(server_info):
            jira.cloud = True
    except Exception:
        pass
    return jira


def _is_cloud_from_server_info(info):
    if not isinstance(info, dict):
        return False

    deployment_type = info.get("deploymentType")
    if deployment_type == "Cloud":
        return True
    elif deployment_type == "Server":
        return False

    version = info.get("version", "0")
    try:
        major_version = int(version.split(".")[0])
        if major_version >= 1000:
            return True
    except (ValueError, IndexError):
        pass
    return False


def _get_issue_count_cloud(jira, jql):
    try:
        result = jira.approximate_issue_count(jql)
        if isinstance(result, dict):
            return result.get("count", 0)
        return 0
    except Exception:
        return 0


def _fetch_issues_cloud(jira, jql, progress_builder):
    issue_count = _get_issue_count_cloud(jira, jql)
    page_count = (
        math.ceil(issue_count / JIRA_MAX_RESULTS_PER_PAGE) if issue_count > 0 else 0
    )
    progress = ChildProgressBuilder.build(progress_builder, child_total=page_count + 1)
    progress.increment(by=1)

    issues = []
    next_page_token = None

    try:
        while True:
            data = jira.enhanced_jql(
                jql,
                fields="*all",
                limit=JIRA_MAX_RESULTS_PER_PAGE,
                nextPageToken=next_page_token,
            )
            progress.increment(by=1)

            if not data.get("issues") and next_page_token is None:
                raise SyncError(JIRA_NO_ISSUES_ERROR)

            issues.extend(data["issues"])
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
    except SyncError:
        raise
    except HTTPError as e:
        raise SyncError(_first_error_message(e))
    except (RequestException, ConnectionError) as e:
        raise SyncError(f"Error connecting to Jira: {str(e)}")
    return issues


def _fetch_issues_on_prem(jira, jql, progress_builder):
    issues = []
    start_at = 0
    progress = None

    try:
        while True:
            data = jira.jql(
                jql,
                fields="*all",
                start=start_at,
                limit=JIRA_MAX_RESULTS_PER_PAGE,
            )

            if not isinstance(data, dict):
                raise SyncError("The request to Jira did not return a valid response.")

            total = data.get("total", 0)
            if total and progress is None:
                page_count = math.ceil(total / JIRA_MAX_RESULTS_PER_PAGE)
                progress = ChildProgressBuilder.build(
                    progress_builder, child_total=page_count
                )

            if progress:
                progress.increment(by=1)

            if not data.get("issues") and start_at == 0:
                raise SyncError(JIRA_NO_ISSUES_ERROR)

            issues.extend(data["issues"])
            start_at += JIRA_MAX_RESULTS_PER_PAGE

            if total <= start_at:
                break
    except SyncError:
        raise
    except HTTPError as e:
        raise SyncError(_first_error_message(e))
    except (RequestException, ConnectionError) as e:
        raise SyncError(f"Error connecting to Jira: {str(e)}")

    if progress is None:
        ChildProgressBuilder.build(progress_builder, child_total=1)
    return issues


def fetch_issues(instance, jql, progress_builder=None):
    jira = _create_jira(instance)

    if jira.cloud:
        return _fetch_issues_cloud(jira, jql, progress_builder)
    else:
        return _fetch_issues_on_prem(jira, jql, progress_builder)
