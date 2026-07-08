from abc import ABC

from baserow.core.operations import ApplicationOperationType
from baserow.core.registries import OperationType


class ListUserSourcesApplicationOperationType(ApplicationOperationType):
    type = "application.list_user_sources"
    object_scope_name = "user_source"


class OrderUserSourcesOperationType(ApplicationOperationType):
    type = "application.order_user_sources"
    object_scope_name = "user_source"


class CreateUserSourceOperationType(ApplicationOperationType):
    type = "application.create_user_source"


class UserSourceOperationType(OperationType, ABC):
    context_scope_name = "user_source"


class DeleteUserSourceOperationType(UserSourceOperationType):
    type = "application.user_source.delete"


class UpdateUserSourceOperationType(UserSourceOperationType):
    type = "application.user_source.update"


class ReadUserSourceOperationType(UserSourceOperationType):
    type = "application.user_source.read"


class RestoreUserSourceOperationType(UserSourceOperationType):
    type = "application.user_source.restore"


class AuthenticateUserSourceOperationType(UserSourceOperationType):
    type = "application.user_source.authenticate"


class LoginUserSourceOperationType(UserSourceOperationType):
    type = "application.user_source.login"
