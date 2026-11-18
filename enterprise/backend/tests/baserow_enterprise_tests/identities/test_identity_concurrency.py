from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

from django.db import connection, connections
from django.urls import reverse

import pytest
from rest_framework.test import APIClient

from baserow.core.identities.service import IdentityService
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.identities.identity_extension_types import (
    EnterpriseIdentityExtensionType,
)
from baserow_enterprise.teams.models import TeamSubject


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("has_initial_team", [False, True])
def test_concurrent_identity_team_replacements_are_serialized(
    data_fixture,
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    has_initial_team,
):
    """A second PATCH waits for the first transaction before replacing its teams."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    first_team = enterprise_data_fixture.create_team(workspace=workspace)
    second_team = enterprise_data_fixture.create_team(workspace=workspace)
    initial_team = enterprise_data_fixture.create_team(workspace=workspace)
    identity = IdentityService().create_identity(
        user,
        workspace,
        name="Concurrent identity",
        team_ids=[initial_team.id] if has_initial_team else [],
    )
    url = reverse("api:identities:item", kwargs={"identity_id": identity.id})
    first_in_extension = Event()
    release_first = Event()
    second_connected = Event()
    second_pid = []
    original_update = EnterpriseIdentityExtensionType.update

    def pause_first_update(extension, identity, values, user):
        if values["team_ids"] == [first_team.id]:
            first_in_extension.set()
            assert release_first.wait(10), "First update was never released"
        return original_update(extension, identity, values, user)

    def request_update(team_id):
        """Give each concurrent request its own client and database connection."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '10s'")
                if team_id == second_team.id:
                    cursor.execute("SELECT pg_backend_pid()")
                    second_pid.append(cursor.fetchone()[0])
                    second_connected.set()
            return APIClient().patch(
                url,
                {"team_ids": [team_id]},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
        finally:
            connections.close_all()

    with (
        patch.object(EnterpriseIdentityExtensionType, "update", pause_first_update),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        first = executor.submit(request_update, first_team.id)
        try:
            assert first_in_extension.wait(10)
            second = executor.submit(request_update, second_team.id)
            assert second_connected.wait(10)
            deadline = monotonic() + 5
            blocked = False
            # Observe a real database lock wait instead of relying on thread timing.
            while monotonic() < deadline and not second.done():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT cardinality(pg_blocking_pids(%s))", second_pid
                    )
                    blocked = cursor.fetchone()[0] > 0
                if blocked:
                    break
                sleep(0.01)
            assert blocked, (
                "The second PATCH did not wait for the first identity update"
            )
        finally:
            release_first.set()
        assert first.result(timeout=10).status_code == 200
        assert second.result(timeout=10).status_code == 200

    assert list(
        TeamSubject.objects.filter(
            subject_type=UserSubjectType().get_content_type(), subject_id=identity.id
        ).values_list("team_id", flat=True)
    ) == [second_team.id]
