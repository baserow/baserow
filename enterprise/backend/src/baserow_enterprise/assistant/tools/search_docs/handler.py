from typing import IO, Iterable, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core import serializers
from django.db.models import Q

import dspy
from httpx import Client as httpxClient
from pgvector.django import L2Distance

from baserow_enterprise.assistant.models import (
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)


class BaserowEmbedder:
    def __init__(self, api_url: str):
        self.api_url = api_url

    def _embed(self, texts: list[str], batch_size=20) -> list[float]:
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = httpxClient(base_url=self.api_url).post(
                "/embed", json={"texts": batch}
            )

            embeddings.extend(response.json()["embeddings"])

        return embeddings

    def __call__(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if not isinstance(texts, (list, tuple)):
            texts = [texts]

        embeddings = self._embed(texts)

        if len(embeddings) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, but got {len(embeddings)}"
            )

        # Ensure the dimensions are correct
        if len(embeddings[0]) > KnowledgeBaseChunk.EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Expected embeddings of dimension {KnowledgeBaseChunk.EMBEDDING_DIMENSIONS}, "
                "but got {len(embeddings[0])}"
            )
        elif len(embeddings[0]) < KnowledgeBaseChunk.EMBEDDING_DIMENSIONS:
            # Pad the embeddings with zeros if they are smaller than expected
            for i in range(len(embeddings)):
                embeddings[i] = embeddings[i] + [0.0] * (
                    KnowledgeBaseChunk.EMBEDDING_DIMENSIONS - len(embeddings[i])
                )
        return embeddings


class VectorHandler:
    def __init__(self, embedder: dspy.Embedder | None = None):
        self._embedder = embedder

    @property
    def embedder(self) -> dspy.Embedder:
        if self._embedder is None:
            self._embedder = dspy.Embedder(
                BaserowEmbedder(settings.BASEROW_EMBEDDINGS_API_URL)
            )
        return self._embedder

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts.

        :param texts: The list of texts to embed
        :return: A list of vectors corresponding to the input texts
        """

        if not texts:
            return []

        embedder = self.embedder
        # Support both dspy.Embedder (callable) and LangChain-style embedders
        if callable(embedder):
            return embedder(texts)
        else:
            return embedder.embed_documents(texts)

    def embed_knowledge_chunks(
        self, chunks: list[KnowledgeBaseChunk]
    ) -> list[list[float]]:
        """
        Embed a list of document chunks, using their content.

        :param document_chunks: The list of document chunks to embed
        :return: A list of embeddings corresponding to the input document chunks
        """

        return self.embed_texts([chunk.content for chunk in chunks])

    def query(self, query: str, num_results: int = 10) -> list[str]:
        """
        Retrieve the most relevant document chunks for the given query.
        It vectorizes the query and performs a similarity search using the vector field.

        :param query: The text query to search for
        :param num_results: The number of results to return
        :return: A list of document chunk contents matching the query
        """

        (vector_query,) = self.embed_texts([query])
        results = self.raw_query(vector_query, num_results=num_results)
        response = [res.content for res in results]

        return response

    def raw_query(
        self, query_vector: list[float], num_results: int = 10
    ) -> list[KnowledgeBaseChunk]:
        """
        Perform a raw similarity search using the vector field.

        :param query_vector: The vector to search for
        :param num_results: The number of results to return
        :return: A list of KnowledgeBaseChunk instances matching the query
        """

        return (
            KnowledgeBaseChunk.objects.filter(
                source_document__status=KnowledgeBaseDocument.Status.READY,
            )
            .alias(
                distance=L2Distance(KnowledgeBaseChunk.VECTOR_FIELD_NAME, query_vector)
            )
            .order_by("distance")[:num_results]
        )


class KnowledgeBaseHandler:
    def __init__(self, vector_handler: VectorHandler | None = None):
        self.vector_handler = vector_handler or VectorHandler()
        self._try_init_vectors()

    def _try_init_vectors(self):
        """
        Ensures that the vector field is initialized if the pgvector extension is
        available, adding the necessary field to the model so it can be queried and
        used.
        """

        KnowledgeBaseChunk.try_init_vector_field()

    def can_search(self) -> bool:
        """
        Returns whether the knowledge base has any documents with status READY that can
        be searched.

        :return: True if the pgvector extension is enabled, the embedding field exists
            and there is at least one READY document, False otherwise.
        """

        return (
            settings.BASEROW_EMBEDDINGS_API_URL != ""
            and KnowledgeBaseChunk.can_search_vectors()
            and KnowledgeBaseDocument.objects.filter(
                status=KnowledgeBaseDocument.Status.READY
            ).exists()
        )

    def search(self, query: str, num_results=10) -> list[str]:
        """
        Retrieve the most relevant knowledge chunks for the given query.

        :param query: The text query to search for
        :param num_results: The number of results to return
        :return: A list of document chunk contents matching the query
        """

        return self.vector_handler.query(query, num_results=num_results)

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
        buffer_or_filename: IO[str] | str,
        document_filters: Q | None = None,
    ) -> int:
        """
        Dump the knowledge base into a zip file, containing the serialized
        representation of the categories, documents and chunks.

        :param buffer_or_filename: The stream or filename where to write the dump.
        :param document_filters: Optional filters to apply to the dumped documents.
        :return: The number of dumped documents.
        """

        if document_filters is None:
            document_filters = Q()

        documents = KnowledgeBaseDocument.objects.filter(
            document_filters
        ).select_related("category")

        categories = KnowledgeBaseCategory.objects.filter(
            id__in=[doc.category_id for doc in documents]
        ).select_related("parent__parent__parent__parent")

        chunks = KnowledgeBaseChunk.objects.filter(
            source_document__in=documents
        ).select_related("source_document")

        def _serialize(items, fields=None, format_type="jsonl"):
            return serializers.serialize(
                format_type,
                list(items),
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True,
                fields=fields,
            )

        # Avoid serializing the vector field, as it's a copy of the _embedding_array
        # field and can cause issues if the pgvector extension is not available at
        # import time.
        chunk_fields = [
            f.name
            for f in KnowledgeBaseChunk._meta.fields
            if f.name not in (KnowledgeBaseChunk.VECTOR_FIELD_NAME, "id")
        ]

        with ZipFile(
            buffer_or_filename, mode="w", compression=ZIP_DEFLATED, allowZip64=True
        ) as zip_file:
            zip_file.writestr("categories.jsonl", _serialize(categories))
            zip_file.writestr("documents.jsonl", _serialize(documents))
            zip_file.writestr("chunks.jsonl", _serialize(chunks, fields=chunk_fields))

        return len(documents)

    def load_knowledge_base(
        self,
        buffer_or_filename: IO[str] | str,
    ) -> list[KnowledgeBaseDocument]:
        """
        Load a knowledge base from a serialized representation, previously exported with
        `dump_knowledge_base`. The existing documents with the same slug will be
        replaced, together with their chunks. The categories will be created if they
        don't exist yet. Once the knowledge base is loaded, the vector store index will
        be synced.

        :param buffer_or_filename: The stream or string containing the serialized
            knowledge base data.
        :return: The list of loaded KnowledgeBaseDocument instances
        """

        def _deserialize(
            stream: IO[str] | str, format_type="jsonl"
        ) -> Iterable[serializers.base.DeserializedObject]:
            return serializers.deserialize(
                format_type, stream, handle_forward_references=True
            )

        categories = []
        documents = []
        chunks = []

        with ZipFile(buffer_or_filename, mode="r", allowZip64=True) as zip_file:
            categories_data = zip_file.read("categories.jsonl").decode("utf-8")
            for obj in _deserialize(categories_data):
                categories.append(obj.object)

            self.load_categories(
                (cat.name, cat.parent.name if cat.parent else None)
                for cat in categories
            )

            documents_data = zip_file.read("documents.jsonl").decode("utf-8")
            for obj in _deserialize(documents_data):
                documents.append(obj.object)

            # Delete existing documents with the same slug to avoid conflicts
            # This also cascades and deletes their chunks
            KnowledgeBaseDocument.objects.filter(
                slug__in=[doc.slug for doc in documents]
            ).delete()

            KnowledgeBaseDocument.objects.bulk_create(documents)

            chunks_data = zip_file.read("chunks.jsonl").decode("utf-8")
            for obj in _deserialize(chunks_data):
                chunks.append(obj.object)

            if KnowledgeBaseChunk.can_search_vectors():
                # If the vector field is available, set it from the _embedding_array
                # field to ensure data consistency
                for chunk in chunks:
                    chunk.embedding = chunk._embedding_array

            KnowledgeBaseChunk.objects.bulk_create(chunks)

        return documents
