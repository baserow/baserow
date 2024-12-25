import dataclasses
from unittest.mock import patch

from django.shortcuts import reverse
from django.test.utils import override_settings
from django.utils.translation import gettext_lazy as _

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
)

from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
    action_type_registry,
)
from baserow.core.actions import CreateWorkspaceActionType
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.audit_log.models import AuditLogEntry


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method,url_name",
    [
        ("get", "users"),
        ("get", "action_types"),
        ("get", "list"),
        ("post", "async_export"),
    ],
)
@override_settings(DEBUG=True)
def test_admins_cannot_access_audit_log_endpoints_without_an_enterprise_license(
    api_client, enterprise_data_fixture, method, url_name
):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = getattr(api_client, method)(
        reverse(f"api:enterprise:audit_log:{url_name}"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["users", "workspaces", "action_types", "list"])
@override_settings(DEBUG=True)
def test_non_admins_cannot_access_audit_log_endpoints(
    api_client, enterprise_data_fixture, url_name
):
    enterprise_data_fixture.enable_enterprise()

    _, token = enterprise_data_fixture.create_user_and_token()

    response = api_client.get(
        reverse(f"api:enterprise:audit_log:{url_name}"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_non_admins_cannot_export_audit_log_to_csv(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()

    response = api_client.post(
        reverse("api:enterprise:audit_log:async_export"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_user_filter_returns_users_correctly(
    api_client, enterprise_data_fixture
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token(
        email="admin@test.com"
    )
    user = enterprise_data_fixture.create_user(email="user@test.com")

    # no search query should return all users
    response = api_client.get(
        reverse("api:enterprise:audit_log:users"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": admin_user.id, "value": admin_user.email},
            {"id": user.id, "value": user.email},
        ],
    }

    # searching by email should return only the correct user
    response = api_client.get(
        reverse("api:enterprise:audit_log:users") + "?search=admin",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": admin_user.id, "value": admin_user.email}],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_workspace_filter_returns_workspaces_correctly(
    api_client, enterprise_data_fixture
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    workspace_1 = enterprise_data_fixture.create_workspace(
        name="workspace 1", user=admin_user
    )
    workspace_2 = enterprise_data_fixture.create_workspace(
        name="workspace 2", user=admin_user
    )

    # no search query should return all workspaces
    response = api_client.get(
        reverse("api:enterprise:audit_log:workspaces"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": workspace_1.id, "value": workspace_1.name},
            {"id": workspace_2.id, "value": workspace_2.name},
        ],
    }

    # searching by name should return only the correct workspace
    response = api_client.get(
        reverse("api:enterprise:audit_log:workspaces") + "?search=1",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": workspace_1.id, "value": workspace_1.name}],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_action_type_filter_returns_action_types_correctly(
    api_client, enterprise_data_fixture
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    action_types = action_type_registry.get_all()

    # no search query should return all the available action types``
    response = api_client.get(
        reverse("api:enterprise:audit_log:action_types"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": len(action_types),
        "next": None,
        "previous": None,
        "results": sorted(
            [
                {"id": action_type.type, "value": action_type.get_short_description()}
                for action_type in action_types
            ],
            key=lambda x: x["value"],
        ),
    }

    # searching by name should return only the correct action_type
    response = api_client.get(
        reverse("api:enterprise:audit_log:action_types")
        + f"?search=create+application",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": "create_application", "value": "Create application"}],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_action_types_are_translated_in_the_admin_language(
    api_client, enterprise_data_fixture
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token(language="it")

    with patch("django.utils.translation.override") as mock_override:
        api_client.get(
            reverse("api:enterprise:audit_log:action_types"),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        mock_override.assert_called_once_with("it")

    # the search works in the user language
    response = api_client.get(
        (reverse("api:enterprise:audit_log:action_types") + f"?search=crea+progetto"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": "create_group", "value": "Crea progetto"}],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_entries_are_created_even_without_a_license(
    api_client, enterprise_data_fixture
):
    user = enterprise_data_fixture.create_user()

    with freeze_time("2023-01-01 12:00:00"):
        CreateWorkspaceActionType.do(user, "workspace 1")

    with freeze_time("2023-01-01 12:00:01"):
        CreateWorkspaceActionType.do(user, "workspace 2")

    assert AuditLogEntry.objects.count() == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_entries_are_created_from_actions_and_returned_in_order(
    api_client, enterprise_data_fixture, synced_roles
):
    session_id = "session_id"
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token(
        session_id=session_id
    )

    with freeze_time("2023-01-01 12:00:00"):
        workspace_1 = CreateWorkspaceActionType.do(admin_user, "workspace 1").workspace

    with freeze_time("2023-01-01 12:00:10"):
        ActionHandler.undo(admin_user, [CreateWorkspaceActionType.scope()], session_id)

    with freeze_time("2023-01-01 12:00:20"):
        ActionHandler.redo(admin_user, [CreateWorkspaceActionType.scope()], session_id)

    common_json = {
        "action_type": "create_group",
        "workspace": f"{workspace_1.name} ({workspace_1.id})",
        "id": AnyInt(),
        "ip_address": None,
        "type": "Create group",
        "user": f"{admin_user.email} ({admin_user.id})",
    }

    response = api_client.get(
        reverse("api:enterprise:audit_log:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {
                **common_json,
                "description": f'REDONE: Group "{workspace_1.name}" ({workspace_1.id}) created.',
                "timestamp": "2023-01-01T12:00:20Z",
            },
            {
                **common_json,
                "description": f'UNDONE: Group "{workspace_1.name}" ({workspace_1.id}) created.',
                "timestamp": "2023-01-01T12:00:10Z",
            },
            {
                **common_json,
                "description": f'Group "{workspace_1.name}" ({workspace_1.id}) created.',
                "timestamp": "2023-01-01T12:00:00Z",
            },
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_entries_are_translated_in_the_user_language(
    api_client, enterprise_data_fixture
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token(language="it")

    with freeze_time("2023-01-01 12:00:00"):
        workspace_1 = CreateWorkspaceActionType.do(admin_user, "workspace 1").workspace

    with freeze_time("2023-01-01 12:00:01"):
        workspace_2 = CreateWorkspaceActionType.do(admin_user, "workspace 2").workspace

    with patch("django.utils.translation.override") as mock_override:
        api_client.get(
            reverse("api:enterprise:audit_log:list"),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        mock_override.assert_called_once_with("it")

    response = api_client.get(
        reverse("api:enterprise:audit_log:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "action_type": "create_group",
                "description": f'Progetto "{workspace_2.name}" ({workspace_2.id}) creato.',
                "workspace": f"{workspace_2.name} ({workspace_2.id})",
                "id": AnyInt(),
                "ip_address": None,
                "timestamp": "2023-01-01T12:00:01Z",
                "type": "Crea progetto",
                "user": f"{admin_user.email} ({admin_user.id})",
            },
            {
                "action_type": "create_group",
                "description": f'Progetto "{workspace_1.name}" ({workspace_1.id}) creato.',
                "workspace": f"{workspace_1.name} ({workspace_1.id})",
                "id": AnyInt(),
                "ip_address": None,
                "timestamp": "2023-01-01T12:00:00Z",
                "type": "Crea progetto",
                "user": f"{admin_user.email} ({admin_user.id})",
            },
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_entries_can_be_filtered(api_client, enterprise_data_fixture):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    user = enterprise_data_fixture.create_user()

    with freeze_time("2023-01-01 12:00:00"):
        workspace_1 = CreateWorkspaceActionType.do(admin_user, "workspace 1").workspace

    with freeze_time("2023-01-01 12:00:01"):
        workspace_2 = CreateWorkspaceActionType.do(user, "workspace 2").workspace

    json_workspace_1 = {
        "action_type": "create_group",
        "description": f'Group "{workspace_1.name}" ({workspace_1.id}) created.',
        "workspace": f"{workspace_1.name} ({workspace_1.id})",
        "id": AnyInt(),
        "ip_address": None,
        "timestamp": "2023-01-01T12:00:00Z",
        "type": "Create group",
        "user": f"{admin_user.email} ({admin_user.id})",
    }
    json_workspace_2 = {
        "action_type": "create_group",
        "description": f'Group "{workspace_2.name}" ({workspace_2.id}) created.',
        "workspace": f"{workspace_2.name} ({workspace_2.id})",
        "id": AnyInt(),
        "ip_address": None,
        "timestamp": "2023-01-01T12:00:01Z",
        "type": "Create group",
        "user": f"{user.email} ({user.id})",
    }

    # by user_id
    response = api_client.get(
        reverse("api:enterprise:audit_log:list") + "?user_id=" + str(user.id),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [json_workspace_2],
    }

    # by workspace_id
    response = api_client.get(
        reverse("api:enterprise:audit_log:list")
        + "?workspace_id="
        + str(workspace_1.id),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [json_workspace_1],
    }

    # by action_type
    response = api_client.get(
        reverse("api:enterprise:audit_log:list") + "?action_type=create_group",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [json_workspace_2, json_workspace_1],
    }

    response = api_client.get(
        reverse("api:enterprise:audit_log:list") + "?action_type=create_application",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }

    # from timestamp
    response = api_client.get(
        reverse("api:enterprise:audit_log:list")
        + "?from_timestamp=2023-01-01T12:00:01Z",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [json_workspace_2],
    }

    # to timestamp
    response = api_client.get(
        reverse("api:enterprise:audit_log:list") + "?to_timestamp=2023-01-01T12:00:00Z",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [json_workspace_1],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_entries_return_400_for_invalid_values(
    api_client, enterprise_data_fixture
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    # an invalid value in the query params should return a 400
    response = api_client.get(
        reverse("api:enterprise:audit_log:list") + "?user_id=wrong_type",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_can_export_to_csv_all_entries(
    api_client,
    enterprise_data_fixture,
    synced_roles,
    django_capture_on_commit_callbacks,
):
    admin_user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    csv_settings = {
        "csv_column_separator": ",",
        "csv_first_row_header": True,
        "export_charset": "utf-8",
    }

    with freeze_time("2023-01-01 12:00"), django_capture_on_commit_callbacks(
        execute=True
    ):
        admin_token = enterprise_data_fixture.generate_token(admin_user)
        response = api_client.post(
            reverse("api:enterprise:audit_log:async_export"),
            data=csv_settings,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
    assert response.status_code == HTTP_202_ACCEPTED, response.json()
    job = response.json()
    assert job["id"] is not None
    assert job["state"] == "pending"
    assert job["type"] == "audit_log_export"

    admin_token = enterprise_data_fixture.generate_token(admin_user)
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "audit_log_export"
    for key, value in csv_settings.items():
        assert job[key] == value
    for key in [
        "filter_user_id",
        "filter_workspace_id",
        "filter_action_type",
        "filter_from_timestamp",
        "filter_to_timestamp",
    ]:
        assert job[key] is None
    assert job["exported_file_name"].endswith(".csv")
    assert job["url"].startswith("http://localhost:8000/media/export_files/")
    assert job["created_on"] == "2023-01-01T12:00:00Z"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_audit_log_can_export_to_csv_filtered_entries(
    api_client,
    enterprise_data_fixture,
    synced_roles,
    django_capture_on_commit_callbacks,
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=admin_user)

    csv_settings = {
        "csv_column_separator": "|",
        "csv_first_row_header": False,
        "export_charset": "utf-8",
        "exclude_columns": "ip_address",
    }
    filters = {
        "filter_user_id": admin_user.id,
        "filter_workspace_id": workspace.id,
        "filter_action_type": "create_application",
        "filter_from_timestamp": "2023-01-01T00:00:00Z",
        "filter_to_timestamp": "2023-01-03T00:00:00Z",
    }

    # if the action type is invalid, it should return a 400
    response = api_client.post(
        reverse("api:enterprise:audit_log:async_export"),
        data={**csv_settings, "filter_action_type": "wrong_type"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    with freeze_time("2023-01-02 12:00"), django_capture_on_commit_callbacks(
        execute=True
    ):
        admin_token = enterprise_data_fixture.generate_token(admin_user)
        response = api_client.post(
            reverse("api:enterprise:audit_log:async_export"),
            data={**csv_settings, **filters},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
    assert response.status_code == HTTP_202_ACCEPTED, response.json()
    job = response.json()
    assert job["id"] is not None
    assert job["state"] == "pending"
    assert job["type"] == "audit_log_export"

    admin_token = enterprise_data_fixture.generate_token(admin_user)
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "audit_log_export"
    for key, value in csv_settings.items():
        assert job[key] == value
    for key in [
        "filter_user_id",
        "filter_workspace_id",
        "filter_action_type",
        "filter_from_timestamp",
        "filter_to_timestamp",
    ]:
        assert job[key] == filters[key]
    assert job["exported_file_name"].endswith(".csv")
    assert job["url"].startswith("http://localhost:8000/media/export_files/")
    assert job["created_on"] == "2023-01-02T12:00:00Z"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_log_entries_still_work_correctly_if_the_action_type_is_removed(
    api_client, enterprise_data_fixture, synced_roles
):
    class TemporaryActionType(ActionType):
        type = "temporary"
        description = ActionTypeDescription(
            short=_("Temporary action"),
            long=_("This is a temporary action with value: %(value)s."),
        )

        @dataclasses.dataclass
        class Params:
            value: str

        @classmethod
        def do(cls, user, value):
            return cls.register_action(user, cls.Params(value), cls.scope())

        @classmethod
        def scope(cls, *args, **kwargs) -> ActionScopeStr:
            return "test"

    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    assert AuditLogEntry.objects.count() == 0

    action_type_registry.register(TemporaryActionType())
    with freeze_time("2023-01-01 12:00"):
        TemporaryActionType.do(admin, "test")
    assert AuditLogEntry.objects.count() == 1

    entry = AuditLogEntry.objects.first()
    assert entry.action_type == TemporaryActionType.type
    assert entry.original_action_long_descr == TemporaryActionType.description.long
    assert entry.original_action_short_descr == TemporaryActionType.description.short

    action_type_registry.unregister(TemporaryActionType.type)

    response = api_client.get(
        reverse("api:enterprise:audit_log:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    entry = response_json["results"][0]
    expected_data = {
        "action_type": "temporary",
        "description": "This is a temporary action with value: test.",
        "workspace": "",
        "ip_address": None,
        "timestamp": "2023-01-01T12:00:00Z",
        "type": "Temporary action",
        "user": f"{admin.email} ({admin.id})",
    }
    for key, value in expected_data.items():
        assert entry[key] == value

    # we can also change the action parameters and everything still works
    class TemporaryActionTypeV2(ActionType):
        type = "temporary"
        description = ActionTypeDescription(
            short=_("Temporary action"),
            long=_("This is a temporary action with value: %(value)s and %(uid)s."),
        )

        @dataclasses.dataclass
        class Params:
            value: str
            uid: int

        @classmethod
        def do(cls, user, value, uid):
            return cls.register_action(user, cls.Params(value, uid), cls.scope())

        @classmethod
        def scope(cls, *args, **kwargs) -> ActionScopeStr:
            return "test"

    action_type_registry.register(TemporaryActionTypeV2())

    response = api_client.get(
        reverse("api:enterprise:audit_log:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    entry = response_json["results"][0]

    # the previous entry now use the new description, leaving the
    # placeholder for the new missing parameter
    expected_data = {
        "action_type": "temporary",
        "description": "This is a temporary action with value: test and %(uid)s.",
        "workspace": "",
        "ip_address": None,
        "timestamp": "2023-01-01T12:00:00Z",
        "type": "Temporary action",
        "user": f"{admin.email} ({admin.id})",
    }
    for key, value in expected_data.items():
        assert entry[key] == value

    # if we now perform a new action, the new description will contain the new uid value
    with freeze_time("2023-01-01 12:01"):
        TemporaryActionTypeV2.do(admin, "test", 42)

    assert AuditLogEntry.objects.count() == 2

    response = api_client.get(
        reverse("api:enterprise:audit_log:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 2
    expected_data = [
        {
            "action_type": "temporary",
            "description": "This is a temporary action with value: test and 42.",
            "workspace": "",
            "ip_address": None,
            "timestamp": "2023-01-01T12:01:00Z",
            "type": "Temporary action",
            "user": f"{admin.email} ({admin.id})",
        },
        {
            "action_type": "temporary",
            "description": "This is a temporary action with value: test and %(uid)s.",
            "workspace": "",
            "ip_address": None,
            "timestamp": "2023-01-01T12:00:00Z",
            "type": "Temporary action",
            "user": f"{admin.email} ({admin.id})",
        },
    ]
    for entry, expected_data in zip(response_json["results"], expected_data):
        for key, value in expected_data.items():
            assert entry[key] == value
