from unittest.mock import MagicMock

from django.test import override_settings

import pytest

from baserow.contrib.integrations.core.exceptions import (
    CoreInboundEmailTriggerServiceDoesNotExist,
)
from baserow.contrib.integrations.core.inbound_email import (
    InboundEmail,
    InboundEmailAddress,
)
from baserow.contrib.integrations.core.service_types import (
    CoreInboundEmailTriggerServiceType,
)
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.pytest_conftest import fake_import_formula

TOKEN = "a" * 32


def make_email():
    return InboundEmail(
        from_=InboundEmailAddress(name="Ada", address="ada@example.com"),
        subject="Hello",
        body_text="Hi",
        message_id="<id@example.com>",
    )


@pytest.mark.django_db
def test_token_is_generated_on_creation(data_fixture):
    service = data_fixture.create_core_inbound_email_trigger_service()

    assert len(service.token) == 32
    assert service.token == service.token.lower()

    other_service = data_fixture.create_core_inbound_email_trigger_service()
    assert other_service.token != service.token


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN="inbound.test")
def test_email_address_property(data_fixture):
    service = data_fixture.create_core_inbound_email_trigger_service(token=TOKEN)

    assert service.email_address == f"{TOKEN}@inbound.test"

    with override_settings(INBOUND_EMAIL_DOMAIN=""):
        assert service.email_address is None


@pytest.mark.django_db
def test_process_inbound_email_raises_if_unknown_token(data_fixture):
    with pytest.raises(CoreInboundEmailTriggerServiceDoesNotExist):
        CoreInboundEmailTriggerServiceType().process_inbound_email(TOKEN, make_email())


@pytest.mark.django_db
def test_process_inbound_email_dispatches_all_matching_services(data_fixture):
    trigger_node = data_fixture.create_inbound_email_trigger_node(
        service_kwargs={"token": TOKEN},
    )
    draft_service = trigger_node.service.specific
    published_service = data_fixture.create_core_inbound_email_trigger_service(
        token=TOKEN, is_public=True
    )

    service_type = CoreInboundEmailTriggerServiceType()
    service_type.on_event = MagicMock()

    service_type.process_inbound_email(TOKEN, make_email())

    services, event_payload = service_type.on_event.call_args.args
    assert {service.id for service in services} == {
        draft_service.id,
        published_service.id,
    }
    payload = event_payload(draft_service)
    assert payload["subject"] == "Hello"
    assert payload["from"] == {"name": "Ada", "address": "ada@example.com"}


@pytest.mark.django_db
def test_prepare_values_regenerates_token(data_fixture):
    user = data_fixture.create_user()
    service_type = CoreInboundEmailTriggerServiceType()

    values = service_type.prepare_values({"regenerate_token": True}, user)
    assert len(values["token"]) == 32

    values = service_type.prepare_values({"regenerate_token": False}, user)
    assert "token" not in values

    values = service_type.prepare_values({}, user)
    assert "token" not in values


@pytest.mark.django_db
@pytest.mark.parametrize("is_publishing", [True, False])
def test_import_serialized_sets_is_public(data_fixture, is_publishing):
    trigger_node = data_fixture.create_inbound_email_trigger_node()
    service = trigger_node.service.specific

    service_type = CoreInboundEmailTriggerServiceType()

    serialized_service = service_type.export_serialized(service)
    assert serialized_service["is_public"] is False

    import_export_config = ImportExportConfig(
        include_permission_data=True,
        reduce_disk_space_usage=False,
        exclude_sensitive_data=False,
        is_publishing=is_publishing,
    )
    instance = service_type.import_serialized(
        None,
        serialized_service,
        {},
        import_export_config,
        import_formula=fake_import_formula,
    )

    assert instance.is_public is is_publishing
    # Publishing must keep the same token so the address keeps working.
    assert instance.token == service.token


@pytest.mark.django_db
def test_import_serialized_regenerates_token_on_duplicate(data_fixture):
    trigger_node = data_fixture.create_inbound_email_trigger_node()
    service = trigger_node.service.specific

    service_type = CoreInboundEmailTriggerServiceType()
    serialized_service = service_type.export_serialized(service)

    import_export_config = ImportExportConfig(
        include_permission_data=True,
        reduce_disk_space_usage=False,
        exclude_sensitive_data=False,
        is_duplicate=True,
    )
    instance = service_type.import_serialized(
        None,
        serialized_service,
        {},
        import_export_config,
        import_formula=fake_import_formula,
    )

    assert len(instance.token) == 32
    assert instance.token != service.token


@pytest.mark.django_db
def test_generate_schema(data_fixture):
    trigger_node = data_fixture.create_inbound_email_trigger_node()
    service = trigger_node.service.specific

    schema = CoreInboundEmailTriggerServiceType().generate_schema(service)

    assert schema["title"] == f"EmailTrigger{service.id}Schema"
    assert schema["type"] == "object"
    properties = schema["properties"]
    assert set(properties.keys()) == {
        "from",
        "to",
        "cc",
        "reply_to",
        "rcpt_to",
        "recipient_tag",
        "subject",
        "body_text",
        "body_html",
        "message_id",
        "in_reply_to",
        "received_at",
        "attachments",
        "sender_validated",
        "dkim_verified_domains",
        "remote_ip",
    }
    assert properties["from"]["type"] == "object"
    assert properties["to"]["type"] == "array"
    assert properties["attachments"]["items"]["properties"]["filename"] == {
        "type": "string",
        "title": "Filename",
    }


@pytest.mark.django_db
def test_generate_schema_with_allowed_fields(data_fixture):
    trigger_node = data_fixture.create_inbound_email_trigger_node()
    service = trigger_node.service.specific

    schema = CoreInboundEmailTriggerServiceType().generate_schema(
        service, allowed_fields=["subject", "body_text"]
    )

    assert set(schema["properties"].keys()) == {"subject", "body_text"}


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN="inbound.test")
def test_dispatch_data_returns_sample_payload_without_event(data_fixture):
    trigger_node = data_fixture.create_inbound_email_trigger_node(
        service_kwargs={"token": TOKEN},
    )
    service = trigger_node.service.specific

    dispatch_context = MagicMock()
    dispatch_context.event_payload = None

    payload = CoreInboundEmailTriggerServiceType().dispatch_data(
        service, {}, dispatch_context
    )

    assert payload["subject"] == "Sample email subject"
    assert payload["to"] == [{"name": "", "address": f"{TOKEN}@inbound.test"}]


@pytest.mark.django_db
def test_dispatch_data_returns_event_payload(data_fixture):
    trigger_node = data_fixture.create_inbound_email_trigger_node()
    service = trigger_node.service.specific

    dispatch_context = MagicMock()
    dispatch_context.event_payload = {"subject": "real email"}

    payload = CoreInboundEmailTriggerServiceType().dispatch_data(
        service, {}, dispatch_context
    )

    assert payload == {"subject": "real email"}
