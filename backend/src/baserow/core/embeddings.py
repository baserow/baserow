"""
Client for Baserow's embeddings service (`BASEROW_EMBEDDINGS_API_URL`), shared by
the Kuma knowledge base and the vector search of database fields. Vectors are
padded to `DEFAULT_EMBEDDING_DIMENSIONS` so every pgvector column has one shape.
"""

from urllib.parse import urlparse

from django.conf import settings

import httpx
from httpx import Client as httpxClient
from loguru import logger

from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS, is_pgvector_enabled

# The service truncates its input to the model's context anyway (MiniLM reads
# roughly this many characters), so longer texts only cost bandwidth.
EMBEDDING_TEXT_LIMIT = 1000


class EmbeddingsServiceError(Exception):
    """
    The embeddings service failed or could not be reached. The underlying
    `httpx` error is only logged because its message carries the service's
    internal URL, which must not reach whoever triggered the request.
    """


class BaserowEmbedder:
    def __init__(self, api_url: str, dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS):
        self.api_url = api_url
        self.dimensions = dimensions

    def _embed(self, texts: list[str], batch_size=8) -> list[list[float]]:
        embeddings = []
        client = httpxClient(base_url=self.api_url)
        try:
            for i in range(0, len(texts), batch_size):
                response = client.post(
                    "/embed", json={"texts": texts[i : i + batch_size]}
                )
                response.raise_for_status()
                embeddings.extend(response.json()["embeddings"])
        except httpx.HTTPError as exc:
            logger.warning("Embeddings service request failed: {!r}", exc)
            raise EmbeddingsServiceError(
                "The embeddings service is unavailable."
            ) from None
        finally:
            client.close()
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

        if len(embeddings[0]) > self.dimensions:
            raise ValueError(
                f"Expected embeddings of dimension {self.dimensions}, "
                f"but got {len(embeddings[0])}"
            )
        elif len(embeddings[0]) < self.dimensions:
            # Pad the embeddings with zeros if they are smaller than expected
            for i in range(len(embeddings)):
                embeddings[i] = embeddings[i] + [0.0] * (
                    self.dimensions - len(embeddings[i])
                )
        return embeddings


def embeddings_configured() -> bool:
    return bool(settings.BASEROW_EMBEDDINGS_API_URL)


def vector_search_available() -> bool:
    """
    Whether this instance can compute and store embeddings: the embeddings
    service is configured and pgvector is installed in the database.
    """

    return embeddings_configured() and is_pgvector_enabled()


def embedding_model_key() -> str:
    """
    Identifies the embedding space the stored vectors live in. It is mixed into
    the per-cell `embedding_hash`, so pointing the instance at another
    embeddings service re-embeds every cell instead of comparing vectors of
    different models against each other.
    """

    host = urlparse(settings.BASEROW_EMBEDDINGS_API_URL or "").netloc
    return f"{host}/{DEFAULT_EMBEDDING_DIMENSIONS}"


def get_embedder() -> BaserowEmbedder:
    return BaserowEmbedder(settings.BASEROW_EMBEDDINGS_API_URL)
