"""
The widget types the shared dashboard tools can create, describe and change.
Each widget type registers how its definition looks and maps to its data source,
so a widget type added by another module (like premium's charts) brings its own.
"""

from functools import cache
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, create_model
from pydantic_core import CoreSchema

from baserow.contrib.dashboard.widgets.models import Widget
from baserow.core.registry import Instance, Registry
from baserow.core.services.models import Service
from baserow.core.tools import ToolContext

from .types import Description, Title


class WidgetToolType(Instance):
    """
    How the shared tools handle one widget type. ``type`` is the widget type's.
    """

    create_model: type[BaseModel]
    """
    The definition of a new widget: ``type`` as a literal, title, description,
    table_id, view_id and the type's own values.
    """

    update_fields: dict[str, tuple[Any, Any]] = {}
    """
    The values of the type the update tool takes, as ``create_model`` fields:
    name to (annotation, default). The default must be None, which keeps the
    widget's value.
    """

    clearable: dict[str, str] = {}
    """
    The values of ``update_fields`` that can be removed with ``clear``, each with
    what removing it does, like "to show a chart without categories".
    """

    data_source_keys: tuple[str, ...] = ()
    """The values of a definition, besides table_id and view_id, that set the data
    source."""

    def describe(self, widget: Widget, service: Service | None) -> dict[str, Any]:
        """
        What the widget shows, besides the values every widget has.

        :param widget: The specific widget.
        :param service: The specific service of its data source, if any.
        :return: The data source keys and the type's other values.
        """

        return {}

    def aggregations(self, config: dict[str, Any]) -> list[tuple[int, str]]:
        """
        The field and aggregation of each value a data source computes.

        :param config: The data source of a widget of this type.
        :return: One (field_id, aggregation_type) pair for each value.
        """

        return []

    def update_config(
        self, config: dict[str, Any], given: dict[str, Any]
    ) -> dict[str, Any]:
        """
        The data source a widget gets from an update.

        :param config: The data source it has.
        :param given: The values the update sets, cleared ones as None.
        :return: The data source it gets.
        """

        return {**config, **{key: given[key] for key in given if key in config}}

    def data_source_values(
        self,
        config: dict[str, Any],
        previous: dict[str, Any] | None,
        service: Service,
    ) -> dict[str, Any]:
        """
        The values to send to the data source's service.

        :param config: The data source the widget gets.
        :param previous: The data source it has, when it is updated. Only the
            values that change are sent.
        :param service: The specific service of the data source.
        :return: The service values.
        """

        return {key: config[key] for key in changed_keys(config, previous)}

    def widget_values(
        self, given: dict[str, Any], current: dict[str, Any] | None
    ) -> dict[str, Any]:
        """
        The widget's own values a definition or an update sets, besides its title
        and description.

        :param given: The values of the definition or the update.
        :param current: The widget as ``describe_widget`` returns it, when it is
            updated. Only the values that change are returned.
        :return: The values to save on the widget.
        :raises DjangoValidationError: When a value doesn't fit the widget.
        """

        return {}

    def after_data_source_update(
        self,
        ctx: ToolContext,
        widget: Widget,
        sent: dict[str, Any],
        widget_values: dict[str, Any],
    ) -> dict[str, Any]:
        """
        The widget values that follow from a change of its data source or of its
        own values, like the style of a chart's series.

        :param ctx: The user and workspace the tool acts for.
        :param widget: The widget, with its data source updated.
        :param sent: The values sent to the data source's service.
        :param widget_values: The values that are saved on the widget.
        :return: More values to save on the widget.
        """

        return {}


def changed_keys(config: dict[str, Any], previous: dict[str, Any] | None) -> set[str]:
    """
    :param config: The data source a widget gets.
    :param previous: The data source it has, or None for a new widget.
    :return: The keys whose value changes, every key for a new widget or a new
        table, so the service checks the fields against the table.
    """

    if previous is None or previous["table_id"] != config["table_id"]:
        return set(config)
    return {key for key in config if previous[key] != config[key]}


class WidgetToolTypeRegistry(Registry[WidgetToolType]):
    name = "dashboard_widget_tool_type"


widget_tool_type_registry = WidgetToolTypeRegistry()


KEEP = "Leave out to keep the current one; remove it with clear."


@cache
def build_update_model() -> type[BaseModel]:
    """
    The changes to one widget, with the values of every registered widget type.
    Built once, so a change validated by a tool's input is the model the tool
    validates again.
    """

    fields: dict[str, Any] = {}
    clearable = {"view_id": "to aggregate every row"}
    for tool_type in widget_tool_type_registry.get_all():
        for name, field in tool_type.update_fields.items():
            fields.setdefault(name, field)
        for name, effect in tool_type.clearable.items():
            clearable.setdefault(name, effect)
    return create_model(
        "WidgetUpdate",
        __config__=ConfigDict(extra="forbid"),
        __doc__=(
            "The changes to one widget. A value left out or null keeps what the "
            "widget has. A value of another widget type is refused."
        ),
        widget_id=(int, Field(description="The widget to change.")),
        title=(Title | None, None),
        description=(Description | None, None),
        table_id=(
            int | None,
            Field(
                default=None,
                description="The table the widget aggregates. Changing it needs "
                "the fields of the new table too.",
            ),
        ),
        view_id=(
            int | None,
            Field(
                default=None,
                description="A view of the table. Only the rows the view shows "
                f"are aggregated, after its filters. {KEEP}",
            ),
        ),
        **fields,
        clear=(
            list[Literal[tuple(clearable)]],
            Field(
                default=[],
                description="Values to remove: "
                + ", ".join(f"{name} {effect}" for name, effect in clearable.items())
                + ".",
            ),
        ),
    )


class WidgetCreate:
    """
    A new widget of any registered widget type. Its schema is built from the
    registry when a tool's input is, after every app registered its types.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        models = tuple(t.create_model for t in widget_tool_type_registry.get_all())
        if len(models) == 1:
            return handler.generate_schema(models[0])
        return handler.generate_schema(
            Annotated[Union[models], Field(discriminator="type")]
        )


class WidgetUpdate:
    """The changes to one widget, see ``build_update_model``."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return handler.generate_schema(build_update_model())
