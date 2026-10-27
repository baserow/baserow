from django.conf import settings

import httpx
from httpx import Client as httpxClient
from loguru import logger

from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS, is_pgvector_enabled


class EmbeddingsServiceError(Exception):
    # The underlying `httpx` error is only logged because its message contains the
    # internal URL of the service, which must not reach whoever triggered the request.
    pass


class BaserowEmbedder:
    def __init__(
        self,
        api_url: str,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
        timeout: float = 5,
    ):
        """
        :param api_url: The URL of the embeddings service.
        :param dimensions: The number of dimensions every embedding is padded to.
        :param timeout: The seconds a request may take.
        """

        self.api_url = api_url
        self.dimensions = dimensions
        self.timeout = timeout

    def _embed(self, texts: list[str], batch_size=8) -> list[list[float]]:
        embeddings = []
        client = httpxClient(base_url=self.api_url, timeout=self.timeout)
        try:
            for i in range(0, len(texts), batch_size):
                response = client.post(
                    "/embed", json={"texts": texts[i : i + batch_size]}
                )
                response.raise_for_status()
                embeddings.extend(response.json()["embeddings"])
        # An invalid response, like the error page of a proxy, is retried like an
        # unavailable service.
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Embeddings service request failed: {!r}", exc)
            raise EmbeddingsServiceError(
                "The embeddings service is unavailable."
            ) from None
        finally:
            client.close()
        return embeddings

    def __call__(self, texts: list[str]) -> list[list[float]]:
        """
        :param texts: The texts to embed.
        :return: The embedding of every text, in the same order.
        :raises EmbeddingsServiceError: If the service is unavailable or responds
            with invalid embeddings.
        """

        if not texts:
            return []

        if not isinstance(texts, (list, tuple)):
            texts = [texts]

        embeddings = self._embed(texts)

        if len(embeddings) != len(texts):
            raise EmbeddingsServiceError(
                f"Expected {len(texts)} embeddings, but got {len(embeddings)}"
            )

        if len(embeddings[0]) > self.dimensions:
            raise EmbeddingsServiceError(
                f"Expected embeddings of dimension {self.dimensions}, "
                f"but got {len(embeddings[0])}"
            )
        elif len(embeddings[0]) < self.dimensions:
            # Every pgvector column has the same number of dimensions, so smaller
            # models are padded with zeros, which does not change cosine distances.
            for i in range(len(embeddings)):
                embeddings[i] = embeddings[i] + [0.0] * (
                    self.dimensions - len(embeddings[i])
                )
        return embeddings


def embeddings_configured() -> bool:
    return bool(settings.BASEROW_EMBEDDINGS_API_URL)


def vector_search_available() -> bool:
    """
    :return: Whether vectors can be created and searched, which requires both the
        embeddings service and pgvector.
    """

    return embeddings_configured() and is_pgvector_enabled()


def get_embedder(timeout: float = 5) -> BaserowEmbedder:
    """
    :param timeout: The seconds a request may take. Background tasks can wait
        longer than someone who waits for the result.
    :return: An embedder of the configured embeddings service.
    """

    return BaserowEmbedder(settings.BASEROW_EMBEDDINGS_API_URL, timeout=timeout)
