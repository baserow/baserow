import dataclasses
from datetime import date, datetime, timedelta
from functools import partial

from django.db.models import QuerySet
from django.db.transaction import on_commit

from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.handler import LicenseHandler
from loguru import logger

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

from .serializers import (
    RequestDateDependencySerializer,
    ResponseDateDependencySerializer,
)


class Sentinel:
    pass


NO_VALUE = Sentinel()


@dataclasses.dataclass
class DateValues:
    FIELDS = (
        "start_date",
        "end_date",
        "duration",
    )

    dependency: DateDependency
    start_date: datetime | None | Sentinel
    end_date: datetime | None | Sentinel
    duration: timedelta | None | Sentinel

    def has_valid_values(self):
        return (
            isinstance(self.end_date, date)
            and isinstance(self.start_date, date)
            and isinstance(self.duration, timedelta)
        )

    def is_valid(self):
        if len(self.get_values_fields()) != 3:
            return False
        if not self.has_valid_values():
            return False
        return self.end_date == self.start_date + self.duration

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

    def get(self, field_name: str) -> datetime | timedelta | None | Sentinel:
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

        # more than two values are not set, so we can't calculate third
        if len(result.get_values_fields()) < 2:
            return result

        none_in_result = result.get_none_fields()
        result_value_fields = result.get_values_fields()
        if none_in_result:
            # 2 or more fields set to None, so we can't calculate
            if len(none_in_result) > 1:
                return result

            # if start_date is removed from a row, we also clear duration
            else:
                missing_field = none_in_result[0]
                if (
                    missing_field == "start_date"
                    and "start_date" in changed_fields
                    and "end_date" in result_value_fields
                ):
                    result.duration = None

        # refresh, as this could be changed
        result_value_fields = result.get_values_fields()
        none_in_result = result.get_none_fields()

        # update scenario
        if len(changed_fields) == 1 and changed_fields[0] in result_value_fields:
            changed_field = changed_fields[0]
            if changed_field == "start_date" and "duration" in result_value_fields:
                result.end_date = result.start_date + result.duration
                self.adjust_end_date(result)

            elif changed_field == "start_date" and "end_date" in result_value_fields:
                result.duration = result.end_date - result.start_date
            elif changed_field == "end_date" and "start_date" in result_value_fields:
                result.duration = result.end_date - result.start_date
            elif changed_field == "duration" and "start_date" in result_value_fields:
                result.end_date = result.start_date + result.duration
                self.adjust_end_date(result)
            elif changed_field == "duration" and "end_date" in result_value_fields:
                result.start_date = result.end_date - result.duration
                self.adjust_end_date(result)
        # insert/paste values scenario - calculate duration only, if it's possible
        elif (
            len(changed_fields) > 1
            and "duration" in none_in_result
            and "start_date" in result_value_fields
            and "end_date" in result_value_fields
        ):
            result.duration = result.end_date - result.start_date
            self.adjust_end_date(result)

        return result

    def adjust_end_date(self, result: DateValues) -> None:
        if not self.include_weekends or result.end_date is None:
            return

        wday = result.end_date.weekday()
        if wday > 4:
            days_diff = 7 - wday
            new_end_date = result.end_date + timedelta(days=days_diff)
            result.end_date = new_end_date
            result.duration = result.end_date - result.start_date


class DateDependencyFieldRuleType(FieldRuleType):
    type = "date_dependency"

    model_class = DateDependency
    serializer_mixins = [ResponseDateDependencySerializer]
    request_serializer_mixins = [RequestDateDependencySerializer]

    serializer_field_names = FieldRuleType.serializer_field_names + [
        "start_date_field_id",
        "end_date_field_id",
        "duration_field_id",
        "dependency_linkrow_field_id",
        "dependency_linkrow_role",
        "dependency_connection_type",
        "dependency_buffer_type",
        "dependency_buffer",
        "include_weekends",
    ]

    def _check_license(self, table):
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            DATE_DEPENDENCY, table.database.workspace
        )

    def enrich_table_queryset(self, queryset) -> QuerySet:
        """
        Allows to modify table queryset with additional related models
        """

        try:
            self._check_license(queryset.model.get_parent())
        except FeaturesNotAvailableError:
            return queryset

        return queryset.select_related("field_rules__date_dependency")

    def _get_date_values(self, row, rule) -> "DateValues":
        """
        Shortcut to get DateValues out of a row and a rule
        """

        rule: DateDependency = rule.specific

        start_date_col = rule.start_date_field.db_column
        end_date_col = rule.end_date_field.db_column
        duration_col = rule.duration_field.db_column

        start_date_before = getattr(row, start_date_col, NO_VALUE)
        end_date_before = getattr(row, end_date_col, NO_VALUE)
        duration_before = getattr(row, duration_col, NO_VALUE)
        return DateValues(rule, start_date_before, end_date_before, duration_before)

    def before_row_created(
        self, model: GeneratedTableModel, row_data: dict, rule: FieldRule
    ) -> RowRuleChanges | None:
        try:
            self._check_license(model.get_parent())
        except FeaturesNotAvailableError:
            logger.debug("no license!", model.get_parent(), model)
            return

        if not (rule.is_active and rule.is_valid):
            return
        rule: DateDependency = rule.specific

        start_date_col = rule.start_date_field.db_column
        end_date_col = rule.end_date_field.db_column
        duration_col = rule.duration_field.db_column

        before = self._get_date_values(None, rule)
        # update can carry None value, so we need to distinguish it from no value.
        start_date_after = row_data.get(start_date_col, NO_VALUE)
        end_date_after = row_data.get(end_date_col, NO_VALUE)
        duration_after = row_data.get(duration_col, NO_VALUE)

        calc = DateDependencyCalculator(
            before,
            DateValues(rule, start_date_after, end_date_after, duration_after),
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
        try:
            self._check_license(row.__class__.get_parent())
        except FeaturesNotAvailableError:
            logger.debug("no license!", row.__class__.get_parent(), row.__class__)
            return

        if not (rule.is_active and rule.is_valid):
            return
        rule: DateDependency = rule.specific
        row_id = None

        start_date_col = rule.start_date_field.db_column
        end_date_col = rule.end_date_field.db_column
        duration_col = rule.duration_field.db_column

        before = self._get_date_values(row, rule)
        # update can carry None value, so we need to distinguish it from no value.
        start_date_after = updated_values.get(start_date_col, NO_VALUE)
        end_date_after = updated_values.get(end_date_col, NO_VALUE)
        duration_after = updated_values.get(duration_col, NO_VALUE)

        calc = DateDependencyCalculator(
            before,
            DateValues(rule, start_date_after, end_date_after, duration_after),
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
        try:
            self._check_license(rule.table)
        except FeaturesNotAvailableError:
            return
        if not (rule.is_valid and rule.is_active):
            return
        values = self._get_date_values(row, rule)
        return RowRuleValidity(row.id, rule.id, values.is_valid())

    def validate_rows(
        self, table: Table, rule: FieldRule, queryset: QuerySet | None = None
    ) -> list[RowRuleValidity]:
        try:
            self._check_license(table)
        except FeaturesNotAvailableError:
            return
        if queryset is None:
            queryset = table.get_model().objects.all()
        out = []
        for row in queryset:
            validity = self.validate_row(row, rule)
            out.append(validity)
        return out

    # lifecycle hooks
    def prepare_values_for_create(
        self, table: Table, in_data: dict
    ) -> DateDepenencyDict:
        self._check_license(table)

        return DateDepenencyDict(
            start_date_field_id=in_data["start_date_field_id"],
            end_date_field_id=in_data["end_date_field_id"],
            duration_field_id=in_data["duration_field_id"],
            include_weekends=in_data.get("include_weekends") or False,
            dependency_linkrow_field_id=in_data.get("dependency_linkrow_field_id"),
            dependency_linkrow_role=in_data.get("dependency_linkrow_role")
            or DependencyLinkrowType.PREDECESSORS,
            dependency_connection_type=in_data.get("dependency_connection_type")
            or DependencyConnectionType.END_TO_START,
            dependency_buffer=in_data.get("dependency_buffer") or timedelta(0),
            dependency_buffer_type=in_data.get("dependency_buffer_type")
            or DependencyBufferType.FIXED,
        )

    def prepare_values_for_update(
        self, rule: DateDependency, in_data: dict
    ) -> DateDepenencyDict:
        self._check_license(rule.table)

        return DateDepenencyDict(
            start_date_field_id=in_data["start_date_field_id"],
            end_date_field_id=in_data["end_date_field_id"],
            duration_field_id=in_data["duration_field_id"],
            include_weekends=in_data.get("include_weekends") or False,
            dependency_linkrow_field_id=in_data.get("dependency_linkrow_field_id"),
            dependency_linkrow_role=in_data.get("dependency_linkrow_role")
            or DependencyLinkrowType.PREDECESSORS,
            dependency_connection_type=in_data.get("dependency_connection_type")
            or DependencyConnectionType.END_TO_START,
            dependency_buffer=in_data.get("dependency_buffer") or timedelta(0),
            dependency_buffer_type=in_data.get("dependency_buffer_type")
            or DependencyBufferType.FIXED,
        )

    def before_rule_deleted(self, rule):
        self._check_license(rule.table)

    def validate_rule(self, rule: FieldRule) -> FieldRuleValidity:
        self._check_license(rule.table)
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
        # we can exit early if the rule is somehow invalid
        if not (rule.is_active and rule.is_valid):
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
        # model = rule.table.get_model()
        # return self.recalculate_rows(model)

    def after_rule_updated(self, rule):
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
