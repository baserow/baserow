import pytest
from django.core.validators import MinValueValidator, MaxValueValidator
from rest_framework.exceptions import ValidationError

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.elements.element_types import (
    RatingElementType,
    RatingInputElementType,
)
from baserow.contrib.builder.elements.models import (
    RatingElement,
    RatingInputElement,
    RatingStyles,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from collections import defaultdict
from baserow.core.utils import MirrorDict


@pytest.mark.django_db
def test_rating_element_type_export_import(data_fixture):
    page = data_fixture.create_builder_page()
    element = data_fixture.create_builder_element(
        RatingElement,
        page=page,
        value="4",
        max_value=5,
        color="#FF0000",
        style=RatingStyles.STAR,
    )

    exported = element_type_registry.get_by_model(element).export_serialized(element)

    assert exported["id"] == element.id
    assert exported["type"] == "rating"
    assert exported["value"] == "4"
    assert exported["max_value"] == 5
    assert exported["color"] == "#FF0000"
    assert exported["style"] == RatingStyles.STAR

    id_mapping = defaultdict(lambda: MirrorDict())
    imported = element_type_registry.get("rating").import_serialized(
        page, exported, id_mapping
    )

    assert imported.id != element.id
    assert imported.value == element.value
    assert imported.max_value == element.max_value
    assert imported.color == element.color
    assert imported.style == element.style
