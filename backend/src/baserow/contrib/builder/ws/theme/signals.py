from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.object_scopes import BuilderObjectScopeType
from baserow.contrib.builder.theme import signals as theme_signals
from baserow.contrib.builder.theme.operations import UpdateThemeOperationType
from baserow.ws.tasks import broadcast_to_permitted_users


@receiver(theme_signals.theme_updated)
def theme_updated(
    sender, builder: Builder, user: AbstractUser, properties: dict, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            builder.workspace_id,
            UpdateThemeOperationType.type,
            BuilderObjectScopeType.type,
            builder.id,
            {
                "type": "theme_updated",
                "builder_id": builder.id,
                "properties": properties,
            },
            getattr(user, "web_socket_id", None),
        )
    )
