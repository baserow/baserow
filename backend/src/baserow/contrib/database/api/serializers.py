from typing import TYPE_CHECKING, List

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.database.api.tables.serializers import TableSerializer
from baserow.contrib.database.models import Database

if TYPE_CHECKING:
    from baserow.contrib.database.application_types import DatabaseApplicationType


class DatabaseSerializer(serializers.ModelSerializer):
    tables = serializers.SerializerMethodField(
        help_text="This field is specific to the `database` application and contains "
        "an array of tables that are in the database."
    )

    class Meta:
        model = Database
        fields = (
            "id",
            "name",
            "tables",
        )

    @extend_schema_field(TableSerializer(many=True))
    def get_tables(self, instance: Database) -> List:
        """
        Serializes the database's tables. Uses pre-fetched tables attribute if
        available; otherwise, retrieves them from the database using the appropriate
        context and application type to avoid unnecessary queries when serializing
        nested fields.

        :param instance: The database application instance.
        :return: A list of serialized tables that belong to this instance.
        """

        tables = getattr(instance, "tables", None)
        if tables is None:
            user = self.context.get("user")
            request = self.context.get("request")

            if user is None and hasattr(request, "user"):
                user = request.user

            database_type: "DatabaseApplicationType" = instance.get_type()
            tables = database_type.fetch_tables_to_serialize(instance, user)

        return TableSerializer(tables, many=True).data
