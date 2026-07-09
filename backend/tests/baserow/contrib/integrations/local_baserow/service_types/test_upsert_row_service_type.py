from io import BytesIO
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.database.api.rows.serializers import RowSerializer
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowGetRow,
    LocalBaserowUpsertRow,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.test_utils.helpers import AnyInt, AnyStr
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.mark.django_db
def test_local_baserow_create_rows_service_dispatch_data(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")

    service = data_fixture.create_local_baserow_create_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()

    formula_context = {
        "page_parameter": {"rows": [{"Ingredient": "Bread"}, {"Ingredient": "Butter"}]}
    }
    dispatch_context = FakeDispatchContext(context=formula_context)

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert [getattr(row, ingredient.db_column) for row in dispatch_data["data"]] == [
        "Bread",
        "Butter",
    ]

    dispatch_result = service_type.dispatch_transform(dispatch_data)

    assert dispatch_result.data["results"][0]["Ingredient"] == "Bread"
    assert dispatch_result.data["results"][1]["Ingredient"] == "Butter"


@pytest.mark.django_db
def test_local_baserow_create_rows_service_dispatch_data_reports_invalid_row(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name")
    data_fixture.create_email_field(table=table, name="Email")

    service = data_fixture.create_local_baserow_create_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": [
                    {"Name": "Bread", "Email": "test@test.fr"},
                    {"Name": "Croissant", "Email": "failing"},
                ]
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(
        InvalidContextContentDispatchException,
        match=(
            "Invalid row values:\n- row 2 "
            r"\(Email='failing': Enter a valid value\.\)"
        ),
    ):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)

    assert table.get_model().objects.count() == 0


@pytest.mark.django_db
@override_settings(INTEGRATION_LOCAL_BASEROW_BATCH_OPERATION_SIZE_LIMIT=1)
def test_local_baserow_create_rows_service_rejects_too_many_rows(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Ingredient")
    service = data_fixture.create_local_baserow_create_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": [{"Ingredient": "Bread"}, {"Ingredient": "Butter"}]
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(
        InvalidContextContentDispatchException,
        match="The batch create rows action can process at most 1 rows at once.",
    ):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)


@pytest.mark.django_db
def test_local_baserow_create_rows_service_dispatch_data_with_json_text_rows(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")

    service = data_fixture.create_local_baserow_create_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": '[{"Ingredient": "Bread"}, {"Ingredient": "Butter"}]'
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert [getattr(row, ingredient.db_column) for row in dispatch_data["data"]] == [
        "Bread",
        "Butter",
    ]


@pytest.mark.django_db
def test_local_baserow_create_rows_service_dispatch_data_with_serialized_select_options(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = data_fixture.create_database_table(user=user, database=database)
    single_select_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Single select",
        type_name="single_select",
        select_options=[
            {"value": "Bakery", "color": "dark-gray"},
        ],
    )
    multiple_select_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Multiple select",
        type_name="multiple_select",
        select_options=[
            {"value": "Bread", "color": "yellow"},
            {"value": "Butter", "color": "light-yellow"},
        ],
    )
    single_select_option = single_select_field.select_options.get(value="Bakery")
    bread_option = multiple_select_field.select_options.get(value="Bread")
    butter_option = multiple_select_field.select_options.get(value="Butter")

    service = data_fixture.create_local_baserow_create_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": [
                    {
                        "Single select": {
                            "id": single_select_option.id,
                            "color": single_select_option.color,
                            "value": single_select_option.value,
                        },
                        "Multiple select": [
                            {
                                "id": bread_option.id,
                                "color": bread_option.color,
                                "value": bread_option.value,
                            },
                            {
                                "id": butter_option.id,
                                "color": butter_option.color,
                                "value": butter_option.value,
                            },
                        ],
                    }
                ]
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    row = dispatch_data["data"][0]
    assert getattr(row, single_select_field.db_column).id == single_select_option.id
    assert [
        option.id for option in getattr(row, multiple_select_field.db_column).all()
    ] == [bread_option.id, butter_option.id]


@pytest.mark.django_db
def test_local_baserow_create_rows_service_dispatch_data_with_serialized_relations(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    related_table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="Related table",
        fields=[
            ("Name", "text", {}),
        ],
    )
    related_primary_field = related_table.field_set.get(primary=True)
    related_row = related_table.get_model().objects.create(
        **{related_primary_field.db_column: "Bakery"}
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Link", "link_row", {"link_row_table": related_table}),
            ("Collaborators", "multiple_collaborators", {}),
        ],
    )
    link_row_field = table.field_set.get(name="Link")
    collaborator_field = table.field_set.get(name="Collaborators")

    service = data_fixture.create_local_baserow_create_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": [
                    {
                        "Link": [
                            {
                                "id": related_row.id,
                                "value": "Bakery",
                                "order": str(related_row.order),
                            }
                        ],
                        "Collaborators": [{"id": user.id, "name": user.first_name}],
                    }
                ]
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    row = dispatch_data["data"][0]
    assert [
        linked_row.id for linked_row in getattr(row, link_row_field.db_column).all()
    ] == [related_row.id]
    assert [
        collaborator.id
        for collaborator in getattr(row, collaborator_field.db_column).all()
    ] == [user.id]


@pytest.mark.django_db
def test_local_baserow_update_rows_service_dispatch_data(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")
    model = table.get_model()
    row_1 = model.objects.create(**{ingredient.db_column: "Flour"})
    row_2 = model.objects.create(**{ingredient.db_column: "Milk"})

    service = data_fixture.create_local_baserow_update_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": [
                    {"id": row_1.id, "Ingredient": "Bread"},
                    {"id": row_2.id, str(ingredient.id): "Butter"},
                ]
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert [getattr(row, ingredient.db_column) for row in dispatch_data["data"]] == [
        "Bread",
        "Butter",
    ]

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, ingredient.db_column) == "Bread"
    assert getattr(row_2, ingredient.db_column) == "Butter"

    dispatch_result = service_type.dispatch_transform(dispatch_data)

    assert dispatch_result.data["results"][0]["Ingredient"] == "Bread"
    assert dispatch_result.data["results"][1]["Ingredient"] == "Butter"


@pytest.mark.django_db
def test_local_baserow_update_rows_service_dispatch_data_reports_invalid_row(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    email_field = data_fixture.create_email_field(table=table, name="Email")
    model = table.get_model()
    row_1 = model.objects.create(
        **{name_field.db_column: "Bread", email_field.db_column: "test@test.fr"}
    )
    row_2 = model.objects.create(
        **{name_field.db_column: "Croissant", email_field.db_column: "old@test.fr"}
    )

    service = data_fixture.create_local_baserow_update_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": [
                    {"id": row_1.id, "Email": "new@test.fr"},
                    {"id": row_2.id, "Email": "failing"},
                ]
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(
        InvalidContextContentDispatchException,
        match=(
            "Invalid row values:\n- row 2 "
            r"\(Email='failing': Enter a valid value\.\)"
        ),
    ):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, email_field.db_column) == "test@test.fr"
    assert getattr(row_2, email_field.db_column) == "old@test.fr"


@pytest.mark.django_db
@override_settings(INTEGRATION_LOCAL_BASEROW_BATCH_OPERATION_SIZE_LIMIT=1)
def test_local_baserow_update_rows_service_rejects_too_many_rows(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Ingredient")
    model = table.get_model()
    row_1 = model.objects.create(**{field.db_column: "Flour"})
    row_2 = model.objects.create(**{field.db_column: "Milk"})
    service = data_fixture.create_local_baserow_update_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": [
                    {"id": row_1.id, "Ingredient": "Bread"},
                    {"id": row_2.id, "Ingredient": "Butter"},
                ]
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(
        InvalidContextContentDispatchException,
        match="The batch update rows action can process at most 1 rows at once.",
    ):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)


@pytest.mark.django_db
def test_local_baserow_update_rows_service_dispatch_data_with_json_text_rows(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")
    model = table.get_model()
    row = model.objects.create(**{ingredient.db_column: "Flour"})

    service = data_fixture.create_local_baserow_update_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {"rows": f'[{{"id": {row.id}, "Ingredient": "Bread"}}]'}
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert getattr(dispatch_data["data"][0], ingredient.db_column) == "Bread"


@pytest.mark.django_db
def test_local_baserow_update_rows_service_dispatch_data_requires_id(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )

    service = data_fixture.create_local_baserow_update_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={"page_parameter": {"rows": [{"Ingredient": "Bread"}]}}
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(
        InvalidContextContentDispatchException,
        match='Row 1 must contain an "id" property.',
    ):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)


@pytest.mark.django_db
def test_local_baserow_update_rows_service_dispatch_data_rejects_duplicate_ids(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")
    row = table.get_model().objects.create(**{ingredient.db_column: "Flour"})

    service = data_fixture.create_local_baserow_update_rows_service(
        integration=integration,
        table=table,
        rows='get("page_parameter.rows")',
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={
            "page_parameter": {
                "rows": [
                    {"id": row.id, "Ingredient": "Bread"},
                    {"id": row.id, "Ingredient": "Butter"},
                ]
            }
        }
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(
        InvalidContextContentDispatchException,
        match=f"Rows with ids \\[{row.id}\\] are duplicated.",
    ):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_without_row_id(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")

    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    service_type = service.get_type()
    service.field_mappings.create(field=ingredient, value='get("page_parameter.id")')

    formula_context = {"page_parameter": {"id": 2}}
    dispatch_context = FakeDispatchContext(context=formula_context)

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert getattr(dispatch_data["data"], ingredient.db_column) == str(
        formula_context["page_parameter"]["id"]
    )


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_without_row_id_with_file(
    data_fixture, fake
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("File", "file", {}),
        ],
    )
    file_field = table.field_set.get(name="File")

    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    service_type = service.get_type()
    service.field_mappings.create(field=file_field, value='get("form.file")')

    image = fake.image()

    formula_context = {
        "form": {
            "file": {
                "__file__": True,
                "name": "superfile",
                "file": SimpleUploadedFile(
                    name="avatar.png", content=image, content_type="image/png"
                ),
            }
        }
    }
    dispatch_context = FakeDispatchContext(context=formula_context)

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    assert getattr(dispatch_data["data"], file_field.db_column) == [
        {
            "image_height": 256,
            "image_width": 256,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
            "visible_name": "superfile",
        },
    ]


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_with_row_id(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Cost", "number", {}),
        ],
    )
    cost = table.field_set.get(name="Cost")
    row = RowHandler().create_row(
        user=user,
        table=table,
        values={f"field_{cost.id}": 5},
    )

    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        row_id=f"'{row.id}'",
        integration=integration,
    )
    service_type = service.get_type()
    service.field_mappings.create(field=cost, value='get("page_parameter.id")')

    formula_context = {"page_parameter": {"id": 10}}

    dispatch_context = FakeDispatchContext(context=formula_context)
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert (
        getattr(dispatch_data["data"], cost.db_column)
        == formula_context["page_parameter"]["id"]
    )

    row.refresh_from_db()
    assert getattr(row, cost.db_column) == formula_context["page_parameter"]["id"]

    # Same test but the page parameter is a string instead.
    formula_context = {"page_parameter": {"id": "10"}}
    dispatch_context = FakeDispatchContext(context=formula_context)
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert getattr(dispatch_data["data"], cost.db_column) == int(
        formula_context["page_parameter"]["id"]
    )

    row.refresh_from_db()
    assert getattr(row, cost.db_column) == int(formula_context["page_parameter"]["id"])


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_disabled_field_mapping_fields(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Name", "text", {}),
            ("Last name", "text", {}),
            ("Location", "text", {}),
        ],
    )

    name_field = table.field_set.get(name="Name")
    last_name_field = table.field_set.get(name="Last name")
    location_field = table.field_set.get(name="Location")

    row = RowHandler().create_row(
        user=user,
        table=table,
        values={
            name_field.id: "Peter",
            last_name_field.id: "Evans",
            location_field.id: "Cornwall",
        },
    )

    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        row_id=f"'{row.id}'",
        integration=integration,
    )
    service_type = service.get_type()
    service.field_mappings.create(field=name_field, value="'Jeff'", enabled=True)
    service.field_mappings.create(field=last_name_field, value="", enabled=False)
    service.field_mappings.create(field=location_field, value="", enabled=False)

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    service_type.dispatch_data(service, dispatch_values, dispatch_context)

    row.refresh_from_db()
    assert getattr(row, name_field.db_column) == "Jeff"
    assert getattr(row, last_name_field.db_column) == "Evans"
    assert getattr(row, location_field.db_column) == "Cornwall"


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_with_multiple_formulas(
    data_fixture,
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user, authorized_user=user
    )
    database = data_fixture.create_database_application(workspace=builder.workspace)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Cost", "number", {}),
            ("Name", "text", {}),
        ],
    )
    cost = table.field_set.get(name="Cost")
    name = table.field_set.get(name="Name")
    row = RowHandler().create_row(
        user=user,
        table=table,
        values={cost.db_column: 5, name.db_column: "test"},
    )

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, table=table, integration=integration
    )

    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        row_id=f'get("data_source.{data_source.id}.id")',
        integration=integration,
    )
    service_type = service.get_type()
    service.field_mappings.create(
        field=cost, value=f'get("data_source.{data_source.id}.{cost.db_column}")'
    )
    service.field_mappings.create(
        field=name, value=f'get("data_source.{data_source.id}.{name.db_column}")'
    )

    formula_context = {
        "data_source": {
            str(data_source.id): {
                cost.db_column: 5,
                name.db_column: "test",
                "id": row.id,
            }
        },
    }

    dispatch_context = FakeDispatchContext(context=formula_context)

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    service_type.dispatch_data(service, dispatch_values, dispatch_context)

    row.refresh_from_db()
    assert getattr(row, cost.db_column) == 5
    assert getattr(row, name.db_column) == "test"


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_with_unknown_row_id(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    table = data_fixture.create_database_table(user=user)
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        row_id="'9999999999999'",
        integration=integration,
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert exc.value.args[0] == "The row with id 9999999999999 does not exist."


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_with_read_only_table_field(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("UUID", "uuid", {}),
            ("Ingredient", "text", {}),
        ],
    )
    uuid = table.field_set.get(name="UUID")
    ingredient = table.field_set.get(name="Ingredient")

    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    service_type = service.get_type()
    service.field_mappings.create(
        field=uuid, value="'b52d8848-f2c2-4495-b8ef-94e1b4f3c49f'"
    )
    service.field_mappings.create(field=ingredient, value="'Potato'")

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert (
        getattr(dispatch_data["data"], uuid.db_column)
        != "b52d8848-f2c2-4495-b8ef-94e1b4f3c49f"
    )
    assert getattr(dispatch_data["data"], ingredient.db_column) == "Potato"


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_transform(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")

    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    service_type = service.get_type()
    service.field_mappings.create(field=ingredient, value='get("page_parameter.id")')

    dispatch_context = FakeDispatchContext(context={"page_parameter": {"id": 2}})
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    serialized_row = service_type.dispatch_transform(dispatch_data)
    assert dict(serialized_row.data) == {
        "id": dispatch_data["data"].id,
        "order": "1.00000000000000000000",
        ingredient.name: str(2),
    }


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_incompatible_value(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Active", "boolean", {}),
        ],
    )
    boolean_field = table.field_set.get()
    single_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Single Select",
        type_name="single_select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
        ],
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    field_mapping = service.field_mappings.create(field=boolean_field, value="'Horse'")
    with pytest.raises(InvalidContextContentDispatchException) as exc:
        service_type.dispatch_data(
            service, {"table": table, field_mapping.id: "Horse"}, dispatch_context
        )

    assert (
        exc.value.args[0]
        == f'Value error for field "{boolean_field.name}": Value is not a valid boolean '
        "or convertible to a boolean."
    )

    service.field_mappings.all().delete()

    field_mapping = service.field_mappings.create(
        field=single_field, value="'99999999999'"
    )
    with pytest.raises(InvalidContextContentDispatchException) as exc:
        service_type.dispatch_data(
            service, {"table": table, field_mapping.id: "99999999999"}, dispatch_context
        )

    assert exc.value.args[0] == (
        f'Value error for field "{single_field.name}": The provided select option '
        "value '99999999999' is not a valid select option."
    )


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_convert_value(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    related_table = data_fixture.create_database_table(user=user, database=database)
    related_table_model = related_table.get_model(attribute_names=True)
    related_table_model.objects.create()
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("boolean", "boolean", {}),
            ("text", "text", {}),
            ("array", "link_row", {"link_row_table": related_table}),
        ],
    )

    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    service_type = service.get_type()

    service.field_mappings.create(
        field=table.field_set.get(name="boolean"), value="'true'"
    )
    service.field_mappings.create(
        field=table.field_set.get(name="text"), value="'text'"
    )
    service.field_mappings.create(field=table.field_set.get(name="array"), value="1")

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    serialized_row = service_type.dispatch_transform(dispatch_data)

    assert dict(serialized_row.data) == {
        "id": 1,
        "order": "1.00000000000000000000",
        # The string 'true' was converted to a boolean value
        table.field_set.get(name="boolean").name: True,
        # The string 'text' is unchanged
        table.field_set.get(name="text").name: "text",
        # The string '1' is converted to a list with a single item
        table.field_set.get(name="array").name: [
            {"id": 1, "value": "unnamed row 1", "order": AnyStr()}
        ],
    }


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_with_serialized_select_options(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = data_fixture.create_database_table(user=user, database=database)
    single_select_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Single select",
        type_name="single_select",
        select_options=[
            {"value": "Bakery", "color": "dark-gray"},
        ],
    )
    multiple_select_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Multiple select",
        type_name="multiple_select",
        select_options=[
            {"value": "Bread", "color": "yellow"},
            {"value": "Butter", "color": "light-yellow"},
        ],
    )
    single_select_option = single_select_field.select_options.get(value="Bakery")
    bread_option = multiple_select_field.select_options.get(value="Bread")
    butter_option = multiple_select_field.select_options.get(value="Butter")

    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    service_type = service.get_type()
    single_select_mapping = service.field_mappings.create(
        field=single_select_field, value='get("page_parameter.single")'
    )
    multiple_select_mapping = service.field_mappings.create(
        field=multiple_select_field, value='get("page_parameter.multiple")'
    )

    dispatch_data = service_type.dispatch_data(
        service,
        {
            single_select_mapping.id: {
                "id": single_select_option.id,
                "color": single_select_option.color,
                "value": single_select_option.value,
            },
            multiple_select_mapping.id: [
                {
                    "id": bread_option.id,
                    "color": bread_option.color,
                    "value": bread_option.value,
                },
                {
                    "id": butter_option.id,
                    "color": butter_option.color,
                    "value": butter_option.value,
                },
            ],
        },
        FakeDispatchContext(),
    )

    row = dispatch_data["data"]
    assert getattr(row, single_select_field.db_column).id == single_select_option.id
    assert [
        option.id for option in getattr(row, multiple_select_field.db_column).all()
    ] == [bread_option.id, butter_option.id]


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_with_serialized_relations(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    related_table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="Related table",
        fields=[
            ("Name", "text", {}),
        ],
    )
    related_primary_field = related_table.field_set.get(primary=True)
    related_row = related_table.get_model().objects.create(
        **{related_primary_field.db_column: "Bakery"}
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Link", "link_row", {"link_row_table": related_table}),
            ("Collaborators", "multiple_collaborators", {}),
        ],
    )
    link_row_field = table.field_set.get(name="Link")
    collaborator_field = table.field_set.get(name="Collaborators")

    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    service_type = service.get_type()
    link_row_mapping = service.field_mappings.create(
        field=link_row_field, value='get("page_parameter.link")'
    )
    collaborator_mapping = service.field_mappings.create(
        field=collaborator_field, value='get("page_parameter.collaborators")'
    )

    dispatch_data = service_type.dispatch_data(
        service,
        {
            link_row_mapping.id: [
                {
                    "id": related_row.id,
                    "value": "Bakery",
                    "order": str(related_row.order),
                }
            ],
            collaborator_mapping.id: [{"id": user.id, "name": user.first_name}],
        },
        FakeDispatchContext(),
    )

    row = dispatch_data["data"]
    assert [
        linked_row.id for linked_row in getattr(row, link_row_field.db_column).all()
    ] == [related_row.id]
    assert [
        collaborator.id
        for collaborator in getattr(row, collaborator_field.db_column).all()
    ] == [user.id]


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_resolve_service_formulas(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Name", "text", {}),
        ],
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    # We're creating a row.
    service.row_id = BaserowFormulaObject(
        formula="",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version=BASEROW_FORMULA_VERSION_INITIAL,
    )
    assert service_type.resolve_service_formulas(service, dispatch_context) == {}

    # We're updating a row, but the ID isn't an integer
    service.row_id = BaserowFormulaObject(
        formula="'horse'",
        mode=BASEROW_FORMULA_MODE_SIMPLE,
        version=BASEROW_FORMULA_VERSION_INITIAL,
    )
    with pytest.raises(InvalidContextContentDispatchException) as exc:
        service_type.resolve_service_formulas(service, dispatch_context)

    assert exc.value.args[0] == (
        'Value error for "row_id": '
        "The value must be an integer or convertible to an integer."
    )


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_prepare_values(data_fixture):
    user = data_fixture.create_user()
    with pytest.raises(ValidationError) as exc:
        LocalBaserowUpsertRowServiceType().prepare_values(
            {"table_id": 9999999999999999}, user
        )
    assert exc.value.args[0] == f"The table with ID 9999999999999999 does not exist."


@pytest.mark.django_db(transaction=True)
def test_export_import_local_baserow_upsert_row_service(
    data_fixture,
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace, order=2)
    page = data_fixture.create_builder_page(builder=builder)
    element = data_fixture.create_builder_button_element(page=page)
    database = data_fixture.create_database_application(workspace=workspace, order=1)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    trashed_field = data_fixture.create_text_field(table=table, trashed=True)
    integration = data_fixture.create_local_baserow_integration(application=builder)

    get_row_service = LocalBaserowGetRow.objects.create(integration=integration)
    data_source = DataSourceService().create_data_source(
        user, service_type=get_row_service.get_type(), page=page
    )
    upsert_row_service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
        row_id=f"get('data_source.{data_source.id}.{field.db_column}')",
    )
    upsert_row_service.field_mappings.create(
        field=field, value=f"get('data_source.{data_source.id}.{field.db_column}')"
    )
    upsert_row_service.field_mappings.create(
        field=trashed_field,
        value=f"get('data_source.{data_source.id}.{trashed_field.db_column}')",
    )

    data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=element, event=EventTypes.CLICK, service=upsert_row_service
    )

    config = ImportExportConfig(include_permission_data=False)
    exported_applications = CoreHandler().export_workspace_applications(
        workspace, BytesIO(), config
    )

    imported_workspace = data_fixture.create_workspace(user=user)
    imported_applications, id_mapping = CoreHandler().import_applications_to_workspace(
        imported_workspace, exported_applications, BytesIO(), config, None
    )

    imported_database, imported_builder = imported_applications
    imported_table = imported_database.table_set.get()
    imported_field = imported_table.field_set.get()

    imported_page = imported_builder.visible_pages.get()
    imported_data_source = imported_page.datasource_set.get()
    imported_integration = imported_builder.integrations.get()
    imported_upsert_row_service = LocalBaserowUpsertRow.objects.get(
        integration=imported_integration
    )
    imported_field_mapping = imported_upsert_row_service.field_mappings.get()

    assert imported_field_mapping.field == imported_field
    assert (
        imported_field_mapping.value["formula"]
        == f"get('data_source.{imported_data_source.id}.{imported_field.db_column}')"
    )
    assert (
        imported_upsert_row_service.row_id["formula"]
        == f"get('data_source.{imported_data_source.id}.{imported_field.db_column}')"
    )


@pytest.mark.django_db()
def test_local_baserow_upsert_row_service_after_update(data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder
    )
    table = data_fixture.create_database_table()
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    field = data_fixture.create_text_field(table=table)
    LocalBaserowUpsertRowServiceType().after_update(
        service,
        {
            "table_id": table.id,
            "integration_id": integration.id,
            "field_mappings": [
                {"field_id": field.id, "value": "'Horse'", "enabled": True}
            ],
        },
        {},
    )
    assert service.field_mappings.count() == 1

    with pytest.raises(ValidationError) as exc:
        LocalBaserowUpsertRowServiceType().after_update(
            service,
            {
                "table_id": table.id,
                "field_mappings": [{"value": "'Bread'", "enabled": True}],
            },
            {},
        )
    assert exc.value.args[0] == "A field mapping must have a `field_id`."

    # Changing the table results in the `field_mapping` getting reset.
    table2 = data_fixture.create_database_table()
    service.table = table2
    service.save()

    with pytest.raises(ValidationError) as exc:
        LocalBaserowUpsertRowServiceType().after_update(
            service,
            {
                "field_mappings": [
                    {"field_id": field.id, "value": "'Pony'", "enabled": True}
                ],
            },
            {"table": (table, table2)},
        )
    assert exc.value.args[0] == f"The field with id {field.id} does not exist."
    service.refresh_from_db()
    assert service.table_id == table2.id
    assert service.field_mappings.count() == 0


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_type_import_path(data_fixture):
    imported_upsert_row_service_type = LocalBaserowUpsertRowServiceType()

    assert imported_upsert_row_service_type.import_path(["id"], {}) == ["id"]
    assert imported_upsert_row_service_type.import_path(["field_1"], {}) == ["field_1"]
    assert imported_upsert_row_service_type.import_path(
        ["field_1"], {"database_fields": {1: 2}}
    ) == ["field_2"]


@pytest.mark.parametrize(
    "field_names,expected",
    [
        (None, None),
        ([], []),
        (["field_123"], [123]),
    ],
)
@patch(
    "baserow.contrib.integrations.local_baserow.service_types.get_row_serializer_class"
)
def test_dispatch_transform_passes_field_ids(
    mock_get_serializer, field_names, expected
):
    """
    Test the LocalBaserowUpsertRowServiceType::dispatch_transform() method.

    Ensure that the field_ids parameter is passed to the serializer class.
    """

    mock_serializer_instance = MagicMock()
    mock_serializer = MagicMock(return_value=mock_serializer_instance)
    mock_serializer.data = {}
    mock_get_serializer.return_value = mock_serializer

    service_type = LocalBaserowUpsertRowServiceType()

    dispatch_data = {
        "baserow_table_model": MagicMock(),
        "data": [],
    }
    dispatch_data["public_formula_fields"] = field_names

    results = service_type.dispatch_transform(dispatch_data)

    assert results.data == mock_serializer.data
    mock_get_serializer.assert_called_once_with(
        dispatch_data["baserow_table_model"],
        RowSerializer,
        is_response=True,
        field_ids=expected,
        user_field_names=True,
    )


@pytest.mark.parametrize(
    "path,expected",
    [
        ([], ["id"]),
        ([None], []),
        ([""], []),
        (["foo"], []),
        (["bar"], []),
        (["foo", "bar"], []),
        # "id" is valid
        (["id"], ["id"]),
        # "field_<id>" is a valid pattern
        (["field_1"], ["field_1"]),
    ],
)
def test_extract_properties_returns_expected_list(path, expected):
    """
    Test the LocalBaserowUpsertRowServiceType::extract_properties() method.

    Ensure that given the path parameter, the expected list is returned.
    """

    service_type = LocalBaserowUpsertRowServiceType()

    mock_service = MagicMock()
    result = service_type.extract_properties(mock_service, path)

    assert result == expected


@pytest.mark.django_db
def test_local_baserow_upsert_row_service_dispatch_data_with_collaborators(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Collaborators", "multiple_collaborators", {}),
        ],
    )
    collaborator_field = table.field_set.get(name="Collaborators")

    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    service_type = service.get_type()
    # Simulate a user ID as a string
    service.field_mappings.create(field=collaborator_field, value=f'"{user.id}"')

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    collaborators = getattr(dispatch_data["data"], collaborator_field.db_column).all()
    assert list(collaborators.values_list("id", flat=True)) == [user.id]


@pytest.mark.django_db
def test_upsert_row_service_export_prepared_values_includes_field_mappings(
    data_fixture,
):
    # The field mappings (each row field's value/formula) must be captured by
    # `export_prepared_values` so that changing a field value is undoable/redoable.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[("Name", "text", {})],
    )
    name_field = table.field_set.get(name="Name")
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table, integration=integration
    )
    service.field_mappings.create(field=name_field, value="'Jeff'", enabled=True)

    exported = service.get_type().export_prepared_values(service)

    assert len(exported["field_mappings"]) == 1
    field_mapping = exported["field_mappings"][0]
    assert field_mapping["field_id"] == name_field.id
    assert field_mapping["enabled"] is True
    assert field_mapping["value"]["formula"] == "'Jeff'"


@pytest.mark.django_db
def test_upsert_row_service_field_mapping_update_can_be_undone(data_fixture):
    # Reproduces the automation/builder create_row undo bug: capturing the original
    # field mappings and re-applying them (as undo does) reverts a field value change.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[("Name", "text", {})],
    )
    name_field = table.field_set.get(name="Name")
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table, integration=integration
    )
    service.field_mappings.create(field=name_field, value="", enabled=True)
    service_type = service.get_type()

    # Snapshot the original (empty) mappings.
    original = service_type.export_prepared_values(service)

    # Change the field value to 'bob'.
    ServiceHandler().update_service(
        service_type,
        service,
        field_mappings=[{"field_id": name_field.id, "enabled": True, "value": "'bob'"}],
    )
    service.refresh_from_db()
    new = service_type.export_prepared_values(service)
    assert new["field_mappings"] != original["field_mappings"]
    assert new["field_mappings"][0]["value"]["formula"] == "'bob'"

    # Undo: re-apply the original mappings -> value reverts to empty.
    ServiceHandler().update_service(
        service_type, service, field_mappings=original["field_mappings"]
    )
    service.refresh_from_db()
    assert service.field_mappings.get(field=name_field).value["formula"] == ""
