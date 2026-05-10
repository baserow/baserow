import io
from xml.etree.ElementTree import ParseError, tostring

from django.db.models import QuerySet

from defusedxml import ElementTree
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


def validate_saml_metadata(value):
    from saml2.xml.schema import XMLSchemaError
    from saml2.xml.schema import validate as validate_saml_metadata_schema

    value = remove_role_descriptors_from_saml_metadata(value)
    metadata = io.StringIO(value)
    try:
        validate_saml_metadata_schema(metadata)
    except XMLSchemaError:
        raise serializers.ValidationError(
            "The metadata is not valid according to the XML schema."
        )

    return value


def remove_role_descriptors_from_saml_metadata(value):
    try:
        root = ElementTree.fromstring(value)
    except ParseError:
        return value

    role_descriptors = root.findall(
        "{urn:oasis:names:tc:SAML:2.0:metadata}RoleDescriptor"
    )
    if not role_descriptors:
        return value

    for role_descriptor in role_descriptors:
        root.remove(role_descriptor)

    return tostring(root, encoding="unicode")
