import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Tuple

from django.conf import settings
from django.db import transaction

from httpx import Client as httpxClient
from loguru import logger
from pgvector.django import L2Distance

from baserow_enterprise.assistant.models import (
    DEFAULT_CATEGORIES,
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
    def __init__(self, embedder=None):
        self._embedder = embedder

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = BaserowEmbedder(settings.BASEROW_EMBEDDINGS_API_URL)
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
        # Support both embedders as callables and LangChain-style embedders
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

    def query(self, query: str, num_results: int = 10) -> list[KnowledgeBaseChunk]:
        """
        Retrieve the most relevant document chunks for the given query.
        It vectorizes the query and performs a similarity search using the vector field.

        :param query: The text query to search for
        :param num_results: The number of results to return
        :return: A list of KnowledgeBaseChunk instances matching the query
        """

        (vector_query,) = self.embed_texts([query])
        return self.raw_query(vector_query, num_results=num_results)

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
            .select_related("source_document")
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

    def can_have_knowledge_base(self):
        """
        Indicates whether it's possible for the knowledge base to be populated. In
        order to do that, we need a valid embeddings server and PostgreSQL server must
        support vectors.

        :return: True if there is an embeddings server and pgvector extension is
            enabled.
        """

        return (
            settings.BASEROW_EMBEDDINGS_API_URL != ""
            and KnowledgeBaseChunk.can_search_vectors()
        )

    def can_search(self) -> bool:
        """
        Returns whether the knowledge base has any documents with status READY that can
        be searched.

        :return: True if the pgvector extension is enabled, the embedding field exists
            and there is at least one READY document, False otherwise.
        """

        return (
            self.can_have_knowledge_base()
            and KnowledgeBaseDocument.objects.filter(
                status=KnowledgeBaseDocument.Status.READY
            ).exists()
        )

    def search(self, query: str, num_results=10) -> list[KnowledgeBaseChunk]:
        """
        Retrieve the most relevant knowledge chunks for the given query.

        :param query: The text query to search for
        :param num_results: The number of results to return
        :return: A list of KnowledgeBaseChunk instances matching the query
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

    def sync_knowledge_base_from_csv(self):
        """
        Sync entries from `website_export.csv` with the knowledgebase documents and
        chunks. The idea is that this `website_export.csv` file can easily be
        exported from the production version of saas.

        It automatically checks if the entry already exists, and will create,
        update or delete accordingly. This will make sure that if a FAQ question is
        removed from the source, it will also be removed in the documents.
        """

        csv_path = self._csv_path()
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = [dict(r) for r in reader]

        if not rows:
            return

        pages = {}  # (doc_type, slug) -> page dict
        slugs_by_type = defaultdict(set)
        cat_names = set()
        faq_type = KnowledgeBaseDocument.DocumentType.FAQ

        for row in rows:
            row_id = row.get("id") or ""
            base_slug = row.get("slug") or ""
            title = row.get("title") or row.get("name") or ""
            body = row.get("markdown_body") or ""
            category = row.get("category") or ""
            source_url = row.get("source_url") or ""
            doc_type = self._csv_type_to_enum(row.get("type"))

            if not (doc_type and base_slug and title):
                continue

            if doc_type == faq_type:
                slug = f"{base_slug}-{row_id}"
            else:
                slug = base_slug

            key = (doc_type, slug)
            pages[key] = {
                "title": title,
                "body": body,
                "category": category,
                "source_url": source_url,
                "type": doc_type,
            }

            slugs_by_type[doc_type].add(slug)
            if category:
                cat_names.add(category)

        if not pages:
            return

        categories = {
            c.name: c for c in KnowledgeBaseCategory.objects.filter(name__in=cat_names)
        }

        with transaction.atomic():
            types_in_csv = list(slugs_by_type.keys())
            existing = {
                (d.type, d.slug): d
                for d in KnowledgeBaseDocument.objects.filter(type__in=types_in_csv)
            }

            # Deletes the user docs that exist in the KnowledgeBaseDocument,
            # but do not exist in the CSV file anymore. This covers the scenario
            # where a page is deleted.
            for t in types_in_csv:
                csv_slugs = slugs_by_type[t]
                to_delete = [
                    k for k in existing.keys() if k[0] == t and k[1] not in csv_slugs
                ]
                if to_delete:
                    KnowledgeBaseDocument.objects.filter(
                        type=t, slug__in=[s for (_, s) in to_delete]
                    ).delete()
                    for k in to_delete:
                        existing.pop(k, None)

            create, update = [], []
            doc_ids_needing_chunks: set[int] = set()

            for key, p in pages.items():
                category = categories.get(p["category"]) if p["category"] else None
                d = existing.get(key)
                if d:
                    changed = False
                    body_changed = False
                    if d.title != p["title"]:
                        d.title = p["title"]
                        changed = True
                    if d.raw_content != p["body"]:
                        d.raw_content = p["body"]
                        changed = True
                        body_changed = True
                    if d.content != p["body"]:
                        d.content = p["body"]
                        changed = True
                        body_changed = True
                    if d.category_id != (category.id if category else None):
                        d.category = category
                        changed = True
                    if d.process_document:
                        d.process_document = False
                        changed = True
                    if d.status != KnowledgeBaseDocument.Status.READY:
                        d.status = KnowledgeBaseDocument.Status.READY
                        changed = True
                    if d.source_url != p["source_url"]:
                        d.source_url = p["source_url"]
                        changed = True

                    if changed:
                        update.append(d)
                    if body_changed:
                        doc_ids_needing_chunks.add(d.id)
                else:
                    new_doc = KnowledgeBaseDocument(
                        title=p["title"],
                        slug=key[1],
                        type=key[0],
                        raw_content=p["body"],
                        process_document=False,
                        content=p["body"],
                        status=KnowledgeBaseDocument.Status.READY,
                        category=category,
                        source_url=p["source_url"],
                    )
                    create.append(new_doc)

            if create:
                KnowledgeBaseDocument.objects.bulk_create(create)
                fresh = KnowledgeBaseDocument.objects.filter(
                    type__in=types_in_csv, slug__in=[d.slug for d in create]
                )
                for d in fresh:
                    existing[(d.type, d.slug)] = d
                    doc_ids_needing_chunks.add(d.id)

            if update:
                # The `updated_on` field is not saved during the bulk update, so we
                # would need to pre_save this value before.
                for d in update:
                    d.updated_on = KnowledgeBaseDocument._meta.get_field(
                        "updated_on"
                    ).pre_save(d, add=False)

                KnowledgeBaseDocument.objects.bulk_update(
                    update,
                    [
                        "title",
                        "raw_content",
                        "process_document",
                        "content",
                        "status",
                        "category",
                        "source_url",
                        "updated_on",
                    ],
                )

            # If there are no chunks to rebuild, we can skip the final part because
            # there is no need to delete and recreate the missing chunks.
            if not doc_ids_needing_chunks:
                return

            KnowledgeBaseChunk.objects.filter(
                source_document_id__in=list(doc_ids_needing_chunks)
            ).delete()

            chunks, texts = [], []
            for (t, s), d in existing.items():
                if d.id not in doc_ids_needing_chunks:
                    continue
                body = pages[(t, s)]["body"]
                chunks.append(
                    KnowledgeBaseChunk(
                        source_document=d, index=0, content=body, metadata={}
                    )
                )
                texts.append(body)

            if not chunks:
                return

            self._update_chunks(texts, chunks)

    def sync_knowledge_base_from_dev_docs(self):
        """
        Sync the developer documentation from the local `docs/` folder with the
        knowledgebase documents and chunks. Every .md file will be included. It will
        automatically figure out a title, slug, etc. It automatically checks if the
        entry already exists, and will create, update or delete accordingly.
        """

        docs_root = self._get_docs_path()
        if docs_root is None:
            logger.warning(
                f"The {docs_root} folder does not exist, skip synchronizing the dev "
                f"docs"
            )
            return

        doc_type = KnowledgeBaseDocument.DocumentType.BASEROW_DEV_DOCS

        pages: dict[str, dict] = {}
        slugs: set[str] = set()

        for md_path in docs_root.rglob("*.md"):
            rel = md_path.relative_to(docs_root)
            rel_str = rel.as_posix()
            if not rel_str.lower().endswith(".md"):
                continue

            rel_without_md = rel_str[:-3]
            slug = f"dev/{rel_without_md}"
            slugs.add(slug)

            stem = md_path.stem  # e.g. "ci-cd"
            stem_normalized = stem.replace("_", "-")
            parts = [p for p in stem_normalized.split("-") if p]
            title = (
                " ".join(p[:1].upper() + p[1:].lower() for p in parts)
                if parts
                else stem[:1].upper() + stem[1:].lower()
            )

            with md_path.open("r", encoding="utf-8") as f:
                body = f.read()

            source_url = f"https://baserow.io/docs/{rel_without_md}"

            pages[slug] = {
                "title": title,
                "body": body,
                "source_url": source_url,
            }

        dev_docs_category = KnowledgeBaseCategory.objects.filter(
            name="dev_docs"
        ).first()

        with transaction.atomic():
            existing = {
                d.slug: d for d in KnowledgeBaseDocument.objects.filter(type=doc_type)
            }

            # Delete docs that no longer have a corresponding markdown file. This is
            # needed because a file could be removed because it's no longer relevant.
            # It should then not show up in the docs anymore.
            to_delete_slugs = [s for s in existing.keys() if s not in slugs]
            if to_delete_slugs:
                KnowledgeBaseDocument.objects.filter(
                    type=doc_type, slug__in=to_delete_slugs
                ).delete()
                for s in to_delete_slugs:
                    existing.pop(s, None)

            create, update = [], []
            doc_ids_needing_chunks: set[int] = set()

            for slug, p in pages.items():
                d = existing.get(slug)
                if d:
                    changed = False
                    body_changed = False
                    if d.title != p["title"]:
                        d.title = p["title"]
                        changed = True
                    if d.raw_content != p["body"]:
                        d.raw_content = p["body"]
                        changed = True
                        body_changed = True
                    if d.content != p["body"]:
                        d.content = p["body"]
                        changed = True
                        body_changed = True
                    if dev_docs_category and d.category_id != dev_docs_category.id:
                        d.category = dev_docs_category
                        changed = True
                    if d.process_document:
                        d.process_document = False
                        changed = True
                    if d.status != KnowledgeBaseDocument.Status.READY:
                        d.status = KnowledgeBaseDocument.Status.READY
                        changed = True
                    if d.source_url != p["source_url"]:
                        d.source_url = p["source_url"]
                        changed = True

                    if changed:
                        update.append(d)
                    if body_changed:
                        doc_ids_needing_chunks.add(d.id)
                else:
                    new_doc = KnowledgeBaseDocument(
                        title=p["title"],
                        slug=slug,
                        type=doc_type,
                        raw_content=p["body"],
                        process_document=False,
                        content=p["body"],
                        status=KnowledgeBaseDocument.Status.READY,
                        category=dev_docs_category,
                        source_url=p["source_url"],
                    )
                    create.append(new_doc)

            if create:
                KnowledgeBaseDocument.objects.bulk_create(create)
                fresh = KnowledgeBaseDocument.objects.filter(
                    type=doc_type, slug__in=[d.slug for d in create]
                )
                for d in fresh:
                    existing[d.slug] = d
                    doc_ids_needing_chunks.add(d.id)

            if update:
                # The `updated_on` field is not saved during the bulk update, so we
                # would need to pre_save this value before.
                for d in update:
                    d.updated_on = KnowledgeBaseDocument._meta.get_field(
                        "updated_on"
                    ).pre_save(d, add=False)

                KnowledgeBaseDocument.objects.bulk_update(
                    update,
                    [
                        "title",
                        "raw_content",
                        "process_document",
                        "content",
                        "status",
                        "category",
                        "source_url",
                        "updated_on",
                    ],
                )

            # If there are no chunks to rebuild, we can skip the final part because
            # there is no need to delete and recreate the missing chunks.
            if not doc_ids_needing_chunks:
                return

            KnowledgeBaseChunk.objects.filter(
                source_document_id__in=list(doc_ids_needing_chunks)
            ).delete()

            chunks, texts = [], []
            for slug, d in existing.items():
                if d.id not in doc_ids_needing_chunks:
                    continue
                body = pages[slug]["body"]
                chunks.append(
                    KnowledgeBaseChunk(
                        source_document=d, index=0, content=body, metadata={}
                    )
                )
                texts.append(body)

            if not chunks:
                return

            self._update_chunks(texts, chunks)

    def _csv_path(self):
        path = Path(__file__).resolve().parents[5] / "website_export.csv"

        if not path.exists():
            raise FileNotFoundError(f"CSV not found at: {path}")

        return path

    def _get_docs_path(self) -> Path | None:
        """
        Returns the path to the `docs` directory if it exists, otherwise None.
        The folder is expected at `../../../../../../../docs` from this handler file.
        """

        path = Path(__file__).resolve().parents[7] / "docs"
        if not path.exists() or not path.is_dir():
            return None
        return path

    def _csv_type_to_enum(self, csv_value: str | None) -> str:
        v = (csv_value or "").strip()
        if not v:
            return KnowledgeBaseDocument.DocumentType.RAW_DOCUMENT
        for dt in KnowledgeBaseDocument.DocumentType:
            if v.lower() == dt.value.lower():
                return dt.value
        return KnowledgeBaseDocument.DocumentType.RAW_DOCUMENT

    def _update_chunks(self, texts, chunks):
        embeddings = self.vector_handler.embed_texts(texts)
        if KnowledgeBaseChunk.can_search_vectors():
            for c, e in zip(chunks, embeddings):
                c.embedding = list(e)
                c._embedding_array = list(e)
        else:
            for c, e in zip(chunks, embeddings):
                c._embedding_array = list(e)

        KnowledgeBaseChunk.objects.bulk_create(chunks)

    def sync_knowledge_base(self):
        # Ensure default categories exist (parents set by load_categories)
        self.load_categories(DEFAULT_CATEGORIES)

        self.sync_knowledge_base_from_csv()
        self.sync_knowledge_base_from_dev_docs()
