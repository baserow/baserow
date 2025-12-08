import json
import re
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from itertools import cycle
from random import randint, randrange, sample
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.aggregates import ArrayAgg, JSONBAgg, StringAgg
from django.core.exceptions import ValidationError
from django.core.files.storage import Storage
from django.db import OperationalError, connection, models
from django.db.models import (
    Case,
    CharField,
    DateTimeField,
    Exists,
    Expression,
    ExpressionWrapper,
    F,
    Func,
    JSONField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
    Window,
)
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.related import ManyToManyField
from django.db.models.functions import Cast, Coalesce, RowNumber

from dateutil import parser
from dateutil.parser import ParserError
from loguru import logger
from rest_framework import serializers

from baserow.contrib.database.api.fields.errors import (
    ERROR_DATE_FORCE_TIMEZONE_OFFSET_ERROR,
    ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE,
    ERROR_INVALID_COUNT_THROUGH_FIELD,
    ERROR_INVALID_LOOKUP_TARGET_FIELD,
    ERROR_INVALID_LOOKUP_THROUGH_FIELD,
    ERROR_INVALID_ROLLUP_FORMULA_FUNCTION,
    ERROR_INVALID_ROLLUP_TARGET_FIELD,
    ERROR_INVALID_ROLLUP_THROUGH_FIELD,
    ERROR_LINK_ROW_TABLE_NOT_IN_SAME_DATABASE,
    ERROR_LINK_ROW_TABLE_NOT_PROVIDED,
    ERROR_SELF_REFERENCING_LINK_ROW_CANNOT_HAVE_RELATED_FIELD,
    ERROR_TOO_DEEPLY_NESTED_FORMULA,
    ERROR_WITH_FORMULA,
)
from baserow.contrib.database.api.fields.serializers import (
    AvailableCollaboratorsSerializer,
    BaserowBooleanField,
    CollaboratorSerializer,
    DurationFieldSerializer,
    FileFieldRequestSerializer,
    FileFieldResponseSerializer,
    IntegerOrStringField,
    LimitListSerializer,
    LinkRowFieldSerializerMixin,
    LinkRowRequestSerializer,
    LinkRowValueSerializer,
    ListOrStringField,
    MustBeEmptyField,
    PasswordSerializer,
    SelectOptionSerializer,
)
from baserow.contrib.database.api.utils import (
    LinkRowJoin,
    get_thousand_and_decimal_separator,
)
from baserow.contrib.database.api.views.errors import (
    ERROR_VIEW_DOES_NOT_EXIST,
    ERROR_VIEW_NOT_IN_TABLE,
)
from baserow.contrib.database.db.functions import RandomUUID
from baserow.contrib.database.fields.exceptions import SelectOptionDoesNotBelongToField
from baserow.contrib.database.fields.filter_support.formula import (
    FormulaFieldTypeArrayFilterSupport,
)
from baserow.contrib.database.fields.utils.expression import (
    get_collaborator_extractor,
    get_select_option_extractor,
    wrap_in_subquery,
)
from baserow.contrib.database.fields.utils.field_constraint import (
    validate_default_value_with_constraints,
)
from baserow.contrib.database.formula import (
    BASEROW_FORMULA_TYPE_ALLOWED_FIELDS,
    BASEROW_FORMULA_TYPE_REQUEST_SERIALIZER_FIELD_NAMES,
    BASEROW_FORMULA_TYPE_SERIALIZER_FIELD_NAMES,
    BaserowExpression,
    BaserowFormulaBooleanType,
    BaserowFormulaCharType,
    BaserowFormulaDateType,
    BaserowFormulaInvalidType,
    BaserowFormulaMultipleCollaboratorsType,
    BaserowFormulaNumberType,
    BaserowFormulaSingleSelectType,
    BaserowFormulaTextType,
    BaserowFormulaType,
    FormulaHandler,
)
from baserow.contrib.database.formula.registries import formula_function_registry
from baserow.contrib.database.formula.types.formula_types import (
    BaserowFormulaArrayType,
    BaserowFormulaDurationType,
    BaserowFormulaMultipleSelectType,
    BaserowFormulaSingleFileType,
    BaserowFormulaURLType,
)
from baserow.contrib.database.models import Table
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.types import SerializedRowHistoryFieldMetadata
from baserow.contrib.database.validators import UnicodeRegexValidator
from baserow.contrib.database.views.exceptions import ViewDoesNotExist, ViewNotInTable
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import (
    DEFAULT_SORT_TYPE_KEY,
    OWNERSHIP_TYPE_COLLABORATIVE,
    View,
)
from baserow.core.db import (
    CombinedForeignKeyAndManyToManyMultipleFieldPrefetch,
    collate_expression,
    specific_queryset,
)
from baserow.core.expressions import DateTrunc
from baserow.core.fields import SyncedDateTimeField
from baserow.core.formula import BaserowFormulaException
from baserow.core.formula.parser.exceptions import FormulaFunctionTypeDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.models import UserFile, WorkspaceUser
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import ExportZipFile, get_default_storage
from baserow.core.user_files.exceptions import UserFileDoesNotExist
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.utils import grouper, list_to_comma_separated_string

from .constants import (
    BASEROW_BOOLEAN_FIELD_FALSE_VALUES,
    BASEROW_BOOLEAN_FIELD_TRUE_VALUES,
    SINGLE_SELECT_SORT_BY_ORDER,
    UPSERT_OPTION_DICT_KEY,
    DeleteFieldStrategyEnum,
)
from .dependencies.exceptions import (
    CircularFieldDependencyError,
    SelfReferenceFieldDependencyError,
)
from .dependencies.handler import FieldDependants, FieldDependencyHandler
from .dependencies.models import FieldDependency
from .dependencies.types import FieldDependencies
from .dependencies.update_collector import DependencyContext, FieldUpdateCollector
from .exceptions import (
    AllProvidedCollaboratorIdsMustBeValidUsers,
    AllProvidedMultipleSelectValuesMustBeSelectOption,
    AllProvidedValuesMustBeIntegersOrStrings,
    DateForceTimezoneOffsetValueError,
    FieldDoesNotExist,
    IncompatiblePrimaryFieldTypeError,
    InvalidCountThroughField,
    InvalidLookupTargetField,
    InvalidLookupThroughField,
    InvalidRollupTargetField,
    InvalidRollupThroughField,
    LinkRowTableNotInSameDatabase,
    LinkRowTableNotProvided,
    SelfReferencingLinkRowCannotHaveRelatedField,
)
from .expressions import extract_jsonb_array_values_to_single_string
from .field_cache import FieldCache
from .field_filters import (
    AnnotatedQ,
    contains_filter,
    contains_word_filter,
    filename_contains_filter,
    parse_ids_from_csv_string,
)
from .field_helpers import prepare_files_for_export
from .field_sortings import OptionallyAnnotatedOrderBy
from .fields import BaserowExpressionField, BaserowLastModifiedField
from .fields import DurationField as DurationModelField
from .fields import (
    IntegerFieldWithSequence,
    MultipleSelectManyToManyField,
    SingleSelectForeignKey,
    SyncedUserForeignKeyField,
)
from .handler import FieldHandler
from .models import (
    AbstractSelectOption,
    AutonumberField,
    BooleanField,
    CountField,
    CreatedByField,
    CreatedOnField,
    DateField,
    DurationField,
    EmailField,
    Field,
    FileField,
    FormulaField,
    LastModifiedByField,
    LastModifiedField,
    LinkRowField,
    LongTextField,
    LookupField,
    MultipleCollaboratorsField,
    MultipleSelectField,
    NumberField,
    PasswordField,
    PhoneNumberField,
    RatingField,
    RollupField,
    SelectOption,
    SingleSelectField,
    TextField,
    URLField,
    UUIDField,
)
from .operations import CreateFieldOperationType, DeleteRelatedLinkRowFieldOperationType
from .registries import (
    FieldType,
    ManyToManyGroupByMixin,
    ReadOnlyFieldType,
    StartingRowType,
    field_type_registry,
)
from .utils import DeferredForeignKeyUpdater
from .utils.duration import (
    DURATION_FORMATS,
    duration_value_sql_to_text,
    duration_value_to_timedelta,
    format_duration_value,
    get_duration_search_expression,
    is_duration_format_conversion_lossy,
    prepare_duration_value_for_db,
    text_value_sql_to_duration,
)

User = get_user_model()


if TYPE_CHECKING:
    from baserow.contrib.database.table.models import FieldObject, GeneratedTableModel


class CollationSortMixin:
    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ) -> OptionallyAnnotatedOrderBy:
        field_expr = collate_expression(F(field_name))

        if order_direction == "ASC":
            field_order_by = field_expr.asc(nulls_first=True)
        else:
            field_order_by = field_expr.desc(nulls_last=True)

        return OptionallyAnnotatedOrderBy(order=field_order_by, can_be_indexed=True)


class TextFieldMatchingRegexFieldType(FieldType, ABC):
    """
    This is an abstract FieldType you can extend to create a field which is a TextField
    but restricted to only allow values passing a regex. Please implement the
    regex and random_value properties.

    This abstract class will then handle all the various places that this regex needs to
    be used:
        - by setting the text field's validator
        - by setting the serializer field's validator
        - checking values passed to prepare_value_for_db pass the regex
        - by checking and only converting column values which match the regex when
          altering a column to being an email type.
    """

    _can_have_db_index = True

    @property
    @abstractmethod
    def regex(self):
        pass

    @property
    def validator(self):
        return UnicodeRegexValidator(regex_value=self.regex)

    def prepare_value_for_db(self, instance, value):
        if value == "" or value is None:
            return ""

        self.validator(value)
        return value

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)
        validators = kwargs.pop("validators", None) or []
        validators.append(self.validator)
        return serializers.CharField(
            **{
                "required": required,
                "allow_null": not required,
                "allow_blank": not required,
                "validators": validators,
                **kwargs,
            }
        )

    def get_model_field(self, instance, **kwargs):
        return models.TextField(
            default="",
            blank=True,
            null=True,
            validators=[self.validator],
            db_index=instance.db_index,
            **kwargs,
        )

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        if connection.vendor == "postgresql":
            return f"""p_in = (
            case
                when p_in::text ~* '{self.regex}'
                then p_in::text
                else ''
                end
            );"""

        return super().get_alter_column_prepare_new_value(
            connection, from_field, to_field
        )

    def contains_query(self, *args):
        return contains_filter(*args)

    def contains_word_query(self, *args):
        return contains_word_filter(*args)

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaTextType(nullable=True)

    def from_baserow_formula_type(self, formula_type: BaserowFormulaCharType):
        return self.model_class()


class CharFieldMatchingRegexFieldType(TextFieldMatchingRegexFieldType):
    """
    This is an abstract FieldType you can extend to create a field which is a CharField
    with a specific max length, but restricted to only allow values passing a regex.
    Please implement the regex, max_length and random_value properties.

    This abstract class will then handle all the various places that this regex needs to
    be used:
        - by setting the char field's validator
        - by setting the serializer field's validator
        - checking values passed to prepare_value_for_db pass the regex
        - by checking and only converting column values which match the regex when
          altering a column to being an email type.
    """

    _can_group_by = True

    @property
    @abstractmethod
    def max_length(self):
        return None

    def get_serializer_field(self, instance, **kwargs):
        kwargs = {"max_length": self.max_length, **kwargs}
        return super().get_serializer_field(instance, **kwargs)

    def get_model_field(self, instance, **kwargs):
        return models.CharField(
            default="",
            blank=True,
            null=True,
            max_length=self.max_length,
            validators=[self.validator],
            db_index=instance.db_index,
            **kwargs,
        )

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaCharType(nullable=True)


class ManyToManyFieldTypeSerializeToInputValueMixin:
    def serialize_to_input_value(self, field: Field, value: any) -> any:
        return [v.id for v in value.all()]

    def random_to_input_value(self, field: Field, value: any) -> any:
        return value


class TextFieldType(CollationSortMixin, FieldType):
    type = "text"
    model_class = TextField
    allowed_fields = ["text_default"]
    serializer_field_names = ["text_default"]
    _can_group_by = True
    _can_have_db_index = True

    can_upsert = True

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)
        return serializers.CharField(
            **{
                "required": required,
                "allow_null": not required,
                "allow_blank": not required,
                "default": instance.text_default or None,
                **kwargs,
            }
        )

    def get_model_field(self, instance, **kwargs):
        return models.TextField(
            default=instance.text_default or None,
            blank=True,
            null=True,
            db_index=instance.db_index,
            **kwargs,
        )

    def random_value(self, instance, fake, cache):
        return fake.name()

    def contains_query(self, *args):
        return contains_filter(*args)

    def contains_word_query(self, *args):
        return contains_word_filter(*args)

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaTextType(nullable=True)

    def from_baserow_formula_type(
        self, formula_type: BaserowFormulaTextType
    ) -> TextField:
        return TextField()

    def get_value_for_filter(self, row: "GeneratedTableModel", field: Field) -> any:
        value = getattr(row, field.db_column)
        return collate_expression(Value(value))


class LongTextFieldType(CollationSortMixin, FieldType):
    type = "long_text"
    model_class = LongTextField
    allowed_fields = ["long_text_enable_rich_text"]
    serializer_field_names = ["long_text_enable_rich_text"]
    _can_have_db_index = True
    can_upsert = True

    def check_can_group_by(self, field: Field, sort_type: str) -> bool:
        return not field.long_text_enable_rich_text

    def can_be_primary_field(self, field_or_values: Union[Field, dict]) -> bool:
        if isinstance(field_or_values, dict):
            enable_rich_text = field_or_values.get("long_text_enable_rich_text", False)
        else:
            enable_rich_text = getattr(
                field_or_values, "long_text_enable_rich_text", False
            )
        return enable_rich_text is False

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)
        return serializers.CharField(
            **{
                "required": required,
                "allow_null": not required,
                "allow_blank": not required,
                **kwargs,
            }
        )

    def serialize_metadata_for_row_history(
        self,
        field: Field,
        row: "GeneratedTableModel",
        metadata,
    ) -> SerializedRowHistoryFieldMetadata:
        base = super().serialize_metadata_for_row_history(field, row, metadata)
        return {
            **base,
            "long_text_enable_rich_text": field.long_text_enable_rich_text,
        }

    def get_model_field(self, instance, **kwargs):
        return models.TextField(
            blank=True, null=True, db_index=instance.db_index, **kwargs
        )

    def random_value(self, instance, fake, cache):
        return fake.text()

    def contains_query(self, *args):
        return contains_filter(*args)

    def contains_word_query(self, *args):
        return contains_word_filter(*args)

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaTextType(nullable=True)

    def from_baserow_formula_type(
        self, formula_type: BaserowFormulaTextType
    ) -> "LongTextField":
        return LongTextField()

    def get_value_for_filter(self, row: "GeneratedTableModel", field: Field) -> any:
        value = getattr(row, field.db_column)
        return collate_expression(Value(value))


class URLFieldType(CollationSortMixin, TextFieldMatchingRegexFieldType):
    type = "url"
    model_class = URLField
    _can_group_by = True
    can_upsert = True

    @property
    def regex(self):
        # A very lenient URL validator that allows all types of URLs as long as it
        # respects the maximal amount of characters before the dot at at least have
        # one character after the dot.
        return r"^[^\s]{0,255}(?:\.|//)[^\s]{1,}$"

    def random_value(self, instance, fake, cache):
        return fake.url()

    def get_value_for_filter(self, row: "GeneratedTableModel", field: Field) -> any:
        value = getattr(row, field.db_column)
        return collate_expression(Value(value))

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaURLType(nullable=True)


class NumberFieldType(FieldType):
    MAX_DIGITS = 50

    type = "number"
    model_class = NumberField
    allowed_fields = [
        "number_decimal_places",
        "number_negative",
        "number_prefix",
        "number_suffix",
        "number_separator",
        "number_default",
    ]
    serializer_field_names = [
        "number_decimal_places",
        "number_negative",
        "number_type",
        "number_prefix",
        "number_suffix",
        "number_separator",
        "number_default",
    ]
    serializer_field_overrides = {
        "number_type": MustBeEmptyField(
            "The number_type option has been removed and can no longer be provided. "
            "Instead set number_decimal_places to 0 for an integer or 1-5 for a "
            "decimal."
        ),
        "_spectacular_annotation": {"exclude_fields": ["number_type"]},
    }
    _can_group_by = True
    _db_column_fields = ["number_decimal_places"]
    _can_have_db_index = True
    can_upsert = True

    def serialize_allowed_fields(self, field: Field) -> Dict[str, Any]:
        serialized = {}
        for field_name in self.allowed_fields:
            value = getattr(field, field_name)
            # number default is Decimal
            if field_name == "number_default" and value is not None:
                value = str(value)
            serialized[field_name] = value
        return serialized

    def serialize_to_input_value(self, field: Field, value: any) -> any:
        if field.specific.number_decimal_places == 0:
            return int(value)
        return value

    def prepare_value_for_db(self, instance: NumberField, value):
        if value is None:
            return value

        if isinstance(value, str):
            if instance.number_prefix is not None:
                value = value.lstrip(instance.number_prefix)
            if instance.number_suffix is not None:
                value = value.rstrip(instance.number_suffix)

            thousand_sep, decimal_sep = get_thousand_and_decimal_separator(
                instance.number_separator
            )

            value = value.replace(thousand_sep, "").replace(decimal_sep, ".").strip()

            if value in ["", "NaN"]:
                return None

        try:
            value = Decimal(value)
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError(
                f"The value for field {instance.id} is not a valid number",
                code="invalid",
            )

        if not instance.number_negative and value < 0:
            raise ValidationError(
                f"The value for field {instance.id} cannot be negative.",
                code="negative_not_allowed",
            )
        return value

    def get_serializer_field(self, instance: NumberField, **kwargs):
        required = kwargs.pop("required", False)

        kwargs["decimal_places"] = instance.number_decimal_places

        if not instance.number_negative:
            kwargs["min_value"] = Decimal("0")

        if not required and instance.number_default is not None:
            kwargs["default"] = instance.number_default

        return serializers.DecimalField(
            **{
                "max_digits": self.MAX_DIGITS + kwargs["decimal_places"],
                "required": required,
                "allow_null": not required,
                **kwargs,
            }
        )

    def get_export_value(self, value, field_object, rich_value=False):
        if value is None:
            return value if rich_value else ""

        instance = field_object["field"]

        apply_formatting = (
            instance.number_prefix
            or instance.number_suffix
            or instance.number_separator
        )

        # Old export that doesn't require formatting
        if not apply_formatting:
            # If the number is an integer we want it to be a literal json number and so
            # don't convert it to a string. However, if a decimal to preserve any
            # precision we keep it as a string.
            instance = field_object["field"]
            if instance.number_decimal_places == 0:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    pass

            # DRF's Decimal Serializer knows how to quantize and format the decimal
            # correctly so lets use it instead of trying to do it ourselves.
            return self.get_serializer_field(instance).to_representation(value)

        formatted_value = self.get_serializer_field(instance).to_representation(value)

        if formatted_value == "NaN":
            return "NaN"

        fractional_part = ""
        if instance.number_decimal_places == 0:
            integer_part = formatted_value.split(".")[0]
        elif "." in formatted_value:
            integer_part, fractional_part = formatted_value.split(".")
        else:
            integer_part = formatted_value

        thousand_separator, decimal_separator = get_thousand_and_decimal_separator(
            instance.number_separator
        )

        minus_sign = ""
        if integer_part.startswith("-"):
            minus_sign = "-"
            integer_part = integer_part[1:]

        # Format integer part with thousand separator
        integer_part_with_sep = f"{int(integer_part):,}".replace(
            ",", thousand_separator
        )

        # Add fractional part with decimal_separator if needed
        if fractional_part:
            fractional_part = f"{decimal_separator}{fractional_part}"

        # Add prefix and suffix
        return (
            f"{minus_sign}"
            f"{instance.number_prefix}"
            f"{integer_part_with_sep}{fractional_part}"
            f"{instance.number_suffix}".strip()
        )

    def get_model_field(self, instance, **kwargs):
        kwargs["decimal_places"] = instance.number_decimal_places
        default = instance.number_default
        if default is not None:
            kwargs["default"] = default
        return models.DecimalField(
            max_digits=self.MAX_DIGITS + kwargs["decimal_places"],
            null=True,
            blank=True,
            db_index=instance.db_index,
            **kwargs,
        )

    def random_value(self, instance: NumberField, fake, cache):
        if instance.number_decimal_places == 0:
            return fake.pyint(
                min_value=-10000 if instance.number_negative else 1,
                max_value=10000,
                step=1,
            )
        elif instance.number_decimal_places > 0:
            return fake.pydecimal(
                min_value=-10000 if instance.number_negative else 1,
                max_value=10000,
                positive=not instance.number_negative,
            )

    def get_alter_column_prepare_new_value(
        self, connection, from_field: NumberField, to_field
    ):
        if connection.vendor == "postgresql":
            decimal_places = to_field.number_decimal_places

            function = f"round(p_in::numeric, {decimal_places})"

            if not to_field.number_negative:
                function = f"greatest({function}, 0)"

            return f"p_in = {function};"

        return super().get_alter_column_prepare_new_value(
            connection, from_field, to_field
        )

    def force_same_type_alter_column(self, from_field, to_field):
        return not to_field.number_negative and from_field.number_negative

    def contains_query(self, *args):
        return contains_filter(*args)

    def get_export_serialized_value(self, row, field_name, cache, files_zip, storage):
        value = self.get_internal_value_from_db(row, field_name)
        return value if value is None else str(value)

    def to_baserow_formula_type(self, field: NumberField) -> BaserowFormulaType:
        return BaserowFormulaNumberType(
            number_decimal_places=field.number_decimal_places,
            number_prefix=field.number_prefix,
            number_suffix=field.number_suffix,
            number_separator=field.number_separator,
            nullable=True,
        )

    def from_baserow_formula_type(
        self, formula_type: BaserowFormulaNumberType
    ) -> NumberField:
        return NumberField(
            number_decimal_places=formula_type.number_decimal_places or 0,
            number_negative=True,
            number_prefix=formula_type.number_prefix,
            number_suffix=formula_type.number_suffix,
            number_separator=formula_type.number_separator,
        )

    def should_update_search_data(
        self, old_field: NumberField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_number_decimal_places = new_field_attrs.get(
            "number_decimal_places", old_field.number_decimal_places
        )
        return old_field.number_decimal_places != new_number_decimal_places

    def should_backup_field_data_for_same_type_update(
        self, old_field: NumberField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_number_decimal_places = new_field_attrs.get(
            "number_decimal_places", old_field.number_decimal_places
        )
        new_number_negative = new_field_attrs.get(
            "number_negative", old_field.number_negative
        )
        return (
            old_field.number_decimal_places > new_number_decimal_places
            or old_field.number_negative
            and not new_number_negative
        )

    def serialize_metadata_for_row_history(
        self,
        field: Field,
        row: "GeneratedTableModel",
        metadata,
    ) -> SerializedRowHistoryFieldMetadata:
        base = super().serialize_metadata_for_row_history(field, row, metadata)

        return {
            **base,
            "number_decimal_places": field.number_decimal_places,
            "number_negative": field.number_negative,
            "number_prefix": field.number_prefix,
            "number_suffix": field.number_suffix,
            "number_separator": field.number_separator,
        }

    def parse_filter_value(self, field, model_field, value):
        """
        Verify if it's a valid and finite decimal value, but the filter value doesn't
        need to respect the number_decimal_places, because they can change while the
        filter_value remains the same.
        """

        if value == "":
            return None

        try:
            value = Decimal(value)
            if not value.is_finite():
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"Invalid value for number field: {value}")
        return value

    def to_runtime_formula_value(self, field, value):
        """
        Transform the value to be usable in runtime formula land.
        """

        if value is None or value == "":
            return None

        if field.number_decimal_places == 0:
            return int(Decimal(value))

        return float(Decimal(value))


class RatingFieldType(FieldType):
    type = "rating"
    model_class = RatingField
    allowed_fields = ["max_value", "color", "style"]
    serializer_field_names = ["max_value", "color", "style"]
    _can_group_by = True
    _db_column_fields = []
    _can_have_db_index = True
    can_upsert = True

    def prepare_value_for_db(self, instance, value):
        if not value:
            return 0

        try:
            # Ensure the value is an int
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(
                f"The value for field {instance.id} is not a valid number",
                code="invalid",
            )

        if value < 0:
            raise ValidationError(
                "Ensure this value is greater than or equal to 0.", code="min_value"
            )
        if value > instance.max_value:
            raise ValidationError(
                f"Ensure this value is less than or equal to {instance.max_value}.",
                code="max_value",
            )

        return value

    def get_serializer_field(self, instance, **kwargs):
        return serializers.IntegerField(
            **{
                "required": False,
                "allow_null": False,
                "min_value": 0,
                "default": 0,
                "max_value": instance.max_value,
                **kwargs,
            }
        )

    def force_same_type_alter_column(self, from_field, to_field):
        """
        Force field alter column hook to be called when changing max_value.
        """

        return to_field.max_value != from_field.max_value

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        """
        Prepare value for Rating field. Clamp between 0 and field max_value.
        Also convert Null value to 0.
        """

        if connection.vendor == "postgresql":
            from_field_type = field_type_registry.get_by_model(from_field)

            if from_field_type.type in ["number", "text", "rating"]:
                # Convert and clamp values on field conversion
                return (
                    f"p_in = least(greatest(round(p_in::numeric), 0)"
                    f", {to_field.max_value});"
                )

            if from_field_type.type == "boolean":
                return """
                    IF p_in THEN
                        p_in = 1;
                    ELSE
                        p_in = 0;
                    END IF;
                """

        return super().get_alter_column_prepare_new_value(
            connection, from_field, to_field
        )

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        """
        Prepare value from Rating field.
        """

        if connection.vendor == "postgresql":
            to_field_type = field_type_registry.get_by_model(to_field)

            if to_field_type.type == "boolean":
                return "p_in = least(p_in::numeric, 1);"

        return super().get_alter_column_prepare_old_value(
            connection, from_field, to_field
        )

    def get_model_field(self, instance, **kwargs):
        return models.PositiveSmallIntegerField(
            blank=False,
            null=False,
            default=0,
            db_index=instance.db_index,
            **kwargs,
        )

    def random_value(self, instance, fake, cache):
        return fake.random_int(0, instance.max_value)

    def contains_query(self, *args):
        return contains_filter(*args)

    def contains_word_query(self, *args):
        return contains_word_filter(*args)

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaNumberType(0)

    def from_baserow_formula_type(
        self, formula_type: BaserowFormulaNumberType
    ) -> "RatingField":
        return RatingField()

    def should_update_search_data(
        self, old_field: RatingField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_max_value = new_field_attrs.get("max_value", old_field.max_value)
        return old_field.max_value > new_max_value

    def should_backup_field_data_for_same_type_update(
        self, old_field: RatingField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_max_value = new_field_attrs.get("max_value", old_field.max_value)
        return old_field.max_value > new_max_value


class BooleanFieldType(FieldType):
    type = "boolean"
    model_class = BooleanField
    allowed_fields = ["boolean_default"]
    serializer_field_names = ["boolean_default"]
    _can_group_by = True
    _can_have_db_index = True
    can_upsert = True

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        """
        Prepare value for Boolean field.
        Convert to True if the text value is equal (case-insensitive) to
        'checked' or to one of the serializers.BooleanField.TRUE_VALUES.
        """

        true_values = ",".join(["'%s'" % v for v in BASEROW_BOOLEAN_FIELD_TRUE_VALUES])
        return f"""
            IF lower(p_in::text) IN ({true_values}) THEN
                p_in = TRUE;
            ELSE
                p_in = FALSE;
            END IF;
        """

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)
        if not required:
            kwargs["default"] = instance.boolean_default
        return BaserowBooleanField(**{"required": required, **kwargs})

    def get_model_field(self, instance, **kwargs):
        return models.BooleanField(
            default=instance.boolean_default, db_index=instance.db_index, **kwargs
        )

    def random_value(self, instance, fake, cache):
        return fake.pybool()

    def get_export_serialized_value(self, row, field_name, cache, files_zip, storage):
        value = self.get_internal_value_from_db(row, field_name)
        return "true" if value else "false"

    def set_import_serialized_value(
        self, row, field_name, value, id_mapping, cache, files_zip, storage
    ):
        setattr(row, field_name, value == "true")

    def to_baserow_formula_type(self, field: NumberField) -> BaserowFormulaType:
        return BaserowFormulaBooleanType()

    def from_baserow_formula_type(
        self, boolean_formula_type: BaserowFormulaBooleanType
    ) -> BooleanField:
        return BooleanField()

    def parse_filter_value(self, field, model_field, value):
        if value == "":
            return None
        elif value in BASEROW_BOOLEAN_FIELD_TRUE_VALUES:
            return True
        elif value in BASEROW_BOOLEAN_FIELD_FALSE_VALUES:
            return False
        else:
            raise ValueError(f"Invalid value for boolean field: {value}")


class DateFieldType(FieldType):
    type = "date"
    model_class = DateField
    allowed_fields = [
        "date_format",
        "date_include_time",
        "date_time_format",
        "date_show_tzinfo",
        "date_force_timezone",
    ]
    serializer_field_names = [
        "date_format",
        "date_include_time",
        "date_time_format",
        "date_show_tzinfo",
        "date_force_timezone",
    ]
    request_serializer_field_names = serializer_field_names + [
        "date_force_timezone_offset",
    ]
    request_serializer_field_overrides = {
        "date_force_timezone_offset": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text=(
                "A UTC offset in minutes to add to all the field datetimes values.",
            ),
        )
    }
    serializer_field_extra_kwargs = {"date_force_timezone_offset": {"write_only": True}}
    api_exceptions_map = {
        DateForceTimezoneOffsetValueError: ERROR_DATE_FORCE_TIMEZONE_OFFSET_ERROR
    }
    _can_group_by = True
    _db_column_fields = ["date_include_time"]
    _can_have_db_index = True
    can_upsert = True

    def can_represent_date(self, field):
        return True

    def get_request_kwargs_to_backup(self, field, kwargs) -> Dict[str, Any]:
        date_force_timezone_offset = kwargs.get("date_force_timezone_offset", None)
        if date_force_timezone_offset:
            return {"date_force_timezone_offset": -date_force_timezone_offset}
        return {}

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        force_timezone_offset = field_kwargs.get("date_force_timezone_offset", None)
        if force_timezone_offset is not None:
            raise DateForceTimezoneOffsetValueError(
                "date_force_timezone_offset is not allowed when creating a date field."
            )

    def before_update(self, from_field, to_field_values, user, field_kwargs):
        force_timezone_offset = field_kwargs.get("date_force_timezone_offset", None)
        if not isinstance(from_field, DateField):
            return

        if force_timezone_offset is not None and not to_field_values.get(
            "date_include_time", from_field.date_include_time
        ):
            raise DateForceTimezoneOffsetValueError(
                "date_include_time must be set to true"
            )

    def after_update(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        user,
        connection,
        altered_column,
        before,
        to_field_kwargs,
    ):
        """
        If the date_force_timezone field is changed and
        date_force_timezone_offset is set to an integer value, we need to
        replace the timezone of all the values in the database by adding the
        utcOffset accordingly.
        """

        timezone_offset_to_add_to_replace_tz = to_field_kwargs.get(
            "date_force_timezone_offset", None
        )
        if timezone_offset_to_add_to_replace_tz is None:
            return

        to_model.objects.filter(**{f"{to_field.db_column}__isnull": False}).update(
            **{
                to_field.db_column: models.F(to_field.db_column)
                + timedelta(minutes=timezone_offset_to_add_to_replace_tz)
            }
        )

    def get_search_expression(
        self,
        field: Union[DateField, LastModifiedField, CreatedOnField],
        queryset: QuerySet,
    ) -> Expression:
        """
        Prepares a `DateField`, `LastModifiedField` or `CreatedOnField`
        for search, by converting the value to its timezone (if the field's
        `date_force_timezone` has been set, otherwise UTC) and then calling
        `to_char` so that it's formatted properly.
        """

        return Func(
            Func(
                # FIXME: what if date_force_timezone is None(user timezone)?
                Value(
                    field.date_force_timezone or "UTC", output_field=models.TextField()
                ),
                F(field.db_column),
                function="timezone",
                output_field=DateTimeField(),
            ),
            Value(field.get_psql_format()),
            function="to_char",
            output_field=models.TextField(),
        )

    def prepare_value_for_db(self, instance, value):
        """
        This method accepts a string, date object or datetime object. If the value is a
        string it will try to parse it using the dateutil's parser. Depending on the
        field's date_include_time, a date or datetime object will be returned. A
        datetime object will always have a UTC timezone. If the value is a datetime
        object with another timezone it will be converted to UTC.

        :param instance: The date field instance for which the value needs to be
            prepared.
        :type instance: DateField
        :param value: The value that needs to be prepared.
        :type value: str, date or datetime
        :return: The date or datetime field with the correct value.
        :rtype: date or datetime(tzinfo=UTC)
        :raises ValidationError: When the provided date string could not be converted
            to a date object.
        """

        if not value:
            return value

        if isinstance(value, str):
            try:
                # Try first to parse isodate
                value = parser.isoparse(value)
            except Exception:
                try:
                    if instance.date_format == "EU":
                        value = parser.parse(value, dayfirst=True)
                    elif instance.date_format == "ISO":
                        value = parser.parse(value, yearfirst=True)
                    else:
                        value = parser.parse(value)
                except ParserError as exc:
                    raise ValidationError(
                        "The provided string could not converted to a date.",
                        code="invalid",
                    ) from exc

        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

        if isinstance(value, datetime):
            value = value.astimezone(timezone.utc)
            return value if instance.date_include_time else value.date()

        raise ValidationError(
            "The value should be a date/time string, date object or datetime object.",
            code="invalid",
        )

    def get_export_value(self, value, field_object, rich_value=False):
        if value is None:
            return value if rich_value else ""

        field = field_object["field"]
        if isinstance(value, datetime) and field.date_force_timezone is not None:
            value = value.astimezone(ZoneInfo(field.date_force_timezone))

        return value.strftime(field.get_python_format())

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)

        if instance.date_include_time:
            return serializers.DateTimeField(
                **{"required": required, "allow_null": not required, **kwargs}
            )
        else:
            return serializers.DateField(
                **{"required": required, "allow_null": not required, **kwargs}
            )

    def get_model_field(self, instance, **kwargs):
        kwargs["null"] = True
        kwargs["blank"] = True
        kwargs["db_index"] = instance.db_index
        if instance.date_include_time:
            return models.DateTimeField(**kwargs)
        else:
            return models.DateField(**kwargs)

    def random_value(self, instance, fake, cache):
        if instance.date_include_time:
            return fake.date_time().replace(tzinfo=timezone.utc)
        else:
            return fake.date_object()

    def contains_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()

        # No user input goes into the RawSQL, safe to use.
        return AnnotatedQ(
            annotation={
                f"formatted_date_{field_name}": Coalesce(
                    Func(
                        Func(
                            # FIXME: what if date_force_timezone is None(user timezone)?
                            Value(field.date_force_timezone or "UTC"),
                            F(field_name),
                            function="timezone",
                            output_field=DateTimeField(),
                        ),
                        Value(field.get_psql_format()),
                        function="to_char",
                        output_field=CharField(),
                    ),
                    Value(""),
                    output_field=models.TextField(),
                )
            },
            q={f"formatted_date_{field_name}__icontains": value},
        )

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        """
        If the field type has changed then we want to convert the date or timestamp to
        a human readable text following the old date format.
        """

        to_field_type = field_type_registry.get_by_model(to_field)
        if to_field_type.type != self.type:
            sql_format = from_field.get_psql_format()
            variables = {}
            variable_name = f"{from_field.db_column}_timezone"
            # FIXME: what if date_force_timezone is None(user timezone)?
            variables[variable_name] = from_field.date_force_timezone or "UTC"
            return (
                f"""p_in = TO_CHAR(p_in::timestamptz at time zone %({variable_name})s,
                '{sql_format}');""",
                variables,
            )

        if (
            to_field.date_include_time is False
            and from_field.date_force_timezone is not None
        ):
            variables = {}
            variable_name = f"{from_field.db_column}_timezone"
            variables[variable_name] = from_field.date_force_timezone or "UTC"
            return (
                f"""p_in = (p_in::timestamptz at time zone %({variable_name})s)::date;""",
                variables,
            )

        return super().get_alter_column_prepare_old_value(
            connection, from_field, to_field
        )

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        """
        If the field type has changed into a date field then we want to parse the old
        text value following the format of the new field and convert it to a date or
        timestamp. If that fails we want to fallback on the default ::date or
        ::timestamp conversion that has already been added.
        """

        from_field_type = field_type_registry.get_by_model(from_field)
        if from_field_type.type != self.type and connection.vendor == "postgresql":
            sql_function = to_field.get_psql_type_convert_function()
            sql_format = to_field.get_psql_format()
            sql_type = to_field.get_psql_type()

            return f"""
                begin
                    IF char_length(p_in::text) < 5 THEN
                        p_in = null;
                    ELSEIF p_in IS NULL THEN
                        p_in = null;
                    ELSE
                        p_in = case when
                            {sql_function}(p_in::text, 'FM{sql_format}')
                            between '0001-01-01'::{sql_type}
                                and '9999-12-31'::{sql_type}
                            then
                                {sql_function}(p_in::text, 'FM{sql_format}')
                            else NULL
                            end;

                    END IF;
                exception when others then
                    begin
                        p_in = case when
                            p_in::{sql_type}
                            between '0001-01-01'::{sql_type}
                                and '9999-12-31'::{sql_type}
                            then
                                p_in::{sql_type}
                            else NULL
                            end;

                    exception when others then
                        p_in = p_default;
                    end;
                end;
            """

        return super().get_alter_column_prepare_old_value(
            connection, from_field, to_field
        )

    def get_export_serialized_value(self, row, field_name, cache, files_zip, storage):
        value = self.get_internal_value_from_db(row, field_name)

        if value is None:
            return value

        return value.isoformat()

    def set_import_serialized_value(
        self, row, field_name, value, id_mapping, cache, files_zip, storage
    ):
        if not value:
            return value

        if isinstance(row._meta.get_field(field_name), models.DateTimeField):
            value = datetime.fromisoformat(value)
        else:
            value = date.fromisoformat(value)

        setattr(row, field_name, value)

    def to_baserow_formula_type(self, field: DateField) -> BaserowFormulaType:
        return BaserowFormulaDateType(
            field.date_format,
            field.date_include_time,
            field.date_time_format,
            date_force_timezone=field.date_force_timezone,
            date_show_tzinfo=field.date_show_tzinfo,
            nullable=True,
        )

    def from_baserow_formula_type(
        self, formula_type: BaserowFormulaDateType
    ) -> DateField:
        return DateField(
            date_format=formula_type.date_format,
            date_include_time=formula_type.date_include_time,
            date_time_format=formula_type.date_time_format,
            date_force_timezone=formula_type.date_force_timezone,
            date_show_tzinfo=formula_type.date_show_tzinfo,
        )

    def should_backup_field_data_for_same_type_update(
        self, old_field: DateField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_date_include_time = new_field_attrs.get(
            "date_include_time", old_field.date_include_time
        )
        return old_field.date_include_time and not new_date_include_time

    def should_update_search_data(
        self, old_field: DateField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_date_include_time = new_field_attrs.get(
            "date_include_time", old_field.date_include_time
        )
        new_date_format = new_field_attrs.get("date_format", old_field.date_format)
        new_date_time_format = new_field_attrs.get(
            "date_time_format", old_field.date_time_format
        )
        new_force_timezone = new_field_attrs.get(
            "date_force_timezone", old_field.date_force_timezone
        )
        return (
            old_field.date_include_time != new_date_include_time
            or old_field.date_format != new_date_format
            or old_field.date_time_format != new_date_time_format
            or old_field.date_force_timezone != new_force_timezone
        )

    def serialize_metadata_for_row_history(
        self,
        field: Field,
        row: "GeneratedTableModel",
        metadata: Optional[SerializedRowHistoryFieldMetadata] = None,
    ) -> SerializedRowHistoryFieldMetadata:
        base = super().serialize_metadata_for_row_history(field, row, metadata)

        return {
            **base,
            "date_format": field.date_format,
            "date_include_time": field.date_include_time,
            "date_time_format": field.date_time_format,
            "date_show_tzinfo": field.date_show_tzinfo,
            "date_force_timezone": field.date_force_timezone,
        }

    def get_group_by_field_unique_value(
        self, field: Field, field_name: str, value: Any
    ) -> Any:
        if value and isinstance(value, datetime):
            # We want to ignore seconds and microseconds when grouping.
            value = value.replace(second=0, microsecond=0)
        return value

    def get_group_by_field_filters_and_annotations(
        self, field, field_name, base_queryset, value, cte, rows
    ):
        filters = {field_name: value}
        annotations = {}

        if value and isinstance(value, datetime):
            # DateTrunc cuts of every after the minute, so we can do a comparison
            # with the provided value that doesn't have the seconds and microseconds.
            annotations[field_name] = DateTrunc(
                "minute", field_name, output_field=models.DateTimeField(null=True)
            )
        return filters, annotations


class CreatedOnLastModifiedBaseFieldType(ReadOnlyFieldType, DateFieldType):
    can_be_in_form_view = False
    field_data_is_derived_from_attrs = True

    source_field_name = None
    model_field_class = SyncedDateTimeField
    model_field_kwargs = {}
    populate_from_field = None

    def get_serializer_field(self, instance, **kwargs):
        if not instance.date_include_time:
            kwargs["format"] = "%Y-%m-%d"

        return serializers.DateTimeField(**{"required": False, **kwargs})

    def get_model_field(self, instance, **kwargs):
        kwargs["null"] = True
        kwargs["blank"] = True
        kwargs["db_index"] = instance.db_index
        kwargs.update(self.model_field_kwargs)
        return self.model_field_class(**kwargs)

    def after_create(self, field, model, user, connection, before, field_kwargs):
        """
        Immediately after the field has been created, we need to populate the values
        with the already existing source_field_name column.
        """

        model.objects.all().update(
            **{f"{field.db_column}": models.F(self.source_field_name)}
        )

    def after_update(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        user,
        connection,
        altered_column,
        before,
        to_field_kwargs,
    ):
        """
        If the field type has changed, we need to update the values from
        the source_field_name column.
        """

        if not isinstance(from_field, self.model_class):
            to_model.objects.all().update(
                **{f"{to_field.db_column}": models.F(self.source_field_name)}
            )

    def set_import_serialized_value(
        self, row, field_name, value, id_mapping, cache, files_zip, storage
    ):
        """
        The `auto_now_add` and `auto_now` properties are set to False during the
        import. This allows us the set the correct from the import.
        """

        if value is None:
            value = getattr(row, self.source_field_name)
        else:
            value = datetime.fromisoformat(value)

        setattr(row, field_name, value)

    def random_value(self, instance, fake, cache):
        return getattr(instance, self.source_field_name)

    def should_backup_field_data_for_same_type_update(
        self, old_field, new_field_attrs: Dict[str, Any]
    ) -> bool:
        return False


class LastModifiedFieldType(CreatedOnLastModifiedBaseFieldType):
    type = "last_modified"
    model_class = LastModifiedField
    update_always = True
    source_field_name = "updated_on"
    model_field_class = BaserowLastModifiedField
    model_field_kwargs = {"sync_with": "updated_on"}


class CreatedOnFieldType(CreatedOnLastModifiedBaseFieldType):
    type = "created_on"
    model_class = CreatedOnField
    source_field_name = "created_on"
    model_field_kwargs = {"sync_with_add": "created_on"}


class LastModifiedByFieldType(ReadOnlyFieldType):
    type = "last_modified_by"
    model_class = LastModifiedByField
    can_be_in_form_view = False
    keep_data_on_duplication = True
    update_always = True

    source_field_name = "last_modified_by"
    model_field_kwargs = {"sync_with": "last_modified_by"}
    request_serializer_field_names = []
    request_serializer_field_overrides = {}
    serializer_field_names = ["available_collaborators"]
    serializer_field_overrides = {
        "available_collaborators": AvailableCollaboratorsSerializer(),
    }

    def can_represent_collaborators(self, field):
        return True

    def get_model_field(self, instance, **kwargs):
        kwargs["null"] = True
        kwargs["blank"] = True
        kwargs.update(self.model_field_kwargs)
        return SyncedUserForeignKeyField(
            User,
            on_delete=models.SET_NULL,
            related_name="+",
            related_query_name="+",
            db_constraint=False,
            **kwargs,
        )

    def get_serializer_field(self, instance, **kwargs):
        return CollaboratorSerializer(required=False, **kwargs)

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        """
        If last_modified_by column is still not present on the table,
        we need to create it first.
        """

        if not table.last_modified_by_column_added:
            table_to_update = TableHandler().get_table_for_update(table.id)
            TableHandler().create_created_by_and_last_modified_by_fields(
                table_to_update
            )
            table.refresh_from_db()

    def after_create(self, field, model, user, connection, before, field_kwargs):
        """
        Immediately after the field has been created, we need to populate the values
        with the already existing source_field_name column.
        """

        model.objects.all().update(
            **{f"{field.db_column}": models.F(self.source_field_name)}
        )

    def after_update(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        user,
        connection,
        altered_column,
        before,
        to_field_kwargs,
    ):
        """
        If the field type has changed, we need to update the values from
        the source_field_name column.
        """

        if not isinstance(from_field, self.model_class):
            to_model.objects.all().update(
                **{f"{to_field.db_column}": models.F(self.source_field_name)}
            )

    def enhance_queryset(self, queryset, field, name, **kwargs):
        return queryset.select_related(name)

    def should_backup_field_data_for_same_type_update(
        self, old_field, new_field_attrs: Dict[str, Any]
    ) -> bool:
        return False

    def random_value(self, instance, fake, cache):
        return None

    def get_export_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        cache: Dict[str, Any],
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Any:
        """
        Exported value will be the user's email address.
        """

        user = self.get_internal_value_from_db(row, field_name)
        return user.email if user else None

    def set_import_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        cache: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        """
        Importing will use the value from source_field_name column.
        """

        value = getattr(row, self.source_field_name)
        setattr(row, field_name, value)

    def get_internal_value_from_db(
        self, row: "GeneratedTableModel", field_name: str
    ) -> Any:
        return getattr(row, field_name)

    def get_export_value(
        self, value: Any, field_object: "FieldObject", rich_value: bool = False
    ) -> Any:
        """
        Exported value will be the user's email address.
        """

        user = value
        return user.email if user else None

    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ) -> OptionallyAnnotatedOrderBy:
        """
        If the user wants to sort the results they expect them to be ordered
        alphabetically based on the user's name.
        """

        order = collate_expression(
            self.get_sortable_column_expression(field, field_name, sort_type)
        )

        if order_direction == "ASC":
            order = order.asc(nulls_first=True)
        else:
            order = order.desc(nulls_last=True)
        return OptionallyAnnotatedOrderBy(order=order)

    def get_value_for_filter(self, row: "GeneratedTableModel", field: Field) -> any:
        value = getattr(row, field.db_column)
        if value is None:
            return None
        return collate_expression(Value(value.first_name))

    def get_search_expression(self, field: Field, queryset: QuerySet) -> Expression:
        return Subquery(
            queryset.filter(pk=OuterRef("pk")).values(f"{field.db_column}__first_name")[
                :1
            ]
        )

    def contains_query(self, field_name, value, model_field, field):
        value = value.strip()
        if value == "":
            return Q()
        return Q(**{f"{field_name}__first_name__icontains": value})

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        """
        When converting to last modified by field type we won't preserve any
        values.
        """

        # fmt: off
        sql = (
            f"""
            p_in = NULL;
            """  # nosec b608
        )
        # fmt: on
        return sql, {}

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        """
        When converting to another field type we won't preserve any values.
        """

        to_field_type = field_type_registry.get_by_model(to_field)
        if to_field_type.type != self.type and connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

            # fmt: off
            sql = (
                f"""
                p_in = NULL;
                """  # nosec b608
            )
            # fmt: on
            return sql, {}

        return super().get_alter_column_prepare_old_value(
            connection, from_field, to_field
        )

    def get_sortable_column_expression(
        self,
        field: Field,
        field_name: str,
        sort_type: str,
    ) -> Expression | F:
        return F(f"{field_name}__first_name")

    def get_distribution_group_by_value(self, field_name: str):
        return f"{field_name}__first_name"


class CreatedByFieldType(ReadOnlyFieldType):
    type = "created_by"
    model_class = CreatedByField
    can_be_in_form_view = False
    keep_data_on_duplication = True

    source_field_name = "created_by"
    model_field_kwargs = {"sync_with_add": "created_by"}
    request_serializer_field_names = []
    request_serializer_field_overrides = {}
    serializer_field_names = ["available_collaborators"]
    serializer_field_overrides = {
        "available_collaborators": AvailableCollaboratorsSerializer(),
    }

    def can_represent_collaborators(self, field):
        return True

    def get_model_field(self, instance, **kwargs):
        kwargs["null"] = True
        kwargs["blank"] = True
        kwargs.update(self.model_field_kwargs)
        return SyncedUserForeignKeyField(
            User,
            on_delete=models.SET_NULL,
            related_name="+",
            related_query_name="+",
            db_constraint=False,
            **kwargs,
        )

    def get_serializer_field(self, instance, **kwargs):
        return CollaboratorSerializer(required=False, **kwargs)

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        """
        If created_by column is still not present on the table,
        we need to create it first.
        """

        if not table.created_by_column_added:
            table_to_update = TableHandler().get_table_for_update(table.id)
            TableHandler().create_created_by_and_last_modified_by_fields(
                table_to_update
            )
            table.refresh_from_db()

    def after_create(self, field, model, user, connection, before, field_kwargs):
        """
        Immediately after the field has been created, we need to populate the values
        with the already existing source_field_name column.
        """

        model.objects.all().update(
            **{f"{field.db_column}": models.F(self.source_field_name)}
        )

    def after_update(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        user,
        connection,
        altered_column,
        before,
        to_field_kwargs,
    ):
        """
        If the field type has changed, we need to update the values from
        the source_field_name column.
        """

        if not isinstance(from_field, self.model_class):
            to_model.objects.all().update(
                **{f"{to_field.db_column}": models.F(self.source_field_name)}
            )

    def enhance_queryset(self, queryset, field, name, **kwargs):
        return queryset.select_related(name)

    def should_backup_field_data_for_same_type_update(
        self, old_field, new_field_attrs: Dict[str, Any]
    ) -> bool:
        return False

    def random_value(self, instance, fake, cache):
        return None

    def get_export_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        cache: Dict[str, Any],
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Any:
        """
        Exported value will be the user's email address.
        """

        user = self.get_internal_value_from_db(row, field_name)
        return user.email if user else None

    def set_import_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        cache: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ):
        """
        Importing will use the value from source_field_name column.
        """

        value = getattr(row, self.source_field_name)
        setattr(row, field_name, value)

    def get_internal_value_from_db(
        self, row: "GeneratedTableModel", field_name: str
    ) -> Any:
        return getattr(row, field_name)

    def get_export_value(
        self, value: Any, field_object: "FieldObject", rich_value: bool = False
    ) -> Any:
        """
        Exported value will be the user's email address.
        """

        user = value
        return user.email if user else None

    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ) -> OptionallyAnnotatedOrderBy:
        """
        If the user wants to sort the results they expect them to be ordered
        alphabetically based on the user's name.
        """

        order = collate_expression(
            self.get_sortable_column_expression(field, field_name, sort_type)
        )

        if order_direction == "ASC":
            order = order.asc(nulls_first=True)
        else:
            order = order.desc(nulls_last=True)
        return OptionallyAnnotatedOrderBy(order=order)

    def get_value_for_filter(self, row: "GeneratedTableModel", field: Field) -> any:
        value = getattr(row, field.db_column)
        if value is None:
            return None
        return collate_expression(Value(value.first_name))

    def get_search_expression(self, field: Field, queryset: QuerySet) -> Expression:
        return Subquery(
            queryset.filter(pk=OuterRef("pk")).values(f"{field.db_column}__first_name")[
                :1
            ]
        )

    def contains_query(self, field_name, value, model_field, field):
        value = value.strip()
        if value == "":
            return Q()
        return Q(**{f"{field_name}__first_name__icontains": value})

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        """
        When converting to created by field type we won't preserve any
        values.
        """

        # fmt: off
        sql = (
            f"""
            p_in = NULL;
            """  # nosec b608
        )
        # fmt: on
        return sql, {}

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        """
        When converting to another field type we won't preserve any values.
        """

        to_field_type = field_type_registry.get_by_model(to_field)
        if to_field_type.type != self.type and connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

            # fmt: off
            sql = (
                f"""
                p_in = NULL;
                """  # nosec b608
            )
            # fmt: on
            return sql, {}

        return super().get_alter_column_prepare_old_value(
            connection, from_field, to_field
        )

    def get_sortable_column_expression(
        self,
        field: Field,
        field_name: str,
        sort_type: str,
    ) -> Expression | F:
        return F(f"{field_name}__first_name")

    def get_distribution_group_by_value(self, field_name: str):
        return f"{field_name}__first_name"


class DurationFieldType(FieldType):
    type = "duration"
    model_class = DurationField
    allowed_fields = ["duration_format"]
    serializer_field_names = ["duration_format"]
    _can_group_by = True
    _db_column_fields = []
    can_upsert = True

    def get_model_field(self, instance: DurationField, **kwargs):
        return DurationModelField(instance.duration_format, null=True, **kwargs)

    def get_serializer_field(self, instance: DurationField, **kwargs):
        return DurationFieldSerializer(
            **{
                "required": False,
                "allow_null": True,
                "duration_format": instance.duration_format,
                **kwargs,
            },
        )

    def get_serializer_help_text(self, instance: DurationField):
        return (
            "The provided value can be a string in one of the available formats "
            "or a number representing the duration in seconds. In any case, the "
            "value will be rounded to match the field's duration format."
        )

    def prepare_value_for_db(self, instance: DurationField, value):
        return prepare_duration_value_for_db(value, instance.duration_format)

    def get_search_expression(self, field: Field, queryset: QuerySet) -> Expression:
        return get_duration_search_expression(field)

    def random_value(self, instance: DurationField, fake, cache):
        random_seconds = fake.random.random() * 60 * 60 * 24
        # if we have days in the format, ensure the random value is picked accordingly
        if "d" in instance.duration_format:
            random_seconds *= 30
        return duration_value_to_timedelta(random_seconds, instance.duration_format)

    def get_alter_column_prepare_old_value(
        self, connection, from_field: DurationField, to_field: Field
    ):
        to_field_type = field_type_registry.get_by_model(to_field)
        if to_field_type.type in (TextFieldType.type, LongTextFieldType.type):
            return f"p_in = {duration_value_sql_to_text(from_field)};"
        elif to_field_type.type == NumberFieldType.type:
            return "p_in = EXTRACT(EPOCH FROM CAST(p_in AS INTERVAL))::NUMERIC;"

    def get_alter_column_prepare_new_value(
        self, connection, from_field: Field, to_field: DurationField
    ):
        from_field_type = field_type_registry.get_by_model(from_field)

        if from_field_type.type in (NumberFieldType.type, self.type):
            duration_format = to_field.duration_format
            sql_round_func = DURATION_FORMATS[duration_format]["sql_round_func"]

            return f"p_in = make_interval(secs=>{sql_round_func});"
        elif from_field_type.type in (TextFieldType.type, LongTextFieldType.type):
            return f"p_in = {text_value_sql_to_duration(to_field)}"

    def serialize_to_input_value(self, field: Field, value: any) -> any:
        return value.total_seconds()

    def format_duration(
        self, value: Optional[timedelta], duration_format: str
    ) -> Optional[str]:
        """
        Formats a timedelta object to a string based on the provided duration_format.

        :param value: The timedelta object that needs to be formatted.
        :param duration_format: The format that needs to be used.
        :return: The formatted string.
        """

        return format_duration_value(value, duration_format)

    def get_export_value(
        self,
        value: Optional[timedelta],
        field_object: "FieldObject",
        rich_value: bool = False,
    ) -> Optional[str]:
        field = field_object["field"]
        duration_format = field.duration_format
        return self.format_duration(value, duration_format)

    def should_backup_field_data_for_same_type_update(
        self, old_field: DurationField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_duration_format = new_field_attrs.get(
            "duration_format", old_field.duration_format
        )

        return is_duration_format_conversion_lossy(
            new_duration_format, old_field.duration_format
        )

    def should_update_search_data(
        self, old_field: DurationField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_duration_format = new_field_attrs.get(
            "duration_format", old_field.duration_format
        )

        return is_duration_format_conversion_lossy(
            new_duration_format, old_field.duration_format
        )

    def force_same_type_alter_column(self, from_field, to_field):
        return is_duration_format_conversion_lossy(
            to_field.duration_format, from_field.duration_format
        )

    def serialize_metadata_for_row_history(
        self,
        field: Field,
        row: "GeneratedTableModel",
        metadata: Optional[SerializedRowHistoryFieldMetadata] = None,
    ) -> SerializedRowHistoryFieldMetadata:
        base = super().serialize_metadata_for_row_history(field, row, metadata)

        return {**base, "duration_format": field.duration_format}

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaDurationType(
            duration_format=field.duration_format, nullable=True
        )

    def from_baserow_formula_type(self, formula_type: BaserowFormulaCharType):
        return self.model_class(duration_format=formula_type.duration_format)

    def get_export_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        cache: Dict[str, Any],
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Any:
        duration = self.get_internal_value_from_db(row, field_name)
        if duration is None:
            return None

        return duration.total_seconds()

    def set_import_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        cache: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Optional[List[models.Model]]:
        field = row._meta.get_field(field_name)
        if value is not None:
            value = duration_value_to_timedelta(value, field.duration_format)

        setattr(row, field_name, value)

    def get_sortable_column_expression(
        self,
        field: Field,
        field_name: str,
        sort_type: str,
    ) -> Expression | F:
        return F(f"{field_name}")


class LinkRowFieldType(
    ManyToManyFieldTypeSerializeToInputValueMixin, ManyToManyGroupByMixin, FieldType
):
    """
    The link row field can be used to link a field to a row of another table. Because
    the user should also be able to see which rows are linked to the related table,
    another link row field in the related table is automatically created.
    """

    type = "link_row"
    model_class = LinkRowField
    allowed_fields = [
        "link_row_table_id",
        "link_row_related_field",
        "link_row_table",
        "link_row_relation_id",
        "link_row_limit_selection_view_id",
        "link_row_limit_selection_view",
        "link_row_multiple_relationships",
    ]
    serializer_field_names = [
        "link_row_table_id",
        "link_row_related_field_id",
        "link_row_table",
        "link_row_related_field",
        "link_row_limit_selection_view_id",
        "link_row_table_primary_field",
        "link_row_multiple_relationships",
    ]
    serializer_extra_args = ["limit_linked_items"]
    serializer_mixins = [LinkRowFieldSerializerMixin]
    serializer_field_overrides = {
        "link_row_table_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="link_row_table.id",
            help_text="The id of the linked table.",
        ),
        "link_row_related_field_id": serializers.PrimaryKeyRelatedField(
            read_only=True, required=False, help_text="The id of the related field."
        ),
        "link_row_table": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="link_row_table.id",
            help_text="(Deprecated) The id of the linked table.",
        ),
        "link_row_related_field": serializers.PrimaryKeyRelatedField(
            read_only=True,
            required=False,
            help_text="(Deprecated) The id of the related field.",
        ),
        "link_row_limit_selection_view_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The ID of the view in the related table where row selection "
            "must be limited to.",
        ),
    }
    request_serializer_field_names = [
        "link_row_table_id",
        "link_row_table",
        "has_related_field",
        "link_row_limit_selection_view_id",
        "link_row_multiple_relationships",
    ]
    request_serializer_field_overrides = {
        "has_related_field": serializers.BooleanField(required=False),
        "link_row_table_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="link_row_table.id",
            help_text="The id of the linked table.",
        ),
        "link_row_table": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="link_row_table.id",
            help_text="(Deprecated) The id of the linked table.",
        ),
        "link_row_limit_selection_view_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            # The default value is `-1` because anything lower than 0 will be
            # ignored. This allows clearing the value by providing `None`,
            # but ignoring it if not provided.
            default=-1,
            help_text="The ID of the view in the related table where row selection "
            "must be limited to.",
        ),
        "link_row_multiple_relationships": serializers.BooleanField(
            required=False,
            help_text="Indicates whether it's allowed set multiple relationships per "
            "row. If disabled, it doesn't guarantee single relationships because they "
            "could have already existed or created through reversed relationship.",
        ),
    }

    api_exceptions_map = {
        LinkRowTableNotProvided: ERROR_LINK_ROW_TABLE_NOT_PROVIDED,
        LinkRowTableNotInSameDatabase: ERROR_LINK_ROW_TABLE_NOT_IN_SAME_DATABASE,
        IncompatiblePrimaryFieldTypeError: ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE,
        SelfReferencingLinkRowCannotHaveRelatedField: ERROR_SELF_REFERENCING_LINK_ROW_CANNOT_HAVE_RELATED_FIELD,
        ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
        ViewNotInTable: ERROR_VIEW_NOT_IN_TABLE,
    }
    _can_be_primary_field = False
    can_get_unique_values = False
    is_many_to_many_field = True
    can_be_target_of_adhoc_lookup = False

    def _get_related_table_primary_field(
        self, field: Field, table_model: Optional["GeneratedTableModel"] = None
    ) -> Optional[Field]:
        # If provided, use the table_model to find the related_primary_field to avoid
        # potential unnecessary queries.
        if table_model is not None:
            model_field_name = table_model.get_field_object_by_id(field.id)["name"]
            model_field = getattr(table_model, model_field_name).field
            remote_table_model = model_field.remote_field.model
            return remote_table_model.get_primary_field()
        else:
            return field.specific.link_row_table_primary_field

    def _check_related_field_can_order_by(
        self,
        related_primary_field: Type[Field],
        order_type: str,
    ) -> bool:
        related_primary_field_type = field_type_registry.get_by_model(
            related_primary_field.specific_class
        )
        return related_primary_field_type.check_can_order_by(
            related_primary_field.specific, order_type
        )

    def check_can_group_by(self, field, sort_type):
        related_primary_field = self._get_related_table_primary_field(field)
        if related_primary_field is None:
            return False
        related_primary_field = related_primary_field.specific
        related_primary_field_type = field_type_registry.get_by_model(
            related_primary_field
        )
        return related_primary_field_type.check_can_group_by(
            related_primary_field, sort_type
        )

    def _get_group_by_agg_expression(self, field_name: str) -> dict:
        return ArrayAgg(
            f"{field_name}__id",
            filter=Q(
                **{
                    f"{field_name}__isnull": False,
                    f"{field_name}__trashed": False,
                }
            ),
            distinct=True,
        )

    def check_can_order_by(self, field: Field, sort_type: str) -> bool:
        related_primary_field = self._get_related_table_primary_field(field)
        if related_primary_field is None:
            return False
        return self._check_related_field_can_order_by(
            related_primary_field.specific, sort_type
        )

    def get_value_for_filter(self, row: "GeneratedTableModel", field):
        related_primary_field = self._get_related_table_primary_field(
            field, row._meta.model
        )
        if related_primary_field is None:
            return None
        related_primary_field = related_primary_field.specific
        related_primary_field_type = field_type_registry.get_by_model(
            related_primary_field
        )
        return related_primary_field_type.get_value_for_filter(
            row, related_primary_field
        )

    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ):
        related_primary_field = self._get_related_table_primary_field(
            field, table_model
        )
        if related_primary_field is None:
            raise ValueError("Cannot find the related primary field.")

        related_primary_field = related_primary_field.specific
        if not self._check_related_field_can_order_by(
            related_primary_field, DEFAULT_SORT_TYPE_KEY
        ):
            raise ValueError(
                "The primary field for the related table cannot be ordered by."
            )
        related_primary_field_type = field_type_registry.get_by_model(
            related_primary_field
        )
        sortable_column_expr = (
            related_primary_field_type.get_sortable_column_expression(
                related_primary_field,
                f"{field_name}__{related_primary_field.db_column}",
                sort_type,
            )
        )

        def get_array_agg(expr):
            return ArrayAgg(
                expr,
                filter=Q(
                    **{f"{field_name}__isnull": False, f"{field_name}__trashed": False}
                ),
                ordering=(f"{field_name}__order", f"{field_name}__id"),
            )

        value_query = get_array_agg(sortable_column_expr)
        order_query = get_array_agg(F(f"{field_name}__order"))
        id_query = get_array_agg(F(f"{field_name}__id"))

        linked_value_column_name = f"{field_name}_{related_primary_field.db_column}"
        # If the value are the same for multiple rows, we don't want Postgres to return
        # them randomly, so we add the order and id of the rows in the linked table to
        # make the ordering deterministic.
        linked_order_column_name = (
            f"{field_name}_{related_primary_field.db_column}_order"
        )
        linked_id_column_name = f"{field_name}_{related_primary_field.db_column}_id"
        annotation = {
            linked_value_column_name: value_query,
            linked_order_column_name: order_query,
            linked_id_column_name: id_query,
        }

        linked_value = F(linked_value_column_name)
        linked_order = F(linked_order_column_name)
        linked_id = F(linked_id_column_name)
        if isinstance(related_primary_field_type, CollationSortMixin):
            linked_value = collate_expression(linked_value)

        if order_direction == "DESC":
            linked_value = linked_value.desc(nulls_first=True)
            linked_order = linked_order.desc()
            linked_id = linked_id.desc()
        else:
            linked_value = linked_value.asc(nulls_first=True)
            linked_order = linked_order.asc()
            linked_id = linked_id.asc()

        return OptionallyAnnotatedOrderBy(
            annotation=annotation,
            order=[linked_value, linked_order, linked_id],
        )

    def get_search_expression(self, field: Field, queryset: QuerySet) -> Expression:
        remote_field = queryset.model._meta.get_field(field.db_column).remote_field
        remote_model = remote_field.model

        primary_field_object = next(
            (
                object
                for object in remote_model._field_objects.values()
                if object["field"].primary
            ),
            None,
        )
        if primary_field_object is None:
            # Every table should have a primary field, but it's not strictly enforeced
            # and if it doesn't (i.e. some tests), we return an empty expression.
            return Value("")

        primary_field = primary_field_object["field"]
        primary_field_type = primary_field_object["type"]
        qs = remote_model.objects.filter(
            **{f"{remote_field.related_name}__id": OuterRef("pk")}
        ).order_by()
        # noinspection PyTypeChecker
        return Subquery(
            # This first values call forces django to group by the ID of the outer
            # table we are updating rows in.
            qs.values(f"{remote_field.related_name}__id")
            .annotate(
                value=StringAgg(
                    primary_field_type.get_search_expression(
                        primary_field, remote_model.objects
                    ),
                    " ",
                    output_field=models.TextField(),
                )
            )
            .values("value")[:1]
        )

    def enhance_queryset(self, queryset, field, name, **kwargs):
        """
        Makes sure that the related rows are prefetched by Django. We also want to
        enhance the primary field of the related queryset. If for example the primary
        field is a single select field then the dropdown options need to be
        prefetched in order to prevent many queries.

        Additionaly we need to prefetch any other requested field for adhoc lookups
        that are passed as LinkRowJoins in the kwargs.
        """

        remote_model = queryset.model._meta.get_field(name).remote_field.model
        related_queryset = remote_model.objects.all()

        # determine if there are link row joins to take care of
        field_kwargs = kwargs.get(f"field_{field.id}", {})
        link_row_join = field_kwargs.get("link_row_join", None)

        primary_field_object = next(
            (
                object
                for object in remote_model._field_objects.values()
                if object["field"].primary
            ),
            None,
        )

        # The list of fields to prefetch is going to be the primary field
        # if it exists together with any joined field for lookup
        target_field_names = (
            [primary_field_object["name"]] if primary_field_object is not None else []
        )
        if link_row_join is not None:
            target_field_names += [
                f"field_{tf.field_id}" for tf in link_row_join.target_fields
            ]

        if len(target_field_names) > 0:
            related_queryset = related_queryset.only("order", *target_field_names)
            for target_field_name in target_field_names:
                field_obj = remote_model.get_field_object(target_field_name)
                related_queryset = field_obj["type"].enhance_queryset(
                    related_queryset,
                    field_obj["field"],
                    field_obj["name"],
                )

        return queryset.prefetch_related(
            models.Prefetch(name, queryset=related_queryset)
        )

    def enhance_field_queryset(
        self, queryset: QuerySet[Field], field: Field
    ) -> QuerySet[Field]:
        base_field_queryset = FieldHandler().get_base_fields_queryset()
        return queryset.prefetch_related(
            models.Prefetch(
                "link_row_table__field_set",
                queryset=specific_queryset(base_field_queryset.filter(primary=True)),
                to_attr=LinkRowField.RELATED_PPRIMARY_FIELD_ATTR,
            )
        )

    def prepare_value_for_db(self, instance, value):
        return self.prepare_value_for_db_in_bulk(
            instance, {0: value}, continue_on_error=False
        )[0]

    def prepare_value_for_db_in_bulk(
        self, instance, values_by_row, continue_on_error=False
    ):
        # Create a map {value -> row_indexes} for ids and strings
        name_map = defaultdict(list)
        invalid_values = []

        def preprocess_value(val):
            return val.strip() if isinstance(val, str) else val

        for row_index, values in values_by_row.items():
            if (
                instance.link_row_multiple_relationships is False
                and isinstance(values, list)
                and len(values) > 1
            ):
                error = ValidationError(
                    f"This link row field only accept one relationship.",
                    code="invalid_value",
                )
                if continue_on_error:
                    for row_index in invalid_values:
                        values_by_row[row_index] = error
                else:
                    raise error
            values_by_row[row_index] = [preprocess_value(val) for val in values]

        for row_index, values in values_by_row.items():
            for row_name_or_id in values:
                if isinstance(row_name_or_id, int):
                    continue
                elif isinstance(row_name_or_id, str):
                    name_map[row_name_or_id].append(row_index)
                else:
                    invalid_values.append(values)
                    break

        if invalid_values:
            if continue_on_error:
                # Replace values by error for failing rows
                for row_index in invalid_values:
                    values_by_row[row_index] = AllProvidedValuesMustBeIntegersOrStrings(
                        values_by_row[row_index]
                    )
            else:
                raise ValidationError(
                    f"The provided link row values {invalid_values} are not "
                    "valid integer or string.",
                    code="invalid_value",
                )

        if name_map:
            # It's a row name -> try to get the corresponding row
            (
                related_model,
                primary_field,
            ) = self._get_related_model_and_primary_field(instance)

            primary_field_type = field_type_registry.get_by_model(
                primary_field["field"]
            )

            # Here we use the can_get_unique_values flag as it seems to filter out
            # the field types we don't want. For now we don't want the field type
            # That can't be filtered easily later like multiple_select, file field
            # or another link row field.
            # Maybe this property isn't a good fit or maybe the name can be improve
            # later.
            if not primary_field_type.can_get_unique_values:
                error = ValidationError(
                    f"The primary field type '{primary_field_type.type}' of the "
                    "linked table doesn't support text values.",
                    code="invalid_value",
                )
                if continue_on_error:
                    for row_ids in name_map.values():
                        for row_index in row_ids:
                            values_by_row[row_index] = error
                else:
                    raise error

            search_values = []
            for name, row_ids in name_map.items():
                try:
                    search_values.append(
                        primary_field_type.parse_field_value_for_db(
                            primary_field["field"], name
                        )
                    )
                except ValidationError as e:
                    error = ValidationError(
                        f"The value '{name}' is an invalid value for the primary field "
                        "of the linked table.",
                        code="invalid_value",
                    )
                    if continue_on_error:
                        # Replace values by error for failing rows
                        for row_index in row_ids:
                            values_by_row[row_index] = error
                    else:
                        raise e

            # Get all matching rows
            rows = related_model.objects.filter(
                **{f"{primary_field['name']}__in": search_values}
            )

            # Map value with row id. Order is reversed to let the first row wins
            # Values are mapped back to their string representation to be compared
            # by the given text value
            row_map = {
                (
                    str(
                        primary_field["type"].get_export_value(
                            getattr(r, primary_field["name"]), primary_field
                        )
                    )
                ): r.id
                for r in rows[::-1]
            }

            rows_that_needs_name_replacement = {
                val for value in name_map.values() for val in value
            }

            # Replace all row names with actual row ids
            for row_index in rows_that_needs_name_replacement:
                values = values_by_row[row_index]
                if not isinstance(values, list):  # filter rows with exceptions
                    continue

                new_values = []
                for val in values:
                    if isinstance(val, int):
                        new_values.append(val)
                        continue

                    if val in row_map:
                        new_values.append(row_map[val])
                        continue

                    # If we get there, it's a name that doesn't exist in the linked
                    # table
                    error = ValidationError(
                        f"The provided text value '{val}' doesn't match any row in "
                        "the linked table.",
                        code="missing_row",
                    )
                    if continue_on_error:
                        values_by_row[row_index] = error
                        break
                    else:
                        raise error

                values_by_row[row_index] = new_values

        # Removes duplicate ids keeping ordering
        values_by_row = {
            k: list(dict.fromkeys(v)) if isinstance(v, list) else v
            for k, v in values_by_row.items()
        }
        return values_by_row

    def get_export_value(self, value, field_object, rich_value=False):
        def map_to_export_value(inner_value, inner_field_object):
            return inner_field_object["type"].get_export_value(
                inner_value, inner_field_object, rich_value=rich_value
            )

        result = self._get_and_map_pk_values(field_object, value, map_to_export_value)

        if rich_value:
            return result
        else:
            return list_to_comma_separated_string(result)

    def get_internal_value_from_db(
        self, row: "GeneratedTableModel", field_name: str
    ) -> List[int]:
        """
        Returns the list of ids for the related rows.

        :param row: The table row instance
        :param field_name: The name of the field.
        :return: A list of related rows ids.
        """

        related_rows = getattr(row, field_name)
        return [related_row.id for related_row in related_rows.all()]

    def get_human_readable_value(self, value, field_object):
        def map_to_human_readable_value(inner_value, inner_field_object):
            return inner_field_object["type"].get_human_readable_value(
                inner_value, inner_field_object
            )

        return ", ".join(
            self._get_and_map_pk_values(
                field_object, value, map_to_human_readable_value
            )
        )

    def _get_related_model_and_primary_field(self, instance):
        """
        Returns related model and primary field.
        """

        if hasattr(instance, "_related_model"):
            related_model = instance._related_model
        else:
            related_model = instance.link_row_table.get_model()

        primary_field = next(
            object
            for object in related_model._field_objects.values()
            if object["field"].primary
        )

        return related_model, primary_field

    def _get_and_map_pk_values(
        self, field_object, value, map_func: Callable[[Any, Dict[str, Any]], Any]
    ):
        """
        Helper function which given a linked row field pointing at another model,
        constructs a list of the related row's primary key values which are mapped by
        the provided map_func function.

        For example, Table A has Field 1 which links to Table B. Table B has a text
        primary key column. This function takes the value for a single row of
        Field 1, which is a number of related rows in Table B. It then gets
        the primary key column values for those related rows in Table B and applies
        map_func to each individual value. Finally it returns those mapped values as a
        list.

        :param value: The value of the link field in a specific row.
        :param field_object: The field object for the link field.
        :param map_func: A function to apply to each linked primary key value.
        :return: A list of mapped linked primary key values.
        """

        instance = field_object["field"]
        if hasattr(instance, "_related_model"):
            _, primary_field = self._get_related_model_and_primary_field(instance)

            if primary_field:
                primary_field_name = primary_field["name"]
                primary_field_values = []
                for sub in value.all():
                    # Ensure we also convert the value from the other table to it's
                    # appropriate form as it could be an odd field type!
                    linked_value = getattr(sub, primary_field_name)
                    if self._is_unnamed_primary_field_value(linked_value):
                        linked_pk_value = f"unnamed row {sub.id}"
                    else:
                        linked_pk_value = map_func(
                            getattr(sub, primary_field_name), primary_field
                        )
                    primary_field_values.append(linked_pk_value)
                return primary_field_values
        return []

    @staticmethod
    def _is_unnamed_primary_field_value(primary_field_value):
        """
        Checks if the value for a linked primary field is considered "unnamed".
        :param primary_field_value: The value of a primary field row in a linked table.
        :return: If this value is considered an unnamed primary field value.
        """

        if isinstance(primary_field_value, list):
            return len(primary_field_value) == 0
        elif isinstance(primary_field_value, dict):
            return len(primary_field_value.keys()) == 0
        else:
            return primary_field_value is None

    def get_serializer_field(self, instance, **kwargs):
        """
        If the value is going to be updated we want to accept a list of integers
        representing the related row ids.
        """

        required = kwargs.pop("required", False)
        kwargs.pop("limit_linked_items", None)  # not needed in the request.

        if instance.link_row_multiple_relationships is False:
            kwargs["max_length"] = 1
        return LinkRowRequestSerializer(required=required, **kwargs)

    def get_response_serializer_field(self, instance, **kwargs):
        """
        If a model has already been generated it will be added as a property to the
        instance. If that is the case then we can extract the primary field from the
        model and we can pass the name along to the LinkRowValueSerializer. It will
        be used to include the primary field's value in the response as a string.

        Optionally, if link_row_join kwarg is passed, the serializer will also include
        serializer fields for all the joined target fields.
        """

        link_row_join: LinkRowJoin = kwargs.pop("link_row_join", None)
        if link_row_join is None:
            inner_serializer = LinkRowValueSerializer
        else:
            inner_serializer = type(
                str("LinkRowLookupValueSerializer"),
                (LinkRowValueSerializer,),
                {
                    f"{target_field.field_ref}": target_field.field_serializer
                    for target_field in link_row_join.target_fields
                },
            )

        return LimitListSerializer(
            child=inner_serializer(),
            **{
                "required": False,
                "limit": kwargs.pop("limit_linked_items", None),
                **kwargs,
            },
        )

    def get_serializer_help_text(self, instance):
        return (
            "This field accepts an `array` containing the ids or the names of the "
            "related rows. "
            "A name is the value of the primary key of the related row. "
            "This field also accepts a string with names separated by a comma or an "
            "array of row names. You can also provide a unique row Id."
            "The response contains a list of objects containing the `id` and "
            "the primary field's `value` as a string for display purposes."
        )

    def get_model_field(self, instance, **kwargs):
        """
        A model field is not needed because the ManyToMany field is going to be added
        after the model has been generated.
        """

        return None

    def after_model_generation(self, instance, model, field_name):
        # Store the current table's model into the manytomany_models object so that the
        # related ManyToMany field can use that one. Otherwise we end up in a recursive
        # loop.
        model_name = model._meta.model_name
        model.baserow_models[model_name] = model

        # Check if the related table model is already in the model.baserow_models.
        if instance.is_self_referencing:
            related_model = model
        else:
            related_model_name = Table.get_table_model_name(
                instance.link_row_table_id
            ).lower()
            related_model = model.baserow_models.get(related_model_name)
            # If we do not have a related table model already we can generate a new one.
            if related_model is None:
                related_model = instance.link_row_table.get_model(
                    manytomany_models=model.baserow_models,
                    app_label=model._meta.app_label,
                )
                model.baserow_models[related_model_name] = related_model

        instance._related_model = related_model
        related_name = f"reversed_field_{instance.id}"

        # Try to find the related field in the related model in order to figure out what
        # the related name should be. If the related if is not found that means that it
        # has not yet been created.
        def field_is_link_row_related_field(related_field):
            return (
                isinstance(related_field["field"], self.model_class)
                and related_field["field"].link_row_related_field_id
                and related_field["field"].link_row_related_field_id == instance.id
            )

        if not instance.is_self_referencing:
            for related_field in related_model._field_objects.values():
                if field_is_link_row_related_field(related_field):
                    related_name = related_field["name"]
                    break

        models.ManyToManyField(
            to=related_model,
            related_name=related_name,
            null=True,
            blank=True,
            db_table=instance.through_table_name,
            db_constraint=False,
        ).contribute_to_class(model, field_name)

    def prepare_values(self, values, user):
        """
        This method checks if the provided link row table is an int because then it
        needs to be converted to a table instance.
        It also provided compatibility between the old name `link_row_table` and the new
        name `link_row_table_id`.
        """

        from baserow.contrib.database.table.handler import TableHandler
        from baserow.contrib.database.table.models import Table

        link_row_table_id = values.pop("link_row_table_id", None)
        # If the value is not set, it will be equal to `-1`. This is to allow setting
        # the value to `None`, to clear it.
        link_row_limit_selection_view_id = values.pop(
            "link_row_limit_selection_view_id", -1
        )

        if link_row_table_id is None:
            link_row_table = values.pop("link_row_table", None)

            if isinstance(link_row_table, Table):
                # set in a previous call to prepare_values, so we can use it.
                values["link_row_table"] = link_row_table
            elif isinstance(link_row_table, int):
                logger.warning(
                    "The 'link_row_table' parameter is deprecated for LinkRow field."
                    "Please, use 'link_row_table_id' instead."
                )
                link_row_table_id = link_row_table

        if isinstance(link_row_table_id, int):
            table = TableHandler().get_table(link_row_table_id)
            CoreHandler().check_permissions(
                user,
                CreateFieldOperationType.type,
                workspace=table.database.workspace,
                context=table,
            )
            values["link_row_table"] = table

        # If the value it not provided, it defaults to -1 in the API. This means it
        # must be ignored. We're doing that because the value is clearable by
        # providing `None`.
        if link_row_limit_selection_view_id is None:
            values["link_row_limit_selection_view"] = None
        elif (
            isinstance(link_row_limit_selection_view_id, int)
            and link_row_limit_selection_view_id > -1
        ):
            from baserow.contrib.database.views.registries import view_type_registry

            view = ViewHandler().get_view(
                link_row_limit_selection_view_id,
                base_queryset=View.objects.filter(
                    ownership_type=OWNERSHIP_TYPE_COLLABORATIVE
                ),
            )
            view_type = view_type_registry.get_by_model(view.specific_class)
            if not view_type.can_filter:
                raise ViewDoesNotExist(
                    f"The view with id {link_row_limit_selection_view_id} doesn't "
                    f"support filters."
                )
            values["link_row_limit_selection_view"] = view

        return values

    def export_prepared_values(self, field: LinkRowField):
        values = super().export_prepared_values(field)

        if field.link_row_table:
            values.pop("link_row_table", None)
            values["link_row_table_id"] = field.link_row_table_id

        # We don't want to serialize the related field as the update call will create
        # it again, but we need to save the field has a related field or not.
        values["has_related_field"] = bool(values.pop("link_row_related_field", None))

        return values

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        """
        It is not allowed to link with a table from another database. This method
        checks if the database ids are the same and if not a proper exception is
        raised.
        """

        link_row_table = allowed_field_values.get("link_row_table")
        link_row_limit_selection_view = allowed_field_values.get(
            "link_row_limit_selection_view"
        )

        if link_row_table is None:
            raise LinkRowTableNotProvided(
                "The link_row_table argument must be provided when creating a link_row "
                "field."
            )

        if table.database_id != link_row_table.database_id:
            raise LinkRowTableNotInSameDatabase(
                f"The link row table {link_row_table.id} is not in the same database "
                f"as the table {table.id}."
            )

        if (
            link_row_limit_selection_view is not None
            and link_row_limit_selection_view.table_id != link_row_table.id
        ):
            raise ViewNotInTable(link_row_limit_selection_view.id)

        CoreHandler().check_permissions(
            user,
            CreateFieldOperationType.type,
            table.database.workspace,
            context=link_row_table,
        )

        self_referencing_link_row = table.id == link_row_table.id
        create_related_field = field_kwargs.get("has_related_field")
        if self_referencing_link_row and create_related_field:
            raise SelfReferencingLinkRowCannotHaveRelatedField(
                f"A self referencing link row cannot have a related field."
            )
        if create_related_field is None:
            field_kwargs["has_related_field"] = not self_referencing_link_row

    def before_update(self, from_field, to_field_values, user, field_kwargs):
        """
        It is not allowed to link with a table from another database if the
        link_row_table has changed and if it is within the same database.
        """

        link_row_table = to_field_values.get("link_row_table")

        existing_or_new_table = to_field_values.get(
            "link_row_table", getattr(from_field, "link_row_table", None)
        )
        existing_or_new_limit_selection_view = to_field_values.get(
            "link_row_limit_selection_view",
            getattr(from_field, "link_row_limit_selection_view", None),
        )

        if (
            existing_or_new_limit_selection_view is not None
            and existing_or_new_limit_selection_view.table_id
            != existing_or_new_table.id
        ):
            raise ViewNotInTable(existing_or_new_limit_selection_view.id)

        if link_row_table is None:
            field_kwargs.setdefault(
                "has_related_field", from_field.link_row_table_has_related_field
            )
            return

        table = from_field.table

        if from_field.table.database_id != link_row_table.database_id:
            raise LinkRowTableNotInSameDatabase(
                f"The link row table {link_row_table.id} is not in the same database "
                f"as the table {table.id}."
            )

        self_referencing_link_row = table.id == link_row_table.id
        to_field_has_related_field = field_kwargs.get("has_related_field")

        if self_referencing_link_row and to_field_has_related_field:
            raise SelfReferencingLinkRowCannotHaveRelatedField(
                f"A self referencing link row cannot have a related field."
            )

        if to_field_has_related_field is None:
            if isinstance(from_field, LinkRowField):
                field_kwargs["has_related_field"] = (
                    from_field.link_row_table_has_related_field
                    and not self_referencing_link_row
                )
            else:
                field_kwargs["has_related_field"] = not self_referencing_link_row

    def after_create(self, field, model, user, connection, before, field_kwargs):
        """
        When the field is created we have to add the related field to the related
        table so a reversed lookup can be done by the user.
        """

        if (
            field.link_row_table_has_related_field
            or field.is_self_referencing
            or not field_kwargs["has_related_field"]
        ):
            return

        related_field_name = self.find_next_unused_related_field_name(field)
        field.link_row_related_field = FieldHandler().create_field(
            user=user,
            table=field.link_row_table,
            type_name=self.type,
            skip_django_schema_editor_add_field=False,
            name=related_field_name,
            link_row_table=field.table,
            link_row_related_field=field,
            link_row_relation_id=field.link_row_relation_id,
            skip_search_updates=True,
        )
        field.save()

    # noinspection PyMethodMayBeStatic
    def find_next_unused_related_field_name(self, field):
        # First just try the tables name, so if say the Client table is linking to the
        # Address table, this field in the Address table will just be called 'Client'.
        # However say we then add another link from the Client to Address table with
        # a field name of "Bank Address", the new field in the Address table will be
        # called 'Client - Bank Address'.
        return FieldHandler().find_next_unused_field_name(
            field.link_row_table,
            [f"{field.table.name}", f"{field.table.name} - {field.name}"],
        )

    def before_schema_change(
        self,
        from_field,
        to_field,
        to_model,
        from_model,
        from_model_field,
        to_model_field,
        user,
        to_field_kwargs,
    ):
        to_instance = isinstance(to_field, self.model_class)
        from_instance = isinstance(from_field, self.model_class)
        from_link_row_table_has_related_field = (
            from_instance and from_field.link_row_table_has_related_field
        )
        to_link_row_table_has_related_field = (
            to_instance and to_field_kwargs["has_related_field"]
        )

        if to_instance:
            CoreHandler().check_permissions(
                user,
                CreateFieldOperationType.type,
                to_field.table.database.workspace,
                context=to_field.link_row_table,
            )

        if from_instance:
            CoreHandler().check_permissions(
                user,
                DeleteRelatedLinkRowFieldOperationType.type,
                from_field.table.database.workspace,
                context=from_field.link_row_table,
            )

        if (
            from_link_row_table_has_related_field
            and not to_link_row_table_has_related_field
        ):
            FieldHandler().delete_field(
                user=user,
                field=from_field.link_row_related_field,
                # Prevent the deletion of from_field itself as normally both link row
                # fields are deleted together.
                delete_strategy=DeleteFieldStrategyEnum.DELETE_OBJECT,
            )
            if to_instance:
                to_field.link_row_related_field = None
        elif to_instance and from_instance:
            related_field_name = self.find_next_unused_related_field_name(to_field)

            if (
                not from_link_row_table_has_related_field
                and to_link_row_table_has_related_field
            ):
                # we need to create the missing link_row_related_field
                to_field.link_row_related_field = FieldHandler().create_field(
                    user=user,
                    table=to_field.link_row_table,
                    type_name=self.type,
                    name=related_field_name,
                    skip_django_schema_editor_add_field=False,
                    link_row_table=to_field.table,
                    link_row_related_field=to_field,
                    link_row_relation_id=to_field.link_row_relation_id,
                    has_related_field=True,
                    skip_search_updates=True,
                )
                to_field.save()
            elif (
                from_link_row_table_has_related_field
                and to_link_row_table_has_related_field
                and from_field.link_row_table != to_field.link_row_table
            ):
                from_field.link_row_related_field.name = related_field_name
                from_field.link_row_related_field.link_row_table = to_field.table
                from_field.link_row_related_field.order = (
                    self.model_class.get_last_order(to_field.link_row_table)
                )
                FieldHandler().move_field_between_tables(
                    from_field.link_row_related_field, to_field.link_row_table
                )
                # We've changed the link_row_related_field on the from_field model
                # instance, make sure we also update the to_field instance to have
                # this updated instance so if it is used later it isn't stale and
                # pointing at the wrong table.
                to_field.link_row_related_field = from_field.link_row_related_field

    def after_update(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        user,
        connection,
        altered_column,
        before,
        to_field_kwargs,
    ):
        """
        If the old field is not already a link row field we have to create the related
        field into the related table. We also need to update the related field
        even if the link_row_table_has_related_field changes.
        """

        to_instance_require_related_field = (
            isinstance(to_field, self.model_class)
            and to_field_kwargs["has_related_field"]
        )
        from_instance = isinstance(from_field, self.model_class)

        if not from_instance and to_instance_require_related_field:
            related_field_name = self.find_next_unused_related_field_name(to_field)
            to_field.link_row_related_field = FieldHandler().create_field(
                user=user,
                table=to_field.link_row_table,
                type_name=self.type,
                skip_django_schema_editor_add_field=False,
                name=related_field_name,
                link_row_table=to_field.table,
                link_row_related_field=to_field,
                link_row_relation_id=to_field.link_row_relation_id,
                skip_search_updates=True,
            )
            to_field.save()

    def after_delete(self, field, model, connection):
        """
        After the field has been deleted we also need to delete the related field.
        """

        if field.link_row_related_field is not None:
            field.link_row_related_field.delete()

    def random_value(self, instance, fake, cache):
        """
        Selects a between 0 and 3 random rows from the instance's link row table and
        return those ids in a list.
        """

        model_name = f"table_{instance.link_row_table_id}"
        count_name = f"table_{instance.link_row_table_id}_count"
        queryset_name = f"table_{instance.link_row_table_id}_queryset"

        if model_name not in cache:
            cache[model_name] = instance.link_row_table.get_model(field_ids=[])
            cache[count_name] = cache[model_name].objects.all().count()

        model = cache[model_name]
        count = cache[count_name]

        if count == 0:
            return []

        def get_random_objects_iterator(limit=10000):
            qs = model.objects.order_by("?").only("id")
            if count > limit:
                return qs.iterator(chunk_size=limit)
            else:
                return cycle(qs.all())

        if queryset_name not in cache:
            cache[queryset_name] = get_random_objects_iterator()

        qs = cache[queryset_name]

        try:
            return [next(qs).id for _ in range(randrange(0, min(3, count)))]  # nosec
        except StopIteration:
            cache[queryset_name] = get_random_objects_iterator()
        return []

    def export_serialized(self, field):
        serialized = super().export_serialized(field, False)
        serialized["link_row_table_id"] = field.link_row_table_id
        serialized["link_row_related_field_id"] = field.link_row_related_field_id
        serialized[
            "link_row_limit_selection_view_id"
        ] = field.link_row_limit_selection_view_id
        serialized["has_related_field"] = field.link_row_table_has_related_field
        serialized[
            "link_row_multiple_relationships"
        ] = field.link_row_multiple_relationships
        return serialized

    def import_serialized(
        self,
        table: "Table",
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        deferred_fk_update_collector: DeferredForeignKeyUpdater,
    ) -> Optional[Field]:
        serialized_copy = serialized_values.copy()
        serialized_copy["link_row_table_id"] = id_mapping["database_tables"][
            serialized_copy["link_row_table_id"]
        ]
        link_row_limit_selection_view_id = serialized_copy.pop(
            "link_row_limit_selection_view_id", None
        )
        link_row_related_field_id = serialized_copy.pop(
            "link_row_related_field_id", None
        )
        has_related_field = serialized_copy.pop(
            "has_related_field", link_row_related_field_id
        )
        related_field_found = (
            "database_fields" in id_mapping
            and has_related_field
            and link_row_related_field_id in id_mapping["database_fields"]
        )

        if related_field_found:
            # If the related field is found, it means that it has already been
            # imported. In that case, we can directly set the `link_row_relation_id`
            # when creating the current field.
            serialized_copy["link_row_related_field_id"] = id_mapping[
                "database_fields"
            ][link_row_related_field_id]
            related_field = LinkRowField.objects.get(
                pk=serialized_copy["link_row_related_field_id"]
            )
            serialized_copy["link_row_relation_id"] = related_field.link_row_relation_id

        field = super().import_serialized(
            table,
            serialized_copy,
            import_export_config,
            id_mapping,
            deferred_fk_update_collector,
        )

        if related_field_found:
            # If the related field is found, it means that when creating that field
            # the `link_row_relation_id` was not yet set because this field,
            # where the relation is being made to, did not yet exist. So we need to
            # set it right now.
            related_field.link_row_related_field_id = field.id
            related_field.save()

        if link_row_limit_selection_view_id:
            deferred_fk_update_collector.add_deferred_fk_to_update(
                field,
                "link_row_limit_selection_view_id",
                link_row_limit_selection_view_id,
                "database_views",
            )

        return field

    def after_import_serialized(
        self,
        field: LinkRowField,
        field_cache: "FieldCache",
        id_mapping: Dict[str, Any],
    ):
        if field.link_row_related_field:
            FieldDependencyHandler.rebuild_dependencies(
                [field.link_row_related_field], field_cache
            )
        FieldDependencyHandler.rebuild_dependencies([field], field_cache)

    def get_export_serialized_value(self, row, field_name, cache, files_zip, storage):
        cache_entry = f"{field_name}_relations"
        if cache_entry not in cache:
            # In order to prevent a lot of lookup queries in the through table,
            # we want to fetch all the relations and add it to a temporary in memory
            # cache containing a mapping of the old ids to the new ids. Every relation
            # can use the cached mapped relations to find the correct id.
            cache[cache_entry] = defaultdict(list)
            through_model = row._meta.get_field(field_name).remote_field.through
            through_model_fields = through_model._meta.get_fields()
            current_field_name = through_model_fields[1].name
            relation_field_name = through_model_fields[2].name
            for relation in through_model.objects.filter(
                Q(**{f"{relation_field_name}__trashed": False})
            ):
                cache[cache_entry][
                    getattr(relation, f"{current_field_name}_id")
                ].append(getattr(relation, f"{relation_field_name}_id"))

        return cache[cache_entry][row.id]

    def set_import_serialized_value(
        self, row, field_name, value, id_mapping, cache, files_zip, storage
    ):
        through_model = row._meta.get_field(field_name).remote_field.through
        through_model_fields = through_model._meta.get_fields()
        current_field_name = through_model_fields[1].name
        relation_field_name = through_model_fields[2].name

        return [
            through_model(
                **{
                    f"{current_field_name}_id": row.id,
                    f"{relation_field_name}_id": item,
                }
            )
            for item in value
        ]

    def get_other_fields_to_trash_restore_always_together(self, field) -> List[Field]:
        fields = []
        if field.link_row_related_field is not None:
            fields.append(field.link_row_related_field)
        return fields

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        primary_field = field.link_row_table_primary_field
        if primary_field is None:
            return BaserowFormulaInvalidType("references unknown or deleted table")
        else:
            primary_field = primary_field.specific
            related_field_type = field_type_registry.get_by_model(primary_field)
            return related_field_type.to_baserow_formula_type(primary_field)

    def to_baserow_formula_expression(
        self, field
    ) -> BaserowExpression[BaserowFormulaType]:
        primary_field = field.link_row_table_primary_field
        return FormulaHandler.get_lookup_field_reference_expression(
            field, primary_field, self.to_baserow_formula_type(field)
        )

    def get_field_dependencies(
        self, field_instance: LinkRowField, field_cache: "FieldCache"
    ) -> FieldDependencies:
        primary_related_field = field_instance.link_row_table_primary_field
        if primary_related_field is not None:
            return [
                FieldDependency(
                    dependency=primary_related_field,
                    dependant=field_instance,
                    via=field_instance,
                )
            ]
        else:
            return []

    def should_backup_field_data_for_same_type_update(
        self, old_field: LinkRowField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_link_row_table_id = new_field_attrs.get(
            "link_row_table_id", old_field.link_row_table_id
        )
        return old_field.link_row_table_id != new_link_row_table_id

    def should_update_search_data(
        self, old_field: LinkRowField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_link_row_table_id = new_field_attrs.get(
            "link_row_table_id", old_field.link_row_table_id
        )
        return old_field.link_row_table_id != new_link_row_table_id

    def get_dependants_which_will_break_when_field_type_changes(
        self, field: LinkRowField, to_field_type: "FieldType", field_cache: "FieldCache"
    ) -> "FieldDependants":
        """
        When a LinkRowField is converted to a different field type, the metadata row
        in the database_linkrowfield table is deleted. This causes a cascading delete
        of any FieldDependency rows which depend via this link row field. We use this
        hook to first query for these via dependencies prior to the type change and
        cascading delete so we can subsequently trigger updates for the affected
        dependant fields which previously went via this one.
        """

        # Find all FieldDependency rows which will get cascade deleted because our
        # LinkRowField row will be deleted. However we need to exclude the dependency
        # that we have via ourself as it makes no sense that we are a dependant of
        # ourself.
        return FieldDependencyHandler.get_via_dependants_of_link_field(field)

    def row_of_dependency_updated(
        self,
        field: Field,
        starting_row: "StartingRowType",
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: List["LinkRowField"],
        dependency_context: DependencyContext,
    ):
        update_collector.add_field_which_has_changed(
            field, via_path_to_starting_table, send_field_updated_signal=False
        )
        super().row_of_dependency_updated(
            field,
            starting_row,
            update_collector,
            field_cache,
            via_path_to_starting_table,
            dependency_context,
        )

    def field_dependency_updated(
        self,
        field: Field,
        updated_field: Field,
        updated_old_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        update_collector.add_field_which_has_changed(
            field, via_path_to_starting_table, send_field_updated_signal=False
        )
        super().field_dependency_updated(
            field,
            updated_field,
            updated_old_field,
            update_collector,
            field_cache,
            via_path_to_starting_table,
        )

    def serialize_metadata_for_row_history(
        self,
        field: Field,
        row: "GeneratedTableModel",
        metadata: Optional[SerializedRowHistoryFieldMetadata] = None,
    ) -> SerializedRowHistoryFieldMetadata:
        base = super().serialize_metadata_for_row_history(field, row, metadata)

        already_serialized_linked_rows = {}
        if metadata and metadata.get("linked_rows"):
            already_serialized_linked_rows = metadata["linked_rows"]

        new_serialized_linked_rows = getattr(row, field.db_column).all()
        new_serialized_linked_rows = {
            linked_row.id: {
                "value": str(linked_row),
            }
            for linked_row in new_serialized_linked_rows
        }

        return {
            **base,
            "linked_rows": {
                **already_serialized_linked_rows,
                **new_serialized_linked_rows,
            },
            "linked_table_id": field.link_row_table_id,
            "linked_field_id": field.link_row_related_field_id,
            "primary_value": str(row),
        }

    def are_row_values_equal(self, value1: any, value2: any) -> bool:
        return set(value1 or []) == set(value2 or [])

    def empty_query(
        self,
        field_name: str,
        model_field: LinkRowField,
        field: ManyToManyField,
    ) -> Q:
        # Exclude all the trashed rows in the related table.
        subq = Subquery(
            model_field.model.objects.filter(
                id=OuterRef("id"), **{f"{field_name}__trashed": False}
            )[:1]
        )
        annotation_name = f"{field_name}_exists"
        return AnnotatedQ(
            annotation={annotation_name: Exists(subq)},
            q={f"{annotation_name}": False},
        )


class EmailFieldType(CollationSortMixin, CharFieldMatchingRegexFieldType):
    type = "email"
    model_class = EmailField
    can_upsert = True

    @property
    def regex(self):
        """
        Returns a highly permissive regex which allows non-valid emails in order to keep
        the regex as simple as possible and also the same behind the frontend, database
        and python code.
        """

        # Use a lookahead to validate entire string length does exceed max length
        # as we are matching multiple different tokens in the following regex.
        lookahead = rf"(?=^.{{3,{self.max_length}}}$)"
        # See wikipedia for allowed punctuation etc:
        # https://en.wikipedia.org/wiki/Email_address#Local-part
        local_and_domain = r"[-\.\[\]!#$&*+/=?^_`{|}~\w]+"
        return rf"(?i){lookahead}^{local_and_domain}@{local_and_domain}$"

    @property
    def max_length(self):
        # max_length=254 to be compliant with RFCs 3696 and 5321
        return 254

    def random_value(self, instance, fake, cache):
        return fake.email()

    def get_value_for_filter(self, row: "GeneratedTableModel", field: Field) -> any:
        value = getattr(row, field.db_column)
        return collate_expression(Value(value))


class FileFieldType(FieldType):
    type = "file"
    model_class = FileField
    can_be_in_form_view = True
    can_get_unique_values = False
    _can_order_by_types = []

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaArrayType(BaserowFormulaSingleFileType(nullable=True))

    def from_baserow_formula_type(self, formula_type) -> Field:
        return self.model_class()

    def get_search_expression(self, field: FileField, queryset: QuerySet) -> Expression:
        """
        Prepares a `FileField`.
        """

        return extract_jsonb_array_values_to_single_string(
            field,
            queryset,
            path_to_value_in_jsonb_list=[
                Value("visible_name", output_field=models.TextField())
            ],
        )

    def can_represent_files(self, field):
        return True

    def _extract_file_names(self, value):
        # Validates the provided object and extract the names from it. We need the name
        # to validate if the file actually exists and to get the 'real' properties
        # from it.
        provided_files = []
        if not value:
            return provided_files
        for o in value:
            provided_files.append(o)
        return provided_files

    def prepare_value_for_db(self, instance, value):
        if value is None:
            return []

        if not isinstance(value, list):
            raise ValidationError(
                "The provided value must be a list.", code="not_a_list"
            )

        if len(value) == 0:
            return []

        provided_files = self._extract_file_names(value)

        # Create a list of the serialized UserFiles in the originally provided order
        # because that is also the order we need to store the serialized versions in.
        user_files = []
        queryset = UserFile.objects.all().name(*[f["name"] for f in provided_files])
        for file in provided_files:
            try:
                user_file = next(
                    user_file
                    for user_file in queryset
                    if user_file.name == file["name"]
                )
                serialized = user_file.serialize()
                serialized["visible_name"] = (
                    file.get("visible_name") or user_file.original_name
                )
            except StopIteration:
                raise UserFileDoesNotExist(file["name"])

            user_files.append(serialized)

        return user_files

    def prepare_value_for_db_in_bulk(
        self, instance, values_by_row, continue_on_error=False
    ):
        provided_names_by_row = {}
        name_map = defaultdict(list)

        # Create {name -> row_indexes} map
        for row_index, value in values_by_row.items():
            provided_names_by_row[row_index] = self._extract_file_names(value)
            names = [pn["name"] for pn in provided_names_by_row[row_index]]
            for name in names:
                name_map[name].append(row_index)

        if not name_map:
            # ensure we're not returning None for any row
            for k, v in values_by_row.items():
                if v is None:
                    values_by_row[k] = []

            return values_by_row

        unique_names = set(name_map.keys())

        # Query the database for existing files
        files = UserFile.objects.all().name(*unique_names)
        if len(files) != len(unique_names):
            invalid_names = sorted(
                list(unique_names - set((file.name) for file in files))
            )
            if continue_on_error:
                for invalid_name in invalid_names:
                    for row_index in name_map[invalid_name]:
                        values_by_row[row_index] = UserFileDoesNotExist(invalid_name)
            else:
                raise UserFileDoesNotExist(invalid_names)

        # Replacing file names by the actual file field dict
        user_files_by_name = {file.name: file for file in files}
        for row_index, value in values_by_row.items():
            # Ignore already raised exceptions
            if isinstance(value, Exception):
                continue
            serialized_files = []
            for file_names in provided_names_by_row[row_index]:
                user_file = user_files_by_name[file_names.get("name")]
                serialized = user_file.serialize()
                serialized["visible_name"] = (
                    file_names.get("visible_name") or user_file.original_name
                )
                serialized_files.append(serialized)
            values_by_row[row_index] = serialized_files

        return values_by_row

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.pop("required", False)
        return FileFieldRequestSerializer(
            required=required, allow_null=not required, **kwargs
        )

    def get_response_serializer_field(self, instance, **kwargs):
        return FileFieldResponseSerializer(
            **{"many": True, "required": False, **kwargs}
        )

    def get_export_value(self, value, field_object, rich_value=False):
        storage = get_default_storage()
        files = []
        for file in value:
            if "name" in file:
                path = UserFileHandler().user_file_path(file["name"])
                url = storage.url(path)
            else:
                url = None

            files.append(
                {
                    "visible_name": file["visible_name"],
                    "name": file["name"],
                    "url": url,
                }
            )

        if rich_value:
            return [{"visible_name": f["visible_name"], "url": f["url"]} for f in files]
        else:
            return list_to_comma_separated_string(
                [f'{file["visible_name"]} ({file["url"]})' for file in files]
            )

    def get_human_readable_value(self, value, field_object):
        file_names = []
        for file in value:
            file_names.append(
                file["visible_name"],
            )

        return ", ".join(file_names)

    def get_serializer_help_text(self, instance):
        return (
            "This field accepts an `array` containing objects with the name of "
            "the file. The response contains an `array` of more detailed objects "
            "related to the files."
        )

    def get_model_field(self, instance, **kwargs):
        return JSONField(default=list, **kwargs)

    def random_value(self, instance, fake, cache):
        """
        Selects between 0 and 3 random user files and returns those serialized in a
        list.
        """

        count_name = f"field_{instance.id}_count"
        queryset_name = f"field_{instance.id}_queryset"

        if count_name not in cache:
            cache[count_name] = UserFile.objects.all().count()

        values = []
        count = cache[count_name]

        if count == 0:
            return values

        def get_random_objects_iterator(limit=10000):
            user_ids = WorkspaceUser.objects.filter(
                workspace=instance.table.database.workspace_id
            ).values_list("user_id", flat=True)
            qs = UserFile.objects.filter(uploaded_by_id__in=user_ids).order_by("?")
            if count > limit:
                return qs.iterator(chunk_size=limit)
            else:
                return cycle(qs.all())

        if queryset_name not in cache:
            cache[queryset_name] = get_random_objects_iterator()

        qs = cache[queryset_name]

        values = []
        for _ in range(randrange(1, min(3, count))):  # nosec
            try:
                user_file = next(qs)
                serialized = user_file.serialize()
                serialized["visible_name"] = user_file.original_name
                values.append(serialized)
            except StopIteration:
                cache[queryset_name] = get_random_objects_iterator()

        return values

    def contains_query(self, *args):
        return filename_contains_filter(*args)

    def get_export_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        cache: Dict[str, Any],
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        name_prefix: str = "",
    ) -> List[Dict[str, Any]]:
        return prepare_files_for_export(
            self.get_internal_value_from_db(row, field_name),
            cache,
            files_zip,
            storage,
            name_prefix,
        )

    def set_import_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        value: Dict[str, Any],
        id_mapping: Dict[str, Any],
        cache: Dict[str, Any],
        files_zip: Optional[ZipFile],
        storage: Optional[Storage],
    ) -> None:
        user_file_handler = UserFileHandler()
        files = []

        for file in value:
            # files_zip could be None when files are in the same storage of the export
            # so no need to export/reimport files already present in the storage.
            if files_zip is None:
                files.append(file)
            else:
                try:
                    with files_zip.open(file["name"]) as stream:
                        # Try to upload the user file with the original name
                        # to make sure that if the was already uploaded, it will
                        # not be uploaded again.
                        user_file = user_file_handler.upload_user_file(
                            None, file["original_name"], stream, storage=storage
                        )
                except KeyError:
                    # File not found in zip archive - skip this file and
                    # let the import process report handle missing files
                    # appropriately
                    continue

                value = user_file.serialize()
                value["visible_name"] = file["visible_name"]
                files.append(value)

        setattr(row, field_name, files)

    def are_row_values_equal(self, value1: any, value2: any) -> bool:
        return {v["name"] for v in value1} == {v["name"] for v in value2}


class SelectOptionBaseFieldType(FieldType):
    can_have_select_options = True
    allowed_fields = ["select_options"]
    serializer_field_names = ["select_options"]
    serializer_field_overrides = {
        "select_options": SelectOptionSerializer(many=True, required=False),
    }
    _can_group_by = True
    _db_column_fields = []

    def get_default_value(self, field: Field) -> Any:
        return getattr(field, self.get_default_options_field_name(), None)

    def create_select_options(self, field, select_options):
        """
        Creates the select options for the field.

        :param field: The field instance.
        :param select_options: List of select options to create.
        :return: Mapping of select option ids before creation to
            their ids after creation
        """

        mapping = {}
        for select_option in select_options:
            select_option_copy = select_option.copy()
            select_option_id = select_option_copy.pop("id")
            select_option_object = SelectOption.objects.create(
                field=field, **select_option_copy
            )
            mapping[select_option_id] = select_option_object.id
        return mapping

    def after_create_select_options(
        self, field, select_default, select_options, mapping
    ):
        """
        Called after creating the select options.
        Can be used i.e. to set default options for field

        :param field: The field instance.
        :param select_default: The default value to set.
        :param select_options: List of select options to search through.
        :param mapping: Mapping of select option ids before creation to
            their ids after creation
        """

        return field

    def get_default_options_index(self, default, select_options):
        """
        Returns the index of the default option in the select_options list.

        :param default: The id of the default option to find.
        :param select_options: List of select options to search through.

        """

        return None

    def get_options_by_index(self, field, index):
        """
        Returns the option at the given index in the select_options list.

        :param field: The field instance.
        :param index: The index of the option to retrieve.

        """

        return None

    def get_validated_default_value(
        self, from_field, default_index, has_new_default_value, select_default_value
    ):
        return None

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        select_options = allowed_field_values.pop("select_options", [])
        default_value_field_name = f"{self.type}_default"
        select_default_value = allowed_field_values.pop(default_value_field_name, None)
        return select_options, select_default_value

    def after_create(self, field, model, user, connection, before, field_kwargs):
        select_options, select_default_value = before

        default_index = self.get_default_options_index(
            select_default_value, select_options
        )

        if select_options and len(select_options) > 0:
            FieldHandler().update_field_select_options(user, field, select_options)

            default_value = self.get_options_by_index(field, default_index)
            if default_value is not None:
                default_value_field_name = self.get_default_options_field_name()
                if hasattr(field, default_value_field_name):
                    setattr(field, default_value_field_name, default_value)
                    field.save(update_fields=[default_value_field_name])

    def before_update(self, from_field, to_field_values, user, kwargs):
        default_value_field_name = self.get_default_options_field_name()

        default_index = None
        has_new_default_value = default_value_field_name in to_field_values

        if has_new_default_value:
            select_default_value = to_field_values[default_value_field_name]
        else:
            select_default_value = getattr(from_field, default_value_field_name, None)

        if "select_options" in to_field_values:
            select_options = to_field_values["select_options"]

            default_index = self.get_default_options_index(
                select_default_value, select_options
            )

            FieldHandler().update_field_select_options(user, from_field, select_options)
            to_field_values.pop("select_options")
        else:
            select_options = list(from_field.select_options.values())
            default_index = self.get_default_options_index(
                select_default_value, select_options
            )
        default_value = self.get_validated_default_value(
            from_field, default_index, has_new_default_value, select_default_value
        )
        to_field_values[default_value_field_name] = default_value

    def should_backup_field_data_for_same_type_update(
        self, old_field: SingleSelectField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        updated_ids = set()
        for o in new_field_attrs.get("select_options", []):
            if UPSERT_OPTION_DICT_KEY in o:
                updated_ids.add(o[UPSERT_OPTION_DICT_KEY])
            if "id" in o:
                updated_ids.add(o["id"])

        # If there are any deleted options we need to backup
        return old_field.select_options.exclude(id__in=updated_ids).exists()

    def should_update_search_data(self, old_field, new_field_attrs):
        return self.should_backup_field_data_for_same_type_update(
            old_field, new_field_attrs
        )

    def enhance_queryset_in_bulk(self, queryset, field_objects, **kwargs):
        existing_multi_field_prefetches = queryset.get_multi_field_prefetches()
        select_model_prefetch = None

        # Check if the queryset already contains a multi field prefetch for the same
        # target, and use that one if so. This can happen if the `single_select` or
        # `multiple_select` field has already called this method.
        for prefetch in existing_multi_field_prefetches:
            if (
                isinstance(
                    prefetch, CombinedForeignKeyAndManyToManyMultipleFieldPrefetch
                )
                and prefetch.target_model == SelectOption
            ):
                select_model_prefetch = prefetch
                break

        if not select_model_prefetch:
            select_model_prefetch = CombinedForeignKeyAndManyToManyMultipleFieldPrefetch(
                SelectOption,
                # Must skip because the multiple_select works with dynamically
                # generated models.
                skip_target_check=True,
            )
            queryset = queryset.multi_field_prefetch(select_model_prefetch)

        field_names = [field_object["name"] for field_object in field_objects]
        select_model_prefetch.add_field_names(field_names)

        return queryset

    def get_sortable_column_expression(
        self,
        field: Field,
        field_name: str,
        sort_type: str,
    ) -> Expression | F:
        return F(f"{field_name}__value")

    def parse_filter_value(self, field, model_field, value) -> List[int]:
        """
        Parses the provided comma separated string value to extract option ids from it.
        If the result does not contain any valid option id, a ValueError is raised.
        """

        if value == "":
            return None

        option_ids = parse_ids_from_csv_string(value)
        if not option_ids:
            raise ValueError("The provided value does not contain a valid option id.")
        return option_ids

    def get_select_options_help_text(self, instance):
        try:
            select_option_pair = ", ".join(
                [
                    f"{select_option.id}={json.dumps(select_option.value)}"
                    for select_option in instance.select_options.all()
                ]
            )
        except ValueError:
            # Happens when the instance does not yet have a primary key.
            return self.get_serializer_help_text(instance)
        return f"(in format option_id=option_value): " f"{select_option_pair}"


class SingleSelectFieldType(CollationSortMixin, SelectOptionBaseFieldType):
    type = "single_select"
    model_class = SingleSelectField
    allowed_fields = ["select_options", "single_select_default"]
    serializer_field_names = ["select_options", "single_select_default"]
    _can_order_by_types = [DEFAULT_SORT_TYPE_KEY, SINGLE_SELECT_SORT_BY_ORDER]

    serializer_field_overrides = {
        "select_options": SelectOptionSerializer(many=True, required=False),
        "single_select_default": serializers.IntegerField(
            required=False, allow_null=True
        ),
    }

    def init_field_data(self, field, model):
        if field.single_select_default:
            field_data = {
                self.get_default_options_field_name(): field.single_select_default
            }
            validate_default_value_with_constraints(
                self,
                [{"type_name": c.type_name} for c in field.field_constraints.all()],
                field_data,
                field,
            )
            model.objects.all().update(
                **{f"{field.db_column}_id": field.single_select_default}
            )

    def get_default_options_index(self, default, select_options):
        if default is None:
            return None
        return next(
            (
                index
                for index, option in enumerate(select_options)
                if option.get("id") == default
                or option.get(UPSERT_OPTION_DICT_KEY) == default
            ),
            None,
        )

    def get_options_by_index(self, field, index):
        if index is None:
            return None
        try:
            return field.select_options.all()[index].id
        except IndexError:
            return None

    def after_create_select_options(
        self, field, select_default, select_options, mapping
    ):
        if select_default is not None:
            mapped_default = mapping.get(select_default, None)
            field_name = self.get_default_options_field_name()
            if hasattr(field, field_name):
                setattr(field, field_name, mapped_default)
                field.save(update_fields=[field_name])
        return field

    def get_instance_default_value(self, instance, default_value):
        """
        Checks if the provided default value is a valid option and returns it.
        If the default value is not a valid option, it returns None.
        """

        default_value = default_value or instance.single_select_default
        if default_value is None or default_value == NOT_PROVIDED:
            return None

        if default_value in [option.id for option in instance.select_options.all()]:
            return default_value

    def get_validated_default_value(
        self, from_field, default_index, has_new_default_value, select_default_value
    ):
        if default_index is not None:
            default_value = self.get_options_by_index(from_field, default_index)
        else:
            if has_new_default_value and select_default_value is not None:
                raise SelectOptionDoesNotBelongToField(
                    select_default_value,
                    field_id=from_field.id,
                )
            else:
                default_value = None
        return default_value

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.pop("required", False)

        serializer_kwargs = {
            "required": required,
            "allow_null": not required,
            **kwargs,
        }

        if not required:
            default_value = self.get_instance_default_value(
                instance, kwargs.get("single_select_default", None)
            )
            serializer_kwargs["default"] = default_value

        serializer_kwargs["help_text"] = (
            f"Accepts one of the following option ids as integer value"
            f" {self.get_select_options_help_text(instance)}."
        )

        field_serializer = IntegerOrStringField(**serializer_kwargs)
        return field_serializer

    def get_response_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)
        return SelectOptionSerializer(
            **{
                "required": required,
                "allow_null": not required,
                "many": False,
                **kwargs,
            }
        )

    def enhance_queryset(self, queryset, field, name, **kwargs):
        # It's important that this individual enhance_queryset method exists, even
        # though the enhance queryset in bulk exists, because the link_row field can
        # prefetch the data individually.
        return queryset.select_related(name)

    def get_value_for_filter(self, row: "GeneratedTableModel", field) -> int:
        value = getattr(row, field.db_column)
        return value

    def get_internal_value_from_db(
        self, row: "GeneratedTableModel", field_name: str
    ) -> int:
        return getattr(row, f"{field_name}_id")

    def get_search_expression(
        self, field: SingleSelectField, queryset: QuerySet
    ) -> Expression:
        return Subquery(
            queryset.filter(pk=OuterRef("pk")).values(f"{field.db_column}__value")[:1]
        )

    def prepare_value_for_db(self, instance, value):
        return self.prepare_value_for_db_in_bulk(
            instance, {0: value}, continue_on_error=False
        )[0]

    def prepare_value_for_db_in_bulk(
        self, instance, values_by_row, continue_on_error=False
    ):
        # Create a map {names/ids -> row_indexes} and extract unique int and text values
        unique_ids = set()
        unique_names = set()
        invalid_values_by_index = {}

        for row_index, value in values_by_row.items():
            if value is None:
                continue

            if isinstance(value, SelectOption):
                continue
            elif isinstance(value, int):
                unique_ids.add(value)
            elif isinstance(value, str):
                unique_names.add(value)
            else:
                error = ValidationError(
                    f"The provided value {value} is not a valid option.",
                    code="invalid_option",
                )
                if continue_on_error:
                    invalid_values_by_index[row_index] = error
                else:
                    raise error

        invalid_values_by_index.update(invalid_values_by_index)

        # Query database with all these gathered values
        select_options = list(
            SelectOption.objects.filter(field=instance).filter(
                Q(id__in=unique_ids) | Q(value__in=unique_names)
            )
        )

        # Create a map {id|value -> option}
        # Here we reverse the select_options list to let the first option
        # win in the map in case of duplicate for text values.
        option_map = {opt.value: opt for opt in select_options[::-1]}
        option_map.update({opt.id: opt for opt in select_options})

        found_option_values = set(option_map.keys())
        unique_values = unique_ids | unique_names

        invalid_values = sorted(
            [str(val) for val in list(unique_values - found_option_values)]
        )

        # Whether invalid values exists ?
        if invalid_values:
            if not continue_on_error:
                # Fail fast
                raise AllProvidedMultipleSelectValuesMustBeSelectOption(invalid_values)

        # Replace original values by real option object if possible
        for row_index, value in values_by_row.items():
            # Ignore empty and select values
            if value is None or isinstance(value, SelectOption):
                continue

            if continue_on_error and value not in option_map:
                values_by_row[row_index] = ValidationError(
                    f"The provided value {value} is not a valid option.",
                    code="invalid_option",
                )
            else:
                values_by_row[row_index] = option_map[value]

        return values_by_row

    def serialize_to_input_value(self, field: Field, value: any) -> any:
        return value.id

    def serialize_metadata_for_row_history(
        self,
        field: Field,
        row: "GeneratedTableModel",
        metadata: Optional[SerializedRowHistoryFieldMetadata] = None,
    ) -> SerializedRowHistoryFieldMetadata:
        base = super().serialize_metadata_for_row_history(field, row, metadata)

        already_serialized_option = {}
        if metadata and metadata.get("select_options"):
            already_serialized_option = metadata["select_options"]

        select_option = getattr(row, field.db_column)
        new_serialized_option = {}
        if select_option is not None:
            new_serialized_option[select_option.id] = {
                "id": select_option.id,
                "value": select_option.value,
                "color": select_option.color,
            }

        return {
            **base,
            "select_options": {
                **already_serialized_option,
                **new_serialized_option,
            },
        }

    def get_serializer_help_text(self, instance):
        return (
            "This field accepts an `integer` representing the chosen select option id "
            "related to the field. Available ids can be found when getting or listing "
            "the field. The response represents chosen field, but also the value and "
            "color is exposed."
        )

    def get_export_value(self, value, field_object, rich_value=False):
        if value is None:
            return None if rich_value else ""
        return value.value

    def get_model_field(self, instance, **kwargs):
        default = self.get_instance_default_value(
            instance, kwargs.get("single_select_default", None)
        )

        if default is not None:
            kwargs["default"] = default

        return SingleSelectForeignKey(
            to=SelectOption,
            on_delete=models.SET_NULL,
            related_name="+",
            related_query_name="+",
            db_constraint=False,
            null=True,
            blank=True,
            **kwargs,
        )

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        """
        If the new field type isn't a single select field we can convert the plain
        text value of the option and maybe that can be used by the new field.
        """

        to_field_type = field_type_registry.get_by_model(to_field)
        if to_field_type.type != self.type and connection.vendor == "postgresql":
            variables = {}
            values_mapping = []
            for option in from_field.select_options.all():
                variable_name = f"option_{option.id}_value"
                variables[variable_name] = option.value
                values_mapping.append(f"('{int(option.id)}', %({variable_name})s)")

            # If there are no values we don't need to convert the value to a string
            # since all values will be converted to null.
            if len(values_mapping) == 0:
                return None

            # Has been checked for issues, everything is properly escaped and safe.
            # fmt: off
            sql = (
                f"""
                p_in = (SELECT value FROM (
                    VALUES {','.join(values_mapping)}
                ) AS values (key, value)
                WHERE key = p_in);
                """  # nosec b608
            )
            # fmt: on
            return sql, variables

        return super().get_alter_column_prepare_old_value(
            connection, from_field, to_field
        )

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        """
        If the old field wasn't a single select field we can try to match the old text
        values to the new options.
        """

        from_field_type = field_type_registry.get_by_model(from_field)
        if from_field_type.type != self.type and connection.vendor == "postgresql":
            variables = {}
            values_mapping = []
            for option in to_field.select_options.all():
                variable_name = f"option_{option.id}_value"
                variables[variable_name] = option.value
                values_mapping.append(
                    f"(lower(%({variable_name})s), '{int(option.id)}')"
                )

            # If there are no values we don't need to convert the value since all
            # values should be converted to null.
            if len(values_mapping) == 0:
                return None

            # Has been checked for issues, everything is properly escaped and safe.
            return (
                f"""p_in = (
                SELECT value FROM (
                    VALUES {','.join(values_mapping)}
                ) AS values (key, value)
                WHERE key = lower(p_in)
            );
            """,  # nosec
                variables,
            )

        return super().get_alter_column_prepare_new_value(
            connection, from_field, to_field
        )

    def get_sortable_column_expression(
        self,
        field: Field,
        field_name: str,
        sort_type: str,
    ) -> Expression | F:
        if sort_type == SINGLE_SELECT_SORT_BY_ORDER:
            return F(f"{field_name}__order")
        else:
            return super().get_sortable_column_expression(field, field_name, sort_type)

    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ) -> OptionallyAnnotatedOrderBy:
        """
        If the user wants to sort the results they expect them to be ordered
        alphabetically based on the select option value and not in the id which is
        stored in the table. This method generates a Case expression which maps the id
        to the correct position.
        """

        column_expression = self.get_sortable_column_expression(
            field, field_name, sort_type
        )

        if sort_type == SINGLE_SELECT_SORT_BY_ORDER:
            order = column_expression
        else:
            order = collate_expression(column_expression)

        if order_direction == "ASC":
            order = order.asc(nulls_first=True)
        else:
            order = order.desc(nulls_last=True)
        return OptionallyAnnotatedOrderBy(order=order)

    def random_value(self, instance, fake, cache):
        """
        Selects a random choice out of the possible options.
        """

        cache_entry_name = f"field_{instance.id}_options"

        if cache_entry_name not in cache:
            cache[cache_entry_name] = instance.select_options.all()

        select_options = cache[cache_entry_name]

        # if the select_options are empty return None
        if not select_options:
            return None

        return select_options[randrange(1, len(select_options))]  # nosec

    def contains_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()
        return Q(**{f"{field_name}__value__icontains": value})

    def contains_word_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()
        value = re.escape(value)
        return Q(**{f"{field_name}__value__iregex": rf"\m{value}\M"})

    def set_import_serialized_value(
        self, row, field_name, value, id_mapping, cache, files_zip, storage
    ):
        select_option_mapping = id_mapping["database_field_select_options"]

        if not value or value not in select_option_mapping:
            setattr(row, field_name + "_id", None)
            return

        setattr(row, field_name + "_id", select_option_mapping[value])

    def to_baserow_formula_type(self, field):
        return BaserowFormulaSingleSelectType(nullable=True)

    def from_baserow_formula_type(self, formula_type) -> Field:
        return self.model_class()

    def get_group_by_serializer_field(self, field, **kwargs):
        return serializers.IntegerField(
            **{
                "required": False,
                "allow_null": True,
                **kwargs,
            }
        )

    def get_formula_reference_to_model_field(
        self, model_field, db_column, already_in_subquery
    ):
        single_select_extractor = get_select_option_extractor(db_column, model_field)
        if already_in_subquery:
            return Case(
                When(**{f"{db_column}__isnull": True}, then=Value(None)),
                default=single_select_extractor,
                output_field=model_field,
            )
        else:
            return wrap_in_subquery(
                single_select_extractor, db_column, model_field.model
            )

    def before_field_options_update(
        self, field, to_create=None, to_update=None, to_delete=None
    ):
        if to_delete:
            model = field.table.get_model()
            model.objects.filter(**{f"{field.db_column}_id__in": to_delete}).update(
                **{field.db_column: None}
            )

    def get_distribution_group_by_value(self, field_name: str):
        return f"{field_name}__value"


class MultipleSelectFieldType(
    CollationSortMixin,
    ManyToManyFieldTypeSerializeToInputValueMixin,
    ManyToManyGroupByMixin,
    SelectOptionBaseFieldType,
):
    type = "multiple_select"
    model_class = MultipleSelectField
    can_get_unique_values = False
    is_many_to_many_field = True
    _can_group_by = True
    allowed_fields = ["select_options", "multiple_select_default"]
    serializer_field_names = ["select_options", "multiple_select_default"]

    serializer_field_overrides = {
        "select_options": SelectOptionSerializer(many=True, required=False),
        "multiple_select_default": serializers.ListField(
            child=serializers.IntegerField(), required=False, allow_null=True
        ),
    }

    def init_field_data(self, field, model):
        if field.multiple_select_default:
            through_model = model._meta.get_field(field.db_column).remote_field.through
            row_id_field = through_model._meta.fields[1].name
            option_id_field = through_model._meta.fields[2].name
            batch_size = 10000
            all_row_ids = model.objects.values_list("id", flat=True).iterator(
                chunk_size=batch_size
            )

            for row_ids_batch in grouper(batch_size, all_row_ids):
                through_model.objects.bulk_create(
                    [
                        through_model(
                            **{
                                f"{row_id_field}_id": row_id,
                                f"{option_id_field}_id": option_id,
                            }
                        )
                        for row_id in row_ids_batch
                        for option_id in field.multiple_select_default
                    ],
                    ignore_conflicts=True,
                )

    def get_default_options_index(self, default, select_options):
        if default is None or default == []:
            return []
        return [
            index
            for index, option in enumerate(select_options)
            if option.get("id") in default
            or option.get(UPSERT_OPTION_DICT_KEY) in default
        ]

    def get_options_by_index(self, field, index):
        if not index:
            return None
        all_option_ids = [option.id for option in field.select_options.all()]
        result = []
        for i in index:
            try:
                result.append(all_option_ids[i])
            except IndexError:
                continue
        return result

    def after_create_select_options(
        self, field, select_default, select_options, mapping
    ):
        if select_default:
            mapped_default = [mapping[key] for key in select_default if key in mapping]
            field_name = self.get_default_options_field_name()
            if hasattr(field, field_name):
                setattr(field, field_name, mapped_default)
                field.save(update_fields=[field_name])
        return field

    def get_validated_default_value(
        self, from_field, default_index, has_new_default_value, select_default_value
    ):
        default_value = self.get_options_by_index(from_field, default_index)
        if not select_default_value:
            return []
        if len(select_default_value) == len(default_value):
            return default_value
        else:
            missing_options = set(select_default_value) - set(default_value)
            if has_new_default_value and missing_options:
                raise SelectOptionDoesNotBelongToField(
                    ", ".join(map(str, missing_options)),
                    field_id=from_field.id,
                )
            else:
                return default_value

    def get_instance_default_value(self, instance, default_value):
        """
        Checks if the provided default value is a valid option and returns it.
        If the default value is not a valid option, it returns None.
        """

        default_value = default_value or instance.multiple_select_default
        if (
            default_value == NOT_PROVIDED
            or default_value == []
            or default_value is None
        ):
            return []
        existing_options = instance.select_options.all()
        return [option.id for option in existing_options if option.id in default_value]

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaMultipleSelectType(nullable=True)

    def from_baserow_formula_type(self, formula_type) -> Field:
        return self.model_class()

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.pop("required", False)
        source = kwargs.pop("source", None)

        if required is False:
            default = self.get_instance_default_value(
                instance, kwargs.get("multiple_select_default", None)
            )
            if default:
                kwargs["default"] = default

        field_serializer = IntegerOrStringField(
            **{
                "required": required,
                "allow_null": not required,
                "help_text": (
                    f"Accepts multiple option ids as an array of integer values"
                    f" {self.get_select_options_help_text(instance)}."
                ),
                **kwargs,
            },
        )
        return ListOrStringField(
            child=field_serializer, required=required, source=source, **kwargs
        )

    def get_value_for_filter(self, row: "GeneratedTableModel", field) -> str:
        related_objects = getattr(row, field.db_column)
        values = [related_object.value for related_object in related_objects.all()]
        value = list_to_comma_separated_string(values)
        return value

    def get_internal_value_from_db(
        self, row: "GeneratedTableModel", field_name: str
    ) -> List[int]:
        related_objects = getattr(row, field_name)
        return [related_object.id for related_object in related_objects.all()]

    def get_response_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)
        return SelectOptionSerializer(
            **{
                "required": required,
                "allow_null": not required,
                "many": True,
                **kwargs,
            }
        )

    def enhance_queryset(self, queryset, field, name, **kwargs):
        # It's important that this individual enhance_queryset method exists, even
        # though the enhance queryset in bulk exists, because the link_row field can
        # prefetch the data individually.
        return queryset.prefetch_related(name)

    def get_search_expression(self, field: MultipleSelectField, queryset) -> Expression:
        return Subquery(
            queryset.filter(pk=OuterRef("pk")).values(
                aggregated=StringAgg(
                    f"{field.db_column}__value", " ", output_field=models.TextField()
                )
            )[:1]
        )

    def prepare_value_for_db(self, instance, value):
        return self.prepare_value_for_db_in_bulk(
            instance, {0: value}, continue_on_error=False
        )[0]

    def prepare_value_for_db_in_bulk(
        self, instance, values_by_row, continue_on_error=False
    ):
        # Create a map {value -> row_indexes} for ids and strings
        id_map = defaultdict(list)
        name_map = defaultdict(list)
        invalid_values = []
        options_from_ids, options_from_names = [], []
        for row_index, values in values_by_row.items():
            for value in values:
                if isinstance(value, int):
                    id_map[value].append(row_index)
                elif isinstance(value, str):
                    name_map[value].append(row_index)
                else:
                    if continue_on_error:
                        invalid_values.append(values)
                        break
                    else:
                        # Fail on first error
                        raise AllProvidedValuesMustBeIntegersOrStrings(value)

        if invalid_values:
            # Replace values by error for failing rows
            for row_index in invalid_values:
                values_by_row[row_index] = AllProvidedValuesMustBeIntegersOrStrings(
                    values_by_row[row_index]
                )

        if id_map:
            # Query database for existing options
            options_from_ids = SelectOption.objects.filter(
                field=instance, id__in=id_map.keys()
            )
            option_ids = [opt.id for opt in options_from_ids]

            if len(option_ids) != len(id_map):
                invalid_ids = sorted(list(set(id_map.keys()) - set(option_ids)))
                if continue_on_error:
                    # Replace values by error for failing rows
                    for invalid_name in invalid_ids:
                        for row_index in id_map[invalid_name]:
                            values_by_row[
                                row_index
                            ] = AllProvidedMultipleSelectValuesMustBeSelectOption(
                                invalid_name
                            )
                else:
                    # or fail fast
                    raise AllProvidedMultipleSelectValuesMustBeSelectOption(invalid_ids)

        if name_map:
            # Query database for existing options
            options_from_names = list(
                SelectOption.objects.filter(field=instance, value__in=name_map.keys())
            )
            # Remove duplicate names
            found_option_names = set([opt.value for opt in options_from_names])

            if len(name_map) != len(found_option_names):
                invalid_names = sorted(list(set(name_map.keys()) - found_option_names))
                if continue_on_error:
                    # Replace values by error for failing rows
                    for invalid_name in invalid_names:
                        for row_index in name_map[invalid_name]:
                            values_by_row[
                                row_index
                            ] = AllProvidedMultipleSelectValuesMustBeSelectOption(
                                invalid_name
                            )

                else:
                    # or fail fast
                    raise AllProvidedMultipleSelectValuesMustBeSelectOption(
                        invalid_names
                    )

            # Map {name -> opt} reverse list to let the first value win in the map
            opt_map = {opt.value: opt for opt in options_from_names[::-1]}

            rows_that_needs_name_replacement = {
                val for value in name_map.values() for val in value
            }

            # Replace all option names with actual option ids
            for row_index in rows_that_needs_name_replacement:
                value = values_by_row[row_index]
                if isinstance(value, list):  # filter rows with exceptions
                    values_by_row[row_index] = [
                        opt_map[val].id if isinstance(val, str) else val
                        for val in value
                    ]

        options = {
            **{opt.id: opt for opt in options_from_ids},
            **{opt.id: opt for opt in options_from_names},
        }

        def are_invalid_options(value):
            return isinstance(value, Exception)

        # Removes duplicates while keeping ordering
        final_values_by_row = {}
        for row_id, value in values_by_row.items():
            if are_invalid_options(value):
                final_values_by_row[row_id] = value
                continue

            value_without_duplicates = list(dict.fromkeys(value))
            final_values_by_row[row_id] = [
                options[v_id] for v_id in value_without_duplicates
            ]

        return final_values_by_row

    def get_serializer_help_text(self, instance):
        return (
            "This field accepts a list of `integer` each of which representing the "
            "chosen select option id related to the field. Available ids can be found"
            "when getting or listing the field. "
            "You can also send a list of option names in which case the option are "
            "searched by name. The first one that matches is used. "
            "This field also accepts a string with names separated by a comma or an "
            "array of file names. "
            "The response represents chosen field, but also the value and "
            "color is exposed."
        )

    def random_value(self, instance, fake, cache):
        """
        Selects a random sublist out of the possible options.
        """

        cache_entry_name = f"field_{instance.id}_options"

        if cache_entry_name not in cache:
            cache[cache_entry_name] = list(
                instance.select_options.values_list("id", flat=True)
            )

        select_options = cache[cache_entry_name]

        # if the select_options are empty return empty list
        if not select_options:
            return None

        return sample(select_options, randint(1, len(select_options)))  # nosec

    def get_export_value(self, value, field_object, rich_value=False):
        if value is None:
            return [] if rich_value else ""

        result = [item.value for item in value.all()]

        if rich_value:
            return result
        else:
            return list_to_comma_separated_string(result)

    def get_human_readable_value(self, value, field_object):
        export_value = self.get_export_value(value, field_object, rich_value=True)

        return ", ".join(export_value)

    def get_model_field(self, instance, **kwargs):
        return None

    def after_model_generation(self, instance, model, field_name):
        select_option_meta = type(
            "Meta",
            (AbstractSelectOption.Meta,),
            {
                "managed": False,
                "app_label": model._meta.app_label,
                "db_tablespace": model._meta.db_tablespace,
                "db_table": "database_selectoption",
                "apps": model._meta.apps,
            },
        )
        select_option_model = type(
            str(f"MultipleSelectField{instance.id}SelectOption"),
            (AbstractSelectOption,),
            {
                "Meta": select_option_meta,
                "field": models.ForeignKey(
                    Field, on_delete=models.CASCADE, related_name="+"
                ),
                "__module__": model.__module__,
                "_generated_table_model": True,
            },
        )
        related_name = f"reversed_field_{instance.id}"
        shared_kwargs = {
            "null": True,
            "blank": True,
            "db_table": instance.through_table_name,
            "db_constraint": False,
        }

        default = self.get_instance_default_value(instance, None)
        if default is not None:
            shared_kwargs["default"] = default

        MultipleSelectManyToManyField(
            to=select_option_model, related_name=related_name, **shared_kwargs
        ).contribute_to_class(model, field_name)
        MultipleSelectManyToManyField(
            to=model, related_name=field_name, **shared_kwargs
        ).contribute_to_class(select_option_model, related_name)

    def get_export_serialized_value(self, row, field_name, cache, files_zip, storage):
        cache_entry = f"{field_name}_relations"
        if cache_entry not in cache:
            # In order to prevent a lot of lookup queries in the through table, we want
            # to fetch all the relations and add it to a temporary in memory cache
            # containing a mapping of the old ids to the new ids. Every relation can
            # use the cached mapped relations to find the correct id.
            cache[cache_entry] = defaultdict(list)
            through_model = row._meta.get_field(field_name).remote_field.through
            through_model_fields = through_model._meta.get_fields()
            current_field_name = through_model_fields[1].name
            relation_field_name = through_model_fields[2].name
            for relation in through_model.objects.all():
                cache[cache_entry][
                    getattr(relation, f"{current_field_name}_id")
                ].append(getattr(relation, f"{relation_field_name}_id"))

        return cache[cache_entry][row.id]

    def set_import_serialized_value(
        self, row, field_name, value, id_mapping, cache, files_zip, storage
    ):
        through_model = row._meta.get_field(field_name).remote_field.through
        through_model_fields = through_model._meta.get_fields()
        current_field_name = through_model_fields[1].name
        relation_field_name = through_model_fields[2].name

        return [
            through_model(
                **{
                    f"{current_field_name}_id": row.id,
                    f"{relation_field_name}_id": id_mapping[
                        "database_field_select_options"
                    ][item],
                }
            )
            for item in value
            if item in id_mapping["database_field_select_options"]
        ]

    def contains_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()

        query = StringAgg(f"{field_name}__value", ",", output_field=models.TextField())

        return AnnotatedQ(
            annotation={
                f"select_option_value_{field_name}": Coalesce(
                    query, Value(""), output_field=models.TextField()
                )
            },
            q={f"select_option_value_{field_name}__icontains": value},
        )

    def contains_word_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()
        value = re.escape(value)
        query = StringAgg(f"{field_name}__value", " ", output_field=models.TextField())

        return AnnotatedQ(
            annotation={
                f"select_option_value_{field_name}": Coalesce(
                    query, Value(""), output_field=models.TextField()
                )
            },
            q={f"select_option_value_{field_name}__iregex": rf"\m{value}\M"},
        )

    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ):
        """
        Order by the concatenated values of the select options, separated by a comma.
        """

        # FIXME: this is broken because the field sort items by insertion order with the
        # id in the through table. It's fixable here using a subquery on the m2m table
        # instead of a `StringAgg`, but it will be very difficult to fix in the formula
        # language. Also the frontend is not matching exactly the backend sorting and we
        # should also consider the possibility that a comma can be part of the value.
        sort_column_name = f"{field_name}_agg_sort"
        query = Coalesce(
            StringAgg(
                self.get_sortable_column_expression(field, field_name, sort_type),
                ",",
                output_field=models.TextField(),
            ),
            Value(""),
            output_field=models.TextField(),
        )
        annotation = {sort_column_name: query}
        order = collate_expression(F(sort_column_name))

        if order_direction == "DESC":
            order = order.desc(nulls_first=True)
        else:
            order = order.asc(nulls_first=True)

        return OptionallyAnnotatedOrderBy(annotation=annotation, order=order)

    def get_group_by_aggregated_order(self, related_field):
        # The multiple select field must be ordered by the id of the entry in the
        # through table because it respects the insertion order. It respects the
        # `MultipleSelectManyToManyDescriptor::related_manager_cls::_apply_rel_ordering`
        return ("id",) + super().get_group_by_aggregated_order(related_field)

    def before_field_options_update(
        self, field, to_create=None, to_update=None, to_delete=None
    ):
        """
        Before removing the select options, we want to delete the link between
        the row and the options.
        """

        through_model = (
            field.table.get_model(fields=[field], field_ids=[])
            ._meta.get_field(field.db_column)
            .remote_field.through
        )
        through_model_fields = through_model._meta.get_fields()
        option_field_name = through_model_fields[2].name
        through_model.objects.filter(**{f"{option_field_name}__in": to_delete}).delete()

    def serialize_metadata_for_row_history(
        self,
        field: Field,
        row: "GeneratedTableModel",
        metadata: Optional[SerializedRowHistoryFieldMetadata] = None,
    ) -> SerializedRowHistoryFieldMetadata:
        base = super().serialize_metadata_for_row_history(field, row, metadata)

        already_serialized_options = {}
        if metadata and metadata.get("select_options"):
            already_serialized_options = metadata["select_options"]

        new_select_options = getattr(row, field.db_column).all()
        new_serialized_options = {
            option.id: {
                "id": option.id,
                "value": option.value,
                "color": option.color,
            }
            for option in new_select_options
        }

        return {
            **base,
            "select_options": {
                **already_serialized_options,
                **new_serialized_options,
            },
        }

    def are_row_values_equal(self, value1: any, value2: any) -> bool:
        return set(value1 or []) == set(value2 or [])

    def get_formula_reference_to_model_field(
        self, model_field, db_column, already_in_subquery
    ):
        agg_expr = JSONBAgg(
            get_select_option_extractor(db_column, model_field),
            filter=Q(**{f"{db_column}__isnull": False}),
            ordering=(f"{db_column}__order", f"{db_column}__id"),
        )
        if already_in_subquery:
            return Coalesce(agg_expr, Value([], output_field=JSONField()))
        else:
            return Coalesce(
                wrap_in_subquery(agg_expr, db_column, model_field.model),
                Value([], output_field=JSONField()),
            )


class PhoneNumberFieldType(CollationSortMixin, CharFieldMatchingRegexFieldType):
    """
    A simple wrapper around a TextField which ensures any entered data is a
    simple phone number.

    See `docs/decisions/001-phone-number-field-validation.md` for context
    as to why the phone number validation was implemented using a simple regex.
    """

    type = "phone_number"
    model_class = PhoneNumberField
    can_upsert = True

    MAX_PHONE_NUMBER_LENGTH = 100

    @property
    def regex(self):
        """
        Allow common punctuation used in phone numbers and spaces to allow formatting,
        but otherwise don't allow text as the phone number should work as a link on
        mobile devices.
        Duplicated in the frontend code at, please keep in sync:
        web-frontend/modules/core/utils/string.js#isSimplePhoneNumber
        """

        return rf"^[0-9NnXx,+._*()#=;/ -]{{1,{self.max_length}}}$"

    @property
    def max_length(self):
        """
        According to the E.164 (https://en.wikipedia.org/wiki/E.164) standard for
        international numbers the max length of an E.164 number without formatting is 15
        characters. However we allow users to store formatting characters, spaces and
        expect them to be entering numbers not in the E.164 standard but instead a
        wide range of local standards which might support longer numbers.
        This is why we have picked a very generous 100 character length to support
        heavily formatted local numbers.
        """

        return self.MAX_PHONE_NUMBER_LENGTH

    def random_value(self, instance, fake, cache):
        return fake.phone_number()

    def get_value_for_filter(self, row: "GeneratedTableModel", field: Field) -> any:
        value = getattr(row, field.db_column)
        return collate_expression(Value(value))


class FormulaFieldType(FormulaFieldTypeArrayFilterSupport, ReadOnlyFieldType):
    type = "formula"
    model_class = FormulaField
    _db_column_fields = []

    can_be_in_form_view = False
    field_data_is_derived_from_attrs = True
    needs_refresh_after_import_serialized = True
    include_in_row_move_updated_fields = False

    CORE_FORMULA_FIELDS = [
        "formula",
        "formula_type",
    ]
    allowed_fields = BASEROW_FORMULA_TYPE_ALLOWED_FIELDS + CORE_FORMULA_FIELDS
    serializer_extra_args = ["limit_linked_items"]
    request_serializer_field_names = (
        BASEROW_FORMULA_TYPE_REQUEST_SERIALIZER_FIELD_NAMES + CORE_FORMULA_FIELDS
    )
    request_serializer_field_overrides = {
        "error": serializers.CharField(required=False, read_only=True),
        "nullable": serializers.BooleanField(required=False, read_only=True),
    }
    serializer_field_names = (
        BASEROW_FORMULA_TYPE_SERIALIZER_FIELD_NAMES + CORE_FORMULA_FIELDS
    )

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.database.formula.types.formula_types import (
            get_baserow_formula_type_serializer_field_overrides,
        )

        return {
            **self.request_serializer_field_overrides,
            **get_baserow_formula_type_serializer_field_overrides(),
        }

    def empty_query(self, field_name, model_field, field) -> Q:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)
        return field_type.empty_query(field_name, model_field, field_instance)

    @staticmethod
    def _stack_error_mapper(e):
        return (
            ERROR_TOO_DEEPLY_NESTED_FORMULA
            if "stack depth limit exceeded" in str(e)
            else None
        )

    api_exceptions_map = {
        BaserowFormulaException: ERROR_WITH_FORMULA,
        OperationalError: _stack_error_mapper,
    }

    def get_search_expression(
        self, field: FormulaField, queryset: QuerySet
    ) -> Expression:
        return self.to_baserow_formula_type(field.specific).get_search_expression(
            field, queryset
        )

    def is_searchable(self, field: FormulaField) -> bool:
        return self.to_baserow_formula_type(field.specific).is_searchable(field)

    @staticmethod
    def array_of(formula_type: str):
        return BaserowFormulaArrayType.formula_array_type_as_str(formula_type)

    @staticmethod
    def compatible_with_formula_types(*compatible_formula_types: List[str]):
        def checker(field) -> bool:
            from baserow.contrib.database.fields.registries import field_type_registry

            field_type = field_type_registry.get_by_model(field.specific_class)
            if isinstance(field_type, FormulaFieldType):
                formula_type = field.specific.cached_formula_type
                return formula_type.check_if_compatible_with(compatible_formula_types)
            else:
                return False

        return checker

    def get_field_instance_and_type_from_formula_field(
        self,
        formula_field_instance: FormulaField,
    ) -> Tuple[Field, FieldType]:
        """
        Gets the BaserowFormulaType the provided formula field currently has and the
        Baserow FieldType used to work with a formula of that formula type.

        :param formula_field_instance: An instance of a formula field.
        :return: The BaserowFormulaType of the formula field instance.
        """

        formula_type = self.to_baserow_formula_type(formula_field_instance)
        return formula_type.get_baserow_field_instance_and_type()

    def _filter_serializer_field_kwargs(
        self, field_type: FieldType, **kwargs
    ) -> Dict[str, Any]:
        """
        Filters the serializer kwargs to only include those that are relevant for
        the formula field type.
        """

        kwargs_to_remove = set(self.serializer_extra_args) - set(
            getattr(field_type, "serializer_extra_args", [])
        )

        return {
            key: value for key, value in kwargs.items() if key not in kwargs_to_remove
        }

    def get_serializer_field(self, instance: FormulaField, **kwargs):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(instance)

        field_kwargs = self._filter_serializer_field_kwargs(field_type, **kwargs)
        return field_type.get_serializer_field(field_instance, **field_kwargs)

    def get_response_serializer_field(self, instance, **kwargs):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(instance)
        field_kwargs = self._filter_serializer_field_kwargs(field_type, **kwargs)
        return field_type.get_response_serializer_field(field_instance, **field_kwargs)

    def get_model_field(self, instance: FormulaField, **kwargs):
        # When typed_table is False we are constructing a table model without
        # doing any type checking, we can't know what the expression is in this
        # case but we still want to generate a model field so the model can be
        # used to do SQL operations like dropping fields etc.
        if not (instance.error or instance.trashed):
            expression = FormulaHandler.get_typed_internal_expression_from_field(
                instance
            )
        else:
            expression = None

        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(instance)
        expression_field_type = field_type.get_model_field(field_instance, **kwargs)

        # Depending on the `expression_field_type` class level state is changed when
        # the field is __init__'ed. This means to prevent different sub types polluting
        # this class level state of other runtime instances we need a unique class
        # per subtype.
        # noinspection PyPep8Naming
        SpecializedBaserowExpressionField = type(
            expression_field_type.__class__.__name__ + "BaserowExpressionField",
            (BaserowExpressionField,),
            {},
        )
        return SpecializedBaserowExpressionField(
            null=True,
            blank=True,
            expression=expression,
            expression_field=expression_field_type,
            db_index=instance.db_index,
            **kwargs,
        )

    def has_compatible_model_fields(self, instance, instance2) -> bool:
        return (
            super().has_compatible_model_fields(instance, instance2)
            and instance.formula_type == instance2.formula_type
            and instance.array_formula_type == instance.array_formula_type
        )

    def prepare_value_for_db(self, instance, value):
        """
        Since the Formula Field is a read only field, we raise a
        ValidationError when there is a value present.
        """

        if not value:
            return value

        raise ValidationError(
            f"Field of type {self.type} is read only and should not be set manually.",
            code="read_only",
        )

    def get_export_value(
        self, value, field_object, rich_value=False
    ) -> BaserowFormulaType:
        instance = field_object["field"]
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(instance)
        # Add the formula_field instance to provide a reference to the source table,
        # which might be needed for the export value (i.e. multiple collaborators field)
        return field_type.get_export_value(
            value,
            {
                "field": field_instance,
                "type": field_type,
                "name": field_object["name"],
                "formula_field": instance,
            },
            rich_value=rich_value,
        )

    def contains_query(self, field_name, value, model_field, field: FormulaField):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)
        return field_type.contains_query(field_name, value, model_field, field_instance)

    def contains_word_query(self, field_name, value, model_field, field):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)
        return field_type.contains_word_query(
            field_name, value, model_field, field_instance
        )

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(from_field)
        return field_type.get_alter_column_prepare_old_value(
            connection, field_instance, to_field
        )

    def to_baserow_formula_type(self, field: FormulaField) -> BaserowFormulaType:
        return field.cached_formula_type

    def to_baserow_formula_expression(
        self, field: FormulaField
    ) -> BaserowExpression[BaserowFormulaType]:
        if field.expand_formula_when_referenced:
            return FormulaHandler.get_typed_internal_expression_from_field(field)
        else:
            return super().to_baserow_formula_expression(field)

    def get_field_dependencies(
        self, field_instance: FormulaField, field_cache: "FieldCache"
    ) -> FieldDependencies:
        return FormulaHandler.get_field_dependencies(field_instance, field_cache)

    def get_human_readable_value(self, value: Any, field_object) -> str:
        formula_field = field_object["field"]
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(formula_field)
        # Add the formula_field instance to provide a reference to the source table,
        # which might be needed for the export value (i.e. multiple collaborators field)
        return field_type.get_human_readable_value(
            value,
            {
                "field": field_instance,
                "type": field_type,
                "name": field_object["name"],
                "formula_field": formula_field,
            },
        )

    def restore_failed(self, field_instance, restore_exception):
        handleable_exceptions_to_error = {
            SelfReferenceFieldDependencyError: "After restoring references itself "
            "which is impossible",
            CircularFieldDependencyError: "After restoring would causes a circular "
            "reference between fields",
        }
        exception_type = type(restore_exception)
        if exception_type in handleable_exceptions_to_error:
            BaserowFormulaInvalidType(
                handleable_exceptions_to_error[exception_type]
            ).persist_onto_formula_field(field_instance)
            field_instance.save(recalculate=False)
            return True
        else:
            return False

    def get_fields_needing_periodic_update(self) -> Optional[QuerySet]:
        return FormulaField.objects.filter(
            needs_periodic_update=True,
            table__trashed=False,
            table__database__trashed=False,
            table__database__workspace__trashed=False,
        )

    def run_periodic_update(
        self,
        fields: List[Field],
        update_collector: "Optional[FieldUpdateCollector]" = None,
        field_cache: "Optional[FieldCache]" = None,
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
        already_updated_fields: Optional[List[Field]] = None,
        skip_search_updates: bool = False,
        database_id: Optional[int] = None,
    ):
        from baserow.contrib.database.fields.dependencies.update_collector import (
            FieldUpdateCollector,
        )

        update_collectors = {}
        updated_fields = set(
            already_updated_fields.copy() if already_updated_fields else []
        )

        if field_cache is None:
            field_cache = FieldCache()

        for field in fields:
            if field.table_id not in update_collectors:
                update_collectors[field.table_id] = FieldUpdateCollector(
                    field.table, update_changes_only=True
                )

            update_collector = update_collectors[field.table_id]

            self._update_field_values(
                field, update_collector, field_cache, via_path_to_starting_table
            )
            updated_fields.add(field)

        for update_collector in update_collectors.values():
            updated_fields |= set(
                update_collector.apply_updates_and_get_updated_fields(
                    field_cache, skip_search_updates=skip_search_updates
                )
            )

        all_dependent_fields_grouped_by_depth = (
            FieldDependencyHandler.group_all_dependent_fields_by_level_from_fields(
                fields,
                field_cache,
                associated_relations_changed=False,
                database_id_prefilter=database_id,
            )
        )
        for dependant_fields_group in all_dependent_fields_grouped_by_depth:
            for table_id, dependant_field, _ in dependant_fields_group:
                if not isinstance(dependant_field, FormulaField):
                    # LinkRowFields might depends on FormulaFields, but we can't update
                    # them here because this is only valid for FormulaFields.
                    continue
                self._update_field_values(
                    dependant_field,
                    update_collectors[table_id],
                    field_cache,
                    via_path_to_starting_table,
                )
            updated_fields |= set(
                update_collector.apply_updates_and_get_updated_fields(
                    field_cache, skip_search_updates=skip_search_updates
                )
            )

        update_collector.send_force_refresh_signals_for_all_updated_tables()

        return list(updated_fields)

    def row_of_dependency_updated(
        self,
        field: FormulaField,
        starting_row: "StartingRowType",
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]],
        dependency_context: DependencyContext,
    ):
        self._update_field_values(
            field, update_collector, field_cache, via_path_to_starting_table
        )

        super().row_of_dependency_updated(
            field,
            starting_row,
            update_collector,
            field_cache,
            via_path_to_starting_table,
            dependency_context,
        )

    def _update_field_values(
        self,
        field: FormulaField,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]],
    ):
        update_statement = (
            FormulaHandler.baserow_expression_to_update_django_expression(
                field.cached_typed_internal_expression,
                field_cache.get_model(field.table),
            )
        )
        update_collector.add_field_with_pending_update_statement(
            field,
            update_statement,
            via_path_to_starting_table=via_path_to_starting_table,
        )

    def field_dependency_created(
        self,
        field: Field,
        created_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        old_field = deepcopy(field)
        self._update_formula_after_dependency_change(
            field, old_field, update_collector, field_cache, via_path_to_starting_table
        )

    def field_dependency_updated(
        self,
        field: Field,
        updated_field: Field,
        updated_old_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        old_field = deepcopy(field)

        old_name = updated_old_field.name
        new_name = updated_field.name
        rename = (
            old_name != new_name
            # Because the `rename_field_references_in_formula_string` only updates
            # field references in the same table, there is no need to rename if the
            # table id doesn't match because it can cause incorrect renames if fields
            # have the same name in the two tables.
            and field.table_id == updated_field.table_id
        )
        if rename:
            field.formula = FormulaHandler.rename_field_references_in_formula_string(
                field.formula, {old_name: new_name}
            )
        self._update_formula_after_dependency_change(
            field,
            old_field,
            update_collector,
            field_cache,
            via_path_to_starting_table,
        )

    # noinspection PyMethodMayBeStatic
    def _update_formula_after_dependency_change(
        self,
        field: FormulaField,
        old_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        expr = FormulaHandler.recalculate_formula_and_get_update_expression(
            field, old_field, field_cache
        )
        # Check if the formula field type has changed. This can for example change into
        # an invalid type. If so, then we need to call the `add_to_fields_type_changed`
        # so that eventually the view filters, sorts, etc are removed if needed.
        if not self.has_compatible_model_fields(field, old_field):
            update_collector.add_to_fields_type_changed(field)
        update_collector.add_to_rebuild_field_dependencies(field)
        update_collector.add_field_with_pending_update_statement(
            field, expr, via_path_to_starting_table=via_path_to_starting_table
        )

    def field_dependency_deleted(
        self,
        field: Field,
        deleted_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        old_field = deepcopy(field)
        self._update_formula_after_dependency_change(
            field, old_field, update_collector, field_cache, via_path_to_starting_table
        )

    def after_create(self, field, model, user, connection, before, field_kwargs):
        """
        Immediately after the field has been created, we need to populate the values
        with the already existing source_field_name column.
        """

        model = field.table.get_model()
        expr = FormulaHandler.baserow_expression_to_update_django_expression(
            field.cached_typed_internal_expression, model
        )
        model.objects_and_trash.all().update(**{f"{field.db_column}": expr})

    def after_rows_created(
        self,
        field: FormulaField,
        rows: List["GeneratedTableModel"],
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
    ):
        self._update_field_values(field, update_collector, field_cache, [])

    def after_update(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        user,
        connection,
        altered_column,
        before,
        to_field_kwargs,
    ):
        to_model = to_field.table.get_model()
        expr = FormulaHandler.baserow_expression_to_update_django_expression(
            to_field.cached_typed_internal_expression, to_model
        )
        to_model.objects_and_trash.all().update(**{f"{to_field.db_column}": expr})

    def after_import_serialized(self, field, field_cache, id_mapping):
        field.save(recalculate=True, field_cache=field_cache)
        FieldDependencyHandler.rebuild_dependencies([field], field_cache)

    def after_rows_imported(
        self,
        field: FormulaField,
        update_collector: Optional[FieldUpdateCollector] = None,
        field_cache: Optional["FieldCache"] = None,
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        apply_updates = False
        if update_collector is None:
            update_collector = FieldUpdateCollector(field.table)
            apply_updates = True

        if field_cache is None:
            field_cache = FieldCache()

        self._update_field_values(
            field, update_collector, field_cache, via_path_to_starting_table or []
        )

        # TODO: To improve performance, group formula fields at the same level and
        # in the same table and apply updates in one go.
        if apply_updates:
            update_collector.apply_updates_and_get_updated_fields(
                field_cache,
                skip_search_updates=True,  # will be updated at the end of the import
            )

    def check_can_order_by(self, field, order_type):
        # The formula types are not compatible with the order type. Therefore,
        # if the `order_type` is not the default, it will always return False.
        if order_type != DEFAULT_SORT_TYPE_KEY:
            return False
        return self.to_baserow_formula_type(field.specific).can_order_by

    def check_can_group_by(self, field, sort_type):
        # The formula types are not compatible with the order type. Therefore,
        # if the `order_type` is not the default, it will always return False.
        return self.to_baserow_formula_type(field.specific).can_group_by

    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ) -> OptionallyAnnotatedOrderBy:
        # Ignore the `sort_type` because that is not yet supported in formulas.
        return self.to_baserow_formula_type(field.specific).get_order(
            field, field_name, order_direction, table_model=table_model
        )

    def get_value_for_filter(self, row: "GeneratedTableModel", field):
        return self.to_baserow_formula_type(field.specific).get_value_for_filter(
            row, field
        )

    def should_update_search_data(
        self, old_field: LinkRowField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_formula = new_field_attrs.get("formula", old_field.formula)
        return old_field.formula != new_formula

    def should_backup_field_data_for_same_type_update(
        self, old_field: FormulaField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        return False

    def can_represent_date(self, field: "Field") -> bool:
        return self.to_baserow_formula_type(field.specific).can_represent_date

    def can_represent_files(self, field):
        return self.to_baserow_formula_type(field.specific).can_represent_files

    def can_represent_select_options(self, field):
        return self.to_baserow_formula_type(field.specific).can_represent_select_options

    def can_represent_collaborators(self, field):
        return self.to_baserow_formula_type(field.specific).can_represent_collaborators

    def get_permission_error_when_user_changes_field_to_depend_on_forbidden_field(
        self, user: AbstractUser, changed_field: Field, forbidden_field: Field
    ) -> Exception:
        from baserow.contrib.database.formula import (
            InvalidFormulaType,
            get_invalid_field_and_table_formula_error,
        )

        return InvalidFormulaType(
            get_invalid_field_and_table_formula_error(
                forbidden_field.name, forbidden_field.table.name
            )
        )

    def valid_for_bulk_update(self, field: Field) -> bool:
        # Let the dependency handler handle the update in the right order
        return False

    def get_field_depdendencies_before_import_serialized(
        self,
        serialized_field: Dict[str, Any],
        serialized_fields_map: Dict[int, Dict[str, Any]],
        primary_table_fields_map: Dict[int, int],
    ) -> Optional[Set[Tuple[Union[int, str], Union[int, str]]]]:
        if "formula" not in serialized_field:
            raise NotImplementedError(
                "Each formula subtype needs to implement this method."
            )

        return FormulaHandler.get_dependencies_field_names(serialized_field["formula"])

    def parse_filter_value(self, field, model_field, value):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)
        return field_type.parse_filter_value(field_instance, model_field, value)

    def can_have_db_index(self, field: Field) -> bool:
        return self.to_baserow_formula_type(field.specific).can_have_db_index


class CountFieldType(FormulaFieldType):
    type = "count"
    model_class = CountField
    api_exceptions_map = {
        **FormulaFieldType.api_exceptions_map,
        InvalidCountThroughField: ERROR_INVALID_COUNT_THROUGH_FIELD,
    }
    can_get_unique_values = False
    allowed_fields = BASEROW_FORMULA_TYPE_ALLOWED_FIELDS + [
        "through_field_id",
    ]
    serializer_field_names = BASEROW_FORMULA_TYPE_ALLOWED_FIELDS + [
        "through_field_id",
        "formula_type",
    ]
    serializer_field_overrides = {
        "through_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="through_field.id",
            help_text="The id of the link row field to count values for.",
        ),
        "nullable": serializers.BooleanField(required=False, read_only=True),
    }

    @property
    def request_serializer_field_names(self):
        return self.serializer_field_names

    @property
    def request_serializer_field_overrides(self):
        return self.serializer_field_overrides

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        self._validate_through_field_values(
            table,
            allowed_field_values,
            field_kwargs,
        )

    def get_fields_needing_periodic_update(self) -> Optional[QuerySet]:
        return None

    def before_update(self, from_field, to_field_values, user, kwargs):
        if isinstance(from_field, CountField):
            through_field_id = (
                from_field.through_field.id
                if from_field.through_field is not None
                else None
            )
            self._validate_through_field_values(
                from_field.table,
                to_field_values,
                kwargs,
                through_field_id,
            )
        else:
            self._validate_through_field_values(
                from_field.table, to_field_values, kwargs
            )

    def field_dependency_deleted(
        self,
        field: CountField,
        deleted_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        if field.through_field_id == deleted_field.id:
            field.through_field_id = None
        return super().field_dependency_deleted(
            field,
            deleted_field,
            update_collector,
            field_cache,
            via_path_to_starting_table,
        )

    def _validate_through_field_values(
        self,
        table,
        values,
        all_kwargs,
        default_through_field_id=None,
    ):
        through_field_id = values.get("through_field_id", default_through_field_id)
        through_field_name = all_kwargs.get("through_field_name", None)

        # If the `through_field_name` is provided in the kwargs when creating or
        # updating a field, then we want to find the `link_row` field by its name.
        if through_field_name is not None:
            try:
                through_field_id = table.field_set.get(name=through_field_name).id
            except Field.DoesNotExist:
                raise InvalidCountThroughField()

        try:
            through_field = FieldHandler().get_field(through_field_id, LinkRowField)
        except FieldDoesNotExist:
            # Occurs when the through_field_id points at a non LinkRowField
            raise InvalidCountThroughField()

        if through_field.table != table:
            raise InvalidCountThroughField()

        values["through_field_id"] = through_field.id
        # There is never a need to allow decimal places on the count field.
        # Therefore, we reset it to 0 to make sure when a formula converts to count,
        # it will have the right value.
        values["number_decimal_places"] = 0

    def import_serialized(
        self,
        table: "Table",
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        deferred_fk_update_collector: DeferredForeignKeyUpdater,
    ) -> "Field":
        serialized_copy = serialized_values.copy()
        # We have to temporarily remove the `through_field_id`, because it can be
        # that they haven't been created yet, which prevents us from finding it in
        # the mapping.
        original_through_field_id = serialized_copy.pop("through_field_id")
        field = super().import_serialized(
            table,
            serialized_copy,
            import_export_config,
            id_mapping,
            deferred_fk_update_collector,
        )
        deferred_fk_update_collector.add_deferred_fk_to_update(
            field, "through_field_id", original_through_field_id, "database_fields"
        )
        return field

    def get_field_depdendencies_before_import_serialized(
        self,
        serialized_field: Dict[str, Any],
        serialized_fields_map: Dict[int, Dict[str, Any]],
        primary_table_fields_map: Dict[int, int],
    ) -> Optional[Set[Tuple[Union[int, str], Union[int, str]]]]:
        through_field_id = serialized_field.get("through_field_id", None)
        if through_field_id is None or through_field_id not in serialized_fields_map:
            return None  # broken reference
        through_field = serialized_fields_map[through_field_id]
        through_field_name = through_field["name"]
        related_table_id = through_field.get("link_row_table_id", None)

        # it means we're targeting a field that already exists before the import
        # (i.e. duplicating a table/field)
        if related_table_id is None or related_table_id not in primary_table_fields_map:
            return None

        target_field_id = primary_table_fields_map[related_table_id]
        target_field = serialized_fields_map[target_field_id]
        target_field_name = target_field["name"]
        return {(target_field_name, through_field_name)}

    def enhance_field_queryset(
        self, queryset: QuerySet[Field], field: Field
    ) -> QuerySet[Field]:
        return queryset.select_related("through_field")


class RollupFieldType(FormulaFieldType):
    type = "rollup"
    model_class = RollupField
    api_exceptions_map = {
        **FormulaFieldType.api_exceptions_map,
        InvalidRollupThroughField: ERROR_INVALID_ROLLUP_THROUGH_FIELD,
        InvalidRollupTargetField: ERROR_INVALID_ROLLUP_TARGET_FIELD,
        FormulaFunctionTypeDoesNotExist: ERROR_INVALID_ROLLUP_FORMULA_FUNCTION,
    }
    can_get_unique_values = False
    allowed_fields = BASEROW_FORMULA_TYPE_ALLOWED_FIELDS + [
        "through_field_id",
        "target_field_id",
        "rollup_function",
    ]
    serializer_field_names = BASEROW_FORMULA_TYPE_ALLOWED_FIELDS + [
        "through_field_id",
        "target_field_id",
        "rollup_function",
        "formula_type",
    ]
    serializer_field_overrides = {
        "through_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="through_field.id",
            help_text="The id of the link row field to rollup values for.",
        ),
        "target_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="target_field.id",
            help_text="The id of the field in the table linked to by the "
            "through_field to rollup.",
        ),
        "nullable": serializers.BooleanField(required=False, read_only=True),
    }

    @property
    def request_serializer_field_names(self):
        return self.serializer_field_names

    @property
    def request_serializer_field_overrides(self):
        return self.serializer_field_overrides

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        self._validate_through_and_target_field_values(
            table,
            allowed_field_values,
            field_kwargs,
        )

    def get_fields_needing_periodic_update(self) -> Optional[QuerySet]:
        return None

    def before_update(self, from_field, to_field_values, user, kwargs):
        if isinstance(from_field, RollupField):
            through_field_id = (
                from_field.through_field.id
                if from_field.through_field is not None
                else None
            )
            target_field_id = (
                from_field.target_field.id
                if from_field.target_field is not None
                else None
            )
            self._validate_through_and_target_field_values(
                from_field.table,
                to_field_values,
                kwargs,
                through_field_id,
                target_field_id,
            )
        else:
            self._validate_through_and_target_field_values(
                from_field.table,
                to_field_values,
                kwargs,
            )

    def _validate_through_and_target_field_values(
        self,
        table,
        values,
        all_kwargs,
        default_through_field_id=None,
        default_target_field_id=None,
    ):
        through_field_id = values.get("through_field_id", default_through_field_id)
        target_field_id = values.get("target_field_id", default_target_field_id)
        through_field_name = all_kwargs.get("through_field_name", None)
        target_field_name = all_kwargs.get("target_field_name", None)

        # If the `through_field_name` is provided in the kwargs when creating or
        # updating a field, then we want to find the `link_row` field by its name.
        if through_field_name is not None:
            try:
                through_field_id = table.field_set.get(name=through_field_name).id
            except Field.DoesNotExist:
                raise InvalidRollupThroughField()
        try:
            through_field = FieldHandler().get_field(through_field_id, LinkRowField)
        except FieldDoesNotExist:
            # Occurs when the through_field_id points at a non LinkRowField
            raise InvalidRollupThroughField()

        if through_field.table != table:
            raise InvalidRollupThroughField()

        # If the `target_field_name` is provided in the kwargs when creating or
        # updating a field, then we want to find the field by its name.
        if target_field_name is not None:
            try:
                target_field_id = through_field.link_row_table.field_set.get(
                    name=target_field_name
                ).id
            except Field.DoesNotExist:
                raise InvalidRollupTargetField()
        try:
            target_field = FieldHandler().get_field(target_field_id)
        except FieldDoesNotExist:
            raise InvalidRollupTargetField()

        if target_field.table != through_field.link_row_table:
            raise InvalidRollupTargetField()

        values["through_field_id"] = through_field.id
        values["target_field_id"] = target_field.id

    def field_dependency_deleted(
        self,
        field: RollupField,
        deleted_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        if field.through_field_id == deleted_field.id:
            field.through_field_id = None
        return super().field_dependency_deleted(
            field,
            deleted_field,
            update_collector,
            field_cache,
            via_path_to_starting_table,
        )

    def import_serialized(
        self,
        table: "Table",
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        deferred_fk_update_collector: DeferredForeignKeyUpdater,
    ) -> "Field":
        serialized_copy = serialized_values.copy()
        # We have to temporarily remove the `through_field_id` and `target_field_id`,
        # because it can be that they haven't been created yet, which prevents us
        # from finding it in the mapping.
        original_through_field_id = serialized_copy.pop("through_field_id")
        original_target_field_id = serialized_copy.pop("target_field_id")
        field = super().import_serialized(
            table,
            serialized_copy,
            import_export_config,
            id_mapping,
            deferred_fk_update_collector,
        )
        deferred_fk_update_collector.add_deferred_fk_to_update(
            field, "through_field_id", original_through_field_id, "database_fields"
        )
        deferred_fk_update_collector.add_deferred_fk_to_update(
            field, "target_field_id", original_target_field_id, "database_fields"
        )
        return field

    def get_field_depdendencies_before_import_serialized(
        self,
        serialized_field: Dict[str, Any],
        serialized_fields_map: Dict[int, Dict[str, Any]],
        primary_table_fields_map: Dict[int, int],
    ) -> Optional[Set[Tuple[Union[int, str], Union[int, str]]]]:
        through_field_id = serialized_field.get("through_field_id", None)
        if through_field_id is None or through_field_id not in serialized_fields_map:
            return None  # broken reference

        via_field = serialized_fields_map[through_field_id]
        via_field_name = via_field["name"]
        target_field_id = serialized_field.get("target_field_id", None)

        # it means we're targeting a field that already exists before the import
        # (i.e. duplicating a table/field)
        if target_field_id is None or target_field_id not in serialized_fields_map:
            return None

        target_field = serialized_fields_map[target_field_id]
        target_field_name = target_field["name"]
        return {(target_field_name, via_field_name)}

    def enhance_field_queryset(
        self, queryset: QuerySet[Field], field: Field
    ) -> QuerySet[Field]:
        return queryset.select_related("through_field", "target_field")

    def should_update_search_data(
        self, old_field: LinkRowField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_through_field_id = new_field_attrs.get(
            "through_field_id", old_field.through_field_id
        )
        new_target_field_id = new_field_attrs.get(
            "target_field_id", old_field.target_field_id
        )
        new_rollup_function = new_field_attrs.get(
            "rollup_function", old_field.rollup_function
        )
        return (
            old_field.through_field_id != new_through_field_id
            or old_field.target_field_id != new_target_field_id
            or old_field.rollup_function != new_rollup_function
        )


class LookupFieldType(FormulaFieldType):
    type = "lookup"
    model_class = LookupField
    api_exceptions_map = {
        **FormulaFieldType.api_exceptions_map,
        InvalidLookupThroughField: ERROR_INVALID_LOOKUP_THROUGH_FIELD,
        InvalidLookupTargetField: ERROR_INVALID_LOOKUP_TARGET_FIELD,
    }
    can_get_unique_values = False
    allowed_fields = BASEROW_FORMULA_TYPE_ALLOWED_FIELDS + [
        "through_field_id",
        "through_field_name",
        "target_field_id",
        "target_field_name",
    ]
    request_serializer_field_names = (
        BASEROW_FORMULA_TYPE_REQUEST_SERIALIZER_FIELD_NAMES
        + [
            "through_field_id",
            "through_field_name",
            "target_field_id",
            "target_field_name",
            "formula_type",
        ]
    )
    serializer_field_names = BASEROW_FORMULA_TYPE_SERIALIZER_FIELD_NAMES + [
        "through_field_id",
        "through_field_name",
        "target_field_id",
        "target_field_name",
        "formula_type",
    ]
    request_serializer_field_overrides = {
        "through_field_name": serializers.CharField(
            required=False,
            allow_blank=True,
            allow_null=True,
            source="through_field.name",
            help_text="The name of the link row field to lookup values for.",
        ),
        "through_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="through_field.id",
            help_text="The id of the link row field to lookup values for. Will override"
            " the `through_field_name` parameter if both are provided, however only "
            "one is required.",
        ),
        "target_field_name": serializers.CharField(
            required=False,
            allow_blank=True,
            allow_null=True,
            source="target_field.name",
            help_text="The name of the field in the table linked to by the "
            "through_field to lookup.",
        ),
        "target_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            source="target_field.id",
            help_text="The id of the field in the table linked to by the "
            "through_field to lookup. Will override the `target_field_id` "
            "parameter if both are provided, however only one is required.",
        ),
        "nullable": serializers.BooleanField(required=False, read_only=True),
        "error": serializers.CharField(required=False, read_only=True),
    }

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        self._validate_through_and_target_field_values(
            table,
            allowed_field_values,
        )

    def get_fields_needing_periodic_update(self) -> Optional[QuerySet]:
        return None

    def before_update(self, from_field, to_field_values, user, kwargs):
        if isinstance(from_field, LookupField):
            through_field_id = (
                from_field.through_field.id
                if from_field.through_field is not None
                else None
            )
            target_field_id = (
                from_field.target_field.id
                if from_field.target_field is not None
                else None
            )
            self._validate_through_and_target_field_values(
                from_field.table,
                to_field_values,
                through_field_id,
                target_field_id,
            )
        else:
            self._validate_through_and_target_field_values(
                from_field.table,
                to_field_values,
            )

    def _validate_through_and_target_field_values(
        self,
        table,
        values,
        default_through_field_id=None,
        default_target_field_id=None,
    ):
        through_field_id = values.get("through_field_id", default_through_field_id)
        target_field_id = values.get("target_field_id", default_target_field_id)
        through_field_name = values.get("through_field_name", None)
        target_field_name = values.get("target_field_name", None)

        through_queryset = LinkRowField.objects.filter(table_id=table.id)
        if through_field_id is not None:
            through_queryset = through_queryset.filter(id=through_field_id)
        elif through_field_name is not None:
            through_queryset = through_queryset.filter(name=through_field_name)
        else:
            raise InvalidLookupThroughField(
                f"Either a through_field_id or through_field_name must be provided."
            )

        try:
            through_field = through_queryset.get()
        except LinkRowField.DoesNotExist:
            raise InvalidLookupThroughField()

        values["through_field_id"] = through_field.id
        values["through_field_name"] = through_field.name

        target_queryset = Field.objects.filter(table_id=through_field.link_row_table_id)
        if target_field_id is not None:
            target_queryset = target_queryset.filter(id=target_field_id)
        elif target_field_name is not None:
            target_queryset = target_queryset.filter(name=target_field_name)
        else:
            raise InvalidLookupTargetField(
                f"Either a target_field_id or target_field_name must be provided."
            )

        try:
            target_field = target_queryset.get()
        except Field.DoesNotExist:
            raise InvalidLookupTargetField()

        values["target_field_id"] = target_field.id
        values["target_field_name"] = target_field.name

    def field_dependency_updated(
        self,
        field: LookupField,
        updated_field: Field,
        updated_old_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        # The updated field can be the through field or the target field, and we're only
        # interested if the name or the field type changed.
        if updated_field.id == field.through_field_id:
            if updated_field.name != field.through_field_name:
                field.through_field_name = updated_field.name
                field.save(recalculate=False)
        elif updated_field.id == field.target_field_id:
            if updated_field.name != field.target_field_name:
                field.target_field_name = updated_field.name
                field.save(recalculate=False)

        super().field_dependency_updated(
            field,
            updated_field,
            updated_old_field,
            update_collector,
            field_cache,
            via_path_to_starting_table,
        )

    def field_dependency_deleted(
        self,
        field: LookupField,
        deleted_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        # Either the through field or the target field has been deleted
        if deleted_field.id == field.through_field_id:
            field.through_field_id = None
            field.target_field_id = None
            field.save(recalculate=False)
        elif deleted_field.id == field.target_field_id:
            field.target_field_id = None
            field.save(recalculate=False)

        super().field_dependency_deleted(
            field,
            deleted_field,
            update_collector,
            field_cache,
            via_path_to_starting_table,
        )

    def field_dependency_created(
        self,
        field: LookupField,
        created_field: Field,
        update_collector: FieldUpdateCollector,
        field_cache: "FieldCache",
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        # If the created field can fix this broken field because it was pointing to
        # the same name, then we can do so.
        if (
            field.error
            and field.through_field_id is None
            and isinstance(created_field, LinkRowField)
            and created_field.name == field.through_field_name
        ):
            field.through_field_id = created_field.id
            field.target_field = Field.objects.filter(
                table_id=created_field.link_row_table_id, name=field.target_field_name
            ).first()
            field.save(recalculate=False)
        elif (
            field.error
            and field.target_field_id is None
            and created_field.name == field.target_field_name
            and created_field.table_id == field.through_field.specific.link_row_table_id
        ):
            field.target_field_id = created_field.id
            field.save(recalculate=False)

        super().field_dependency_created(
            field,
            created_field,
            update_collector,
            field_cache,
            via_path_to_starting_table,
        )

    def import_serialized(
        self,
        table: "Table",
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        deferred_fk_update_collector: DeferredForeignKeyUpdater,
    ) -> "Field":
        serialized_copy = serialized_values.copy()
        # We have to temporarily set the `through_field_id` and `target_field_id`,
        # because it can be that they haven't been created yet, which prevents us
        # from finding it in the mapping.
        original_through_field_id = serialized_copy.pop("through_field_id")
        original_target_field_id = serialized_copy.pop("target_field_id")
        field = super().import_serialized(
            table,
            serialized_copy,
            import_export_config,
            id_mapping,
            deferred_fk_update_collector,
        )
        deferred_fk_update_collector.add_deferred_fk_to_update(
            field, "through_field_id", original_through_field_id, "database_fields"
        )
        deferred_fk_update_collector.add_deferred_fk_to_update(
            field, "target_field_id", original_target_field_id, "database_fields"
        )
        return field

    def get_field_depdendencies_before_import_serialized(
        self,
        serialized_field: Dict[str, Any],
        serialized_fields_map: Dict[int, Dict[str, Any]],
        primary_table_fields_map: Dict[int, int],
    ) -> Optional[Set[Tuple[Union[int, str], Union[int, str]]]]:
        through_field_id = serialized_field.get("through_field_id", None)
        if through_field_id is None or through_field_id not in serialized_fields_map:
            return None  # broken reference

        via_field = serialized_fields_map[through_field_id]
        via_field_name = via_field["name"]
        target_field_id = serialized_field.get("target_field_id", None)

        # it means we're targeting a field that already exists before the import
        # (i.e. duplicating a table/field)
        if target_field_id is None or target_field_id not in serialized_fields_map:
            return None

        target_field_id = serialized_field["target_field_id"]
        target_field = serialized_fields_map[target_field_id]
        target_field_name = target_field["name"]

        return {(target_field_name, via_field_name)}

    def enhance_field_queryset(
        self, queryset: QuerySet[Field], field: Field
    ) -> QuerySet[Field]:
        return queryset.select_related("through_field", "target_field")

    def should_update_search_data(
        self, old_field: LinkRowField, new_field_attrs: Dict[str, Any]
    ) -> bool:
        new_through_field_id = new_field_attrs.get(
            "through_field_id", old_field.through_field_id
        )
        new_target_field_id = new_field_attrs.get(
            "target_field_id", old_field.target_field_id
        )
        return (
            old_field.through_field_id != new_through_field_id
            or old_field.target_field_id != new_target_field_id
        )


class MultipleCollaboratorsFieldType(
    CollationSortMixin,
    ManyToManyFieldTypeSerializeToInputValueMixin,
    ManyToManyGroupByMixin,
    FieldType,
):
    type = "multiple_collaborators"
    model_class = MultipleCollaboratorsField
    can_get_unique_values = False
    allowed_fields = ["notify_user_when_added"]
    request_serializer_field_names = ["notify_user_when_added"]
    request_serializer_field_overrides = {
        "notify_user_when_added": serializers.BooleanField(required=False),
    }
    serializer_field_names = [
        "available_collaborators",
        *request_serializer_field_names,
    ]
    serializer_field_overrides = {
        "available_collaborators": AvailableCollaboratorsSerializer(),
        **request_serializer_field_overrides,
    }
    is_many_to_many_field = True
    _can_group_by = True

    def can_represent_collaborators(self, field):
        return True

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.pop("required", False)
        field_serializer = CollaboratorSerializer(
            **{
                "required": required,
                "allow_null": False,
                **kwargs,
            }
        )
        return serializers.ListSerializer(
            child=field_serializer, required=required, **kwargs
        )

    def get_search_expression(
        self, field: MultipleCollaboratorsField, queryset: QuerySet
    ) -> Expression:
        return Subquery(
            queryset.filter(pk=OuterRef("pk")).values(
                aggregated=StringAgg(
                    f"{field.db_column}__first_name",
                    " ",
                    output_field=models.TextField(),
                )
            )[:1]
        )

    def get_internal_value_from_db(
        self, row: "GeneratedTableModel", field_name: str
    ) -> List[int]:
        related_objects = getattr(row, field_name)
        return [related_object.id for related_object in related_objects.all()]

    def get_response_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)
        return CollaboratorSerializer(
            **{
                "required": required,
                "allow_null": False,
                "many": True,
                **kwargs,
            }
        )

    def serialize_to_input_value(self, field: Field, value: any) -> any:
        return [{"id": u.id, "name": u.first_name} for u in value.all()]

    def prepare_value_for_db(self, instance, value):
        if not isinstance(
            value,
            (
                list,
                set,
                tuple,
            ),
        ) or not all([isinstance(v, (dict, int)) for v in value]):
            raise ValidationError(
                f"The value for field {instance.id} is not a valid list of dictionaries",
                code="invalid",
            )

        if value is None:
            return []

        if len(value) == 0:
            return []

        user_ids = [v["id"] if isinstance(v, dict) else v for v in value]
        workspace = instance.table.database.workspace
        workspace_users_count = WorkspaceUser.objects.filter(
            user_id__in=user_ids, workspace_id=workspace.id
        ).count()

        if workspace_users_count != len(user_ids):
            raise AllProvidedCollaboratorIdsMustBeValidUsers(user_ids)

        return user_ids

    def prepare_value_for_db_in_bulk(
        self, instance, values_by_row, continue_on_error=False
    ):
        # {user_id -> row_indexes}
        rows_by_value = defaultdict(list)
        all_user_ids = set()
        for row_index, values in values_by_row.items():
            user_ids = [v["id"] if isinstance(v, dict) else v for v in values]
            for user_id in user_ids:
                rows_by_value[user_id].append(row_index)
            all_user_ids = all_user_ids.union(user_ids)
            values_by_row[row_index] = user_ids

        workspace = instance.table.database.workspace

        selected_ids = WorkspaceUser.objects.filter(
            user_id__in=all_user_ids, workspace_id=workspace.id
        ).values_list("user_id", flat=True)

        if len(selected_ids) != len(all_user_ids):
            invalid_ids = sorted(list(all_user_ids - set(selected_ids)))
            if continue_on_error:
                for invalid_id in invalid_ids:
                    for row_index in rows_by_value[invalid_id]:
                        values_by_row[
                            row_index
                        ] = AllProvidedCollaboratorIdsMustBeValidUsers(invalid_id)
            else:
                # or fail fast
                raise AllProvidedCollaboratorIdsMustBeValidUsers(invalid_ids)

        return values_by_row

    def get_serializer_help_text(self, instance):
        return (
            "This field accepts a list of objects representing the chosen "
            "collaborators through the object's `id` property. The id is Baserow "
            "user id. The response objects also contains the collaborator name "
            "directly along with its id."
        )

    def get_export_value(self, value, field_object, rich_value=False):
        if hasattr(value, "all"):
            value = value.all()

        if not value:
            return [] if rich_value else ""

        result = [f"{user.first_name} <{user.email}>" for user in value]
        if rich_value:
            return result
        else:
            return list_to_comma_separated_string(result)

    def get_human_readable_value(self, value, field_object):
        export_value = self.get_export_value(value, field_object, rich_value=True)
        if len(export_value) == 0:
            return ""
        return ", ".join(export_value)

    def serialize_metadata_for_row_history(
        self,
        field: Field,
        row: "GeneratedTableModel",
        metadata: Optional[SerializedRowHistoryFieldMetadata] = None,
    ) -> SerializedRowHistoryFieldMetadata:
        base = super().serialize_metadata_for_row_history(field, row, metadata)

        already_serialized_collaborators = {}
        if metadata and metadata.get("collaborators"):
            already_serialized_collaborators = metadata["collaborators"]

        new_collaborators = getattr(row, field.db_column).all()
        new_serialized_collaborators = {
            collaborator.id: {
                "id": collaborator.id,
                "name": collaborator.first_name,
            }
            for collaborator in new_collaborators
        }

        return {
            **base,
            "collaborators": {
                **already_serialized_collaborators,
                **new_serialized_collaborators,
            },
        }

    def are_row_values_equal(self, value1: any, value2: any) -> bool:
        v1 = set([v["id"] if isinstance(v, dict) else v for v in value1])
        v2 = set([v["id"] if isinstance(v, dict) else v for v in value2])
        return v1 == v2

    def get_model_field(self, instance, **kwargs):
        return None

    def after_model_generation(self, instance, model, field_name):
        user_meta = type(
            "Meta",
            (AbstractUser.Meta,),
            {
                "managed": False,
                "app_label": model._meta.app_label,
                "db_tablespace": model._meta.db_tablespace,
                "db_table": get_user_model().objects.model._meta.db_table,
                "apps": model._meta.apps,
            },
        )
        user_model = type(
            str(f"MultipleCollaboratorsField{instance.id}User"),
            (AbstractUser,),
            {
                # We need to override the `workspaces` and `user_permissions` here
                # because they're normally many to many relationships with the
                # `Workspace` and `Permission` model. This is something that we do not
                # need and we don't want to create reversed relationships for generated
                # model.
                "groups": None,
                "user_permissions": None,
                "Meta": user_meta,
                "__module__": model.__module__,
                "_generated_table_model": True,
            },
        )

        related_name = f"reversed_field_{instance.id}"
        shared_kwargs = {
            "null": True,
            "blank": True,
            "db_table": instance.through_table_name,
            "db_constraint": False,
        }
        additional_filters = {
            "id__in": WorkspaceUser.objects.filter(
                workspace_id=instance.table.database.workspace_id
            ).values_list("user_id", flat=True)
        }

        MultipleSelectManyToManyField(
            to=user_model,
            related_name=related_name,
            additional_filters=additional_filters,
            **shared_kwargs,
        ).contribute_to_class(model, field_name)
        MultipleSelectManyToManyField(
            to=model,
            related_name=field_name,
            reversed_additional_filters=additional_filters,
            **shared_kwargs,
        ).contribute_to_class(user_model, related_name)

    def enhance_queryset(self, queryset, field, name, **kwargs):
        return queryset.prefetch_related(name)

    def get_export_serialized_value(self, row, field_name, cache, files_zip, storage):
        cache_entry = f"{field_name}_relations_export"
        if cache_entry not in cache:
            # In order to prevent a lot of lookup queries in the through table, we want
            # to fetch all the relations and add it to a temporary in memory cache
            # containing a mapping of the row ids to collaborator emails.
            cache[cache_entry] = defaultdict(list)
            through_model = row._meta.get_field(field_name).remote_field.through
            through_model_fields = through_model._meta.get_fields()
            current_field_name = through_model_fields[1].name
            relation_field_name = through_model_fields[2].name
            users_relation = through_model.objects.select_related(relation_field_name)
            for relation in users_relation:
                cache[cache_entry][
                    getattr(relation, f"{current_field_name}_id")
                ].append(getattr(relation, relation_field_name).email)
        return cache[cache_entry][row.id]

    def set_import_serialized_value(
        self, row, field_name, value, id_mapping, cache, files_zip, storage
    ):
        workspace_id = id_mapping["import_workspace_id"]
        cache_entry = f"{field_name}_relations_import"
        if cache_entry not in cache:
            # In order to prevent a lot of lookup queries in the through table, we want
            # to fetch all the relations and add it to a temporary in memory cache
            # containing a mapping of the row ids to collaborator emails.
            cache[cache_entry] = defaultdict(list)

            workspaceusers_from_workspace = WorkspaceUser.objects.filter(
                workspace_id=workspace_id
            ).select_related("user")

            for workspaceuser in workspaceusers_from_workspace:
                cache[cache_entry][workspaceuser.user.email] = workspaceuser.user.id

        through_model = row._meta.get_field(field_name).remote_field.through
        through_model_fields = through_model._meta.get_fields()
        current_field_name = through_model_fields[1].name
        relation_field_name = through_model_fields[2].name

        through_objects = []
        for email in value:
            user_id = cache[cache_entry].get(email, None)
            if user_id is not None:
                through_objects.append(
                    through_model(
                        **{
                            f"{current_field_name}_id": row.id,
                            f"{relation_field_name}_id": cache[cache_entry].get(
                                email, None
                            ),
                        }
                    )
                )

        return through_objects

    def random_value(self, instance, fake, cache):
        """
        Selects a random sublist out of the possible collaborators.
        """

        cache_entry_name = f"field_{instance.id}_collaborators"

        if cache_entry_name not in cache:
            table = Table.objects.get(id=instance.table_id)
            workspaceusers_ids = WorkspaceUser.objects.filter(
                workspace=table.database.workspace_id
            ).values_list("user_id", flat=True)
            cache[cache_entry_name] = list(workspaceusers_ids)

        collaborators = cache[cache_entry_name]

        if not collaborators:
            return None

        return sample(collaborators, randint(1, len(collaborators)))  # nosec

    def random_to_input_value(self, field, value):
        return [{"id": user_id} for user_id in value]

    def get_order(
        self, field, field_name, order_direction, sort_type, table_model=None
    ):
        """
        If the user wants to sort the results they expect them to be ordered
        alphabetically based on the user's name and not in the id which is
        stored in the table. This method generates a Case expression which maps
        the id to the correct position.
        """

        sort_column_name = f"{field_name}_agg_sort"
        query = Coalesce(
            StringAgg(
                self.get_sortable_column_expression(field, field_name, sort_type),
                "",
                output_field=models.TextField(),
            ),
            Value(""),
            output_field=models.TextField(),
        )
        annotation = {sort_column_name: query}

        order = collate_expression(F(sort_column_name))

        if order_direction == "DESC":
            order = order.desc(nulls_first=True)
        else:
            order = order.asc(nulls_first=True)

        return OptionallyAnnotatedOrderBy(annotation=annotation, order=order)

    def get_group_by_aggregated_order(self, related_field):
        # The multiple select field must be ordered by the id of the entry in the
        # through table because it respects the insertion order. It respects the
        # `MultipleSelectManyToManyDescriptor::related_manager_cls::_apply_rel_ordering`
        return ("id",) + super().get_group_by_aggregated_order(related_field)

    def get_value_for_filter(self, row: "GeneratedTableModel", field) -> any:
        related_objects = getattr(row, field.db_column)
        values = [related_object.first_name for related_object in related_objects.all()]
        value = list_to_comma_separated_string(values)
        return value

    def get_sortable_column_expression(
        self,
        field: Field,
        field_name: str,
        sort_type: str,
    ) -> Expression | F:
        return F(f"{field_name}__first_name")

    def to_baserow_formula_type(self, field: Field):
        return BaserowFormulaMultipleCollaboratorsType(nullable=True)

    def from_baserow_formula_type(self, formula_type) -> Field:
        return self.model_class()

    def get_formula_reference_to_model_field(
        self, model_field, db_column, already_in_subquery
    ):
        if already_in_subquery:
            return Coalesce(
                JSONBAgg(
                    get_collaborator_extractor(db_column, model_field),
                    filter=Q(**{f"{db_column}__isnull": False}),
                    order=f"{db_column}__id",
                ),
                Value([], output_field=JSONField()),
            )
        else:
            return Coalesce(
                wrap_in_subquery(
                    JSONBAgg(
                        get_collaborator_extractor(db_column, model_field),
                        order=f"{db_column}__id",
                    ),
                    db_column,
                    model_field.model,
                ),
                Value([], output_field=JSONField()),
            )


class UUIDFieldType(ReadOnlyFieldType):
    """
    The UUIDFieldType is ReadOnly, but does not extend the `ReadOnlyFieldType` class
    because the value should persistent on export/import and field duplication.
    """

    type = "uuid"
    model_class = UUIDField
    can_be_in_form_view = False
    keep_data_on_duplication = True
    _can_have_db_index = True

    def get_serializer_field(self, instance, **kwargs):
        return serializers.UUIDField(required=False, **kwargs)

    def get_serializer_help_text(self, instance):
        return "Contains a unique and persistent UUID for every row."

    def get_model_field(self, instance, **kwargs):
        return models.UUIDField(
            default=uuid.uuid4,
            null=True,
            db_index=instance.db_index,
            **kwargs,
        )

    def after_create(self, field, model, user, connection, before, field_kwargs):
        model.objects.all().update(**{f"{field.db_column}": RandomUUID()})

    def after_update(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        user,
        connection,
        altered_column,
        before,
        to_field_kwargs,
    ):
        if not isinstance(from_field, self.model_class):
            to_model.objects.all().update(**{f"{to_field.db_column}": RandomUUID()})

    def prepare_value_for_db(self, instance: Field, value):
        raise ValidationError(
            f"Field of type {self.type} is read only and should not be set manually."
        )

    def get_export_serialized_value(
        self,
        row: "GeneratedTableModel",
        field_name: str,
        cache: Dict[str, Any],
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> None:
        return str(
            super().get_export_serialized_value(
                row, field_name, cache, files_zip, storage
            )
        )

    def get_export_value(self, value, field_object, rich_value=False) -> str:
        return "" if value is None else str(value)

    def contains_query(self, *args):
        return contains_filter(*args, validate=False)

    def to_baserow_formula_expression(self, field):
        # Cast the uuid to text, to make it compatible with all the text related
        # functions.
        totext = formula_function_registry.get("totext")
        return totext(super().to_baserow_formula_expression(field))

    def to_baserow_formula_type(self, field) -> BaserowFormulaType:
        return BaserowFormulaTextType(nullable=True, unwrap_cast_to_text=False)

    def from_baserow_formula_type(
        self, formula_type: BaserowFormulaTextType
    ) -> UUIDField:
        return UUIDField()

    def get_formula_reference_to_model_field(
        self, model_field, db_column, already_in_subquery
    ):
        """
        Casts the uuid to text to make it compatible with all the text related
        functions.
        """

        return ExpressionWrapper(
            Cast(F(db_column), output_field=models.TextField()),
            output_field=models.TextField(),
        )


class AutonumberFieldType(ReadOnlyFieldType):
    """
    Autonumber fields automatically generate unique and incremented numbers for
    each record. Autonumbers can be helpful when you need a unique identifier
    for each record or when using a formula in the primary field
    """

    type = "autonumber"
    model_class = AutonumberField
    can_be_in_form_view = False
    keep_data_on_duplication = True
    request_serializer_field_names = ["view_id"]
    request_serializer_field_overrides = {
        "view_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The id of the view to use for the initial ordering.",
        )
    }
    _can_have_db_index = True

    def get_serializer_field(self, instance, **kwargs):
        return serializers.IntegerField(required=False, **kwargs)

    def get_serializer_help_text(self, instance):
        return (
            "Contains a unique and persistent incremental integer number for every row."
        )

    def get_model_field(self, instance, **kwargs):
        return IntegerFieldWithSequence(null=True, db_index=instance.db_index, **kwargs)

    def after_rows_imported(
        self,
        field: FormulaField,
        update_collector: Optional[FieldUpdateCollector] = None,
        field_cache: Optional["FieldCache"] = None,
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        # Create the sequence so that rows can start being automatically numbered.
        self.create_field_sequence(field, field.table.get_model(), connection)

    def _extract_view_from_field_kwargs(self, user, field_kwargs):
        view_id = field_kwargs.get("view_id", None)
        if view_id is not None:
            field_kwargs["view"] = ViewHandler().get_view_as_user(user, view_id)

    def before_create(
        self, table, primary, allowed_field_values, order, user, field_kwargs
    ):
        self._extract_view_from_field_kwargs(user, field_kwargs)

    def after_create(self, field, model, user, connection, before, field_kwargs):
        self.create_field_sequence(field, model, connection)
        self.update_rows_with_field_sequence(field, field_kwargs.get("view", None))

    def before_update(self, from_field, to_field_values, user, field_kwargs):
        self._extract_view_from_field_kwargs(user, field_kwargs)

    def before_schema_change(
        self,
        from_field,
        to_field,
        to_model,
        from_model,
        from_model_field,
        to_model_field,
        user,
        to_field_kwargs,
    ):
        from_autonumber = isinstance(from_field, self.model_class)
        to_autonumber = isinstance(to_field, self.model_class)

        if from_autonumber and not to_autonumber:
            self.drop_field_sequence(from_field, to_model, connection)

    def after_update(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        user,
        connection,
        altered_column,
        before,
        to_field_kwargs,
    ):
        if isinstance(to_field, self.model_class) and not isinstance(
            from_field, self.model_class
        ):
            self.create_field_sequence(to_field, to_model, connection)
            self.update_rows_with_field_sequence(
                to_field, to_field_kwargs.get("view", None)
            )

    def prepare_value_for_db(self, instance: Field, value):
        raise ValidationError(
            f"Field of type {self.type} is read only and should not be set manually."
        )

    def contains_query(self, *args):
        return contains_filter(*args)

    def update_rows_with_field_sequence(
        self, field: Field, view: Optional["View"] = None
    ):
        """
        Renumber the row values for the given field, according to the view's
        filters and sorting. If the view has filters, the rows matching the
        filters will have lower row numbers than the rows that don't match the
        filters. If the view has sorting, the rows will be numbered accordingly.
        If the table have trashed rows, they will receive the highest row
        numbers. If no view is provided, then all the rows in the table are
        renumbered according to the default ordering of the table (order, id).

        :param field: The field to initialize the values for.
        :param view: The view to initialize the values according to.
        """

        not_trashed_first = Case(When(Q(trashed=False), then=Value(0)), default=1).asc()
        order_bys = (not_trashed_first, "order", "id")

        if view is not None:
            queryset = ViewHandler().get_queryset(None, view).values("id")

            filters = queryset.query.where
            filtered_first = Case(When(filters, then=Value(0)), default=1).asc()

            # The last two order bys are the default order bys of the table
            if custom_order_bys := queryset.query.order_by[:-2]:
                order_bys = (*custom_order_bys, *order_bys)

            order_bys = (filtered_first, *order_bys)

        table_model = field.table.get_model()
        qs = table_model.objects_and_trash.annotate(
            row_nr=Window(expression=RowNumber(), order_by=order_bys),
        ).values("id", "row_nr")
        sql, params = qs.query.get_compiler(connection=connection).as_sql()

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                WITH ordered AS ({sql})
                UPDATE {table_model._meta.db_table} AS t
                SET {field.db_column} = ordered.row_nr
                FROM ordered
                WHERE t.id = ordered.id;
                """,  # nosec B608
                params,
            )

    def create_field_sequence(
        self, field: Field, model: "GeneratedTableModel", connection
    ):
        """
        Create a sequence and set the default value to the next value in the
        sequence for the given field. The sequence is needed to make sure that
        the autonumber field is unique and incremented.

        :param field: The field to create the sequence for.
        :param model: The model of the table that the field belongs to.
        :param connection: The connection to use for the queries.
        """

        db_table = model._meta.db_table
        db_column = field.db_column

        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SEQUENCE IF NOT EXISTS {db_column}_seq;")
            cursor.execute(
                f"ALTER TABLE {db_table} ALTER COLUMN {db_column} SET DEFAULT nextval('{db_column}_seq');"
            )
            cursor.execute(
                f"ALTER SEQUENCE {db_column}_seq OWNED BY {db_table}.{db_column};"
            )
            # Set the sequence to the count of rows in the table, only if there
            # is at least one row.
            cursor.execute(
                f"""
                WITH count AS (SELECT COUNT(*) FROM {db_table})
                SELECT setval('{db_column}_seq', count) FROM count WHERE count > 0;
                """  # nosec B608
            )

    def drop_field_sequence(
        self, field: Field, model: "GeneratedTableModel", connection
    ):
        """
        Drop the sequence for the given autonumber field.

        :param field: The field to drop the sequence for.
        :param model: The model of the table that the field belongs to.
        :param connection: The connection to use for the queries.
        """

        db_table = model._meta.db_table
        db_column = field.db_column

        with connection.cursor() as cursor:
            cursor.execute(
                f"ALTER TABLE {db_table} ALTER COLUMN {db_column} DROP DEFAULT;"
            )
            cursor.execute(f"DROP SEQUENCE IF EXISTS {db_column}_seq;")

    def to_baserow_formula_type(self, field: NumberField) -> BaserowFormulaType:
        return BaserowFormulaNumberType(
            number_decimal_places=0, requires_refresh_after_insert=True
        )

    def from_baserow_formula_type(
        self, formula_type: BaserowFormulaNumberType
    ) -> NumberField:
        return NumberField(number_decimal_places=0, number_negative=False)


class PasswordFieldType(FieldType):
    """
    Password fields are write only and store the hash of the provided value. This
    can be used for authentication.
    """

    type = "password"
    model_class = PasswordField
    can_be_in_form_view = True
    keep_data_on_duplication = True
    _can_order_by_types = []
    _can_be_primary_field = False
    can_get_unique_values = False
    allowed_fields = ["allow_endpoint_authentication"]
    serializer_field_names = ["allow_endpoint_authentication"]

    def get_serializer_field(self, instance, **kwargs):
        # If a string value is provided, the password will be set. If `None` is
        # provided, the password will be cleared. If `True` is provided, it will be
        # ignored because this is what will be in the response and we can't do
        # anything with that value.
        return PasswordSerializer(
            **{
                "required": False,
                "allow_null": True,
                "allow_blank": True,
                **kwargs,
            }
        )

    def get_response_serializer_field(self, instance, **kwargs):
        # For the response it must be a BooleanField because we never want to expose
        # the password, this will make it respond with `True` if set, and `null` is not.
        return serializers.BooleanField(required=False, **kwargs)

    def get_serializer_help_text(self, instance):
        return (
            "Allows setting a write only password value. Providing a string will set "
            "the password, `null` will unset it, `true` will be ignored. The response "
            "will respond with `true` is a password is set, but will never expose the "
            "password itself."
        )

    def get_model_field(self, instance, **kwargs):
        return models.CharField(null=True, max_length=128)

    def get_human_readable_value(self, value: Any, field_object: "FieldObject") -> str:
        # We don't want to expose the hash of the password, so we just show `True` or
        # `False` as string depending on whether the value is set.
        return bool(value)

    def get_export_value(
        self, value: Any, field_object: "FieldObject", rich_value: bool = False
    ) -> Any:
        # We don't want to expose the hash of the password, so we just show `True` or
        # `False` as string depending on whether the value is set.
        return bool(value)

    def prepare_value_for_row_history(self, value):
        # We don't want to expose the hash of the password, so we just show `True` or
        # `False` as string depending on whether the value is set.
        return bool(value)

    def is_searchable(self, field: Field) -> bool:
        # passwords shouldn't be searchable!
        return False
