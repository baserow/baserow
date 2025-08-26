from datetime import timedelta

from django.db import models

from baserow.contrib.database.field_rules.models import FieldRule
from baserow_enterprise.date_dependency.types import DateDepenencyDict


class DependencyLinkrowType(models.TextChoices):
    """
    Describes the direction for a linkrow field in date dependency (whether current
    row's linkrow field keeps children or parents).
    """

    PREDECESSORS = "predecessors"
    SUCCESSORS = "successors"


class DependencyConnectionType(models.TextChoices):
    """
    Describes which field from parent are updating which field in child.

    By default it's end-to-start, so the end date of a parent will update start date
    of a child
    """

    END_TO_START = "end-to-start"
    END_TO_END = "end-to-end"
    START_TO_END = "start-to-end"
    START_TO_START = "start-to-start"


class DependencyBufferType(models.TextChoices):
    """
    Describes how between-rows buffer is used.
    """

    FLEXIBLE = "flexible"
    FIXED = "fixed"
    NONE = "none"


class DateDependency(FieldRule):
    start_date_field = models.ForeignKey(
        "database.Field", null=True, on_delete=models.CASCADE, related_name="+"
    )
    end_date_field = models.ForeignKey(
        "database.Field", null=True, on_delete=models.CASCADE, related_name="+"
    )
    duration_field = models.ForeignKey(
        "database.Field", null=True, on_delete=models.CASCADE, related_name="+"
    )

    dependency_linkrow_field = models.ForeignKey(
        "database.LinkRowField", null=True, on_delete=models.CASCADE, related_name="+"
    )
    dependency_linkrow_role = models.CharField(
        choices=DependencyLinkrowType,
        default=DependencyLinkrowType.PREDECESSORS,
        null=True,
    )
    dependency_connection_type = models.CharField(
        choices=DependencyConnectionType,
        default=DependencyConnectionType.END_TO_START,
        null=True,
    )
    dependency_buffer_type = models.CharField(
        choices=DependencyBufferType, default=DependencyBufferType.FIXED, null=True
    )

    dependency_buffer = models.DurationField(null=True, default=timedelta(0))

    include_weekends = models.BooleanField(null=False, default=True)

    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        d = DateDepenencyDict(
            start_date_field_id=self.start_date_field_id,
            end_date_field_id=self.end_date_field_id,
            duration_field_id=self.duration_field_id,
            dependency_linkrow_field_id=self.dependency_linkrow_field_id,
            dependency_buffer=self.dependency_buffer,
            dependency_buffer_type=self.dependency_buffer_type,
            dependency_connection_type=self.dependency_connection_type,
            dependency_linkrow_role=self.dependency_linkrow_role,
            include_weekends=self.include_weekends,
        )
        d.update(base_dict)
        return d
