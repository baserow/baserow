from unittest.mock import MagicMock

from baserow_enterprise.assistant.deps import AssistantDeps, ToolHelpers


def create_fake_tool_helpers() -> ToolHelpers:
    """Create a fresh ToolHelpers instance for testing."""
    return ToolHelpers(lambda x: None, lambda x: None)


def make_test_ctx(user, workspace, tool_helpers=None):
    """
    Build a mock ``RunContext[AssistantDeps]`` for unit-testing tool functions.

    Returns a ``MagicMock`` whose ``.deps`` attribute is a real
    ``AssistantDeps`` instance.
    """

    if tool_helpers is None:
        tool_helpers = create_fake_tool_helpers()
    ctx = MagicMock()
    ctx.deps = AssistantDeps(
        user=user,
        workspace=workspace,
        tool_helpers=tool_helpers,
    )
    return ctx
