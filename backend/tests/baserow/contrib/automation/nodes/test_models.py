from django.contrib.contenttypes.models import ContentType

import pytest

from baserow.contrib.automation.nodes.models import get_default_node_content_type


@pytest.mark.django_db
def test_automation_node_get_parent(data_fixture):
    node = data_fixture.create_automation_node()

    result = node.get_parent()

    assert result == node.workflow


@pytest.mark.django_db
def test_get_default_node_content_type(data_fixture):
    result = get_default_node_content_type()
    node = data_fixture.create_automation_node()

    assert isinstance(result, ContentType)
    assert isinstance(node.content_type, ContentType)
