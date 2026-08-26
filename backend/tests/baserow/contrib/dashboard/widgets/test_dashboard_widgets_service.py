from unittest.mock import ANY, patch

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connections, transaction

import pytest

from baserow.contrib.dashboard.exceptions import DashboardDoesNotExist
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.widgets.exceptions import (
    WidgetDoesNotExist,
    WidgetTypeDoesNotExist,
)
from baserow.contrib.dashboard.widgets.models import SummaryWidget, Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.exceptions import PermissionException


@pytest.mark.django_db
def test_get_widget(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    assert WidgetService().get_widget(user, widget.id).id == widget.id


@pytest.mark.django_db
def test_get_widget_does_not_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(WidgetDoesNotExist):
        assert WidgetService().get_widget(user, 0)


@pytest.mark.django_db
def test_get_widget_permission_denied(data_fixture):
    user_without_perms = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    with pytest.raises(PermissionException):
        WidgetService().get_widget(user_without_perms, widget.id)


@pytest.mark.django_db
def test_get_widget_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard, trashed=True)

    with pytest.raises(WidgetDoesNotExist):
        WidgetService().get_widget(user, widget.id)


@pytest.mark.django_db
def test_get_widget_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    with pytest.raises(WidgetDoesNotExist):
        WidgetService().get_widget(user, widget.id)


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
def test_get_widgets_for_layout_mutation_locks_dashboard(data_fixture):
    dashboard = data_fixture.create_dashboard_application()

    with transaction.atomic():
        WidgetService()._get_widgets_for_layout_mutation(dashboard)

        with pytest.raises(DatabaseError):
            connections["default-copy"]
            Dashboard.objects.using("default-copy").select_for_update(nowait=True).get(
                id=dashboard.id
            )


@pytest.mark.django_db
def test_get_widgets(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)
    widget_2 = data_fixture.create_summary_widget(dashboard=dashboard)
    widget_3 = data_fixture.create_summary_widget(dashboard=dashboard)

    assert Widget.objects.count() == 3

    assert [p.id for p in WidgetService().get_widgets(user, dashboard.id)] == [
        widget.id,
        widget_2.id,
        widget_3.id,
    ]

    def exclude_widget_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=widget.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_widget_1

        assert [p.id for p in WidgetService().get_widgets(user, dashboard.id)] == [
            widget_2.id,
            widget_3.id,
        ]


@pytest.mark.django_db
def test_get_widgets_initializes_a_widget_created_by_a_pre_grid_process(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    current_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Current"
    )
    legacy_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Legacy"
    )
    Widget.objects.filter(id=legacy_widget.id).update(
        grid_x=0,
        grid_y=0,
        grid_width=6,
        grid_height=9,
        grid_layout_initialized=False,
    )

    with patch(
        "baserow.contrib.dashboard.widgets.service.widgets_layout_updated.send"
    ) as widgets_layout_updated_mock:
        widgets = WidgetService().get_widgets(user, dashboard.id)

    assert [widget.id for widget in widgets] == [current_widget.id, legacy_widget.id]
    current_widget.refresh_from_db()
    legacy_widget.refresh_from_db()
    assert current_widget.grid_layout_initialized is True
    assert (
        legacy_widget.grid_x,
        legacy_widget.grid_y,
        legacy_widget.grid_width,
        legacy_widget.grid_height,
        legacy_widget.grid_layout_initialized,
    ) == (0, 4, 2, 4, True)
    widgets_layout_updated_mock.assert_called_once()
    _, kwargs = widgets_layout_updated_mock.call_args
    assert kwargs["user"] is None
    assert kwargs["dashboard"] == dashboard
    assert "widgets" not in kwargs


@pytest.mark.django_db
def test_get_widgets_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)

    with pytest.raises(DashboardDoesNotExist):
        WidgetService().get_widgets(user, dashboard.id)


@pytest.mark.django_db
def test_create_widget(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget_type = "summary"

    created_widget = WidgetService().create_widget(
        user, widget_type, dashboard.id, title="My widget", description="My description"
    )

    assert created_widget.title == "My widget"
    assert created_widget.description == "My description"
    assert created_widget.dashboard == dashboard
    assert created_widget.content_type == ContentType.objects.get_for_model(
        SummaryWidget
    )


@pytest.mark.django_db
def test_create_widget_places_widgets_in_first_available_positions(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)

    first_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="First"
    )
    second_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Second"
    )
    third_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Third"
    )

    assert (first_widget.grid_x, first_widget.grid_y) == (0, 0)
    assert (second_widget.grid_x, second_widget.grid_y) == (2, 0)
    assert (third_widget.grid_x, third_widget.grid_y) == (4, 0)


@pytest.mark.django_db
def test_create_widget_broadcasts_legacy_event_and_layout_invalidation(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)

    with (
        patch(
            "baserow.contrib.dashboard.widgets.service.widget_created.send"
        ) as widget_created_mock,
        patch(
            "baserow.contrib.dashboard.widgets.service.widgets_layout_updated.send"
        ) as widgets_layout_updated_mock,
    ):
        widget = WidgetService().create_widget(
            user, "summary", dashboard.id, title="Created"
        )

    widget_created_mock.assert_called_once_with(ANY, user=user, widget=widget)
    widgets_layout_updated_mock.assert_called_once_with(
        ANY, user=user, dashboard=dashboard
    )


@pytest.mark.django_db
def test_create_widget_permission_denied(data_fixture):
    user_without_perms = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application()
    widget_type = "summary"

    with pytest.raises(PermissionException):
        WidgetService().create_widget(
            user_without_perms,
            widget_type,
            dashboard.id,
            title="My widget",
            description="My description",
        )


@pytest.mark.django_db
def test_create_widget_widget_type_doesnt_exist(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget_type = "xxx"

    with pytest.raises(WidgetTypeDoesNotExist):
        WidgetService().create_widget(
            user,
            widget_type,
            dashboard.id,
            title="My widget",
            description="My description",
        )


@pytest.mark.django_db
def test_create_widget_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)
    widget_type = "summary"

    with pytest.raises(DashboardDoesNotExist):
        WidgetService().create_widget(
            user,
            widget_type,
            dashboard.id,
            title="My widget",
            description="My description",
        )


@pytest.mark.django_db
def test_create_widget_blank_title(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget_type = "summary"

    with pytest.raises(ValidationError):
        WidgetService().create_widget(user, widget_type, dashboard.id, title="")


@pytest.mark.django_db
def test_update_widget(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    dashboard_2 = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    updated_widget = WidgetService().update_widget(
        user,
        widget.id,
        title="Updated title",
        description="Updated description",
        dashboard=dashboard_2,
    )

    assert updated_widget.widget.title == "Updated title"
    assert updated_widget.widget.description == "Updated description"
    assert updated_widget.widget.dashboard == dashboard  # cannot change


@pytest.mark.django_db
def test_update_widget_permission_denied(data_fixture):
    user_without_perms = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    with pytest.raises(PermissionException):
        WidgetService().update_widget(user_without_perms, widget.id, title="New title")


@pytest.mark.django_db
def test_update_widget_no_title(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, title="Original title"
    )

    with pytest.raises(ValidationError):
        WidgetService().update_widget(user, widget.id, title=None)


@pytest.mark.django_db
def test_update_widget_blank_title(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, title="Original title"
    )

    with pytest.raises(ValidationError):
        WidgetService().update_widget(user, widget.id, title="")


@pytest.mark.django_db
def test_update_widget_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard, trashed=True)

    with pytest.raises(WidgetDoesNotExist):
        WidgetService().update_widget(
            user,
            widget.id,
            title="Updated title",
            description="Updated description",
        )


@pytest.mark.django_db
def test_update_widget_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    with pytest.raises(WidgetDoesNotExist):
        WidgetService().update_widget(
            user,
            widget.id,
            title="Updated title",
            description="Updated description",
        )


@pytest.mark.django_db
def test_update_visible_widget_layout_preserves_hidden_widgets(
    data_fixture, stub_check_permissions
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    visible_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Visible"
    )
    hidden_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Hidden"
    )
    hidden_updated_on = hidden_widget.updated_on

    def exclude_hidden_widget(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=hidden_widget.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_hidden_widget
        updated_layout = WidgetService().update_visible_widget_layout(
            user,
            dashboard.id,
            [
                {
                    "id": visible_widget.id,
                    "grid_x": 4,
                    "grid_y": 0,
                    "grid_width": 2,
                    "grid_height": 4,
                }
            ],
        )

    visible_widget.refresh_from_db()
    hidden_widget.refresh_from_db()
    assert (visible_widget.grid_x, visible_widget.grid_y) == (4, 0)
    assert (hidden_widget.grid_x, hidden_widget.grid_y) == (2, 0)
    assert hidden_widget.updated_on == hidden_updated_on
    assert [item["id"] for item in updated_layout.layout_delta.original_layout] == [
        visible_widget.id
    ]
    assert [item["id"] for item in updated_layout.layout_delta.new_layout] == [
        visible_widget.id
    ]


@pytest.mark.django_db
def test_update_visible_widget_layout_pushes_widget_below_hidden_collision(
    data_fixture, stub_check_permissions
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    visible_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Visible"
    )
    hidden_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Hidden"
    )

    def exclude_hidden_widget(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=hidden_widget.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_hidden_widget
        updated_layout = WidgetService().update_visible_widget_layout(
            user,
            dashboard.id,
            [
                {
                    "id": visible_widget.id,
                    "grid_x": 2,
                    "grid_y": 0,
                    "grid_width": 2,
                    "grid_height": 4,
                }
            ],
        )

    visible_widget.refresh_from_db()
    hidden_widget.refresh_from_db()
    assert (visible_widget.grid_x, visible_widget.grid_y) == (2, 4)
    assert (hidden_widget.grid_x, hidden_widget.grid_y) == (2, 0)
    assert updated_layout.visible_layout == [
        {
            "id": visible_widget.id,
            "grid_x": 2,
            "grid_y": 4,
            "grid_width": 2,
            "grid_height": 4,
        }
    ]


@pytest.mark.django_db
def test_update_visible_layout_compacts_around_hidden_obstacles(
    data_fixture, stub_check_permissions
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    hidden_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Hidden"
    )
    blocked_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Blocked"
    )
    free_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Free"
    )
    Widget.objects.filter(id=blocked_widget.id).update(grid_x=0, grid_y=4)
    Widget.objects.filter(id=free_widget.id).update(grid_x=2, grid_y=4)
    hidden_updated_on = hidden_widget.updated_on

    def exclude_hidden_widget(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=hidden_widget.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_hidden_widget
        updated_layout = WidgetService().update_visible_widget_layout(
            user,
            dashboard.id,
            [
                {
                    "id": blocked_widget.id,
                    "grid_x": 0,
                    "grid_y": 4,
                    "grid_width": 2,
                    "grid_height": 4,
                },
                {
                    "id": free_widget.id,
                    "grid_x": 2,
                    "grid_y": 4,
                    "grid_width": 2,
                    "grid_height": 4,
                },
            ],
        )

    hidden_widget.refresh_from_db()
    blocked_widget.refresh_from_db()
    free_widget.refresh_from_db()
    assert (hidden_widget.grid_x, hidden_widget.grid_y) == (0, 0)
    assert hidden_widget.updated_on == hidden_updated_on
    assert (blocked_widget.grid_x, blocked_widget.grid_y) == (0, 4)
    assert (free_widget.grid_x, free_widget.grid_y) == (2, 0)
    assert [(item["id"], item["grid_y"]) for item in updated_layout.visible_layout] == [
        (free_widget.id, 0),
        (blocked_widget.id, 4),
    ]
    assert [item["id"] for item in updated_layout.layout_delta.new_layout] == [
        free_widget.id
    ]


@pytest.mark.django_db
def test_delete_widget(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    WidgetService().delete_widget(user, widget.id)

    assert Widget.objects.count() == 0


@pytest.mark.django_db
def test_delete_widget_broadcasts_legacy_event_and_layout_invalidation(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    deleted_widget = data_fixture.create_summary_widget(dashboard=dashboard)
    data_fixture.create_summary_widget(dashboard=dashboard)

    with (
        patch(
            "baserow.contrib.dashboard.widgets.service.widget_deleted.send"
        ) as widget_deleted_mock,
        patch(
            "baserow.contrib.dashboard.widgets.service.widgets_layout_updated.send"
        ) as widgets_layout_updated_mock,
    ):
        WidgetService().delete_widget(user, deleted_widget.id)

    widget_deleted_mock.assert_called_once_with(ANY, user=user, widget=deleted_widget)
    widgets_layout_updated_mock.assert_called_once()
    _, kwargs = widgets_layout_updated_mock.call_args
    assert kwargs["dashboard"] == dashboard
    assert "widgets" not in kwargs


@pytest.mark.django_db
def test_restore_widget_broadcasts_legacy_event_and_layout_invalidation(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    restored_widget = data_fixture.create_summary_widget(dashboard=dashboard)
    remaining_widget = data_fixture.create_summary_widget(dashboard=dashboard)
    original_layout = [
        {
            "id": restored_widget.id,
            "grid_x": 0,
            "grid_y": 0,
            "grid_width": 2,
            "grid_height": 4,
        },
        {
            "id": remaining_widget.id,
            "grid_x": 2,
            "grid_y": 0,
            "grid_width": 2,
            "grid_height": 4,
        },
    ]
    WidgetService().delete_widget(user, restored_widget.id)

    with (
        patch(
            "baserow.contrib.dashboard.widgets.trash_types.widget_created.send"
        ) as widget_created_mock,
        patch(
            "baserow.contrib.dashboard.widgets.service.widgets_layout_updated.send"
        ) as widgets_layout_updated_mock,
    ):
        WidgetService().restore_widget_and_update_layout(
            user,
            dashboard.id,
            restored_widget.id,
            original_layout,
        )

    widget_created_mock.assert_called_once()
    _, created_kwargs = widget_created_mock.call_args
    assert created_kwargs["widget"].id == restored_widget.id
    widgets_layout_updated_mock.assert_called_once()
    _, kwargs = widgets_layout_updated_mock.call_args
    assert kwargs["dashboard"] == dashboard
    assert "widgets" not in kwargs


@pytest.mark.django_db
def test_restore_widget_legacy_keeps_the_standard_trash_restore_placement(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    restored_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Restored"
    )
    remaining_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Remaining"
    )
    remaining_widget.grid_y = 8
    remaining_widget.save(update_fields=["grid_y"])

    WidgetService().delete_widget_legacy(user, restored_widget.id)

    with patch(
        "baserow.contrib.dashboard.widgets.trash_types.widget_created.send"
    ) as widget_created_mock:
        WidgetService().restore_widget_legacy(user, restored_widget.id)

    restored_widget.refresh_from_db()
    assert restored_widget.grid_y == 12
    widget_created_mock.assert_called_once()


@pytest.mark.django_db
def test_delete_widget_compacts_legacy_widget_layout(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    remaining_widget = data_fixture.create_summary_widget(dashboard=dashboard)
    deleted_widget = data_fixture.create_summary_widget(dashboard=dashboard)
    Widget.objects.filter(id=remaining_widget.id).update(grid_height=9)
    Widget.objects.filter(id=deleted_widget.id).update(grid_y=12, grid_height=9)

    WidgetService().delete_widget(user, deleted_widget.id)

    remaining_widget.refresh_from_db()
    assert remaining_widget.grid_y == 0
    assert remaining_widget.grid_height == 9


@pytest.mark.django_db
def test_delete_widget_permission_denied(data_fixture):
    user_without_perms = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    with pytest.raises(PermissionException):
        WidgetService().delete_widget(user_without_perms, widget.id)


@pytest.mark.django_db
def test_delete_widget_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard, trashed=True)

    with pytest.raises(WidgetDoesNotExist):
        WidgetService().delete_widget(user, widget.id)


@pytest.mark.django_db
def test_delete_widget_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    with pytest.raises(WidgetDoesNotExist):
        WidgetService().delete_widget(user, widget.id)
