from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.integrations.models import Integration
from baserow.core.mixins import (
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)


def get_default_service_service():
    return ContentType.objects.get_for_model(Integration)


class Service(
    PolymorphicContentTypeMixin,
    WithRegistry,
    TrashableModelMixin,
    models.Model,
):
    """
    An integration service represents one of the services provided by a particular
    external integration.
    It is linked to an integration that contains the configuration required to use
    the associated external service.
    An integration service can be associated with an application or with specific
    objects (such as a page for AB or a node for WA), depending on the integration's
    scope.
    """

    integration = models.ForeignKey(
        Integration,
        related_name="services",
        on_delete=models.SET_NULL,
        null=True,
        help_text="The integration used to establish the connection with the service.",
    )

    content_type = models.ForeignKey(
        ContentType,
        related_name="services",
        on_delete=models.SET(get_default_service_service),
    )

    sample_data = models.JSONField(
        default=None,
        blank=True,
        null=True,
        help_text="Store the sample data used for generating a schema.",
    )

    class Meta:
        ordering = ("id",)

    @staticmethod
    def get_type_registry():
        from .registries import service_type_registry

        return service_type_registry


class SearchableServiceMixin(models.Model):
    """
    A mixin which can be applied to Services to denote that they're searchable,
    and to add a `search_query` field to it.
    """

    search_query = FormulaField(
        help_text="The query to apply to the service to narrow the results down.",
    )

    class Meta:
        abstract = True


class ServiceFilter(HierarchicalModelMixin):
    """
    An abstract Model which service subclass's filter model can inherit from.
    """

    service = models.ForeignKey(
        Service,
        related_name="service_filters",
        help_text="The service which this filter belongs to.",
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True

    def get_parent(self):
        return self.service


class ServiceSort(HierarchicalModelMixin):
    """
    An abstract Model which service subclass's sort model can inherit from.
    """

    service = models.ForeignKey(
        Service,
        related_name="service_sorts",
        help_text="The service which this sort belongs to.",
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True

    def get_parent(self):
        return self.service
