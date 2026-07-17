from django.test.utils import override_settings

import pytest
import requests

import advocate
from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.database.data_sync.utils import (
    get_data_sync_request_function,
    get_data_sync_session,
)


@override_settings(BASEROW_DATA_SYNC_ALLOW_PRIVATE_ADDRESS=False)
def test_get_data_sync_request_function_blocks_private_address_when_not_allowed():
    # When private addresses are not allowed, data sync requests must go through
    # advocate so that user configured URLs can't reach Baserow's internal network.
    assert get_data_sync_request_function() is advocate.request


@override_settings(BASEROW_DATA_SYNC_ALLOW_PRIVATE_ADDRESS=True)
def test_get_data_sync_request_function_allows_private_address_when_enabled():
    assert get_data_sync_request_function() is requests.request


@override_settings(BASEROW_DATA_SYNC_ALLOW_PRIVATE_ADDRESS=False)
def test_get_data_sync_session_blocks_private_address_when_not_allowed():
    assert isinstance(get_data_sync_session(), advocate.Session)


@override_settings(BASEROW_DATA_SYNC_ALLOW_PRIVATE_ADDRESS=True)
def test_get_data_sync_session_allows_private_address_when_enabled():
    session = get_data_sync_session()
    assert isinstance(session, requests.Session)
    assert not isinstance(session, advocate.Session)


@override_settings(BASEROW_DATA_SYNC_ALLOW_PRIVATE_ADDRESS=False)
def test_get_data_sync_request_function_rejects_private_ip():
    # Port 80 is in advocate's whitelist, so the private IP check itself is hit.
    with pytest.raises(UnacceptableAddressException):
        get_data_sync_request_function()("GET", "http://10.0.0.1:80/", timeout=5)


@override_settings(BASEROW_DATA_SYNC_ALLOW_PRIVATE_ADDRESS=False)
def test_get_data_sync_session_rejects_private_ip():
    with pytest.raises(UnacceptableAddressException):
        get_data_sync_session().get("http://10.0.0.1:80/", timeout=5)
