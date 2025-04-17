from unittest.mock import MagicMock

from django.db.models import Q

import pytest

from baserow.contrib.automation.object_scopes import AutomationObjectScopeType


@pytest.mark.django_db
def test_raises_if_scope_type_invalid():
    mock_scope = MagicMock()
    mock_scope.type = "foo"

    with pytest.raises(TypeError) as exc_info:
        AutomationObjectScopeType().get_filter_for_scope_type(mock_scope, [])

    assert str(exc_info.value) == "The given type is not handled."


@pytest.mark.django_db
def test_get_filter_for_scope_type():
    mock_scope = MagicMock()
    mock_scope.type = "automation"

    result = AutomationObjectScopeType().get_filter_for_scope_type(mock_scope, [])
    assert result == Q(id__in=[])
