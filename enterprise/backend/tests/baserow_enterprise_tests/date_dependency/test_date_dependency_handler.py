from datetime import date, timedelta
from unittest import mock

import pytest
from baserow_premium.license.exceptions import FeaturesNotAvailableError

from baserow.contrib.database.field_rules.handlers import FieldRuleHandler
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow_enterprise.date_dependency.field_rule_types import (
    DateDependencyFieldRuleType,
)
from baserow_enterprise.date_dependency.models import DateDependency


@pytest.mark.django_db
def test_date_dependency_handler_create_rule_serializer(
    data_fixture, premium_data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    fh = FieldRuleHandler(table, user)
    rule_type = fh.get_type_handler("date_dependency")
    assert isinstance(rule_type, DateDependencyFieldRuleType)
    serializer_cls = rule_type.get_serializer_class(request_serializer=True)
    serializer = serializer_cls(context={"table": table}, data={})
    assert not serializer.is_valid(raise_exception=False)
    assert set(serializer.errors.keys()) == set(
        ["start_date_field_id", "end_date_field_id", "duration_field_id"]
    )

    invalid_fields_payload = {
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
        table=table, name="duration_field"
    )

    text_field = data_fixture.create_text_field(table=table, name="text_field")
    invalid_payload = {
        "start_date_field_id": text_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    serializer = serializer_cls(data=invalid_payload, context={"table": table})

    assert not serializer.is_valid(raise_exception=False)
    assert set(serializer.errors.keys()) == set(["start_date_field_id"])

    valid_payload = {
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

    fh = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field"
    )

    valid_payload = {
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    with pytest.raises(FeaturesNotAvailableError):
        fh.create_rule("date_dependency", valid_payload)


@pytest.mark.django_db
def test_date_dependency_handler_create_rule(data_fixture, enable_enterprise):
    user = data_fixture.create_user()

    table = data_fixture.create_database_table(user=user)

    fh = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field"
    )

    valid_payload = {
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    rule = fh.create_rule("date_dependency", valid_payload)
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

    fh = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field"
    )

    valid_payload = {
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    rule = fh.create_rule("date_dependency", valid_payload)
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
    data_fixture, enable_enterprise
):
    user = data_fixture.create_user()

    table = data_fixture.create_database_table(user=user)

    fh = FieldRuleHandler(table, user)

    start_date_field = data_fixture.create_date_field(
        table=table, name="start_date_field"
    )
    end_date_field = data_fixture.create_date_field(table=table, name="end_date_field")
    duration_field = data_fixture.create_duration_field(
        table=table, name="duration_field"
    )

    valid_payload = {
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }

    rule = fh.create_rule("date_dependency", valid_payload)
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
            False,
            {
                "a": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=4),
                ),
                "b": (
                    None,
                    date(2025, 1, 5),
                    None,
                ),
                "c": (
                    date(2025, 1, 1),
                    None,
                    None,
                ),
                "d": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=4),
                ),
                "e": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=4),
                ),
                "f": (
                    None,
                    date(2025, 1, 5),
                    timedelta(days=4),
                ),
                "g": (
                    date(2025, 1, 5),
                    None,
                    timedelta(days=4),
                ),
                "h": (
                    None,
                    None,
                    timedelta(days=4),
                ),
                "i": (
                    None,
                    None,
                    None,
                ),
            },
        ),
        (
            True,
            {
                "a": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=4),
                ),
                "b": (
                    None,
                    date(2025, 1, 5),
                    None,
                ),
                "c": (
                    date(2025, 1, 1),
                    None,
                    None,
                ),
                "d": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=4),
                ),
                "e": (
                    date(2025, 1, 1),
                    date(2025, 1, 5),
                    timedelta(days=4),
                ),
                "f": (
                    None,
                    date(2025, 1, 5),
                    timedelta(days=4),
                ),
                "g": (
                    date(2025, 1, 5),
                    None,
                    timedelta(days=4),
                ),
                "h": (
                    None,
                    None,
                    timedelta(days=4),
                ),
                "i": (
                    None,
                    None,
                    None,
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

    fh = FieldRuleHandler(table, user)

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
    ]
    model = table.get_model()
    RowHandler().import_rows(
        user, table=table, data=data, send_realtime_update=False, validate=False
    )
    rows_inserted = list(model.objects.all())

    assert len(rows_inserted) == len(data) == len(expected.keys())

    valid_payload = {
        "start_date_field_id": start_date_field.id,
        "end_date_field_id": end_date_field.id,
        "duration_field_id": duration_field.id,
    }
    with mock.patch(
        "baserow_enterprise.date_dependency.field_rule_types.DateDependencyFieldRuleType.schedule_recalculate"
    ) as mocked_task:
        rule = fh.create_rule("date_dependency", valid_payload)
        mocked_task.assert_called_once()

    from baserow_enterprise.date_dependency.tasks import (
        date_dependency_recalculate_rows,
    )

    # normally this should be called at the end of transaction
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

        expected_row = expected.get(row_id)
        assert (row_id, start_date, end_date, duration) == (row_id, *expected_row)
