from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.workflows.constants import WorkflowState

from ...inbound_email_test_utils import make_mox_payload

INBOUND_DOMAIN = "inbound.test"
SECRET = "super-secret-value"
TOKEN = "a" * 32
ADDRESS = f"{TOKEN}@{INBOUND_DOMAIN}"


def get_url():
    return reverse("api:inbound_email")


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.mark.django_db
@override_settings(
    INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET=SECRET
)
@pytest.mark.parametrize("http_method", ["get", "put", "patch", "delete"])
def test_rejects_disallowed_methods(api_client, http_method):
    resp = getattr(api_client, http_method)(get_url(), HTTP_AUTHORIZATION=SECRET)

    assert resp.status_code == HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
@override_settings(
    INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET=SECRET
)
def test_rejects_missing_authorization_header(api_client):
    resp = api_client.post(get_url(), make_mox_payload(ADDRESS), format="json")

    assert resp.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(
    INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET=SECRET
)
def test_rejects_wrong_secret(api_client):
    resp = api_client.post(
        get_url(),
        make_mox_payload(ADDRESS),
        format="json",
        HTTP_AUTHORIZATION="wrong-secret",
    )

    assert resp.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET="")
def test_rejects_all_requests_when_secret_not_configured(api_client):
    # An empty Authorization header must never match an empty configured
    # secret.
    resp = api_client.post(
        get_url(), make_mox_payload(ADDRESS), format="json", HTTP_AUTHORIZATION=""
    )

    assert resp.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(
    INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET=SECRET
)
def test_rejects_malformed_payload(api_client):
    resp = api_client.post(
        get_url(),
        {"not": "a mox payload"},
        format="json",
        HTTP_AUTHORIZATION=SECRET,
    )

    assert resp.status_code == HTTP_400_BAD_REQUEST
    assert resp.json()["error"] == "ERROR_INVALID_INBOUND_EMAIL_PAYLOAD"


@pytest.mark.django_db
@override_settings(
    INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET=SECRET
)
def test_discards_unknown_token(api_client):
    resp = api_client.post(
        get_url(),
        make_mox_payload(ADDRESS),
        format="json",
        HTTP_AUTHORIZATION=SECRET,
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.json() == {"status": "discarded"}


@pytest.mark.django_db(transaction=True)
@override_settings(
    INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET=SECRET
)
def test_accepts_email_and_starts_live_workflow(api_client, data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(
        user=user, automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=automation
    )

    trigger_node = data_fixture.create_inbound_email_trigger_node(
        workflow=workflow,
        service_kwargs={"token": TOKEN, "is_public": True},
    )

    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, fields, _ = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Name", "text")],
        rows=[],
    )
    action_service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    action_service.field_mappings.create(
        field=fields[0],
        value=f"get('previous_node.{trigger_node.id}.subject')",
    )
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        service=action_service,
    )

    resp = api_client.post(
        get_url(),
        make_mox_payload(ADDRESS),
        format="json",
        HTTP_AUTHORIZATION=SECRET,
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.json() == {"status": "accepted"}

    model = table.get_model()
    rows = model.objects.all()
    assert len(rows) == 1
    assert getattr(rows[0], f"field_{fields[0].id}") == "Hello from Ada"


@pytest.mark.django_db(transaction=True)
@override_settings(
    INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET=SECRET
)
def test_duplicate_delivery_is_idempotent(api_client, data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, state=WorkflowState.LIVE, create_trigger=False
    )
    data_fixture.create_inbound_email_trigger_node(
        workflow=workflow,
        service_kwargs={"token": TOKEN, "is_public": True},
    )

    payload = make_mox_payload(ADDRESS)

    resp = api_client.post(get_url(), payload, format="json", HTTP_AUTHORIZATION=SECRET)
    assert resp.json() == {"status": "accepted"}

    resp = api_client.post(get_url(), payload, format="json", HTTP_AUTHORIZATION=SECRET)
    assert resp.json() == {"status": "duplicate"}

    assert AutomationWorkflowHistory.objects.count() == 1


@pytest.mark.django_db(transaction=True)
@override_settings(
    INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN, INBOUND_EMAIL_WEBHOOK_SECRET=SECRET
)
def test_draft_workflow_not_started_outside_test_window(api_client, data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, state=WorkflowState.DRAFT, create_trigger=False
    )
    data_fixture.create_inbound_email_trigger_node(
        workflow=workflow,
        service_kwargs={"token": TOKEN},
    )

    resp = api_client.post(
        get_url(),
        make_mox_payload(ADDRESS),
        format="json",
        HTTP_AUTHORIZATION=SECRET,
    )

    # The message matches a service, so it is accepted, but the draft
    # workflow is not started because it is not in a test run window.
    assert resp.json() == {"status": "accepted"}
    assert AutomationWorkflowHistory.objects.count() == 0
