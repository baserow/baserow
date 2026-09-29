import pytest

from baserow.core.ai_provider.exceptions import InvalidAIProviderSettings
from baserow.core.ai_provider.provider_types import validate_provider_settings


@pytest.mark.parametrize(
    "region",
    ["us-east-1", "eu-central-1", "ap-southeast-2", "us-gov-west-1", "eusc-de-east-1"],
)
def test_bedrock_accepts_aws_regions(region):
    assert validate_provider_settings(
        "bedrock", "secret", {"region": region}, ["model"], require_credentials=True
    ) == {"region": region}


@pytest.mark.parametrize(
    "region",
    ["evil.example.com", "us-east-1.evil.com", "us-east-1/", "US-EAST-1", "localhost"],
)
def test_bedrock_rejects_values_that_are_not_aws_regions(region):
    with pytest.raises(InvalidAIProviderSettings) as exc_info:
        validate_provider_settings(
            "bedrock", "secret", {"region": region}, ["model"], require_credentials=True
        )

    assert "region" in exc_info.value.errors


def test_bedrock_accepts_an_iam_access_key_id():
    assert validate_provider_settings(
        "bedrock",
        "secret-access-key",
        {"region": "eu-central-1", "access_key_id": "AKIAIOSFODNN7EXAMPLE"},
        ["model"],
        require_credentials=True,
    ) == {"region": "eu-central-1", "access_key_id": "AKIAIOSFODNN7EXAMPLE"}


@pytest.mark.parametrize("access_key_id", ["AKIA-NOT-VALID-ID", "TOO-SHORT"])
def test_bedrock_rejects_malformed_access_key_ids(access_key_id):
    with pytest.raises(InvalidAIProviderSettings) as exc_info:
        validate_provider_settings(
            "bedrock",
            "secret",
            {"region": "eu-central-1", "access_key_id": access_key_id},
            ["model"],
            require_credentials=True,
        )

    assert "access_key_id" in exc_info.value.errors


@pytest.mark.parametrize(
    "secret",
    ["ABSKpart1\npart2", "ABSKpart1\r\npart2", "ABSK part", "ABSK\tpart"],
)
def test_bedrock_rejects_secrets_with_embedded_whitespace(secret):
    with pytest.raises(InvalidAIProviderSettings) as exc_info:
        validate_provider_settings(
            "bedrock",
            secret,
            {"region": "eu-central-1"},
            ["model"],
            require_credentials=True,
        )

    assert "api_key" in exc_info.value.errors


def test_bedrock_trims_trailing_whitespace_from_region_and_access_key_id():
    assert validate_provider_settings(
        "bedrock",
        "secret",
        {"region": "eu-central-1\n", "access_key_id": "AKIAIOSFODNN7EXAMPLE\n"},
        ["model"],
        require_credentials=True,
    ) == {"region": "eu-central-1", "access_key_id": "AKIAIOSFODNN7EXAMPLE"}


def test_bedrock_requires_a_secret_and_a_region():
    with pytest.raises(InvalidAIProviderSettings) as missing_secret:
        validate_provider_settings(
            "bedrock",
            "",
            {"region": "eu-central-1"},
            ["model"],
            require_credentials=True,
        )
    with pytest.raises(InvalidAIProviderSettings) as missing_region:
        validate_provider_settings(
            "bedrock", "secret", {}, ["model"], require_credentials=True
        )

    assert "api_key" in missing_secret.value.errors
    assert "region" in missing_region.value.errors
