import csv
from pathlib import Path
from unittest.mock import patch

import pytest

from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS
from baserow_enterprise.assistant.models import (
    DEFAULT_CATEGORIES,
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)
from baserow_enterprise.assistant.tools.search_docs.handler import KnowledgeBaseHandler


@pytest.fixture
def handler_and_csv(tmp_path, monkeypatch):
    csv_path = tmp_path / "website_export.csv"
    monkeypatch.setattr(KnowledgeBaseHandler, "_csv_path", lambda self: csv_path)
    handler = KnowledgeBaseHandler()
    return handler, csv_path


def write_csv(path: Path, rows: list[dict]):
    headers = [
        "id",
        "name",
        "slug",
        "title",
        "markdown_body",
        "category",
        "type",
        "source_url",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def mock_embeddings_vectors(n: int, base: float = 0.1):
    return [
        [base + i * 0.01] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1) for i in range(n)
    ]


def patch_embedder(return_vectors):
    p = patch("baserow_enterprise.assistant.tools.search_docs.handler.httpxClient")
    m = p.start()
    resp = m.return_value.post.return_value
    resp.json.return_value = {"embeddings": return_vectors}
    return p


@pytest.mark.django_db
def test_sync_creates_documents_chunks_and_splits_faq(handler_and_csv):
    handler, csv_path = handler_and_csv

    rows = [
        # user docs
        {
            "id": "1",
            "name": "Home",
            "slug": "index",
            "title": "Home",
            "markdown_body": "**test** *yes*",
            "category": "workspace",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/index",
        },
        {
            "id": "2",
            "name": "category 2",
            "slug": "category-2",
            "title": "Title 2",
            "markdown_body": "> Body 4",
            "category": "snapshot",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/category-2",
        },
        # faq (two separate rows, same base slug 'faq')
        {
            "id": "1",
            "name": "Question 2?",
            "slug": "faq",
            "title": "Question 2?",
            "markdown_body": "Question 2?\n\nAnswer 2",
            "category": "faq",
            "type": "faq",
            "source_url": "https://baserow.io/faq",
        },
        {
            "id": "2",
            "name": "Question 3?",
            "slug": "faq",
            "title": "Question 3?",
            "markdown_body": "Question 3?\n\nAnswer 3",
            "category": "faq",
            "type": "faq",
            "source_url": "https://baserow.io/faq",
        },
    ]
    write_csv(csv_path, rows)

    p = patch_embedder(mock_embeddings_vectors(4))
    try:
        handler.sync_knowledge_base()
    finally:
        p.stop()

    # Documents created
    assert KnowledgeBaseDocument.objects.filter(
        type="baserow_user_docs", slug="index"
    ).exists()
    assert KnowledgeBaseDocument.objects.filter(
        type="baserow_user_docs", slug="category-2"
    ).exists()

    # FAQ should be split into faq-1 and faq-2
    assert KnowledgeBaseDocument.objects.filter(type="faq", slug="faq-1").exists()
    assert KnowledgeBaseDocument.objects.filter(type="faq", slug="faq-2").exists()

    # One chunk per document
    for d in KnowledgeBaseDocument.objects.all():
        assert KnowledgeBaseChunk.objects.filter(source_document=d).count() == 1

    # Categories linked by name
    assert KnowledgeBaseDocument.objects.get(slug="index").category.name == "workspace"
    assert (
        KnowledgeBaseDocument.objects.get(slug="category-2").category.name == "snapshot"
    )
    assert KnowledgeBaseDocument.objects.get(slug="faq-1").category.name == "faq"


@pytest.mark.django_db
def test_sync_no_reembedding_when_body_unchanged(handler_and_csv, monkeypatch):
    handler, csv_path = handler_and_csv

    rows = [
        {
            "id": "1",
            "name": "Home",
            "slug": "index",
            "title": "Home",
            "markdown_body": "**test** *yes*",
            "category": "workspace",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/index",
        }
    ]
    write_csv(csv_path, rows)

    # First sync embeds once
    p1 = patch_embedder(mock_embeddings_vectors(1))
    try:
        handler.sync_knowledge_base()
    finally:
        p1.stop()

    doc = KnowledgeBaseDocument.objects.get(slug="index", type="baserow_user_docs")
    chunk_before = KnowledgeBaseChunk.objects.get(source_document=doc)
    chunk_before_id = chunk_before.id

    # Second sync with same CSV: ensure embedder is NOT called
    called = {"n": 0}

    def fake_embed(texts):
        called["n"] += 1
        return mock_embeddings_vectors(len(texts))

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed)

    handler.sync_knowledge_base()

    # No new chunks created; existing remains the same id
    chunk_after = KnowledgeBaseChunk.objects.get(source_document=doc)
    assert chunk_after.id == chunk_before_id
    # Embeddings not recomputed
    assert called["n"] == 0


@pytest.mark.django_db
def test_sync_reembeds_on_body_change(handler_and_csv):
    handler, csv_path = handler_and_csv

    initial_rows = [
        {
            "id": "1",
            "name": "Home",
            "slug": "index",
            "title": "Home",
            "markdown_body": "Original body",
            "category": "workspace",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/index",
        }
    ]
    write_csv(csv_path, initial_rows)

    p1 = patch_embedder(mock_embeddings_vectors(1, base=0.2))
    try:
        handler.sync_knowledge_base()
    finally:
        p1.stop()

    doc = KnowledgeBaseDocument.objects.get(slug="index", type="baserow_user_docs")
    old_chunk = KnowledgeBaseChunk.objects.get(source_document=doc)
    old_chunk_id = old_chunk.id
    assert "Original body" in old_chunk.content

    # Update CSV body
    updated_rows = [
        {
            "id": "1",
            "name": "Home",
            "slug": "index",
            "title": "Home",
            "markdown_body": "Updated body text",
            "category": "workspace",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/index",
        }
    ]
    write_csv(csv_path, updated_rows)

    p2 = patch_embedder(mock_embeddings_vectors(1, base=0.3))
    try:
        handler.sync_knowledge_base()
    finally:
        p2.stop()

    # Chunk should be replaced (deleted + created)
    new_chunk = KnowledgeBaseChunk.objects.get(source_document=doc)
    assert new_chunk.id != old_chunk_id
    assert "Updated body text" in new_chunk.content


@pytest.mark.django_db
def test_sync_deletes_docs_missing_from_csv_within_same_type(handler_and_csv):
    handler, csv_path = handler_and_csv

    rows1 = [
        {
            "id": "1",
            "name": "Home",
            "slug": "index",
            "title": "Home",
            "markdown_body": "A",
            "category": "workspace",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/index",
        },
        {
            "id": "2",
            "name": "Page",
            "slug": "category-2",
            "title": "Page",
            "markdown_body": "B",
            "category": "snapshot",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/category-2",
        },
        {
            "id": "1",
            "name": "Q2",
            "slug": "faq",
            "title": "Q2",
            "markdown_body": "A2",
            "category": "faq",
            "type": "faq",
            "source_url": "https://baserow.io/faq",
        },
    ]
    write_csv(csv_path, rows1)

    p1 = patch_embedder(mock_embeddings_vectors(3))
    try:
        handler.sync_knowledge_base()
    finally:
        p1.stop()

    assert KnowledgeBaseDocument.objects.filter(
        type="baserow_user_docs", slug="index"
    ).exists()
    assert KnowledgeBaseDocument.objects.filter(
        type="baserow_user_docs", slug="category-2"
    ).exists()

    # Now export contains only user_doc 'category-2' (same type), so 'index' should be
    # deleted
    rows2 = [
        {
            "id": "2",
            "name": "Page",
            "slug": "category-2",
            "title": "Page",
            "markdown_body": "B",
            "category": "snapshot",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/category-2",
        },
        {
            "id": "1",
            "name": "Q2",
            "slug": "faq",
            "title": "Q2",
            "markdown_body": "A2",
            "category": "faq",
            "type": "faq",
            "source_url": "https://baserow.io/faq",
        },
    ]
    write_csv(csv_path, rows2)

    p2 = patch_embedder(mock_embeddings_vectors(2))
    try:
        handler.sync_knowledge_base()
    finally:
        p2.stop()

    assert not KnowledgeBaseDocument.objects.filter(
        type="baserow_user_docs", slug="index"
    ).exists()
    assert KnowledgeBaseDocument.objects.filter(
        type="baserow_user_docs", slug="category-2"
    ).exists()


@pytest.mark.django_db
def test_sync_links_existing_categories(handler_and_csv):
    handler, csv_path = handler_and_csv
    handler.load_categories(DEFAULT_CATEGORIES)

    rows = [
        {
            "id": "1",
            "name": "Home",
            "slug": "index",
            "title": "Home",
            "markdown_body": "Body",
            "category": "workspace",
            "type": "baserow_user_docs",
            "source_url": "https://baserow.io/user-docs/index",
        },
        {
            "id": "1",
            "name": "Q",
            "slug": "faq",
            "title": "Q",
            "markdown_body": "A",
            "category": "faq",
            "type": "faq",
            "source_url": "https://baserow.io/faq",
        },
    ]
    write_csv(csv_path, rows)

    p = patch_embedder(mock_embeddings_vectors(2))
    try:
        handler.sync_knowledge_base()
    finally:
        p.stop()

    assert KnowledgeBaseCategory.objects.filter(name="workspace").exists()
    assert KnowledgeBaseCategory.objects.filter(name="faq").exists()

    d1 = KnowledgeBaseDocument.objects.get(type="baserow_user_docs", slug="index")
    d2 = KnowledgeBaseDocument.objects.get(type="faq", slug="faq-1")
    assert d1.category.name == "workspace"
    assert d2.category.name == "faq"
