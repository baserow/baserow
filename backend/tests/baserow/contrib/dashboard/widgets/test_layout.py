from unittest.mock import patch

import pytest

from baserow.contrib.dashboard.widgets.exceptions import WidgetLayoutInvalid
from baserow.contrib.dashboard.widgets.layout import WidgetLayoutHandler
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.dashboard.widgets.types import WidgetLayoutDelta


def test_widget_layout_delta_contains_only_added_removed_or_changed_widgets():
    unchanged = {
        "id": 1,
        "grid_x": 0,
        "grid_y": 0,
        "grid_width": 2,
        "grid_height": 4,
    }
    changed_before = {
        "id": 2,
        "grid_x": 2,
        "grid_y": 0,
        "grid_width": 2,
        "grid_height": 4,
    }
    changed_after = {**changed_before, "grid_x": 4}
    removed = {**unchanged, "id": 3, "grid_y": 4}
    added = {**unchanged, "id": 4, "grid_y": 4}

    delta = WidgetLayoutDelta.between(
        [unchanged, changed_before, removed],
        [unchanged, changed_after, added],
    )

    assert delta.original_layout == [changed_before, removed]
    assert delta.new_layout == [changed_after, added]


@pytest.mark.django_db
def test_widget_layout_handler_validates_and_compacts_a_complete_layout(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    first_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="First"
    )
    second_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Second"
    )
    widgets = list(
        Widget.objects.filter(dashboard=dashboard)
        .select_related("content_type")
        .order_by("id")
    )

    compacted = WidgetLayoutHandler(widgets).validate(
        [
            {
                "id": first_widget.id,
                "grid_x": 0,
                "grid_y": 0,
                "grid_width": 2,
                "grid_height": 4,
            },
            {
                "id": second_widget.id,
                "grid_x": 0,
                "grid_y": 8,
                "grid_width": 2,
                "grid_height": 4,
            },
        ],
        enforce_vertical_bound=False,
        compact=True,
    )

    assert compacted[first_widget.id]["grid_y"] == 0
    assert compacted[second_widget.id]["grid_y"] == 4

    with pytest.raises(WidgetLayoutInvalid, match="cannot overlap"):
        WidgetLayoutHandler(widgets).validate(
            [
                compacted[first_widget.id],
                {**compacted[second_widget.id], "grid_y": 0},
            ]
        )


@pytest.mark.django_db
def test_widget_layout_handler_applies_only_changed_rows(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    first_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="First"
    )
    second_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Second"
    )
    first_updated_on = first_widget.updated_on
    second_updated_on = second_widget.updated_on
    widgets = list(
        Widget.objects.filter(dashboard=dashboard)
        .select_related("content_type")
        .order_by("id")
    )
    handler = WidgetLayoutHandler(widgets)
    layout_by_widget_id = handler.validate(
        [
            handler.from_widget(widgets[0]),
            {**handler.from_widget(widgets[1]), "grid_x": 4},
        ]
    )

    with patch(
        "baserow.contrib.dashboard.widgets.layout.Widget.objects.bulk_update",
        wraps=Widget.objects.bulk_update,
    ) as bulk_update_mock:
        delta = handler.apply(layout_by_widget_id)

    assert [item["id"] for item in delta.original_layout] == [second_widget.id]
    assert [item["id"] for item in delta.new_layout] == [second_widget.id]
    assert delta.original_layout[0]["grid_x"] == 2
    assert delta.new_layout[0]["grid_x"] == 4
    bulk_update_mock.assert_called_once()
    assert [widget.id for widget in bulk_update_mock.call_args.args[0]] == [
        second_widget.id
    ]

    first_widget.refresh_from_db()
    second_widget.refresh_from_db()
    assert first_widget.updated_on == first_updated_on
    assert second_widget.updated_on != second_updated_on
    assert second_widget.grid_x == 4
