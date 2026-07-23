from collections import defaultdict
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.timezone import now

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
)

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.registries import plugin_registry
from baserow.core.user_sources.exceptions import UserSourceImproperlyConfigured
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.registries import user_source_type_registry
from baserow.core.user_sources.service import UserSourceService
from baserow.core.utils import MirrorDict
from baserow_enterprise.application_users.usage import get_over_limit_cache_key
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowPasswordAppAuthProvider,
)
from baserow_premium.application_user_usage.constants import (
    DEFAULT_APPLICATION_USERS_LIMIT,
)
from baserow_premium.license.plugin import LicensePlugin
from baserow_premium.plugins import PremiumPlugin

from .helpers import populate_local_baserow_test_data


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise):
    pass


@pytest.mark.django_db
def test_create_local_baserow_password_app_auth_provider_w_field(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    integration = data_fixture.create_local_baserow_integration(application=application)

    table, fields, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Password", "password"),
            ("Role", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test", "password", ""],
        ],
    )

    email_field, name_field, password_field, role_field = fields

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table.id,
            "email_field_id": email_field.id,
            "name_field_id": name_field.id,
            "role_field_id": role_field.id,
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "domain": None,
                    "enabled": True,
                    "password_field_id": password_field.id,
                }
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    created = LocalBaserowPasswordAppAuthProvider.objects.first()

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["auth_providers"] == [
        {
            "type": "local_baserow_password",
            "id": created.id,
            "domain": None,
            "password_field_id": password_field.id,
        }
    ]


@pytest.mark.django_db
def test_create_local_baserow_password_app_auth_provider_w_wrong_field_type(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    integration = data_fixture.create_local_baserow_integration(application=application)

    table, fields, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Password", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test", "password", ""],
        ],
    )

    email_field, name_field, password_field, role_field = fields

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table.id,
            "email_field_id": email_field.id,
            "name_field_id": name_field.id,
            "role_field_id": role_field.id,
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "domain": None,
                    "enabled": True,
                    "password_field_id": password_field.id,
                }
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["password_field_id"][0]["code"] == "invalid_field"


@pytest.mark.django_db
def test_create_local_baserow_password_app_auth_provider_w_wrong_field_id(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    integration = data_fixture.create_local_baserow_integration(application=application)

    table, fields, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Password", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test", "password", ""],
        ],
    )

    email_field, name_field, password_field, role_field = fields

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table.id,
            "email_field_id": email_field.id,
            "name_field_id": name_field.id,
            "role_field_id": role_field.id,
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "domain": None,
                    "enabled": True,
                    "password_field_id": 0,
                }
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["password_field_id"][0]["code"] == "invalid_field"

    FieldHandler().delete_field(user, password_field)

    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table.id,
            "email_field_id": email_field.id,
            "name_field_id": name_field.id,
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "domain": None,
                    "enabled": True,
                    "password_field_id": password_field.id,
                }
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["password_field_id"][0]["code"] == "invalid_field"


@pytest.mark.django_db
def test_local_baserow_password_app_auth_provider_after_user_source_update(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(database=database)
    integration = data_fixture.create_local_baserow_integration(application=application)

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Password", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test", "super not secret", ""],
        ],
    )

    email_field, name_field, password_field, role_field = fields

    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Password", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test", "super not secret", ""],
        ],
    )

    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")

    user_source = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application,
        integration=integration,
        table=table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )

    app_auth_provider = data_fixture.create_app_auth_provider(
        LocalBaserowPasswordAppAuthProvider,
        user_source=user_source,
        password_field=password_field,
    )

    UserSourceService().update_user_source(user, user_source, table=table2)

    app_auth_provider.refresh_from_db()

    assert app_auth_provider.password_field_id is None


@pytest.mark.django_db
def test_local_baserow_token_auth(api_client, data_fixture):
    data = populate_local_baserow_test_data(data_fixture)

    response = api_client.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": data["user_source"].id},
        ),
        {"email": "test@baserow.io", "password": "super not secret"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert "refresh_token" in response_json
    assert "access_token" in response_json


@pytest.mark.django_db
@override_settings(
    BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True,
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_local_baserow_token_auth_over_application_user_limit(
    mock_aggregate_user_source_counts, api_client, data_fixture
):
    """
    ApplicationUserLimitReached is a self-describing APIException so that the plain
    REST login endpoint in core renders it directly, without a core-side exception
    mapping. This pins that contract at the API level.
    """

    mock_aggregate_user_source_counts.return_value = DEFAULT_APPLICATION_USERS_LIMIT + 1
    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]
    workspace = user_source.application.specific.get_workspace()
    cache.set(
        get_over_limit_cache_key(workspace.id),
        (now() - timedelta(hours=2)).isoformat(),
    )

    # Force the self-hosted license plugin so the limit resolves from the licenses
    # (the default limit here) in every environment, including the SaaS one.
    premium_plugin = plugin_registry.get_by_type(PremiumPlugin)
    with patch.object(
        premium_plugin,
        "get_license_plugin",
        lambda cache_queries=False: LicensePlugin(cache_queries),
    ):
        response = api_client.post(
            reverse(
                "api:user_sources:token_auth",
                kwargs={"user_source_id": user_source.id},
            ),
            {"email": "test@baserow.io", "password": "super not secret"},
            format="json",
        )

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    response_json = response.json()
    assert response_json["error"] == "ERROR_APPLICATION_USER_LIMIT_REACHED"
    assert response_json["detail"]


@pytest.mark.django_db
def test_local_baserow_user_source_authentication_improperly_configured(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    data["auth_provider"].password_field = None
    data["auth_provider"].save()

    with pytest.raises(UserSourceImproperlyConfigured):
        user_source_type.authenticate(
            user_source, email="test@baserow.io", password="super not secret"
        )


@pytest.mark.django_db
def test_import_local_baserow_password_app_auth_provider(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )

    table_from_same_workspace1, fields, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Password", "password"),
        ],
        rows=[
            ["test@baserow.io", "Test", "password"],
        ],
    )

    email_field, name_field, password_field = fields

    TO_IMPORT = {
        "email_field_id": 42,
        "id": 28,
        "integration_id": 42,
        "name": "Test name",
        "name_field_id": 43,
        "order": "1.00000000000000000000",
        "table_id": 42,
        "type": "local_baserow",
        "auth_providers": [
            {
                "id": 42,
                "type": "local_baserow_password",
                "domain": None,
                "enabled": True,
                "password_field_id": 44,
            }
        ],
    }

    id_mapping = defaultdict(MirrorDict)
    id_mapping["integrations"] = {42: integration.id}
    id_mapping["database_tables"] = {42: table_from_same_workspace1.id}
    id_mapping["database_fields"] = {
        42: email_field.id,
        43: name_field.id,
        44: password_field.id,
    }

    imported_instance = UserSourceHandler().import_user_source(
        application, TO_IMPORT, id_mapping
    )

    assert (
        imported_instance.auth_providers.first().specific.password_field_id
        == password_field.id
    )


@pytest.mark.django_db
def test_import_local_baserow_password_app_auth_provider_without_database(data_fixture):
    """
    Test the import of the LocalBaserowPasswordAppAuthProvider when the
    password field is missing in the id_mapping.

    The password field might be missing during an import, because the user
    might have either deleted the password field in the database, or deleted
    the table entirely.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )

    table_from_same_workspace1, fields, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Password", "password"),
        ],
        rows=[
            ["test@baserow.io", "Test", "password"],
        ],
    )

    email_field, name_field, password_field = fields

    TO_IMPORT = {
        "email_field_id": 42,
        "id": 28,
        "integration_id": 42,
        "name": "Test name",
        "name_field_id": 43,
        "order": "1.00000000000000000000",
        "table_id": 42,
        "type": "local_baserow",
        "auth_providers": [
            {
                "id": 42,
                "type": "local_baserow_password",
                "domain": None,
                "enabled": True,
                "password_field_id": 44,
            }
        ],
    }

    id_mapping = defaultdict(MirrorDict)
    id_mapping["integrations"] = {42: integration.id}
    id_mapping["database_tables"] = {42: table_from_same_workspace1.id}

    # the password field is intentionally excluded from database_fields
    id_mapping["database_fields"] = {
        42: email_field.id,
        43: name_field.id,
    }

    imported_instance = UserSourceHandler().import_user_source(
        application, TO_IMPORT, id_mapping
    )

    assert imported_instance.auth_providers.first().specific.password_field_id is None
