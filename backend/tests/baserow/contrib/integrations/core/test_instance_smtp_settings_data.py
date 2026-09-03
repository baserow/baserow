from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.integrations.core.service_types import CoreSMTPEmailServiceType
from baserow.core.services.registries import service_type_registry


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


@pytest.mark.django_db
def test_a_configured_backend_without_a_host_is_not_available(api_client, settings):
    """
    The editor and the dispatch have to answer this the same way. A mail
    backend with no host to give it cannot send, and a database action has no
    integration to fall back on, so offering the action would only produce a
    failed click.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = ""

    response = api_client.get(reverse("api:settings:get"))

    assert response.json()["instance_smtp"] == {
        "available": False,
        "unavailable_reason": "no_server",
    }

    # The check the send makes agrees, which is the point of the fix.
    service_type = service_type_registry.get(CoreSMTPEmailServiceType.type)
    assert service_type.instance_smtp_is_available() is False
