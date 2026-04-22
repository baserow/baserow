import asyncio
import logging
import os

from django.conf import settings

import pytest

from baserow.config.settings.test import TEST_ENV_VARS

# Expose API keys from TEST_ENV_FILE to os.environ so that LLM provider
# SDKs (which read os.getenv() at import/construction time) can find them.
# test.py already parses TEST_ENV_FILE via dotenv_values but deliberately
# does NOT inject non-allowlisted keys into os.environ.  We bridge that
# gap here for the small set of keys the eval suite needs.
_API_KEY_NAMES = ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
for _k in _API_KEY_NAMES:
    if (_v := TEST_ENV_VARS.get(_k)) and not os.environ.get(_k):
        os.environ[_k] = _v


_EVALS_DIR = os.path.dirname(__file__)


def _evals_explicitly_requested(config):
    """Return True when the user intentionally targeted eval tests."""

    # ``-m eval`` on the command line
    marker_expr = config.getoption("-m", default="")
    if "eval" in marker_expr:
        return True

    # User pointed pytest at an eval file/directory (e.g. VSCode test runner)
    for arg in config.args:
        if os.path.abspath(arg).startswith(_EVALS_DIR):
            return True

    return False


def pytest_collection_modifyitems(config, items):
    """Skip eval tests unless explicitly requested (``-m eval`` or by path).

    Also wires up ``EVAL_RETRIES``: when set to a positive integer, every eval
    test is automatically marked with ``pytest.mark.retry(N)`` so that failing
    tests are re-run up to N times.  A test that passes on retry is a flake
    (LLM non-determinism); one that fails all N retries is a consistent bug.
    """

    if not _evals_explicitly_requested(config):
        skip_eval = pytest.mark.skip(reason="eval tests only run with -m eval")
        for item in items:
            if item.get_closest_marker("eval"):
                item.add_marker(skip_eval)
        return

    eval_retries = int(os.environ.get("EVAL_RETRIES", "0"))
    if eval_retries > 0:
        for item in items:
            if item.get_closest_marker("eval"):
                item.add_marker(pytest.mark.retry(eval_retries))


def pytest_generate_tests(metafunc):
    """Auto-parametrize tests that use the ``eval_model`` fixture."""

    if "eval_model" in metafunc.fixturenames:
        from .eval_utils import get_eval_model

        model_str = get_eval_model()
        models = [m.strip() for m in model_str.split(",") if m.strip()]
        metafunc.parametrize("eval_model", models, scope="session")


@pytest.fixture(scope="session")
def synced_knowledge_base(django_db_blocker):
    """
    Sync the knowledge base once per pytest session if not already populated.

    With ``--reuse-db`` the DB persists across sessions, so the (slow)
    embedding + sync step only runs the very first time.  Subsequent
    sessions detect that the KB is already populated and return immediately.
    """

    with django_db_blocker.unblock():
        if not getattr(settings, "BASEROW_EMBEDDINGS_API_URL", ""):
            return  # No embeddings server → nothing to sync

        from baserow_enterprise.assistant.tools.search_user_docs.handler import (
            KnowledgeBaseHandler,
        )

        handler = KnowledgeBaseHandler()

        if handler.can_search():
            return  # Already populated (e.g. --reuse-db from a previous run)

        if not handler.can_have_knowledge_base():
            return  # pgvector not available

        print("\n[eval] Syncing knowledge base (first run — this may take a while)...")
        handler.sync_knowledge_base()
        print("[eval] Knowledge base sync complete.")


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
