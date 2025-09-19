from uuid import uuid4


class CoreHTTPWebhookServiceDoesNotExist(Exception):
    """When the specified webhook service doesn't exist."""

    def __init__(self, uid: uuid4, *args, **kwargs):
        self.uid = uid
        super().__init__(
            f"The webhook service {uid} does not exist.",
            *args,
            **kwargs,
        )
