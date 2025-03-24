import dataclasses
from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.models import Database
from baserow.core.action.registries import ActionType, ActionTypeDescription
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    WorkspaceActionScopeType,
)
from baserow.core.models import Workspace
from baserow.core.utils import ChildProgressBuilder

from .config import AirtableImportConfig
from .handler import AirtableHandler


class ImportDatabaseFromAirtableActionType(ActionType):
    type = "import_database_from_airtable"
    description = ActionTypeDescription(
        _("Import database from Airtable"),
        _(
            'Imported database "%(installed_application_name)s" (%(installed_application_id)s) '
            'from Airtable share ID "%(airtable_share_id)s"'
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "installed_application_id",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        airtable_share_id: str
        installed_application_id: int
        installed_application_name: str
        workspace_id: int
        workspace_name: str
        skip_files: bool
        session: Optional[str]
        session_signature: Optional[str]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        airtable_share_id: str,
        skip_files: bool,
        session: Optional[str] = None,
        session_signature: Optional[str] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
        **kwargs,
    ) -> Database:
        """
        Imports a database from an Airtable share ID. The database will be
        created in the given workspace. The progress builder can be used to track
        the progress of the import.
        Look at .handler.AirtableHandler.import_from_airtable_to_workspace for more
        information.
        """

        config = AirtableImportConfig(
            skip_files=skip_files, session=session, session_signature=session_signature
        )

        database = AirtableHandler.import_from_airtable_to_workspace(
            workspace,
            airtable_share_id,
            progress_builder=progress_builder,
            config=config,
            **kwargs,
        )

        params = cls.Params(
            airtable_share_id,
            database.id,
            database.name,
            workspace.id,
            workspace.name,
            skip_files,
            session,
            session_signature,
        )
        cls.register_action(user, params, cls.scope(workspace.id), workspace)

        return database

    @classmethod
    def scope(cls, workspace_id):
        return WorkspaceActionScopeType.value(workspace_id)
