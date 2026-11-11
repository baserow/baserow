import pytest

from baserow.contrib.builder.elements.element_types import ChoiceElementType
from baserow.contrib.builder.elements.models import ChoiceElement
from baserow.contrib.builder.pages.handler import PageHandler


@pytest.mark.django_db
def test_choice_search_model_default(data_fixture):
    page = data_fixture.create_builder_page()

    element = ChoiceElement.objects.create(page=page)

    element.refresh_from_db()
    assert element.show_search is False


@pytest.mark.django_db
@pytest.mark.parametrize("show_search", [False, True])
def test_choice_search_import_export(data_fixture, show_search):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_choice_element(
        page=page, show_search=show_search
    )
    element.choiceelementoption_set.create(name="United Kingdom", value="uk")

    serialized = ChoiceElementType().export_serialized(element)
    assert serialized["show_search"] is show_search

    [imported] = PageHandler().import_elements(page, [serialized], {})

    assert imported.id != element.id
    assert imported.show_search is show_search
    assert imported.choiceelementoption_set.get().value == "uk"


@pytest.mark.django_db
def test_choice_search_legacy_import_defaults_to_disabled(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_choice_element(page=page, show_search=True)
    serialized = ChoiceElementType().export_serialized(element)
    serialized.pop("show_search")

    [imported] = PageHandler().import_elements(page, [serialized], {})

    assert imported.show_search is False
