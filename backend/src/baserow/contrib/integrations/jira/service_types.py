from typing import Any, Dict, List
from urllib.parse import quote

from baserow.contrib.integrations.external_api import (
    ExternalAPIServiceType,
    array_property,
    boolean_property,
    number_property,
    string_property,
)
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.utils import get_value_at_path

from .integration_types import JiraIntegrationType
from .models import (
    JiraCreateIssueService,
    JiraDeleteIssueService,
    JiraListIssuesService,
    JiraUpdateIssueService,
)

MAX_LIST_RESULTS = 100
ISSUE_FIELDS = (
    "summary,description,status,issuetype,priority,assignee,reporter,labels,"
    "project,created,updated,duedate"
)


class JiraServiceType(ExternalAPIServiceType):
    integration_type = JiraIntegrationType.type
    provider_name = "Jira"

    def site(self, service):
        integration = self.get_integration(service)
        if not integration.url or not integration.api_token:
            raise ServiceImproperlyConfiguredDispatchException(
                "The Jira integration needs its site URL and token first."
            )
        return (
            integration.url.rstrip("/"),
            {
                **JiraIntegrationType().auth_headers(integration),
                "Accept": "application/json",
            },
        )

    def issue_url(self, site_url: str, key: str) -> str:
        return f"{site_url}/browse/{key}"


def _require(resolved_values: Dict[str, Any], name: str, label: str) -> str:
    value = (resolved_values.get(name) or "").strip()
    if not value:
        raise ServiceImproperlyConfiguredDispatchException(f"The {label} is missing.")
    return value


def _labels(value: str) -> List[str]:
    return [label.strip() for label in (value or "").split(",") if label.strip()]


def _issue_fields(resolved_values: Dict[str, Any]) -> Dict[str, Any]:
    """Only what the user filled in, so an update leaves the rest untouched."""

    fields: Dict[str, Any] = {}
    summary = (resolved_values.get("summary") or "").strip()
    if summary:
        fields["summary"] = summary
    description = resolved_values.get("description") or ""
    if description.strip():
        fields["description"] = description
    issue_type = (resolved_values.get("issue_type") or "").strip()
    if issue_type:
        fields["issuetype"] = {"name": issue_type}
    priority = (resolved_values.get("priority") or "").strip()
    if priority:
        fields["priority"] = {"name": priority}
    labels = _labels(resolved_values.get("labels"))
    if labels:
        fields["labels"] = labels
    assignee = (resolved_values.get("assignee") or "").strip()
    if assignee:
        # Cloud identifies people by account id (`5b10ac8d82e05b22cc7d4ef5` or
        # `712020:<uuid>`), Server and Data Center by username.
        is_account_id = ":" in assignee or (
            len(assignee) == 24 and all(c in "0123456789abcdef" for c in assignee)
        )
        fields["assignee"] = (
            {"accountId": assignee} if is_account_id else {"name": assignee}
        )
    return fields


def _issue_output(issue: dict, site_url: str) -> Dict[str, Any]:
    from jira2markdown import convert

    description = get_value_at_path(issue, "fields.description", "") or ""
    if isinstance(description, dict):
        # Only the v3 API answers with a document; v2 gives wiki markup.
        description = _document_to_text(description)
    else:
        try:
            description = convert(description)
        except Exception:  # noqa: BLE001
            description = str(description)
    key = issue.get("key", "")
    return {
        "id": issue.get("id"),
        "key": key,
        "url": f"{site_url}/browse/{key}" if key else "",
        "summary": get_value_at_path(issue, "fields.summary", "") or "",
        "description": description,
        "status": get_value_at_path(issue, "fields.status.name", "") or "",
        "issue_type": get_value_at_path(issue, "fields.issuetype.name", "") or "",
        "priority": get_value_at_path(issue, "fields.priority.name", "") or "",
        "assignee": get_value_at_path(issue, "fields.assignee.displayName", "") or "",
        "reporter": get_value_at_path(issue, "fields.reporter.displayName", "") or "",
        "labels": ", ".join(get_value_at_path(issue, "fields.labels", []) or []),
        "project": get_value_at_path(issue, "fields.project.name", "") or "",
        "created": get_value_at_path(issue, "fields.created", "") or "",
        "updated": get_value_at_path(issue, "fields.updated", "") or "",
        "due_date": get_value_at_path(issue, "fields.duedate", "") or "",
    }


def _document_to_text(node: Any) -> str:
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        inner = "".join(_document_to_text(child) for child in node.get("content", []))
        return inner + ("\n" if node.get("type") == "paragraph" else "")
    if isinstance(node, list):
        return "".join(_document_to_text(child) for child in node)
    return ""


ISSUE_PROPERTIES = {
    "id": string_property("Issue id"),
    "key": string_property("Key"),
    "url": string_property("Link"),
    "summary": string_property("Summary"),
    "description": string_property("Description"),
    "status": string_property("Status"),
    "issue_type": string_property("Issue type"),
    "priority": string_property("Priority"),
    "assignee": string_property("Assignee"),
    "reporter": string_property("Reporter"),
    "labels": string_property("Labels"),
    "project": string_property("Project"),
    "created": string_property("Created"),
    "updated": string_property("Updated"),
    "due_date": string_property("Due date"),
}


class JiraListIssuesServiceType(JiraServiceType):
    type = "jira_list_issues"
    model_class = JiraListIssuesService
    formula_fields = ["jql"]
    plain_fields = ["max_results"]
    # The Cloud search may answer 404 for the old endpoint, so two tries.
    request_count = 2
    schema_properties = {
        "issues": array_property("Issues", ISSUE_PROPERTIES),
        "count": number_property("Count"),
    }

    def dispatch_data(
        self,
        service: JiraListIssuesService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        site_url, headers = self.site(service)
        jql = (resolved_values.get("jql") or "").strip() or "ORDER BY created DESC"
        max_results = max(1, min(service.max_results or 50, MAX_LIST_RESULTS))
        params = {"jql": jql, "maxResults": max_results, "fields": ISSUE_FIELDS}
        # Jira Cloud retired `/search` for `/search/jql`; Server and Data
        # Center only know the former.
        try:
            _, body = self.request_json(
                dispatch_context,
                "GET",
                f"{site_url}/rest/api/2/search/jql",
                headers=headers,
                params=params,
            )
        except RemoteRefusedDispatchException as e:
            if "404" not in str(e):
                raise
            _, body = self.request_json(
                dispatch_context,
                "GET",
                f"{site_url}/rest/api/2/search",
                headers=headers,
                params={**params, "startAt": 0},
            )
        issues = body.get("issues") if isinstance(body, dict) else None
        if issues is None:
            raise RemoteRefusedDispatchException(
                "Jira did not answer with a list of issues."
            )
        output = [
            _issue_output(issue, site_url)
            for issue in issues
            if isinstance(issue, dict)
        ]
        return {"issues": output, "count": len(output)}


class JiraCreateIssueServiceType(JiraServiceType):
    type = "jira_create_issue"
    model_class = JiraCreateIssueService
    formula_fields = [
        "project_key",
        "issue_type",
        "summary",
        "description",
        "priority",
        "labels",
        "assignee",
    ]
    schema_properties = {
        "id": string_property("Issue id"),
        "key": string_property("Key"),
        "url": string_property("Link"),
    }

    def dispatch_data(self, service, resolved_values, dispatch_context):
        site_url, headers = self.site(service)
        project_key = _require(resolved_values, "project_key", "project key")
        _require(resolved_values, "summary", "summary")
        fields = _issue_fields(resolved_values)
        fields["project"] = {"key": project_key}
        fields.setdefault("issuetype", {"name": "Task"})
        _, body = self.request_json(
            dispatch_context,
            "POST",
            f"{site_url}/rest/api/2/issue",
            headers=headers,
            json={"fields": fields},
        )
        body = body if isinstance(body, dict) else {}
        key = body.get("key", "")
        return {"id": body.get("id"), "key": key, "url": self.issue_url(site_url, key)}


class JiraUpdateIssueServiceType(JiraServiceType):
    type = "jira_update_issue"
    model_class = JiraUpdateIssueService
    formula_fields = [
        "issue_key",
        "summary",
        "description",
        "issue_type",
        "priority",
        "labels",
        "assignee",
    ]
    schema_properties = {
        "key": string_property("Key"),
        "url": string_property("Link"),
        "updated": boolean_property("Updated"),
    }

    def dispatch_data(self, service, resolved_values, dispatch_context):
        site_url, headers = self.site(service)
        issue_key = _require(resolved_values, "issue_key", "issue key")
        fields = _issue_fields(resolved_values)
        if not fields:
            raise ServiceImproperlyConfiguredDispatchException(
                "Nothing to change: fill in at least one issue property."
            )
        self.request_json(
            dispatch_context,
            "PUT",
            f"{site_url}/rest/api/2/issue/{quote(issue_key, safe='')}",
            headers=headers,
            json={"fields": fields},
        )
        return {
            "key": issue_key,
            "url": self.issue_url(site_url, issue_key),
            "updated": True,
        }


class JiraDeleteIssueServiceType(JiraServiceType):
    type = "jira_delete_issue"
    model_class = JiraDeleteIssueService
    formula_fields = ["issue_key"]
    schema_properties = {
        "key": string_property("Key"),
        "deleted": boolean_property("Deleted"),
    }

    def dispatch_data(self, service, resolved_values, dispatch_context):
        site_url, headers = self.site(service)
        issue_key = _require(resolved_values, "issue_key", "issue key")
        self.request_json(
            dispatch_context,
            "DELETE",
            f"{site_url}/rest/api/2/issue/{quote(issue_key, safe='')}",
            headers=headers,
            params={"deleteSubtasks": "false"},
        )
        return {"key": issue_key, "deleted": True}
