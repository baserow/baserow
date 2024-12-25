from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from health_check.backends import BaseHealthCheckBackend
from health_check.db.backends import DatabaseBackend
from health_check.exceptions import ServiceUnavailable
from health_check.plugins import plugin_dir
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_503_SERVICE_UNAVAILABLE,
)


class AlwaysFailingHealthCheck(BaseHealthCheckBackend):
    def check_status(self):
        raise ServiceUnavailable("Error")


@pytest.fixture(autouse=True)
def reset_health_checks_to_expected():
    plugin_dir.reset()
    plugin_dir.register(DatabaseBackend)


@pytest.mark.django_db
def test_anonymous_user_cant_get_full_health_checks(data_fixture, api_client):
    response = api_client.get(
        reverse("api:health:full_health_check"),
        content_type="application/json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_non_staff_user_cant_get_full_health_checks(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:health:full_health_check"),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
@patch("baserow.api.health.views.get_celery_queue_size")
def test_staff_user_can_get_full_health_checks(mock_get_size, data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse("api:health:full_health_check"),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@patch("baserow.api.health.views.get_celery_queue_size")
def test_full_health_check_endpoint_returns_dict_of_checks_vs_status_with_200_status(
    mock_get_size, data_fixture, api_client
):
    mock_get_size.return_value = 5
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse("api:health:full_health_check"),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "passing": True,
        "checks": {
            "DatabaseBackend": "working",
        },
        "celery_queue_size": 5,
        "celery_export_queue_size": 5,
    }


@pytest.mark.django_db
@patch("baserow.api.health.views.get_celery_queue_size")
def test_passing_is_false_when_one_critical_service_fails(
    mock_get_size, data_fixture, api_client
):
    mock_get_size.return_value = 5
    user, token = data_fixture.create_user_and_token(is_staff=True)

    plugin_dir.register(AlwaysFailingHealthCheck)

    response = api_client.get(
        reverse("api:health:full_health_check"),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "checks": {
            "AlwaysFailingHealthCheck": "unavailable: Error",
            "DatabaseBackend": "working",
        },
        "passing": False,
        "celery_queue_size": 5,
        "celery_export_queue_size": 5,
    }


@pytest.mark.django_db
@override_settings(BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE=10)
@patch("baserow.api.health.views.get_celery_queue_size")
def test_celery_queue_size_exceed_within_limits(
    mock_get_size, data_fixture, api_client
):
    mock_get_size.return_value = 9
    response = api_client.get(
        reverse("api:health:celery_queue_size_exceeded") + "?queue=celery",
        content_type="application/json",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE=10)
@patch("baserow.api.health.views.get_celery_queue_size")
def test_celery_queue_size_exceed_outside_limits(
    mock_get_size, data_fixture, api_client
):
    mock_get_size.return_value = 11
    response = api_client.get(
        reverse("api:health:celery_queue_size_exceeded") + "?queue=celery",
        content_type="application/json",
    )
    assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
    assert response.content == b'"not ok"'


@pytest.mark.django_db
@override_settings(BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE=10)
@patch("baserow.api.health.views.get_celery_queue_size", kwargs={"queue": "celery"})
def test_celery_queue_size_exceed_queue_name(mock_get_size, data_fixture, api_client):
    mock_get_size.return_value = 0
    api_client.get(
        reverse("api:health:celery_queue_size_exceeded") + "?queue=celery",
        content_type="application/json",
    )
    mock_get_size.assert_called_with("celery")


@pytest.mark.django_db
@override_settings(BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE=10)
@patch("baserow.api.health.views.get_celery_queue_size", kwargs={"queue": "celery"})
def test_celery_queue_size_exceed_export_queue_name(
    mock_get_size, data_fixture, api_client
):
    mock_get_size.return_value = 0
    api_client.get(
        reverse("api:health:celery_queue_size_exceeded") + "?queue=export",
        content_type="application/json",
    )
    mock_get_size.assert_called_with("export")


@pytest.mark.django_db
@override_settings(BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE=10)
@patch("baserow.api.health.views.get_celery_queue_size", kwargs={"queue": "celery"})
def test_celery_queue_size_exceed_export_one_of_the_queues(
    mock_get_size, data_fixture, api_client
):
    def get_queue_size_side_effect(arg1):
        if arg1 == "celery":
            return 9
        elif arg1 == "export":
            return 11

    mock_get_size.side_effect = get_queue_size_side_effect

    response = api_client.get(
        reverse("api:health:celery_queue_size_exceeded") + "?queue=export&queue=celery",
        content_type="application/json",
    )
    assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
    assert response.content == b'"not ok"'


@pytest.mark.django_db
@override_settings(BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE=10)
@patch("baserow.api.health.views.get_celery_queue_size", kwargs={"queue": "celery"})
def test_celery_queue_size_exceed_queue_not_found(
    mock_get_size, data_fixture, api_client
):
    mock_get_size.return_value = 0
    response = api_client.get(
        reverse("api:health:celery_queue_size_exceeded") + "?queue=unknown",
        content_type="application/json",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.content == b'"queue unknown not found"'


@pytest.mark.django_db
@override_settings(BASEROW_MAX_HEALTHY_CELERY_QUEUE_SIZE=10)
@patch("baserow.api.health.views.get_celery_queue_size", kwargs={"queue": "celery"})
def test_celery_queue_size_exceed_no_queue_provided(
    mock_get_size, data_fixture, api_client
):
    mock_get_size.return_value = 0
    response = api_client.get(
        reverse("api:health:celery_queue_size_exceeded"),
        content_type="application/json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
