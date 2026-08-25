from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command

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

    def test_output_includes_reference_answer_when_case_sets_one(self):
        case = _make_case("docs/case-1", reference_answer="Use date_diff().")

        examples = build_dataset_examples([case])

        assert examples[0]["output"] == {"reference_answer": "Use date_diff()."}

    def test_output_is_empty_dict_when_no_reference_answer(self):
        case = _make_case("docs/case-1")

        examples = build_dataset_examples([case])

        assert examples[0]["output"] == {}

    def test_case_metadata_is_merged_into_example_metadata(self):
        case = _make_case(
            "docs/case-1", metadata={"expected_keywords": ["share", "public"]}
        )

        examples = build_dataset_examples([case])

        assert examples[0]["metadata"]["expected_keywords"] == ["share", "public"]

    def test_fixed_keys_win_over_case_metadata_on_collision(self):
        case = _make_case("db/case-1", metadata={"case_id": "not-the-real-id"})

        examples = build_dataset_examples([case])

        assert examples[0]["metadata"]["case_id"] == "db/case-1"


class _FakeDataset:
    def __init__(self, examples):
        self.examples = examples


class _FakeDatasetsAPI:
    def __init__(self, existing: dict[str, list[dict]] | None = None):
        self.calls: list[tuple[str, list[dict]]] = []
        self.get_dataset_calls: list[str] = []
        self._existing = existing or {}

    def create_dataset(self, *, name, examples):
        self.calls.append((name, examples))

    def get_dataset(self, *, dataset):
        self.get_dataset_calls.append(dataset)
        if dataset not in self._existing:
            raise ValueError(f"Dataset not found: {dataset}")
        return _FakeDataset(self._existing[dataset])


class _FakeClient:
    def __init__(self, existing: dict[str, list[dict]] | None = None):
        self.datasets = _FakeDatasetsAPI(existing)


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


class TestSyncDatasetsMergesForeignExamples:
    """UI-added ("foreign") examples must survive the wholesale upload."""

    def test_foreign_example_preserved_with_stable_id(self):
        registry.register_case(_make_case("db/case-a", dataset="kuma-database"))
        foreign_example = {
            "id": "RGF0YXNldEV4YW1wbGU6NQ==",
            "node_id": "RGF0YXNldEV4YW1wbGU6NQ==",
            "input": {"prompt": "a UI-added question"},
            "output": {},
            "metadata": {"note": "added from the trace view"},
        }
        client = _FakeClient({"kuma-database": [foreign_example]})

        counts = sync_datasets(client)

        assert counts == {"kuma-database": 2}
        _, examples = client.datasets.calls[0]
        ids = [e["id"] for e in examples]
        assert "db/case-a" in ids
        assert "RGF0YXNldEV4YW1wbGU6NQ==" in ids

        kept = next(e for e in examples if e["id"] == "RGF0YXNldEV4YW1wbGU6NQ==")
        assert "node_id" not in kept
        assert kept["input"] == {"prompt": "a UI-added question"}
        assert kept["metadata"] == {"note": "added from the trace view"}

    def test_code_owned_example_no_longer_in_registry_is_still_deleted(self):
        """A code-owned example (has case_id) is never treated as foreign."""

        registry.register_case(_make_case("db/case-a", dataset="kuma-database"))
        stale_code_owned = {
            "id": "old-id",
            "node_id": "old-id",
            "input": {"prompt": "stale"},
            "output": {},
            "metadata": {"case_id": "db/removed-case"},
        }
        client = _FakeClient({"kuma-database": [stale_code_owned]})

        counts = sync_datasets(client)

        assert counts == {"kuma-database": 1}
        _, examples = client.datasets.calls[0]
        assert [e["id"] for e in examples] == ["db/case-a"]

    def test_adopted_example_dropped_by_matching_prompt(self):
        registry.register_case(
            _make_case("db/case-a", dataset="kuma-database", prompt="do the thing")
        )
        foreign_example = {
            "id": "RGF0YXNldEV4YW1wbGU6OQ==",
            "node_id": "RGF0YXNldEV4YW1wbGU6OQ==",
            "input": {"prompt": "  do the thing  "},
            "output": {},
            "metadata": {},
        }
        client = _FakeClient({"kuma-database": [foreign_example]})

        counts = sync_datasets(client)

        assert counts == {"kuma-database": 1}
        _, examples = client.datasets.calls[0]
        assert [e["id"] for e in examples] == ["db/case-a"]

    def test_dataset_not_found_falls_back_to_plain_upload(self):
        registry.register_case(_make_case("db/case-a", dataset="kuma-database"))
        client = _FakeClient()

        counts = sync_datasets(client)

        assert counts == {"kuma-database": 1}
        assert client.datasets.get_dataset_calls == ["kuma-database"]
        _, examples = client.datasets.calls[0]
        assert [e["id"] for e in examples] == ["db/case-a"]

    def test_logs_code_foreign_and_adopted_counts(self):
        registry.register_case(
            _make_case("db/case-a", dataset="kuma-database", prompt="do the thing")
        )
        foreign_kept = {
            "id": "kept-id",
            "node_id": "kept-id",
            "input": {"prompt": "a different question"},
            "output": {},
            "metadata": {},
        }
        foreign_adopted = {
            "id": "adopted-id",
            "node_id": "adopted-id",
            "input": {"prompt": "do the thing"},
            "output": {},
            "metadata": {},
        }
        client = _FakeClient({"kuma-database": [foreign_kept, foreign_adopted]})

        with patch("baserow_enterprise.assistant.evals.sync.logger") as mock_logger:
            sync_datasets(client)

        message = mock_logger.info.call_args[0][0]
        assert message == (
            "Synced Phoenix dataset 'kuma-database': 1 code cases, "
            "1 foreign kept, 1 adopted, 0 references preserved (2 total)"
        )


class TestSyncDatasetsPreservesLiveReferenceAnswers:
    """A UI-curated `output.reference_answer` must survive a resync."""

    def test_live_reference_answer_preserved_when_code_case_has_none(self):
        registry.register_case(_make_case("docs/case-a", dataset="kuma-docs"))
        live_example = {
            "id": "docs/case-a",
            "node_id": "RGF0YXNldEV4YW1wbGU6NQ==",
            "input": {"prompt": "do the thing"},
            "output": {"reference_answer": "Curated in the UI."},
            "metadata": {"case_id": "docs/case-a"},
        }
        client = _FakeClient({"kuma-docs": [live_example]})

        sync_datasets(client)

        _, examples = client.datasets.calls[0]
        synced = next(e for e in examples if e["id"] == "docs/case-a")
        assert synced["output"] == {"reference_answer": "Curated in the UI."}

    def test_code_reference_answer_wins_over_live_output(self):
        registry.register_case(
            _make_case(
                "docs/case-a", dataset="kuma-docs", reference_answer="Code says this."
            )
        )
        live_example = {
            "id": "docs/case-a",
            "node_id": "RGF0YXNldEV4YW1wbGU6NQ==",
            "input": {"prompt": "do the thing"},
            "output": {"reference_answer": "Curated in the UI."},
            "metadata": {"case_id": "docs/case-a"},
        }
        client = _FakeClient({"kuma-docs": [live_example]})

        sync_datasets(client)

        _, examples = client.datasets.calls[0]
        synced = next(e for e in examples if e["id"] == "docs/case-a")
        assert synced["output"] == {"reference_answer": "Code says this."}

    def test_live_empty_output_is_not_preserved(self):
        registry.register_case(_make_case("docs/case-a", dataset="kuma-docs"))
        live_example = {
            "id": "docs/case-a",
            "node_id": "RGF0YXNldEV4YW1wbGU6NQ==",
            "input": {"prompt": "do the thing"},
            "output": {},
            "metadata": {"case_id": "docs/case-a"},
        }
        client = _FakeClient({"kuma-docs": [live_example]})

        sync_datasets(client)

        _, examples = client.datasets.calls[0]
        synced = next(e for e in examples if e["id"] == "docs/case-a")
        assert synced["output"] == {}

    def test_foreign_example_output_is_unaffected(self):
        """The preserve rule only applies to code-owned examples."""

        registry.register_case(_make_case("docs/case-a", dataset="kuma-docs"))
        foreign_example = {
            "id": "RGF0YXNldEV4YW1wbGU6OQ==",
            "node_id": "RGF0YXNldEV4YW1wbGU6OQ==",
            "input": {"prompt": "a UI-added question"},
            "output": {"reference_answer": "Should not leak onto code case."},
            "metadata": {},
        }
        client = _FakeClient({"kuma-docs": [foreign_example]})

        sync_datasets(client)

        _, examples = client.datasets.calls[0]
        synced = next(e for e in examples if e["id"] == "docs/case-a")
        assert synced["output"] == {}

    def test_logs_preserved_count(self):
        registry.register_case(_make_case("docs/case-a", dataset="kuma-docs"))
        live_example = {
            "id": "docs/case-a",
            "node_id": "RGF0YXNldEV4YW1wbGU6NQ==",
            "input": {"prompt": "do the thing"},
            "output": {"reference_answer": "Curated in the UI."},
            "metadata": {"case_id": "docs/case-a"},
        }
        client = _FakeClient({"kuma-docs": [live_example]})

        with patch("baserow_enterprise.assistant.evals.sync.logger") as mock_logger:
            sync_datasets(client)

        message = mock_logger.info.call_args[0][0]
        assert "1 references preserved" in message


@pytest.mark.django_db
class TestSyncAssistantEvalsCommand:
    def test_prints_dataset_and_prompt_sync_results(self):
        with (
            patch(
                "baserow_enterprise.management.commands.sync_assistant_evals.load_all"
            ) as mock_load_all,
            patch(
                "baserow_enterprise.management.commands.sync_assistant_evals."
                "get_phoenix_client"
            ) as mock_get_client,
            patch(
                "baserow_enterprise.management.commands.sync_assistant_evals."
                "sync_datasets",
                return_value={"kuma-database": 2},
            ) as mock_sync_datasets,
            patch(
                "baserow_enterprise.management.commands.sync_assistant_evals."
                "sync_prompts",
                return_value={"kuma-system-prompt": "created"},
            ) as mock_sync_prompts,
        ):
            call_command("sync_assistant_evals")

        mock_load_all.assert_called_once()
        mock_sync_datasets.assert_called_once_with(mock_get_client.return_value)
        mock_sync_prompts.assert_called_once_with(mock_get_client.return_value)

    def test_output_includes_prompt_statuses(self, capsys):
        with (
            patch(
                "baserow_enterprise.management.commands.sync_assistant_evals.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.sync_assistant_evals."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.sync_assistant_evals."
                "sync_datasets",
                return_value={},
            ),
            patch(
                "baserow_enterprise.management.commands.sync_assistant_evals."
                "sync_prompts",
                return_value={"kuma-system-prompt": "unchanged"},
            ),
        ):
            call_command("sync_assistant_evals")

        assert "kuma-system-prompt: unchanged" in capsys.readouterr().out


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
