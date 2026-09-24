"""
Centralized model configuration and per-model settings for all agents.

Contains:
- ``resolve_assistant_model()``: Freezes model selection for one logical request.
- ``ResolvedAssistantModelProfile``: The frozen selection, able to build the model.
- ``check_lm_ready_or_raise()``: Cached live compatibility check of that selection.
- ``get_model_settings(model, role)``: Per-model, per-role settings.

Usage::

    from baserow_enterprise.assistant.model_profiles import (
        ORCHESTRATOR, resolve_assistant_model,
    )

    profile = resolve_assistant_model()
    model = profile.create_model()
    settings = profile.get_settings(ORCHESTRATOR)
"""

import time
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Literal

from django.conf import settings

from loguru import logger
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_TEST_MAX_TOKENS,
    AI_PROVIDER_TEST_TIMEOUT_SECONDS,
    AI_PROVIDER_TYPES,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderModel
from baserow.core.ai_provider.resolution import (
    ScopedAIProviderState,
    get_ai_provider_state,
)
from baserow.core.cache import global_cache
from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled
from baserow.core.generative_ai.capabilities import test_model_text_and_tool_calling
from baserow.core.generative_ai.generative_ai_model_types import (
    sanitize_google_model_settings,
)
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.models import Workspace
from baserow_enterprise.assistant.exceptions import (
    AssistantConfiguredModelNotAvailableError,
    AssistantModelDisabledError,
    AssistantModelNotSupportedError,
)
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.retrying_model import RetryingModel

_MODEL_READINESS_CACHE_TIMEOUT_SECONDS = 300
_MODEL_READINESS_FAILURE_CACHE_TIMEOUT_SECONDS = 30
_process_local_model_readiness_cache: dict[str, tuple[float, bool]] = {}
_process_local_model_readiness_cache_lock = Lock()
_process_local_model_readiness_probe_locks: dict[str, Lock] = {}

# ---------------------------------------------------------------------------
# Agent roles
# ---------------------------------------------------------------------------

ORCHESTRATOR = "orchestrator"
SUBAGENT = "subagent"  # database, builder, automations
UTILITY = "utility"  # formula, fixer (precision-oriented)
SAMPLE = "sample"  # sample row generation (creative)
TITLE = "title"  # title generation
SUGGESTIONS = "suggestions"  # onboarding prompt suggestions (creative)

# ---------------------------------------------------------------------------
# Per-model profiles
# ---------------------------------------------------------------------------

# Fallback when the model isn't in _MODEL_PROFILES
_DEFAULT_PROFILE: dict[str, ModelSettings] = {
    ORCHESTRATOR: {
        "temperature": 0.3,
        "timeout": 30,
        "parallel_tool_calls": False,
        "max_tokens": 16384,
    },
    SUBAGENT: {
        "temperature": 0.3,
        "timeout": 20,
        "parallel_tool_calls": False,
        "max_tokens": 16384,
    },
    UTILITY: {
        "temperature": 0.1,
        "timeout": 20,
    },
    SAMPLE: {
        "temperature": 0.5,
        "timeout": 20,
    },
    TITLE: {
        "temperature": 0.7,
        # Gemini rejects deadlines under 10s, so stay clear of the floor.
        "timeout": 15,
        "max_tokens": AssistantChat.TITLE_MAX_LENGTH,
    },
    SUGGESTIONS: {
        "temperature": 0.6,
        "timeout": 30,
        "max_tokens": 4096,
    },
}

# GPT-OSS rejects ``reasoning_format``, so it keeps the provider-agnostic defaults.
_MODEL_PROFILES: dict[str, dict[str, ModelSettings]] = {}


def get_model_settings(model: str, role: str) -> ModelSettings:
    """
    Return the ModelSettings for a given model string and agent role.

    The model string is the pydantic-ai format (e.g. ``"groq:openai/gpt-oss-120b"``).
    We match on the last path segment (e.g. ``"gpt-oss-120b"``) to find the profile.

    For the ``ORCHESTRATOR`` role the temperature defaults to the value of
    ``BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE`` (if set), allowing
    operators to override it without changing code.

    :param model: pydantic-ai model string (e.g. ``"groq:openai/gpt-oss-120b"``).
    :param role: One of ORCHESTRATOR, SUBAGENT, UTILITY, SAMPLE, TITLE, SUGGESTIONS.
    :return: A ModelSettings dict suitable for ``model_settings=`` parameter.
    """

    # Extract model name after the provider prefix:
    #   "groq:openai/gpt-oss-120b" -> "gpt-oss-120b"
    #   "ollama:kimi-2.5:cloud"    -> "kimi-2.5:cloud"
    provider, sep, after_provider = model.partition(":")
    model_name = after_provider.rsplit("/", 1)[-1] if sep else model

    profile = _MODEL_PROFILES.get(model_name, _DEFAULT_PROFILE)
    result = dict(profile.get(role, _DEFAULT_PROFILE.get(role, {})))

    # Allow the env-var-driven setting to override the orchestrator temperature.
    if role == ORCHESTRATOR:
        env_temp = getattr(
            settings, "BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE", None
        )
        if env_temp is not None:
            result["temperature"] = env_temp

    if provider in {"google", "google-gla", "google-cloud", "google-vertex"}:
        result = sanitize_google_model_settings(after_provider, result)

    return result


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


# pydantic-ai's infer_model only accepts its own provider names.
_PROVIDER_PREFIX_ALIASES = {"google-gla": "google", "google-vertex": "google-cloud"}

AssistantModelSource = Literal["legacy", "database", "explicit"]
_DatabaseModelSource = Literal["legacy", "database", "disabled"]


def _normalize_model_string(value: str) -> str:
    """Normalize a legacy model identifier for Pydantic AI.

    :param value: The configured model identifier.
    :return: The normalized ``provider:model`` identifier.
    """

    slash_pos = value.find("/")
    colon_pos = value.find(":")
    if slash_pos != -1 and (colon_pos == -1 or slash_pos < colon_pos):
        value = value.replace("/", ":", 1)
    elif slash_pos == -1 and colon_pos == -1:
        value = f"openai:{value}"

    provider, sep, rest = value.partition(":")
    if sep and provider in _PROVIDER_PREFIX_ALIASES:
        value = f"{_PROVIDER_PREFIX_ALIASES[provider]}:{rest}"

    return value


def _get_database_model(
    workspace: Workspace | None = None,
    state: ScopedAIProviderState | None = None,
) -> tuple[AIProviderModel | None, _DatabaseModelSource]:
    """Resolve Kuma's database-backed model from one provider-state snapshot.

    :param workspace: The workspace scope, or ``None`` for the instance scope.
    :param state: An already-loaded provider state for the requested scope.
    :return: The selected model, if any, and its resolution source.
    """

    if not feature_flag_is_enabled(FF_AI_PROVIDERS):
        return None, "legacy"

    if state is None:
        state = get_ai_provider_state(workspace)
    settings_list = AIProviderHandler.list_feature_settings(workspace, state=state)
    setting = next(
        (
            value
            for value in settings_list
            if value["feature_type"] == AI_PROVIDER_FEATURE_KUMA
        ),
        None,
    )
    if setting is None or setting["state"] in {"unconfigured", "invalid"}:
        return None, "legacy"
    if setting["state"] == "disabled":
        return None, "disabled"
    return setting["model"], "database"


@dataclass(frozen=True, slots=True)
class ResolvedAssistantModelProfile:
    """Immutable model resolution used throughout one logical assistant request."""

    model_string: str
    source: AssistantModelSource
    workspace: Workspace | None
    database_model: AIProviderModel | None

    def create_model(self) -> Model:
        """Create the retrying model represented by this snapshot.

        :return: A retrying Pydantic AI model using the resolved credentials.
        """

        if self.database_model is None:
            return RetryingModel(self.model_string)

        provider = self.database_model.provider_config
        model_type = generative_ai_model_type_registry.get(provider.provider_type)
        settings_override = {
            name: provider.extra_settings.get(name)
            for name in AI_PROVIDER_TYPES[provider.provider_type]["extra_settings"]
        }
        settings_override.update(
            {
                "api_key": provider.api_key,
                "models": [self.database_model.model_identifier],
            }
        )
        resolved = model_type.get_ai_model(
            self.database_model.model_identifier,
            workspace=self.workspace,
            settings_override=settings_override,
        )
        return RetryingModel(resolved)

    def get_settings(self, role: str) -> ModelSettings:
        """Return settings for this resolved model and agent role.

        :param role: The assistant agent role requesting settings.
        :return: A fresh model-settings mapping for the role.
        """

        return get_model_settings(self.model_string, role)


def resolve_assistant_model(
    workspace: Workspace | None = None,
    model: str | None = None,
) -> ResolvedAssistantModelProfile:
    """Resolve one immutable assistant model profile for a logical request.

    :param workspace: The workspace scope, or ``None`` for the instance scope.
    :param model: An explicit model identifier that bypasses persisted selection.
    :return: The resolved model profile and provider-state snapshot.
    :raises AssistantModelDisabledError: If Kuma is explicitly disabled.
    """

    if model is not None:
        return ResolvedAssistantModelProfile(
            model_string=_normalize_model_string(model),
            source="explicit",
            workspace=workspace,
            database_model=None,
        )

    state = (
        get_ai_provider_state(workspace)
        if feature_flag_is_enabled(FF_AI_PROVIDERS)
        else None
    )
    database_model, source = _get_database_model(workspace, state=state)
    if source == "disabled":
        raise AssistantModelDisabledError("Kuma is disabled for this scope.")

    if database_model is not None:
        model_string = (
            f"{database_model.provider_config.provider_type}:"
            f"{database_model.model_identifier}"
        )
        resolved_source: AssistantModelSource = "database"
    else:
        model_string = _normalize_model_string(
            settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL
        )
        resolved_source = "legacy"

    return ResolvedAssistantModelProfile(
        model_string=model_string,
        source=resolved_source,
        workspace=workspace,
        database_model=database_model,
    )


def get_model_string(
    model: str | None = None, workspace: Workspace | None = None
) -> str:
    """Return the normalized model string for compatibility with existing callers.

    :param model: An explicit model identifier, or None to resolve the configured model.
    :param workspace: The workspace scope, or None for the instance scope.
    :return: A model string compatible with Pydantic AI.
    """

    return resolve_assistant_model(workspace=workspace, model=model).model_string


def _model_readiness_cache_key(
    model_profile: ResolvedAssistantModelProfile,
) -> str:
    """Build the readiness cache key for a resolved profile.

    :param model_profile: The immutable model profile being tested.
    :return: The cache key bound to the model and credential revision.
    """

    database_model = model_profile.database_model
    if database_model is None:
        fingerprint = f"legacy:{model_profile.model_string}"
    else:
        provider = database_model.provider_config
        fingerprint = ":".join(
            (
                "database",
                str(database_model.id),
                database_model.model_identifier,
                str(provider.id),
                provider.updated_on.isoformat(),
            )
        )
    digest = sha256(fingerprint.encode()).hexdigest()
    return f"assistant:model-readiness:{digest}"


def _check_process_local_model_ready(
    model_profile: ResolvedAssistantModelProfile,
) -> bool:
    """Validate and briefly throttle process-local readiness probes.

    :param model_profile: The immutable legacy or explicit model profile.
    :return: ``True`` when the model passes the compatibility probe.
    :raises RuntimeError: If a recent compatibility probe failed.
    """

    model_string = model_profile.model_string

    with _process_local_model_readiness_cache_lock:
        probe_lock = _process_local_model_readiness_probe_locks.setdefault(
            model_string, Lock()
        )

    # Only one thread in this process should probe a model at a time. Waiting callers
    # re-check the cache after acquiring the lock and reuse its result.
    with probe_lock:
        now = time.monotonic()
        with _process_local_model_readiness_cache_lock:
            cached = _process_local_model_readiness_cache.get(model_string)
            if cached is not None and cached[0] <= now:
                del _process_local_model_readiness_cache[model_string]
                cached = None
        if cached is not None:
            if cached[1]:
                return True
            raise RuntimeError("The model compatibility check recently failed.")

        try:
            model = model_profile.create_model()
            test_model_text_and_tool_calling(
                model, max_tokens=AI_PROVIDER_TEST_MAX_TOKENS
            )
        except Exception:
            # Start the failure TTL after the potentially full-timeout probe finishes.
            failure_expires_at = (
                time.monotonic() + _MODEL_READINESS_FAILURE_CACHE_TIMEOUT_SECONDS
            )
            with _process_local_model_readiness_cache_lock:
                _process_local_model_readiness_cache[model_string] = (
                    failure_expires_at,
                    False,
                )
            raise

        with _process_local_model_readiness_cache_lock:
            # Legacy credentials come from the environment and cannot change while
            # the process lives, so a success never needs re-probing here.
            _process_local_model_readiness_cache[model_string] = (float("inf"), True)
        return True


def _clear_process_local_model_readiness_cache() -> None:
    """Clear process-local readiness results and probe locks.

    :return: None.
    """

    with _process_local_model_readiness_cache_lock:
        _process_local_model_readiness_cache.clear()
        _process_local_model_readiness_probe_locks.clear()


def check_lm_ready_or_raise(
    workspace: Workspace | None = None,
    *,
    model_profile: ResolvedAssistantModelProfile | None = None,
) -> None:
    """Check that the exact model profile for a request is usable.

    :param workspace: The workspace scope when no profile was resolved yet.
    :param model_profile: The already-resolved profile for this logical request.
    :return: None.
    :raises AssistantModelNotSupportedError: If the resolved model is unavailable.
    :raises AssistantConfiguredModelNotAvailableError: If a database-backed model is
        unavailable.
    """

    model_profile = model_profile or resolve_assistant_model(workspace=workspace)
    source = model_profile.source
    model_string = model_profile.model_string
    try:
        if source in {"legacy", "explicit"}:
            # Process-local construction: another pod's success proves nothing here.
            _check_process_local_model_ready(model_profile)
        else:

            def check_database_model() -> bool:
                """Run the database-model compatibility probe.

                :return: Whether the exact resolved model passed the probe.
                """

                try:
                    model = model_profile.create_model()
                    test_model_text_and_tool_calling(
                        model, max_tokens=AI_PROVIDER_TEST_MAX_TOKENS
                    )
                except Exception as exc:
                    provider = model_profile.database_model.provider_config
                    logger.warning(
                        "[assistant] Compatibility probe failed for model '{}': {}",
                        model_string,
                        AIProviderHandler.sanitize_test_error(
                            exc,
                            AIProviderHandler.secret_values(
                                provider.api_key, provider.extra_settings
                            ),
                        ),
                    )
                    return False
                else:
                    return True

            is_ready = global_cache.get(
                _model_readiness_cache_key(model_profile),
                default=check_database_model,
                timeout=lambda ready: (
                    _MODEL_READINESS_CACHE_TIMEOUT_SECONDS
                    if ready
                    else _MODEL_READINESS_FAILURE_CACHE_TIMEOUT_SECONDS
                ),
                lock_timeout=AI_PROVIDER_TEST_TIMEOUT_SECONDS + 10,
            )
            if not is_ready:
                raise RuntimeError("The model compatibility check failed.")
    except AssistantModelNotSupportedError:
        raise
    except Exception as e:
        exception_class = (
            AssistantConfiguredModelNotAvailableError
            if source == "database"
            else AssistantModelNotSupportedError
        )
        raise exception_class(
            f"The model '{model_string}' is not supported or accessible: {e}"
        ) from e
