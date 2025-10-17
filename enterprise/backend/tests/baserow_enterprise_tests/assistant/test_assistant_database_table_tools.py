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
    ListTablesFilterArg,
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
    database_1 = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )
    database_2 = data_fixture.create_database_application(
        workspace=workspace, name="Database 2"
    )
    table_1 = data_fixture.create_database_table(database=database_1, name="Table 1")
    table_2 = data_fixture.create_database_table(database=database_1, name="Table 2")
    table_3 = data_fixture.create_database_table(database=database_2, name="Table 3")

    tool = get_list_tables_tool(user, workspace, fake_tool_helpers)

    # Test 1: Filter by database_ids (single database) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=[database_1.id],
            database_names=None,
            table_ids=None,
            table_names=None,
        )
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 2: Filter by database_names (single database) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=["Database 2"],
            table_ids=None,
            table_names=None,
        )
    )
    assert response == [
        {"id": table_3.id, "name": "Table 3", "database_id": database_2.id},
    ]

    # Test 3: Filter by multiple database_ids - returns database wrapper structure
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=[database_1.id, database_2.id],
            database_names=None,
            table_ids=None,
            table_names=None,
        )
    )
    assert response == [
        {
            "id": database_1.id,
            "name": "Database 1",
            "tables": [
                {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
                {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
            ],
        },
        {
            "id": database_2.id,
            "name": "Database 2",
            "tables": [
                {"id": table_3.id, "name": "Table 3", "database_id": database_2.id},
            ],
        },
    ]

    # Test 4: Filter by table_ids (single database) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=None,
            table_ids=[table_1.id, table_2.id],
            table_names=None,
        )
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 5: Filter by table_names (single database) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=None,
            table_ids=None,
            table_names=["Table 1"],
        )
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
    ]

    # Test 6: Filter by table_ids across multiple databases - returns database wrapper
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=None,
            table_ids=[table_1.id, table_3.id],
            table_names=None,
        )
    )
    assert response == [
        {
            "id": database_1.id,
            "name": "Database 1",
            "tables": [
                {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
            ],
        },
        {
            "id": database_2.id,
            "name": "Database 2",
            "tables": [
                {"id": table_3.id, "name": "Table 3", "database_id": database_2.id},
            ],
        },
    ]

    # Test 7: Combined filters (database_ids + table_names) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=[database_1.id],
            database_names=None,
            table_ids=None,
            table_names=["Table 2"],
        )
    )
    assert response == [
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 8: No matching tables - returns "No tables found"
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=None,
            table_ids=None,
            table_names=["Nonexistent Table"],
        )
    )
    assert response == "No tables found"


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
        add_sample_rows=False,
    )

    assert response == {
        "created_tables": [{"id": AnyInt(), "name": "New Table"}],
        "notes": [],
    }

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
        add_sample_rows=False,
    )

    assert response == {
        "created_tables": [{"id": AnyInt(), "name": "New Table"}],
        "notes": [],
    }

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
