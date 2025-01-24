import pytest

from baserow.contrib.builder.elements.element_types import (
    FooterElementType,
    HeaderElementType,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import element_type_registry


def test_header_footer_child_types_allowed():
    assert sorted([e.type for e in HeaderElementType().child_types_allowed]) == sorted(
        [
            element_type.type
            for element_type in element_type_registry.get_all()
            if not element_type.is_multi_page_element
        ]
    )

    assert sorted([e.type for e in FooterElementType().child_types_allowed]) == sorted(
        [
            element_type.type
            for element_type in element_type_registry.get_all()
            if not element_type.is_multi_page_element
        ]
    )


# Test prepare value
@pytest.mark.django_db
@pytest.mark.parametrize(
    "element_type", [HeaderElementType.type, FooterElementType.type]
)
def test_header_footer_prepare_value_for_db(data_fixture, element_type):
    page = data_fixture.create_builder_page()
    page1 = data_fixture.create_builder_page(builder=page.builder)
    page2 = data_fixture.create_builder_page(builder=page.builder)
    page3 = data_fixture.create_builder_page(builder=page.builder)
    page4 = data_fixture.create_builder_page()
    shared_page = page.builder.shared_page

    element_type = element_type_registry.get(element_type)

    created_element = ElementHandler().create_element(
        element_type,
        page=shared_page,
        share_type="only",
        pages=[page1, page2, page4, shared_page],
    )

    assert sorted([p.id for p in created_element.pages.all()]) == sorted(
        [page1.id, page2.id]
    )

    updated_element = ElementHandler().update_element(
        created_element,
        pages=[page1, page4, shared_page],
    )

    assert sorted([p.id for p in updated_element.pages.all()]) == sorted([page1.id])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "element_type", [HeaderElementType.type, FooterElementType.type]
)
def test_header_footer_import_with_id_mapping(data_fixture, element_type):
    page = data_fixture.create_builder_page()
    page42 = data_fixture.create_builder_page()
    page43 = data_fixture.create_builder_page()

    SERIALIZED_HEADER = {
        "id": 42,
        "type": element_type,
        "share_type": "only",
        "parent_element_id": None,
        "pages": [42, 43],
    }

    cache = {}
    id_mapping = {"builder_pages": {42: page42, 43: page43}}

    created_element = ElementHandler().import_element(
        page,
        SERIALIZED_HEADER,
        id_mapping,
        cache=cache,
    )

    # We keep only the pages that are in the same builder
    assert sorted([p.id for p in created_element.pages.all()]) == sorted(
        [page42.id, page43.id]
    )
