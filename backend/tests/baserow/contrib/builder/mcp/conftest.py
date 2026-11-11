from pathlib import Path

import pytest

from tests.baserow.contrib.builder.tools.fixtures import (  # noqa: F401
    block_model_calls,
    builder_ctx,
)

HERE = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def no_model_calls_over_mcp(request, monkeypatch):
    # Named apart from the fixture of builder/tools: under such a rootdir both
    # are global and one would replace the other.
    # Run from a rootdir that doesn't contain this folder, pytest applies an
    # autouse fixture of a conftest to every test, so check the test's folder.
    if HERE in Path(request.node.path).resolve().parents:
        yield from block_model_calls(monkeypatch)
    else:
        yield []
