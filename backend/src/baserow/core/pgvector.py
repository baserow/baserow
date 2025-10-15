from enum import StrEnum
from functools import lru_cache

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import FieldDoesNotExist
from django.db import connection, models, transaction

from loguru import logger
from pgvector.django import VectorField

from baserow.core.models import SchemaOperation
from baserow.core.psycopg import sql

# This is the dimensions used by most open source models. OpenAI models use 1536 or
# higher dimensions but some models support 768 as well. This is also a good compromise
# between performance, space requirements and quality.
DEFAULT_EMBEDDING_DIMENSIONS = 768


class EmbeddingSchemaOperationType(StrEnum):
    ADD_EMBEDDING_FIELD = "add_embedding_field"
    MIGRATE_EMBEDDING_DATA = "migrate_embedding_data"


@lru_cache(maxsize=1)
def is_pgvector_enabled() -> bool:
    """
    Checks if the pgvector extension is enabled in the current database.
    Also caches the result for future calls.

    :return: True if the pgvector extension is available, False otherwise.
    """

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
        return cursor.fetchone() is not None


def try_enable_pgvector() -> bool:
    """
    Try to enable the pgvector extension.

    :return: True if the extension is now enabled, False otherwise.
    """

    if is_pgvector_enabled():
        return True

    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            is_pgvector_enabled.cache_clear()
    except Exception:
        return False

    return is_pgvector_enabled()


class EmbeddingMixinManager(models.Manager):
    def get_queryset(self):
        """
        The first time this is called, we try to initialize the vector fields on all
        models that inherit from EmbeddingMixin, so that their _can_search_vectors
        attribute is set correctly.
        """

        self.model.try_init_vector_field()
        return super().get_queryset()


class EmbeddingMixin(models.Model):
    VECTOR_FIELD_NAME = "embedding"
    EMBEDDING_DIMENSIONS = DEFAULT_EMBEDDING_DIMENSIONS

    _can_search_vectors = None
    """
    Set to True if the VectorField is available for similarity search. This is only
    possible if pgvector is installed and the vector field has been created.
    """

    _embedding_array = ArrayField(
        models.FloatField(),
        size=EMBEDDING_DIMENSIONS,
        help_text=(
            "An array containing the embedding values as a float list. This is used for "
            "as backup if pgvector is not available, so we can copy the values to the "
            "vector field when pgvector is enabled, but they cannot be queried directly."
        ),
        null=True,
    )

    objects = EmbeddingMixinManager()

    @classmethod
    def _init_vector_field(cls) -> None:
        """
        Initializes the mixin by setting the _can_search_vectors attribute.
        This should be called once when all apps are ready.
        """

        cls._can_search_vectors = cls.is_vector_field_ready()
        if cls._can_search_vectors:
            cls._add_vector_field_to_model()

    @classmethod
    def try_init_vector_field(cls) -> None:
        """
        Initializes the mixin by setting the _can_search_vectors attribute.
        This should be called once when all apps are ready.
        """

        if cls._can_search_vectors is None:
            cls._init_vector_field()

    @classmethod
    def can_search_vectors(cls) -> bool:
        cls.try_init_vector_field()
        return cls._can_search_vectors

    class Meta:
        abstract = True

    @classmethod
    @transaction.atomic
    def _create_field_in_model(cls, field: VectorField) -> None:
        """
        Creates the given vector field in the given model's database table.
        It also records the operation in the SchemaOperation table so that it is not
        attempted again.

        :param model: The model to add the field to
        :param field: The vector field to add

        """

        with connection.schema_editor() as schema_editor:
            # Ensure we only create the field if it does not exist yet. While this
            # should not happen if the SchemaOperation is updated correctly, this can
            # happen in tests or if some manual intervention happened. In any case, if
            # the field already exists, there's no need to fail or log an error.
            schema_editor.sql_create_column = schema_editor.sql_create_column.replace(
                "ADD COLUMN", "ADD COLUMN IF NOT EXISTS"
            )
            schema_editor.add_field(cls, field)

        SchemaOperation.objects.create(
            content_type=ContentType.objects.get_for_model(cls),
            operation=EmbeddingSchemaOperationType.ADD_EMBEDDING_FIELD.value,
        )

    @classmethod
    def _add_vector_field_to_model(cls) -> VectorField:
        """
        Adds the vector field to the given model class, so that it can be used for
        vector search. It does not create the field in the database, use
        `_create_field_in_model` for that.

        :param model: The model to add the field to
        :return: The created VectorField instance
        """

        vector_field = VectorField(
            dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
            null=True,
            help_text=(
                "The embedding vector for the chunk. This is used for retrieval."
            ),
        )
        vector_field.contribute_to_class(cls, cls.VECTOR_FIELD_NAME)

        cls._meta._expire_cache()
        cls._can_search_vectors = True

        return vector_field

    @classmethod
    def _create_vector_index(cls) -> None:
        """
        Creates the vector index on the given model's vector field, if it does not
        already exist. It uses the HNSW algorithm with cosine distance.

        :param model: The model to create the index for
        :return: None
        """

        field_name = cls.VECTOR_FIELD_NAME

        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    """
                CREATE INDEX IF NOT EXISTS {index_name}
                ON {table} USING hnsw ({field} vector_cosine_ops)
                WITH (m=16, ef_construction=64);
            """
                ).format(
                    index_name=sql.Identifier(f"{cls._meta.db_table}_{field_name}_idx"),
                    table=sql.Identifier(cls._meta.db_table),
                    field=sql.Identifier(field_name),
                )
            )

    @classmethod
    @transaction.atomic
    def _migrate_embedding_data(cls) -> None:
        """
        Migrates the existing embedding data from the ArrayField to the VectorField
        in the given model. It also creates the vector index on the field and records
        the operation in the SchemaOperation table so that it is not attempted again.

        :param model: The model to migrate the data for
        :return: None
        """

        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    """
                UPDATE {table}
                SET {field} = _embedding_array::vector
                WHERE {field} IS NULL AND _embedding_array IS NOT NULL
            """
                ).format(
                    table=sql.Identifier(cls._meta.db_table),
                    field=sql.Identifier(cls.VECTOR_FIELD_NAME),
                )
            )

        cls._create_vector_index()

        # This doesn't need to fail if we already did
        SchemaOperation.objects.bulk_create(
            [
                SchemaOperation(
                    content_type=ContentType.objects.get_for_model(cls),
                    operation=EmbeddingSchemaOperationType.MIGRATE_EMBEDDING_DATA.value,
                )
            ],
            ignore_conflicts=True,
        )

    @classmethod
    def is_vector_field_ready(cls) -> bool:
        """
        Checks if the vector field exists and is ready for similarity search.

        :param table_name: The database table name to check
        :return: True if the vector field exists and is ready for similarity search,
            False otherwise.
        """

        return (
            is_pgvector_enabled()
            and SchemaOperation.objects.filter(
                content_type=ContentType.objects.get_for_model(cls),
                operation=EmbeddingSchemaOperationType.MIGRATE_EMBEDDING_DATA.value,
            ).exists()
        )

    @classmethod
    def migrate_to_vector_field_if_needed(cls) -> None:
        """
        Ensures that the vector field is added to the model if pgvector is enabled and
        the existing data has been migrated from the ArrayField to the VectorField, so
        that vector search can be used. If the field already exists and the data has
        been migrated, this function does nothing.
        """

        data_migrated_done = SchemaOperation.objects.filter(
            content_type=ContentType.objects.get_for_model(cls),
            operation=EmbeddingSchemaOperationType.MIGRATE_EMBEDDING_DATA.value,
        ).exists()

        if data_migrated_done:
            return

        vector_field_created = SchemaOperation.objects.filter(
            content_type=ContentType.objects.get_for_model(cls),
            operation=EmbeddingSchemaOperationType.ADD_EMBEDDING_FIELD.value,
        ).exists()

        try:
            if not vector_field_created:
                try:
                    field = cls._meta.get_field(cls.VECTOR_FIELD_NAME)
                except FieldDoesNotExist:
                    field = cls._add_vector_field_to_model()

                cls._create_field_in_model(field)

            cls._migrate_embedding_data()
        except Exception:
            logger.exception(f"Failed to migrate {cls.__name__} to pgvector field.")


def reset_vector_schema_operations() -> None:
    """
    if pgvector is disabled, it cascade deletes the vector field and related index,
    so we need to reset the state to allow re-creating it later.
    """

    SchemaOperation.objects.filter(
        operation__in=[
            EmbeddingSchemaOperationType.ADD_EMBEDDING_FIELD.value,
            EmbeddingSchemaOperationType.MIGRATE_EMBEDDING_DATA.value,
        ]
    ).delete()


def try_migrate_vector_fields(sender, **kwargs):
    """
    Verify if the pgvector extension is enabled or not. This is called during the
    migration process, typically executed with the `locked_migrate` management command.

    If it is enabled, ensure that the embedding field exists and that the existing data
    has been migrated to the pgvector field, so that vector search can be used.

    If we just enabled pgvector, we also make sure to reset the state if it was
    previously disabled, so that the field and index can be created later.
    """

    was_enabled = is_pgvector_enabled()
    pgvector_enabled = try_enable_pgvector()

    print("Checking pgvector extension:", end=" ")

    if not pgvector_enabled:  # nothing to do
        print("not available. It will be retried on next migration.")
        return
    elif not was_enabled:  # we just enabled it
        print("enabled now.", end=" ")
        # Make sure we start from a clean state
        reset_vector_schema_operations()
    else:
        print("available.", end=" ")

    print("Ensuring vector fields are ready...", end=" ")

    for model in apps.get_models():
        if issubclass(model, EmbeddingMixin):
            model.migrate_to_vector_field_if_needed()

    print("done.")
