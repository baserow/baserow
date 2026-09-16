from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import connection, transaction
from django.db.models import Exists, Max, OuterRef, Q, QuerySet
from django.utils import timezone

from loguru import logger
from rest_framework import serializers

from baserow.core.handler import CoreHandler
from baserow.core.psycopg import sql
from baserow.core.registries import (
    LastViewedItemType,
    last_viewed_item_type_registry,
)
from baserow.core.user.utils import is_user_impersonated

from .models import UserLastViewedItem
from .tasks import mark_item_viewed

# Small enough to keep every delete transaction short, so a sweep over a large
# table never holds locks for long.
DELETE_BATCH_SIZE = 10_000

# How many rows the first batch of a listing reads. Large enough that one batch
# serves a page in every normal case, small enough to stay cheap when it does not.
SCAN_BATCH_SIZE = 200
MAX_SCAN_BATCH_SIZE = 5_000

# How deep the listing pages. Every item before the offset has to be resolved to
# know which ones follow it, so paging on forever would let one request walk an
# entire history. The listing reports no more items once this depth is reached,
# which is far beyond what answering "what was I working on" needs.
MAX_LISTED_ITEMS = 400

# Stateless for `to_representation`, so one instance serves every caller.
_LAST_VIEWED_FIELD = serializers.DateTimeField()

# The floor is applied by the database itself, so refreshing a fresh row is a
# single statement. A rejected update is not free though: it still locks the
# row and consumes a transaction id and a sequence value, which is why the task
# keeps its lock for the whole interval and such runs stay rare.
UPSERT_SQL = sql.SQL(
    """
    INSERT INTO {table}
        (user_id, item_type, item_id, application_id, workspace_id, last_viewed)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id, item_type, item_id) DO UPDATE SET
        last_viewed = EXCLUDED.last_viewed,
        application_id = EXCLUDED.application_id,
        workspace_id = EXCLUDED.workspace_id
    WHERE {table}.last_viewed < EXCLUDED.last_viewed - %s
    """
).format(table=sql.Identifier(UserLastViewedItem._meta.db_table))


@dataclass(frozen=True)
class LastViewedUpdate:
    application_id: int
    workspace_id: int
    last_viewed: datetime


@dataclass(frozen=True)
class LastViewedListItem:
    """
    One entry of the recently viewed listing: the stored row together with the
    resolved item, so the serializer never has to query again.
    """

    row: UserLastViewedItem
    item_type: LastViewedItemType
    instance: Any
    sub_type: Optional[str]


# Optional sub types per item type, `None` meaning every item of that type.
LastViewedTypeFilters = Dict[str, Optional[Iterable[str]]]


class LastViewedHandler:
    @classmethod
    def serialize_last_viewed(cls, value: Optional[datetime]) -> Optional[str]:
        """
        The representation of the REST API, used by the realtime payloads too so
        the frontend can compare values from both sources.

        :param value: The stored moment, or `None` when never viewed.
        :return: The ISO 8601 string, or `None`.
        """

        return _LAST_VIEWED_FIELD.to_representation(value)

    @classmethod
    def schedule_mark_viewed(
        cls, user: AbstractUser, item_type: str, item_id: int
    ) -> None:
        """
        Called from the request path, so it must never touch the database. The write
        is deferred to a debounced celery task after the transaction commits.

        :param user: The user that opened the item, anonymous when browsing a
            template.
        :param item_type: The type of a registered `LastViewedItemType`.
        :param item_id: The id of the item that was opened.
        """

        # The "loaded" endpoints are open to anonymous visitors of template
        # workspaces, which have nothing to track. A support session that
        # impersonates the user must not reorder their recent items either.
        if not user.is_authenticated or is_user_impersonated(user):
            return

        user_id = user.id
        # Captured here rather than in the worker, so a queue delay can't make an
        # earlier visit look more recent than a later one.
        viewed_at = timezone.now().isoformat()

        def enqueue():
            try:
                mark_item_viewed.apply_async(
                    args=(user_id, item_type, item_id, viewed_at),
                    countdown=settings.BASEROW_LAST_VIEWED_DEBOUNCE_SECONDS,
                )
            except Exception:
                # Tracking is a side effect of a page load that already succeeded,
                # so a broker or lock backend outage must not turn it into an error.
                logger.exception("Could not schedule the last viewed update.")

        transaction.on_commit(enqueue)

    @classmethod
    def mark_viewed(
        cls, user_id: int, item_type: str, item_id: int, viewed_at: datetime
    ) -> Optional[LastViewedUpdate]:
        """
        Stores the moment of the visit in two queries: one resolving the item
        through the type's queryset, which also enforces that the user may see it,
        and one upsert that only writes when the stored value is older than
        `BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS` before the visit. A visit
        that arrives late for an item that was opened again since is left out by
        that same condition.

        :param user_id: The id of the user that opened the item.
        :param item_type: The type of a registered `LastViewedItemType`.
        :param item_id: The id of the item that was opened.
        :param viewed_at: When the item was opened.
        :return: What was stored, or `None` when nothing changed because the item
            is gone, not visible to the user, or was viewed recently enough.
        """

        item_type_obj = last_viewed_item_type_registry.get(item_type)
        instance = (
            item_type_obj.get_queryset_for_user(user_id).filter(id=item_id).first()
        )
        if instance is None:
            return None

        update = LastViewedUpdate(
            application_id=item_type_obj.get_application_id(instance),
            workspace_id=item_type_obj.get_workspace_id(instance),
            last_viewed=viewed_at,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                UPSERT_SQL,
                [
                    user_id,
                    item_type,
                    item_id,
                    update.application_id,
                    update.workspace_id,
                    update.last_viewed,
                    timedelta(
                        seconds=settings.BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS
                    ),
                ],
            )
            changed = cursor.rowcount > 0
        return update if changed else None

    @classmethod
    def get_last_viewed_per_application(
        cls, user: AbstractUser, application_ids: Iterable[int]
    ) -> Dict[int, datetime]:
        """
        Single query on the (user, application) index, so the cost does not grow
        with the number of workspaces or application types.

        :param user: The user to get the values for.
        :param application_ids: The ids of the applications to look up.
        :return: A dict mapping the application id to the most recent moment the
            user viewed one of its items. Applications never viewed are absent.
        """

        return cls.get_last_viewed_per_user_and_application(
            application_ids, [user.id]
        ).get(user.id, {})

    @classmethod
    def get_last_viewed_per_user_and_application(
        cls, application_ids: Iterable[int], user_ids: Optional[Iterable[int]] = None
    ) -> Dict[int, Dict[int, datetime]]:
        """
        Used by realtime broadcasts, which carry a personal payload per recipient
        but must not run a query per recipient.

        :param application_ids: The ids of the applications to look up.
        :param user_ids: Optionally limits the users, otherwise everyone who viewed
            one of the applications is included.
        :return: A dict mapping the user id to the result of
            `get_last_viewed_per_application` for that user.
        """

        application_ids = list(application_ids)
        if not application_ids:
            return {}

        queryset = UserLastViewedItem.objects.filter(application_id__in=application_ids)
        if user_ids is not None:
            queryset = queryset.filter(user_id__in=user_ids)

        result: Dict[int, Dict[int, datetime]] = {}
        for user_id, application_id, last_viewed in (
            queryset.values("user_id", "application_id")
            .annotate(last_viewed=Max("last_viewed"))
            .values_list("user_id", "application_id", "last_viewed")
        ):
            result.setdefault(user_id, {})[application_id] = last_viewed
        return result

    @classmethod
    def list_items(
        cls,
        user: AbstractUser,
        *,
        workspace_ids: Optional[Iterable[int]] = None,
        type_filters: Optional[LastViewedTypeFilters] = None,
        limit: int,
        offset: int = 0,
    ) -> Tuple[List[LastViewedListItem], bool]:
        """
        Lists the items the user opened most recently, newest first.

        The rows are walked newest first in batches and the visibility of a batch is
        resolved separately, because asking the permission managers for every
        workspace of the user at once makes the statement grow with the number of
        workspaces they are a member of: a batch only spans the few workspaces it
        actually contains. The rows of a batch are read as tuples, so looking past
        items that no longer exist never instantiates them.

        :param user: The user whose history is listed.
        :param workspace_ids: Limits the result to these workspaces. Workspaces the
            user is not a member of are silently ignored.
        :param type_filters: Limits the result to these item types, each optionally
            limited to sub types. Every registered type when omitted.
        :param limit: The maximum number of items to return.
        :param offset: The number of visible items to skip.
        :return: The items of the page and whether more items follow.
        """

        core_handler = CoreHandler()
        # The enhanced queryset prefetches the memberships, which keeps the
        # permission managers from querying once per workspace.
        workspace_queryset = core_handler.list_user_workspaces(user)
        if workspace_ids is not None:
            workspace_queryset = workspace_queryset.filter(id__in=workspace_ids)
        workspaces = {workspace.id: workspace for workspace in workspace_queryset}
        # Without workspaces the permission filtering would run globally instead of
        # denying everything, so it must not be reached.
        if not workspaces:
            return [], False

        if type_filters is None:
            type_filters = {
                item_type.type: None
                for item_type in last_viewed_item_type_registry.get_all()
            }

        candidates = UserLastViewedItem.objects.filter(
            user_id=user.id,
            workspace_id__in=list(workspaces),
            item_type__in=list(type_filters),
        ).order_by("-last_viewed", "-id")

        # One more than requested tells whether a next page exists without a count.
        end = min(offset + limit, MAX_LISTED_ITEMS)
        wanted = end + 1
        visible: List[Tuple[int, str, int]] = []
        cursor = None
        batch_size = SCAN_BATCH_SIZE
        while len(visible) < wanted:
            batch_queryset = candidates
            if cursor is not None:
                last_viewed, row_id = cursor
                batch_queryset = batch_queryset.filter(
                    Q(last_viewed__lt=last_viewed)
                    | Q(last_viewed=last_viewed, id__lt=row_id)
                )
            batch = list(
                batch_queryset.values_list(
                    "id", "item_type", "item_id", "workspace_id", "last_viewed"
                )[:batch_size]
            )
            if not batch:
                break

            visible.extend(
                cls._filter_visible_rows(
                    core_handler, user, batch, type_filters, workspaces
                )
            )
            if len(batch) < batch_size:
                break

            cursor = (batch[-1][4], batch[-1][0])
            # Most pages are served by the first batch. Growing the next ones keeps
            # the number of round trips low when a user has many items they can no
            # longer see, without reading far ahead for everyone else.
            batch_size = min(batch_size * 2, MAX_SCAN_BATCH_SIZE)

        page = visible[offset:end]
        # Nothing follows the last item the listing pages to, so the caller is not
        # invited to ask for a page it would be refused.
        has_more = len(visible) > end and end < MAX_LISTED_ITEMS
        if not page:
            return [], has_more

        rows = UserLastViewedItem.objects.filter(
            id__in=[row_id for row_id, _, _ in page]
        ).select_related("application", "workspace")
        rows_by_id = {row.id: row for row in rows}

        item_ids_per_type = defaultdict(list)
        for _, type_name, item_id in page:
            item_ids_per_type[type_name].append(item_id)

        instances = {}
        for type_name, item_ids in item_ids_per_type.items():
            item_type = last_viewed_item_type_registry.get(type_name)
            queryset = item_type.enhance_list_queryset(
                item_type.get_visible_queryset()
            ).filter(id__in=item_ids)
            for instance in queryset:
                instances[(type_name, instance.id)] = instance

        items = []
        for row_id, type_name, item_id in page:
            row = rows_by_id.get(row_id)
            instance = instances.get((type_name, item_id))
            # Gone between the queries, which the next page load corrects.
            if row is None or instance is None:
                continue
            item_type = last_viewed_item_type_registry.get(type_name)
            items.append(
                LastViewedListItem(
                    row=row,
                    item_type=item_type,
                    instance=instance,
                    sub_type=item_type.get_sub_type(instance),
                )
            )
        return items, has_more

    @classmethod
    def _filter_visible_rows(
        cls,
        core_handler: CoreHandler,
        user: AbstractUser,
        batch: List[Tuple],
        type_filters: LastViewedTypeFilters,
        workspaces: Dict[int, Any],
    ) -> List[Tuple[int, str, int]]:
        """
        Resolves which rows of one batch point at an item the user can still open, in
        one query per item type of the batch. Items that were trashed or that
        permissions hide are left out, so they never occupy a slot of a page.

        :param core_handler: Reused so its per request caches are shared.
        :param user: The user whose history is listed.
        :param batch: Tuples of `(id, item_type, item_id, workspace_id, last_viewed)`,
            newest first.
        :param type_filters: The requested types and sub types.
        :param workspaces: The workspaces of the user, keyed by id.
        :return: The `(id, item_type, item_id)` of the visible rows, in batch order.
        """

        item_ids_per_type = defaultdict(list)
        batch_workspace_ids = set()
        for _, type_name, item_id, workspace_id, _ in batch:
            item_ids_per_type[type_name].append(item_id)
            batch_workspace_ids.add(workspace_id)
        batch_workspaces = [workspaces[id] for id in batch_workspace_ids]

        visible_ids_per_type = {}
        for type_name, item_ids in item_ids_per_type.items():
            item_type = last_viewed_item_type_registry.get(type_name)
            queryset = item_type.get_visible_queryset().filter(id__in=item_ids)
            sub_types = type_filters.get(type_name)
            if sub_types:
                queryset = item_type.filter_queryset_by_sub_types(queryset, sub_types)
            queryset = core_handler.filter_queryset_for_workspaces(
                user, item_type.list_operation_type, queryset, batch_workspaces
            )
            visible_ids_per_type[type_name] = set(queryset.values_list("id", flat=True))

        return [
            (row_id, type_name, item_id)
            for row_id, type_name, item_id, _, _ in batch
            if item_id in visible_ids_per_type[type_name]
        ]

    @classmethod
    def delete_for_user_in_workspace(cls, user_id: int, workspace_id: int) -> int:
        """
        A user who is removed from a workspace should not carry what they last
        opened there back in when they are invited again.

        :param user_id: The id of the user that lost access.
        :param workspace_id: The id of the workspace the user lost access to.
        :return: The number of deleted rows.
        """

        return UserLastViewedItem.objects.filter(
            user_id=user_id, workspace_id=workspace_id
        ).delete()[0]

    @classmethod
    def delete_items(cls, item_type: str, item_ids: Iterable[int]) -> int:
        """
        Deletes the rows of every user for the given items.

        :param item_type: The type of a registered `LastViewedItemType`.
        :param item_ids: The ids of the items that no longer exist.
        :return: The number of deleted rows.
        """

        return UserLastViewedItem.objects.filter(
            item_type=item_type, item_id__in=item_ids
        ).delete()[0]

    @classmethod
    def delete_stale_items(cls) -> int:
        """
        Safety net for rows whose item disappeared without passing through the
        permanent deletion hooks, or whose type is no longer registered.

        :return: The number of deleted rows.
        """

        deleted = 0
        registered_types = []
        for item_type in last_viewed_item_type_registry.get_all():
            registered_types.append(item_type.type)
            existing = item_type.get_existing_item_ids_queryset().filter(
                id=OuterRef("item_id")
            )
            deleted += cls._delete_in_batches(
                UserLastViewedItem.objects.filter(item_type=item_type.type).exclude(
                    Exists(existing)
                )
            )

        deleted += cls._delete_in_batches(
            UserLastViewedItem.objects.exclude(item_type__in=registered_types)
        )
        return deleted

    @classmethod
    def _delete_in_batches(cls, queryset: QuerySet) -> int:
        """
        Deletes the matching rows by primary key in batches. Only used by the
        periodic sweep, which runs in autocommit, so every batch commits on its own
        and a large deletion never blocks the writers for long.

        :param queryset: The rows to delete.
        :return: The number of deleted rows.
        """

        deleted = 0
        while ids := list(queryset.values_list("id", flat=True)[:DELETE_BATCH_SIZE]):
            deleted += UserLastViewedItem.objects.filter(id__in=ids).delete()[0]
            if len(ids) < DELETE_BATCH_SIZE:
                break
        return deleted
