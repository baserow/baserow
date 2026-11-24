import time
from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.utils import timezone

import pytest
from requests import exceptions as request_exceptions

from baserow.api.services.serializers import ServiceSerializer
from baserow.contrib.integrations.oauth_account.exceptions import (
    ClientRejected,
    OAuthFailed,
    ProviderUnavailable,
    ReconnectRequired,
    ScopesMissing,
)
from baserow.contrib.integrations.oauth_account.handler import (
    REFRESH_LOCK_KEY,
    OAuthAccountHandler,
)
from baserow.contrib.integrations.oauth_account.service_types import (
    quote_path_segments,
)
from baserow.core.fields import UndecryptableSecret
from baserow.core.services.exceptions import (
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)

from .fake_provider import (
    API_REQUEST,
    PROVIDER_REQUEST,
    FakeResponse,
    StubOAuthServiceType,
    token_error,
    token_response,
)

SEND_SCOPES = ["email", "openid", "Profile.Read", "Messages.Send"]


def expiring(fake_oauth, **kwargs):
    return fake_oauth.create(
        expires_at=timezone.now() + timedelta(seconds=30), **kwargs
    )


def handler(fake_oauth):
    return OAuthAccountHandler(fake_oauth.type)


@pytest.mark.django_db
def test_a_token_that_doesnt_expire_soon_is_used_as_is(fake_oauth, mocker):
    integration = fake_oauth.create()
    request = mocker.patch(PROVIDER_REQUEST)

    assert handler(fake_oauth).get_access_token(integration, ["openid"]) == (
        "access-token"
    )
    request.assert_not_called()


@pytest.mark.django_db
def test_an_expiring_token_is_refreshed_and_the_new_refresh_token_kept(
    fake_oauth, mocker
):
    integration = expiring(fake_oauth)
    request = mocker.patch(PROVIDER_REQUEST, return_value=token_response())

    assert handler(fake_oauth).get_access_token(integration, []) == "new-access"

    sent = request.call_args.kwargs
    assert sent["data"]["grant_type"] == "refresh_token"
    assert sent["data"]["refresh_token"] == "refresh-token"  # nosec B105
    assert "Profile.Read" in sent["data"]["scope"].split()
    assert sent["allow_redirects"] is False
    integration.refresh_from_db()
    assert integration.access_token == "new-access"  # nosec B105
    assert integration.refresh_token == "new-refresh"  # nosec B105
    assert integration.expires_at > timezone.now() + timedelta(minutes=50)


@pytest.mark.django_db
def test_a_refresh_without_a_new_refresh_token_keeps_the_old_one(fake_oauth, mocker):
    integration = expiring(fake_oauth)
    mocker.patch(PROVIDER_REQUEST, return_value=token_response(refresh_token=""))

    handler(fake_oauth).get_access_token(integration, [])

    integration.refresh_from_db()
    assert integration.refresh_token == "refresh-token"  # nosec B105


@pytest.mark.django_db
def test_a_refused_refresh_token_must_be_connected_again(fake_oauth, mocker):
    integration = expiring(fake_oauth)
    generation = integration.generation
    mocker.patch(PROVIDER_REQUEST, return_value=token_error("invalid_grant"))

    with pytest.raises(ReconnectRequired):
        handler(fake_oauth).get_access_token(integration, [])

    integration.refresh_from_db()
    assert integration.connected is False
    assert integration.access_token == ""
    # Who it was stays.
    assert integration.account_email == "alice@example.com"
    # A clear by a refresh doesn't stop a reconnect already started.
    assert integration.generation == generation


@pytest.mark.django_db
@pytest.mark.parametrize(
    "answer,expected",
    [
        (request_exceptions.ConnectionError(), ProviderUnavailable),
        (FakeResponse(503, {}), ProviderUnavailable),
        (FakeResponse(429, {"error": "invalid_grant"}), ProviderUnavailable),
        (token_error("temporarily_unavailable"), ProviderUnavailable),
        (token_error("invalid_client", 401), ClientRejected),
        (token_error("invalid_scope"), OAuthFailed),
        (FakeResponse(400, None), OAuthFailed),
    ],
)
def test_failures_that_arent_about_the_account_keep_the_tokens(
    fake_oauth, mocker, answer, expected
):
    integration = expiring(fake_oauth)
    if isinstance(answer, Exception):
        mocker.patch(PROVIDER_REQUEST, side_effect=answer)
    else:
        mocker.patch(PROVIDER_REQUEST, return_value=answer)

    with pytest.raises(expected) as exc_info:
        handler(fake_oauth).get_access_token(integration, [])

    if expected is ProviderUnavailable:
        assert exc_info.value.retryable is True
    if expected is OAuthFailed:
        assert exc_info.value.retryable is False
    integration.refresh_from_db()
    assert integration.refresh_token == "refresh-token"  # nosec B105


@pytest.mark.django_db
def test_missing_scopes_and_disconnected_accounts_are_refused(fake_oauth):
    integration = fake_oauth.create(scopes=["openid", "messages.send"])

    # This provider's scopes compare case-insensitively.
    handler(fake_oauth).get_access_token(integration, ["Messages.Send"])
    with pytest.raises(ScopesMissing) as exc_info:
        handler(fake_oauth).get_access_token(
            integration, ["Messages.Send", "Calendar.Read"]
        )
    assert exc_info.value.scopes == ["Calendar.Read"]

    disconnected = fake_oauth.create(connected=False)
    with pytest.raises(ReconnectRequired):
        handler(fake_oauth).get_access_token(disconnected, [])


@pytest.mark.django_db
def test_an_unreadable_token_is_never_sent_nor_cleared(fake_oauth, mocker):
    integration = fake_oauth.create()
    # As read when the key that encrypted it isn't configured any more.
    integration.access_token = UndecryptableSecret("stored")
    request = mocker.patch(PROVIDER_REQUEST)

    with pytest.raises(ReconnectRequired):
        handler(fake_oauth).get_access_token(integration, [])

    request.assert_not_called()

    integration.refresh_from_db()
    assert integration.refresh_token == "refresh-token"  # nosec B105


@pytest.mark.django_db
def test_a_refresh_after_a_disconnect_doesnt_bring_the_tokens_back(fake_oauth, mocker):
    integration = expiring(fake_oauth)
    stale = fake_oauth.model.objects.get(id=integration.id)
    handler(fake_oauth).disconnect(integration)
    request = mocker.patch(PROVIDER_REQUEST, return_value=token_response())

    with pytest.raises(ReconnectRequired):
        handler(fake_oauth).refresh(stale)

    request.assert_not_called()


@pytest.mark.django_db
def test_a_refresh_doesnt_overwrite_a_newer_sign_in(fake_oauth, mocker):
    integration = expiring(fake_oauth)

    def signed_in_again_meanwhile(**kwargs):
        stored = fake_oauth.model.objects.get(id=integration.id)
        stored.access_token = "from-sign-in"  # nosec B105
        stored.refresh_token = "from-sign-in"  # nosec B105
        stored.generation += 1
        stored.save()
        return token_response()

    mocker.patch(PROVIDER_REQUEST, side_effect=signed_in_again_meanwhile)

    handler(fake_oauth).refresh(integration)

    integration.refresh_from_db()
    assert integration.access_token == "from-sign-in"  # nosec B105


@pytest.mark.django_db
def test_a_refused_token_is_refreshed_unless_a_newer_one_is_stored(fake_oauth, mocker):
    integration = fake_oauth.create()
    request = mocker.patch(PROVIDER_REQUEST, return_value=token_response())

    # Another request stored a newer one since: it's tried as it is.
    assert (
        handler(fake_oauth).refuse_token(integration, "an-older-token")
        == "access-token"
    )
    request.assert_not_called()

    assert handler(fake_oauth).refuse_token(integration, "access-token") == (
        "new-access"
    )
    assert request.call_count == 1


@pytest.mark.django_db
def test_a_refused_token_refreshed_just_before_is_refreshed_again(fake_oauth, mocker):
    # The caller's copy has the token from before its own refresh: the refused
    # token is compared, not the copy's.
    integration = expiring(fake_oauth)
    mocker.patch(
        PROVIDER_REQUEST,
        side_effect=[
            token_response(access_token="first"),
            token_response(access_token="second"),
        ],
    )

    token = handler(fake_oauth).get_access_token(integration, [])
    assert token == "first"  # nosec B105

    assert handler(fake_oauth).refuse_token(integration, token) == "second"


@pytest.mark.django_db(transaction=True)
def test_the_provider_is_called_outside_any_database_transaction(fake_oauth, mocker):
    integration = expiring(fake_oauth)
    in_transaction = []

    def answer(**kwargs):
        in_transaction.append(connection.in_atomic_block)
        return token_response()

    mocker.patch(PROVIDER_REQUEST, side_effect=answer)

    handler(fake_oauth).get_access_token(integration, [])

    # No row lock is held while the provider answers.
    assert in_transaction == [False]


@pytest.mark.django_db
def test_a_refresh_already_running_is_waited_for_not_repeated(fake_oauth, mocker):
    integration = expiring(fake_oauth)
    key = REFRESH_LOCK_KEY.format(integration.id)
    cache.set(key, "another-request", 30)
    request = mocker.patch(PROVIDER_REQUEST)

    def other_request_finishes(seconds):
        stored = fake_oauth.model.objects.get(id=integration.id)
        stored.access_token = "theirs"  # nosec B105
        stored.expires_at = timezone.now() + timedelta(hours=1)
        stored.save(update_fields=["access_token", "expires_at"])
        cache.delete(key)

    mocker.patch(
        "baserow.contrib.integrations.oauth_account.handler.time.sleep",
        side_effect=other_request_finishes,
    )

    assert handler(fake_oauth).get_access_token(integration, []) == "theirs"
    request.assert_not_called()


@pytest.mark.django_db
def test_waiting_for_another_refresh_stops_at_the_deadline(fake_oauth, mocker):
    integration = expiring(fake_oauth)
    cache.set(REFRESH_LOCK_KEY.format(integration.id), "another-request", 30)
    mocker.patch("baserow.contrib.integrations.oauth_account.handler.time.sleep")

    with pytest.raises(ProviderUnavailable) as exc_info:
        handler(fake_oauth).refresh(integration, deadline=time.monotonic() - 1)

    assert exc_info.value.retryable is True
    cache.delete(REFRESH_LOCK_KEY.format(integration.id))


@pytest.mark.django_db
def test_the_refresh_request_is_bounded_by_the_deadline(fake_oauth, mocker):
    integration = expiring(fake_oauth)
    refresh = mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    deadline = time.monotonic() + 5

    handler(fake_oauth).get_access_token(integration, [], deadline=deadline)

    assert refresh.call_args.kwargs["deadline"] <= deadline
    # And by the provider's own limit when the caller's is further away.
    handler(fake_oauth).refresh(
        integration, refused_token="new-access", deadline=time.monotonic() + 3600
    )
    assert refresh.call_args.kwargs["deadline"] <= time.monotonic() + 31


def test_path_segments_are_quoted_one_by_one():
    assert quote_path_segments("chats", "19:a/b@thread.v2", "messages") == (
        "chats/19%3Aa%2Fb%40thread.v2/messages"
    )
    assert quote_path_segments("teams", "../me", "channels") == (
        "teams/..%2Fme/channels"
    )
    for segment in ("", ".", ".."):
        with pytest.raises(ValueError):
            quote_path_segments("chats", segment, "messages")


def send_message_service(data_fixture, fake_oauth, **kwargs):
    kwargs.setdefault("scopes", SEND_SCOPES)
    return data_fixture.create_local_baserow_get_row_service(
        integration=fake_oauth.create(**kwargs)
    )


@pytest.mark.django_db
def test_requests_send_the_token_and_refresh_it_once_when_refused(
    data_fixture, fake_oauth, mocker
):
    service = send_message_service(data_fixture, fake_oauth)
    api = mocker.patch(
        API_REQUEST,
        side_effect=[FakeResponse(401, {}), FakeResponse(201, {"id": "m1"})],
    )
    mocker.patch(PROVIDER_REQUEST, return_value=token_response(scope=""))

    answer = StubOAuthServiceType().dispatch_data(service, {"chat": "c/1"}, None)

    assert answer == {"id": "m1"}
    first, second = api.call_args_list
    assert first.kwargs["headers"]["Authorization"] == "Bearer access-token"
    assert second.kwargs["headers"]["Authorization"] == "Bearer new-access"
    assert second.kwargs["allow_redirects"] is False
    assert second.kwargs["send_netrc_credentials"] is False
    assert second.kwargs["url"] == "https://api.example.com/v1/chats/c%2F1/messages"


@pytest.mark.django_db
def test_a_token_refused_twice_must_be_connected_again(
    data_fixture, fake_oauth, mocker
):
    service = send_message_service(data_fixture, fake_oauth)
    mocker.patch(API_REQUEST, return_value=FakeResponse(401, {}))
    mocker.patch(PROVIDER_REQUEST, return_value=token_response(scope=""))

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        StubOAuthServiceType().dispatch_data(service, {}, None)

    assert "connected again" in str(exc_info.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "answer,expected",
    [
        (
            FakeResponse(403, {"error": {"code": "Forbidden"}}),
            RemoteRefusedDispatchException,
        ),
        (FakeResponse(404, {}), RemoteRefusedDispatchException),
        (
            FakeResponse(400, {"error": {"code": "BadRequest"}}),
            RemoteRefusedDispatchException,
        ),
        (FakeResponse(429, {}, {"Retry-After": "7"}), RemoteBusyDispatchException),
        (FakeResponse(503, {}), RemoteBusyDispatchException),
        # Not followed: the token only goes where it was configured to.
        (
            FakeResponse(302, None, {"Location": "https://evil.example.com"}),
            RemoteRefusedDispatchException,
        ),
        (request_exceptions.ReadTimeout("secret"), RuntimeDispatchException),
    ],
)
def test_api_errors_become_dispatch_exceptions(
    data_fixture, fake_oauth, mocker, answer, expected
):
    service = send_message_service(data_fixture, fake_oauth)
    if isinstance(answer, Exception):
        mocker.patch(API_REQUEST, side_effect=answer)
    else:
        mocker.patch(API_REQUEST, return_value=answer)

    with pytest.raises(expected) as exc_info:
        StubOAuthServiceType().dispatch_data(service, {}, None)

    assert "secret" not in str(exc_info.value)


@pytest.mark.django_db
def test_api_errors_carry_the_code_and_never_the_message(
    data_fixture, fake_oauth, mocker
):
    service = send_message_service(data_fixture, fake_oauth)
    mocker.patch(
        API_REQUEST,
        return_value=FakeResponse(
            400, {"error": {"code": "InvalidBody", "message": "row data here"}}
        ),
    )

    with pytest.raises(RemoteRefusedDispatchException) as exc_info:
        StubOAuthServiceType().dispatch_data(service, {}, None)

    assert "InvalidBody" in str(exc_info.value)
    assert "row data" not in str(exc_info.value)


@pytest.mark.django_db
def test_an_id_that_isnt_a_path_segment_is_refused(data_fixture, fake_oauth, mocker):
    service = send_message_service(data_fixture, fake_oauth)
    api = mocker.patch(API_REQUEST)

    with pytest.raises(ValueError):
        StubOAuthServiceType().dispatch_data(service, {"chat": ".."}, None)

    api.assert_not_called()


@pytest.mark.django_db
def test_service_types_explain_what_must_be_fixed(data_fixture, fake_oauth, mocker):
    service_type = StubOAuthServiceType()

    missing = send_message_service(data_fixture, fake_oauth, scopes=["openid", "email"])
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service_type.dispatch_data(missing, {}, None)
    assert "hasn't allowed Baserow to send messages yet" in str(exc_info.value)

    disconnected = send_message_service(data_fixture, fake_oauth, connected=False)
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service_type.dispatch_data(disconnected, {}, None)
    assert "connected again" in str(exc_info.value)

    other_type = data_fixture.create_local_baserow_get_row_service(
        integration=data_fixture.create_slack_bot_integration()
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service_type.dispatch_data(other_type, {}, None)
    assert "not a Example account" in str(exc_info.value)

    no_integration = data_fixture.create_local_baserow_get_row_service()
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        service_type.dispatch_data(no_integration, {}, None)


@pytest.mark.django_db
def test_only_transient_token_failures_are_retryable_dispatch_errors(
    data_fixture, fake_oauth, mocker
):
    service_type = StubOAuthServiceType()

    def service():
        return data_fixture.create_local_baserow_get_row_service(
            integration=expiring(fake_oauth, scopes=SEND_SCOPES)
        )

    # The provider is down, whatever the body says: try again later.
    mocker.patch(
        PROVIDER_REQUEST,
        return_value=FakeResponse(503, {"error": "invalid_grant"}),
    )
    transient = service()
    with pytest.raises(RuntimeDispatchException):
        service_type.dispatch_data(transient, {}, None)
    transient.integration.specific.refresh_from_db()
    assert transient.integration.specific.connected is True

    # A refusal that isn't about the account won't pass on a retry.
    mocker.patch(PROVIDER_REQUEST, return_value=token_error("invalid_scope"))
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service_type.dispatch_data(service(), {}, None)
    assert not isinstance(exc_info.value, RuntimeDispatchException)

    mocker.patch(PROVIDER_REQUEST, return_value=token_error("invalid_client"))
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service_type.dispatch_data(service(), {}, None)
    assert "Contact your Baserow admin" in str(exc_info.value)


@pytest.mark.django_db
def test_the_api_deadline_bounds_the_token_refresh_too(
    data_fixture, fake_oauth, mocker
):
    service = data_fixture.create_local_baserow_get_row_service(
        integration=expiring(fake_oauth, scopes=SEND_SCOPES)
    )
    refresh = mocker.patch(PROVIDER_REQUEST, return_value=token_response(scope=""))
    mocker.patch(API_REQUEST, return_value=FakeResponse(200, {}))
    deadline = time.monotonic() + 5

    StubOAuthServiceType().request_as_account(
        service, "GET", "https://api.example.com/v1/me", deadline=deadline
    )

    assert refresh.call_args.kwargs["deadline"] <= deadline


@pytest.mark.django_db
def test_services_say_which_scopes_are_missing(data_fixture, fake_oauth):
    service_type = StubOAuthServiceType()

    def missing(**kwargs):
        service = data_fixture.create_local_baserow_get_row_service(
            integration=fake_oauth.create(**kwargs)
        )
        return service_type.get_missing_scopes(service)

    assert missing(scopes=["openid"]) == ["Messages.Send"]
    assert missing(scopes=SEND_SCOPES) == []
    # Nothing to grant before it's connected.
    assert missing(connected=False) == []


@pytest.mark.django_db
def test_services_say_which_scopes_they_need_without_querying(
    data_fixture, fake_oauth, django_assert_num_queries
):
    service_type = StubOAuthServiceType()
    service = data_fixture.create_local_baserow_get_row_service(
        integration=fake_oauth.create()
    )
    service_type.required_scopes = ["messages.send", "Messages.Send", "Chat.Read"]

    with django_assert_num_queries(0):
        serialized = service_type.get_serializer(service, ServiceSerializer).data

    # As the provider normalizes them, to compare with an integration's scopes.
    assert serialized["required_scopes"] == ["Chat.Read", "messages.send"]
    # Never in requests, nor in public serializers.
    assert "required_scopes" not in service_type.get_field_names(True, {})
    assert "required_scopes" not in service_type.get_field_names(
        False, {"public": True}
    )
