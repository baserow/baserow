import io
import re

from django.db.models import QuerySet

from rest_framework import serializers

from baserow_enterprise.sso.saml.exceptions import SamlProviderForDomainAlreadyExists
from baserow_enterprise.sso.saml.models import SamlAuthProviderModel


def validate_unique_saml_domain(
    domain, instance=None, base_queryset: QuerySet | None = None
):
    if base_queryset is None:
        base_queryset = SamlAuthProviderModel.objects

    queryset = base_queryset.filter(domain=domain)
    if instance:
        queryset = queryset.exclude(id=instance.id)
    if queryset.exists():
        raise SamlProviderForDomainAlreadyExists(
            "There is already a provider for this domain."
        )
    return domain


def _strip_non_standard_saml_elements(xml_string: str) -> str:
    """
    Remove non-standard elements from SAML metadata XML before strict schema
    validation.

    AzureAD Federation Metadata XML includes ``<RoleDescriptor>`` elements
    with proprietary ``xsi:type`` extensions (e.g.
    ``fed:SecurityTokenServiceType``) that reference schemas outside the
    SAML 2.0 metadata XSD.  The strict ``saml2.xml.schema.validate`` call
    rejects these, even though the rest of the metadata is perfectly valid.

    This function strips any ``RoleDescriptor`` elements (with or without a
    namespace prefix) so that the cleaned XML passes schema validation.  The
    **original** value is always stored and used for actual SAML operations —
    pysaml2's runtime parser is tolerant of these extensions.

    Returns the cleaned XML string, or the original if parsing fails.
    """
    return re.sub(
        r"<(?:[\w-]+:)?RoleDescriptor[^>]*>.*?</(?:[\w-]+:)?RoleDescriptor>",
        "",
        xml_string,
        flags=re.DOTALL,
    )


def validate_saml_metadata(value):
    from saml2.xml.schema import XMLSchemaError
    from saml2.xml.schema import validate as validate_saml_metadata_schema

    metadata = io.StringIO(value)
    try:
        validate_saml_metadata_schema(metadata)
    except XMLSchemaError:
        # Retry after stripping non-standard elements such as AzureAD's
        # <RoleDescriptor> with proprietary xsi:type extensions.  If the
        # stripped version validates successfully, accept the original value
        # (pysaml2 handles these elements at runtime without issues).
        cleaned = _strip_non_standard_saml_elements(value)
        try:
            validate_saml_metadata_schema(io.StringIO(cleaned))
        except XMLSchemaError:
            raise serializers.ValidationError(
                "The metadata is not valid according to the XML schema."
            )

    return value
