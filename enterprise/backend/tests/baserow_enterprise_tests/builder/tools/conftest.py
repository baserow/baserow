from pathlib import Path

import pytest

from baserow_enterprise_tests.builder.tools.fixtures import (  # noqa: F401
    block_model_calls,
    builder_ctx,
)

HERE = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def no_model_calls(request, monkeypatch):
    # Run from a rootdir that doesn't contain this folder, pytest applies an
    # autouse fixture of a conftest to every test, so check the test's folder.
    if HERE in Path(request.node.path).resolve().parents:
        yield from block_model_calls(monkeypatch)
    else:
        yield []
