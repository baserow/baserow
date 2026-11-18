from copy import deepcopy
from decimal import Decimal
from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    FractionOrderableMixin,
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)

if TYPE_CHECKING:
    from baserow.contrib.dashboard.models import Dashboard


class Widget(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    FractionOrderableMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
    models.Model,
):
    """
    This model represents a dashboard widget. It displays
    information or something the user can interact with.
    """

    title = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    dashboard = models.ForeignKey("dashboard.Dashboard", on_delete=models.CASCADE)
    order = models.DecimalField(
        help_text="Lowest first.",
        max_digits=40,
        decimal_places=20,
        editable=False,
        default=Decimal("1"),
    )
    grid_x = models.PositiveIntegerField(default=0, db_default=0)
    grid_y = models.PositiveIntegerField(default=0, db_default=0)
    grid_width = models.PositiveIntegerField(default=6, db_default=6)
    grid_height = models.PositiveIntegerField(default=9, db_default=9)
    # TODO ZDM: Remove this field after every pre-grid-layout application version
    # has been retired.
    grid_layout_initialized = models.BooleanField(default=True, db_default=False)
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="dashboard_widgets",
        on_delete=models.CASCADE,
    )

    class Meta:
        ordering = ("grid_y", "grid_x", "id")

    @staticmethod
    def get_type_registry():
        from .registries import widget_type_registry

        return widget_type_registry

    def get_parent(self):
        return self.dashboard

    @classmethod
    def get_last_order(
        cls,
        dashboard: "Dashboard",
    ):
        """
        Returns the last order for the given page.

        :param dashboard: The dashboard we want the order for.
        :param base_queryset: The base queryset to use.
        :return: The last order.
        """

        return cls.get_last_orders(dashboard)[0]

    @classmethod
    def get_last_orders(
        cls,
        dashboard: "Dashboard",
        amount=1,
    ):
        """
        Returns the last orders for the given dashboard.

        :param dashboard: The dashboard we want the order for.
        :param amount: The number of orders you wish to have returned
        :return: The last order.
        """

        queryset = Widget.objects.filter(dashboard=dashboard)
        return cls.get_highest_order_of_queryset(queryset, amount=amount)


class SummaryWidget(Widget):
    data_source = models.ForeignKey(
        "dashboard.DashboardDataSource",
        on_delete=models.PROTECT,
        help_text="Data source for fetching the result to display.",
    )


class TextFilterWidget(Widget):
    """A text filter whose viewer value remains local to the browser."""

    class Mode(models.TextChoices):
        INPUT = "input", "Input"
        DROPDOWN = "dropdown", "Dropdown"

    mode = models.CharField(
        max_length=16, choices=Mode.choices, default=Mode.INPUT, db_default=Mode.INPUT
    )
    options = FormulaField(db_default="")
    multiple = models.BooleanField(default=False, db_default=False)

    placeholder = models.TextField(blank=True, default="", db_default="")
    default_value = models.JSONField(blank=True, default=str, db_default="")

    @property
    def target_filters(self):
        """Expose the API representation while conditions live in related tables."""
        if "_target_filters" not in self.__dict__:
            from .filter_handler import WidgetFilterHandler

            self._target_filters = WidgetFilterHandler().get_target_filters(self)
            self._saved_target_filters = deepcopy(self._target_filters)
        return self._target_filters

    @target_filters.setter
    def target_filters(self, value):
        self._target_filters = value

    def save(self, *args, **kwargs):
        """Persist an assigned filter configuration after the widget has an ID."""
        update_fields = kwargs.get("update_fields")
        save_filters = update_fields is None or "target_filters" in update_fields
        if update_fields is not None and "target_filters" in update_fields:
            kwargs["update_fields"] = set(update_fields) - {"target_filters"}
        super().save(*args, **kwargs)
        if save_filters and "_target_filters" in self.__dict__:
            if self._target_filters != getattr(self, "_saved_target_filters", None):
                from .filter_handler import WidgetFilterHandler

                WidgetFilterHandler().set_target_filters(self, self._target_filters)
                self._saved_target_filters = deepcopy(self._target_filters)

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self.__dict__.pop("_target_filters", None)
        self.__dict__.pop("_saved_target_filters", None)


class WidgetFilterTarget(models.Model):
    """An explicit contribution from one filter widget to a display widget."""

    widget = models.ForeignKey(
        Widget, related_name="filter_targets", on_delete=models.CASCADE
    )
    target_widget = models.ForeignKey(
        Widget, related_name="contributed_filters", on_delete=models.CASCADE
    )
    order = models.PositiveIntegerField(default=0, db_default=0)
    enabled = models.BooleanField(default=True, db_default=True)
    empty_behavior = models.CharField(
        max_length=32, default="apply_nothing", db_default="apply_nothing"
    )
    # Preserve optional API attributes without storing groups or formulas as JSON.
    configuration = models.JSONField(default=dict, db_default={})

    def get_widget(self):
        return self.widget

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["widget", "target_widget"], name="unique_widget_filter_target"
            )
        ]


class WidgetFilterGroup(models.Model):
    """A root or nested AND/OR group in either branch of a target link."""

    target = models.ForeignKey(
        WidgetFilterTarget, related_name="groups", on_delete=models.CASCADE
    )
    parent_group = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    alternative = models.BooleanField(default=False, db_default=False)
    filter_type = models.CharField(max_length=3, default="AND", db_default="AND")
    order = models.PositiveIntegerField(default=0, db_default=0)
    # Client group identifiers may be strings or integers, independent of ORM IDs.
    reference = models.JSONField(null=True, default=None, db_default=None)
    configuration = models.JSONField(default=dict, db_default={})

    def get_widget(self):
        return self.target.widget

    class Meta:
        ordering = ("order", "id")


class WidgetFilterCondition(models.Model):
    """One integration field condition with a standard runtime formula value."""

    group = models.ForeignKey(
        WidgetFilterGroup, related_name="conditions", on_delete=models.CASCADE
    )
    # The integration validates/remaps this reference. Dashboard cannot depend on
    # database models; zero denotes a field that was unavailable during import.
    field_id = models.BigIntegerField()
    type = models.CharField(max_length=48)
    value = FormulaField()
    order = models.PositiveIntegerField(default=0, db_default=0)
    configuration = models.JSONField(default=dict, db_default={})

    def get_widget(self):
        return self.group.target.widget

    class Meta:
        ordering = ("order", "id")
