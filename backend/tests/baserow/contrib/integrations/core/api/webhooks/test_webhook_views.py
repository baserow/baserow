from django.urls import reverse

import pytest
from rest_framework.status import HTTP_204_NO_CONTENT, HTTP_405_METHOD_NOT_ALLOWED


def get_url(uid):
    return reverse("api:http_trigger", kwargs={"webhook_uid": uid})


@pytest.mark.parametrize(
    "http_method",
    ["head", "options", "trace"],
)
@pytest.mark.django_db
def test_rejects_disallowed_methods(api_client, data_fixture, http_method):
    node = data_fixture.create_http_trigger_node()

    url = get_url(node.service.uid)
    resp = getattr(api_client, http_method)(url)

    assert resp.status_code == HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_rejects_http_get_if_service_excludes_get(
    api_client, data_fixture, django_assert_num_queries
):
    node = data_fixture.create_http_trigger_node()
    node.service.exclude_get = True
    node.service.save()

    url = get_url(node.service.uid) + "?test=true"

    # 1 model query, 3 transaction management queries
    with django_assert_num_queries(4):
        resp = api_client.get(url)

    assert resp.status_code == HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
@pytest.mark.parametrize(
    "http_method",
    ["get", "post", "put", "patch", "delete"],
)
def test_allows_valid_http_methods(api_client, data_fixture, http_method):
    node = data_fixture.create_http_trigger_node()

    url = get_url(node.service.uid) + "?test=true"
    resp = getattr(api_client, http_method)(url)

    assert resp.status_code == HTTP_204_NO_CONTENT
