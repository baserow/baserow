from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.db import models, transaction
from django.db.models import Case, F, Func, JSONField, Value, When

from baserow.contrib.database.table.constants import FIELD_METADATA_COLUMN_NAME
from baserow.contrib.database.table.models import GeneratedTableModel


class JSONBRemoveKey(Func):
    """Custom Func for PostgreSQL JSONB - operator (remove key)."""

    function = ""
    arity = 2
    arg_joiner = " - "
    output_field = models.JSONField()

    def as_sql(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="%(expressions)s",
            arg_joiner=self.arg_joiner,
            **extra_context,
        )


@dataclass
class MetadataUpdate:
    """Typed container for metadata update operations."""

    row_id: int
    field_id: int
    metadata: Dict[str, Any]


class FieldMetadataHandler:
    METADATA_COLUMN = FIELD_METADATA_COLUMN_NAME

    @classmethod
    def is_metadata_available(cls, model: type[GeneratedTableModel]) -> bool:
        """
        Check if the metadata column is available on the model.

        This provides a consistent way to check if metadata operations
        can be performed on a model.

        :param model: The generated table model class
        :return: True if metadata column exists, False otherwise
        """

        return hasattr(model, cls.METADATA_COLUMN)

    @staticmethod
    def get_model_field() -> models.JSONField:
        """
        Returns the field definition for the metadata column.
        Used when adding the column to a table dynamically.
        """

        return models.JSONField(
            null=False,
            blank=True,
            default=dict,
            db_default={},
            help_text="Stores metadata for all fields in this row.",
        )

    @classmethod
    def get_metadata(
        cls,
        model: type[GeneratedTableModel],
        row_ids: List[int],
        field_ids: Optional[List[int]] = None,
    ) -> Dict[int, Dict[int, Dict[str, Any]]]:
        """
        Get metadata for rows efficiently in a single query.

        Returns a nested dictionary structure:
        {row_id: {field_id: metadata_dict, ...}, ...}

        Only rows and fields that have metadata are included in the result.

        :param model: The generated table model class
        :param row_ids: List of row IDs to get metadata for
        :param field_ids: Optional list of field IDs to filter by.
            If None, returns metadata for all fields.
        :return: Nested dictionary of {row_id: {field_id: metadata}}
        """

        if not cls.is_metadata_available(model):
            return {}

        if not row_ids:
            return {}

        rows = model.objects.filter(id__in=row_ids).only("id", cls.METADATA_COLUMN)

        result: Dict[int, Dict[int, Dict[str, Any]]] = {}

        for row in rows:
            field_metadata = getattr(row, cls.METADATA_COLUMN, {}) or {}

            if not field_metadata:
                continue

            row_metadata: Dict[int, Dict[str, Any]] = {}

            for field_id_str, metadata in field_metadata.items():
                try:
                    field_id = int(field_id_str)
                except ValueError:
                    continue

                if field_ids is not None and field_id not in field_ids:
                    continue

                if metadata:
                    row_metadata[field_id] = metadata

            if row_metadata:
                result[row.id] = row_metadata

        return result

    @classmethod
    def set_metadata(
        cls,
        model: type[GeneratedTableModel],
        updates: List[MetadataUpdate],
        merge: bool = True,
    ):
        """
        Set metadata for rows/fields.

        Always accepts a list of MetadataUpdate objects. For single updates,
        pass a list with one element.

        When merge=True (default), uses PostgreSQL's jsonb_set function to
        atomically update only the specific field's metadata, avoiding race
        conditions from concurrent updates to different fields.

        When merge=False, replaces the entire field metadata.

        :param model: The generated table model class
        :param updates: List of MetadataUpdate objects
        :param merge: If True, merge with existing metadata. If False,
            replace completely. Defaults to True.

        """

        if not cls.is_metadata_available(model):
            return

        if merge:
            cls._set_metadata_merge(model, updates)
        else:
            cls._set_metadata_replace(model, updates)

    @classmethod
    def _set_metadata_merge(
        cls,
        model: type[GeneratedTableModel],
        updates: List[MetadataUpdate],
    ):
        """
        Internal method to set metadata using merge mode (atomic jsonb_set).
        """

        updates_by_row = defaultdict(dict)
        for update in updates:
            field_id_str = str(update.field_id)
            updates_by_row[update.row_id][field_id_str] = update.metadata

        row_ids = list(updates_by_row.keys())

        whens = []
        for row_id, field_updates in updates_by_row.items():
            jsonb_expr = F(cls.METADATA_COLUMN)

            for field_id, metadata in field_updates.items():
                jsonb_expr = Func(
                    Func(
                        jsonb_expr,
                        Value("{}"),
                        function="COALESCE",
                        output_field=JSONField(),
                    ),
                    Value([field_id]),
                    Value(metadata, output_field=JSONField()),
                    Value(True),  # create_missing = true
                    function="jsonb_set",
                    output_field=JSONField(),
                )

            whens.append(When(id=row_id, then=jsonb_expr))

        if whens:
            model.objects.filter(id__in=row_ids).update(
                **{cls.METADATA_COLUMN: Case(*whens, default=F(cls.METADATA_COLUMN))}
            )

    @classmethod
    def _set_metadata_replace(
        cls,
        model: type[GeneratedTableModel],
        updates: List[MetadataUpdate],
    ):
        """
        Internal method to set metadata using replace mode.
        Fetches rows and replaces field metadata completely.
        """

        updates_by_row = defaultdict(dict)
        for update in updates:
            field_id_str = str(update.field_id)
            updates_by_row[update.row_id][field_id_str] = update.metadata

        row_ids = list(updates_by_row.keys())

        with transaction.atomic():
            rows = model.objects.select_for_update().filter(id__in=row_ids)

            rows_to_update = []
            for row in rows:
                field_metadata = getattr(row, cls.METADATA_COLUMN, {}) or {}
                field_updates = updates_by_row.get(row.id, {})

                for field_id, metadata in field_updates.items():
                    field_metadata[field_id] = metadata

                setattr(row, cls.METADATA_COLUMN, field_metadata)
                rows_to_update.append(row)

            if rows_to_update:
                model.objects.bulk_update(rows_to_update, [cls.METADATA_COLUMN])

    @classmethod
    def delete_metadata(
        cls,
        model: type[GeneratedTableModel],
        field_id: int,
        row_ids: Optional[List[int]] = None,
    ):
        """
        Delete metadata for a specific field.

        Can delete for all rows or specific rows:
        - delete_metadata(model, field_id) - delete for all rows
        - delete_metadata(model, field_id, row_ids=[...]) - delete for specific rows

        Uses PostgreSQL's - operator to remove a key from JSONB atomically.

        :param model: The generated table model class
        :param field_id: The field ID to remove metadata for
        :param row_ids: Optional list of row IDs to limit deletion to
        """

        if not cls.is_metadata_available(model):
            return

        field_id_str = str(field_id)

        queryset = model.objects.filter(
            **{f"{cls.METADATA_COLUMN}__has_key": field_id_str}
        )

        if row_ids is not None:
            queryset = queryset.filter(id__in=row_ids)

        queryset.update(
            **{
                cls.METADATA_COLUMN: JSONBRemoveKey(
                    F(cls.METADATA_COLUMN), Value(field_id_str)
                )
            }
        )

    @classmethod
    def get_rows_by_metadata(
        cls,
        model: type[GeneratedTableModel],
        field_id: int,
        key: str,
        value: Any,
    ):
        """
        Query rows by metadata key:value for a specific field.

        This is a generic filter that can match any key:value in the
        field's metadata.

        :param model: The generated table model class
        :param field_id: The field ID to query
        :param key: The metadata key to filter by
        :param value: The value to match
        :return: QuerySet of rows matching the criteria
        """

        if not cls.is_metadata_available(model):
            return model.objects.none()

        field_id_str = str(field_id)

        return model.objects.filter(
            **{f"{cls.METADATA_COLUMN}__{field_id_str}__{key}": value}
        )

    @classmethod
    def get_rows_with_metadata(
        cls,
        model: type[GeneratedTableModel],
        field_id: int,
    ):
        """
        Get all rows that have metadata for a specific field.

        :param model: The generated table model class
        :param field_id: The field ID to query
        :return: QuerySet of rows with metadata for this field
        """

        if not cls.is_metadata_available(model):
            return model.objects.none()

        field_id_str = str(field_id)

        return model.objects.filter(**{f"{cls.METADATA_COLUMN}__has_key": field_id_str})

    @classmethod
    def on_field_updated(cls, field, field_type_changed: bool):
        """
        Handle field updates by clearing metadata if the field type changed.

        When a field's type changes, any existing metadata becomes invalid
        and should be cleared. This method encapsulates the logic for checking
        if the type changed, if metadata is available, and clearing it if needed.

        :param field: The field that was updated
        :param field_type_changed: Whether the field type changed
        """

        if not field_type_changed:
            return

        model = field.table.get_model(field_ids=[], add_dependencies=False)
        if cls.is_metadata_available(model):
            cls.delete_metadata(model, field.id)

    @classmethod
    def on_field_deleted(cls, field):
        """
        Handle field deletion by removing all metadata for the field.

        This should be called when a field is permanently deleted to clean up
        any associated metadata.

        :param field: The field that was deleted
        """

        model = field.table.get_model(field_ids=[], add_dependencies=False)
        if cls.is_metadata_available(model):
            cls.delete_metadata(model, field.id)
