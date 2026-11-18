import json
from copy import deepcopy

from django.db import connection

import pytest

from baserow.contrib.dashboard.formula_property_extractor import (
    get_dashboard_used_property_names,
)
from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.models import (
    TextFilterWidget,
    WidgetFilterCondition,
    WidgetFilterGroup,
    WidgetFilterTarget,
)
from baserow.core.formula import BaserowFormulaObject


@pytest.fixture
def linked_filter(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    table = data_fixture.create_database_table()
    field = data_fixture.create_text_field(table=table)
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, table=table
    )
    target = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    owner = TextFilterWidget.objects.create(dashboard=dashboard, title="Filter")
    group = {
        "filter_type": "OR",
        # Children can precede their parent in the API representation.
        "filter_groups": [
            {"id": "child", "parent_group": 1, "filter_type": "AND"},
            {"id": 1, "parent_group": None, "filter_type": "OR"},
        ],
        "filters": [
            {
                "field": field.id,
                "type": "equal",
                "value": BaserowFormulaObject.create("first", mode="raw"),
                "group": "child",
            },
            {
                "field": field.id,
                "type": "contains",
                "value": BaserowFormulaObject.create("second", mode="raw"),
            },
        ],
    }
    owner.target_filters = [
        {
            "target_widget_id": target.id,
            "enabled": False,
            "empty_behavior": "apply_alternative",
            "group": group,
            "alternative_group": deepcopy(group),
        }
    ]
    owner.save()
    return owner, target


@pytest.mark.django_db
def test_relational_filter_round_trip_and_formula_storage(linked_filter):
    owner, _ = linked_filter
    original = deepcopy(owner.target_filters)
    owner.refresh_from_db()
    assert owner.target_filters == original
    condition_ids = list(WidgetFilterCondition.objects.values_list("id", flat=True))
    # Ordinary widget edits must not recreate the relational conditions.
    owner.title = "Renamed"
    owner.save(update_fields=["title"])
    owner.save()
    assert (
        list(WidgetFilterCondition.objects.values_list("id", flat=True))
        == condition_ids
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT value FROM dashboard_widgetfiltercondition ORDER BY id LIMIT 1"
        )
        stored = cursor.fetchone()[0]
    if isinstance(stored, str):
        stored = json.loads(stored)
    assert stored == {"f": "first", "m": "raw", "v": "0.1"}


@pytest.mark.django_db
def test_deleting_target_cascades_only_its_contributions(linked_filter, data_fixture):
    owner, target = linked_filter
    other = data_fixture.create_summary_widget(dashboard=owner.dashboard)
    original = deepcopy(owner.target_filters[0])
    original["target_widget_id"] = other.id
    owner.target_filters.append(original)
    owner.save()
    target.delete()
    owner.refresh_from_db()
    assert owner.target_filters == [original]
    assert WidgetFilterTarget.objects.count() == 1
    assert WidgetFilterGroup.objects.count() == 6
    assert WidgetFilterCondition.objects.count() == 4


@pytest.mark.django_db
def test_related_formula_edits_invalidate_cached_widget_properties(
    linked_filter, monkeypatch
):
    owner, _ = linked_filter
    widget_type = owner.get_type()
    calls = []

    def extract(widget, **kwargs):
        calls.append(widget.id)
        return {
            "test": [
                widget.target_filters[0]["group"]["filters"][0]["value"]["formula"]
            ]
        }

    monkeypatch.setattr(widget_type, "extract_properties", extract)
    assert get_dashboard_used_property_names([owner]) == {"test": ["first"]}
    assert get_dashboard_used_property_names([owner]) == {"test": ["first"]}
    condition = WidgetFilterCondition.objects.order_by("id").first()
    condition.value = BaserowFormulaObject.create("changed", mode="raw")
    condition.save()
    reloaded = WidgetHandler().get_widget(owner.id)
    assert get_dashboard_used_property_names([reloaded]) == {"test": ["changed"]}
    assert calls == [owner.id, owner.id]


@pytest.mark.django_db
def test_widget_list_prefetches_all_filter_branches(
    linked_filter, django_assert_num_queries
):
    owner, _ = linked_filter
    widgets = list(WidgetHandler().get_widgets(owner.dashboard))
    with django_assert_num_queries(0):
        assert (
            next(w for w in widgets if w.id == owner.id).target_filters
            == owner.target_filters
        )
