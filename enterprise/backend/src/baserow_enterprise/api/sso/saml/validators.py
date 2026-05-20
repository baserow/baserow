import io
from typing import Any, Iterable

from django.db.models import QuerySet

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from rest_framework import serializers

from baserow_enterprise.sso.saml.exceptions import SamlProviderForDomainAlreadyExists
from baserow_enterprise.sso.saml.models import SamlAuthProviderModel

SAML_METADATA_NAMESPACE = "urn:oasis:names:tc:SAML:2.0:metadata"
SAML_ROLE_DESCRIPTOR_TAG = f"{{{SAML_METADATA_NAMESPACE}}}RoleDescriptor"
SAML_METADATA_VALIDATION_ERROR = (
    "The metadata is not valid according to the XML schema."
)


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


def _remove_matching_children(root: Any, child_tags: Iterable[str]) -> bool:
    child_tags = set(child_tags)
    removed = False

    for parent in root.iter():
        for child in list(parent):
            if child.tag in child_tags:
                parent.remove(child)
                removed = True

    return removed


def normalize_saml_metadata(value):
    """
    Remove unsupported extension role descriptors from SAML metadata.

    Microsoft Entra ID/Azure AD can include WS-Federation RoleDescriptor nodes in
    its federation metadata alongside the SAML IDPSSODescriptor. PySAML2 rejects
    those extension role descriptors during schema validation even though Baserow
    only needs the SAML descriptor.
    """

    try:
        root = ElementTree.fromstring(value)
    except (ElementTree.ParseError, DefusedXmlException):
        return value

    if not _remove_matching_children(root, [SAML_ROLE_DESCRIPTOR_TAG]):
        return value

    return ElementTree.tostring(root, encoding="unicode")


def validate_saml_metadata(value):
    from saml2.xml.schema import XMLSchemaError
    from saml2.xml.schema import validate as validate_saml_metadata_schema

    metadata = io.StringIO(normalize_saml_metadata(value))
    try:
        validate_saml_metadata_schema(metadata)
    except XMLSchemaError:
        raise serializers.ValidationError(SAML_METADATA_VALIDATION_ERROR)

    return value
