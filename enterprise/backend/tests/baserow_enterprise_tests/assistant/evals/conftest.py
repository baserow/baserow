import asyncio
import logging
import os

from django.conf import settings

import pytest

from baserow.config.settings.test import TEST_ENV_VARS

# Expose provider credentials from TEST_ENV_FILE to os.environ so that LLM
# provider SDKs (which read os.getenv() at import/construction time) can find
# them.  test.py already parses TEST_ENV_FILE via dotenv_values but deliberately
# does NOT inject non-allowlisted keys into os.environ.  Matching on suffix
# rather than an explicit list means a new OpenAI-compatible endpoint only needs
# its <ALIAS>_BASE_URL / <ALIAS>_API_KEY pair, with no change here.
_CREDENTIAL_SUFFIXES = ("_API_KEY", "_BASE_URL")
for _k, _v in TEST_ENV_VARS.items():
    if _v and _k.endswith(_CREDENTIAL_SUFFIXES) and not os.environ.get(_k):
        os.environ[_k] = _v


_EVALS_DIR = os.path.dirname(__file__)


def _get_eval_runs():
    """Return stable run identifiers for repeated model reliability checks."""

    runs = int(os.environ.get("EVAL_RUNS", "1"))
    if runs < 1:
        raise pytest.UsageError("EVAL_RUNS must be a positive integer")
    return list(range(1, runs + 1))


@pytest.fixture(
    autouse=True,
    params=_get_eval_runs(),
    ids=lambda run: f"run-{run}",
)
def eval_run(request):
    """Repeat every eval equally so pass and flake rates are comparable."""

    return request.param


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


@pytest.hookimpl(tryfirst=True)
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

    _assign_xdist_groups(config, items)


def _provider_of(model: str) -> str:
    """Return the provider prefix of a pydantic-ai model string."""

    return model.split(":", 1)[0] if ":" in model else "openai"


def _shards_per_model(models: list[str], workers: int) -> dict[str, int]:
    """Decide how many xdist groups each model gets, widest axis first.

    Parallelism is spread across providers, then across models, and only then
    doubled up on a single model, because provider rate limits are the real
    ceiling for this suite: a 429 scored as a test failure is indistinguishable
    from a model-quality regression.

    An empty result means "group by provider" — the narrowest, safest layout.
    """

    providers = {_provider_of(m) for m in models}
    if workers <= len(providers):
        return {}
    if workers <= len(models):
        return dict.fromkeys(models, 1)
    base, extra = divmod(workers, len(models))
    return {m: base + (1 if i < extra else 0) for i, m in enumerate(models)}


def _group_name(model: str, occurrence: int, shards: dict[str, int]) -> str:
    """Return the ``xdist_group`` for one test of *model*."""

    if not shards:
        return _provider_of(model)
    count = shards.get(model, 1)
    return model if count <= 1 else f"{model}#{occurrence % count}"


def _worker_count(config) -> int:
    """Number of xdist workers, as seen from the controller *or* a worker.

    Workers are not launched with ``-n``, so ``numprocesses`` is unset there;
    they learn the count from ``workerinput``. Both sides must agree or they
    compute different groups for the same test.
    """

    workerinput = getattr(config, "workerinput", None)
    if workerinput:
        return int(workerinput.get("workercount", 1))
    workers = getattr(config.option, "numprocesses", None)
    return workers if isinstance(workers, int) else 1


def _assign_xdist_groups(config, items) -> None:
    """Tag eval items so ``--dist loadgroup`` schedules them per the policy above.

    Assignment happens here rather than on the ``eval_model`` parameter because
    splitting one model across several workers means splitting *its items*, which
    is only possible once the full collection is known.

    This must run in the workers too: xdist reads the marker there, when it
    suffixes node ids with the group name.
    """

    workers = _worker_count(config)
    if workers < 2:
        return

    by_model: dict[str, list] = {}
    for item in items:
        callspec = getattr(item, "callspec", None)
        model = callspec.params.get("eval_model") if callspec else None
        if model:
            by_model.setdefault(model, []).append(item)

    if not by_model:
        return

    shards = _shards_per_model(list(by_model), workers)
    for model, model_items in by_model.items():
        for occurrence, item in enumerate(model_items):
            item.add_marker(
                pytest.mark.xdist_group(name=_group_name(model, occurrence, shards))
            )


def pytest_configure(config):
    """Default to loadgroup scheduling so the grouping policy is honoured."""

    if getattr(config.option, "numprocesses", None) and config.option.dist in (
        "no",
        "load",
    ):
        config.option.dist = "loadgroup"


def pytest_xdist_make_scheduler(config, log):
    """Force group-aware scheduling for parallel runs.

    Setting ``config.option.dist`` alone is not reliable: xdist derives its
    default from ``-n`` at its own point in startup, so depending on hook order
    the flip can be overwritten and every worker ends up serving every provider.
    """

    if not getattr(config.option, "numprocesses", None):
        return None
    if config.option.dist not in ("no", "load", "loadgroup"):
        return None

    from xdist.scheduler import LoadGroupScheduling

    return LoadGroupScheduling(config, log)


def pytest_generate_tests(metafunc):
    """Auto-parametrize tests that use the ``eval_model`` fixture."""

    if "eval_model" in metafunc.fixturenames:
        from .eval_utils import get_eval_model

        model_str = get_eval_model()
        models = [m.strip() for m in model_str.split(",") if m.strip()]
        metafunc.parametrize("eval_model", models, scope="session")


@pytest.fixture(scope="session")
def synced_knowledge_base(django_db_setup, django_db_blocker):
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
