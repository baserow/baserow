from datetime import timedelta
from functools import partial

from django.db.models import QuerySet
from django.db.transaction import on_commit

from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.handler import LicenseHandler
from loguru import logger
from rest_framework import serializers

from baserow.contrib.database.field_rules.collector import FieldRuleCollector
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

from .calculations import DateCalculator, DateDependencyCalculator, DateValues
from .serializers import (
    RequestDateDependencySerializer,
    ResponseDateDependencySerializer,
)


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
        "dependency_linkrow_field_id",
    ]
    request_serializer_field_names = [
        "is_active",
        "start_date_field_id",
        "end_date_field_id",
        "duration_field_id",
        "dependency_linkrow_field_id",
    ]

    allowed_fields = [
        "is_active",
        "start_date_field_id",
        "end_date_field_id",
        "duration_field_id",
        "dependency_linkrow_field_id",
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
        dependency_linkrow_field_id=serializers.IntegerField(
            required=False, allow_null=True, help_text="Linkrow field id"
        ),
    )

    def check_license(self, table):
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
        self,
        model: GeneratedTableModel,
        row_data: dict,
        rule: FieldRule,
        collector: FieldRuleCollector,
    ) -> list[RowRuleChanges] | None:
        """
        Calculates start/end/duration values if possible for a new row.
        """

        try:
            self.check_license(model.get_parent())
        except FeaturesNotAvailableError:
            logger.debug(f"No license for {model.get_parent()}.")
            return

        if not (rule.is_active and rule.is_valid):
            return
        rule: DateDependency = rule.specific

        calc = DateCalculator(
            DateValues.from_row(None, rule),
            DateValues.from_dict(row_data, rule),
            include_weekends=rule.include_weekends,
        )

        new_values = calc.calculate()
        out = []
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
            out.append(ret)
            collector.add_changes([ret])
            row_updated = model(id=-1, **new_values)
            deps_calc = DateDependencyCalculator(row_updated, rule, collector.visited)
            deps_calc.calculate()
            for row_id, row_data_values in deps_calc.modified:
                out.append(
                    RowRuleChanges(
                        row_id=row_id,
                        updated_values=row_data_values.to_dict(),
                        updated_field_ids=changed_column_ids,
                    )
                )

        return out

    def before_row_updated(
        self,
        row: GeneratedTableModel,
        rule: FieldRule,
        updated_values: dict,
        collector: FieldRuleCollector,
    ) -> list[RowRuleChanges] | None:
        """
        Calculates start/end/duration values if possible for a row with updated values.
        """

        try:
            self.check_license(row.__class__.get_parent())
        except FeaturesNotAvailableError:
            logger.debug(f"No license for {row.__class__.get_parent()}.")
            return

        if not (rule.is_active and rule.is_valid):
            return
        rule: DateDependency = rule.specific

        calc = DateCalculator(
            DateValues.from_row(row, rule),
            DateValues.from_dict(updated_values, rule),
            include_weekends=rule.include_weekends,
        )

        new_values = calc.calculate()
        out = []
        if new_values:
            changed_column_ids = set(
                [
                    rule.start_date_field_id,
                    rule.end_date_field_id,
                    rule.duration_field_id,
                ]
            )
            ret = RowRuleChanges(
                row_id=row.id,
                updated_values=new_values,
                updated_field_ids=changed_column_ids,
            )
            out.append(ret)
            row_updated = row.__class__(id=row.id, **new_values)
            collector.add_starting_rows([row_updated])
            collector.add_changes(out)
            deps_calc = DateDependencyCalculator(row_updated, rule, collector.visited)
            deps_calc.calculate()
            for row_id, row_data_values in deps_calc.modified:
                out.append(
                    RowRuleChanges(
                        row_id=row_id,
                        updated_values=row_data_values.to_dict(),
                        updated_field_ids=changed_column_ids,
                    )
                )
        return out

    def validate_row(
        self, row: GeneratedTableModel, rule: FieldRule
    ) -> RowRuleValidity | None:
        """
        Validate if row's state conforms the rule.
        """

        try:
            self.check_license(rule.table)
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
            self.check_license(table)
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

        self.check_license(table)
        return self._validate_data(table, in_data)

    def prepare_values_for_update(
        self, rule: DateDependency, in_data: dict
    ) -> DateDepenencyDict:
        """
        Returns a dictionary with values needed to update a rule.
        """

        self.check_license(rule.table)
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
            self.check_license(rule.table)
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
