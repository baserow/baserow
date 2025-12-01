import pytest

from baserow_enterprise.assistant.models import (
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)


@pytest.mark.django_db
class TestKnowledgeBaseCommands:
    """Test the dump_knowledge_base and load_knowledge_base management commands"""

    @pytest.fixture(autouse=True)
    def init_vector_field(self):
        KnowledgeBaseChunk.try_init_vector_field()

    @pytest.fixture
    def single_document_data(self):
        """Create a single document with 1 category and 1 chunk"""

        category = KnowledgeBaseCategory.objects.create(
            name="Test Category", description="Test category description"
        )
        document = KnowledgeBaseDocument.objects.create(
            title="Test Document",
            slug="test-doc",
            raw_content="Test content",
            content="Test content",
            category=category,
            status=KnowledgeBaseDocument.Status.READY,
        )
        chunk = KnowledgeBaseChunk.objects.create(
            source_document=document,
            content="Test chunk content",
            index=0,
            embedding=[1.0] * KnowledgeBaseChunk.EMBEDDING_DIMENSIONS,
            metadata={"test": "data"},
        )
        return {"category": category, "document": document, "chunk": chunk}

    @pytest.fixture
    def multiple_document_data(self):
        """Create multiple documents with different statuses for testing --all option"""

        category = KnowledgeBaseCategory.objects.create(
            name="Test Category", description="Test category description"
        )

        # Ready document (should be included in normal dump)
        ready_document = KnowledgeBaseDocument.objects.create(
            title="Ready Document",
            slug="ready-doc",
            raw_content="Ready content",
            content="Ready content",
            category=category,
            status=KnowledgeBaseDocument.Status.READY,
        )
        ready_chunk = KnowledgeBaseChunk.objects.create(
            source_document=ready_document,
            content="Ready chunk content",
            index=0,
            embedding=[1.0] * KnowledgeBaseChunk.EMBEDDING_DIMENSIONS,
            metadata={"test": "ready"},
        )

        # Processing document (should only be included with --all)
        processing_document = KnowledgeBaseDocument.objects.create(
            title="Processing Document",
            slug="processing-doc",
            raw_content="Processing content",
            content="Processing content",
            category=category,
            status=KnowledgeBaseDocument.Status.PROCESSING,
        )
        processing_chunk = KnowledgeBaseChunk.objects.create(
            source_document=processing_document,
            content="Processing chunk content",
            index=0,
            embedding=[2.0] * KnowledgeBaseChunk.EMBEDDING_DIMENSIONS,
            metadata={"test": "processing"},
        )

        return {
            "category": category,
            "ready_document": ready_document,
            "ready_chunk": ready_chunk,
            "processing_document": processing_document,
            "processing_chunk": processing_chunk,
        }
