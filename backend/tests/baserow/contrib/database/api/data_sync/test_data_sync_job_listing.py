from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext, override_settings

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.data_sync.models import (
    DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC,
    SyncDataSyncTableJob,
)
from baserow.core.jobs.constants import JOB_FINISHED


def create_data_sync_with_two_members(data_fixture):
    owner, token = data_fixture.create_user_and_token(first_name="Owner")
    workspace = data_fixture.create_workspace(user=owner)
    member = data_fixture.create_user(workspace=workspace, first_name="Member")
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_sync = data_fixture.create_ical_data_sync(
        table=table, ical_url="https://baserow.io/ical.ics"
    )
    return owner, token, member, data_sync


@pytest.mark.django_db
def test_list_sync_jobs_includes_other_users_runs(api_client, data_fixture):
    owner, token, member, data_sync = create_data_sync_with_two_members(data_fixture)
    foreign_job = SyncDataSyncTableJob.objects.create(
        user=member,
        data_sync=data_sync,
        state=JOB_FINISHED,
        triggered_by=DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC,
    )

    response = api_client.get(
        reverse("api:jobs:list") + f"?type=sync_data_sync_table"
        f"&sync_data_sync_table_data_sync_id={data_sync.id}&limit=10",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 1
    jobs = response.json()["jobs"]
    assert [job["id"] for job in jobs] == [foreign_job.id]
    assert jobs[0]["triggered_by"] == DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC
    assert jobs[0]["user_name"] == "Member"
    assert jobs[0]["state"] == JOB_FINISHED


@pytest.mark.django_db
def test_list_sync_jobs_hidden_without_workspace_access(api_client, data_fixture):
    owner, token, member, data_sync = create_data_sync_with_two_members(data_fixture)
    SyncDataSyncTableJob.objects.create(
        user=member, data_sync=data_sync, state=JOB_FINISHED
    )
    outsider, outsider_token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:jobs:list") + f"?type=sync_data_sync_table"
        f"&sync_data_sync_table_data_sync_id={data_sync.id}",
        HTTP_AUTHORIZATION=f"JWT {outsider_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["jobs"] == []


@pytest.mark.django_db
def test_polling_by_job_ids_only_widens_for_opted_in_job_types(
    api_client, data_fixture
):
    owner, token, member, data_sync = create_data_sync_with_two_members(data_fixture)
    foreign_sync_job = SyncDataSyncTableJob.objects.create(
        user=member, data_sync=data_sync
    )
    foreign_other_job = data_fixture.create_fake_job(user=member)

    response = api_client.get(
        reverse("api:jobs:list")
        + f"?job_ids={foreign_sync_job.id},{foreign_other_job.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert [job["id"] for job in response.json()["jobs"]] == [foreign_sync_job.id]


@pytest.mark.django_db
def test_starting_sync_conflicts_with_another_users_running_job(
    api_client, data_fixture
):
    owner, token, member, data_sync = create_data_sync_with_two_members(data_fixture)
    SyncDataSyncTableJob.objects.create(user=member, data_sync=data_sync)

    response = api_client.post(
        reverse(
            "api:database:data_sync:sync_table",
            kwargs={"data_sync_id": data_sync.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MAX_JOB_COUNT_EXCEEDED"


@pytest.mark.django_db
def test_list_sync_jobs_paginates_with_count(api_client, data_fixture):
    owner, token, member, data_sync = create_data_sync_with_two_members(data_fixture)
    jobs = [
        SyncDataSyncTableJob.objects.create(
            user=member, data_sync=data_sync, state=JOB_FINISHED
        )
        for _ in range(3)
    ]

    response = api_client.get(
        reverse("api:jobs:list") + f"?type=sync_data_sync_table"
        f"&sync_data_sync_table_data_sync_id={data_sync.id}&limit=2&offset=2",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 3
    assert [job["id"] for job in response.json()["jobs"]] == [jobs[0].id]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_sync_jobs_query_count_does_not_scale_with_results(
    api_client, data_fixture
):
    owner, token, member, data_sync = create_data_sync_with_two_members(data_fixture)
    url = (
        reverse("api:jobs:list") + f"?type=sync_data_sync_table"
        f"&sync_data_sync_table_data_sync_id={data_sync.id}&limit=10"
    )

    SyncDataSyncTableJob.objects.create(
        user=member, data_sync=data_sync, state=JOB_FINISHED
    )
    ContentType.objects.clear_cache()
    with CaptureQueriesContext(connection) as queries_for_one:
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK

    for _ in range(9):
        SyncDataSyncTableJob.objects.create(
            user=member, data_sync=data_sync, state=JOB_FINISHED
        )
    ContentType.objects.clear_cache()
    with CaptureQueriesContext(connection) as queries_for_ten:
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert len(response.json()["jobs"]) == 10

    assert len(queries_for_ten) <= len(queries_for_one)


@pytest.mark.django_db
def test_polling_foreign_job_types_batches_content_type_lookup(
    api_client, data_fixture
):
    owner, token, member, data_sync = create_data_sync_with_two_members(data_fixture)
    foreign_sync_job = SyncDataSyncTableJob.objects.create(
        user=member, data_sync=data_sync
    )
    foreign_other_job = data_fixture.create_fake_job(user=member)
    ContentType.objects.clear_cache()

    with CaptureQueriesContext(connection) as queries:
        response = api_client.get(
            reverse("api:jobs:list")
            + f"?job_ids={foreign_sync_job.id},{foreign_other_job.id}",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    batched_content_type_fetches = [
        query
        for query in queries
        if 'FROM "django_content_type"' in query["sql"]
        and '"django_content_type"."id" IN (' in query["sql"]
    ]
    # User scoping resolves every requested foreign job type with one IN query. Other
    # single-ID content-type reads can still be made while serializing concrete jobs.
    assert len(batched_content_type_fetches) == 1
