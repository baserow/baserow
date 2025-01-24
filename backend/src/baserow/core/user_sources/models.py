import uuid
from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.integrations.models import Integration
from baserow.core.mixins import (
    FractionOrderableMixin,
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)

if TYPE_CHECKING:
    from baserow.core.models import Application


def get_default_user_source():
    return ContentType.objects.get_for_model(UserSource)


def gen_uuid():
    return uuid.uuid4().hex


class UserSource(
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
    FractionOrderableMixin,
    TrashableModelMixin,
    models.Model,
):
    """
    UserSources provide a way to configure user authentication source within an
    application like the Application Builder.

    A user_source can be associated with an application, and it stores the data
    required to use the corresponding external service. This data may include an API
    key for accessing an external database service, a user account for querying a
    Baserow database, as well as the necessary URL, credentials, and headers for making
    an API call.
    """

    application = models.ForeignKey(
        "core.Application", on_delete=models.CASCADE, related_name="user_sources"
    )
    name = models.CharField(max_length=255)
    integration = models.ForeignKey(
        Integration,
        related_name="user_sources",
        on_delete=models.SET_NULL,
        null=True,
        help_text="The Integration used to establish the connection with the service.",
    )
    order = models.DecimalField(
        help_text="Lowest first.",
        max_digits=40,
        decimal_places=20,
        editable=False,
        default=1,
    )
    content_type = models.ForeignKey(
        ContentType,
        related_name="user_sources",
        on_delete=models.SET(get_default_user_source),
    )
    uid = models.TextField(
        default=gen_uuid,
        editable=False,
        unique=True,
        null=False,
        help_text="Unique id for this user source.",
    )

    @staticmethod
    def get_type_registry():
        from .registries import user_source_type_registry

        return user_source_type_registry

    class Meta:
        ordering = ("order", "id")

    def get_parent(self):
        return self.application

    @classmethod
    def get_last_order(cls, application: "Application"):
        """
        Returns the last order for the given application.

        :param application: The application we want the order for.
        :return: The last order.
        """

        queryset = UserSource.objects.filter(application=application)
        return cls.get_highest_order_of_queryset(queryset)[0]

    @classmethod
    def get_unique_order_before_user_source(cls, before: "UserSource"):
        """
        Returns a safe order value before the given user_source in the given
        application.

        :param application: The application we want the order for.
        :param before: The user_source before which we want the safe order
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the items must be recalculated in this
            case before calling this method again.
        :return: The order value.
        """

        queryset = UserSource.objects.filter(application=before.application)
        return cls.get_unique_orders_before_item(before, queryset)[0]
