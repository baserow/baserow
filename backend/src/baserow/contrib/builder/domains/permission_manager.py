from django.contrib.auth import get_user_model

from baserow.contrib.builder.data_sources.operations import (
    DispatchDataSourceOperationType,
    ListDataSourcesPageOperationType,
)
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.elements.operations import ListElementsPageOperationType
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.workflow_actions.operations import (
    DispatchBuilderWorkflowActionOperationType,
    ListBuilderWorkflowActionsPageOperationType,
)
from baserow.core.operations import ReadApplicationOperationType
from baserow.core.registries import PermissionManagerType, operation_type_registry
from baserow.core.subjects import AnonymousUserSubjectType, UserSubjectType
from baserow.core.user_sources.operations import (
    AuthenticateUserSourceOperationType,
    ListUserSourcesApplicationOperationType,
    LoginUserSourceOperationType,
)
from baserow.core.user_sources.subjects import UserSourceUserSubjectType

User = get_user_model()


class AllowPublicBuilderManagerType(PermissionManagerType):
    """
    Allow some read operations on public builders for all users even anonymous.
    """

    type = "allow_public_builder"
    supported_actor_types = [
        UserSubjectType.type,
        UserSourceUserSubjectType.type,
        AnonymousUserSubjectType.type,
    ]

    # Public elements, public data sources and public actions
    page_level_operations = [
        ListElementsPageOperationType.type,
        ListDataSourcesPageOperationType.type,
        ListBuilderWorkflowActionsPageOperationType.type,
    ]
    # Data source or Action dispatch
    sub_page_level_operations = [
        DispatchDataSourceOperationType.type,
        DispatchBuilderWorkflowActionOperationType.type,
    ]
    sub_application_level_operations = [
        LoginUserSourceOperationType.type,
        AuthenticateUserSourceOperationType.type,
    ]
    application_level_operations = [
        ReadApplicationOperationType.type,
        ListUserSourcesApplicationOperationType.type,
    ]

    def check_multiple_permissions(self, checks, workspace=None, include_trash=False):
        result = {}

        for check in checks:
            operation_type = operation_type_registry.get(check.operation_name)
            if operation_type.type in self.page_level_operations:
                builder = check.context.builder
            elif operation_type.type in self.sub_page_level_operations:
                builder = check.context.page.builder
            elif (
                operation_type.type in self.sub_application_level_operations
                and isinstance(check.context.application.specific, Builder)
            ):
                builder = check.context.application.specific
            elif (
                operation_type.type in self.application_level_operations
                and isinstance(check.context.specific, Builder)
            ):
                builder = check.context.specific
            else:
                continue

            # Exception here, we don't want to login if we are not Anonymous.
            # This disables the "double" auth for published User sources.
            if (
                operation_type.type == LoginUserSourceOperationType.type
                and not isinstance(check.actor, AnonymousUserSubjectType.model_class)
            ):
                continue

            if (
                isinstance(check.actor, UserSourceUserSubjectType.model_class)
                and operation_type.type != AuthenticateUserSourceOperationType.type
            ):
                if check.actor.user_source.application_id == builder.id:
                    # The user source user is from the same application. Let's allow it.
                    result[check] = True
                else:
                    # Otherwise we don't allow it. Yes the authenticated US user has
                    # less permissions than an AnonymousUser. This is because the
                    # authentication populate the `request.user_source_user` and can
                    # give access to specific data.
                    continue

            if DomainHandler().get_domain_for_builder(builder) is not None:
                # it's a public builder, we allow it.
                result[check] = True

        return result

    def get_permissions_object(self, actor, workspace=None):
        return None
