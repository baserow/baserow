import subprocess
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError

import pytest
from opentelemetry.sdk.trace import TracerProvider

from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals import gitinfo, registry
from baserow_enterprise.assistant.evals.judge import JudgeVerdict
from baserow_enterprise.assistant.evals.models import DEFAULT_EVAL_MODEL
from baserow_enterprise.assistant.evals.run import (
    answer_quality,
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


class TestGetGitInfo:
    def test_uses_git_subprocess_when_available(self, monkeypatch):
        monkeypatch.delenv("BASEROW_EVAL_GIT_BRANCH", raising=False)
        monkeypatch.delenv("BASEROW_EVAL_GIT_COMMIT", raising=False)

        def fake_run(args, **kwargs):
            if args[-2:] == ["--abbrev-ref", "HEAD"]:
                return subprocess.CompletedProcess(args, 0, stdout="feature/x\n")
            return subprocess.CompletedProcess(args, 0, stdout="a1b2c3d\n")

        with patch(
            "baserow_enterprise.assistant.evals.gitinfo.subprocess.run",
            side_effect=fake_run,
        ):
            info = gitinfo.get_git_info()

        assert info == {"git_branch": "feature/x", "git_commit": "a1b2c3d"}

    def test_subprocess_takes_precedence_over_env_vars(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_GIT_BRANCH", "env-branch-should-not-be-used")

        with patch(
            "baserow_enterprise.assistant.evals.gitinfo.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout="real-branch\n"),
        ):
            info = gitinfo.get_git_info()

        assert info["git_branch"] == "real-branch"

    def test_falls_back_to_env_vars_when_subprocess_raises(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_GIT_BRANCH", "env-branch")
        monkeypatch.setenv("BASEROW_EVAL_GIT_COMMIT", "env-commit")

        with patch(
            "baserow_enterprise.assistant.evals.gitinfo.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            info = gitinfo.get_git_info()

        assert info == {"git_branch": "env-branch", "git_commit": "env-commit"}

    def test_falls_back_to_env_vars_on_nonzero_exit(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_GIT_BRANCH", "env-branch")
        monkeypatch.delenv("BASEROW_EVAL_GIT_COMMIT", raising=False)

        with patch(
            "baserow_enterprise.assistant.evals.gitinfo.subprocess.run",
            return_value=subprocess.CompletedProcess([], 128, stdout=""),
        ):
            info = gitinfo.get_git_info()

        assert info == {"git_branch": "env-branch"}

    def test_falls_back_to_env_vars_on_timeout(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_GIT_BRANCH", "env-branch")
        monkeypatch.setenv("BASEROW_EVAL_GIT_COMMIT", "env-commit")

        with patch(
            "baserow_enterprise.assistant.evals.gitinfo.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=2),
        ):
            info = gitinfo.get_git_info()

        assert info == {"git_branch": "env-branch", "git_commit": "env-commit"}

    def test_returns_empty_dict_when_nothing_resolves(self, monkeypatch):
        monkeypatch.delenv("BASEROW_EVAL_GIT_BRANCH", raising=False)
        monkeypatch.delenv("BASEROW_EVAL_GIT_COMMIT", raising=False)

        with patch(
            "baserow_enterprise.assistant.evals.gitinfo.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            info = gitinfo.get_git_info()

        assert info == {}


class TestChecklistEvaluator:
    def test_score_is_passed_over_total(self):
        checks = [
            {"name": "a", "passed": True, "hint": ""},
            {"name": "b", "passed": False, "hint": "missing X"},
        ]

        result = checklist({"checks": checks})

        assert result == {"score": 0.5, "explanation": "✗ b — missing X"}

    def test_all_passed_has_no_explanation(self):
        checks = [{"name": "a", "passed": True, "hint": ""}]

        result = checklist({"checks": checks})

        assert result == {"score": 1.0, "explanation": None}

    def test_zero_checks_scores_zero(self):
        result = checklist({"checks": []})

        assert result == {"score": 0.0, "explanation": None}

    def test_skipped_output_scores_empty_result(self):
        """Skipped cases must stay out of aggregates, not score 0.0."""

        result = checklist({"skipped": "knowledge base unavailable"})

        assert result == {}

    def test_multiple_failures_joined_by_newline(self):
        checks = [
            {"name": "a", "passed": False, "hint": "first"},
            {"name": "b", "passed": False, "hint": "second"},
        ]

        result = checklist({"checks": checks})

        assert result["explanation"] == "✗ a — first\n✗ b — second"


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

    def test_skipped_output_scores_empty_result(self):
        """Skipped cases must stay out of aggregates, not count as passing."""

        result = passed({"skipped": "knowledge base unavailable"})

        assert result == {}


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
            "sources": ["a", "b"],
            "sources_count": 2,
            "request_count": 2,
            "duration_s": 1.5,
        }

    def test_sources_are_serialized_to_plain_strings(self):
        case = _make_case("db/case-1")
        output = _make_output(sources=[{"url": "https://x"}, "https://y"])

        with patch(
            "baserow_enterprise.assistant.evals.run.run_case",
            return_value=(output, []),
        ):
            result = run_case_for_experiment(case, "groq:test-model", kb_available=True)

        assert result["sources"] == ["{'url': 'https://x'}", "https://y"]


class TestAnswerQualityEvaluator:
    def test_non_docs_case_scores_empty(self):
        registry.register_case(_make_case("db/case-1"))
        output = {"answer": "the answer", "sources": []}

        result = answer_quality(output, {"case_id": "db/case-1"})

        assert result == {}

    def test_skipped_output_scores_empty(self):
        result = answer_quality(
            {"skipped": "knowledge base unavailable"},
            {"case_id": "docs/case-1", "expected_keywords": ["x"]},
        )

        assert result == {}

    def test_judge_exception_scores_empty_and_warns(self):
        registry.register_case(_make_case("docs/case-1", requires_knowledge_base=True))
        output = {"answer": "the answer", "sources": []}

        with (
            patch(
                "baserow_enterprise.assistant.evals.run.judge_docs_answer",
                side_effect=RuntimeError("judge is down"),
            ),
            patch("baserow_enterprise.assistant.evals.run.logger") as mock_logger,
        ):
            result = answer_quality(
                output, {"case_id": "docs/case-1", "expected_keywords": ["x"]}
            )

        assert result == {}
        mock_logger.warning.assert_called_once()

    def test_unknown_case_id_scores_empty_and_warns(self):
        """A judge failure includes the case being missing from the registry."""

        output = {"answer": "the answer", "sources": []}

        with patch("baserow_enterprise.assistant.evals.run.logger") as mock_logger:
            result = answer_quality(output, {"case_id": "docs/does-not-exist"})

        assert result == {}
        mock_logger.warning.assert_called_once()

    def test_success_returns_score_and_explanation(self):
        registry.register_case(
            _make_case("docs/case-1", prompt="How do I share a view?")
        )
        output = {"answer": "the answer", "sources": ["https://x"]}
        verdict = JudgeVerdict(score=0.75, explanation="Mostly right.")

        with patch(
            "baserow_enterprise.assistant.evals.run.judge_docs_answer",
            return_value=verdict,
        ) as mock_judge:
            result = answer_quality(
                output, {"case_id": "docs/case-1", "expected_keywords": ["share"]}
            )

        mock_judge.assert_called_once_with(
            question="How do I share a view?",
            answer="the answer",
            sources=["https://x"],
            keywords=["share"],
            reference_answer=None,
        )
        assert result == {"score": 0.75, "explanation": "Mostly right."}

    def test_accepts_expected_param_for_phoenix_binding(self):
        """Phoenix's evaluator binder passes the example's output as `expected`."""

        import inspect

        assert "expected" in inspect.signature(answer_quality).parameters

    def test_passes_reference_answer_from_expected_output(self):
        registry.register_case(
            _make_case("docs/case-1", prompt="How do I share a view?")
        )
        output = {"answer": "the answer", "sources": ["https://x"]}
        verdict = JudgeVerdict(score=0.9, explanation="Matches the reference.")

        with patch(
            "baserow_enterprise.assistant.evals.run.judge_docs_answer",
            return_value=verdict,
        ) as mock_judge:
            result = answer_quality(
                output,
                {"case_id": "docs/case-1", "expected_keywords": ["share"]},
                {"reference_answer": "Use the share button."},
            )

        mock_judge.assert_called_once_with(
            question="How do I share a view?",
            answer="the answer",
            sources=["https://x"],
            keywords=["share"],
            reference_answer="Use the share button.",
        )
        assert result == {"score": 0.9, "explanation": "Matches the reference."}

    def test_missing_reference_answer_in_expected_passes_none(self):
        registry.register_case(_make_case("docs/case-1", prompt="q"))
        output = {"answer": "a", "sources": []}
        verdict = JudgeVerdict(score=0.5, explanation="ok")

        with patch(
            "baserow_enterprise.assistant.evals.run.judge_docs_answer",
            return_value=verdict,
        ) as mock_judge:
            answer_quality(output, {"case_id": "docs/case-1"}, {})

        mock_judge.assert_called_once_with(
            question="q", answer="a", sources=[], keywords=[], reference_answer=None
        )

    def test_empty_reference_answer_string_passes_none(self):
        registry.register_case(_make_case("docs/case-1", prompt="q"))
        output = {"answer": "a", "sources": []}
        verdict = JudgeVerdict(score=0.5, explanation="ok")

        with patch(
            "baserow_enterprise.assistant.evals.run.judge_docs_answer",
            return_value=verdict,
        ) as mock_judge:
            answer_quality(output, {"case_id": "docs/case-1"}, {"reference_answer": ""})

        mock_judge.assert_called_once_with(
            question="q", answer="a", sources=[], keywords=[], reference_answer=None
        )

    def test_no_expected_arg_defaults_to_none_reference(self):
        """`expected` is absent when called outside Phoenix's evaluator binding."""

        registry.register_case(_make_case("docs/case-1", prompt="q"))
        output = {"answer": "a", "sources": []}
        verdict = JudgeVerdict(score=0.5, explanation="ok")

        with patch(
            "baserow_enterprise.assistant.evals.run.judge_docs_answer",
            return_value=verdict,
        ) as mock_judge:
            answer_quality(output, {"case_id": "docs/case-1"})

        mock_judge.assert_called_once_with(
            question="q", answer="a", sources=[], keywords=[], reference_answer=None
        )

    def test_requires_knowledge_base_flag_gates_non_docs_prefixed_case(self):
        registry.register_case(
            _make_case("kb/case-1", prompt="q", requires_knowledge_base=True)
        )
        output = {"answer": "the answer", "sources": []}
        verdict = JudgeVerdict(score=1.0, explanation="Good.")

        with patch(
            "baserow_enterprise.assistant.evals.run.judge_docs_answer",
            return_value=verdict,
        ):
            result = answer_quality(
                output,
                {
                    "case_id": "kb/case-1",
                    "requires_knowledge_base": True,
                    "expected_keywords": [],
                },
            )

        assert result == {"score": 1.0, "explanation": "Good."}


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
            patch(
                "baserow_enterprise.assistant.evals.run.prompt_hashes",
                return_value={"kuma-system-prompt": "abc123"},
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.get_git_info",
                return_value={"git_branch": "my-branch", "git_commit": "deadbee"},
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.get_judge_model",
                return_value="groq:openai/gpt-oss-120b",
            ),
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for(
                "kuma-database", "groq:test-model", runs=2, experiment_name="exp-name"
            )

        assert len(client.experiments.run_experiment_calls) == 1
        call_kwargs = client.experiments.run_experiment_calls[0]
        assert call_kwargs["dataset"] is dataset
        assert call_kwargs["evaluators"] == [checklist, passed, answer_quality]
        assert call_kwargs["experiment_name"] == "exp-name"
        assert call_kwargs["experiment_metadata"] == {
            "model": "groq:test-model",
            "judge_model": "groq:openai/gpt-oss-120b",
            "prompts": {"kuma-system-prompt": "abc123"},
            "git_branch": "my-branch",
            "git_commit": "deadbee",
        }
        assert call_kwargs["repetitions"] == 2

    def test_experiment_metadata_omits_git_info_when_unresolved(self):
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
            patch(
                "baserow_enterprise.assistant.evals.run.prompt_hashes",
                return_value={},
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.get_git_info",
                return_value={},
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.get_judge_model",
                return_value="groq:openai/gpt-oss-120b",
            ),
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for("kuma-database", "groq:test-model")

        call_kwargs = client.experiments.run_experiment_calls[0]
        assert call_kwargs["experiment_metadata"] == {
            "model": "groq:test-model",
            "judge_model": "groq:openai/gpt-oss-120b",
            "prompts": {},
        }

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

    def test_foreign_example_without_case_id_is_skipped(self):
        """A UI-added example carries no `case_id`; the task must not KeyError."""

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
            patch("baserow_enterprise.assistant.evals.run.run_case") as mock_run_case,
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for("kuma-database", "groq:test-model")
            task = client.experiments.run_experiment_calls[0]["task"]
            result = task(_ExampleStub(None))

        mock_run_case.assert_not_called()
        assert result == {"skipped": "ui example not yet promoted to code"}

    def test_example_with_unregistered_case_id_is_skipped_not_crashed(self):
        """A stale/removed case_id must not crash the task via a KeyError."""

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
            patch("baserow_enterprise.assistant.evals.run.run_case") as mock_run_case,
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for("kuma-database", "groq:test-model")
            task = client.experiments.run_experiment_calls[0]["task"]
            result = task(_ExampleStub("db/does-not-exist"))

        mock_run_case.assert_not_called()
        assert result == {"skipped": "ui example not yet promoted to code"}


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
            patch(
                "baserow_enterprise.assistant.evals.run.get_assistant_tracer_provider",
                return_value=None,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.prompt_hashes",
                return_value={"kuma-system-prompt": "abc123"},
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.get_git_info",
                return_value={"git_branch": "my-branch", "git_commit": "deadbee"},
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.get_judge_model",
                return_value="groq:openai/gpt-oss-120b",
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
        assert create_kwargs["experiment_metadata"] == {
            "model": "groq:test-model",
            "judge_model": "groq:openai/gpt-oss-120b",
            "case_ids": ["db/case-1"],
            "prompts": {"kuma-system-prompt": "abc123"},
            "git_branch": "my-branch",
            "git_commit": "deadbee",
        }

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

    def test_uses_assistant_tracer_provider_when_available(self):
        """Root spans nest under the agent's own spans, not a throwaway tracer."""

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
        assistant_provider = TracerProvider()

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
                "baserow_enterprise.assistant.evals.run.get_assistant_tracer_provider",
                return_value=assistant_provider,
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.trace.get_tracer"
            ) as mock_global_get_tracer,
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for(
                "kuma-database", "groq:test-model", case_ids=["db/case-1"]
            )

        mock_global_get_tracer.assert_not_called()
        trace_id = client.experiments.log_run_calls[0]["trace_id"]
        assert isinstance(trace_id, str)
        assert len(trace_id) == 32
        int(trace_id, 16)

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
        # Regression: a skipped case must not be scored, poisoning aggregates.
        assert client.experiments.log_evaluation_calls == []

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

    def test_foreign_example_in_dataset_does_not_break_case_lookup(self):
        """A UI-added example with no case_id must not crash building the lookup."""

        registry.register_case(_make_case("db/case-1"))
        examples = [
            {
                "id": "database/creates-simple-table",
                "node_id": "RGF0YXNldEV4YW1wbGU6MQ==",
                "input": {},
                "output": {},
                "metadata": {"case_id": "db/case-1"},
            },
            {
                "id": "ui-added-id",
                "node_id": "ui-added-id",
                "input": {"prompt": "a UI question"},
                "output": {},
                "metadata": {},
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
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for(
                "kuma-database", "groq:test-model", case_ids=["db/case-1"]
            )

        assert len(client.experiments.log_run_calls) == 1

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

    def test_logs_answer_quality_evaluation_for_docs_case(self):
        registry.register_case(
            _make_case(
                "docs/case-1",
                dataset="kuma-docs",
                requires_knowledge_base=True,
                prompt="How do I share a view?",
            )
        )
        examples = [
            {
                "id": "docs/case-1",
                "node_id": "RGF0YXNldEV4YW1wbGU6MQ==",
                "input": {},
                "output": {},
                "metadata": {
                    "case_id": "docs/case-1",
                    "requires_knowledge_base": True,
                    "expected_keywords": ["share"],
                },
            }
        ]
        dataset = _FakeDataset(examples)
        client = _FakeClient(dataset)
        verdict = JudgeVerdict(score=0.9, explanation="Good and grounded.")

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
                return_value=(_make_output(answer="Use the share button."), []),
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.judge_docs_answer",
                return_value=verdict,
            ) as mock_judge,
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for("kuma-docs", "groq:test-model", case_ids=["docs/case-1"])

        mock_judge.assert_called_once()
        eval_names = {c["name"] for c in client.experiments.log_evaluation_calls}
        assert eval_names == {"checklist", "passed", "answer_quality"}
        aq_call = next(
            c
            for c in client.experiments.log_evaluation_calls
            if c["name"] == "answer_quality"
        )
        assert aq_call["score"] == 0.9
        assert aq_call["explanation"] == "Good and grounded."

    def test_reference_answer_from_example_output_passed_to_judge(self):
        """The subset path must bind the example's `output`, same as `run_experiment`."""

        registry.register_case(
            _make_case(
                "docs/case-1",
                dataset="kuma-docs",
                requires_knowledge_base=True,
                prompt="How do I share a view?",
            )
        )
        examples = [
            {
                "id": "docs/case-1",
                "node_id": "RGF0YXNldEV4YW1wbGU6MQ==",
                "input": {},
                "output": {"reference_answer": "Use the share button."},
                "metadata": {
                    "case_id": "docs/case-1",
                    "requires_knowledge_base": True,
                    "expected_keywords": ["share"],
                },
            }
        ]
        dataset = _FakeDataset(examples)
        client = _FakeClient(dataset)
        verdict = JudgeVerdict(score=0.9, explanation="Matches the reference.")

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
                return_value=(_make_output(answer="Use the share button."), []),
            ),
            patch(
                "baserow_enterprise.assistant.evals.run.judge_docs_answer",
                return_value=verdict,
            ) as mock_judge,
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for("kuma-docs", "groq:test-model", case_ids=["docs/case-1"])

        mock_judge.assert_called_once_with(
            question="How do I share a view?",
            answer="Use the share button.",
            sources=[],
            keywords=["share"],
            reference_answer="Use the share button.",
        )

    def test_non_docs_case_in_subset_does_not_log_answer_quality(self):
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
            patch(
                "baserow_enterprise.assistant.evals.run.judge_docs_answer"
            ) as mock_judge,
        ):
            mock_kb_cls.return_value.can_search.return_value = True

            run_experiment_for(
                "kuma-database", "groq:test-model", case_ids=["db/case-1"]
            )

        mock_judge.assert_not_called()
        eval_names = {c["name"] for c in client.experiments.log_evaluation_calls}
        assert eval_names == {"checklist", "passed"}


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
