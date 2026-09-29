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

# Mirrors `baserow.contrib.database.fields.field_filters.FILTER_TYPE_{AND,OR}` and
# `views.models.FILTER_TYPES`. Redefined here as plain literals to avoid importing the
# `contrib.database` filter modules into `core`, which would cause a circular import
# (`core.models` is loaded before `contrib.database`).
SERVICE_FILTER_TYPE_AND = "AND"
SERVICE_FILTER_TYPE_OR = "OR"
SERVICE_FILTER_TYPES = (
    (SERVICE_FILTER_TYPE_AND, "And"),
    (SERVICE_FILTER_TYPE_OR, "Or"),
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


class ServiceFilterGroup(HierarchicalModelMixin):
    """
    An abstract Model which service subclass's filter group model can inherit from.

    A filter group allows service filters to be nested and combined with their own
    `AND`/`OR` operator, independently from the service's top-level operator. Groups
    can themselves be nested via `parent_group` (a `parent_group` of `None` denotes a
    top-level group directly under the service).
    """

    filter_type = models.CharField(
        max_length=3,
        choices=SERVICE_FILTER_TYPES,
        default=SERVICE_FILTER_TYPE_AND,
        help_text="Indicates whether all the rows should apply to all filters (AND) "
        "or to any filter (OR) in the group to be shown.",
    )
    parent_group = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        default=None,
        help_text="The parent filter group, allowing groups to be nested. If null, "
        "the group is directly under the service.",
    )
    service = models.ForeignKey(
        Service,
        related_name="service_filter_groups",
        help_text="The service which this filter group belongs to.",
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
