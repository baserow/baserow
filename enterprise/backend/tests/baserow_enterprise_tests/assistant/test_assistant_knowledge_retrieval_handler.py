from unittest.mock import patch

import numpy as np
import pytest

from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS
from baserow_enterprise.assistant.models import (
    KnowledgeBaseCategory,
    KnowledgeBaseChunk,
    KnowledgeBaseDocument,
)
from baserow_enterprise.assistant.tools.search_user_docs.handler import (
    BaserowEmbedder,
    KnowledgeBaseHandler,
    VectorHandler,
)


@pytest.mark.django_db
class TestBaserowEmbedder:
    """Tests for the BaserowEmbedder class"""

    def test_returns_list_of_vectors(self):
        """Test that calling BaserowEmbedder returns a list of vectors"""

        embedder = BaserowEmbedder(api_url="http://test-api:8000")

        # Mock the httpxClient where it's used in the handler module
        with patch(
            "baserow_enterprise.assistant.tools.search_user_docs.handler.httpxClient"
        ) as mock_client:
            mock_client_instance = mock_client.return_value
            mock_post_response = mock_client_instance.post.return_value
            mock_post_response.json.return_value = {
                "embeddings": [
                    [0.1] * DEFAULT_EMBEDDING_DIMENSIONS,
                    [0.2] * DEFAULT_EMBEDDING_DIMENSIONS,
                    [0.3] * DEFAULT_EMBEDDING_DIMENSIONS,
                ]
            }

            texts = ["text 1", "text 2", "text 3"]
            result = embedder(texts)

            # Verify result is a list of vectors
            assert isinstance(result, list)
            assert len(result) == 3
            for vector in result:
                assert isinstance(vector, list)
                assert all(isinstance(x, (int, float)) for x in vector)

    def test_returns_embeddings_with_correct_dimensions(self):
        """Test that embeddings have the correct number of dimensions"""

        embedder = BaserowEmbedder(api_url="http://test-api:8000")

        # Mock the httpxClient where it's used in the handler module
        with patch(
            "baserow_enterprise.assistant.tools.search_user_docs.handler.httpxClient"
        ) as mock_client:
            mock_client_instance = mock_client.return_value
            mock_post_response = mock_client_instance.post.return_value
            mock_post_response.json.return_value = {
                "embeddings": [
                    [0.1] * DEFAULT_EMBEDDING_DIMENSIONS,
                    [0.2] * DEFAULT_EMBEDDING_DIMENSIONS,
                ]
            }

            texts = ["text 1", "text 2"]
            result = embedder(texts)

            # Verify all embeddings have the correct dimensions
            assert len(result) == 2
            for vector in result:
                assert len(vector) == DEFAULT_EMBEDDING_DIMENSIONS

    def test_pads_smaller_dimensions_with_zeros(self):
        """Test that embeddings with fewer dimensions are padded with zeros"""

        embedder = BaserowEmbedder(api_url="http://test-api:8000")

        # Mock the httpxClient where it's used in the handler module
        with patch(
            "baserow_enterprise.assistant.tools.search_user_docs.handler.httpxClient"
        ) as mock_client:
            # Mock the httpxClient.post call with smaller dimensions
            small_dimension = 512
            mock_client_instance = mock_client.return_value
            mock_post_response = mock_client_instance.post.return_value
            mock_post_response.json.return_value = {
                "embeddings": [
                    [0.5] * small_dimension,
                ]
            }

            texts = ["text 1"]
            result = embedder(texts)

            # Verify padding was added
            assert len(result) == 1
            assert len(result[0]) == DEFAULT_EMBEDDING_DIMENSIONS
            # Check that the last values are zeros (padding)
            padding_size = DEFAULT_EMBEDDING_DIMENSIONS - small_dimension
            assert result[0][-padding_size:] == [0.0] * padding_size

    def test_raises_error_on_larger_dimensions(self):
        """Test that embeddings with more dimensions raise an error"""

        embedder = BaserowEmbedder(api_url="http://test-api:8000")

        # Mock the httpxClient where it's used in the handler module
        with patch(
            "baserow_enterprise.assistant.tools.search_user_docs.handler.httpxClient"
        ) as mock_client:
            # Mock the httpxClient.post call with larger dimensions
            large_dimension = DEFAULT_EMBEDDING_DIMENSIONS + 100
            mock_client_instance = mock_client.return_value
            mock_post_response = mock_client_instance.post.return_value
            mock_post_response.json.return_value = {
                "embeddings": [
                    [0.5] * large_dimension,
                ]
            }

            texts = ["text 1"]

            # Should raise ValueError
            with pytest.raises(ValueError) as exc_info:
                embedder(texts)

            assert (
                f"Expected embeddings of dimension {DEFAULT_EMBEDDING_DIMENSIONS}"
                in str(exc_info.value)
            )

    def test_returns_empty_list_for_empty_input(self):
        """Test that empty input returns an empty list"""

        embedder = BaserowEmbedder(api_url="http://test-api:8000")

        result = embedder([])

        assert result == []


class MockEmbeddings:
    """Mock vectorizer for testing that returns deterministic embeddings"""

    def __init__(self):
        # Map query strings to mock embeddings
        self.query_embeddings = {
            "database fundamentals": [1.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1),
            "database query": [0.8] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1),
            "database": [0.9] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1),
            "application": [0.0, 1.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 2),
        }

    def embed_documents(self, texts):
        """Mock embedding for documents"""

        embeddings = []
        for text in texts:
            # Create deterministic embeddings based on text content
            if "database" in text.lower():
                embeddings.append([1.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1))
            elif "application" in text.lower():
                embeddings.append(
                    [0.0, 1.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 2)
                )
            else:
                embeddings.append([0.0] * DEFAULT_EMBEDDING_DIMENSIONS)
        return embeddings

    def embed_query(self, text):
        """Mock embedding for a single query"""

        return self.query_embeddings.get(
            text.lower(), [0.0] * DEFAULT_EMBEDDING_DIMENSIONS
        )


@pytest.mark.django_db
class TestKnowledgeHandler:
    @pytest.fixture(autouse=True)
    def init_vector_field(self):
        KnowledgeBaseChunk.try_init_vector_field()

    @pytest.fixture
    def knowledge_handler(self):
        """Create handler with test vector store"""

        return KnowledgeBaseHandler(vector_handler=VectorHandler(MockEmbeddings()))

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
            embedding=np.random.RandomState(42)
            .random(DEFAULT_EMBEDDING_DIMENSIONS)
            .tolist(),
            index=0,
            metadata={"section": "fundamentals"},
        )
        chunk2 = KnowledgeBaseChunk.objects.create(
            source_document=doc2,
            content="Building web applications with frameworks",
            embedding=np.random.RandomState(43)
            .random(DEFAULT_EMBEDDING_DIMENSIONS)
            .tolist(),
            index=0,
            metadata={"section": "applications"},
        )

        return [doc1, doc2], [chunk1, chunk2]

    def test_retrieve_knowledge_chunks_empty_store(self, knowledge_handler):
        """Test knowledge retrieval when vector store is empty"""

        results = knowledge_handler.search("database query")
        assert list(results) == []

    def test_retrieve_knowledge_chunks_with_data(
        self, knowledge_handler, sample_documents_with_chunks
    ):
        """Test knowledge retrieval with actual data in vector store"""

        documents, chunks = sample_documents_with_chunks

        # The chunks are already in the database and available for search

        # Query for database-related content
        results = [
            ch.content
            for ch in knowledge_handler.search("database fundamentals", num_results=5)
        ]

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
                embedding=np.random.random(DEFAULT_EMBEDDING_DIMENSIONS).tolist(),
                index=i + 1,
                metadata={"section": "additional"},
            )
            chunk.save()
            chunks.append(chunk)

        # The chunks are already in the database and available for search

        results = knowledge_handler.search("database", num_results=3)

        assert len(results) <= 3

    def test_search_orders_by_l2_distance(self, knowledge_handler):
        """Test that search results are ordered by L2 distance (closest first)"""

        # Create a category for our test documents
        category = KnowledgeBaseCategory.objects.create(
            name="Distance Test Category",
            description="For testing L2 distance ordering",
        )

        # Create a document
        doc = KnowledgeBaseDocument.objects.create(
            title="Distance Test Document",
            slug="distance-test-doc",
            raw_content="Test document for distance ordering",
            content="Test document for distance ordering",
            category=category,
            status=KnowledgeBaseDocument.Status.READY,
        )

        # Create chunks with specific embeddings to control distances
        # Query embedding will be [1.0, 0.0, 0.0, ...]
        # These embeddings will have known L2 distances from the query

        # Closest match: embedding [1.0, 0.0, 0.0, ...] -> distance = 0
        closest_chunk = KnowledgeBaseChunk.objects.create(
            source_document=doc,
            content="Closest content to query",
            embedding=[1.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1),
            index=0,
            metadata={"distance_test": "closest"},
        )

        # Medium match: embedding [0.5, 0.0, 0.0, ...] -> distance = 0.5
        medium_chunk = KnowledgeBaseChunk.objects.create(
            source_document=doc,
            content="Medium distance content",
            embedding=[0.5] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 1),
            index=1,
            metadata={"distance_test": "medium"},
        )

        # Farthest match: embedding [0.0, 0.0, 0.0, ...] -> distance = 1.0
        farthest_chunk = KnowledgeBaseChunk.objects.create(
            source_document=doc,
            content="Farthest content from query",
            embedding=[0.0] * DEFAULT_EMBEDDING_DIMENSIONS,
            index=2,
            metadata={"distance_test": "farthest"},
        )

        # Search with a query that will be embedded as [1.0, 0.0, 0.0, ...]
        # (our MockEmbeddings returns this for "database" queries)
        results = [
            ch.content for ch in knowledge_handler.search("database", num_results=3)
        ]

        # Results should be ordered by distance (closest first)
        assert len(results) == 3
        assert "Closest content to query" == results[0]
        assert "Medium distance content" == results[1]
        assert "Farthest content from query" == results[2]

    def test_search_l2_distance_with_different_vectors(self, knowledge_handler):
        """Test L2 distance ordering with more complex vectors"""

        # Create a category and document
        category = KnowledgeBaseCategory.objects.create(
            name="Vector Test Category",
            description="For testing vector distance calculations",
        )

        doc = KnowledgeBaseDocument.objects.create(
            title="Vector Test Document",
            slug="vector-test-doc",
            raw_content="Test document for vector distances",
            content="Test document for vector distances",
            category=category,
            status=KnowledgeBaseDocument.Status.READY,
        )

        # Query will be embedded as [1.0, 0.0, 0.0, 0.0, ...] for "database"
        # Create chunks with known L2 distances:

        # Distance = sqrt((1-1)² + (0-0)² + (0-0)² + ...) = 0
        chunk_distance_0 = KnowledgeBaseChunk.objects.create(
            source_document=doc,
            content="Perfect match",
            embedding=[1.0, 0.0, 0.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 3),
            index=0,
        )

        # Distance = sqrt((1-0)² + (0-1)² + (0-0)² + ...) = sqrt(2) ≈ 1.414
        chunk_distance_sqrt2 = KnowledgeBaseChunk.objects.create(
            source_document=doc,
            content="Distance sqrt(2)",
            embedding=[0.0, 1.0, 0.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 3),
            index=1,
        )

        # Distance = sqrt((1-0.5)² + (0-0.5)² + (0-0)² + ...) = sqrt(0.5) ≈ 0.707
        chunk_distance_sqrt05 = KnowledgeBaseChunk.objects.create(
            source_document=doc,
            content="Distance sqrt(0.5)",
            embedding=[0.5, 0.5, 0.0] + [0.0] * (DEFAULT_EMBEDDING_DIMENSIONS - 3),
            index=2,
        )

        results = [
            ch.content for ch in knowledge_handler.search("database", num_results=3)
        ]

        # Should be ordered: distance 0, sqrt(0.5), sqrt(2)
        assert len(results) == 3
        assert "Perfect match" == results[0]  # distance 0
        assert "Distance sqrt(0.5)" == results[1]  # distance ~0.707
        assert "Distance sqrt(2)" == results[2]  # distance ~1.414

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

    def test_handler_with_default_vector_store(self):
        """Test handler creation with default vector store"""

        with patch(
            "baserow_enterprise.assistant.tools.search_user_docs.handler.VectorHandler"
        ) as mock_vector_handler:
            handler = KnowledgeBaseHandler()

            # Should have created a VectorHandler instance
            mock_vector_handler.assert_called_once()
            assert handler.vector_handler is not None

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
