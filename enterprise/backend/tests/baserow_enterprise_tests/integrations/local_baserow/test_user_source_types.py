from collections import defaultdict
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    CreatedByField,
    CreatedOnField,
    DateField,
    DurationField,
    FileField,
    FormulaField,
    LastModifiedByField,
    LastModifiedField,
    LinkRowField,
    PasswordField,
    PhoneNumberField,
    RatingField,
    SelectOption,
    SingleSelectField,
    TextField,
    URLField,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.exceptions import UserSourceImproperlyConfigured
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.registries import (
    DEFAULT_USER_ROLE_PREFIX,
    user_source_type_registry,
)
from baserow.core.user_sources.service import UserSourceService
from baserow.core.utils import MirrorDict, Progress
from baserow.test_utils.helpers import AnyStr
from baserow_enterprise.integrations.local_baserow.models import LocalBaserowUserSource
from baserow_enterprise.integrations.local_baserow.user_source_types import (
    LocalBaserowUserSourceType,
)

from .helpers import populate_local_baserow_test_data


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise):
    pass


@pytest.mark.django_db
def test_get_user_sources(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
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
            ("Role", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test", ""],
        ],
    )

    email_field, name_field, role_field = fields

    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")

    user_source1 = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application,
        integration=integration,
        table=table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )

    user_source2 = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application,
        integration=integration,
        table=table,
        email_field=email_field,
    )

    user_source3 = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application,
        integration=integration,
        table=table,
    )

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    assert response_json[0]["id"] == user_source1.id
    assert response_json[0]["type"] == "local_baserow"
    assert response_json[0]["integration_id"] == integration.id
    assert response_json[0]["table_id"] == table.id
    assert response_json[0]["email_field_id"] == email_field.id
    assert response_json[0]["name_field_id"] == name_field.id
    assert response_json[0]["role_field_id"] == role_field.id

    assert response_json[1]["id"] == user_source2.id
    assert response_json[1]["type"] == "local_baserow"
    assert response_json[1]["integration_id"] == integration.id
    assert response_json[1]["table_id"] == table.id
    assert response_json[1]["email_field_id"] == email_field.id
    assert response_json[1]["name_field_id"] is None
    assert response_json[1]["role_field_id"] is None

    assert response_json[2]["id"] == user_source3.id
    assert response_json[2]["type"] == "local_baserow"
    assert response_json[2]["integration_id"] == integration.id
    assert response_json[2]["table_id"] == table.id
    assert response_json[2]["email_field_id"] is None
    assert response_json[2]["name_field_id"] is None
    assert response_json[2]["role_field_id"] is None


@pytest.fixture(autouse=True)
def user_source_fixture(data_fixture):
    """A fixture to help test LocalBaserowUserSourceType."""

    user, _ = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    page = data_fixture.create_builder_page(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")

    user_source = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application,
    )
    return user_source


@pytest.mark.django_db
def test_create_local_baserow_user_source(api_client, data_fixture):
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
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    email_field, name_field = fields

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
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "local_baserow"
    assert response_json["integration_id"] == integration.id
    assert response_json["table_id"] == table.id
    assert response_json["email_field_id"] == email_field.id
    assert response_json["name_field_id"] == name_field.id


@pytest.mark.django_db
def test_create_local_baserow_user_source_wrong_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    integration = data_fixture.create_local_baserow_integration(application=application)

    table, fields, _ = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Email", "rating"),
            ("Name", "url"),
            ("Email", "text"),
        ],
        rows=[
            [2, "https://baserow.io", "test"],
        ],
    )

    email_field, name_field, another_email_field = fields

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
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["email_field_id"][0]["code"] == "invalid_field"

    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table.id,
            "email_field_id": another_email_field.id,
            "name_field_id": name_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["name_field_id"][0]["code"] == "invalid_field"


@pytest.mark.django_db
def test_create_local_baserow_user_source_w_a_password_auth_source(
    api_client, data_fixture
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
                    "password_field_id": password_field.id,
                    "type": "local_baserow_password",
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_create_local_baserow_user_source_w_two_password_auth_source(
    api_client, data_fixture
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
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    email_field, name_field = fields

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
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                },
                {
                    "type": "local_baserow_password",
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AUTH_PROVIDER_CANT_BE_CREATED"


@pytest.mark.django_db
def test_create_local_baserow_user_source_w_wrong_field_ids(api_client, data_fixture):
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
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    email_field, name_field = fields

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table.id,
            "email_field_id": 0,
            "name_field_id": name_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["email_field_id"][0]["code"] == "invalid_field"

    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table.id,
            "email_field_id": email_field.id,
            "name_field_id": 0,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["name_field_id"][0]["code"] == "invalid_field"

    FieldHandler().delete_field(user, email_field)

    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table.id,
            "email_field_id": email_field.id,
            "name_field_id": name_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["email_field_id"][0]["code"] == "invalid_field"


@pytest.mark.django_db
def test_create_user_source_table_from_other_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )

    table_from_other_workspace, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table_from_other_workspace.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["table_id"][0]["code"] == "invalid_table"


@pytest.mark.django_db
def test_create_local_baserow_user_source_w_a_missing_table(api_client, data_fixture):
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
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    email_field, name_field = fields

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": 0,
            "email_field_id": email_field.id,
            "name_field_id": name_field.id,
            "auth_providers": [
                {
                    "password_field_id": name_field.id,
                    "type": "local_baserow_password",
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["table_id"][0]["code"] == "invalid_table"


@pytest.mark.django_db
def test_create_user_source_field_from_other_table(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
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
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    table_from_same_workspace2, fields2, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    email_field_other_table, name_field_other_table = fields2

    # Email field for another table
    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table_from_same_workspace1.id,
            "email_field_id": email_field_other_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["email_field_id"][0]["code"] == "invalid_field"

    # name field from another table
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "table_id": table_from_same_workspace1.id,
            "name_field_id": name_field_other_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["name_field_id"][0]["code"] == "invalid_field"

    # email field without table
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "email_field_id": email_field_other_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["email_field_id"][0]["code"] == "missing_table"

    # name field without table
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "name_field_id": name_field_other_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["name_field_id"][0]["code"] == "missing_table"


@pytest.mark.django_db
def test_user_source_create_user(data_fixture):
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
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    email_field, name_field = fields

    user_source = data_fixture.create_user_source_with_first_type(
        integration=integration,
        name="Test name",
        table=table_from_same_workspace1,
        email_field=email_field,
        name_field=name_field,
        uid="uid",
    )

    created_user = user_source.get_type().create_user(
        user_source, "test2@baserow.io", "Test2"
    )

    model = table_from_same_workspace1.get_model()
    assert created_user.email == "test2@baserow.io"
    assert model.objects.count() == 2
    assert getattr(model.objects.last(), email_field.db_column) == "test2@baserow.io"


@pytest.mark.django_db
def test_user_source_create_user_w_role(data_fixture):
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
            ("Role", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test", "role1"],
        ],
    )

    email_field, name_field, role_field = fields

    user_source = data_fixture.create_user_source_with_first_type(
        integration=integration,
        name="Test name",
        table=table_from_same_workspace1,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
        uid="uid",
    )

    created_user = user_source.get_type().create_user(
        user_source, "test2@baserow.io", "Test2", "role2"
    )

    model = table_from_same_workspace1.get_model()
    assert created_user.role == "role2"
    assert getattr(model.objects.last(), role_field.db_column) == "role2"


@pytest.mark.django_db
def test_export_user_source(data_fixture):
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
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    email_field, name_field = fields

    user_source = data_fixture.create_user_source_with_first_type(
        integration=integration,
        name="Test name",
        table=table_from_same_workspace1,
        email_field=email_field,
        name_field=name_field,
    )

    auth_provider = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source
    )

    exported = UserSourceHandler().export_user_source(user_source)

    assert exported == {
        "email_field_id": email_field.id,
        "id": exported["id"],
        "integration_id": integration.id,
        "name": "Test name",
        "name_field_id": name_field.id,
        "order": "1.00000000000000000000",
        "role_field_id": None,
        "table_id": table_from_same_workspace1.id,
        "type": "local_baserow",
        "uid": user_source.get_type().gen_uid(user_source),
        "auth_providers": [
            {
                "id": auth_provider.id,
                "type": auth_provider.get_type().type,
                "domain": None,
                "enabled": True,
                "password_field_id": None,
            }
        ],
    }


@pytest.mark.django_db
def test_import_local_baserow_user_source(data_fixture):
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
        ],
        rows=[
            ["test@baserow.io", "Test"],
        ],
    )

    email_field, name_field = fields

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
                "password_field_id": None,
            }
        ],
    }

    id_mapping = defaultdict(MirrorDict)
    id_mapping["integrations"] = {42: integration.id}
    id_mapping["database_tables"] = {42: table_from_same_workspace1.id}
    id_mapping["database_fields"] = {42: email_field.id, 43: name_field.id}

    imported_instance = UserSourceHandler().import_user_source(
        application, TO_IMPORT, id_mapping
    )

    assert imported_instance.table_id == table_from_same_workspace1.id
    assert imported_instance.email_field_id == email_field.id
    assert imported_instance.name_field_id == name_field.id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "id_mapping_key,missing_field_name",
    [
        ("database_tables", "table_id"),
        ("database_fields", "email_field_id"),
        ("database_fields", "name_field_id"),
        ("database_fields", "role_field_id"),
    ],
)
def test_import_local_baserow_user_source_with_missing_fields(
    data_fixture, id_mapping_key, missing_field_name
):
    """
    Test the import of the LocalBaserowUserSource when one or more fields
    are missing in the exported workspace's database.

    A field, such as the Role field might have been deleted before the user
    has exported the workspace. As such, when importing the workspace, the
    missing field needs to be safely handled.
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
            ("Role", "text"),
        ],
        rows=[
            ["test@baserow.io", "Test", "Foo Role"],
        ],
    )

    email_field, name_field, role_field = fields

    TO_IMPORT = {
        "id": 28,
        "name": "Test name",
        "order": "1.00000000000000000000",
        "type": "local_baserow",
        "integration_id": 42,
        "table_id": 42,
        "name_field_id": 43,
        "email_field_id": 42,
        "role_field_id": 44,
        "auth_providers": [
            {
                "id": 42,
                "type": "local_baserow_password",
                "domain": None,
                "enabled": True,
                "password_field_id": None,
            }
        ],
    }

    id_mapping = defaultdict(MirrorDict)

    id_mapping_data = {
        "table_id": (42, table_from_same_workspace1.id),
        "email_field_id": (42, email_field.id),
        "name_field_id": (43, name_field.id),
        "role_field_id": (44, role_field.id),
    }
    id_mapping["integrations"] = {42: integration.id}
    id_mapping["database_tables"] = {42: table_from_same_workspace1.id}
    id_mapping["database_fields"] = {
        42: email_field.id,
        43: name_field.id,
        44: role_field.id,
    }

    # Remove a specific field to simulate a "missing field"
    id_mapping[id_mapping_key].pop(id_mapping_data[missing_field_name][0])

    imported_instance = UserSourceHandler().import_user_source(
        application, TO_IMPORT, id_mapping
    )

    for property in id_mapping_data:
        value = getattr(imported_instance, property)
        if property == missing_field_name:
            # Ensure that None is returned instead of raising a KeyError
            assert value is None
        else:
            assert value is id_mapping_data[property][1]


@pytest.mark.django_db
def test_create_local_baserow_user_source_w_auth_providers(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)
    table, fields, rows = data_fixture.build_table(
        columns=[("Name", "text"), ("Password", "password")],
        rows=["Peter", "hunter2"],
        user=user,
        database=database,
    )
    password_field = table.field_set.get(name="Password")

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "table_id": table.id,
            "integration_id": integration.id,
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "enabled": True,
                    "domain": "test1.com",
                    "password_field_id": password_field.id,
                }
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert AppAuthProvider.objects.count() == 1
    first = AppAuthProvider.objects.first()

    assert response_json["auth_providers"] == [
        {
            "domain": "test1.com",
            "id": first.id,
            "password_field_id": password_field.id,
            "type": "local_baserow_password",
        },
    ]


@pytest.mark.django_db
def test_local_baserow_user_source_token_generation(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(
        workspace=workspace, user=user
    )
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(database=database)
    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )

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

    user_source_type = user_source.get_type()

    user = rows[0]

    user = user_source_type.get_user(user_source, email="test@baserow.io")

    assert user.email == "test@baserow.io"
    assert user.id == rows[0].id


@pytest.mark.django_db
def test_public_dispatch_data_source_with_ab_user_using_user_source(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace, user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(database=database)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )

    # Create the table to dispatch
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
        ],
    )

    # Define the data source to dispatch
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
        row_id="2",
    )

    # Create the user table for the user_source
    user_table, user_fields, user_rows = data_fixture.build_table(
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
    email_field, name_field, password_field, role_field = user_fields

    # Create the user source and the auth provider
    user_source = data_fixture.create_user_source(
        user_source_type_registry.get("local_baserow").model_class,
        application=builder,
        integration=integration,
        table=user_table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )

    # Create a domain and publish the application
    domain1 = data_fixture.create_builder_custom_domain(builder=builder)
    progress = Progress(100)
    DomainHandler().publish(domain1, progress)
    domain1.refresh_from_db()

    user_source_type = user_source.get_type()

    user = user_rows[0]

    user_source_user = user_source_type.get_user(user_source, email="test@baserow.io")

    refresh_token = user_source_user.get_refresh_token()
    access_token = refresh_token.access_token

    published_page = domain1.published_to.visible_pages.first()
    published_data_source = published_page.datasource_set.first()

    url = reverse(
        "api:builder:data_source:dispatch",
        kwargs={"data_source_id": published_data_source.id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION_US=f"JWT {access_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": 2,
        "order": AnyStr(),
        fields[0].name: "Audi",
        fields[1].name: "Orange",
    }


@pytest.mark.django_db
def test_local_baserow_user_source_create_user(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    user_source_type.create_user(
        user_source, email="test_create@baserow.io", name="user name"
    )

    UserModel = data["user_table"].get_model()

    email_field, name_field, *other_fields = data["fields"]

    assert (
        UserModel.objects.filter(
            **{
                email_field.db_column: "test_create@baserow.io",
                name_field.db_column: "user name",
            }
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_local_baserow_user_source_create_user_bad_configuration(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    user_source_type.create_user(
        user_source, email="test_create@baserow.io", name="user name"
    )

    user_table = data["user_table"]

    # `is_configured` will be False if the name_field is None
    user_source.name_field = None
    user_source.save()

    with pytest.raises(UserSourceImproperlyConfigured):
        user_source_type.create_user(
            user_source, email="test_create@baserow.io", name="user name"
        )

    email_field, name_field, *other_fields = data["fields"]

    # Re-add the name field, so we can verify that `get_user_model`
    # will raise `UserNotFound` (from `UserSourceImproperlyConfigured`)
    # if the table has been trashed.
    user_source.name_field = name_field
    user_source.save()
    user_source.table.trashed = True
    user_source.table.save()

    with pytest.raises(UserSourceImproperlyConfigured):
        user_source_type.create_user(
            user_source, email="test_create@baserow.io", name="user name"
        )


@pytest.mark.django_db
def test_local_baserow_user_source_get_user(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    UserModel = data["user_table"].get_model()

    first_user = UserModel.objects.first()

    user = user_source_type.get_user(user_source, user_id=first_user.id)

    assert user.id == first_user.id
    assert user.username == getattr(first_user, user_source.name_field.db_column)
    assert user.email == getattr(first_user, user_source.email_field.db_column)

    user = user_source_type.get_user(
        user_source, email=getattr(first_user, user_source.email_field.db_column)
    )

    assert user.id == first_user.id
    assert user.username == getattr(first_user, user_source.name_field.db_column)
    assert user.email == getattr(first_user, user_source.email_field.db_column)


@pytest.mark.django_db
def test_local_baserow_user_source_get_user_misconfigured(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    user_table = data["user_table"]
    UserModel = user_table.get_model()

    first_user = UserModel.objects.first()

    name_field = user_source.name_field

    # `is_configured` will be False if the name_field is None
    user_source.name_field = None
    user_source.save()

    with pytest.raises(UserNotFound):
        user_source_type.get_user(user_source, user_id=first_user.id)

    # Re-add the name field, so we can verify that `get_user_model`
    # will raise `UserNotFound` (from `UserSourceImproperlyConfigured`)
    # if the table has been trashed.
    user_source.name_field = name_field
    user_source.save()
    user_source.table.trashed = True
    user_source.table.save()

    with pytest.raises(UserNotFound):
        user_source_type.get_user(user_source, user_id=first_user.id)


@pytest.mark.django_db
def test_local_baserow_user_source_get_user_with_duplicate(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    UserModel = data["user_table"].get_model()

    first_user = UserModel.objects.first()

    # Let's create another user with same email and check that it's still working
    UserModel.objects.create(
        **{
            user_source.name_field.db_column: "a user name",
            user_source.email_field.db_column: getattr(
                first_user, user_source.email_field.db_column
            ),  # Ouch a duplicate!!!
        }
    )

    user = user_source_type.get_user(
        user_source, email=getattr(first_user, user_source.email_field.db_column)
    )
    assert user.id == first_user.id


@pytest.mark.django_db
def test_local_baserow_user_source_get_user_fails(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    with pytest.raises(UserNotFound):
        user_source_type.get_user(user_source, user_id=0)

    with pytest.raises(UserNotFound):
        user_source_type.get_user(user_source, email="missing@ema.il")


@pytest.mark.django_db
def test_local_baserow_user_source_authentication(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    user = user_source_type.authenticate(
        user_source, email="test@baserow.io", password="super not secret"
    )

    assert user.email == "test@baserow.io"
    assert user.username == "Test"

    user = user_source_type.authenticate(
        user_source, email="test2@baserow.io", password="super not secret"
    )

    assert user.email == "test2@baserow.io"
    assert user.username == "Test2"


@pytest.mark.django_db
def test_local_baserow_user_source_authentication_improperly_configured(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    email_field = user_source.email_field

    user_source.email_field = None
    user_source.save()

    with pytest.raises(UserSourceImproperlyConfigured):
        user_source_type.authenticate(
            user_source, email="test@baserow.io", password="super not secret"
        )

    user_source.email_field = email_field
    user_source.name_field = None
    user_source.save()

    with pytest.raises(UserSourceImproperlyConfigured):
        user_source_type.authenticate(
            user_source, email="test@baserow.io", password="super not secret"
        )


@pytest.mark.django_db
def test_local_baserow_user_source_authentication_missing_auth_provider(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    data["auth_provider"].delete()

    with pytest.raises(UserSourceImproperlyConfigured):
        user_source_type.authenticate(
            user_source, email="test@baserow.io", password="super not secret"
        )


@pytest.mark.django_db
def test_local_baserow_user_source_authentication_bad_creds(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    with pytest.raises(AuthenticationFailed):
        user_source_type.authenticate(
            user_source, email="test@baserow.io", password="bad password"
        )

    with pytest.raises(UserNotFound):
        user_source_type.authenticate(
            user_source, email="testt@baserow.io", password="super not secret"
        )

    with pytest.raises(AuthenticationFailed):
        user_source_type.authenticate(
            user_source, email="test4@baserow.io", password="super not secret"
        )


@pytest.mark.django_db
def test_local_baserow_user_source_authentication_list_users(
    data_fixture, disable_full_text_search
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    first_user, second_user, third_user, fourth_user = (
        data["user_table"].get_model().objects.all()
    )

    result = user_source_type.list_users(user_source)

    assert len(result) == 4
    assert result[0].id == first_user.id
    assert result[1].id == second_user.id
    assert result[2].id == third_user.id
    assert result[3].id == fourth_user.id

    result = user_source_type.list_users(user_source, count=2)

    assert len(result) == 2

    result = user_source_type.list_users(user_source, search="test@")

    assert len(result) == 1


@pytest.mark.django_db
def test_local_baserow_user_source_authentication_list_users_not_configured(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()

    user_source.email_field = None
    user_source.save()

    result = user_source_type.list_users(user_source)

    assert len(result) == 0


@pytest.mark.django_db
def test_local_baserow_user_source_authentication_list_users_get_user_model_misconfiguration(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)
    table = data["user_table"]
    table.trashed = True
    table.save()

    user_source = data["user_source"]
    user_source_type = user_source.get_type()
    result = user_source_type.list_users(user_source)

    assert len(result) == 0


def test_local_baserow_user_source_get_user_model_with_trashed_table(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)
    trashed_table = data_fixture.create_database_table(user=user, trashed=True)
    with pytest.raises(UserSourceImproperlyConfigured) as exc:
        LocalBaserowUserSourceType().get_user_model(
            LocalBaserowUserSource(table=trashed_table, integration=integration)
        )
    assert exc.value.args[0] == "The table doesn't exist."


def test_local_baserow_user_source_authentication_is_configured(
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]

    user_source_type = LocalBaserowUserSourceType()
    # All configured fields.
    assert user_source_type.is_configured(user_source) is True

    for field in [
        "table",
        "email_field",
        "name_field",
        "integration",
    ]:
        prev_field = getattr(user_source, field)
        setattr(user_source, field, None)
        assert (
            user_source_type.is_configured(user_source) is False
        ), f"Failed for {field}"
        setattr(user_source, field, prev_field)


@pytest.fixture(autouse=True)
def role_field_id_test_fixture(data_fixture):
    """Fixture to help test the role_field_id."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)
    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")

    user_source = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application,
        integration=integration,
    )

    return user, user_source, application, workspace, integration


@pytest.mark.django_db
def test_prepare_values_role_field_id_raises_if_no_table_to_check(data_fixture):
    """
    Test the prepare_values() method when the "role_field_id" is in values.

    Ensure an exception is raised if the table is missing.
    """

    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = LocalBaserowUserSourceType()

    with pytest.raises(RequestBodyValidationException) as e:
        user_source_type.prepare_values(
            {"role_field_id": 1},
            user_source,
        )

    assert "Please select a table before selecting this field" in str(e.value)


@pytest.mark.django_db
def test_prepare_values_role_field_id_raises_if_field_doesnt_exist(
    data_fixture,
    role_field_id_test_fixture,
):
    """
    Test the prepare_values() method when the "role_field_id" is in values.

    Ensure an exception is raised if the role_field is missing.
    """

    user, user_source, _, _, _ = role_field_id_test_fixture

    users_table = data_fixture.create_database_table(name="test_users")
    role_field = data_fixture.create_text_field(table=users_table, order=0, name="role")
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    with pytest.raises(RequestBodyValidationException) as e:
        LocalBaserowUserSourceType().prepare_values(
            # Add 100 to the latest role_field, which should simulate a
            # non-existent ID.
            {"role_field_id": role_field.id + 100},
            user,
            user_source,
        )

    assert "The provided Id doesn't exist." in str(e.value)


@pytest.mark.django_db
def test_prepare_values_role_field_id_raises_if_field_id_mismatch(
    data_fixture,
    role_field_id_test_fixture,
):
    """
    Test the prepare_values() method when the "role_field_id" is in values.

    Ensure an exception is raised if the role field's table_id doesns't match
    the table's ID.
    """

    user, user_source, application, _, _ = role_field_id_test_fixture

    users_table = data_fixture.create_database_table(name="test_users")
    role_field = data_fixture.create_text_field(table=users_table, order=0, name="role")
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    # Create a different table
    foo_table = data_fixture.create_database_table(name="foo")
    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")
    user_source_2 = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application,
    )
    user_source_2.table = foo_table
    user_source_2.save()

    with pytest.raises(RequestBodyValidationException) as e:
        LocalBaserowUserSourceType().prepare_values(
            {"role_field_id": role_field.id},
            user,
            user_source_2,
        )

    assert (
        f"The field with ID {role_field.id} is not related to the given table."
        in str(e.value)
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_creator,",
    [
        "create_autonumber_field",
        "create_boolean_field",
        "create_created_by_field",
        "create_created_on_field",
        "create_date_field",
        "create_duration_field",
        "create_email_field",
        "create_file_field",
        "create_last_modified_by_field",
        "create_last_modified_field",
        "create_link_row_field",
        "create_long_text_field",
        "create_lookup_field",
        "create_multiple_collaborators_field",
        "create_multiple_select_field",
        "create_number_field",
        "create_password_field",
        "create_phone_number_field",
        "create_rating_field",
        "create_url_field",
        "create_uuid_field",
    ],
)
def test_prepare_values_role_field_id_raises_if_field_type_wrong(
    data_fixture,
    role_field_id_test_fixture,
    field_creator,
):
    """
    Test the prepare_values() method when the "role_field_id" is in values.

    Ensure an exception is raised if the role field's type is not allowed.
    """

    user, user_source, _, _, _ = role_field_id_test_fixture

    users_table = data_fixture.create_database_table(name="test_users")
    role_field = getattr(data_fixture, field_creator)(
        table=users_table, order=0, name="role"
    )
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    with pytest.raises(RequestBodyValidationException) as e:
        LocalBaserowUserSourceType().prepare_values(
            {"role_field_id": role_field.id},
            user,
            user_source,
        )

    assert f"This field type can't be used as a role." in str(e.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_creator,",
    [
        "create_formula_field",
        "create_single_select_field",
        "create_text_field",
    ],
)
def test_prepare_values_role_field_id_returns_values(
    data_fixture, role_field_id_test_fixture, field_creator
):
    """
    Test the prepare_values() method when the "role_field_id" is in values.

    Ensure that the expected values dict is returned for the valid field types.
    """

    user, user_source, _, _, _ = role_field_id_test_fixture

    users_table = data_fixture.create_database_table(name="test_users")
    role_field = getattr(data_fixture, field_creator)(
        table=users_table, order=0, name="role"
    )
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    values = LocalBaserowUserSourceType().prepare_values(
        {"role_field_id": role_field.id},
        user,
        user_source,
    )

    field = FieldHandler().get_field(role_field.id)
    assert values["role_field"] == field
    assert "role_field_id" not in values


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_creator,",
    [
        "create_formula_field",
        "create_single_select_field",
        "create_text_field",
    ],
)
def test_prepare_values_role_field_id_returns_empty_values_if_role_field_id_is_none(
    data_fixture, field_creator
):
    """
    Test the prepare_values() method when the "role_field_id" is in values.

    Ensure that the expected values dict is empty if the role_field_id is None.
    """

    user = data_fixture.create_user()

    values = LocalBaserowUserSourceType().prepare_values(
        {"role_field_id": None},
        user,
    )

    assert values["role_field"] is None
    assert "role_field_id" not in values


@pytest.mark.django_db
def test_prepare_values_sets_role_field_to_none(
    data_fixture,
    role_field_id_test_fixture,
):
    """
    Test the prepare_values() method when the "role_field_id" is
    missing in values.

    Ensure that role_field with a value of None is added to values.
    """

    user, user_source, _, workspace, integration = role_field_id_test_fixture

    database = data_fixture.create_database_application(workspace=workspace)
    users_table = data_fixture.create_database_table(
        name="test_users", database=database
    )
    other_table = data_fixture.create_database_table(
        name="test_other", database=database
    )

    role_field = data_fixture.create_text_field(table=users_table, order=0, name="role")
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    values = LocalBaserowUserSourceType().prepare_values(
        {
            "table_id": other_table.id,
            "integration": integration,
        },
        user,
        user_source,
    )

    assert values["role_field"] is None


@pytest.mark.django_db
def test_get_user_role_returns_role_from_text_field(data_fixture):
    """
    Ensure the get_user_role() method returns a specific user role when
    the Role Field is of type TextFieldType.
    """

    role_name = "foo_role"
    data = populate_local_baserow_test_data(data_fixture, role_name=role_name)
    user_source = data["user_source"]

    UserModel = data["user_table"].get_model()
    first_user = UserModel.objects.first()

    user_role = LocalBaserowUserSourceType().get_user_role(
        first_user,
        user_source,
    )

    assert user_role == role_name


@pytest.mark.django_db
def test_get_user_role_returns_role_from_single_select_field(data_fixture):
    """
    Ensure the get_user_role() method returns a specific user role when
    the Role Field is of type SingleSelectFieldType.
    """

    role = "foo_role"
    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]

    role_field = data_fixture.create_single_select_field(
        table=user_source.table, name="role", order=0
    )
    option = data_fixture.create_select_option(field=role_field, value=role)

    user_source.role_field = role_field
    user_source.save()

    UserModel = data["user_table"].get_model()
    first_user = UserModel.objects.first()
    setattr(first_user, user_source.role_field.db_column, option)

    user_role = LocalBaserowUserSourceType().get_user_role(
        first_user,
        user_source,
    )

    assert user_role == role


@pytest.mark.django_db
def test_get_user_role_returns_empty_string_from_single_select_field(data_fixture):
    """
    Ensure the get_user_role() method returns an empty string, if the Role
    Field is of type SingleSelectFieldType, but there is no selection for
    the row.

    This might happen if a row is created in the Users table, but the Role
    Field is left blank.
    """

    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]

    role_field = data_fixture.create_single_select_field(
        table=user_source.table, name="role", order=0
    )

    # The role_field does not have any actual options, so any rows created
    # would have a null/None value for the Role.
    user_source.role_field = role_field
    user_source.save()

    UserModel = data["user_table"].get_model()
    first_user = UserModel.objects.first()
    user_role = LocalBaserowUserSourceType().get_user_role(
        first_user,
        user_source,
    )

    assert user_role == ""


@pytest.mark.django_db
def test_get_user_role_returns_default_role(data_fixture):
    """
    Ensure the get_user_role() method returns the default user role if
    the UserRole.role_field is None.
    """

    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]
    user_source.role_field = None
    user_source.save()

    UserModel = data["user_table"].get_model()
    first_user = UserModel.objects.first()

    user_role = LocalBaserowUserSourceType().get_user_role(
        first_user,
        user_source,
    )

    assert user_role == f"{DEFAULT_USER_ROLE_PREFIX}{user_source.id}"


@pytest.mark.django_db
def test_get_roles_returns_default_role_if_role_field_is_null(data_fixture):
    """
    Ensure get_roles() returns only the Default User Role if the role_field
    is null.
    """

    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]
    user_source.role_field = None
    user_source.save()

    roles = LocalBaserowUserSourceType().get_roles(user_source)

    assert roles == [f"{DEFAULT_USER_ROLE_PREFIX}{user_source.id}"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_type,expected_is_allowed",
    [
        (None, False),
        (CreatedByField, False),
        (CreatedOnField, False),
        (DateField, False),
        (DurationField, False),
        (FileField, False),
        (FormulaField, True),
        (LastModifiedByField, False),
        (LastModifiedField, False),
        (LinkRowField, False),
        (PasswordField, False),
        (PhoneNumberField, False),
        (RatingField, False),
        (SingleSelectField, True),
        (TextField, True),
        (URLField, False),
    ],
)
def test_role_type_is_allowed(data_fixture, field_type, expected_is_allowed):
    """
    Ensure role_type_is_allowed() returns True if the Field Type is an allowed
    type for Role or False otherwise.
    """

    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]

    if field_type is None:
        role_field = None
    else:
        kwargs = {}
        if field_type == LinkRowField:
            kwargs["link_row_table"] = user_source.table

        role_field = field_type.objects.create(
            table=user_source.table, name=f"name_{str(field_type)}", order=0, **kwargs
        )
        data_fixture.create_model_field(
            user_source.table,
            role_field,
        )

    user_source.role_field = role_field
    user_source.save()

    is_allowed = LocalBaserowUserSourceType().role_type_is_allowed(role_field)

    assert is_allowed is expected_is_allowed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_allowed,expected_roles",
    [
        (True, ["bar_role", "foo_role"]),
        (False, []),
    ],
)
def test_get_roles_returns_empty_list_if_role_type_unsupported(
    data_fixture, is_allowed, expected_roles
):
    """
    Ensure get_roles() returns an empty list if the Role Type is unsupported.
    """

    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]

    # Create a roles field and add some rows
    users_table = data_fixture.create_database_table(name="test_users")
    role_field = data_fixture.create_text_field(
        table=users_table, order=0, name="role", text_default=""
    )
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    # Add some roles
    model = users_table.get_model()
    for role in ["foo_role", "bar_role"]:
        model.objects.create(**{f"field_{role_field.id}": role})

    user_source_type = LocalBaserowUserSourceType()
    user_source_type.role_type_is_allowed = MagicMock(return_value=is_allowed)

    roles = user_source_type.get_roles(user_source)

    assert roles == expected_roles


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles,expected_roles",
    [
        (
            [],
            [],
        ),
        (
            [
                "foo_role",
            ],
            [
                "foo_role",
            ],
        ),
        # We expect the returned roles to be ordered
        (
            ["foo_role", "bar_role"],
            ["bar_role", "foo_role"],
        ),
    ],
)
def test_get_roles_returns_single_select_roles(data_fixture, roles, expected_roles):
    """
    Ensure get_roles() returns the expected list of roles, if the Role Type
    field is a Single Select Field.
    """

    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]

    role_field = data_fixture.create_single_select_field(
        table=user_source.table, name="role", order=0
    )
    for role in roles:
        data_fixture.create_select_option(field=role_field, value=role)

    user_source.role_field = role_field
    user_source.save()

    with patch.object(TableHandler, "get_table") as mock_handler:
        roles = LocalBaserowUserSourceType().get_roles(user_source)

    mock_handler.assert_not_called()
    assert roles == expected_roles


@pytest.mark.django_db
def test_get_roles_returns_empty_list_if_table_is_trashed(data_fixture):
    """Ensure get_roles() returns an empty list if Table is trashed."""

    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]
    role_field = data_fixture.create_text_field(
        table=user_source.table, order=0, name="role"
    )
    user_source.role_field = role_field
    user_source.save()

    with patch.object(
        TableHandler, "get_table", MagicMock(side_effect=TableDoesNotExist)
    ) as mock_handler:
        roles = LocalBaserowUserSourceType().get_roles(user_source)

    mock_handler.assert_called_once_with(user_source.table.id)
    assert roles == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_roles,expected_roles",
    [
        (
            ["foo_role"],
            ["foo_role"],
        ),
        (
            ["foo_role", "bar_role"],
            ["foo_role", "bar_role"],
        ),
        # Ensure empty strings are converted to the default No Role value
        (
            ["foo_role", ""],
            ["foo_role", ""],
        ),
        (
            ["", "foo_role", ""],
            ["foo_role", ""],
        ),
        # Ensure roles with leading/trailing white spaces are trimmed
        (
            ["  "],
            [""],
        ),
        (
            ["foo_role "],
            ["foo_role"],
        ),
        (
            [" foo_role", "bar_role ", " "],
            ["foo_role", "bar_role", ""],
        ),
    ],
)
def test_get_roles_returns_expected_roles(
    data_fixture, user_source_fixture, user_roles, expected_roles
):
    """Ensure get_roles() returns expected roles."""

    user_source = user_source_fixture

    # Create a roles field and add some rows
    users_table = data_fixture.create_database_table(name="test_users")
    role_field = data_fixture.create_text_field(
        table=users_table, order=0, name="role", text_default=""
    )
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    # Add some roles
    model = users_table.get_model()
    for role in user_roles:
        model.objects.create(**{f"field_{role_field.id}": role})

    roles = LocalBaserowUserSourceType().get_roles(user_source)

    assert sorted(roles) == sorted(expected_roles)


@pytest.mark.django_db
def test_get_user_role_returns_role_from_formula_field_date_field(data_fixture):
    """
    Ensure the get_user_role() method returns a specific user role when
    the Role Field is of type FormulaField that points to a Date field.
    """

    role_name = "foo_role"
    extra_fields = [
        {
            "name": "foo_custom_field",
            "field_type": "date",
            "value": "2024-11-14",
        }
    ]
    data = populate_local_baserow_test_data(
        data_fixture, role_name=role_name, extra_fields=extra_fields
    )

    user_source = data["user_source"]
    table = data["user_table"]
    user = data["user"]

    field_handler = FieldHandler()
    formula_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="role_field",
        formula="field('foo_custom_field')",
    )

    user_source.role_field = formula_field
    user_source.save()

    UserModel = data["user_table"].get_model()
    user = UserModel.objects.first()

    user_role = LocalBaserowUserSourceType().get_user_role(
        user,
        user_source,
    )

    assert user_role == "2024-11-14"


@pytest.mark.django_db
def test_get_user_role_returns_role_from_formula_multiple_select_field(data_fixture):
    """
    Ensure the get_user_role() method returns a specific user role when
    the Role Field is of type FormulaField that points to a Multiple select field.
    """

    role_name = "foo_role"
    extra_fields = [
        {
            "name": "foo_custom_field",
            "field_type": "multiple_select",
            "value": {},
        }
    ]
    data = populate_local_baserow_test_data(
        data_fixture, role_name=role_name, extra_fields=extra_fields
    )

    user_source = data["user_source"]
    table = data["user_table"]
    user = data["user"]

    multiple_select_field = data["fields"][-1]

    option = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Sea",
        color="green",
    )

    for row in data["rows"]:
        RowHandler().update_row(
            user,
            table,
            row,
            values={f"field_{multiple_select_field.id}": ["Sea"]},
        )

    field_handler = FieldHandler()
    formula_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="role_field",
        formula="field('foo_custom_field')",
    )

    user_source.role_field = formula_field
    user_source.save()

    UserModel = data["user_table"].get_model()
    user = UserModel.objects.first()

    user_role = LocalBaserowUserSourceType().get_user_role(
        user,
        user_source,
    )

    assert user_role == f'{{"id": {option.id}, "color": "green", "value": "Sea"}}'


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,expected_role",
    [
        ("foo_role", "foo_role"),
        ("", ""),
        # If the role field is null, return an empty string
        (None, ""),
    ],
)
def test_get_user_role_handles_empty_role_field(data_fixture, role, expected_role):
    """
    Test that the get_user_role() method returns a valid role, regardless of
    the state of the role_field.

    The role_field may be None or an empty string, in which case an empty string
    should be returned as the role.
    """

    data = populate_local_baserow_test_data(data_fixture, role_name=role)
    user_source = data["user_source"]
    user_model = data["user_table"].get_model()

    first_user = user_model.objects.first()

    user_role = LocalBaserowUserSourceType().get_user_role(
        first_user,
        user_source,
    )

    assert user_role == expected_role


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_provided_email",
    (
        [
            "foo@bar.com",
            "Foo@bar.com",
            "foo@Bar.com",
            "foo@bar.Com",
            "FOO@bar.com",
            "foo@BAR.com",
            "foo@bar.COM",
            "FOO@BAR.COM",
        ]
    ),
)
def test_local_baserow_user_source_get_user_is_case_insensitive(
    data_fixture,
    user_provided_email,
):
    """
    Ensure that the user provided email address is not case sensitive when
    authenticating in the backend.
    """

    data = populate_local_baserow_test_data(data_fixture)

    user_source = data["user_source"]
    user_source_type = user_source.get_type()
    UserModel = data["user_table"].get_model()

    user = UserModel.objects.first()

    # set the user's actual email in the backend
    actual_email = "foo@bar.com"
    email_field = user_source.email_field.db_column
    setattr(user, email_field, actual_email)
    user.save()

    user = user_source_type.get_user(user_source, email=user_provided_email)

    assert user.email == actual_email


def test__generate_update_user_count_cache_key():
    user_source = Mock(id=123)
    assert (
        LocalBaserowUserSourceType()._generate_update_user_count_cache_key(user_source)
        == "local_baserow_user_source_123_user_count"
    )


def test__generate_update_user_count_cache_value():
    with freeze_time("2024-11-29T12:00:00.00Z"):
        assert (
            LocalBaserowUserSourceType()._generate_update_user_count_cache_value(500)
            == "500-1732881600.0"
        )


@pytest.mark.django_db
def test_update_user_count_with_configured_user_sources(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application1 = data_fixture.create_builder_application(workspace=workspace)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application1
    )
    application2 = data_fixture.create_builder_application(workspace=workspace)
    integration2 = data_fixture.create_local_baserow_integration(
        application=application2
    )
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["jrmi@baserow.io", "Jérémie", ""],
            ["peter@baserow.io", "Peter", ""],
            ["afonso@baserow.io", "Afonso", ""],
            ["tsering@baserow.io", "Tsering", ""],
            ["evren@baserow.io", "Evren", ""],
        ],
    )
    email_field, name_field, role_field = fields

    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")

    user_source1 = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application1,
        integration=integration1,
        table=table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )
    user_source2 = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=application2,
        integration=integration2,
        table=table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )

    # 1. Fetching all configured user sources.
    # 2. Fetching all tables for the user sources.
    # 3. One COUNT per table, in our case here, once.
    with freeze_time("2030-11-29T12:00:00.00Z"), django_assert_num_queries(3):
        local_baserow_user_source_type.update_user_count()

    with django_assert_num_queries(0):
        user_count = local_baserow_user_source_type.get_user_count(user_source1)
        assert user_count.count == 5
        assert user_count.last_updated == datetime(2030, 11, 29, 12, 0, 0)

    with django_assert_num_queries(0):
        user_count = local_baserow_user_source_type.get_user_count(user_source2)
        assert user_count.count == 5
        assert user_count.last_updated == datetime(2030, 11, 29, 12, 0, 0)


@pytest.mark.django_db
def test_update_user_count_with_misconfigured_user_sources(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    application1 = data_fixture.create_builder_application(workspace=workspace)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application1
    )
    application2 = data_fixture.create_builder_application(workspace=workspace)
    integration2 = data_fixture.create_local_baserow_integration(
        application=application2
    )

    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")

    user_source1 = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        table=table,
        application=application1,
        integration=integration1,
    )
    user_source2 = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        table=table,
        application=application2,
        integration=integration2,
    )

    # 1. Fetching all configured user sources.
    with django_assert_num_queries(1):
        local_baserow_user_source_type.update_user_count()

    # `get_user_count` will find that there's no cache entry, so they
    # will each trigger 1 query. We only cache the count if the user
    # source is configured.
    with django_assert_num_queries(0):
        assert local_baserow_user_source_type.get_user_count(user_source1) is None
    with django_assert_num_queries(0):
        assert local_baserow_user_source_type.get_user_count(user_source2) is None


@pytest.mark.django_db
def test_trigger_user_count_update_on_properties_requiring_user_recount_update(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)
    table_a, fields_a, rows_a = data_fixture.build_table(
        database=database,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["jrmi@baserow.io", "Jérémie", ""],
            ["peter@baserow.io", "Peter", ""],
        ],
    )
    email_field_a, name_field_a, role_field_a = fields_a

    user_source_type = LocalBaserowUserSourceType()
    user_source = data_fixture.create_user_source(
        user_source_type.model_class,
        table=table_a,
        application=application,
        integration=integration,
        email_field=email_field_a,
        name_field=name_field_a,
        role_field=role_field_a,
    )

    table_a_count = user_source_type.get_user_count(user_source)
    assert table_a_count.count == 2

    table_b, fields_b, rows_b = data_fixture.build_table(
        database=database,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["jrmi@baserow.io", "Jérémie", ""],
            ["peter@baserow.io", "Peter", ""],
            ["afonso@baserow.io", "Afonso", ""],
            ["tsering@baserow.io", "Tsering", ""],
            ["evren@baserow.io", "Evren", ""],
        ],
    )
    email_field_b, name_field_b, role_field_b = fields_b

    UserSourceService().update_user_source(
        user,
        user_source,
        **{
            "table": table_b,
            "email_field": email_field_b,
            "name_field": name_field_b,
            "role_field": role_field_b,
        },
    )

    table_b_count = user_source_type.get_user_count(user_source)
    assert table_b_count.count == 5
    assert (
        table_b_count.last_updated != table_a_count.last_updated
    )  # confirm it's a fresh cache entry


def test_local_baserow_after_user_source_update_requires_user_recount():
    assert (
        LocalBaserowUserSourceType().after_user_source_update_requires_user_recount(
            Mock(), {}
        )
        is True
    )
