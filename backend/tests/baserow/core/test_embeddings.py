from unittest.mock import patch

from django.test import override_settings

import httpx
import pytest
from httpx import ConnectError

from baserow.core.embeddings import (
    BaserowEmbedder,
    EmbeddingsServiceError,
    vector_search_available,
)


def test_embedder_hides_service_errors():
    with patch("baserow.core.embeddings.httpxClient") as client:
        client.return_value.post.side_effect = ConnectError("http://internal-host")
        with pytest.raises(EmbeddingsServiceError) as exc_info:
            BaserowEmbedder("http://internal-host")(["text"])

    assert "internal-host" not in str(exc_info.value)
    client.return_value.close.assert_called_once()


def test_embedder_treats_an_invalid_response_as_a_service_error():
    # For example the error page of a proxy in front of the service.
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="<html>Bad gateway</html>")
    )
    real_client = httpx.Client
    with patch(
        "baserow.core.embeddings.httpxClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    ):
        with pytest.raises(EmbeddingsServiceError):
            BaserowEmbedder("http://test")(["text"])


def test_embedder_pads_vectors():
    with patch("baserow.core.embeddings.httpxClient") as client:
        client.return_value.post.return_value.json.return_value = {
            "embeddings": [[1.0, 2.0]]
        }
        assert BaserowEmbedder("http://test", dimensions=4)(["text"]) == [
            [1.0, 2.0, 0.0, 0.0]
        ]


@pytest.mark.django_db
def test_vector_search_available():
    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        assert vector_search_available() is False

    with (
        override_settings(BASEROW_EMBEDDINGS_API_URL="http://embeddings"),
        patch("baserow.core.embeddings.is_pgvector_enabled", return_value=False),
    ):
        assert vector_search_available() is False

    with (
        override_settings(BASEROW_EMBEDDINGS_API_URL="http://embeddings"),
        patch("baserow.core.embeddings.is_pgvector_enabled", return_value=True),
    ):
        assert vector_search_available() is True
