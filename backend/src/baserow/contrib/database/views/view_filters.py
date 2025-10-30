import datetime as datetime_module
import zoneinfo
from collections import defaultdict
from datetime import date, datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, NamedTuple, Optional, Tuple, Union

from django.core.exceptions import ValidationError
from django.db.models import DateField, DateTimeField, IntegerField, Q, Value
from django.db.models.expressions import F, Func
from django.db.models.fields.json import JSONField
from django.db.models.functions import Extract, Length, Mod, TruncDate

from dateutil import parser
from dateutil.relativedelta import MO, relativedelta

from baserow.contrib.database.fields.field_filters import (
    FILTER_TYPE_AND,
    AnnotatedQ,
    FilterBuilder,
    OptionallyAnnotatedQ,
    filename_contains_filter,
    map_ids_from_csv_string,
    parse_ids_from_csv_string,
)
from baserow.contrib.database.fields.field_types import (
    AutonumberFieldType,
    BooleanFieldType,
    CreatedByFieldType,
    CreatedOnFieldType,
    DateFieldType,
    DurationFieldType,
    EmailFieldType,
    FileFieldType,
    FormulaFieldType,
    LastModifiedByFieldType,
    LastModifiedFieldType,
    LinkRowFieldType,
    LongTextFieldType,
    MultipleCollaboratorsFieldType,
    MultipleSelectFieldType,
    NumberFieldType,
    PasswordFieldType,
    PhoneNumberFieldType,
    RatingFieldType,
    SingleSelectFieldType,
    TextFieldType,
    URLFieldType,
    UUIDFieldType,
)
from baserow.contrib.database.fields.filter_support.base import (
    get_jsonb_has_any_in_value_filter_expr,
)
from baserow.contrib.database.fields.models import Field, LinkRowField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.formula import (
    BaserowFormulaBooleanType,
    BaserowFormulaCharType,
    BaserowFormulaDateType,
    BaserowFormulaNumberType,
    BaserowFormulaTextType,
)
from baserow.contrib.database.formula.types.formula_types import (
    BaserowFormulaDateIntervalType,
    BaserowFormulaDurationType,
    BaserowFormulaMultipleCollaboratorsType,
    BaserowFormulaMultipleSelectType,
    BaserowFormulaSingleFileType,
    BaserowFormulaSingleSelectType,
    BaserowFormulaURLType,
)
from baserow.core.datetime import get_timezones
from baserow.core.models import WorkspaceUser

from .registries import ViewFilterType

DATE_FILTER_EMPTY_VALUE = ""
DATE_FILTER_TIMEZONE_SEPARATOR = "?"


class NotViewFilterTypeMixin:
    def default_filter_on_exception(self):
        return Q()

    def get_filter(self, *args, **kwargs):
        return ~super().get_filter(*args, **kwargs)


class EqualViewFilterType(ViewFilterType):
    """
    The equal filter compared the field value to the filter value. It must be the same.
    It is compatible with models.CharField, models.TextField, models.BooleanField ('1'
    is True), models.IntegerField and models.DecimalField. It will probably also be
    compatible with other fields, but these have been tested.
    """

    type = "equal"
    compatible_field_types = [
        BooleanFieldType.type,
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        EmailFieldType.type,
        PhoneNumberFieldType.type,
        UUIDFieldType.type,
        AutonumberFieldType.type,
        DurationFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaTextType.type,
            BaserowFormulaCharType.type,
            BaserowFormulaNumberType.type,
            BaserowFormulaDurationType.type,
            BaserowFormulaURLType.type,
        ),
    ]

    def get_filter(self, field_name, value, model_field, field):
        # Check if the model_field accepts the value.
        field_type = field_type_registry.get_by_model(field)
        try:
            value = field_type.parse_filter_value(field, model_field, value.strip())
        except ValueError:
            return self.default_filter_on_exception()

        # If an empty value has been provided we do not want to filter at all.
        if value is None:
            return Q()

        return Q(**{field_name: value})


class NotEqualViewFilterType(NotViewFilterTypeMixin, EqualViewFilterType):
    type = "not_equal"


class FilenameContainsViewFilterType(ViewFilterType):
    """
    The filename contains filter checks if the filename's visible name contains the
    provided filter value. It is only compatible with fields.JSONField which contain
    a list of File JSON Objects.
    """

    type = "filename_contains"
    compatible_field_types = [
        FileFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaSingleFileType.type)
        ),
    ]

    def get_filter(self, *args):
        return filename_contains_filter(*args)


class HasFileTypeViewFilterType(ViewFilterType):
    """
    The file field type column contains an array of objects with details related to
    the uploaded user files. Every object always contains the property `is_image`
    that indicates if the user file is an image. Using the Django contains lookup,
    we can check if there is at least one object where the `is_image` is True. If the
    filter value is `image`, there must at least be one object where the `is_image`
    is true. If the filter value is `document` there must at least be one object
    where the `is_image` is false. If an unsupported filter value is provided, we don't
    want to filter on anything.
    """

    type = "has_file_type"
    compatible_field_types = [
        FileFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaSingleFileType.type)
        ),
    ]

    def get_filter(self, field_name, value, model_field, field):
        value = value.strip()
        is_image = value == "image"
        is_document = value == "document"

        if is_document or is_image:
            return Q(
                **{
                    f"{field_name}__contains": Value(
                        [{"is_image": is_image}], JSONField()
                    )
                }
            )
        else:
            return Q()


class FilesLowerThanViewFilterType(ViewFilterType):
    """
    The files lower than filter checks if the number of file objects present
    in a column of type file is smaller than a given value.

    It is only compatible with fields.JSONField which contain a list of File
    JSON Objects.
    """

    type = "files_lower_than"
    compatible_field_types = [FileFieldType.type]

    def get_filter(self, field_name, value, model_field, field):
        value = value.strip()

        # If a non numeric value has been provided we do not want to filter.
        if not value.lstrip("-").isdigit():
            return Q()

        # Annotate the query with the length of the JSON array, using the
        # proper PostgreSQL function
        # See: https://www.postgresql.org/docs/current/functions-json.html
        annotation_query = Func(
            F(field_name),
            function="jsonb_array_length",
            output_field=IntegerField(),
        )
        return AnnotatedQ(
            annotation={f"{field_name}_length": annotation_query},
            q={f"{field_name}_length__lt": int(value)},
        )


class ContainsViewFilterType(ViewFilterType):
    """
    The contains filter checks if the field value contains the provided filter value.
    It is compatible with models.CharField and models.TextField.
    """

    type = "contains"
    compatible_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        EmailFieldType.type,
        PhoneNumberFieldType.type,
        DateFieldType.type,
        LastModifiedFieldType.type,
        CreatedOnFieldType.type,
        SingleSelectFieldType.type,
        MultipleSelectFieldType.type,
        NumberFieldType.type,
        AutonumberFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaTextType.type,
            BaserowFormulaCharType.type,
            BaserowFormulaNumberType.type,
            BaserowFormulaDateType.type,
            BaserowFormulaURLType.type,
            BaserowFormulaSingleSelectType.type,
            BaserowFormulaMultipleSelectType.type,
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        try:
            field_type = field_type_registry.get_by_model(field)
            return field_type.contains_query(field_name, value, model_field, field)
        except Exception:
            return self.default_filter_on_exception()


class ContainsWordViewFilterType(ViewFilterType):
    """
    The contains word filter checks if the field value contains the provided filter
    value as a whole word, and not as a substring. It is compatible with
    models.CharField and models.TextField.
    """

    type = "contains_word"
    compatible_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        EmailFieldType.type,
        SingleSelectFieldType.type,
        MultipleSelectFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaTextType.type,
            BaserowFormulaCharType.type,
            BaserowFormulaURLType.type,
            BaserowFormulaSingleSelectType.type,
            BaserowFormulaMultipleSelectType.type,
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        # Check if the model_field accepts the value.
        try:
            field_type = field_type_registry.get_by_model(field)
            return field_type.contains_word_query(field_name, value, model_field, field)
        except Exception:
            return self.default_filter_on_exception()


class DoesntContainWordViewFilterType(
    NotViewFilterTypeMixin, ContainsWordViewFilterType
):
    type = "doesnt_contain_word"


class ContainsNotViewFilterType(NotViewFilterTypeMixin, ContainsViewFilterType):
    type = "contains_not"


class LengthIsLowerThanViewFilterType(ViewFilterType):
    """
    The length is lower than filter checks if the fields character
    length is less than x
    """

    type = "length_is_lower_than"
    compatible_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        EmailFieldType.type,
        PhoneNumberFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaURLType.type,
        ),
    ]

    def get_filter(self, field_name, value, model_field, field):
        if value == 0:
            return Q()

        try:
            return AnnotatedQ(
                annotation={f"{field_name}_len": Length(field_name)},
                q={f"{field_name}_len__lt": int(value)},
            )
        except ValueError:
            return self.default_filter_on_exception()


class IsEvenAndWholeViewFilterType(ViewFilterType):
    """
    The is even and whole filter checks if the field value is an even number
    AND if it's a whole number.
    It only works if a numeric number is provided. It is at compatible with
    models.DecimalField.
    """

    type = "is_even_and_whole"
    compatible_field_types = [
        NumberFieldType.type,
        AutonumberFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
        ),
    ]

    def get_filter(self, field_name, value, model_field, field):
        return AnnotatedQ(
            annotation={f"{field_name}_is_even_and_whole": Mod(F(f"{field_name}"), 2)},
            q={f"{field_name}_is_even_and_whole": 0},
        )


class NumericComparisonViewFilterType(ViewFilterType):
    """
    Base filter type for basic numeric comparisons. It defines common logic for
    'lower than', 'lower than or equal', 'higher than' and 'higher than or equal'
    view filter types.
    """

    operator = None
    compatible_field_types = [
        NumberFieldType.type,
        RatingFieldType.type,
        AutonumberFieldType.type,
        DurationFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type, BaserowFormulaDurationType.type
        ),
    ]

    def get_filter(self, field_name, value, model_field, field):
        field_type = field_type_registry.get_by_model(field)
        try:
            filter_value = field_type.parse_filter_value(
                field, model_field, value.strip()
            )
        except ValueError:
            return self.default_filter_on_exception()

        if filter_value is None:
            return Q()

        return Q(**{f"{field_name}__{self.operator}": filter_value})


class LowerThanViewFilterType(NumericComparisonViewFilterType):
    """
    The lower than filter checks if the field value is lower than the filter value.
    It only works if a numeric number is provided.
    """

    type = "lower_than"
    operator = "lt"


class LowerThanOrEqualViewFilterType(NumericComparisonViewFilterType):
    """
    The lower than or equal filter checks if the field value is lower or if it
    equals to the filter value.
    It only works if a numeric number is provided.
    """

    type = "lower_than_or_equal"
    operator = "lte"


class HigherThanViewFilterType(NumericComparisonViewFilterType):
    """
    The higher than filter checks if the field value is higher than the filter value.
    It only works if a numeric number is provided.
    """

    type = "higher_than"
    operator = "gt"


class HigherThanOrEqualViewFilterType(NumericComparisonViewFilterType):
    """
    The higher than or equal filter checks if the field value is higher than or
    if it equals to the filter value.
    It only works if a numeric number is provided.
    """

    type = "higher_than_or_equal"
    operator = "gte"


class TimezoneAwareDateViewFilterType(ViewFilterType):
    @property
    def time_sensitive(self) -> bool:
        return True

    compatible_field_types = [
        DateFieldType.type,
        LastModifiedFieldType.type,
        CreatedOnFieldType.type,
        FormulaFieldType.compatible_with_formula_types(BaserowFormulaDateType.type),
    ]

    def is_empty_filter(self, filter_value: str) -> bool:
        return filter_value == DATE_FILTER_EMPTY_VALUE

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        """
        Parses the provided filter value and returns a date or datetime object
        that can be used to compare with the field value.

        :param filter_value: The value that has been provided by the user.
        :param timezone: The timezone that should be used to convert the date to
            an aware date.
        :raises ValueError: If the provided value is not valid.
        :raise OverflowError: If the provided value is out of range.
        :raise ParserError: If the provided value is not a valid date to parse.
        :return: a date or an aware datetime that should be used to compare with
            the field value.
        """

        try:
            return parser.isoparser().parse_isodate(filter_value)
        except ValueError:
            datetime_value = parser.isoparse(filter_value)
            if datetime_value.tzinfo is None:
                return datetime_value.replace(tzinfo=timezone)
            return datetime_value.astimezone(timezone)

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[datetime, date], now: datetime
    ) -> Dict:
        """
        Returns a dictionary that can be used to create a Q object.

        :param field_name: The name of the field that should be used in the
            query.
        :param aware_filter_date: The date that should be used to compare with
            the field value.
        :param now: The current aware datetime that can be used to compare with
            the field value.
        """

        raise NotImplementedError()

    def _split_optional_timezone_and_filter_value(
        self, field, filter_value, separator
    ) -> Tuple[Optional[str], Optional[str]]:
        if separator in filter_value:  # specific timezone provided by the filter
            try:
                timezone_value, filter_value = filter_value.split(separator)
                return timezone_value, filter_value
            except ValueError:
                # the separator was included multiple times, we don't know what to do
                return None, None
        elif filter_value in get_timezones():
            # only a timezone value was provided with no filter value
            return filter_value, None
        else:
            # default to the fields timezone if any and the provided value
            return field.date_force_timezone, filter_value

    def split_timezone_and_filter_value(
        self, field, filter_value, separator=DATE_FILTER_TIMEZONE_SEPARATOR
    ) -> Tuple[zoneinfo.ZoneInfo, str]:
        """
        Splits the timezone and the value from the provided value. If the value
        does not contain a timezone then the default timezone will be used.

        :param field: The field that is being filtered.
        :param filter_value: The value that has been provided by the user.
        :param separator: The separator that is used to split the timezone and
            the value.
        :return: A tuple containing the timezone and the filter_value string.
        """

        (
            user_timezone_str,
            parsed_filter_value,
        ) = self._split_optional_timezone_and_filter_value(
            field, filter_value, separator
        )

        python_timezone = (
            zoneinfo.ZoneInfo(user_timezone_str)
            if user_timezone_str is not None
            else datetime_module.timezone.utc
        )

        validated_filter_value = (
            parsed_filter_value
            if parsed_filter_value is not None
            else DATE_FILTER_EMPTY_VALUE
        )

        return python_timezone, validated_filter_value

    def get_filter(
        self, field_name: str, value: str, model_field, field: Field
    ) -> Union[Q, AnnotatedQ]:
        """
        Returns a Q object that can be used to filter the provided field.

        :param field_name: The name of the field that should be used in the
            query.
        :param value: The value that has been provided by the user.
        :param model_field: The Django model field of the database table that is
            being filtered.
        :param field: The Baserow field instance containing the metadata related
            to the field.
        :return: A Q object that can be used to filter the provided field.
        """

        try:
            timezone, filter_value = self.split_timezone_and_filter_value(
                field, value.strip()
            )
            if self.is_empty_filter(filter_value):
                return Q()

            filter_date = self.get_filter_date(filter_value, timezone)
        except (
            OverflowError,
            ValueError,
            parser.ParserError,
            zoneinfo.ZoneInfoNotFoundError,
        ):
            return Q(pk__in=[])

        annotation = {}
        query_field_name = field_name

        if isinstance(model_field, DateTimeField):
            if not isinstance(filter_date, datetime):
                query_field_name = f"{field_name}_tzdate"
                annotation[query_field_name] = TruncDate(field_name, tzinfo=timezone)

        elif isinstance(model_field, DateField) and isinstance(filter_date, datetime):
            filter_date = filter_date.date()

        query_dict = {
            f"{field_name}__isnull": False,  # makes `NotViewFilterTypeMixin` work with timezones
            **self.get_filter_query_dict(
                query_field_name, filter_date, datetime.now(timezone)
            ),
        }
        return AnnotatedQ(annotation=annotation, q=query_dict)


class DateEqualViewFilterType(TimezoneAwareDateViewFilterType):
    """
    The date filter parses the provided value as date and checks if the field value is
    the same date. It only works if a valid ISO date is provided as value and it is
    only compatible with models.DateField and models.DateTimeField.
    """

    type = "date_equal"

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {field_name: aware_filter_date}


class DateBeforeViewFilterType(TimezoneAwareDateViewFilterType):
    """
    The date before filter parses the provided filter value as date and checks if the
    field value is before this date (lower than).
    It is an extension of the BaseDateFieldLookupFilter
    """

    type = "date_before"

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict[str, Any]:
        return {f"{field_name}__lt": aware_filter_date}


class DateBeforeOrEqualViewFilterType(TimezoneAwareDateViewFilterType):
    """
    This filter parses the provided value as date and checks if the field value
    is before or equal.
    """

    type = "date_before_or_equal"

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict[str, Any]:
        return {f"{field_name}__lte": aware_filter_date}


class DateAfterViewFilterType(TimezoneAwareDateViewFilterType):
    """
    The after date filter parses the provided filter value as date and checks if
    the field value is after this date (greater than).
    It is an extension of the BaseDateFieldLookupFilter
    """

    type = "date_after"

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict[str, Any]:
        return {f"{field_name}__gt": aware_filter_date}


class DateAfterOrEqualViewFilterType(TimezoneAwareDateViewFilterType):
    """
    This filter parses the provided value as date and checks if the field value
    is after or equal.
    """

    type = "date_after_or_equal"

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict[str, Any]:
        return {f"{field_name}__gte": aware_filter_date}


class DateEqualsDayOfMonthViewFilterType(TimezoneAwareDateViewFilterType):
    """
    The day of month filter checks if the field number value
    matches the date's day of the month value.
    """

    type = "date_equals_day_of_month"

    def get_filter(
        self, field_name: str, value: str, model_field, field: Field
    ) -> Union[Q, AnnotatedQ]:
        try:
            timezone, filter_value = self.split_timezone_and_filter_value(
                field, value.strip()
            )
            if self.is_empty_filter(filter_value):
                return Q()

            day_of_month = int(filter_value)
            if day_of_month < 1 or day_of_month > 31:
                raise ValueError

        except (ValueError, zoneinfo.ZoneInfoNotFoundError):
            return Q(pk__in=[])

        if field.date_include_time:  # filter on a datetime field
            annotated_field_name = f"{field_name}_day_of_month_tz"
            return AnnotatedQ(
                annotation={annotated_field_name: Extract(field_name, "day", timezone)},
                q={annotated_field_name: day_of_month},
            )
        else:  # filter on a date field
            return Q(**{f"{field_name}__day": day_of_month})


class EmptyFilterValueMixin:
    def is_empty_filter(self, filter_value: str) -> bool:
        return False


class DateEqualsTodayViewFilterType(
    EmptyFilterValueMixin, TimezoneAwareDateViewFilterType
):
    """
    The today filter checks if the field value matches with today's date.
    """

    type = "date_equals_today"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        return datetime.now(tz=timezone).date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {field_name: aware_filter_date}


class DateBeforeTodayViewFilterType(
    EmptyFilterValueMixin, TimezoneAwareDateViewFilterType
):
    """
    The before today filter checks if the field value is before today's date.
    """

    type = "date_before_today"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        return (datetime.now(tz=timezone) - timedelta(days=1)).date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {f"{field_name}__lte": aware_filter_date}


class DateAfterTodayViewFilterType(
    EmptyFilterValueMixin, TimezoneAwareDateViewFilterType
):
    """
    The after today filter checks if the field value is after today's date.
    """

    type = "date_after_today"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        return (datetime.now(tz=timezone) + timedelta(days=1)).date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {f"{field_name}__gte": aware_filter_date}


class DateEqualsCurrentWeekViewFilterType(
    EmptyFilterValueMixin, TimezoneAwareDateViewFilterType
):
    """
    The current week filter works as a subset of today filter and checks if the
    field value falls into current week.
    """

    type = "date_equals_week"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        return datetime.now(tz=timezone).date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        week_of_year = aware_filter_date.isocalendar().week
        return {
            f"{field_name}__week": week_of_year,
            f"{field_name}__year": aware_filter_date.year,
        }


class DateEqualsCurrentMonthViewFilterType(
    EmptyFilterValueMixin, TimezoneAwareDateViewFilterType
):
    """
    The current month filter works as a subset of today filter and checks if the
    field value falls into current month.
    """

    type = "date_equals_month"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        return datetime.now(tz=timezone).date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {
            f"{field_name}__month": aware_filter_date.month,
            f"{field_name}__year": aware_filter_date.year,
        }


class DateEqualsCurrentYearViewFilterType(
    EmptyFilterValueMixin, TimezoneAwareDateViewFilterType
):
    """
    The current month filter works as a subset of today filter and checks if the
    field value falls into current year.
    """

    type = "date_equals_year"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        return datetime.now(tz=timezone).date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {f"{field_name}__year": aware_filter_date.year}


def get_is_within_filter_query_dict(
    field_name: str, aware_filter_date: Union[date, datetime], now: datetime
) -> Dict:
    """
    The utility function checks if the field value is between today's date and
    the date specified in the filter value and returns the query dict.
    It ensure that the filter works correctly even if the filter date is before
    today's date.
    """

    op1, op2 = ("lte", "gte") if aware_filter_date >= now.date() else ("gte", "lte")

    return {
        f"{field_name}__{op1}": aware_filter_date,
        f"{field_name}__{op2}": now.date(),
    }


class DateIsWithinXDaysViewFilterType(TimezoneAwareDateViewFilterType):
    """
    Is within X days filter checks if the field value is between today's date
    and the number of days specified in the filter.

    The value of the filter is expected to be a string like "Europe/Rome?1". It
    uses character ? as separator between the timezone and the number of days.
    """

    type = "date_within_days"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        """
        Zero days means today, one day means today and tomorrow, and so on.
        """

        number_of_days = int(filter_value)

        filter_date = datetime.now(tz=timezone) + relativedelta(days=number_of_days)
        return filter_date.date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return get_is_within_filter_query_dict(field_name, aware_filter_date, now)


class DateIsWithinXWeeksViewFilterType(TimezoneAwareDateViewFilterType):
    """
    Is within X weeks filter checks if the field value is between today's date
    and the number of weeks specified in the filter.

    The value of the filter is expected to be a string like "Europe/Rome?1". It
    uses character ? as separator between the timezone and the number of days.
    """

    type = "date_within_weeks"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        """
        Since zero weeks can be confusing, we raise an error if the number of
        weeks is 0. One week means today + 1 week inclusive, and so on.
        """

        number_of_weeks = int(filter_value)
        if number_of_weeks == 0:
            raise ValueError("Number of weeks cannot be 0")

        filter_date = datetime.now(tz=timezone) + relativedelta(weeks=number_of_weeks)
        return filter_date.date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return get_is_within_filter_query_dict(field_name, aware_filter_date, now)


class DateIsWithinXMonthsViewFilterType(TimezoneAwareDateViewFilterType):
    """
    Is within X months filter checks if the field value is between today's date
    and the number of months specified in the filter.

    The value of the filter is expected to be a string like "Europe/Rome?1". It
    uses character ? as separator between the timezone and the number of days.
    """

    type = "date_within_months"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        """
        Since zero months can be confusing, we raise an error if the number of
        months is 0. One month means today + 1 month inclusive, and so on. E.g.
        if today is 2023-01-31, within 1 month means within 2020-02-28
        inclusive.
        """

        number_of_months = int(filter_value)
        if number_of_months == 0:
            raise ValueError("Number of months cannot be 0")

        filter_date = datetime.now(tz=timezone) + relativedelta(months=number_of_months)
        return filter_date.date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return get_is_within_filter_query_dict(field_name, aware_filter_date, now)


class DateEqualsDaysAgoViewFilterType(TimezoneAwareDateViewFilterType):
    """
    The "number of days ago" filter checks if the field value matches with today's
    date minus the specified number of days.

    The value of the filter is expected to be a string like "Europe/Rome?1".
    It uses character ? as separator between the timezone and the number of days.
    """

    type = "date_equals_days_ago"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        filter_date = datetime.now(tz=timezone) - timedelta(days=int(filter_value))
        return filter_date.date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {field_name: aware_filter_date}


class DateEqualsMonthsAgoViewFilterType(TimezoneAwareDateViewFilterType):
    """
    The "number of months ago" filter checks if the field value's month is within
    the specified "months ago" based on the current date.

    The value of the filter is expected to be a string like "Europe/Rome?1".
    It uses character ? as separator between the timezone and the number of months.
    """

    type = "date_equals_months_ago"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        filter_date = datetime.now(tz=timezone) + relativedelta(
            months=-int(filter_value)
        )
        return filter_date.date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {
            f"{field_name}__year": aware_filter_date.year,
            f"{field_name}__month": aware_filter_date.month,
        }


class DateEqualsYearsAgoViewFilterType(TimezoneAwareDateViewFilterType):
    """
    The "is years ago" filter checks if the field value's year is within
    the specified "years ago" based on the current date.

    The value of the filter is expected to be a string like "Europe/Rome?1".
    It uses character ? as separator between the timezone and the number of months.
    """

    type = "date_equals_years_ago"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        filter_date = datetime.now(tz=timezone) + relativedelta(
            years=-int(filter_value)
        )
        return filter_date.date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {f"{field_name}__year": aware_filter_date.year}


class DateNotEqualViewFilterType(NotViewFilterTypeMixin, DateEqualViewFilterType):
    type = "date_not_equal"


class DateAfterDaysAgoViewFilterType(TimezoneAwareDateViewFilterType):
    """
    The "is after days ago" filter checks if the field value falls within the specified
    number of past days, including the current date. The filter only includes records
    with field values on or after the date calculated based on the given number of days
    ago from the current date.

    The filter takes the timezone into consideration when performing the date
    calculations.
    """

    type = "date_after_days_ago"

    def is_empty_filter(self, filter_value: str) -> bool:
        return super().is_empty_filter(filter_value) or filter_value == "0"

    def get_filter_date(
        self, filter_value: str, timezone: datetime_module.tzinfo
    ) -> Union[datetime, date]:
        # Calculate and return the date `filter_value` days ago in the given timezone
        filter_date = datetime.now(tz=timezone) - timedelta(days=int(filter_value))
        return filter_date.date()

    def get_filter_query_dict(
        self, field_name: str, aware_filter_date: Union[date, datetime], now: datetime
    ) -> Dict:
        return {
            f"{field_name}__gte": aware_filter_date,
        }


class SingleSelectEqualViewFilterType(ViewFilterType):
    """
    The single select equal filter accepts a select option id as filter value. This
    filter is only compatible with the SingleSelectFieldType field type.
    """

    type = "single_select_equal"
    compatible_field_types = [
        SingleSelectFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaSingleSelectType.type
        ),
    ]

    @staticmethod
    def _get_filter(field_name, value: int, model_field, field):
        return Q(**{f"{field_name}_id": value})

    @staticmethod
    def _get_formula_filter(field_name, value: int, model_field, field):
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, [value], query_path="$.id"
        )

    filter_functions = MappingProxyType(
        {
            SingleSelectFieldType.type: _get_filter,
            FormulaFieldType.type: _get_formula_filter,
        }
    )

    def get_filter(self, field_name, value, model_field, field):
        value = value.strip()

        try:
            int(value)
        except ValueError:
            return Q()

        field_type = field_type_registry.get_by_model(field)
        effective_field_type = field_type.get_compatible_filter_field_type(field)
        filter_function = self.filter_functions[effective_field_type.type]
        return filter_function(field_name, value, model_field, field)

    def set_import_serialized_value(self, value, id_mapping):
        mapping = id_mapping["database_field_select_options"]
        try:
            return map_ids_from_csv_string(value, mapping)[0]
        except IndexError:
            return ""


class SingleSelectNotEqualViewFilterType(
    NotViewFilterTypeMixin, SingleSelectEqualViewFilterType
):
    type = "single_select_not_equal"


class SingleSelectIsAnyOfViewFilterType(ViewFilterType):
    """
    This filter accepts a string with a list of option ids separated with a comma as
    value input. The filter will show rows that have single select option value in
    the filter's value list.
    """

    type = "single_select_is_any_of"
    compatible_field_types = [
        SingleSelectFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaSingleSelectType.type
        ),
    ]

    def _get_filter(field_name, option_ids, model_field, field):
        return Q(**{f"{field_name}_id__in": option_ids})

    def _get_formula_filter(field_name, option_ids, model_field, field):
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, option_ids, query_path="$.id"
        )

    filter_functions = MappingProxyType(
        {
            SingleSelectFieldType.type: _get_filter,
            FormulaFieldType.type: _get_formula_filter,
        }
    )

    def get_filter(self, field_name, value: str, model_field, field):
        value = value.strip()
        if not value:
            return Q()

        if not (option_ids := parse_ids_from_csv_string(value)):
            return self.default_filter_on_exception()

        field_type = field_type_registry.get_by_model(field)
        effective_field_type = field_type.get_compatible_filter_field_type(field)
        filter_function = self.filter_functions[effective_field_type.type]
        return filter_function(field_name, option_ids, model_field, field)

    def set_import_serialized_value(self, value: str | None, id_mapping: dict) -> str:
        select_option_map = id_mapping["database_field_select_options"]
        new_values = map_ids_from_csv_string(value or "", select_option_map)
        return ",".join(new_values)


class SingleSelectIsNoneOfViewFilterType(
    NotViewFilterTypeMixin, SingleSelectIsAnyOfViewFilterType
):
    """
    This filter accepts a string with a list of option ids separated with a comma as
    value input. The filter will show rows that have single select option value not
    present in the filter's value list.
    """

    type = "single_select_is_none_of"


class BooleanViewFilterType(ViewFilterType):
    """
    The boolean filter tries to convert the provided filter value to a boolean and
    compares that to the field value. If for example '1' is provided then only field
    value with True are going to be matched. This filter is compatible with
    models.BooleanField.
    """

    type = "boolean"
    compatible_field_types = [
        BooleanFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaBooleanType.type,
        ),
    ]

    def get_filter(self, field_name, value, model_field, field):
        if value == "":  # consider an empty string as False
            return Q(**{field_name: False})

        try:
            filter_value = BooleanFieldType().parse_filter_value(
                field, model_field, value
            )
        except ValueError:
            return self.default_filter_on_exception()

        return Q(**{field_name: filter_value})


class ManyToManyHasBaseViewFilter(ViewFilterType):
    """
    The many to many base filter accepts a relationship ID. It filters the queryset so
    that only rows that have a relationship with the provided ID will remain. So if for
    example '10' is provided, then only rows where the many to many field has a
    relationship to a foreignkey with the ID of 10.
    """

    def _get_filter(self, field_name, value, model_field, field):
        remote_field = model_field.remote_field
        remote_model = remote_field.model
        filter_dict = {"id__in": value} if isinstance(value, list) else {"id": value}
        return Q(
            id__in=remote_model.objects.filter(**filter_dict).values(
                f"{remote_field.related_name}__id"
            )
        )

    def _get_formula_filter(field_name, value, model_field, field):
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, [value], query_path="$.id"
        )

    filter_functions = MappingProxyType({FormulaFieldType.type: _get_formula_filter})

    def get_filter(self, field_name, value: str, model_field, field):
        value = value.strip()
        if not value:
            return Q()

        try:
            val = int(value.strip())
        except (ValueError, TypeError):
            return Q()

        field_type = field_type_registry.get_by_model(field)
        filter_function = self.filter_functions.get(field_type.type, self._get_filter)
        return filter_function(field_name, val, model_field, field)


class LinkRowHasViewFilterType(ManyToManyHasBaseViewFilter):
    """
    The link row has filter accepts the row ID of the related table as value.
    """

    type = "link_row_has"
    compatible_field_types = [LinkRowFieldType.type]

    def get_filter(self, field_name, value, model_field, field):
        if not (option_ids := parse_ids_from_csv_string(value)):
            return Q()

        field_type = field_type_registry.get_by_model(field)
        filter_function = self.filter_functions.get(field_type.type, self._get_filter)
        return filter_function(field_name, option_ids, model_field, field)

    def get_preload_values(self, view_filter):
        """
        This method preloads the display name of the related value. This prevents a
        lot of API requests if the view has a lot of `link_row_has` filters. It will
        also make sure that the display name is visible for read only previews.
        """

        name = None
        related_row_id = None

        try:
            related_row_id = int(view_filter.value)
        except ValueError:
            pass

        if related_row_id:
            related_table_id = LinkRowField.objects.filter(
                id=view_filter.field_id
            ).values("link_row_table_id")[:1]
            try:
                primary_field = Field.objects.select_related("table").get(
                    primary=True, table_id=related_table_id
                )

                model = primary_field.table.get_model(
                    field_ids=[], fields=[primary_field], add_dependencies=False
                )

                name = str(model.objects.get(pk=related_row_id))
            except (Field.DoesNotExist, model.DoesNotExist):
                pass

        return {"display_name": name}


class LinkRowHasNotViewFilterType(LinkRowHasViewFilterType):
    """
    The link row has filter accepts the row ID of the related table as value. It
    filters the queryset so that only rows that don't have a relationship with the
    provided row ID will remain. So if for example '10' is provided, then only rows
    where the link row field does not have a relationship with the row '10' persists.
    """

    type = "link_row_has_not"

    def default_filter_on_exception(self):
        return Q()

    def get_filter(self, field_name, value, model_field, field):
        try:
            val = int(value.strip())
            return ~Q(**{f"field_{field.id}": val})
        except ValueError:
            return Q()


class LinkRowContainsViewFilterType(ViewFilterType):
    type = "link_row_contains"
    compatible_field_types = [LinkRowFieldType.type]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        related_primary_field = field.link_row_table_primary_field.specific
        if related_primary_field is None:
            return Q()
        related_primary_field_type = field_type_registry.get_by_model(
            related_primary_field
        )
        model = field.table.get_model()
        related_primary_field_model_field = related_primary_field_type.get_model_field(
            related_primary_field
        )

        try:
            subquery = (
                FilterBuilder(FILTER_TYPE_AND)
                .filter(
                    related_primary_field_type.contains_query(
                        f"{field_name}__{related_primary_field.db_column}",
                        value,
                        related_primary_field_model_field,
                        related_primary_field,
                    )
                )
                .apply_to_queryset(model.objects)
                .values_list("id", flat=True)
            )
        except (ValueError, ValidationError):
            subquery = []

        return Q(
            **{f"id__in": subquery},
        )


class LinkRowNotContainsViewFilterType(
    NotViewFilterTypeMixin, LinkRowContainsViewFilterType
):
    type = "link_row_not_contains"

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        if value == "":
            return Q()

        return super().get_filter(field_name, value, model_field, field)


class MultipleSelectHasViewFilterType(ManyToManyHasBaseViewFilter):
    """
    The multiple select has filter accepts the ID of the select_option to filter for
    and filters the rows where the multiple select field has the provided select_option.
    """

    type = "multiple_select_has"
    compatible_field_types = [
        MultipleSelectFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaMultipleSelectType.type
        ),
    ]

    @staticmethod
    def _get_filter(field_name, option_ids, model_field, field):
        remote_field = model_field.remote_field
        remote_model = remote_field.model
        return Q(
            id__in=remote_model.objects.filter(id__in=option_ids).values(
                f"{remote_field.related_name}__id"
            )
        )

    @staticmethod
    def _get_formula_filter(field_name, option_ids, model_field, field):
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, option_ids, query_path="$[*].id"
        )

    filter_functions = MappingProxyType(
        {
            MultipleSelectFieldType.type: _get_filter,
            FormulaFieldType.type: _get_formula_filter,
        }
    )

    def get_filter(self, field_name, value: str, model_field, field):
        value = value.strip()
        if not value:
            return Q()

        if not (option_ids := parse_ids_from_csv_string(value)):
            return self.default_filter_on_exception()

        field_type = field_type_registry.get_by_model(field)
        effective_field_type = field_type.get_compatible_filter_field_type(field)
        filter_function = self.filter_functions[effective_field_type.type]
        return filter_function(field_name, option_ids, model_field, field)

    def set_import_serialized_value(self, value: str | None, id_mapping: dict) -> str:
        select_option_map = id_mapping["database_field_select_options"]
        new_values = map_ids_from_csv_string(value or "", select_option_map)
        return ",".join(new_values)


class MultipleSelectHasNotViewFilterType(
    NotViewFilterTypeMixin, MultipleSelectHasViewFilterType
):
    """
    The multiple select has filter accepts the ID of the select_option to filter for
    and filters the rows where the multiple select field does not have the provided
    select_option.
    """

    type = "multiple_select_has_not"


class MultipleCollaboratorsHasViewFilterType(ManyToManyHasBaseViewFilter):
    """
    The multiple collaborators has filter accepts the ID of the user to filter for
    and filters the rows where the multiple collaborators field has the provided user.
    """

    type = "multiple_collaborators_has"
    compatible_field_types = [
        MultipleCollaboratorsFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            MultipleCollaboratorsFieldType.type
        ),
    ]

    COLLABORATORS_KEY = f"available_collaborators"

    def get_export_serialized_value(self, value, id_mapping):
        if value is None:
            value = ""
        if self.COLLABORATORS_KEY not in id_mapping:
            workspace_id = id_mapping.get("workspace_id", None)
            if workspace_id is None:
                return value

            id_mapping[self.COLLABORATORS_KEY] = defaultdict(list)

            workspaceusers_from_workspace = WorkspaceUser.objects.filter(
                workspace_id=workspace_id
            ).select_related("user")

            for workspaceuser in workspaceusers_from_workspace:
                id_mapping[self.COLLABORATORS_KEY][
                    str(workspaceuser.user.id)
                ] = workspaceuser.user.email

        return id_mapping[self.COLLABORATORS_KEY].get(value, "")

    def set_import_serialized_value(self, value, id_mapping):
        workspace_id = id_mapping.get("workspace_id", None)
        if workspace_id is None:
            return ""

        if self.COLLABORATORS_KEY not in id_mapping:
            id_mapping[self.COLLABORATORS_KEY] = defaultdict(list)
            workspaceusers_from_workspace = WorkspaceUser.objects.filter(
                workspace_id=workspace_id
            ).select_related("user")
            for workspaceuser in workspaceusers_from_workspace:
                id_mapping[self.COLLABORATORS_KEY][str(workspaceuser.user.email)] = str(
                    workspaceuser.user.id
                )
        return id_mapping[self.COLLABORATORS_KEY].get(value, "")


class MultipleCollaboratorsHasNotViewFilterType(
    NotViewFilterTypeMixin, MultipleCollaboratorsHasViewFilterType
):
    """
    The multiple collaborators has not filter accepts the ID of the user to filter for
    and filters the rows where the field does not have the provided user.
    """

    type = "multiple_collaborators_has_not"


class UserIsViewFilterType(ViewFilterType):
    """
    The user is filter accepts the ID of the user to filter for
    and filters the rows where the field has the provided user.
    """

    type = "user_is"
    compatible_field_types = [CreatedByFieldType.type, LastModifiedByFieldType.type]

    USER_KEY = f"users"

    def get_filter(self, field_name, value, model_field, field):
        if not value:
            return Q()
        value = value.strip()
        try:
            return Q(**{f"{field_name}__id": int(value)})
        except ValueError:
            return Q()

    def get_export_serialized_value(self, value, id_mapping):
        if value is None:
            value = ""
        if self.USER_KEY not in id_mapping:
            workspace_id = id_mapping.get("workspace_id", None)
            if workspace_id is None:
                return value

            id_mapping[self.USER_KEY] = defaultdict(list)

            workspaceusers_from_workspace = WorkspaceUser.objects.filter(
                workspace_id=workspace_id
            ).select_related("user")

            for workspaceuser in workspaceusers_from_workspace:
                id_mapping[self.USER_KEY][
                    str(workspaceuser.user.id)
                ] = workspaceuser.user.email

        return id_mapping[self.USER_KEY].get(value, "")

    def set_import_serialized_value(self, value, id_mapping):
        workspace_id = id_mapping.get("workspace_id", None)
        if workspace_id is None:
            return ""

        if self.USER_KEY not in id_mapping:
            id_mapping[self.USER_KEY] = defaultdict(list)
            workspaceusers_from_workspace = WorkspaceUser.objects.filter(
                workspace_id=workspace_id
            ).select_related("user")
            for workspaceuser in workspaceusers_from_workspace:
                id_mapping[self.USER_KEY][str(workspaceuser.user.email)] = str(
                    workspaceuser.user.id
                )
        return id_mapping[self.USER_KEY].get(value, "")


class UserIsNotViewFilterType(NotViewFilterTypeMixin, UserIsViewFilterType):
    """
    The user is not filter accepts the ID of the user to filter for
    and filters the rows where the field does not have the provided user.
    """

    type = "user_is_not"


class EmptyViewFilterType(ViewFilterType):
    """
    The empty filter checks if the field value is empty, this can be '', null,
    [] or anything. It is compatible with all fields
    """

    type = "empty"
    compatible_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        BooleanFieldType.type,
        DateFieldType.type,
        LastModifiedFieldType.type,
        CreatedOnFieldType.type,
        LinkRowFieldType.type,
        EmailFieldType.type,
        FileFieldType.type,
        SingleSelectFieldType.type,
        PhoneNumberFieldType.type,
        MultipleSelectFieldType.type,
        MultipleCollaboratorsFieldType.type,
        DurationFieldType.type,
        PasswordFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaTextType.type,
            BaserowFormulaCharType.type,
            BaserowFormulaNumberType.type,
            BaserowFormulaDateType.type,
            BaserowFormulaBooleanType.type,
            BaserowFormulaDateIntervalType.type,
            BaserowFormulaDurationType.type,
            BaserowFormulaURLType.type,
            BaserowFormulaSingleSelectType.type,
            BaserowFormulaMultipleSelectType.type,
            MultipleCollaboratorsFieldType.type,
            FormulaFieldType.array_of(BaserowFormulaSingleFileType.type),
            FormulaFieldType.array_of(BaserowFormulaTextType.type),
            FormulaFieldType.array_of(BaserowFormulaCharType.type),
            FormulaFieldType.array_of(BaserowFormulaURLType.type),
            FormulaFieldType.array_of(BaserowFormulaNumberType.type),
            FormulaFieldType.array_of(BaserowFormulaBooleanType.type),
            FormulaFieldType.array_of(BaserowFormulaDateType.type),
            FormulaFieldType.array_of(BaserowFormulaSingleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleCollaboratorsType.type),
            FormulaFieldType.array_of(BaserowFormulaDurationType.type),
        ),
    ]

    def get_filter(self, field_name, value, model_field, field):
        field_type = field_type_registry.get_by_model(field)
        return field_type.empty_query(field_name, model_field, field)


class NotEmptyViewFilterType(NotViewFilterTypeMixin, EmptyViewFilterType):
    type = "not_empty"


class DateFilterOperators(Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    TOMORROW = "tomorrow"
    ONE_WEEK_AGO = "one_week_ago"
    ONE_MONTH_AGO = "one_month_ago"
    ONE_YEAR_AGO = "one_year_ago"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    THIS_YEAR = "this_year"
    NEXT_WEEK = "next_week"
    NEXT_MONTH = "next_month"
    NEXT_YEAR = "next_year"
    NR_DAYS_AGO = "nr_days_ago"
    NR_WEEKS_AGO = "nr_weeks_ago"
    NR_MONTHS_AGO = "nr_months_ago"
    NR_YEARS_AGO = "nr_years_ago"
    NR_DAYS_FROM_NOW = "nr_days_from_now"
    NR_WEEKS_FROM_NOW = "nr_weeks_from_now"
    NR_MONTHS_FROM_NOW = "nr_months_from_now"
    NR_YEARS_FROM_NOW = "nr_years_from_now"
    EXACT_DATE = "exact_date"


DATE_FILTER_OPERATOR_FROM_VALUE = {
    opr.value: opr for opr in DateFilterOperators.__members__.values()
}


class DateFilterBounds(NamedTuple):
    """
    The DateFilterBounds is a named tuple that contains the lower bound (inclusive) and
    upper bound (exclusive) of the date filter. It's used to represent the range of
    dates matching a specific date filter operator.
    """

    lower_bound: date
    upper_bound: date


# It contains the mapping between the filter operator and the function that should be
# called to get the lower bound (inclusive) and upper bound (exclusive) of the filter.
# The filter_date corresponds to datetime.now(tz=timezone).date() if the filter does not
# have a specific date provided, while it automatically converts the provided string to
# a date within the range if a value is provided. Look at
# `DateMultiStepViewFilterType.get_filter_date` for more info.
DATE_FILTER_OPERATOR_BOUNDS = {
    DateFilterOperators.TODAY: lambda filter_date: DateFilterBounds(
        filter_date,
        filter_date + relativedelta(days=1),
    ),
    DateFilterOperators.YESTERDAY: lambda filter_date: DateFilterBounds(
        filter_date - relativedelta(days=1),
        filter_date,
    ),
    DateFilterOperators.TOMORROW: lambda filter_date: DateFilterBounds(
        filter_date + relativedelta(days=1),
        filter_date + relativedelta(days=2),
    ),
    DateFilterOperators.ONE_WEEK_AGO: lambda filter_date: DateFilterBounds(
        filter_date + relativedelta(weekday=MO(-2)),
        filter_date + relativedelta(weekday=MO(-1)),
    ),
    DateFilterOperators.ONE_MONTH_AGO: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1) - relativedelta(months=1),
        filter_date.replace(day=1),
    ),
    DateFilterOperators.ONE_YEAR_AGO: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1, month=1) - relativedelta(years=1),
        filter_date.replace(day=1, month=1),
    ),
    DateFilterOperators.THIS_WEEK: lambda filter_date: DateFilterBounds(
        filter_date + relativedelta(weekday=MO(-1)),
        filter_date + relativedelta(days=1, weekday=MO(+1)),
    ),
    DateFilterOperators.THIS_MONTH: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1),
        filter_date.replace(day=1) + relativedelta(months=1),
    ),
    DateFilterOperators.THIS_YEAR: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1, month=1),
        filter_date.replace(day=1, month=1) + relativedelta(years=1),
    ),
    DateFilterOperators.NEXT_WEEK: lambda filter_date: DateFilterBounds(
        filter_date + relativedelta(days=1, weekday=MO(+1)),
        filter_date + relativedelta(days=1, weekday=MO(+2)),
    ),
    DateFilterOperators.NEXT_MONTH: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1) + relativedelta(months=1),
        filter_date.replace(day=1) + relativedelta(months=2),
    ),
    DateFilterOperators.NEXT_YEAR: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1, month=1) + relativedelta(years=1),
        filter_date.replace(day=1, month=1) + relativedelta(years=2),
    ),
    DateFilterOperators.NR_DAYS_AGO: lambda filter_date: DateFilterBounds(
        filter_date,
        filter_date + relativedelta(days=1),
    ),
    DateFilterOperators.NR_WEEKS_AGO: lambda filter_date: DateFilterBounds(
        filter_date + relativedelta(weekday=MO(-1)),
        filter_date + relativedelta(days=1, weekday=MO(+1)),
    ),
    DateFilterOperators.NR_MONTHS_AGO: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1), filter_date.replace(day=1) + relativedelta(months=1)
    ),
    DateFilterOperators.NR_YEARS_AGO: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1, month=1),
        filter_date.replace(day=1, month=1) + relativedelta(years=1),
    ),
    DateFilterOperators.NR_DAYS_FROM_NOW: lambda filter_date: DateFilterBounds(
        filter_date,
        filter_date + relativedelta(days=1),
    ),
    DateFilterOperators.NR_WEEKS_FROM_NOW: lambda filter_date: DateFilterBounds(
        filter_date + relativedelta(weekday=MO(-1)),
        filter_date + relativedelta(days=1, weekday=MO(+1)),
    ),
    DateFilterOperators.NR_MONTHS_FROM_NOW: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1), filter_date.replace(day=1) + relativedelta(months=1)
    ),
    DateFilterOperators.NR_YEARS_FROM_NOW: lambda filter_date: DateFilterBounds(
        filter_date.replace(day=1, month=1),
        filter_date.replace(day=1, month=1) + relativedelta(years=1),
    ),
    DateFilterOperators.EXACT_DATE: lambda filter_date: DateFilterBounds(
        filter_date,
        filter_date + relativedelta(days=1),
    ),
}

DATE_FILTER_OPERATOR_DELTA_MAP = {
    DateFilterOperators.NR_DAYS_AGO.value: lambda v: -timedelta(days=int(v or 0)),
    DateFilterOperators.NR_DAYS_FROM_NOW.value: lambda v: timedelta(days=int(v or 0)),
    DateFilterOperators.NR_WEEKS_AGO.value: lambda v: relativedelta(weeks=-int(v or 0)),
    DateFilterOperators.NR_WEEKS_FROM_NOW.value: lambda v: relativedelta(
        weeks=int(v or 0)
    ),
    DateFilterOperators.NR_MONTHS_AGO.value: lambda v: relativedelta(
        months=-int(v or 0)
    ),
    DateFilterOperators.NR_MONTHS_FROM_NOW.value: lambda v: relativedelta(
        months=int(v or 0)
    ),
    DateFilterOperators.NR_YEARS_AGO.value: lambda v: relativedelta(years=-int(v or 0)),
    DateFilterOperators.NR_YEARS_FROM_NOW.value: lambda v: relativedelta(
        years=int(v or 0)
    ),
}


class BaseDateMultiStepViewFilterType(ViewFilterType):
    incompatible_operators = []

    @property
    def time_sensitive(self) -> bool:
        return True

    def get_filter_date(
        self,
        operator: str,
        filter_value: str,
        timezone: datetime_module.tzinfo,
    ) -> date:
        """
        Returns the date that should be used to filter the field based on the provided
        operator and filter value. The date returned is always in the provided timezone
        and within the range of the provided operator, but not necessarily the beginning
        of the period.

        :param operator: The operator that should be used to filter the field.
        :param filter_value: The value that has been provided by the user.
        :param timezone: The timezone that should be used to filter the field.
        :return: The date that should be used to filter the field.
        """

        if operator == DateFilterOperators.EXACT_DATE.value:
            try:
                return parser.isoparser().parse_isodate(filter_value)
            except ValueError:
                datetime_value = parser.isoparse(filter_value)
                if datetime_value.tzinfo is None:
                    return datetime_value.replace(tzinfo=timezone)
            return datetime_value.astimezone(timezone)

        date_value = datetime.now(tz=timezone).date()
        if operator in DATE_FILTER_OPERATOR_DELTA_MAP:
            date_value += DATE_FILTER_OPERATOR_DELTA_MAP[operator](filter_value)
        return date_value

    def _split_combined_value(
        self, field, filter_value, separator
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        operator = None
        if separator in filter_value:  # specific timezone provided by the filter
            splitted_value = filter_value.split(separator)
            if len(splitted_value) == 2:  # partial, maybe coming from old date filters
                timezone_value, filter_value = splitted_value
                return timezone_value, filter_value, operator
            elif len(splitted_value) == 3:
                timezone_value, filter_value, operator = splitted_value
                return timezone_value, filter_value, operator
            else:
                return None, None, None
        elif filter_value in get_timezones():
            # only a timezone value was provided with no filter value
            return filter_value, None
        else:
            # default to the fields timezone if any and the provided value
            return field.date_force_timezone, filter_value

    def get_available_operators(self):
        """
        Returns a list of all available operators that can be used to filter the field.
        """

        return [
            opr
            for opr in DateFilterOperators.__members__.values()
            if opr not in self.incompatible_operators
        ]

    def split_combined_value(
        self, field, filter_value, separator=DATE_FILTER_TIMEZONE_SEPARATOR
    ) -> Tuple[zoneinfo.ZoneInfo, str, str]:
        """
        Splits the timezone and the value from the provided value. If the value does not
        contain a timezone then the default timezone will be used.

        :param field: The field that is being filtered.
        :param filter_value: The value that has been provided by the user.
        :param separator: The separator that is used to split the timezone and the
            value.
        :return: A tuple containing the timezone, the filter_value string and the
            operator.
        """

        (
            user_timezone_str,
            parsed_filter_value,
            operator,
        ) = self._split_combined_value(field, filter_value, separator)

        python_timezone = zoneinfo.ZoneInfo(
            user_timezone_str if user_timezone_str else "UTC"
        )

        validated_filter_value = (
            parsed_filter_value
            if parsed_filter_value is not None
            else DATE_FILTER_EMPTY_VALUE
        )

        available_operator_values = [
            opr.value for opr in self.get_available_operators()
        ]
        if operator not in available_operator_values:
            raise ValueError(f"Invalid operator {operator} provided.")

        return python_timezone, validated_filter_value, operator

    def is_empty_filter(self, operator: str, filter_value: str) -> bool:
        if operator not in ("exact_date", "nr_days_ago", "nr_days_from_now"):
            return False
        return filter_value == DATE_FILTER_EMPTY_VALUE

    def get_filter_expression(
        self,
        field_name: str,
        model_field,
        lower_bound: date | datetime,
        upper_bound: date | datetime,
        timezone: zoneinfo.ZoneInfo,
    ) -> OptionallyAnnotatedQ:
        """
        Returns an OptionallyAnnotatedQ object that can be used to filter the provided
        field_name, given the lower and upper bounds of the filter and the timezone to
        consider.

        :param field_name: The name of the field that should be used in the query.
        :params model_field: The Django model field of the database table that is being
            filtered.
        :param lower_bound: The lower bound of the filter.
        :param upper_bound: The upper bound of the filter.
        :param timezone: The timezone that should be used to filter the provided field.
        :return: An OptionallyAnnotatedQ object that can be used to filter the provided
            field.
        """

        raise NotImplementedError()

    def get_filter(
        self, field_name: str, value: str, model_field, field: Field
    ) -> Union[Q, AnnotatedQ]:
        """
        Returns a Q object that can be used to filter the provided field.

        :param field_name: The name of the field that should be used in the
            query.
        :param value: The value that has been provided by the user.
        :param model_field: The Django model field of the database table that is
            being filtered.
        :param field: The Baserow field instance containing the metadata related
            to the field.
        :return: A Q object that can be used to filter the provided field.
        """

        try:
            timezone, filter_value, operator = self.split_combined_value(
                field, value.strip()
            )
            if self.is_empty_filter(operator, filter_value):
                return Q()

            filter_date = self.get_filter_date(operator, filter_value, timezone)
        except (
            OverflowError,
            ValueError,
            parser.ParserError,
            zoneinfo.ZoneInfoNotFoundError,
        ):
            return Q(pk__in=[])

        if isinstance(model_field, DateField) and isinstance(filter_date, datetime):
            filter_date = filter_date.date()

        date_filter_operator = DATE_FILTER_OPERATOR_FROM_VALUE[operator]
        lower_bound, upper_bound = DATE_FILTER_OPERATOR_BOUNDS[date_filter_operator](
            filter_date
        )

        return self.get_filter_expression(
            field_name, model_field, lower_bound, upper_bound, timezone
        )


class DateMultiStepViewFilterType(BaseDateMultiStepViewFilterType):
    compatible_field_types = [
        DateFieldType.type,
        LastModifiedFieldType.type,
        CreatedOnFieldType.type,
        FormulaFieldType.compatible_with_formula_types(BaserowFormulaDateType.type),
    ]

    def get_filter_query_dict(
        self,
        operator: str,
        field_name: str,
        aware_filter_date: Union[datetime, date],
        **kwargs,
    ) -> Dict[str, Union[date, datetime]]:
        """
        Returns a dictionary that can be used to create a Q object.

        :param operator: The operator that should be used to filter the field.
        :param field_name: The name of the field that should be used in the
            query.
        :param aware_filter_date: The date that should be used to compare with
            the field value.
        """

        raise NotImplementedError()

    def get_filter_expression(
        self,
        field_name: str,
        model_field,
        lower_bound: date | datetime,
        upper_bound: date | datetime,
        timezone: zoneinfo.ZoneInfo,
    ) -> OptionallyAnnotatedQ:
        annotation = {}
        query_field_name = field_name

        if isinstance(model_field, DateTimeField) and isinstance(lower_bound, date):
            tzname = str(timezone).lower().replace("/", "_")
            query_field_name = f"{field_name}_tz_{tzname}"
            annotation[query_field_name] = TruncDate(field_name, tzinfo=timezone)

        query_dict = {
            f"{field_name}__isnull": False,  # makes `NotViewFilterTypeMixin` work with timezones
            **self.get_filter_query_dict(
                query_field_name, lower_bound, upper_bound, timezone
            ),
        }
        return AnnotatedQ(annotation=annotation, q=query_dict)


class DateIsEqualMultiStepFilterType(DateMultiStepViewFilterType):
    type = "date_is"

    def get_filter_query_dict(
        self,
        field_name: str,
        lower_bound: Union[date, datetime],
        upper_bound: Union[date, datetime],
        timezone: datetime_module.tzinfo,
    ) -> Dict[str, Union[date, datetime]]:
        return {f"{field_name}__gte": lower_bound, f"{field_name}__lt": upper_bound}


class DateIsNotEqualMultiStepFilterType(
    NotViewFilterTypeMixin, DateIsEqualMultiStepFilterType
):
    type = "date_is_not"


class DateIsBeforeMultiStepFilterType(DateMultiStepViewFilterType):
    type = "date_is_before"

    def get_filter_query_dict(
        self,
        field_name: str,
        lower_bound: Union[date, datetime],
        upper_bound: Union[date, datetime],
        timezone: datetime_module.tzinfo,
    ) -> Dict[str, Union[date, datetime]]:
        return {f"{field_name}__lt": lower_bound}


class DateIsOnOrBeforeMultiStepFilterType(DateMultiStepViewFilterType):
    type = "date_is_on_or_before"

    def get_filter_query_dict(
        self,
        field_name: str,
        lower_bound: Union[date, datetime],
        upper_bound: Union[date, datetime],
        timezone: datetime_module.tzinfo,
    ) -> Dict[str, Union[date, datetime]]:
        return {f"{field_name}__lt": upper_bound}


class DateIsAfterMultiStepFilterType(DateMultiStepViewFilterType):
    type = "date_is_after"

    def get_filter_query_dict(
        self,
        field_name: str,
        lower_bound: Union[date, datetime],
        upper_bound: Union[date, datetime],
        timezone: datetime_module.tzinfo,
    ) -> Dict[str, Union[date, datetime]]:
        return {f"{field_name}__gte": upper_bound}


class DateIsOnOrAfterMultiStepFilterType(DateMultiStepViewFilterType):
    type = "date_is_on_or_after"

    def get_filter_query_dict(
        self,
        field_name: str,
        lower_bound: Union[date, datetime],
        upper_bound: Union[date, datetime],
        timezone: datetime_module.tzinfo,
    ) -> Dict[str, Union[date, datetime]]:
        return {f"{field_name}__gte": lower_bound}


class DateIsWithinMultiStepFilterType(DateMultiStepViewFilterType):
    type = "date_is_within"

    incompatible_operators = [DateFilterOperators.TODAY]

    def get_filter_query_dict(
        self,
        field_name: str,
        lower_bound: Union[date, datetime],
        upper_bound: Union[date, datetime],
        timezone: datetime_module.tzinfo,
    ) -> Dict[str, Union[date, datetime]]:
        today = datetime.now(tz=timezone).date()
        if today < upper_bound:
            lower_bound = today
        else:
            upper_bound = today + timedelta(days=1)
        return {
            f"{field_name}__gte": lower_bound,
            f"{field_name}__lt": upper_bound,
        }
