from typing import TYPE_CHECKING, Literal, TypeAlias, TypeVar

from django.db import models

if TYPE_CHECKING:
    from django.db.models import Model

    from baserow.core.graph.models import GraphModelMixin

    class GraphModelBase(GraphModelMixin, Model):
        class Meta:
            abstract = True


GraphPoint = TypeVar("GraphPoint", bound="Model")
GraphModelInstance = TypeVar("GraphModelInstance", bound="GraphModelBase")


class GraphPointPosition(models.TextChoices):
    SOUTH = "south", "South"
    CHILD = "child", "Child"


GraphPointPositionType = Literal["south", "child"]
GraphPointPositionTriplet: TypeAlias = tuple[
    GraphPoint | None, GraphPointPositionType, str
]
