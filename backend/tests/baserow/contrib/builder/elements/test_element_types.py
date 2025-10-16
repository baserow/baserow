import json
from collections import defaultdict
from io import BytesIO
from tempfile import tempdir
from unittest.mock import MagicMock, Mock
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import FileSystemStorage
from django.http import HttpRequest

import pytest
import zipstream
from rest_framework.exceptions import ValidationError

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.elements.element_types import (
    ButtonElementType,
    CheckboxElementType,
    ChoiceElementType,
    ColumnElementType,
    DateTimePickerElementType,
    FormContainerElementType,
    HeadingElementType,
    IFrameElementType,
    ImageElementType,
    InputTextElementType,
    LinkElementType,
    RecordSelectorElementType,
    TextElementType,
    collection_element_types,
)
from baserow.contrib.builder.elements.exceptions import ElementImproperlyConfigured
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.mixins import (
    ContainerElementTypeMixin,
    FormElementTypeMixin,
)
from baserow.contrib.builder.elements.models import (
    ButtonElement,
    CheckboxElement,
    ChoiceElement,
    ChoiceElementOption,
    CollectionField,
    DateTimePickerElement,
    Element,
    FormContainerElement,
    HeadingElement,
    IFrameElement,
    ImageElement,
    InputTextElement,
    LinkElement,
    RatingInputElement,
    RecordSelectorElement,
    TableElement,
    TextElement,
)
from baserow.contrib.builder.elements.registries import (
    ElementType,
    element_type_registry,
)
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.pages.service import PageService
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import ExportZipFile
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_sources.registries import DEFAULT_USER_ROLE_PREFIX
from baserow.core.utils import MirrorDict


def pytest_generate_tests(metafunc):
    if "element_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "element_type",
            [pytest.param(e, id=e.type) for e in element_type_registry.get_all()],
        )


@pytest.mark.django_db
def test_export_element(data_fixture, element_type: ElementType):
    page = data_fixture.create_builder_page()
    pytest_params = element_type.get_pytest_params(data_fixture)
    element = data_fixture.create_builder_element(
        element_type.model_class, page=page, order=17, **pytest_params
    )

    exported = element_type.export_serialized(element)

    assert exported["id"] == element.id
    assert exported["type"] == element_type.type
    assert exported["order"] == str(element.order)

    for key, value in pytest_params.items():
        assert exported[key] == value


@pytest.mark.django_db
def test_import_element(data_fixture, element_type: ElementType):
    page = data_fixture.create_builder_page()
    pytest_params = element_type.get_pytest_params(data_fixture)

    serialized = {
        "id": 9999,
        "order": 42,
        "type": element_type.type,
        "parent_element_id": None,
        "roles": [],
        "role_type": Element.ROLE_TYPES.ALLOW_ALL,
    }
    serialized.update(element_type.get_pytest_params(data_fixture))

    id_mapping = defaultdict(lambda: MirrorDict())
    element = element_type.import_serialized(page, serialized, id_mapping)

    assert element.id != 9999
    assert element.order == element.order
    assert isinstance(element, element_type.model_class)

    for key, value in pytest_params.items():
        assert getattr(element, key) == value


@pytest.mark.django_db
def test_link_element_path_parameter_does_not_exist(data_fixture):
    builder = data_fixture.create_builder_application()
    page = data_fixture.create_builder_page(builder=builder)
    page_with_params = data_fixture.create_builder_page(
        builder=builder,
        path="/test/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )

    link_element = data_fixture.create_builder_link_element(
        page=page,
        navigation_type=LinkElement.NAVIGATION_TYPES.PAGE,
        navigate_to_page=page_with_params,
    )

    with pytest.raises(ValidationError):
        ElementHandler().update_element(
            link_element, page_parameters=[{"name": "invalid", "value": "something"}]
        )


@pytest.mark.django_db
def test_link_element_path_parameter_does_not_exist_new_page(data_fixture):
    builder = data_fixture.create_builder_application()
    page = data_fixture.create_builder_page(builder=builder)
    page_with_params = data_fixture.create_builder_page(
        builder=builder,
        path="/test/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )

    link_element = data_fixture.create_builder_link_element(
        page=page,
    )

    with pytest.raises(ValidationError):
        ElementHandler().update_element(
            link_element,
            navigation_type=LinkElement.NAVIGATION_TYPES.PAGE,
            navigate_to_page_id=page_with_params.id,
            page_parameters=[{"name": "invalid", "value": "something"}],
        )


@pytest.mark.django_db
def test_link_collection_field_import_export_formula(data_fixture):
    """
    Test the import/export of the Link CollectionField.
    """

    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()

    table_element = TableElement.objects.create(
        order=1,
        page=page,
        items_per_page=5,
        content_type=ContentType.objects.get_for_model(TableElement),
    )
    field = CollectionField.objects.create(
        order=1,
        name="test1",
        type="link",
        config={
            "link_name": f"get('data_source.{data_source_1.id}.field_1')",
            "navigate_to_url": f"get('data_source.{data_source_1.id}.field_1')",
            "navigation_type": "",
            "navigate_to_page_id": "",
            "page_parameters": [
                {
                    "name": "fooPageParam",
                    "value": f"get('data_source.{data_source_1.id}.field_1')",
                },
            ],
            "query_parameters": [
                {
                    "name": "fooQueryParam",
                    "value": f"get('data_source.{data_source_1.id}.field_2')",
                },
            ],
            "target": "",
            "variant": LinkElement.VARIANTS.BUTTON,
        },
    )
    table_element.fields.add(field)

    field_type = table_element.get_type()
    serialized = field_type.export_serialized(table_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}

    imported_element = field_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    expected_query_formula = f"get('data_source.{data_source_2.id}.field_2')"
    imported_field = imported_element.fields.all()[0]
    assert imported_field.config["link_name"]["formula"] == expected_formula
    assert imported_field.config["navigate_to_url"]["formula"] == expected_formula
    assert (
        imported_field.config["page_parameters"][0]["value"]["formula"]
        == expected_formula
    )
    assert (
        imported_field.config["query_parameters"][0]["value"]["formula"]
        == expected_query_formula
    )


@pytest.mark.django_db
def test_link_element_import_export_formula(data_fixture):
    """Test the import/export of the LinkElement."""

    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = LinkElementType()

    exported_element = data_fixture.create_builder_element(
        LinkElement,
        navigate_to_url=f"get('data_source.{data_source_1.id}.field_1')",
        value=f"get('data_source.{data_source_1.id}.field_1')",
        page_parameters=[
            {
                "name": "fooPageParam",
                "value": f"get('data_source.{data_source_1.id}.field_1')",
            },
        ],
        query_parameters=[
            {
                "name": "fooQueryParam",
                "value": f"get('data_source.{data_source_1.id}.field_2')",
            },
        ],
    )
    serialized = element_type.export_serialized(exported_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    expected_query_formula = f"get('data_source.{data_source_2.id}.field_2')"
    assert imported_element.navigate_to_url["formula"] == expected_formula
    assert imported_element.value["formula"] == expected_formula
    assert imported_element.page_parameters[0]["value"]["formula"] == expected_formula
    assert (
        imported_element.query_parameters[0]["value"]["formula"]
        == expected_query_formula
    )


@pytest.mark.django_db
def test_form_container_element_import_export_formula(data_fixture):
    """Test the import/export of the FormContainerElement."""

    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = FormContainerElementType()

    exported_element = data_fixture.create_builder_element(
        FormContainerElement,
        submit_button_label=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = element_type.export_serialized(exported_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.submit_button_label["formula"] == expected_formula


@pytest.mark.parametrize(
    "allowed_element_type",
    [
        element_type.type
        for element_type in element_type_registry.get_all()
        if element_type.type != FormContainerElementType.type
        and not element_type.is_multi_page_element
    ],
)
def test_form_container_child_types_allowed(allowed_element_type):
    assert allowed_element_type in [
        e.type for e in FormContainerElementType().child_types_allowed
    ]


@pytest.mark.django_db
def test_text_element_import_export_formula(data_fixture):
    """Test the import/export of the TextElementType."""

    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = TextElementType()

    exported_text_element = data_fixture.create_builder_element(
        TextElement,
        value=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = element_type.export_serialized(exported_text_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.value["formula"] == expected_formula


@pytest.mark.django_db
def test_input_text_element_import_export_formula(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = InputTextElementType()

    exported_input_text_element = data_fixture.create_builder_element(
        InputTextElement,
        label=f"get('data_source.{data_source_1.id}.field_1')",
        default_value=f"get('data_source.{data_source_1.id}.field_1')",
        placeholder=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = element_type.export_serialized(exported_input_text_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.label["formula"] == expected_formula
    assert imported_element.default_value["formula"] == expected_formula
    assert imported_element.placeholder["formula"] == expected_formula


@pytest.mark.django_db
def test_image_element_import_export_formula(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = ImageElementType()

    exported_image_element = data_fixture.create_builder_element(
        ImageElement,
        image_url=f"get('data_source.{data_source_1.id}.field_1')",
        alt_text=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = element_type.export_serialized(exported_image_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.image_url["formula"] == expected_formula
    assert imported_element.alt_text["formula"] == expected_formula


@pytest.mark.django_db
def test_button_element_import_export_formula(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = ButtonElementType()

    exported_image_element = data_fixture.create_builder_element(
        ButtonElement,
        value=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = element_type.export_serialized(exported_image_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.value["formula"] == expected_formula


def test_rating_input_element_type_is_valid_with_valid_value():
    # Setup
    element_type = element_type_registry.get("rating_input")
    element = MagicMock(spec=RatingInputElement)
    element.required = False
    element.max_value = 5
    dispatch_context = MagicMock()

    # Test with valid values
    assert element_type.is_valid(element, 0, dispatch_context) == 0
    assert element_type.is_valid(element, 3, dispatch_context) == 3
    assert element_type.is_valid(element, 5, dispatch_context) == 5


def test_rating_input_element_type_is_valid_with_required_element():
    # Setup
    element_type = element_type_registry.get("rating_input")
    element = MagicMock(spec=RatingInputElement)
    element.required = True
    element.max_value = 5
    dispatch_context = MagicMock()

    # Test with valid value
    assert element_type.is_valid(element, 3, dispatch_context) == 3

    # Test with None value (should raise exception)
    with pytest.raises(ValueError) as excinfo:
        element_type.is_valid(element, None, dispatch_context)
    assert "The value is required" in str(excinfo.value)


def test_rating_input_element_type_is_valid_with_out_of_range_values():
    # Setup
    element_type = element_type_registry.get("rating_input")
    element = MagicMock(spec=RatingInputElement)
    element.required = False
    element.max_value = 5
    dispatch_context = MagicMock()

    # Test with values outside the valid range
    for invalid_value in [-1, 6, 10]:
        with pytest.raises(ValueError) as excinfo:
            element_type.is_valid(element, invalid_value, dispatch_context)
        assert "The value is required" in str(excinfo.value)


def test_rating_input_element_type_is_valid_edge_cases():
    # Setup
    element_type = element_type_registry.get("rating_input")
    element = MagicMock(spec=RatingInputElement)
    element.required = False
    element.max_value = 5
    dispatch_context = MagicMock()

    # Test with None value for non-required element
    # This should pass since the element is not required
    assert element_type.is_valid(element, None, dispatch_context) is None

    # Test with boundary values
    assert element_type.is_valid(element, 0, dispatch_context) == 0
    assert element_type.is_valid(element, 5, dispatch_context) == 5


@pytest.mark.django_db
def test_choice_element_import_export_formula(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = ChoiceElementType()

    exported_choice_element = data_fixture.create_builder_element(
        ChoiceElement,
        label=f"get('data_source.{data_source_1.id}.field_1')",
        default_value=f"get('data_source.{data_source_1.id}.field_1')",
        placeholder=f"get('data_source.{data_source_1.id}.field_1')",
        formula_name=f"get('data_source.{data_source_1.id}.field_1')",
        formula_value=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = element_type.export_serialized(exported_choice_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.label["formula"] == expected_formula
    assert imported_element.default_value["formula"] == expected_formula
    assert imported_element.placeholder["formula"] == expected_formula
    assert imported_element.formula_name["formula"] == expected_formula
    assert imported_element.formula_value["formula"] == expected_formula


@pytest.mark.django_db
@pytest.mark.parametrize(
    "required,type,value,result",
    [
        (True, "integer", "", ValueError),
        (True, "integer", 42, 42),
        (True, "integer", "4.2", 4.2),
        (True, "integer", "4,2", TypeError),
        (True, "integer", "42", 42),
        (True, "integer", "horse", TypeError),
        (False, "integer", "", ""),
        (True, "email", "foo@bar.com", "foo@bar.com"),
        (True, "email", "foobar.com", ValueError),
        (False, "email", "", ""),
        (True, "any", "", ValueError),
        (True, "any", 42, 42),
        (True, "any", "42", "42"),
        (True, "any", "horse", "horse"),
        (False, "any", "", ""),
    ],
)
def test_input_text_element_is_valid(data_fixture, required, type, value, result):
    if result not in [TypeError, ValueError]:
        assert (
            InputTextElementType().is_valid(
                InputTextElement(validation_type=type, required=required),
                value,
                {},
            )
            == result
        ), repr(f"{value} != {result}")
    else:
        with pytest.raises(result):
            InputTextElementType().is_valid(
                InputTextElement(validation_type=type, required=required),
                value,
                {},
            )


@pytest.mark.django_db
def test_choice_element_import_serialized(data_fixture):
    parent = data_fixture.create_builder_page()
    choice_element = data_fixture.create_builder_choice_element(
        page=parent, label="'test'"
    )
    ChoiceElementOption.objects.create(
        choice=choice_element, value="hello", name="there"
    )
    serialized_values = ChoiceElementType().export_serialized(choice_element)
    id_mapping = {}

    choice_element_imported = ChoiceElementType().import_serialized(
        parent, serialized_values, id_mapping
    )

    assert choice_element.id != choice_element_imported.id
    assert choice_element.label == choice_element_imported.label

    options = choice_element_imported.choiceelementoption_set.all()

    assert ChoiceElementOption.objects.count() == 2
    assert len(options) == 1
    assert options[0].value == "hello"
    assert options[0].name == "there"
    assert options[0].choice_id == choice_element_imported.id


@pytest.mark.django_db
def test_choice_element_is_valid(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    choice = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("choice"),
        page=page,
    )
    choice.choiceelementoption_set.create(value="uk", name="United Kingdom")
    choice.choiceelementoption_set.create(value="it", name="Italy")

    choice.required = True

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, "", {})

    assert ChoiceElementType().is_valid(choice, "uk", {}) == "uk"

    choice.multiple = True

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, [], {})

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, [""], {})

    assert ChoiceElementType().is_valid(choice, ["uk"], {}) == ["uk"]
    assert ChoiceElementType().is_valid(choice, "uk", {}) == ["uk"]
    assert ChoiceElementType().is_valid(choice, ["uk", "it"], {}) == ["uk", "it"]
    assert ChoiceElementType().is_valid(choice, "uk,it", {}) == ["uk", "it"]

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, ["uk", "it", "pt"], {})

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, "uk,it,pt", {})

    choice.multiple = False
    choice.required = False

    assert ChoiceElementType().is_valid(choice, "", {}) == ""
    assert ChoiceElementType().is_valid(choice, "uk", {}) == "uk"

    choice.multiple = True

    assert ChoiceElementType().is_valid(choice, [], {}) == []
    assert ChoiceElementType().is_valid(choice, "", {}) == []

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, [""], {})

    assert ChoiceElementType().is_valid(choice, ["uk"], {}) == ["uk"]
    assert ChoiceElementType().is_valid(choice, ["uk", "it"], {}) == ["uk", "it"]
    assert ChoiceElementType().is_valid(choice, "uk,it", {}) == ["uk", "it"]

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, ["uk", "it", "pt"], {})

    choice.choiceelementoption_set.create(value="", name="Blank")
    choice.multiple = False
    choice.required = True

    assert ChoiceElementType().is_valid(choice, "", {}) == ""

    choice.multiple = True
    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, [], {})
    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, "", {})

    assert ChoiceElementType().is_valid(choice, [""], {}) == [""]
    assert ChoiceElementType().is_valid(choice, ["uk"], {}) == ["uk"]
    assert ChoiceElementType().is_valid(choice, "uk", {}) == ["uk"]
    assert ChoiceElementType().is_valid(choice, ["uk", "it"], {}) == ["uk", "it"]
    assert ChoiceElementType().is_valid(choice, "uk,it", {}) == ["uk", "it"]
    assert ChoiceElementType().is_valid(choice, ["uk", "it", ""], {}) == [
        "uk",
        "it",
        "",
    ]

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, ["uk", "it", "", "pt"], {})

    choice.multiple = False
    choice.required = False

    assert ChoiceElementType().is_valid(choice, "uk", {}) == "uk"

    choice.multiple = True

    assert ChoiceElementType().is_valid(choice, [], {}) == []
    assert ChoiceElementType().is_valid(choice, [""], {}) == [""]
    assert ChoiceElementType().is_valid(choice, ["uk"], {}) == ["uk"]
    assert ChoiceElementType().is_valid(choice, ["uk", "it"], {}) == ["uk", "it"]
    assert ChoiceElementType().is_valid(choice, ["uk", "it", ""], {}) == [
        "uk",
        "it",
        "",
    ]

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, ["uk", "it", "", "pt"], {})


@pytest.mark.django_db
def test_choice_element_is_valid_formula_data_source(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["BMW"], ["Audi"], ["Seat"], ["Volvo"]],
    )
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )
    choice = ElementService().create_element(
        page=page,
        user=user,
        element_type=element_type_registry.get("choice"),
        option_type=ChoiceElement.OPTION_TYPE.FORMULAS,
        formula_value=f"get('data_source.{data_source.id}.*.{fields[0].db_column}')",
    )

    # Call is_valid with an option that is not present in the list raises an exception
    dispatch_context = BuilderDispatchContext(
        HttpRequest(),
        page,
        offset=0,
        count=20,
        only_expose_public_allowed_properties=False,
    )

    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, "Invalid", dispatch_context)

    # Call is_valid with a valid option simply returns its value
    dispatch_context = BuilderDispatchContext(
        HttpRequest(),
        page,
        offset=0,
        count=20,
        only_expose_public_allowed_properties=False,
    )

    assert ChoiceElementType().is_valid(choice, "BMW", dispatch_context) == "BMW"


@pytest.mark.django_db
def test_choice_element_is_valid_formula_context(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(user=user, columns=[], rows=[])
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="single_select",
        name="Country",
        select_options=[
            {"value": "Germany", "color": "white"},
            {"value": "Spain", "color": "red"},
            {"value": "Sweden", "color": "yellow"},
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )
    choice = ElementService().create_element(
        page=page,
        user=user,
        element_type=element_type_registry.get("choice"),
        option_type=ChoiceElement.OPTION_TYPE.FORMULAS,
        formula_value=f"get('data_source_context.{data_source.id}.{field.db_column}.*.value')",
    )

    # Call is_valid with an option that is not present in the list raises an exception
    dispatch_context = BuilderDispatchContext(HttpRequest(), page, offset=0, count=20)
    with pytest.raises(ValueError):
        ChoiceElementType().is_valid(choice, "Invalid", dispatch_context)

    # Call is_valid with a valid option simply returns its value
    assert (
        ChoiceElementType().is_valid(choice, "Germany", dispatch_context) == "Germany"
    )


def test_element_type_import_element_priority():
    element_types = element_type_registry.get_all()
    container_element_types = [
        element_type
        for element_type in element_types
        if isinstance(element_type, ContainerElementTypeMixin)
    ]
    form_element_types = [
        element_type
        for element_type in element_types
        if isinstance(element_type, FormElementTypeMixin)
    ]
    other_element_types = [
        element_type
        for element_type in element_types
        if not isinstance(element_type, ContainerElementTypeMixin)
        and not isinstance(element_type, FormElementTypeMixin)
    ]
    manual_ordering = container_element_types + form_element_types + other_element_types
    expected_ordering = sorted(
        element_types,
        key=lambda element_type: element_type.import_element_priority,
        reverse=True,
    )
    assert manual_ordering == expected_ordering, (
        "The element types ordering are expected to be: "
        "containers first, then form elements, then everything else."
    )


@pytest.mark.django_db
def test_page_with_element_using_form_data_has_dependencies_import_first(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    form_container = data_fixture.create_builder_form_container_element(page=page)
    form_input = data_fixture.create_builder_input_text_element(
        page=page, parent_element=form_container
    )
    data_fixture.create_builder_heading_element(
        page=page, value=f"get('form_data.{form_input.id}')"
    )

    page_clone = PageService().duplicate_page(user, page)

    form_input_clone = InputTextElement.objects.get(page=page_clone)
    heading_clone = HeadingElement.objects.get(page=page_clone)
    assert heading_clone.value["formula"] == f"get('form_data.{form_input_clone.id}')"


@pytest.mark.django_db
def test_checkbox_element_import_export_formula(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = CheckboxElementType()

    exported_input_element = data_fixture.create_builder_element(
        CheckboxElement,
        label=f"get('data_source.{data_source_1.id}.field_1')",
        default_value=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = element_type.export_serialized(exported_input_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.label["formula"] == expected_formula
    assert imported_element.default_value["formula"] == expected_formula


@pytest.mark.django_db
def test_checkbox_text_element_is_valid(data_fixture):
    with pytest.raises(ValueError):
        CheckboxElementType().is_valid(CheckboxElement(required=True), False, {})

    with pytest.raises(ValueError):
        CheckboxElementType().is_valid(CheckboxElement(required=True), 0, {})

    assert (
        CheckboxElementType().is_valid(CheckboxElement(required=True), True, {}) is True
    )

    assert CheckboxElementType().is_valid(CheckboxElement(required=True), 1, {}) is True
    assert (
        CheckboxElementType().is_valid(CheckboxElement(required=True), "true", {})
        is True
    )
    assert (
        CheckboxElementType().is_valid(CheckboxElement(required=False), False, {})
        is False
    )
    assert (
        CheckboxElementType().is_valid(CheckboxElement(required=False), "false", {})
        is False
    )
    assert (
        CheckboxElementType().is_valid(CheckboxElement(required=False), 0, {}) is False
    )
    assert (
        CheckboxElementType().is_valid(CheckboxElement(required=False), True, {})
        is True
    )


@pytest.mark.django_db
def test_iframe_element_import_export_formula(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = IFrameElementType()

    exported_element = data_fixture.create_builder_element(
        IFrameElement,
        url=f"get('data_source.{data_source_1.id}.field_1')",
        embed=f"get('data_source.{data_source_1.id}.field_1')",
    )
    serialized = element_type.export_serialized(exported_element)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.url["formula"] == expected_formula
    assert imported_element.embed["formula"] == expected_formula


@pytest.mark.django_db
@pytest.mark.parametrize(
    "storage",
    [None, FileSystemStorage(location=str(tempdir), base_url="http://localhost")],
)
def test_image_element_import_export(data_fixture, fake, storage):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = ImageElementType()

    zip_buffer = BytesIO()
    image_file = UserFileHandler().upload_user_file(
        user, "test.jpg", BytesIO(fake.image()), storage=storage
    )

    element_to_export = data_fixture.create_builder_element(
        ImageElement,
        image_source_type="upload",
        image_file=image_file,
        image_url=f"get('data_source.{data_source_1.id}.field_1')",
    )

    zip_file = ExportZipFile(
        compress_level=settings.BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
        compress_type=zipstream.ZIP_DEFLATED,
    )

    serialized = element_type.export_serialized(
        element_to_export, files_zip=zip_file, storage=storage
    )

    for chunk in zip_file:
        zip_buffer.write(chunk)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}

    # Let check if the file is actually imported from the zip_file
    image_file.delete()

    with ZipFile(zip_buffer, "r", ZIP_DEFLATED, False) as files_zip:
        imported_element = element_type.import_serialized(
            page, serialized, id_mapping, files_zip=files_zip, storage=storage
        )

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.image_url["formula"] == expected_formula
    assert (
        imported_element.image_file_id is not None
        and imported_element.image_file_id != element_to_export.image_file_id
    )


@pytest.mark.django_db
def test_choice_element_import_export(data_fixture):
    page = data_fixture.create_builder_page()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = ChoiceElementType()

    exported_element = data_fixture.create_builder_element(
        ChoiceElement,
        label=f"get('data_source.42.field_1')",
        default_value=f"get('data_source.42.field_1')",
        placeholder=f"get('data_source.42.field_1')",
        multiple=True,
    )
    serialized = element_type.export_serialized(exported_element)

    # Just check that the serialization works properly
    json.dumps(serialized)

    # After applying the ID mapping the imported formula should have updated
    # the data source IDs
    id_mapping = {"builder_data_sources": {42: data_source_2.id}}

    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    expected_formula = f"get('data_source.{data_source_2.id}.field_1')"
    assert imported_element.label["formula"] == expected_formula
    assert imported_element.default_value["formula"] == expected_formula
    assert imported_element.placeholder["formula"] == expected_formula

    assert imported_element.multiple is True


@pytest.mark.django_db
def test_choice_element_import_old_format(data_fixture):
    page = data_fixture.create_builder_page()
    element_type = ChoiceElementType()

    serialized = {
        "id": 1,
        "order": "1.00000000000000000000",
        "type": "dropdown",  # Element type is the old one
        "parent_element_id": None,
        "place_in_container": None,
        "visibility": "all",
        "style_border_top_color": "border",
        "style_border_top_size": 0,
        "style_padding_top": 10,
        "style_border_bottom_color": "border",
        "style_border_bottom_size": 0,
        "style_padding_bottom": 10,
        "style_border_left_color": "border",
        "style_border_left_size": 0,
        "style_padding_left": 20,
        "style_border_right_color": "border",
        "style_border_right_size": 0,
        "style_padding_right": 20,
        "style_background": "none",
        "style_background_color": "#ffffffff",
        "style_width": "normal",
        "label": "'label'",
        "required": False,
        "placeholder": "'test'",
        "default_value": "'default'",
        "options": [
            {"value": "Option 1", "name": "option1"},
            {"value": "Option 2", "name": "option2"},
        ],
        "roles": [],
        "role_type": Element.ROLE_TYPES.ALLOW_ALL,
        # multiple property is missing
        # show_as_dropdown property is  missing
    }

    imported_element = element_type.import_serialized(page, serialized, {})

    assert isinstance(imported_element.specific, ChoiceElement)
    assert imported_element.multiple is False
    assert imported_element.show_as_dropdown is True
    assert len(imported_element.choiceelementoption_set.all()) == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "initial_roles,valid_roles,cleaned_roles",
    [
        (
            ["invalid_role_a"],
            [],
            # "invalid_role_a" is not a valid role, so we expect an empty list
            [],
        ),
        (
            ["invalid_role_a"],
            ["foo_role"],
            # "invalid_role_a" doesn't match valid roles in ["foo_role"], so
            # we expect an empty list
            [],
        ),
        (
            ["invalid_role_a", "foo_role"],
            ["foo_role"],
            # "foo_role" is the only valid role, so we expect that
            # "invalid_role_a" is removed and only "foo_role" is returned
            ["foo_role"],
        ),
        (
            ["foo_role", "bar_role"],
            ["foo_role", "bar_role"],
            # Both "foo_role" and "bar_role" are valid, so we expect both
            # roles to be returned.
            ["foo_role", "bar_role"],
        ),
    ],
)
def test_sanitize_element_roles_removes_invalid_roles(
    initial_roles,
    valid_roles,
    cleaned_roles,
):
    """
    Ensure that sanitize_element_roles() removes invalid roles if they exist
    in the element's roles list.

    This can happen if the role has since been deleted or renamed.
    """

    element_type = HeadingElementType()

    result = element_type.sanitize_element_roles(
        initial_roles,
        valid_roles,
        {},
    )

    assert result == cleaned_roles


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_source_ids,initial_roles,valid_roles,cleaned_roles",
    [
        (
            (100, 7777),
            [],
            [f"{DEFAULT_USER_ROLE_PREFIX}7777"],
            # existing roles is empty, so despite there existing a Default User
            # Role, it shouldn't be returned.
            [],
        ),
        (
            (100, 7777),
            ["invalid_role_a"],
            [f"{DEFAULT_USER_ROLE_PREFIX}7777"],
            # "invalid_role_a" is not a valid role, so we expect an empty list.
            [],
        ),
        (
            (100, 7777),
            ["invalid_role_a", f"{DEFAULT_USER_ROLE_PREFIX}100", "invalid_role_b"],
            [f"{DEFAULT_USER_ROLE_PREFIX}7777"],
            # We expect only the default user role to be returned
            [f"{DEFAULT_USER_ROLE_PREFIX}7777"],
        ),
        (
            (100, 7777),
            [f"{DEFAULT_USER_ROLE_PREFIX}100"],
            [],
            # Although the initial roles contains a Default User Role, it is
            # not valid, so we expect an empty list.
            [],
        ),
        (
            (100, 7777),
            [f"{DEFAULT_USER_ROLE_PREFIX}100", f"{DEFAULT_USER_ROLE_PREFIX}900"],
            [f"{DEFAULT_USER_ROLE_PREFIX}7777"],
            # the 900 id is missing in the datasource map so we don't keep that one.
            [f"{DEFAULT_USER_ROLE_PREFIX}7777"],
        ),
    ],
)
def test_sanitize_element_roles_fixes_default_user_role(
    user_source_ids,
    initial_roles,
    valid_roles,
    cleaned_roles,
):
    """
    Ensure that sanitize_element_roles() fixes the default user role.

    The Default User Role is based on the User Source ID. Since the User Source
    is newly created during an import, the Default User Role must also be
    updated.
    """

    user_sources_mapping = {user_source_ids[0]: user_source_ids[1]}
    element_type = HeadingElementType()

    result = element_type.sanitize_element_roles(
        initial_roles,
        valid_roles,
        user_sources_mapping,
    )

    assert result == cleaned_roles


@pytest.mark.parametrize("collection_element_type", collection_element_types())
def test_collection_element_type_publicly_searchable_sortable_filterable(
    collection_element_type,
):
    expected_results = {
        "repeat": {
            "is_publicly_sortable": True,
            "is_publicly_searchable": True,
            "is_publicly_filterable": True,
        },
        "table": {
            "is_publicly_sortable": True,
            "is_publicly_searchable": True,
            "is_publicly_filterable": True,
        },
        "record_selector": {
            "is_publicly_sortable": False,
            "is_publicly_searchable": True,
            "is_publicly_filterable": False,
        },
    }
    expected_result = expected_results.get(collection_element_type.type)
    if not expected_result:
        # A new collection element type has been implemented and
        # needs to be added to the expected results.
        pytest.fail(
            f"Missing expected result for collection element type {collection_element_type.type}"
        )
    assert (
        collection_element_type.is_publicly_sortable
        == expected_result["is_publicly_sortable"]
    )
    assert (
        collection_element_type.is_publicly_searchable
        == expected_result["is_publicly_searchable"]
    )
    assert (
        collection_element_type.is_publicly_filterable
        == expected_result["is_publicly_filterable"]
    )


@pytest.mark.django_db
@pytest.mark.parametrize("collection_element_type", collection_element_types())
def test_collection_element_type_after_update(collection_element_type, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = collection_element_type.model_class.objects.create(page=page)
    element.property_options.create(schema_property="field_123")

    # The `after_update` method drops all property options, and creates
    # only what is provided into the method in its `values`.
    collection_element_type.after_update(
        element, {"property_options": [{"schema_property": "field_456"}]}, {}
    )
    assert element.property_options.count() == 1
    assert element.property_options.filter(schema_property="field_456").exists()

    # The `after_update` method drops all property options if the data source
    # has changed.
    collection_element_type.after_update(element, {}, {"data_source": (Mock(), Mock())})
    assert element.property_options.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("collection_element_type", collection_element_types())
def test_collection_element_type_prepare_value_for_db(
    collection_element_type, data_fixture
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    different_page = data_fixture.create_builder_page(user=user, builder=builder)
    element = collection_element_type.model_class.objects.create(page=page)

    multiple_rows = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
    )
    single_row = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user, page=page
    )

    multiple_rows_different_page = (
        data_fixture.create_builder_local_baserow_list_rows_data_source(
            user=user,
            page=different_page,
        )
    )

    data_source_no_service = data_fixture.create_builder_data_source(page=page)

    # The data source must belong to the same page as `page`.
    with pytest.raises(RequestBodyValidationException):
        assert collection_element_type.prepare_value_for_db(
            {"page": page, "data_source_id": multiple_rows_different_page.id}, element
        )

    # Schema property is not allowed when the data source returns multiple rows.
    with pytest.raises(ValidationError) as exc:
        assert collection_element_type.prepare_value_for_db(
            {"schema_property": "field_123", "data_source_id": multiple_rows.id},
            element,
        )
    assert (
        exc.value.args[0] == "Data sources which return multiple rows cannot "
        "be used in conjunction with the schema property."
    )

    # The data source has no service to use.
    with pytest.raises(ValidationError) as exc:
        assert collection_element_type.prepare_value_for_db(
            {"data_source_id": data_source_no_service.id},
            element,
        )
    assert (
        exc.value.args[0] == f"Data source {data_source_no_service.id} is "
        "partially configured and not ready for use."
    )

    # Prepare for db a multiple rows data source.
    assert collection_element_type.prepare_value_for_db(
        {"page": page, "data_source_id": multiple_rows.id}, element
    ) == {"data_source": multiple_rows, "page": page}

    # Prepare for db a single row data source.
    assert collection_element_type.prepare_value_for_db(
        {"page": page, "data_source_id": single_row.id, "schema_property": "field_123"},
        element,
    ) == {"data_source": single_row, "page": page, "schema_property": "field_123"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "choices,expected_choices,invalid_choices",
    [
        (
            [
                {"name": "foo_name1", "value": "foo_value1"},
                {"name": "bar_name1", "value": "bar_value1"},
            ],
            # Since the "value" exists for all options, return the values.
            ["foo_value1", "bar_value1"],
            # Since the "value" exists, the "name" isn't used and thus are
            # invalid options.
            ["foo_name1", "bar_name1"],
        ),
        (
            [
                {"name": "foo_name2", "value": None},
                {"name": "bar_name2", "value": None},
            ],
            # Since the "value" doesn't exist, return the "name".
            ["foo_name2", "bar_name2"],
            # Since the "value" doesn't exist, the "name" is used. Any other
            # values are invalid options.
            ["foo_value2", "bar_value2"],
        ),
        (
            [
                {"name": "foo_name3", "value": ""},
                {"name": "bar_name3", "value": ""},
            ],
            # An empty string is a valid value
            [""],
            # Since the "value" is an empty string and is valid, it is used.
            # Any other values are invalid options.
            ["foo_name3", "bar_name3"],
        ),
        (
            [
                {"name": "foo_name", "value": "foo_value"},
                {"name": "bar_name", "value": ""},
                {"name": "baz_name", "value": None},
            ],
            # The valid list of values
            ["foo_value", "", "baz_name"],
            # The invalid list of values
            ["foo_name", "bar_name"],
        ),
    ],
)
def test_choice_element_validation_none_vs_empty(
    data_fixture, choices, expected_choices, invalid_choices
):
    """
    Test that None and empty string are handled correctly by the
    ChoiceElementType's is_valid() method.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    choice = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("choice"),
        page=page,
    )

    for item in choices:
        choice.choiceelementoption_set.create(name=item["name"], value=item["value"])

    for value in expected_choices:
        assert ChoiceElementType().is_valid(choice, value, {}) is value

    for value in invalid_choices:
        with pytest.raises(ValueError):
            ChoiceElementType().is_valid(choice, value, {})


@pytest.mark.django_db
def test_choice_element_integer_option_values(data_fixture):
    """
    Ensure that the row ID key (in addition to the Primary DB field) can be used
    as a valid Option Value when referring to a linked table.
    """

    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Ingredient", "text"),
        ],
        rows=[
            ["Palak Paneer", "Cottage Cheese"],
            ["Gobi Manchurian", "Cauliflower"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )
    choice = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("choice"),
        page=page,
        option_type=ChoiceElement.OPTION_TYPE.FORMULAS,
        formula_name=f"get('data_source.{data_source.id}.*.field_{fields[0].id}')",
        formula_value=f"get('data_source.{data_source.id}.*.id')",
    )

    expected_choices = [row.id for row in rows]

    dispatch_context = BuilderDispatchContext(
        HttpRequest(),
        page,
        offset=0,
        count=20,
        only_expose_public_allowed_properties=False,
    )

    for value in expected_choices:
        dispatch_context.reset_call_stack()
        assert ChoiceElementType().is_valid(choice, value, dispatch_context) is value


@pytest.mark.parametrize(
    "allowed_element_type",
    [
        element_type.type
        for element_type in element_type_registry.get_all()
        if element_type.type != ColumnElementType.type
        and not element_type.is_multi_page_element
    ],
)
def test_column_container_child_types_allowed(allowed_element_type):
    assert allowed_element_type in [
        e.type for e in ColumnElementType().child_types_allowed
    ]


@pytest.mark.django_db
def test_record_element_is_valid(data_fixture):
    user = data_fixture.create_user()

    # There must exist one database with a primary column for the record name
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    model = table.get_model(attribute_names=True)
    row_ids = [
        model.objects.create(name="BMW").id,
        model.objects.create(name="Audi").id,
        model.objects.create(name="2Cv").id,
        model.objects.create(name="Tesla").id,
    ]

    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )

    # Record selector with no data sources is invalid
    with pytest.raises(ElementImproperlyConfigured):
        element = RecordSelectorElement()
        RecordSelectorElementType().is_valid(element, "", dispatch_context)

    # Record selector that is required should not accept empty values
    with pytest.raises(ValueError):
        element = RecordSelectorElement(data_source=data_source, required=True)
        RecordSelectorElementType().is_valid(element, "", dispatch_context)

    # Record selector that is required should accept only valid values
    element = RecordSelectorElement(data_source=data_source, required=True)
    for row_id in row_ids:
        assert (
            RecordSelectorElementType().is_valid(element, row_id, dispatch_context)
            == row_id
        )
    with pytest.raises(ValueError):
        RecordSelectorElementType().is_valid(element, "-1", dispatch_context)

    # Record selector that is not required should accept empty values
    element = RecordSelectorElement(data_source=data_source, required=False)
    assert RecordSelectorElementType().is_valid(element, "", dispatch_context) == ""

    # Record selector that is not required should accept only valid values
    element = RecordSelectorElement(data_source=data_source, required=False)
    for row_id in row_ids:
        assert (
            RecordSelectorElementType().is_valid(element, row_id, dispatch_context)
            == row_id
        )
    with pytest.raises(ValueError):
        RecordSelectorElementType().is_valid(element, "-1", dispatch_context)

    # Record selector that is multiple and required should not accept empty values
    with pytest.raises(ValueError):
        element = RecordSelectorElement(
            data_source=data_source, required=True, multiple=True
        )
        RecordSelectorElementType().is_valid(element, "", dispatch_context)

    # Record selector that is multiple should not accept invalid values
    with pytest.raises(TypeError):
        element = RecordSelectorElement(
            data_source=data_source, required=False, multiple=True
        )
        RecordSelectorElementType().is_valid(element, ["invalid", ""], dispatch_context)

    # Record selector that is multiple and required should accept only valid values
    element = RecordSelectorElement(
        data_source=data_source, required=True, multiple=True
    )
    assert (
        RecordSelectorElementType().is_valid(element, row_ids, dispatch_context)
        == row_ids
    )
    with pytest.raises(ValueError):
        RecordSelectorElementType().is_valid(element, [], dispatch_context)

    # Record selector that is multiple and not required should accept empty values
    element = RecordSelectorElement(
        data_source=data_source, required=False, multiple=True
    )
    assert RecordSelectorElementType().is_valid(element, "", dispatch_context) == ""

    # Record selector that is multiple and not required should accept only valid values
    element = RecordSelectorElement(
        data_source=data_source, required=False, multiple=True
    )
    assert (
        RecordSelectorElementType().is_valid(element, row_ids, dispatch_context)
        == row_ids
    )
    with pytest.raises(ValueError):
        RecordSelectorElementType().is_valid(element, "-1", dispatch_context)


@pytest.mark.django_db(transaction=True)
def test_repeat_element_import_export(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    table = data_fixture.create_database_table(database=database)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    data_fixture.create_select_option(
        field=multiple_select_field, value="A", color="blue", order=0
    )

    page = data_fixture.create_builder_page(builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    outer_repeat = data_fixture.create_builder_repeat_element(
        data_source=data_source, page=page
    )
    data_fixture.create_builder_repeat_element(
        page=page,
        data_source=None,
        parent_element_id=outer_repeat.id,
        schema_property=multiple_select_field.db_column,
    )

    config = ImportExportConfig(include_permission_data=False)
    exported_applications = CoreHandler().export_workspace_applications(
        workspace, BytesIO(), config
    )

    # Ensure the values are json serializable
    try:
        json.dumps(exported_applications)
    except Exception as e:
        pytest.fail(f"Exported applications are not json serializable: {e}")

    imported_applications, _ = CoreHandler().import_applications_to_workspace(
        workspace, exported_applications, BytesIO(), config, None
    )
    imported_database, imported_builder = imported_applications

    # Pluck out the imported database records.
    imported_table = imported_database.table_set.get()
    imported_field = imported_table.field_set.get()

    # Pluck out the imported builder records.
    imported_page = imported_builder.visible_pages.all()[0]
    imported_data_source = imported_page.datasource_set.get()
    imported_root_repeat = imported_page.element_set.get(
        parent_element_id=None
    ).specific
    imported_nested_repeat = imported_root_repeat.children.get().specific

    assert imported_root_repeat.data_source_id == imported_data_source.id
    assert imported_nested_repeat.schema_property == imported_field.db_column


@pytest.mark.parametrize(
    "required,date_format,include_time,time_format,value,expected",
    [
        (False, "ISO", False, "24", None, "None"),
        (True, "ISO", False, "24", None, ValueError),
        (True, "ISO", False, "24", "2024-04-25T00:00:00.000Z", "2024-04-25"),
        (True, "ISO", True, "24", "2024-04-25T14:30:00.000Z", "2024-04-25 14:30"),
        (True, "EU", False, "24", "2024-04-25T00:00:00.000Z", "25/04/2024"),
        (True, "US", False, "24", "2024-04-25T00:00:00.000Z", "04/25/2024"),
        (True, "EU", True, "12", "2024-04-25T14:30:00.000Z", "25/04/2024 02:30 PM"),
        (True, "US", True, "12", "2024-04-25T14:30:00.000Z", "04/25/2024 02:30 PM"),
    ],
)
def test_datetime_picker_element_is_valid(
    required, date_format, include_time, time_format, value, expected
):
    element_type = DateTimePickerElementType()
    element = DateTimePickerElement(
        required=required,
        date_format=date_format,
        include_time=include_time,
        time_format=time_format,
    )
    if expected is ValueError:
        with pytest.raises(ValueError):
            element_type.is_valid(element, value, {})
    else:
        assert str(element_type.is_valid(element, value, {})) == expected
