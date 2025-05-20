from typing import Optional

from django.db.models import QuerySet

from baserow.contrib.database.models import Database
from baserow.core.handler import CoreHandler


class DatabaseHandler:
    def get_database(
        self, database_id: int, base_queryset: Optional[QuerySet] = None
    ) -> Database:
        """
        Selects a database application with a given id from the database.

        :param database_id: The identifier of the database application
            that must be returned.
        :param base_queryset: The base queryset from where to select the application
            object. This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises ApplicationDoesNotExist: When the application with the provided id
            does not exist.
        :return: The requested database application instance of the provided id.
        """

        if base_queryset is None:
            base_queryset = Database.objects.select_related(
                "workspace__workspacedatabasesettings"
            )

        return (
            CoreHandler()
            .get_application(database_id, base_queryset=base_queryset)
            .specific
        )
