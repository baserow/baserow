from contextlib import contextmanager
from functools import lru_cache
from typing import Type

from django.db import IntegrityError, ProgrammingError, connection, router, transaction
from django.db.models import Exists, Model, OuterRef, QuerySet

from loguru import logger
from pgvector.django import HnswIndex

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.search.handler import SearchDatabaseSchemaEditor
from baserow.contrib.database.table.models import GeneratedModelAppsProxy
from baserow.core.psycopg import errors, sql
from baserow.core.utils import to_camel_case

from .models import AbstractSemanticSearchChunk


def get_vector_table_name(workspace_id: int) -> str:
    """
    :param workspace_id: The workspace of the vector table.
    :return: The name of the database table with the chunks of the workspace.
    """

    return f"database_semantic_search_workspace_{workspace_id}_data"


@lru_cache(maxsize=1024)
def _vector_table_exists(workspace_id: int) -> bool:
    """
    Cached to avoid a query on every indexing run. The cache is cleared when a table
    is created or dropped.

    :param workspace_id: The workspace of the vector table.
    :return: Whether the vector table of the workspace exists.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema()
                AND table_name = %s
            )
            """,
            [get_vector_table_name(workspace_id)],
        )
        return cursor.fetchone()[0]


@lru_cache(maxsize=1024)
def _generate_vector_table_model(
    workspace_id: int, managed: bool = False
) -> Type[AbstractSemanticSearchChunk]:
    """
    :param workspace_id: The workspace of which the table contains the chunks.
    :param managed: Only True to create or drop the table, because Django only
        creates the indexes of managed models.
    :return: The model of the vector table of the workspace.
    """

    app_label = "database_semantic_search"
    table_name = get_vector_table_name(workspace_id)
    model_name = to_camel_case(table_name)

    baserow_models = {}
    apps = GeneratedModelAppsProxy(baserow_models, app_label)
    meta = type(
        "Meta",
        (),
        {
            "apps": apps,
            "managed": managed,
            "db_table": table_name,
            "app_label": app_label,
            "unique_together": [("field_id", "row_id", "chunk_index")],
            "indexes": [
                HnswIndex(
                    name=f"{table_name}_embedding_idx",
                    fields=["embedding"],
                    m=16,
                    ef_construction=64,
                    opclasses=["vector_cosine_ops"],
                )
            ],
        },
    )

    def __str__(self):
        return model_name

    attrs = {
        "Meta": meta,
        "__module__": "database.models",
        "_generated_table_model": True,
        "baserow_workspace_id": workspace_id,
        "baserow_models": baserow_models,
        "parent": workspace_id,
        "__str__": __str__,
    }

    return type(model_name, (AbstractSemanticSearchChunk, Model), attrs)


@contextmanager
def _ignore_missing_table():
    # The table can be dropped together with its workspace at any moment, and the
    # cached existence can be outdated, so it isn't checked first.
    try:
        with transaction.atomic():
            yield
    except ProgrammingError as exc:
        if not isinstance(exc.__cause__, errors.UndefinedTable):
            raise


class SemanticSearchVectorTable:
    """
    The chunks and embeddings of all semantic search fields of a workspace. The
    table is created when the workspace first needs it.
    """

    def __init__(self, workspace_id: int):
        """
        :param workspace_id: The workspace of which the table contains the vectors.
        """

        self.workspace_id = workspace_id
        self.model = _generate_vector_table_model(workspace_id)
        self.name = self.model._meta.db_table

    def exists(self) -> bool:
        """
        :return: Whether the table was created.
        """

        return _vector_table_exists(self.workspace_id)

    def create_if_not_exists(self):
        """
        Creates the table if it doesn't exist yet. Several tables of the same workspace
        can be indexed at the same time, so another task can create it first.
        """

        if _vector_table_exists(self.workspace_id):
            return

        # Django creates indexes only when the model is managed. The index is
        # created while the table is still empty, so that it never has to be built on
        # a large table.
        model = _generate_vector_table_model(self.workspace_id, managed=True)
        try:
            with transaction.atomic():
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(model)
        except ProgrammingError as exc:
            if isinstance(
                exc.__cause__, (errors.DuplicateTable, errors.DuplicateObject)
            ):
                logger.debug(
                    f"Vector table for workspace {self.workspace_id} already exists."
                )
            else:
                raise exc
        except IntegrityError as exc:
            if isinstance(exc.__cause__, errors.UniqueViolation):
                logger.debug(
                    f"Race condition: sequence or object for workspace "
                    f"{self.workspace_id} already exists (UniqueViolation)."
                )
            else:
                raise
        _vector_table_exists.cache_clear()

    def drop(self):
        model = _generate_vector_table_model(self.workspace_id, managed=True)
        with safe_django_schema_editor(
            classes=[SearchDatabaseSchemaEditor]
        ) as schema_editor:
            schema_editor.delete_model(model)

        _vector_table_exists.cache_clear()

    def _delete(self, queryset):
        # Without loading the chunks first, which have large embeddings.
        queryset._raw_delete(using=router.db_for_write(self.model))

    def get_content_hashes(self, field_id: int, row_ids: list[int]) -> dict[int, str]:
        """
        :param field_id: The field of the cells.
        :param row_ids: The rows of the cells.
        :return: The hash of the indexed value of every cell that has chunks, by
            row id.
        """

        return dict(
            self.model.objects.filter(
                field_id=field_id, row_id__in=row_ids, chunk_index=0
            ).values_list("row_id", "content_hash")
        )

    def replace_chunks(
        self,
        field_id: int,
        row_ids: list[int],
        chunks: list[AbstractSemanticSearchChunk],
    ):
        """
        Replaces all the chunks of the provided rows. Rows without new chunks no
        longer have a value to search in.

        :param field_id: The field of the cells.
        :param row_ids: The rows of which the chunks are replaced.
        :param chunks: The new chunks of the rows, created with `self.model`.
        """

        with transaction.atomic():
            self._delete(
                self.model.objects.filter(field_id=field_id, row_id__in=row_ids)
            )
            self.model.objects.bulk_create(chunks)

    def delete_marked(self, marked_updates: QuerySet):
        """
        Deletes the chunks of the fields and rows that are marked for deletion, if the
        table exists.

        :param marked_updates: The pending updates that mark the chunks.
        """

        with _ignore_missing_table():
            # Two statements, like the full-text search data, because one with an
            # `OR` can't use the indexes.
            self._delete(
                self.model.objects.filter(
                    Exists(
                        marked_updates.filter(
                            field_id=OuterRef("field_id"), row_id__isnull=True
                        )
                    )
                )
            )
            self._delete(
                self.model.objects.filter(
                    Exists(
                        marked_updates.filter(
                            field_id=OuterRef("field_id"), row_id=OuterRef("row_id")
                        )
                    )
                )
            )

    def delete_rows_not_in(self, field_id: int, row_model: Type[Model]):
        """
        Deletes the chunks of rows that no longer exist, because not every way of
        deleting rows goes through the trash.

        :param field_id: The field of which the chunks are checked.
        :param row_model: The model of the table of the field.
        """

        self._delete(
            self.model.objects.filter(field_id=field_id).exclude(
                Exists(row_model.objects_and_trash.filter(id=OuterRef("row_id")))
            )
        )

    def copy_field(
        self,
        source: "SemanticSearchVectorTable",
        source_field_id: int,
        target_field_id: int,
    ):
        """
        Copies the chunks of a field of which the rows were copied with the same
        ids, so that they don't have to be embedded again. Nothing is copied if the
        source table doesn't exist.

        :param source: The vector table of the workspace of the source field.
        :param source_field_id: The field of which the chunks are copied.
        :param target_field_id: The field that gets the chunks.
        """

        # In the database, because the ORM would load all embeddings.
        with _ignore_missing_table(), connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    INSERT INTO {target}
                        (field_id, row_id, chunk_index, content_hash, embedding)
                    SELECT %s, row_id, chunk_index, content_hash, embedding
                    FROM {source} WHERE field_id = %s
                    ON CONFLICT DO NOTHING
                    """
                ).format(
                    target=sql.Identifier(self.name),
                    source=sql.Identifier(source.name),
                ),
                [target_field_id, source_field_id],
            )
