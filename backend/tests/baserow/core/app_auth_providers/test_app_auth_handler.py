from collections import defaultdict

import pytest

from baserow.core.app_auth_providers.auth_provider_types import AppAuthProviderType
from baserow.core.app_auth_providers.handler import AppAuthProviderHandler
from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.auth_provider.exceptions import AuthProviderModelNotFound
from baserow.core.utils import MirrorDict


def pytest_generate_tests(metafunc):
    if "app_auth_provider_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "app_auth_provider_type",
            [
                pytest.param(e, id=e.type)
                for e in app_auth_provider_type_registry.get_all()
            ],
        )


@pytest.mark.django_db
def test_create_app_auth_provider(
    data_fixture, app_auth_provider_type: AppAuthProviderType
):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    with app_auth_provider_type.apply_patch_pytest():
        app_auth_provider = AppAuthProviderHandler.create_app_auth_provider(
            user,
            app_auth_provider_type,
            user_source,
            **app_auth_provider_type.prepare_values(
                app_auth_provider_type.get_pytest_params(data_fixture), user
            ),
        )

    assert app_auth_provider.user_source.id == user_source.id
    assert AppAuthProvider.objects.count() == 1


@pytest.mark.django_db
def test_get_app_auth_provider(data_fixture):
    app_auth_provider = data_fixture.create_app_auth_provider_with_first_type()
    assert (
        AppAuthProviderHandler.get_auth_provider_by_id(app_auth_provider.id).id
        == app_auth_provider.id
    )


@pytest.mark.django_db
def test_get_app_auth_provider_does_not_exist(data_fixture):
    data_fixture.create_app_auth_provider_with_first_type()
    with pytest.raises(AuthProviderModelNotFound):
        assert AppAuthProviderHandler.get_auth_provider_by_id(0)


@pytest.mark.django_db
def test_get_app_auth_providers(data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)
    app_auth_provider1 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source, domain="A"
    )
    app_auth_provider2 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source, domain="B"
    )
    app_auth_provider3 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source, domain="C"
    )

    app_auth_providers = AppAuthProviderHandler.list_app_auth_providers_for_user_source(
        user_source
    )

    assert [e.id for e in app_auth_providers] == [
        app_auth_provider1.id,
        app_auth_provider2.id,
        app_auth_provider3.id,
    ]

    first_app_auth_provider_type = list(app_auth_provider_type_registry.get_all())[0]

    assert isinstance(app_auth_providers[0], first_app_auth_provider_type.model_class)


@pytest.mark.django_db
def test_delete_app_auth_provider(data_fixture):
    user = data_fixture.create_user()
    app_auth_provider = data_fixture.create_app_auth_provider_with_first_type(user=user)

    AppAuthProviderHandler().delete_auth_provider(user, app_auth_provider)

    assert AppAuthProvider.objects.count() == 0


@pytest.mark.django_db
def test_update_app_auth_provider(data_fixture):
    user = data_fixture.create_user()
    app_auth_provider = data_fixture.create_app_auth_provider_with_first_type(user=user)

    app_auth_provider_updated = AppAuthProviderHandler.update_auth_provider(
        user, app_auth_provider, domain="test"
    )

    assert app_auth_provider_updated.domain == "test"


@pytest.mark.django_db
def test_update_app_auth_provider_invalid_values(data_fixture):
    user = data_fixture.create_user()
    app_auth_provider = data_fixture.create_app_auth_provider_with_first_type(user=user)

    app_auth_provider_updated = AppAuthProviderHandler.update_auth_provider(
        user, app_auth_provider, nonsense="hello"
    )

    assert not hasattr(app_auth_provider_updated, "nonsense")


@pytest.mark.django_db
def test_export_app_auth_provider(data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    app_auth_provider = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source, domain="Test domain"
    )

    exported = AppAuthProviderHandler.export_app_auth_provider(app_auth_provider)

    assert exported == {
        "id": exported["id"],
        "domain": "Test domain",
        "password_field_id": None,
        "enabled": True,
        "type": "local_baserow_password",
    }


@pytest.mark.django_db
def test_import_app_auth_provider(data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    TO_IMPORT = {
        "id": 28,
        "type": "local_baserow_password",
    }

    id_mapping = defaultdict(MirrorDict)

    imported_instance = AppAuthProviderHandler.import_app_auth_provider(
        user_source, TO_IMPORT, id_mapping
    )

    assert imported_instance.user_source_id == user_source.id


@pytest.mark.django_db
def test_import_app_auth_provider_with_migrated_user_source(data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    TO_IMPORT = {"id": 28, "type": "local_baserow_password"}

    id_mapping = defaultdict(MirrorDict)

    imported_instance = AppAuthProviderHandler.import_app_auth_provider(
        user_source, TO_IMPORT, id_mapping
    )

    assert imported_instance.user_source_id == user_source.id
