import uuid

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from baserow.contrib.integrations.core.constants import (
    BODY_TYPE,
    CSV_FILE_READER_INPUT_TYPE,
    HTTP_METHOD,
    PERIODIC_INTERVAL_CHOICES,
)
from baserow.core.formula.field import FormulaField
from baserow.core.integrations.models import Integration
from baserow.core.services.models import Service

User = get_user_model()


class SMTPIntegration(Integration):
    """
    Integration that stores SMTP server configuration. Can be used for sending emails.
    """

    host = models.CharField(
        max_length=255,
        help_text="The SMTP server hostname or IP address.",
    )
    port = models.PositiveIntegerField(
        default=587,
        help_text="The SMTP server port.",
    )
    use_tls = models.BooleanField(
        default=True,
        help_text="Whether to use TLS encryption.",
    )
    username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="The SMTP username for authentication.",
    )
    password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="The SMTP password for authentication.",
    )


class CoreIteratorService(Service):
    """
    A service to iterate over an array of data.
    """

    source = FormulaField(
        help_text="The path of the array.",
    )


class CoreCSVFileReaderService(Service):
    """
    A service to read rows from a CSV file.
    """

    file = FormulaField(
        blank=True,
        help_text="The CSV file to read.",
    )
    csv = FormulaField(
        blank=True,
        help_text="The raw CSV data to read.",
    )
    input_type = models.CharField(
        max_length=32,
        choices=CSV_FILE_READER_INPUT_TYPE.choices,
        default=CSV_FILE_READER_INPUT_TYPE.FILE,
        help_text="Whether the CSV should be read from a file or raw content.",
    )
    separator = models.CharField(
        max_length=1,
        default=",",
        help_text="The character used to separate columns in the CSV file.",
    )
    encoding = models.CharField(
        max_length=32,
        default="utf-8",
        help_text="The character encoding used to decode the CSV file.",
    )
    first_line_is_header = models.BooleanField(
        default=True,
        help_text="Whether the first line of the CSV file contains column names.",
    )


class CoreManualTriggerService(Service):
    """
    A trigger service for workflows that can only be started manually.
    """


class CoreStartWorkflowService(Service):
    """
    A service for starting an automation workflow.
    """

    workflow = models.ForeignKey(
        "automation.AutomationWorkflow",
        null=True,
        on_delete=models.SET_NULL,
        help_text="The automation workflow to start.",
    )


class CoreHTTPRequestService(Service):
    """
    A service for handling HTTP requests.
    """

    http_method = models.CharField(
        max_length=10,
        choices=HTTP_METHOD.choices,
        default=HTTP_METHOD.GET,
        help_text="The HTTP method to use for the request (e.g., GET, POST).",
    )
    url = FormulaField(
        blank=True, help_text="The URL to which the HTTP request will be sent."
    )
    body_type = models.CharField(
        max_length=20,
        choices=BODY_TYPE.choices,
        default=BODY_TYPE.NONE,
        help_text="The type of the body content (e.g., JSON, Form Data).",
    )
    body_content = FormulaField(
        blank=True,
        help_text="The content of the body of the HTTP request.",
    )
    timeout = models.PositiveIntegerField(
        default=30,
        validators=[
            MinValueValidator(1, message="Value cannot be less than 1."),
            MaxValueValidator(120, message="Value cannot be greater than 120."),
        ],
        help_text="The timeout for the HTTP request in seconds.",
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


class CoreSMTPEmailService(Service):
    """
    A service for sending emails via SMTP.
    """

    use_instance_smtp_settings = models.BooleanField(
        default=False,
        db_default=False,
        help_text="Whether to use the instance-level Django SMTP configuration.",
    )
    from_email = FormulaField(
        help_text="The sender's email address.",
    )
    from_name = FormulaField(
        blank=True,
        help_text="The sender's name.",
    )
    to_emails = FormulaField(
        help_text="Comma-separated list of recipient email addresses.",
    )
    cc_emails = FormulaField(
        blank=True,
        help_text="Comma-separated list of CC email addresses.",
    )
    bcc_emails = FormulaField(
        blank=True,
        help_text="Comma-separated list of BCC email addresses.",
    )
    subject = FormulaField(
        help_text="The email subject.",
    )
    body_type = models.CharField(
        max_length=10,
        choices=[
            ("plain", "Plain Text"),
            ("html", "HTML"),
        ],
        default="plain",
        help_text="The type of the email body (plain text or HTML).",
    )
    body = FormulaField(
        help_text="The email body content.",
    )

    @property
    def instance_smtp_settings_enabled(self) -> bool:
        return self.get_type()._instance_smtp_is_available()


class CoreRouterService(Service):
    default_edge_label = models.CharField(
        blank=True,
        max_length=75,
        help_text="The label to apply next to router edge.",
    )


class CoreRouterServiceEdge(models.Model):
    uid = models.UUIDField(default=uuid.uuid4)
    label = models.CharField(
        blank=True,
        max_length=75,
        help_text="The label to apply next to router edge.",
    )
    order = models.DecimalField(
        help_text="Lowest first.",
        max_digits=40,
        decimal_places=20,
        editable=False,
        default=1,
    )
    condition = FormulaField(
        help_text="The formula that must evaluate to true for this edge to be followed.",
    )
    service = models.ForeignKey(
        CoreRouterService, on_delete=models.CASCADE, related_name="edges"
    )

    class Meta:
        ordering = ("order",)


class CoreGotoService(Service):
    """
    A service that, when its condition formula evaluates to true, redirects
    execution to the configured destination instead of the natural next step.

    This makes while loops, retries, and conditional jumps possible.
    """

    condition = FormulaField(
        help_text="The formula that must evaluate to true for the jump to the "
        "destination node to be followed.",
    )
    destination_node = models.ForeignKey(
        "automation.AutomationNode",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The node to jump to when the condition evaluates to true.",
    )


class CorePeriodicService(Service):
    last_periodic_run = models.DateTimeField(
        null=True,
        help_text="Timestamp when the service was last executed periodically. This "
        "value is used to calculate when it should be run.",
    )
    next_run_at = models.DateTimeField(
        null=True,
        db_index=True,
        db_default=None,
        help_text="The next scheduled time for this service to run. Automatically "
        "calculated based on the interval and schedule fields.",
    )
    interval = models.CharField(
        max_length=10,
        choices=PERIODIC_INTERVAL_CHOICES,
        null=True,
        default=None,
        help_text="The interval frequency for running the service.",
    )
    minute = models.PositiveSmallIntegerField(
        default=0,
        help_text="The minute of the hour when to run (0-59). Required for hourly, "
        "daily, weekly, monthly intervals.",
    )
    hour = models.PositiveSmallIntegerField(
        default=0,
        help_text="The hour of the day when to run (0-23). Required for daily, "
        "weekly, monthly intervals.",
    )
    day_of_week = models.PositiveSmallIntegerField(
        default=0,
        help_text="The day of the week when to run (0=Monday, 6=Sunday). Required "
        "for weekly intervals.",
    )
    day_of_month = models.PositiveSmallIntegerField(
        default=1,
        help_text="The day of the month when to run (1-31). Required for monthly "
        "intervals.",
    )


class CoreHTTPTriggerService(Service):
    """
    A service for handling HTTP webhook requests.
    """

    uid = models.UUIDField(
        default=uuid.uuid4,
        help_text="The service identifier for the webhook.",
    )

    exclude_get = models.BooleanField(
        default=False,
        help_text="Whether the service should exclude GET requests for added security. "
        "By default all HTTP methods listed in the API endpoint are supported.",
    )

    is_public = models.BooleanField(
        default=False,
        help_text="Defines whether the service is published or not.",
    )
