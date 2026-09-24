"""Public export must preserve whether an ad-hoc grouping option was supplied."""

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.export.models import ExportJob
from baserow_premium.api.views.signers import export_public_view_signer


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("group_mode", ["omitted", "clear", "replace"])
def test_public_export_job_preserves_group_by_presence(
    premium_data_fixture, api_client, group_mode
):
    table = premium_data_fixture.create_database_table()
    field = premium_data_fixture.create_text_field(table=table, primary=True)
    view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    premium_data_fixture.create_view_group_by(view=view, field=field, order="ASC")
    payload = {"exporter_type": "csv"}
    if group_mode != "omitted":
        payload["group_by"] = "" if group_mode == "clear" else f"-{field.db_column}"

    response = api_client.post(
        reverse("api:premium:view:export_public_view", kwargs={"slug": view.slug}),
        payload,
        format="json",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    job = ExportJob.objects.get(
        id=export_public_view_signer.loads(response.json()["id"])
    )
    assert job.view_id == view.id
    if group_mode == "omitted":
        assert "group_by" not in job.export_options, (
            "An ordinary public export must not gain group_by=None in its persisted "
            f"worker payload: {job.export_options}"
        )
    else:
        assert job.export_options["group_by"] == payload["group_by"]
