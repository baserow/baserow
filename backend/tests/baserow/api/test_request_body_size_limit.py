import json

from django.shortcuts import reverse
from django.test import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
)


@pytest.mark.django_db
@override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1024)
def test_oversized_request_body_returns_json_error(api_client, data_fixture):
    """
    Django raises RequestDataTooBig while the body is being read, which is outside
    the reach of DRF's exception handler. Without RequestDataTooBigMiddleware the
    client gets Django's HTML handler400 page instead of an API error.
    """

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Notes")

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {f"field_{field.id}": "a" * 2048},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert response["Content-Type"].startswith("application/json")
    assert json.loads(response.content)["error"] == "ERROR_REQUEST_BODY_TOO_LARGE"


@pytest.mark.django_db
@override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None)
def test_large_request_body_is_accepted_when_no_limit_is_configured(
    api_client, data_fixture
):
    """
    The limit is unset by default because the table import and create endpoints
    inline the whole dataset as JSON.
    """

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Notes")

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {f"field_{field.id}": "a" * 100_000},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["testserver"])
def test_other_bad_requests_also_return_json(api_client, data_fixture):
    """
    Every other SuspiciousOperation routed to handler400 stays generic, because
    Django withholds their detail to avoid echoing a rejected host or path back
    to whoever is probing for it.
    """

    url = reverse("api:settings:get")
    response = api_client.get(url, HTTP_HOST="not-an-allowed-host")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response["Content-Type"].startswith("application/json")
    assert json.loads(response.content)["error"] == "ERROR_BAD_REQUEST"
