from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.api.utils import extract_field_ids_from_list
from baserow.contrib.database.fields.models import Field
from baserow.contrib.integrations.local_baserow.mixins import (
    LocalBaserowTableServiceFilterableMixin,
    import_refinement_field_id,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowTableRowsListServiceTypeMixin,
    LocalBaserowViewServiceType,
)
from baserow.core.embeddings import EmbeddingsServiceError
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.validator import ensure_string
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.registries import DispatchTypes
from baserow.core.services.types import DispatchResult, FormulaToResolve
from baserow_enterprise.features import SEMANTIC_SEARCH
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowSemanticSearch,
)
from baserow_enterprise.semantic_search.exceptions import SemanticSearchNotAvailable
from baserow_enterprise.semantic_search.handler import SemanticSearchHandler
from baserow_enterprise.semantic_search.models import SemanticSearchField
from baserow_premium.license.handler import LicenseHandler

# The values of a row are nested, because a field can have any name, including the
# names of the other properties of a result.
ROW_PROPERTY = "row"
SCORE_PROPERTY = "score"
SIMILARITY_PROPERTY = "similarity"
MATCHED_FIELD_PROPERTY = "matched_field"
RESULT_PROPERTIES = [SCORE_PROPERTY, SIMILARITY_PROPERTY, MATCHED_FIELD_PROPERTY]


class LocalBaserowSemanticSearchServiceType(
    LocalBaserowTableRowsListServiceTypeMixin,
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowViewServiceType,
):
    """
    Finds the rows of which the values of the fields with semantic search enabled
    match the meaning of the search query best.
    """

    type = "local_baserow_semantic_search"
    model_class = LocalBaserowSemanticSearch
    dispatch_types = [DispatchTypes.DATA, DispatchTypes.ACTION]
    serializer_mixins = LocalBaserowTableServiceFilterableMixin.mixin_serializer_mixins

    @property
    def simple_formula_fields(self):
        return super().simple_formula_fields + ["search_query"]

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + LocalBaserowTableServiceFilterableMixin.mixin_allowed_fields
            + [
                "search_all_fields",
                "include_all_fields",
                "search_query",
                "max_results",
                "min_similarity",
            ]
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_names
            + [
                "search_all_fields",
                "search_field_ids",
                "include_all_fields",
                "included_field_ids",
                "search_query",
                "max_results",
                "min_similarity",
            ]
        )

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            **LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_overrides,
            "search_all_fields": serializers.BooleanField(
                read_only=True,
                help_text="Whether every field with semantic search enabled is "
                "searched. False without `search_field_ids` when all the chosen "
                "fields were deleted.",
            ),
            "search_field_ids": serializers.ListField(
                child=serializers.IntegerField(),
                required=False,
                help_text="The fields with semantic search enabled to search in. All "
                "of them when empty.",
            ),
            "include_all_fields": serializers.BooleanField(
                read_only=True,
                help_text="Whether the values of every field are returned. False "
                "without `included_field_ids` when all the chosen fields were "
                "deleted.",
            ),
            "included_field_ids": serializers.ListField(
                child=serializers.IntegerField(),
                required=False,
                help_text="The fields of which the values are returned. All when "
                "empty.",
            ),
            "search_query": FormulaSerializerField(
                required=False, help_text="The text to search for."
            ),
            "max_results": serializers.IntegerField(
                required=False,
                min_value=1,
                max_value=settings.BASEROW_SEMANTIC_SEARCH_MAX_RESULTS,
                help_text="The maximum number of rows to return.",
            ),
            "min_similarity": serializers.FloatField(
                required=False,
                allow_null=True,
                min_value=0,
                max_value=1,
                help_text="Rows of which the meaning is less similar to the query "
                "are left out.",
            ),
        }

    class SerializedDict(
        LocalBaserowViewServiceType.SerializedDict,
        LocalBaserowTableServiceFilterableMixin.SerializedDict,
    ):
        search_all_fields: bool
        search_field_ids: List[int]
        include_all_fields: bool
        included_field_ids: List[int]
        search_query: str
        max_results: int
        min_similarity: Optional[float]

    def is_deactivated(self, workspace) -> bool:
        handler = SemanticSearchHandler()
        return not handler.is_available() or not handler.workspace_has_feature(
            workspace
        )

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            SEMANTIC_SEARCH, workspace
        )
        if not SemanticSearchHandler().is_available():
            raise SemanticSearchNotAvailable()

    def dispatch(self, service, dispatch_context: DispatchContext) -> DispatchResult:
        self.raise_if_deactivated(dispatch_context.workspace)
        return super().dispatch(service, dispatch_context)

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related("search_fields", "included_fields")
        )

    def get_max_result_limit(self, service: LocalBaserowSemanticSearch):
        return service.max_results

    def get_default_result_limit(self, service: LocalBaserowSemanticSearch):
        return service.max_results

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[LocalBaserowSemanticSearch] = None,
    ) -> Dict[str, Any]:
        values = super().prepare_values(values, user, instance)
        table = values.get("table", getattr(instance, "table", None))

        if (
            "table" in values
            and instance is not None
            and instance.table_id != getattr(values["table"], "id", None)
        ):
            # The fields belong to the previous table.
            values.setdefault("search_field_ids", [])
            values.setdefault("included_field_ids", [])
            values.setdefault("search_all_fields", True)
            values.setdefault("include_all_fields", True)

        if "search_field_ids" in values:
            choice_changed = instance is None or set(values["search_field_ids"]) != set(
                instance.search_field_ids
            )
            values["search_field_ids"] = self._get_table_field_ids(
                values["search_field_ids"],
                self._get_linked_field_ids(instance.search_fields) if instance else [],
                Field.objects.filter(table=table, semantic_search__isnull=False),
                "One or more fields to search in aren't fields with semantic "
                "search enabled of the given table.",
            )
            # Undo restores the flag together with the fields. An unchanged choice
            # keeps it, so that one of which all fields are gone doesn't become all
            # fields with another change.
            if choice_changed:
                values.setdefault("search_all_fields", not values["search_field_ids"])
        if "included_field_ids" in values:
            choice_changed = instance is None or set(
                values["included_field_ids"]
            ) != set(instance.included_field_ids)
            values["included_field_ids"] = self._get_table_field_ids(
                values["included_field_ids"],
                self._get_linked_field_ids(instance.included_fields)
                if instance
                else [],
                Field.objects.filter(table=table),
                "One or more included fields are not related to the given table.",
            )
            if choice_changed:
                values.setdefault(
                    "include_all_fields", not values["included_field_ids"]
                )

        return values

    def _get_table_field_ids(
        self,
        field_ids: List[int],
        stored_field_ids: List[int],
        allowed_fields: QuerySet,
        error: str,
    ) -> List[int]:
        field_ids = set(field_ids)
        allowed_field_ids = set(
            allowed_fields.filter(id__in=field_ids).values_list("id", flat=True)
        )
        # A chosen field that was trashed or of which semantic search was disabled
        # since stays chosen, so that the other changes can still be saved and the
        # choice doesn't widen to all fields. It's used again when it can be.
        kept_field_ids = (field_ids - allowed_field_ids) & set(stored_field_ids)
        if field_ids - allowed_field_ids - kept_field_ids:
            # The error code lets the editor show the error.
            raise DRFValidationError(
                detail={"detail": error, "error": "invalid_field"},
                code="invalid_field",
            )
        return sorted(allowed_field_ids | kept_field_ids)

    def after_create(self, instance: LocalBaserowSemanticSearch, values: Dict):
        super().after_create(instance, values)
        self._set_fields(instance, values)

    def after_update(
        self, instance: LocalBaserowSemanticSearch, values: Dict, changes: Dict
    ):
        super().after_update(instance, values, changes)
        self._set_fields(instance, values)

    def _set_fields(self, instance: LocalBaserowSemanticSearch, values: Dict):
        if "search_field_ids" in values:
            self._replace_fields(instance.search_fields, values["search_field_ids"])
        if "included_field_ids" in values:
            self._replace_fields(instance.included_fields, values["included_field_ids"])

    def _get_linked_field_ids(self, relation) -> List[int]:
        # Through the links, because the related manager can't see trashed fields.
        return list(
            relation.through.objects.filter(
                **{relation.source_field_name: relation.instance}
            ).values_list(f"{relation.target_field_name}_id", flat=True)
        )

    def _replace_fields(self, relation, field_ids: List[int]):
        # `set` can't see trashed fields, so it would keep the links to the ones
        # that are no longer chosen, and they would be chosen again when restored.
        relation.through.objects.filter(
            **{relation.source_field_name: relation.instance}
        ).exclude(**{f"{relation.target_field_name}_id__in": field_ids}).delete()
        relation.add(*field_ids)

    def export_prepared_values(self, instance: LocalBaserowSemanticSearch):
        values = super().export_prepared_values(instance)
        values["search_field_ids"] = instance.search_field_ids
        values["included_field_ids"] = instance.included_field_ids
        return values

    def serialize_property(
        self,
        service: LocalBaserowSemanticSearch,
        prop_name: str,
        import_export_config=None,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "search_field_ids":
            return service.search_field_ids
        if prop_name == "included_field_ids":
            return service.included_field_ids
        return super().serialize_property(
            service,
            prop_name,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        if prop_name in ("search_field_ids", "included_field_ids"):
            # Like the fields of filters, so that publishing, which doesn't import
            # the databases, keeps them.
            config = kwargs.get("import_export_config")
            mapped = [
                import_refinement_field_id(field_id, id_mapping, config)
                for field_id in value
            ]
            return [field_id for field_id in mapped if field_id is not None]
        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        search_field_ids = serialized_values.pop("search_field_ids", [])
        included_field_ids = serialized_values.pop("included_field_ids", [])
        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )
        # Fields that weren't imported, for example because they're in another
        # workspace, are left out.
        table_fields = Field.objects.filter(table_id=service.table_id)
        service.search_fields.set(table_fields.filter(id__in=search_field_ids))
        service.included_fields.set(table_fields.filter(id__in=included_field_ids))
        return service

    def formulas_to_resolve(
        self, service: LocalBaserowSemanticSearch
    ) -> list[FormulaToResolve]:
        return [
            FormulaToResolve(
                "search_query",
                service.search_query,
                ensure_string,
                'property "Search query"',
            )
        ]

    def get_fields_to_search(self, service: LocalBaserowSemanticSearch) -> List[Field]:
        """
        Returns the chosen fields, or all fields of the table, that can be searched.
        Chosen fields that were deleted or of which semantic search was disabled
        are left out, so that the others are still searched. Fields that another
        field made incompatible are left out until they're compatible again, but
        stay chosen.

        :raises ServiceImproperlyConfiguredDispatchException: If no field can be
            searched.
        """

        fields = Field.objects.filter(
            table_id=service.table_id, semantic_search__isnull=False
        )
        if not service.search_all_fields:
            fields = fields.filter(id__in=service.search_field_ids)
        fields = list(fields.select_related("semantic_search").order_by("id"))
        if not fields:
            raise ServiceImproperlyConfiguredDispatchException(
                "The table has no fields with semantic search enabled."
                if service.search_all_fields
                else "None of the selected fields has semantic search enabled anymore."
            )
        # Their vectors are deleted until their values are text again.
        compatible_fields = [
            field
            for field in fields
            if field.semantic_search.status != SemanticSearchField.Status.INCOMPATIBLE
        ]
        if not compatible_fields:
            raise ServiceImproperlyConfiguredDispatchException(
                "The fields with semantic search can't be searched right now, because "
                "their values aren't text anymore."
            )
        return compatible_fields

    def generate_schema(
        self,
        service: LocalBaserowSemanticSearch,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        row_properties = self.get_table_properties(service)
        if row_properties is None:
            return None

        if not service.include_all_fields:
            included = {f"field_{field_id}" for field_id in service.included_field_ids}
            row_properties = {
                name: value
                for name, value in row_properties.items()
                if name == "id" or name in included
            }
        if allowed_fields is not None:
            row_properties = {
                name: value
                for name, value in row_properties.items()
                if name in set(allowed_fields)
            }
        not_refinable = {"sortable": False, "filterable": False, "searchable": False}
        return self.get_schema_for_return_type(
            service,
            {
                "id": {"type": "number", "title": "Id", **not_refinable},
                ROW_PROPERTY: {
                    "type": "object",
                    "title": "Row",
                    "properties": row_properties,
                    **not_refinable,
                },
                SCORE_PROPERTY: {"type": "number", "title": "Score", **not_refinable},
                SIMILARITY_PROPERTY: {
                    "type": "number",
                    "title": "Similarity",
                    **not_refinable,
                },
                MATCHED_FIELD_PROPERTY: {
                    "type": "string",
                    "title": "Matched field",
                    **not_refinable,
                },
            },
        )

    def extract_properties(
        self, service: LocalBaserowSemanticSearch, path: List[str], **kwargs
    ) -> List[str]:
        if not path:
            return super().extract_properties(service, path, **kwargs) + (
                RESULT_PROPERTIES
            )
        if path[0] == ROW_PROPERTY:
            return super().extract_properties(service, path[1:], **kwargs)
        if path[0] in RESULT_PROPERTIES:
            return [path[0]]
        return ["id"]

    def sanitize_result(self, service, result, allowed_field_names):
        # The used fields are in the row of each result, so the generic sanitizing
        # of the top level properties would remove all of them. The matched field
        # can be one that the page doesn't show.
        used_properties = [
            name for name in RESULT_PROPERTIES if name in allowed_field_names
        ]
        row_field_names = self._convert_allowed_field_names(
            service, allowed_field_names
        )
        return {
            **result,
            "results": [
                {
                    "id": item["id"],
                    ROW_PROPERTY: self.remove_unused_field_names(
                        item[ROW_PROPERTY], row_field_names
                    ),
                    **{name: item[name] for name in used_properties},
                }
                for item in result["results"]
            ],
        }

    def prepare_value_path(self, service: LocalBaserowSemanticSearch, path: List[str]):
        # E.g. `["row", "field_1"]`, because the values of a row are nested.
        if path and path[0] == ROW_PROPERTY:
            return [ROW_PROPERTY, *super().prepare_value_path(service, path[1:])]
        return path

    def import_path(self, path, id_mapping):
        # E.g. `[0, "row", "field_1", "value"]`
        if len(path) >= 3 and path[1] == ROW_PROPERTY:
            index, _, *row_path = path
            return [
                index,
                ROW_PROPERTY,
                *super().import_path([index, *row_path], id_mapping)[1:],
            ]
        return path

    def import_context_path(self, path, id_mapping, **kwargs):
        # The previous and current node data providers of automations use the same
        # paths to the values of a row, e.g. `[0, "row", "field_1"]`.
        if len(path) >= 3 and path[1] == ROW_PROPERTY:
            return self.import_path(path, id_mapping)
        return super().import_context_path(path, id_mapping, **kwargs)

    def dispatch_data(
        self,
        service: LocalBaserowSemanticSearch,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        fields = self.get_fields_to_search(service)
        offset, count = dispatch_context.range(service)
        if count is None:
            count = self.get_default_result_limit(service)

        table_model = self.get_table_model(service)
        queryset = self.build_queryset(
            service, service.table, dispatch_context, model=table_model
        )
        # Like list rows, only the clicked row of a collection is returned, so that
        # its action uses the values of that row instead of the first result.
        if (
            dispatch_context.only_record_id is not None
            and dispatch_context.is_adhoc_refinable(service)
        ):
            queryset = queryset.filter(id=dispatch_context.only_record_id)
        query = resolved_values.get("search_query", "").strip()
        limit = min(offset + count, service.max_results)
        if not query or limit <= offset:
            matches = []
        else:
            try:
                # Always all results, because the ranking depends on how many are
                # requested, so pages of a smaller ranking would overlap.
                matches = SemanticSearchHandler().search(
                    fields,
                    query,
                    queryset,
                    service.max_results,
                    service.min_similarity,
                )
            except EmbeddingsServiceError as exc:
                raise UnexpectedDispatchException(str(exc)) from exc

        page = matches[offset:limit]
        field_ids = self._get_returned_field_ids(service, dispatch_context)
        rows = queryset
        if field_ids is not None:
            # Like list rows, the other values aren't loaded. The order is used by
            # the serializer, and a used field can be deleted since.
            rows = rows.only(
                "id",
                "order",
                *(
                    f"field_{field_id}"
                    for field_id in field_ids
                    if field_id in table_model._field_objects
                ),
            )
        rows_by_id = rows.in_bulk([match.row_id for match in page])
        field_names = {field.id: field.name for field in fields}
        return {
            "results": [
                (
                    rows_by_id[match.row_id],
                    match.relevance,
                    match.similarity,
                    field_names[match.field_id],
                )
                for match in page
                if match.row_id in rows_by_id
            ],
            "has_next_page": len(matches) > limit,
            "baserow_table_model": table_model,
            "field_ids": field_ids,
        }

    def _get_returned_field_ids(
        self, service: LocalBaserowSemanticSearch, dispatch_context: DispatchContext
    ) -> Optional[List[int]]:
        used_field_names = self.get_used_field_names(service, dispatch_context)
        used_field_ids = (
            set(extract_field_ids_from_list(used_field_names))
            if isinstance(used_field_names, list)
            else None
        )
        if service.include_all_fields:
            return None if used_field_ids is None else sorted(used_field_ids)
        field_ids = set(service.included_field_ids)
        if used_field_ids is not None:
            field_ids &= used_field_ids
        return sorted(field_ids)

    def dispatch_transform(self, dispatch_data: Dict[str, Any]) -> DispatchResult:
        table_model = dispatch_data["baserow_table_model"]
        serializer = get_row_serializer_class(
            table_model,
            RowSerializer,
            is_response=True,
            field_ids=dispatch_data["field_ids"],
            user_field_names=True,
        )
        rows = serializer([row for row, *_ in dispatch_data["results"]], many=True).data
        for row in rows:
            # The rows are ordered by relevance instead.
            row.pop("order", None)
        rows = self._prepare_result(table_model, {"results": rows})["results"]

        return DispatchResult(
            data={
                "results": [
                    {
                        "id": row["id"],
                        ROW_PROPERTY: row,
                        SCORE_PROPERTY: relevance,
                        SIMILARITY_PROPERTY: similarity,
                        MATCHED_FIELD_PROPERTY: matched_field,
                    }
                    for row, (_, relevance, similarity, matched_field) in zip(
                        rows, dispatch_data["results"]
                    )
                ],
                "has_next_page": dispatch_data["has_next_page"],
            }
        )
