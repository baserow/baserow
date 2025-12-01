from django.db import connection

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.dependencies.handler import FieldDependencyHandler
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.field_types import AutonumberFieldType
from baserow.contrib.database.fields.models import (
    AutonumberField,
    BooleanField,
    CreatedByField,
    CreatedOnField,
    DateField,
    DurationField,
    EmailField,
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
    SelectOption,
    SingleSelectField,
    TextField,
    URLField,
    UUIDField,
)
from baserow.contrib.database.formula import FormulaHandler


class FieldFixtures:
    def create_model_field(self, table, field):
        with safe_django_schema_editor() as schema_editor:
            to_model = table.get_model(
                fields=[field], field_ids=[], add_dependencies=False
            )
            model_field = to_model._meta.get_field(field.db_column)
            schema_editor.add_field(to_model, model_field)

    def create_select_option(self, user=None, **kwargs):
        if "value" not in kwargs:
            kwargs["value"] = self.fake.name()

        if "color" not in kwargs:
            kwargs["color"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        if "field" not in kwargs:
            kwargs["field"] = self.create_single_select_field(user=user)

        return SelectOption.objects.create(**kwargs)

    def create_text_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = TextField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_duration_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = DurationField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_autonumber_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)
        view = kwargs.pop("view", None)

        field = AutonumberField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

            # Manually call the after_create hook to number existing rows and to create
            # the sequence needed by the field.
            model = kwargs["table"].get_model()
            field_kwargs = {"view": view}
            AutonumberFieldType().after_create(
                field, model, user, connection, None, field_kwargs
            )

        return field

    def set_test_field_kwarg_defaults(self, user, kwargs):
        if "table" not in kwargs:
            kwargs["table"] = self.create_database_table(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        kwargs.setdefault("tsvector_column_created", True)

    def create_long_text_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = LongTextField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_number_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = NumberField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_rating_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = RatingField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_boolean_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = BooleanField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_date_field(self, user=None, create_field=True, **kwargs):
        if "date_show_tzinfo" not in kwargs:
            kwargs["date_show_tzinfo"] = False

        self.set_test_field_kwarg_defaults(user, kwargs)

        field = DateField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_link_row_field(
        self,
        user=None,
        create_field=True,
        setup_dependencies=True,
        **kwargs,
    ):
        if "link_row_table" not in kwargs:
            kwargs["link_row_table"] = self.create_database_table(user=user)

        self.set_test_field_kwarg_defaults(user, kwargs)

        field = LinkRowField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        if setup_dependencies:
            FieldDependencyHandler().rebuild_dependencies([field], FieldCache())

        return field

    def create_file_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = FileField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_single_select_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = SingleSelectField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_multiple_select_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = MultipleSelectField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_multiple_collaborators_field(
        self, user=None, create_field=True, **kwargs
    ):
        self.set_test_field_kwarg_defaults(user, kwargs)

        if "notify_user_when_added" not in kwargs:
            kwargs["notify_user_when_added"] = False

        field = MultipleCollaboratorsField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_url_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = URLField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_email_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = EmailField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_phone_number_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = PhoneNumberField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_last_modified_field(self, user=None, create_field=True, **kwargs):
        if "date_include_time" not in kwargs:
            kwargs["date_include_time"] = False

        if "date_show_tzinfo" not in kwargs:
            kwargs["date_show_tzinfo"] = False

        self.set_test_field_kwarg_defaults(user, kwargs)

        field = LastModifiedField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_last_modified_by_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = LastModifiedByField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_created_by_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = CreatedByField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_created_on_field(self, user=None, create_field=True, **kwargs):
        if "date_include_time" not in kwargs:
            kwargs["date_include_time"] = False

        if "date_show_tzinfo" not in kwargs:
            kwargs["date_show_tzinfo"] = False

        self.set_test_field_kwarg_defaults(user, kwargs)

        field = CreatedOnField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_formula_field(
        self,
        user=None,
        create_field=True,
        setup_dependencies=True,
        calculate_cell_values=True,
        **kwargs,
    ):
        if "formula" not in kwargs:
            kwargs["formula"] = "'test'"

        if "formula_type" not in kwargs:
            kwargs["formula_type"] = "text"

        if "internal_formula" not in kwargs:
            kwargs["internal_formula"] = kwargs["formula"]

        if "requires_refresh_after_insert" not in kwargs:
            kwargs["requires_refresh_after_insert"] = False

        if "nullable" not in kwargs:
            kwargs["nullable"] = False

        if "date_show_tzinfo" not in kwargs:
            kwargs["date_show_tzinfo"] = False

        recalculate = kwargs.pop("recalculate", True)

        self.set_test_field_kwarg_defaults(user, kwargs)

        field = FormulaField(**kwargs)
        field.save(recalculate=recalculate)

        if create_field:
            self.create_model_field(kwargs["table"], field)
            if calculate_cell_values:
                model = field.table.get_model()
                expr = FormulaHandler.baserow_expression_to_update_django_expression(
                    field.cached_typed_internal_expression, model
                )
                model.objects_and_trash.all().update(**{f"{field.db_column}": expr})

        if setup_dependencies:
            FieldDependencyHandler().rebuild_dependencies([field], FieldCache())

        return field

    def create_lookup_field(
        self,
        user=None,
        create_field=True,
        setup_dependencies=True,
        **kwargs,
    ):
        recalculate = kwargs.pop("recalculate", True)

        self.set_test_field_kwarg_defaults(user, kwargs)

        field = LookupField(**kwargs)
        field.save(recalculate=recalculate)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        if setup_dependencies:
            FieldDependencyHandler().rebuild_dependencies([field], FieldCache())

        return field

    def create_uuid_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = UUIDField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field

    def create_password_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        field = PasswordField.objects.create(**kwargs)
        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field
