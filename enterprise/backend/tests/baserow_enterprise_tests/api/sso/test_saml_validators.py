import pytest
from rest_framework import serializers

from baserow_enterprise.api.sso.saml.validators import validate_saml_metadata
from baserow_enterprise_tests.fixtures.sso.saml.saml import load_test_idp_metadata


def test_validate_saml_metadata_preserves_valid_metadata_without_role_descriptor():
    metadata = load_test_idp_metadata()

    assert validate_saml_metadata(metadata) == metadata


def test_validate_saml_metadata_accepts_azure_metadata_with_role_descriptor():
    metadata = load_test_idp_metadata()
    azure_role_descriptor = """
    <md:RoleDescriptor
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:type="fed:ApplicationServiceType"
        protocolSupportEnumeration="http://docs.oasis-open.org/wsfed/federation/200706"
        xmlns:fed="http://docs.oasis-open.org/wsfed/federation/200706">
        <md:KeyDescriptor use="signing"/>
    </md:RoleDescriptor>
    """
    metadata_with_role_descriptor = metadata.replace(
        "</md:EntityDescriptor>",
        f"{azure_role_descriptor}</md:EntityDescriptor>",
    )

    validated_metadata = validate_saml_metadata(metadata_with_role_descriptor)

    assert "RoleDescriptor" not in validated_metadata
    assert "IDPSSODescriptor" in validated_metadata


def test_validate_saml_metadata_still_rejects_invalid_metadata():
    with pytest.raises(serializers.ValidationError):
        validate_saml_metadata("invalid_metadata")
