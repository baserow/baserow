import uuid
from typing import TYPE_CHECKING, List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import SET_NULL, QuerySet
from django.utils.functional import lazy

from baserow.contrib.builder.constants import (
    BACKGROUND_IMAGE_MODES,
    COLOR_FIELD_MAX_LENGTH,
    HorizontalAlignments,
    VerticalAlignments,
)
from baserow.core.constants import (
    DATE_FORMAT_CHOICES,
    DATE_TIME_FORMAT_CHOICES,
    RatingStyleChoices,
)
from baserow.core.formula.field import FormulaField, JSONFormulaField
from baserow.core.formula.serializers import collect_json_formula_field_properties
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    FractionOrderableMixin,
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)
from baserow.core.user_files.models import UserFile

if TYPE_CHECKING:
    from baserow.contrib.builder.pages.models import Page


class BackgroundTypes(models.TextChoices):
    NONE = "none"
    COLOR = "color"
    IMAGE = "image"


class WidthTypes(models.TextChoices):
    FULL = "full"
    FULL_WIDTH = "full-width"
    NORMAL = "normal"
    MEDIUM = "medium"
    SMALL = "small"


class ChildWidthTypes(models.TextChoices):
    NORMAL = "normal"
    MEDIUM = "medium"
    SMALL = "small"


class INPUT_TEXT_TYPES(models.TextChoices):
    TEXT = "text"
    PASSWORD = "password"  # nosec bandit B105


def get_default_element_content_type():
    return ContentType.objects.get_for_model(Element)


def get_default_table_orientation():
    return {
        "smartphone": "horizontal",
        "tablet": "horizontal",
        "desktop": "horizontal",
    }


def get_collection_field_config_formula_properties() -> List[str]:
    """
    Returns the list of properties in the collection field config that are formulas.
    :return: A list of property names.
    """

    from baserow.contrib.builder.elements.registries import (
        collection_field_type_registry,
    )

    return collect_json_formula_field_properties(collection_field_type_registry)


class Element(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    FractionOrderableMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
    models.Model,
):
    """
    This model represents a page element. An element is a piece of the page that
    display an information or something the user can interact with.
    """

    class VISIBILITY_TYPES(models.TextChoices):
        ALL = "all"
        LOGGED_IN = "logged-in"
        NOT_LOGGED = "not-logged"

    class ROLE_TYPES(models.TextChoices):
        ALLOW_ALL = "allow_all"
        ALLOW_ALL_EXCEPT = "allow_all_except"
        DISALLOW_ALL_EXCEPT = "disallow_all_except"

    page = models.ForeignKey("builder.Page", on_delete=models.CASCADE)
    order = models.DecimalField(
        help_text="Lowest first.",
        max_digits=40,
        decimal_places=20,
        editable=False,
        default=1,
    )
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="page_elements",
        on_delete=models.SET(get_default_element_content_type),
    )
    # This is used for container elements, if NULL then this is a root element
    parent_element = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        default=None,
        help_text="The parent element, if inside a container.",
        related_name="children",
    )

    role_type = models.CharField(
        choices=ROLE_TYPES.choices,
        max_length=19,
        default=ROLE_TYPES.ALLOW_ALL,
        db_index=True,
    )
    roles = models.JSONField(
        default=list,
        help_text="User roles associated with this element, used in conjunction with role_type.",
    )

    # The following fields are used to store the position of the element in the
    # container. If the element is a root element then this is null.
    place_in_container = models.CharField(
        null=True,
        blank=True,
        default=None,
        max_length=255,
        help_text="The place in the container.",
    )

    visibility = models.CharField(
        choices=VISIBILITY_TYPES.choices,
        max_length=20,
        default=VISIBILITY_TYPES.ALL,
        db_index=True,
    )

    visibility_condition = FormulaField(
        help_text="Change element visibility depending on a formula value"
    )

    styles = models.JSONField(
        default=dict,
        help_text="The theme overrides for this element",
    )

    css_classes = models.CharField(
        max_length=255,
        default="",
        db_default="",
        blank=True,
        help_text="The additional CSS classes for this element.",
    )

    style_border_top_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="border",
        blank=True,
        help_text="Top border color.",
    )
    style_border_top_size = models.PositiveIntegerField(
        default=0, help_text="Pixel height of the top border."
    )
    style_padding_top = models.PositiveIntegerField(
        default=10, help_text="Padding size of the top border."
    )
    style_margin_top = models.PositiveIntegerField(
        default=0,
        help_text="Margin size of the top border.",
    )

    style_border_bottom_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="border",
        blank=True,
        help_text="Bottom border color",
    )
    style_border_bottom_size = models.PositiveIntegerField(
        default=0, help_text="Pixel height of the bottom border."
    )
    style_padding_bottom = models.PositiveIntegerField(
        default=10, help_text="Padding size of the bottom border."
    )
    style_margin_bottom = models.PositiveIntegerField(
        default=0,
        help_text="Margin size of the bottom border.",
    )

    style_border_left_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="border",
        blank=True,
        help_text="Left border color",
    )
    style_border_left_size = models.PositiveIntegerField(
        default=0, help_text="Pixel height of the left border."
    )
    style_padding_left = models.PositiveIntegerField(
        default=20, help_text="Padding size of the left border."
    )
    style_margin_left = models.PositiveIntegerField(
        default=0,
        help_text="Margin size of the left border.",
    )

    style_border_right_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="border",
        blank=True,
        help_text="Right border color",
    )
    style_border_right_size = models.PositiveIntegerField(
        default=0, help_text="Pixel height of the right border."
    )
    style_padding_right = models.PositiveIntegerField(
        default=20, help_text="Padding size of the right border."
    )
    style_margin_right = models.PositiveIntegerField(
        default=0,
        help_text="Margin size of the right border.",
    )

    style_background_radius = models.SmallIntegerField(
        default=0, db_default=0, help_text="Background radius."
    )
    style_border_radius = models.SmallIntegerField(
        default=0, db_default=0, help_text="Border radius."
    )

    style_background = models.CharField(
        choices=BackgroundTypes.choices,
        default=BackgroundTypes.NONE,
        help_text="What type of background the element should have.",
        max_length=20,
    )
    style_background_color = models.CharField(
        max_length=COLOR_FIELD_MAX_LENGTH,
        default="#ffffffff",
        blank=True,
        help_text="The background color if `style_background` is color.",
    )

    style_background_file = models.ForeignKey(
        UserFile,
        null=True,
        on_delete=models.SET_NULL,
        related_name="element_background_image_file",
        help_text="An image file uploaded by the user to be used as element background",
    )

    style_background_mode = models.CharField(
        help_text="The mode of the background image",
        choices=BACKGROUND_IMAGE_MODES.choices,
        max_length=32,
        default=BACKGROUND_IMAGE_MODES.FILL,
    )

    style_width = models.CharField(
        choices=WidthTypes.choices,
        default=WidthTypes.NORMAL,
        help_text="Indicates the width of the root element.",
        max_length=20,
    )

    style_width_child = models.CharField(
        choices=ChildWidthTypes.choices,
        default=ChildWidthTypes.NORMAL,
        db_default=ChildWidthTypes.NORMAL,
        help_text="Indicates the width of the child element.",
        max_length=6,
    )

    class Meta:
        ordering = ("order", "id")

    @staticmethod
    def get_type_registry():
        from .registries import element_type_registry

        return element_type_registry

    def get_parent(self):
        return self.page

    def get_sibling_elements(self):
        return Element.objects.filter(
            parent_element=self.parent_element, page=self.page
        ).exclude(id=self.id)

    @property
    def is_root_element(self):
        return self.parent_element is None

    @classmethod
    def get_last_order(
        cls,
        page: "Page",
        parent_element_id: Optional[int] = None,
        place_in_container: Optional[str] = None,
    ):
        """
        Returns the last order for the given page.

        :param page: The page we want the order for.
        :param base_queryset: The base queryset to use.
        :return: The last order.
        """

        return cls.get_last_orders(page, parent_element_id, place_in_container)[0]

    @classmethod
    def get_last_orders(
        cls,
        page: "Page",
        parent_element_id: Optional[int] = None,
        place_in_container: Optional[str] = None,
        amount=1,
    ):
        """
        Returns the last orders for the given page.

        :param page: The page we want the order for.
        :param parent_element_id: The id of the parent element.
        :param place_in_container: The place in the container
        :param amount: The number of orders you wish to have returned
        :return: The last order.
        """

        queryset = Element.objects.filter(page=page)

        queryset = cls._scope_queryset_to_container(
            queryset, parent_element_id, place_in_container
        )

        return cls.get_highest_order_of_queryset(queryset, amount=amount)

    @classmethod
    def get_unique_order_before_element(
        cls, before: "Element", parent_element_id: int, place_in_container: str
    ):
        """
        Returns a safe order value before the given element in the given page.

        :param before: The element before which we want the safe order
        :param parent_element_id: The id of the parent element.
        :param place_in_container: The place in the container
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the items must be recalculated in this
            case before calling this method again.
        :return: The order value.
        """

        queryset = Element.objects.filter(page=before.page)

        queryset = cls._scope_queryset_to_container(
            queryset, parent_element_id, place_in_container
        )

        return cls.get_unique_orders_before_item(before, queryset)[0]

    @classmethod
    def _scope_queryset_to_container(
        cls, queryset: QuerySet, parent_element_id: int, place_in_container: str
    ) -> QuerySet:
        """
        Filters the queryset to only include elements that are in the same container
        as the child element.

        :param queryset: The queryset to filter.
        :param parent_element_id: The ID of the parent element.
        :param place_in_container: The place in container of the child element.
        :return: The filtered queryset.
        """

        if parent_element_id:
            return queryset.filter(
                parent_element_id=parent_element_id,
                place_in_container=place_in_container,
            )
        else:
            return queryset.filter(
                parent_element_id=None,
            )


class ContainerElement(Element):
    """
    Base class for container elements.
    """

    class Meta:
        abstract = True


class ColumnElement(ContainerElement):
    """
    A column element that can contain other elements.
    """

    column_amount = models.IntegerField(
        default=3,
        help_text="The amount of columns inside this column element.",
        validators=[
            MinValueValidator(1, message="Value cannot be less than 0."),
            MaxValueValidator(6, message="Value cannot be greater than 6."),
        ],
    )
    column_gap = models.IntegerField(
        default=20,
        help_text="The amount of space between the columns.",
        validators=[
            MinValueValidator(0, message="Value cannot be less than 0."),
            MaxValueValidator(2000, message="Value cannot be greater than 2000."),
        ],
    )
    alignment = models.CharField(
        choices=VerticalAlignments.choices,
        max_length=10,
        default=VerticalAlignments.TOP,
    )


class HeadingElement(Element):
    """
    A Heading element to display a title.
    """

    class HeadingLevel(models.IntegerChoices):
        H1 = 1
        H2 = 2
        H3 = 3
        H4 = 4
        H5 = 5

    value = FormulaField()
    level = models.IntegerField(
        choices=HeadingLevel.choices, default=1, help_text="The level of the heading"
    )


class TextElement(Element):
    """
    A simple blob of text.
    """

    class TEXT_FORMATS(models.TextChoices):
        PLAIN = "plain"
        MARKDOWN = "markdown"

    value = FormulaField()
    format = models.CharField(
        choices=TEXT_FORMATS.choices,
        help_text="The format of the text",
        max_length=10,
        default=TEXT_FORMATS.PLAIN,
    )


class NavigationElementMixin(models.Model):
    """
    Abstract base class for navigation elements.
    """

    class NAVIGATION_TYPES(models.TextChoices):
        PAGE = "page"
        CUSTOM = "custom"

    class TARGETS(models.TextChoices):
        SELF = "self"
        BLANK = "blank"

    navigation_type = models.CharField(
        choices=NAVIGATION_TYPES.choices,
        help_text="The navigation type.",
        max_length=10,
        default=NAVIGATION_TYPES.PAGE,
        null=True,
    )
    navigate_to_page = models.ForeignKey(
        "builder.Page",
        null=True,
        on_delete=models.SET_NULL,
        help_text=(
            "Destination page id for this link. If null then we use the "
            "navigate_to_url property instead.",
        ),
    )
    navigate_to_url = FormulaField(
        help_text="If no page is selected, this indicate the destination of the link.",
    )
    page_parameters = JSONFormulaField(
        properties=["value"],
        default=list,
        help_text="The parameters for each parameters of the selected page if any.",
        null=True,
    )
    query_parameters = JSONFormulaField(
        properties=["value"],
        db_default=[],
        default=list,
        help_text="The query parameters for each parameter of the selected page if any.",
        null=True,
    )
    target = models.CharField(
        choices=TARGETS.choices,
        help_text="The target of the link when we click on it.",
        max_length=10,
        default=TARGETS.SELF,
        null=True,
    )

    class Meta:
        abstract = True


class LinkElement(Element, NavigationElementMixin):
    """
    A simple link.
    """

    class VARIANTS(models.TextChoices):
        LINK = "link"
        BUTTON = "button"

    value = FormulaField()
    variant = models.CharField(
        choices=VARIANTS.choices,
        help_text="The variant of the link.",
        max_length=10,
        default=VARIANTS.LINK,
    )


class ImageElement(Element):
    """
    A simple image element that can display an image either through a remote source
    or via an uploaded file
    """

    class IMAGE_SOURCE_TYPES(models.TextChoices):
        UPLOAD = "upload"
        URL = "url"

    class IMAGE_CONSTRAINT_TYPES(models.TextChoices):
        COVER = "cover"
        CONTAIN = "contain"
        FULL_WIDTH = "full-width"

    image_source_type = models.CharField(
        choices=IMAGE_SOURCE_TYPES.choices,
        max_length=32,
        default=IMAGE_SOURCE_TYPES.UPLOAD,
    )
    image_file = models.ForeignKey(
        UserFile,
        null=True,
        on_delete=models.SET_NULL,
        related_name="image_element_image_file",
        help_text="An image file uploaded by the user to be used by the element",
    )
    image_url = FormulaField(help_text="A link to the image file")
    alt_text = FormulaField(
        help_text="Text that is displayed when the image can't load"
    )


class FormContainerElement(ContainerElement):
    """
    A form element
    """

    submit_button_label = FormulaField()
    reset_initial_values_post_submission = models.BooleanField(
        default=False,
        help_text="Whether to reset the form to using its initial "
        "values after a successful form submission.",
    )


class FormElement(Element):
    """
    The base form element, which can be extended to
    support an element for each supported type.
    """

    required = models.BooleanField(
        default=False, help_text="Whether this form element is a required field."
    )

    class Meta:
        abstract = True


class BaseRatingElement(Element):
    """
    A Rating element to display a rating.
    """

    value = FormulaField()

    max_value = models.PositiveSmallIntegerField(
        default=5,
        help_text="Maximum value the rating can take.",
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    color = models.CharField(
        max_length=50,
        blank=False,
        help_text="Color of the symbols.",
        default="primary",
    )
    rating_style = models.CharField(
        choices=RatingStyleChoices,
        default=RatingStyleChoices.STAR,
        max_length=50,
        blank=False,
        help_text=(
            "Rating style. Allowed values: "
            f"{', '.join([value for value in RatingStyleChoices.values])}."
        ),
    )

    class Meta:
        abstract = True


class RatingElement(BaseRatingElement):
    pass


class RatingInputElement(BaseRatingElement, FormElement):
    label = FormulaField(
        help_text="The text label for this field",
    )


class InputTextElement(FormElement):
    """
    An input element of text type.
    """

    class INPUT_TEXT_VALIDATION_TYPES(models.TextChoices):
        ANY = "any"
        EMAIL = "email"
        INTEGER = "integer"

    label = FormulaField(
        help_text="The text label for this input",
    )
    default_value = FormulaField(help_text="This text input's default value.")
    validation_type = models.CharField(
        max_length=15,
        choices=INPUT_TEXT_VALIDATION_TYPES.choices,
        default=INPUT_TEXT_VALIDATION_TYPES.ANY,
        help_text="Optionally set the validation type to use when applying form data.",
    )
    placeholder = FormulaField(
        help_text="The placeholder text which should be applied to the element.",
    )
    is_multiline = models.BooleanField(
        default=False,
        help_text="Whether this text input is multiline.",
    )
    rows = models.PositiveIntegerField(
        default=3,
        help_text="Number of rows displayed by the rendered input element",
    )
    input_type = models.CharField(
        max_length=10,
        choices=INPUT_TEXT_TYPES.choices,
        default=INPUT_TEXT_TYPES.TEXT,
        help_text="The type of the input, not applicable for multiline inputs.",
    )


class ChoiceElement(FormElement):
    class OPTION_TYPE(models.TextChoices):
        MANUAL = "manual"
        FORMULAS = "formulas"

    label = FormulaField(
        help_text="The text label for this choice",
    )
    default_value = FormulaField(
        help_text="This choice's input default value.",
    )
    placeholder = FormulaField(
        help_text="The placeholder text which should be applied to the element.",
    )
    multiple = models.BooleanField(
        default=False,
        help_text="Whether this choice allows users to choose multiple values.",
    )
    show_as_dropdown = models.BooleanField(
        default=True,
        help_text="Whether to show the choices as a dropdown.",
    )
    option_type = models.CharField(
        choices=OPTION_TYPE.choices,
        max_length=32,
        default=OPTION_TYPE.MANUAL,
    )
    formula_value = FormulaField(
        help_text="The value of the option if it is a formula",
    )
    formula_name = FormulaField(
        help_text="The display name of the option if it is a formula",
    )


class ChoiceElementOption(models.Model):
    value = models.TextField(
        null=True,
        blank=True,
        default="",
        help_text=(
            "The value of the option. An empty string is a valid value. When "
            "the value field is null, the frontend will auto-populate the "
            "value using the name field."
        ),
    )
    name = models.TextField(
        blank=True,
        default="",
        help_text="The display name of the option",
    )
    choice = models.ForeignKey(
        ChoiceElement,
        on_delete=models.CASCADE,
    )


class CheckboxElement(FormElement):
    """
    A checkbox element.
    """

    label = FormulaField(
        help_text="The text label for this input",
    )
    default_value = FormulaField(help_text="The input's default value.")


class ButtonElement(Element):
    """
    A button element
    """

    value = FormulaField(help_text="The caption of the button.")


class CollectionField(models.Model):
    """
    A field of a Collection element
    """

    uid = models.UUIDField(default=uuid.uuid4)
    order = models.PositiveIntegerField()
    name = models.CharField(
        max_length=225, help_text="The name of the field.", blank=True
    )

    type = models.CharField(
        max_length=225,
        help_text="The type of the field.",
    )

    config = JSONFormulaField(
        default=dict,
        properties=lazy(get_collection_field_config_formula_properties, list)(),
        help_text="The configuration of the field.",
    )

    styles = models.JSONField(
        default=dict,
        help_text="The theme overrides for this field",
        null=True,  # TODO zdm remove me after 1.27
    )

    def get_type(self):
        """Returns the type for this model instance"""

        from .registries import collection_field_type_registry

        return collection_field_type_registry.get(self.type)

    class Meta:
        ordering = ("order", "id")


class CollectionElement(Element):
    data_source = models.ForeignKey(
        "builder.DataSource",
        null=True,
        on_delete=SET_NULL,
        help_text="The data source we want to show in the element for. "
        "Only data_sources that return list are allowed.",
    )

    schema_property = models.CharField(
        max_length=225,
        null=True,
        help_text="A multiple valued schema property to use for the data source.",
    )

    items_per_page = models.PositiveIntegerField(
        default=20,
        help_text="The amount item loaded with each page.",
        validators=[
            MinValueValidator(1, message="Value cannot be less than 1."),
        ],
    )

    button_load_more_label = FormulaField(
        help_text="The label of the show more button",
    )

    class Meta:
        abstract = True


class CollectionElementPropertyOptions(models.Model):
    """
    This model represents the options that can be set for a property of a
    collection element. These options can be used to determine if the
    property should be searchable, filterable or sortable.
    """

    element = models.ForeignKey(
        Element,
        related_name="property_options",
        help_text="The element this property option belongs to.",
        on_delete=models.CASCADE,
    )
    schema_property = models.CharField(
        max_length=225,
        help_text="The name of the property in the schema this option belongs to.",
    )
    searchable = models.BooleanField(
        default=False,
        help_text="Whether this element is searchable or not by visitors.",
    )
    filterable = models.BooleanField(
        default=False,
        help_text="Whether this element is filterable or not by visitors.",
    )
    sortable = models.BooleanField(
        default=False,
        help_text="Whether this element is sortable or not by visitors.",
    )

    class Meta:
        unique_together = ("element", "schema_property")


class TableElement(CollectionElement):
    """
    A table element
    """

    orientation = models.JSONField(
        blank=True,
        null=True,
        default=get_default_table_orientation,
        help_text="The table orientation (horizontal or vertical) for each device type",
    )
    fields = models.ManyToManyField(CollectionField)


class IFrameElement(Element):
    """
    An element for embedding external resources in the application.
    """

    class IFRAME_SOURCE_TYPE(models.TextChoices):
        URL = "url"
        EMBED = "embed"

    source_type = models.CharField(
        choices=IFRAME_SOURCE_TYPE.choices,
        max_length=32,
        default=IFRAME_SOURCE_TYPE.URL,
    )
    url = FormulaField(
        help_text="A link to the page to embed",
    )
    embed = FormulaField(help_text="Inline HTML to embed")
    height = models.PositiveIntegerField(
        help_text="Height in pixels of the iframe",
        default=300,
    )


class RepeatElement(CollectionElement, ContainerElement):
    """
    A container and collection type element which repeats the child elements for each
    item in the data source that it is bound to.
    """

    class ORIENTATIONS(models.TextChoices):
        VERTICAL = "vertical"
        HORIZONTAL = "horizontal"

    orientation = models.CharField(
        choices=ORIENTATIONS.choices,
        max_length=10,
        default=ORIENTATIONS.VERTICAL,
    )
    items_per_row = models.JSONField(
        default=dict,
        help_text="The amount repetitions per row, per device type. "
        "Only applicable when the orientation is horizontal.",
    )
    horizontal_gap = models.IntegerField(
        default=0,
        db_default=0,
        help_text="The amount of horizontal space between repeat elements.",
        validators=[
            MinValueValidator(0, message="Value cannot be less than 0."),
            MaxValueValidator(2000, message="Value cannot be greater than 2000."),
        ],
    )
    vertical_gap = models.IntegerField(
        default=0,
        db_default=0,
        help_text="The amount of vertical space between repeat elements.",
        validators=[
            MinValueValidator(0, message="Value cannot be less than 0."),
            MaxValueValidator(2000, message="Value cannot be greater than 2000."),
        ],
    )


class RecordSelectorElement(CollectionElement, FormElement):
    """A collection element that displays a list of records for the user to select."""

    label = FormulaField(
        help_text="The text label for this record selector",
    )
    default_value = FormulaField(
        help_text="This record selector default value.",
    )
    placeholder = FormulaField(
        help_text="The placeholder text which should be applied to the element.",
    )
    multiple = models.BooleanField(
        default=False,
        help_text="Whether this record selector allows users to choose multiple values.",
    )
    option_name_suffix = FormulaField(
        help_text="The formula to generate the displayed option name suffix",
    )


class DateTimePickerElement(FormElement):
    """
    An input element of datetime type.
    """

    label = FormulaField(
        help_text="The text label for this date time picker",
    )
    default_value = FormulaField(
        help_text="This date time picker input's default value.",
    )
    date_format = models.CharField(
        choices=DATE_FORMAT_CHOICES,
        default="EU",
        max_length=32,
        help_text="EU (25/04/2024), US (04/25/2024) or ISO (2024-04-25)",
    )
    include_time = models.BooleanField(
        default=False,
        help_text="Whether to include time in the representation of the date",
    )
    time_format = models.CharField(
        choices=DATE_TIME_FORMAT_CHOICES,
        default="24",
        max_length=32,
        help_text="24 (14:00) or 12 (02:30) PM",
    )


class MultiPageElement(Element):
    """
    A container element that can contain other elements and be can shared across
    multiple pages.
    """

    class SHARE_TYPE(models.TextChoices):
        ALL = "all"
        ONLY = "only"
        EXCEPT = "except"

    share_type = models.CharField(
        choices=SHARE_TYPE.choices,
        max_length=10,
        default=SHARE_TYPE.ALL,
    )

    pages = models.ManyToManyField("builder.Page", blank=True)

    class Meta:
        abstract = True


class HeaderElement(MultiPageElement, ContainerElement):
    """
    A multi-page container element positioned at the top of the page.
    """


class FooterElement(MultiPageElement, ContainerElement):
    """
    A multi-page container element positioned at the bottom of the page.
    """


class MenuItemElement(NavigationElementMixin):
    """
    An item in a MenuElement.
    """

    class VARIANTS(models.TextChoices):
        LINK = "link"
        BUTTON = "button"

    variant = models.CharField(
        choices=VARIANTS.choices,
        help_text="The variant of the link.",
        max_length=10,
        default=VARIANTS.LINK,
    )

    class TYPES(models.TextChoices):
        BUTTON = "button"
        LINK = "link"
        SEPARATOR = "separator"
        SPACER = "spacer"

    type = models.CharField(
        choices=TYPES.choices,
        help_text="The type of the Menu Item.",
        max_length=9,
        default=TYPES.LINK,
    )

    name = models.CharField(
        max_length=225,
        help_text="The name of the Menu Item.",
    )

    menu_item_order = models.PositiveIntegerField()
    uid = models.UUIDField(default=uuid.uuid4)

    parent_menu_item = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        default=None,
        help_text="The parent MenuItemElement element, if it is a nested item.",
        related_name="menu_item_children",
    )

    class Meta:
        ordering = ("menu_item_order",)


class MenuElement(Element):
    """
    A menu element that helps with navigating the application.
    """

    class ORIENTATIONS(models.TextChoices):
        HORIZONTAL = "horizontal"
        VERTICAL = "vertical"

    orientation = models.CharField(
        choices=ORIENTATIONS.choices,
        max_length=10,
        default=ORIENTATIONS.HORIZONTAL,
        db_default=ORIENTATIONS.HORIZONTAL,
    )

    alignment = models.CharField(
        choices=HorizontalAlignments.choices,
        max_length=10,
        default=HorizontalAlignments.LEFT,
    )

    menu_items = models.ManyToManyField(MenuItemElement)


class SimpleContainerElement(ContainerElement):
    """
    A simple container to group elements
    """
