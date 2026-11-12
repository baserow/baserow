from django.shortcuts import reverse

from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator
from openapi_spec_validator import openapi_v30_spec_validator


def test_openapi_spec(api_client):
    response = api_client.get(reverse("api:json_schema"))

    # If no exception is raised the spec is valid
    openapi_v30_spec_validator.validate(response.json())


def test_openapi_spec_has_one_serializer_per_service_request_component():
    GENERATOR_STATS.reset()

    SchemaGenerator().get_schema(request=None, public=True)

    collisions = [
        warning
        for warning in GENERATOR_STATS._warn_cache
        if "Integration_ServiceBasePolymorphicRequest" in warning
    ]
    assert collisions == []
