from django.urls import reverse

import pytest
from freezegun import freeze_time

from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.contrib.database.api.rows.serializers import RowSerializer
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.models import WorkspaceUser


@pytest.fixture
def options_snapshot_dashboard(data_fixture, request):
    field_type = getattr(request, "param", "number")
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Value", field_type)],
        rows=[
            [str(index % 250) if field_type == "text" else index % 250]
            for index in range(500)
        ],
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    widget = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    reference = f"get('table.{table.id}.*.{fields[0].db_column}')"
    selection = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Numbers",
        formula_value=BaserowFormulaObject.create(reference),
    )
    return user, token, selection, table, fields[0], widget, reference


@pytest.mark.django_db
@pytest.mark.parametrize("calculated", [False, True])
def test_option_snapshot_continues_without_reading_rows_and_refreshes_explicitly(
    api_client, options_snapshot_dashboard, monkeypatch, calculated
):
    user, token, selection, table, field, _, reference = options_snapshot_dashboard
    if calculated:
        DashboardFilterService().update_filter(
            user,
            selection.id,
            formula_value=BaserowFormulaObject.create(f"if(true, {reference}, '')"),
        )
    serialized_rows = 0
    original = RowSerializer.to_representation

    def count_serialized_rows(self, instance):
        nonlocal serialized_rows
        serialized_rows += 1
        return original(self, instance)

    monkeypatch.setattr(RowSerializer, "to_representation", count_serialized_rows)
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    after = None
    for offset in range(0, 250, 50):
        response = api_client.post(
            url,
            {"after": after, "selected": ["249", "missing"]},
            format="json",
            **headers,
        )
        assert response.status_code == 200, response.json()
        assert response.json()["results"] == [
            str(index) for index in range(offset, offset + 50)
        ]
        assert response.json()["available"] == ["249"]
        assert serialized_rows == (500 if calculated else 0)
        after = response.json()["next"]
        if offset == 0:
            table.get_model().objects.all().update(**{field.db_column: 999})
    assert after is None
    refreshed = api_client.post(url, {}, format="json", **headers)
    assert refreshed.status_code == 200, refreshed.json()
    assert refreshed.json()["results"] == ["999"]
    assert serialized_rows == (1000 if calculated else 0)


@pytest.mark.django_db
@pytest.mark.parametrize("calculated", [False, True])
@pytest.mark.parametrize(
    "change, status, error",
    [
        ("table_access", 401, "PERMISSION_DENIED"),
        ("dashboard_access", 401, "PERMISSION_DENIED"),
        ("unused_table", 400, "ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED"),
        ("configuration", 400, "ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED"),
        ("other_user", 400, "ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED"),
        ("other_filter", 400, "ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED"),
        ("expired", 400, "ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED"),
    ],
)
def test_option_snapshot_rechecks_access_and_configuration(
    api_client,
    data_fixture,
    options_snapshot_dashboard,
    change,
    status,
    error,
    calculated,
):
    user, token, selection, table, field, widget, reference = options_snapshot_dashboard
    if calculated:
        DashboardFilterService().update_filter(
            user,
            selection.id,
            formula_value=BaserowFormulaObject.create(f"if(true, {reference}, '')"),
        )
        selection.refresh_from_db()
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    first = api_client.post(url, {"limit": 1}, format="json", **headers)
    assert first.status_code == 200, first.json()
    after = first.json()["next"]
    assert after
    if change == "table_access":
        assert table.database.workspace_id != selection.dashboard.workspace_id
        WorkspaceUser.objects.filter(
            user=user, workspace=table.database.workspace
        ).delete()
    elif change == "dashboard_access":
        WorkspaceUser.objects.filter(
            user=user, workspace=selection.dashboard.workspace
        ).delete()
    elif change == "unused_table":
        widget.delete()
    elif change == "configuration":
        DashboardFilterService().update_filter(
            user,
            selection.id,
            formula_value=BaserowFormulaObject.create("'Updated'"),
        )
    elif change == "other_user":
        other, other_token = data_fixture.create_user_and_token()
        for workspace in [selection.dashboard.workspace, table.database.workspace]:
            data_fixture.create_user_workspace(user=other, workspace=workspace)
        headers = {"HTTP_AUTHORIZATION": f"JWT {other_token}"}
    elif change == "other_filter":
        other = DashboardFilterService().create_filter(
            user, selection.dashboard_id, formula_value=selection.formula_value
        )
        url = reverse("api:dashboard:filters:options", kwargs={"filter_id": other.id})
    if change == "expired":
        api_client.force_authenticate(user=user)
        with freeze_time("2100-01-01"):
            response = api_client.post(url, {"after": after}, format="json", **headers)
    else:
        response = api_client.post(url, {"after": after}, format="json", **headers)
    assert response.status_code == status, response.json()
    assert response.json()["error"] == error


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change",
    [
        {"label": "Renamed"},
        {"operator": "not_equal"},
        {"mode": "input"},
        {"multiple": True},
    ],
)
def test_option_snapshot_survives_changes_unrelated_to_its_values(
    api_client, options_snapshot_dashboard, change
):
    user, token, selection, *_ = options_snapshot_dashboard
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    first = api_client.post(url, {"limit": 1}, format="json", **headers)
    assert first.status_code == 200, first.json()
    assert first.json()["results"] == ["0"]

    DashboardFilterService().update_filter(user, selection.id, **change)
    continuation = api_client.post(
        url, {"after": first.json()["next"], "limit": 1}, format="json", **headers
    )
    assert continuation.status_code == 200, continuation.json()
    assert continuation.json()["results"] == ["1"]


@pytest.mark.django_db
@pytest.mark.parametrize("change", [{"mode": "advanced"}, {"version": "0.2"}])
def test_option_snapshot_expires_when_formula_metadata_changes_with_identical_text(
    api_client, options_snapshot_dashboard, change
):
    user, token, selection, *_ = options_snapshot_dashboard
    formula = BaserowFormulaObject.create("'France,Belgium'", "raw")
    DashboardFilterService().update_filter(user, selection.id, formula_value=formula)
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    first = api_client.post(url, {"limit": 1}, format="json", **headers)
    assert first.status_code == 200, first.json()
    assert first.json()["next"]

    DashboardFilterService().update_filter(
        user, selection.id, formula_value={**formula, **change}
    )
    expired = api_client.post(
        url, {"after": first.json()["next"]}, format="json", **headers
    )
    assert expired.status_code == 400, expired.json()
    assert expired.json()["error"] == "ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "setting, maximum", [("MAX_SNAPSHOT_VALUES", 100), ("MAX_SNAPSHOT_BYTES", 10)]
)
@pytest.mark.parametrize(
    "options_snapshot_dashboard", ["number", "text"], indirect=True
)
def test_option_snapshot_budget_failure_cleans_up_and_keeps_previous_choices(
    api_client, options_snapshot_dashboard, monkeypatch, setting, maximum
):
    from django.core.cache import cache

    from django_redis import get_redis_connection

    from baserow.contrib.dashboard.filters import option_snapshots

    user, token, selection, *_ = options_snapshot_dashboard
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    first = api_client.post(url, {}, format="json", **headers)
    assert first.status_code == 200, first.json()
    redis = get_redis_connection("default")
    pattern = (
        cache.make_key(f"dashboard-filter-options:{user.pk}:{selection.pk}") + ":*"
    )
    previous_keys = set(redis.scan_iter(match=pattern))
    monkeypatch.setattr(option_snapshots, setting, maximum)
    failed = api_client.post(url, {}, format="json", **headers)
    assert failed.status_code == 400, failed.json()
    assert failed.json()["error"] == "ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE"
    assert set(redis.scan_iter(match=pattern)) == previous_keys
    continuation = api_client.post(
        url, {"after": first.json()["next"]}, format="json", **headers
    )
    assert continuation.status_code == 200, continuation.json()
    assert continuation.json()["results"] == [str(index) for index in range(50, 100)]


@pytest.mark.django_db
def test_initial_loads_and_refreshes_keep_other_tabs_option_snapshots(
    api_client, options_snapshot_dashboard
):
    user, token, selection, table, field, *_ = options_snapshot_dashboard
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    initial_pages = [
        api_client.post(url, {"limit": 1}, format="json", **headers) for _ in range(2)
    ]
    for initial in initial_pages:
        assert initial.status_code == 200, initial.json()
        assert initial.json()["results"] == ["0"]

    table.get_model().objects.all().update(**{field.db_column: 999})
    refreshed = api_client.post(url, {}, format="json", **headers)
    assert refreshed.status_code == 200, refreshed.json()
    assert refreshed.json()["results"] == ["999"]

    for initial in initial_pages:
        continuation = api_client.post(
            url, {"after": initial.json()["next"], "limit": 1}, format="json", **headers
        )
        assert continuation.status_code == 200, continuation.json()
        assert continuation.json()["results"] == ["1"]


@pytest.mark.django_db
def test_concurrent_option_resolutions_retain_independent_snapshots(
    options_snapshot_dashboard,
):
    from baserow.contrib.dashboard.filters.option_snapshots import (
        DashboardFilterOptionsSnapshot,
    )

    user, _, selection, *_ = options_snapshot_dashboard
    snapshot = DashboardFilterOptionsSnapshot(user, selection)
    latest = None

    def older_values():
        nonlocal latest
        yield "Old first"
        latest = snapshot.create(lambda: ["New first", "New second"], [])
        yield "Old second"

    older = snapshot.create(older_values, [])
    assert snapshot.page(
        older, limit=50, selected=[], validate_tables=lambda _: None
    ) == {
        "results": ["Old first", "Old second"],
        "next": None,
        "snapshot": older,
        "available": [],
    }
    assert snapshot.page(
        latest, limit=50, selected=[], validate_tables=lambda _: None
    ) == {
        "results": ["New first", "New second"],
        "next": None,
        "snapshot": latest,
        "available": [],
    }


@pytest.mark.django_db
def test_a_slow_calculated_formula_keeps_its_own_snapshot_after_a_newer_load(
    api_client, options_snapshot_dashboard, monkeypatch
):
    from baserow.contrib.dashboard.filters import options

    user, token, selection, _, _, _, reference = options_snapshot_dashboard
    DashboardFilterService().update_filter(
        user,
        selection.id,
        formula_value=BaserowFormulaObject.create(f"if(true, {reference}, '')"),
    )
    url = reverse("api:dashboard:filters:options", kwargs={"filter_id": selection.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    latest = None
    resolving_older = True

    def resolve_in_reverse_order(*args):
        nonlocal latest, resolving_older
        if resolving_older:
            resolving_older = False
            latest = api_client.post(url, {"limit": 1}, format="json", **headers)
            return ["Old first", "Old second"]
        return ["New first", "New second"]

    monkeypatch.setattr(options, "resolve_formula", resolve_in_reverse_order)
    older = api_client.post(url, {"limit": 1}, format="json", **headers)
    assert older.status_code == 200, older.json()
    assert older.json()["results"] == ["Old first"]
    assert latest.status_code == 200, latest.json()
    assert latest.json()["results"] == ["New first"]
    continuation = api_client.post(
        url, {"after": latest.json()["next"]}, format="json", **headers
    )
    assert continuation.status_code == 200, continuation.json()
    assert continuation.json()["results"] == ["New second"]
    continuation = api_client.post(
        url, {"after": older.json()["next"]}, format="json", **headers
    )
    assert continuation.status_code == 200, continuation.json()
    assert continuation.json()["results"] == ["Old second"]
