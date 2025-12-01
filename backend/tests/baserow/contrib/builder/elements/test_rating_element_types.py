from collections import defaultdict

import pytest

from baserow.contrib.builder.elements.models import RatingElement, RatingStyleChoices
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.core.utils import MirrorDict


@pytest.mark.django_db
def test_rating_element_type_export_import(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_element(
        RatingElement,
        page=page,
        value="'4'",
        max_value=5,
        color="#FF0000",
        rating_style=RatingStyleChoices.STAR,
    )

    exported = element_type_registry.get_by_model(element).export_serialized(element)

    assert exported["id"] == element.id
    assert exported["type"] == "rating"
    assert exported["value"] == BaserowFormulaObject(
        formula="'4'",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version=BASEROW_FORMULA_VERSION_INITIAL,
    )
    assert exported["max_value"] == 5
    assert exported["color"] == "#FF0000"
    assert exported["rating_style"] == RatingStyleChoices.STAR

    id_mapping = defaultdict(lambda: MirrorDict())
    imported = element_type_registry.get("rating").import_serialized(
        page, exported, id_mapping
    )

    assert imported.id != element.id
    assert imported.value == element.value
    assert imported.max_value == element.max_value
    assert imported.color == element.color
    assert imported.rating_style == element.rating_style
