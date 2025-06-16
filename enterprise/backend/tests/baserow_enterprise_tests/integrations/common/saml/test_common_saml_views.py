import base64
import io
import zlib
from urllib.parse import parse_qsl, urlencode, urlparse

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from defusedxml import ElementTree
from freezegun import freeze_time
from rest_framework.status import HTTP_302_FOUND
from saml2.xml.schema import validate as validate_saml_xml

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.core.user_sources.registries import user_source_type_registry
from baserow_enterprise.integrations.common.sso.saml.models import (
    SamlAppAuthProviderModel,
)

from ...local_baserow.helpers import populate_local_baserow_test_data


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise):
    pass


def decode_saml_request(idp_redirect_url):
    parsed_url = urlparse(idp_redirect_url)
    query_params = parse_qsl(parsed_url.query)
    encoded_saml_request = [v for k, v in query_params if k == "SAMLRequest"][0]
    saml_request_xml = zlib.decompress(
        base64.b64decode(encoded_saml_request), -15
    ).decode("utf-8")
    return ElementTree.parse(io.BytesIO(saml_request_xml.encode("utf-8")))


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_builder_saml_baserow_initiated_login_view(
    data_fixture, api_client, enterprise_data_fixture
):
    metadata = enterprise_data_fixture.get_test_saml_idp_metadata()

    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["unpublished_user_source"]
    domain = data["domain"]
    domain.domain_name = "test.com"
    domain.save()

    data_fixture.create_app_auth_provider(
        SamlAppAuthProviderModel,
        user_source=user_source,
        domain="test.com",
        metadata=metadata,
    )

    # Republish the domain to have the new provider
    domain = DomainHandler().publish(domain)

    published_builder = domain.published_to

    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")

    published_user_source = local_baserow_user_source_type.model_class.objects.get(
        application=published_builder
    )

    auth_provider_login = reverse(
        "api:user_sources:sso_saml:login",
        kwargs={"user_source_uid": user_source.uid},
    )
    query_params = urlencode(
        {
            "original": "http://test.com:3000/login?next=%2Ftoto",
        }
    )

    response = api_client.get(
        f"{auth_provider_login}?{query_params}",
        format="json",
    )
    assert response.status_code == HTTP_302_FOUND

    # First time with the unpublished user source. Should redirect to preview url
    idp_sign_in_url = response.headers["Location"]
    idp_url_initial_part = (
        "https://samltest.id/idp/profile/SAML2/Redirect/SSO?SAMLRequest="
    )
    assert idp_sign_in_url.startswith(idp_url_initial_part)
    saml_request = decode_saml_request(idp_sign_in_url)
    assert validate_saml_xml(saml_request) is None
    response_query_params = dict(parse_qsl(urlparse(idp_sign_in_url).query))
    assert (
        response_query_params["RelayState"]
        == f"http://localhost:3000/builder/{domain.builder.id}/preview/"
    )

    # Second time, should redirect to the same URL
    auth_provider_login = reverse(
        "api:user_sources:sso_saml:login",
        kwargs={"user_source_uid": published_user_source.uid},
    )

    response = api_client.get(
        f"{auth_provider_login}?{query_params}",
        format="json",
    )

    idp_sign_in_url = response.headers["Location"]
    assert idp_sign_in_url.startswith(idp_url_initial_part)
    saml_request = decode_saml_request(idp_sign_in_url)
    assert validate_saml_xml(saml_request) is None
    response_query_params = dict(parse_qsl(urlparse(idp_sign_in_url).query))
    assert (
        response_query_params["RelayState"] == "http://test.com:3000/login?next=%2Ftoto"
    )


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_builder_saml_assertion_consumer_service(
    data_fixture, api_client, enterprise_data_fixture
):
    (
        metadata,
        saml_response,
    ) = enterprise_data_fixture.get_valid_saml_idp_metadata_and_response_for_builder()

    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["unpublished_user_source"]
    domain = data["domain"]
    domain.domain_name = "test.com"
    domain.save()

    data_fixture.create_app_auth_provider(
        SamlAppAuthProviderModel,
        user_source=user_source,
        domain="test.com",
        metadata=metadata,
    )

    # Republish the domain to have the new provider
    domain = DomainHandler().publish(domain)

    published_builder = domain.published_to

    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")
    published_user_source = local_baserow_user_source_type.model_class.objects.get(
        application=published_builder
    )
    sp_sso_saml_acs_url = reverse(
        "api:user_sources:sso_saml:acs",
    )

    with freeze_time("2024-12-17T15:53:00.00Z"):
        response = api_client.post(
            sp_sso_saml_acs_url,
            data={
                "SAMLResponse": saml_response,
                "RelayState": "http://test.com:3000/login?next=%2Ftoto",
            },
        )
        assert response.status_code == HTTP_302_FOUND

        parsed_redirect = urlparse(response.headers["Location"])

        assert parsed_redirect.hostname == "test.com"
        assert parsed_redirect.path == "/login"

        query_param = dict(parse_qsl(parsed_redirect.query))

        assert query_param["next"] == "/toto"
        assert f"user_source_saml_token__{published_user_source.id}" in query_param
