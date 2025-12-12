import abc
import uuid
from datetime import datetime
from decimal import InvalidOperation
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypedDict,
    Union,
)

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import IntegerField, Q, QuerySet
from django.db.models.functions import Cast

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.api.elements.serializers import (
    ChoiceOptionSerializer,
    MenuItemSerializer,
    NestedMenuItemsMixin,
)
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.elements.exceptions import ElementImproperlyConfigured
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.mixins import (
    CollectionElementTypeMixin,
    CollectionElementWithFieldsTypeMixin,
    ContainerElementTypeMixin,
    FormElementTypeMixin,
    MultiPageElementTypeMixin,
)
from baserow.contrib.builder.elements.models import (
    INPUT_TEXT_TYPES,
    ButtonElement,
    CheckboxElement,
    ChoiceElement,
    ChoiceElementOption,
    ColumnElement,
    DateTimePickerElement,
    Element,
    FooterElement,
    FormContainerElement,
    HeaderElement,
    HeadingElement,
    HorizontalAlignments,
    IFrameElement,
    ImageElement,
    InputTextElement,
    LinkElement,
    MenuElement,
    MenuItemElement,
    NavigationElementMixin,
    RatingElement,
    RatingInputElement,
    RecordSelectorElement,
    RepeatElement,
    SimpleContainerElement,
    TableElement,
    TextElement,
    VerticalAlignments,
    get_default_table_orientation,
)
from baserow.contrib.builder.elements.registries import (
    ElementType,
    element_type_registry,
)
from baserow.contrib.builder.formula_property_extractor import FormulaFieldVisitor
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.theme.theme_config_block_types import (
    TableThemeConfigBlockType,
)
from baserow.contrib.builder.types import ElementDict
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.constants import (
    DATE_FORMAT,
    DATE_FORMAT_CHOICES,
    DATE_TIME_FORMAT,
    DATE_TIME_FORMAT_CHOICES,
)
from baserow.core.datetime import FormattedDate, FormattedDateTime
from baserow.core.formula import (
    BaserowFormulaSyntaxError,
    get_parse_tree_for_formula,
    resolve_formula,
)
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormula,
    BaserowFormulaObject,
)
from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_integer,
    ensure_numeric,
    ensure_string_or_integer,
)
from baserow.core.registry import Instance, T
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.utils import merge_dicts_no_duplicates


def collection_element_types():
    """
    Responsible for returning all collection element types. We do this by checking if
    the element type is a subclass of the base `CollectionElementTypeMixin` class.

    :return: A list of collection element types
    """

    return [
        element_type
        for element_type in element_type_registry.get_all()
        if getattr(element_type, "is_collection_element", False)
    ]


class ColumnElementType(ContainerElementTypeMixin, ElementType):
    """
    A column element is a container element that can be used to display other elements
    in a column.
    """

    type = "column"
    model_class = ColumnElement

    class SerializedDict(ContainerElementTypeMixin.SerializedDict):
        column_amount: int
        column_gap: int
        alignment: str

    @property
    def serializer_field_names(self):
        return super().serializer_field_names + [
            "column_amount",
            "column_gap",
            "alignment",
        ]

    @property
    def allowed_fields(self):
        return super().allowed_fields + [
            "column_amount",
            "column_gap",
            "alignment",
        ]

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {
            "column_amount": 2,
            "column_gap": 10,
            "alignment": VerticalAlignments.TOP,
        }

    def get_new_place_in_container(
        self, container_element_before_update: ColumnElement, places_removed: List[str]
    ) -> int:
        places_removed_casted = [int(place) for place in places_removed]

        if len(places_removed) == 0:
            return container_element_before_update.column_amount - 1

        return min(places_removed_casted) - 1

    def get_places_in_container_removed(
        self, values: Dict, instance: ColumnElement
    ) -> List[str]:
        column_amount = values.get("column_amount", None)

        if column_amount is None:
            return []

        places_removed = list(range(column_amount, instance.column_amount))

        return [str(place) for place in places_removed]

    def apply_order_by_children(self, queryset: QuerySet[Element]) -> QuerySet[Element]:
        return queryset.annotate(
            place_in_container_as_int=Cast(
                "place_in_container", output_field=IntegerField()
            )
        ).order_by("place_in_container_as_int", "order")

    def validate_place_in_container(
        self, place_in_container: str, instance: ColumnElement
    ):
        max_place_in_container = instance.column_amount - 1
        if int(place_in_container) > max_place_in_container:
            raise DRFValidationError(
                f"place_in_container can at most be {max_place_in_container}, ({place_in_container}, was given)"
            )

    @property
    def child_types_allowed(self) -> List[str]:
        """
        The column container only forbids itself as a child.
        :return: a list of element types, without the column container type.
        """

        return [
            element_type
            for element_type in super().child_types_allowed
            if element_type.type != self.type
        ]


class FormContainerElementType(ContainerElementTypeMixin, ElementType):
    type = "form_container"
    model_class = FormContainerElement
    allowed_fields = [
        "submit_button_label",
        "reset_initial_values_post_submission",
    ]
    serializer_field_names = [
        "submit_button_label",
        "reset_initial_values_post_submission",
    ]
    simple_formula_fields = ["submit_button_label"]

    class SerializedDict(ContainerElementTypeMixin.SerializedDict):
        submit_button_label: BaserowFormulaObject
        reset_initial_values_post_submission: bool

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {
            "submit_button_label": BaserowFormulaObject(
                formula="'Submit'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "reset_initial_values_post_submission": True,
        }

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ButtonThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "submit_button_label": FormulaSerializerField(
                help_text=FormContainerElement._meta.get_field(
                    "submit_button_label"
                ).help_text,
            ),
            "reset_initial_values_post_submission": serializers.BooleanField(
                help_text=FormContainerElement._meta.get_field(
                    "reset_initial_values_post_submission"
                ).help_text,
                required=False,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="button",
                theme_config_block_type_name=ButtonThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
            ),
        }

    @property
    def child_types_allowed(self) -> List[str]:
        """
        The form container only forbids itself as a child.
        :return: a list of element types, without the form container type.
        """

        return [
            element_type
            for element_type in super().child_types_allowed
            if element_type.type != self.type
        ]


class SimpleContainerElementType(ContainerElementTypeMixin, ElementType):
    type = "simple_container"
    model_class = SimpleContainerElement

    class SerializedDict(ContainerElementTypeMixin.SerializedDict):
        pass

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {}


class TableElementType(CollectionElementWithFieldsTypeMixin, ElementType):
    type = "table"
    model_class = TableElement

    class SerializedDict(CollectionElementWithFieldsTypeMixin.SerializedDict):
        orientation: dict

    @property
    def allowed_fields(self):
        return super().allowed_fields + ["orientation"]

    @property
    def serializer_field_names(self):
        return super().serializer_field_names + ["orientation"]

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ButtonThemeConfigBlockType,
            TypographyThemeConfigBlockType,
        )

        return {
            **super().serializer_field_overrides,
            "orientation": serializers.JSONField(
                allow_null=False,
                default=get_default_table_orientation,
                help_text=TableElement._meta.get_field("orientation").help_text,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name=["button", "table", "header_button"],
                theme_config_block_type_name=[
                    ButtonThemeConfigBlockType.type,
                    [
                        TableThemeConfigBlockType.type,
                        TypographyThemeConfigBlockType.type,
                    ],
                    ButtonThemeConfigBlockType.type,
                ],
                serializer_kwargs={"required": False},
            ),
        }

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).prefetch_related("fields")

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {
            "data_source_id": None,
            "button_load_more_label": BaserowFormulaObject(
                formula="'test'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "orientation": get_default_table_orientation(),
        }


class RepeatElementType(
    CollectionElementTypeMixin, ContainerElementTypeMixin, ElementType
):
    type = "repeat"
    model_class = RepeatElement

    @property
    def allowed_fields(self):
        return super().allowed_fields + [
            "orientation",
            "items_per_row",
            "horizontal_gap",
            "vertical_gap",
        ]

    @property
    def serializer_field_names(self):
        return super().serializer_field_names + [
            "orientation",
            "items_per_row",
            "horizontal_gap",
            "vertical_gap",
        ]

    class SerializedDict(
        CollectionElementTypeMixin.SerializedDict,
        ContainerElementTypeMixin.SerializedDict,
    ):
        orientation: str
        items_per_row: dict
        horizontal_gap: int
        vertical_gap: int

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ButtonThemeConfigBlockType,
        )

        return {
            **super().serializer_field_overrides,
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name=["button", "header_button"],
                theme_config_block_type_name=[
                    ButtonThemeConfigBlockType.type,
                    ButtonThemeConfigBlockType.type,
                ],
                serializer_kwargs={"required": False},
            ),
        }

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {
            "data_source_id": None,
            "button_load_more_label": BaserowFormulaObject(
                formula="'test'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "orientation": RepeatElement.ORIENTATIONS.VERTICAL,
        }


class RecordSelectorElementType(
    FormElementTypeMixin, CollectionElementTypeMixin, ElementType
):
    type = "record_selector"
    model_class = RecordSelectorElement
    simple_formula_fields = CollectionElementTypeMixin.simple_formula_fields + [
        "label",
        "default_value",
        "placeholder",
    ]

    # The record selector cannot be sorted or filtered publicly,
    # page visitors can only search against its data.
    is_publicly_sortable = False
    is_publicly_filterable = False

    class SerializedDict(CollectionElementTypeMixin.SerializedDict):
        required: bool
        label: BaserowFormulaObject
        default_value: BaserowFormulaObject
        placeholder: BaserowFormulaObject
        multiple: bool
        option_name_suffix: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        # RecordSelectorElement does not allow 'schema_property' as it always
        # relies on data sources that return lists.
        collection_serializer_field_overrides = (
            super().serializer_field_overrides.copy()
        )
        collection_serializer_field_overrides.pop("schema_property")

        return {
            **collection_serializer_field_overrides,
            "required": serializers.BooleanField(
                help_text=RecordSelectorElement._meta.get_field("required").help_text,
                default=False,
                required=False,
            ),
            "label": FormulaSerializerField(
                help_text=RecordSelectorElement._meta.get_field("label").help_text,
            ),
            "default_value": FormulaSerializerField(
                help_text=RecordSelectorElement._meta.get_field(
                    "default_value"
                ).help_text,
            ),
            "placeholder": FormulaSerializerField(
                help_text=RecordSelectorElement._meta.get_field(
                    "placeholder"
                ).help_text,
            ),
            "multiple": serializers.BooleanField(
                help_text=RecordSelectorElement._meta.get_field("multiple").help_text,
                default=False,
                required=False,
            ),
            "option_name_suffix": FormulaSerializerField(
                help_text=RecordSelectorElement._meta.get_field(
                    "option_name_suffix"
                ).help_text,
            ),
        }

    @property
    def allowed_fields(self):
        # RecordSelectorElement does not allow 'schema_property' as it always
        # relies on data sources that return lists.
        collection_allowed_fields = super().allowed_fields.copy()
        collection_allowed_fields.remove("schema_property")
        return collection_allowed_fields + [
            "required",
            "label",
            "default_value",
            "placeholder",
            "multiple",
            "option_name_suffix",
        ]

    @property
    def serializer_field_names(self):
        # RecordSelectorElement does not allow 'schema_property' as it always
        # relies on data sources that return lists.
        collection_serializer_field_names = super().serializer_field_names.copy()
        collection_serializer_field_names.remove("schema_property")
        return collection_serializer_field_names + [
            "required",
            "label",
            "default_value",
            "placeholder",
            "multiple",
            "option_name_suffix",
        ]

    def extract_properties(self, instance: Element, **kwargs) -> Dict[int, List[str]]:
        """
        For the record selector we always need the `id` and the row name property.
        """

        properties = super().extract_properties(instance, **kwargs)

        if instance.data_source_id and instance.data_source.service_id:
            service = instance.data_source.service.specific

            # We need the id for the element
            id_property = service.get_type().get_id_property(service)
            if id_property not in properties.setdefault(
                instance.data_source.service_id, []
            ):
                properties[instance.data_source.service_id].append(id_property)

            primary_property = service.get_type().get_name_property(service)
            if (
                primary_property is not None
                and primary_property not in properties[instance.data_source.service_id]
            ):
                # And we also need at least the name that identifies the row
                properties[instance.data_source.service_id].append(primary_property)

            try:
                # Beside the id and the name field, the record selector also requires
                # the properties used in the `option_name_suffix` formula.
                # This formula has access to the `CurrentDataProvider` so we need
                # to populate the formula context with the `data_source_id`
                # of the element so that we can resolve them.
                formula_context = kwargs | self.import_context_addition(instance)
                tree = get_parse_tree_for_formula(
                    instance.option_name_suffix["formula"]
                )
                properties = merge_dicts_no_duplicates(
                    properties,
                    FormulaFieldVisitor(**formula_context).visit(tree),
                )
            except BaserowFormulaSyntaxError:
                # If there is a syntax error within the formula we ignore it as
                # there will be no properties to extract
                pass

        return properties

    def import_formulas(
        self,
        instance: Instance,
        id_mapping: Dict[str, Any],
        import_formula: Callable[[str, Dict[str, Any]], str],
        **kwargs: Dict[str, Any],
    ) -> Set[Instance]:
        # We need to import the option_name_suffix formula separately because
        # it uses a different import_context
        updated_models = super().import_formulas(
            instance, id_mapping, import_formula, **kwargs
        )
        formula_context = ElementHandler().get_import_context_addition(instance.id)
        instance.option_name_suffix = import_formula(
            instance.option_name_suffix,
            id_mapping,
            **(kwargs | formula_context),
        )
        updated_models.add(instance)
        return updated_models

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {
            "data_source_id": None,
            "required": False,
            "label": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "default_value": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "placeholder": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "multiple": False,
            "option_name_suffix": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
        }

    def is_valid(
        self,
        element: RecordSelectorElement,
        value: Union[List, str],
        dispatch_context: DispatchContext,
    ) -> bool:
        """
        Responsible for validating `RecordSelectorElement` form data.
        """

        if not element.data_source_id:
            msg = "A valid data source is required"
            raise ElementImproperlyConfigured(msg)

        data_source = DataSourceHandler().get_data_source(element.data_source_id)

        service = data_source.service
        service_type = service.get_type()

        try:
            record_ids = set(map(ensure_integer, ensure_array(value)))
            record_names = service_type.get_record_names(
                service.specific,
                record_ids,
                dispatch_context,
            )
            available_record_ids = set(record_names.keys())
        except ValidationError as err:
            msg = (
                "The value must be an array of integers, or convertible to an"
                "array of integers"
            )
            raise TypeError(msg) from err

        if element.multiple:
            if element.required and not record_ids:
                msg = "The value is required"
                raise ValueError(msg)

            if not record_ids.issubset(available_record_ids):
                msg = f"{value} is not a valid option"
                raise ValueError(msg)
        else:
            record_id = value

            if not record_id:
                if element.required:
                    msg = "The value is required"
                    raise ValueError(msg)
            elif record_id not in available_record_ids:
                msg = f"{record_id} is not a valid option"
                raise ValueError(msg)

        return value


class HeadingElementType(ElementType):
    """
    A simple heading element that can be used to display a title.
    """

    type = "heading"
    model_class = HeadingElement
    serializer_field_names = ["value", "level"]
    allowed_fields = ["value", "level"]
    simple_formula_fields = ["value"]

    class SerializedDict(ElementDict):
        value: BaserowFormulaObject
        level: int

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            TypographyThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "value": FormulaSerializerField(
                help_text="The value of the element. Must be an formula.",
            ),
            "level": serializers.IntegerField(
                help_text="The level of the heading from 1 to 6.",
                min_value=1,
                max_value=6,
                default=1,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="typography",
                theme_config_block_type_name=TypographyThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
            ),
        }

        return overrides

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "value": BaserowFormulaObject(
                formula="'Corporis perspiciatis'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "level": 2,
        }


class TextElementType(ElementType):
    """
    A text element that allows plain or markdown content.
    """

    type = "text"
    model_class = TextElement
    serializer_field_names = ["value", "format"]
    allowed_fields = ["value", "format"]
    simple_formula_fields = ["value"]

    class SerializedDict(ElementDict):
        value: BaserowFormulaObject
        format: str

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "value": BaserowFormulaObject(
                formula="'Suscipit maxime eos ea vel commodi dolore. "
                "Eum dicta sit rerum animi. Sint sapiente eum cupiditate nobis vel. "
                "Maxime qui nam consequatur. "
                "Asperiores corporis perspiciatis nam harum veritatis. "
                "Impedit qui maxime aut illo quod ea molestias.'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "format": TextElement.TEXT_FORMATS.PLAIN,
        }

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            TypographyThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "value": FormulaSerializerField(
                help_text="The value of the element. Must be a formula.",
            ),
            "format": serializers.ChoiceField(
                choices=TextElement.TEXT_FORMATS.choices,
                default=TextElement.TEXT_FORMATS.PLAIN,
                help_text=TextElement._meta.get_field("format").help_text,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="typography",
                theme_config_block_type_name=TypographyThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
            ),
        }


class NavigationElementManager:
    """
    A base class that adds navigation properties to an element. (not an actual element)
    """

    def __init__(self, type=None):
        self.type = type

    serializer_field_names = [
        "navigation_type",
        "navigate_to_page_id",
        "navigate_to_url",
        "page_parameters",
        "query_parameters",
        "target",
    ]
    allowed_fields = [
        "navigation_type",
        "navigate_to_page_id",
        "navigate_to_url",
        "page_parameters",
        "query_parameters",
        "target",
    ]
    simple_formula_fields = ["navigate_to_url"]

    class SerializedDict(TypedDict):
        navigation_type: str
        navigate_to_page_id: int
        page_parameters: List
        query_parameters: List
        navigate_to_url: BaserowFormulaObject
        target: str

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        **kwargs,
    ) -> Any:
        if prop_name == "navigate_to_page_id" and value:
            return id_mapping["builder_pages"][value]

        return value

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.elements.serializers import (
            PageParameterValueSerializer,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "navigation_type": serializers.ChoiceField(
                choices=NavigationElementMixin.NAVIGATION_TYPES.choices,
                default=NavigationElementMixin.NAVIGATION_TYPES.PAGE,
                help_text=NavigationElementMixin._meta.get_field(
                    "navigation_type"
                ).help_text,
                required=False,
            ),
            "navigate_to_page_id": serializers.IntegerField(
                allow_null=True,
                default=None,
                help_text=NavigationElementMixin._meta.get_field(
                    "navigate_to_page"
                ).help_text,
                required=False,
            ),
            "navigate_to_url": FormulaSerializerField(
                help_text=NavigationElementMixin._meta.get_field(
                    "navigate_to_url"
                ).help_text,
            ),
            "page_parameters": PageParameterValueSerializer(
                many=True,
                default=[],
                help_text=NavigationElementMixin._meta.get_field(
                    "page_parameters"
                ).help_text,
                required=False,
            ),
            "query_parameters": PageParameterValueSerializer(
                many=True,
                default=[],
                help_text=NavigationElementMixin._meta.get_field(
                    "query_parameters"
                ).help_text,
                required=False,
            ),
            "target": serializers.ChoiceField(
                choices=NavigationElementMixin.TARGETS.choices,
                default=NavigationElementMixin.TARGETS.SELF,
                help_text=NavigationElementMixin._meta.get_field("target").help_text,
                required=False,
            ),
        }
        return overrides

    @classmethod
    def get_serializer_field_overrides(cls):
        return cls().serializer_field_overrides

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "navigation_type": "custom",
            "navigate_to_page_id": None,
            "navigate_to_url": BaserowFormulaObject(
                formula='"http://example.com"',
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "page_parameters": [],
            "query_parameters": [],
            "target": "blank",
        }

    def validate_place(
        self,
        page: Page,
        parent_element: Optional[Element],
        place_in_container: str,
    ):
        """
        We need it because it's called in the prepare_value_for_db.
        """

    def prepare_value_for_db(
        self, values: Dict, instance: Optional[LinkElement] = None
    ):
        """
        set the type of the element for the prepare_value_for_db method in case we're
        adding to a parent element which requires a type check
        """

        page_params = values.get("page_parameters", [])
        navigate_to_page_id = values.get(
            "navigate_to_page_id", getattr(instance, "navigate_to_page_id", None)
        )

        if len(page_params) != 0 and navigate_to_page_id is not None:
            page = (
                PageHandler().get_page(navigate_to_page_id)
                if navigate_to_page_id is not None
                else instance.navigate_to_page
            )

            self._raise_if_path_params_are_invalid(page_params, page)

        return ElementType.prepare_value_for_db(self, values, instance)

    def _raise_if_path_params_are_invalid(self, path_params: List, page: Page) -> None:
        """
        Checks if the path parameters being set are correctly correlated to the
        path parameters defined for the page.

        :param path_params: The path params defined for the navigation event
        :param page: The page the element is navigating to
        :raises DRFValidationError: If the param does not exist or the
            type does not match
        """

        parameter_types = {p["name"]: p["type"] for p in page.path_params}
        for page_parameter in path_params:
            page_parameter_name = page_parameter["name"]
            page_parameter_type = parameter_types.get(page_parameter_name, None)

            if page_parameter_type is None:
                raise DRFValidationError(
                    f"Page path parameter {page_parameter['name']} does not exist"
                )


class LinkElementType(ElementType):
    """
    A link element that can be used to navigate to a page or a URL.
    """

    type = "link"
    model_class = LinkElement
    simple_formula_fields = NavigationElementManager.simple_formula_fields + ["value"]

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + NavigationElementManager.serializer_field_names
            + [
                "value",
                "variant",
            ]
        )

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + NavigationElementManager.allowed_fields
            + [
                "value",
                "variant",
            ]
        )

    class SerializedDict(ElementDict, NavigationElementManager.SerializedDict):
        value: BaserowFormulaObject
        variant: str

    def formula_generator(
        self, element: Element
    ) -> Generator[str | Instance, str, None]:
        """
        Generator that returns formula fields for the LinkElementType.

        Unlike other Element types, this one has its formula fields in the
        page_parameters and query_prameters JSON fields.
        """

        yield from super().formula_generator(element)

        for index, data in enumerate(element.page_parameters):
            new_formula = yield BaserowFormulaObject.to_formula(data["value"])
            if new_formula is not None:
                element.page_parameters[index]["value"] = new_formula
                yield element

        for index, data in enumerate(element.query_parameters or []):
            new_formula = yield BaserowFormulaObject.to_formula(data["value"])
            if new_formula is not None:
                element.query_parameters[index]["value"] = new_formula
                yield element

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        return super().deserialize_property(
            prop_name,
            NavigationElementManager().deserialize_property(
                prop_name, value, id_mapping, **kwargs
            ),
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ButtonThemeConfigBlockType,
            LinkThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = (
            super().serializer_field_overrides
            | NavigationElementManager().get_serializer_field_overrides()
            | {
                "value": FormulaSerializerField(
                    help_text="The value of the element. Must be an formula.",
                ),
                "variant": serializers.ChoiceField(
                    choices=LinkElement.VARIANTS.choices,
                    help_text=LinkElement._meta.get_field("variant").help_text,
                    required=False,
                ),
                "styles": DynamicConfigBlockSerializer(
                    required=False,
                    property_name=["button", "link"],
                    theme_config_block_type_name=[
                        ButtonThemeConfigBlockType.type,
                        LinkThemeConfigBlockType.type,
                    ],
                    serializer_kwargs={"required": False},
                ),
            }
        )

        return overrides

    def get_pytest_params(self, pytest_data_fixture):
        return NavigationElementManager().get_pytest_params(pytest_data_fixture) | {
            "value": BaserowFormulaObject(
                formula="'test'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "variant": "link",
        }

    def prepare_value_for_db(
        self, values: Dict, instance: Optional[LinkElement] = None
    ):
        return NavigationElementManager(self.type).prepare_value_for_db(
            values, instance
        )


class ImageElementType(ElementType):
    """
    A simple image element that can display an image either through a remote source
    or via an uploaded file
    """

    type = "image"
    model_class = ImageElement
    serializer_field_names = [
        "image_source_type",
        "image_file",
        "image_url",
        "alt_text",
    ]
    request_serializer_field_names = [
        "image_source_type",
        "image_file",
        "image_url",
        "alt_text",
    ]
    allowed_fields = [
        "image_source_type",
        "image_file",
        "image_url",
        "alt_text",
    ]
    simple_formula_fields = ["image_url", "alt_text"]

    class SerializedDict(ElementDict):
        image_source_type: str
        image_file_id: int
        image_url: BaserowFormulaObject
        alt_text: BaserowFormulaObject

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "image_source_type": ImageElement.IMAGE_SOURCE_TYPES.UPLOAD,
            "image_file_id": None,
            "image_url": BaserowFormulaObject(
                formula="'https://test.com/image.png'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "alt_text": BaserowFormulaObject(
                formula="'some alt text'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
        }

    @property
    def serializer_field_overrides(self):
        from baserow.api.user_files.serializers import UserFileSerializer
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ImageThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "image_file": UserFileSerializer(required=False),
            "image_url": FormulaSerializerField(
                help_text=ImageElement._meta.get_field("image_url").help_text,
            ),
            "alt_text": FormulaSerializerField(
                help_text=ImageElement._meta.get_field("alt_text").help_text,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="image",
                theme_config_block_type_name=ImageThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
            ),
        }

        overrides.update(super().serializer_field_overrides)
        return overrides

    @property
    def request_serializer_field_overrides(self):
        from baserow.api.user_files.serializers import UserFileField
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.api.validators import image_file_validation
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ImageThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "image_url": FormulaSerializerField(
                help_text=ImageElement._meta.get_field("image_url").help_text
            ),
            "alt_text": FormulaSerializerField(
                help_text=ImageElement._meta.get_field("alt_text").help_text
            ),
            "image_file": UserFileField(
                allow_null=True,
                required=False,
                default=None,
                help_text="The image file",
                validators=[image_file_validation],
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="image",
                theme_config_block_type_name=ImageThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
                request_serializer=True,
            ),
        }
        if super().request_serializer_field_overrides is not None:
            overrides.update(super().request_serializer_field_overrides)
        return overrides

    def serialize_property(
        self,
        element: Element,
        prop_name: BaserowFormula,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "image_file_id":
            return UserFileHandler().export_user_file(
                element.image_file, files_zip=files_zip, storage=storage, cache=cache
            )

        return super().serialize_property(
            element, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        if prop_name == "image_file_id":
            user_file = UserFileHandler().import_user_file(
                value, files_zip=files_zip, storage=storage
            )
            if user_file:
                return user_file.id
            return None

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )


class InputElementType(FormElementTypeMixin, ElementType, abc.ABC):
    pass


class RatingElementType(ElementType):
    type = "rating"
    model_class = RatingElement
    allowed_fields = [
        "max_value",
        "color",
        "rating_style",
        "value",
    ]
    serializer_field_names = [
        "max_value",
        "color",
        "rating_style",
        "value",
    ]
    simple_formula_fields = ["value"]

    class SerializedDict(ElementDict):
        value: BaserowFormulaObject
        max_value: str
        color: str
        rating_style: str

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "max_value": 5,
            "value": BaserowFormulaObject(
                formula="5",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "color": "dark-orange",
            "rating_style": "star",
        }

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "value": FormulaSerializerField(
                help_text=RatingElement._meta.get_field("value").help_text
            ),
        }


class RatingInputElementType(InputElementType):
    type = "rating_input"
    model_class = RatingInputElement
    allowed_fields = [
        "max_value",
        "color",
        "rating_style",
        "value",
        "required",
        "label",
    ]
    serializer_field_names = [
        "max_value",
        "color",
        "rating_style",
        "value",
        "required",
        "label",
    ]
    simple_formula_fields = ["value", "label"]

    class SerializedDict(ElementDict):
        label: BaserowFormulaObject
        required: bool
        value: BaserowFormulaObject
        max_value: str
        color: str
        rating_style: str

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "max_value": 5,
            "value": BaserowFormulaObject(
                formula="5",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "color": "dark-orange",
            "rating_style": "star",
            "label": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "required": False,
        }

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        return super().serializer_field_overrides | {
            "label": FormulaSerializerField(
                help_text=RatingInputElement._meta.get_field("label").help_text
            ),
            "required": serializers.BooleanField(
                help_text=RatingInputElement._meta.get_field("required").help_text,
                default=False,
                required=False,
            ),
            "value": FormulaSerializerField(
                help_text=RatingInputElement._meta.get_field("value").help_text,
            ),
        }

    def is_valid(
        self,
        element: Type[RatingInputElement],
        value: Any,
        dispatch_context: DispatchContext,
    ) -> bool:
        """
        :param element: The element we're trying to use form data in.
        :param value: The form data value, which may be invalid.
        :param dispatch_context: The context the element is being used in.
        :return: Whether the value is valid or not for this element.
        """

        if (element.required and value is None) or not (
            value is None or 0 <= value <= element.max_value
        ):
            raise ValueError("The value is required")
        return value


class InputTextElementType(InputElementType):
    type = "input_text"
    model_class = InputTextElement
    allowed_fields = [
        "label",
        "default_value",
        "required",
        "validation_type",
        "placeholder",
        "is_multiline",
        "rows",
        "input_type",
    ]
    serializer_field_names = [
        "label",
        "default_value",
        "required",
        "validation_type",
        "placeholder",
        "is_multiline",
        "rows",
        "input_type",
    ]
    simple_formula_fields = ["label", "default_value", "placeholder"]

    class SerializedDict(ElementDict):
        label: BaserowFormulaObject
        required: bool
        validation_type: str
        placeholder: str
        default_value: BaserowFormulaObject
        is_multiline: bool
        rows: int
        input_type: str

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            InputThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "label": FormulaSerializerField(
                help_text=InputTextElement._meta.get_field("label").help_text,
            ),
            "default_value": FormulaSerializerField(
                help_text=InputTextElement._meta.get_field("default_value").help_text,
            ),
            "required": serializers.BooleanField(
                help_text=InputTextElement._meta.get_field("required").help_text,
                default=False,
                required=False,
            ),
            "placeholder": FormulaSerializerField(
                help_text=InputTextElement._meta.get_field("placeholder").help_text
            ),
            "is_multiline": serializers.BooleanField(
                help_text=InputTextElement._meta.get_field("is_multiline").help_text,
                required=False,
                default=False,
            ),
            "rows": serializers.IntegerField(
                help_text=InputTextElement._meta.get_field("rows").help_text,
                required=False,
                default=3,
                min_value=1,
                max_value=100,
            ),
            "input_type": serializers.ChoiceField(
                choices=INPUT_TEXT_TYPES.choices,
                help_text=InputTextElement._meta.get_field("input_type").help_text,
                required=False,
                default=INPUT_TEXT_TYPES.TEXT,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="input",
                theme_config_block_type_name=InputThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
            ),
        }

        return overrides

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "label": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "required": False,
            "placeholder": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "default_value": BaserowFormulaObject(
                formula="'Corporis perspiciatis'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "is_multiline": False,
            "rows": 1,
            "input_type": "text",
        }

    def is_valid(
        self, element: InputTextElement, value: Any, dispatch_context: DispatchContext
    ) -> Any:
        """
        :param element: The element we're trying to use form data in.
        :param value: The form data value, which may be invalid.
        :return: Whether the value is valid or not for this element.
        """

        if not value:
            if element.required:
                raise ValueError("The value is required")

        elif element.validation_type == "integer":
            try:
                return ensure_numeric(value)
            except (InvalidOperation, ValidationError) as exc:
                raise TypeError(f"{value} is not a valid number") from exc

        elif element.validation_type == "email":
            try:
                validate_email(value)
            except ValidationError as exc:
                raise ValueError(f"{value} is not a valid email") from exc
        return value


class ButtonElementType(ElementType):
    type = "button"
    model_class = ButtonElement
    allowed_fields = ["value"]
    serializer_field_names = ["value"]
    simple_formula_fields = ["value"]

    class SerializedDict(ElementDict):
        value: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ButtonThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "value": FormulaSerializerField(
                help_text=ButtonElement._meta.get_field("value").help_text,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="button",
                theme_config_block_type_name=ButtonThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
            ),
        }

        return overrides

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {
            "value": BaserowFormulaObject(
                formula="'Some value'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            )
        }


class CheckboxElementType(InputElementType):
    type = "checkbox"
    model_class = CheckboxElement
    allowed_fields = ["label", "default_value", "required"]
    serializer_field_names = ["label", "default_value", "required"]
    simple_formula_fields = ["label", "default_value"]

    class SerializedDict(ElementDict):
        label: BaserowFormulaObject
        required: bool
        default_value: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            InputThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "label": FormulaSerializerField(
                help_text=CheckboxElement._meta.get_field("label").help_text,
            ),
            "default_value": FormulaSerializerField(
                help_text=CheckboxElement._meta.get_field("default_value").help_text,
            ),
            "required": serializers.BooleanField(
                help_text=CheckboxElement._meta.get_field("required").help_text,
                default=False,
                required=False,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="input",
                theme_config_block_type_name=InputThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
            ),
        }

        return overrides

    def is_valid(
        self, element: CheckboxElement, value: Any, dispatch_context: DispatchContext
    ) -> bool:
        if element.required and not value:
            raise ValueError("The value is required")

        try:
            return ensure_boolean(value)
        except ValidationError as exc:
            raise ValueError(
                "The value must be a boolean or convertible to a boolean"
            ) from exc

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "label": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "required": False,
            "default_value": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
        }


class ChoiceElementType(FormElementTypeMixin, ElementType):
    type = "choice"
    model_class = ChoiceElement
    allowed_fields = [
        "label",
        "default_value",
        "required",
        "placeholder",
        "multiple",
        "show_as_dropdown",
        "option_type",
        "formula_value",
        "formula_name",
    ]
    serializer_field_names = [
        "label",
        "default_value",
        "required",
        "placeholder",
        "options",
        "multiple",
        "show_as_dropdown",
        "option_type",
        "formula_value",
        "formula_name",
    ]
    request_serializer_field_names = [
        "label",
        "default_value",
        "required",
        "placeholder",
        "options",
        "multiple",
        "show_as_dropdown",
        "option_type",
        "formula_value",
        "formula_name",
    ]
    simple_formula_fields = [
        "label",
        "default_value",
        "placeholder",
        "formula_value",
        "formula_name",
    ]

    class SerializedDict(ElementDict):
        label: BaserowFormulaObject
        required: bool
        placeholder: BaserowFormulaObject
        default_value: BaserowFormulaObject
        options: List
        multiple: bool
        show_as_dropdown: bool
        option_type: str
        formula_value: BaserowFormulaObject
        formula_name: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            InputThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "label": FormulaSerializerField(
                help_text=ChoiceElement._meta.get_field("label").help_text,
            ),
            "default_value": FormulaSerializerField(
                help_text=ChoiceElement._meta.get_field("default_value").help_text,
            ),
            "required": serializers.BooleanField(
                help_text=ChoiceElement._meta.get_field("required").help_text,
                default=False,
                required=False,
            ),
            "placeholder": FormulaSerializerField(
                help_text=ChoiceElement._meta.get_field("placeholder").help_text
            ),
            "options": ChoiceOptionSerializer(
                source="choiceelementoption_set", many=True, required=False
            ),
            "multiple": serializers.BooleanField(
                help_text=ChoiceElement._meta.get_field("multiple").help_text,
                default=False,
                required=False,
            ),
            "show_as_dropdown": serializers.BooleanField(
                help_text=ChoiceElement._meta.get_field("show_as_dropdown").help_text,
                default=True,
                required=False,
            ),
            "option_type": serializers.ChoiceField(
                choices=ChoiceElement.OPTION_TYPE.choices,
                help_text=ChoiceElement._meta.get_field("option_type").help_text,
                required=False,
                default=ChoiceElement.OPTION_TYPE.MANUAL,
            ),
            "formula_value": FormulaSerializerField(
                help_text=ChoiceElement._meta.get_field("formula_value").help_text,
            ),
            "formula_name": FormulaSerializerField(
                help_text=ChoiceElement._meta.get_field("formula_name").help_text,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="input",
                theme_config_block_type_name=InputThemeConfigBlockType.type,
                serializer_kwargs={"required": False},
            ),
        }

        return overrides

    @property
    def request_serializer_field_overrides(self):
        return {
            **self.serializer_field_overrides,
            "options": ChoiceOptionSerializer(many=True, required=False),
        }

    def serialize_property(
        self,
        element: ChoiceElement,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "options":
            return [
                self.serialize_option(option)
                for option in element.choiceelementoption_set.all()
            ]

        return super().serialize_property(
            element, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> T:
        choice_element = super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        options = []
        for option in serialized_values.get("options", []):
            option["choice_id"] = choice_element.id
            option_deserialized = self.deserialize_option(option)
            options.append(option_deserialized)

        ChoiceElementOption.objects.bulk_create(options)

        return choice_element

    def create_instance_from_serialized(
        self,
        serialized_values: Dict[str, Any],
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> T:
        serialized_values.pop("options", None)
        return super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def serialize_option(self, option: ChoiceElementOption) -> Dict:
        return {
            "value": option.value,
            "name": option.name,
            "choice_id": option.choice_id,
        }

    def deserialize_option(self, value: Dict):
        return ChoiceElementOption(**value)

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {
            "label": BaserowFormulaObject(
                formula="'test'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "default_value": BaserowFormulaObject(
                formula="'option 1'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "required": False,
            "placeholder": BaserowFormulaObject(
                formula="'some placeholder'",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "multiple": False,
            "show_as_dropdown": True,
            "option_type": ChoiceElement.OPTION_TYPE.MANUAL,
            "formula_value": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "formula_name": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
        }

    def after_create(self, instance: ChoiceElement, values: Dict):
        options = values.get("options", [])

        ChoiceElementOption.objects.bulk_create(
            [ChoiceElementOption(choice=instance, **option) for option in options]
        )

    def after_update(
        self, instance: ChoiceElement, values: Dict, changes: Dict[str, Tuple]
    ):
        options = values.get("options", None)

        if options is not None:
            ChoiceElementOption.objects.filter(choice=instance).delete()
            ChoiceElementOption.objects.bulk_create(
                [ChoiceElementOption(choice=instance, **option) for option in options]
            )

    def is_valid(
        self,
        element: ChoiceElement,
        value: Union[List, str],
        dispatch_context: DispatchContext,
    ) -> str:
        """
        Responsible for validating `ChoiceElement` form data. We handle
        this validation a little differently to ensure that if someone creates
        an option with a blank value, it's considered valid.

        :param element: The choice element.
        :param value: The choice value we want to validate.
        :return: The value if it is valid for this element.
        """

        options_tuple = set(
            element.choiceelementoption_set.values_list("value", "name")
        )
        options = [
            value if value is not None else name for (value, name) in options_tuple
        ]

        if element.option_type == ChoiceElement.OPTION_TYPE.FORMULAS:
            options = ensure_array(
                resolve_formula(
                    element.formula_value,
                    formula_runtime_function_registry,
                    dispatch_context,
                )
            )
            options = [ensure_string_or_integer(option) for option in options]

        if element.multiple:
            try:
                value = ensure_array(value)
            except ValidationError as exc:
                raise ValueError(
                    "The value must be an array or convertible to an array"
                ) from exc

            if not value:
                if element.required:
                    raise ValueError("The value is required")
            else:
                for v in value:
                    if v not in options:
                        raise ValueError(f"{value} is not a valid option")
        else:
            if not value:
                if element.required and value not in options:
                    raise ValueError("The value is required")
            elif value not in options:
                raise ValueError(f"{value} is not a valid option")

        return value


class IFrameElementType(ElementType):
    type = "iframe"
    model_class = IFrameElement
    allowed_fields = ["source_type", "url", "embed", "height"]
    serializer_field_names = ["source_type", "url", "embed", "height"]
    simple_formula_fields = ["url", "embed"]

    class SerializedDict(ElementDict):
        source_type: str
        url: BaserowFormulaObject
        embed: BaserowFormulaObject
        height: int

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "source_type": serializers.ChoiceField(
                help_text=IFrameElement._meta.get_field("source_type").help_text,
                required=False,
                choices=IFrameElement.IFRAME_SOURCE_TYPE.choices,
                default=IFrameElement.IFRAME_SOURCE_TYPE.URL,
            ),
            "url": FormulaSerializerField(
                help_text=IFrameElement._meta.get_field("url").help_text,
            ),
            "embed": FormulaSerializerField(
                help_text=IFrameElement._meta.get_field("embed").help_text,
            ),
            "height": serializers.IntegerField(
                help_text=IFrameElement._meta.get_field("height").help_text,
                required=False,
                default=300,
                min_value=1,
                max_value=2000,
            ),
        }

        return overrides

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "source_type": IFrameElement.IFRAME_SOURCE_TYPE.URL,
            "url": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "embed": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "height": 300,
        }


class DateTimePickerElementType(FormElementTypeMixin, ElementType):
    type = "datetime_picker"
    model_class = DateTimePickerElement
    allowed_fields = [
        "label",
        "required",
        "default_value",
        "date_format",
        "include_time",
        "time_format",
    ]
    serializer_field_names = [
        "label",
        "required",
        "default_value",
        "date_format",
        "include_time",
        "time_format",
    ]
    simple_formula_fields = [
        "label",
        "default_value",
    ]

    class SerializedDict(ElementDict):
        label: BaserowFormulaObject
        required: bool
        default_value: BaserowFormulaObject
        date_format: str
        include_time: bool
        time_format: str

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "label": FormulaSerializerField(
                help_text=DateTimePickerElement._meta.get_field("label").help_text,
            ),
            "required": serializers.BooleanField(
                help_text=DateTimePickerElement._meta.get_field("required").help_text,
                default=False,
                required=False,
            ),
            "default_value": FormulaSerializerField(
                help_text=DateTimePickerElement._meta.get_field(
                    "default_value"
                ).help_text
            ),
            "date_format": serializers.ChoiceField(
                help_text=DateTimePickerElement._meta.get_field(
                    "date_format"
                ).help_text,
                choices=DATE_FORMAT_CHOICES,
                default="EU",
            ),
            "include_time": serializers.BooleanField(
                help_text=DateTimePickerElement._meta.get_field(
                    "include_time"
                ).help_text,
                default=False,
                required=False,
            ),
            "time_format": serializers.ChoiceField(
                help_text=DateTimePickerElement._meta.get_field(
                    "time_format"
                ).help_text,
                choices=DATE_TIME_FORMAT_CHOICES,
                default="24",
            ),
        }
        return overrides

    def is_valid(
        self,
        element: DateTimePickerElement,
        value: Any,
        dispatch_context: DispatchContext,
    ) -> FormattedDate | FormattedDateTime | None:
        """
        Validate the upcoming date value.

        :param element: The datetime picker element.
        :param value: The datetime value we want to validate.
        :param dispatch_context: The context this element was dispatched with.
        :return: The value if it is valid for this element.
        """

        super().is_valid(element, value, dispatch_context)

        if value:
            try:
                value = datetime.fromisoformat(value)
                date_format = DATE_FORMAT[element.date_format]["format"]
                time_format = DATE_TIME_FORMAT[element.time_format]["format"]
                return (
                    FormattedDateTime(value, f"{date_format} {time_format}")
                    if element.include_time
                    else FormattedDate(value, date_format)
                )
            except ValueError as exc:
                msg = f"'{value}' is not a valid date"
                raise ValueError(msg) from exc

        return value

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {
            "required": False,
            "label": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "default_value": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "date_format": DATE_FORMAT_CHOICES[0][0],
            "include_time": False,
            "time_format": DATE_TIME_FORMAT_CHOICES[0][0],
        }


class MultiPageContainerElementType(
    ContainerElementTypeMixin, MultiPageElementTypeMixin, ElementType
):
    """
    A base class container element that can be displayed on multiple pages.
    """

    class SerializedDict(
        MultiPageElementTypeMixin.SerializedDict,
        ContainerElementTypeMixin.SerializedDict,
    ):
        ...


class HeaderElementType(MultiPageContainerElementType):
    """
    A container element that can be displayed on multiple pages.
    """

    type = "header"
    model_class = HeaderElement


class FooterElementType(MultiPageContainerElementType):
    """
    A container element that can be displayed on multiple pages.
    """

    type = "footer"
    model_class = FooterElement


class MenuElementType(ElementType):
    """
    A Menu element that provides navigation capabilities to the application.
    """

    type = "menu"
    model_class = MenuElement
    serializer_field_names = ["orientation", "alignment", "menu_items"]
    allowed_fields = ["orientation", "alignment"]

    serializer_mixins = [NestedMenuItemsMixin]
    request_serializer_mixins = []

    class SerializedDict(ElementDict):
        orientation: str
        alignment: str
        menu_items: List[Dict]

    @property
    def serializer_field_overrides(self) -> Dict[str, Any]:
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ButtonThemeConfigBlockType,
            LinkThemeConfigBlockType,
        )

        overrides = {
            **super().serializer_field_overrides,
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_name="menu",
                theme_config_block_type_name=[
                    [ButtonThemeConfigBlockType.type, LinkThemeConfigBlockType.type]
                ],
                serializer_kwargs={"required": False},
            ),
        }
        return overrides

    @property
    def request_serializer_field_overrides(self) -> Dict[str, Any]:
        return {
            **self.serializer_field_overrides,
            "menu_items": MenuItemSerializer(many=True, required=False),
        }

    def enhance_queryset(
        self, queryset: QuerySet[MenuItemElement]
    ) -> QuerySet[MenuItemElement]:
        return queryset.prefetch_related("menu_items")

    def before_delete(self, instance: MenuElement) -> None:
        """
        Handle any clean-up needed before the MenuElement is deleted.

        Deletes all related objects of this MenuElement instance such as Menu
        Items and Workflow actions.
        """

        self.delete_workflow_actions(instance)
        instance.menu_items.all().delete()

    def after_create(self, instance: MenuItemElement, values: Dict[str, Any]) -> None:
        """
        After a MenuElement is created, MenuItemElements are bulk-created
        using the information in the "menu_items" array.
        """

        menu_items = values.get("menu_items", [])

        created_menu_items = MenuItemElement.objects.bulk_create(
            [
                MenuItemElement(**item, menu_item_order=index)
                for index, item in enumerate(menu_items)
            ]
        )
        instance.menu_items.add(*created_menu_items)

    def delete_workflow_actions(
        self, instance: MenuElement, menu_item_uids_to_keep: Optional[List[str]] = None
    ) -> None:
        """
        Deletes all Workflow actions related to a specific MenuElement instance.

        :param instance: The MenuElement instance for which related Workflow
            actions will be deleted.
        :param menu_item_uids_to_keep: An optional list of UUIDs. If a related
            Workflow action matches a UUID in this list, it will *not* be deleted.
        :return: None
        """

        # Get all workflow actions associated with this menu element.
        all_workflow_actions = BuilderWorkflowAction.objects.filter(element=instance)

        # If there are menu items, only keep workflow actions that match
        # existing menu items.
        if menu_item_uids_to_keep:
            workflow_actions_to_keep_query = Q()
            for uid in menu_item_uids_to_keep:
                workflow_actions_to_keep_query |= Q(event__startswith=uid)

            # Find Workflow actions to delete (those not matching any
            # current Menu Item).
            workflow_actions_to_delete = all_workflow_actions.exclude(
                workflow_actions_to_keep_query
            )
        else:
            # Since there are no Menu Items, delete all Workflow actions
            # for this element.
            workflow_actions_to_delete = all_workflow_actions

        # Delete the workflow actions that are no longer associated with
        # any menu item.
        if workflow_actions_to_delete.exists():
            workflow_actions_to_delete.delete()

    def after_update(self, instance: MenuElement, values, changes: Dict[str, Tuple]):
        """
        After the element has been updated we need to update the fields.

        :param instance: The instance of the element that has been updated.
        :param values: The values that have been updated.
        :param changes: A dictionary containing all changes which were made to the
            collection element prior to `after_update` being called.
        :return: None
        """

        if "menu_items" in values:
            instance.menu_items.all().delete()

            menu_item_uids_to_keep = [item["uid"] for item in values["menu_items"]]
            self.delete_workflow_actions(instance, menu_item_uids_to_keep)

            items_to_create = []
            child_uids_parent_uids = {}

            keys_to_remove = ["parent_menu_item", "menu_item_order"]
            for index, item in enumerate(values["menu_items"]):
                for key in keys_to_remove:
                    item.pop(key, None)

                # Keep track of child-parent relationship via the uid
                for child_index, child in enumerate(item.pop("children", [])):
                    for key in keys_to_remove + ["children"]:
                        child.pop(key, None)

                    items_to_create.append(
                        MenuItemElement(**child, menu_item_order=child_index)
                    )
                    child_uids_parent_uids[str(child["uid"])] = str(item["uid"])

                items_to_create.append(MenuItemElement(**item, menu_item_order=index))

            created_items = MenuItemElement.objects.bulk_create(items_to_create)
            instance.menu_items.add(*created_items)

            # Re-associate the child-parent
            for item in instance.menu_items.all():
                if parent_uid := child_uids_parent_uids.get(str(item.uid)):
                    parent_item = instance.menu_items.filter(uid=parent_uid).first()
                    item.parent_menu_item = parent_item
                    item.save()

        super().after_update(instance, values, changes)

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "orientation": RepeatElement.ORIENTATIONS.VERTICAL,
            "alignment": HorizontalAlignments.LEFT,
        }

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        if prop_name == "menu_items":
            updated_menu_items = []
            for item in value:
                updated = {}
                for item_key, item_value in item.items():
                    new_value = super().deserialize_property(
                        item_key,
                        NavigationElementManager().deserialize_property(
                            item_key, item_value, id_mapping, **kwargs
                        ),
                        id_mapping,
                        files_zip=files_zip,
                        storage=storage,
                        cache=cache,
                        **kwargs,
                    )
                    updated[item_key] = new_value
                updated_menu_items.append(updated)
            return updated_menu_items

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def serialize_property(
        self,
        element: MenuElement,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        if prop_name == "menu_items":
            return MenuItemSerializer(
                element.menu_items.all(),
                many=True,
            ).data

        return super().serialize_property(
            element,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def create_instance_from_serialized(
        self,
        serialized_values: Dict[str, Any],
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> MenuElement:
        menu_items = serialized_values.pop("menu_items", [])

        instance = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        menu_items_to_create = []
        child_uids_parent_uids = {}

        # Generate new uids to prevent conflicts
        updated_uids = {i["uid"]: str(uuid.uuid4()) for i in menu_items}

        ids_uids = {i["id"]: i["uid"] for i in menu_items}
        keys_to_remove = ["id", "menu_item_order", "children"]

        for index, item in enumerate(menu_items):
            for key in keys_to_remove:
                item.pop(key, None)

            old_uid = item.pop("uid")
            new_uid = updated_uids[old_uid]

            # Keep track of child-parent relationship via the uid
            if parent_id := item.pop("parent_menu_item", None):
                child_uids_parent_uids[new_uid] = updated_uids[ids_uids[parent_id]]

            # Map the old uid to the new uid. This ensures that any workflow
            # actions with an `event` pointing to the old uid will have the
            # pointer to the new uid.
            id_mapping["builder_element_event_uids"][old_uid] = new_uid

            menu_items_to_create.append(
                MenuItemElement(**item, uid=new_uid, menu_item_order=index)
            )

        created_menu_items = MenuItemElement.objects.bulk_create(menu_items_to_create)
        instance.menu_items.add(*created_menu_items)

        # Re-associate the child-parent
        for item in instance.menu_items.all():
            if parent_uid := child_uids_parent_uids.get(str(item.uid)):
                parent_item = instance.menu_items.filter(uid=parent_uid).first()
                item.parent_menu_item = parent_item
                item.save()

        return instance

    def formula_generator(
        self, element: Element
    ) -> Generator[str | Instance, str, None]:
        """
        Generator that returns formula fields for the MenuElementType.

        The MenuElement has a menu_items field, which is a many-to-many
        relationship with MenuItemElement. The MenuItemElement has navigation
        related fields like page_parameters, yet does not have a type of its
        own.

        This method ensures that any formulas found inside MenuItemElements
        are extracted correctly. It ensures that when a formula is declared
        in page_parameters, etc, the resolved formula value is available
        in the frontend.
        """

        yield from super().formula_generator(element)

        for item in element.menu_items.all():
            for index, data in enumerate(item.page_parameters or []):
                new_formula = yield BaserowFormulaObject.to_formula(data["value"])
                if new_formula is not None:
                    item.page_parameters[index]["value"] = new_formula
                    yield item

            for index, data in enumerate(item.query_parameters or []):
                new_formula = yield BaserowFormulaObject.to_formula(data["value"])
                if new_formula is not None:
                    item.query_parameters[index]["value"] = new_formula
                    yield item

            for formula_field in NavigationElementManager.simple_formula_fields:
                new_formula = yield BaserowFormulaObject.to_formula(
                    getattr(item, formula_field, "")
                )
                if new_formula is not None:
                    setattr(item, formula_field, new_formula)
                    yield item
