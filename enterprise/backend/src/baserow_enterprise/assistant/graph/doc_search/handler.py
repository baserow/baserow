from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import re
import time
from typing import Any, TypedDict
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain_core.documents.base import Document
import numpy as np
import requests
from html2text import HTML2Text
from bs4 import BeautifulSoup
from loguru import logger
from django_redis import get_redis_connection
from django.db import transaction
from django.db.models import QuerySet, Q
from baserow_enterprise.assistant.models import (
    KnowledgeBaseDocument,
    KnowledgeBaseDocumentCategory,
    KnowledgeBaseDocumentChunk,
)
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery, filter
from redisvl.utils.vectorize import OpenAITextVectorizer, base
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.chat_models import init_chat_model

from .prompts import (
    PREPROCESS_DOCUMENT_PROMPT,
)


OFFICIAL_KNOWLEDGE_BASE_URL = "https://baserow.io/user-docs"
VECTOR_STORE_INDEX_NAME = "assistant_knowledge_base"

VECTORIZER_MODEL = "text-embedding-3-large"
VECTORIZER_DIMENSIONS = 3072


def html_to_markdown(page_content: str) -> str:
    """
    Convert the HTML content of a page to markdown.

    :param page_content: The HTML content of the page.
    :return: The markdown content of the page.
    :raises ValueError: If no page content is provided.
    """

    if not page_content:
        raise ValueError("No page content provided")

    h2t = HTML2Text()
    h2t.ignore_links = False
    h2t.ignore_images = True
    h2t.body_width = 0  # Prevents wrapping
    markdown = h2t.handle(page_content)
    # Remove excessive blank lines
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown


def fetch_official_knowledge_base_page_content(
    page_url: str, content_selector=".docs__content"
) -> str | None:
    """
    Fetch the content of a page given its URL and a CSS selector. If the selector does
    not match any elements, None is returned.

    :param page_url: The URL of the page to fetch.
    :return: The content of the page as a string or None if not found.
    :raises re
    """

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    response_text = None
    for _ in range(3):
        try:
            response = requests.get(page_url, headers=headers, timeout=10)
            if response.status_code == 200:
                response_text = response.text
                break
            else:
                logger.debug(
                    f"Failed to fetch page {page_url}, status code: {response.status_code}. "
                )
        except requests.RequestException as e:
            logger.debug(f"Error fetching page {page_url}: {e}")

        time.sleep(1)

    if response_text is None:
        raise ValueError(f"Failed to fetch page {page_url}")

    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.select_one(content_selector)
    return str(content) if content else None


@dataclass
class Page:
    title: str
    url: str
    content: str


@dataclass
class TocCategory:
    name: str
    description: str
    links: list[tuple[str, str]]  # (link name, URL)
    pages: list[Page] | None = None


MARKDOWN_HEADERS_TO_SPLIT_ON = [
    ("#", "title"),
    ("##", "category"),
]

# Map knowledge base categories to one of DEFAULT_CATEGORIES
KNOWLEDGE_BASE_CATEGORY_MAP = {
    "Enterprise license": "enterprise",
    "Databases": "database",
    "Application Builder": "application builder",
    "Application Builder Editor": "application builder",
    "Account management": "account management",
    "Formula": "database formula",
    "Rows overview": "row",
    "Integrations and automation": "integrations",
    "Working with views": "view",
    "Permissions overview": "roles and permissions",
    "Baserow billing": "billing",
    "Collaboration": "collaboration",
    "Getting started": "getting started",
    "Tables": "table",
    "Enterprise SSO": "sso",
    "Workspaces": "workspace",
    "Application Builder Elements": "element",
    "Organise data with fields": "field",
}


def _parse_toc_category(category: Document) -> TocCategory:
    """
    Extract the category description and all markdown links from the given content.

    :param content: The content to extract links from.
    :return: A list of tuples containing the link text and URL.
    """

    links_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
    page_content = category.page_content.strip()
    links = re.findall(links_pattern, page_content)

    # Use the text up to the first link as description
    if links:
        # Make sure all links are absolute, if they're not, make them absolute
        links = [
            (text, requests.compat.urljoin(OFFICIAL_KNOWLEDGE_BASE_URL, url))
            for text, url in links
        ]
        description = page_content.split(links[0][0])[0].strip()
    else:
        description = page_content

    return TocCategory(
        name=category.metadata["category"], description=description, links=links
    )


def _prepare_chunk_content(
    title: str, url: str, section: str, content: str, category_name: str | None = None
) -> str:
    content = f"""
# {title}

## {section}

{content}
----
Source: {url}
    """
    if category_name:
        content = f"""
{category_name}
------
{content}
"""
    return content


class OnlineUserDocsHandler:
    def update_documents(self, document_ids: list[int], max_workers: int = 10) -> None:
        """
        Update the pages with the given IDs in parallel.

        :param document_ids: The IDs of the documents to update.
        :param max_workers: Maximum number of parallel threads to use.
        """

        documents = KnowledgeBaseDocument.objects.filter(id__in=document_ids).all()
        if not documents:
            return

        docs_to_update = []
        
        # Fetch all pages in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all fetch tasks
            future_to_document = {}
            for document in documents:
                if document.source_url:
                    future = executor.submit(
                        self._fetch_and_compare_document, document
                    )
                    future_to_document[future] = document

            # Collect results as they complete
            for future in as_completed(future_to_document):
                document = future_to_document[future]
                try:
                    updated_document = future.result()
                    if updated_document:
                        docs_to_update.append(updated_document)
                except Exception as e:
                    logger.error(
                        f"Failed to update document {document.title} ({document.source_url}): {e}"
                    )

        # Bulk update all changed documents
        if docs_to_update:
            KnowledgeBaseDocument.objects.bulk_update(
                docs_to_update, ["raw_content", "status", "content", "updated_on"]
            )
            IngestionService().ingest_pending_documents(docs_to_update)

    def _fetch_and_compare_document(self, document: KnowledgeBaseDocument) -> KnowledgeBaseDocument | None:
        """
        Fetch and compare a single document's content.

        :param document: The document to fetch and compare
        :return: The document if it was updated, None if no update was needed
        """
        try:
            page_content = fetch_official_knowledge_base_page_content(
                document.source_url
            )
            if page_content:
                markdown = html_to_markdown(page_content)
                if markdown == document.raw_content:
                    logger.debug(
                        f"Document {document.title}({document.source_url}) is up to date"
                    )
                    return None

                # Mark document for update
                document.raw_content = markdown
                document.status = KnowledgeBaseDocument.Status.STALE_CONTENT
                document.content = ""
                return document
        except Exception as e:
            logger.error(
                f"Failed to fetch content for document {document.title} ({document.source_url}): {e}"
            )
            return None

    def _fetch_toc_category_pages(self, category: Document) -> TocCategory:
        """
        Fetch all pages for a single category.

        :param category: The category Document to process
        :return: TocCategory with all pages fetched
        """
        toc_category = _parse_toc_category(category)

        # Fetch all pages for this category in parallel
        if toc_category.links:
            with ThreadPoolExecutor(max_workers=5) as page_executor:
                future_to_link = {}
                for link_name, link_url in toc_category.links:
                    future = page_executor.submit(
                        self._fetch_single_page, link_name, link_url
                    )
                    future_to_link[future] = (link_name, link_url)

                for future in as_completed(future_to_link):
                    link_name, link_url = future_to_link[future]
                    try:
                        page = future.result()
                        if page:
                            if toc_category.pages is None:
                                toc_category.pages = []
                            toc_category.pages.append(page)
                    except Exception as e:
                        logger.debug(
                            f"ERROR: Failed to fetch page {link_name}({link_url}): {e}"
                        )

        return toc_category

    def _fetch_single_page(self, link_name: str, link_url: str) -> Page | None:
        """
        Fetch a single page and convert it to Page object.

        :param link_name: The name of the link
        :param link_url: The URL to fetch
        :return: Page object or None if fetch failed
        """
        try:
            page_content = fetch_official_knowledge_base_page_content(link_url)
            logger.debug(f"Page {link_name}({link_url}) fetched successfully")

            if page_content:
                content = html_to_markdown(page_content)
                return Page(
                    title=link_name,
                    url=link_url,
                    content=content,
                )
        except ValueError:
            logger.debug(f"ERROR: Failed to fetch page {link_name}({link_url})")

        return None

    def fetch_official_knowledge_base(
        self, parallel_threads: int = 20
    ) -> list[TocCategory]:
        """
        Fetch the official knowledge base for the given query.

        It reads the table of contents and returns all the relevant pages.

        :param parallel_threads: The number of parallel threads to use
        :return: A list of TocCategory objects, containing the content for each category
            and each page listed
        """

        # First get the table of contents with all the categories and all the links to
        # the relevant pages
        toc_url = f"{OFFICIAL_KNOWLEDGE_BASE_URL}"
        toc_content = html_to_markdown(
            fetch_official_knowledge_base_page_content(toc_url)
        )

        category_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=MARKDOWN_HEADERS_TO_SPLIT_ON
        )
        categories = category_splitter.split_text(toc_content)
        # Exclude the first one as it's the title
        categories = categories[1:]

        # Process all categories in parallel
        toc_categories = [
            TocCategory(
                name="Getting started",
                description="",
                links=[],
                pages=[
                    Page(
                        title="Table of contents",
                        url=toc_url,
                        content=toc_content,
                    )
                ],
            )
        ]
        with ThreadPoolExecutor(max_workers=parallel_threads) as executor:
            # Submit all category processing tasks
            future_to_category = {
                executor.submit(self._fetch_toc_category_pages, category): category
                for category in categories
            }

            # Collect results as they complete
            for future in as_completed(future_to_category):
                try:
                    toc_category = future.result()
                    toc_categories.append(toc_category)
                except Exception as e:
                    logger.error(f"Failed to process category: {e}")

        return toc_categories

    def _update_official_knowledge_base(
        self, toc_categories: list[TocCategory]
    ) -> list[KnowledgeBaseDocument]:
        """
        Update the official knowledge base with the given table of contents categories.

        :param toc_categories: The table of contents categories to update
        :return: A list of updated KnowledgeBaseDocument objects that need to be synced
            with the VectorStore because they are either new or have been modified.
        """

        # Create the missing categories
        existing_documents_by_url = {
            doc.source_url: doc
            for doc in KnowledgeBaseDocument.objects.filter(
                type=KnowledgeBaseDocument.DocumentType.BASEROW_USER_DOCS
            ).all()
        }
        existing_categories_by_name = {
            category.name: category
            for category in KnowledgeBaseDocumentCategory.objects.all()
        }
        analyzed_urls = set()

        docs_to_create = []
        docs_to_update = []
        for toc_category in toc_categories:
            # Set the KnowledgeBaseDocumentCategory we want to for all the pages
            category_name = KNOWLEDGE_BASE_CATEGORY_MAP.get(toc_category.name)
            category = (
                existing_categories_by_name.get(category_name)
                if category_name
                else None
            )
            if category is None:
                logger.debug(f"Unknown category {toc_category.name} found")

            for page in toc_category.pages or []:
                existing_doc = existing_documents_by_url.get(page.url)

                if existing_doc is None:  # create it
                    doc = KnowledgeBaseDocument(
                        title=page.title,
                        source_url=page.url,
                        type=KnowledgeBaseDocument.DocumentType.BASEROW_USER_DOCS,
                        raw_content=page.content,
                        status=KnowledgeBaseDocument.Status.NEW,
                        category=category,
                        process_document=False,
                    )
                    docs_to_create.append(doc)
                elif existing_doc.raw_content != page.content:  # update it
                    doc = existing_doc
                    doc.title = page.title
                    doc.status = KnowledgeBaseDocument.Status.STALE_CONTENT
                    doc.raw_content = page.content
                    doc.content = ""
                    docs_to_update.append(doc)
                else:  # nothing to do
                    logger.debug(f"Document {page.title}({page.url}) is up to date")
                analyzed_urls.add(page.url)

        created_docs = []
        if docs_to_create:
            created_docs = KnowledgeBaseDocument.objects.bulk_create(docs_to_create)

        updated_docs = []
        if docs_to_update:
            KnowledgeBaseDocument.objects.bulk_update(
                docs_to_update,
                ["title", "status", "raw_content", "content", "updated_on"],
            )
            updated_docs = docs_to_update

        existing_url_not_analyzed = (
            set(existing_documents_by_url.keys()) - analyzed_urls
        )
        if existing_url_not_analyzed:
            logger.info(f"Existing URLs not analyzed: {existing_url_not_analyzed}")

        return created_docs + updated_docs

    def ingest(self, documents: list[KnowledgeBaseDocument]):
        # Ingest all the new and updated documents:
        # 1. Split document in chunks
        # 2. Vectorize chunks
        # 3. Sync ready chunks in the vector store

        # Pick all new or stale content documents

        ingestion_service = IngestionService()
        ingestion_service.sync_chunks_to_vector_store()

    def _get_documents_to_ingest(self) -> QuerySet[KnowledgeBaseDocument]:
        return KnowledgeBaseDocument.objects.filter(
            type=KnowledgeBaseDocument.DocumentType.BASEROW_USER_DOCS,
            status__in=[
                KnowledgeBaseDocument.Status.NEW,
                KnowledgeBaseDocument.Status.STALE_CONTENT,
            ],
        ).select_related("category__parent__parent__parent")

    def update_official_knowledge_base(self) -> None:
        """
        Update the official knowledge base with the given table of contents categories.

        :param toc_categories: The list of TocCategory objects to update
        """

        # Fetch the latest content
        toc_categories = self.fetch_official_knowledge_base()
        changed_documents = self._update_official_knowledge_base(toc_categories)
        IngestionService().ingest_pending_documents(changed_documents)


VECTOR_FIELD_NAME = "embedding"
DOCUMENT_CHUNK_ID_FIELD_NAME = "document_chunk_id"
CONTENT_FIELD_NAME = "content"


class Vector(TypedDict):
    title: str
    content: str
    section: str
    document_chunk_id: int
    category: str
    embedding: list[float]
    url: str

    @staticmethod
    def to_redis_schema() -> list[dict[str, Any]]:
        return [
            {"name": "title", "type": "text"},
            {"name": "url", "type": "text"},
            {"name": CONTENT_FIELD_NAME, "type": "text"},
            {"name": "section", "type": "text"},
            {"name": DOCUMENT_CHUNK_ID_FIELD_NAME, "type": "numeric"},
            {"name": "category", "type": "tag"},
            {
                "name": VECTOR_FIELD_NAME,
                "type": "vector",
                "attrs": {
                    "dims": VECTORIZER_DIMENSIONS,
                    "distance_metric": "cosine",
                    "algorithm": "flat",
                    "datatype": "float32",
                },
            },
        ]


INDEX_SCHEMA = {
    "index": {
        "name": VECTOR_STORE_INDEX_NAME,
        "prefix": "aikb",
    },
    "fields": Vector.to_redis_schema(),
}


def _document_chunk_to_vector(document_chunk: KnowledgeBaseDocumentChunk) -> Vector:
    source_doc = document_chunk.source_document
    # Ensure embedding is a list of floats
    embedding_list = np.array(
        list(document_chunk.embedding) if document_chunk.embedding else [],
        dtype=np.float32,
    ).tobytes()
    return Vector(
        title=source_doc.title,
        section=document_chunk.metadata.get("section", ""),
        category=source_doc.category.full_path if source_doc.category else "",
        url=source_doc.source_url or "",
        content=document_chunk.content,
        embedding=embedding_list,
        document_chunk_id=document_chunk.id,
    )


class RedisVectorStore:
    def __init__(self, vectorizer: base.BaseVectorizer | None = None):
        self.redis_client = get_redis_connection("default")
        self._vectorizer = vectorizer
        index, _ = self.create_index(overwrite=False)
        self.index = index

    def create_index(
        self, index_schema=None, overwrite=False
    ) -> tuple[SearchIndex:, bool]:
        """
        Create a search index with the specified schema. If index_schema is None, the
        default index schema will be used. If overwrite is True, the index will be
        dropped and re-created.

        :param index_schema: The schema to use for the index
        :param overwrite: Whether to drop and re-create the index, in case it already
            exists
        :return: The created search index and a boolean indicating whether it was
            created or it was already existing
        """

        if index_schema is None:
            index_schema = INDEX_SCHEMA

        index = SearchIndex.from_dict(
            index_schema,
            redis_client=self.redis_client,
            validate_on_load=True,
        )
        if not overwrite and index.exists():
            created = False
        else:
            index.create(overwrite=overwrite, drop=overwrite)
            created = True

        return index, created

    def load_data(
        self, vectors: list[Vector], index: SearchIndex | None = None
    ) -> list[str]:
        """
        Load data into the specified search index.

        :param index: The search index to load data into
        :param vectors: The list of vectors to load
        :return: A list of keys for the loaded vectors
        :raise SchemaValidationError: If the vector schema is invalid according to the
            index schema
        """

        if not vectors:
            return []

        index = index or self.index
        keys = index.load(vectors)
        return keys

    def fetch_by_id(
        self, vector_id: str, index: SearchIndex | None = None
    ) -> dict | None:
        """
        Fetch a single vector by its ID from the index.

        :param vector_id: The ID of the vector to fetch
        :param index: The search index to fetch from
        :return: The vector data or None if not found
        """
        index = index or self.index
        # The fetch method expects just the key, without the prefix
        result = index.fetch(vector_id.split(":", 1)[-1])
        return result if result else None

    def _get_vectorizer(self):
        if self._vectorizer is None:
            self._vectorizer = OpenAITextVectorizer(model=VECTORIZER_MODEL)
        return self._vectorizer

    def vectorize_many(self, texts: list[str]) -> list[list[float]]:
        """
        Vectorize a list of texts.

        :param texts: The list of texts to vectorize
        :return: A list of vectors corresponding to the input texts
        """
        if not texts:
            return []

        vectorizer = self._get_vectorizer()
        return vectorizer.embed_many(texts, batch_size=20)

    def vectorize_many_chunks(
        self, document_chunks: list[KnowledgeBaseDocumentChunk]
    ) -> list[list[float]]:
        """
        Vectorize a list of document chunks.

        :param document_chunks: The list of document chunks to vectorize
        :return: A list of vectors corresponding to the input document chunks
        """

        return self.vectorize_many([chunk.content for chunk in document_chunks])

    def delete_many(
        self, vector_ids: list[str], index: SearchIndex | None = None
    ) -> None:
        if not vector_ids:
            return

        index = index or self.index
        index.drop_keys(vector_ids)

    def query(
        self,
        query_vector: list[float],
        vector_field_name: str | None = None,
        return_fields: list[str] | None = None,
        num_results: int = 10,
        filter_expression: filter.FilterExpression | None = None,
        index: SearchIndex | None = None,
    ) -> list[Vector]:
        """
        Query the specified search index.

        :param query: The query string to search for
        :param filters: Optional filters to apply to the search
        :return: A list of vectors matching the query
        """

        vector_field_name = vector_field_name or VECTOR_FIELD_NAME
        return_fields = return_fields or [
            DOCUMENT_CHUNK_ID_FIELD_NAME,
            CONTENT_FIELD_NAME,
        ]

        index = index or self.index
        query = VectorQuery(
            vector=query_vector,
            vector_field_name=vector_field_name,
            return_fields=return_fields,
            num_results=num_results,
            filter_expression=filter_expression,
        )
        return index.query(query)


class IngestionService:
    def __init__(self, vector_store: RedisVectorStore | None = None):
        self.vector_store = vector_store or RedisVectorStore()

    def sync_chunks_to_vector_store(self, chunk_ids: list[int] | None = None):
        """
        Sync existing ready KnowledgeBaseDocumentChunk embeddings with the vector store index.

        This method repopulates the Redis index from already computed embeddings
        without needing to re-run the vectorization process. Useful if the index
        has been deleted or corrupted and you want to restore it quickly.
        """

        chunks_filters = Q(source_document__status=KnowledgeBaseDocument.Status.READY)
        if chunk_ids is not None:
            chunks_filters &= Q(id__in=chunk_ids)

        chunks_to_sync = (
            KnowledgeBaseDocumentChunk.objects.filter(chunks_filters)
            .select_related("source_document__category__parent__parent__parent")
            .all()
        )

        # Drop and recreate the index with the ready chunks
        self.vector_store.create_index(overwrite=True)
        vector_ids = self.vector_store.load_data(
            [_document_chunk_to_vector(chunk) for chunk in chunks_to_sync]
        )

        for vector_id, chunk in zip(vector_ids, chunks_to_sync):
            chunk.vector_id = vector_id
        KnowledgeBaseDocumentChunk.objects.bulk_update(
            chunks_to_sync, ["vector_id", "updated_on"]
        )

    def _split_document_into_chunks(
        self, document: KnowledgeBaseDocument
    ) -> list[KnowledgeBaseDocumentChunk]:
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "title"),
                ("##", "section"),
                ("###", "subsection"),
            ]
        )
        chunks = markdown_splitter.split_text(
            document.content if document.process_document else document.raw_content
        )
        document_chunks = []
        category_full_path = document.category.full_path if document.category else ""
        for index, chunk in enumerate(chunks):
            section, subsection = chunk.metadata.get("section", ""), chunk.metadata.get(
                "subsection", ""
            )
            if section == "Related content":  # Doesn't provide any value as chunk alone
                continue
            if subsection:
                section += f" > {subsection}"
            document_chunk = KnowledgeBaseDocumentChunk(
                source_document=document,
                index=index,
                content=_prepare_chunk_content(
                    document.title,
                    document.source_url,
                    section,
                    chunk.page_content,
                    category_full_path,
                ),
                metadata={
                    "title": document.title,
                    "category": category_full_path,
                    "section": section,
                },
            )
            document_chunks.append(document_chunk)
        return document_chunks

    def _ingest_pending_documents(
        self, documents: list[KnowledgeBaseDocument] | None = None
    ) -> list[KnowledgeBaseDocumentChunk]:
        """
        #TODO
        """

        # Preprocess the documents
        docs_to_process = []
        for doc in documents:
            doc.content = ""  # Clear content for processing
            if doc.process_document:
                docs_to_process.append(doc)

        if docs_to_process:
            preprocessed_docs = self._preprocess_document_contents_in_batch(
                [doc.raw_content for doc in docs_to_process]
            )

            for doc_content, doc in zip(preprocessed_docs, docs_to_process):
                doc.content = doc_content

        KnowledgeBaseDocument.objects.bulk_update(
            docs_to_process, ["content", "updated_on"]
        )

        # Remove existing chunks, from the database and the vector_store
        chunks_to_delete = KnowledgeBaseDocumentChunk.objects.filter(
            source_document__in=documents
        )
        self.vector_store.delete_many(
            [chunk.vector_id for chunk in chunks_to_delete if chunk.vector_id]
        )
        chunks_to_delete.delete()

        # Split documents in chunk
        document_chunks_to_create: list[KnowledgeBaseDocumentChunk] = []
        for doc in documents:
            chunks = self._split_document_into_chunks(doc)
            document_chunks_to_create.extend(chunks)

        # Vectorize the documents
        embeddings = self.vector_store.vectorize_many_chunks(document_chunks_to_create)
        for chunk, embedding in zip(document_chunks_to_create, embeddings):
            chunk.embedding = embedding

        # Load the vectors into the vector store. We need to create the chunks first
        # because we need to store the chunk_id in the vector
        created_chunks = KnowledgeBaseDocumentChunk.objects.bulk_create(
            document_chunks_to_create
        )
        chunk_vector_ids = self.vector_store.load_data(
            [_document_chunk_to_vector(chunk) for chunk in created_chunks]
        )

        # Update the chunks with their vector IDs
        for vector_id, chunk in zip(chunk_vector_ids, created_chunks):
            chunk.vector_id = vector_id
        KnowledgeBaseDocumentChunk.objects.bulk_update(created_chunks, ["vector_id"])

        return created_chunks

    def ingest_pending_documents(
        self, documents: list[KnowledgeBaseDocument] | None = None
    ):
        docs_to_ingest = documents or self._get_pending_documents_to_ingest()
        if not docs_to_ingest:
            return

        # Update the document status to PROCESSING to avoid concurrent ingestion
        original_status = {doc.id: doc.status for doc in docs_to_ingest}
        for doc in docs_to_ingest:
            doc.status = KnowledgeBaseDocument.Status.PROCESSING
        KnowledgeBaseDocument.objects.bulk_update(
            docs_to_ingest, ["status", "updated_on"]
        )

        try:
            with transaction.atomic():
                self._ingest_pending_documents(docs_to_ingest)
        except Exception as exc:
            # Rollback the document status to the original status in case of an error
            for doc in docs_to_ingest:
                doc.status = original_status.get(doc.id, doc.status)
            KnowledgeBaseDocument.objects.bulk_update(
                docs_to_ingest, ["status", "updated_on"]
            )

            raise exc
        else:
            # Ingestion completed
            for doc in docs_to_ingest:
                doc.status = KnowledgeBaseDocument.Status.READY
            KnowledgeBaseDocument.objects.bulk_update(
                docs_to_ingest, ["status", "updated_on"]
            )

    def _get_pending_documents_to_ingest(self) -> QuerySet[KnowledgeBaseDocument]:
        return KnowledgeBaseDocument.objects.filter(
            status__in=[
                KnowledgeBaseDocument.Status.NEW,
                KnowledgeBaseDocument.Status.STALE_CONTENT,
            ]
        ).select_related("category__parent__parent__parent")

    def _preprocess_document_contents_in_batch(self, contents: list[str]) -> list[str]:
        """
        Batch process multiple documents with the LLM for better efficiency.
        Uses LangChain's native batch processing.
        """
        prompt = ChatPromptTemplate.from_template(PREPROCESS_DOCUMENT_PROMPT)
        llm = init_chat_model(model="openai:gpt-5-nano", temperature=0.3)
        chain = prompt | llm | StrOutputParser()

        # Create input dicts for all documents
        inputs = [{"document_content": content} for content in contents]

        # Process in batches
        preprocessed_contents = chain.batch(inputs, config={"max_concurrency": 5})
        return preprocessed_contents


class DocSearchHandler:
    def __init__(self, vector_store: RedisVectorStore | None = None):
        self.vector_store = vector_store or RedisVectorStore()

    def search_documents(self, user_query: str, num_results=20) -> list[str]:
        (vector_query,) = self.vector_store.vectorize_many([user_query])
        results = self.vector_store.query(vector_query, num_results=num_results)
        return [res["content"] for res in results]
