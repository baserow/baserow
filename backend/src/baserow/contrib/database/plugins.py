from datetime import date
from typing import TYPE_CHECKING

from django.utils.translation import gettext as _
from django.utils.translation import override

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.handler import CoreHandler
from baserow.core.registries import Plugin

from .table.handler import TableHandler

LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Fusce "
    "dignissim, urna eget rutrum sollicitudin, sapien diam interdum nisi, "
    "quis malesuada nibh eros a est."
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace


class DatabasePlugin(Plugin):
    type = "database"

    def create_initial_workspace(
        self,
        user: "AbstractUser",
        workspace: "Workspace" = None,
    ):
        """
        Called when an initial workspace is created. This adds an example database.
        """

        core_handler = CoreHandler()
        table_handler = TableHandler()
        row_handler = RowHandler()

        with override(user.profile.language):
            database = core_handler.create_application(
                user,
                workspace,
                type_name=self.type,
                name=_("%(first_name)s's company") % {"first_name": user.first_name},
            )

            # Creating the example customers table.
            table = table_handler.create_table_and_fields(
                user,
                database,
                name=_("Customers"),
                fields=[
                    (_("Name"), "text", {}),
                    (_("Last name"), "text", {}),
                    (_("Notes"), "long_text", {"field_options": {"width": 400}}),
                    (_("Active"), "boolean", {"field_options": {"width": 100}}),
                ],
            )

            data = [
                ["Ada", "Lovelace", "", True],
                ["Alan", "Turing", LOREM, False],
                ["Grace", "Hopper", "", True],
                ["John", "Von Neumann", "", True],
                ["Blaise", "Pascal", "", True],
            ]
            row_handler.import_rows(user, table, data=data, send_realtime_update=False)

            # Creating the example projects table.
            table = table_handler.create_table_and_fields(
                user,
                database,
                name=_("Projects"),
                fields=[
                    (_("Name"), "text", {}),
                    (_("Started"), "date", {}),
                    (_("Active"), "boolean", {"field_options": {"width": 100}}),
                ],
            )

            data = [
                [_("Calculator"), str(date(1642, 1, 1)), False],
                [_("Turing machine"), str(date(1936, 6, 1)), True],
                [_("Computer architecture"), str(date(1945, 1, 1)), False],
                [_("Cellular Automata"), str(date(1952, 6, 1)), False],
            ]
            row_handler.import_rows(user, table, data=data, send_realtime_update=False)
