import asyncio
import logging
import os

from django.conf import settings

import pytest
from dotenv import dotenv_values

# Load API keys from TEST_ENV_FILE into os.environ BEFORE any LLM clients
# are imported, because some providers read os.getenv() at module import time.
_test_env_file = os.environ.get("TEST_ENV_FILE", "")
if _test_env_file:
    # Resolve the same way as backend/src/baserow/config/settings/test.py:
    # BASE_DIR (= .../config) + ../../../ + TEST_ENV_FILE
    # We replicate this by finding the baserow config package location.
    import baserow.config.settings as _settings_pkg

    _settings_dir = os.path.dirname(os.path.abspath(_settings_pkg.__file__))
    # _settings_dir = .../backend/src/baserow/config/settings
    # test.py uses dirname(dirname(__file__)) = .../config, then ../../../
    # So from _settings_dir we need ../../../../
    _env_path = os.path.normpath(
        os.path.join(_settings_dir, f"../../../../{_test_env_file}")
    )
    for _k, _v in dotenv_values(_env_path).items():
        if _k not in os.environ and _v is not None:
            os.environ[_k] = _v


# Fallback: also try loading .vscode/env from the repo root if GROQ_API_KEY
# is not yet set.  This makes ``pytest -m eval`` work out of the box when
# running from the worktree without needing to set TEST_ENV_FILE.
if "GROQ_API_KEY" not in os.environ:
    _repo_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "../../../../../../..")
    )
    _vscode_env = os.path.join(_repo_root, ".vscode", "env")
    if os.path.isfile(_vscode_env):
        for _k, _v in dotenv_values(_vscode_env).items():
            if _k not in os.environ and _v is not None:
                os.environ[_k] = _v


def pytest_generate_tests(metafunc):
    """Auto-parametrize tests that use the ``eval_model`` fixture."""

    if "eval_model" in metafunc.fixturenames:
        models_str = os.environ.get("EVAL_LLM_MODELS", "")
        if models_str:
            models = [m.strip() for m in models_str.split(",") if m.strip()]
        else:
            from .eval_utils import get_eval_model

            models = [get_eval_model()]
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
