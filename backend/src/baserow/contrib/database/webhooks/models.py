import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxLengthValidator
from django.db import models

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import View
from baserow.core.models import CreatedAndUpdatedOnMixin

from .validators import header_name_validator, header_value_validator, url_validator


class WebhookRequestMethods(models.TextChoices):
    POST = "POST"
    GET = "GET"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class TableWebhook(CreatedAndUpdatedOnMixin, models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    active = models.BooleanField(
        default=True,
        help_text="Indicates whether the web hook is active. When a webhook has "
        "failed multiple times, it will automatically be deactivated.",
    )
    use_user_field_names = models.BooleanField(
        default=True,
        help_text="Indicates whether the field names must be used as payload key "
        "instead of the id.",
    )

    # We use a `TextField` here as Django `URLField` is based on 255 chars
    # limited `CharField`
    url = models.TextField(
        help_text="The URL that must be called when the webhook is triggered.",
        validators=[MaxLengthValidator(2000), url_validator],
    )
    request_method = models.CharField(
        max_length=10,
        choices=WebhookRequestMethods.choices,
        default=WebhookRequestMethods.POST,
        help_text="The request method that be used when the event occurs.",
    )
    name = models.CharField(
        max_length=255, help_text="An internal name of the webhook."
    )
    include_all_events = models.BooleanField(
        default=True,
        help_text="Indicates whether this webhook should listen to all events.",
    )
    failed_triggers = models.IntegerField(
        default=0, help_text="The amount of failed webhook calls."
    )

    @property
    def header_dict(self):
        return {header.name: header.value for header in self.headers.all()}

    @property
    def batch_limit(self) -> int:
        """
        This value will be used to limit the amount batches a single webhook can make to
        paginate the payload. If the payload is too large to be sent in one go, the
        event_type can split it into multiple batches. If the number of batches exceeds
        this limit, a notification will be sent to workspace admins informing them that
        the webhook couldn't send all the data.
        """

        return settings.BASEROW_WEBHOOKS_BATCH_LIMIT

    class Meta:
        ordering = ("id",)


class TableWebhookEvent(CreatedAndUpdatedOnMixin, models.Model):
    webhook = models.ForeignKey(
        TableWebhook, related_name="events", on_delete=models.CASCADE
    )
    event_type = models.CharField(max_length=50)
    fields = models.ManyToManyField(Field)
    views = models.ManyToManyField(View)
    view_subscriptions = GenericRelation(
        "ViewSubscription",
        content_type_field="subscriber_content_type",
        object_id_field="subscriber_id",
    )

    def get_type(self):
        from .registries import webhook_event_type_registry

        return webhook_event_type_registry.get(self.event_type)

    class Meta:
        ordering = ("id",)


class TableWebhookHeader(models.Model):
    webhook = models.ForeignKey(
        TableWebhook, related_name="headers", on_delete=models.CASCADE
    )
    name = models.TextField(validators=[header_name_validator])
    value = models.TextField(validators=[header_value_validator])

    class Meta:
        ordering = ("id",)


class TableWebhookCall(models.Model):
    event_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        help_text="Event ID where the call originated from.",
    )
    batch_id = models.PositiveIntegerField(
        null=True,
        help_text=(
            "The batch ID for this call. Null if not part of a batch. "
            "Used for batching multiple calls of the same event_id due to large data."
        ),
    )
    webhook = models.ForeignKey(
        TableWebhook, related_name="calls", on_delete=models.CASCADE
    )
    event_type = models.CharField(max_length=50)
    called_time = models.DateTimeField(null=True)
    called_url = models.TextField(validators=[MaxLengthValidator(2000), url_validator])
    request = models.TextField(
        null=True, help_text="A text copy of the request headers and body."
    )
    response = models.TextField(
        null=True, help_text="A text copy of the response headers and body."
    )
    response_status = models.IntegerField(
        null=True, help_text="The HTTP response status code."
    )
    error = models.TextField(
        null=True, help_text="An internal error reflecting what went wrong."
    )

    class Meta:
        ordering = ("-called_time",)
        unique_together = ("event_id", "batch_id", "webhook", "event_type")
