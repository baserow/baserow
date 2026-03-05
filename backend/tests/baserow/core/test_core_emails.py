from django.template.exceptions import TemplateDoesNotExist

import pytest

from baserow.core.emails import BaseEmailMessage


class WithoutTemplateNameEmail(BaseEmailMessage):
    subject = "Test"


class WithoutSubjectEmail(BaseEmailMessage):
    template_name = "test.html"


class WrongTemplateEmail(BaseEmailMessage):
    subject = "Test"
    template_name = "test.html"


class SimpleResetPasswordEmail(BaseEmailMessage):
    subject = "Reset password"
    template_name = "baserow/core/user/reset_password.html"


@pytest.mark.django_db
def test_base_email_message():
    with pytest.raises(NotImplementedError):
        WithoutSubjectEmail("test@baserow.io")

    with pytest.raises(NotImplementedError):
        WithoutSubjectEmail("test@baserow.io")

    with pytest.raises(TemplateDoesNotExist):
        WrongTemplateEmail("test@baserow.io")

    email = SimpleResetPasswordEmail(["test@baserow.io"])
    context = email.get_context()
    assert "public_backend_url" in context
    assert "public_backend_hostname" in context
    assert "public_web_frontend_url" in context
    assert "public_web_frontend_hostname" in context
    assert "baserow_embedded_share_url" in context
    assert "baserow_embedded_share_hostname" in context
    assert email.get_from_email() == "no-reply@localhost"
    assert email.get_subject() == "Reset password"


@pytest.mark.django_db
def test_base_email_message_has_correct_message_id_domain(settings):
    """
    Ensure that the Message-ID header uses the configured domain
    instead of the machine's hostname, which could expose infrastructure
    internals like Kubernetes pod names.
    """

    settings.EMAIL_MESSAGE_ID_DOMAIN = "baserow.io"
    email = SimpleResetPasswordEmail(["test@baserow.io"])
    message_id = email.extra_headers.get("Message-ID", "")
    assert message_id.endswith("@baserow.io>"), (
        f"Expected Message-ID to end with '@baserow.io>', got: {message_id}"
    )


@pytest.mark.django_db
def test_base_email_message_id_domain_defaults_to_from_email(settings):
    """
    When EMAIL_MESSAGE_ID_DOMAIN is not explicitly set, it should
    default to the domain portion of FROM_EMAIL.
    """

    settings.FROM_EMAIL = "noreply@example.com"
    settings.EMAIL_MESSAGE_ID_DOMAIN = "example.com"
    email = SimpleResetPasswordEmail(["test@baserow.io"])
    message_id = email.extra_headers.get("Message-ID", "")
    assert message_id.endswith("@example.com>"), (
        f"Expected Message-ID to end with '@example.com>', got: {message_id}"
    )

