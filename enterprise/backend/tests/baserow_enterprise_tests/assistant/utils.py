from typing import Any
from unittest.mock import MagicMock

from baserow_enterprise.assistant.deps import AssistantDeps, ToolHelpers
from baserow_enterprise.assistant.model_profiles import ResolvedAssistantModelProfile


def create_fake_tool_helpers(
    model_profile: ResolvedAssistantModelProfile | None = None,
) -> ToolHelpers:
    """Create fresh tool helpers for a test.

    :param model_profile: The resolved profile nested agents should use. A mock
        profile is created when the test does not exercise model behavior.
    :return: A fresh helper container.
    """

    if model_profile is None:
        model_profile = MagicMock(spec=ResolvedAssistantModelProfile)
    return ToolHelpers(
        lambda x: None,
        lambda x: None,
        model_profile=model_profile,
    )


def make_test_ctx(
    user: Any,
    workspace: Any,
    tool_helpers: ToolHelpers | None = None,
    model_profile: ResolvedAssistantModelProfile | None = None,
) -> MagicMock:
    """
    Build a mock ``RunContext[AssistantDeps]`` for unit-testing tool functions.

    :param user: The user on whose behalf the tool runs.
    :param workspace: The workspace that scopes the tool run.
    :param tool_helpers: Optional pre-built helpers for the context.
    :param model_profile: The profile to use when creating default helpers.
    :return: A mock context whose ``deps`` is a real ``AssistantDeps`` instance.
    """

    if tool_helpers is None:
        tool_helpers = create_fake_tool_helpers(model_profile=model_profile)
    ctx = MagicMock()
    ctx.deps = AssistantDeps(
        user=user,
        workspace=workspace,
        tool_helpers=tool_helpers,
    )
    return ctx
