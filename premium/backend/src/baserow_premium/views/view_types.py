from typing import Any, Dict, List, Optional, Set
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db.models import Q
from django.urls import include, path

from baserow_premium.api.views.calendar.serializers import (
    CalendarViewFieldOptionsSerializer,
)
from baserow_premium.api.views.kanban.errors import (
    ERROR_KANBAN_VIEW_FIELD_DOES_NOT_BELONG_TO_SAME_TABLE,
)
from baserow_premium.api.views.kanban.serializers import (
    KanbanViewFieldOptionsSerializer,
)
from baserow_premium.api.views.timeline.errors import (
    ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS,
)
from baserow_premium.api.views.timeline.serializers import (
    TimelineViewFieldOptionsSerializer,
)
from rest_framework.fields import BooleanField, CharField
from rest_framework.serializers import PrimaryKeyRelatedField

from baserow.contrib.database.api.fields.errors import (
    ERROR_FIELD_NOT_IN_TABLE,
    ERROR_INCOMPATIBLE_FIELD,
)
from baserow.contrib.database.fields.exceptions import (
    FieldNotInTable,
    IncompatibleField,
)
from baserow.contrib.database.fields.models import (
    DateField,
    Field,
    FileField,
    SingleSelectField,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import ViewType
from baserow.core.registries import ImportExportConfig

from .exceptions import (
    KanbanViewFieldDoesNotBelongToSameTable,
    TimelineViewHasInvalidDateSettings,
)
from .models import (
    CalendarView,
    CalendarViewFieldOptions,
    KanbanView,
    KanbanViewFieldOptions,
    TimelineView,
    TimelineViewFieldOptions,
)


class KanbanViewType(ViewType):
    type = "kanban"
    model_class = KanbanView
    field_options_model_class = KanbanViewFieldOptions
    field_options_serializer_class = KanbanViewFieldOptionsSerializer
    allowed_fields = ["single_select_field", "card_cover_image_field"]
    field_options_allowed_fields = ["hidden", "order"]
    serializer_field_names = ["single_select_field", "card_cover_image_field"]
    serializer_field_overrides = {
        "single_select_field": PrimaryKeyRelatedField(
            queryset=SingleSelectField.objects.all(),
            required=False,
            default=None,
            allow_null=True,
        ),
        "card_cover_image_field": PrimaryKeyRelatedField(
            queryset=FileField.objects.all(),
            required=False,
            default=None,
            allow_null=True,
            help_text="References a file field of which the first image must be shown "
            "as card cover image.",
        ),
    }
    api_exceptions_map = {
        KanbanViewFieldDoesNotBelongToSameTable: (
            ERROR_KANBAN_VIEW_FIELD_DOES_NOT_BELONG_TO_SAME_TABLE
        ),
        FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
    }
    can_decorate = True
    can_share = True
    has_public_info = True

    def get_api_urls(self):
        from baserow_premium.api.views.kanban import urls as api_urls

        return [
            path("kanban/", include(api_urls, namespace=self.type)),
        ]

    def prepare_values(self, values, table, user):
        """
        Check if the provided single select option belongs to the same table.
        Check if the provided card cover image field belongs to the same table.
        """

        name = "single_select_field"
        if name in values:
            if isinstance(values[name], int):
                values[name] = SingleSelectField.objects.get(pk=values[name])

            if (
                isinstance(values[name], SingleSelectField)
                and values[name].table_id != table.id
            ):
                raise KanbanViewFieldDoesNotBelongToSameTable(
                    "The provided single select field does not belong to the kanban "
                    "view's table."
                )

        name = "card_cover_image_field"
        if name in values:
            if isinstance(values[name], int):
                values[name] = FileField.objects.get(pk=values[name])

            if (
                isinstance(values[name], FileField)
                and values[name].table_id != table.id
            ):
                raise FieldNotInTable(
                    "The provided file select field id does not belong to the kanban "
                    "view's table."
                )

        return super().prepare_values(values, table, user)

    def export_serialized(
        self,
        kanban: View,
        import_export_config: ImportExportConfig,
        cache: Optional[Dict] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        """
        Adds the serialized kanban view options to the exported dict.
        """

        serialized = super().export_serialized(
            kanban, import_export_config, cache, files_zip, storage
        )
        if kanban.single_select_field_id:
            serialized["single_select_field_id"] = kanban.single_select_field_id

        if kanban.card_cover_image_field_id:
            serialized["card_cover_image_field_id"] = kanban.card_cover_image_field_id

        serialized_field_options = []
        for field_option in kanban.get_field_options():
            serialized_field_options.append(
                {
                    "id": field_option.id,
                    "field_id": field_option.field_id,
                    "hidden": field_option.hidden,
                    "order": field_option.order,
                }
            )

        serialized["field_options"] = serialized_field_options
        return serialized

    def import_serialized(
        self,
        table: Table,
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Optional[View]:
        """
        Imports the serialized kanban view field options.
        """

        serialized_copy = serialized_values.copy()
        if "single_select_field_id" in serialized_copy:
            serialized_copy["single_select_field_id"] = id_mapping["database_fields"][
                serialized_copy.pop("single_select_field_id")
            ]

        if "card_cover_image_field_id" in serialized_copy:
            serialized_copy["card_cover_image_field_id"] = id_mapping[
                "database_fields"
            ][serialized_copy.pop("card_cover_image_field_id")]

        field_options = serialized_copy.pop("field_options")
        kanban_view = super().import_serialized(
            table, serialized_copy, import_export_config, id_mapping, files_zip, storage
        )

        if kanban_view is not None:
            if "database_kanban_view_field_options" not in id_mapping:
                id_mapping["database_kanban_view_field_options"] = {}

            for field_option in field_options:
                field_option_copy = field_option.copy()
                field_option_id = field_option_copy.pop("id")
                field_option_copy["field_id"] = id_mapping["database_fields"][
                    field_option["field_id"]
                ]
                field_option_object = KanbanViewFieldOptions.objects.create(
                    kanban_view=kanban_view, **field_option_copy
                )
                id_mapping["database_kanban_view_field_options"][
                    field_option_id
                ] = field_option_object.id

        return kanban_view

    def view_created(self, view: View):
        """
        When a kanban view is created, we want to set the first three fields as visible.
        """

        field_options = view.get_field_options(create_if_missing=True).order_by(
            "-field__primary", "field__id"
        )
        ids_to_update = [f.id for f in field_options[0:3]]

        if len(ids_to_update) > 0:
            KanbanViewFieldOptions.objects.filter(id__in=ids_to_update).update(
                hidden=False
            )

    def export_prepared_values(self, view: KanbanView) -> Dict[str, Any]:
        values = super().export_prepared_values(view)
        values["single_select_field"] = view.single_select_field_id
        values["card_cover_image_field"] = view.card_cover_image_field_id
        return values

    def get_visible_field_options_in_order(self, kanban_view: KanbanView):
        return (
            kanban_view.get_field_options(create_if_missing=True)
            .filter(
                Q(hidden=False)
                # If the `single_select_field_id` or `card_cover_image_field_id` is set,
                # we must always expose those fields because the values are needed to
                # work correctly.
                | Q(field_id=kanban_view.single_select_field_id)
                | Q(field_id=kanban_view.card_cover_image_field_id)
            )
            .order_by("order", "field__id")
        )

    def get_hidden_fields(
        self,
        view: KanbanView,
        field_ids_to_check: Optional[List[int]] = None,
    ) -> Set[int]:
        hidden_field_ids = set()
        fields = view.table.field_set.all()
        field_options = view.kanbanviewfieldoptions_set.all()

        if field_ids_to_check is not None:
            fields = [f for f in fields if f.id in field_ids_to_check]

        for field in fields:
            # If the `single_select_field_id` or `card_cover_image_field_id` is set,
            # we must always expose those fields because the values are needed to
            # work correctly.
            if field.id in [
                view.single_select_field_id,
                view.card_cover_image_field_id,
            ]:
                continue

            field_option_matching = None
            for field_option in field_options:
                if field_option.field_id == field.id:
                    field_option_matching = field_option

            # A field is considered hidden, if it is explicitly hidden
            # or if the field options don't exist
            if field_option_matching is None or field_option_matching.hidden:
                hidden_field_ids.add(field.id)

        return hidden_field_ids

    def enhance_queryset(self, queryset):
        return queryset.prefetch_related("kanbanviewfieldoptions_set")

    def after_field_delete(self, field: Field) -> None:
        if isinstance(field, FileField):
            KanbanView.objects.filter(card_cover_image_field_id=field.id).update(
                card_cover_image_field_id=None
            )
        elif isinstance(field, SingleSelectField):
            KanbanView.objects.filter(single_select_field_id=field.id).update(
                single_select_field_id=None
            )


class CalendarViewType(ViewType):
    type = "calendar"
    model_class = CalendarView
    field_options_model_class = CalendarViewFieldOptions
    field_options_serializer_class = CalendarViewFieldOptionsSerializer
    allowed_fields = [
        "date_field",
        "ical_public",
    ]
    field_options_allowed_fields = ["hidden", "order"]

    # We don't expose CalendarView.ical_slug directly only through ical_feed_url
    # property. When the user wants to change ical feed publicity status, the frontend
    # needs to send ical_public flag only.
    serializer_field_names = [
        "date_field",
        "ical_feed_url",
        "ical_public",
    ]
    serializer_field_overrides = {
        "date_field": PrimaryKeyRelatedField(
            queryset=Field.objects.all(),
            required=False,
            default=None,
            allow_null=True,
        ),
        "ical_feed_url": CharField(
            read_only=True,
            help_text="Read-only field with ICal feed endpoint. "
            "Note: this url will not be active if "
            "ical_public value is set to False.",
        ),
        "ical_public": BooleanField(
            allow_null=True,
            default=None,
            help_text="A flag to show if ical feed is exposed. "
            "Set this field to True when modifying "
            "this resource to enable ICal feed url.",
        ),
    }
    api_exceptions_map = {
        IncompatibleField: ERROR_INCOMPATIBLE_FIELD,
        FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
    }
    can_decorate = True
    can_share = True
    has_public_info = True

    def get_api_urls(self):
        from baserow_premium.api.views.calendar import urls as api_urls

        return [
            path("calendar/", include(api_urls, namespace=self.type)),
        ]

    def before_view_create(self, values: dict, table: "Table", user: "AbstractUser"):
        if values.get("ical_public"):
            values["ical_slug"] = View.create_new_slug()

    def before_view_update(self, values: dict, table: "Table", user: "AbstractUser"):
        if values.get("ical_public") and not table.ical_slug:
            table.ical_slug = View.create_new_slug()

    def prepare_values(self, values, table, user):
        """
        Check if the provided date field belongs to the same table.
        """

        date_field_value = values.get("date_field", None)
        if date_field_value is not None:
            if isinstance(date_field_value, int):
                values["date_field"] = date_field_value = Field.objects.get(
                    pk=date_field_value
                )

            date_field_value = date_field_value.specific
            field_type = field_type_registry.get_by_model(date_field_value)
            if not field_type.can_represent_date(date_field_value):
                raise IncompatibleField()

            if (
                isinstance(date_field_value, Field)
                and date_field_value.table_id != table.id
            ):
                raise FieldNotInTable(
                    "The provided date field id does not belong to the calendar "
                    "view's table."
                )

        return super().prepare_values(values, table, user)

    def export_serialized(
        self,
        calendar: View,
        import_export_config: ImportExportConfig,
        cache: Optional[Dict] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        """
        Adds the serialized calendar view options to the exported dict.
        """

        serialized = super().export_serialized(
            calendar, import_export_config, cache, files_zip, storage
        )
        if calendar.date_field_id:
            serialized["date_field_id"] = calendar.date_field_id

        serialized_field_options = []
        for field_option in calendar.get_field_options():
            serialized_field_options.append(
                {
                    "id": field_option.id,
                    "field_id": field_option.field_id,
                    "hidden": field_option.hidden,
                    "order": field_option.order,
                }
            )

        serialized["field_options"] = serialized_field_options
        return serialized

    def import_serialized(
        self,
        table: Table,
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> View:
        """
        Imports the serialized calendar view field options.
        """

        serialized_copy = serialized_values.copy()
        if "date_field_id" in serialized_copy:
            old_date_field_id = serialized_copy.pop("date_field_id")
            serialized_copy["date_field_id"] = id_mapping["database_fields"].get(
                old_date_field_id, None
            )

        field_options = serialized_copy.pop("field_options")
        calendar_view = super().import_serialized(
            table, serialized_copy, import_export_config, id_mapping, files_zip, storage
        )

        if calendar_view is not None:
            if "database_calendar_view_field_options" not in id_mapping:
                id_mapping["database_calendar_view_field_options"] = {}

            for field_option in field_options:
                field_option_copy = field_option.copy()
                field_option_id = field_option_copy.pop("id")
                field_option_copy["field_id"] = id_mapping["database_fields"][
                    field_option["field_id"]
                ]
                field_option_object = CalendarViewFieldOptions.objects.create(
                    calendar_view=calendar_view, **field_option_copy
                )
                id_mapping["database_calendar_view_field_options"][
                    field_option_id
                ] = field_option_object.id

        return calendar_view

    def view_created(self, view: View):
        """
        When a calendar view is created, we want to set the first field as visible.
        """

        field_options = view.get_field_options(create_if_missing=True).order_by(
            "-field__primary", "field__id"
        )
        ids_to_update = [f.id for f in field_options[0:1]]

        if len(ids_to_update) > 0:
            CalendarViewFieldOptions.objects.filter(id__in=ids_to_update).update(
                hidden=False
            )

    def export_prepared_values(self, view: CalendarView) -> Dict[str, Any]:
        values = super().export_prepared_values(view)
        values["date_field"] = view.date_field_id
        return values

    def get_visible_field_options_in_order(self, calendar_view: CalendarView):
        return (
            calendar_view.get_field_options(create_if_missing=True)
            .filter(
                Q(hidden=False)
                # If the `date_field_id` is set, we must always expose the field
                # because the values are needed.
                | Q(field_id=calendar_view.date_field_id)
            )
            .order_by("order", "field__id")
        )

    def get_hidden_fields(
        self,
        view: CalendarView,
        field_ids_to_check: Optional[List[int]] = None,
    ) -> Set[int]:
        hidden_field_ids = set()
        fields = view.table.field_set.all()
        field_options = view.calendarviewfieldoptions_set.all()

        if field_ids_to_check is not None:
            fields = [f for f in fields if f.id in field_ids_to_check]

        for field in fields:
            # If the `date_field_id` is set, we must always expose the field
            # because the values are needed.
            if field.id in [
                view.date_field_id,
            ]:
                continue

            field_option_matching = None
            for field_option in field_options:
                if field_option.field_id == field.id:
                    field_option_matching = field_option

            # A field is considered hidden, if it is explicitly hidden
            # or if the field options don't exist
            if field_option_matching is None or field_option_matching.hidden:
                hidden_field_ids.add(field.id)

        return hidden_field_ids

    def enhance_queryset(self, queryset):
        return queryset.prefetch_related("calendarviewfieldoptions_set")

    def after_field_delete(self, field: Field) -> None:
        CalendarView.objects.filter(date_field_id=field.id).update(date_field_id=None)


class TimelineViewType(ViewType):
    type = "timeline"
    model_class = TimelineView
    field_options_model_class = TimelineViewFieldOptions
    field_options_serializer_class = TimelineViewFieldOptionsSerializer
    allowed_fields = ["start_date_field", "end_date_field", "timescale"]
    field_options_allowed_fields = ["hidden", "order"]
    serializer_field_names = ["start_date_field", "end_date_field", "timescale"]
    serializer_field_overrides = {
        "start_date_field": PrimaryKeyRelatedField(
            queryset=Field.objects.all(),
            required=False,
            default=None,
            allow_null=True,
        ),
        "end_date_field": PrimaryKeyRelatedField(
            queryset=Field.objects.all(),
            required=False,
            default=None,
            allow_null=True,
        ),
    }
    api_exceptions_map = {
        IncompatibleField: ERROR_INCOMPATIBLE_FIELD,
        FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
        TimelineViewHasInvalidDateSettings: ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS,
    }
    can_decorate = True
    can_share = True
    has_public_info = True

    def get_api_urls(self):
        from baserow_premium.api.views.timeline import urls as api_urls

        return [
            path("timeline/", include(api_urls, namespace=self.type)),
        ]

    def raise_if_invalid_date_settings(self, view: TimelineView):
        """
        Raises an exception if the date settings are invalid.

        :param view: The timeline view instance.
        :raises TimelineViewHasInvalidDateSettings: If the date settings are invalid.
        """

        if view.start_date_field_id is None or view.end_date_field_id is None:
            raise TimelineViewHasInvalidDateSettings(
                "The start and end date fields must be set before the view can be used."
            )

        start_date_field = view.start_date_field.specific
        start_date_field_type = field_type_registry.get_by_model(start_date_field)
        if not start_date_field_type.can_represent_date(start_date_field):
            raise IncompatibleField(
                "The provided field is not a date field and cannot be used as a start date field."
            )

        end_date_field = view.end_date_field.specific
        end_date_field_type = field_type_registry.get_by_model(end_date_field)
        if not end_date_field_type.can_represent_date(end_date_field):
            raise IncompatibleField(
                "The provided field is not a date field and cannot be used as an end date field."
            )

        if not self.date_fields_are_compatible(view):
            raise TimelineViewHasInvalidDateSettings(
                "The start and end date fields must be valid date fields with the same "
                "timezone and include time settings."
            )

    def _date_fields_are_compatible(
        self, start_date_field: DateField, end_date_field: DateField
    ) -> bool:
        """
        Verify that the start and the end date fields have compatible settings. This
        means that both fields must have the same timezone (if set) and include time
        settings. If include_time is False (date only fields), the timezone setting is
        ignored. Please keep this in sync with the dateFieldsAreCompatible function in
        web-frontend/modules/baserow_premium/utils/timeline.js.

        :param start_date_field: The start date field instance.
        :return: True if the date settings are valid, otherwise False.
        :param end_date_field: The end date field instance.
        """

        start_has_time = start_date_field.date_include_time
        start_tz = start_date_field.date_force_timezone
        end_has_time = end_date_field.date_include_time
        end_tz = end_date_field.date_force_timezone
        return start_has_time == end_has_time and (
            start_has_time and start_tz == end_tz or not start_has_time
        )

    def date_fields_are_compatible(self, view: TimelineView) -> bool:
        """
        Verify that the start and the end date fields have the same timezone and include
        time settings.

        :param view: The timeline view instance.
        :return: True if the date settings are valid, otherwise False.
        """

        start_date_field = view.start_date_field.specific
        end_date_field = view.end_date_field.specific
        return self._date_fields_are_compatible(start_date_field, end_date_field)

    def prepare_date_field_value(
        self, field_value: int | Field, table_id: int
    ) -> DateField:
        """
        Prepare the date field by checking if the provided field belongs to the same
        table and if it is a date field.

        :param field_value: The provided field value from the request.
        :param table_id: The id of the table the field should belong to.
        :raises FieldNotInTable: If the provided field does not belong to the table.
        :raises IncompatibleField: If the provided field is not a date field.
        :return: The prepared date field.
        """

        if isinstance(field_value, int):
            field_value = Field.objects.get(pk=field_value)

        if field_value.table_id != table_id:
            raise FieldNotInTable(
                "The provided date field id does not belong to the timeline "
                "view's table."
            )

        field_value = field_value.specific
        field_type = field_type_registry.get_by_model(field_value)
        if not field_type.can_represent_date(field_value):
            raise IncompatibleField(
                "The provided field is not a date field and cannot be used as a start date field."
            )
        return field_value

    def prepare_values(self, values, table, user):
        """
        Check if the provided date field belongs to the same table.
        """

        start_date_field_value = values.get("start_date_field", None)
        if start_date_field_value is not None:
            values[
                "start_date_field"
            ] = start_date_field_value = self.prepare_date_field_value(
                start_date_field_value, table.id
            )

        end_date_field_value = values.get("end_date_field", None)
        if end_date_field_value is not None:
            values[
                "end_date_field"
            ] = end_date_field_value = self.prepare_date_field_value(
                end_date_field_value, table.id
            )

        if (
            start_date_field_value
            and end_date_field_value
            and not self._date_fields_are_compatible(
                start_date_field_value, end_date_field_value
            )
        ):
            raise TimelineViewHasInvalidDateSettings(
                "The start and end date fields must have the same timezone and include "
                "time settings."
            )

        return super().prepare_values(values, table, user)

    def export_serialized(
        self,
        timeline: View,
        import_export_config: ImportExportConfig,
        cache: Optional[Dict] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        """
        Adds the serialized timeline view options to the exported dict.
        """

        serialized = super().export_serialized(
            timeline, import_export_config, cache, files_zip, storage
        )
        if timeline.start_date_field_id:
            serialized["start_date_field_id"] = timeline.start_date_field_id
        if timeline.end_date_field_id:
            serialized["end_date_field_id"] = timeline.end_date_field_id

        serialized_field_options = []
        for field_option in timeline.get_field_options():
            serialized_field_options.append(
                {
                    "id": field_option.id,
                    "field_id": field_option.field_id,
                    "hidden": field_option.hidden,
                    "order": field_option.order,
                }
            )

        serialized["field_options"] = serialized_field_options
        return serialized

    def import_serialized(
        self,
        table: Table,
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> View:
        """
        Imports the serialized timeline view field options.
        """

        serialized_copy = serialized_values.copy()
        if "start_date_field_id" in serialized_copy:
            serialized_copy["start_date_field_id"] = id_mapping["database_fields"][
                serialized_copy.pop("start_date_field_id")
            ]
        if "end_date_field_id" in serialized_copy:
            serialized_copy["end_date_field_id"] = id_mapping["database_fields"][
                serialized_copy.pop("end_date_field_id")
            ]

        field_options = serialized_copy.pop("field_options")
        timeline_view = super().import_serialized(
            table, serialized_copy, import_export_config, id_mapping, files_zip, storage
        )

        if "database_timeline_view_field_options" not in id_mapping:
            id_mapping["database_timeline_view_field_options"] = {}

        for field_option in field_options:
            field_option_copy = field_option.copy()
            field_option_id = field_option_copy.pop("id")
            field_option_copy["field_id"] = id_mapping["database_fields"][
                field_option["field_id"]
            ]
            field_option_object = TimelineViewFieldOptions.objects.create(
                timeline_view=timeline_view, **field_option_copy
            )
            id_mapping["database_timeline_view_field_options"][
                field_option_id
            ] = field_option_object.id

        return timeline_view

    def view_created(self, view: View):
        """
        When a timeline view is created, we want to set the first field as visible.
        """

        field_options = view.get_field_options(create_if_missing=True).order_by(
            "-field__primary", "field__id"
        )
        ids_to_update = [f.id for f in field_options[:1]]

        if len(ids_to_update) > 0:
            TimelineViewFieldOptions.objects.filter(id__in=ids_to_update).update(
                hidden=False
            )

    def export_prepared_values(self, view: TimelineView) -> Dict[str, Any]:
        values = super().export_prepared_values(view)
        values["start_date_field"] = view.start_date_field_id
        values["end_date_field"] = view.end_date_field_id
        return values

    def get_visible_field_options_in_order(self, timeline_view: TimelineView):
        return (
            timeline_view.get_field_options(create_if_missing=True)
            .filter(
                Q(hidden=False)
                # If the `start_date_field_id` and the `end_date_field_id` is set, we
                # must always expose the field because the values are needed.
                | Q(field_id=timeline_view.start_date_field_id)
                | Q(field_id=timeline_view.end_date_field_id)
            )
            .order_by("order", "field__id")
        )

    def get_hidden_fields(
        self,
        view: TimelineView,
        field_ids_to_check: Optional[List[int]] = None,
    ) -> Set[int]:
        hidden_field_ids = set()
        fields = view.table.field_set.all()
        field_options = view.timelineviewfieldoptions_set.all()

        if field_ids_to_check is not None:
            fields = [f for f in fields if f.id in field_ids_to_check]

        for field in fields:
            # If the `start_date_field_id` and `end_date_field_id` are set, we must
            # always expose the field because the values are needed.
            if field.id in [
                view.start_date_field_id,
                view.end_date_field_id,
            ]:
                continue

            field_option_matching = None
            for field_option in field_options:
                if field_option.field_id == field.id:
                    field_option_matching = field_option

            # A field is considered hidden, if it is explicitly hidden
            # or if the field options don't exist
            if field_option_matching is None or field_option_matching.hidden:
                hidden_field_ids.add(field.id)

        return hidden_field_ids

    def _reset_views_with_incpompatible_fields(self, field):
        TimelineView.objects.filter(start_date_field_id=field.id).update(
            start_date_field_id=None
        )
        TimelineView.objects.filter(end_date_field_id=field.id).update(
            end_date_field_id=None
        )

    def after_field_delete(self, field: Field) -> None:
        self._reset_views_with_incpompatible_fields(field)

    def enhance_queryset(self, queryset):
        return queryset.select_related(
            "start_date_field", "end_date_field"
        ).prefetch_related("timelineviewfieldoptions_set")
