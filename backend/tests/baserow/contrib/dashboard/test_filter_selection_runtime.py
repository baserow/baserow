from types import SimpleNamespace
from unittest.mock import patch

from django.db import models
from django.db.models import Q

import pytest

from baserow.contrib.dashboard.data_providers import DashboardFilterDataProviderType
from baserow.contrib.dashboard.filters.operators import get_filter_operators
from baserow.contrib.dashboard.filters.runtime import get_dashboard_filter_q
from baserow.contrib.dashboard.filters.values import MAX_SELECTION_VALUES
from baserow.contrib.database.fields.models import TextField
from baserow.core.formula.types import BaserowFormulaObject


@pytest.mark.parametrize("operator", ["equal", "not_equal"])
@pytest.mark.parametrize(
    "suffix,values,expected_values",
    [
        ("", ["A"] * MAX_SELECTION_VALUES, ["A"]),
        ("", ["A", "A", "B", "", " "], ["A", "B"]),
        (".*", ["A", "A", "B"], ["A", "B"]),
        (".0", ["A", "A", "B"], ["A"]),
        (".1", ["A", "A", "B"], ["A"]),
        (".2", ["A", "A", "B"], ["B"]),
        ("", ["", " "], []),
        ("", [], []),
    ],
)
def test_resolved_selection_terms_are_unique_without_changing_provider_indexes(
    operator, suffix, values, expected_values
):
    field = TextField(id=1)
    field.specific_class = TextField
    model_field = models.TextField()
    model = SimpleNamespace(
        _field_objects={1: {"field": field, "name": "field_1"}},
        _meta=SimpleNamespace(get_field=lambda name: model_field),
    )
    condition = SimpleNamespace(
        field_id=1,
        value=BaserowFormulaObject.create(f"get('dashboard_filter.1{suffix}')"),
    )
    configuration = SimpleNamespace(
        type="text", operator=operator, mode="dropdown", multiple=True, values=values
    )
    context = SimpleNamespace(
        dashboard=SimpleNamespace(id=1),
        cache={("dashboard_filters", 1): {"1": configuration}},
    )
    filter_type = get_filter_operators("text")[operator]
    with patch.object(
        filter_type, "get_filter", wraps=filter_type.get_filter
    ) as get_filter:
        result = get_dashboard_filter_q(condition, model, context)
    assert [call.args[1] for call in get_filter.call_args_list] == expected_values
    assert DashboardFilterDataProviderType().get_data_chunk(context, ["1"]) == values
    expected_query = Q()
    for value in expected_values:
        if operator == "equal":
            expected_query |= Q(field_1=value)
        else:
            expected_query &= ~Q(field_1=value)
    assert (result.q if expected_values else result) == expected_query
