from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.session import Session
from botocore.tokens import FrozenAuthToken

# pydantic-ai ignores ModelSettings.timeout for Bedrock, so these are the only bound.
_CLIENT_CONFIG = Config(
    connect_timeout=10,
    read_timeout=300,
    # total_max_attempts counts the initial call, unlike max_attempts.
    retries={"mode": "standard", "total_max_attempts": 3},
    # Baserow's own S3/MinIO endpoint env vars must never redirect Bedrock traffic.
    ignore_configured_endpoint_urls=True,
)


class _BearerTokenSession(Session):
    """A botocore session that only authenticates with one Bedrock API key."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def get_auth_token(self, **kwargs: Any) -> FrozenAuthToken:
        return FrozenAuthToken(self._token)

    def get_credentials(self) -> None:
        return None


def create_bedrock_runtime_client(
    region: str | None, secret: str | None, access_key_id: str | None = None
) -> BaseClient:
    """
    Create a Bedrock runtime client that only uses the given credentials.

    :param region: The AWS region of the Bedrock runtime.
    :param secret: The IAM secret access key when ``access_key_id`` is set,
        otherwise a Bedrock API key.
    :param access_key_id: The IAM access key ID, or None for a Bedrock API key.
    :return: A ``bedrock-runtime`` client.
    :raises ValueError: If ``secret`` or ``region`` is falsy.
    """

    if not secret or not region:
        raise ValueError(
            "An Amazon Bedrock API key or secret access key and a region are required."
        )

    if access_key_id:
        session = boto3.session.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret,
            region_name=region,
        )
        # Without it botocore prefers AWS_BEARER_TOKEN_BEDROCK over these keys.
        signature_version = "v4"
    else:
        session = boto3.session.Session(
            botocore_session=_BearerTokenSession(secret), region_name=region
        )
        signature_version = "bearer"
    return session.client(
        "bedrock-runtime",
        config=_CLIENT_CONFIG.merge(Config(signature_version=signature_version)),
    )
