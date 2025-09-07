from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.files.storage import Storage
from django.db.models import Count, Q
from django.urls import include, path

from rest_framework import serializers

from baserow.api.user_files.serializers import UserFileField
from baserow.contrib.database.api.fields.errors import (
    ERROR_FIELD_NOT_IN_TABLE,
    ERROR_INCOMPATIBLE_FIELD,
    ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD,
)
from baserow.contrib.database.api.views.form.errors import (
    ERROR_FORM_VIEW_FIELD_OPTIONS_CONDITION_GROUP_DOES_NOT_EXIST,
    ERROR_FORM_VIEW_FIELD_TYPE_IS_NOT_SUPPORTED,
    ERROR_FORM_VIEW_READ_ONLY_FIELD_IS_NOT_SUPPORTED,
)
from baserow.contrib.database.api.views.form.exceptions import (
    FormViewFieldOptionsConditionGroupDoesNotExist,
)
from baserow.contrib.database.api.views.form.serializers import (
    FormViewFieldOptionsSerializer,
    FormViewNotifyOnSubmitSerializerMixin,
)
from baserow.contrib.database.api.views.gallery.serializers import (
    GalleryViewFieldOptionsSerializer,
)
from baserow.contrib.database.api.views.grid.errors import (
    ERROR_AGGREGATION_DOES_NOT_SUPPORTED_FIELD,
)
from baserow.contrib.database.api.views.grid.serializers import (
    GridViewFieldOptionsSerializer,
)
from baserow.contrib.database.fields.exceptions import (
    FieldNotInTable,
    IncompatibleField,
    SelectOptionDoesNotBelongToField,
)
from baserow.contrib.database.fields.models import Field, FileField, SelectOption
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.registries import view_aggregation_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.import_export.utils import file_chunk_generator
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import ExportZipFile
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.models import UserFile

from .exceptions import (
    FormViewFieldTypeIsNotSupported,
    FormViewReadOnlyFieldIsNotSupported,
    GridViewAggregationDoesNotSupportField,
)
from .handler import ViewHandler
from .models import (
    FormView,
    FormViewFieldOptions,
    FormViewFieldOptionsAllowedSelectOptions,
    FormViewFieldOptionsCondition,
    FormViewFieldOptionsConditionGroup,
    GalleryView,
    GalleryViewFieldOptions,
    GridView,
    GridViewFieldOptions,
    View,
)
from .registries import ViewType, form_view_mode_registry, view_filter_type_registry


class GridViewType(ViewType):
    type = "grid"
    model_class = GridView
    field_options_model_class = GridViewFieldOptions
    field_options_serializer_class = GridViewFieldOptionsSerializer
    can_aggregate_field = True
    can_share = True
    can_decorate = True
    has_public_info = True
    can_group_by = True
    when_shared_publicly_requires_realtime_events = True
    allowed_fields = ["row_identifier_type", "row_height_size"]
    field_options_allowed_fields = [
        "width",
        "hidden",
        "order",
        "aggregation_type",
        "aggregation_raw_type",
    ]
    serializer_field_names = ["row_identifier_type", "row_height_size"]

    api_exceptions_map = {
        GridViewAggregationDoesNotSupportField: ERROR_AGGREGATION_DOES_NOT_SUPPORTED_FIELD,
    }

    def get_api_urls(self):
        from baserow.contrib.database.api.views.grid import urls as api_urls

        return [
            path("grid/", include(api_urls, namespace=self.type)),
        ]

    def export_serialized(
        self,
        grid: View,
        import_export_config: ImportExportConfig,
        cache: Optional[Dict] = None,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        """
        Adds the serialized grid view options to the exported dict.
        """

        serialized = super().export_serialized(
            grid, import_export_config, cache, files_zip, storage
        )
        serialized["row_identifier_type"] = grid.row_identifier_type
        serialized["row_height_size"] = grid.row_height_size

        serialized_field_options = []
        for field_option in grid.get_field_options():
            serialized_field_options.append(
                {
                    "id": field_option.id,
                    "field_id": field_option.field_id,
                    "width": field_option.width,
                    "hidden": field_option.hidden,
                    "order": field_option.order,
                    "aggregation_type": field_option.aggregation_type,
                    "aggregation_raw_type": field_option.aggregation_raw_type,
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
        Imports the serialized grid view field options.
        """

        serialized_copy = serialized_values.copy()
        field_options = serialized_copy.pop("field_options")
        grid_view = super().import_serialized(
            table, serialized_copy, import_export_config, id_mapping, files_zip, storage
        )
        if grid_view is not None:
            if "database_grid_view_field_options" not in id_mapping:
                id_mapping["database_grid_view_field_options"] = {}

            for field_option in field_options:
                field_option_copy = field_option.copy()
                field_option_id = field_option_copy.pop("id")
                field_option_copy["field_id"] = id_mapping["database_fields"][
                    field_option["field_id"]
                ]
                field_option_object = GridViewFieldOptions.objects.create(
                    grid_view=grid_view, **field_option_copy
                )
                id_mapping["database_grid_view_field_options"][
                    field_option_id
                ] = field_option_object.id

        return grid_view

    def get_visible_fields_and_model(self, view):
        """
        Returns the model and the field options in the correct order for exporting
        this view type.
        """

        grid_view = ViewHandler().get_view(view.id, view_model=GridView)
        ordered_visible_field_ids = self.get_visible_field_options_in_order(
            grid_view
        ).values_list("field__id", flat=True)
        model = grid_view.table.get_model(field_ids=ordered_visible_field_ids)
        ordered_field_objects = [
            model._field_objects[field_id] for field_id in ordered_visible_field_ids
        ]
        return ordered_field_objects, model

    def before_field_options_update(self, view, field_options, fields):
        """
        Checks if a aggregation raw types are compatible with the field types.
        """

        fields_dict = {field.id: field for field in fields}

        for field_id, options in field_options.items():
            field = fields_dict.get(int(field_id), None)
            aggregation_raw_type = options.get("aggregation_raw_type")

            if aggregation_raw_type and field:
                try:
                    # Invalidate cache if new aggregation raw type has changed
                    prev_options = GridViewFieldOptions.objects.only(
                        "aggregation_raw_type"
                    ).get(field=field, grid_view=view)
                    if prev_options.aggregation_raw_type != aggregation_raw_type:
                        ViewHandler().clear_aggregation_cache(view, field.db_column)
                except GridViewFieldOptions.DoesNotExist:
                    pass

                # Checks if the aggregation raw type is compatible with the field type
                aggregation_type = view_aggregation_type_registry.get(
                    aggregation_raw_type
                )
                if not aggregation_type.field_is_compatible(field):
                    raise GridViewAggregationDoesNotSupportField(aggregation_type)

        return field_options

    def after_fields_type_change(self, fields):
        """
        Check field option aggregation_raw_type compatibility with the new field type.
        """

        field_options = (
            GridViewFieldOptions.objects_and_trash.filter(field__in=fields)
            .exclude(aggregation_raw_type="")
            .select_related("grid_view", "field")
        )

        view_handler = ViewHandler()

        for field_option in field_options:
            aggregation_type = view_aggregation_type_registry.get(
                field_option.aggregation_raw_type
            )

            view_handler.clear_aggregation_cache(
                field_option.grid_view, field_option.field.db_column
            )

            if not aggregation_type.field_is_compatible(field_option.field):
                # The field has an aggregation and the type is not compatible with
                # the new field, so we need to clean the aggregation.
                # @TODO check if there are multiple fields from the same field and
                #  update them in bulk.
                view_handler.update_field_options(
                    view=field_option.grid_view,
                    field_options={
                        field_option.field_id: {
                            "aggregation_type": "",
                            "aggregation_raw_type": "",
                        }
                    },
                )

    def get_visible_field_options_in_order(self, grid_view):
        return (
            grid_view.get_field_options(create_if_missing=True)
            .filter(hidden=False)
            .order_by("-field__primary", "order", "field__id")
        )

    def get_aggregations(self, grid_view):
        """
        Returns the (Field, aggregation_type) list computed from the field options for
        the specified view.
        """

        field_options = (
            GridViewFieldOptions.objects.filter(grid_view=grid_view)
            .exclude(aggregation_raw_type="")
            .select_related("field")
        )
        return [(option.field, option.aggregation_raw_type) for option in field_options]

    def after_field_value_update(self, updated_fields):
        """
        When a field value change, we need to invalidate the aggregation cache for this
        field.
        """

        to_clear = defaultdict(list)
        view_map = {}

        field_options = (
            GridViewFieldOptions.objects.filter(field__in=updated_fields)
            .exclude(aggregation_raw_type="")
            .select_related("grid_view", "field")
        )

        for options in field_options:
            to_clear[options.grid_view.id].append(options.field.db_column)
            view_map[options.grid_view.id] = options.grid_view

        view_handler = ViewHandler()
        for view_id, names in to_clear.items():
            view_handler.clear_aggregation_cache(view_map[view_id], names + ["total"])

    def after_field_update(self, updated_fields):
        """
        When a field configuration is changed, we need to invalid the cache for
        corresponding aggregations also.
        """

        self.after_field_value_update(updated_fields)

    def after_filter_update(self, grid_view):
        """
        If the view filters change we also need to invalid the aggregation cache for all
        fields of this view.
        """

        ViewHandler().clear_full_aggregation_cache(grid_view)

    def get_hidden_fields(
        self,
        view: GridView,
        field_ids_to_check: Optional[List[int]] = None,
    ) -> Set[int]:
        fields_with_options = view.gridviewfieldoptions_set.all()
        field_ids_with_options = {o.field_id for o in fields_with_options}
        hidden_field_ids = {o.field_id for o in fields_with_options if o.hidden}
        # Hide fields in shared views by default if they don't have field_options.
        if view.public:
            if field_ids_to_check is None:
                field_ids_to_check = [f.id for f in view.table.field_set.all()]
            additional_hidden_field_ids = {
                f_id
                for f_id in field_ids_to_check
                if f_id not in field_ids_with_options
            }
            hidden_field_ids |= additional_hidden_field_ids

        return hidden_field_ids

    def enhance_queryset(self, queryset):
        return queryset.prefetch_related("gridviewfieldoptions_set")


class GalleryViewType(ViewType):
    type = "gallery"
    model_class = GalleryView
    field_options_model_class = GalleryViewFieldOptions
    field_options_serializer_class = GalleryViewFieldOptionsSerializer
    allowed_fields = ["card_cover_image_field"]
    field_options_allowed_fields = ["hidden", "order"]
    serializer_field_names = ["card_cover_image_field"]
    serializer_field_overrides = {
        "card_cover_image_field": serializers.PrimaryKeyRelatedField(
            queryset=Field.objects.all(),
            required=False,
            default=None,
            allow_null=True,
            help_text="References a file field of which the first image must be shown "
            "as card cover image.",
        )
    }
    api_exceptions_map = {
        FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
        IncompatibleField: ERROR_INCOMPATIBLE_FIELD,
    }
    can_decorate = True
    can_share = True
    has_public_info = True

    def get_api_urls(self):
        from baserow.contrib.database.api.views.gallery import urls as api_urls

        return [
            path("gallery/", include(api_urls, namespace=self.type)),
        ]

    def prepare_values(self, values, table, user):
        """
        Check if the provided card cover image field belongs to the same table.
        """

        name = "card_cover_image_field"

        if values.get(name, None) is not None:
            if isinstance(values[name], int):
                values[name] = Field.objects.get(pk=values[name])

            field_type = field_type_registry.get_by_model(values[name].specific)
            if not field_type.can_represent_files(values[name]):
                raise IncompatibleField(
                    "The provided field cannot be used as a card cover image field."
                )
            elif values[name].table_id != table.id:
                raise FieldNotInTable(
                    "The provided file select field id does not belong to the gallery "
                    "view's table."
                )

        return super().prepare_values(values, table, user)

    def after_fields_type_change(self, fields):
        fields_cannot_represent_files = [
            field
            for field in fields
            if not field_type_registry.get_by_model(
                field.specific_class
            ).can_represent_files(field)
        ]
        if len(fields_cannot_represent_files) > 0:
            GalleryView.objects.filter(
                card_cover_image_field_id__in=[
                    f.id for f in fields_cannot_represent_files
                ]
            ).update(card_cover_image_field_id=None)

    def export_serialized(
        self,
        gallery: View,
        import_export_config: ImportExportConfig,
        cache: Optional[Dict] = None,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        """
        Adds the serialized gallery view options to the exported dict.
        """

        serialized = super().export_serialized(
            gallery, import_export_config, cache, files_zip, storage
        )

        if gallery.card_cover_image_field_id:
            serialized["card_cover_image_field_id"] = gallery.card_cover_image_field_id

        serialized_field_options = []
        for field_option in gallery.get_field_options():
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
        Imports the serialized gallery view field options.
        """

        serialized_copy = serialized_values.copy()

        if serialized_copy.get("card_cover_image_field_id", None):
            serialized_copy["card_cover_image_field_id"] = id_mapping[
                "database_fields"
            ][serialized_copy["card_cover_image_field_id"]]

        field_options = serialized_copy.pop("field_options")

        gallery_view = super().import_serialized(
            table, serialized_copy, import_export_config, id_mapping, files_zip, storage
        )

        if gallery_view is not None:
            if "database_gallery_view_field_options" not in id_mapping:
                id_mapping["database_gallery_view_field_options"] = {}

            for field_option in field_options:
                field_option_copy = field_option.copy()
                field_option_id = field_option_copy.pop("id")
                field_option_copy["field_id"] = id_mapping["database_fields"][
                    field_option["field_id"]
                ]
                field_option_object = GalleryViewFieldOptions.objects.create(
                    gallery_view=gallery_view, **field_option_copy
                )
                id_mapping["database_gallery_view_field_options"][
                    field_option_id
                ] = field_option_object.id

        return gallery_view

    def view_created(self, view):
        """
        When a gallery view is created, we want to set the first three fields as
        visible.
        """

        field_options = view.get_field_options(create_if_missing=True).order_by(
            "-field__primary", "field__id"
        )
        ids_to_update = [f.id for f in field_options[0:3]]

        if ids_to_update:
            GalleryViewFieldOptions.objects.filter(id__in=ids_to_update).update(
                hidden=False
            )

    def export_prepared_values(self, view: GalleryView) -> Dict[str, Any]:
        """
        Add `card_cover_image_field` to the exportable fields.

        :param view: The gallery view to export.
        :return: The prepared values.
        """

        values = super().export_prepared_values(view)
        values["card_cover_image_field"] = view.card_cover_image_field_id

        return values

    def get_visible_field_options_in_order(self, gallery_view: GalleryView):
        return (
            gallery_view.get_field_options(create_if_missing=True)
            .filter(
                Q(hidden=False) | Q(field__id=gallery_view.card_cover_image_field_id)
            )
            .order_by("order", "field__id")
        )

    def get_hidden_fields(
        self,
        view: GalleryView,
        field_ids_to_check: Optional[List[int]] = None,
    ) -> Set[int]:
        hidden_field_ids = set()
        fields = view.table.field_set.all()
        field_options = view.galleryviewfieldoptions_set.all()

        if field_ids_to_check is not None:
            fields = [f for f in fields if f.id in field_ids_to_check]

        for field in fields:
            # The card cover image field is always visible.
            if field.id == view.card_cover_image_field_id:
                continue

            # Find corresponding field option
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
        return queryset.prefetch_related("galleryviewfieldoptions_set")

    def after_field_delete(self, field: Field) -> None:
        if isinstance(field, FileField):
            GalleryView.objects.filter(card_cover_image_field_id=field.id).update(
                card_cover_image_field_id=None
            )


class FormViewType(ViewType):
    type = "form"
    model_class = FormView
    can_filter = False
    can_sort = False
    can_share = True
    can_list_rows = False
    restrict_link_row_public_view_sharing = False
    when_shared_publicly_requires_realtime_events = False
    field_options_model_class = FormViewFieldOptions
    field_options_serializer_class = FormViewFieldOptionsSerializer
    allowed_fields = [
        "title",
        "description",
        "mode",
        "cover_image",
        "logo_image",
        "submit_text",
        "submit_action",
        "submit_action_message",
        "submit_action_redirect_url",
        "users_to_notify_on_submit",
    ]
    field_options_allowed_fields = [
        "name",
        "description",
        "enabled",
        "required",
        "show_when_matching_conditions",
        "condition_type",
        "order",
        "field_component",
        "include_all_select_options",
    ]
    serializer_mixins = [FormViewNotifyOnSubmitSerializerMixin]
    serializer_field_names = [
        "title",
        "description",
        "mode",
        "cover_image",
        "logo_image",
        "submit_text",
        "submit_action",
        "submit_action_message",
        "submit_action_redirect_url",
        "receive_notification_on_submit",  # from FormViewNotifyOnSubmitSerializerMixin
    ]
    serializer_field_overrides = {
        "cover_image": UserFileField(
            required=False,
            help_text="The cover image that must be displayed at the top of the form.",
        ),
        "logo_image": UserFileField(
            required=False,
            help_text="The logo image that must be displayed at the top of the form.",
        ),
    }
    api_exceptions_map = {
        FormViewFieldTypeIsNotSupported: ERROR_FORM_VIEW_FIELD_TYPE_IS_NOT_SUPPORTED,
        FormViewReadOnlyFieldIsNotSupported: ERROR_FORM_VIEW_READ_ONLY_FIELD_IS_NOT_SUPPORTED,
        FormViewFieldOptionsConditionGroupDoesNotExist: ERROR_FORM_VIEW_FIELD_OPTIONS_CONDITION_GROUP_DOES_NOT_EXIST,
        SelectOptionDoesNotBelongToField: ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD,
    }

    def get_api_urls(self):
        from baserow.contrib.database.api.views.form import urls as api_urls

        return [
            path("form/", include(api_urls, namespace=self.type)),
        ]

    def after_fields_type_change(self, fields):
        fields_cannot_be_in_form_view = [
            field
            for field in fields
            if not field_type_registry.get_by_model(
                field.specific_class
            ).can_be_in_form_view
        ]
        if len(fields_cannot_be_in_form_view) > 0:
            # If the new field type is not compatible with the form view, we must
            # disable all the form view field options because they're not compatible
            # anymore.
            FormViewFieldOptions.objects_and_trash.filter(
                field__in=[f.id for f in fields_cannot_be_in_form_view], enabled=True
            ).update(enabled=False)

    def before_field_options_update(self, view, field_options, fields):
        """
        Checks if a field type that is incompatible with the form view is being
        enabled.
        """

        fields_dict = {field.id: field for field in fields}
        for field_id, options in field_options.items():
            field = fields_dict.get(int(field_id), None)
            if options.get("enabled") and field:
                field_type = field_type_registry.get_by_model(field.specific_class)
                if field.read_only:
                    raise FormViewReadOnlyFieldIsNotSupported(field.name)
                if not field_type.can_be_in_form_view:
                    raise FormViewFieldTypeIsNotSupported(field_type.type)

        return field_options

    def _prepare_new_condition_group(
        self, updated_field_option_instance, group, existing_condition_group_ids
    ):
        parent_group_id = group.get("parent_group", None)
        if (
            parent_group_id is not None
            and parent_group_id not in existing_condition_group_ids
        ):
            raise FormViewFieldOptionsConditionGroupDoesNotExist(
                "Invalid parent filter group id."
            )
        return FormViewFieldOptionsConditionGroup(
            field_option=updated_field_option_instance,
            filter_type=group["filter_type"],
            parent_group_id=group.get("parent_group", None),
        )

    def _group_exists_and_matches_field(self, existing_group, numeric_field_id):
        return (
            existing_group is not None
            and existing_group.field_option.field_id == numeric_field_id
        )

    def _prepare_condition_groups(
        self,
        field_options: Dict[str, Any],
        updated_field_options_by_field_id: Dict[int, FormViewFieldOptions],
        existing_condition_groups: Dict[int, FormViewFieldOptionsConditionGroup],
    ) -> Tuple[
        List[int],
        List[FormViewFieldOptionsConditionGroup],
        List[FormViewFieldOptionsConditionGroup],
        List[int],
    ]:
        """
        Figures out which condition groups need to be created, updated or deleted in
        order to match the provided field options.
        """

        groups_to_create_temp_ids = []
        groups_to_create = []
        groups_to_update = []
        existing_condition_group_ids = set(existing_condition_groups.keys())
        group_ids_to_delete = existing_condition_group_ids.copy()

        for field_id, options in field_options.items():
            if "condition_groups" not in options:
                continue

            numeric_field_id = int(field_id)
            updated_field_option_instance = updated_field_options_by_field_id[
                numeric_field_id
            ]

            for group in options["condition_groups"]:
                existing_group = existing_condition_groups.get(group["id"], None)

                parent_group_id = group.get("parent_group", None)
                if (
                    parent_group_id is not None
                    and parent_group_id in group_ids_to_delete
                ):
                    group_ids_to_delete.remove(parent_group_id)

                if self._group_exists_and_matches_field(
                    existing_group, numeric_field_id
                ):
                    existing_group.filter_type = group["filter_type"]
                    groups_to_update.append(existing_group)
                    group_ids_to_delete.remove(existing_group.id)

                else:
                    new_condition_group = self._prepare_new_condition_group(
                        updated_field_option_instance,
                        group,
                        existing_condition_group_ids,
                    )
                    groups_to_create_temp_ids.append(group["id"])
                    groups_to_create.append(new_condition_group)

        return (
            groups_to_create_temp_ids,
            groups_to_create,
            groups_to_update,
            group_ids_to_delete,
        )

    def _update_field_options_condition_groups(
        self,
        field_options: Dict[str, Any],
        updated_field_options_by_field_id: Dict[int, FormViewFieldOptions],
        existing_condition_groups: Dict[int, FormViewFieldOptionsConditionGroup],
    ) -> Dict[int, FormViewFieldOptionsConditionGroup]:
        """
        Updates the condition groups for the specified field options. Based on
        the new provided field options and the existing groups, this function
        figures out which groups need to be created, updated or deleted in order
        to match the options provided.

        :param field_options: The field options that are being updated.
        :param updated_field_options_by_field_id: A map containing the updated field
            options by field id.
        :param existing_condition_groups: A map containing the existing condition
            groups by id.
        :return: A map between the condition groups and their temporary id.
        """

        (
            groups_to_create_temp_ids,
            groups_to_create,
            groups_to_update,
            group_ids_to_delete,
        ) = self._prepare_condition_groups(
            field_options, updated_field_options_by_field_id, existing_condition_groups
        )

        groups_created = []
        if len(groups_to_create) > 0:
            groups_created = FormViewFieldOptionsConditionGroup.objects.bulk_create(
                groups_to_create
            )

        if len(groups_to_update) > 0:
            FormViewFieldOptionsConditionGroup.objects.bulk_update(
                groups_to_update, ["filter_type"]
            )

        if len(group_ids_to_delete) > 0:
            FormViewFieldOptionsConditionGroup.objects.filter(
                id__in=group_ids_to_delete
            ).delete()

        # The map contains the temporary ids for the newly created groups, so
        # that we can later map filters to the correct group.
        condition_group_ids_map = {
            **{
                groups_to_create_temp_ids[i]: groups_created[i]
                for i in range(len(groups_created))
            },
            **{group.id: group for group in groups_to_update},
        }

        return condition_group_ids_map

    def _prepare_condition_update(self, existing_condition, condition, group_id):
        existing_condition.field_id = condition["field"]
        existing_condition.type = condition["type"]
        existing_condition.value = condition["value"]
        existing_condition.group_id = group_id

    def _prepare_new_condition(
        self, updated_field_option_instance, condition, group_id
    ) -> FormViewFieldOptionsCondition:
        return FormViewFieldOptionsCondition(
            field_option=updated_field_option_instance,
            field_id=condition["field"],
            type=condition["type"],
            value=condition["value"],
            group_id=group_id,
        )

    def _get_group_id(self, condition, condition_group_id_map):
        group_id = condition.get("group", None)
        if group_id is None:
            return None
        elif group_id in condition_group_id_map:
            return condition_group_id_map[group_id].id
        else:
            raise FormViewFieldOptionsConditionGroupDoesNotExist(
                "Invalid filter group id."
            )

    def _condition_exists_and_matches_field(self, existing_condition, numeric_field_id):
        return (
            existing_condition is not None
            and existing_condition.field_option.field_id == numeric_field_id
        )

    def _prepare_conditions(
        self,
        field_options: Dict[str, Any],
        updated_field_options_by_field_id,
        existing_conditions: Dict[int, FormViewFieldOptionsCondition],
        condition_group_id_map,
        table_id: int,
        table_field_ids: Set[int],
    ) -> Tuple[
        List[FormViewFieldOptionsCondition],
        List[FormViewFieldOptionsCondition],
        List[int],
    ]:
        """
        Figures out which conditions need to be created, updated or deleted in
        order to match the options provided.
        """

        conditions_to_create = []
        conditions_to_update = []
        condition_ids_to_delete = set(existing_conditions.keys())

        for field_id, options in field_options.items():
            if "conditions" not in options:
                continue

            numeric_field_id = int(field_id)
            updated_field_option_instance = updated_field_options_by_field_id[
                numeric_field_id
            ]

            for condition in options["conditions"]:
                if condition["field"] not in table_field_ids:
                    raise FieldNotInTable(
                        f"The field {condition['field']} does not belong to table {table_id}."
                    )

                existing_condition = existing_conditions.get(condition["id"], None)
                group_id = self._get_group_id(condition, condition_group_id_map)

                if self._condition_exists_and_matches_field(
                    existing_condition, numeric_field_id
                ):
                    self._prepare_condition_update(
                        existing_condition, condition, group_id
                    )
                    conditions_to_update.append(existing_condition)
                    condition_ids_to_delete.remove(existing_condition.id)
                else:
                    new_condition = self._prepare_new_condition(
                        updated_field_option_instance, condition, group_id
                    )
                    conditions_to_create.append(new_condition)

        return conditions_to_create, conditions_to_update, condition_ids_to_delete

    def _update_field_options_conditions(
        self,
        view: View,
        field_options: Dict[str, Any],
        existing_conditions: Dict[int, FormViewFieldOptionsCondition],
        table_field_ids: Set[int],
        updated_field_options_by_field_id: Dict[int, FormViewFieldOptions],
        condition_group_id_map: Dict[int, FormViewFieldOptionsConditionGroup],
    ):
        """
        Updates the conditions for the specified field options. Based on the new
        provided field options and the existing conditions, this function figures out
        which conditions need to be created, updated or deleted in order to match the
        options provided.

        :param view: The form view instance.
        :param field_options: The field options that are being updated.
        :param existing_conditions: A map containing the existing conditions by id.
        :param table_field_ids: A set containing all the field ids that belong to the
            table.
        :param updated_field_options_by_field_id: A map containing the updated field
            options by field id.
        :param condition_group_id_map: A map containing the condition group ids by
            temporary id.
        """

        (
            conditions_to_create,
            conditions_to_update,
            condition_ids_to_delete,
        ) = self._prepare_conditions(
            field_options,
            updated_field_options_by_field_id,
            existing_conditions,
            condition_group_id_map,
            view.table_id,
            table_field_ids,
        )

        if len(conditions_to_create) > 0:
            FormViewFieldOptionsCondition.objects.bulk_create(conditions_to_create)

        if len(conditions_to_update) > 0:
            FormViewFieldOptionsCondition.objects.bulk_update(
                conditions_to_update, ["field_id", "type", "value"]
            )

        if len(condition_ids_to_delete) > 0:
            FormViewFieldOptionsCondition.objects.filter(
                id__in=condition_ids_to_delete
            ).delete()

    def after_field_options_update(
        self, view, field_options, fields, update_field_option_instances
    ):
        """
        This method is called directly after the form view field options are updated.
        It will create, update or delete the provided conditions in a query efficient
        manner.
        """

        field_ids = {field.id for field in fields}
        updated_field_options_by_field_id = {
            o.field_id: o for o in update_field_option_instances
        }
        updated_field_options = [
            updated_field_options_by_field_id[field_id]
            for field_id, options in field_options.items()
            if "conditions" in options
        ]

        # Prefetch all the existing conditions to avoid N amount of queries later on.
        existing_conditions = {
            c.id: c
            for c in FormViewFieldOptionsCondition.objects.filter(
                field_option__in=updated_field_options,
            ).select_related("field_option")
        }
        existing_condition_groups = {
            g.id: g
            for g in FormViewFieldOptionsConditionGroup.objects.filter(
                field_option__in=updated_field_options,
            ).select_related("field_option")
        }

        condition_group_ids_map = self._update_field_options_condition_groups(
            field_options,
            updated_field_options_by_field_id,
            existing_condition_groups,
        )

        self._update_field_options_conditions(
            view,
            field_options,
            existing_conditions,
            field_ids,
            updated_field_options_by_field_id,
            condition_group_ids_map,
        )

        # Delete all groups that have no conditions anymore.
        FormViewFieldOptionsConditionGroup.objects.filter(
            field_option__in=updated_field_options
        ).annotate(
            count=Count("conditions") + Count("formviewfieldoptionsconditiongroup")
        ).filter(
            count=0
        ).delete()

        self._update_field_options_allowed_select_options(
            view, field_options, updated_field_options_by_field_id
        )

    def _update_field_options_allowed_select_options(
        self, view, field_options, updated_field_options_by_field_id
    ):
        # Dict containing the field options object as key and a list of desired field
        # option IDs based on the provided `field_options`.
        desired_allowed_select_options = {}
        for field_id, options in field_options.items():
            field_options_id = updated_field_options_by_field_id[int(field_id)]
            if "allowed_select_options" in options:
                desired_allowed_select_options[field_options_id] = options[
                    "allowed_select_options"
                ]

        # No need to execute any query if no select options have been provided.
        if len(desired_allowed_select_options) == 0:
            return

        # Fetch the available select options per field, so that we can check whether
        # the provided select option is allowed.
        select_options_per_field_options_field = defaultdict(list)
        for select_option in SelectOption.objects.filter(
            field__in=[
                field_id
                for field_id, options in field_options.items()
                if "allowed_select_options" in options
            ]
        ).values("field_id", "id"):
            select_options_per_field_options_field[select_option["field_id"]].append(
                select_option["id"]
            )

        # Fetch the existing allowed select options of the updated field options,
        # so that we can compare with the `desired_allowed_select_options` and figure
        # out which one must be created and deleted.
        existing_allowed_select_options = defaultdict(list)
        for (
            allowed_select_option
        ) in FormViewFieldOptionsAllowedSelectOptions.objects.filter(
            form_view_field_options__in=[
                updated_field_options_by_field_id[field_id].id
                for field_id, options in field_options.items()
                if "allowed_select_options" in options
            ],
        ):
            existing_allowed_select_options[
                allowed_select_option.form_view_field_options_id
            ].append(allowed_select_option.select_option_id)

        to_create = []
        to_delete = []

        for (
            form_view_field_options,
            desired_select_options,
        ) in desired_allowed_select_options.items():
            existing_select_options = set(
                existing_allowed_select_options.get(form_view_field_options.id, [])
            )
            desired_select_options = set(desired_select_options)

            for select_option_id in desired_select_options - existing_select_options:
                if (
                    select_option_id
                    not in select_options_per_field_options_field[
                        form_view_field_options.field_id
                    ]
                ):
                    raise SelectOptionDoesNotBelongToField(
                        select_option_id, form_view_field_options.field_id
                    )
                to_create.append(
                    FormViewFieldOptionsAllowedSelectOptions(
                        form_view_field_options_id=form_view_field_options.id,
                        select_option_id=select_option_id,
                    )
                )

            for select_option_id in existing_select_options - desired_select_options:
                to_delete.append(select_option_id)

        if to_delete:
            FormViewFieldOptionsAllowedSelectOptions.objects.filter(
                form_view_field_options__in=desired_allowed_select_options.keys(),
                select_option_id__in=to_delete,
            ).delete()

        if to_create:
            FormViewFieldOptionsAllowedSelectOptions.objects.bulk_create(to_create)

    def export_serialized(
        self,
        form: View,
        import_export_config: ImportExportConfig,
        cache: Optional[Dict] = None,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        """
        Adds the serialized form view options to the exported dict.
        """

        serialized = super().export_serialized(
            form, import_export_config, cache, files_zip, storage
        )

        def add_user_file(user_file):
            if not user_file:
                return None

            name = user_file.name
            namelist = (
                [item["name"] for item in files_zip.info_list()]
                if files_zip is not None
                else []
            )
            if files_zip is not None and name not in namelist:
                file_path = UserFileHandler().user_file_path(name)

                chunk_generator = file_chunk_generator(storage, file_path)
                files_zip.add(chunk_generator, name)

            return {"name": name, "original_name": user_file.original_name}

        serialized["title"] = form.title
        serialized["description"] = form.description
        serialized["cover_image"] = add_user_file(form.cover_image)
        serialized["logo_image"] = add_user_file(form.logo_image)
        serialized["submit_text"] = form.submit_text
        serialized["submit_action"] = form.submit_action
        serialized["submit_action_message"] = form.submit_action_message
        serialized["submit_action_redirect_url"] = form.submit_action_redirect_url

        serialized_field_options = []
        for field_option in form.get_field_options():
            serialized_field_options.append(
                {
                    "id": field_option.id,
                    "field_id": field_option.field_id,
                    "name": field_option.name,
                    "description": field_option.description,
                    "enabled": field_option.enabled,
                    "required": field_option.required,
                    "order": field_option.order,
                    "show_when_matching_conditions": field_option.show_when_matching_conditions,
                    "condition_type": field_option.condition_type,
                    "conditions": [
                        {
                            "id": condition.id,
                            "field": condition.field_id,
                            "type": condition.type,
                            "group": condition.group_id,
                            "value": view_filter_type_registry.get(
                                condition.type
                            ).get_export_serialized_value(condition.value, {}),
                        }
                        for condition in field_option.conditions.all()
                    ],
                    "condition_groups": [
                        {
                            "id": condition_group.id,
                            "parent_group": condition_group.parent_group_id,
                            "filter_type": condition_group.filter_type,
                        }
                        for condition_group in field_option.condition_groups.all()
                    ],
                    "field_component": field_option.field_component,
                    "include_all_select_options": field_option.include_all_select_options,
                    "allowed_select_options": [
                        s.id for s in field_option.allowed_select_options.all()
                    ],
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
        Imports the serialized form view and field options.
        """

        def get_file(file):
            if not file:
                return None

            if files_zip is None:
                user_file = UserFileHandler().get_user_file_by_name(file["name"])
            else:
                with files_zip.open(file["name"]) as stream:
                    user_file = UserFileHandler().upload_user_file(
                        None, file["original_name"], stream, storage=storage
                    )
            return user_file

        serialized_copy = serialized_values.copy()
        serialized_copy["cover_image"] = get_file(serialized_copy.pop("cover_image"))
        serialized_copy["logo_image"] = get_file(serialized_copy.pop("logo_image"))
        field_options = serialized_copy.pop("field_options")
        form_view = super().import_serialized(
            table, serialized_copy, import_export_config, id_mapping, files_zip, storage
        )

        if form_view is not None:
            if "database_form_view_field_options" not in id_mapping:
                id_mapping["database_form_view_field_options"] = {}
                id_mapping["database_form_view_condition_groups"] = {}

            condition_objects = []
            form_view_field_options_allowed_select_options = []
            for field_option in field_options:
                field_option_copy = field_option.copy()
                field_option_id = field_option_copy.pop("id")
                field_option_conditions = field_option_copy.pop("conditions", [])
                field_option_condition_groups = field_option_copy.pop(
                    "condition_groups", []
                )
                allowed_select_options = field_option_copy.pop(
                    "allowed_select_options", []
                )
                field_option_copy["field_id"] = id_mapping["database_fields"][
                    field_option["field_id"]
                ]
                field_option_object = FormViewFieldOptions.objects.create(
                    form_view=form_view, **field_option_copy
                )
                for condition_group in field_option_condition_groups:
                    condition_group_copy = condition_group.copy()
                    condition_group_id = condition_group_copy.pop("id")
                    if condition_group_copy["parent_group"]:
                        condition_group_copy["parent_group_id"] = id_mapping[
                            "database_form_view_condition_groups"
                        ][condition_group_copy.pop("parent_group")]
                    condition_group_object = (
                        FormViewFieldOptionsConditionGroup.objects.create(
                            field_option=field_option_object, **condition_group_copy
                        )
                    )
                    id_mapping["database_form_view_condition_groups"][
                        condition_group_id
                    ] = condition_group_object.id
                for condition in field_option_conditions:
                    value = view_filter_type_registry.get(
                        condition["type"]
                    ).set_import_serialized_value(condition["value"], id_mapping)
                    mapped_group_id = None
                    group = condition.get("group", None)
                    if group:
                        mapped_group_id = id_mapping[
                            "database_form_view_condition_groups"
                        ][group]
                    condition_objects.append(
                        FormViewFieldOptionsCondition(
                            field_option=field_option_object,
                            field_id=id_mapping["database_fields"][condition["field"]],
                            type=condition["type"],
                            value=value,
                            group_id=mapped_group_id,
                        )
                    )
                for select_option_id in allowed_select_options:
                    form_view_field_options_allowed_select_options.append(
                        FormViewFieldOptionsAllowedSelectOptions(
                            form_view_field_options_id=field_option_object.id,
                            select_option_id=id_mapping[
                                "database_field_select_options"
                            ][select_option_id],
                        )
                    )

                    field_option_object.id
                id_mapping["database_form_view_field_options"][
                    field_option_id
                ] = field_option_object.id

            # Create the objects in bulk to improve performance.
            FormViewFieldOptionsCondition.objects.bulk_create(condition_objects)
            FormViewFieldOptionsAllowedSelectOptions.objects.bulk_create(
                form_view_field_options_allowed_select_options
            )

        return form_view

    def get_visible_field_options_in_order(self, form_view):
        return (
            form_view.get_field_options(create_if_missing=True)
            .filter(enabled=True)
            .order_by("-field__primary", "order", "field__id")
        )

    def before_view_create(self, values: dict, table: "Table", user: AbstractUser):
        if "mode" in values:
            mode_type = form_view_mode_registry.get(values["mode"])
        else:
            # This is the default mode that's set when nothing is provided.
            mode_type = form_view_mode_registry.get_default_type()

        mode_type.before_form_create(values, table, user)

    def before_view_update(self, values: dict, view: "View", user: AbstractUser):
        mode_type = form_view_mode_registry.get(values.get("mode", view.mode))
        mode_type.before_form_update(values, view, user)

        notify_on_submit = values.pop("receive_notification_on_submit", None)
        if notify_on_submit is not None:
            users_to_notify_on_submit = [
                utn.id
                for utn in view.users_to_notify_on_submit.all()
                if utn.id != user.id
            ]
            if notify_on_submit:
                users_to_notify_on_submit.append(user.id)
            values["users_to_notify_on_submit"] = users_to_notify_on_submit

    def prepare_values(
        self, values: Dict[str, Any], table: Table, user: AbstractUser
    ) -> Dict[str, Any]:
        """
        Prepares the values for the form view.
        If a serialized version of UserFile is found, it will be converted to a
        UserFile object.

        :param values: The values to prepare.
        :param table: The table the form view belongs to.
        :param user: The user that is submitting the form.
        :raises: ValidationError if the provided value for images is not
            compatible with UserFile.
        :return: The prepared values.
        """

        for user_file_key in ["cover_image", "logo_image"]:
            user_file = values.get(user_file_key, None)

            if user_file is None:
                continue

            if isinstance(user_file, dict):
                values[user_file_key] = UserFileHandler().get_user_file_by_name(
                    user_file.get("name", None)
                )

            elif not isinstance(user_file, UserFile):
                raise ValidationError(
                    f"Invalid user file type. '{user_file_key}' should be a UserFile \
                        instance or the serialized version of it."
                )

        return super().prepare_values(values, table, user)

    def export_prepared_values(self, view: FormView) -> Dict[str, Any]:
        """
        Add form fields to the exportable fields for undo/redo.
        This is the counterpart of prepare_values. Starting from object instances,
        it exports data to a serialized version of the object, in a way that
        prepare_values can be used to import it.

        :param view: The gallery view to export.
        :return: The prepared values.
        """

        values = super().export_prepared_values(view)

        for field in ["cover_image", "logo_image"]:
            user_file = getattr(view, field)
            values[field] = user_file and user_file.serialize()

        return values

    def enhance_queryset(self, queryset):
        return queryset.prefetch_related(
            "formviewfieldoptions_set", "users_to_notify_on_submit"
        )

    def enhance_field_options_queryset(self, queryset):
        return queryset.prefetch_related(
            "conditions", "condition_groups", "allowed_select_options"
        )

    def prepare_field_options(
        self, view: FormView, field_id: int
    ) -> FormViewFieldOptions:
        return FormViewFieldOptions(
            field_id=field_id, form_view_id=view.id, enabled=False
        )

    def check_view_update_permissions(self, user, view, data):
        from .operations import CanReceiveNotificationOnSubmitFormViewOperationType

        workspace = view.table.database.workspace

        if "receive_notification_on_submit" in data:
            # If `receive_notification_on_submit` is in the data, then we must check if
            # the user has permissions to receive a notification on submit.
            CoreHandler().check_permissions(
                user,
                CanReceiveNotificationOnSubmitFormViewOperationType.type,
                workspace=workspace,
                context=view,
            )

            # If only the `receive_notification_on_submit` is provided, then there is
            # no need to check if the user has permissions to update the view because
            # nothing else is changed.
            if len(data) == 1:
                return

        return super().check_view_update_permissions(user, view, data)
