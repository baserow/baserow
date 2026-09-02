from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import connection, transaction
from django.db.models import Exists, Max, OuterRef, QuerySet
from django.utils import timezone

from loguru import logger
from rest_framework import serializers

from baserow.core.psycopg import sql
from baserow.core.registries import last_viewed_item_type_registry

from .models import UserLastViewedItem
from .tasks import mark_item_viewed

# Small enough to keep every delete transaction short, so a sweep over a large
# table never holds locks for long.
DELETE_BATCH_SIZE = 10_000

# Stateless for `to_representation`, so one instance serves every caller.
_LAST_VIEWED_FIELD = serializers.DateTimeField()

# The floor is applied by the database itself, so refreshing a fresh row costs a
# single statement that touches nothing.
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
        # workspaces, which have nothing to track.
        if not user.is_authenticated:
            return

        user_id = user.id

        def enqueue():
            try:
                mark_item_viewed.apply_async(
                    args=(user_id, item_type, item_id),
                    countdown=settings.BASEROW_LAST_VIEWED_DEBOUNCE_SECONDS,
                )
            except Exception:
                # Tracking is a side effect of a page load that already succeeded,
                # so a broker or lock backend outage must not turn it into an error.
                logger.exception("Could not schedule the last viewed update.")

        transaction.on_commit(enqueue)

    @classmethod
    def mark_viewed(
        cls, user_id: int, item_type: str, item_id: int
    ) -> Optional[LastViewedUpdate]:
        """
        Stores `now` as the last viewed timestamp in two queries: one resolving the
        item through the type's queryset, which also enforces that the user may see
        it, and one upsert that only writes when the stored value is older than
        `BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS`.

        :param user_id: The id of the user that opened the item.
        :param item_type: The type of a registered `LastViewedItemType`.
        :param item_id: The id of the item that was opened.
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
            last_viewed=timezone.now(),
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
