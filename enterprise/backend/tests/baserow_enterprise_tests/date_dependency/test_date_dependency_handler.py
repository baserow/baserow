from collections.abc import Iterable
from datetime import date, timedelta
from typing import NamedTuple
from unittest import mock

from django.contrib.auth.models import AbstractUser

import pytest
from baserow_premium.license.exceptions import FeaturesNotAvailableError

from baserow.contrib.database.field_rules.exceptions import FieldRuleAlreadyExistsError
from baserow.contrib.database.field_rules.handlers import FieldRuleHandler
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow_enterprise.date_dependency.calculations import DateValues
from baserow_enterprise.date_dependency.field_rule_types import (
    DateDependencyFieldRuleType,
)
from baserow_enterprise.date_dependency.models import DateDependency


class DateDepsTestData(NamedTuple):
    user: AbstractUser
    table: Table
    model: type[GeneratedTableModel]
    fields: Iterable[Field]
    rule: DateDependency


@pytest.mark.django_db
def test_date_dependency_handler_create_rule_serializer(
    data_fixture, premium_data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_rules_handler = FieldRuleHandler(table, user)
    rule_type = field_rules_handler.get_type_handler("date_dependency")
    assert isinstance(rule_type, DateDependencyFieldRuleType)
    serializer_cls = rule_type.get_serializer_class(request_serializer=True)
    serializer = serializer_cls(context={"table": table}, data={})
    assert not serializer.is_valid(raise_exception=False)
    assert set(serializer.errors.keys()) == set(["is_active"])

    invalid_fields_payload = {
        "is_active": True,
        "start_date_field_id": 100,
        "end_date_field_id": 200,
        "duration_field_id": 300,
    }
    serializer = serializer_cls(data=invalid_fields_payload, context={"table": table})

    assert not serializer.is_valid(raise_exception=False)
    assert set(serializer.errors.keys()) == set(
        ["start_date_field_id", "end_date_field_id", "duration_field_id"]
    )

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field", duration_format="d h"
    )

    text_field = data_fixture.create_text_field(table=table, name="text_field")
    invalid_payload = {
        "is_active": True,
        "start_date_field_id": text_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    serializer = serializer_cls(data=invalid_payload, context={"table": table})

    assert not serializer.is_valid(raise_exception=False)
    assert set(serializer.errors.keys()) == set(["start_date_field_id"])

    valid_payload = {
        "is_active": True,
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }
    serializer = serializer_cls(data=valid_payload, context={"table": table})
    assert serializer.is_valid(raise_exception=False)


@pytest.mark.django_db
def test_date_dependency_handler_create_rule_no_license(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_rules_handler = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field"
    )

    valid_payload = {
        "is_active": True,
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    with pytest.raises(FeaturesNotAvailableError):
        field_rules_handler.create_rule("date_dependency", valid_payload)


@pytest.mark.django_db
def test_date_dependency_handler_create_rule_no_duplicate(
    data_fixture, enable_enterprise, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_rules_handler = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field", duration_format="d h"
    )

    valid_payload = {
        "is_active": True,
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }
    assert table.field_rules.count() == 0
    rule = field_rules_handler.create_rule("date_dependency", valid_payload)

    assert rule
    assert table.field_rules.count() == 1

    # 4 queries:
    # * one to check if there's a rule
    # * one per field in serializer to get field's details
    with django_assert_num_queries(4) as queries:
        with pytest.raises(FieldRuleAlreadyExistsError):
            field_rules_handler.create_rule("date_dependency", valid_payload)

    assert table.field_rules.count() == 1


@pytest.mark.django_db
def test_date_dependency_handler_create_rule(data_fixture, enable_enterprise):
    user = data_fixture.create_user()

    table = data_fixture.create_database_table(user=user)

    field_rules_handler = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field", duration_format="d h"
    )

    valid_payload = {
        "is_active": True,
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    rule = field_rules_handler.create_rule("date_dependency", valid_payload)

    assert isinstance(rule, DateDependency)
    assert rule.is_active
    assert rule.is_valid
    assert rule.start_date_field_id == start_date_field.id
    assert rule.end_date_field_id == end_date_field.id
    assert rule.duration_field_id == duration_field.id


@pytest.mark.django_db
def test_date_dependency_handler_validate_rule_after_field_change(
    data_fixture, enable_enterprise
):
    user = data_fixture.create_user()

    table = data_fixture.create_database_table(user=user)

    field_rules_handler = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field", duration_format="d h"
    )

    valid_payload = {
        "is_active": True,
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    rule = field_rules_handler.create_rule("date_dependency", valid_payload)
    assert isinstance(rule, DateDependency)
    assert rule.is_active
    assert rule.is_valid
    assert rule.start_date_field_id == start_date_field.id
    assert rule.end_date_field_id == end_date_field.id
    assert rule.duration_field_id == duration_field.id

    FieldHandler().update_field(user, start_date_field, new_type_name="text")

    rule.refresh_from_db()
    assert rule.is_active
    # not valid after field type change
    assert not rule.is_valid
    assert rule.start_date_field_id == start_date_field.id
    assert rule.end_date_field_id == end_date_field.id
    assert rule.duration_field_id == duration_field.id


@pytest.mark.django_db
def test_date_dependency_handler_validate_rule_after_field_removed(
    data_fixture, enable_enterprise, django_assert_num_queries
):
    user = data_fixture.create_user()

    table = data_fixture.create_database_table(user=user)

    field_rules_handler = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field", duration_format="d h"
    )

    valid_payload = {
        "is_active": True,
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    rule = field_rules_handler.create_rule("date_dependency", valid_payload)
    assert isinstance(rule, DateDependency)
    assert rule.is_active
    assert rule.is_valid
    assert rule.start_date_field_id == start_date_field.id
    assert rule.end_date_field_id == end_date_field.id
    assert rule.duration_field_id == duration_field.id

    FieldHandler().delete_field(user, start_date_field)

    rule.refresh_from_db()
    assert rule.is_active
    # not valid after field type change
    assert not rule.is_valid
    assert rule.start_date_field_id == start_date_field.id
    assert rule.end_date_field_id == end_date_field.id
    assert rule.duration_field_id == duration_field.id


@pytest.mark.parametrize(
    "include_weekends,expected",
    [
        (
            True,
            {
                "a": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=5),
                    True,
                ),
                "b": (
                    None,
                    date(2025, 1, 5),
                    None,
                    False,
                ),
                "c": (
                    date(2025, 1, 1),
                    None,
                    None,
                    False,
                ),
                "d": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=5),
                    True,
                ),
                "e": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=5),
                    True,
                ),
                "f": (
                    None,
                    date(2025, 1, 5),
                    timedelta(days=4),
                    False,
                ),
                "g": (
                    date(2025, 1, 5),
                    None,
                    timedelta(days=4),
                    False,
                ),
                "h": (
                    None,
                    None,
                    timedelta(days=4),
                    False,
                ),
                "i": (
                    None,
                    None,
                    None,
                    False,
                ),
                "j": (date(2025, 1, 10), date(2025, 1, 5), timedelta(days=5), False),
                "k": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=5),
                    True,
                ),
            },
        ),
    ],
)
@pytest.mark.django_db
def test_date_dependency_handler_create_rule_and_populate_rows(
    data_fixture, enable_enterprise, include_weekends, expected
):
    user = data_fixture.create_user()

    table = data_fixture.create_database_table(user=user)

    field_rules_handler = FieldRuleHandler(table, user)

    text_field = data_fixture.create_text_field(
        table=table, name="text_field", primary=True
    )
    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field", duration_format="d h"
    )
    data = [
        ["a", "2025-01-01", "2025-01-05", None],
        ["b", None, "2025-01-05", None],
        ["c", "2025-01-01", None, None],
        ["d", "2025-01-01", "2025-01-05", "4d 0h"],
        ["e", "2025-01-01", "2025-01-05", "5d 0h"],
        ["f", None, "2025-01-05", "4d 0h"],
        ["g", "2025-01-05", None, "4d 0h"],
        ["h", None, None, "4d 0h"],
        ["i", None, None, None],
        ["j", "2025-01-10", "2025-01-05", "5d 0h"],
        ["k", "2025-01-01", "2025-01-05", "-5d 0h"],
    ]
    model = table.get_model()
    RowHandler().import_rows(
        user, table=table, data=data, send_realtime_update=False, validate=False
    )
    rows_inserted = list(model.objects.all())

    assert len(rows_inserted) == len(data) == len(expected.keys())

    valid_payload = {
        "is_active": True,
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }
    with mock.patch(
        "baserow_enterprise.date_dependency.field_rule_types.DateDependencyFieldRuleType.schedule_recalculate"
    ) as mocked_task:
        rule = field_rules_handler.create_rule("date_dependency", valid_payload)
        mocked_task.assert_called_once()

    from baserow_enterprise.date_dependency.tasks import (
        date_dependency_recalculate_rows,
    )

    # Normally this will be executed as a Celery task scheduled at the end of the
    # current transaction, but we're in test, so need to call this manually.
    date_dependency_recalculate_rows(rule_id=rule.id, table_id=table.id)

    assert isinstance(rule, DateDependency)
    assert rule.is_active
    assert rule.is_valid
    assert rule.start_date_field_id == start_date_field.id
    assert rule.end_date_field_id == end_date_field.id
    assert rule.duration_field_id == duration_field.id

    rows_after_rule = list(model.objects.all())
    for row in rows_after_rule:
        row_id = getattr(row, text_field.db_column)
        start_date = getattr(row, start_date_field.db_column)
        end_date = getattr(row, end_date_field.db_column)
        duration = getattr(row, duration_field.db_column)
        is_valid = getattr(row, "field_rules_are_valid")

        expected_row = expected.get(row_id)
        assert (
            row_id,
            start_date,
            end_date,
            duration,
            is_valid,
        ) == (row_id, *expected_row)


@pytest.mark.django_db
def test_date_dependency_update_cascade_multi_root_and_leaf(
    data_fixture, enable_enterprise, django_capture_on_commit_callbacks
):
    """ test if moving A1 will move B2 and A3

     A1 -- A2 - A3
          / \
     B1 -+  +-B2
    """

    data = [
        # text, start, end, duration, linkrow
        ["A1", "2025-05-10", "2025-05-11", "2d 0h", []],
        ["B1", "2025-05-10", "2025-05-11", "2d 0h", []],
        ["A2", "2025-05-10", "2025-05-11", "2d 0h", ["A1", "B1"]],
        ["A3", "2025-05-10", "2025-05-11", "2d 0h", ["A2"]],
        ["B2", "2025-05-10", "2025-05-11", "2d 0h", ["A2"]],
    ]

    user, table, model, fields, rule = create_date_dependency_table(
        data_fixture, data, django_capture_on_commit_callbacks
    )
    text, start, end, duration, linkrow = fields
    update_data = [{"id": 1, start.db_column: "2025-05-12"}]

    initial_rows = list(model.objects.all())
    assert len(data) == len(initial_rows)
    for row_imported, row_requested in zip(initial_rows, data):
        assert row_imported.get_primary_field_value() == row_requested[0]
        # ensure rows are related
        assert [
            related.get_primary_field_value()
            for related in getattr(row_imported, linkrow.db_column).all()
        ] == row_requested[-1]

    updated = RowHandler().update_rows(
        user,
        table,
        update_data,
        model,
        send_realtime_update=False,
        send_webhook_events=False,
        skip_search_update=True,
    )

    assert len(updated.updated_rows) == 1
    updated_row = updated.updated_rows[0]

    assert updated_row.id == 1
    assert updated_row.get_primary_field_value() == "A1"
    assert getattr(updated_row, start.db_column) == date(2025, 5, 12)
    assert getattr(updated_row, end.db_column) == date(2025, 5, 13)
    assert getattr(updated_row, duration.db_column) == timedelta(days=2)

    assert len(updated.cascade_update.row_ids) == 3

    expected_updated_rows = {
        3: {"start_date": date(2025, 5, 14), "end_date": date(2025, 5, 15)},
        4: {"start_date": date(2025, 5, 16), "end_date": date(2025, 5, 17)},
        5: {"start_date": date(2025, 5, 16), "end_date": date(2025, 5, 17)},
    }

    assert set(updated.cascade_update.row_ids) == set(expected_updated_rows.keys())

    for updated_row in updated.cascade_update.updated_rows:
        date_value = DateValues.from_row(updated_row, rule)
        expected = expected_updated_rows[updated_row.id]
        assert date_value.start_date == expected["start_date"]
        assert date_value.end_date == expected["end_date"]


@pytest.mark.django_db
def test_date_dependency_update_cascade_multi_root(
    data_fixture, enable_enterprise, django_capture_on_commit_callbacks
):
    data = [
        # text, start, end, duration, linkrow
        ["R1", "2025-05-10", "2025-05-11", "2d 0h", []],
        ["R2", "2025-05-10", "2025-05-11", "2d 0h", []],
        ["R3", "2025-05-12", "2025-01-13", "2d 0h", ["R1", "R2"]],
    ]

    user, table, model, fields, rule = create_date_dependency_table(
        data_fixture, data, django_capture_on_commit_callbacks
    )
    text, start, end, duration, linkrow = fields
    update_data = [{"id": 3, start.db_column: "2025-05-10"}]

    initial_rows = list(model.objects.all())
    assert len(data) == len(initial_rows)
    for row_imported, row_requested in zip(initial_rows, data):
        assert row_imported.get_primary_field_value() == row_requested[0]
        # ensure rows are related
        assert [
            related.get_primary_field_value()
            for related in getattr(row_imported, linkrow.db_column).all()
        ] == row_requested[-1]

    updated = RowHandler().update_rows(
        user,
        table,
        update_data,
        model,
        send_realtime_update=False,
        send_webhook_events=False,
        skip_search_update=True,
    )

    assert len(updated.updated_rows) == 1
    updated_row = updated.updated_rows[0]

    assert updated_row.id == 3
    assert updated_row.get_primary_field_value() == "R3"
    assert getattr(updated_row, start.db_column) == date(2025, 5, 10)
    assert getattr(updated_row, end.db_column) == date(2025, 5, 11)
    assert getattr(updated_row, duration.db_column) == timedelta(days=2)

    assert len(updated.cascade_update.row_ids) == 2
    assert set(updated.cascade_update.row_ids) == {1, 2}


@pytest.mark.django_db
def test_date_dependency_update_cascade(
    data_fixture, enable_enterprise, django_capture_on_commit_callbacks
):
    data = [
        # text, start, end, duration, linkrow
        ["root", "2025-01-01", "2025-01-05", None, []],
        ["a1-cascade-updated", "2025-01-06", "2025-01-10", None, ["root"]],
        ["a2-updated", "2025-01-11", "2025-01-15", None, ["a1-cascade-updated"]],
        ["a3-cascade-updated", "2025-01-16", "2025-01-20", None, ["a2-updated"]],
        # a4-invalid won't be updated because dates are invalid
        ["a4-invalid", "2025-01-25", "2025-01-21", "10d 0h", ["a3-cascade-updated"]],
        # a5-skipped won't be updated, because it depends on an invalid row
        ["a5-skipped", "2025-01-24", "2025-01-25", "2d 0h", ["a4-invalid"]],
        # a6-updated will be updated, as it's another leaf
        ["a6-updated", "2025-01-20", "2025-01-25", "4d 0h", ["a3-cascade-updated"]],
    ]

    user, table, model, fields, rule = create_date_dependency_table(
        data_fixture, data, django_capture_on_commit_callbacks
    )
    text, start, end, duration, linkrow = fields
    update_data = [
        {"id": 3, start.db_column: "2025-01-09", end.db_column: "2025-01-16"}
    ]

    initial_rows = list(model.objects.all())
    assert len(data) == len(initial_rows)
    for row_imported, row_requested in zip(initial_rows, data):
        assert row_imported.get_primary_field_value() == row_requested[0]
        # ensure rows are related
        assert [
            related.get_primary_field_value()
            for related in getattr(row_imported, linkrow.db_column).all()
        ] == row_requested[-1]

    updated = RowHandler().update_rows(
        user,
        table,
        update_data,
        model,
        send_realtime_update=False,
        send_webhook_events=False,
        skip_search_update=True,
    )

    assert len(updated.updated_rows) == 1
    updated_row = updated.updated_rows[0]

    assert updated_row.id == 3
    assert updated_row.get_primary_field_value() == "a2-updated"
    assert getattr(updated_row, start.db_column) == date(2025, 1, 9)
    assert getattr(updated_row, end.db_column) == date(2025, 1, 16)
    assert getattr(updated_row, duration.db_column) == timedelta(days=8)

    assert len(updated.cascade_update.row_ids) == 4

    assert set(updated.cascade_update.row_ids) == {1, 2, 4, 7}


def create_date_dependency_table(
    data_fixture, data, django_capture_on_commit_callbacks
) -> DateDepsTestData:
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_rules_handler = FieldRuleHandler(table, user)
    text_field = data_fixture.create_text_field(
        user=user, table=table, name="text_field", primary=True
    )
    start_date_field = data_fixture.create_date_field(
        user=user, table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(
        user=user, table=table, name="end_date_field"
    )
    duration_field = data_fixture.create_duration_field(
        user=user, table=table, name="duration_field", duration_format="d h"
    )
    linkrow_field = data_fixture.create_link_row_field(
        user=user, table=table, name="linkrow_field", link_row_table=table
    )

    field_names = [
        text_field.db_column,
        start_date_field.db_column,
        end_date_field.db_column,
        duration_field.db_column,
        linkrow_field.db_column,
    ]

    model = table.get_model()
    rh = RowHandler()
    create_rows_data = []
    map_refs = {}
    for row_in in data:
        row_data = {k: v for k, v in zip(field_names, row_in)}

        # get parent row ids instead of names
        row_data[linkrow_field.db_column] = [
            map_refs[val] for val in row_data[linkrow_field.db_column]
        ]

        rows_created = rh.create_rows(
            user=user,
            table=table,
            rows_values=[row_data],
            model=model,
            send_realtime_update=False,
            send_webhook_events=False,
        ).created_rows
        row = rows_created[0]

        # allow to map row name to id
        map_refs[getattr(row, text_field.db_column)] = row.id

    rows_inserted = list(model.objects.all())

    assert len(rows_inserted) == len(data)

    valid_payload = {
        "is_active": True,
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
        "dependency_linkrow_field_id": linkrow_field.id,
    }

    with django_capture_on_commit_callbacks(execute=True):
        rule = field_rules_handler.create_rule("date_dependency", valid_payload)

    rule.refresh_from_db()
    assert rule.is_active
    assert rule.is_valid

    fields = (
        text_field,
        start_date_field,
        end_date_field,
        duration_field,
        linkrow_field,
    )

    return DateDepsTestData(
        user,
        table,
        model,
        fields,
        rule,
    )
