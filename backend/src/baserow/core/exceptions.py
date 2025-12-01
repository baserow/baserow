from django.db import OperationalError


class PermissionException(Exception):
    """
    Every permission related exception should inherit from this one.
    """


class IsNotAdminError(PermissionException):
    """
    Raised when the user tries to perform an action that is not allowed because they
    does not have admin permissions.
    """


class UserNotInWorkspace(PermissionException):
    """Raised when the user doesn't have access to the related workspace."""

    def __init__(self, user=None, workspace=None, *args, **kwargs):
        if user and workspace:
            super().__init__(
                f"User {user} doesn't belong to workspace {workspace}.", *args, **kwargs
            )
        else:
            super().__init__(
                "The user doesn't belong to the workspace", *args, **kwargs
            )


class UserInvalidWorkspacePermissionsError(PermissionException):
    """
    Raised when a user doesn't have the right permissions to the related workspace.
    """

    def __init__(self, user, workspace, permissions, *args, **kwargs):
        self.user = user
        self.workspace = workspace
        self.permissions = permissions
        super().__init__(
            f"The user {user} doesn't have the right permissions {permissions} to "
            f"{workspace}.",
            *args,
            **kwargs,
        )


class PermissionDenied(PermissionException):
    """
    Generic permission exception when a user doesn't have the right permissions to do
    the given operations.
    """

    def __init__(self, actor=None, *args, **kwargs):
        if actor:
            super().__init__(
                f"{actor} doesn't have the required permissions.", *args, **kwargs
            )
        else:
            super().__init__(f"Permission denied.", *args, **kwargs)


class WorkspaceDoesNotExist(Exception):
    """Raised when trying to get a workspace that does not exist."""


class WorkspaceUserDoesNotExist(Exception):
    """Raised when trying to get a workspace user that does not exist."""


class WorkspaceUserAlreadyExists(Exception):
    """
    Raised when trying to create a workspace user that already exists. This could also
    be raised when an invitation is created for a user that is already part of the
    workspace.
    """


class MaxNumberOfPendingWorkspaceInvitesReached(Exception):
    """
    Raised when the maximum number of pending workspace invites has been reached.
    This value is configurable via the `BASEROW_MAX_PENDING_WORKSPACE_INVITES` setting.
    """


class WorkspaceUserIsLastAdmin(Exception):
    """
    Raised when the last admin of the workspace tries to leave it. This will leave the
    workspace in a state where no one has control over it. They either need to delete
    the workspace or make someone else admin.
    """


class CannotDeleteYourselfFromWorkspace(Exception):
    """
    Raised when the user tries to delete himself from the workspace.
    The `leave_workspace` method must be used in that case.
    """


class ApplicationDoesNotExist(Exception):
    """Raised when trying to get an application that does not exist."""


class ApplicationNotInWorkspace(Exception):
    """Raised when a provided application does not belong to a workspace."""

    def __init__(self, application_id=None, *args, **kwargs):
        self.application_id = application_id
        super().__init__(
            f"The application {application_id} does not belong to the workspace.",
            *args,
            **kwargs,
        )


class InstanceTypeAlreadyRegistered(Exception):
    """
    Raised when the instance model instance is already registered in the registry.
    """


class InstanceTypeDoesNotExist(Exception):
    """
    Raised when a requested instance model instance isn't registered in the registry.
    """

    def __init__(self, type_name, *args, **kwargs):
        self.type_name = type_name
        super().__init__(*args, **kwargs)


class ApplicationTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass


class ApplicationTypeDoesNotExist(InstanceTypeDoesNotExist):
    pass


class ApplicationOperationNotSupported(Exception):
    """
    Raised when the particular operation is not supported by the
    application type.
    """


class AuthenticationProviderTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass


class AuthenticationProviderTypeDoesNotExist(InstanceTypeDoesNotExist):
    pass


class PermissionManagerTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass


class PermissionManagerTypeDoesNotExist(InstanceTypeDoesNotExist):
    pass


class ObjectScopeTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass


class ObjectScopeTypeDoesNotExist(InstanceTypeDoesNotExist):
    pass


class OperationTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    pass


class OperationTypeDoesNotExist(InstanceTypeDoesNotExist):
    pass


class SubjectTypeNotExist(Exception):
    """Raised when trying to use a subject type that does not exist."""


class BaseURLHostnameNotAllowed(Exception):
    """
    Raised when the provided base url is not allowed when requesting a password
    reset email.
    """


class WorkspaceInvitationDoesNotExist(Exception):
    """
    Raised when the requested workspace invitation doesn't exist.
    """


class WorkspaceInvitationEmailMismatch(Exception):
    """
    Raised when the workspace invitation email is not the expected email address.
    """


class TemplateDoesNotExist(Exception):
    """
    Raised when the requested template does not exist in the database.
    """


class TemplateFileDoesNotExist(Exception):
    """
    Raised when the JSON template file does not exist in the
    APPLICATION_TEMPLATE_DIRS directory.
    """


class TrashItemDoesNotExist(Exception):
    """
    Raised when the trash item does not exist in the database.
    """


class LockConflict(Exception):
    """
    Generic base class used for exceptions raised when an operation fails as part of
    Baserow has been locked for some operation.
    """


class InvalidPermissionContext(Exception):
    """
    Used when an invalid context is passed to a permission checker.
    """


class MaxLocksPerTransactionExceededException(Exception):
    """
    Baserow can sometimes perform operations that require a Postgres LOCK on a large
    number of tuples. If this quantity results in the lock count exceeding the value
    set in `max_locks_per_transaction`, a subclass of this exception will be raised.
    """

    message = (
        "Baserow has exceeded the maximum number of PostgreSQL locks per transaction. "
        "Please read https://baserow.io/docs/technical/postgresql-locks"
    )


def is_max_lock_exceeded_exception(exception: OperationalError) -> bool:
    """
    Returns whether the `OperationalError` which we've been given
    is due to `max_locks_per_transaction` being exceeded.
    """

    return "You might need to increase max_locks_per_transaction" in exception.args[0]


class DuplicateApplicationMaxLocksExceededException(
    MaxLocksPerTransactionExceededException
):
    """
    If someone tries to duplicate an application with a lot of tables in a single
    transaction, it'll quickly exceed the `max_locks_per_transaction` value set
    in Postgres. This exception is raised when we detect the scenario.
    """

    message = (
        "Baserow attempted to duplicate an application, but exceeded the maximum "
        "number of PostgreSQL locks per transaction. Please read "
        "https://baserow.io/docs/technical/postgresql-locks"
    )


class LastAdminOfWorkspace(Exception):
    """
    Raised when somebody tries to remove the last admin of a workspace.
    """


class IdDoesNotExist(Exception):
    """
    Raised when an ID is queried that does not exist
    """

    def __init__(self, not_existing_id=None, *args, **kwargs):
        self.not_existing_id = not_existing_id
        super().__init__(
            f"The id {not_existing_id} does not exist.",
            *args,
            **kwargs,
        )


class CannotCalculateIntermediateOrder(Exception):
    """
    Raised when an intermediate order can't be calculated. This could be because the
    fractions are equal.
    """


class FeatureDisabledException(Exception):
    """
    Raised when a feature is disabled.
    """


class DeadlockException(OperationalError):
    """
    Raised when a database operation fails due to a deadlock.
    """

    message = "The database failed to commit the transaction due to a deadlock."
