import base64
import io
import zlib
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

from django.conf import settings
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from defusedxml import ElementTree
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_302_FOUND,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
)
from saml2.xml.schema import validate as validate_saml_xml

from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceUser
from baserow_enterprise.api.sso.utils import (
    get_frontend_default_redirect_url,
    get_frontend_login_error_url,
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_saml_provider_get_login_url(api_client, data_fixture, enterprise_data_fixture):
    # create a valid SAML provider
    auth_provider_1 = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )
    auth_provider_login = reverse("api:enterprise_sso_saml:login")
    auth_provider_login_url = reverse("api:enterprise_sso_saml:login_url")

    _, unauthorized_token = data_fixture.create_user_and_token()

    response = api_client.get(
        auth_provider_login_url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED

    _, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    # cannot create a SAML provider with an invalid domain or metadata
    response = api_client.get(
        auth_provider_login_url, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "redirect_url" in response_json
    assert response_json["redirect_url"] == urljoin(
        settings.PUBLIC_BACKEND_URL, auth_provider_login
    )

    # if more than one SAML provider is enabled, this endpoint need a email address
    auth_provider_2 = enterprise_data_fixture.create_saml_auth_provider(
        domain="test2.com"
    )

    # cannot create a SAML provider with an invalid domain or metadata
    response = api_client.get(
        auth_provider_login_url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_SAML_INVALID_LOGIN_REQUEST"

    query_params = urlencode(
        {
            "email": f"user@{auth_provider_1.domain}",
            "original": "/database/1/table/1",
        }
    )
    response = api_client.get(
        f"{auth_provider_login_url}?{query_params}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "redirect_url" in response_json
    assert response_json["redirect_url"] == urljoin(
        settings.PUBLIC_BACKEND_URL, f"{auth_provider_login}?{query_params}"
    )

    query_params = urlencode(
        {
            "email": f"user@{auth_provider_2.domain}",
            "original": "http://external-site.com",
        }
    )
    response = api_client.get(
        f"{auth_provider_login_url}?{query_params}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "redirect_url" in response_json
    # the original url is not relative so it should be ignored
    response_query_params = urlencode(
        {
            "email": f"user@{auth_provider_2.domain}",
        }
    )
    assert response_json["redirect_url"] == urljoin(
        settings.PUBLIC_BACKEND_URL,
        f"{auth_provider_login}?{response_query_params}",
    )

    query_params = urlencode(
        {
            "email": "user@unregistered-domain.com",
            "original": "http://test.com",
        }
    )
    response = api_client.get(
        f"{auth_provider_login_url}?{query_params}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_SAML_INVALID_LOGIN_REQUEST"

    response = api_client.get(
        f"{auth_provider_login_url}?email=invalid_email",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_user_cannot_initiate_saml_sso_without_enterprise_license(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.create_saml_auth_provider(domain="test1.com")
    response = api_client.get(reverse("api:enterprise_sso_saml:login"))
    assert response.status_code == HTTP_302_FOUND
    assert (
        response.headers["Location"]
        == f"{get_frontend_login_error_url()}?error=errorSsoFeatureNotActive"
    )


def decode_saml_request(idp_redirect_url):
    parsed_url = urlparse(idp_redirect_url)
    query_params = parse_qsl(parsed_url.query)
    encoded_saml_request = [v for k, v in query_params if k == "SAMLRequest"][0]
    saml_request_xml = zlib.decompress(
        base64.b64decode(encoded_saml_request), -15
    ).decode("utf-8")
    return ElementTree.parse(io.BytesIO(saml_request_xml.encode("utf-8")))


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_user_can_initiate_saml_sso_with_enterprise_license(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.create_saml_auth_provider(domain="test1.com")
    enterprise_data_fixture.enable_enterprise()

    sp_sso_saml_login_url = reverse("api:enterprise_sso_saml:login")
    original_relative_url = "database/1/table/1/"
    request_query_string = urlencode({"original": original_relative_url})

    response = api_client.get(f"{sp_sso_saml_login_url}?{request_query_string}")
    assert response.status_code == HTTP_302_FOUND
    idp_sign_in_url = response.headers["Location"]
    idp_url_initial_part = (
        "https://samltest.id/idp/profile/SAML2/Redirect/SSO?SAMLRequest="
    )
    assert idp_sign_in_url.startswith(idp_url_initial_part)
    saml_request = decode_saml_request(idp_sign_in_url)
    assert validate_saml_xml(saml_request) is None
    response_query_params = dict(parse_qsl(urlparse(idp_sign_in_url).query))
    assert response_query_params["RelayState"] == urljoin(
        settings.PUBLIC_WEB_FRONTEND_URL, original_relative_url
    )

    # an invalid email address should result in an error
    response = api_client.get(f"{sp_sso_saml_login_url}?email=john@acme.it")
    assert response.status_code == HTTP_302_FOUND
    assert (
        response.headers["Location"]
        == f"{get_frontend_login_error_url()}?error=errorInvalidSamlRequest"
    )


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_saml_assertion_consumer_service(api_client, enterprise_data_fixture):
    user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    sp_sso_saml_acs_url = reverse("api:enterprise_sso_saml:acs")

    (
        metadata,
        saml_response,
    ) = enterprise_data_fixture.get_valid_saml_idp_metadata_and_response()

    enterprise_data_fixture.create_saml_auth_provider(domain="test1.com")
    with freeze_time("2022-11-23T14:23:25.00Z"):
        response = api_client.post(
            sp_sso_saml_acs_url,
            data={
                "SAMLResponse": saml_response,
                "RelayState": get_frontend_default_redirect_url(),
            },
        )
        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{get_frontend_login_error_url()}?error=errorInvalidSamlResponse"
        )

    provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="baserow.io", metadata=metadata
    )

    response = api_client.post(
        sp_sso_saml_acs_url,
        data={
            "SAMLResponse": "some invalid SAML response",
            "RelayState": get_frontend_default_redirect_url(),
        },
    )
    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == (
        f"{get_frontend_login_error_url()}?error=errorInvalidSamlResponse"
    )

    response = api_client.post(
        sp_sso_saml_acs_url,
        data={
            "SAMLResponse": base64.b64encode(
                "some invalid SAML encoded response".encode("utf-8")
            ),
            "RelayState": get_frontend_default_redirect_url(),
        },
    )
    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == (
        f"{get_frontend_login_error_url()}?error=errorInvalidSamlResponse"
    )

    with freeze_time("2022-11-23T14:23:25.00Z"):
        workspace_user = enterprise_data_fixture.create_user_workspace(user=user)
        invitation = enterprise_data_fixture.create_workspace_invitation(
            workspace=workspace_user.workspace, email="newuser@email.com"
        )
        core_handler = CoreHandler()
        signer = core_handler.get_workspace_invitation_signer()
        workspace_invitation_token = signer.dumps(invitation.id)

        assert not provider.is_verified

        query_string = urlencode(
            {"language": "en", "workspace_invitation_token": workspace_invitation_token}
        )
        response = api_client.post(
            sp_sso_saml_acs_url,
            data={
                "SAMLResponse": saml_response,
                "RelayState": f"{settings.PUBLIC_WEB_FRONTEND_URL}?{query_string}",
            },
        )
        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"].startswith(
            (
                f"{get_frontend_login_error_url()}?error=errorWorkspaceInvitationEmailMismatch"
            )
        )

        invitation = enterprise_data_fixture.create_workspace_invitation(
            workspace=workspace_user.workspace, email="davide@baserow.io"
        )
        signer = core_handler.get_workspace_invitation_signer()
        workspace_invitation_token = signer.dumps(invitation.id)

        query_string = urlencode(
            {"language": "en", "workspace_invitation_token": workspace_invitation_token}
        )
        response = api_client.post(
            sp_sso_saml_acs_url,
            data={
                "SAMLResponse": saml_response,
                "RelayState": f"{settings.PUBLIC_WEB_FRONTEND_URL}?{query_string}",
            },
        )
        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"].startswith(
            f"{get_frontend_default_redirect_url()}?token="
        )
        # Extract the token from the URL, handling the new format with user_session
        redirect_url = response.headers["Location"]
        query_params = dict(parse_qsl(urlparse(redirect_url).query))
        token = query_params.get("token")

        # ensure the token is valid and a user has been created
        response = api_client.post(
            reverse("api:user:token_verify"),
            {"refresh_token": token},
            format="json",
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert response_json["user"]["username"] is not None

        # assert the user is a member of the workspace
        workspace_user = WorkspaceUser.objects.get(
            user__username=response_json["user"]["username"]
        )
        assert workspace_user.workspace_id == invitation.workspace_id

        # the SAML provider should be verified now
        provider.refresh_from_db()
        assert provider.is_verified

    # 10 minutes later the response is no longer valid
    with freeze_time("2022-11-23T14:33:25.00Z"):
        response = api_client.post(
            sp_sso_saml_acs_url,
            data={
                "SAMLResponse": saml_response,
                "RelayState": get_frontend_default_redirect_url(),
            },
        )
        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{get_frontend_login_error_url()}?error=errorInvalidSamlResponse"
        )
