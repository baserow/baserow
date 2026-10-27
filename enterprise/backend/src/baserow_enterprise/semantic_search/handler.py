import hashlib
import json
import time
from collections import defaultdict
from typing import TYPE_CHECKING, NamedTuple, Optional

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, QuerySet

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search.registries import search_data_updater_registry
from baserow.contrib.database.table.models import Table
from baserow.core.embeddings import (
    get_embedder,
    vector_search_available,
)
from baserow.core.models import Workspace
from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS
from baserow.core.text_chunking import split_text
from baserow.ws.registries import page_registry
from baserow_enterprise.features import SEMANTIC_SEARCH
from baserow_premium.license.handler import LicenseHandler

from .models import SemanticSearchField, SemanticSearchPendingUpdate
from .registries import SemanticSearchFieldType, semantic_search_field_type_registry
from .vector_table import (
    EXACT_SEARCH_MAX_ROWS,
    MAX_INDEX_CANDIDATES,
    SemanticSearchVectorTable,
)

if TYPE_CHECKING:
    from .search_data_updater_types import SemanticSearchDataUpdaterType

INDEX_BATCH_ROWS = 100
EMBEDDING_BATCH_CHUNKS = 64
MAX_FULL_TEXT_QUERY_TERMS = 64
# The constant of reciprocal rank fusion. It dampens the influence of the top ranks,
# so a row ranked well by both searches beats a row ranked first by only one.
RANK_FUSION_CONSTANT = 60
MAX_FAILED_ATTEMPTS_BEFORE_ERROR = 3
MAX_RETRY_DELAY_SECONDS = 60 * 15
EMBEDDINGS_REQUEST_TIMEOUT_SECONDS = 60


class SemanticSearchMatch(NamedTuple):
    row_id: int
    # The field of which the value matches best.
    field_id: int
    # None if the row isn't indexed yet, and only matches by the words it contains.
    similarity: float | None


class SemanticSearchStatus:
    INDEXING = SemanticSearchField.Status.INDEXING.value
    READY = SemanticSearchField.Status.READY.value
    ERROR = SemanticSearchField.Status.ERROR.value
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"


class SemanticSearchHandler:
    def is_available(self) -> bool:
        """
        :return: Whether this instance supports semantic search.
        """

        return vector_search_available()

    def workspace_has_feature(self, workspace: Workspace) -> bool:
        """
        :param workspace: The workspace that's checked.
        :return: Whether the workspace has the license for semantic search.
        """

        return LicenseHandler.workspace_has_feature(SEMANTIC_SEARCH, workspace)

    def can_index(self, workspace: Workspace) -> bool:
        """
        :param workspace: The workspace of the fields.
        :return: Whether the fields of the workspace can be indexed now.
        """

        return self.is_available() and self.workspace_has_feature(workspace)

    def get_semantic_search_field(self, field: Field) -> Optional[SemanticSearchField]:
        """
        :param field: The field that's checked.
        :return: The semantic search state of the field, or None if semantic search
            is disabled for it.
        """

        # The reverse relation raises an `AttributeError` subclass if it doesn't
        # exist, which some field models intercept with a custom `__getattr__`.
        return getattr(field, "semantic_search", None)

    def get_semantic_search_field_type(
        self, field: Field
    ) -> Optional[SemanticSearchFieldType]:
        """
        :param field: The field that's checked.
        :return: The type that reads the texts of the field, or None if semantic
            search isn't supported for it.
        """

        return semantic_search_field_type_registry.get_for_field(field.specific)

    def get_status(
        self, semantic_search_field: SemanticSearchField, workspace: Workspace
    ) -> str:
        """
        :param semantic_search_field: The semantic search state of the field.
        :param workspace: The workspace of the field.
        :return: One of the `SemanticSearchStatus` values.
        """

        if not self.is_available():
            return SemanticSearchStatus.UNAVAILABLE
        if not self.workspace_has_feature(workspace):
            return SemanticSearchStatus.PAUSED
        return str(semantic_search_field.status)

    def enable(
        self,
        field: Field,
        start_indexing: bool = True,
        copy_vectors_from_field_id: Optional[int] = None,
    ) -> SemanticSearchField:
        """
        Enables semantic search for the field without checking the license and
        availability, so that remembered values are kept.

        :param field: The field of which the values become searchable.
        :param start_indexing: False if the indexing is started later, for example
            because the rows still have to be imported.
        :param copy_vectors_from_field_id: A field with the same rows and values,
            like the original of a duplicate, of which the vectors can be reused.
        :return: The semantic search state of the field.
        """

        semantic_search_field, created = SemanticSearchField.objects.get_or_create(
            field=field
        )
        field.semantic_search = semantic_search_field
        # Snapshots don't belong to a workspace and aren't searchable, they only
        # remember that semantic search was enabled.
        if created and field.table.database.workspace_id is not None:
            self.queue_full_updates(
                field.table,
                [semantic_search_field],
                start_indexing,
                copy_vectors_from_field_id=copy_vectors_from_field_id,
            )
        return semantic_search_field

    def disable(self, field: Field):
        """
        Disables semantic search for the field and marks its vectors for deletion.

        :param field: The field of which the values aren't searchable anymore.
        """

        deleted, _ = SemanticSearchField.objects.filter(field=field).delete()
        field.semantic_search = None
        if deleted:
            self.mark_vectors_for_deletion(field.table, [field.id])

    def disable_incompatible_fields(self, fields: list[Field]):
        """
        Disables semantic search for the fields of which the type no longer supports
        it, like converting a field to a type without an index removes the index.

        :param fields: The fields that may have changed type.
        """

        enabled_field_ids = set(
            SemanticSearchField.objects.filter(field__in=fields).values_list(
                "field_id", flat=True
            )
        )
        for field in fields:
            if (
                field.id in enabled_field_ids
                and self.get_semantic_search_field_type(field) is None
            ):
                self.disable(field)

    def mark_vectors_for_deletion(
        self,
        table: Table,
        field_ids: list[int],
        row_ids: list[int] | None = None,
    ):
        """
        Marks the vectors for deletion when the transaction is committed. They're
        deleted by the periodic check, like the full-text search data.

        :param table: The table of the fields.
        :param field_ids: The fields of which the vectors are deleted.
        :param row_ids: Only the vectors of these rows are deleted, if set.
        """

        workspace_id = table.database.workspace_id
        if workspace_id is None or not field_ids:
            return

        search_data_updater_type = self.get_search_data_updater_type()
        transaction.on_commit(
            lambda: search_data_updater_type.mark_for_deletion(
                workspace_id, field_ids, row_ids
            )
        )

    def get_search_data_updater_type(self) -> "SemanticSearchDataUpdaterType":
        """
        :return: The registered search data updater that keeps the vectors up to date.
        """

        from .search_data_updater_types import SemanticSearchDataUpdaterType

        return search_data_updater_registry.get(SemanticSearchDataUpdaterType.type)

    def queue_full_updates(
        self,
        table: Table,
        semantic_search_fields: list[SemanticSearchField],
        start_indexing: bool = True,
        copy_vectors_from_field_id: Optional[int] = None,
    ):
        """
        Queues an update of all rows of the fields. An update of all rows that's
        already in progress starts over, because rows it already processed may have
        changed.

        :param table: The table of the fields.
        :param semantic_search_fields: The semantic search states of the fields.
        :param start_indexing: False if the indexing is started later, for example
            because the rows still have to be imported.
        :param copy_vectors_from_field_id: A field with the same rows and values of
            which the vectors are copied first.
        """

        values = {"processed_until_row_id": None}
        if copy_vectors_from_field_id:
            values["copy_vectors_from_field_id"] = copy_vectors_from_field_id
        self.get_search_data_updater_type().queue_pending_updates(
            [
                semantic_search_field.field_id
                for semantic_search_field in semantic_search_fields
            ],
            **values,
        )
        self._set_status(
            table,
            [
                semantic_search_field
                for semantic_search_field in semantic_search_fields
                if semantic_search_field.status != SemanticSearchStatus.INDEXING
            ],
            SemanticSearchStatus.INDEXING,
        )
        if start_indexing:
            transaction.on_commit(
                lambda: self.get_search_data_updater_type().schedule(table.id)
            )

    def _set_status(
        self,
        table: Table,
        semantic_search_fields: list[SemanticSearchField],
        status: str,
    ):
        if not semantic_search_fields:
            return

        SemanticSearchField.objects.filter(
            id__in=[field.id for field in semantic_search_fields]
        ).update(status=status)
        for semantic_search_field in semantic_search_fields:
            semantic_search_field.status = status

        # While indexing is paused or unavailable, the fields show that instead of
        # the stored status, like `get_status` returns.
        if not self.can_index(table.database.workspace):
            return

        table_id = table.id
        payloads = [
            {
                "type": "semantic_search_field_status_updated",
                "field_id": semantic_search_field.field_id,
                "semantic_search_status": status,
            }
            for semantic_search_field in semantic_search_fields
        ]
        transaction.on_commit(
            lambda: [
                page_registry.get("table").broadcast(payload, table_id=table_id)
                for payload in payloads
            ]
        )

    def index_table(self, table: Table, deadline: Optional[float] = None) -> bool:
        """
        Processes the pending updates of the table until the deadline.

        :param table: The table of which the pending updates are processed.
        :param deadline: The `time.monotonic()` after which no new batch is started.
        :return: Whether all pending updates were processed.
        :raises EmbeddingsServiceError: If the embeddings service fails. The pending
            updates are then kept, so that they're retried later.
        """

        search_data_updater_type = self.get_search_data_updater_type()
        if not search_data_updater_type.prepare(table):
            return True
        return search_data_updater_type.process_pending_updates(table, deadline)

    def _get_fields_with_pending_updates(self, table: Table):
        return SemanticSearchField.objects.filter(
            field__table=table,
            field_id__in=SemanticSearchPendingUpdate.objects.values("field_id"),
        )

    def mark_indexed(self, table: Table):
        """
        Marks the fields of the table without pending updates as ready.

        :param table: The table that was indexed.
        """

        self._set_status(
            table,
            list(
                SemanticSearchField.objects.filter(field__table=table)
                .exclude(status=SemanticSearchStatus.READY)
                .exclude(
                    field_id__in=SemanticSearchPendingUpdate.objects.values("field_id")
                )
            ),
            SemanticSearchStatus.READY,
        )

    def _get_retry_cache_key(self, table: Table) -> str:
        return f"semantic_search_retry_{table.id}"

    def mark_indexing_failed(self, table: Table) -> int:
        """
        Postpones indexing the table, longer after every consecutive failure, and
        marks its fields with pending updates as failed after too many failures.

        :param table: The table of which the indexing failed.
        :return: The seconds after which indexing the table is retried.
        """

        cache_key = self._get_retry_cache_key(table)
        failed_attempts = (cache.get(cache_key) or {}).get("failed_attempts", 0) + 1
        retry_delay = min(60 * 2 ** (failed_attempts - 1), MAX_RETRY_DELAY_SECONDS)
        cache.set(
            cache_key,
            {
                "failed_attempts": failed_attempts,
                "retry_after": time.time() + retry_delay,
            },
            # Kept a while after the retry, so that a next failure waits longer.
            timeout=retry_delay + MAX_RETRY_DELAY_SECONDS,
        )
        if failed_attempts >= MAX_FAILED_ATTEMPTS_BEFORE_ERROR:
            self._set_status(
                table,
                list(
                    self._get_fields_with_pending_updates(table).exclude(
                        status=SemanticSearchStatus.ERROR
                    )
                ),
                SemanticSearchStatus.ERROR,
            )
        return retry_delay

    def is_retry_postponed(self, table: Table) -> bool:
        """
        :param table: The table that's checked.
        :return: Whether indexing the table must wait until its retry, so that
            changes don't make it try more often while the embeddings service
            fails.
        """

        retry = cache.get(self._get_retry_cache_key(table))
        return retry is not None and time.time() < retry["retry_after"]

    def clear_indexing_failures(self, table: Table):
        """
        :param table: The table that was indexed without failing, so that a next
            failure is retried soon again.
        """

        cache.delete(self._get_retry_cache_key(table))

    def drop_vector_table(self, workspace_id: int):
        """
        :param workspace_id: The workspace of which all vectors are deleted.
        """

        SemanticSearchVectorTable(workspace_id).drop()

    def search(
        self,
        fields: list[Field],
        query: str,
        queryset: QuerySet,
        limit: int,
        min_similarity: float | None = None,
    ) -> list[SemanticSearchMatch]:
        """
        Finds the rows of the queryset matching the query best in any of the fields,
        based on their meaning and on the words they contain.

        :return: The matches ordered by relevance.
        :raises EmbeddingsServiceError: If the query can't be embedded.
        """

        field_ids = [field.id for field in fields]
        vector_table = SemanticSearchVectorTable(fields[0].table.database.workspace_id)
        queryset = queryset.order_by()
        # The embedding model only reads the start of a text, so a longer query only
        # costs more to send.
        query = query[: settings.BASEROW_SEMANTIC_SEARCH_CHUNK_SIZE]
        query_embedding = get_embedder()([query])[0]
        semantic_matches = self._get_semantic_matches(
            vector_table, field_ids, query_embedding, queryset, limit
        )
        full_text_matches = self._get_full_text_matches(fields, query, queryset, limit)

        scores = defaultdict(float)
        for ranked_row_ids in (semantic_matches, full_text_matches):
            for rank, row_id in enumerate(ranked_row_ids):
                scores[row_id] += 1 / (RANK_FUSION_CONSTANT + rank)

        best_chunks = dict(semantic_matches)
        missing_row_ids = [r for r in full_text_matches if r not in best_chunks]
        if missing_row_ids:
            best_chunks.update(
                (row_id, (field_id, similarity))
                for row_id, field_id, similarity in vector_table.get_similarities(
                    field_ids, query_embedding, missing_row_ids, limit
                )
            )
        matches = [
            SemanticSearchMatch(
                row_id,
                # Rows that aren't indexed yet only match by their words.
                *best_chunks.get(row_id, (full_text_matches.get(row_id), None)),
            )
            for row_id in sorted(scores, key=scores.get, reverse=True)
        ]
        if min_similarity is not None:
            matches = [
                match for match in matches if (match.similarity or 0) >= min_similarity
            ]
        return matches[:limit]

    def _get_semantic_matches(
        self,
        vector_table: SemanticSearchVectorTable,
        field_ids: list[int],
        query_embedding: list[float],
        queryset: QuerySet,
        limit: int,
    ) -> dict[int, tuple[int, float]]:
        """
        :return: The `(field_id, similarity)` of the best chunk per row, ordered by
            similarity.
        """

        candidate_row_ids = list(
            queryset.values_list("id", flat=True)[: EXACT_SEARCH_MAX_ROWS + 1]
        )
        if len(candidate_row_ids) <= EXACT_SEARCH_MAX_ROWS:
            return {
                row_id: (field_id, similarity)
                for row_id, field_id, similarity in vector_table.get_similarities(
                    field_ids, query_embedding, candidate_row_ids, limit
                )
            }

        # The vector index doesn't know about the filters and permissions of the
        # queryset, so more chunks are fetched until enough of them are visible.
        # Every field gets its share, so that rows matching in one field aren't
        # pushed out by the chunks of another.
        chunk_limit = min(limit * 4 * len(field_ids), MAX_INDEX_CANDIDATES)
        while True:
            chunks = vector_table.get_nearest_chunks(
                field_ids, query_embedding, chunk_limit
            )
            best_chunks = {}
            for row_id, field_id, similarity in chunks:
                if similarity > best_chunks.get(row_id, (None, -1))[1]:
                    best_chunks[row_id] = (field_id, similarity)
            visible_row_ids = set(
                queryset.filter(id__in=best_chunks).values_list("id", flat=True)
            )
            matches = sorted(
                (
                    (row_id, best_chunk)
                    for row_id, best_chunk in best_chunks.items()
                    if row_id in visible_row_ids
                ),
                key=lambda match: match[1][1],
                reverse=True,
            )
            if (
                len(matches) >= limit
                or len(chunks) < chunk_limit
                or chunk_limit >= MAX_INDEX_CANDIDATES
            ):
                return dict(matches[:limit])
            chunk_limit = min(chunk_limit * 4, MAX_INDEX_CANDIDATES)

    def _get_full_text_matches(
        self, fields: list[Field], query: str, queryset: QuerySet, limit: int
    ) -> dict[int, int]:
        """
        :return: The field matching best per row, ordered by rank.
        """

        table = fields[0].table
        if not SearchHandler.can_use_full_text_search(table):
            return {}

        terms = SearchHandler.escape_query(query).split()[:MAX_FULL_TEXT_QUERY_TERMS]
        if not terms:
            return {}

        # All words must match, so that this finds exact names and terms, while
        # common words in a question don't match unrelated rows.
        search_query = SearchQuery(
            " & ".join(f"$${term}$$" for term in terms),
            search_type="raw",
            config=SearchHandler.search_config(),
        )
        search_model = SearchHandler.get_workspace_search_table_model(
            table.database.workspace_id
        )
        matches = {}
        for row_id, field_id in (
            search_model.objects.filter(
                field_id__in=[field.id for field in fields],
                value=search_query,
                row_id__in=queryset.values("id"),
            )
            .annotate(rank=SearchRank(F("value"), search_query))
            .order_by("-rank")
            .values_list("row_id", "field_id")[: limit * len(fields)]
        ):
            matches.setdefault(row_id, field_id)
        return dict(list(matches.items())[:limit])


class _FieldIndexer:
    def __init__(
        self,
        field: Field,
        semantic_search_field_type: SemanticSearchFieldType,
        model,
        vector_table: SemanticSearchVectorTable,
        deadline: Optional[float],
    ):
        self.field = field
        self.semantic_search_field_type = semantic_search_field_type
        self.model = model
        self.vector_table = vector_table
        self.deadline = deadline
        # Changing how texts are chunked or embedded changes all chunks. The whole
        # URL of the embeddings service is included, because one host can serve
        # several models.
        self.hash_prefix = json.dumps(
            [
                settings.BASEROW_EMBEDDINGS_API_URL,
                DEFAULT_EMBEDDING_DIMENSIONS,
                settings.BASEROW_SEMANTIC_SEARCH_CHUNK_SIZE,
                settings.BASEROW_SEMANTIC_SEARCH_CHUNK_OVERLAP,
                settings.BASEROW_SEMANTIC_SEARCH_MAX_CHUNKS_PER_CELL,
                semantic_search_field_type.get_index_settings(),
            ]
        )

    def deadline_passed(self) -> bool:
        return self.deadline is not None and time.monotonic() > self.deadline

    def index_rows(self, row_ids: list[int]) -> int:
        """
        :param row_ids: The rows of which the values changed, in order.
        :return: The number of rows that were indexed before the deadline.
        :raises EmbeddingsServiceError: If the embeddings service fails.
        """

        values = dict(
            self.semantic_search_field_type.get_values(
                self.field, self.model.objects_and_trash.filter(id__in=row_ids)
            )
        )
        # Rows that no longer exist get a None value, so that their chunks are
        # removed.
        return self._index([(row_id, values.get(row_id)) for row_id in row_ids])

    def index_all_rows(
        self, full_update: SemanticSearchPendingUpdate, check_timestamp
    ) -> bool:
        """
        :param full_update: The pending update of all rows of the field, of which
            the progress is saved.
        :param check_timestamp: If the update was queued again after this moment,
            its progress isn't saved, so that it starts over.
        :return: Whether all rows were indexed before the deadline.
        :raises EmbeddingsServiceError: If the embeddings service fails.
        """

        if full_update.copy_vectors_from_field_id:
            self._copy_vectors(full_update.copy_vectors_from_field_id)
            SemanticSearchPendingUpdate.objects.filter(id=full_update.id).update(
                copy_vectors_from_field_id=None
            )

        processed_until_row_id = full_update.processed_until_row_id or 0
        # Trashed rows are indexed as well, so that they're immediately searchable
        # again when restored.
        queryset = self.model.objects_and_trash.order_by("id")
        while not self.deadline_passed() and (
            values := list(
                self.semantic_search_field_type.get_values(
                    self.field, queryset.filter(id__gt=processed_until_row_id)
                )[:INDEX_BATCH_ROWS]
            )
        ):
            processed = self._index(values)
            if processed:
                processed_until_row_id = values[processed - 1][0]
                # If the update was queued again in the meantime, it must start over.
                SemanticSearchPendingUpdate.objects.filter(
                    id=full_update.id, updated_on__lte=check_timestamp
                ).update(processed_until_row_id=processed_until_row_id)
            if processed < len(values):
                return False

        if self.deadline_passed():
            return False

        self.vector_table.delete_rows_not_in(self.field.id, self.model)
        return True

    def _copy_vectors(self, source_field_id: int):
        source_workspace_id = (
            Field.objects_and_trash.filter(id=source_field_id)
            .values_list("table__database__workspace_id", flat=True)
            .first()
        )
        if source_workspace_id is None:
            return
        self.vector_table.copy_field(
            SemanticSearchVectorTable(source_workspace_id),
            source_field_id,
            self.field.id,
        )

    def _get_content_hash(self, value) -> str | None:
        if not value:
            return None
        content = f"{self.hash_prefix}\n{json.dumps(value, default=str)}"
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()

    def _index(self, values: list[tuple[int, object]]) -> int:
        """
        Indexes the changed values in order until the deadline.

        :param values: The row ids and values of the field, of which the values
            without a stored hash or with a different one are indexed.
        :return: The number of values that were processed. The remaining ones can
            be processed later.
        :raises EmbeddingsServiceError: If the embeddings service fails.
        """

        content_hashes = {
            row_id: self._get_content_hash(value) for row_id, value in values
        }
        stored_content_hashes = self.vector_table.get_content_hashes(
            self.field.id, list(content_hashes)
        )
        batch = _ChunkBatch(self.field.id, self.vector_table)
        for processed, (row_id, value) in enumerate(values):
            if content_hashes[row_id] == stored_content_hashes.get(row_id):
                continue
            if self.deadline_passed():
                batch.save()
                return processed
            texts = self.semantic_search_field_type.get_texts(self.field, value)
            content_hash = content_hashes[row_id]
            if not texts.complete:
                # Doesn't match the value anymore, so that it's read again.
                content_hash = self._get_content_hash([value, "incomplete"])
            batch.add(row_id, content_hash, self._split(texts.texts))
        batch.save()
        return len(values)

    def _split(self, texts: list[str]) -> list[str]:
        chunks = []
        for text in texts:
            for _, _, content in split_text(
                text,
                settings.BASEROW_SEMANTIC_SEARCH_CHUNK_SIZE,
                settings.BASEROW_SEMANTIC_SEARCH_CHUNK_OVERLAP,
            ):
                if len(chunks) >= settings.BASEROW_SEMANTIC_SEARCH_MAX_CHUNKS_PER_CELL:
                    return chunks
                chunks.append(content)
        return chunks


class _ChunkBatch:
    """
    Collects the chunks of changed rows, and embeds and saves them in batches, so
    that the memory and the duration of one embeddings request stay bounded.
    """

    def __init__(self, field_id: int, vector_table: SemanticSearchVectorTable):
        self.field_id = field_id
        self.vector_table = vector_table
        self.row_ids = []
        self.chunks = []

    def add(self, row_id: int, content_hash: str | None, contents: list[str]):
        self.row_ids.append(row_id)
        self.chunks.extend(
            (row_id, chunk_index, content_hash, content)
            for chunk_index, content in enumerate(contents)
        )
        # Otherwise more texts per request wouldn't have any effect.
        if len(self.chunks) >= max(
            EMBEDDING_BATCH_CHUNKS, settings.BASEROW_EMBEDDINGS_TEXTS_PER_REQUEST
        ):
            self.save()

    def save(self):
        if not self.row_ids:
            return
        embeddings = get_embedder(timeout=EMBEDDINGS_REQUEST_TIMEOUT_SECONDS)(
            [content for *_, content in self.chunks]
        )
        with transaction.atomic():
            # Disabling semantic search while the chunks are embedded deletes the
            # vectors of the field. Locking makes it either wait until the chunks
            # are saved, so that they're deleted as well, or happen first, after
            # which they aren't saved.
            if (
                SemanticSearchField.objects.select_for_update(no_key=True)
                .filter(field_id=self.field_id)
                .exists()
            ):
                self.vector_table.replace_chunks(
                    self.field_id,
                    self.row_ids,
                    [
                        self.vector_table.model(
                            field_id=self.field_id,
                            row_id=row_id,
                            chunk_index=chunk_index,
                            content_hash=content_hash,
                            embedding=embedding,
                        )
                        for (row_id, chunk_index, content_hash, _), embedding in zip(
                            self.chunks, embeddings
                        )
                    ],
                )
        self.row_ids = []
        self.chunks = []
