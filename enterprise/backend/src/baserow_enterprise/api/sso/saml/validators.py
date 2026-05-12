import io

from django.db.models import QuerySet

from defusedxml import ElementTree
from rest_framework import serializers

from baserow_enterprise.sso.saml.exceptions import SamlProviderForDomainAlreadyExists
from baserow_enterprise.sso.saml.models import SamlAuthProviderModel

SAML_METADATA_NAMESPACE = "urn:oasis:names:tc:SAML:2.0:metadata"
ROLE_DESCRIPTOR_TAG = f"{{{SAML_METADATA_NAMESPACE}}}RoleDescriptor"


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

    value = remove_saml_metadata_role_descriptors(value)
    metadata = io.StringIO(value)
    try:
        validate_saml_metadata_schema(metadata)
    except XMLSchemaError:
        raise serializers.ValidationError(
            "The metadata is not valid according to the XML schema."
        )

    return value


def remove_saml_metadata_role_descriptors(value):
    try:
        root = ElementTree.fromstring(value)
    except ElementTree.ParseError:
        return value

    removed = False
    for parent in root.iter():
        for child in list(parent):
            if child.tag == ROLE_DESCRIPTOR_TAG:
                parent.remove(child)
                removed = True

    if not removed:
        return value

    return ElementTree.tostring(root, encoding="unicode")


class SamlMetadataField(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return validate_saml_metadata(value)
