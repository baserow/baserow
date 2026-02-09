from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.builder.api.data_sources.serializers import DataSourceSerializer
from baserow.contrib.builder.data_sources import signals as data_source_signals
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.object_scopes import (
    BuilderDataSourceObjectScopeType,
)
from baserow.contrib.builder.data_sources.operations import (
    ListDataSourcesPageOperationType,
    ReadDataSourceOperationType,
)
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.object_scopes import BuilderPageObjectScopeType
from baserow.core.services.registries import service_type_registry
from baserow.ws.tasks import broadcast_to_permitted_users


@receiver(data_source_signals.data_source_created)
def data_source_created(
    sender, data_source: DataSource, user: AbstractUser, before_id=None, **kwargs
):
    if data_source.service:
        serializer = service_type_registry.get_serializer(
            data_source.service,
            DataSourceSerializer,
            context={"data_source": data_source},
        )
    else:
        serializer = DataSourceSerializer(
            data_source, context={"data_source": data_source}
        )

    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            data_source.page.builder.workspace_id,
            ReadDataSourceOperationType.type,
            BuilderDataSourceObjectScopeType.type,
            data_source.id,
            {
                "type": "data_source_created",
                "data_source": serializer.data,
                "before_id": before_id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(data_source_signals.data_source_updated)
def data_source_updated(sender, data_source: DataSource, user: AbstractUser, **kwargs):
    if data_source.service:
        serializer = service_type_registry.get_serializer(
            data_source.service,
            DataSourceSerializer,
            context={"data_source": data_source},
        )
    else:
        serializer = DataSourceSerializer(
            data_source, context={"data_source": data_source}
        )

    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            data_source.page.builder.workspace_id,
            ReadDataSourceOperationType.type,
            BuilderDataSourceObjectScopeType.type,
            data_source.id,
            {
                "type": "data_source_updated",
                "data_source": serializer.data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(data_source_signals.data_source_deleted)
def data_source_deleted(
    sender, data_source_id: int, page: Page, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            page.builder.workspace_id,
            ListDataSourcesPageOperationType.type,
            BuilderPageObjectScopeType.type,
            page.id,
            {
                "type": "data_source_deleted",
                "data_source_id": data_source_id,
                "page_id": page.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )
