"""Export payload compatibility and independent grouping/sorting semantics."""

import csv
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.export.handler import ExportHandler
from baserow.contrib.database.export.models import (
    EXPORT_JOB_FINISHED_STATUS,
    ExportJob,
)


@pytest.fixture
def export_grid(data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    group = data_fixture.create_text_field(table=table, name="Group", primary=True)
    rank = data_fixture.create_number_field(table=table, name="Rank")
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=view, field=group, order="ASC")
    data_fixture.create_view_sort(view=view, field=rank, order="DESC")
    model = table.get_model()
    rows = [
        model.objects.create(order=index, **{group.db_column: value, rank.db_column: n})
        for index, (value, n) in enumerate([("B", 2), ("A", 3), ("B", 4), ("A", 1)])
    ]
    return token, table, view, group, rank, rows


@pytest.mark.django_db
@pytest.mark.parametrize("scope", ["table", "view"])
@pytest.mark.parametrize("group_mode", ["omitted", "clear", "replace"])
def test_export_job_preserves_group_by_presence(
    export_grid, api_client, scope, group_mode
):
    token, table, view, group, _, _ = export_grid
    payload = {"exporter_type": "csv"}
    if scope == "view":
        payload["view_id"] = view.id
    if group_mode != "omitted":
        payload["group_by"] = "" if group_mode == "clear" else f"-{group.db_column}"

    response = api_client.post(
        reverse("api:database:export:export_table", kwargs={"table_id": table.id}),
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    job = ExportJob.objects.get(id=response.json()["id"])
    assert job.view_id == (view.id if scope == "view" else None)
    if group_mode == "omitted":
        # This JSON payload crosses a deployment boundary: an older Celery worker
        # does not consume group_by and forwards unknown keys to the CSV writer.
        assert "group_by" not in job.export_options, (
            "An export request without group_by must not persist group_by=None. "
            "Older workers forward that unexpected keyword to the exporter. "
            f"Persisted options: {job.export_options}"
        )
    else:
        assert job.export_options["group_by"] == payload["group_by"]


@pytest.mark.django_db
@pytest.mark.parametrize("group_mode", ["inherit", "clear", "replace"])
@pytest.mark.parametrize("sort_mode", ["inherit", "clear", "replace"])
def test_csv_export_keeps_grouping_and_sorting_overrides_independent(
    export_grid, api_client, tmp_path, settings, group_mode, sort_mode
):
    token, table, view, group, rank, rows = export_grid
    payload = {"exporter_type": "csv", "view_id": view.id}
    if group_mode != "inherit":
        payload["group_by"] = "" if group_mode == "clear" else f"-{group.db_column}"
    if sort_mode != "inherit":
        payload["order_by"] = "" if sort_mode == "clear" else rank.db_column

    response = api_client.post(
        reverse("api:database:export:export_table", kwargs={"table_id": table.id}),
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    job = ExportJob.objects.get(id=response.json()["id"])
    storage = FileSystemStorage(location=str(tmp_path), base_url="http://localhost")
    with patch("baserow.core.storage.get_default_storage", return_value=storage):
        ExportHandler.run_export_job(job)

    job.refresh_from_db()
    assert job.state == EXPORT_JOB_FINISHED_STATUS
    path = tmp_path / settings.EXPORT_FILES_DIRECTORY / job.exported_file_name
    with path.open(encoding="utf-8-sig", newline="") as exported_file:
        exported_rows = list(csv.DictReader(exported_file))

    expected_order = {
        ("inherit", "inherit"): [1, 3, 2, 0],
        ("inherit", "clear"): [1, 3, 0, 2],
        ("inherit", "replace"): [3, 1, 0, 2],
        ("clear", "inherit"): [2, 1, 0, 3],
        ("clear", "clear"): [0, 1, 2, 3],
        ("clear", "replace"): [3, 0, 1, 2],
        ("replace", "inherit"): [2, 0, 1, 3],
        ("replace", "clear"): [0, 2, 1, 3],
        ("replace", "replace"): [0, 2, 3, 1],
    }
    assert [int(row["id"]) for row in exported_rows] == [
        rows[index].id for index in expected_order[group_mode, sort_mode]
    ]


@pytest.mark.django_db
def test_csv_exporter_write_to_file_tolerates_unknown_kwargs(
    export_grid, api_client, tmp_path, settings
):
    """
    During a rolling deploy an old Celery worker may forward unknown export
    options (like group_by) to write_to_file. All exporters must accept
    **kwargs so this does not crash.
    """

    token, table, view, group, rank, rows = export_grid
    payload = {"exporter_type": "csv", "view_id": view.id}

    response = api_client.post(
        reverse("api:database:export:export_table", kwargs={"table_id": table.id}),
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    job = ExportJob.objects.get(id=response.json()["id"])
    # Simulate old worker not popping group_by from export_options.
    job.export_options["group_by"] = f"field_{group.id}"
    job.save(update_fields=["export_options"])

    storage = FileSystemStorage(location=str(tmp_path), base_url="http://localhost")
    with patch("baserow.core.storage.get_default_storage", return_value=storage):
        ExportHandler.run_export_job(job)

    job.refresh_from_db()
    assert job.state == EXPORT_JOB_FINISHED_STATUS, (
        f"Export should succeed even with unknown kwargs, but state={job.state}"
    )
