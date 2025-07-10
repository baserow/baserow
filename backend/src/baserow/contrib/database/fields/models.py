from enum import Enum
from typing import TYPE_CHECKING, NewType

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.fields.mixins import (
    DATE_FORMAT_CHOICES,
    DATE_TIME_FORMAT_CHOICES,
    BaseDateMixin,
)
from baserow.contrib.database.fields.utils.duration import DURATION_FORMATS
from baserow.contrib.database.formula import (
    BASEROW_FORMULA_ARRAY_TYPE_CHOICES,
    BASEROW_FORMULA_TYPE_CHOICES,
    FormulaHandler,
)
from baserow.contrib.database.mixins import ParentFieldTrashableModelMixin
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.contrib.database.table.constants import (
    LINK_ROW_THROUGH_TABLE_PREFIX,
    MULTIPLE_COLLABORATOR_THROUGH_TABLE_PREFIX,
    MULTIPLE_SELECT_THROUGH_TABLE_PREFIX,
    get_tsv_vector_field_name,
)
from baserow.core.constants import RatingStyleChoices
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)
from baserow.core.utils import remove_special_characters, to_snake_case

from .fields import SerialField

if TYPE_CHECKING:
    from baserow.contrib.database.fields.dependencies.handler import FieldDependants
    from baserow.contrib.database.fields.registries import FieldType  # noqa: F401

NUMBER_MAX_DECIMAL_PLACES = 10

NUMBER_DECIMAL_PLACES_CHOICES = [
    (0, "1"),
    (1, "1.0"),
    (2, "1.00"),
    (3, "1.000"),
    (4, "1.0000"),
    (5, "1.00000"),
    (6, "1.000000"),
    (7, "1.0000000"),
    (8, "1.00000000"),
    (9, "1.000000000"),
    (NUMBER_MAX_DECIMAL_PLACES, "1.0000000000"),
]


# We use these constants to map the separators to the values used in the database.
# The same variables are used in the frontend
class THOUSAND_SEPARATORS(Enum):
    SPACE = " "
    COMMA = ","
    PERIOD = "."
    NONE = ""


class DECIMAL_SEPARATORS(Enum):
    COMMA = ","
    PERIOD = "."


DEFAULT_THOUSAND_SEPARATOR = THOUSAND_SEPARATORS.NONE
DEFAULT_DECIMAL_SEPARATOR = DECIMAL_SEPARATORS.PERIOD

NUMBER_SEPARATORS = {
    "": {
        "label": "No formatting",
        "separators": (DEFAULT_THOUSAND_SEPARATOR, DEFAULT_DECIMAL_SEPARATOR),
    },
    "SPACE_COMMA": {
        "label": "Space, comma",
        "separators": (THOUSAND_SEPARATORS.SPACE, DECIMAL_SEPARATORS.COMMA),
    },
    "SPACE_PERIOD": {
        "label": "Space, period",
        "separators": (THOUSAND_SEPARATORS.SPACE, DECIMAL_SEPARATORS.PERIOD),
    },
    "COMMA_PERIOD": {
        "label": "Comma, period",
        "separators": (THOUSAND_SEPARATORS.COMMA, DECIMAL_SEPARATORS.PERIOD),
    },
    "PERIOD_COMMA": {
        "label": "Period, comma",
        "separators": (DECIMAL_SEPARATORS.PERIOD, THOUSAND_SEPARATORS.COMMA),
    },
}

NUMBER_SEPARATOR_CHOICES = [
    (key, value["label"]) for key, value in NUMBER_SEPARATORS.items()
]

DURATION_FORMAT_CHOICES = [(k, v["name"]) for k, v in DURATION_FORMATS.items()]


def get_default_field_content_type():
    return ContentType.objects.get_for_model(Field)


class Field(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
    PolymorphicContentTypeMixin,
    WithRegistry["FieldType"],
    models.Model,
):
    """
    Baserow base field model. All custom fields should inherit from this class.
    Because each field type can have custom settings, for example precision for a number
    field, values for an option field or checkbox style for a boolean field we need a
    polymorphic content type to store these settings in another table.
    """

    table = models.ForeignKey("database.Table", on_delete=models.CASCADE)
    order = models.PositiveIntegerField(help_text="Lowest first.")
    name = models.CharField(max_length=255, db_index=True)
    primary = models.BooleanField(
        default=False,
        help_text="Indicates if the field is a primary field. If `true` the field "
        "cannot be deleted and the value should represent the whole row.",
    )
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="database_fields",
        on_delete=models.SET(get_default_field_content_type),
    )
    field_dependencies = models.ManyToManyField(
        "self",
        related_name="dependant_fields",
        through="FieldDependency",
        through_fields=("dependant", "dependency"),
        symmetrical=False,
    )
    tsvector_column_created = models.BooleanField(
        default=False,
        help_text="Indicates whether a `tsvector` has been created for this field yet. "
        "This value will be False for fields created before the full text "
        "search release which haven't been lazily migrated yet. Or for "
        "users who have turned off full text search entirely. "
        "DEPRECATED: remove in a future version and drop tsv_column in database table",
    )
    search_data_initialized_at = models.DateTimeField(
        null=True,
        help_text=(
            "The timestamp when this field's tsvector values were first generated "
            "and added to the workspace search table. "
            "If null, the search data has not yet been initialized."
        ),
    )
    description = models.TextField(
        help_text="Field description", default=None, null=True
    )
    read_only = models.BooleanField(
        default=False,
        help_text="Indicates whether the field is read-only regardless of the field "
        "type. If true, then it won't be possible to update the cell value via the "
        "API.",
    )
    immutable_type = models.BooleanField(
        default=False,
        help_text="Indicates whether the field type is immutable. If true, then it "
        "won't be possible to change the field type via the API.",
    )
    immutable_properties = models.BooleanField(
        default=False,
        help_text="Indicates whether the field properties are immutable. If true, "
        "then it won't be possible to change the properties and the type via the API.",
    )
    db_index = models.BooleanField(
        db_default=False,
        default=False,
        help_text="If true, then an index will be added to the Baserow field to "
        "increase lookup and filter speed. Note that this comes at a performance cost "
        "when creating the row and updating the cell.",
    )

    class Meta:
        ordering = (
            "-primary",
            "order",
        )

    @staticmethod
    def get_type_registry():
        from .registries import field_type_registry

        return field_type_registry

    def get_parent(self):
        return self.table

    @classmethod
    def get_last_order(cls, table):
        queryset = Field.objects.filter(table=table)
        return cls.get_highest_order_of_queryset(queryset) + 1

    @classmethod
    def get_max_name_length(cls):
        return cls._meta.get_field("name").max_length

    @property
    def db_column(self):
        return f"field_{self.id}"

    def get_field_ref(self, user_field_names: bool = False) -> str:
        """
        Generates a reference (name or user field name) for a field.

        :param user_field_names: Whether user field names are used.
        """

        return self.name if user_field_names else self.db_column

    @property
    def tsv_db_column(self):
        return get_tsv_vector_field_name(self.id)

    @property
    def tsv_index_name(self):
        return f"tbl_tsv_{self.id}_idx"

    @property
    def model_attribute_name(self):
        """
        Generates a pascal case based model attribute name based on the field name.

        :return: The generated model attribute name.
        :rtype: str
        """

        name = remove_special_characters(self.name, False)
        name = to_snake_case(name)

        if name[0].isnumeric():
            name = f"field_{name}"

        return name

    def invalidate_table_model_cache(self):
        invalidate_table_in_model_cache(self.table_id)

    def dependant_fields_with_types(
        self,
        field_cache=None,
        starting_via_path_to_starting_table=None,
        associated_relation_changed=False,
    ) -> "FieldDependants":
        from baserow.contrib.database.fields.dependencies.handler import (
            FieldDependencyHandler,
        )

        return FieldDependencyHandler.get_dependant_fields_with_type(
            self.table_id,
            [self.id],
            associated_relation_changed,
            field_cache,
            starting_via_path_to_starting_table,
        )

    def save(self, *args, **kwargs):
        kwargs.pop("field_cache", None)
        kwargs.pop("raise_if_invalid", None)
        save = super().save(*args, **kwargs)
        self.invalidate_table_model_cache()
        return save


class AbstractSelectOption(
    HierarchicalModelMixin, ParentFieldTrashableModelMixin, models.Model
):
    value = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField()
    field = models.ForeignKey(
        Field, on_delete=models.CASCADE, related_name="select_options"
    )

    class Meta:
        abstract = True
        ordering = (
            "order",
            "id",
        )

    def get_parent(self):
        return self.field

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"<SelectOption {self.value} ({self.id})>"


class FieldConstraint(TrashableModelMixin, CreatedAndUpdatedOnMixin, models.Model):
    field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name="field_constraints",
        help_text="The field this constraint belongs to.",
    )
    type_name = models.CharField(
        max_length=255, help_text="The type name of the constraint."
    )

    class Meta:
        unique_together = ("field", "type_name")
        ordering = ("type_name",)


class SelectOption(AbstractSelectOption):
    @classmethod
    def get_max_value_length(cls):
        return cls._meta.get_field("value").max_length


class TextField(Field):
    text_default = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="If set, this value is going to be added every time a new row "
        "created.",
    )


class LongTextField(Field):
    long_text_enable_rich_text = models.BooleanField(
        default=False, null=True, help_text="Enable rich text formatting for the field."
    )  # TODO: Remove null=True in a future release.


class URLField(Field):
    pass


class NumberField(Field):
    number_decimal_places = models.IntegerField(
        choices=NUMBER_DECIMAL_PLACES_CHOICES,
        default=0,
        help_text="The amount of digits allowed after the point.",
    )
    number_negative = models.BooleanField(
        default=False, help_text="Indicates if negative values are allowed."
    )
    number_prefix = models.CharField(
        max_length=10,
        blank=True,
        help_text="The prefix to use for the field.",
        db_default="",
        default="",
    )
    number_suffix = models.CharField(
        max_length=100,
        blank=True,
        help_text="The suffix to use for the field.",
        default="",
        db_default="",
    )
    number_separator = models.CharField(
        choices=NUMBER_SEPARATOR_CHOICES,
        default=NUMBER_SEPARATOR_CHOICES[0][0],
        db_default=NUMBER_SEPARATOR_CHOICES[0][0],
        max_length=16,
        help_text="The thousand and decimal separator to use for the field.",
    )

    number_default = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        null=True,
        blank=True,
        help_text="The default value for field if none is provided.",
    )

    def save(self, *args, **kwargs):
        """Check if the number_decimal_places has a valid choice."""

        if not any(
            self.number_decimal_places in _tuple
            for _tuple in NUMBER_DECIMAL_PLACES_CHOICES
        ):
            raise ValueError(f"{self.number_decimal_places} is not a valid choice.")
        super(NumberField, self).save(*args, **kwargs)


class RatingField(Field):
    max_value = models.PositiveSmallIntegerField(
        default=5,
        help_text="Maximum value the rating can take.",
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    color = models.CharField(
        max_length=50,
        blank=False,
        help_text="Color of the symbols.",
        default="dark-orange",
    )
    style = models.CharField(
        choices=RatingStyleChoices,
        default="star",
        max_length=50,
        blank=False,
        help_text=(
            "Rating style. Allowed values: "
            f"{', '.join([value for value in RatingStyleChoices.values])}."
        ),
    )

    def save(self, *args, **kwargs):
        """
        Check if the max_value, color and style have a valid value.
        """

        if self.style not in RatingStyleChoices.values:
            raise ValueError(f"{self.style} is not a valid choice.")
        if not self.color:
            raise ValueError(f"color should be defined.")

        if self.max_value < 1:
            raise ValueError("Ensure this value is greater than or equal to 1.")
        if self.max_value > 10:
            raise ValueError(f"Ensure this value is less than or equal to 10.")

        super().save(*args, **kwargs)


class BooleanField(Field):
    boolean_default = models.BooleanField(
        default=False,
        db_default=False,
        help_text="The default value for field if none is provided.",
    )


class DateField(Field, BaseDateMixin):
    date_default_now = models.BooleanField(
        default=False,
        db_default=False,
        help_text=(
            "If enabled, the default value for new rows will be set to the current date "
            "and time when the row is created. If disabled, no default value will be set."
        ),
    )


class LastModifiedField(Field, BaseDateMixin):
    pass


class LastModifiedByField(Field):
    pass


class CreatedOnField(Field, BaseDateMixin):
    pass


class CreatedByField(Field):
    pass


class DurationField(Field):
    duration_format = models.CharField(
        choices=DURATION_FORMAT_CHOICES,
        default=DURATION_FORMAT_CHOICES[0][0],
        max_length=32,
        help_text=_("The format of the duration."),
    )


class LinkRowField(Field):
    THROUGH_DATABASE_TABLE_PREFIX = LINK_ROW_THROUGH_TABLE_PREFIX
    RELATED_PPRIMARY_FIELD_ATTR = "primary_fields"

    link_row_table = models.ForeignKey(
        "database.Table",
        on_delete=models.CASCADE,
        help_text="The table that the field has a relation with.",
        blank=True,
    )
    link_row_related_field = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        help_text="The relation field in the other table.",
        null=True,
        blank=True,
    )
    link_row_relation_id = SerialField(null=True, unique=False)
    link_row_limit_selection_view = models.ForeignKey(
        "database.View",
        on_delete=models.SET_NULL,
        help_text="Visually only select rows that match the view filter. Note that "
        "this is frontend only, and it will still be possible to make relationship to "
        "rows that don't match the view.",
        blank=True,
        null=True,
    )
    link_row_multiple_relationships = models.BooleanField(
        default=True,
        db_default=True,
        help_text="Indicates whether it's allowed set multiple relationships per row. "
        "If disabled, it doesn't guarantee single relationships because they could "
        "have already existed or created through reversed relationship.",
    )

    @property
    def through_table_name(self):
        """
        Generating a unique through table name based on the relation id.

        :return: The table name of the through model.
        :rtype: string
        """

        if not self.link_row_relation_id:
            raise ValueError("The link row field does not yet have a relation id.")

        return f"{self.THROUGH_DATABASE_TABLE_PREFIX}{self.link_row_relation_id}"

    @property
    def link_row_table_primary_field(self):
        # It's possible to optionally preset the `link_row_table_primary_field` using
        # the setter. If that's the case, then it must be returned.
        if hasattr(self, "_link_row_table_primary_field"):
            return self._link_row_table_primary_field

        # LinkRowFieldType.enhance_field_queryset prefetches the primary field
        # into RELATED_PPRIMARY_FIELD_ATTR. Let's check if it's already there first.
        if related_primary_field_set := getattr(
            self.link_row_table, self.RELATED_PPRIMARY_FIELD_ATTR, None
        ):
            return related_primary_field_set[0]

        try:
            return self.link_row_table.field_set.get(primary=True)
        except Field.DoesNotExist:
            return None

    @link_row_table_primary_field.setter
    def link_row_table_primary_field(self, value):
        self._link_row_table_primary_field = value

    @property
    def is_self_referencing(self):
        return self.link_row_table_id == self.table_id

    @property
    def link_row_table_has_related_field(self):
        return self.link_row_related_field_id is not None


class EmailField(Field):
    pass


class FileField(Field):
    pass


class SingleSelectField(Field):
    single_select_default = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text=(
            "The default value for the field if none is provided. Can be None if no default "
            "is set, or the ID of an available select option."
        ),
    )


class MultipleSelectField(Field):
    THROUGH_DATABASE_TABLE_PREFIX = MULTIPLE_SELECT_THROUGH_TABLE_PREFIX

    multiple_select_default = ArrayField(
        models.PositiveBigIntegerField(),
        null=True,
        blank=True,
        help_text=(
            "The default value for the field if none is provided. Can be None if no default "
            "is set, or the IDs of an available select options."
        ),
    )

    @property
    def through_table_name(self):
        """
        Generating a unique through table name based on the relation id.

        :return: The table name of the through model.
        :rtype: string
        """

        return f"{self.THROUGH_DATABASE_TABLE_PREFIX}{self.id}"


class PhoneNumberField(Field):
    pass


class FormulaField(Field):
    formula = models.TextField()
    internal_formula = models.TextField()
    version = models.IntegerField()
    requires_refresh_after_insert = models.BooleanField()
    old_formula_with_field_by_id = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    nullable = models.BooleanField()

    formula_type = models.TextField(
        choices=BASEROW_FORMULA_TYPE_CHOICES,
        default="invalid",
    )
    array_formula_type = models.TextField(
        choices=BASEROW_FORMULA_ARRAY_TYPE_CHOICES,
        default=None,
        null=True,
    )
    number_decimal_places = models.IntegerField(
        choices=NUMBER_DECIMAL_PLACES_CHOICES,
        default=None,
        null=True,
        help_text="The amount of digits allowed after the point.",
    )
    number_prefix = models.CharField(
        max_length=10,
        blank=True,
        help_text="The prefix to use for the field.",
        default="",
        db_default="",
    )
    number_suffix = models.CharField(
        max_length=10,
        blank=True,
        help_text="The suffix to use for the field.",
        default="",
        db_default="",
    )
    number_separator = models.CharField(
        choices=NUMBER_SEPARATOR_CHOICES,
        default=NUMBER_SEPARATOR_CHOICES[0][0],
        db_default=NUMBER_SEPARATOR_CHOICES[0][0],
        max_length=16,
        help_text="The thousand and decimal separator to use for the field.",
    )
    date_format = models.CharField(
        choices=DATE_FORMAT_CHOICES,
        default=None,
        max_length=32,
        help_text="EU (20/02/2020), US (02/20/2020) or ISO (2020-02-20)",
        null=True,
    )
    date_include_time = models.BooleanField(
        default=None,
        help_text="Indicates if the field also includes a time.",
        null=True,
    )
    date_time_format = models.CharField(
        choices=DATE_TIME_FORMAT_CHOICES,
        default=None,
        null=True,
        max_length=32,
        help_text="24 (14:30) or 12 (02:30 PM)",
    )
    date_show_tzinfo = models.BooleanField(
        default=None,
        null=True,
        help_text="Indicates if the time zone should be shown.",
    )
    date_force_timezone = models.CharField(
        max_length=255,
        null=True,
        help_text="Force a timezone for the field overriding user profile settings.",
    )
    duration_format = models.CharField(
        choices=DURATION_FORMAT_CHOICES,
        default=DURATION_FORMAT_CHOICES[0][0],
        max_length=32,
        null=True,
        help_text=_("The format of the duration."),
    )
    needs_periodic_update = models.BooleanField(
        default=False,
        help_text="Indicates if the field needs to be periodically updated.",
    )
    expand_formula_when_referenced = models.BooleanField(
        default=False,
        null=True,  # TODO zdm remove me in next release
        help_text=(
            "Indicates if the formula should be expanded when referenced (i.e. contains a lookup) "
            "or if it's possible to use the calculated value directly.",
        ),
    )

    @cached_property
    def cached_untyped_expression(self):
        return FormulaHandler.raw_formula_to_untyped_expression(self.formula)

    @cached_property
    def cached_typed_internal_expression(self):
        return FormulaHandler.get_typed_internal_expression_from_field(self)

    @cached_property
    def cached_formula_type(self):
        return FormulaHandler.get_formula_type_from_field(self)

    def clear_cached_properties(self):
        try:
            # noinspection PyPropertyAccess
            del self.cached_untyped_expression
        except AttributeError:
            # It has not been cached yet so nothing to deleted.
            pass
        try:
            # noinspection PyPropertyAccess
            del self.cached_formula_type
        except AttributeError:
            # It has not been cached yet so nothing to deleted.
            pass

    def recalculate_internal_fields(self, raise_if_invalid=False, field_cache=None):
        self.clear_cached_properties()
        expression = FormulaHandler.recalculate_formula_field_cached_properties(
            self, field_cache
        )
        expression_type = expression.expression_type
        # Update the cached properties
        setattr(self, "cached_typed_internal_expression", expression)
        setattr(self, "cached_formula_type", expression_type)

        if raise_if_invalid:
            expression_type.raise_if_invalid()

    def mark_as_invalid_and_save(self, error: str):
        from baserow.contrib.database.formula import BaserowFormulaInvalidType

        try:
            # noinspection PyPropertyAccess
            del self.cached_typed_internal_expression
        except AttributeError:
            # It has not been cached yet so nothing to deleted.
            pass

        invalid_type = BaserowFormulaInvalidType(error)
        invalid_type.persist_onto_formula_field(self)
        setattr(self, "cached_formula_type", invalid_type)
        self.save(recalculate=False, raise_if_invalid=False)

    def save(self, *args, **kwargs):
        recalculate = kwargs.pop("recalculate", not self.trashed)
        field_cache = kwargs.pop("field_cache", None)
        raise_if_invalid = kwargs.pop("raise_if_invalid", False)

        if recalculate:
            self.recalculate_internal_fields(
                field_cache=field_cache, raise_if_invalid=raise_if_invalid
            )
        super().save(*args, **kwargs)

    def refresh_from_db(self, *args, **kwargs) -> None:
        super().refresh_from_db(*args, **kwargs)
        self.clear_cached_properties()

    def __str__(self):
        return (
            "FormulaField(\n"
            + f"formula={self.formula},\n"
            + f"internal_formula={self.internal_formula},\n"
            + f"formula_type={self.formula_type},\n"
            + f"error={self.error},\n"
            + ")"
        )


class CountField(FormulaField):
    through_field = models.ForeignKey(
        Field,
        on_delete=models.SET_NULL,
        related_name="count_fields_used_by",
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):
        from baserow.contrib.database.formula.ast.function_defs import BaserowCount
        from baserow.contrib.database.formula.ast.tree import BaserowFieldReference

        field_reference = BaserowFieldReference(
            getattr(self.through_field, "name", ""), None, None
        )
        self.formula = f"{BaserowCount.type}({field_reference})"
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            "CountField(\n"
            + f"formula={self.formula},\n"
            + f"through_field_id={self.through_field_id},\n"
            + f"error={self.error},\n"
            + ")"
        )


class RollupField(FormulaField):
    through_field = models.ForeignKey(
        Field,
        on_delete=models.SET_NULL,
        related_name="rollup_fields_used_by",
        null=True,
        blank=True,
    )
    target_field = models.ForeignKey(
        Field,
        on_delete=models.SET_NULL,
        related_name="targeting_rollup_fields",
        null=True,
        blank=True,
    )
    rollup_function = models.CharField(
        max_length=64,
        blank=True,
        help_text="The rollup formula function that must be applied.",
    )

    def save(self, *args, **kwargs):
        from baserow.contrib.database.formula.ast.tree import BaserowFieldReference
        from baserow.contrib.database.formula.registries import (
            formula_function_registry,
        )

        formula_function = formula_function_registry.get(self.rollup_function)
        field_reference = BaserowFieldReference(
            getattr(self.through_field, "name", ""),
            getattr(self.target_field, "name", ""),
            None,
        )
        self.formula = f"{formula_function.type}({field_reference})"
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            "RollupField(\n"
            + f"through_field={getattr(self.through_field, 'name', '')},\n"
            + f"target_field={getattr(self.target_field, 'name', '')},\n"
            + f"rollup_function={self.rollup_function},\n"
            + f"error={self.error},\n"
            + ")"
        )


class LookupField(FormulaField):
    through_field = models.ForeignKey(
        Field,
        on_delete=models.SET_NULL,
        related_name="lookup_fields_used_by",
        null=True,
        blank=True,
    )
    target_field = models.ForeignKey(
        Field,
        on_delete=models.SET_NULL,
        related_name="targeting_lookup_fields",
        null=True,
        blank=True,
    )
    through_field_name = models.CharField(max_length=255)
    target_field_name = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        from baserow.contrib.database.formula.ast.tree import BaserowFieldReference

        expression = str(
            BaserowFieldReference(self.through_field_name, self.target_field_name, None)
        )
        self.formula = expression
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            "LookupField(\n"
            + f"through_field={self.through_field_name},\n"
            + f"target_field={self.target_field_name},\n"
            + f"array_formula_type={self.array_formula_type},\n"
            + f"error={self.error},\n"
            + ")"
        )


class MultipleCollaboratorsField(Field):
    THROUGH_DATABASE_TABLE_PREFIX = MULTIPLE_COLLABORATOR_THROUGH_TABLE_PREFIX

    notify_user_when_added = models.BooleanField(
        default=True,
        help_text=(
            "Indicates if the user should be notified when they are added as a "
            "collaborator."
        ),
    )
    multiple_collaborators_default = ArrayField(
        models.PositiveBigIntegerField(),
        null=True,
        blank=True,
        help_text=(
            "The default value for the field if none is provided. Can be None if no "
            "default is set, or the IDs of available collaborators or value 0 to "
            "automatically set the current user when row is created."
        ),
    )

    @property
    def through_table_name(self):
        """
        Generating a unique through table name based on the relation id.

        :return: The table name of the through model.
        :rtype: string
        """

        return f"{self.THROUGH_DATABASE_TABLE_PREFIX}{self.id}"


class UUIDField(Field):
    pass


class AutonumberField(Field):
    pass


class PasswordField(Field):
    allow_endpoint_authentication = models.BooleanField(
        db_default=False,
        default=False,
        help_text="If true, then it's possible to use the "
        "`password_field_authentication` API endpoint to check if the password is "
        "correct. This can be used to use Baserow as authentication backend.",
    )


class DuplicateFieldJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    original_field = models.ForeignKey(
        Field,
        null=True,
        related_name="duplicated_by_jobs",
        on_delete=models.SET_NULL,
        help_text="The Baserow field to duplicate.",
    )
    duplicate_data = models.BooleanField(
        default=False,
        help_text="Indicates if the data of the field should be duplicated.",
    )
    duplicated_field = models.OneToOneField(
        Field,
        null=True,
        related_name="duplicated_from_jobs",
        on_delete=models.SET_NULL,
        help_text="The duplicated Baserow field.",
    )


SpecificFieldForUpdate = NewType("SpecificFieldForUpdate", Field)
