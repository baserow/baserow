from unittest.mock import MagicMock

import pytest

from baserow.contrib.automation.workflows.object_scopes import (
    AutomationWorkflowObjectScopeType,
)


@pytest.mark.django_db
def test_raises_if_scope_type_invalid():
    mock_scope = MagicMock()
    mock_scope.type = "foo"

    with pytest.raises(TypeError) as exc_info:
        AutomationWorkflowObjectScopeType().get_filter_for_scope_type(mock_scope, [])

    assert str(exc_info.value) == "The given type is not handled."
