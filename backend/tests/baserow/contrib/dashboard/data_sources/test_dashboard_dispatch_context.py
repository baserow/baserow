from django.http import HttpRequest

import pytest

from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)


@pytest.mark.django_db
def test_dispatch_context_clone(data_fixture):
    widget = data_fixture.create_summary_widget()
    request = HttpRequest()

    dispatch_context = DashboardDispatchContext(request, widget)
    dispatch_context.cache = {"key": "value"}

    new_dispatch_context = dispatch_context.clone()

    assert new_dispatch_context.request is request
    assert new_dispatch_context.widget == widget
    assert new_dispatch_context.cache == {"key": "value"}


@pytest.mark.django_db
def test_dispatch_context_clone_with_another_widget(data_fixture):
    widget = data_fixture.create_summary_widget()
    other_widget = data_fixture.create_summary_widget()

    dispatch_context = DashboardDispatchContext(HttpRequest(), widget)

    assert dispatch_context.clone(widget=other_widget).widget == other_widget


@pytest.mark.django_db
def test_dispatch_context_is_not_publicly_refinable(data_fixture):
    """The flags are read as attributes, so a plain method would read as True."""

    dispatch_context = DashboardDispatchContext(HttpRequest())

    assert dispatch_context.is_publicly_searchable is False
    assert dispatch_context.is_publicly_filterable is False
    assert dispatch_context.is_publicly_sortable is False
    assert dispatch_context.public_allowed_properties is None
