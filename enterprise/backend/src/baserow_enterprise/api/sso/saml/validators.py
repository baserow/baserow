import io

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


def validate_saml_metadata(value):
    from saml2.xml.schema import XMLSchemaError
    from saml2.xml.schema import validate as validate_saml_metadata_schema

    metadata = io.StringIO(value)
    try:
        validate_saml_metadata_schema(metadata)
    except XMLSchemaError:
        raise serializers.ValidationError(
            "The metadata is not valid according to the XML schema."
        )

    return value
