from django.test.utils import override_settings

import requests

import advocate
from baserow.contrib.database.data_sync.utils import get_data_sync_request_function


@override_settings(BASEROW_DATA_SYNC_ALLOW_PRIVATE_ADDRESS=False)
def test_get_data_sync_request_function_blocks_private_address_by_default():
    # By default data sync requests must go through advocate so that user configured
    # URLs can't be used to reach Baserow's internal network (SSRF protection).
    assert get_data_sync_request_function() is advocate.request


@override_settings(BASEROW_DATA_SYNC_ALLOW_PRIVATE_ADDRESS=True)
def test_get_data_sync_request_function_allows_private_address_when_enabled():
    assert get_data_sync_request_function() is requests.request
