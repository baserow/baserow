import base64
from datetime import timedelta
from email import policy
from email.parser import BytesParser
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.utils import timezone

import pytest
from rest_framework.exceptions import ValidationError

from baserow.api.integrations.serializers import IntegrationSerializer
from baserow.contrib.integrations.google import oauth
from baserow.contrib.integrations.google import service as google_service
from baserow.contrib.integrations.google.models import GoogleIntegration
from baserow.contrib.integrations.google.service_types import (
    GoogleGmailSendEmailServiceType,
)
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.test_utils.pytest_conftest import FakeDispatchContext

pytestmark = pytest.mark.django_db


@pytest.fixture
def google(data_fixture):
    """Return the Google configuration fields supported by this operation."""
    user = data_fixture.create_user()
    app = data_fixture.create_automation_application(user=user)
    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("google"),
        application=app,
        client_mode="custom",
        client_id="client",
        client_secret="secret",
    )
    return user, app, integration


def connect(integration):
    integration.access_token = "access"
    integration.refresh_token = "refresh"
    integration.expires_at = timezone.now() + timedelta(hours=1)
    integration.granted_scopes = [oauth.GMAIL_SEND_SCOPE, *oauth.IDENTITY_SCOPES]
    integration.account_id = "account"
    integration.account_email = "sender@example.com"
    integration.connected_client = oauth.client_fingerprint(integration)
    integration.connected = True
    integration.save()


def token_response(**overrides):
    return {
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "expires_in": 3600,
        "scope": "openid https://www.googleapis.com/auth/userinfo.email "
        + oauth.GMAIL_SEND_SCOPE,
        **overrides,
    }


def state_for(user, integration, service_type="google_gmail_send_email"):
    return parse_qs(
        urlparse(google_service.start(user, integration.id, service_type)).query
    )["state"][0]


def test_authorize_pkce_and_default_client(google, settings):
    """Verify authorize pkce and default client."""
    user, app, integration = google
    query = parse_qs(
        urlparse(
            google_service.start(user, integration.id, "google_gmail_send_email")
        ).query
    )
    assert query["access_type"] == ["offline"]
    assert query["code_challenge_method"] == ["S256"]
    assert oauth.GMAIL_SEND_SCOPE in query["scope"][0]
    assert "calendar" not in query["scope"][0]
    integration.client_mode = "default"
    integration.save()
    with pytest.raises(ValidationError):
        google_service.start(user, integration.id)
    settings.GOOGLE_OAUTH_CLIENT_ID = "global-client"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "global-secret"
    query = parse_qs(urlparse(google_service.start(user, integration.id)).query)
    assert query["client_id"] == ["global-client"]
    assert oauth.GMAIL_SEND_SCOPE not in query["scope"][0]


def test_complete_one_time_user_bound_state(google, data_fixture):
    """Verify complete one time user bound state."""
    user, app, integration = google
    state = state_for(user, integration)
    other = data_fixture.create_user()
    with pytest.raises(ValidationError):
        google_service.complete(other, state, "code")
    with patch.object(
        oauth,
        "request_json",
        side_effect=[
            (200, token_response()),
            (
                200,
                {
                    "sub": "account",
                    "email": "sender@example.com",
                    "email_verified": True,
                },
            ),
        ],
    ):
        connected = google_service.complete(user, state, "code")
    assert connected.connected
    assert connected.account_id == "account"
    with pytest.raises(ValidationError):
        google_service.complete(user, state, "code")


@pytest.mark.parametrize(
    "cause", ["expired", "superseded", "disconnected", "changed_client"]
)
def test_stale_state(google, cause):
    """Verify stale state."""
    user, app, integration = google
    state = state_for(user, integration)
    if cause == "expired":
        cache.delete(f"google_oauth:{state}")
    elif cause == "superseded":
        state_for(user, integration)
    elif cause == "disconnected":
        google_service.disconnect(user, integration.id)
    else:
        integration.client_id = "different"
        integration.save()
    with patch.object(oauth, "request_json") as request:
        with pytest.raises(ValidationError):
            google_service.complete(user, state, "code")
        request.assert_not_called()


def test_reconnect_rejects_different_account(google):
    """Verify reconnect rejects different account."""
    user, app, integration = google
    connect(integration)
    state = state_for(user, integration)
    with patch.object(
        oauth,
        "request_json",
        side_effect=[
            (200, token_response()),
            (
                200,
                {
                    "sub": "other-account",
                    "email": "other@example.com",
                    "email_verified": True,
                },
            ),
        ],
    ):
        with pytest.raises(ValidationError, match="different Google account"):
            google_service.complete(user, state, "code")
    integration.refresh_from_db()
    assert integration.access_token == "access"
    assert integration.account_id == "account"


def test_partial_consent_stored_and_send_blocked(google):
    """Verify partial consent stored and send blocked."""
    user, app, integration = google
    state = state_for(user, integration)
    with patch.object(
        oauth,
        "request_json",
        side_effect=[
            (200, token_response(scope="openid email")),
            (
                200,
                {
                    "sub": "account",
                    "email": "sender@example.com",
                    "email_verified": True,
                },
            ),
        ],
    ):
        integration = google_service.complete(user, state, "code")
    assert integration.granted_scopes == ["openid", "email"]
    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException, match="permissions"
    ):
        oauth.access_token(integration.id, [oauth.GMAIL_SEND_SCOPE])


def test_refresh_preserves_token_and_avoids_second_refresh(google):
    """Verify refresh preserves token and avoids second refresh."""
    user, app, integration = google
    connect(integration)
    integration.expires_at = timezone.now()
    integration.save()
    token = token_response()
    del token["refresh_token"]
    with patch.object(oauth, "request_json", return_value=(200, token)) as request:
        assert (
            oauth.access_token(integration.id, [oauth.GMAIL_SEND_SCOPE])[0]
            == "new-access"
        )
        assert (
            oauth.access_token(integration.id, [oauth.GMAIL_SEND_SCOPE])[0]
            == "new-access"
        )
        request.assert_called_once()
    integration.refresh_from_db()
    assert integration.refresh_token == "refresh"


def test_refresh_revocation_persisted_and_transient_error_preserves_credentials(google):
    """Verify refresh revocation persisted and transient error preserves credentials."""
    user, app, integration = google
    connect(integration)
    integration.expires_at = timezone.now()
    integration.save()
    with patch.object(
        oauth, "request_json", side_effect=RemoteBusyDispatchException("busy")
    ):
        with pytest.raises(RemoteBusyDispatchException):
            oauth.access_token(integration.id, [oauth.GMAIL_SEND_SCOPE])
    integration.refresh_from_db()
    assert integration.refresh_token == "refresh"
    with patch.object(
        oauth, "request_json", return_value=(400, {"error": "invalid_grant"})
    ):
        with pytest.raises(ServiceImproperlyConfiguredDispatchException):
            oauth.access_token(integration.id, [oauth.GMAIL_SEND_SCOPE])
    integration.refresh_from_db()
    assert not integration.connected
    assert not integration.refresh_token


def test_api_export_import_and_publication(google):
    """Verify api export import and publication."""
    user, app, integration = google
    connect(integration)
    kind = integration.get_type()
    response = kind.get_serializer(integration, IntegrationSerializer).data
    assert response["has_client_secret"]
    assert not {"access_token", "refresh_token", "client_secret"} & response.keys()
    exported = IntegrationHandler().export_integration(
        integration,
        ImportExportConfig(include_permission_data=False, exclude_sensitive_data=False),
    )
    assert exported["client_secret"] == ""
    assert "access" not in str(exported)
    assert "refresh" not in str(exported)
    imported = IntegrationHandler().import_integration(app, exported, {})
    assert not imported.connected
    assert not imported.client_secret
    published = IntegrationHandler().import_integration(
        app,
        exported,
        {},
        import_export_config=ImportExportConfig(
            include_permission_data=False, is_publishing=True
        ),
    )
    assert published.credential_source_id == integration.id
    google_service.disconnect(user, integration.id)
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        oauth.access_token(published.credential_source_id, [oauth.GMAIL_SEND_SCOPE])


@pytest.mark.parametrize("body_type", ["plain", "html"])
def test_send_mime_formulas_and_downstream_result(google, body_type):
    """Verify send mime formulas and downstream result."""
    user, app, integration = google
    connect(integration)
    kind = GoogleGmailSendEmailServiceType()
    service = ServiceHandler().create_service(
        kind,
        integration=integration,
        to_emails="'to@example.com'",
        cc_emails="'cc@example.com'",
        bcc_emails="'hidden@example.com'",
        subject="'Héllo'",
        body="'Bonjour ☀'",
        body_type=body_type,
    )
    with patch.object(
        oauth,
        "request_json",
        return_value=(200, {"id": "message", "threadId": "thread"}),
    ) as request:
        result = kind.dispatch(service, FakeDispatchContext())
    assert result.data == {"id": "message", "threadId": "thread"}
    raw = request.call_args.kwargs["json"]["raw"]
    message = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(raw)
    )
    assert message["From"] == "sender@example.com"
    assert message["To"] == "to@example.com"
    assert message["Cc"] == "cc@example.com"
    assert message["Bcc"] == "hidden@example.com"
    assert message["Subject"] == "Héllo"
    assert message.get_content_type() == f"text/{body_type}"
    assert message.get_content().strip() == "Bonjour ☀"
    exported = kind.export_serialized(service)
    assert exported["to_emails"] == service.to_emails
    assert set(kind.generate_schema(service)["properties"]) == set(result.data)


def test_header_injection_rejected_before_send(google):
    """Verify header injection rejected before send."""
    user, app, integration = google
    connect(integration)
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(), integration=integration
    )
    with patch.object(oauth, "request_json") as request:
        with pytest.raises(InvalidContextContentDispatchException):
            service.get_type().dispatch_data(
                service,
                {
                    "to_emails": ["to@example.com"],
                    "cc_emails": [],
                    "bcc_emails": [],
                    "subject": "hello\r\nBcc: attacker@example.com",
                    "body": "body",
                },
                FakeDispatchContext(),
            )
        request.assert_not_called()


def test_oauth_endpoints_require_edit_permissions(google, data_fixture, api_client):
    """Verify oauth endpoints require edit permissions."""
    user, app, integration = google
    stranger, stranger_token = data_fixture.create_user_and_token()
    url = f"/api/integrations/google/{integration.id}/oauth/start/"
    assert api_client.post(url, {}).status_code == 401
    response = api_client.post(url, {}, HTTP_AUTHORIZATION=f"JWT {stranger_token}")
    assert response.status_code in (400, 401, 403)
    integration.refresh_from_db()
    assert integration.generation == 0
    token = data_fixture.generate_token(user)
    response = api_client.post(
        url,
        {"service_type": "google_gmail_send_email"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    state = parse_qs(urlparse(response.json()["authorization_url"]).query)["state"][0]
    response = api_client.post(
        "/api/integrations/google/oauth/complete/",
        {"state": state, "code": ""},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert cache.get(f"google_oauth:{state}") is None


def test_client_change_disconnects_and_invalidates_pending_flow(google, settings):
    """Verify client change disconnects and invalidates pending flow."""
    user, app, integration = google
    connect(integration)
    state = state_for(user, integration)
    # In production the service is called while the integration row is locked.
    from django.db import transaction

    with transaction.atomic():
        locked = IntegrationHandler().get_integration_for_update(integration.id)
        IntegrationService().update_integration(
            user, locked.specific, client_id="new-client", client_secret="new-secret"
        )
    integration.refresh_from_db()
    assert not integration.connected
    assert not integration.access_token
    assert not integration.refresh_token
    with pytest.raises(ValidationError):
        google_service.complete(user, state, "code")


@pytest.mark.django_db(transaction=True)
def test_concurrent_refreshes_use_refresh_token_once(data_fixture):
    """Two workers must share the refreshed token, including when Google rotates it."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections

    user = data_fixture.create_user()
    app = data_fixture.create_automation_application(user=user)
    integration = GoogleIntegration.objects.create(
        application=app, client_id="client", client_secret="secret"
    )
    connect(integration)
    integration.expires_at = timezone.now()
    integration.save()
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return oauth.access_token(integration.id, [oauth.GMAIL_SEND_SCOPE])[0]
        finally:
            close_old_connections()

    with patch.object(
        oauth, "request_json", return_value=(200, token_response())
    ) as request:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
    assert results == ["new-access", "new-access"]
    assert request.call_count == 1
    integration.refresh_from_db()
    assert integration.refresh_token == "new-refresh"


@pytest.mark.parametrize(
    "body,status,error",
    [
        (
            {"error": {"errors": [{"reason": "userRateLimitExceeded"}]}},
            403,
            RemoteBusyDispatchException,
        ),
        (
            {"error": {"errors": [{"reason": "insufficientPermissions"}]}},
            403,
            RemoteRefusedDispatchException,
        ),
    ],
)
def test_google_send_errors(google, body, status, error):
    """Verify google send errors."""
    user, app, integration = google
    connect(integration)
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(),
        integration=integration,
        to_emails="'to@example.com'",
        subject="'Subject'",
        body="'Body'",
    )
    with patch.object(oauth, "request_json", return_value=(status, body)):
        with pytest.raises(error):
            service.get_type().dispatch(service, FakeDispatchContext())


def test_ambiguous_timeout_sends_once_and_does_not_expose_message(google):
    """Verify ambiguous timeout sends once and does not expose message."""
    from requests.exceptions import Timeout

    from baserow.core.services.exceptions import RuntimeDispatchException

    user, app, integration = google
    connect(integration)
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(),
        integration=integration,
        to_emails="'to@example.com'",
        subject="'private subject'",
        body="'private body'",
    )
    with patch.object(
        oauth, "send_http_request", side_effect=Timeout("private body access-token")
    ) as request:
        with pytest.raises(
            RuntimeDispatchException, match="Google could not be reached"
        ) as exc:
            service.get_type().dispatch(service, FakeDispatchContext())
        request.assert_called_once()
    assert "private" not in str(exc.value)


def test_simulation_replays_sample_without_google(google):
    """Verify simulation replays sample without google."""
    user, app, integration = google
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(),
        integration=integration,
        sample_data={"data": {"id": "sample-message", "threadId": "sample-thread"}},
    )
    service.sample_data = {
        "data": {"id": "sample-message", "threadId": "sample-thread"}
    }
    service.save()
    context = FakeDispatchContext(use_sample_data=True)
    with patch.object(oauth, "request_json") as request:
        result = service.get_type().dispatch(service, context)
        request.assert_not_called()
    assert result.data == {"id": "sample-message", "threadId": "sample-thread"}


@pytest.mark.parametrize("surface", ["automation", "builder", "database"])
def test_google_action_roundtrip_for_each_surface(data_fixture, surface):
    """Product wrappers must keep Gmail formulas and remap their integration on import."""
    user = data_fixture.create_user()
    app = getattr(
        data_fixture,
        f"create_{'builder' if surface == 'builder' else surface}_application",
    )(user=user)
    integration = GoogleIntegration.objects.create(
        application=app, client_id="client", client_secret="secret"
    )
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(),
        integration=integration,
        to_emails="'recipient@example.com'",
        subject="'Subject'",
        body="'Body'",
    )
    if surface == "automation":
        from baserow.contrib.automation.nodes.registries import (
            automation_node_type_registry,
        )

        kind = automation_node_type_registry.get("google_gmail_send_email")
        workflow = data_fixture.create_automation_workflow(user=user, automation=app)
        action = data_fixture.create_automation_node(
            user=user, type=kind, workflow=workflow, service=service
        )
        parent = workflow
    elif surface == "builder":
        from baserow.contrib.builder.workflow_actions.registries import (
            builder_workflow_action_type_registry,
        )

        kind = builder_workflow_action_type_registry.get("google_gmail_send_email")
        page = data_fixture.create_builder_page(builder=app)
        action = data_fixture.create_workflow_action(
            kind.model_class, page=page, service=service
        )
        parent = page
    else:
        from baserow.contrib.database.workflow_actions.registries import (
            database_workflow_action_type_registry,
        )

        kind = database_workflow_action_type_registry.get("google_gmail_send_email")
        table = data_fixture.create_database_table(database=app)
        field = data_fixture.create_button_field(table=table)
        action = data_fixture.create_database_workflow_action(
            kind.model_class, field=field, service=service
        )
        parent = field
    serialized = kind.export_serialized(action)
    replacement = GoogleIntegration.objects.create(application=app)
    mapping = {
        "integrations": {integration.id: replacement.id},
        "builder_page_elements": {None: None},
        "builder_pages": {parent.id: parent.id},
    }
    from baserow.core.deferred_callbacks import deferred_callback_context

    with deferred_callback_context():
        imported = kind.import_serialized(parent, serialized, mapping)
    assert imported.service.specific.integration_id == replacement.id
    assert imported.service.specific.subject == service.subject
    assert imported.service.specific.to_emails == service.to_emails


@pytest.mark.django_db(transaction=True)
def test_rotated_refresh_token_survives_send_failure(data_fixture):
    """A failed send cannot roll back the new refresh token Google already issued."""
    user = data_fixture.create_user()
    app = data_fixture.create_automation_application(user=user)
    integration = GoogleIntegration.objects.create(
        application=app, client_id="client", client_secret="secret"
    )
    connect(integration)
    integration.expires_at = timezone.now()
    integration.save()
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(),
        integration=integration,
        to_emails="'to@example.com'",
        subject="'Subject'",
        body="'Body'",
    )
    with patch.object(
        oauth,
        "request_json",
        side_effect=[(200, token_response()), RemoteBusyDispatchException("busy")],
    ):
        with pytest.raises(RemoteBusyDispatchException):
            service.get_type().dispatch(service, FakeDispatchContext())
    integration.refresh_from_db()
    assert integration.refresh_token == "new-refresh"
    assert integration.access_token == "new-access"
