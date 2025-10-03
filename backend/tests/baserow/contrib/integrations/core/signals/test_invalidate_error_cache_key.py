from unittest.mock import MagicMock, call, patch
from uuid import uuid4

from baserow.contrib.integrations.core.signals import invalidate_error_cache_key


@patch("baserow.contrib.integrations.core.signals.global_cache")
def test_invalidates_cache(mock_global_cache):
    mock_service = MagicMock()
    mock_service.uid = uuid4()

    result = invalidate_error_cache_key(None, mock_service)

    assert result is None
    prefix = "http_webhook_error_simulate_"
    mock_global_cache.invalidate.assert_has_calls(
        [
            call(f"{prefix}True_{mock_service.uid}"),
            call(f"{prefix}False_{mock_service.uid}"),
        ]
    )
