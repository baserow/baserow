from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.api.user_sources.serializers import UserSourceSerializer
from baserow.core.models import Application
from baserow.core.object_scopes import ApplicationObjectScopeType
from baserow.core.user_sources import signals as user_source_signals
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.object_scopes import UserSourceObjectScopeType
from baserow.core.user_sources.operations import (
    ListUserSourcesApplicationOperationType,
    ReadUserSourceOperationType,
)
from baserow.core.user_sources.registries import user_source_type_registry
from baserow.ws.tasks import broadcast_to_permitted_users


@receiver(user_source_signals.user_source_created)
def user_source_created(
    sender, user_source: UserSource, user: AbstractUser, before_id=None, **kwargs
):
    serializer = user_source_type_registry.get_serializer(
        user_source, UserSourceSerializer
    )
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            user_source.application.workspace_id,
            ReadUserSourceOperationType.type,
            UserSourceObjectScopeType.type,
            user_source.id,
            {
                "type": "user_source_created",
                "user_source": serializer.data,
                "before_id": before_id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(user_source_signals.user_source_updated)
def user_source_updated(sender, user_source: UserSource, user: AbstractUser, **kwargs):
    serializer = user_source_type_registry.get_serializer(
        user_source, UserSourceSerializer
    )
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            user_source.application.workspace_id,
            ReadUserSourceOperationType.type,
            UserSourceObjectScopeType.type,
            user_source.id,
            {
                "type": "user_source_updated",
                "user_source": serializer.data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(user_source_signals.user_source_deleted)
def user_source_deleted(
    sender, user_source_id: int, application: Application, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            application.workspace_id,
            ListUserSourcesApplicationOperationType.type,
            ApplicationObjectScopeType.type,
            application.id,
            {
                "type": "user_source_deleted",
                "user_source_id": user_source_id,
                "application_id": application.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )
