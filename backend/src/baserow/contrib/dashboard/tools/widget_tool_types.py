from typing import Annotated, Any

from pydantic import Field

from baserow.contrib.dashboard.widgets.models import Widget
from baserow.core.services.models import Service

from .registries import WidgetToolType
from .types import AggregationType, SummaryWidgetCreate


class SummaryWidgetToolType(WidgetToolType):
    type = "summary"
    create_model = SummaryWidgetCreate
    update_fields = {
        "field_id": (
            Annotated[int | None, Field(description="The field a summary aggregates.")],
            None,
        ),
        "aggregation_type": (AggregationType | None, None),
    }
    data_source_keys = ("field_id", "aggregation_type")

    def describe(self, widget: Widget, service: Service | None) -> dict[str, Any]:
        return {
            "field_id": getattr(service, "field_id", None),
            "aggregation_type": getattr(service, "aggregation_type", None),
        }

    def aggregations(self, config: dict[str, Any]) -> list[tuple[int, str]]:
        return [(config["field_id"], config["aggregation_type"])]
