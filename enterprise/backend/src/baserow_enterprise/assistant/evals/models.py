from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalModel:
    id: str
    label: str
    api_key_env: str


EVAL_MODELS: tuple[EvalModel, ...] = (
    EvalModel(
        "groq:openai/gpt-oss-120b", "GPT-OSS 120B (Groq, default)", "GROQ_API_KEY"
    ),
    EvalModel("groq:openai/gpt-oss-20b", "GPT-OSS 20B (Groq)", "GROQ_API_KEY"),
    EvalModel("groq:qwen/qwen3.6-27b", "Qwen3.6 27B (Groq)", "GROQ_API_KEY"),
    EvalModel("openai:gpt-5-mini", "GPT-5 mini (OpenAI)", "OPENAI_API_KEY"),
    EvalModel("openai:gpt-5.4-mini", "GPT-5.4 mini (OpenAI)", "OPENAI_API_KEY"),
    EvalModel("openai:gpt-5.6-luna", "GPT-5.6 Luna (OpenAI)", "OPENAI_API_KEY"),
    EvalModel("openai:gpt-5.6-terra", "GPT-5.6 Terra (OpenAI)", "OPENAI_API_KEY"),
    EvalModel(
        "google:gemini-3.6-flash",
        "Gemini 3.6 Flash (Google)",
        "GOOGLE_API_KEY",
    ),
    EvalModel(
        "google:gemini-3.7-flash",
        "Gemini 3.7 Flash (Google)",
        "GOOGLE_API_KEY",
    ),
    EvalModel(
        "anthropic:claude-sonnet-5",
        "Claude Sonnet 5 (Anthropic)",
        "ANTHROPIC_API_KEY",
    ),
    EvalModel(
        "anthropic:claude-haiku-4-5-20251001",
        "Claude Haiku 4.5 (Anthropic)",
        "ANTHROPIC_API_KEY",
    ),
)

DEFAULT_EVAL_MODEL = EVAL_MODELS[0].id


def available_models() -> list[EvalModel]:
    """Return the models whose API key env var is set in the environment."""

    return [m for m in EVAL_MODELS if os.environ.get(m.api_key_env)]
