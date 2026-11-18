"""
Audit log tools shared by the clients that act for a user. They only read the audit
log of the context's workspace.
"""

from datetime import timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q, QuerySet
from django.utils import timezone as django_timezone

from pydantic import AwareDatetime, Field, StringConstraints

from baserow.core.subjects import UserSubjectType
from baserow.core.tools import ToolContext, tool_execution
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.audit_log.utils import (
    check_for_license_and_permissions_or_raise,
)

MAX_PAGE_SIZE = 100
MAX_SEARCH_DAYS = 90

SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=200),
    Field(
        description=(
            "Text to find, ignoring case, in who did it, the action type and the "
            "action's short description. It matches literally, so use one short "
            "word like delete, not deleted or a phrase. A search covers at most 90 "
            "days, the last 90 unless from_timestamp or to_timestamp says otherwise. "
            "It doesn't search the names of the things that changed, like a table's "
            "name, and no result doesn't prove nothing happened."
        )
    ),
]


def _timezone(ctx: ToolContext) -> ZoneInfo:
    # Kuma takes the timezone from what the browser reports, without checking it.
    try:
        return ZoneInfo(ctx.timezone or "UTC")
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return ZoneInfo("UTC")


def _workspace_entries(ctx: ToolContext) -> QuerySet[AuditLogEntry]:
    check_for_license_and_permissions_or_raise(ctx.user, ctx.workspace.id)
    return AuditLogEntry.objects.filter(workspace_id=ctx.workspace.id)


def _page(
    ctx: ToolContext, entries: QuerySet[AuditLogEntry], page: int, size: int
) -> dict[str, Any]:
    start = (page - 1) * size
    # One more than the page, to know if another follows without counting them all.
    found = list(entries.order_by("-action_timestamp", "-id")[start : start + size + 1])
    timezone = _timezone(ctx)

    return {
        "entries": [
            {
                "id": entry.id,
                "timestamp": entry.action_timestamp.astimezone(timezone).isoformat(),
                "actor": {
                    "id": entry.actor_id,
                    "type": entry.actor_type,
                    "name": entry.actor_name,
                },
                "action_type": entry.action_type,
                "description": str(entry.description),
            }
            for entry in found[:size]
        ],
        "has_more": len(found) > size,
    }


@tool_execution
def list_audit_log(
    ctx: ToolContext,
    query: SearchQuery | None = None,
    user_id: Annotated[
        int | None, Field(description="Only what this user did, by user ID.")
    ] = None,
    action_types: Annotated[
        list[str] | None,
        Field(description="Only these actions, like create_table or delete_rows."),
    ] = None,
    from_timestamp: Annotated[
        AwareDatetime | None,
        Field(
            description=(
                "Only from this moment, in ISO format with the offset of the user's "
                "timezone, like 2026-11-02T09:00:00+01:00."
            )
        ),
    ] = None,
    to_timestamp: Annotated[
        AwareDatetime | None,
        Field(description="Only up to this moment, in the same format."),
    ] = None,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of entries a page."),
    ] = 50,
) -> dict[str, Any]:
    """
    List what happened in this workspace, newest first: who did what and when, with
    an optional text search. Needs an advanced or enterprise licence and a workspace
    admin.
    """

    entries = _workspace_entries(ctx)
    if user_id is not None:
        # An agent can have the same id as a user.
        entries = entries.filter(actor_id=user_id, actor_type=UserSubjectType.type)
    if action_types:
        entries = entries.filter(action_type__in=action_types)

    if query:
        search_days = timedelta(days=MAX_SEARCH_DAYS)
        to_timestamp = to_timestamp or (
            from_timestamp + search_days if from_timestamp else django_timezone.now()
        )
        from_timestamp = from_timestamp or to_timestamp - search_days
        if to_timestamp - from_timestamp > search_days:
            raise DjangoValidationError(
                f"A search can cover at most {MAX_SEARCH_DAYS} days."
            )
        entries = entries.filter(
            Q(actor_name__icontains=query)
            | Q(action_type__icontains=query)
            | Q(original_action_short_descr__icontains=query)
        )

    if from_timestamp and to_timestamp and to_timestamp < from_timestamp:
        raise DjangoValidationError("to_timestamp must be after from_timestamp.")
    if from_timestamp:
        entries = entries.filter(action_timestamp__gte=from_timestamp)
    if to_timestamp:
        entries = entries.filter(action_timestamp__lte=to_timestamp)

    return _page(ctx, entries, page, size)
