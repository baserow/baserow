from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

import pytest

from baserow.contrib.dashboard.exceptions import DashboardDoesNotExist
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
def test_delete_widget(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    WidgetService().delete_widget(user, widget.id)

    assert Widget.objects.count() == 0


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
