from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError

import pytest
from opentelemetry.sdk.trace import TracerProvider

from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals import registry
from baserow_enterprise.assistant.evals.models import DEFAULT_EVAL_MODEL
from baserow_enterprise.assistant.evals.run import (
    checklist,
    passed,
    run_case_for_experiment,
    run_experiment_for,
)
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
)


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


def _make_output(**overrides) -> EvalRunOutput:
    defaults = dict(
        answer="the answer",
        messages=[],
        tool_calls=["list_tables"],
        tool_error_count=0,
        tool_error_hint="",
        sources=[],
        request_count=2,
        duration_s=1.5,
    )
    defaults.update(overrides)
    return EvalRunOutput(**defaults)


class TestChecklistEvaluator:
    def test_score_is_passed_over_total(self):
        checks = [
            {"name": "a", "passed": True, "hint": ""},
            {"name": "b", "passed": False, "hint": "missing X"},
        ]

        score, explanation = checklist({"checks": checks})

        assert score == 0.5
        assert explanation == "✗ b — missing X"

    def test_all_passed_has_empty_explanation(self):
        checks = [{"name": "a", "passed": True, "hint": ""}]

        score, explanation = checklist({"checks": checks})

        assert score == 1.0
        assert explanation == ""

    def test_zero_checks_scores_zero(self):
        score, explanation = checklist({"checks": []})

        assert score == 0.0
        assert explanation == ""

    def test_missing_checks_key_scores_zero(self):
        score, explanation = checklist({"skipped": "knowledge base unavailable"})

        assert score == 0.0
        assert explanation == ""

    def test_multiple_failures_joined_by_newline(self):
        checks = [
            {"name": "a", "passed": False, "hint": "first"},
            {"name": "b", "passed": False, "hint": "second"},
        ]

        _, explanation = checklist({"checks": checks})

        assert explanation == "✗ a — first\n✗ b — second"


class TestPassedEvaluator:
    def test_true_when_all_checks_passed(self):
        checks = [
            {"name": "tool_errors_within_budget", "passed": True, "hint": ""},
            {"name": "a", "passed": True, "hint": ""},
        ]

        assert passed({"checks": checks}) is True

    def test_false_when_any_check_failed(self):
        checks = [
            {"name": "tool_errors_within_budget", "passed": True, "hint": ""},
            {"name": "b", "passed": False, "hint": "bad"},
        ]

        assert passed({"checks": checks}) is False

    def test_true_when_no_checks(self):
        assert passed({"checks": []}) is True


class TestRunCaseForExperiment:
    def test_skips_kb_gated_case_when_kb_unavailable(self):
        case = _make_case("kb/case-1", requires_knowledge_base=True)

        with patch("baserow_enterprise.assistant.evals.run.run_case") as mock_run_case:
            result = run_case_for_experiment(
                case, "groq:test-model", kb_available=False
            )

        mock_run_case.assert_not_called()
        assert result == {"skipped": "knowledge base unavailable"}

    def test_runs_kb_gated_case_when_kb_available(self):
        case = _make_case("kb/case-1", requires_knowledge_base=True)
        output = _make_output()
        checks = [CheckResult(name="tool_errors_within_budget", passed=True)]

        with patch(
            "baserow_enterprise.assistant.evals.run.run_case",
            return_value=(output, checks),
        ) as mock_run_case:
            result = run_case_for_experiment(case, "groq:test-model", kb_available=True)

        mock_run_case.assert_called_once_with(case, "groq:test-model")
        assert result["answer"] == "the answer"

    def test_non_kb_case_runs_regardless_of_kb_availability(self):
        case = _make_case("db/case-1", requires_knowledge_base=False)
        output = _make_output()

        with patch(
            "baserow_enterprise.assistant.evals.run.run_case",
            return_value=(output, []),
        ) as mock_run_case:
            run_case_for_experiment(case, "groq:test-model", kb_available=False)

        mock_run_case.assert_called_once()

    def test_output_dict_shape(self):
        case = _make_case("db/case-1")
        output = _make_output(sources=["a", "b"])
        checks = [
            CheckResult(name="tool_errors_within_budget", passed=True),
            CheckResult(name="answer_mentions_table", passed=False, hint="no mention"),
        ]

        with patch(
            "baserow_enterprise.assistant.evals.run.run_case",
            return_value=(output, checks),
        ):
            result = run_case_for_experiment(case, "groq:test-model", kb_available=True)

        assert result == {
            "answer": "the answer",
            "tool_calls": ["list_tables"],
            "tool_error_count": 0,
            "checks": [
                {"name": "tool_errors_within_budget", "passed": True, "hint": ""},
                {
                    "name": "answer_mentions_table",
                    "passed": False,
                    "hint": "no mention",
                },
            ],
            "score": 0.5,
            "passed": False,
            "sources_count": 2,
            "request_count": 2,
            "duration_s": 1.5,
        }


class _FakeExperimentsAPI:
    def __init__(self):
        self.run_experiment_calls: list[dict] = []
        self.create_calls: list[dict] = []
        self.log_run_calls: list[dict] = []
        self.log_evaluation_calls: list[dict] = []
        self.get_experiment_calls: list[dict] = []
        self._run_id_counter = 0

    def run_experiment(self, **kwargs):
        self.run_experiment_calls.append(kwargs)
        return {"experiment_id": "exp-1", "dataset_id": "ds-1"}

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return {"id": "exp-2", "dataset_id": kwargs["dataset_id"]}

    def log_run(self, **kwargs):
        self.log_run_calls.append(kwargs)
        self._run_id_counter += 1
        return {"id": f"run-{self._run_id_counter}"}

    def log_evaluation(self, **kwargs):
        self.log_evaluation_calls.append(kwargs)

    def get_experiment(self, **kwargs):
        self.get_experiment_calls.append(kwargs)
        return {"experiment_id": kwargs["experiment_id"], "dataset_id": "ds-1"}

    def get_experiment_url(self, **kwargs):
        return f"http://phoenix/datasets/{kwargs['dataset_id']}/experiments/{kwargs['experiment_id']}"


class _FakeDataset:
    def __init__(self, examples):
        self.id = "ds-1"
        self.version_id = "v1"
        self.examples = examples


class _FakeDatasetsAPI:
    def __init__(self, dataset):
        self._dataset = dataset
        self.get_dataset_calls: list[dict] = []

    def get_dataset(self, **kwargs):
        self.get_dataset_calls.append(kwargs)
        return self._dataset


class _FakeClient:
    def __init__(self, dataset):
        self.experiments = _FakeExperimentsAPI()
        self.datasets = _FakeDatasetsAPI(dataset)


class _ExampleStub:
    def __init__(self, case_id):
        self.metadata = {"case_id": case_id}


class TestRunExperimentForFullDataset:
    def test_calls_run_experiment_with_dataset_and_evaluators(self):
        registry.register_case(_make_case("db/case-1"))
        dataset = _FakeDataset([])
        client = _FakeClient(dataset)

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"
            ) as mock_kb_cls,
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for(
                "kuma-database", "groq:test-model", runs=2, experiment_name="exp-name"
            )

        assert len(client.experiments.run_experiment_calls) == 1
        call_kwargs = client.experiments.run_experiment_calls[0]
        assert call_kwargs["dataset"] is dataset
        assert call_kwargs["evaluators"] == [checklist, passed]
        assert call_kwargs["experiment_name"] == "exp-name"
        assert call_kwargs["experiment_metadata"] == {"model": "groq:test-model"}
        assert call_kwargs["repetitions"] == 2

    def test_task_closure_resolves_case_by_metadata_and_runs_it(self):
        registry.register_case(_make_case("db/case-1"))
        dataset = _FakeDataset([])
        client = _FakeClient(dataset)
        output = _make_output()

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"
            ) as mock_kb_cls,
            patch(
                "baserow_enterprise.assistant.evals.run.run_case",
                return_value=(output, []),
            ) as mock_run_case,
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for("kuma-database", "groq:test-model")
            task = client.experiments.run_experiment_calls[0]["task"]
            result = task(_ExampleStub("db/case-1"))

        mock_run_case.assert_called_once()
        assert result["answer"] == "the answer"

    def test_kb_gated_case_skipped_via_task_closure(self):
        registry.register_case(_make_case("kb/case-1", requires_knowledge_base=True))
        dataset = _FakeDataset([])
        client = _FakeClient(dataset)

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"
            ) as mock_kb_cls,
            patch("baserow_enterprise.assistant.evals.run.run_case") as mock_run_case,
        ):
            mock_kb_cls.return_value.can_search.return_value = False

            run_experiment_for("kuma-knowledge-base", "groq:test-model")
            task = client.experiments.run_experiment_calls[0]["task"]
            result = task(_ExampleStub("kb/case-1"))

        mock_run_case.assert_not_called()
        assert result == {"skipped": "knowledge base unavailable"}

    def test_kb_availability_checked_once_per_experiment(self):
        registry.register_case(_make_case("db/case-1"))
        registry.register_case(_make_case("kb/case-2", requires_knowledge_base=True))
        dataset = _FakeDataset([])
        client = _FakeClient(dataset)

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"
            ) as mock_kb_cls,
            patch(
                "baserow_enterprise.assistant.evals.run.run_case",
                return_value=(_make_output(), []),
            ),
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for("kuma-database", "groq:test-model")
            task = client.experiments.run_experiment_calls[0]["task"]
            task(_ExampleStub("db/case-1"))
            task(_ExampleStub("kb/case-2"))

        mock_kb_cls.return_value.can_search.assert_called_once()


class TestRunExperimentForCaseSubset:
    def test_creates_experiment_and_logs_runs_and_evaluations(self):
        registry.register_case(_make_case("db/case-1"))
        registry.register_case(_make_case("db/case-2"))
        examples = [
            {
                "id": "database/creates-simple-table",
                "node_id": "RGF0YXNldEV4YW1wbGU6MQ==",
                "input": {},
                "output": {},
                "metadata": {"case_id": "db/case-1"},
            },
            {
                "id": "database/other-case",
                "node_id": "RGF0YXNldEV4YW1wbGU6Mg==",
                "input": {},
                "output": {},
                "metadata": {"case_id": "db/case-2"},
            },
        ]
        dataset = _FakeDataset(examples)
        client = _FakeClient(dataset)

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"
            ) as mock_kb_cls,
            patch(
                "baserow_enterprise.assistant.evals.run.run_case",
                return_value=(_make_output(), []),
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.trace.get_tracer",
                return_value=TracerProvider().get_tracer("test"),
            ),
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            result = run_experiment_for(
                "kuma-database", "groq:test-model", case_ids=["db/case-1"]
            )

        assert len(client.experiments.create_calls) == 1
        create_kwargs = client.experiments.create_calls[0]
        assert create_kwargs["dataset_id"] == "ds-1"
        assert create_kwargs["dataset_version_id"] == "v1"
        assert create_kwargs["repetitions"] == 1

        assert len(client.experiments.log_run_calls) == 1
        run_kwargs = client.experiments.log_run_calls[0]
        # Regression: the server's log_run wants the example's GlobalID
        # (node_id), not the custom sync-time id, which lives in "id".
        assert run_kwargs["dataset_example_id"] == "RGF0YXNldEV4YW1wbGU6MQ=="
        assert run_kwargs["dataset_example_id"] != "database/creates-simple-table"
        assert run_kwargs["repetition_number"] == 1
        assert run_kwargs["experiment_id"] == "exp-2"

        trace_id = run_kwargs["trace_id"]
        assert isinstance(trace_id, str)
        assert len(trace_id) == 32
        int(trace_id, 16)

        assert len(client.experiments.log_evaluation_calls) == 2
        eval_names = {c["name"] for c in client.experiments.log_evaluation_calls}
        assert eval_names == {"checklist", "passed"}
        for evaluation in client.experiments.log_evaluation_calls:
            assert evaluation["experiment_run_id"] == "run-1"

        # Result is the re-fetched experiment, not the create() snapshot.
        assert len(client.experiments.get_experiment_calls) == 1
        assert client.experiments.get_experiment_calls[0]["experiment_id"] == "exp-2"
        assert result == {"experiment_id": "exp-2", "dataset_id": "ds-1"}

    def test_runs_multiple_repetitions(self):
        registry.register_case(_make_case("db/case-1"))
        examples = [
            {
                "id": "database/creates-simple-table",
                "node_id": "RGF0YXNldEV4YW1wbGU6MQ==",
                "input": {},
                "output": {},
                "metadata": {"case_id": "db/case-1"},
            }
        ]
        dataset = _FakeDataset(examples)
        client = _FakeClient(dataset)

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"
            ) as mock_kb_cls,
            patch(
                "baserow_enterprise.assistant.evals.run.run_case",
                return_value=(_make_output(), []),
            ),
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for(
                "kuma-database", "groq:test-model", case_ids=["db/case-1"], runs=3
            )

        assert len(client.experiments.log_run_calls) == 3
        assert [c["repetition_number"] for c in client.experiments.log_run_calls] == [
            1,
            2,
            3,
        ]

    def test_kb_gated_case_in_subset_is_skipped(self):
        registry.register_case(_make_case("kb/case-1", requires_knowledge_base=True))
        examples = [
            {
                "id": "knowledge-base/answers-from-docs",
                "node_id": "RGF0YXNldEV4YW1wbGU6MQ==",
                "input": {},
                "output": {},
                "metadata": {"case_id": "kb/case-1"},
            }
        ]
        dataset = _FakeDataset(examples)
        client = _FakeClient(dataset)

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"
            ) as mock_kb_cls,
            patch("baserow_enterprise.assistant.evals.run.run_case") as mock_run_case,
        ):
            mock_kb_cls.return_value.can_search.return_value = False

            run_experiment_for(
                "kuma-knowledge-base", "groq:test-model", case_ids=["kb/case-1"]
            )

        mock_run_case.assert_not_called()
        logged_output = client.experiments.log_run_calls[0]["output"]
        assert logged_output == {"skipped": "knowledge base unavailable"}

    def test_dataset_example_id_falls_back_to_id_when_node_id_absent(self):
        """Older/unsynced servers may not deliver a ``node_id`` at all."""

        registry.register_case(_make_case("db/case-1"))
        examples = [
            {
                "id": "database/creates-simple-table",
                "input": {},
                "output": {},
                "metadata": {"case_id": "db/case-1"},
            }
        ]
        dataset = _FakeDataset(examples)
        client = _FakeClient(dataset)

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"
            ) as mock_kb_cls,
            patch(
                "baserow_enterprise.assistant.evals.run.run_case",
                return_value=(_make_output(), []),
            ),
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for(
                "kuma-database", "groq:test-model", case_ids=["db/case-1"]
            )

        run_kwargs = client.experiments.log_run_calls[0]
        assert run_kwargs["dataset_example_id"] == "database/creates-simple-table"

    def test_unknown_case_id_raises_clear_error(self):
        registry.register_case(_make_case("db/case-1"))
        examples = [
            {
                "id": "database/creates-simple-table",
                "node_id": "RGF0YXNldEV4YW1wbGU6MQ==",
                "input": {},
                "output": {},
                "metadata": {"case_id": "db/case-1"},
            }
        ]
        dataset = _FakeDataset(examples)
        client = _FakeClient(dataset)

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.get_phoenix_client",
                return_value=client,
            ),
            patch("baserow_enterprise.assistant.evals.run.KnowledgeBaseHandler"),
        ):
            with pytest.raises(ValueError, match="just b eval-sync"):
                run_experiment_for(
                    "kuma-database", "groq:test-model", case_ids=["db/case-missing"]
                )


@pytest.mark.django_db
class TestRunAssistantEvalsCommand:
    def test_requires_dataset_or_case(self):
        with pytest.raises(CommandError, match="--dataset is required"):
            call_command("run_assistant_evals")

    def test_dataset_arg_runs_full_dataset(self):
        with (
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "setup_instrumentation"
            ) as mock_setup,
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "run_experiment_for",
                return_value={"experiment_id": "exp-1", "dataset_id": "ds-1"},
            ) as mock_run,
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "get_phoenix_client"
            ) as mock_client,
        ):
            mock_client.return_value.experiments.get_experiment_url.return_value = (
                "http://phoenix/x"
            )

            call_command("run_assistant_evals", "--dataset", "kuma-database")

        mock_setup.assert_called_once()
        mock_run.assert_called_once_with(
            dataset_name="kuma-database",
            model=DEFAULT_EVAL_MODEL,
            case_ids=None,
            runs=1,
            experiment_name=None,
        )

    def test_model_runs_and_name_are_forwarded(self):
        with (
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "run_experiment_for",
                return_value={"id": "exp-2", "dataset_id": "ds-1"},
            ) as mock_run,
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "get_phoenix_client"
            ),
        ):
            call_command(
                "run_assistant_evals",
                "--dataset",
                "kuma-database",
                "--model",
                "openai:gpt-5-mini",
                "--runs",
                "3",
                "--name",
                "my-experiment",
            )

        mock_run.assert_called_once_with(
            dataset_name="kuma-database",
            model="openai:gpt-5-mini",
            case_ids=None,
            runs=3,
            experiment_name="my-experiment",
        )

    def test_case_repeatable_and_resolves_dataset_from_registry(self):
        registry.register_case(_make_case("db/case-1", dataset="kuma-database"))
        registry.register_case(_make_case("db/case-2", dataset="kuma-database"))

        with (
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "run_experiment_for",
                return_value={"id": "exp-2", "dataset_id": "ds-1"},
            ) as mock_run,
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "get_phoenix_client"
            ),
        ):
            call_command(
                "run_assistant_evals",
                "--case",
                "db/case-1",
                "--case",
                "db/case-2",
            )

        mock_run.assert_called_once_with(
            dataset_name="kuma-database",
            model=DEFAULT_EVAL_MODEL,
            case_ids=["db/case-1", "db/case-2"],
            runs=1,
            experiment_name=None,
        )

    def test_case_ids_spanning_multiple_datasets_without_dataset_raises(self):
        registry.register_case(_make_case("db/case-1", dataset="kuma-database"))
        registry.register_case(_make_case("kb/case-1", dataset="kuma-knowledge-base"))

        with (
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "setup_instrumentation"
            ),
            pytest.raises(CommandError, match="multiple datasets"),
        ):
            call_command(
                "run_assistant_evals",
                "--case",
                "db/case-1",
                "--case",
                "kb/case-1",
            )

    def test_explicit_dataset_overrides_case_lookup(self):
        registry.register_case(_make_case("db/case-1", dataset="kuma-database"))

        with (
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "run_experiment_for",
                return_value={"id": "exp-2", "dataset_id": "ds-1"},
            ) as mock_run,
            patch(
                "baserow_enterprise.management.commands.run_assistant_evals."
                "get_phoenix_client"
            ),
        ):
            call_command(
                "run_assistant_evals",
                "--dataset",
                "explicit-dataset",
                "--case",
                "db/case-1",
            )

        mock_run.assert_called_once_with(
            dataset_name="explicit-dataset",
            model=DEFAULT_EVAL_MODEL,
            case_ids=["db/case-1"],
            runs=1,
            experiment_name=None,
        )
