import dataclasses
from copy import copy
from datetime import date, datetime, timedelta

from django.db.models import ForeignKey

from loguru import logger

from baserow.contrib.database.fields.models import LinkRowField
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.core.psycopg import sql
from baserow_enterprise.date_dependency.models import DateDependency

from .constants import (
    DURATION_FIELD,
    END_DATE_FIELD,
    NO_VALUE,
    ROW_DEPENDENCY_GRAPH_QUERY,
    START_DATE_FIELD,
    NoValueSentinel,
)


@dataclasses.dataclass
class DateValues:
    FIELDS = (
        START_DATE_FIELD,
        END_DATE_FIELD,
        DURATION_FIELD,
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
                (self.end_date - self.start_date == self.duration - timedelta(1))
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
        """
        Returns a list of fields with None values
        """

        return [fname for fname in self.FIELDS if self.get(fname) is None]

    def get_set_fields(self) -> list[str]:
        """
        Returns a list of fields that have a value set
        """

        return [fname for fname in self.FIELDS if self.get(fname) is not NO_VALUE]

    def get_changed_fields(self, old_val: "DateValues") -> list[str]:
        """
        Returns a list of fields that are different from old value
        """

        return [
            fname
            for fname in self.FIELDS
            if self.get(fname) is not NO_VALUE and self.get(fname) != old_val.get(fname)
        ]

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

    def to_row(self, row: GeneratedTableModel) -> GeneratedTableModel:
        changes = self.to_dict()
        for field_name, value in changes.items():
            setattr(row, field_name, value)
        return row

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (
            self.dependency == other.dependency
            and self.start_date == other.start_date
            and self.end_date == other.end_date
            and self.duration == other.duration
        )


class DateCalculator:
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
        if not (changed_fields := new_val.get_set_fields()):
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

        # At least two fields have no value, so we can't calculate anything.
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
            DURATION_FIELD in changed_fields
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
                    missing_field == START_DATE_FIELD
                    and START_DATE_FIELD in changed_fields
                    and END_DATE_FIELD in result_value_fields
                ):
                    result.duration = None

        # refresh, as this could be changed
        result_value_fields = result.get_values_fields()

        try:
            # NOTE on duration calculation: the feature specifies that
            # duration = start_date + end_date + 1 day.
            # one field update scenario
            if len(changed_fields) == 1 and changed_fields[0] in result_value_fields:
                changed_field = changed_fields[0]
                if (
                    changed_field == START_DATE_FIELD
                    and DURATION_FIELD in result_value_fields
                ):
                    result = calculate_date_dependency_end(result)
                elif (
                    changed_field == START_DATE_FIELD
                    and END_DATE_FIELD in result_value_fields
                ):
                    result = calculate_date_dependency_duration(result)
                elif (
                    changed_field == END_DATE_FIELD
                    and START_DATE_FIELD in result_value_fields
                ):
                    # if end date is below start date, we shift the start date
                    if result.end_date - result.start_date < timedelta(days=0):
                        result = calculate_date_dependency_start(result)
                    else:
                        result = calculate_date_dependency_duration(result)
                elif (
                    changed_field == DURATION_FIELD
                    and START_DATE_FIELD in result_value_fields
                ):
                    result = calculate_date_dependency_end(result)
                elif (
                    changed_field == DURATION_FIELD
                    and END_DATE_FIELD in result_value_fields
                ):
                    result = calculate_date_dependency_start(result)
            elif (
                # We also do recalculation, when we know that duration didn't change,
                # but other fields are present and at least one of them was changed.
                # This excludes a situation, when duration is cleared by the user
                # explicitly, but if it was changed from None to None, it should be
                # recalculated.
                DURATION_FIELD not in changed_fields
                and START_DATE_FIELD in result_value_fields
                and END_DATE_FIELD in result_value_fields
                and (
                    START_DATE_FIELD in changed_fields
                    or END_DATE_FIELD in changed_fields
                )
            ):
                result = calculate_date_dependency_duration(result)
            elif (
                START_DATE_FIELD not in changed_fields
                and DURATION_FIELD in result_value_fields
                and END_DATE_FIELD in result_value_fields
                and (
                    DURATION_FIELD in changed_fields or END_DATE_FIELD in changed_fields
                )
            ):
                result = calculate_date_dependency_start(result)
            elif (
                END_DATE_FIELD not in changed_fields
                and DURATION_FIELD in result_value_fields
                and START_DATE_FIELD in result_value_fields
                and (
                    DURATION_FIELD in changed_fields
                    or START_DATE_FIELD in changed_fields
                )
            ):
                result = calculate_date_dependency_end(result)

        except (
            TypeError,
            ValueError,
            OverflowError,
        ) as err:
            logger.opt(exception=err).error(
                f"Error when calculating date dependency: {err}"
            )
            return initial_result
        return result


class DateDependencyCalculator:
    """
    Calculates values for dependent rows.

    Date dependency allows to pick a linkrow field to represent predecessors (parents)
    of a row. Rows can be organized into hierarchies, where start/end dates should not
    overlap, and linkrow field will describe a connection between specific rows.

    This class receives a starting row and date dependency rule, and will calculate
    full graph of dependent rows in both directions (predecessors and successors). Then,
    it will walk up and down the graph, and check if start/end dates between two rows
    connected don't overlap (according to date dependency parameters). If there's an
    overlap, the other end of connection will be adjusted accordingly.
    """

    def __init__(
        self,
        row: GeneratedTableModel,
        rule: DateDependency,
        previsited: set | None = None,
    ):
        """
        Creates an instance.

        :param row: Starting row to calculate the graph.
        :param rule: Rule with dependency parameters.
        :param previsited: Optional list of visited row ids, useful if multiple rules
            may affect the same row. If a row id is present in the visited list, it
            should not be processed. What's more, the processing of a chain should
            also be stopped, if it hits a row that was previously visited.
        """

        self.row = row
        self.rule = rule
        self.cache = {row.id: row}
        self.dependency_map = {}
        self.visited = set().union(previsited or set())
        self.modified = []
        self.graph_paths = []

    def get_linkrow_from_to_fields(
        self, linkrow_field: LinkRowField
    ) -> tuple[ForeignKey, ForeignKey]:
        """
        Extracts from/to fields in relation table for the linkrow.

        Linkrow field values are stored in a separate `database_relation_XXX` table,
        where pairs of from row/to row are stored. This allows to model complex graph
        of dependent rows.

        This method returns a tuple of fields, where one represents `from` row, and the
        other represents `to` row.

        :param linkrow_field:
        :return: A tuple with Child/parent fields
        """

        table = linkrow_field.table
        model = table.get_model()
        through = getattr(model, linkrow_field.db_column).through
        parent_field = None
        child_field = None

        for field in through._meta.get_fields():
            if type(field) is not ForeignKey:
                continue
            field_name = field.get_attname_column()[1]
            if field_name.startswith("from_"):
                child_field = field
            elif field_name.startswith("to_"):
                parent_field = field
        if not (parent_field and child_field):
            raise ValueError("Parent/child fields not found!")
        return (
            child_field,
            parent_field,
        )

    def populate_dependency_graph(self):
        """
        Populates dependency graph for the starting row, and cache for rows.

        This queries the table with linkrow relations for user data table, and builds
        a graph of dependent rows for the starting row. Based on results, it populates
        `.graph_paths` and  `.cache` with rows.
        """

        rule = self.rule
        if not (
            rule.duration_field
            and rule.start_date_field
            and rule.end_date_field
            and rule.dependency_linkrow_field
        ):
            logger.warning(f"Field Rule doesn't have all fields: {rule.to_dict()}")
            return
        linkrow_field = self.rule.dependency_linkrow_field.specific
        table_name = sql.Identifier(self.row.__class__._meta.db_table)
        start_date_field = sql.Identifier(self.rule.start_date_field.db_column)
        end_date_field = sql.Identifier(self.rule.end_date_field.db_column)
        duration_field = sql.Identifier(self.rule.duration_field.db_column)

        relation_table_name = sql.Identifier(linkrow_field.through_table_name)
        from_field, to_field = self.get_linkrow_from_to_fields(linkrow_field)
        from_field_name = sql.Identifier(from_field.column)
        to_field_name = sql.Identifier(to_field.column)

        row_id = self.row.pk

        params = {
            "value": sql.Literal(row_id),
            "to_field_name": to_field_name,
            "from_field_name": from_field_name,
            "relation_table_name": relation_table_name,
            "table_name": table_name,
            "start_date_field": start_date_field,
            "end_date_field": end_date_field,
            "duration_field": duration_field,
        }

        query = ROW_DEPENDENCY_GRAPH_QUERY.format(**params)

        affected_rows = list(self.row.__class__.objects.raw(query))

        for rule in affected_rows:
            if rule.node_type == "LEAF":
                self.graph_paths.append(rule.path)
            if rule.id in self.cache:
                continue
            self.cache[rule.id] = rule

    def _get_row(self, row_id) -> GeneratedTableModel:
        try:
            return self.cache[row_id]
        except KeyError:
            row = self.row.__class__.objects.get(pk=row_id)
            self.cache[row_id] = row
            return row

    def _set_row(self, row: GeneratedTableModel) -> GeneratedTableModel:
        self.cache[row.id] = row
        return row

    def calculate(self):
        self.modified.clear()

        self.populate_dependency_graph()
        if not (self.graph_paths):
            logger.debug(f"No dependencies found for {self.row}")
            return
        self.adjust_predecessors()
        self.adjust_successors()

    def adjust_predecessors(self):
        """
        Find all paths that will end up in root elements and change values, if dates
        are overlapping.
        """

        paths = self.graph_paths

        visited = self.visited
        modified = self.modified

        for path in paths:
            # walk from child to parent, so we need to revert the path
            walk_items = list(reversed(path))
            child = DateValues.from_row(self.row, self.rule)
            # we can walk when we get past current row
            can_walk = False
            local_visited = set()

            for item_id in walk_items:
                if item_id == self.row.id:
                    can_walk = True
                    continue
                if not can_walk:
                    continue

                # If visited just for this path, then we bail, as this may be a loop.
                if item_id in local_visited:
                    break
                local_visited.add(item_id)

                # Row may have been processed globally already, so we move to the
                # next one. However, any subsequent row should use this one as a
                # previous row.
                parent_row = self._get_row(item_id)
                parent = DateValues.from_row(parent_row, self.rule)
                if item_id in visited:
                    child = parent
                    continue

                visited.add(item_id)

                if not parent.has_valid_value_types():
                    logger.debug(
                        "Breaking from adjust_predecessors because parent "
                        f" {item_id} has invalid values: {parent.to_dict()}"
                    )
                    break
                adjusted = adjust_parent(parent, child, self.rule)
                if not adjusted:
                    break
                self._set_row(parent.to_row(parent_row))
                modified.append(
                    (
                        item_id,
                        parent,
                    )
                )
                child = parent

    def adjust_successors(self):
        """
        Adjust start/end date values for all successors (children) of the initial row.

        This will walk through all paths and update rows after the initial row. If a
        child row is invalid, or was already processed by another rule, this, and
        subsequent items won't be processed.
        """

        paths = self.graph_paths

        visited = self.visited
        modified = self.modified

        for path in paths:
            walk_items = copy(path)
            can_walk = False
            local_visited = set()
            parent = DateValues.from_row(self.row, self.rule)
            for item_id in walk_items:
                if item_id == self.row.id:
                    can_walk = True
                    continue
                if not can_walk:
                    continue

                if item_id in local_visited:
                    break
                local_visited.add(item_id)

                # Row may have been processed globally already, so we move to the
                # next one. However, any subsequent row should use this one as a
                # previous row.
                child_row = self._get_row(item_id)
                child = DateValues.from_row(child_row, self.rule)
                if item_id in visited:
                    parent = child
                    continue
                visited.add(item_id)

                if not child.is_valid():
                    logger.warning(
                        "Breaking from adjust_successors because child "
                        f" {item_id} has invalid values: {child.to_dict()}"
                    )
                    break
                adjusted = adjust_child(parent, child, self.rule)
                if not adjusted:
                    break
                self._set_row(child.to_row(child_row))
                modified.append(
                    (
                        item_id,
                        child,
                    )
                )
                parent = child


def adjust_parent(parent: DateValues, child: DateValues, rule: DateDependency) -> bool:
    """
    Move parent back one day before child's start date, if its end date overlaps with
    child's start date. This will change values in place, and return True, if they
    were modified.
    """

    if rule.buffer_is_none:
        return False
    if rule.buffer_is_fixed:
        if not (
            isinstance(child.start_date, date)
            and isinstance(parent.end_date, date)
            and isinstance(parent.duration, timedelta)
        ):
            return False

        if child.start_date <= parent.end_date:
            parent.end_date = child.start_date - timedelta(days=1)
            new_parent = calculate_date_dependency_start(parent)
            parent.start_date = new_parent.start_date
            return True
    elif rule.buffer_is_flexible:
        if not (
            isinstance(child.start_date, date)
            and isinstance(parent.end_date, date)
            and isinstance(parent.duration, timedelta)
        ):
            return False

        if child.start_date <= parent.end_date or (
            rule.dependency_buffer
            and (child.start_date - parent.end_date) < rule.dependency_buffer
        ):
            parent.end_date = (
                child.start_date - rule.dependency_buffer - timedelta(days=1)
            )
            new_parent = calculate_date_dependency_start(parent)
            parent.start_date = new_parent.start_date
            return True
    return False


def adjust_child(parent: DateValues, child: DateValues, rule: DateDependency) -> bool:
    """
    Move child forward one day after parent's end date, if its start date overlaps
    with parent's end date. This will change values in place, and return True, if
    they were modified.
    """

    if rule.buffer_is_none:
        return False
    if rule.buffer_is_fixed:
        if not (
            isinstance(child.start_date, date)
            and isinstance(parent.end_date, date)
            and isinstance(child.duration, timedelta)
        ):
            return False

        if child.start_date <= parent.end_date:
            child.start_date = parent.end_date + timedelta(days=1)
            new_child = calculate_date_dependency_end(child)
            child.end_date = new_child.end_date
            return True
    elif rule.buffer_is_flexible:
        if not (
            isinstance(child.start_date, date)
            and isinstance(parent.end_date, date)
            and isinstance(child.duration, timedelta)
        ):
            return False

        if child.start_date <= parent.end_date or (
            rule.dependency_buffer
            and (child.start_date - parent.end_date) < rule.dependency_buffer
        ):
            child.start_date = (
                parent.end_date + rule.dependency_buffer + timedelta(days=1)
            )
            new_child = calculate_date_dependency_end(child)
            child.end_date = new_child.end_date

            return True
    return False


def calculate_date_dependency_start(in_data: DateValues) -> DateValues:
    """
    Calculates start date for end date and duration in days and returns updated values.

    If we calculate including weekends, then we take the number of days (+1 day to
    include start day).

    Start date calculation when weekends should be excluded, is more complicated. We
    need to count
    """

    if not (
        isinstance(in_data.duration, timedelta) and isinstance(in_data.end_date, date)
    ):
        return in_data

    # we can't calculate start, if duration is below 1 day. Duration includes 1 extra
    # day to include start date Such a case is considered invalid.
    if in_data.dependency.include_weekends and in_data.duration < timedelta(days=1):
        return in_data

    end_date = in_data.end_date
    days = in_data.duration.days

    result = DateValues(
        in_data.dependency,
        start_date=None,
        end_date=end_date,
        duration=in_data.duration,
    )

    result.start_date = end_date - timedelta(days=(days - 1))
    return result


def calculate_date_dependency_end(in_data: DateValues) -> DateValues:
    """
    Calculates end date for start date and duration in days, and returns updated values.

    If we calculate including weekends, then we take the number of days (+1 day to
    include start day).

    Date calculation when weekends should be excluded, is more complicated. We
    need to count just regular workdays, so we may not add start/end date day.
    """

    if not (
        isinstance(in_data.duration, timedelta) and isinstance(in_data.start_date, date)
    ):
        return in_data

    # don't calculate start date if we include weekends. Duration is invalid in this
    # case.
    if in_data.dependency.include_weekends and in_data.duration < timedelta(days=1):
        return in_data

    start_date = in_data.start_date
    days = in_data.duration.days

    result = DateValues(
        in_data.dependency,
        end_date=None,
        start_date=start_date,
        duration=in_data.duration,
    )
    result.end_date = start_date + timedelta(days=days - 1)
    return result


def calculate_date_dependency_duration(in_data: DateValues) -> DateValues:
    """
    Calculates duration for start date and end date in days, and returns updated values.

    If we calculate including weekends, then we take the number of days (+1 day to
    include start day).

    Date calculation when weekends should be excluded, is more complicated. We
    need to count just regular workdays, so we may not add start/end date day.
    """

    if not (
        isinstance(in_data.start_date, date) and isinstance(in_data.end_date, date)
    ):
        return in_data

    # start date is after end date, so invalid
    if in_data.start_date > in_data.end_date:
        return in_data

    start_date, end_date = in_data.start_date, in_data.end_date

    result = DateValues(
        in_data.dependency,
        end_date=end_date,
        start_date=start_date,
        duration=None,
    )

    result.duration = in_data.end_date - in_data.start_date + timedelta(days=1)
    return result
