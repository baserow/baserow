from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.services.models import Service

from .constants import MAIL_BODY_TYPE


class SMTPSendEmailService(Service):
    """
    A service for sending emails.
    """

    body_type = models.CharField(
        max_length=20,
        choices=MAIL_BODY_TYPE.choices,
        default=MAIL_BODY_TYPE.TEXT,
        help_text="The type of the body content (e.g., JSON, Form Data).",
    )
    body_content = FormulaField(
        blank=True,
        help_text="The content of the body of the HTTP request.",
    )
    response_sample = models.JSONField(
        default=None,
        blank=True,
        null=True,
        help_text="Response got from test.",
    )


class HTTPFormData(models.Model):
    """
    Model to store Form data.
    """

    service = models.ForeignKey(
        CoreHTTPRequestService, on_delete=models.CASCADE, related_name="form_data"
    )
    key = models.CharField(max_length=255, help_text="The form data key.")
    value = FormulaField(blank=True, help_text="The form data value.")


class HTTPHeader(models.Model):
    """
    Model to store HTTP headers.
    """

    service = models.ForeignKey(
        CoreHTTPRequestService, on_delete=models.CASCADE, related_name="headers"
    )
    key = models.CharField(max_length=255, help_text="The header key.")
    value = FormulaField(blank=True, help_text="The header value.")


class HTTPQueryParam(models.Model):
    """
    Model to store HTTP query parameters.
    """

    service = models.ForeignKey(
        CoreHTTPRequestService, on_delete=models.CASCADE, related_name="query_params"
    )
    key = models.CharField(max_length=255, help_text="The query parameter key.")
    value = FormulaField(blank=True, help_text="The query parameter value.")
