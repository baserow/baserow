from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from django.urls import reverse

import pytest

from baserow.core.action.models import Action
from baserow.core.action.signals import action_done
from baserow.core.integrations.models import Integration
from baserow.throttling.types import RateLimit

from .conftest import registered_stub_service_type
from .fake_provider import (
    ACCOUNT_ID,
    FAKE_TYPE,
    PROVIDER_REQUEST,
    token_error,
    token_response,
)


def url(name, integration_type=FAKE_TYPE, **kwargs):
    return reverse(
        f"api:oauth_account:{name}",
        kwargs={"integration_type": integration_type, **kwargs},
    )


def start(api_client, token, integration_type=FAKE_TYPE, **body):
    return api_client.post(
        url("start", integration_type),
        body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


def complete(api_client, token, state, code="", integration_type=FAKE_TYPE, **extra):
    return api_client.post(
        url("complete", integration_type),
        {"state": state, "code": code, **extra},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


def disconnect(api_client, token, integration_id, integration_type=FAKE_TYPE):
    return api_client.post(
        url("disconnect", integration_type, integration_id=integration_id),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@contextmanager
def audited_actions():
    audited = []

    def audit(sender, action_type, **kwargs):
        audited.append(action_type.type)

    action_done.connect(audit)
    try:
        yield audited
    finally:
        action_done.disconnect(audit)


def state_and_params(response):
    authorization_url = response.json()["authorization_url"]
    params = parse_qs(urlparse(authorization_url).query)
    return params["state"][0], params, authorization_url


@pytest.mark.django_db
def test_config_says_whether_the_provider_is_set_up(
    api_client, data_fixture, fake_oauth
):
    _, token = data_fixture.create_user_and_token()

    with override_settings(TEST_OAUTH_CLIENT_ID=""):
        response = api_client.get(url("config"), HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.json()["configured"] is False

    with override_settings(PUBLIC_WEB_FRONTEND_URL="https://b.io"):
        response = api_client.get(url("config"), HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.json() == {
        "configured": True,
        "redirect_uri": "https://b.io/integrations/test_oauth/oauth-callback",
        "allow_account_switch": True,
        "keep_connection_in_published_copies": True,
    }


@pytest.mark.django_db
def test_only_oauth_account_types_have_sign_in_endpoints(
    api_client, data_fixture, fake_oauth
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    for integration_type in ("smtp", "does_not_exist"):
        response = api_client.get(
            url("config", integration_type), HTTP_AUTHORIZATION=f"JWT {token}"
        )
        assert response.status_code == 404
        assert response.json()["error"] == "ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST"
        response = start(
            api_client, token, integration_type, application_id=application.id
        )
        assert response.status_code == 404


@pytest.mark.django_db
def test_start_is_refused_for_the_workspace(api_client, data_fixture, fake_oauth):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)

    response = start(api_client, token, application_id=shared_application.id)

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED"


@pytest.mark.django_db
def test_start_is_refused_when_the_provider_isnt_set_up(
    api_client, data_fixture, fake_oauth
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    with override_settings(TEST_OAUTH_CLIENT_SECRET=""):
        response = start(api_client, token, application_id=application.id)

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_OAUTH_NOT_CONFIGURED"


@pytest.mark.django_db
def test_start_needs_exactly_one_target(api_client, data_fixture, fake_oauth):
    user, token = data_fixture.create_user_and_token()
    integration = fake_oauth.create(user=user)

    assert start(api_client, token).status_code == 400
    response = start(
        api_client,
        token,
        application_id=integration.application_id,
        integration_id=integration.id,
    )
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_signing_in_creates_a_connected_integration(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    response = start(api_client, token, application_id=application.id)
    assert response.status_code == 200
    state, params, authorization_url = state_and_params(response)
    assert authorization_url.startswith("https://login.example.com/authorize?")
    assert params["client_id"] == ["client-id"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"][0]
    assert params["prompt"] == ["select_account"]
    assert params["redirect_uri"] == [
        "http://localhost:3000/integrations/test_oauth/oauth-callback"
    ]
    # Only the base scopes: no service asked for more.
    assert params["scope"][0].split() == ["email", "openid", "Profile.Read"]
    assert not Integration.objects.filter(application=application).exists()

    request = mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    response = complete(api_client, token, state, code="the-code")

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["created"] is True
    serialized = body["integration"]
    assert serialized["type"] == FAKE_TYPE
    assert serialized["name"] == "Example (alice@example.com)"
    assert serialized["connected"] is True
    assert serialized["account_email"] == "alice@example.com"
    assert serialized["account_name"] == "Alice"
    assert serialized["connected_by_name"] == user.first_name
    # Tokens are never sent back.
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "new-access" not in str(body)

    sent = request.call_args.kwargs
    assert sent["url"] == "https://login.example.com/token"
    assert sent["allow_redirects"] is False
    assert sent["send_netrc_credentials"] is False
    assert sent["data"]["grant_type"] == "authorization_code"
    assert sent["data"]["code"] == "the-code"
    assert sent["data"]["client_secret"] == "client-secret"  # nosec B105
    assert sent["data"]["code_verifier"]

    integration = fake_oauth.model.objects.get(id=serialized["id"])
    assert integration.account_id == ACCOUNT_ID
    # The provider's own connection field is stored too.
    assert integration.tenant == "contoso"
    assert integration.access_token == "new-access"  # nosec B105
    assert integration.refresh_token == "new-refresh"  # nosec B105
    assert integration.connected_by == user
    assert integration.generation == 1
    # The creation is an ordinary, undoable integration creation.
    assert Action.objects.filter(user=user, type="create_integration").exists()


@pytest.mark.django_db
def test_the_given_name_is_used(api_client, data_fixture, fake_oauth, mocker):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_automation_application(user=user)

    state, _, _ = state_and_params(
        start(api_client, token, application_id=application.id, name="Sales")
    )
    mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    response = complete(api_client, token, state, code="code")

    assert response.json()["integration"]["name"] == "Sales"


@pytest.mark.django_db
def test_scopes_come_from_service_types_only(
    api_client, data_fixture, fake_oauth, stub_service_type
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    response = start(
        api_client,
        token,
        application_id=application.id,
        service_types=[stub_service_type.type],
    )
    _, params, _ = state_and_params(response)
    assert "Messages.Send" in params["scope"][0].split()

    # Another type's service, or a scope passed off as a service type.
    for service_types in (["local_baserow_get_row"], ["Mail.ReadWrite"]):
        response = start(
            api_client,
            token,
            application_id=application.id,
            service_types=service_types,
        )
        assert response.status_code == 400
        assert response.json()["error"] == "ERROR_OAUTH_SERVICE_TYPE_NOT_ALLOWED"


@pytest.mark.django_db
def test_a_service_type_the_workspace_cant_use_is_refused(
    api_client, data_fixture, fake_oauth
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    with registered_stub_service_type(deactivated=True) as service_type:
        response = start(
            api_client,
            token,
            application_id=application.id,
            service_types=[service_type.type],
        )

    assert response.json()["error"] == "ERROR_OAUTH_SERVICE_TYPE_NOT_ALLOWED"


@pytest.mark.django_db
def test_start_checks_permissions(api_client, data_fixture, fake_oauth):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application()
    integration = fake_oauth.create()

    response = start(api_client, token, application_id=application.id)
    assert response.status_code == 401

    response = start(api_client, token, integration_id=integration.id)
    assert response.status_code == 401

    response = start(api_client, token, application_id=999999)
    assert response.status_code == 404


@pytest.mark.django_db
def test_start_only_accepts_integrations_of_its_type(
    api_client, data_fixture, fake_oauth
):
    user, token = data_fixture.create_user_and_token()
    integration = data_fixture.create_smtp_integration(user=user)

    response = start(api_client, token, integration_id=integration.id)

    assert response.status_code == 404
    assert response.json()["error"] == "ERROR_INTEGRATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_complete_checks_permissions_again(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    application = data_fixture.create_builder_application(workspace=workspace)
    state, _, _ = state_and_params(
        start(api_client, token, application_id=application.id)
    )
    request = mocker.patch(PROVIDER_REQUEST, return_value=token_response())

    # Access was lost while signing in.
    from baserow.core.handler import CoreHandler

    CoreHandler().leave_workspace(user, workspace)
    response = complete(api_client, token, state, code="code")

    assert response.status_code == 401
    request.assert_not_called()
    assert not Integration.objects.filter(application=application).exists()


@pytest.mark.django_db
def test_a_state_works_once_and_only_for_who_started_it(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    other, other_token = data_fixture.create_user_and_token(email="other@example.com")
    application = data_fixture.create_builder_application(user=user)
    state, _, _ = state_and_params(
        start(api_client, token, application_id=application.id)
    )
    request = mocker.patch(PROVIDER_REQUEST, return_value=token_response())

    assert complete(api_client, token, "forged", code="x").status_code == 400
    response = complete(api_client, other_token, state, code="x")
    assert response.json()["error"] == "ERROR_OAUTH_STATE_INVALID"
    # Someone else's attempt leaves the sign-in be.
    assert complete(api_client, token, state, code="x").status_code == 200
    response = complete(api_client, token, state, code="x")
    assert response.json()["error"] == "ERROR_OAUTH_STATE_INVALID"
    assert request.call_count == 1


@pytest.mark.django_db
def test_a_state_only_completes_for_its_own_type(
    api_client, data_fixture, fake_oauth, mocker
):
    from .fake_provider import FakeOAuthIntegrationType

    class OtherType(FakeOAuthIntegrationType):
        type = "test_oauth_other"

    from baserow.core.integrations.registries import integration_type_registry

    other_type = OtherType(fake_oauth.model)
    integration_type_registry.registry[other_type.type] = other_type
    try:
        user, token = data_fixture.create_user_and_token()
        application = data_fixture.create_builder_application(user=user)
        state, _, _ = state_and_params(
            start(api_client, token, application_id=application.id)
        )
        mocker.patch(PROVIDER_REQUEST, return_value=token_response())

        response = complete(
            api_client, token, state, code="x", integration_type=other_type.type
        )
        assert response.json()["error"] == "ERROR_OAUTH_STATE_INVALID"
    finally:
        del integration_type_registry.registry[other_type.type]


@pytest.mark.django_db
def test_a_cancelled_sign_in_creates_nothing(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    request = mocker.patch(PROVIDER_REQUEST)

    state, _, _ = state_and_params(
        start(api_client, token, application_id=application.id)
    )
    response = complete(
        api_client,
        token,
        state,
        error="access_denied",
        error_description="The user declined.",
    )
    assert response.json()["error"] == "ERROR_OAUTH_SIGN_IN_CANCELLED"

    # No code and no error: nothing to finish either.
    state, _, _ = state_and_params(
        start(api_client, token, application_id=application.id)
    )
    response = complete(api_client, token, state)
    assert response.json()["error"] == "ERROR_OAUTH_SIGN_IN_CANCELLED"

    assert not Integration.objects.filter(application=application).exists()
    request.assert_not_called()


@pytest.mark.django_db
def test_callback_errors_are_classified_by_the_provider(
    api_client, data_fixture, fake_oauth
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    def finish_with(error, description):
        state, _, _ = state_and_params(
            start(api_client, token, application_id=application.id)
        )
        return complete(
            api_client, token, state, error=error, error_description=description
        ).json()

    body = finish_with("access_denied", "ADMIN_ONLY: an admin must approve.")
    assert body["error"] == "ERROR_OAUTH_ADMIN_CONSENT_REQUIRED"
    assert body["detail"] == (
        "https://login.example.com/adminconsent?client_id=client-id"
    )
    body = finish_with("invalid_request", "TENANT_BLOCKED")
    assert body["error"] == "ERROR_OAUTH_TENANT_NOT_ALLOWED"
    body = finish_with("server_error", "secret details")
    assert body["error"] == "ERROR_OAUTH_FAILED"
    # What the provider said is never repeated.
    assert "secret details" not in str(body)


@pytest.mark.django_db
def test_a_refused_code_or_client_is_reported(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    state, _, _ = state_and_params(
        start(api_client, token, application_id=application.id)
    )
    mocker.patch(PROVIDER_REQUEST, return_value=token_error("invalid_grant"))
    response = complete(api_client, token, state, code="old")
    assert response.json()["error"] == "ERROR_OAUTH_FAILED"

    state, _, _ = state_and_params(
        start(api_client, token, application_id=application.id)
    )
    mocker.patch(PROVIDER_REQUEST, return_value=token_error("invalid_client", 401))
    response = complete(api_client, token, state, code="code")
    assert response.json()["error"] == "ERROR_OAUTH_CLIENT_REJECTED"

    assert not Integration.objects.filter(application=application).exists()


@pytest.mark.django_db
def test_an_answer_without_an_account_or_refresh_token_is_refused(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    for answer in (token_response(id_token=False), token_response(refresh_token="")):
        state, _, _ = state_and_params(
            start(api_client, token, application_id=application.id)
        )
        mocker.patch(PROVIDER_REQUEST, return_value=answer)
        response = complete(api_client, token, state, code="code")
        assert response.json()["error"] == "ERROR_OAUTH_FAILED"

    assert not Integration.objects.filter(application=application).exists()


@pytest.mark.django_db
def test_reconnecting_keeps_the_granted_scopes_and_suggests_the_account(
    api_client, data_fixture, fake_oauth, mocker, stub_service_type
):
    user, token = data_fixture.create_user_and_token()
    integration = fake_oauth.create(user=user, scopes=["openid", "Calendar.Read"])

    response = start(
        api_client,
        token,
        integration_id=integration.id,
        service_types=[stub_service_type.type],
    )
    state, params, _ = state_and_params(response)
    requested = params["scope"][0].split()
    assert "Calendar.Read" in requested
    assert "Messages.Send" in requested
    assert params["login_hint"] == ["alice@example.com"]

    # Signing in as another account is allowed by default.
    mocker.patch(
        PROVIDER_REQUEST,
        return_value=token_response(
            access_token="second-access",
            scope="openid Calendar.Read Messages.Send",
            email="bob@example.com",
            sub="bob",
        ),
    )
    with audited_actions() as audited:
        response = complete(api_client, token, state, code="code")

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert audited == ["connect_oauth_account"]
    integration.refresh_from_db()
    assert integration.account_email == "bob@example.com"
    assert integration.account_id == "bob"
    assert integration.access_token == "second-access"  # nosec B105
    # What the provider says was granted.
    assert integration.scopes == ["Calendar.Read", "Messages.Send", "openid"]


@pytest.mark.django_db
def test_a_provider_can_refuse_reconnecting_as_another_account(
    api_client, data_fixture, fake_oauth, mocker
):
    fake_oauth.provider.allow_account_switch = False
    user, token = data_fixture.create_user_and_token()
    integration = fake_oauth.create(user=user)

    state, _, _ = state_and_params(
        start(api_client, token, integration_id=integration.id)
    )
    mocker.patch(PROVIDER_REQUEST, return_value=token_response(sub="bob"))
    response = complete(api_client, token, state, code="code")

    assert response.json()["error"] == "ERROR_OAUTH_ACCOUNT_MISMATCH"
    integration.refresh_from_db()
    assert integration.account_id == ACCOUNT_ID
    assert integration.access_token == "access-token"  # nosec B105

    # The same account reconnects.
    state, _, _ = state_and_params(
        start(api_client, token, integration_id=integration.id)
    )
    mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    assert complete(api_client, token, state, code="code").status_code == 200


@pytest.mark.django_db
def test_a_reconnect_started_before_a_disconnect_cant_finish(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    integration = fake_oauth.create(user=user)
    state, _, _ = state_and_params(
        start(api_client, token, integration_id=integration.id)
    )

    with audited_actions() as audited:
        response = disconnect(api_client, token, integration.id)
    assert response.status_code == 200
    assert audited == ["disconnect_oauth_account"]
    assert response.json()["connected"] is False
    # Who it was stays, so the person knows which account to sign in with.
    assert response.json()["account_email"] == "alice@example.com"

    mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    response = complete(api_client, token, state, code="code")

    assert response.json()["error"] == "ERROR_OAUTH_STATE_INVALID"
    integration.refresh_from_db()
    assert integration.connected is False


@pytest.mark.django_db
def test_a_reconnect_cant_finish_with_another_client(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    integration = fake_oauth.create(
        user=user, own_client_id="own-id", own_client_secret="own-secret"
    )
    state, params, _ = state_and_params(
        start(api_client, token, integration_id=integration.id)
    )
    # The integration's own client is used.
    assert params["client_id"] == ["own-id"]

    fake_oauth.model.objects.filter(id=integration.id).update(
        own_client_secret="changed"
    )
    request = mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    response = complete(api_client, token, state, code="code")

    assert response.json()["error"] == "ERROR_OAUTH_STATE_INVALID"
    request.assert_not_called()


@pytest.mark.django_db
def test_disconnect_checks_permissions(api_client, data_fixture, fake_oauth):
    _, token = data_fixture.create_user_and_token()
    integration = fake_oauth.create()

    response = disconnect(api_client, token, integration.id)

    assert response.status_code == 401
    integration.refresh_from_db()
    assert integration.connected is True


@pytest.mark.django_db
def test_disconnect_only_accepts_integrations_of_its_type(
    api_client, data_fixture, fake_oauth
):
    user, token = data_fixture.create_user_and_token()
    integration = data_fixture.create_slack_bot_integration(user=user)

    response = disconnect(api_client, token, integration.id)

    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_the_tab_that_started_the_sign_in_isnt_sent_the_real_time_update(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    broadcast = mocker.patch(
        "baserow.core.integrations.ws.signals.broadcast_to_permitted_users.delay"
    )

    response = api_client.post(
        url("start"),
        {"application_id": application.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_WEBSOCKETID="opener-tab",
    )
    state, _, _ = state_and_params(response)
    mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    # The popup finishes the sign-in, without the opener's websocket id.
    complete(api_client, token, state, code="code")

    [call] = broadcast.call_args_list
    assert call.args[4]["type"] == "integration_created"
    assert call.args[4]["integration"]["connected"] is True
    assert call.args[5] == "opener-tab"


@pytest.mark.django_db
def test_the_tab_that_started_the_sign_in_can_undo_the_creation(
    api_client, data_fixture, fake_oauth, mocker
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    opener_session = "f6bc1f8a-6d63-4b1e-9b0e-0b4c1f9a7c11"

    response = api_client.post(
        url("start"),
        {"application_id": application.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=opener_session,
    )
    state, _, _ = state_and_params(response)
    mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    # The popup is another tab, with a session of its own.
    api_client.post(
        url("complete"),
        {"state": state, "code": "code"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID="0d6c4c34-2b7e-4f3c-8f57-5d0f8f5b9e21",
    )

    action = Action.objects.get(user=user, type="create_integration")
    assert action.session == opener_session


@pytest.mark.django_db(transaction=True)
def test_the_provider_is_called_outside_any_transaction_on_completion(
    api_client, data_fixture, fake_oauth, mocker
):
    from django.db import connection

    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    state, _, _ = state_and_params(
        start(api_client, token, application_id=application.id)
    )
    in_transaction = []

    def answer(**kwargs):
        in_transaction.append(connection.in_atomic_block)
        return token_response()

    mocker.patch(PROVIDER_REQUEST, side_effect=answer)

    assert complete(api_client, token, state, code="code").status_code == 200
    assert in_transaction == [False]


@pytest.mark.django_db
@override_settings(
    INTEGRATIONS_OAUTH_START_RATE_LIMITS=(RateLimit.from_string("2/m"),),
)
def test_starting_sign_ins_is_rate_limited_per_user(
    api_client, data_fixture, fake_oauth
):
    from baserow.throttling.handler import _get_redis_cli

    user, token = data_fixture.create_user_and_token()
    other, other_token = data_fixture.create_user_and_token(email="o@example.com")
    application = data_fixture.create_builder_application(user=user)
    other_application = data_fixture.create_builder_application(user=other)
    for key in _get_redis_cli().keys("baserow_rate_limit:oauth_account_start:*"):
        _get_redis_cli().delete(key)

    for _ in range(2):
        response = start(api_client, token, application_id=application.id)
        assert response.status_code == 200
    response = start(api_client, token, application_id=application.id)

    assert response.status_code == 429
    # Counted per user.
    assert (
        start(api_client, other_token, application_id=other_application.id).status_code
        == 200
    )
