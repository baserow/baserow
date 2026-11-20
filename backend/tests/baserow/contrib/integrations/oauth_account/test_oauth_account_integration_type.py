from django.contrib.auth import get_user_model
from django.urls import reverse

import pytest

from baserow.contrib.integrations.oauth_account.receivers import oauth_account_models
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig

from .fake_provider import FAKE_TYPE


@pytest.mark.django_db
def test_the_api_never_returns_the_tokens(api_client, data_fixture, fake_oauth):
    user, token = data_fixture.create_user_and_token()
    integration = fake_oauth.create(user=user)

    response = api_client.get(
        reverse(
            "api:integrations:list",
            kwargs={"application_id": integration.application_id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    [serialized] = response.json()
    assert serialized["connected"] is True
    assert serialized["account_email"] == "alice@example.com"
    assert serialized["scopes"] == ["email", "openid", "Profile.Read"]
    assert "access-token" not in str(serialized)
    assert "refresh-token" not in str(serialized)


@pytest.mark.django_db
def test_the_integration_api_can_only_rename_it(api_client, data_fixture, fake_oauth):
    user, token = data_fixture.create_user_and_token()
    integration = fake_oauth.create(user=user)

    response = api_client.patch(
        reverse("api:integrations:item", kwargs={"integration_id": integration.id}),
        {
            "name": "Renamed",
            "access_token": "planted",
            "refresh_token": "planted",
            "account_email": "mallory@example.com",
            "scopes": ["Mail.ReadWrite"],
            "connected_by_id": data_fixture.create_user().id,
            "tenant": "planted",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    integration.refresh_from_db()
    assert integration.name == "Renamed"
    assert integration.access_token == "access-token"  # nosec B105
    assert integration.account_email == "alice@example.com"
    assert integration.tenant == "contoso"
    assert integration.connected_by_id is None
    assert "Mail.ReadWrite" not in integration.scopes


@pytest.mark.django_db
def test_an_integration_created_through_the_api_isnt_connected(
    api_client, data_fixture, fake_oauth
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    response = api_client.post(
        reverse("api:integrations:list", kwargs={"application_id": application.id}),
        {"type": FAKE_TYPE, "name": "M", "refresh_token": "planted"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["connected"] is False
    assert fake_oauth.model.objects.get().refresh_token == ""


@pytest.mark.django_db
def test_exports_leave_the_account_out(data_fixture, fake_oauth):
    integration = fake_oauth.create()

    exported = fake_oauth.type.export_serialized(
        integration,
        ImportExportConfig(include_permission_data=False, exclude_sensitive_data=True),
    )
    for name in (
        "access_token",
        "refresh_token",
        "account_email",
        "account_id",
        "scopes",
        "connected_by_id",
        "tenant",
    ):
        assert exported[name] is None

    application = data_fixture.create_builder_application()
    imported = fake_oauth.type.import_serialized(application, exported, {})

    assert imported.connected is False
    assert imported.account_email == ""
    assert imported.scopes == []
    assert imported.expires_at is None
    assert imported.tenant == ""


@pytest.mark.django_db
def test_duplicates_keep_the_connection(data_fixture, fake_oauth):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = fake_oauth.create(
        application=builder, connected_by=user, scopes=["openid", "Messages.Send"]
    )

    clone = CoreHandler().duplicate_application(user, builder)

    copied = fake_oauth.model.objects.get(application=clone)
    assert copied.id != integration.id
    assert copied.connected is True
    assert copied.access_token == "access-token"  # nosec B105
    assert copied.refresh_token == "refresh-token"  # nosec B105
    assert copied.expires_at == integration.expires_at
    assert copied.connected_at == integration.connected_at
    assert copied.connected_by == user
    assert copied.scopes == ["openid", "Messages.Send"]
    assert copied.tenant == "contoso"


@pytest.mark.django_db
def test_a_provider_can_drop_the_connection_in_duplicates(data_fixture, fake_oauth):
    fake_oauth.provider.keep_connection_in_duplicates = False
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    fake_oauth.create(application=builder, connected_by=user)

    clone = CoreHandler().duplicate_application(user, builder)

    copied = fake_oauth.model.objects.get(application=clone)
    assert copied.connected is False
    assert copied.connected_by is None


@pytest.mark.django_db
@pytest.mark.parametrize("keep", [True, False])
def test_publishing_copies_the_connection_unless_the_provider_says_not_to(
    data_fixture, fake_oauth, keep
):
    from baserow.contrib.builder.domains.handler import DomainHandler

    fake_oauth.provider.keep_connection_in_published_copies = keep
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    fake_oauth.create(application=builder, connected_by=user)
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    domain = DomainHandler().publish(domain)

    published = fake_oauth.model.objects.get(application=domain.published_to)
    assert published.connected is keep
    assert (published.refresh_token == "refresh-token") is keep  # nosec B105


def crafted_integration(connected_by_id):
    # A file someone wrote, claiming another user connected a planted account.
    return {
        "id": 1,
        "name": "Example",
        "order": "1",
        "type": FAKE_TYPE,
        "account_id": "x",
        "account_email": "planted@example.com",
        "account_name": "Planted",
        "tenant": "planted",
        "scopes": ["Mail.ReadWrite"],
        "access_token": "planted",
        "refresh_token": "planted",
        "expires_at": "2030-01-01T00:00:00+00:00",
        "connected_at": "2026-01-01T00:00:00+00:00",
        "connected_by_id": connected_by_id,
    }


@pytest.mark.django_db
def test_only_internal_copies_keep_an_imported_connection(data_fixture, fake_oauth):
    integration_type = fake_oauth.type
    other_user = data_fixture.create_user(first_name="Victim")
    crafted = crafted_integration(other_user.id)

    for config in (
        None,
        ImportExportConfig(include_permission_data=False),
        ImportExportConfig(
            include_permission_data=False, is_duplicate=True, is_template=True
        ),
    ):
        imported = integration_type.import_serialized(
            data_fixture.create_builder_application(),
            dict(crafted),
            {},
            import_export_config=config,
        )
        assert imported.connected is False
        assert imported.connected_by_id is None
        assert imported.account_email == ""
        assert imported.tenant == ""
        assert imported.scopes == []

    trusted = ImportExportConfig(
        include_permission_data=True,
        is_duplicate=True,
        exclude_sensitive_data=False,
    )
    # A duplicate into a workspace whose member connected it keeps it.
    member_workspace = data_fixture.create_workspace(user=other_user)
    duplicate = integration_type.import_serialized(
        data_fixture.create_builder_application(workspace=member_workspace),
        dict(crafted),
        {},
        import_export_config=trusted,
    )
    assert duplicate.connected is True
    assert duplicate.connected_by_id == other_user.id
    assert duplicate.tenant == "planted"

    # Not where the one who connected it isn't a member.
    elsewhere = integration_type.import_serialized(
        data_fixture.create_builder_application(),
        dict(crafted),
        {},
        import_export_config=trusted,
    )
    assert elsewhere.connected is False
    assert elsewhere.connected_by_id is None

    # A copy with no workspace, like a snapshot, never stores it.
    hidden = integration_type.import_serialized(
        data_fixture.create_builder_application(workspace=None),
        dict(crafted),
        {},
        import_export_config=trusted,
    )
    assert hidden.connected is False

    # A published copy has no workspace either: it's checked against the
    # workspace it's published from.
    publishing = ImportExportConfig(
        include_permission_data=True,
        is_publishing=True,
        exclude_sensitive_data=False,
    )
    published = integration_type.import_serialized(
        data_fixture.create_builder_application(workspace=None),
        dict(crafted),
        {"import_workspace_id": member_workspace.id},
        import_export_config=publishing,
    )
    assert published.connected is True
    not_a_member = integration_type.import_serialized(
        data_fixture.create_builder_application(workspace=None),
        dict(crafted),
        {"import_workspace_id": data_fixture.create_workspace().id},
        import_export_config=publishing,
    )
    assert not_a_member.connected is False

    # Unless the provider doesn't copy tokens into published copies.
    fake_oauth.provider.keep_connection_in_published_copies = False
    without_copy = integration_type.import_serialized(
        data_fixture.create_builder_application(workspace=None),
        dict(crafted),
        {"import_workspace_id": member_workspace.id},
        import_export_config=publishing,
    )
    assert without_copy.connected is False


@pytest.mark.django_db
def test_garbage_in_an_imported_connection_is_cleaned(data_fixture, fake_oauth):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    values = {
        **crafted_integration(user.id),
        "account_email": None,
        "account_name": "x" * 400,
        "scopes": ["openid", 3, None],
        "expires_at": "not a date",
        "connected_at": 12,
    }

    imported = fake_oauth.type.import_serialized(
        data_fixture.create_builder_application(workspace=workspace),
        values,
        {},
        import_export_config=ImportExportConfig(
            include_permission_data=True,
            is_duplicate=True,
            exclude_sensitive_data=False,
        ),
    )

    assert imported.account_email == ""
    assert len(imported.account_name) == 255
    assert imported.scopes == ["openid"]
    assert imported.expires_at is None
    assert imported.connected_at is None


@pytest.mark.django_db
def test_snapshots_dont_keep_the_account_so_restoring_cant_bring_it_back(
    data_fixture, fake_oauth
):
    from baserow.core.snapshots.handler import SnapshotHandler
    from baserow.core.utils import Progress

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    fake_oauth.create(application=builder, connected_by=user)
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=builder, name="snapshot", created_by=user
    )

    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    stored = fake_oauth.model.objects.get(application=snapshot.snapshot_to_application)
    assert stored.refresh_token == ""
    assert stored.access_token == ""
    assert stored.connected_by is None

    restored = SnapshotHandler().perform_restore(
        snapshot, Progress(total=100), restored_by=user
    )
    restored_integration = fake_oauth.model.objects.get(application=restored)
    assert restored_integration.connected is False
    assert restored_integration.name == "Example"


@pytest.mark.django_db
def test_every_registered_oauth_account_model_is_handled(fake_oauth):
    assert fake_oauth.model in oauth_account_models()


@pytest.mark.django_db
def test_deleting_the_user_who_connected_it_forgets_the_tokens(
    data_fixture, fake_oauth
):
    user = data_fixture.create_user()
    other = data_fixture.create_user()
    connected = fake_oauth.create(connected_by=user)
    untouched = fake_oauth.create(connected_by=other)
    generation = connected.generation

    # As the permanent deletion of users does it.
    get_user_model().objects.filter(id=user.id).delete()

    connected.refresh_from_db()
    assert connected.connected is False
    assert connected.access_token == ""
    assert connected.connected_by is None
    # A reconnect started before can't finish.
    assert connected.generation == generation + 1
    # Who it was stays, so editors know whom to sign in as.
    assert connected.account_email == "alice@example.com"
    untouched.refresh_from_db()
    assert untouched.connected is True


@pytest.mark.django_db
def test_a_member_leaving_the_workspace_stops_being_the_account_used(
    data_fixture, fake_oauth
):
    from baserow.contrib.automation.models import Automation

    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    elsewhere = data_fixture.create_workspace(user=member)

    builder = data_fixture.create_builder_application(workspace=workspace)
    in_app = fake_oauth.create(application=builder, connected_by=member)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    in_published_app = fake_oauth.create(
        application=published_builder, connected_by=member
    )
    workflow = data_fixture.create_automation_workflow(
        automation=data_fixture.create_automation_application(workspace=workspace)
    )
    published_automation = Automation.objects.create(
        workspace=None, name="Published", order=1, published_from=workflow
    )
    in_published_workflow = fake_oauth.create(
        application=published_automation, connected_by=member
    )
    by_admin = fake_oauth.create(application=builder, connected_by=admin)
    other_workspace = fake_oauth.create(
        application=data_fixture.create_builder_application(workspace=elsewhere),
        connected_by=member,
    )

    CoreHandler().leave_workspace(member, workspace)

    for integration in (in_app, in_published_app, in_published_workflow):
        integration.refresh_from_db()
        assert integration.connected is False
        assert integration.account_email == "alice@example.com"
    for integration in (by_admin, other_workspace):
        integration.refresh_from_db()
        assert integration.connected is True


@pytest.mark.django_db
def test_a_member_removed_from_the_workspace_stops_being_the_account_used(
    data_fixture, fake_oauth
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = fake_oauth.create(application=builder, connected_by=member)

    CoreHandler().delete_workspace_user(
        admin, workspace.workspaceuser_set.get(user=member)
    )

    integration.refresh_from_db()
    assert integration.connected is False


@pytest.mark.django_db
def test_trashed_integrations_forget_the_tokens_too(data_fixture, fake_oauth):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    deleted = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member, deleted])
    builder = data_fixture.create_builder_application(workspace=workspace)
    trashed_by_member = fake_oauth.create(
        application=builder, connected_by=member, trashed=True
    )
    trashed_by_deleted = fake_oauth.create(
        application=builder, connected_by=deleted, trashed=True
    )
    trashed_application = data_fixture.create_builder_application(
        workspace=workspace, trashed=True
    )
    in_trashed_application = fake_oauth.create(
        application=trashed_application, connected_by=member
    )

    CoreHandler().leave_workspace(member, workspace)
    get_user_model().objects.filter(id=deleted.id).delete()

    # Restoring them from the trash brings no tokens back.
    for integration in (
        trashed_by_member,
        trashed_by_deleted,
        in_trashed_application,
    ):
        restored = fake_oauth.model.objects_and_trash.get(id=integration.id)
        assert restored.refresh_token == ""
        assert restored.access_token == ""
