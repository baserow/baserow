from typing import TYPE_CHECKING, Any, List, Optional

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Expression, F
from django.utils.functional import lazy

from baserow_premium.api.fields.exceptions import (
    ERROR_GENERATIVE_AI_DOES_NOT_SUPPORT_FILE_FIELD,
)
from baserow_premium.fields.exceptions import GenerativeAITypeDoesNotSupportFileField
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from rest_framework import serializers

from baserow.api.generative_ai.errors import (
    ERROR_GENERATIVE_AI_DOES_NOT_EXIST,
    ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE,
)
from baserow.contrib.database.api.fields.errors import ERROR_FIELD_DOES_NOT_EXIST
from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.contrib.database.fields.dependencies.types import FieldDependencies
from baserow.contrib.database.fields.dependencies.update_collector import (
    DependencyContext,
    FieldUpdateCollector,
)
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.field_types import (
    CollationSortMixin,
    SelectOptionBaseFieldType,
)
from baserow.contrib.database.fields.models import Field, LinkRowField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.formula import BaserowFormulaType
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.generative_ai.exceptions import (
    GenerativeAITypeDoesNotExist,
    ModelDoesNotBelongToType,
)
from baserow.core.generative_ai.registries import (
    GenerativeAIWithFilesModelType,
    generative_ai_model_type_registry,
)
from baserow.core.jobs.handler import JobHandler

from .models import AIField
from .registries import ai_field_output_registry
from .visitors import extract_field_id_dependencies, replace_field_id_references

User = get_user_model()

if TYPE_CHECKING:
    from baserow.contrib.database.fields.registries import StartingRowType
    from baserow.contrib.database.table.models import GeneratedTableModel


class AIFieldType(CollationSortMixin, SelectOptionBaseFieldType):
    """
    The AI field can automatically query a generative AI model based on the provided
    prompt. It's possible to reference other fields to generate a unique output.
    """

    type = "ai"
    model_class = AIField
    can_be_in_form_view = False
    keep_data_on_duplication = True
    allowed_fields = SelectOptionBaseFieldType.allowed_fields + [
        "ai_generative_ai_type",
        "ai_generative_ai_model",
        "ai_output_type",
        "ai_temperature",
        "ai_prompt",
        "ai_file_field_id",
        "ai_auto_update",
        "ai_auto_update_user_id",
    ]
    serializer_field_names = SelectOptionBaseFieldType.allowed_fields + [
        "ai_generative_ai_type",
        "ai_generative_ai_model",
        "ai_output_type",
        "ai_temperature",
        "ai_prompt",
        "ai_file_field_id",
        "ai_auto_update",
    ]
    serializer_field_overrides = {
        "ai_output_type": serializers.ChoiceField(
            required=False,
            choices=lazy(ai_field_output_registry.get_types, list)(),
            help_text="The desired output type of the field. It will try to force the "
            "response of the prompt to match it.",
        ),
        "ai_temperature": serializers.FloatField(
            required=False,
            allow_null=True,
            min_value=0,
            max_value=2,
            help_text="Between 0 and 2, adjusts response randomness—lower values yield "
            "focused answers, while higher values increase creativity.",
        ),
        "ai_prompt": FormulaSerializerField(
            help_text="The prompt that must run for each row. Must be an formula.",
            required=False,
        ),
        "ai_file_field_id": serializers.IntegerField(
            min_value=1,
            help_text="File field that will be used as a knowledge base for the AI model.",
            required=False,
            allow_null=True,
            default=None,
        ),
        "ai_auto_update": serializers.BooleanField(
            default=False,
            required=False,
            allow_null=True,
            help_text="If set, AI field will be recalculated if a value of a "
            "referenced field has been changed.",
        ),
        **SelectOptionBaseFieldType.serializer_field_overrides,
    }
    api_exceptions_map = {
        GenerativeAITypeDoesNotExist: ERROR_GENERATIVE_AI_DOES_NOT_EXIST,
        ModelDoesNotBelongToType: ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE,
        GenerativeAITypeDoesNotSupportFileField: ERROR_GENERATIVE_AI_DOES_NOT_SUPPORT_FILE_FIELD,
        IntegrityError: ERROR_FIELD_DOES_NOT_EXIST,
    }
    can_get_unique_values = True
    can_have_select_options = True

    def get_internal_value_from_db(
        self, row: "GeneratedTableModel", field_name: str
    ) -> Any:
        field_object = row.get_field_object(field_name)
        baserow_field_type = self.get_baserow_field_type(field_object["field"])
        return baserow_field_type.get_internal_value_from_db(row, field_name)

    def get_baserow_field_type(self, instance):
        output_type = ai_field_output_registry.get(instance.ai_output_type)
        baserow_field_type = field_type_registry.get_by_type(
            output_type.baserow_field_type
        )
        return baserow_field_type

    def get_serializer_field(self, instance, **kwargs):
        baserow_field_type = self.get_baserow_field_type(instance)
        return baserow_field_type.get_serializer_field(instance, **kwargs)

    def get_response_serializer_field(self, instance, **kwargs):
        baserow_field_type = self.get_baserow_field_type(instance)
        return baserow_field_type.get_response_serializer_field(instance, **kwargs)

    def get_model_field(self, instance, **kwargs):
        baserow_field_type = self.get_baserow_field_type(instance)
        return baserow_field_type.get_model_field(instance, **kwargs)

    def get_serializer_help_text(self, instance):
        return (
            "Holds a value that is generated by a generative AI model using a "
            "dynamic prompt."
        )

    def random_value(self, instance, fake, cache):
        baserow_field_type = self.get_baserow_field_type(instance)
        return baserow_field_type.random_value(instance, fake, cache)

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.to_baserow_formula_type(field)

    def get_value_for_filter(self, row: "GeneratedTableModel", field: Field) -> any:
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.get_value_for_filter(row, field)

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        baserow_field_type = self.get_baserow_field_type(from_field)
        return baserow_field_type.get_alter_column_prepare_old_value(
            connection, from_field, to_field
        )

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        baserow_field_type = self.get_baserow_field_type(to_field)
        return baserow_field_type.get_alter_column_prepare_new_value(
            connection, from_field, to_field
        )

    def contains_query(self, field_name, value, model_field, field):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.contains_query(field_name, value, model_field, field)

    def parse_filter_value(self, field, model_field, value):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.parse_filter_value(field, model_field, value)

    def get_compatible_filter_field_type(self, field):
        """
        For AI fields, return the underlying core field type used for filtering.
        """

        ai_field_instance = field.specific if hasattr(field, "specific") else field
        return self.get_baserow_field_type(ai_field_instance)

    def contains_word_query(self, field_name, value, model_field, field):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.contains_word_query(
            field_name, value, model_field, field
        )

    def check_can_order_by(self, field: Field, sort_type: str) -> bool:
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.check_can_order_by(field, sort_type)

    def check_can_group_by(self, field: Field, sort_type: str) -> bool:
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.check_can_group_by(field, sort_type)

    def get_search_expression(self, field: Field, queryset):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.get_search_expression(field, queryset)

    def is_searchable(self, field):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.is_searchable(field)

    def enhance_queryset(self, queryset, field, name, **kwargs):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.enhance_queryset(queryset, field, name)

    def get_sortable_column_expression(
        self,
        field: Field,
        field_name: str,
        sort_type: str,
    ) -> Expression | F:
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.get_sortable_column_expression(
            field, field_name, sort_type
        )

    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.get_order(
            field, field_name, order_direction, sort_type, table_model=table_model
        )

    def serialize_to_input_value(self, field, value):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.serialize_to_input_value(field, value)

    def valid_for_bulk_update(self, field):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.valid_for_bulk_update(field)

    def prepare_value_for_db(self, instance, value):
        baserow_field_type = self.get_baserow_field_type(instance)
        return baserow_field_type.prepare_value_for_db(instance, value)

    def prepare_value_for_db_in_bulk(
        self, instance, values_by_row, continue_on_error=False
    ):
        baserow_field_type = self.get_baserow_field_type(instance)
        return baserow_field_type.prepare_value_for_db_in_bulk(
            instance, values_by_row, continue_on_error
        )

    def get_group_by_serializer_field(self, field, **kwargs):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.get_group_by_serializer_field(field, **kwargs)

    def get_group_by_field_unique_value(self, field, field_name, value):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.get_group_by_field_unique_value(
            field, field_name, value
        )

    def get_group_by_field_filters_and_annotations(
        self, field, field_name, base_queryset, value, cte, rows
    ):
        baserow_field_type = self.get_baserow_field_type(field)
        return baserow_field_type.get_group_by_field_filters_and_annotations(
            field, field_name, base_queryset, value, cte, rows
        )

    def get_formula_reference_to_model_field(
        self, model_field, db_column, already_in_subquery
    ):
        instance = model_field.model.get_field_object(
            model_field.name, include_trash=True
        )["field"]
        baserow_field_type = self.get_baserow_field_type(instance)
        return baserow_field_type.get_formula_reference_to_model_field(
            model_field, db_column, already_in_subquery
        )

    def get_export_serialized_value(
        self,
        row,
        field_name,
        cache,
        files_zip=None,
        storage=None,
    ):
        field_object = row.get_field_object(field_name)
        baserow_field_type = self.get_baserow_field_type(field_object["field"])
        return baserow_field_type.get_export_serialized_value(
            row, field_name, cache, files_zip, storage
        )

    def set_import_serialized_value(
        self,
        row,
        field_name,
        value,
        id_mapping,
        cache,
        files_zip=None,
        storage=None,
    ):
        field_object = row.get_field_object(field_name)
        baserow_field_type = self.get_baserow_field_type(field_object["field"])
        return baserow_field_type.set_import_serialized_value(
            row, field_name, value, id_mapping, cache, files_zip, storage
        )

    def get_export_value(self, value, field_object, rich_value=False):
        baserow_field_type = self.get_baserow_field_type(field_object["field"])
        return baserow_field_type.get_export_value(value, field_object, rich_value)

    def get_human_readable_value(self, value, field_object):
        baserow_field_type = self.get_baserow_field_type(field_object["field"])
        return baserow_field_type.get_human_readable_value(value, field_object)

    def _validate_field_kwargs(
        self, ai_output_type, ai_type, model_type, ai_file_field_id, workspace=None
    ):
        ai_field_output_registry.get(ai_output_type)
        ai_type = generative_ai_model_type_registry.get(ai_type)
        models = ai_type.get_enabled_models(workspace=workspace)
        if model_type not in models:
            raise ModelDoesNotBelongToType(model_name=model_type)
        if ai_file_field_id is not None and not isinstance(
            ai_type, GenerativeAIWithFilesModelType
        ):
            raise GenerativeAITypeDoesNotSupportFileField()

    def get_field_dependencies(
        self, field_instance: AIField, field_cache: "FieldCache"
    ) -> FieldDependencies:
        field_ids = extract_field_id_dependencies(field_instance.ai_prompt["formula"])
        return [
            FieldDependency(
                dependency_id=field_id,
                dependant=field_instance,
                via=None,
            )
            for field_id in field_ids
        ]

    def _handle_dependent_rows_change(
        self,
        field: AIField,
        starting_row: "StartingRowType",
    ):
        """
        Schedules the recalculation of the AI field for the rows that depend on the
        starting row via field dependencies.
        """

        if not field.ai_auto_update:
            return

        try:
            user = field.ai_auto_update_user
        except (
            User.DoesNotExist
        ):  # If the field comes from the cache might contains stale data
            user = None
        # The user than enabled the auto update is no longer available. Let's disable
        # the auto_update To avoid this from being called over and over again.
        # TODO: send a notification to the workspace admins?
        workspace = field.table.database.workspace
        if not user or not LicenseHandler.user_has_feature(PREMIUM, user, workspace):
            field.ai_auto_update = False
            field.ai_auto_update_user = None
            field.save()
            return

        if isinstance(starting_row, list):
            row_ids = [row.id for row in starting_row]
        else:
            row_ids = [starting_row.id]

        transaction.on_commit(
            lambda: JobHandler().create_and_start_job(
                user, "generate_ai_values", field_id=field.id, row_ids=row_ids
            )
        )

    def row_of_dependency_deleted(
        self,
        field: Field,
        starting_row: "StartingRowType",
        update_collector: "FieldUpdateCollector",
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]],
        dependency_context: "DependencyContext",
    ):
        # no need to process deletion for AI field, so we just do a noop.
        return

    def row_of_dependency_created(
        self,
        field: AIField,
        starting_row: "StartingRowType",
        update_collector: "FieldUpdateCollector",
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]],
        dependency_context: DependencyContext,
    ):
        if dependency_context.depth == 0:
            self._handle_dependent_rows_change(field, starting_row)

    def row_of_dependency_updated(
        self,
        field: AIField,
        starting_row: "StartingRowType",
        update_collector: "FieldUpdateCollector",
        field_cache: "FieldCache",
        via_path_to_starting_table: List["LinkRowField"],
        dependency_context: DependencyContext,
    ):
        # For AI fields, a dependency depth higher than 0 means another AI field is
        # involved, but we need to wait for that field to finish updating before we can
        # recalculate this one.
        # Note: empty dependency_context is used when
        if dependency_context.depth == 0:
            self._handle_dependent_rows_change(field, starting_row)

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        ai_output_type = field_kwargs.get(
            "ai_output_type", AIField._meta.get_field("ai_output_type").default
        )
        ai_type = field_kwargs.get("ai_generative_ai_type", None)
        model_type = field_kwargs.get("ai_generative_ai_model", None)
        ai_file_field_id = field_kwargs.get("ai_file_field_id", None)
        workspace = table.database.workspace
        self._validate_field_kwargs(
            ai_output_type, ai_type, model_type, ai_file_field_id, workspace=workspace
        )
        if allowed_field_values.get("ai_auto_update"):
            allowed_field_values["ai_auto_update_user_id"] = user.id if user else None

        return super().before_create(
            table, primary, allowed_field_values, order, user, field_kwargs
        )

    def before_update(self, from_field, to_field_values, user, field_kwargs):
        update_field = None
        if isinstance(from_field, AIField):
            update_field = from_field

        ai_output_type = (
            field_kwargs.get("ai_output_type", None)
            or getattr(update_field, "ai_output_type", None)
            or AIField._meta.get_field("ai_output_type").default
        )
        ai_type = field_kwargs.get("ai_generative_ai_type", None) or getattr(
            update_field, "ai_generative_ai_type", None
        )
        model_type = field_kwargs.get("ai_generative_ai_model", None) or getattr(
            update_field, "ai_generative_ai_model", None
        )
        try:
            ai_file_field_id = field_kwargs["ai_file_field_id"]
        except KeyError:
            ai_file_field_id = getattr(update_field, "ai_file_field_id", None)
        workspace = from_field.table.database.workspace
        self._validate_field_kwargs(
            ai_output_type, ai_type, model_type, ai_file_field_id, workspace=workspace
        )

        # Set the auto update user if the auto update is being enabled.
        if to_field_values.get("ai_auto_update") and (
            update_field is None or not update_field.ai_auto_update
        ):
            to_field_values["ai_auto_update_user_id"] = user.id if user else None

        return super().before_update(from_field, to_field_values, user, field_kwargs)

    def after_import_serialized(
        self,
        field: AIField,
        field_cache,
        id_mapping,
    ):
        save = False
        if field.ai_file_field_id:
            field.ai_file_field_id = id_mapping["database_fields"][
                field.ai_file_field_id
            ]
            save = True

        if field.ai_prompt:
            try:
                field.ai_prompt = replace_field_id_references(
                    field.ai_prompt, id_mapping["database_fields"]
                )
                save = True
            except KeyError:
                # Raised when the field ID is not found in the mapping. If that's the
                # case, we leave the field ID references broken so that the import
                # can still succeed.
                pass

        if save:
            field.save()

    def should_backup_field_data_for_same_type_update(
        self, old_field, new_field_attrs
    ) -> bool:
        backup = super().should_backup_field_data_for_same_type_update(
            old_field, new_field_attrs
        )
        # Backup the field if the output type changes because
        ai_output_changed = (
            "ai_output_type" in new_field_attrs
            and new_field_attrs["ai_output_type"]
            and new_field_attrs["ai_output_type"] != old_field.ai_output_type
        )
        return backup or ai_output_changed
