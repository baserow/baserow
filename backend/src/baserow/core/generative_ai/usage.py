"""
Reports the usage of generative AI models, so that plugins can limit or charge
for it. Nothing in here limits or charges anything by itself.

Before a model is prompted, `ai_request_starting` is sent with an `AIUsageScope`
describing who prompts which model with which credentials. A receiver can refuse
the request by raising `AIUsageLimitExceeded`. Once the model has responded,
`ai_request_completed` is sent with the same scope and the tokens that were used.
Any other error of a receiver is logged and never fails the request, so that a
broken plugin can't break the AI features.

Both are sent per model request by `UsageReportingModel`, which wraps every model
that's prompted. The code that knows what the AI is used for, like the AI field or
the AI agent node, describes it with the `ai_usage_context` context manager. It's
picked up by every request made within it.

Code that prompts models from threads that must not query the database, like the
workers of the AI field, marks those requests with
`ai_usage_context(database_allowed=False)`. Before it starts them, it calls
`notify_ai_usage_preparing` from a thread that can, so that receivers can load
what they need to handle those requests without the database.

Plugins can show the reported usage, for example what it cost, through
`Plugin.get_ai_usage_plugin_data`, collected with `get_ai_usage_plugin_data`.
"""

import contextlib
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any, AsyncIterator, Iterable, Iterator, Optional

from django.db import connection, transaction
from django.dispatch import Signal

from asgiref.sync import sync_to_async
from loguru import logger
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.models.wrapper import WrapperModel

from baserow.core.models import Workspace

from .exceptions import GenerativeAIPromptError

# What the AI is used for.
AI_USAGE_FEATURE_AI_FIELD = "ai_field"
AI_USAGE_FEATURE_AI_FORMULA = "ai_formula"
AI_USAGE_FEATURE_AI_NODE = "ai_node"
AI_USAGE_FEATURE_BUILDER_AI_ACTION = "builder_ai_action"
AI_USAGE_FEATURE_AGENT = "agent"
AI_USAGE_FEATURE_ASSISTANT = "kuma"
AI_USAGE_FEATURE_UNKNOWN = "unknown"

# Whose credentials are used to prompt the model.
# A provider configured by an instance admin for the whole instance.
AI_USAGE_KEY_SCOPE_INSTANCE = "instance"
# A provider configured with environment variables.
AI_USAGE_KEY_SCOPE_ENVIRONMENT = "env"
# A provider configured by the workspace itself.
AI_USAGE_KEY_SCOPE_WORKSPACE = "workspace"
# A provider configured in the legacy workspace settings.
AI_USAGE_KEY_SCOPE_LEGACY_WORKSPACE = "legacy_workspace"
# A provider configured in an AI integration of an application.
AI_USAGE_KEY_SCOPE_INTEGRATION = "integration"
# Credentials passed in explicitly, of which the origin isn't known.
AI_USAGE_KEY_SCOPE_EXPLICIT = "explicit"

# The key scopes of credentials that aren't owned by the workspace.
AI_USAGE_SHARED_KEY_SCOPES = frozenset(
    [AI_USAGE_KEY_SCOPE_INSTANCE, AI_USAGE_KEY_SCOPE_ENVIRONMENT]
)

ai_usage_preparing = Signal()
ai_request_starting = Signal()
ai_request_completed = Signal()

_ai_usage_context: ContextVar[dict] = ContextVar("ai_usage_context", default={})


class AIUsageLimitExceeded(GenerativeAIPromptError):
    """
    Raised by an `ai_request_starting` receiver to refuse an AI request, for
    example because the workspace has used up its credits. The message is shown
    to the user.
    """


@dataclass(frozen=True)
class AIUsage:
    """The tokens used by a request to a model."""

    input_tokens: int = 0
    output_tokens: int = 0
    # Part of `input_tokens` that was read from the provider's prompt cache.
    cache_read_tokens: int = 0
    # Part of `input_tokens` that was written to the provider's prompt cache.
    cache_write_tokens: int = 0

    @classmethod
    def from_pydantic_ai(cls, usage: Any) -> "AIUsage":
        """
        Converts the `RunUsage` or `RequestUsage` of pydantic-ai.

        :param usage: The pydantic-ai usage object, or None.
        """

        # Depending on the pydantic-ai object, `usage` is a method or a property.
        if callable(usage):
            usage = usage()
        if usage is None:
            return cls()

        def read(name):
            return int(getattr(usage, name, 0) or 0)

        return cls(
            input_tokens=read("input_tokens"),
            output_tokens=read("output_tokens"),
            cache_read_tokens=read("cache_read_tokens"),
            cache_write_tokens=read("cache_write_tokens"),
        )


@dataclass(frozen=True)
class AIUsageScope:
    """Who prompts which model, for what, and with whose credentials."""

    provider_type: str
    model: str
    key_scope: str
    feature: str = AI_USAGE_FEATURE_UNKNOWN
    workspace: Optional[Workspace] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    # False when the request is made from a thread that must not query the
    # database, so receivers must handle it without, see
    # `notify_ai_usage_preparing`.
    database_allowed: bool = True

    @property
    def uses_shared_key(self) -> bool:
        """
        Whether the credentials aren't owned by the workspace, but by the
        instance.
        """

        return self.key_scope in AI_USAGE_SHARED_KEY_SCOPES

    def with_usage_context(self) -> "AIUsageScope":
        """
        Completes the scope with the current `ai_usage_context`. Its values take
        precedence, except that it can't change resolved credentials or a known
        workspace.
        """

        context = _ai_usage_context.get()
        key_scope = self.key_scope
        if key_scope == AI_USAGE_KEY_SCOPE_EXPLICIT:
            key_scope = context.get("key_scope", key_scope)
        return replace(
            self,
            key_scope=key_scope,
            feature=context.get("feature", self.feature),
            workspace=self.workspace or context.get("workspace"),
            reference_type=context.get("reference_type", self.reference_type),
            reference_id=context.get("reference_id", self.reference_id),
            database_allowed=context.get("database_allowed", self.database_allowed),
        )


@contextlib.contextmanager
def ai_usage_context(
    feature: Optional[str] = None,
    workspace: Optional[Workspace] = None,
    key_scope: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Any = None,
    database_allowed: Optional[bool] = None,
) -> Iterator[None]:
    """
    Describes the AI requests made within the block. Nested blocks extend the
    outer one.

    :param feature: What the AI is used for, one of the `AI_USAGE_FEATURE_*`.
    :param workspace: The workspace on whose behalf the AI is used.
    :param key_scope: The `AI_USAGE_KEY_SCOPE_*` of the credentials, when the code
        resolved them itself and passes them to the model explicitly.
    :param reference_type: What the requests can be attributed to, like
        `automation_workflow_history`.
    :param reference_id: The id of the referenced object.
    :param database_allowed: False when the requests are made from a thread that
        must not query the database, see `notify_ai_usage_preparing`.
    """

    values = {
        key: value
        for key, value in {
            "feature": feature,
            "workspace": workspace,
            "key_scope": key_scope,
            "reference_type": reference_type,
            "reference_id": None if reference_id is None else str(reference_id),
            "database_allowed": database_allowed,
        }.items()
        if value is not None
    }
    token = _ai_usage_context.set({**_ai_usage_context.get(), **values})
    try:
        yield
    finally:
        _ai_usage_context.reset(token)


def _send(signal: Signal, **kwargs) -> None:
    """
    Sends the signal to every receiver, of which a failure never fails the AI
    request, except for a deliberate refusal: the first `AIUsageLimitExceeded` is
    raised after all receivers ran. Other errors are logged, so that a broken
    receiver can't break every AI feature, also not with the workspace's own
    credentials, and its error message never reaches the user.

    :raises AIUsageLimitExceeded: When a receiver refused the request.
    """

    def send():
        return signal.send_robust(sender=None, **kwargs)

    if connection.in_atomic_block:
        # In a savepoint that's rolled back when a receiver failed, so that its
        # failed query can't break the surrounding transaction. Not for a refusal,
        # of which the receiver can have stored something, like a notification.
        with transaction.atomic():
            responses = send()
            transaction.set_rollback(
                any(
                    isinstance(response, Exception)
                    and not isinstance(response, AIUsageLimitExceeded)
                    for _, response in responses
                )
            )
    else:
        responses = send()

    refusal = None
    for receiver, response in responses:
        if isinstance(response, AIUsageLimitExceeded):
            refusal = refusal or response
        elif isinstance(response, Exception):
            logger.opt(exception=response).error(
                "The AI usage receiver {receiver} failed: {exception}",
                receiver=getattr(receiver, "__qualname__", receiver),
                exception=type(response).__name__,
            )
    if refusal is not None:
        raise refusal


def notify_ai_usage_preparing(workspace: Workspace, feature: str) -> None:
    """
    Must be called from a thread that can query the database, before AI requests
    are made on behalf of the workspace from threads that can't. Receivers can
    load what they need to handle those requests, which are marked with
    `ai_usage_context(database_allowed=False)`. A failing receiver is logged.

    :param workspace: The workspace on whose behalf the AI will be used.
    :param feature: What the AI will be used for, one of the `AI_USAGE_FEATURE_*`.
    """

    try:
        _send(ai_usage_preparing, workspace=workspace, feature=feature)
    except AIUsageLimitExceeded:
        # Refusing is only possible per request.
        pass


def notify_ai_request_starting(scope: AIUsageScope) -> None:
    """
    Must be called right before a model is prompted. Only a refusal fails the
    request, any other failure of a receiver is logged.

    :raises AIUsageLimitExceeded: When a receiver refuses the request.
    """

    _send(ai_request_starting, scope=scope)


def notify_ai_request_completed(scope: AIUsageScope, usage: AIUsage) -> None:
    """
    Must be called after a model responded, with the tokens it used. A failing
    receiver never fails the request, because the model already responded.
    """

    try:
        _send(ai_request_completed, scope=scope, usage=usage)
    except AIUsageLimitExceeded:
        # The model already responded, so it can't be refused anymore.
        pass


async def _anotify_ai_request_starting(scope: AIUsageScope) -> None:
    # Receivers can query the database, which needs a thread. Without receivers,
    # skipping the thread keeps requests exactly as fast as without reporting.
    if ai_request_starting.has_listeners():
        await sync_to_async(notify_ai_request_starting)(scope)


async def _anotify_ai_request_completed(scope: AIUsageScope, usage: AIUsage) -> None:
    if ai_request_completed.has_listeners():
        await sync_to_async(notify_ai_request_completed)(scope, usage)


class UsageReportingModel(WrapperModel):
    """
    Reports every request to the wrapped model: `ai_request_starting` before it,
    which can refuse it, and `ai_request_completed` with its tokens after. The
    usage of a request is reported as soon as it's done, so it's also reported
    when the run fails or is stopped later.

    The scope is completed with the `ai_usage_context` of each request, because
    one model can serve several purposes, like an agent and its sub-agents.
    """

    def __init__(self, wrapped: Model, usage_scope: AIUsageScope):
        super().__init__(wrapped)
        self.usage_scope = usage_scope

    async def request(self, *args, **kwargs) -> ModelResponse:
        scope = self.usage_scope.with_usage_context()
        await _anotify_ai_request_starting(scope)
        response = await super().request(*args, **kwargs)
        await _anotify_ai_request_completed(
            scope, AIUsage.from_pydantic_ai(response.usage)
        )
        return response

    @contextlib.asynccontextmanager
    async def request_stream(self, *args, **kwargs) -> AsyncIterator[Any]:
        scope = self.usage_scope.with_usage_context()
        await _anotify_ai_request_starting(scope)
        async with super().request_stream(*args, **kwargs) as streamed_response:
            try:
                yield streamed_response
            finally:
                # Also reported when the consumer stopped reading or failed. Many
                # providers, like OpenAI compatible ones, only send the usage with
                # the last chunk, so a stream stopped early can report 0 tokens.
                await _anotify_ai_request_completed(
                    scope, AIUsage.from_pydantic_ai(streamed_response.usage)
                )


def get_ai_usage_plugin_data(
    reference_type: str, reference_ids: Iterable[Any]
) -> dict[str, dict[str, Any]]:
    """
    Collects what every plugin provides about the AI usage of the referenced
    objects, like what they cost.

    :param reference_type: The reference type the usage was reported with.
    :param reference_ids: The ids the usage was reported with.
    :return: The data by reference id and then by plugin type. A plugin that
        fails is logged and left out.
    """

    from baserow.core.registries import Plugin, plugin_registry

    reference_ids = list(dict.fromkeys(str(id_) for id_ in reference_ids))
    plugin_data: dict[str, dict[str, Any]] = {}
    if not reference_ids:
        return plugin_data
    for plugin in plugin_registry.get_all():
        if type(plugin).get_ai_usage_plugin_data is Plugin.get_ai_usage_plugin_data:
            # Most plugins don't provide any, which saves their savepoint.
            continue
        # The data is only shown alongside, so a failing plugin must not fail what
        # it's shown with, like persisting an agent reply. The savepoint keeps a
        # failed query from breaking a surrounding transaction.
        try:
            with transaction.atomic():
                data_by_id = plugin.get_ai_usage_plugin_data(
                    reference_type, reference_ids
                )
        except Exception:
            logger.exception(
                "The AI usage plugin data of {plugin} failed.", plugin=plugin.type
            )
            continue
        for reference_id, data in data_by_id.items():
            plugin_data.setdefault(str(reference_id), {})[plugin.type] = data
    return plugin_data
