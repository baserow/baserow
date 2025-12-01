from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.models import Table, TableUsage


class TableFixtures:
    def create_database_table(self, user=None, create_table=True, **kwargs):
        if "database" not in kwargs:
            kwargs["database"] = self.create_database_application(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        row_count = kwargs.pop("row_count", None)
        usage = {}
        if row_count is not None:
            usage = {"row_count": row_count}

        storage_usage = kwargs.pop("storage_usage", None)
        if storage_usage is not None:
            usage["storage_usage"] = storage_usage

        table = Table.objects.create(**kwargs)
        if usage:
            TableUsage.objects.create(table=table, **usage)

        if create_table:
            model = table.get_model()
            with safe_django_schema_editor() as schema_editor:
                schema_editor.create_model(model)

            workspace_id = table.database.workspace_id
            if workspace_id:  # Some tests explicitly create tables without a workspace.
                SearchHandler.create_workspace_search_table_if_not_exists(workspace_id)

        return table

    def build_table(self, columns, rows, **kwargs):
        user = kwargs.pop("user", None)
        if user is None:
            user = self.create_user()

        table = self.create_database_table(user=user, **kwargs)
        fields = []
        for index, (name, field_type) in enumerate(columns):
            kwargs = {}
            if isinstance(field_type, dict):
                kwargs = field_type
                field_type = kwargs.pop("type")
            fields.append(
                getattr(self, f"create_{field_type}_field")(
                    name=name, table=table, order=index, **kwargs
                )
            )
        if rows:
            created_rows = (
                RowHandler()
                .force_create_rows(
                    user=user,
                    table=table,
                    rows_values=[
                        {
                            f"field_{field.id}": row[index]
                            for index, field in enumerate(fields)
                        }
                        for row in rows
                    ],
                )
                .created_rows
            )
        else:
            created_rows = []

        return table, fields, created_rows

    def create_two_linked_tables(
        self, user=None, table_b=None, table_kwargs=None, **kwargs
    ):
        if user is None:
            user = self.create_user()

        if "database" not in kwargs:
            if table_b is None:
                database = self.create_database_application(user=user)
            else:
                database = table_b.database
        else:
            database = kwargs["database"]

        table_kwargs = table_kwargs or {}
        table_a = self.create_database_table(
            database=database, name="table_a", **table_kwargs
        )
        if table_b is None:
            table_b = self.create_database_table(
                database=database, name="table_b", **table_kwargs
            )

        if not table_a.field_set.filter(primary=True).exists():
            self.create_text_field(table=table_a, name="primary", primary=True)
        if not table_b.field_set.filter(primary=True).exists():
            self.create_text_field(table=table_b, name="primary", primary=True)

        has_related_field = kwargs.pop("has_related_field", True)

        link_field = FieldHandler().create_field(
            user=user,
            table=table_a,
            type_name="link_row",
            name="link",
            link_row_table=table_b,
            has_related_field=has_related_field,
        )

        return table_a, table_b, link_field
