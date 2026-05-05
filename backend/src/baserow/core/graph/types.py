from typing import TYPE_CHECKING, Literal, TypeAlias, TypedDict, TypeVar

from django.db import models

if TYPE_CHECKING:
    from django.db.models import Model

    from baserow.core.graph.models import GraphModelMixin

    class GraphModelBase(GraphModelMixin, Model):
        class Meta:
            abstract = True


GraphPoint = TypeVar("GraphPoint", bound="Model")
GraphModelInstance = TypeVar("GraphModelInstance", bound="GraphModelBase")


class SerializedGraphPoint(TypedDict, total=False):
    next: dict[str, list[int]]
    children: list[int]


SerializedGraph = dict[str, int | SerializedGraphPoint]


class GraphPointPosition(models.TextChoices):
    NORTH = "north", "North"
    SOUTH = "south", "South"
    CHILD = "child", "Child"


GraphPointPositionType = Literal["north", "south", "child"]
GraphPointPositionTriplet: TypeAlias = tuple[
    GraphPoint | None, GraphPointPositionType, str
]
