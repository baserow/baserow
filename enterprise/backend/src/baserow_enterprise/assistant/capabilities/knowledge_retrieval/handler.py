from typing import IO, Iterable, Literal, Tuple

from django.core import serializers
from django.db.models import F, Q

from django_redis import get_redis_connection
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery, filter
from redisvl.utils.vectorize import OpenAITextVectorizer, base

from baserow_enterprise.assistant.models import (
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)

from .constants import (
    DOCUMENT_CHUNK_ID_FIELD_NAME,
    DOCUMENT_CONTENT_FIELD_NAME,
    EMBEDDING_MODEL,
    KNOWLEDGE_EMBEDDING_FIELD_NAME,
)
from .types import KNOWLEDGE_INDEX_SCHEMA, KnowledgeVector
from .utils import document_chunk_to_knowledge_vector


class VectorStore:
    """
    A vector store that uses Redis as the backend. It allows creating a search index,
    loading vectors, querying the index, and deleting vectors. A vector represents a
    document chunk in the knowledge base, with its metadata and embedding for similarity
    search. When document chunks are added or updated in the knowledge base, their
    embeddings should be computed and loaded into the vector store to keep it in sync.
    """

    def __init__(
        self,
        vectorizer: base.BaseVectorizer | None = None,
    ):
        self._redis_client = get_redis_connection("default")
        self._index = None
        self._vectorizer = vectorizer

    @property
    def index(self) -> SearchIndex:
        if self._index is None:
            self._index, _ = self._create_index(overwrite=False)
        return self._index

    @property
    def vectorizer(self):
        if self._vectorizer is None:
            self._vectorizer = OpenAITextVectorizer(model=EMBEDDING_MODEL)
        return self._vectorizer

    def _create_index(self, overwrite=False) -> tuple[SearchIndex:, bool]:
        """
        Create a search index with the specified schema. If index_schema is None, the
        default index schema will be used. If overwrite is True, the index will be
        dropped and re-created.

        :param index_schema: The schema to use for the index
        :param overwrite: Whether to drop and re-create the index, in case it already
            exists
        :param drop: Whether to drop the index if it already exists
        :return: The created search index and a boolean indicating whether it was
            created or it was already existing
        """

        index = SearchIndex.from_dict(
            KNOWLEDGE_INDEX_SCHEMA,
            redis_client=self._redis_client,
            validate_on_load=True,
        )
        if not overwrite and index.exists():
            created = False
        else:
            index.create(overwrite=overwrite, drop=overwrite)
            created = True

        return index, created

    def load_vectors(self, vectors: list[KnowledgeVector]) -> list[str]:
        """
        Load data into the specified search index.

        :param vectors: The list of vectors to load
        :return: A list of keys for the loaded vectors
        :raise SchemaValidationError: If the vector schema is invalid according to the
            index schema
        """

        if not vectors:
            return []

        keys = self.index.load(vectors)
        return keys

    def fetch_by_key(self, vector_key: str) -> KnowledgeVector | None:
        """
        Fetch a single vector by its key. The key can be in the format
        `prefix:key` or just `key`.

        :param vector_key: The key of the vector to fetch
        :return: The vector data or None if not found
        """

        # The fetch method expects just the key, without the prefix
        return self.index.fetch(vector_key.split(":", 1)[-1])

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts.

        :param texts: The list of texts to embed
        :return: A list of vectors corresponding to the input texts
        """

        if not texts:
            return []

        return self.vectorizer.embed_many(texts, batch_size=20)

    def embed_many_chunks(
        self, document_chunks: list[KnowledgeBaseChunk]
    ) -> list[list[float]]:
        """
        Embed a list of document chunks, using their content.

        :param document_chunks: The list of document chunks to embed
        :return: A list of embeddings corresponding to the input document chunks
        """

        return self.embed_many([chunk.content for chunk in document_chunks])

    def delete_many(self, vector_keys: list[str]) -> int:
        """
        Remove a specific entry or multiple entries from the index by it's key ID.
        """

        if not vector_keys:
            return 0

        return self.index.drop_keys(vector_keys)

    def query(self, query: str, num_results: int = 20) -> list[str]:
        """
        Query the vector store with the given text query and return the content of the
        most relevant document chunks.

        :param query: The text query to search for
        :param num_results: The number of results to return
        :return: A list of document chunk contents matching the query
        """

        (vector_query,) = self.embed_many([query])
        results = self.raw_query(vector_query, num_results=num_results)
        response = [res[DOCUMENT_CONTENT_FIELD_NAME] for res in results]

        return response

    def raw_query(
        self,
        query_vector: list[float],
        vector_field_name: str | None = None,
        return_fields: list[str] | None = None,
        num_results: int = 20,
        filter_expression: filter.FilterExpression | None = None,
    ) -> list[KnowledgeVector]:
        """
        Query the specified search index.

        :param query: The query string to search for
        :param filters: Optional filters to apply to the search
        :return: A list of vectors matching the query
        """

        vector_field_name = vector_field_name or KNOWLEDGE_EMBEDDING_FIELD_NAME
        return_fields = return_fields or [
            DOCUMENT_CHUNK_ID_FIELD_NAME,
            DOCUMENT_CONTENT_FIELD_NAME,
        ]

        query = VectorQuery(
            vector=query_vector,
            vector_field_name=vector_field_name,
            return_fields=return_fields,
            num_results=num_results,
            filter_expression=filter_expression,
        )
        return self.index.query(query)

    def sync_vectors(self, chunks: Iterable[KnowledgeBaseChunk] | None = None):
        """
        Sync KnowledgeBaseDocumentChunk chunks embeddings with the vector store index,
        so the assistant can retrieve them. If no chunks are provided, all chunks
        belonging to documents with status READY will be synced.

        This method repopulates the Redis index from already computed embeddings without
        needing to re-run the vectorization process. Useful to make sure the index is in
        sync with the documents in the knowledge base.
        """

        if chunks is None:
            chunks_filters = Q(
                source_document__status=KnowledgeBaseDocument.Status.READY
            )

            chunks = (
                KnowledgeBaseChunk.objects.filter(chunks_filters)
                .select_related(
                    "source_document__category__parent__parent__parent__parent"
                )
                .all()
            )

        # Drop and recreate the index with the ready chunks to ensure it's synced
        self._create_index(overwrite=True)
        chunk_vectors = [document_chunk_to_knowledge_vector(chunk) for chunk in chunks]
        vector_ids = self.load_vectors(chunk_vectors)

        for vector_id, chunk in zip(vector_ids, chunks):
            chunk.vector_id = vector_id

        KnowledgeBaseChunk.objects.bulk_update(chunks, ["vector_id", "updated_on"])


class KnowledgeBaseHandler:
    def __init__(self, vector_store: VectorStore | None = None):
        self.vector_store = vector_store or VectorStore()

    def has_knowledge(self) -> bool:
        """
        Returns whether the knowledge base has any documents with status READY.

        :return: True if there is at least one document with status READY, False
            otherwise
        """

        return KnowledgeBaseDocument.objects.filter(
            status=KnowledgeBaseDocument.Status.READY
        ).exists()

    def retrieve_knowledge_chunks(self, query: str, num_results=20) -> list[str]:
        """
        Retrieve the most relevant knowledge chunks for the given query.

        :param query: The text query to search for
        :param num_results: The number of results to return
        :return: A list of document chunk contents matching the query
        """

        return self.vector_store.query(query, num_results=num_results)

    def load_categories(self, categories_serialized: Iterable[Tuple[str, str | None]]):
        """
        Import categories into the knowledge base.

        :param categories_serialized: An iterable of tuples containing category names
            and their parent category names (or None if no parent).
        """

        category_by_name = {}
        parent_name_by_name = {}
        categories = []

        # Make sure all categories exist, so later we can set the parent IDs
        for name, parent_name in categories_serialized:
            category = KnowledgeBaseCategory(name=name, parent_id=None)
            categories.append(category)
            category_by_name[name] = category
            if parent_name:
                parent_name_by_name[name] = parent_name

        KnowledgeBaseCategory.objects.bulk_create(
            categories,
            update_conflicts=True,
            unique_fields=["name"],
            update_fields=["parent_id"],
        )

        # Now that all categories exist and have an ID, update the parent IDs
        categories_with_parents = []
        for name, parent_name in parent_name_by_name.items():
            if (
                not parent_name
                or (parent_category := category_by_name.get(parent_name)) is None
            ):
                continue

            category = category_by_name[name]
            category.parent_id = parent_category.id
            categories_with_parents.append(category)

        KnowledgeBaseCategory.objects.bulk_update(
            categories_with_parents, ["parent_id"]
        )

    def dump_knowledge_base(
        self,
        documents: Iterable[KnowledgeBaseDocument] | None = None,
        format: Literal["json", "yaml", "jsonl", "xml"] = "jsonl",
        stream: IO[str] | None = None,
    ) -> str | None:
        """
        Dump the knowledge base to a serialized representation that can be later loaded
        with `load_knowledge_base`. If no documents are provided, all documents will be
        dumped, together with their categories and chunks. If a stream is provided, the
        serialized data will be written to it and None will be returned. Otherwise, the
        serialized data will be returned as a string.

        :param documents: The documents to dump. If None, all documents will be dumped.
        :param format: The format to use for serialization.
        :param stream: The stream to write the serialized data to. If None, the data
            will be returned as a string.
        :return: The serialized data as a string, or None if a stream is provided.
        """

        if documents is None:
            documents = KnowledgeBaseDocument.objects.all().select_related("category")

        categories = (
            KnowledgeBaseCategory.objects.filter(
                id__in=[doc.category_id for doc in documents]
            )
            .select_related("parent__parent__parent__parent")
            .order_by(F("parent").asc(nulls_first=True))
        )
        chunks = KnowledgeBaseChunk.objects.filter(
            source_document__in=documents
        ).select_related("source_document")

        export = serializers.serialize(
            format,
            list(categories) + list(documents) + list(chunks),
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True,
            stream=stream,
        )
        return export

    def load_knowledge_base(
        self,
        stream_or_string: IO[str] | str,
        format: Literal["json", "yaml", "jsonl", "xml"] = "jsonl",
    ) -> list[KnowledgeBaseDocument]:
        """
        Load a knowledge base from a serialized representation, previously exported with
        `dump_knowledge_base`. The existing documents with the same slug will be
        replaced, together with their chunks. The categories will be created if they
        don't exist yet. Once the knowledge base is loaded, the vector store index will
        be synced.

        :param stream_or_string: The stream or string containing the serialized
            knowledge base data.
        :param format: The format of the serialized data
        :return: The list of loaded KnowledgeBaseDocument instances
        """

        categories = []
        documents = []
        chunks = []

        def _recreate_documents():
            # 1. This also cascade deletes all the chunks belonging to the documents
            KnowledgeBaseDocument.objects.filter(
                slug__in=[doc.slug for doc in documents]
            ).delete()

            # 2. Now let's re-create all documents and chunks
            return KnowledgeBaseDocument.objects.bulk_create(documents)

        for obj in serializers.deserialize(
            format, stream_or_string, handle_forward_references=True
        ):
            if isinstance(obj.object, KnowledgeBaseCategory):
                categories.append(obj.object)
            elif isinstance(obj.object, KnowledgeBaseDocument):
                if len(documents) == 0:
                    # If this is the first document, we need to recreate all categories
                    self.load_categories(
                        (cat.name, cat.parent.name if cat.parent else None)
                        for cat in categories
                    )
                documents.append(obj.object)
            elif isinstance(obj.object, KnowledgeBaseChunk):
                if len(chunks) == 0:
                    # If this is the first chunk, we need to recreate all documents
                    # so chunks can reference them with a foreign key
                    documents = _recreate_documents()

                chunks.append(obj.object)
            else:
                continue

        KnowledgeBaseChunk.objects.bulk_create(chunks)

        # 3. Sync the vector store with the newly loaded chunks, so they can be
        # retrieved by the assistant
        self.vector_store.sync_vectors()

        return documents
