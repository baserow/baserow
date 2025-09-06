import io
import json
from unittest.mock import patch

import numpy as np
import pytest

from baserow_enterprise.assistant.capabilities.knowledge_retrieval.constants import (
    EMBEDDING_DIMENSIONS,
)
from baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler import (
    KnowledgeBaseHandler,
)
from baserow_enterprise.assistant.models import (
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)

from .utils import TestVectorStore


@pytest.mark.django_db
class TestKnowledgeHandler:
    @pytest.fixture
    def knowledge_handler(self):
        """Create handler with test vector store"""

        test_vector_store = TestVectorStore()
        return KnowledgeBaseHandler(vector_store=test_vector_store)

    @pytest.fixture
    def sample_categories(self):
        """Create sample category hierarchy"""

        parent_cat = KnowledgeBaseCategory.objects.create(
            name="Parent Category", description="Parent category description"
        )
        child_cat = KnowledgeBaseCategory.objects.create(
            name="Child Category",
            description="Child category description",
            parent=parent_cat,
        )
        return parent_cat, child_cat

    @pytest.fixture
    def sample_documents_with_chunks(self, sample_categories):
        """Create sample documents with chunks that have embeddings"""

        parent_cat, child_cat = sample_categories

        doc1 = KnowledgeBaseDocument.objects.create(
            title="Database Guide",
            slug="database-guide",
            raw_content="Complete guide to databases",
            content="Complete guide to databases",
            category=parent_cat,
            status=KnowledgeBaseDocument.Status.READY,
        )
        doc2 = KnowledgeBaseDocument.objects.create(
            title="Application Manual",
            slug="application-manual",
            raw_content="How to build applications",
            content="How to build applications",
            category=child_cat,
            status=KnowledgeBaseDocument.Status.READY,
        )

        # Create chunks with embeddings (deterministic for testing)
        chunk1 = KnowledgeBaseChunk.objects.create(
            source_document=doc1,
            content="Database fundamentals and SQL basics",
            embedding=np.random.RandomState(42).random(EMBEDDING_DIMENSIONS).tolist(),
            index=0,
            metadata={"section": "fundamentals"},
        )
        chunk2 = KnowledgeBaseChunk.objects.create(
            source_document=doc2,
            content="Building web applications with frameworks",
            embedding=np.random.RandomState(43).random(EMBEDDING_DIMENSIONS).tolist(),
            index=0,
            metadata={"section": "applications"},
        )

        return [doc1, doc2], [chunk1, chunk2]

    def test_retrieve_knowledge_chunks_empty_store(self, knowledge_handler):
        """Test knowledge retrieval when vector store is empty"""

        results = knowledge_handler.retrieve_knowledge_chunks("database query")
        assert results == []

    def test_retrieve_knowledge_chunks_with_data(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test knowledge retrieval with actual data in vector store"""

        documents, chunks = sample_documents_with_chunks

        # Sync the chunks to the vector store
        knowledge_handler.vector_store.sync_vectors(chunks)

        # Query for database-related content
        results = knowledge_handler.retrieve_knowledge_chunks(
            "database fundamentals", num_results=5
        )

        assert len(results) > 0
        assert any(
            "database" in result.lower() or "sql" in result.lower()
            for result in results
        )

    def test_retrieve_knowledge_chunks_respects_num_results(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test that num_results parameter is respected"""

        documents, chunks = sample_documents_with_chunks

        # Add more chunks to test limiting
        for i in range(5):
            chunk = chunks[0].__class__(
                source_document=documents[0],
                content=f"Additional database content {i}",
                embedding=np.random.random(EMBEDDING_DIMENSIONS).tolist(),
                index=i + 1,
                metadata={"section": "additional"},
            )
            chunk.save()
            chunks.append(chunk)

        knowledge_handler.vector_store.sync_vectors(chunks)

        results = knowledge_handler.retrieve_knowledge_chunks("database", num_results=3)

        assert len(results) <= 3

    def test_load_categories_creates_hierarchy(self, knowledge_handler):
        """Test category loading with parent-child relationships"""

        categories_data = [
            ("Root Category", None),
            ("Child Category", "Root Category"),
            ("Grandchild Category", "Child Category"),
        ]

        knowledge_handler.load_categories(categories_data)

        # Verify categories were created with correct hierarchy
        root_cat = KnowledgeBaseCategory.objects.get(name="Root Category")
        child_cat = KnowledgeBaseCategory.objects.get(name="Child Category")
        grandchild_cat = KnowledgeBaseCategory.objects.get(name="Grandchild Category")

        assert root_cat.parent is None
        assert child_cat.parent == root_cat
        assert grandchild_cat.parent == child_cat

    def test_load_categories_handles_empty_data(self, knowledge_handler):
        """Test loading empty categories data"""

        knowledge_handler.load_categories([])

        assert KnowledgeBaseCategory.objects.count() == 0

    def test_load_categories_updates_existing(self, knowledge_handler):
        """Test that existing categories are updated, not duplicated"""

        # Create existing category
        existing_cat = KnowledgeBaseCategory.objects.create(
            name="Existing Category", description="Existing description"
        )
        original_id = existing_cat.id

        categories_data = [
            ("Existing Category", None),
            ("New Child", "Existing Category"),
        ]

        knowledge_handler.load_categories(categories_data)

        # Should only have 2 categories total
        assert KnowledgeBaseCategory.objects.count() == 2

        # Existing category should still have same ID (was updated, not replaced)
        existing_cat.refresh_from_db()
        assert existing_cat.id == original_id
        assert existing_cat.name == "Existing Category"

        # New child should be created
        child_cat = KnowledgeBaseCategory.objects.get(name="New Child")
        assert child_cat.parent == existing_cat

    def test_load_categories_handles_missing_parent(self, knowledge_handler):
        """Test handling of categories with missing parent references"""

        categories_data = [
            ("Child Category", "Nonexistent Parent"),
            ("Valid Category", None),
        ]

        # This should create both categories, but the child won't have a parent set
        knowledge_handler.load_categories(categories_data)

        assert KnowledgeBaseCategory.objects.count() == 2

        child_cat = KnowledgeBaseCategory.objects.get(name="Child Category")
        valid_cat = KnowledgeBaseCategory.objects.get(name="Valid Category")

        assert child_cat.parent is None  # Parent wasn't found
        assert valid_cat.parent is None

    def test_dump_knowledge_base_json_format(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test dumping knowledge base to JSON format"""

        documents, chunks = sample_documents_with_chunks

        result = knowledge_handler.dump_knowledge_base(
            documents=documents, format="json"
        )

        assert result is not None

        # Parse JSON to verify structure
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0

        # Should contain categories, documents, and chunks
        model_types = {item["model"] for item in data}
        expected_models = {
            "baserow_enterprise.knowledgebasecategory",
            "baserow_enterprise.knowledgebasedocument",
            "baserow_enterprise.knowledgebasechunk",
        }
        assert expected_models.issubset(model_types)

    def test_dump_knowledge_base_to_stream(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test dumping knowledge base to a stream"""

        documents, chunks = sample_documents_with_chunks
        stream = io.StringIO()

        result = knowledge_handler.dump_knowledge_base(
            documents=documents, format="json", stream=stream
        )

        # Stream should contain the serialized data
        stream_content = stream.getvalue()
        assert len(stream_content) > 0

        # Should be valid JSON
        data = json.loads(stream_content)
        assert isinstance(data, list)

    def test_dump_knowledge_base_all_documents(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test dumping all documents when none specified"""

        documents, chunks = sample_documents_with_chunks

        result = knowledge_handler.dump_knowledge_base(format="json")

        assert result is not None
        data = json.loads(result)

        # Should include all documents in the database
        document_items = [
            item
            for item in data
            if item["model"] == "baserow_enterprise.knowledgebasedocument"
        ]
        assert len(document_items) >= len(documents)

    def test_dump_knowledge_base_different_formats(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test dumping in different serialization formats"""

        documents, chunks = sample_documents_with_chunks

        # Test XML format
        xml_result = knowledge_handler.dump_knowledge_base(
            documents=documents, format="xml"
        )
        assert xml_result is not None
        assert xml_result.startswith("<?xml")

        # Test YAML format (if supported)
        yaml_result = knowledge_handler.dump_knowledge_base(
            documents=documents, format="yaml"
        )
        assert yaml_result is not None

    def test_load_knowledge_base_from_string(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test loading knowledge base from serialized string"""

        documents, chunks = sample_documents_with_chunks

        # First dump the knowledge base
        serialized_data = knowledge_handler.dump_knowledge_base(
            documents=documents, format="json"
        )

        # Clear existing data
        KnowledgeBaseDocument.objects.all().delete()
        KnowledgeBaseCategory.objects.all().delete()

        # Load it back
        loaded_docs = knowledge_handler.load_knowledge_base(
            serialized_data, format="json"
        )

        assert len(loaded_docs) == 2
        assert KnowledgeBaseDocument.objects.count() == 2
        assert KnowledgeBaseChunk.objects.count() == 2

        # Verify document content was preserved
        doc_titles = {doc.title for doc in loaded_docs}
        expected_titles = {doc.title for doc in documents}
        assert doc_titles == expected_titles

    def test_load_knowledge_base_from_stream(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test loading knowledge base from stream"""

        documents, chunks = sample_documents_with_chunks

        # Create serialized data in stream
        stream = io.StringIO()
        knowledge_handler.dump_knowledge_base(
            documents=documents, format="json", stream=stream
        )

        # Reset stream position for reading
        stream.seek(0)

        # Clear existing data
        KnowledgeBaseDocument.objects.all().delete()
        KnowledgeBaseCategory.objects.all().delete()

        # Load from stream
        loaded_docs = knowledge_handler.load_knowledge_base(stream, format="json")

        assert len(loaded_docs) == 2
        assert KnowledgeBaseDocument.objects.count() == 2

    def test_load_knowledge_base_replaces_existing_documents(self, knowledge_handler):
        """Test that loading replaces existing documents with same slug"""

        # Create existing document
        category = KnowledgeBaseCategory.objects.create(
            name="Test Category", description="Test category description"
        )
        existing_doc = KnowledgeBaseDocument.objects.create(
            title="Original Title",
            slug="test-document",
            raw_content="Original content",
            content="Original content",
            category=category,
        )

        # Create chunk for existing document
        KnowledgeBaseChunk.objects.create(
            source_document=existing_doc,
            content="Original chunk content",
            index=0,
            metadata={},
        )

        assert KnowledgeBaseDocument.objects.count() == 1
        assert KnowledgeBaseChunk.objects.count() == 1

        serialized_data = json.dumps(
            [
                {
                    "model": "baserow_enterprise.knowledgebasedocument",
                    "fields": {
                        "title": "Updated Title",
                        "slug": "test-document",  # Same slug as existing
                        "raw_content": "Updated content",
                        "content": "Updated content",
                        "category": ["Test Category"],
                        "status": KnowledgeBaseDocument.Status.READY,
                    },
                },
                {
                    "model": "baserow_enterprise.knowledgebasechunk",
                    "fields": {
                        "source_document": ["test-document"],
                        "content": "Updated chunk content",
                        "embedding": [0, 1],
                        "index": 0,
                        "metadata": {},
                    },
                },
            ]
        )

        # Load it
        loaded_docs = knowledge_handler.load_knowledge_base(
            serialized_data, format="json"
        )

        # Should have replaced the existing document (still only 1)
        assert KnowledgeBaseDocument.objects.count() == 1
        assert KnowledgeBaseChunk.objects.count() == 1

        updated_doc = KnowledgeBaseDocument.objects.get(slug="test-document")
        assert updated_doc.title == "Updated Title"
        assert updated_doc.content == "Updated content"

        # Chunk should also be replaced
        updated_chunk = KnowledgeBaseChunk.objects.get(source_document=updated_doc)
        assert updated_chunk.content == "Updated chunk content"

    def test_load_knowledge_base_syncs_vector_store(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test that loading knowledge base syncs the vector store"""

        documents, chunks = sample_documents_with_chunks

        # Serialize the data
        serialized_data = knowledge_handler.dump_knowledge_base(
            documents=documents, format="json"
        )

        # Clear the vector store
        knowledge_handler.vector_store.vectors.clear()
        knowledge_handler.vector_store.embeddings.clear()
        knowledge_handler.vector_store.index_created = False

        # Load the knowledge base
        knowledge_handler.load_knowledge_base(serialized_data, format="json")

        # Vector store should have been synced
        assert knowledge_handler.vector_store.index_created is True

    def test_load_knowledge_base_handles_empty_data(self, knowledge_handler):
        """Test loading empty knowledge base data"""

        empty_data = "[]"

        loaded_docs = knowledge_handler.load_knowledge_base(empty_data, format="json")

        assert loaded_docs == []
        assert KnowledgeBaseDocument.objects.count() == 0

    def test_load_knowledge_base_different_formats(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test loading knowledge base from different formats"""

        documents, chunks = sample_documents_with_chunks

        # Test with XML format
        xml_data = knowledge_handler.dump_knowledge_base(
            documents=documents, format="xml"
        )

        # Clear data
        KnowledgeBaseDocument.objects.all().delete()
        KnowledgeBaseCategory.objects.all().delete()

        loaded_docs = knowledge_handler.load_knowledge_base(xml_data, format="xml")

        assert len(loaded_docs) == 2
        assert KnowledgeBaseDocument.objects.count() == 2

    def test_handler_with_default_vector_store(self):
        """Test handler creation with default vector store"""

        with patch(
            "baserow_enterprise.assistant.capabilities.knowledge_retrieval.handler.VectorStore"
        ) as mock_vector_store:
            handler = KnowledgeBaseHandler()

            # Should have created a VectorStore instance
            mock_vector_store.assert_called_once()
            assert handler.vector_store is not None

    def test_handler_with_custom_vector_store(self):
        """Test handler creation with custom vector store"""

        custom_store = TestVectorStore()
        handler = KnowledgeBaseHandler(vector_store=custom_store)

        assert handler.vector_store is custom_store

    def test_complex_category_hierarchy_load(self, knowledge_handler):
        """Test loading a complex category hierarchy with multiple levels"""

        categories_data = [
            ("Technology", None),
            ("Programming", "Technology"),
            ("Web Development", "Programming"),
            ("Frontend", "Web Development"),
            ("Backend", "Web Development"),
            ("React", "Frontend"),
            ("Vue", "Frontend"),
            ("Django", "Backend"),
            ("Flask", "Backend"),
        ]

        knowledge_handler.load_categories(categories_data)

        assert KnowledgeBaseCategory.objects.count() == 9

        # Verify specific relationships
        tech_cat = KnowledgeBaseCategory.objects.get(name="Technology")
        prog_cat = KnowledgeBaseCategory.objects.get(name="Programming")
        web_cat = KnowledgeBaseCategory.objects.get(name="Web Development")
        react_cat = KnowledgeBaseCategory.objects.get(name="React")

        assert prog_cat.parent == tech_cat
        assert web_cat.parent == prog_cat
        assert react_cat.parent.name == "Frontend"
        assert react_cat.parent.parent == web_cat

    def test_load_categories_order_independence(self, knowledge_handler):
        """Test that category order doesn't matter for hierarchy creation"""

        # Categories in "wrong" order (children before parents)
        categories_data = [
            ("Grandchild", "Child"),
            ("Child", "Parent"),
            ("Parent", None),
        ]

        knowledge_handler.load_categories(categories_data)

        parent_cat = KnowledgeBaseCategory.objects.get(name="Parent")
        child_cat = KnowledgeBaseCategory.objects.get(name="Child")
        grandchild_cat = KnowledgeBaseCategory.objects.get(name="Grandchild")

        assert parent_cat.parent is None
        assert child_cat.parent == parent_cat
        assert grandchild_cat.parent == child_cat
