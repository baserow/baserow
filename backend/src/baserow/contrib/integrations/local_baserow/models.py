from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, OrderBy

from baserow.contrib.database.fields.field_filters import FILTER_TYPE_AND
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import (
    FILTER_TYPES,
    SORT_ORDER_ASC,
    SORT_ORDER_CHOICES,
    View,
)
from baserow.core.formula.field import FormulaField
from baserow.core.integrations.models import Integration
from baserow.core.services.models import (
    SearchableServiceMixin,
    Service,
    ServiceFilter,
    ServiceSort,
)

User = get_user_model()


class LocalBaserowIntegration(Integration):
    """
    An integration for accessing the local baserow instance. Everything which is
    accessible by the associated user can be accessed with this integration.
    """

    authorized_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)


class LocalBaserowTableService(Service):
    table = models.ForeignKey(Table, null=True, default=None, on_delete=models.SET_NULL)

    class Meta:
        abstract = True


class LocalBaserowViewService(LocalBaserowTableService):
    view = models.ForeignKey(View, null=True, default=None, on_delete=models.SET_NULL)

    class Meta:
        abstract = True


class LocalBaserowFilterableServiceMixin(models.Model):
    """
    A mixin which can be applied to LocalBaserow services to denote that they're
    filterable, and allows them to control their and/or filter operator type.
    """

    filter_type = models.CharField(
        max_length=3,
        choices=FILTER_TYPES,
        default=FILTER_TYPE_AND,
        help_text="Indicates whether all the rows should apply to all filters (AND) "
        "or to any filter (OR).",
    )

    @property
    def service_filters_with_untrashed_fields(self):
        return [
            f
            for f in self.service_filters.all()
            if not f.field_id or not f.field.trashed
        ]

    class Meta:
        abstract = True


class LocalBaserowFilterableSortableMixin(models.Model):
    """
    A mixin which can be applied to LocalBaserow services to denote that they're
    sortable.
    """

    @property
    def service_sorts_with_untrashed_fields(self):
        return [
            f for f in self.service_sorts.all() if not f.field_id or not f.field.trashed
        ]

    class Meta:
        abstract = True


class LocalBaserowListRows(
    LocalBaserowViewService,
    LocalBaserowFilterableServiceMixin,
    LocalBaserowFilterableSortableMixin,
    SearchableServiceMixin,
):
    """
    A model for the local baserow list rows service configuration data.
    """

    default_result_count = models.PositiveIntegerField(
        default=20,
        db_default=20,
        help_text="The default record count returned with each page.",
    )


class LocalBaserowAggregateRows(
    LocalBaserowViewService, LocalBaserowFilterableServiceMixin, SearchableServiceMixin
):
    """
    A model for the local baserow aggregate rows service configuration data.
    """

    field = models.ForeignKey(
        "database.Field",
        help_text="The aggregated field.",
        null=True,
        on_delete=models.SET_NULL,
    )
    aggregation_type = models.CharField(
        default="", blank=True, max_length=48, help_text="The field aggregation type."
    )


class LocalBaserowGetRow(
    LocalBaserowViewService,
    LocalBaserowFilterableServiceMixin,
    LocalBaserowFilterableSortableMixin,
    SearchableServiceMixin,
):
    """
    A model for the local baserow get row service configuration data.
    """

    row_id = FormulaField()


class LocalBaserowUpsertRow(LocalBaserowTableService):
    """
    A model for the local baserow upsert row service configuration data.
    """

    row_id = FormulaField()


class LocalBaserowDeleteRow(LocalBaserowTableService):
    """
    A model for the local baserow delete row service configuration data.
    """

    row_id = FormulaField()


class LocalBaserowRowsCreated(LocalBaserowTableService):
    """
    A model for the local baserow rows created trigger service.
    """


class LocalBaserowRowsUpdated(LocalBaserowTableService):
    """
    A model for the local baserow rows updated trigger service.
    """


class LocalBaserowRowsDeleted(LocalBaserowTableService):
    """
    A model for the local baserow rows deleted trigger service.
    """


class LocalBaserowTableServiceRefinementManager(models.Manager):
    """
    Kept for legacy purposes (in migrations)
    """

    use_in_migrations = True


class LocalBaserowTableServiceFilter(ServiceFilter):
    """
    A service filter applicable to a `LocalBaserowTableService` integration service.
    """

    objects = LocalBaserowTableServiceRefinementManager()

    field = models.ForeignKey(
        "database.Field",
        help_text="The database Field, in the LocalBaserowTableService, "
        "which we would like to filter upon.",
        on_delete=models.CASCADE,
    )
    type = models.CharField(
        max_length=48,
        help_text="Indicates how the field's value must be compared to the filter's "
        "value. The filter is always in this order `field` `type` `value` "
        "(example: `field_1` `contains` `Test`).",
    )
    value = FormulaField(
        default="",
        blank=True,
        help_text="The filter value that must be compared to the field's value.",
    )
    value_is_formula = models.BooleanField(
        default=False,
        help_text="Indicates whether the value is a formula or not.",
    )
    order = models.PositiveIntegerField()

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"<LocalBaserowTableServiceFilter {self.field} {self.type} {self.value}>"

    class Meta:
        ordering = ("order", "id")


class LocalBaserowTableServiceSort(ServiceSort):
    """
    A service sort applicable to a `LocalBaserowTableService` integration service.
    """

    objects = LocalBaserowTableServiceRefinementManager()

    field = models.ForeignKey(
        "database.Field",
        help_text="The database Field, in the LocalBaserowTableService service, "
        "which we would like to sort upon.",
        on_delete=models.CASCADE,
    )
    order_by = models.CharField(
        max_length=4,
        choices=SORT_ORDER_CHOICES,
        help_text="Indicates the sort order direction. ASC (Ascending) is from A to Z "
        "and DESC (Descending) is from Z to A.",
        default=SORT_ORDER_ASC,
    )
    order = models.PositiveIntegerField()

    def __repr__(self):
        return f"<LocalBaserowTableServiceSort {self.field} {self.order_by}>"

    class Meta:
        ordering = ("order", "id")

    def get_order_by(self) -> OrderBy:
        """
        Responsible for returning the `OrderBy` object,
        configured based on the `field` and `order` values.
        """

        field_expr = F(self.field.db_column)

        if self.order_by == SORT_ORDER_ASC:
            field_order_by = field_expr.asc(nulls_first=True)
        else:
            field_order_by = field_expr.desc(nulls_last=True)

        return field_order_by


class LocalBaserowTableServiceFieldMappingManager(models.Manager):
    """
    Manager for the `LocalBaserowTableServiceFieldMapping` model.
    Ensures that we exclude mappings with trashed fields.
    """

    def get_queryset(self):
        return super().get_queryset().filter(field__trashed=False)


class LocalBaserowTableServiceFieldMapping(models.Model):
    """
    Responsible for mapping a `LocalBaserowTableService` subclass's field
    to a specific value, or formula.
    """

    objects_and_trash = models.Manager()
    objects = LocalBaserowTableServiceFieldMappingManager()

    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        help_text="The Baserow field that this mapping relates to.",
    )
    enabled = models.BooleanField(
        null=True,  # TODO zdm remove me after v1.27
        default=True,
        help_text="Indicates if the field mapping is enabled. If it is disabled, "
        "we will not use the `value` when creating and updating rows.",
    )
    value = FormulaField(default="", help_text="The field mapping's value.")
    service = models.ForeignKey(
        Service,
        related_name="field_mappings",
        on_delete=models.CASCADE,
        help_text="The LocalBaserow Service that this field mapping relates to.",
    )
