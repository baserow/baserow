import numpy as np

from baserow_enterprise.assistant.capabilities.knowledge_retrieval.constants import (
    DOCUMENT_CONTENT_FIELD_NAME,
    EMBEDDING_DIMENSIONS,
)


class TestVectorStore:
    """In-memory vector store for testing that actually performs similarity search"""

    def __init__(self):
        self.vectors = {}  # vector_id -> KnowledgeVector
        self.embeddings = {}  # vector_id -> numpy array
        self.vector_counter = 0
        self.index_created = False

    @property
    def index(self):
        """Mock index property"""

        return self

    @property
    def vectorizer(self):
        """Mock vectorizer property"""

        return self

    def query(self, query, num_results=20):
        """Mock query that performs basic similarity search"""

        if not self.embeddings:
            return []

        # Create a mock embedding for the query (normally would be from OpenAI)
        query_embedding = np.random.random(EMBEDDING_DIMENSIONS)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)  # Normalize

        # Calculate cosine similarity with stored embeddings
        similarities = []
        for vector_id, embedding in self.embeddings.items():
            if vector_id in self.vectors:
                # Normalize stored embedding
                norm_embedding = embedding / np.linalg.norm(embedding)
                similarity = np.dot(query_embedding, norm_embedding)
                similarities.append((similarity, vector_id))

        # Sort by similarity (highest first) and return top results
        similarities.sort(reverse=True, key=lambda x: x[0])
        results = []
        for similarity, vector_id in similarities[:num_results]:
            vector = self.vectors[vector_id]
            results.append(vector[DOCUMENT_CONTENT_FIELD_NAME])

        return results

    def raw_query(
        self,
        query_vector,
        vector_field_name=None,
        return_fields=None,
        num_results=20,
        filter_expression=None,
    ):
        """Mock raw query that returns KnowledgeVector format"""

        if not self.embeddings:
            return []

        query_embedding = np.array(query_vector)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        similarities = []
        for vector_id, embedding in self.embeddings.items():
            if vector_id in self.vectors:
                norm_embedding = embedding / np.linalg.norm(embedding)
                similarity = np.dot(query_embedding, norm_embedding)
                similarities.append((similarity, vector_id))

        similarities.sort(reverse=True, key=lambda x: x[0])
        results = []
        for similarity, vector_id in similarities[:num_results]:
            vector = self.vectors[vector_id].copy()
            # Only return requested fields
            if return_fields:
                filtered_vector = {}
                for field in return_fields:
                    if field in vector:
                        filtered_vector[field] = vector[field]
                results.append(filtered_vector)
            else:
                results.append(vector)

        return results

    def sync_vectors(self, chunks=None):
        """Mock syncing - creates index and loads vectors from chunks"""

        self.index_created = True

        if chunks is None:
            # In real implementation, this would fetch from database
            return

        # Convert chunks to vectors and store them
        from baserow_enterprise.assistant.capabilities.knowledge_retrieval.utils import (
            document_chunk_to_knowledge_vector,
        )

        for chunk in chunks:
            if chunk.embedding:
                vector = document_chunk_to_knowledge_vector(chunk)
                vector_id = f"test_vector_{self.vector_counter}"
                self.vector_counter += 1

                # Store the vector and embedding
                self.vectors[vector_id] = vector
                self.embeddings[vector_id] = np.array(chunk.embedding, dtype=np.float32)

                # Update chunk with vector_id (simulating real behavior)
                chunk.vector_id = vector_id

    def load_vectors(self, vectors):
        """Mock loading vectors into the index"""

        vector_ids = []
        for vector in vectors:
            vector_id = f"test_vector_{self.vector_counter}"
            self.vector_counter += 1

            self.vectors[vector_id] = vector
            # Convert embedding bytes back to numpy array for similarity calculation
            embedding_array = np.frombuffer(vector["embedding"], dtype=np.float32)
            self.embeddings[vector_id] = embedding_array
            vector_ids.append(vector_id)

        return vector_ids

    def delete_many(self, vector_ids):
        """Mock deleting vectors from the index"""

        deleted_count = 0
        for vector_id in vector_ids:
            if vector_id in self.vectors:
                del self.vectors[vector_id]
                del self.embeddings[vector_id]
                deleted_count += 1
        return deleted_count

    def embed_many(self, texts):
        """Mock embedding generation"""

        embeddings = []
        for text in texts:
            # Create deterministic embeddings based on text hash for consistent testing
            hash_val = hash(text) % (2**32)
            np.random.seed(hash_val)
            embedding = np.random.random(EMBEDDING_DIMENSIONS)
            embeddings.append(embedding.tolist())
        return embeddings

    def embed_many_chunks(self, document_chunks):
        """Mock embedding chunks using their content"""

        return self.embed_many([chunk.content for chunk in document_chunks])

    def _create_index(self, overwrite=False):
        """Mock index creation"""

        self.index_created = True
        return self, True
