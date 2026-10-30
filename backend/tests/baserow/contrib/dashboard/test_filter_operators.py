from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

import pytest

from baserow.contrib.dashboard.api.filters.serializers import DashboardFilterSerializer
from baserow.contrib.dashboard.filters.operators import get_filter_operators
from baserow.contrib.database.views.registries import view_filter_type_registry


@pytest.mark.django_db
def test_dashboard_filter_schema_and_url_checks_do_not_query_the_database(
    django_db_blocker,
):
    ContentType.objects.clear_cache()

    with django_db_blocker.block():
        serializer = DashboardFilterSerializer()

        assert "equal" in serializer.fields["operator"].choices
        assert "higher_than" in serializer.fields["operator"].choices
        assert "date_is" in serializer.fields["operator"].choices
        assert "single_select_equal" not in serializer.fields["operator"].choices
        call_command("check")


@pytest.mark.django_db
@pytest.mark.parametrize("filter_type", ["text", "number", "date"])
def test_dashboard_filter_operators_match_builder_conditions(data_fixture, filter_type):
    field = getattr(data_fixture, f"create_{filter_type}_field")()

    expected = {
        operator.type
        for operator in view_filter_type_registry.get_all()
        if operator.field_is_compatible(field)
    }

    assert set(get_filter_operators(filter_type)) == expected
