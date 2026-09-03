from unittest.mock import MagicMock, patch

import pytest

from baserow_enterprise.assistant.evals.judge import (
    DEFAULT_JUDGE_MODEL,
    JudgeVerdict,
    get_judge_model,
    judge_docs_answer,
)


class TestGetJudgeModel:
    def test_defaults_to_groq_gpt_oss_120b(self, monkeypatch):
        monkeypatch.delenv("BASEROW_EVAL_JUDGE_MODEL", raising=False)

        assert get_judge_model() == "groq:openai/gpt-oss-120b"
        assert get_judge_model() == DEFAULT_JUDGE_MODEL

    def test_reads_env_override(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_JUDGE_MODEL", "openai:gpt-5-mini")

        assert get_judge_model() == "openai:gpt-5-mini"


class TestJudgeVerdict:
    def test_accepts_score_in_range(self):
        verdict = JudgeVerdict(score=0.5, explanation="ok")

        assert verdict.score == 0.5
        assert verdict.explanation == "ok"

    def test_rejects_score_above_one(self):
        with pytest.raises(ValueError):
            JudgeVerdict(score=1.5, explanation="ok")

    def test_rejects_score_below_zero(self):
        with pytest.raises(ValueError):
            JudgeVerdict(score=-0.1, explanation="ok")


class TestJudgeDocsAnswer:
    def test_runs_agent_with_judge_model_and_returns_verdict(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_JUDGE_MODEL", "groq:test-judge-model")
        verdict = JudgeVerdict(score=0.8, explanation="Mostly correct.")

        with patch(
            "baserow_enterprise.assistant.evals.judge.docs_answer_judge.run_sync",
            return_value=MagicMock(output=verdict),
        ) as mock_run_sync:
            result = judge_docs_answer(
                question="How do I share a view?",
                answer="Use the share button.",
                sources=["https://baserow.io/docs/x"],
                keywords=["share", "public"],
            )

        assert result is verdict
        mock_run_sync.assert_called_once()
        call_args, call_kwargs = mock_run_sync.call_args
        assert call_kwargs["model"] == "groq:test-judge-model"
        prompt = call_args[0]
        assert "How do I share a view?" in prompt
        assert "Use the share button." in prompt
        assert "https://baserow.io/docs/x" in prompt
        assert "share" in prompt

    def test_includes_reference_answer_when_given(self, monkeypatch):
        monkeypatch.delenv("BASEROW_EVAL_JUDGE_MODEL", raising=False)
        verdict = JudgeVerdict(score=0.9, explanation="Matches the reference.")

        with patch(
            "baserow_enterprise.assistant.evals.judge.docs_answer_judge.run_sync",
            return_value=MagicMock(output=verdict),
        ) as mock_run_sync:
            judge_docs_answer(
                question="How do I compute a date diff?",
                answer="Use date_diff('day', [Start], [End]).",
                sources=[],
                keywords=["date_diff"],
                reference_answer="Use the date_diff function.",
            )

        prompt = mock_run_sync.call_args[0][0]
        assert "Use the date_diff function." in prompt
        assert "reference" in prompt.lower()

    def test_omits_reference_section_when_not_given(self, monkeypatch):
        monkeypatch.delenv("BASEROW_EVAL_JUDGE_MODEL", raising=False)
        verdict = JudgeVerdict(score=0.5, explanation="ok")

        with patch(
            "baserow_enterprise.assistant.evals.judge.docs_answer_judge.run_sync",
            return_value=MagicMock(output=verdict),
        ) as mock_run_sync:
            judge_docs_answer(question="q", answer="a", sources=[], keywords=[])

        prompt = mock_run_sync.call_args[0][0]
        assert "reference" not in prompt.lower()

    def test_propagates_agent_exceptions(self, monkeypatch):
        monkeypatch.delenv("BASEROW_EVAL_JUDGE_MODEL", raising=False)

        with patch(
            "baserow_enterprise.assistant.evals.judge.docs_answer_judge.run_sync",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                judge_docs_answer(question="q", answer="a", sources=[], keywords=[])
