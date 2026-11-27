import pytest

from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.integrations.signals import integration_changed
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["create", "update", "delete", "restore", "promote"])
def test_integration_changes_notify_dependents_once(data_fixture, mocker, change):
    """Real lifecycle operations all expose the same dependency notification."""
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    shared = data_fixture.create_shared_application(workspace=application.workspace)
    integration = data_fixture.create_smtp_integration(application=application)
    service = IntegrationService()
    if change == "restore":
        service.delete_integration(user, integration)
    notification = mocker.spy(integration_changed, "send")

    if change == "create":
        integration = service.create_integration(
            user, integration_type_registry.get("smtp"), application, name="Email"
        )
    elif change == "update":
        service.update_integration(user, integration, name="Renamed")
    elif change == "delete":
        service.delete_integration(user, integration)
    elif change == "restore":
        TrashHandler.restore_item(user, "integration", integration.id)
    else:
        service.update_integration(user, integration, application_id=shared.id)
        application = shared

    assert notification.call_count == 1
    payload = notification.call_args.kwargs
    assert payload["integration_id"] == integration.id
    assert payload["application"].id == application.id
    assert payload["user"] == (None if change == "restore" else user)
    assert (
        payload["change_type"]
        == {
            "create": "created",
            "restore": "created",
            "update": "updated",
            "promote": "updated",
            "delete": "deleted",
        }[change]
    )
