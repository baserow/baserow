class TableWebhookDoesNotExist(Exception):
    """Raised when trying to fetch a webhook that does not exist."""


class TableWebhookMaxAllowedCountExceeded(Exception):
    """Raised when trying to create more webhooks than a table allows."""


class TableWebhookEventConfigFieldNotInTable(Exception):
    """Raised when trying to update the"""

    def __init__(self, field_id=None, *args, **kwargs):
        self.field_id = field_id
        super().__init__(
            f"The field {field_id} does not belong to the table.",
            *args,
            **kwargs,
        )


class SkipWebhookCall(Exception):
    """Raised when the webhook call must be skipped"""
