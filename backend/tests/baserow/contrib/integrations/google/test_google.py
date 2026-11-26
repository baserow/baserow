import base64
import time
from datetime import timedelta
from email import policy
from email.parser import BytesParser
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from django.utils import timezone

import pytest
from requests.exceptions import Timeout

from baserow.api.integrations.serializers import IntegrationSerializer
from baserow.contrib.integrations.google.models import GoogleIntegration
from baserow.contrib.integrations.google.providers import (
    GMAIL_SEND_SCOPE,
    GoogleOAuthProvider,
)
from baserow.contrib.integrations.google.service_types import (
    GoogleGmailSendEmailServiceType,
)
from baserow.contrib.integrations.oauth_account.exceptions import OAuthFailed
from baserow.contrib.integrations.oauth_account.providers import OAuthClient, TokenSet
from baserow.contrib.integrations.oauth_account.service import OAuthAccountService
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.test_utils.pytest_conftest import FakeDispatchContext

pytestmark = pytest.mark.django_db
API_REQUEST = (
    "baserow.contrib.integrations.oauth_account.service_types.send_http_request"
)
TOKEN_REQUEST = "baserow.contrib.integrations.oauth_account.providers.send_http_request"
IDENTITY_REQUEST = "baserow.contrib.integrations.google.providers.send_http_request"


def response(payload, status=200):
    return Mock(status_code=status, json=Mock(return_value=payload), headers={})


@pytest.fixture
def google(data_fixture):
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
    integration.account_id = "account"
    integration.account_email = "sender@example.com"
    integration.scopes = [
        GMAIL_SEND_SCOPE,
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ]
    integration.access_token = "access"
    integration.refresh_token = "refresh"
    integration.expires_at = timezone.now() + timedelta(hours=1)
    integration.connected_at = timezone.now()
    integration.connected_by = user
    integration.connected_client = (
        GoogleOAuthProvider().get_client(integration).fingerprint
    )
    integration.save()
    return user, app, integration


def test_google_custom_and_instance_clients(google, settings):
    user, app, integration = google
    provider = GoogleOAuthProvider()
    assert provider.get_client(integration) == OAuthClient("client", "secret")
    settings.GOOGLE_OAUTH_CLIENT_ID = "global"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "global-secret"
    integration.client_mode = "default"
    assert provider.get_client(integration) == OAuthClient("global", "global-secret")
    assert not integration.connected


def test_google_sign_in_uses_shared_flow_and_actual_grants(google):
    """The Google adapter delegates PKCE/state/storage and keeps partial consent."""
    user, app, integration = google
    service = OAuthAccountService(integration.get_type())
    url = service.start_sign_in(
        user, ["google_gmail_send_email"], integration_id=integration.id
    )
    query = parse_qs(urlparse(url).query)
    assert query["access_type"] == ["offline"]
    assert query["include_granted_scopes"] == ["true"]
    assert query["code_challenge_method"] == ["S256"]
    assert GMAIL_SEND_SCOPE in query["scope"][0]
    assert "calendar" not in query["scope"][0]
    assert query["redirect_uri"][0].endswith("/integrations/google/oauth-callback")
    with (
        patch(
            TOKEN_REQUEST,
            return_value=response(
                {
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                    "scope": "openid email",
                }
            ),
        ),
        patch(
            IDENTITY_REQUEST,
            return_value=response(
                {
                    "sub": "account",
                    "email": "sender@example.com",
                    "email_verified": True,
                }
            ),
        ),
    ):
        result = service.complete_sign_in(user, query["state"][0], "code")
    assert not result.created
    assert result.integration.connected
    assert result.integration.scopes == [
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    ]
    gmail = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(), integration=result.integration
    )
    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException, match="hasn't allowed"
    ):
        gmail.get_type().get_access_token(gmail)


@pytest.mark.parametrize("verified", [False, None])
def test_google_identity_must_be_verified(verified):
    provider = GoogleOAuthProvider()
    tokens = TokenSet("access", "refresh", timezone.now(), [], {})
    with patch(
        IDENTITY_REQUEST,
        return_value=response(
            {
                "sub": "account",
                "email": "sender@example.com",
                "email_verified": verified,
            }
        ),
    ):
        with pytest.raises(OAuthFailed):
            provider.identify(
                OAuthClient("client", "secret"), tokens, time.monotonic() + 20
            )


@pytest.mark.parametrize("omit_client_secret", [False, True])
def test_google_export_uses_shared_privacy_policy(google, omit_client_secret):
    """Redacted and omitted client secrets import without restoring credentials."""
    user, app, integration = google
    serialized = (
        integration.get_type().get_serializer(integration, IntegrationSerializer).data
    )
    assert serialized["connected"]
    assert not {"access_token", "refresh_token", "client_secret"} & serialized.keys()
    exported = IntegrationHandler().export_integration(
        integration,
        ImportExportConfig(include_permission_data=False, exclude_sensitive_data=True),
    )
    assert exported["client_secret"] is None
    assert exported["access_token"] is None
    if omit_client_secret:
        exported.pop("client_secret")
    imported = IntegrationHandler().import_integration(app, exported, {})
    imported.refresh_from_db()
    assert not imported.connected
    assert imported.client_secret == ""
    assert imported.access_token == ""
    assert imported.refresh_token == ""
    assert imported.connected_at is None
    assert imported.connected_by_id is None


@pytest.mark.parametrize("body_type", ["plain", "html"])
def test_gmail_send_mime_and_result(google, body_type):
    """Gmail's MIME envelope, formulas and returned IDs work through shared transport."""
    user, app, integration = google
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
    with patch(
        API_REQUEST, return_value=response({"id": "message", "threadId": "thread"})
    ) as request:
        result = kind.dispatch(service, FakeDispatchContext())
    assert result.data == {"id": "message", "threadId": "thread"}
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer access"
    message = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(request.call_args.kwargs["json"]["raw"])
    )
    assert message["From"] == "sender@example.com"
    assert message["To"] == "to@example.com"
    assert message["Cc"] == "cc@example.com"
    assert message["Bcc"] == "hidden@example.com"
    assert message["Subject"] == "Héllo"
    assert message.get_content_type() == f"text/{body_type}"
    assert message.get_content().strip() == "Bonjour ☀"
    assert set(kind.generate_schema(service)["properties"]) == {"id", "threadId"}


@pytest.mark.parametrize(
    "reason,error",
    [
        ("userRateLimitExceeded", RemoteBusyDispatchException),
        ("insufficientPermissions", RemoteRefusedDispatchException),
    ],
)
def test_gmail_error_codes(google, reason, error):
    user, app, integration = google
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(),
        integration=integration,
        to_emails="'to@example.com'",
        subject="'Subject'",
        body="'Body'",
    )
    with patch(
        API_REQUEST,
        return_value=response({"error": {"errors": [{"reason": reason}]}}, 403),
    ):
        with pytest.raises(error):
            service.get_type().dispatch(service, FakeDispatchContext())


def test_gmail_timeout_never_retries_send(google):
    user, app, integration = google
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(),
        integration=integration,
        to_emails="'to@example.com'",
        subject="'Subject'",
        body="'Body'",
    )
    with patch(API_REQUEST, side_effect=Timeout("private content")) as request:
        with pytest.raises(RuntimeDispatchException) as error:
            service.get_type().dispatch(service, FakeDispatchContext())
        request.assert_called_once()
    assert "private content" not in str(error.value)


def test_gmail_header_injection_rejected_before_send(google):
    user, app, integration = google
    service = ServiceHandler().create_service(
        GoogleGmailSendEmailServiceType(), integration=integration
    )
    with patch(API_REQUEST) as request:
        with pytest.raises(InvalidContextContentDispatchException):
            service.get_type().dispatch_data(
                service,
                {
                    "to_emails": ["to@example.com"],
                    "cc_emails": [],
                    "bcc_emails": [],
                    "subject": "Subject\r\nBcc: attacker@example.com",
                    "body": "Body",
                },
                FakeDispatchContext(),
            )
        request.assert_not_called()


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
