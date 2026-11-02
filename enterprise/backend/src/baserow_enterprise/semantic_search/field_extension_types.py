from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet, prefetch_related_objects

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import (
    FieldExtensionType,
    field_type_registry,
)
from baserow.core.feature_flags import FF_SEMANTIC_SEARCH, feature_flag_is_enabled
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.features import SEMANTIC_SEARCH
from baserow_premium.license.handler import LicenseHandler

from .exceptions import SemanticSearchNotAvailable, SemanticSearchNotSupported
from .handler import SemanticSearchHandler
from .models import SemanticSearchField


@extend_schema_field(OpenApiTypes.BOOL)
class SemanticSearchEnabledField(serializers.Field):
    def __init__(self, **kwargs):
        super().__init__(source="*", read_only=True, **kwargs)

    def to_representation(self, field):
        return SemanticSearchHandler().get_semantic_search_field(field) is not None


@extend_schema_field(OpenApiTypes.STR)
class SemanticSearchStatusField(serializers.Field):
    def __init__(self, **kwargs):
        super().__init__(source="*", read_only=True, **kwargs)

    def to_representation(self, field):
        handler = SemanticSearchHandler()
        semantic_search_field = handler.get_semantic_search_field(field)
        if semantic_search_field is None:
            return None
        return handler.get_status(semantic_search_field, field.table.database.workspace)


class SemanticSearchFieldExtensionType(FieldExtensionType):
    type = "semantic_search"
    request_serializer_field_names = ["semantic_search_enabled"]
    serializer_field_names = ["semantic_search_enabled", "semantic_search_status"]

    def get_request_serializer_field_overrides(self):
        return {
            "semantic_search_enabled": serializers.BooleanField(
                required=False,
                help_text="Whether the field's values can be searched by their "
                "meaning. Requires the advanced plan.",
            )
        }

    def get_serializer_field_overrides(self):
        return {
            "semantic_search_enabled": SemanticSearchEnabledField(
                help_text="Whether the field's values can be searched by their meaning."
            ),
            "semantic_search_status": SemanticSearchStatusField(
                help_text="The state of the semantic search index of the field: "
                "`indexing`, `ready`, `error`, `incompatible` if a change of "
                "another field made its value something else than text, `paused` "
                "if the workspace doesn't have the required license or "
                "`unavailable` if the instance doesn't support it. Null if "
                "semantic search is disabled.",
            ),
        }

    def enhance_fields_queryset(self, queryset: QuerySet) -> QuerySet:
        return queryset.select_related("semantic_search")

    def prefetch_fields(self, fields: List[Field]):
        prefetch_related_objects(fields, "semantic_search")

    def after_create(self, user: AbstractUser, field: Field, values: Dict[str, Any]):
        if values.get("semantic_search_enabled"):
            self._enable(field)

    def after_update(
        self,
        user: AbstractUser,
        field: Field,
        old_field: Field,
        values: Dict[str, Any],
    ):
        handler = SemanticSearchHandler()
        enabled = values.get("semantic_search_enabled")
        is_compatible = handler.get_semantic_search_field_type(field) is not None
        type_changed = type(field) is not type(old_field)
        # Nothing changes for a compatible field of the same type without a new
        # value, which is most field updates, so the setting isn't looked up.
        if enabled is None and is_compatible and not type_changed:
            return

        semantic_search_field = handler.get_semantic_search_field(field)
        was_enabled = semantic_search_field is not None
        if enabled and not was_enabled:
            self._enable(field)
        elif enabled is False and was_enabled:
            handler.disable(field)
        elif (
            was_enabled
            and not is_compatible
            and (
                type_changed
                or handler.get_semantic_search_field_type(old_field) is not None
            )
        ):
            # The user's own change made it incompatible, like converting it to a
            # number, which also removes its index. Also if another field already
            # made it incompatible, because the setting doesn't apply to the new type.
            handler.disable(field)
        elif (
            was_enabled
            and is_compatible
            and semantic_search_field.status == SemanticSearchField.Status.INCOMPATIBLE
        ):
            # Like a formula that another field made incompatible, converted to a
            # text field. Its type is no longer one that depends on other fields.
            handler.queue_full_updates(field.table, [semantic_search_field])

    def _enable(self, field: Field):
        """
        Enables semantic search because a user asked for it.

        :param field: The field of which the values become searchable.
        :raises FeaturesNotAvailableError: If the workspace doesn't have the license.
        :raises SemanticSearchNotAvailable: If the instance doesn't support it, or
            the feature flag isn't enabled.
        :raises SemanticSearchNotSupported: If the type of the field isn't supported.
        """

        if not feature_flag_is_enabled(FF_SEMANTIC_SEARCH):
            raise SemanticSearchNotAvailable()
        handler = SemanticSearchHandler()
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            SEMANTIC_SEARCH, field.table.database.workspace
        )
        if not handler.is_available():
            raise SemanticSearchNotAvailable()
        if handler.get_semantic_search_field_type(field) is None:
            raise SemanticSearchNotSupported(
                field_type_registry.get_by_model(field).type
            )
        handler.enable(field)

    def after_duplicate(
        self,
        user: AbstractUser,
        original_field: Field,
        new_field: Field,
        duplicate_data: bool,
    ):
        handler = SemanticSearchHandler()
        if handler.get_semantic_search_field(original_field) is None:
            return
        handler.enable(
            new_field,
            copy_vectors_from_field_id=original_field.id if duplicate_data else None,
        )

    def export_prepared_values(self, field: Field) -> Dict[str, Any]:
        return {
            "semantic_search_enabled": SemanticSearchHandler().get_semantic_search_field(
                field
            )
            is not None
        }

    def export_serialized(
        self, field: Field, import_export_config: Optional[ImportExportConfig]
    ) -> Dict[str, Any]:
        # Fields that aren't saved, like the ones of an Airtable import, can't have
        # semantic search enabled. Those can have an Airtable id as primary key.
        if field._state.adding or not SemanticSearchHandler().get_semantic_search_field(
            field
        ):
            return {}
        return {"enabled": True}

    def import_serialized(
        self,
        field: Field,
        values: Dict[str, Any],
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Any],
        import_export_config: ImportExportConfig,
    ):
        if not values.get("enabled"):
            return

        # A duplicate copies the rows with the same ids, so the existing vectors
        # can be reused. The data of an exported file can differ from the
        # vectors of a field with the same id on this instance.
        reuse_vectors = (
            import_export_config.is_duplicate
            and not import_export_config.is_template
            and not import_export_config.only_structure
        )
        # The rows are imported after the fields. Their search data update queues
        # the indexing, or the periodic check does if it's skipped. Like the
        # full-text search data, copies that save disk space, like the ones of
        # templates, aren't indexed. Installing them indexes the installed copy.
        SemanticSearchHandler().enable(
            field,
            start_indexing=False,
            copy_vectors_from_field_id=(
                serialized_values["id"] if reuse_vectors else None
            ),
            queue_indexing=not import_export_config.reduce_disk_space_usage,
        )
