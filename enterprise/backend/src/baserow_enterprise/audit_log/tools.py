"""
Audit log tools shared by the clients that act for a user. They only read the audit
log of the context's workspace.
"""

from datetime import datetime, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q, QuerySet
from django.utils import timezone as django_timezone

from pydantic import Field

from baserow.core.subjects import UserSubjectType
from baserow.core.tools import ToolContext
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.audit_log.utils import (
    check_for_license_and_permissions_or_raise,
)

MAX_PAGE_SIZE = 100
MAX_SEARCH_DAYS = 90


def _timezone(ctx: ToolContext) -> ZoneInfo:
    return ZoneInfo(ctx.timezone or "UTC")


def _aware(ctx: ToolContext, value: datetime) -> datetime:
    """A timestamp without an offset is in the timezone of the context."""

    if django_timezone.is_naive(value):
        return django_timezone.make_aware(value, _timezone(ctx))
    return value


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
                "ip_address": entry.ip_address,
            }
            for entry in found[:size]
        ],
        "has_more": len(found) > size,
    }


def list_audit_log(
    ctx: ToolContext,
    user_id: Annotated[
        int | None, Field(description="Only what this user did, by user ID.")
    ] = None,
    action_types: Annotated[
        list[str] | None,
        Field(description="Only these actions, like create_table or delete_rows."),
    ] = None,
    from_timestamp: Annotated[
        datetime | None,
        Field(
            description=(
                "Only from this moment, in ISO format. Without an offset it is in the "
                "user's timezone."
            )
        ),
    ] = None,
    to_timestamp: Annotated[
        datetime | None,
        Field(description="Only up to this moment, in the same format."),
    ] = None,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of entries a page."),
    ] = 50,
) -> dict[str, Any]:
    """
    List what happened in this workspace, newest first: who did what and when. Needs
    an enterprise licence and a workspace admin.
    """

    entries = _workspace_entries(ctx)
    if user_id is not None:
        # An agent can have the same id as a user.
        entries = entries.filter(actor_id=user_id, actor_type=UserSubjectType.type)
    if action_types:
        entries = entries.filter(action_type__in=action_types)
    if from_timestamp is not None:
        entries = entries.filter(action_timestamp__gte=_aware(ctx, from_timestamp))
    if to_timestamp is not None:
        entries = entries.filter(action_timestamp__lte=_aware(ctx, to_timestamp))

    return _page(ctx, entries, page, size)


def search_audit_log(
    ctx: ToolContext,
    query: Annotated[
        str,
        Field(
            min_length=2,
            max_length=200,
            description=(
                "Text to find, ignoring case, in who did it, the action type and the "
                "action's short description. It matches literally, so use one short "
                "word like delete, not deleted or a phrase."
            ),
        ),
    ],
    from_timestamp: Annotated[
        datetime,
        Field(
            description=(
                "The start of the range, in ISO format. Without an offset it is in "
                "the user's timezone."
            )
        ),
    ],
    to_timestamp: Annotated[
        datetime,
        Field(description="The end of the range, at most 90 days after the start."),
    ],
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of entries a page."),
    ] = 50,
) -> dict[str, Any]:
    """
    Search what happened in this workspace within a date range of at most 90 days,
    newest first. It doesn't search the names of the things that changed, like a
    table's name. No result doesn't prove nothing happened: try another word or
    list_audit_log. Needs an enterprise licence and a workspace admin.
    """

    entries = _workspace_entries(ctx)
    start = _aware(ctx, from_timestamp)
    end = _aware(ctx, to_timestamp)
    if end < start:
        raise DjangoValidationError("to_timestamp must be after from_timestamp.")
    if end - start > timedelta(days=MAX_SEARCH_DAYS):
        raise DjangoValidationError(
            f"The date range can be at most {MAX_SEARCH_DAYS} days."
        )

    entries = entries.filter(
        Q(actor_name__icontains=query)
        | Q(action_type__icontains=query)
        | Q(original_action_short_descr__icontains=query),
        action_timestamp__range=(start, end),
    )
    return _page(ctx, entries, page, size)
