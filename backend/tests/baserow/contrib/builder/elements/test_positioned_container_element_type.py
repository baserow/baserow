import json
from collections import defaultdict

import pytest

from baserow.contrib.builder.constants import PageAlignments, PageBehaviours
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import PositionedContainerElement
from baserow.core.utils import MirrorDict


@pytest.fixture
def positioned_container_fixture(data_fixture):
    """Fixture to help test the Menu element."""

    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, path="/page/")

    element = data_fixture.create_builder_positioned_container_element(
        user=user, page=page
    )

    return {
        "token": token,
        "page": page,
        "element": element,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "alignment,behaviour",
    [
        (PageAlignments.TOP, PageBehaviours.FIXED),
        (PageAlignments.BOTTOM, PageBehaviours.FIXED),
        (PageAlignments.TOP, PageBehaviours.STICKY),
        (PageAlignments.BOTTOM, PageBehaviours.STICKY),
    ],
)
def test_import_export(positioned_container_fixture, alignment, behaviour):
    page = positioned_container_fixture["page"]
    positioned_container_element = positioned_container_fixture["element"]

    positioned_container_element.alignment = alignment
    positioned_container_element.behaviour = behaviour
    positioned_container_element.save()

    element_type = positioned_container_element.get_type()

    # Export the Menu element and ensure there are no Menu elements
    # after deleting it.
    exported = element_type.export_serialized(positioned_container_element)
    assert json.dumps(exported)

    ElementHandler().delete_element(positioned_container_element)

    assert PositionedContainerElement.objects.count() == 0

    id_mapping = defaultdict(lambda: MirrorDict())
    element_type.import_serialized(page, exported, id_mapping)

    imported_element = PositionedContainerElement.objects.first()
    assert imported_element.alignment == alignment
    assert imported_element.behaviour == behaviour
