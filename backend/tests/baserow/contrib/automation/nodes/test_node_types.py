import pytest

from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowCreateRowNodeType,
    service_backed_automation_nodes,
)


@pytest.mark.django_db
def test_service_backed_automation_nodes():
    result = service_backed_automation_nodes()

    assert isinstance(result[0], LocalBaserowCreateRowNodeType)
