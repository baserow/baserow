from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import connection, router

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.dependencies.update_collector import (
    FieldUpdateCollector,
)
from baserow.contrib.database.fields.exceptions import FieldDataConstraintException
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.signals import rows_created
from baserow.contrib.database.table.models import (
    GeneratedTableModel,
    RichTextFieldMention,
    Table,
)
from baserow.contrib.database.table.signals import table_created, table_updated
from baserow.contrib.database.views.handler import ViewHandler, ViewIndexingHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import (
    view_ownership_type_registry,
    view_type_registry,
)
from baserow.contrib.database.views.signals import view_created
from baserow.core.exceptions import TrashItemDoesNotExist
from baserow.core.models import TrashEntry
from baserow.core.trash.exceptions import RelatedTableTrashedException
from baserow.core.trash.registries import TrashableItemType

from ..fields.operations import RestoreFieldOperationType
from ..rows.operations import RestoreDatabaseRowOperationType
from ..search.handler import SearchHandler
from ..table.operations import RestoreDatabaseTableOperationType
from ..views.operations import RestoreViewOperationType
from .models import TrashedRows

User = get_user_model()


class TableTrashableItemType(TrashableItemType):
    type = "table"
    model_class = Table

    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        return trashed_item.database

    def get_name(self, trashed_item: Table) -> str:
        return trashed_item.name

    def lookup_trashed_item(
        self, trashed_entry, trash_item_lookup_cache: Dict[str, Any] = None
    ):
        try:
            return self.model_class.trash.select_related("database__workspace").get(
                id=trashed_entry.trash_item_id
            )
        except self.model_class.DoesNotExist:
            raise TrashItemDoesNotExist()

    def fields_to_restore(self, trashed_item: Table, trash_entry: TrashEntry):
        for field in trashed_item.field_set(manager="objects_and_trash").all():
            field = field.specific
            field_type = field_type_registry.get_by_model(field)
            field_ids_to_check_for_individual_entries = [field.id] + [
                f.id
                for f in field_type.get_other_fields_to_trash_restore_always_together(
                    field
                )
            ]
            if TrashEntry.objects.filter(
                trash_item_type="field",
                trash_item_id__in=field_ids_to_check_for_individual_entries,
                application=trashed_item.database,
                workspace=trashed_item.database.workspace,
            ).exists():
                # Don't restore fields with their own trash entry as they have been
                # separately deleted individually before the table was deleted.
                continue

            yield field

        related_items = trash_entry.related_items or {}
        for field_id in related_items.get(FieldTrashableItemType.type, []):
            try:
                field = Field.objects_and_trash.get(id=field_id).specific
            except Field.DoesNotExist:
                continue

            yield field

    def restore(self, trashed_item: Table, trash_entry: TrashEntry):
        super().restore(trashed_item, trash_entry)

        field_cache = FieldCache()
        field_handler = FieldHandler()
        for field in self.fields_to_restore(trashed_item, trash_entry):
            try:
                field_handler.restore_field(
                    field,
                    send_field_restored_signal=field.table_id != trashed_item.id,
                    field_cache=field_cache,
                )
            except RelatedTableTrashedException:
                continue

            field_cache.cache_field(field)

        table_created.send(
            self,
            table=trashed_item,
            user=None,
        )

    def permanently_delete_item(
        self,
        trashed_item: Table,
        trash_item_lookup_cache=None,
    ):
        """Deletes the table schema and instance."""

        if (
            trash_item_lookup_cache is not None
            and "row_table_model_cache" in trash_item_lookup_cache
        ):
            # Invalidate the cached model for this table after it is deleted as
            # otherwise a row being deleted after will use the cached model and assume
            # it still exists.
            trash_item_lookup_cache["row_table_model_cache"].pop(trashed_item.id, None)

        try:
            Table.objects_and_trash.select_for_update(of=("self",)).get(
                id=trashed_item.id
            )
        except Table.DoesNotExist:
            raise TrashItemDoesNotExist()

        with safe_django_schema_editor() as schema_editor:
            model = trashed_item.get_model()
            schema_editor.delete_model(model)

        trashed_item.delete()

    # noinspection PyMethodMayBeStatic
    def trash(
        self,
        item_to_trash: Table,
        requesting_user: User,
        trash_entry: TrashEntry,
    ):
        table_to_trash = item_to_trash
        model = table_to_trash.get_model()

        update_collector = FieldUpdateCollector(table_to_trash)
        field_cache = FieldCache()
        handler = FieldHandler()

        for field in model._field_objects.values():
            field = field["field"]
            # One of the previously deleted fields might have cached this field we
            # now want to delete, ensure it is gone from the cache as presence in the
            # cache is treated as the field not being trashed in other code.
            field_cache.uncache_field(field)
            handler.delete_field(
                requesting_user,
                field,
                existing_trash_entry=trash_entry,
                apply_and_send_updates=False,
                update_collector=update_collector,
                field_cache=field_cache,
                allow_deleting_primary=True,
            )

        update_collector.send_additional_field_updated_signals()

        super().trash(table_to_trash, requesting_user, trash_entry)

        # Since link_row can link this table without creating the reverse relation,
        # we need to be sure to trash that fields manually.
        related_fields_to_trash: List[int] = []
        for field in table_to_trash.linkrowfield_set.filter(trashed=False):
            if (
                not field.trashed
                and field.table_id is not table_to_trash.id
                and not field.link_row_table_has_related_field
            ):
                handler.delete_field(
                    requesting_user,
                    field,
                    existing_trash_entry=trash_entry,
                    apply_and_send_updates=False,
                    update_collector=update_collector,
                    field_cache=field_cache,
                )
                related_fields_to_trash.append(field.id)

        if related_fields_to_trash:
            related_type = FieldTrashableItemType.type
            if trash_entry.related_items.get(related_type, None) is None:
                trash_entry.related_items[related_type] = []
            trash_entry.related_items[related_type].extend(related_fields_to_trash)
            trash_entry.save()

    def get_restore_operation_type(self) -> str:
        return RestoreDatabaseTableOperationType.type


class FieldTrashableItemType(TrashableItemType):
    type = "field"
    model_class = Field

    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        return trashed_item.table

    def get_name(self, trashed_item: Field) -> str:
        return trashed_item.name

    def restore(self, trashed_item: Field, trash_entry: TrashEntry):
        FieldHandler().restore_field(trashed_item.specific)

    def permanently_delete_item(
        self,
        field: Field,
        trash_item_lookup_cache=None,
    ):
        """Deletes the table schema and instance."""

        if (
            trash_item_lookup_cache is not None
            and "row_table_model_cache" in trash_item_lookup_cache
        ):
            # Invalidate the cached model for this field's table as after this field is
            # deleted usage of the old model will cause ProgrammingError's as the column
            # for this field no longer exists.
            trash_item_lookup_cache["row_table_model_cache"].pop(field.table.id, None)

        try:
            field = (
                Field.objects_and_trash.select_for_update(of=("self",))
                .get(id=field.id)
                .specific
            )
        except Field.DoesNotExist:
            raise TrashItemDoesNotExist()
        field_type = field_type_registry.get_by_model(field)

        # Remove the field from the table schema.
        with safe_django_schema_editor() as schema_editor:
            table = field.table
            from_model = table.get_model(field_ids=[], fields=[field])
            model_field = from_model._meta.get_field(field.db_column)
            schema_editor.remove_field(from_model, model_field)
            field.delete()

        # After the field is deleted we are going to call the after_delete method of
        # the field type because some instance cleanup might need to happen.
        field_type.after_delete(field, from_model, connection)

    def get_restore_operation_type(self) -> str:
        return RestoreFieldOperationType.type


class RowTrashableItemType(TrashableItemType):
    type = "row"
    model_class = GeneratedTableModel

    @property
    def requires_parent_id(self) -> bool:
        # A row is not unique just with its ID. We also need the table id (parent id)
        # to uniquely identify and lookup a specific row.
        return True

    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        return self._get_table(trashed_item.baserow_table_id)

    @staticmethod
    def _get_table(parent_id):
        try:
            return Table.objects_and_trash.select_related(
                "database", "database__workspace"
            ).get(id=parent_id)
        except Table.DoesNotExist:
            # The parent table must have been actually deleted, in which case the
            # row itself no longer exits.
            raise TrashItemDoesNotExist()

    def get_name(self, trashed_item) -> str:
        return str(trashed_item.id)

    def get_names(self, trashed_item: Any) -> str:
        return [str(trashed_item) or f"unnamed row {trashed_item.id}"]

    def restore(self, trashed_item, trash_entry: TrashEntry):
        try:
            super().restore(trashed_item, trash_entry)
        except Exception:
            raise FieldDataConstraintException()

        table = self.get_parent(trashed_item)
        model = table.get_model()
        rows_to_restore = [trashed_item]

        updated_fields = [f["field"] for f in model._field_objects.values()]

        _, dependant_fields = RowHandler().update_dependencies_of_rows_created(
            model, rows_to_restore
        )

        ViewHandler().field_value_updated(updated_fields + dependant_fields)
        SearchHandler.schedule_update_search_data(table, row_ids=[trashed_item.id])

        rows_to_return = list(
            model.objects.all().enhance_by_fields().filter(id=trashed_item.id)
        )
        rows_created.send(
            self,
            rows=rows_to_return,
            table=table,
            model=model,
            before=None,
            user=None,
            fields=updated_fields,
            dependant_fields=dependant_fields,
        )

    def permanently_delete_item(self, row, trash_item_lookup_cache=None):
        RichTextFieldMention.objects.filter(
            table_id=row.baserow_table_id, row_id=row.id
        ).delete()
        row.delete()

    def lookup_trashed_item(
        self, trashed_entry: TrashEntry, trash_item_lookup_cache=None
    ):
        """
        Returns the actual instance of the trashed item. By default simply does a get
        on the model_class's trash manager.

        :param trash_item_lookup_cache: A cache dict used to store the generated models
            for a given table so if looking up many rows from the same table we only
            need to lookup the tables fields etc once.
        :param trashed_entry: The entry to get the real trashed instance for.
        :return: An instance of the model_class with trashed_item_id
        """

        # Cache the expensive table.get_model function call if we are looking up
        # many trash items at once.
        if trash_item_lookup_cache is not None:
            model_cache = trash_item_lookup_cache.setdefault(
                "row_table_model_cache", {}
            )
            try:
                model = model_cache[trashed_entry.parent_trash_item_id]
            except KeyError:
                model = model_cache.setdefault(
                    trashed_entry.parent_trash_item_id,
                    self._get_table_model(trashed_entry.parent_trash_item_id),
                )
        else:
            model = self._get_table_model(trashed_entry.parent_trash_item_id)

        try:
            return model.trash.get(id=trashed_entry.trash_item_id)
        except model.DoesNotExist:
            raise TrashItemDoesNotExist()

    def _get_table_model(self, table_id):
        table = self._get_table(table_id)
        return table.get_model()

    def get_restore_operation_type(self) -> str:
        return RestoreDatabaseRowOperationType.type

    def get_restore_operation_context(self, trashed_entry, trashed_item) -> str:
        return self._get_table(trashed_entry.parent_trash_item_id)


class RowsTrashableItemType(TrashableItemType):
    type = "rows"
    model_class = TrashedRows

    @property
    def requires_parent_id(self) -> bool:
        # A row is not unique just with its ID. We also need the table id (parent id)
        return True

    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        return self._get_table(trashed_item.table_id)

    @staticmethod
    def _get_table(parent_id):
        try:
            return Table.objects_and_trash.select_related("database__workspace").get(
                id=parent_id
            )
        except Table.DoesNotExist:
            # The parent table must have been actually deleted, in which case the
            # row itself no longer exits.
            raise TrashItemDoesNotExist()

    def get_name(self, trashed_item) -> str:
        return " "

    def get_names(self, trashed_item) -> list:
        # When trashing the item, we store the row objects on the `trashed_item`,
        # so that we can re-use it later and prevent a possibly expensive query.
        if hasattr(trashed_item, "rows"):
            rows = trashed_item.rows
        else:
            rows = (
                trashed_item.table.get_model()
                .objects_and_trash.filter(id__in=trashed_item.row_ids)
                .enhance_by_fields()
            )
        return [str(row) or f"unnamed row {row.id}" for row in rows]

    def restore(self, trashed_item, trash_entry: TrashEntry):
        table = self._get_table(trashed_item.table_id)
        model = self._get_table_model(trashed_item.table_id)
        rows_to_restore_queryset = model.objects_and_trash.filter(
            id__in=trashed_item.row_ids
        )
        rows_to_restore_queryset.update(trashed=False)
        rows_to_restore = rows_to_restore_queryset.enhance_by_fields()
        trashed_item.delete()

        updated_fields = [f["field"] for f in model._field_objects.values()]
        _, dependant_fields = RowHandler().update_dependencies_of_rows_created(
            model, rows_to_restore
        )

        ViewHandler().field_value_updated(updated_fields + dependant_fields)
        SearchHandler.schedule_update_search_data(table, row_ids=trashed_item.row_ids)

        if len(rows_to_restore) < 50:
            rows_to_return = list(
                model.objects.all()
                .enhance_by_fields()
                .filter(id__in=[row.id for row in rows_to_restore])
            )
            rows_created.send(
                self,
                rows=rows_to_return,
                table=table,
                model=model,
                before=None,
                user=None,
                fields=updated_fields,
                dependant_fields=dependant_fields,
            )
        else:
            # Use table signal here instead of row signal because we don't want
            # to send too many ids in the signal
            table_updated.send(self, table=table, user=None, force_table_refresh=True)

    def trash(self, item_to_trash, requesting_user, trash_entry: TrashEntry):
        """
        Sets trashed=True for all the rows
        """

        table_model = self._get_table_model(item_to_trash.table_id)
        table_model.objects.filter(id__in=item_to_trash.row_ids).update(trashed=True)

    def permanently_delete_item(self, trashed_item, trash_item_lookup_cache=None):
        table_model = self._get_table_model(trashed_item.table_id)
        delete_qs = table_model.objects_and_trash.filter(id__in=trashed_item.row_ids)
        delete_qs._raw_delete(using=router.db_for_write(delete_qs.model))
        trashed_item.delete()
        RichTextFieldMention.objects.filter(
            table_id=trashed_item.table_id,
            row_id__in=trashed_item.row_ids,
        ).delete()

    def lookup_trashed_item(
        self, trashed_entry: TrashEntry, trash_item_lookup_cache=None
    ):
        try:
            return TrashedRows.objects.get(id=trashed_entry.trash_item_id)
        except TrashedRows.DoesNotExist:
            raise TrashItemDoesNotExist()

    def _get_table_model(self, table_id):
        table = self._get_table(table_id)
        return table.get_model()

    def get_restore_operation_type(self) -> str:
        return RestoreDatabaseRowOperationType.type

    def get_restore_operation_context(self, trashed_entry, trashed_item) -> str:
        return trashed_item.table


class ViewTrashableItemType(TrashableItemType):
    type = "view"
    model_class = View

    @property
    def requires_parent_id(self) -> bool:
        return False

    def permanently_delete_item(
        self, trashed_item: View, trash_item_lookup_cache: Dict[str, View] = None
    ):
        ViewIndexingHandler.before_view_permanently_deleted(trashed_item)
        trashed_item.delete()

    def get_owner(self, trashed_item: View) -> Optional[AbstractUser]:
        return view_ownership_type_registry.get(
            trashed_item.ownership_type
        ).get_trashed_item_owner(trashed_item)

    def get_parent(self, trashed_item: View) -> Optional[Any]:
        return trashed_item.table

    def restore(self, trashed_item: View, trash_entry):
        super().restore(trashed_item, trash_entry)

        type_name = view_type_registry.get_by_model(trashed_item.specific_class).type
        view_created.send(
            self,
            user=trash_entry.user_who_trashed,
            view=trashed_item,
            type_name=type_name,
        )

    def get_name(self, trashed_item: View) -> str:
        return trashed_item.name

    def get_restore_operation_type(self) -> str:
        return RestoreViewOperationType.type
