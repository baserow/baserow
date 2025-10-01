import pytest

from baserow.contrib.database.table.models import Table
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.assistant.tools.database.tools import (
    get_create_tables_tool,
    get_list_tables_tool,
)
from baserow_enterprise.assistant.tools.database.types import (
    BooleanFieldItemCreate,
    DateFieldItemCreate,
    FileFieldItemCreate,
    LinkRowFieldItemCreate,
    LongTextFieldItemCreate,
    MultipleSelectFieldItemCreate,
    NumberFieldItemCreate,
    RatingFieldItemCreate,
    SelectOptionCreate,
    SingleSelectFieldItemCreate,
    TableItemCreate,
    TextFieldItemCreate,
    field_item_registry,
)

from .utils import fake_tool_helpers


@pytest.mark.django_db
def test_list_tables_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )
    table = data_fixture.create_database_table(database=database, name="Table 1")

    tool = get_list_tables_tool(user, workspace, fake_tool_helpers)
    response = tool(database_id=database.id)

    assert response == {"tables": [{"id": table.id, "name": "Table 1"}]}

    table_2 = data_fixture.create_database_table(database=database, name="Table 2")
    response = tool(database_id=database.id)
    assert response == {
        "tables": [
            {"id": table.id, "name": "Table 1"},
            {"id": table_2.id, "name": "Table 2"},
        ]
    }


@pytest.mark.django_db
def test_create_simple_table_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )

    tool = get_create_tables_tool(user, workspace, fake_tool_helpers)
    response = tool(
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="New Table",
                primary_field=TextFieldItemCreate(type="text", name="Name"),
                fields=[],
            )
        ],
    )

    assert response == {"created_tables": [{"id": AnyInt(), "name": "New Table"}]}

    # Ensure the table was actually created
    assert Table.objects.filter(
        id=response["created_tables"][0]["id"], name="New Table"
    ).exists()


@pytest.mark.django_db
def test_create_complex_table_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )
    table = data_fixture.create_database_table(database=database, name="Table 1")

    tool = get_create_tables_tool(user, workspace, fake_tool_helpers)
    primary_field = TextFieldItemCreate(type="text", name="Name")
    fields = [
        LongTextFieldItemCreate(
            type="long_text",
            name="Description",
            rich_text=True,
        ),
        NumberFieldItemCreate(
            type="number",
            name="Amount",
            decimal_places=2,
            suffix="$",
        ),
        DateFieldItemCreate(
            type="date",
            name="Due Date",
            include_time=False,
        ),
        DateFieldItemCreate(
            type="date",
            name="Event Time",
            include_time=True,
        ),
        BooleanFieldItemCreate(
            type="boolean",
            name="Done?",
        ),
        SingleSelectFieldItemCreate(
            type="single_select",
            name="Status",
            options=[
                SelectOptionCreate(value="New", color="blue"),
                SelectOptionCreate(value="In Progress", color="yellow"),
                SelectOptionCreate(value="Done", color="green"),
            ],
        ),
        MultipleSelectFieldItemCreate(
            type="multiple_select",
            name="Tags",
            options=[
                SelectOptionCreate(value="Red", color="red"),
                SelectOptionCreate(value="Yellow", color="yellow"),
                SelectOptionCreate(value="Green", color="green"),
                SelectOptionCreate(value="Blue", color="blue"),
            ],
        ),
        LinkRowFieldItemCreate(
            type="link_row",
            name="Related Items",
            linked_table=table.id,
            has_link_back=False,
            multiple=True,
        ),
        RatingFieldItemCreate(
            type="rating",
            name="Rating",
            max_value=5,
        ),
        FileFieldItemCreate(
            type="file",
            name="Attachments",
        ),
    ]
    response = tool(
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="New Table",
                primary_field=primary_field,
                fields=fields,
            )
        ],
    )

    assert response == {"created_tables": [{"id": AnyInt(), "name": "New Table"}]}

    # Ensure the table was actually created with all fields
    created_table = Table.objects.filter(
        id=response["created_tables"][0]["id"], name="New Table"
    ).first()
    assert created_table is not None
    assert created_table.field_set.count() == 11

    table_model = created_table.get_model()
    fields_map = {field.name: field for field in fields}
    fields_map[primary_field.name] = primary_field
    for field_object in table_model.get_field_objects():
        orm_field = field_object["field"]
        assert orm_field.name in fields_map
        field_item = fields_map.pop(orm_field.name).model_dump()
        orm_field_to_item = field_item_registry.from_django_orm(orm_field).model_dump()
        if orm_field.primary:
            assert field_item["name"] == primary_field.name

        for key, value in orm_field_to_item.items():
            if key == "id":
                continue
            if key == "options":
                # Saved options have an ID, so we need to remove them before comparison
                for option in value:
                    option.pop("id")

            assert field_item[key] == value
