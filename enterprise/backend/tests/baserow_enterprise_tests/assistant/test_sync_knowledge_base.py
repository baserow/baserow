import csv
from pathlib import Path

import pytest

from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS
from baserow_enterprise.assistant.models import (
    DEFAULT_CATEGORIES,
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)
from baserow_enterprise.assistant.tools.search_user_docs.handler import (
    KnowledgeBaseHandler,
)


@pytest.fixture
def handler_and_csv(tmp_path, monkeypatch):
    csv_path = tmp_path / "website_export.csv"
    monkeypatch.setattr(KnowledgeBaseHandler, "_csv_path", lambda self: csv_path)
    handler = KnowledgeBaseHandler()
    return handler, csv_path


@pytest.fixture
def handler_and_docs_root(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(KnowledgeBaseHandler, "_get_docs_path", lambda self: docs_root)

    handler = KnowledgeBaseHandler()
    return handler, docs_root


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


def fake_embed_texts(texts):
    return [[0.1] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1) for _ in texts]


@pytest.mark.django_db
def test_sync_creates_documents_chunks_and_splits_faq(handler_and_csv, monkeypatch):
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

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

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

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

    doc = KnowledgeBaseDocument.objects.get(slug="index", type="baserow_user_docs")
    chunk_before = KnowledgeBaseChunk.objects.get(source_document=doc)
    chunk_before_id = chunk_before.id

    # Second sync with same CSV: ensure embedder is NOT called
    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

    # No new chunks created; existing remains the same id
    chunk_after = KnowledgeBaseChunk.objects.get(source_document=doc)
    assert chunk_after.id == chunk_before_id


@pytest.mark.django_db
def test_sync_reembeds_on_body_change(handler_and_csv, monkeypatch):
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

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

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

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

    # Chunk should be replaced (deleted + created)
    new_chunk = KnowledgeBaseChunk.objects.get(source_document=doc)
    assert new_chunk.id != old_chunk_id
    assert "Updated body text" in new_chunk.content


@pytest.mark.django_db
def test_sync_deletes_docs_missing_from_csv_within_same_type(
    handler_and_csv, monkeypatch
):
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

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

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

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

    assert not KnowledgeBaseDocument.objects.filter(
        type="baserow_user_docs", slug="index"
    ).exists()
    assert KnowledgeBaseDocument.objects.filter(
        type="baserow_user_docs", slug="category-2"
    ).exists()


@pytest.mark.django_db
def test_sync_links_existing_categories(handler_and_csv, monkeypatch):
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

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

    assert KnowledgeBaseCategory.objects.filter(name="workspace").exists()
    assert KnowledgeBaseCategory.objects.filter(name="faq").exists()

    d1 = KnowledgeBaseDocument.objects.get(type="baserow_user_docs", slug="index")
    d2 = KnowledgeBaseDocument.objects.get(type="faq", slug="faq-1")
    assert d1.category.name == "workspace"
    assert d2.category.name == "faq"


@pytest.mark.django_db
def test_sync_knowledge_base_with_real_file(monkeypatch):
    handler = KnowledgeBaseHandler()
    handler.load_categories(DEFAULT_CATEGORIES)

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base()

    count_documents = KnowledgeBaseDocument.objects.all().count()
    count_chunks = KnowledgeBaseChunk.objects.all().count()

    assert count_documents > 100
    assert count_chunks > 100

    handler.sync_knowledge_base()

    assert count_documents == KnowledgeBaseDocument.objects.all().count()
    assert count_chunks == KnowledgeBaseChunk.objects.all().count()


@pytest.mark.django_db
def test_sync_dev_docs_creates_documents_and_chunks(handler_and_docs_root, monkeypatch):
    handler, docs_root = handler_and_docs_root

    handler.load_categories(DEFAULT_CATEGORIES)
    assert KnowledgeBaseCategory.objects.filter(name="dev_docs").exists()

    dev_dir = docs_root / "development"
    api_dir = dev_dir / "api"
    dev_dir.mkdir()
    api_dir.mkdir()

    file1 = dev_dir / "ci-cd.md"
    file1.write_text("# CI/CD guide", encoding="utf-8")

    file2 = api_dir / "this-is-a-name.md"
    file2.write_text("API doc body", encoding="utf-8")

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base_from_dev_docs()

    doc_type = KnowledgeBaseDocument.DocumentType.BASEROW_DEV_DOCS

    d1 = KnowledgeBaseDocument.objects.get(type=doc_type, slug="dev/development/ci-cd")
    d2 = KnowledgeBaseDocument.objects.get(
        type=doc_type, slug="dev/development/api/this-is-a-name"
    )

    assert d1.title == "Ci Cd"
    assert d2.title == "This Is A Name"

    assert d1.category.name == "dev_docs"
    assert d2.category.name == "dev_docs"

    assert d1.source_url == "https://baserow.io/docs/development/ci-cd"
    assert d2.source_url == "https://baserow.io/docs/development/api/this-is-a-name"

    assert KnowledgeBaseChunk.objects.filter(source_document=d1).count() == 1
    assert KnowledgeBaseChunk.objects.filter(source_document=d2).count() == 1


@pytest.mark.django_db
def test_sync_dev_docs_no_reembedding_when_body_unchanged(
    handler_and_docs_root, monkeypatch
):
    handler, docs_root = handler_and_docs_root

    handler.load_categories(DEFAULT_CATEGORIES)

    dev_dir = docs_root / "development"
    dev_dir.mkdir()

    doc_file = dev_dir / "ci-cd.md"
    doc_file.write_text("Initial body", encoding="utf-8")

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base_from_dev_docs()

    doc_type = KnowledgeBaseDocument.DocumentType.BASEROW_DEV_DOCS
    doc = KnowledgeBaseDocument.objects.get(type=doc_type, slug="dev/development/ci-cd")
    chunk_before = KnowledgeBaseChunk.objects.get(source_document=doc)
    chunk_before_id = chunk_before.id

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base_from_dev_docs()

    chunk_after = KnowledgeBaseChunk.objects.get(source_document=doc)
    assert chunk_after.id == chunk_before_id


@pytest.mark.django_db
def test_sync_dev_docs_reembeds_on_body_change(handler_and_docs_root, monkeypatch):
    handler, docs_root = handler_and_docs_root

    handler.load_categories(DEFAULT_CATEGORIES)

    dev_dir = docs_root / "development"
    dev_dir.mkdir()

    doc_file = dev_dir / "ci-cd.md"
    doc_file.write_text("Original body", encoding="utf-8")

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base_from_dev_docs()

    doc_type = KnowledgeBaseDocument.DocumentType.BASEROW_DEV_DOCS
    doc = KnowledgeBaseDocument.objects.get(type=doc_type, slug="dev/development/ci-cd")
    old_chunk = KnowledgeBaseChunk.objects.get(source_document=doc)
    old_chunk_id = old_chunk.id
    assert "Original body" in old_chunk.content

    doc_file.write_text("Updated body text", encoding="utf-8")

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base_from_dev_docs()

    new_chunk = KnowledgeBaseChunk.objects.get(source_document=doc)
    assert new_chunk.id != old_chunk_id
    assert "Updated body text" in new_chunk.content


@pytest.mark.django_db
def test_sync_dev_docs_deletes_docs_when_file_removed(
    handler_and_docs_root, monkeypatch
):
    handler, docs_root = handler_and_docs_root

    handler.load_categories(DEFAULT_CATEGORIES)

    dev_dir = docs_root / "development"
    dev_dir.mkdir()

    file1 = dev_dir / "ci-cd.md"
    file2 = dev_dir / "other-page.md"
    file1.write_text("A", encoding="utf-8")
    file2.write_text("B", encoding="utf-8")

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base_from_dev_docs()

    doc_type = KnowledgeBaseDocument.DocumentType.BASEROW_DEV_DOCS
    assert KnowledgeBaseDocument.objects.filter(
        type=doc_type, slug="dev/development/ci-cd"
    ).exists()
    assert KnowledgeBaseDocument.objects.filter(
        type=doc_type, slug="dev/development/other-page"
    ).exists()

    file1.unlink()

    monkeypatch.setattr(handler.vector_handler, "embed_texts", fake_embed_texts)
    handler.sync_knowledge_base_from_dev_docs()

    # Document for removed file should be deleted; other remains
    assert not KnowledgeBaseDocument.objects.filter(
        type=doc_type, slug="dev/development/ci-cd"
    ).exists()
    assert KnowledgeBaseDocument.objects.filter(
        type=doc_type, slug="dev/development/other-page"
    ).exists()
