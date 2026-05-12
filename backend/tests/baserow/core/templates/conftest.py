import warnings

import pytest


@pytest.fixture(autouse=True)
def _suppress_syrupy_location_warning():
    # syrupy warns when the snapshot file path doesn't follow its default
    # naming convention (one file per test module). We use a custom extension
    # that writes one file per template slug, so the warning is expected and
    # can be safely silenced.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Can not relate snapshot location",
        )
        yield
