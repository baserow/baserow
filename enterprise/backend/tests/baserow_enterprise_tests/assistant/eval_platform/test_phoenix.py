import gc
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

import httpx
import pytest

from baserow_enterprise.assistant.evals import baseline
from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client


@pytest.fixture
def phoenix_requests(monkeypatch):
    requests = []

    def respond(transport, request):
        requests.append(request)
        return httpx.Response(200, json={"data": [], "next_cursor": None})

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", respond)
    return requests


class TestGetPhoenixClient:
    def test_raises_when_no_url_configured(self, settings, monkeypatch):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = ""
        monkeypatch.setenv("PHOENIX_ENDPOINT", "http://unrelated-project")

        with pytest.raises(ImproperlyConfigured, match="ai-assistant-tracing.md"):
            get_phoenix_client()

    @pytest.mark.parametrize("api_key", ["settings-key", ""])
    @pytest.mark.parametrize("credential_source", ["environment", "config-file"])
    def test_uses_only_baserow_settings(
        self,
        settings,
        monkeypatch,
        tmp_path,
        phoenix_requests,
        api_key,
        credential_source,
    ):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://settings-url/phoenix"
        settings.BASEROW_ASSISTANT_PHOENIX_API_KEY = api_key
        unrelated_config = {
            "PHOENIX_ENDPOINT": "http://unrelated-project",
            "PHOENIX_API_KEY": "unrelated-key",
            "PHOENIX_CLIENT_HEADERS": "x-other-token=unrelated-header",
        }
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PHOENIX_DISCOVER_CONFIG", "true")
        for key, value in unrelated_config.items():
            if credential_source == "environment":
                monkeypatch.setenv(key, value)
            else:
                monkeypatch.delenv(key, raising=False)
        if credential_source == "config-file":
            config_file = tmp_path / ".env.phoenix"
            config_file.write_text(
                "\n".join(f"{key}={value}" for key, value in unrelated_config.items())
            )
            config_file.chmod(0o600)

        client = get_phoenix_client()

        assert client.datasets.list() == []
        request = phoenix_requests[0]
        assert request.url.host == "settings-url"
        assert request.url.path == "/phoenix/v1/datasets"
        assert request.headers.get("authorization") == (
            f"Bearer {api_key}" if api_key else None
        )
        assert "x-other-token" not in request.headers

    def test_resources_keep_http_client_alive_until_they_are_collected(
        self, settings, monkeypatch, phoenix_requests
    ):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://phoenix-client-cleanup"
        closed = []
        original_close = httpx.Client.close

        def close(client):
            original_close(client)
            if client.base_url.host == "phoenix-client-cleanup":
                closed.append(client.is_closed)

        monkeypatch.setattr(httpx.Client, "close", close)
        client = get_phoenix_client()
        datasets = client.datasets

        del client
        gc.collect()

        assert datasets.list() == []
        assert closed == []

        del datasets
        gc.collect()

        assert closed == [True]

    def test_releases_http_client_if_sdk_construction_fails(self, settings):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://settings-url"

        with (
            patch(
                "phoenix.client.Client", side_effect=RuntimeError("construction")
            ) as create_client,
            pytest.raises(RuntimeError, match="construction"),
        ):
            get_phoenix_client()

        assert create_client.call_args.kwargs["http_client"].is_closed


@pytest.mark.parametrize("api_key", ["settings-key", ""])
def test_baseline_requests_use_only_baserow_settings(
    settings, monkeypatch, phoenix_requests, api_key
):
    settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://settings-url/phoenix/"
    settings.BASEROW_ASSISTANT_PHOENIX_API_KEY = api_key
    monkeypatch.setenv("PHOENIX_ENDPOINT", "http://unrelated-project")
    monkeypatch.setenv("PHOENIX_API_KEY", "unrelated-key")

    assert baseline._get("/v1/datasets") == []
    assert baseline._graphql("query { probe }", {}) == []

    assert [str(request.url) for request in phoenix_requests] == [
        "http://settings-url/phoenix/v1/datasets",
        "http://settings-url/phoenix/graphql",
    ]
    assert [request.headers.get("authorization") for request in phoenix_requests] == [
        f"Bearer {api_key}" if api_key else None,
    ] * 2
