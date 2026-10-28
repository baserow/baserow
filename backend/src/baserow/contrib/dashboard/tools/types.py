"""
The widget definitions the dashboard tools take.
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
        "average, min, max, median, std_dev, variance, not_empty_count, "
        "empty_count, unique_count. Which ones fit depends on the field type."
    ),
]
GroupByFieldId = Annotated[
    int | None,
    Field(
        description="The field whose values become the chart's categories. null "
        "shows one value per series, without categories."
    ),
]


class AggregationSeries(BaseModel):
    field_id: Annotated[int, Field(description="The field to aggregate.")]
    aggregation_type: AggregationType


Series = Annotated[
    list[AggregationSeries],
    Field(min_length=1, description="The values the chart shows, one per series."),
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


class ChartWidgetCreate(BaseModel):
    """A chart: series of aggregated fields, grouped by a field."""

    type: Literal["chart"]
    title: Title
    description: Description = ""
    table_id: TableId
    view_id: ViewId = None
    series: Series
    group_by_field_id: GroupByFieldId = None
    chart_type: Annotated[
        Literal["BAR", "LINE"] | None,
        Field(description="How the chart draws its series. null draws bars."),
    ] = None


class PieChartWidgetCreate(ChartWidgetCreate):
    """A pie chart: series of aggregated fields, grouped by a field."""

    type: Literal["pie_chart"]
    chart_type: Annotated[
        Literal["PIE", "DOUGHNUT"] | None,
        Field(description="How the pie chart draws its series. null draws a pie."),
    ] = None


# The chart types each widget type can be drawn as.
CHART_TYPES = {"chart": ("BAR", "LINE"), "pie_chart": ("PIE", "DOUGHNUT")}

WidgetCreate = Annotated[
    SummaryWidgetCreate | ChartWidgetCreate | PieChartWidgetCreate,
    Field(discriminator="type"),
]


KEEP = "Leave out to keep the current one; remove it with clear."


class WidgetUpdate(BaseModel):
    """
    The changes to one widget. A value left out or null keeps what the widget
    has. field_id and aggregation_type are for a summary widget, series,
    group_by_field_id and chart_type for a chart or pie chart.
    """

    widget_id: Annotated[int, Field(description="The widget to change.")]
    title: Title | None = None
    description: Description | None = None
    table_id: Annotated[
        int | None,
        Field(
            description="The table the widget aggregates. Changing it needs the "
            "fields of the new table too."
        ),
    ] = None
    view_id: Annotated[
        int | None,
        Field(
            description="A view of the table. Only the rows the view shows are "
            f"aggregated, after its filters. {KEEP}"
        ),
    ] = None
    field_id: Annotated[int | None, Field(description="The field to aggregate.")] = None
    aggregation_type: AggregationType | None = None
    series: Series | None = None
    group_by_field_id: Annotated[
        int | None,
        Field(
            description=f"The field whose values become the chart's categories. {KEEP}"
        ),
    ] = None
    chart_type: Annotated[
        Literal["BAR", "LINE", "PIE", "DOUGHNUT"] | None,
        Field(
            description="How the chart draws its series: BAR or LINE for a chart, "
            "PIE or DOUGHNUT for a pie chart. Every series is redrawn this way."
        ),
    ] = None
    clear: Annotated[
        list[Literal["view_id", "group_by_field_id"]],
        Field(
            description="Values to remove: view_id to aggregate every row, "
            "group_by_field_id to show a chart without categories."
        ),
    ] = []
