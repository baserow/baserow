from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction
from django.utils import timezone

import pytest

from baserow.core.integrations.registries import integration_type_registry
from baserow.core.services.registries import service_type_registry

from .fake_provider import FakeOAuthIntegrationType, StubOAuthServiceType


@pytest.fixture(scope="session")
def fake_oauth_table(django_db_setup, django_db_blocker):
    """
    Registers the test-only model and creates its table, once per session. The
    table is kept: once registered, the model stays in the app registry.
    """

    with django_db_blocker.unblock():
        from .fake_model import FakeOAuthIntegration

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Workers may share a database.
                cursor.execute("SELECT pg_advisory_xact_lock(20261120, 6809);")
            if (
                FakeOAuthIntegration._meta.db_table
                not in connection.introspection.table_names()
            ):
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(FakeOAuthIntegration)
    return FakeOAuthIntegration


@contextmanager
def registered_stub_service_type(deactivated=False):
    service_type = StubOAuthServiceType()
    service_type.is_deactivated = lambda workspace: deactivated
    service_type_registry.register(service_type)
    try:
        yield service_type
    finally:
        service_type_registry.unregister(service_type.type)


@pytest.fixture
def fake_oauth(fake_oauth_table, data_fixture):
    """
    The fake OAuth account integration type, registered for the test, and a
    helper creating its integrations. Connected ones have an account, tokens
    valid for an hour and the base scopes, unless given.
    """

    ContentType.objects.clear_cache()
    integration_type = FakeOAuthIntegrationType(fake_oauth_table)
    integration_type_registry.register(integration_type)

    def create(connected=True, **kwargs):
        kwargs.setdefault("name", "Example")
        if connected:
            kwargs.setdefault("account_id", "account-alice")
            kwargs.setdefault("tenant", "contoso")
            kwargs.setdefault("account_email", "alice@example.com")
            kwargs.setdefault("account_name", "Alice")
            kwargs.setdefault("scopes", ["email", "openid", "Profile.Read"])
            kwargs.setdefault("access_token", "access-token")  # nosec B105
            kwargs.setdefault("refresh_token", "refresh-token")  # nosec B105
            kwargs.setdefault("expires_at", timezone.now() + timedelta(hours=1))
            kwargs.setdefault("connected_at", timezone.now())
        return data_fixture.create_integration(fake_oauth_table, **kwargs)

    try:
        yield SimpleNamespace(
            model=fake_oauth_table,
            type=integration_type,
            provider=integration_type.provider,
            create=create,
        )
    finally:
        integration_type_registry.unregister(integration_type.type)


@pytest.fixture
def stub_service_type(fake_oauth):
    with registered_stub_service_type() as service_type:
        yield service_type
