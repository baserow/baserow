import dataclasses
from copy import copy
from datetime import date, datetime, timedelta
from functools import partial

from django.db.models import QuerySet
from django.db.transaction import on_commit

from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.handler import LicenseHandler
from loguru import logger
from rest_framework import serializers

from baserow.contrib.database.field_rules.exceptions import FieldRuleAlreadyExistsError
from baserow.contrib.database.field_rules.models import FieldRule
from baserow.contrib.database.field_rules.registries import (
    FieldRuleType,
    FieldRuleValidity,
    RowRuleChanges,
    RowRuleValidity,
)
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow_enterprise.date_dependency.models import (
    DateDependency,
    DependencyBufferType,
    DependencyConnectionType,
    DependencyLinkrowType,
)
from baserow_enterprise.date_dependency.types import DateDepenencyDict
from baserow_enterprise.features import DATE_DEPENDENCY

from .constants import NO_VALUE, DateDependencyFieldNames, NoValueSentinel
from .serializers import (
    RequestDateDependencySerializer,
    ResponseDateDependencySerializer,
)


@dataclasses.dataclass
class DateValues:
    FIELDS = (
        DateDependencyFieldNames.START_DATE,
        DateDependencyFieldNames.END_DATE,
        DateDependencyFieldNames.DURATION,
    )

    dependency: DateDependency
    start_date: datetime | None | NoValueSentinel
    end_date: datetime | None | NoValueSentinel
    duration: timedelta | None | NoValueSentinel

    @classmethod
    def from_row(cls, row: GeneratedTableModel, rule: DateDependency) -> "DateValues":
        start_date_col = rule.start_date_field.db_column
        end_date_col = rule.end_date_field.db_column
        duration_col = rule.duration_field.db_column

        start_date_before = getattr(row, start_date_col, NO_VALUE)
        end_date_before = getattr(row, end_date_col, NO_VALUE)
        duration_before = getattr(row, duration_col, NO_VALUE)
        return cls(rule, start_date_before, end_date_before, duration_before)

    @classmethod
    def from_dict(cls, row: dict, rule: DateDependency) -> "DateValues":
        start_date_col = rule.start_date_field.db_column
        end_date_col = rule.end_date_field.db_column
        duration_col = rule.duration_field.db_column

        start_date_before = row.get(start_date_col, NO_VALUE)
        end_date_before = row.get(end_date_col, NO_VALUE)
        duration_before = row.get(duration_col, NO_VALUE)
        return cls(rule, start_date_before, end_date_before, duration_before)

    def has_valid_value_types(self):
        return (
            isinstance(self.end_date, date)
            and isinstance(self.start_date, date)
            and isinstance(self.duration, timedelta)
        )

    def has_valid_duration(self):
        try:
            return (
                # start/end dates match the duration + 1 day
                self.end_date == (self.start_date + (self.duration - timedelta(1)))
                # duration is positive
                and self.duration.total_seconds() > 0
                # duration is aligned to days
                and int(self.duration.total_seconds() / self.duration.days)
                * self.duration.days
                == self.duration.total_seconds()
            )
        except (TypeError, ValueError, OverflowError):
            return False

    def is_valid(self):
        if len(self.get_values_fields()) != 3:
            return False
        if not self.has_valid_value_types():
            return False
        return self.has_valid_duration()

    def get_no_values_fields(self) -> list[str]:
        return [fname for fname in self.FIELDS if self.get(fname) is NO_VALUE]

    def get_values_fields(self) -> list[str]:
        return [
            fname
            for fname in self.FIELDS
            if self.get(fname) is not NO_VALUE and self.get(fname) is not None
        ]

    def get_none_fields(self) -> list[str]:
        return [fname for fname in self.FIELDS if self.get(fname) is None]

    def get_changed_fields(self) -> list[str]:
        return [fname for fname in self.FIELDS if self.get(fname) is not NO_VALUE]

    def get(self, field_name: str) -> datetime | timedelta | None | NoValueSentinel:
        if field_name in self.FIELDS:
            return getattr(self, field_name)
        raise ValueError(f"Invalid field name: {field_name}")

    def to_dict(self) -> dict:
        out = {
            self.dependency.start_date_field.db_column: self.start_date,
            self.dependency.end_date_field.db_column: self.end_date,
            self.dependency.duration_field.db_column: self.duration,
        }
        return out

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (
            self.dependency == other.dependency
            and self.start_date == other.start_date
            and self.end_date == other.end_date
            and self.duration == other.duration
        )


class DateDependencyCalculator:
    def __init__(
        self, old_values: DateValues, new_values: DateValues, include_weekends: bool
    ):
        """

        :param old_values:
        :param new_values:
        """

        self.old_values = old_values
        self.new_values = new_values
        self.include_weekends = include_weekends

    def field_changed(self, old_val, new_val) -> bool:
        changed = old_val != new_val and new_val is not NO_VALUE
        return changed

    def field_value(self, old_val, new_val) -> datetime | timedelta | None:
        """
        Return resulting field value based on old/new values.

        :param old_val: initial field value
        :param new_val: updated field value, can be None (to reset the value)
            or NO_VALUE to indicate that there's no update.
        :return: resulting field value
        """

        # no update, we return old one
        if new_val is NO_VALUE:
            return old_val
        return new_val

    def calculate(self) -> dict:
        if result := self._calculate():
            return result.to_dict()
        return {}

    def _calculate(self) -> DateValues | None:
        old_val = self.old_values
        new_val = self.new_values

        # no change
        if old_val == new_val:
            return
        if not (changed_fields := new_val.get_changed_fields()):
            return

        dep = new_val.dependency

        result_values = {
            fname: self.field_value(old_val.get(fname), new_val.get(fname))
            for fname in DateValues.FIELDS
        }

        result = DateValues(dep, **result_values)

        # no change
        if result == old_val:
            return

        # More than two values are not set, so we can't calculate third
        # Also, if all three values are provided with values, we don't recalculate.
        if len(result.get_values_fields()) < 2 or (
            len(changed_fields) == len(result.get_values_fields()) == 3
        ):
            return result

        # keep a copy of original result,so we can return unmodified values in case of
        # faulty calculations
        initial_result = copy(result)

        none_in_result = result.get_none_fields()
        result_value_fields = result.get_values_fields()

        # Negative duration, or duration set to hours.
        # This is invalid, so we don't recalculate, but we should round the value to 0.
        if (
            DateDependencyFieldNames.DURATION in changed_fields
            and isinstance(result.duration, timedelta)
            and result.duration < timedelta(days=1)
        ):
            initial_result.duration = timedelta(days=0)
            return initial_result

        if none_in_result:
            # 2 or more fields set to None, so we can't calculate
            if len(none_in_result) > 1:
                return result

            # if start_date is removed from a row, we also clear duration
            else:
                missing_field = none_in_result[0]
                if (
                    missing_field == DateDependencyFieldNames.START_DATE
                    and DateDependencyFieldNames.START_DATE in changed_fields
                    and DateDependencyFieldNames.END_DATE in result_value_fields
                ):
                    result.duration = None

        # refresh, as this could be changed
        result_value_fields = result.get_values_fields()
        none_in_result = result.get_none_fields()

        try:
            # NOTE on duration calculation: the feature specifies that
            # duration = start_date + end_date + 1 day.

            # update scenario
            if len(changed_fields) == 1 and changed_fields[0] in result_value_fields:
                changed_field = changed_fields[0]
                if (
                    changed_field == DateDependencyFieldNames.START_DATE
                    and DateDependencyFieldNames.DURATION in result_value_fields
                ):
                    self.adjust_duration_before(result)
                    result.end_date = result.start_date + result.duration
                    self.adjust_end_date(result)
                    self.adjust_duration_after(result)

                elif (
                    changed_field == DateDependencyFieldNames.START_DATE
                    and DateDependencyFieldNames.END_DATE in result_value_fields
                ):
                    result.duration = result.end_date - result.start_date
                    self.adjust_duration_after(result)
                elif (
                    changed_field == DateDependencyFieldNames.END_DATE
                    and DateDependencyFieldNames.START_DATE in result_value_fields
                ):
                    # if end date is below start date, we shift the start date
                    if result.end_date - result.start_date < timedelta(days=0):
                        self.adjust_duration_before(result)
                        result.start_date = result.end_date - result.duration
                    else:
                        result.duration = result.end_date - result.start_date
                    self.adjust_duration_after(result)
                elif (
                    changed_field == DateDependencyFieldNames.DURATION
                    and DateDependencyFieldNames.START_DATE in result_value_fields
                ):
                    self.adjust_duration_before(result)
                    result.end_date = result.start_date + result.duration
                    self.adjust_end_date(result)
                    self.adjust_duration_after(result)

                elif (
                    changed_field == DateDependencyFieldNames.DURATION
                    and DateDependencyFieldNames.END_DATE in result_value_fields
                ):
                    self.adjust_duration_before(result)
                    result.start_date = result.end_date - result.duration
                    self.adjust_end_date(result)
                    self.adjust_duration_after(result)
            # insert/paste values scenario - calculate duration only, if it's possible
            elif (
                len(changed_fields) > 1
                and DateDependencyFieldNames.DURATION in none_in_result
                and DateDependencyFieldNames.START_DATE in result_value_fields
                and DateDependencyFieldNames.END_DATE in result_value_fields
            ):
                result.duration = result.end_date - result.start_date
                self.adjust_end_date(result)
                self.adjust_duration_after(result)

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return initial_result

        return result

    def adjust_duration_before(self, in_values: DateValues) -> DateValues:
        """
        Decrease .duration value by 1 day to adjust duration before any calculations.

        This should be called before any calculations that are changing fields other
        than .duration in the in_values. Duration value will be decreased by 1 day, and
        aligned to a day. If the result value is negative, it will be replaced with 0.

        See .adjust_duration_after() for details.
        """

        SECONDS_PER_DAY = 86400

        if not isinstance(in_values.duration, timedelta):
            return in_values

        duration = in_values.duration - timedelta(days=1)

        days = int(duration.total_seconds() / SECONDS_PER_DAY)
        duration = timedelta(days=days)
        if duration < timedelta(seconds=0):
            duration = timedelta(seconds=0)
        in_values.duration = duration

        return in_values

    def adjust_duration_after(self, in_values: DateValues) -> DateValues:
        """
        Adjusts duration value after any recalculation. This will adjust duration to
        match the formula:

          duration = end date - start date + 1 day

        This formula simulates a calculation equivalent roughly to

          duration = end date at 23:59:59 - start date at 0:00

        but since we're using dates, we have to adjust the duration value after any
        recalculation.

        The adjust will happen only if the current duration value is equal to

            end_date - start_date

        formula. Any other value should be considered as invalid, and should not
        be changed.
        """

        if not in_values.has_valid_value_types():
            return in_values
        duration = in_values.end_date - in_values.start_date
        if duration == in_values.duration:
            in_values.duration = duration + timedelta(days=1)
        return in_values

    def adjust_end_date(self, in_values: DateValues) -> DateValues:
        """
        Adjusts end date if the configuration was set to include weekends and
        end date was a weekend.

        This will move end date to the nearest next workday, if it's required.
        """

        if self.include_weekends or in_values.end_date is None:
            return in_values

        wday = in_values.end_date.weekday()
        if wday > 4:
            days_diff = 7 - wday
            new_end_date = in_values.end_date + timedelta(days=days_diff)
            in_values.end_date = new_end_date
            in_values.duration = in_values.end_date - in_values.start_date
        return in_values


class DateDependencyFieldRuleType(FieldRuleType):
    type = "date_dependency"

    model_class = DateDependency
    serializer_mixins = [ResponseDateDependencySerializer]
    request_serializer_mixins = [RequestDateDependencySerializer]

    serializer_field_names = [
        "is_active",
        "start_date_field_id",
        "end_date_field_id",
        "duration_field_id",
    ]
    request_serializer_field_names = [
        "is_active",
        "start_date_field_id",
        "end_date_field_id",
        "duration_field_id",
    ]

    allowed_fields = [
        "is_active",
        "start_date_field_id",
        "end_date_field_id",
        "duration_field_id",
    ]

    serializer_field_overrides = dict(
        is_active=serializers.BooleanField(
            help_text=(
                "Whether the date dependency is active or not. "
                "If set to false, all other values in the payload will be ignored."
            )
        ),
        start_date_field_id=serializers.IntegerField(
            required=False, help_text="Start date field id"
        ),
        end_date_field_id=serializers.IntegerField(
            required=False, help_text="End date field id"
        ),
        duration_field_id=serializers.IntegerField(
            required=False, help_text="Duration field id"
        ),
    )

    def _check_license(self, table):
        """
        A shortcut to check the license.
        """

        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            DATE_DEPENDENCY, table.database.workspace
        )

    def enhance_table_queryset(self, queryset) -> QuerySet:
        """
        Allows to modify Table queryset with additional related models.
        """

        return queryset.prefetch_related("field_rules__datedependency")

    def enhance_queryset(self, queryset, rule: FieldRule) -> QuerySet[FieldRule]:
        return queryset.select_related(
            "table__database__workspace",
            "start_date_field__datefield",
            "end_date_field__datefield",
            "duration_field__durationfield",
            "dependency_linkrow_field",
        )

    def before_row_created(
        self, model: GeneratedTableModel, row_data: dict, rule: FieldRule
    ) -> RowRuleChanges | None:
        """
        Calculates start/end/duration values if possible for a new row.
        """

        try:
            self._check_license(model.get_parent())
        except FeaturesNotAvailableError:
            logger.debug(f"No license for {model.get_parent()}.")
            return

        if not (rule.is_active and rule.is_valid):
            return
        rule: DateDependency = rule.specific

        calc = DateDependencyCalculator(
            DateValues.from_row(None, rule),
            DateValues.from_dict(row_data, rule),
            include_weekends=rule.include_weekends,
        )

        new_values = calc.calculate()
        if new_values:
            changed_column_ids = set(
                [
                    rule.start_date_field_id,
                    rule.end_date_field_id,
                    rule.duration_field_id,
                ]
            )
            ret = RowRuleChanges(
                row_id=None,
                updated_values=new_values,
                updated_field_ids=changed_column_ids,
            )
            return ret

    def before_row_updated(
        self, row: GeneratedTableModel, rule: FieldRule, updated_values: dict
    ) -> RowRuleChanges | None:
        """
        Calculates start/end/duration values if possible for a row with updated values.
        """

        try:
            self._check_license(row.__class__.get_parent())
        except FeaturesNotAvailableError:
            logger.debug(f"No license for {row.__class__.get_parent()}.")
            return

        if not (rule.is_active and rule.is_valid):
            return
        rule: DateDependency = rule.specific
        row_id = None

        calc = DateDependencyCalculator(
            DateValues.from_row(row, rule),
            DateValues.from_dict(updated_values, rule),
            include_weekends=rule.include_weekends,
        )

        new_values = calc.calculate()
        if new_values:
            changed_column_ids = set(
                [
                    rule.start_date_field_id,
                    rule.end_date_field_id,
                    rule.duration_field_id,
                ]
            )
            ret = RowRuleChanges(
                row_id=row_id,
                updated_values=new_values,
                updated_field_ids=changed_column_ids,
            )
            return ret

    def validate_row(
        self, row: GeneratedTableModel, rule: FieldRule
    ) -> RowRuleValidity | None:
        """
        Validate if row's state conforms the rule.
        """

        try:
            self._check_license(rule.table)
        except FeaturesNotAvailableError:
            logger.debug(f"No license for {rule.table}.")
            return
        if not (rule.is_valid and rule.is_active):
            return
        values = DateValues.from_row(row, rule)
        return RowRuleValidity(row.id, rule.id, values.is_valid())

    def validate_rows(
        self, table: Table, rule: FieldRule, queryset: QuerySet | None = None
    ) -> list[RowRuleValidity]:
        """
        Validates if selected rows conform the rule.
        """

        try:
            self._check_license(table)
        except FeaturesNotAvailableError:
            logger.debug(f"No license for {table}.")
            return
        if queryset is None:
            queryset = table.get_model().objects.all()
        out = []
        for row in queryset:
            validity = self.validate_row(row, rule)
            out.append(validity)
        return out

    def _validate_data(self, table: Table, in_data: dict) -> DateDepenencyDict:
        serializer_class = self.get_serializer_class(request_serializer=True)

        serializer = serializer_class(data=in_data, context={"table": table})

        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        return DateDepenencyDict(
            start_date_field_id=validated["start_date_field_id"],
            end_date_field_id=validated["end_date_field_id"],
            duration_field_id=validated["duration_field_id"],
            include_weekends=validated.get("include_weekends", True),
            dependency_linkrow_field_id=validated.get("dependency_linkrow_field_id"),
            dependency_linkrow_role=validated.get("dependency_linkrow_role")
            or DependencyLinkrowType.PREDECESSORS,
            dependency_connection_type=validated.get("dependency_connection_type")
            or DependencyConnectionType.END_TO_START,
            dependency_buffer=validated.get("dependency_buffer") or timedelta(0),
            dependency_buffer_type=validated.get("dependency_buffer_type")
            or DependencyBufferType.FIXED,
        )

    # lifecycle hooks
    def prepare_values_for_create(
        self, table: Table, in_data: dict
    ) -> DateDepenencyDict:
        """
        Returns a dictionary with values needed to create a new rule.
        """

        self._check_license(table)
        return self._validate_data(table, in_data)

    def prepare_values_for_update(
        self, rule: DateDependency, in_data: dict
    ) -> DateDepenencyDict:
        """
        Returns a dictionary with values needed to update a rule.
        """

        self._check_license(rule.table)
        return self._validate_data(rule.table, in_data)

    def before_rule_deleted(self, rule):
        pass

    def before_rule_created(self, table: Table, in_data: DateDepenencyDict):
        """
        Checks if there is no other date dependency rule created for the table.
        """

        # This check has to be done in the code, because we can't enforce this at
        # model level. We need to enforce this on a model subclass, but table
        # information is at the base model level.
        if (
            table.field_rules.prefetch_related("datedependency", "content_type")
            .filter(content_type=self.get_content_type())
            .exists()
        ):
            raise FieldRuleAlreadyExistsError()

    def validate_rule(self, rule: FieldRule) -> FieldRuleValidity:
        """
        Checks if table's state still allow to use the rule. Internally, this will
        run validation if fields referenced by the rule are of valid types (field's id
        will not change, but field's parameters may be not usable anymore).

        This method should be called each time table schema is modified.
        """

        try:
            self._check_license(rule.table)
        except FeaturesNotAvailableError:
            logger.debug(f"No license for {rule.table}.")
            return FieldRuleValidity(
                is_valid=True, rule_id=rule.id, table_id=rule.table_id, error_text=None
            )

        serializer_cls = self.get_serializer_class(request_serializer=True)

        data = rule.specific.to_dict()
        serializer = serializer_cls(data=data, context={"table": rule.table})
        is_valid = serializer.is_valid(raise_exception=False)
        return FieldRuleValidity(
            is_valid=is_valid,
            rule_id=rule.id,
            table_id=rule.table_id,
            error_text=str(serializer.errors),
        )

    def recalculate_rows(self, rule, model):
        """
        Runs full-table rows recalculation to fill missing values where possible,
        and mark rows that are not valid for the rule.

        Depending on a table, this may take a significant amount of time, thus this
        method acts as a shim to schedule a task that actually recalculates the table.
        """

        # we can exit early if the rule is somehow invalid
        if not (rule.is_active and rule.is_valid):
            return
        # do not recalculate for a snapshot
        if rule.table.database.workspace_id is None:
            return
        rule: "DateDependency" = rule.specific
        if not (
            rule.end_date_field_id
            and rule.duration_field_id
            and rule.start_date_field_id
        ):
            return

        self.schedule_recalculate(rule)

    def schedule_recalculate(self, rule):
        from .tasks import date_dependency_recalculate_rows

        on_commit(
            partial(
                date_dependency_recalculate_rows.delay,
                rule_id=rule.id,
                table_id=rule.table_id,
            )
        )

    def after_rule_created(self, rule):
        model = rule.table.get_model()
        return self.recalculate_rows(rule, model)

    def after_rule_deleted(self, rule):
        pass

    def after_rule_updated(self, rule):
        should_recalculate = rule.is_active and rule.is_valid
        if should_recalculate:
            model = rule.table.get_model()
            return self.recalculate_rows(rule, model)

    def prepare_values_for_import(self, rule_data: dict, id_mapping: dict) -> dict:
        updated = {**rule_data}
        for key in (
            "start_date_field_id",
            "end_date_field_id",
            "duration_field_id",
            "dependency_linkrow_field_id",
        ):
            if updated[key] is not None:
                updated[key] = id_mapping[updated[key]]
        return updated

    def prepare_values_for_export(self, rule_data: dict) -> dict:
        rule_data["dependency_buffer"] = rule_data["dependency_buffer"].total_seconds()
        return rule_data
