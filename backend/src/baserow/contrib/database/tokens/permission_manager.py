from collections import defaultdict

from baserow.contrib.database.tokens.exceptions import NoPermissionToTable
from baserow.contrib.database.tokens.models import TokenPermission
from baserow.contrib.database.tokens.subjects import TokenSubjectType
from baserow.core.registries import PermissionManagerType

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

        permission_by_token = {}
        for check in token_checks:
            scopes = scopes_by_token_id_and_operation[
                (check.actor.id, check.operation_name)
            ]
            context = check.context
            if (
                (None, None) in scopes
                or any(table_id == context.id for table_id, _ in scopes)
                or any(database_id == context.database_id for _, database_id in scopes)
            ):
                permission_by_token[check] = True
            else:
                permission_by_token[check] = NoPermissionToTable(
                    f"The provided token does not have "
                    f"{OPERATION_TO_TOKEN_MAP[check.operation_name]}"
                    f" permissions to table {context.id}."
                )

        return permission_by_token
