from datetime import datetime
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.db import connection, models, transaction
from django.db.utils import IntegrityError
from django.test.utils import CaptureQueriesContext

import pytest
from baserow_premium.fields.field_types import AIFieldType
from faker import Faker

from baserow.contrib.database.fields.constants import (
    UNIQUE_WITH_EMPTY_CONSTRAINT_NAME,
    UPSERT_OPTION_DICT_KEY,
)
from baserow.contrib.database.fields.exceptions import (
    CannotChangeFieldType,
    CannotDeletePrimaryField,
    FieldDoesNotExist,
    FieldIsAlreadyPrimary,
    FieldNotInTable,
    FieldTypeDoesNotExist,
    FieldWithSameNameAlreadyExists,
    IncompatibleFieldTypeForUniqueValues,
    IncompatiblePrimaryFieldTypeError,
    MaxFieldLimitExceeded,
    MaxFieldNameLengthExceeded,
    PrimaryFieldAlreadyExists,
    ReservedBaserowFieldNameException,
    TableHasNoPrimaryField,
)
from baserow.contrib.database.fields.field_constraints import (
    RatingTypeUniqueWithEmptyConstraint,
    TextTypeUniqueWithEmptyConstraint,
    UniqueWithEmptyConstraint,
)
from baserow.contrib.database.fields.field_helpers import (
    construct_all_possible_field_kwargs,
)
from baserow.contrib.database.fields.field_types import (
    AutonumberFieldType,
    BooleanFieldType,
    CountFieldType,
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
    LookupFieldType,
    MultipleCollaboratorsFieldType,
    MultipleSelectFieldType,
    NumberFieldType,
    PhoneNumberFieldType,
    RatingFieldType,
    RollupFieldType,
    SingleSelectFieldType,
    TextFieldType,
    URLFieldType,
    UUIDFieldType,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    BooleanField,
    Field,
    FormulaField,
    LongTextField,
    NumberField,
    SelectOption,
    TextField,
)
from baserow.contrib.database.fields.registries import (
    field_constraint_registry,
    field_type_registry,
)
from baserow.contrib.database.fields.utils import DeferredForeignKeyUpdater
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import ViewFilter
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.psycopg import is_unique_violation_error
from baserow.core.registries import ImportExportConfig
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import setup_interesting_test_table


@pytest.fixture(autouse=True)
def clean_registry_cache():
    """
    Ensure no patched version stays in cache.
    """

    field_type_registry.get_for_class.cache_clear()
    yield


def _test_can_convert_between_fields(data_fixture, field_type_to_test):
    """
    Tests that field conversion for the provided field_type_to_test works
    in every possible conversion scenario. It only checks that the conversion
    does not raise any exceptions.
    """

    table, user, row, _, _ = setup_interesting_test_table(data_fixture)

    handler = FieldHandler()
    row_handler = RowHandler()
    fake = Faker()

    cache = {}

    # Some baserow field types have multiple different 'modes' which result in
    # different conversion behaviour or entirely different database columns being
    # created. Here the kwargs which control these modes are enumerated so we can then
    # generate every possible type of conversion.
    all_possible_kwargs_per_type = construct_all_possible_field_kwargs(
        table,
        Table.objects.get(name="link_table"),
        Table.objects.get(name="decimal_link_table"),
        Table.objects.get(name="file_link_table"),
        Table.objects.get(name="multiple_collaborators_link_table"),
    )

    i = 1

    def test_field_conversion(
        field_name,
        from_field_type_name,
        from_field_kwargs,
        to_field_type_name,
        to_field_kwargs,
    ):
        nonlocal i

        print(
            f"Converting num {i} from {from_field_type_name} to"
            f" {to_field_type_name}",
            flush=True,
        )

        field_type = field_type_registry.get(from_field_type_name)
        new_name = f"{field_name}_to_{to_field_type_name}_{i}"
        from_field_kwargs["primary"] = False

        from_field = handler.create_field(
            user=user,
            table=table,
            type_name=from_field_type_name,
            name=new_name,
            **{k: v for k, v in from_field_kwargs.items() if k != "name"},
        )
        if not field_type.read_only:
            random_field_value = field_type.random_value(from_field, fake, cache)
            row_handler.update_row_by_id(
                user=user,
                table=table,
                row_id=row.id,
                values={
                    f"field_{from_field.id}": field_type.random_to_input_value(
                        from_field, random_field_value
                    )
                },
            )

        handler.update_field(
            user=user,
            field=from_field,
            new_type_name=to_field_type_name,
            **{k: v for k, v in to_field_kwargs.items() if k != "name"},
        )

        i += 1

        # Check the field metadata is as expected
        new_field_type = field_type_registry.get(to_field_type_name)
        if not isinstance(new_field_type, type(field_type)):
            assert not field_type.model_class.objects.filter(id=from_field.id).exists()
        assert new_field_type.model_class.objects.filter(id=from_field.id).exists()

        # Ensure we can still delete the field afterwards, also by
        # deleting we speedup the test overall by not having a table
        # with 900+ fields.
        handler.delete_field(user, from_field)
        TrashHandler.permanently_delete(from_field)

    for from_field_kwargs in all_possible_kwargs_per_type[field_type_to_test]:
        field_name = from_field_kwargs.pop("name")
        for to_field_type_name, all_kwargs in all_possible_kwargs_per_type.items():
            for to_field_kwargs in all_kwargs:
                # from field_type_to_test to other types
                test_field_conversion(
                    field_name,
                    field_type_to_test,
                    from_field_kwargs,
                    to_field_type_name,
                    to_field_kwargs,
                )
                if field_type_to_test != to_field_type_name:
                    # from other types to field_type_to_test
                    test_field_conversion(
                        field_name,
                        to_field_type_name,
                        to_field_kwargs,
                        field_type_to_test,
                        from_field_kwargs,
                    )


@pytest.mark.field_text
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_text(data_fixture):
    _test_can_convert_between_fields(data_fixture, TextFieldType.type)


@pytest.mark.field_long_text
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_long_text(data_fixture):
    _test_can_convert_between_fields(data_fixture, LongTextFieldType.type)


@pytest.mark.field_url
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_url(data_fixture):
    _test_can_convert_between_fields(data_fixture, URLFieldType.type)


@pytest.mark.field_number
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_number(data_fixture):
    _test_can_convert_between_fields(data_fixture, NumberFieldType.type)


@pytest.mark.field_rating
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_rating(data_fixture):
    _test_can_convert_between_fields(data_fixture, RatingFieldType.type)


@pytest.mark.field_boolean
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_boolean(data_fixture):
    _test_can_convert_between_fields(data_fixture, BooleanFieldType.type)


@pytest.mark.field_date
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_date(data_fixture):
    _test_can_convert_between_fields(data_fixture, DateFieldType.type)


@pytest.mark.field_created_on
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_created_on(data_fixture):
    _test_can_convert_between_fields(data_fixture, CreatedOnFieldType.type)


@pytest.mark.field_last_modified
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_last_modified(data_fixture):
    _test_can_convert_between_fields(data_fixture, LastModifiedFieldType.type)


@pytest.mark.field_email
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_email(data_fixture):
    _test_can_convert_between_fields(data_fixture, EmailFieldType.type)


@pytest.mark.field_phone_number
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_phone_number(data_fixture):
    _test_can_convert_between_fields(data_fixture, PhoneNumberFieldType.type)


@pytest.mark.field_count
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_count(data_fixture):
    _test_can_convert_between_fields(data_fixture, CountFieldType.type)


@pytest.mark.field_rollup
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_rollup(data_fixture):
    _test_can_convert_between_fields(data_fixture, RollupFieldType.type)


@pytest.mark.field_lookup
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_lookup(data_fixture):
    _test_can_convert_between_fields(data_fixture, LookupFieldType.type)


@pytest.mark.field_uuid
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_uuid(data_fixture):
    _test_can_convert_between_fields(data_fixture, UUIDFieldType.type)


@pytest.mark.field_file
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_file(data_fixture):
    _test_can_convert_between_fields(data_fixture, FileFieldType.type)


@pytest.mark.field_single_select
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_single_select(data_fixture):
    _test_can_convert_between_fields(data_fixture, SingleSelectFieldType.type)


@pytest.mark.field_multiple_select
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_multiple_select(data_fixture):
    _test_can_convert_between_fields(data_fixture, MultipleSelectFieldType.type)


@pytest.mark.field_link_row
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_link_row(data_fixture):
    _test_can_convert_between_fields(data_fixture, LinkRowFieldType.type)


@pytest.mark.field_formula
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_formula(data_fixture):
    _test_can_convert_between_fields(data_fixture, FormulaFieldType.type)


@pytest.mark.field_multiple_collaborators
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_multiple_collaborators(data_fixture):
    _test_can_convert_between_fields(data_fixture, MultipleCollaboratorsFieldType.type)


@pytest.mark.field_last_modified_by
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_last_modified_by(data_fixture):
    _test_can_convert_between_fields(data_fixture, LastModifiedByFieldType.type)


@pytest.mark.field_created_by
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_created_by(data_fixture):
    _test_can_convert_between_fields(data_fixture, CreatedByFieldType.type)


@pytest.mark.field_autonumber
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_autonumber(data_fixture):
    _test_can_convert_between_fields(data_fixture, AutonumberFieldType.type)


@pytest.mark.field_ai
@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_field_conversion_ai(data_fixture):
    _test_can_convert_between_fields(data_fixture, AIFieldType.type)


@pytest.mark.django_db
def test_get_field(data_fixture):
    user = data_fixture.create_user()
    data_fixture.create_user()
    text = data_fixture.create_text_field(user=user)

    handler = FieldHandler()

    with pytest.raises(FieldDoesNotExist):
        handler.get_field(field_id=99999)

    field = handler.get_field(field_id=text.id)

    assert text.id == field.id
    assert text.name == field.name
    assert isinstance(field, Field)

    field = handler.get_field(field_id=text.id, field_model=TextField)

    assert text.id == field.id
    assert text.name == field.name
    assert isinstance(field, TextField)

    # If the error is raised we know for sure that the query has resolved.
    with pytest.raises(AttributeError):
        handler.get_field(
            field_id=text.id, base_queryset=Field.objects.prefetch_related("UNKNOWN")
        )


@pytest.mark.django_db
def test_get_fields(data_fixture):
    user = data_fixture.create_user()
    data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text = data_fixture.create_text_field(table=table)
    number = data_fixture.create_number_field(table=table)

    handler = FieldHandler()
    assert set(handler.get_fields(table, specific=True)) == {number, text}
    assert set(handler.get_fields(table, specific=False)) == {
        number.field_ptr,
        text.field_ptr,
    }
    assert handler.get_fields(
        table, table.field_set.filter(id=number.id), specific=True
    ) == [number]


@pytest.mark.django_db
@patch("baserow.contrib.database.fields.signals.field_created.send")
def test_create_field(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Test text field",
        text_default="Some default",
    )

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["field"].id == field.id
    assert send_mock.call_args[1]["user"].id == user.id

    assert Field.objects.all().count() == 1
    assert TextField.objects.all().count() == 1

    text_field = TextField.objects.all().first()
    assert text_field.name == "Test text field"
    assert text_field.order == 1
    assert text_field.table == table
    assert text_field.text_default == "Some default"
    assert not text_field.primary

    table_model = table.get_model()
    field_name = f"field_{text_field.id}"
    assert field_name in [field.name for field in table_model._meta.get_fields()]

    instance = table_model.objects.create(**{field_name: "Test 1"})
    assert getattr(instance, field_name) == "Test 1"

    instance_2 = table_model.objects.create()
    assert getattr(instance_2, field_name) == "Some default"

    with pytest.raises(ValueError):
        handler.create_field(
            user=user,
            table=table,
            type_name="number",
            name="Test decimal with oversized decimal places value",
            number_decimal_places=9999,
        )

    handler.create_field(
        user=user,
        table=table,
        type_name="number",
        name="Test number field",
        number_decimal_places=0,
        number_negative=True,
    )

    number_field = NumberField.objects.all().first()
    assert number_field.name == "Test number field"
    assert number_field.order == 2
    assert number_field.table == table
    assert number_field.number_decimal_places == 0
    assert number_field.number_negative

    handler.create_field(
        user=user,
        table=table,
        type_name="boolean",
        name="Test boolean field",
        random_other_field="WILL_BE_IGNORED",
    )

    boolean_field = BooleanField.objects.all().first()
    assert boolean_field.name == "Test boolean field"
    assert boolean_field.order == 3
    assert boolean_field.table == table

    assert Field.objects.all().count() == 3
    assert TextField.objects.all().count() == 1
    assert NumberField.objects.all().count() == 1
    assert BooleanField.objects.all().count() == 1

    with pytest.raises(FieldWithSameNameAlreadyExists):
        handler.create_field(
            user=user, table=table, type_name="boolean", name=boolean_field.name
        )

    with pytest.raises(ReservedBaserowFieldNameException):
        handler.create_field(user=user, table=table, type_name="boolean", name="order")

    with pytest.raises(ReservedBaserowFieldNameException):
        handler.create_field(user=user, table=table, type_name="boolean", name="id")

    field_limit = settings.MAX_FIELD_LIMIT
    settings.MAX_FIELD_LIMIT = 2

    with pytest.raises(MaxFieldLimitExceeded):
        handler.create_field(
            user=user,
            table=table,
            type_name="text",
            name="Test text field",
            text_default="Some default",
        )

    settings.MAX_FIELD_LIMIT = field_limit

    with pytest.raises(UserNotInWorkspace):
        handler.create_field(user=user_2, table=table, type_name="text")

    with pytest.raises(FieldTypeDoesNotExist):
        handler.create_field(user=user, table=table, type_name="UNKNOWN")

    too_long_field_name = "x" * 256
    field_name_with_ok_length = "x" * 255

    with pytest.raises(MaxFieldNameLengthExceeded):
        handler.create_field(
            user=user,
            table=table,
            type_name="text",
            name=too_long_field_name,
            text_default="Some default",
        )

    field_with_max_length_name = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name=field_name_with_ok_length,
        text_default="Some default",
    )
    assert getattr(field_with_max_length_name, "name") == field_name_with_ok_length


@pytest.mark.django_db
def test_create_primary_field(data_fixture):
    user = data_fixture.create_user()
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table_1, primary=True)

    with pytest.raises(PrimaryFieldAlreadyExists):
        handler = FieldHandler()
        handler.create_field(
            user=user, table=table_1, type_name="text", primary=True, name="test"
        )

    handler = FieldHandler()
    field = handler.create_field(
        user=user, table=table_2, type_name="text", primary=True, name="primary"
    )

    assert field.primary

    with pytest.raises(PrimaryFieldAlreadyExists):
        handler.create_field(
            user=user, table=table_2, type_name="text", primary=True, name="new_primary"
        )

    # Should be able to create a regular field when there is already a primary field.
    handler.create_field(
        user=user, table=table_2, type_name="text", primary=False, name="non_primary"
    )


@pytest.mark.django_db
@patch("baserow.contrib.database.fields.signals.field_updated.send")
def test_update_field(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, order=0)
    field = data_fixture.create_text_field(table=table, order=1)

    handler = FieldHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.update_field(user=user_2, field=field)

    with pytest.raises(ValueError):
        handler.update_field(user=user, field=object())

    with pytest.raises(FieldTypeDoesNotExist):
        handler.update_field(user=user, field=field, new_type_name="NOT_EXISTING")

    # The link row field is not compatible with a primary field so an exception
    # is expected.
    field.primary = True
    field.save()
    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        handler.update_field(user=user, field=field, new_type_name="link_row")
    field.primary = False
    field.save()

    # Change some values of the text field and test if they have been changed.
    field = handler.update_field(
        user=user, field=field, name="Text field", text_default="Default value"
    )

    assert field.name == "Text field"
    assert field.text_default == "Default value"
    assert isinstance(field, TextField)

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["field"].id == field.id
    assert send_mock.call_args[1]["user"].id == user.id

    # Insert some rows to the table which should be converted later.
    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "Text value"})
    model.objects.create(**{f"field_{field.id}": "100.22"})
    model.objects.create(**{f"field_{field.id}": "10"})

    # Change the field type to a number and test if the values have been changed.
    field = handler.update_field(
        user=user,
        field=field,
        new_type_name="number",
        name="Number field",
        number_decimal_places=0,
        number_negative=False,
    )

    assert field.name == "Number field"
    assert field.number_decimal_places == 0
    assert field.number_negative is False
    assert not hasattr(field, "text_default")

    model = table.get_model()
    row_0, row_1, row_2 = model.objects.all()

    assert getattr(row_0, f"field_{field.id}") is None
    assert getattr(row_1, f"field_{field.id}") == 100
    assert getattr(row_2, f"field_{field.id}") == 10

    # Change the field type to a decimal and test if the values have been changed.
    field = handler.update_field(
        user=user,
        field=field,
        new_type_name="number",
        name="Price field",
        number_decimal_places=2,
        number_negative=True,
    )

    assert field.name == "Price field"
    assert field.number_decimal_places == 2
    assert field.number_negative is True

    model = table.get_model()
    row_0, row_1, row_2 = model.objects.all()
    assert getattr(row_0, f"field_{field.id}") is None
    assert getattr(row_1, f"field_{field.id}") == Decimal("100.00")
    assert getattr(row_2, f"field_{field.id}") == Decimal("10.00")

    # Change the field type to a boolean and test if the values have been changed.
    field = handler.update_field(
        user=user, field=field, new_type_name="boolean", name="Active"
    )

    field.refresh_from_db()
    assert field.name == "Active"
    assert not hasattr(field, "number_decimal_places")
    assert not hasattr(field, "number_negative")

    model = table.get_model()
    row_0, row_1, row_2 = model.objects.all()
    assert getattr(row_0, f"field_{field.id}") is False
    assert getattr(row_1, f"field_{field.id}") is False
    assert getattr(row_2, f"field_{field.id}") is False

    with pytest.raises(ReservedBaserowFieldNameException):
        handler.update_field(user=user, field=field, name="order")

    with pytest.raises(ReservedBaserowFieldNameException):
        handler.update_field(user=user, field=field, name="id")

    field_2 = data_fixture.create_text_field(table=table, order=1)
    with pytest.raises(FieldWithSameNameAlreadyExists):
        handler.update_field(user=user, field=field_2, name=field.name)

    too_long_field_name = "x" * 256
    field_name_with_ok_length = "x" * 255

    field_3 = data_fixture.create_text_field(table=table)
    with pytest.raises(MaxFieldNameLengthExceeded):
        handler.update_field(
            user=user,
            field=field_3,
            name=too_long_field_name,
        )

    field_with_max_length_name = handler.update_field(
        user=user,
        field=field_3,
        name=field_name_with_ok_length,
    )
    assert getattr(field_with_max_length_name, "name") == field_name_with_ok_length


@pytest.mark.django_db
@pytest.mark.field_formula
@patch("baserow.contrib.database.fields.signals.field_updated.send")
def test_update_field_reset_filter_formula_field(send_mock, data_fixture):
    """
    When there is a field change changing the underlying database
    type of the field, the update_field() method should initiate
    a cleanup for affected views. Formula fields can be in this
    situation when the formula expression changes.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_formula_field(table=table, order=1, formula="today()")
    view = data_fixture.create_grid_view(table=table)
    # create a view filter that won't be compatible with the new type
    data_fixture.create_view_filter(
        view=view, field=field, type="date_equals_today", value="UTC?"
    )
    model = table.get_model()
    model.objects.create()
    handler = FieldHandler()

    field = handler.update_field(
        user=user,
        field=field,
        new_type_name="formula",
        formula="1",
    )

    field.refresh_from_db()
    rows = model.objects.all()
    assert getattr(rows[0], f"field_{field.id}") == Decimal("1")
    # incompatible filter has been removed
    assert ViewFilter.objects.filter(view=view).count() == 0


# This failing field type triggers the CannotChangeFieldType error if a field is
# changed into this type.
class FailingFieldType(TextFieldType):
    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        return "p_in::NOT_VALID_SQL_SO_IT_WILL_FAIL("


@pytest.mark.django_db
def test_update_field_failing(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, order=1)

    handler = FieldHandler()

    with patch.dict(field_type_registry.registry, {"text": FailingFieldType()}):
        # Need to clear the cache again
        field_type_registry.get_for_class.cache_clear()

        with pytest.raises(CannotChangeFieldType):
            handler.update_field(user=user, field=field, new_type_name="text")

    handler.update_field(user, field=field, new_type_name="text")
    assert Field.objects.all().count() == 1
    assert TextField.objects.all().count() == 1


@pytest.mark.django_db
def test_update_field_when_underlying_sql_type_doesnt_change(data_fixture):
    class AlwaysLowercaseTextField(TextFieldType):
        type = "lowercase_text"
        model_class = LongTextField

        def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
            return """p_in = (lower(p_in));"""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_text_field = data_fixture.create_text_field(table=table, order=1)

    model = table.get_model()

    field_name = f"field_{existing_text_field.id}"
    row = model.objects.create(
        **{
            field_name: "Test",
        }
    )

    handler = FieldHandler()

    with patch.dict(
        field_type_registry.registry, {"lowercase_text": AlwaysLowercaseTextField()}
    ):
        # Need to clear the cache again
        field_type_registry.get_for_class.cache_clear()

        handler.update_field(
            user=user, field=existing_text_field, new_type_name="lowercase_text"
        )

        row.refresh_from_db()
        assert getattr(row, field_name) == "test"
        assert Field.objects.all().count() == 1
        assert TextField.objects.all().count() == 0
        assert LongTextField.objects.all().count() == 1


class ReversingTextFieldUsingBothVarCharAndTextSqlTypes(TextFieldType):
    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        return """p_in = (reverse(p_in));"""

    def get_model_field(self, instance, **kwargs):
        kwargs["null"] = True
        kwargs["blank"] = True
        if instance.text_default == "use_other_sql_type":
            return models.TextField(**kwargs)
        else:
            return models.CharField(**kwargs)


@pytest.mark.django_db
def test_field_which_changes_its_underlying_type_will_have_alter_sql_run(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_text_field = data_fixture.create_text_field(table=table, order=1)

    model = table.get_model()

    field_name = f"field_{existing_text_field.id}"
    row = model.objects.create(
        **{
            field_name: "Test",
        }
    )

    handler = FieldHandler()

    with patch.dict(
        field_type_registry.registry,
        {"text": ReversingTextFieldUsingBothVarCharAndTextSqlTypes()},
    ):
        # Need to clear the cache again
        field_type_registry.get_for_class.cache_clear()

        # Update to the same baserow type, but due to this fields implementation of
        # get_model_field this will alter the underlying database column from type
        # of varchar to text, which should make our reversing alter sql run.
        handler.update_field(
            user=user,
            field=existing_text_field,
            new_type_name="text",
            text_default="use_other_sql_type",
        )

        row.refresh_from_db()
        assert getattr(row, field_name) == "tseT"
        assert Field.objects.all().count() == 1
        assert TextField.objects.all().count() == 1


class AlwaysReverseOnUpdateField(TextFieldType):
    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        return """p_in = (reverse(p_in));"""


@pytest.mark.django_db
def test_just_changing_a_fields_name_will_not_run_alter_sql(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_text_field = data_fixture.create_text_field(table=table, order=1)

    model = table.get_model()

    field_name = f"field_{existing_text_field.id}"
    row = model.objects.create(
        **{
            field_name: "Test",
        }
    )

    handler = FieldHandler()

    with patch.dict(
        field_type_registry.registry, {"text": AlwaysReverseOnUpdateField()}
    ):
        # Need to clear the cache again
        field_type_registry.get_for_class.cache_clear()

        handler.update_field(
            user=user, field=existing_text_field, new_type_name="text", name="new_name"
        )

        row.refresh_from_db()
        # The field has not been reversed as just the name changed!
        assert getattr(row, field_name) == "Test"
        assert Field.objects.all().count() == 1
        assert TextField.objects.all().count() == 1


class SameTypeAlwaysReverseOnUpdateField(TextFieldType):
    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        return """p_in = (reverse(p_in));"""

    def force_same_type_alter_column(self, from_field, to_field):
        return True


@pytest.mark.django_db
def test_when_field_type_forces_same_type_alter_fields_alter_sql_is_run(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_text_field = data_fixture.create_text_field(table=table, order=1)

    model = table.get_model()

    field_name = f"field_{existing_text_field.id}"
    row = model.objects.create(
        **{
            field_name: "Test",
        }
    )

    handler = FieldHandler()

    with patch.dict(
        field_type_registry.registry, {"text": SameTypeAlwaysReverseOnUpdateField()}
    ):
        # Need to clear the cache again
        field_type_registry.get_for_class.cache_clear()

        handler.update_field(
            user=user,
            field=existing_text_field,
            new_type_name="text",
            name="new_name",
        )

        row.refresh_from_db()
        # The alter sql has been run due to the force override
        assert getattr(row, field_name) == "tseT"
        assert Field.objects.all().count() == 1
        assert TextField.objects.all().count() == 1


@pytest.mark.django_db
def test_update_field_with_type_error_on_conversion_should_null_field(data_fixture):
    class AlwaysThrowsSqlExceptionOnConversionField(TextFieldType):
        type = "throws_field"
        model_class = LongTextField

        def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
            return """p_in = (lower(p_in::numeric::text));"""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_text_field = data_fixture.create_text_field(table=table, order=1)

    model = table.get_model()

    field_name = f"field_{existing_text_field.id}"
    row = model.objects.create(
        **{
            field_name: "Test",
        }
    )

    handler = FieldHandler()

    with patch.dict(
        field_type_registry.registry,
        {"throws_field": AlwaysThrowsSqlExceptionOnConversionField()},
    ):
        # Need to clear the cache again
        field_type_registry.get_for_class.cache_clear()

        handler.update_field(
            user=user, field=existing_text_field, new_type_name="throws_field"
        )

        row.refresh_from_db()
        assert getattr(row, field_name) is None
        assert Field.objects.all().count() == 1
        assert TextField.objects.all().count() == 0
        assert LongTextField.objects.all().count() == 1


class ReversesWhenConvertsAwayTextField(LongTextFieldType):
    type = "reserves_text"
    model_class = LongTextField

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        return """p_in = concat(reverse(p_in), %(some_variable)s);""", {
            "some_variable": "_POST_FIX"
        }


class AlwaysLowercaseTextField(TextFieldType):
    model_class = LongTextField

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        return """p_in = concat(%(other_variable)s, lower(p_in));""", {
            "other_variable": "pre_fix_"
        }


@pytest.mark.django_db
def test_update_field_when_underlying_sql_type_doesnt_change_with_vars(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_field_with_old_value_prep = data_fixture.create_long_text_field(
        table=table
    )

    model = table.get_model()

    field_name = f"field_{existing_field_with_old_value_prep.id}"
    row = model.objects.create(
        **{
            field_name: "Test",
        }
    )

    handler = FieldHandler()

    with patch.dict(
        field_type_registry.registry,
        {
            "lowercase_text": AlwaysLowercaseTextField(),
            "long_text": ReversesWhenConvertsAwayTextField(),
        },
    ):
        # Need to clear the cache again
        field_type_registry.get_for_class.cache_clear()

        handler.update_field(
            user=user,
            field=existing_field_with_old_value_prep,
            new_type_name="lowercase_text",
        )

        row.refresh_from_db()
        assert getattr(row, field_name) == "pre_fix_tset_post_fix"
        assert Field.objects.all().count() == 1
        assert TextField.objects.all().count() == 0
        assert LongTextField.objects.all().count() == 1


class ReversesWhenConvertsAwayTextField2(LongTextFieldType):
    model_class = LongTextField

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        return """p_in = (reverse(p_in));"""


class AlwaysLowercaseTextField2(TextFieldType):
    type = "lowercase_text"
    model_class = LongTextField

    def get_alter_column_prepare_new_value(self, connection, from_field, to_field):
        return """p_in = (lower(p_in));"""


@pytest.mark.django_db
def test_update_field_when_underlying_sql_type_doesnt_change_old_prep(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_field_with_old_value_prep = data_fixture.create_long_text_field(
        table=table
    )

    model = table.get_model()

    field_name = f"field_{existing_field_with_old_value_prep.id}"
    row = model.objects.create(
        **{
            field_name: "Test",
        }
    )

    handler = FieldHandler()

    with patch.dict(
        field_type_registry.registry,
        {
            "lowercase_text": AlwaysLowercaseTextField2(),
            "long_text": ReversesWhenConvertsAwayTextField2(),
        },
    ):
        # Need to clear the cache again
        field_type_registry.get_for_class.cache_clear()

        handler.update_field(
            user=user,
            field=existing_field_with_old_value_prep,
            new_type_name="lowercase_text",
        )

        row.refresh_from_db()
        assert getattr(row, field_name) == "tset"
        assert Field.objects.all().count() == 1
        assert TextField.objects.all().count() == 0
        assert LongTextField.objects.all().count() == 1


@pytest.mark.django_db
@patch("baserow.contrib.database.fields.signals.field_deleted.send")
def test_delete_field(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    handler = FieldHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.delete_field(user=user_2, field=text_field)

    with pytest.raises(ValueError):
        handler.delete_field(user=user_2, field=object())

    assert Field.objects.all().count() == 1
    assert TextField.objects.all().count() == 1
    field_id = text_field.id
    handler.delete_field(user=user, field=text_field)
    assert Field.objects.all().count() == 0
    assert Field.trash.all().count() == 1
    assert TextField.objects.all().count() == 0

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["field_id"] == field_id
    assert send_mock.call_args[1]["field"].id == field_id
    assert send_mock.call_args[1]["user"].id == user.id

    primary = data_fixture.create_text_field(table=table, primary=True)
    with pytest.raises(CannotDeletePrimaryField):
        handler.delete_field(user=user, field=primary)


@pytest.mark.django_db
def test_update_select_options(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_single_select_field(table=table)
    field_2 = data_fixture.create_single_select_field(table=table)
    data_fixture.create_text_field(table=table)

    handler = FieldHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.update_field_select_options(field=field, user=user_2, select_options=[])

    handler.update_field_select_options(
        field=field,
        user=user,
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "red"},
        ],
    )

    assert SelectOption.objects.all().count() == 2
    select_options = field.select_options.all()
    assert len(select_options) == 2

    assert select_options[0].order == 0
    assert select_options[0].value == "Option 1"
    assert select_options[0].color == "blue"
    assert select_options[0].field_id == field.id

    assert select_options[1].order == 1
    assert select_options[1].value == "Option 2"
    assert select_options[1].color == "red"
    assert select_options[1].field_id == field.id

    handler.update_field_select_options(
        field=field,
        user=user,
        select_options=[
            {"id": select_options[0].id, "value": "Option 1 A", "color": "blue 2"},
            {"id": select_options[1].id, "value": "Option 2 A", "color": "red 2"},
        ],
    )

    assert SelectOption.objects.all().count() == 2
    select_options_2 = field.select_options.all()
    assert len(select_options_2) == 2

    assert select_options_2[0].id == select_options[0].id
    assert select_options_2[0].order == 0
    assert select_options_2[0].value == "Option 1 A"
    assert select_options_2[0].color == "blue 2"
    assert select_options_2[0].field_id == field.id

    assert select_options_2[1].id == select_options[1].id
    assert select_options_2[1].order == 1
    assert select_options_2[1].value == "Option 2 A"
    assert select_options_2[1].color == "red 2"
    assert select_options_2[1].field_id == field.id

    handler.update_field_select_options(
        field=field,
        user=user,
        select_options=[
            {"id": select_options[1].id, "value": "Option 1 B", "color": "red"},
            {"value": "Option 2 B", "color": "green"},
        ],
    )

    assert SelectOption.objects.all().count() == 2
    select_options_3 = field.select_options.all()
    assert len(select_options_3) == 2

    assert select_options_3[0].id == select_options[1].id
    assert select_options_3[0].order == 0
    assert select_options_3[0].value == "Option 1 B"
    assert select_options_3[0].color == "red"
    assert select_options_3[0].field_id == field.id

    assert select_options_3[1].order == 1
    assert select_options_3[1].value == "Option 2 B"
    assert select_options_3[1].color == "green"
    assert select_options_3[1].field_id == field.id

    handler.update_field_select_options(
        field=field_2,
        user=user,
        select_options=[
            {"id": select_options[1].id, "value": "Option 1 B", "color": "red"},
        ],
    )

    assert SelectOption.objects.all().count() == 3
    select_options_4 = field_2.select_options.all()
    assert len(select_options_4) == 1

    assert select_options_4[0].id != select_options[1].id
    assert select_options_4[0].order == 0
    assert select_options_4[0].value == "Option 1 B"
    assert select_options_4[0].color == "red"
    assert select_options_4[0].field_id == field_2.id

    handler.update_field_select_options(field=field_2, user=user, select_options=[])

    assert SelectOption.objects.all().count() == 2
    assert field_2.select_options.all().count() == 0


@pytest.mark.django_db
def test_can_create_single_select_options_with_specific_pk(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_single_select_field(table=table)

    # Test that no changes are reported when the values passed in are the same as the
    # existing values
    FieldHandler().update_field_select_options(
        field=field,
        user=user,
        select_options=[
            {
                UPSERT_OPTION_DICT_KEY: 9999,
                # This other id should be ignored if set.
                "id": 1,
                "value": "Option 1 B",
                "color": "red",
            },
        ],
    )
    created_option = SelectOption.objects.get(pk=9999)
    assert created_option.value == "Option 1 B"
    assert created_option.color == "red"


@pytest.mark.django_db
def test_can_update_single_select_options_with_upsert_key(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_single_select_field(table=table)

    # Test that no changes are reported when the values passed in are the same as the
    # existing values
    FieldHandler().update_field_select_options(
        field=field,
        user=user,
        select_options=[
            {
                UPSERT_OPTION_DICT_KEY: field.id,
                # This other id should be ignored if set.
                "id": 1,
                "value": "Option 1 B",
                "color": "red",
            },
        ],
    )
    created_option = SelectOption.objects.get(pk=field.id)
    assert created_option.value == "Option 1 B"
    assert created_option.color == "red"
    assert SelectOption.objects.count() == 1


@pytest.mark.django_db
def test_find_next_free_field_name(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, order=0)

    data_fixture.create_text_field(name="test", table=table, order=1)
    field_1 = data_fixture.create_text_field(name="field", table=table, order=1)
    data_fixture.create_text_field(name="field 2", table=table, order=1)
    handler = FieldHandler()

    assert handler.find_next_unused_field_name(table, ["test"]) == "test 2"
    assert handler.find_next_unused_field_name(table, ["test", "other"]) == "other"
    assert handler.find_next_unused_field_name(table, ["field"]) == "field 3"

    assert (
        handler.find_next_unused_field_name(table, ["field"], [field_1.id]) == "field"
    )

    data_fixture.create_text_field(name="regex like field [0-9]", table=table, order=1)
    data_fixture.create_text_field(
        name="regex like field [0-9] 2", table=table, order=1
    )
    assert (
        handler.find_next_unused_field_name(table, ["regex like field [0-9]"])
        == "regex like field [0-9] 3"
    )

    assert handler.find_next_unused_field_name(table, ["id"]) == "id 2"


@pytest.mark.django_db
def test_find_next_free_field_name_returns_strings_with_max_length(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    max_field_name_length = Field.get_max_name_length()
    exactly_length_field_name = "x" * max_field_name_length
    too_long_field_name = "x" * (max_field_name_length + 1)

    data_fixture.create_text_field(name=exactly_length_field_name, table=table, order=1)
    handler = FieldHandler()

    # Make sure that the returned string does not exceed the max_field_name_length
    assert (
        len(handler.find_next_unused_field_name(table, [exactly_length_field_name]))
        <= max_field_name_length
    )
    assert (
        len(
            handler.find_next_unused_field_name(
                table, [f"{exactly_length_field_name} - test"]
            )
        )
        <= max_field_name_length
    )
    assert (
        len(handler.find_next_unused_field_name(table, [too_long_field_name]))
        <= max_field_name_length
    )

    initial_name = (
        "xIyV4w3J4J0Zzd5ZIz4eNPucQOa9tS25ULHw2SCr4RDZ9h2AvxYr5nlGRNQR2ir517B3SkZB"
        "nw2eGnBJQAdX8A6QcSCmcbBAnG3BczFytJkHJK7cE6VsAS6tROTg7GOwSQsdImURRwEarrXo"
        "lv9H4bylyJM0bDPkgB4H6apiugZ19X0C9Fw2ed125MJHoFgTZLbJRc6joNyJSOkGkmGhBuIq"
        "RKipRYGzB4oiFKYPx5Xoc8KHTsLqVDQTWwwzhaR"
    )
    expected_name_1 = (
        "xIyV4w3J4J0Zzd5ZIz4eNPucQOa9tS25ULHw2SCr4RDZ9h2AvxYr5nlGRNQR2ir517B3SkZB"
        "nw2eGnBJQAdX8A6QcSCmcbBAnG3BczFytJkHJK7cE6VsAS6tROTg7GOwSQsdImURRwEarrXo"
        "lv9H4bylyJM0bDPkgB4H6apiugZ19X0C9Fw2ed125MJHoFgTZLbJRc6joNyJSOkGkmGhBuIq"
        "RKipRYGzB4oiFKYPx5Xoc8KHTsLqVDQTWwwzh 2"
    )

    expected_name_2 = (
        "xIyV4w3J4J0Zzd5ZIz4eNPucQOa9tS25ULHw2SCr4RDZ9h2AvxYr5nlGRNQR2ir517B3SkZB"
        "nw2eGnBJQAdX8A6QcSCmcbBAnG3BczFytJkHJK7cE6VsAS6tROTg7GOwSQsdImURRwEarrXo"
        "lv9H4bylyJM0bDPkgB4H6apiugZ19X0C9Fw2ed125MJHoFgTZLbJRc6joNyJSOkGkmGhBuIq"
        "RKipRYGzB4oiFKYPx5Xoc8KHTsLqVDQTWwwzh 3"
    )

    data_fixture.create_text_field(name=initial_name, table=table, order=1)

    assert handler.find_next_unused_field_name(table, [initial_name]) == expected_name_1

    data_fixture.create_text_field(name=expected_name_1, table=table, order=1)

    assert handler.find_next_unused_field_name(table, [initial_name]) == expected_name_2


@pytest.mark.django_db
def test_can_convert_formula_to_numeric_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_formula_field = data_fixture.create_formula_field(
        table=table, formula="'1'"
    )

    model = table.get_model()

    field_name = f"field_{existing_formula_field.id}"
    row = RowHandler().create_row(user=user, table=table, model=model)
    assert getattr(row, field_name) == "1"

    handler = FieldHandler()

    # Update to the same baserow type, but due to this fields implementation of
    # get_model_field this will alter the underlying database column from type
    # of varchar to text, which should make our reversing alter sql run.
    handler.update_field(
        user=user,
        field=existing_formula_field,
        new_type_name="number",
        name="Price field",
        number_decimal_places=0,
        number_negative=True,
    )

    row.refresh_from_db()
    assert getattr(row, field_name) == 1
    assert Field.objects.all().count() == 1
    assert NumberField.objects.all().count() == 1
    assert FormulaField.objects.all().count() == 0


@pytest.mark.django_db
def test_get_unique_row_values(data_fixture):
    table = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(table=table, name="text")
    file_field = data_fixture.create_file_field(table=table, name="file")

    model = table.get_model(attribute_names=True)
    model.objects.create(text="value5")
    model.objects.create(text="value1")
    model.objects.create(text="value1,value2")
    model.objects.create(text="value2,value3")
    model.objects.create(text="value4")
    model.objects.create(text="value5")
    model.objects.create(text="value5")
    model.objects.create(text="value3,value5")
    model.objects.create(text="value3,value5")
    model.objects.create(text="")
    model.objects.create(text=None)

    handler = FieldHandler()

    with pytest.raises(IncompatibleFieldTypeForUniqueValues):
        handler.get_unique_row_values(field=file_field, limit=10)

    values = list(handler.get_unique_row_values(field=text_field, limit=10))
    assert values == [
        "value5",
        "value3,value5",
        "value2,value3",
        "value1,value2",
        "value4",
        "value1",
    ]

    values = list(handler.get_unique_row_values(field=text_field, limit=2))
    assert values == ["value5", "value3,value5"]

    values = list(
        handler.get_unique_row_values(
            field=text_field, limit=10, split_comma_separated=True
        )
    )
    assert values == ["value5", "value3", "value2", "value1", "value4"]

    values = list(
        handler.get_unique_row_values(
            field=text_field, limit=2, split_comma_separated=True
        )
    )
    assert values == ["value5", "value3"]


@pytest.mark.django_db
def test_get_unique_row_values_single_select(data_fixture):
    table = data_fixture.create_database_table()
    single_select_field = data_fixture.create_single_select_field(
        table=table, name="single_select"
    )
    option_1 = data_fixture.create_select_option(
        field=single_select_field, value="Option 1"
    )
    option_2 = data_fixture.create_select_option(
        field=single_select_field, value="Option 2"
    )

    model = table.get_model(attribute_names=True)
    model.objects.create(singleselect=option_1)
    model.objects.create(singleselect=option_2)
    model.objects.create(singleselect=option_1)
    model.objects.create(singleselect=option_2)
    model.objects.create(singleselect=option_2)
    model.objects.create(singleselect=option_2)
    model.objects.create()

    handler = FieldHandler()

    # By testing the single select field, we actually test if the
    # `get_alter_column_prepare_old_value` method is being used correctly.
    values = list(handler.get_unique_row_values(field=single_select_field, limit=10))
    assert values == ["Option 2", "Option 1"]


@pytest.mark.django_db(transaction=True)
def test_when_public_field_updated_number_of_queries_does_not_increase_with_amount_of_grid_views(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    visible_field = data_fixture.create_text_field(table=table, order=0, name="b")

    data_fixture.create_grid_view(
        user=user,
        table=table,
        public=True,
    )

    # Warm up the caches
    FieldHandler().update_field(user, visible_field, name="c")

    with CaptureQueriesContext(connection) as captured:
        FieldHandler().update_field(user, visible_field, name="a")

    data_fixture.create_grid_view(
        user=user,
        table=table,
        public=True,
    )

    with django_assert_num_queries(len(captured.captured_queries)):
        FieldHandler().update_field(user, visible_field, name="abc")


@pytest.mark.django_db(transaction=True)
def test_when_public_field_updated_number_of_queries_does_not_increase_with_amount_of_gallery_views(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    visible_field = data_fixture.create_text_field(table=table, order=0, name="b")

    data_fixture.create_gallery_view(
        user=user,
        table=table,
        public=True,
    )

    # Warm up the caches
    FieldHandler().update_field(user, visible_field, name="c")

    with CaptureQueriesContext(connection) as captured:
        FieldHandler().update_field(user, visible_field, name="a")

    data_fixture.create_gallery_view(
        user=user,
        table=table,
        public=True,
    )

    with django_assert_num_queries(len(captured.captured_queries)):
        FieldHandler().update_field(user, visible_field, name="abc")


@pytest.mark.django_db
def test_new_select_options_are_used_when_duplicating_single_select_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_single_select_field(table=table)

    handler = FieldHandler()

    handler.update_field_select_options(
        field=field,
        user=user,
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "red"},
        ],
    )

    original_select_options = list(field.select_options.all())

    RowHandler().create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{field.id}": original_select_options[0].id,
            },
            {
                f"field_{field.id}": original_select_options[1].id,
            },
        ],
    )

    dup_field, _ = handler.duplicate_field(field=field, user=user, duplicate_data=True)

    for row in table.get_model().objects.all():
        assert getattr(row, f"field_{field.pk}") != getattr(
            row, f"field_{dup_field.pk}"
        )


@pytest.mark.django_db
def test_new_select_options_are_used_when_duplicating_multiple_select_field(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_multiple_select_field(table=table)

    handler = FieldHandler()

    handler.update_field_select_options(
        field=field,
        user=user,
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "red"},
        ],
    )

    original_select_options = list(field.select_options.all())

    RowHandler().create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{field.id}": [
                    original_select_options[0].id,
                    original_select_options[1].id,
                ],
            },
            {
                f"field_{field.id}": [original_select_options[1].id],
            },
        ],
    )

    dup_field, _ = handler.duplicate_field(field=field, user=user, duplicate_data=True)

    for row in table.get_model().objects.all():
        assert getattr(row, f"field_{field.pk}") != getattr(
            row, f"field_{dup_field.pk}"
        )


@pytest.mark.django_db
def test_duplicating_link_row_field_properly_resets_pk_sequence_of_new_table(
    data_fixture,
):
    workspace = data_fixture.create_workspace()
    creator = data_fixture.create_user(workspace=workspace)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=creator)

    table_a_primary = table_a.field_set.get(primary=True).specific
    table_a_text_field = FieldHandler().create_field(
        creator, table_a, "text", name="text"
    )
    table_a_row_1 = RowHandler().create_row(
        user=creator,
        table=table_a,
        values={
            f"{link_field.db_column}": [],
            f"{table_a_text_field.db_column}": "1",
        },
    )
    table_a_row_2 = RowHandler().create_row(
        user=creator,
        table=table_a,
        values={
            f"{link_field.db_column}": [],
            f"{table_a_text_field.db_column}": "0",
        },
    )
    table_b_row_1 = RowHandler().create_row(
        user=creator,
        table=table_b,
        values={f"field_{link_field.link_row_related_field_id}": [table_a_row_1.id]},
    )
    table_b_row_2 = RowHandler().create_row(
        user=creator,
        table=table_b,
        values={
            f"field_{link_field.link_row_related_field_id}": [
                table_a_row_1.id,
                table_a_row_2.id,
            ]
        },
    )

    dupe_field, _ = FieldHandler().duplicate_field(
        creator, link_field, duplicate_data=True
    )

    new_row = RowHandler().create_row(
        user=creator,
        table=table_a,
        values={
            f"field_{dupe_field.id}": [
                table_b_row_1.id,
                table_b_row_2.id,
            ]
        },
    )
    linked_vals = set(
        getattr(new_row, dupe_field.db_column).all().values_list("id", flat=True)
    )
    assert table_b_row_1.id in linked_vals
    assert table_b_row_2.id in linked_vals


@pytest.mark.django_db
def test_change_primary_field_different_table(data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)
    table_b = data_fixture.create_database_table(user)

    with pytest.raises(FieldNotInTable):
        FieldHandler().change_primary_field(user, table_b, field_2)


@pytest.mark.django_db
def test_change_primary_field_type_not_primary(data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_password_field(
        user=user, primary=False, table=table_a
    )

    with pytest.raises(IncompatiblePrimaryFieldTypeError):
        FieldHandler().change_primary_field(user, table_a, field_2)


@pytest.mark.django_db
def test_change_primary_field_field_is_already_primary(data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)

    with pytest.raises(FieldIsAlreadyPrimary):
        FieldHandler().change_primary_field(user, table_a, field_1)


@pytest.mark.django_db
def test_change_primary_field_field_no_update_permissions(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    with pytest.raises(UserNotInWorkspace):
        FieldHandler().change_primary_field(user_2, table_a, field_2)


@pytest.mark.django_db
def test_change_primary_field_field_without_primary(data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    with pytest.raises(TableHasNoPrimaryField):
        FieldHandler().change_primary_field(user, table_a, field_2)


@pytest.mark.django_db
def test_change_primary_field_field_with_primary(data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    new_primary, old_primary = FieldHandler().change_primary_field(
        user, table_a, field_2
    )

    assert new_primary.id == field_2.id
    assert new_primary.primary is True
    assert old_primary.id == field_1.id
    assert old_primary.primary is False


@pytest.mark.django_db
def test_change_primary_field_field_with_existing_primary_field(data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)
    data_fixture.create_text_field(user=user, primary=True)

    new_primary, old_primary = FieldHandler().change_primary_field(
        user, table_a, field_2
    )

    assert new_primary.id == field_2.id
    assert new_primary.primary is True
    assert old_primary.id == field_1.id
    assert old_primary.primary is False


@pytest.mark.django_db
@patch("baserow.contrib.database.fields.signals.field_updated.send")
def test_change_primary_field_signal_send(send_mock, data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    new_primary, old_primary = FieldHandler().change_primary_field(
        user, table_a, field_2
    )

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["field"].id == field_2.id
    assert send_mock.call_args[1]["field"].primary is True
    assert send_mock.call_args[1]["old_field"].id == field_2.id
    assert send_mock.call_args[1]["old_field"].primary is False
    assert send_mock.call_args[1]["related_fields"][0].id == field_1.id
    assert send_mock.call_args[1]["related_fields"][0].primary is False


@pytest.mark.django_db
def test_can_change_primary_field_and_update_dependencies(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    orig_prim_b = table_b.get_primary_field()
    new_prim_b = data_fixture.create_text_field(
        user=user, table=table_b, name="new_primary"
    )

    row_b1 = RowHandler().create_row(
        user,
        table_b,
        {orig_prim_b.db_column: "orig1", new_prim_b.db_column: "new1"},
    )

    f1 = data_fixture.create_formula_field(
        user=user, table=table_a, formula="field('link')", name="f1"
    )
    f2 = data_fixture.create_formula_field(
        user=user, table=table_a, formula="field('f1') + ' ?!'"
    )
    lookup_old = data_fixture.create_formula_field(
        user=user, table=table_a, formula="lookup('link', 'primary')"
    )
    lookup_new = data_fixture.create_formula_field(
        user=user, table=table_a, formula="lookup('link', 'new_primary')"
    )

    row_a1 = RowHandler().create_row(user, table_a, {link_a_b.db_column: [row_b1.id]})

    assert getattr(row_a1, f1.db_column) == [{"id": row_b1.id, "value": "orig1"}]
    assert getattr(row_a1, f2.db_column) == [{"id": row_b1.id, "value": "orig1 ?!"}]
    assert getattr(row_a1, lookup_old.db_column) == [
        {"id": row_b1.id, "value": "orig1"}
    ]
    assert getattr(row_a1, lookup_new.db_column) == [{"id": row_b1.id, "value": "new1"}]

    FieldHandler().change_primary_field(user, table_b, new_prim_b)

    row_a1.refresh_from_db()

    assert getattr(row_a1, f1.db_column) == [{"id": row_b1.id, "value": "new1"}]
    assert getattr(row_a1, f2.db_column) == [{"id": row_b1.id, "value": "new1 ?!"}]
    assert getattr(row_a1, lookup_old.db_column) == [
        {"id": row_b1.id, "value": "orig1"}
    ]
    assert getattr(row_a1, lookup_new.db_column) == [{"id": row_b1.id, "value": "new1"}]


@pytest.mark.django_db
def test_select_options_deleted_when_field_type_changed(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    select_field = data_fixture.create_single_select_field(table=table)

    handler = FieldHandler()

    handler.update_field_select_options(
        field=select_field,
        user=user,
        select_options=[
            {"value": "A", "color": "blue"},
            {"value": "B", "color": "red"},
        ],
    )

    assert SelectOption.objects.filter(field=select_field).count() == 2

    handler.update_field(
        user=user,
        field=select_field,
        new_type_name="text",
    )

    assert SelectOption.objects.filter(field=select_field).count() == 0


@pytest.mark.django_db
@pytest.mark.field_constraints
def test_field_constraints_unique_with_empty(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()

    # Get all specific constraints for unique_with_empty
    unique_with_empty_constraints = [
        constraint
        for constraint in field_constraint_registry.registry.values()
        if constraint.constraint_name == UNIQUE_WITH_EMPTY_CONSTRAINT_NAME
    ]

    select_field = data_fixture.create_single_select_field(table=table)
    select_option = SelectOption.objects.create(
        field=select_field,
        value="Option 1",
        color="blue",
        order=1,
    )

    fields = {
        TextFieldType.type: {
            "constraint": TextTypeUniqueWithEmptyConstraint.constraint_name,
            "empty": "",
            "value": "simple text",
        },
        LongTextFieldType.type: {
            "constraint": TextTypeUniqueWithEmptyConstraint.constraint_name,
            "empty": "",
            "value": "long text",
        },
        RatingFieldType.type: {
            "constraint": RatingTypeUniqueWithEmptyConstraint.constraint_name,
            "empty": 0,
            "value": 3,
        },
        NumberFieldType.type: {
            "constraint": UniqueWithEmptyConstraint.constraint_name,
            "empty": 0,
            "value": 3,
        },
        DateFieldType.type: {
            "constraint": UniqueWithEmptyConstraint.constraint_name,
            "empty": None,
            "value": datetime.now(),
        },
        URLFieldType.type: {
            "constraint": UniqueWithEmptyConstraint.constraint_name,
            "empty": "",
            "value": "https://baserow.io",
        },
        EmailFieldType.type: {
            "constraint": UniqueWithEmptyConstraint.constraint_name,
            "empty": "",
            "value": "test@example.com",
        },
        DurationFieldType.type: {
            "constraint": UniqueWithEmptyConstraint.constraint_name,
            "empty": None,
            "value": "00:00:00",
        },
        SingleSelectFieldType.type: {
            "constraint": UniqueWithEmptyConstraint.constraint_name,
            "empty": None,
            "value": select_option,
        },
    }

    fields_to_test = []
    for constraint in unique_with_empty_constraints:
        fields_to_test.extend(constraint.get_compatible_field_types())

    missing_fields = set(fields_to_test) - set(fields.keys())
    assert set(fields_to_test) == set(
        fields.keys()
    ), f"Fields that should be tested are missing: {missing_fields}"

    for field_type, field_data in fields.items():
        with pytest.raises(Exception) as exc_info:
            handler.create_field(
                user=user,
                table=table,
                type_name=field_type,
                name=f"Unique {field_type} Field",
                field_constraints=[{"type_name": "invalid_constraint_name"}],
            )
            assert is_unique_violation_error(exc_info.value) is True
        field = handler.create_field(
            user=user,
            table=table,
            type_name=field_type,
            name=f"Unique {field_type} Field",
            field_constraints=[{"type_name": field_data["constraint"]}],
        )
        assert list(field.field_constraints.values_list("type_name", flat=True)) == [
            field_data["constraint"]
        ]

        model = table.get_model()
        model.objects.all().delete()

        row_empty = model.objects.create(**{f"field_{field.id}": field_data["empty"]})
        assert getattr(row_empty, f"field_{field.id}") == field_data["empty"]

        row_non_empty = model.objects.create(
            **{f"field_{field.id}": field_data["value"]}
        )
        assert getattr(row_non_empty, f"field_{field.id}") == field_data["value"]

        with transaction.atomic(), pytest.raises(IntegrityError):
            model.objects.create(**{f"field_{field.id}": field_data["value"]})

        field = handler.update_field(user=user, field=field, field_constraints=[])
        assert list(field.field_constraints.values_list("type_name", flat=True)) == []

        row_duplicate = model.objects.create(
            **{f"field_{field.id}": field_data["value"]}
        )
        assert getattr(row_duplicate, f"field_{field.id}") == field_data["value"]

        assert model.objects.count() == 3


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_constraints
def test_import_export_field_constraints_preservation(data_fixture):
    """Test that field constraints are preserved during import/export operations."""

    user = data_fixture.create_user()
    source_workspace = data_fixture.create_workspace(user=user)
    target_workspace = data_fixture.create_workspace(user=user)

    source_database = data_fixture.create_database_application(
        user=user, workspace=source_workspace, name="Source Database"
    )
    source_table = data_fixture.create_database_table(
        name="Test Table", database=source_database
    )

    handler = FieldHandler()

    text_field = handler.create_field(
        user=user,
        table=source_table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    long_text_field = handler.create_field(
        user=user,
        table=source_table,
        type_name="long_text",
        name="Unique Long Text Field",
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    rating_field = handler.create_field(
        user=user,
        table=source_table,
        type_name="rating",
        name="Unique Rating Field",
        field_constraints=[
            {"type_name": RatingTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    number_field = handler.create_field(
        user=user,
        table=source_table,
        type_name="number",
        name="Unique Number Field",
        field_constraints=[{"type_name": UniqueWithEmptyConstraint.constraint_name}],
    )

    model = source_table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "unique_value_1"})
    model.objects.create(**{f"field_{long_text_field.id}": "unique_long_value_1"})
    model.objects.create(**{f"field_{rating_field.id}": 3})
    model.objects.create(**{f"field_{number_field.id}": 42})

    core_handler = CoreHandler()
    config = ImportExportConfig(include_permission_data=False)
    exported_applications = core_handler.export_workspace_applications(
        source_workspace, BytesIO(), config
    )

    exported_database = exported_applications[0]
    exported_table = exported_database["tables"][0]

    exported_text_field = next(
        f for f in exported_table["fields"] if f["name"] == "Unique Text Field"
    )
    exported_long_text_field = next(
        f for f in exported_table["fields"] if f["name"] == "Unique Long Text Field"
    )
    exported_rating_field = next(
        f for f in exported_table["fields"] if f["name"] == "Unique Rating Field"
    )
    exported_number_field = next(
        f for f in exported_table["fields"] if f["name"] == "Unique Number Field"
    )

    assert exported_text_field["field_constraints"] == [
        {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
    ]
    assert exported_long_text_field["field_constraints"] == [
        {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
    ]
    assert exported_rating_field["field_constraints"] == [
        {"type_name": RatingTypeUniqueWithEmptyConstraint.constraint_name}
    ]
    assert exported_number_field["field_constraints"] == [
        {"type_name": UniqueWithEmptyConstraint.constraint_name}
    ]

    imported_applications, _ = core_handler.import_applications_to_workspace(
        target_workspace, exported_applications, BytesIO(), config, None
    )

    imported_database = imported_applications[0]
    imported_tables = imported_database.table_set.all()
    imported_table = imported_tables[0]
    imported_model = imported_table.get_model()

    assert imported_database.name == "Source Database"

    assert len(imported_tables) == 1

    assert imported_table.name == "Test Table"

    imported_text_field = imported_table.field_set.get(
        name="Unique Text Field"
    ).specific
    imported_long_text_field = imported_table.field_set.get(
        name="Unique Long Text Field"
    ).specific
    imported_rating_field = imported_table.field_set.get(
        name="Unique Rating Field"
    ).specific
    imported_number_field = imported_table.field_set.get(
        name="Unique Number Field"
    ).specific

    assert list(
        imported_text_field.field_constraints.values_list("type_name", flat=True)
    ) == [TextTypeUniqueWithEmptyConstraint.constraint_name]
    assert list(
        imported_long_text_field.field_constraints.values_list("type_name", flat=True)
    ) == [TextTypeUniqueWithEmptyConstraint.constraint_name]
    assert list(
        imported_rating_field.field_constraints.values_list("type_name", flat=True)
    ) == [RatingTypeUniqueWithEmptyConstraint.constraint_name]
    assert list(
        imported_number_field.field_constraints.values_list("type_name", flat=True)
    ) == [UniqueWithEmptyConstraint.constraint_name]

    with transaction.atomic(), pytest.raises(IntegrityError) as exc_info:
        imported_model.objects.create(
            **{f"field_{imported_text_field.id}": "unique_value_1"}
        )
        assert is_unique_violation_error(exc_info.value) is True

    with transaction.atomic(), pytest.raises(IntegrityError) as exc_info:
        imported_model.objects.create(
            **{f"field_{imported_long_text_field.id}": "unique_long_value_1"}
        )
        assert is_unique_violation_error(exc_info.value) is True

    with transaction.atomic(), pytest.raises(IntegrityError) as exc_info:
        imported_model.objects.create(**{f"field_{imported_rating_field.id}": 3})
        assert is_unique_violation_error(exc_info.value) is True

    with transaction.atomic(), pytest.raises(IntegrityError) as exc_info:
        imported_model.objects.create(**{f"field_{imported_number_field.id}": 42})
        assert is_unique_violation_error(exc_info.value) is True

    imported_model.objects.create(**{f"field_{imported_text_field.id}": ""})
    imported_model.objects.create(**{f"field_{imported_long_text_field.id}": ""})
    imported_model.objects.create(**{f"field_{imported_rating_field.id}": 0})
    imported_model.objects.create(**{f"field_{imported_number_field.id}": 0})

    initial_row_count = imported_model.objects.count()

    imported_model.objects.create(
        **{f"field_{imported_text_field.id}": "different_value"}
    )
    imported_model.objects.create(
        **{f"field_{imported_long_text_field.id}": "different_long_value"}
    )
    imported_model.objects.create(**{f"field_{imported_rating_field.id}": 5})
    imported_model.objects.create(**{f"field_{imported_number_field.id}": 100})

    expected_total = initial_row_count + 4
    assert imported_model.objects.count() == expected_total


@pytest.mark.django_db
@pytest.mark.field_constraints
def test_import_export_field_constraints_serialization(data_fixture):
    """Test that field constraints are properly serialized and deserialized."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()

    field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Test Field",
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    field_type = field_type_registry.get_by_model(field)
    serialized_field = field_type.export_serialized(field)

    assert serialized_field["field_constraints"] == [
        {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
    ]

    id_mapping = {}
    imported_field = field_type.import_serialized(
        table,
        serialized_field,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        DeferredForeignKeyUpdater(),
    )

    assert list(
        imported_field.field_constraints.values_list("type_name", flat=True)
    ) == [TextTypeUniqueWithEmptyConstraint.constraint_name]
    assert imported_field.id != field.id
