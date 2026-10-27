from django.db import transaction

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceFilterGroup,
)
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.models import TrashEntry
from baserow.core.utils import extract_allowed

from .exceptions import (
    DashboardFilterDoesNotExist,
    InvalidDashboardFilterConfiguration,
    InvalidDashboardFilterOrder,
)
from .models import DashboardFilter
from .operators import get_default_filter_operator, get_filter_operators
from .references import get_referenced_dashboard_filters
from .values import selection_format, validate_selection_budget


class DashboardFilterHandler:
    allowed_fields = (
        "label",
        "type",
        "operator",
        "mode",
        "multiple",
        "formula_value",
        "values",
    )

    def get_filter(self, filter_id, for_update=False):
        queryset = DashboardFilter.objects.select_related("dashboard__workspace")
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        try:
            return queryset.get(
                id=filter_id,
                dashboard__trashed=False,
                dashboard__workspace__trashed=False,
            )
        except DashboardFilter.DoesNotExist as exc:
            raise DashboardFilterDoesNotExist() from exc

    def get_filters(self, dashboard):
        return DashboardFilter.objects.filter(dashboard=dashboard)

    @transaction.atomic
    def create_filter(self, dashboard, order=None, **values):
        DashboardHandler().get_dashboard_for_update(dashboard.id)
        values = self.prepare_values(values)
        self.validate_values(dashboard, values.get("values", []))
        if order is None:
            order = (
                DashboardFilter.get_highest_order_of_queryset(
                    DashboardFilter.objects_and_trash.filter(dashboard=dashboard)
                )
                + 1
            )
        dashboard_filter = DashboardFilter.objects.create(
            dashboard=dashboard,
            order=order,
            **values,
        )
        return dashboard_filter

    def order_filters(self, dashboard, order, ignore_missing=False):
        """Reorder active filters, preserving any filters omitted by a stale client."""

        queryset = self.get_filters(dashboard)
        previous = list(queryset.select_for_update().values_list("id", flat=True))
        if len(order) != len(set(order)):
            raise InvalidDashboardFilterOrder()
        if ignore_missing:
            order = [filter_id for filter_id in order if filter_id in previous]
        try:
            ordered = DashboardFilter.order_objects(queryset, order)
        except IdDoesNotExist as exc:
            raise InvalidDashboardFilterOrder() from exc
        return previous, ordered

    def delete_filter(self, dashboard_filter):
        dashboard_filter.delete()

    def filter_available_source_conditions(self, dashboard, conditions):
        """Discard deleted control references sent by a stale source editor."""

        available_filters = set(
            self.get_filters(dashboard).values_list("id", flat=True)
        )
        return [
            condition
            for condition in conditions
            if get_referenced_dashboard_filters(condition["value"]) <= available_filters
        ]

    def remove_source_conditions(self, dashboard_filter):
        """Remove linked conditions, retaining their configuration for trash restore."""

        service_ids = list(
            DashboardDataSource.objects_and_trash.select_for_update()
            .filter(dashboard_id=dashboard_filter.dashboard_id)
            .values_list("service_id", flat=True)
        )
        conditions = [
            condition
            for condition in LocalBaserowTableServiceFilter.objects.filter(
                service_id__in=service_ids
            ).values(
                "id",
                "service_id",
                "field_id",
                "type",
                "value",
                "value_is_formula",
                "order",
                "group_id",
            )
            if dashboard_filter.id
            in get_referenced_dashboard_filters(condition["value"])
        ]
        LocalBaserowTableServiceFilter.objects.filter(
            id__in=[condition["id"] for condition in conditions]
        ).delete()
        saved_conditions = [
            {key: value for key, value in condition.items() if key != "id"}
            for condition in conditions
        ]
        # Another deleted control may already have removed a shared condition.
        # Keep a copy here too so the last restored control can bring it back.
        restoration_data = TrashEntry.objects.filter(
            application_id=dashboard_filter.dashboard_id,
            trash_item_type="dashboard_filter",
        ).values_list("additional_restoration_data", flat=True)
        for data in restoration_data:
            for condition in (data or {}).get("source_conditions", []):
                if (
                    dashboard_filter.id
                    in get_referenced_dashboard_filters(condition["value"])
                    and condition not in saved_conditions
                ):
                    saved_conditions.append(condition)
        return saved_conditions

    def restore_source_conditions(self, dashboard_filter, conditions):
        if not conditions:
            return
        sources = (
            DashboardDataSource.objects_and_trash.select_for_update(of=("self",))
            .filter(
                dashboard_id=dashboard_filter.dashboard_id,
                service_id__in={condition["service_id"] for condition in conditions},
            )
            .select_related("service")
        )
        tables = {
            source.service_id: getattr(source.service.specific, "table_id", None)
            for source in sources
        }
        fields = dict(
            Field.objects_and_trash.filter(
                id__in={condition["field_id"] for condition in conditions}
            ).values_list("id", "table_id")
        )
        groups = dict(
            LocalBaserowTableServiceFilterGroup.objects.filter(
                service_id__in=tables
            ).values_list("id", "service_id")
        )
        available_filters = set(
            self.get_filters(dashboard_filter.dashboard).values_list("id", flat=True)
        )
        for condition in conditions:
            service_id = condition["service_id"]
            if (
                service_id not in tables
                or tables[service_id] is None
                or fields.get(condition["field_id"]) != tables[service_id]
            ):
                continue
            if (
                condition["group_id"] is not None
                and groups.get(condition["group_id"]) != service_id
            ):
                continue
            missing_filters = (
                get_referenced_dashboard_filters(condition["value"]) - available_filters
            )
            if missing_filters:
                # Every other deleted control retains its own copy in the trash.
                continue
            # Preserve edits made since deletion; restore only the removed rows.
            LocalBaserowTableServiceFilter.objects.get_or_create(**condition)

    @transaction.atomic
    def update_filter(self, dashboard_filter, **values):
        DashboardHandler().get_dashboard_for_update(dashboard_filter.dashboard_id)
        dashboard_filter.refresh_from_db()
        values = self.prepare_values(values, dashboard_filter)
        self.validate_values(
            dashboard_filter.dashboard,
            values.get("values", dashboard_filter.values),
            exclude_id=dashboard_filter.id,
        )
        previous = {key: getattr(dashboard_filter, key) for key in values}
        for key, value in values.items():
            setattr(dashboard_filter, key, value)
        dashboard_filter.save()
        return previous, values

    def prepare_values(self, values, dashboard_filter=None):
        values = extract_allowed(values, self.allowed_fields)
        previous_type = dashboard_filter.type if dashboard_filter else "text"
        filter_type = values.get("type", previous_type)
        if dashboard_filter is None or filter_type != previous_type:
            values.setdefault("operator", get_default_filter_operator(filter_type))
        operator = values.get(
            "operator", dashboard_filter.operator if dashboard_filter else "equal"
        )
        if operator not in get_filter_operators(filter_type):
            raise InvalidDashboardFilterConfiguration()
        if dashboard_filter is not None:
            fields = ("type", "mode", "multiple", "operator")
            previous_format = selection_format(
                *(getattr(dashboard_filter, field) for field in fields)
            )
            next_format = selection_format(
                *(
                    values.get(field, getattr(dashboard_filter, field))
                    for field in fields
                )
            )
            if previous_format != next_format:
                # Explicit values let undo restore the previous format and selection.
                values.setdefault("values", [])
        if "values" in values:
            validate_selection_budget([values["values"]])
        return values

    def validate_values(self, dashboard, values, exclude_id=None):
        """The caller locks the dashboard so simultaneous saves share one budget."""

        selections = (
            self.get_filters(dashboard)
            .exclude(id=exclude_id)
            .values_list("values", flat=True)
        )
        validate_selection_budget([values, *selections])

    def export_filter(self, dashboard_filter):
        return {
            "id": dashboard_filter.id,
            "order": dashboard_filter.order,
            **{key: getattr(dashboard_filter, key) for key in self.allowed_fields},
        }

    def import_filter(self, dashboard, values, id_mapping):
        dashboard_filter = self.create_filter(
            dashboard,
            order=values.get("order"),
            **extract_allowed(values, self.allowed_fields),
        )
        id_mapping.setdefault("dashboard_filters", {})[values["id"]] = (
            dashboard_filter.id
        )
        return dashboard_filter
