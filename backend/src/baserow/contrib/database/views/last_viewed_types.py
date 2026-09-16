from typing import Iterable, List

from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet

from baserow.contrib.database.api.tables.serializers import TableReferenceSerializer
from baserow.contrib.database.trash.trash_types import (
    TableTrashableItemType,
    ViewTrashableItemType,
)
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.operations import ListViewsOperationType
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.registries import LastViewedItemType


class DatabaseViewLastViewedItemType(LastViewedItemType):
    type = "database_view"
    model_class = View
    list_operation_type = ListViewsOperationType.type
    serializer_field_names = ["id", "name", "table"]
    serializer_field_overrides = {"table": TableReferenceSerializer(read_only=True)}

    def get_visible_queryset(self) -> QuerySet:
        # Trashing a table or database does not flag its views, hence the explicit
        # parent filters.
        return View.objects.filter(
            table__trashed=False,
            table__database__trashed=False,
        )

    def get_queryset_for_user(self, user_id: int) -> QuerySet:
        # `Database` is a child of `Application`, so this join also brings the
        # workspace id along.
        return (
            self.get_visible_queryset()
            .select_related("table__database")
            .filter(
                table__database__workspace__trashed=False,
                table__database__workspace__workspaceuser__user_id=user_id,
            )
        )

    def get_application_id(self, instance: View) -> int:
        return instance.table.database_id

    def get_workspace_id(self, instance: View) -> int:
        return instance.table.database.workspace_id

    def get_sub_types(self) -> List[str]:
        return view_type_registry.get_types()

    def filter_queryset_by_sub_types(
        self, queryset: QuerySet, sub_types: Iterable[str]
    ) -> QuerySet:
        # The content type lookups are cached per process, so this is free after
        # the first request.
        content_types = [
            ContentType.objects.get_for_model(
                view_type_registry.get(sub_type).model_class
            )
            for sub_type in sub_types
        ]
        return queryset.filter(content_type__in=content_types)

    def get_sub_type(self, instance: View) -> str:
        # `specific_class` only resolves the cached content type, so no query is
        # needed to know which kind of view this is.
        return view_type_registry.get_by_model(instance.specific_class).type

    def enhance_list_queryset(self, queryset: QuerySet) -> QuerySet:
        return queryset.select_related("table")

    def get_item_ids_of_permanently_deleted(
        self, trash_item_type: str, trash_item
    ) -> Iterable[int]:
        if trash_item_type == ViewTrashableItemType.type:
            return [trash_item.id]
        if trash_item_type == TableTrashableItemType.type:
            return View.objects_and_trash.filter(table_id=trash_item.id).values_list(
                "id", flat=True
            )
        return []
