import asyncio
import logging
from unittest.mock import MagicMock, Mock, patch

import pytest
from udspy.module.callbacks import ModuleContext

from baserow_enterprise.assistant.assistant import ToolHelpers
from baserow_enterprise.assistant.tools.builder.tools import (
    get_page_content_tool_factory,
)

fake_tool_helpers = ToolHelpers(lambda x: None, lambda x: None)


@pytest.fixture(autouse=True)
def suppress_asyncio_stopiteration_error():
    """
    Suppress the 'StopIteration interacts badly with generators' asyncio error.

    This is a known Python issue when generators raise StopIteration in contexts
    where asyncio futures are involved. The error is harmless but noisy.
    """
    original_handler = None

    def custom_exception_handler(loop, context):
        exception = context.get("exception")
        if isinstance(exception, TypeError) and "StopIteration" in str(exception):
            return  # Suppress this specific error
        if original_handler:
            original_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    try:
        loop = asyncio.get_event_loop()
        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(custom_exception_handler)
    except RuntimeError:
        pass  # No event loop

    # Also suppress the log message
    asyncio_logger = logging.getLogger("asyncio")
    original_level = asyncio_logger.level
    asyncio_logger.setLevel(logging.CRITICAL)

    yield

    asyncio_logger.setLevel(original_level)
    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(original_handler)
    except RuntimeError:
        pass


@pytest.fixture
def mock_generate_formulas():
    """
    Mock the udspy.Predict call inside get_formula_generator so that
    generate_formulas() returns deterministic formulas without calling the LLM.

    The formula validation step (resolve_formula) still runs against the real
    BuilderFormulaContext, so invalid formulas will be caught.

    Usage:
        def test_something(mock_generate_formulas):
            mock_generate_formulas({"value": "get('user.email')"})
    """

    patchers = []

    def setup(formulas: dict[str, str]):
        mock_result = MagicMock()
        mock_result.generated_formulas = formulas
        mock_predict_instance = MagicMock(return_value=mock_result)
        patcher = patch(
            "baserow_enterprise.assistant.tools.shared.formula_utils.udspy.Predict",
            return_value=mock_predict_instance,
        )
        patcher.start()
        patchers.append(patcher)

    yield setup

    for p in patchers:
        p.stop()


@pytest.fixture
def create_elements_tool():
    """
    Returns a function (user, workspace) -> create_elements tool callable.

    Extracts the create_elements tool from the page content tool factory
    so tests can call it directly.
    """

    def _get_tool(user, workspace):
        factory = get_page_content_tool_factory(user, workspace, fake_tool_helpers)
        tools_upgrade = factory()

        mock_module = Mock()
        mock_module._tools = []
        mock_module.init_module = Mock()
        tools_upgrade(ModuleContext(module=mock_module))

        added_tools = mock_module.init_module.call_args[1]["tools"]
        tool = next(t for t in added_tools if t.name == "create_elements")
        return tool.func

    return _get_tool
