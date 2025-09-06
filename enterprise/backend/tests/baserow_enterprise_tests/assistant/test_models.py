import pytest
from unittest.mock import Mock, patch

from baserow_enterprise.assistant.models import (
    KnowledgeBaseDocument,
    KnowledgeBaseDocumentCategory,
    KnowledgeBaseDocumentChunk,
)


@pytest.mark.django_db
class TestKnowledgeBaseDocumentSignals:
    """Test signal handlers for KnowledgeBaseDocument model."""

    def test_cleanup_document_vector_chunks_on_delete(self):
        """Test that vector chunks are cleaned up from Redis when document is deleted."""
        # Create a category first
        category = KnowledgeBaseDocumentCategory.objects.create(
            name="Test Category", description="Test description"
        )

        # Create a document
        document = KnowledgeBaseDocument.objects.create(
            title="Test Document",
            raw_content="Test content",
            content="Test processed content",
            category=category,
        )

        # Create some chunks with vector_ids
        chunk1 = KnowledgeBaseDocumentChunk.objects.create(
            source_document=document,
            vector_id="test_vector_1",
            embedding=[0.1, 0.2, 0.3],
            index=0,
            content="Chunk 1 content",
            metadata={"test": "data"},
        )

        chunk2 = KnowledgeBaseDocumentChunk.objects.create(
            source_document=document,
            vector_id="test_vector_2",
            embedding=[0.4, 0.5, 0.6],
            index=1,
            content="Chunk 2 content",
            metadata={"test": "data"},
        )

        # Create a chunk without vector_id (should be ignored)
        chunk3 = KnowledgeBaseDocumentChunk.objects.create(
            source_document=document,
            vector_id=None,
            embedding=[0.7, 0.8, 0.9],
            index=2,
            content="Chunk 3 content",
            metadata={"test": "data"},
        )

        # Mock the RedisVectorStore
        with patch(
            "baserow_enterprise.assistant.models.RedisVectorStore"
        ) as mock_vector_store_class:
            mock_vector_store = Mock()
            mock_vector_store_class.return_value = mock_vector_store

            # Delete the document
            document.delete()

            # Verify that RedisVectorStore was initialized and delete_many was called
            mock_vector_store_class.assert_called_once()
            mock_vector_store.delete_many.assert_called_once_with(
                ["test_vector_1", "test_vector_2"]
            )

    def test_cleanup_document_vector_chunks_no_vector_ids(self):
        """Test that no cleanup happens when chunks have no vector_ids."""
        # Create a category first
        category = KnowledgeBaseDocumentCategory.objects.create(
            name="Test Category", description="Test description"
        )

        # Create a document
        document = KnowledgeBaseDocument.objects.create(
            title="Test Document",
            raw_content="Test content",
            content="Test processed content",
            category=category,
        )

        # Create chunks without vector_ids
        KnowledgeBaseDocumentChunk.objects.create(
            source_document=document,
            vector_id=None,
            embedding=[0.1, 0.2, 0.3],
            index=0,
            content="Chunk 1 content",
            metadata={"test": "data"},
        )

        # Mock the RedisVectorStore
        with patch(
            "baserow_enterprise.assistant.models.RedisVectorStore"
        ) as mock_vector_store_class:
            mock_vector_store = Mock()
            mock_vector_store_class.return_value = mock_vector_store

            # Delete the document
            document.delete()

            # Verify that RedisVectorStore was NOT initialized since there are no vector_ids
            mock_vector_store_class.assert_not_called()
            mock_vector_store.delete_many.assert_not_called()

    def test_cleanup_document_vector_chunks_exception_handling(self):
        """Test that document deletion succeeds even if vector cleanup fails."""
        # Create a category first
        category = KnowledgeBaseDocumentCategory.objects.create(
            name="Test Category", description="Test description"
        )

        # Create a document
        document = KnowledgeBaseDocument.objects.create(
            title="Test Document",
            raw_content="Test content",
            content="Test processed content",
            category=category,
        )

        # Create a chunk with vector_id
        KnowledgeBaseDocumentChunk.objects.create(
            source_document=document,
            vector_id="test_vector_1",
            embedding=[0.1, 0.2, 0.3],
            index=0,
            content="Chunk 1 content",
            metadata={"test": "data"},
        )

        # Mock the RedisVectorStore to raise an exception
        with patch(
            "baserow_enterprise.assistant.models.RedisVectorStore"
        ) as mock_vector_store_class:
            mock_vector_store = Mock()
            mock_vector_store.delete_many.side_effect = Exception("Redis error")
            mock_vector_store_class.return_value = mock_vector_store

            # Delete the document should succeed despite the exception
            document.delete()

            # Verify that delete_many was attempted
            mock_vector_store.delete_many.assert_called_once_with(["test_vector_1"])

        # Verify the document was actually deleted
        assert not KnowledgeBaseDocument.objects.filter(id=document.id).exists()

    def test_cleanup_document_vector_chunks_no_chunks(self):
        """Test that cleanup handles documents with no chunks gracefully."""
        # Create a category first
        category = KnowledgeBaseDocumentCategory.objects.create(
            name="Test Category", description="Test description"
        )

        # Create a document without any chunks
        document = KnowledgeBaseDocument.objects.create(
            title="Test Document",
            raw_content="Test content",
            content="Test processed content",
            category=category,
        )

        # Mock the RedisVectorStore
        with patch(
            "baserow_enterprise.assistant.models.RedisVectorStore"
        ) as mock_vector_store_class:
            mock_vector_store = Mock()
            mock_vector_store_class.return_value = mock_vector_store

            # Delete the document
            document.delete()

            # Verify that RedisVectorStore was NOT initialized since there are no chunks
            mock_vector_store_class.assert_not_called()
            mock_vector_store.delete_many.assert_not_called()