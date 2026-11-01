"""
How the shared dashboard tools create, describe and change charts and pie charts.
"""

from typing import Annotated, Any, Literal

from django.core.exceptions import ValidationError as DjangoValidationError

from pydantic import Field

from baserow.contrib.dashboard.tools.registries import (
    KEEP,
    WidgetToolType,
    changed_keys,
)
from baserow.contrib.dashboard.tools.types import (
    AggregationType,
    BaseModel,
    Description,
    TableId,
    Title,
    ViewId,
)
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.services.models import Service
from baserow.core.tools import ToolContext


class AggregationSeries(BaseModel):
    field_id: Annotated[int, Field(description="The field to aggregate.")]
    aggregation_type: AggregationType


Series = Annotated[
    list[AggregationSeries],
    Field(min_length=1, description="The values the chart shows, one per series."),
]
GroupByFieldId = Annotated[
    int | None,
    Field(
        description="The field whose values become the chart's categories. null "
        "shows one value per series, without categories."
    ),
]


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


def _series_ids(
    series: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> list[int | None]:
    """
    The id each series of a chart keeps, so its color and chart type stay. A
    series given again keeps its id wherever it moves. The others take the ids
    left over in order, so a series whose field or aggregation changes keeps its
    style too.

    :param series: The series the chart gets.
    :param existing: The series it has, with their ids, in order.
    :return: For each series, the id it keeps, or None for a new one.
    """

    def key(s):
        return s["field_id"], s["aggregation_type"]

    left = list(existing)
    ids: list[int | None] = []
    for new in series:
        match = next((old for old in left if key(old) == key(new)), None)
        if match is not None:
            left.remove(match)
        ids.append(match["id"] if match is not None else None)
    rest = iter(old["id"] for old in left)
    return [next(rest, None) if id_ is None else id_ for id_ in ids]


class ChartWidgetToolType(WidgetToolType):
    type = "chart"
    create_model = ChartWidgetCreate
    update_fields = {
        "series": (Series | None, None),
        "group_by_field_id": (
            Annotated[
                int | None,
                Field(
                    description="The field whose values become a chart's "
                    f"categories. {KEEP}"
                ),
            ],
            None,
        ),
        "chart_type": (
            Annotated[
                Literal["BAR", "LINE", "PIE", "DOUGHNUT"] | None,
                Field(
                    description="How the chart draws its series: BAR or LINE for "
                    "a chart, PIE or DOUGHNUT for a pie chart. Every series is "
                    "redrawn this way."
                ),
            ],
            None,
        ),
    }
    clearable = {"group_by_field_id": "to show a chart without categories"}
    data_source_keys = ("series", "group_by_field_id", "group_by_row_id")

    def describe(self, widget: Widget, service: Service | None) -> dict[str, Any]:
        if service is not None and hasattr(service, "service_aggregation_series"):
            series = list(service.service_aggregation_series.all())
            group_bys = list(service.service_aggregation_group_bys.all())
        else:
            series, group_bys = [], []
        return {
            "series": [
                {"field_id": s.field_id, "aggregation_type": s.aggregation_type}
                for s in series
            ],
            "group_by_field_id": group_bys[0].field_id if group_bys else None,
            # Grouped by row id in the UI: one category per row.
            "group_by_row_id": bool(group_bys) and group_bys[0].field_id is None,
            "chart_type": widget.default_series_chart_type,
        }

    def aggregations(self, config: dict[str, Any]) -> list[tuple[int, str]]:
        return [(s["field_id"], s["aggregation_type"]) for s in config["series"]]

    def update_config(
        self, config: dict[str, Any], given: dict[str, Any]
    ) -> dict[str, Any]:
        new_config = super().update_config(config, given)
        if "group_by_field_id" in given:
            new_config["group_by_row_id"] = False
        return new_config

    def data_source_values(
        self,
        config: dict[str, Any],
        previous: dict[str, Any] | None,
        service: Service,
    ) -> dict[str, Any]:
        changed = changed_keys(config, previous)
        values = {key: config[key] for key in changed & {"table_id", "view_id"}}
        # A new table drops the series and group by of the old one.
        table_changed = "table_id" in changed and previous is not None
        # The grouped aggregate service takes the series and group bys under the
        # names of their relations. It drops the sorts they no longer match.
        if "series" in changed or table_changed:
            existing = [
                {
                    "id": series.id,
                    "field_id": series.field_id,
                    "aggregation_type": series.aggregation_type,
                }
                for series in service.service_aggregation_series.all()
            ]
            ids = _series_ids(config["series"], existing)
            values["service_aggregation_series"] = [
                {
                    **({"id": id_} if id_ is not None else {}),
                    "field_id": series["field_id"],
                    "aggregation_type": series["aggregation_type"],
                }
                for id_, series in zip(ids, config["series"])
            ]
        if changed & {"group_by_field_id", "group_by_row_id"} or table_changed:
            group_by = config["group_by_field_id"]
            # A group by without a field groups by row id.
            values["service_aggregation_group_bys"] = (
                [{"field_id": group_by}]
                if group_by is not None or config.get("group_by_row_id")
                else []
            )
        return values

    def widget_values(
        self, given: dict[str, Any], current: dict[str, Any] | None
    ) -> dict[str, Any]:
        chart_type = given.get("chart_type")
        if chart_type is None:
            return {}
        chart_types = CHART_TYPES[self.type]
        if chart_type not in chart_types:
            other_type, other_chart_types = next(
                item for item in CHART_TYPES.items() if item[0] != self.type
            )
            raise DjangoValidationError(
                f"A {self.type} is drawn as {' or '.join(chart_types)}; use a "
                f"{other_type} for {' or '.join(other_chart_types)}."
            )
        if current is not None and chart_type == current["chart_type"]:
            return {}
        return {"default_series_chart_type": chart_type}

    def after_data_source_update(
        self,
        ctx: ToolContext,
        widget: Widget,
        sent: dict[str, Any],
        widget_values: dict[str, Any],
    ) -> dict[str, Any]:
        restyle = "default_series_chart_type" in widget_values
        if "service_aggregation_series" not in sent and not restyle:
            return {}
        widget = WidgetService().get_widget(ctx.user, widget.id)
        if restyle:
            widget.default_series_chart_type = widget_values[
                "default_series_chart_type"
            ]
        return {
            "series_config": widget_type_registry.get(self.type).series_config_for(
                widget, restyle
            )
        }


class PieChartWidgetToolType(ChartWidgetToolType):
    type = "pie_chart"
    create_model = PieChartWidgetCreate
