from collections import defaultdict

from django.db.models import prefetch_related_objects

from baserow.contrib.database.tokens.exceptions import NoPermissionToTable
from baserow.contrib.database.tokens.models import TokenPermission
from baserow.contrib.database.tokens.subjects import TokenSubjectType
from baserow.core.handler import CoreHandler
from baserow.core.registries import PermissionManagerType
from baserow.core.types import PermissionCheck

from .constants import OPERATION_TO_TOKEN_MAP, TOKEN_TO_OPERATION_MAP


class TokenPermissionManagerType(PermissionManagerType):
    type = "token"
    supported_actor_types = [TokenSubjectType.type]

    def check_multiple_permissions(self, checks, workspace=None, include_trash=False):
        """
        Checks multiple permissions for token.
        """

        token_checks = [
            check for check in checks if check.operation_name in OPERATION_TO_TOKEN_MAP
        ]
        if not token_checks:
            return {}

        # One query for all contexts, the scopes are matched in memory.
        scopes_by_token_id_and_operation = defaultdict(set)
        for token_id, type, table_id, database_id in TokenPermission.objects.filter(
            token__in={check.actor.id for check in token_checks},
            type__in={
                OPERATION_TO_TOKEN_MAP[check.operation_name] for check in token_checks
            },
        ).values_list("token_id", "type", "table_id", "database_id"):
            scopes_by_token_id_and_operation[
                (token_id, TOKEN_TO_OPERATION_MAP[type])
            ].add((table_id, database_id))

        prefetch_related_objects([check.context for check in token_checks], "database")
        permission_by_token = {}
        owner_checks = {}
        for check in token_checks:
            scopes = scopes_by_token_id_and_operation[
                (check.actor.id, check.operation_name)
            ]
            table = check.context
            explicit = (table.id, None) in scopes or (None, table.database_id) in scopes
            if table.database.access_policy:
                if explicit and table.database.workspace_id == check.actor.workspace_id:
                    owner_checks[check] = PermissionCheck(
                        check.actor.user, check.operation_name, table
                    )
            elif explicit or (None, None) in scopes:
                permission_by_token[check] = True
                continue
            permission_by_token[check] = NoPermissionToTable(
                f"The provided token does not have "
                f"{OPERATION_TO_TOKEN_MAP[check.operation_name]} permissions to table {table.id}."
            )

        # Workspace-wide tokens predate the app. Only an explicit token grant
        # within its owner's current permissions can reach a protected database.
        if owner_checks:
            allowed = CoreHandler().check_multiple_permissions(
                list(owner_checks.values()), workspace, include_trash=include_trash
            )
            for check, owner_check in owner_checks.items():
                if allowed[owner_check]:
                    permission_by_token[check] = True
        return permission_by_token
