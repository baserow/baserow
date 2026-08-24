from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

import pytest

from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals import registry
from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.sync import (
    build_dataset_examples,
    sync_datasets,
)
from baserow_enterprise.assistant.evals.types import EvalCase


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setattr(registry, "_cases", {})
    monkeypatch.setattr(registry, "_scenarios", {})


def _noop_checks(case, scenario, output):
    return []


def _make_case(case_id: str, **overrides) -> EvalCase:
    defaults = dict(
        dataset="kuma-database",
        prompt="do the thing",
        scenario="empty-workspace",
        checks=_noop_checks,
        mode=AgentMode.DATABASE,
        max_iters=15,
        max_tool_errors=0,
        requires_knowledge_base=False,
        metadata={},
    )
    defaults.update(overrides)
    return EvalCase(id=case_id, **defaults)


class TestBuildDatasetExamples:
    def test_shape_and_prompt_passthrough(self):
        case = _make_case("db/case-1", prompt="list my tables")

        examples = build_dataset_examples([case])

        assert examples == [
            {
                "id": "db/case-1",
                "input": {"prompt": "list my tables"},
                "output": {},
                "metadata": {
                    "case_id": "db/case-1",
                    "scenario": "empty-workspace",
                    "mode": "database",
                    "max_iters": 15,
                    "max_tool_errors": 0,
                    "requires_knowledge_base": False,
                    "check_names": [],
                },
            }
        ]

    def test_mode_uses_agent_mode_value_string(self):
        case = _make_case("app/case-1", mode=AgentMode.APPLICATION)

        examples = build_dataset_examples([case])

        assert examples[0]["metadata"]["mode"] == "application"

    def test_check_names_read_from_metadata_when_present(self):
        case = _make_case(
            "db/case-2", metadata={"check_names": ["answer_mentions_table"]}
        )

        examples = build_dataset_examples([case])

        assert examples[0]["metadata"]["check_names"] == ["answer_mentions_table"]

    def test_check_names_defaults_to_empty_list(self):
        case = _make_case("db/case-3")

        examples = build_dataset_examples([case])

        assert examples[0]["metadata"]["check_names"] == []

    def test_examples_sorted_by_case_id(self):
        case_b = _make_case("db/case-b")
        case_a = _make_case("db/case-a")

        examples = build_dataset_examples([case_b, case_a])

        assert [e["id"] for e in examples] == ["db/case-a", "db/case-b"]


class _FakeDatasetsAPI:
    def __init__(self):
        self.calls: list[tuple[str, list[dict]]] = []

    def create_dataset(self, *, name, examples):
        self.calls.append((name, examples))


class _FakeClient:
    def __init__(self):
        self.datasets = _FakeDatasetsAPI()


class TestSyncDatasets:
    def test_calls_create_dataset_once_per_dataset_with_full_example_list(self):
        registry.register_case(_make_case("db/case-a", dataset="kuma-database"))
        registry.register_case(_make_case("db/case-b", dataset="kuma-database"))
        registry.register_case(_make_case("kb/case-a", dataset="kuma-knowledge-base"))
        client = _FakeClient()

        counts = sync_datasets(client)

        assert counts == {"kuma-database": 2, "kuma-knowledge-base": 1}
        called_names = {name for name, _ in client.datasets.calls}
        assert called_names == {"kuma-database", "kuma-knowledge-base"}

        db_examples = next(
            ex for name, ex in client.datasets.calls if name == "kuma-database"
        )
        assert [e["id"] for e in db_examples] == ["db/case-a", "db/case-b"]

    def test_no_datasets_registered_syncs_nothing(self):
        client = _FakeClient()

        counts = sync_datasets(client)

        assert counts == {}
        assert client.datasets.calls == []


class TestGetPhoenixClient:
    def test_raises_when_no_url_configured(self, settings, monkeypatch):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = ""
        monkeypatch.delenv("PHOENIX_ENDPOINT", raising=False)

        with pytest.raises(ImproperlyConfigured, match="ai-assistant-tracing.md"):
            get_phoenix_client()

    def test_builds_client_from_settings(self, settings, monkeypatch):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://phoenix:6006"
        settings.BASEROW_ASSISTANT_PHOENIX_API_KEY = ""
        monkeypatch.delenv("PHOENIX_ENDPOINT", raising=False)
        monkeypatch.delenv("PHOENIX_API_KEY", raising=False)

        with patch("phoenix.client.Client") as mock_client_cls:
            get_phoenix_client()

        mock_client_cls.assert_called_once_with(
            base_url="http://phoenix:6006", api_key=None
        )

    def test_env_vars_take_precedence_over_settings(self, settings, monkeypatch):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://settings-url"
        settings.BASEROW_ASSISTANT_PHOENIX_API_KEY = "settings-key"
        monkeypatch.setenv("PHOENIX_ENDPOINT", "http://env-url")
        monkeypatch.setenv("PHOENIX_API_KEY", "env-key")

        with patch("phoenix.client.Client") as mock_client_cls:
            get_phoenix_client()

        mock_client_cls.assert_called_once_with(
            base_url="http://env-url", api_key="env-key"
        )
