from django.db import models

from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowFilterableServiceMixin,
    LocalBaserowViewService,
)
from baserow.core.services.models import Service


class LocalBaserowGroupedAggregateRows(
    LocalBaserowViewService, LocalBaserowFilterableServiceMixin
):
    """
    A model for the local baserow grouped aggregate rows
    service configuration data.
    """

    ...


class LocalBaserowTableServiceAggregationSeries(models.Model):
    """
    An aggregation series applicable to a `LocalBaserowTableService`
    integration service.
    """

    service = models.ForeignKey(
        Service,
        related_name="service_aggregation_series",
        help_text="The service which this aggregation series belongs to.",
        on_delete=models.CASCADE,
    )
    field = models.ForeignKey(
        "database.Field",
        help_text="The aggregated field.",
        null=True,
        on_delete=models.CASCADE,
    )
    aggregation_type = models.CharField(
        default="", blank=True, max_length=48, help_text="The field aggregation type."
    )

    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order", "id")


class LocalBaserowTableServiceAggregationGroupBy(models.Model):
    """
    A group by for aggregations applicable to a `LocalBaserowTableService`
    integration service.
    """

    service = models.ForeignKey(
        Service,
        related_name="service_aggregation_group_bys",
        help_text="The service which this aggregation series belongs to.",
        on_delete=models.CASCADE,
    )
    field = models.ForeignKey(
        "database.Field",
        help_text="The field to use in group by.",
        null=True,
        on_delete=models.CASCADE,
    )
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order", "id")


class SortOn(models.TextChoices):
    SERIES = "SERIES", "Series"
    GROUP_BY = "GROUP_BY", "Group by"
    PRIMARY = "PRIMARY", "Primary"


class SortDirection(models.TextChoices):
    ASCENDING = "ASC", "Ascending"
    DESCENDING = "DESC", "Descending"


class LocalBaserowTableServiceAggregationSortBy(models.Model):
    """
    A sort by for aggregations applicable to a `LocalBaserowTableService`
    integration service.
    """

    service = models.ForeignKey(
        Service,
        related_name="service_aggregation_sorts",
        help_text="The service which this aggregation series belongs to.",
        on_delete=models.CASCADE,
    )
    sort_on = models.CharField(max_length=255, choices=SortOn.choices)
    reference = models.CharField(max_length=255)
    direction = models.CharField(max_length=255, choices=SortDirection.choices)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order", "id")
