import logging
import math
from typing import Any, Iterator, List, Optional

from atlassian import Jira
from requests.exceptions import HTTPError, RequestException

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.core.utils import ChildProgressBuilder

from .models import (
    JIRA_ISSUES_DATA_SYNC_API_TOKEN,
    JIRA_ISSUES_DATA_SYNC_PERSONAL_ACCESS_TOKEN,
    JiraIssuesDataSync,
)

logger = logging.getLogger(__name__)

JIRA_MAX_RESULTS_PER_PAGE = 50

JIRA_NO_ISSUES_ERROR = (
    "No issues found. This is usually because the authentication details are wrong."
)


def _first_error_message(http_error: HTTPError) -> str:
    """Extract the first error message from a Jira HTTP error response."""

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


def _is_cloud_from_server_info(info: Optional[dict[str, Any]]) -> bool:
    """Detect whether the Jira instance is Cloud based on serverInfo response."""

    if not isinstance(info, dict):
        return False

    deployment_type = info.get("deploymentType")
    if deployment_type == "Cloud":
        return True
    elif deployment_type == "Server":
        return False

    # Jira Cloud uses version numbers >= 1000 (e.g. 1001.0.0),
    # while on-prem/Data Center stays below 1000.
    version = info.get("version", "0")
    try:
        major_version = int(version.split(".")[0])
        if major_version >= 1000:
            return True
    except (ValueError, IndexError):
        pass
    return False


def _create_jira(instance: JiraIssuesDataSync) -> Jira:
    """Create a Jira client with auto-detected cloud/on-prem mode."""

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
        server_info = jira.get_server_info()
        if _is_cloud_from_server_info(server_info):
            jira.cloud = True
    except (HTTPError, RequestException):
        pass
    return jira


def _approximate_total(jira: Jira, jql: str) -> int:
    """Get approximate issue count for Cloud progress tracking."""

    try:
        result = jira.approximate_issue_count(jql)
        if isinstance(result, dict):
            return int(result.get("count") or 0)
        return 0
    except (HTTPError, RequestException) as e:
        logger.debug("Could not fetch Jira approximate count: %s", e)
        return 0


def _iter_pages(jira: Jira, jql: str) -> Iterator[dict]:
    """Yield issue pages from Jira, handling cloud/on-prem pagination differences.

    On-prem responses include 'total'. For Cloud, we look it up once via
    approximate_issue_count and stamp it onto every page so callers can
    build progress identically for both deployments.
    """

    if jira.cloud:
        total = _approximate_total(jira, jql)
        token: Optional[str] = None
        while True:
            page = jira.enhanced_jql(
                jql,
                fields="*all",
                limit=JIRA_MAX_RESULTS_PER_PAGE,
                nextPageToken=token,
            )
            if not isinstance(page, dict):
                raise SyncError("The request to Jira did not return a valid response.")
            page.setdefault("total", total)
            yield page
            token = page.get("nextPageToken")
            if not token:
                return
    else:
        start = 0
        while True:
            page = jira.jql(
                jql, fields="*all", start=start, limit=JIRA_MAX_RESULTS_PER_PAGE
            )
            if not isinstance(page, dict):
                raise SyncError("The request to Jira did not return a valid response.")
            yield page
            page_issues = page.get("issues", [])
            start += len(page_issues)
            total = int(page.get("total") or 0)
            if (
                total <= start
                or not page_issues
                or len(page_issues) < JIRA_MAX_RESULTS_PER_PAGE
            ):
                return


def fetch_issues(
    instance: JiraIssuesDataSync,
    jql: str,
    progress_builder: Optional[ChildProgressBuilder] = None,
) -> List[dict]:
    """Fetch all issues matching a JQL query from a Jira instance."""

    jira = _create_jira(instance)
    issues: List[dict] = []
    progress = None

    try:
        for i, page in enumerate(_iter_pages(jira, jql)):
            if progress is None:
                total = int(page.get("total") or 0)
                child_total = (
                    math.ceil(total / JIRA_MAX_RESULTS_PER_PAGE) if total else 1
                )
                progress = ChildProgressBuilder.build(
                    progress_builder, child_total=child_total
                )
            progress.increment(by=1)

            page_issues = page.get("issues") or []
            if i == 0 and not page_issues:
                raise SyncError(JIRA_NO_ISSUES_ERROR)
            issues.extend(page_issues)
        return issues
    except SyncError:
        raise
    except HTTPError as e:
        raise SyncError(_first_error_message(e))
    except RequestException as e:
        raise SyncError(f"Error connecting to Jira: {str(e)}")
    finally:
        if progress is None:
            ChildProgressBuilder.build(progress_builder, child_total=1)
