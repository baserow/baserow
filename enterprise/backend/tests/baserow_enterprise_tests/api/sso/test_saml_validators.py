from pathlib import Path

from baserow_enterprise.api.sso.saml.validators import SamlMetadataField


def test_saml_metadata_field_removes_azure_ad_role_descriptors():
    metadata_path = Path(__file__).parents[2] / Path(
        "fixtures/sso/saml/idp_test_metadata.xml"
    )
    metadata = metadata_path.read_text()
    role_descriptor = (
        '<RoleDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" '
        'protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol" />'
    )
    metadata = metadata.replace(
        "<IDPSSODescriptor", f"{role_descriptor}<IDPSSODescriptor", 1
    )

    normalized_metadata = SamlMetadataField().run_validation(metadata)

    assert "RoleDescriptor" not in normalized_metadata
