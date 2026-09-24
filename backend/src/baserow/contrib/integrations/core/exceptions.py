from uuid import uuid4


class CoreHTTPTriggerServiceDoesNotExist(Exception):
    """When the specified HTTP trigger service doesn't exist."""

    def __init__(self, uid: uuid4, *args, **kwargs):
        self.uid = uid
        super().__init__(
            f"The webhook service {uid} does not exist.",
            *args,
            **kwargs,
        )


class CoreHTTPTriggerServiceMethodNotAllowed(Exception):
    """When the specified method isn't allowed for the service."""

    pass


class CoreInboundEmailTriggerServiceDoesNotExist(Exception):
    """When no email trigger service matches the provided token."""

    def __init__(self, token: str, *args, **kwargs):
        self.token = token
        super().__init__(
            f"No email trigger service matches the token {token}.",
            *args,
            **kwargs,
        )


class InvalidInboundEmailPayload(Exception):
    """When an inbound email webhook payload is malformed."""

    pass
