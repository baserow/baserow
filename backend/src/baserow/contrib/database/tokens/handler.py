from typing import List, Union

from rest_framework.request import Request

from baserow.contrib.database.exceptions import DatabaseDoesNotBelongToGroup
from baserow.contrib.database.models import Database, Table
from baserow.contrib.database.table.exceptions import TableDoesNotBelongToGroup
from baserow.contrib.database.tokens.constants import (
    TOKEN_OPERATION_TYPES,
    TOKEN_TO_OPERATION_MAP,
)
from baserow.core.handler import CoreHandler
from baserow.core.registries import object_scope_type_registry
from baserow.core.types import PermissionCheck
from baserow.core.utils import random_string

from .exceptions import (
    MaximumUniqueTokenTriesError,
    NoPermissionToTable,
    TokenDoesNotBelongToUser,
    TokenDoesNotExist,
)
from .models import Token, TokenPermission
from .operations import (
    CreateTokenOperationType,
    ReadTokenOperationType,
    UseTokenOperationType,
)


class TokenHandler:
    def get_by_key(self, key):
        """
        Fetches a single token instance based on the key.

        :param key: The unique token key.
        :param key: str
        :raises TokenDoesNotExist: Raised when the requested token was not found or
            if it does not belong to the user.
        :return: The fetched token matching the provided key.
        :rtype: Token
        """

        try:
            token = Token.objects.select_related("workspace", "user").get(key=key)
        except Token.DoesNotExist:
            raise TokenDoesNotExist(f"The token with key {key} does not exist.")

        return token

    def get_token(self, user, token_id, base_queryset=None):
        """
        Fetches a single token and checks if the user belongs to the workspace.

        :param user: The user on whose behalf the token is requested.
        :type user: User
        :param token_id: The id of the requested token.
        :type token_id: int
        :param base_queryset: The base queryset from where to select the token
            object from. This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises TokenDoesNotExist: Raised when the requested token was not found or
            if it does not belong to the user.
        :return: The fetched token.
        :rtype: Token
        """

        if base_queryset is None:
            base_queryset = Token.objects

        try:
            token = base_queryset.select_related("workspace").get(
                id=token_id, user=user
            )
        except Token.DoesNotExist:
            raise TokenDoesNotExist(f"The token with id {token_id} does not exist.")

        workspace = token.workspace
        CoreHandler().check_permissions(
            user, ReadTokenOperationType.type, workspace=workspace, context=token
        )

        return token

    def generate_unique_key(self, length=32, max_tries=1000):
        """
        Generates a unique token key.

        :param length: Indicates the amount of characters that the token must contain.
        :type length: int
        :param max_tries: The maximum amount of tries to check if a token with the key
            already exists.
        :type max_tries: int
        :raises MaximumUniqueTokenTriesError: When the maximum amount of tries has
            been exceeded. A new generated token is tried every time the token
            already exists.
        :return: A unique token
        :rtype: str
        """

        i = 0

        while True:
            if i > max_tries:
                raise MaximumUniqueTokenTriesError(
                    f"Tried {max_tries} tokens, but none of them are unique."
                )

            i += 1
            token = random_string(length)

            if not Token.objects.filter(key=token).exists():
                return token

    def create_token(self, user, workspace, name):
        """
        Creates a new API token.

        :param user: The user of whose behalf the token is created.
        :type user: User
        :param workspace: The workspace object of which the token is related to.
        :type workspace: Workspace
        :param name: The name of the token.
        :type name: str
        :return: The created token instance.
        :rtype: Token
        """

        CoreHandler().check_permissions(
            user, CreateTokenOperationType.type, workspace=workspace, context=workspace
        )

        token = Token.objects.create(
            name=name, key=self.generate_unique_key(), user=user, workspace=workspace
        )

        # The newly created token should have access to all the tables in the workspace
        # when it is created.
        self.update_token_permissions(
            user, token, create=True, read=True, update=True, delete=True
        )

        return token

    def rotate_token_key(self, user, token):
        """
        Generates a new key for the provided token object and updates it.

        :param user: The user on whose behalf the key is refreshed.
        :type user: User
        :param token: The token instance of which the key needs to be refreshed.
        :type token: Token
        :raises TokenDoesNotBelongToUser: When the provided token does not belong the
            provided user.
        :return: The updated token instance.
        :rtype: Token
        """

        if not user.id == token.user_id:
            raise TokenDoesNotBelongToUser(
                "The user is not authorized to rotate the " "key."
            )

        token.key = self.generate_unique_key()
        token.save()

        return token

    def update_token(self, user, token, name):
        """
        Updates an existing token.

        :param user: The user on whose behalf the token is updated.
        :type user: User
        :param token: The token object that needs to be updated.
        :type token: Token
        :param name: The new name of the token.
        :type name: str
        :raises TokenDoesNotBelongToUser: When the provided token does not belong the
            provided user.
        :return: The updated token instance.
        :rtype: Token
        """

        if not user.id == token.user_id:
            raise TokenDoesNotBelongToUser(
                "The user is not authorized to rotate the " "key."
            )

        token.name = name
        token.save()

        return token

    def update_token_permissions(
        self, user, token, create=None, read=None, update=None, delete=None
    ):
        """
        Updates create, read, update and delete permissions of the provided token.

        Example:

        TokenHandler().update_token_permissions(
            token=token,
            create=[Database.objects.get(pk=1), Table.objects.get(pk=10)],
            read=True,
            update=False,
            delete=None
        )

        * Gives create row permissions to all tables in database 1 and to table 10.
        * Gives read permissions to all tables in the token's workspace.
        * Doesn't give permissions to update any row in all the tables related to the
          token's workspace.
        * Doesn't give permissions to delete any row in all the tables related to the
          token's workspace.

        :param user: The user on whose behalf the permissions are updated.
        :type user: User
        :param token: The token for which the permissions need to be updated.
        :type token: Token
        :param create: Indicates for which tables the token can create rows. True
            indicates all tables in the workspace, a database indicates all tables in
            the provided databases and a table indicates only that table. Multiple
            values can be provided in a list.
        :type create: list, bool or none
        :param read: Indicates for which tables the token can list and get rows. True
            indicates all tables in the workspace, a database indicates all tables in
            the provided databases and a table indicates only that table. Multiple
            values can be provided in a list.
        :type read: list, bool or none
        :param update: Indicates for which tables the token can update rows. True
            indicates all tables in the workspace, a database indicates all tables in
            the provided databases and a table indicates only that table. Multiple
            values can be provided in a list.
        :type update: list, bool or none
        :param delete: Indicates for which tables the token can delete rows. True
            indicates all tables in the workspace, a database indicates all tables in
            the provided databases and a table indicates only that table. Multiple
            values can be provided in a list.
        :type delete: list, bool or none
        :raises DatabaseDoesNotBelongToGroup: If a provided database instance does not
            belong to the token's workspace.
        :raises TableDoesNotBelongToGroup: If a provided table instance does not
            belong to the token's workspace.
        :raises TokenDoesNotBelongToUser: When the provided token does not belong the
            provided user.
        """

        if not user.id == token.user_id:
            raise TokenDoesNotBelongToUser(
                "The user is not authorized to delete the token."
            )

        table_scope_type = object_scope_type_registry.get("database_table")

        # Does the user have the permissions to perform these operations?
        for object_list, token_action in [
            (create, "create"),
            (read, "read"),
            (update, "update"),
            (delete, "delete"),
        ]:
            # Only check permission for tables so ignoring non list type (True or False)
            # and select only database_table objects
            # We can't check the permission at workspace and database level because it
            # just means that all underlying tables are affected but only those
            # already visible by the user. It's not a security check. The security
            # check is done in the corresponding API endpoint.
            if isinstance(object_list, list):
                all_tables = [
                    obj for obj in object_list if table_scope_type.contains(obj)
                ]
                for table in all_tables:
                    CoreHandler().check_permissions(
                        user,
                        TOKEN_TO_OPERATION_MAP[token_action],
                        workspace=token.workspace,
                        context=table,
                    )

        existing_permissions = token.tokenpermission_set.all()
        desired_permissions = []

        # Create a list of desired tokens based on the provided create, read, update
        # and delete parameters.
        for type_name in TOKEN_OPERATION_TYPES:
            value = locals()[type_name]

            if value is True:
                desired_permissions.append(TokenPermission(token=token, type=type_name))
            elif isinstance(value, list):
                for instance in value:
                    if isinstance(instance, Database):
                        if instance.workspace_id != token.workspace_id:
                            raise DatabaseDoesNotBelongToGroup(
                                f"The database {instance.id} does not belong to the "
                                f"token's workspace."
                            )

                        desired_permissions.append(
                            TokenPermission(
                                token=token, type=type_name, database_id=instance.id
                            )
                        )
                    elif isinstance(instance, Table):
                        if instance.database.workspace_id != token.workspace_id:
                            raise TableDoesNotBelongToGroup(
                                f"The table {instance.id} does not belong to the "
                                f"token's workspace."
                            )

                        desired_permissions.append(
                            TokenPermission(
                                token=token, type=type_name, table_id=instance.id
                            )
                        )

        def equals(permission_1, permission_2):
            """
            Checks if the two provided permissions are the same.
            """

            return (
                permission_1.token_id == permission_2.token_id
                and permission_1.type == permission_2.type
                and permission_1.database_id == permission_2.database_id
                and permission_1.table_id == permission_2.table_id
            )

        # Check which existing permissions must be deleted by comparing them to the
        # desired permissions.
        to_delete = [
            existing.id
            for existing in existing_permissions
            if not any([equals(existing, desired) for desired in desired_permissions])
        ]

        # Check which permission must be created by comparing them to the existing
        # permissions.
        to_create = [
            desired
            for desired in desired_permissions
            if not any([equals(desired, existing) for existing in existing_permissions])
        ]

        # Delete the permissions that must be delete in bulk.
        if len(to_delete) > 0:
            TokenPermission.objects.filter(id__in=to_delete).delete()

        # Create the permissions that must be created in bulk.
        if len(to_create) > 0:
            TokenPermission.objects.bulk_create(to_create)

    def has_table_permission(
        self, token: Token, type_name: Union[str, List[str]], table: Table
    ) -> bool:
        """
        Checks if the provided token has access to perform an operation on the provided
        table.

        :param token: The token instance.
        :param type_name: The CRUD operation, create, read, update or delete to check
            the permissions for. Can be a list if you want to check at least one of the
            listed operation.
        :param table: The table object to check the permissions for.
        :return: Indicates if the token has permissions to perform the operation on
            the provided table.
        """

        if token.workspace_id != table.database.workspace_id:
            return False

        # First check the user has the permission to use the token
        if not CoreHandler().check_permissions(
            token.user,
            UseTokenOperationType.type,
            workspace=token.workspace,
            context=token,
        ):
            return False

        type_names = type_name if isinstance(type_name, list) else [type_name]

        checks = [
            PermissionCheck(token, TOKEN_TO_OPERATION_MAP[token_operation], table)
            for token_operation in type_names
            if token_operation in TOKEN_TO_OPERATION_MAP
        ]

        token_permission = CoreHandler().check_multiple_permissions(
            checks, token.workspace
        )

        # At least one must be True
        return any([v is True for v in token_permission.values()])

    def get_token_from_request(self, request: Request) -> Token | None:
        """
        Extracts the token from the request. If the token is not found then None is
        returned.

        :param request: The request from which the token must be extracted.
        :return: The extracted token or None if it could not be found.
        """

        return getattr(request, "user_token", None)

    def raise_table_permission_error(self, table: Table, type_name: str | list[str]):
        """
        Raises an exception indicating that the provided token does not have permission
        to the provided table. Used to raise a consistent exception when the token does
        not have permission to the table.

        :param table: The table object to check the permissions for.
        :param type_name: The CRUD operation, create, read, update or delete to check
            the permissions for. Can be a list if you want to check at least one of the
            listed operation.
        :raises NoPermissionToTable: Raised when the token does not have permissions to
        """

        raise NoPermissionToTable(
            f"The provided token does not have {type_name} "
            f"permissions to table {table.id}."
        )

    def check_table_permissions(
        self,
        request_or_token: Request | Token,
        type_name: str | list[str],
        table: Table,
        force_check=False,
    ):
        """
        Instead of returning True or False, this method will raise an exception if the
        token does not have permission to the table.

        :param request_or_token: If a request is provided then the token will be
            extracted from the request. Otherwise a token object is expected.
        :param type_name: The CRUD operation, create, read, update or delete to check
            the permissions for. Can be a list if you want to check at least one of the
            listed operation.
        :param table: The table object to check the permissions for.
        :param force_check: Indicates if a NoPermissionToTable exception must be raised
            when the token could not be extracted from the request. This can be
            useful if a view accepts multiple types of authentication.
        :raises ValueError: when neither a Token or HttpRequest is provided.
        :raises NoPermissionToTable: when the token does not have permissions to the
            table.
        """

        token = None
        if isinstance(request_or_token, Token):
            token = request_or_token
        elif isinstance(request_or_token, Request):
            token = self.get_token_from_request(request_or_token)
        else:
            raise ValueError(
                "The provided instance should be a HttpRequest or Token object."
            )

        should_check_permissions = token is not None or force_check
        has_table_permissions = token is not None and self.has_table_permission(
            token, type_name, table
        )
        if should_check_permissions and not has_table_permissions:
            self.raise_table_permission_error(table, type_name)

    def delete_token(self, user, token):
        """
        Deletes an existing token

        :param user: The user on whose behalf the token is deleted.
        :type user: User
        :param token: The token object that needs to be deleted.
        :type token: Token
        :raises TokenDoesNotBelongToUser: When the provided token does not belong the
            provided user.
        """

        if not user.id == token.user_id:
            raise TokenDoesNotBelongToUser(
                "The user is not authorized to delete the " "token."
            )

        token.delete()
