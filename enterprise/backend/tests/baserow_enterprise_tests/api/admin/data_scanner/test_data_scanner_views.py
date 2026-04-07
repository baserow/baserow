from io import BytesIO
from unittest.mock import MagicMock, patch

from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.test_utils.helpers import AnyStr
from baserow_enterprise.data_scanner.job_types import DataScanResultExportJobType
from baserow_enterprise.data_scanner.models import DataScan, DataScanResult


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_scans_unauthenticated(api_client):
    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:list"),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_scans_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_scans_without_enterprise_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_scans(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    scan = DataScan.objects.create(
        name="Scan 1", scan_type="pattern", pattern="AA", created_by=user
    )
    DataScan.objects.create(name="Scan 2", scan_type="list_of_values", created_by=user)

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["count"] == 2
    assert data["results"][0] == {
        "id": scan.id,
        "name": "Scan 1",
        "scan_type": "pattern",
        "pattern": "AA",
        "frequency": "manual",
        "scan_all_workspaces": True,
        "whole_words": True,
        "workspace_ids": [],
        "is_running": False,
        "last_run_started_at": None,
        "last_run_finished_at": None,
        "last_error": None,
        "list_items": [],
        "results_count": 0,
        "source_table_id": None,
        "source_field_id": None,
        "source_workspace_id": None,
        "source_database_id": None,
        "created_on": AnyStr(),
        "updated_on": AnyStr(),
    }


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_scans_search(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    DataScan.objects.create(
        name="IBAN Scanner", scan_type="pattern", pattern="AA", created_by=user
    )
    DataScan.objects.create(
        name="Email Scanner", scan_type="pattern", pattern="99", created_by=user
    )

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:list"),
        {"search": "IBAN"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["name"] == "IBAN Scanner"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_scans_query_count_is_constant(api_client, enterprise_data_fixture):
    """
    The number of queries when listing scans must not grow with the number of
    scans (no N+1). Adding more scans should not increase the query count.
    """

    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    workspace = enterprise_data_fixture.create_workspace(user=user)

    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["value"]],
    )

    DataScan.objects.create(
        name="Scan 1", scan_type="pattern", pattern="AA", created_by=user
    )
    scan2 = DataScan.objects.create(
        name="Scan 2", scan_type="list_of_values", created_by=user
    )
    scan2.workspaces.add(workspace)

    DataScanResult.objects.create(
        scan=scan2,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test",
        first_identified_on=timezone.now(),
        last_identified_on=timezone.now(),
    )

    url = reverse("api:enterprise:admin:data_scanner:list")

    with CaptureQueriesContext(connection) as captured_2_scans:
        response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        assert response.json()["count"] == 2

    num_queries_2 = len(captured_2_scans)

    for i in range(3, 8):
        DataScan.objects.create(
            name=f"Scan {i}", scan_type="pattern", pattern="DD", created_by=user
        )

    with CaptureQueriesContext(connection) as captured_7_scans:
        response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        assert response.json()["count"] == 7

    num_queries_7 = len(captured_7_scans)

    assert num_queries_7 == num_queries_2, (
        f"Query count grew from {num_queries_2} to {num_queries_7} when adding "
        f"more scans — likely an N+1 problem."
    )


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_unauthenticated(api_client):
    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {"name": "Test", "scan_type": "pattern", "pattern": "AA"},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {"name": "Test", "scan_type": "pattern", "pattern": "AA"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {"name": "Test", "scan_type": "pattern", "pattern": "AA"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_pattern(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {
            "name": "IBAN Scan",
            "scan_type": "pattern",
            "pattern": "AADDAAAADDDDDDDDDD",
            "frequency": "daily",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["name"] == "IBAN Scan"
    assert data["scan_type"] == "pattern"
    assert data["pattern"] == "AADDAAAADDDDDDDDDD"
    assert data["frequency"] == "daily"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_list_of_values(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {
            "name": "List Scan",
            "scan_type": "list_of_values",
            "list_items": ["val1", "val2"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["scan_type"] == "list_of_values"
    assert data["list_items"] == ["val1", "val2"]


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_list_table(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["test"]],
    )

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {
            "name": "Table Scan",
            "scan_type": "list_table",
            "source_table_id": table.id,
            "source_field_id": fields[0].id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["source_table_id"] == table.id
    assert data["source_field_id"] == fields[0].id


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_with_specific_workspaces(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    ws = enterprise_data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {
            "name": "WS Scan",
            "scan_type": "pattern",
            "pattern": "AA",
            "scan_all_workspaces": False,
            "workspace_ids": [ws.id],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["scan_all_workspaces"] is False
    assert data["workspace_ids"] == [ws.id]


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_pattern_missing_pattern(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {"name": "Missing Pattern", "scan_type": "pattern"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_list_of_values_missing_items(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {"name": "Missing Items", "scan_type": "list_of_values"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_list_table_missing_source(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {"name": "Missing Source", "scan_type": "list_table"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_list_table_incompatible_source_field(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table = enterprise_data_fixture.create_database_table(user=user)
    boolean_field = enterprise_data_fixture.create_boolean_field(
        table=table, name="Active"
    )

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {
            "name": "Boolean Scan",
            "scan_type": "list_table",
            "source_table_id": table.id,
            "source_field_id": boolean_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_whole_words(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    # Default should be True.
    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {
            "name": "Default whole_words",
            "scan_type": "pattern",
            "pattern": "AA",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["whole_words"] is True

    # Explicitly setting whole_words=False should be forwarded.
    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:list"),
        {
            "name": "Disable whole_words",
            "scan_type": "pattern",
            "pattern": "AA",
            "whole_words": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["whole_words"] is False


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_structure_excludes_incompatible_fields(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table = enterprise_data_fixture.create_database_table(user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Name")
    enterprise_data_fixture.create_boolean_field(table=table, name="Active")
    workspace = table.database.workspace

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:workspace_structure",
            kwargs={"workspace_id": workspace.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    fields = data[0]["tables"][0]["fields"]
    field_names = {f["name"] for f in fields}
    assert "Name" in field_names
    assert "Active" not in field_names


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_scan_unauthenticated(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=user
    )

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_scan_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=admin
    )

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_scan_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": 1},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_scan(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    scan = DataScan.objects.create(
        name="Test Scan", scan_type="pattern", pattern="AA", created_by=user
    )

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": scan.id,
        "name": "Test Scan",
        "scan_type": "pattern",
        "pattern": "AA",
        "frequency": "manual",
        "scan_all_workspaces": True,
        "whole_words": True,
        "workspace_ids": [],
        "is_running": False,
        "last_run_started_at": None,
        "last_run_finished_at": None,
        "last_error": None,
        "list_items": [],
        "results_count": 0,
        "source_table_id": None,
        "source_field_id": None,
        "source_workspace_id": None,
        "source_database_id": None,
        "created_on": AnyStr(),
        "updated_on": AnyStr(),
    }


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_scan_not_found(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": 99999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_unauthenticated(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=user
    )

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        {"name": "Updated"},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=admin
    )

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        {"name": "Updated"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": 1},
        ),
        {"name": "Updated"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    scan = DataScan.objects.create(
        name="Original", scan_type="pattern", pattern="AA", created_by=user
    )

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        {"name": "Updated", "frequency": "weekly"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "Updated"
    assert response.json()["frequency"] == "weekly"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_not_found(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": 99999},
        ),
        {"name": "Updated"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_already_running(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    scan = DataScan.objects.create(
        name="Running",
        scan_type="pattern",
        pattern="AA",
        created_by=user,
        is_running=True,
    )

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        {"name": "Updated"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_409_CONFLICT


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_unauthenticated(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=user
    )

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=admin
    )

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": 1},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    scan = DataScan.objects.create(
        name="To Delete", scan_type="pattern", pattern="AA", created_by=user
    )

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert DataScan.objects.filter(id=scan.id).count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_not_found(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": 99999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_already_running(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    scan = DataScan.objects.create(
        name="Running",
        scan_type="pattern",
        pattern="AA",
        created_by=user,
        is_running=True,
    )

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:detail",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_409_CONFLICT


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_unauthenticated(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=user
    )

    response = api_client.post(
        reverse(
            "api:enterprise:admin:data_scanner:trigger",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=admin
    )

    response = api_client.post(
        reverse(
            "api:enterprise:admin:data_scanner:trigger",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse(
            "api:enterprise:admin:data_scanner:trigger",
            kwargs={"scan_id": 1},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    scan = DataScan.objects.create(
        name="Trigger Test", scan_type="pattern", pattern="AA", created_by=user
    )

    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "baserow_enterprise.data_scanner.tasks.run_data_scan.delay",
            lambda scan_id: None,
        )
        response = api_client.post(
            reverse(
                "api:enterprise:admin:data_scanner:trigger",
                kwargs={"scan_id": scan.id},
            ),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_202_ACCEPTED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_not_found(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse(
            "api:enterprise:admin:data_scanner:trigger",
            kwargs={"scan_id": 9999999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_already_running(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    scan = DataScan.objects.create(
        name="Running",
        scan_type="pattern",
        pattern="AA",
        created_by=user,
        is_running=True,
    )

    response = api_client.post(
        reverse(
            "api:enterprise:admin:data_scanner:trigger",
            kwargs={"scan_id": scan.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_409_CONFLICT


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_results_unauthenticated(api_client):
    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:results"),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_results_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:results"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_results_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:results"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_results(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["test"]],
    )

    scan = DataScan.objects.create(
        name="Results Test", scan_type="pattern", pattern="AA", created_by=user
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test value",
        first_identified_on=now,
        last_identified_on=now,
    )

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:results"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["count"] == 1
    result = data["results"][0]
    assert result["matched_value"] == "test value"
    assert result["scan_name"] == "Results Test"
    assert result["table_name"] == table.name
    assert result["field_name"] == fields[0].name
    assert result["workspace_name"] == table.database.workspace.name
    assert result["database_name"] == table.database.name


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_results_filter_by_scan(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["test"]],
    )

    scan1 = DataScan.objects.create(
        name="Scan 1", scan_type="pattern", pattern="AA", created_by=user
    )
    scan2 = DataScan.objects.create(
        name="Scan 2", scan_type="pattern", pattern="99", created_by=user
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan1,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="match1",
        first_identified_on=now,
        last_identified_on=now,
    )
    DataScanResult.objects.create(
        scan=scan2,
        table=table,
        field=fields[0],
        row_id=2,
        matched_value="match2",
        first_identified_on=now,
        last_identified_on=now,
    )

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:results"),
        {"scan_id": scan1.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["scan_name"] == "Scan 1"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_results_search(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["test"]],
    )

    scan = DataScan.objects.create(
        name="Search Test", scan_type="pattern", pattern="AA", created_by=user
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="NL12ABCD0123456789",
        first_identified_on=now,
        last_identified_on=now,
    )
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=2,
        matched_value="something-else",
        first_identified_on=now,
        last_identified_on=now,
    )

    response = api_client.get(
        reverse("api:enterprise:admin:data_scanner:results"),
        {"search": "NL12"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["matched_value"] == "NL12ABCD0123456789"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_results_query_count_is_constant(api_client, enterprise_data_fixture):
    """
    The number of queries when listing results must not grow with the number of
    results (no N+1). Adding more results should not increase the query count.
    """

    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["test"]],
    )

    scan = DataScan.objects.create(
        name="Query Count Test", scan_type="pattern", pattern="AA", created_by=user
    )
    now = timezone.now()
    for i in range(1, 3):
        DataScanResult.objects.create(
            scan=scan,
            table=table,
            field=fields[0],
            row_id=i,
            matched_value=f"match{i}",
            first_identified_on=now,
            last_identified_on=now,
        )

    url = reverse("api:enterprise:admin:data_scanner:results")

    with CaptureQueriesContext(connection) as captured_2_results:
        response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        assert response.json()["count"] == 2

    num_queries_2 = len(captured_2_results)

    for i in range(3, 8):
        DataScanResult.objects.create(
            scan=scan,
            table=table,
            field=fields[0],
            row_id=i,
            matched_value=f"match{i}",
            first_identified_on=now,
            last_identified_on=now,
        )

    with CaptureQueriesContext(connection) as captured_7_results:
        response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        assert response.json()["count"] == 7

    num_queries_7 = len(captured_7_results)

    assert num_queries_7 == num_queries_2, (
        f"Query count grew from {num_queries_2} to {num_queries_7} when adding "
        f"more results — likely an N+1 problem."
    )


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_result_unauthenticated(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=user
    )
    now = timezone.now()
    result = DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test",
        first_identified_on=now,
        last_identified_on=now,
    )

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:result_delete",
            kwargs={"result_id": result.id},
        ),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_result_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=admin, columns=[("Name", "text")], rows=[["test"]]
    )
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=admin
    )
    now = timezone.now()
    result = DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test",
        first_identified_on=now,
        last_identified_on=now,
    )

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:result_delete",
            kwargs={"result_id": result.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_result_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:result_delete",
            kwargs={"result_id": 1},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_result(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )
    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=user
    )
    now = timezone.now()
    result = DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test",
        first_identified_on=now,
        last_identified_on=now,
    )

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:result_delete",
            kwargs={"result_id": result.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert DataScanResult.objects.filter(id=result.id).count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_result_not_found(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:data_scanner:result_delete",
            kwargs={"result_id": 99999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_structure_unauthenticated(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    ws = enterprise_data_fixture.create_workspace(user=user)

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:workspace_structure",
            kwargs={"workspace_id": ws.id},
        ),
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_structure_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)
    ws = enterprise_data_fixture.create_workspace(user=admin)

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:workspace_structure",
            kwargs={"workspace_id": ws.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_structure_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:workspace_structure",
            kwargs={"workspace_id": 1},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_structure(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text"), ("Notes", "text")],
        rows=[["test", "note"]],
    )
    workspace = table.database.workspace

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:workspace_structure",
            kwargs={"workspace_id": workspace.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    db = data[0]
    assert db["name"] == table.database.name
    assert len(db["tables"]) == 1
    tbl = db["tables"][0]
    assert tbl["name"] == table.name
    assert len(tbl["fields"]) >= 2
    field_names = {f["name"] for f in tbl["fields"]}
    assert "Name" in field_names
    assert "Notes" in field_names


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_structure_not_found(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse(
            "api:enterprise:admin:data_scanner:workspace_structure",
            kwargs={"workspace_id": 99999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_export_results_unauthenticated(api_client):
    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:results_export"),
        {},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_export_results_non_staff(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=False)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:results_export"),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_export_results_without_license(api_client, enterprise_data_fixture):
    _, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:enterprise:admin:data_scanner:results_export"),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.storage.get_default_storage")
def test_export_results_csv(get_storage_mock, api_client, enterprise_data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )
    scan = DataScan.objects.create(
        name="Export Test", scan_type="pattern", pattern="AA", created_by=user
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="matched",
        first_identified_on=now,
        last_identified_on=now,
    )

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user,
        DataScanResultExportJobType.type,
        csv_column_separator=",",
        csv_first_row_header=True,
        export_charset="utf-8",
        sync=True,
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED

    data = stub_file.getvalue().decode("utf-8")
    assert "Export Test" in data
    assert "matched" in data
    assert "Scan Name" in data

    close()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.storage.get_default_storage")
def test_export_results_csv_without_header(
    get_storage_mock, api_client, enterprise_data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )
    scan = DataScan.objects.create(
        name="NoHeader", scan_type="pattern", pattern="AA", created_by=user
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="val",
        first_identified_on=now,
        last_identified_on=now,
    )

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user,
        DataScanResultExportJobType.type,
        csv_column_separator=",",
        csv_first_row_header=False,
        export_charset="utf-8",
        sync=True,
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED

    data = stub_file.getvalue().decode("utf-8")
    assert "Scan Name" not in data
    assert "NoHeader" in data

    close()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.storage.get_default_storage")
def test_export_results_csv_filter_by_scan(
    get_storage_mock, api_client, enterprise_data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )
    scan1 = DataScan.objects.create(
        name="Scan A", scan_type="pattern", pattern="AA", created_by=user
    )
    scan2 = DataScan.objects.create(
        name="Scan B", scan_type="pattern", pattern="99", created_by=user
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan1,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="a_match",
        first_identified_on=now,
        last_identified_on=now,
    )
    DataScanResult.objects.create(
        scan=scan2,
        table=table,
        field=fields[0],
        row_id=2,
        matched_value="b_match",
        first_identified_on=now,
        last_identified_on=now,
    )

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user,
        DataScanResultExportJobType.type,
        csv_column_separator=",",
        csv_first_row_header=True,
        export_charset="utf-8",
        filter_scan_id=scan1.id,
        sync=True,
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED

    data = stub_file.getvalue().decode("utf-8")
    assert "a_match" in data
    assert "b_match" not in data

    close()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.storage.get_default_storage")
def test_export_results_deleting_job_deletes_file(
    get_storage_mock, api_client, enterprise_data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None

    csv_export_job = JobHandler().create_and_start_job(
        user,
        DataScanResultExportJobType.type,
        csv_column_separator=",",
        csv_first_row_header=True,
        export_charset="utf-8",
        sync=True,
    )
    csv_export_job.refresh_from_db()
    assert csv_export_job.state == JOB_FINISHED
    assert csv_export_job.exported_file_name is not None

    close()

    from baserow.contrib.database.export.handler import ExportHandler

    with patch(
        "baserow_enterprise.data_scanner.job_types.get_default_storage"
    ) as mock_storage:
        mock_storage.return_value = storage_mock
        DataScanResultExportJobType().before_delete(csv_export_job)
        storage_mock.delete.assert_called_once_with(
            ExportHandler.export_file_path(csv_export_job.exported_file_name)
        )
