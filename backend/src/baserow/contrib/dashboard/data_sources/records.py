from django.db.models import Subquery

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.core.formula.exceptions import InvalidRuntimeFormula


class DashboardTableRecordsHandler:
    def iter_scalar_field_values(self, table, field_name):
        """Stream distinct text/numbers in first-row order without losing precision."""

        model = table.get_model()
        field_object = next(
            (item for item in model.get_field_objects() if item["name"] == field_name),
            None,
        )
        if (
            field_object is None
            or field_object["type"].type
            not in {"text", "long_text", "url", "email", "phone_number", "number"}
            or getattr(field_object["field"], "long_text_enable_rich_text", False)
        ):
            return None

        rows = model.objects.all()
        first_occurrences = rows.order_by(field_name, "order", "id").distinct(
            field_name
        )
        return (
            rows.filter(id__in=Subquery(first_occurrences.values("id")))
            .order_by("order", "id")
            .values_list(field_name, flat=True)
            .iterator(chunk_size=100)
        )

    def iter_records(self, table, field_name=None, *, row_index=None):
        model = table.get_model()
        field_objects = model.get_field_objects()
        if field_name is not None:
            field_objects = [
                item for item in field_objects if item["name"] == field_name
            ]
            if not field_objects and field_name != "id":
                raise InvalidRuntimeFormula("The table field no longer exists.")
        field_ids = [item["field"].id for item in field_objects]
        queryset = (
            model.objects.all()
            .enhance_by_fields(only_field_ids=field_ids)
            .only("id", "order", *(item["name"] for item in field_objects))
        )
        if row_index is not None:
            queryset = queryset[row_index : row_index + 1]
        serializer = get_row_serializer_class(
            model, RowSerializer, is_response=True, field_ids=field_ids
        )
        for row in queryset.iterator(chunk_size=100):
            record = dict(serializer(row).data)
            for item in field_objects:
                name = item["name"]
                record[name] = item["type"].to_runtime_formula_value(
                    item["field"], record[name]
                )
            yield record
