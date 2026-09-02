from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK


@pytest.mark.django_db
def test_the_settings_say_whether_this_instance_can_send_email(api_client, settings):
    """
    An action being configured has not been saved yet, so there is no service
    to ask. The editor reads this instead and says so before the save.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

    response = api_client.get(reverse("api:settings:get"))

    assert response.status_code == HTTP_200_OK
    assert response.json()["instance_smtp"] == {
        "available": True,
        "unavailable_reason": None,
    }


@pytest.mark.django_db
def test_the_settings_say_which_way_sending_is_unavailable(api_client, settings):
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = False

    response = api_client.get(reverse("api:settings:get"))

    assert response.json()["instance_smtp"] == {
        "available": False,
        "unavailable_reason": "turned_off",
    }

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    response = api_client.get(reverse("api:settings:get"))

    assert response.json()["instance_smtp"] == {
        "available": False,
        "unavailable_reason": "no_server",
    }
