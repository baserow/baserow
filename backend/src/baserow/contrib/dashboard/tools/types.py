"""
The values the widget definitions of the dashboard tools share, and the summary
widget's definition.
"""

from typing import Annotated, Literal

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid")


Title = Annotated[
    str, Field(min_length=1, max_length=255, description="The widget's title.")
]
Description = Annotated[
    str, Field(max_length=255, description="Text shown under the widget's title.")
]
TableId = Annotated[int, Field(description="The table the widget aggregates.")]
ViewId = Annotated[
    int | None,
    Field(
        description="A view of the table. Only the rows the view shows are "
        "aggregated, after its filters. null uses every row."
    ),
]
AggregationType = Annotated[
    str,
    Field(
        description="How the field's values are aggregated, for example sum, "
        "average, min, max, median, std_dev, variance, count, not_empty_count, "
        "empty_count, unique_count. Which ones fit depends on the field type. "
        "count counts the rows, whatever their value in the field; "
        "not_empty_count counts only the rows where the field has a value."
    ),
]


class SummaryWidgetCreate(BaseModel):
    """A widget that shows one number: one field aggregated over the rows."""

    type: Literal["summary"]
    title: Title
    description: Description = ""
    table_id: TableId
    view_id: ViewId = None
    field_id: Annotated[int, Field(description="The field to aggregate.")]
    aggregation_type: AggregationType
