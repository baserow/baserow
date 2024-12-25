from typing import List, Optional

from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import CannotCalculateIntermediateOrder
from baserow.core.handler import CoreHandler
from baserow.core.models import Application
from baserow.core.user_sources.exceptions import UserSourceNotInSameApplication
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.operations import (
    CreateUserSourceOperationType,
    DeleteUserSourceOperationType,
    ListUserSourcesApplicationOperationType,
    LoginUserSourceOperationType,
    ReadUserSourceOperationType,
    UpdateUserSourceOperationType,
)
from baserow.core.user_sources.registries import UserSourceType
from baserow.core.user_sources.signals import (
    user_source_created,
    user_source_deleted,
    user_source_moved,
    user_source_orders_recalculated,
    user_source_updated,
)
from baserow.core.user_sources.types import UserSourceForUpdate


class UserSourceService:
    def __init__(self):
        self.handler = UserSourceHandler()

    def get_user_source(
        self, user: AbstractUser, user_source_id: int, for_authentication: bool = False
    ) -> UserSource:
        """
        Returns an user_source instance from the database. Also checks the user
        permissions.

        :param user: The user trying to get the user_source.
        :param user_source_id: The ID of the user_source.
        :param for_authentication: If true we check a different permission.
        :return: The user_source instance.
        """

        user_source = self.handler.get_user_source(user_source_id)

        operation = (
            LoginUserSourceOperationType.type
            if for_authentication
            else ReadUserSourceOperationType.type
        )

        CoreHandler().check_permissions(
            user,
            operation,
            workspace=user_source.application.workspace,
            context=user_source,
        )

        return user_source

    def get_user_source_by_uid(
        self, user: AbstractUser, user_source_uid: str, for_authentication: bool = False
    ) -> UserSource:
        """
        Returns a user_source instance from the database. Also checks the user
        permissions.

        :param user: The user trying to get the user_source.
        :param user_source_uid: The uid of the user_source.
        :param for_authentication: If true we check a different permission.
        :return: The user_source instance.
        """

        user_source = self.handler.get_user_source_by_uid(user_source_uid)

        operation = (
            LoginUserSourceOperationType.type
            if for_authentication
            else ReadUserSourceOperationType.type
        )

        CoreHandler().check_permissions(
            user,
            operation,
            workspace=user_source.application.workspace,
            context=user_source,
        )

        return user_source

    def get_user_sources(
        self, user: AbstractUser, application: Application
    ) -> List[UserSource]:
        """
        Gets all the user_sources of a given application visible to the given user.

        :param user: The user trying to get the user_sources.
        :param application: The application that holds the user_sources.
        :return: The user_sources of that application.
        """

        CoreHandler().check_permissions(
            user,
            ListUserSourcesApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        user_user_sources = CoreHandler().filter_queryset(
            user,
            ListUserSourcesApplicationOperationType.type,
            UserSource.objects.all(),
            workspace=application.workspace,
        )

        return self.handler.get_user_sources(
            application=application, base_queryset=user_user_sources
        )

    def create_user_source(
        self,
        user: AbstractUser,
        user_source_type: UserSourceType,
        application: Application,
        before: Optional[UserSource] = None,
        **kwargs,
    ) -> UserSource:
        """
        Creates a new user_source for an application given the user permissions.

        :param user: The user trying to create the user_source.
        :param user_source_type: The type of the user_source.
        :param application: The application the user_source exists in.
        :param before: If set, the new user_source is inserted before this user_source.
        :param kwargs: Additional attributes of the user_source.
        :return: The created user_source.
        """

        CoreHandler().check_permissions(
            user,
            CreateUserSourceOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        prepared_values = user_source_type.prepare_values(kwargs, user)

        try:
            new_user_source = self.handler.create_user_source(
                user_source_type, application, before=before, **prepared_values
            )
        except CannotCalculateIntermediateOrder:
            self.recalculate_full_orders(user, application)
            # If the `find_intermediate_order` fails with a
            # `CannotCalculateIntermediateOrder`, it means that it's not possible
            # calculate an intermediate fraction. Therefore, must reset all the
            # orders of the user_sources (while respecting their original order),
            # so that we can then can find the fraction any many more after.
            before.refresh_from_db()
            new_user_source = self.handler.create_user_source(
                user_source_type, application, before=before, **prepared_values
            )

        new_user_source.get_type().after_create(user, new_user_source, prepared_values)

        user_source_created.send(
            self,
            user_source=new_user_source,
            user=user,
            before_id=before.id if before else None,
        )

        return new_user_source

    def update_user_source(
        self, user: AbstractUser, user_source: UserSourceForUpdate, **kwargs
    ) -> UserSource:
        """
        Updates and user_source with values. Will also check if the values are allowed
        to be set on the user_source first.

        :param user: The user trying to update the user_source.
        :param user_source: The user_source that should be updated.
        :param kwargs: The values that should be set on the user_source.
        :return: The updated user_source.
        """

        CoreHandler().check_permissions(
            user,
            UpdateUserSourceOperationType.type,
            workspace=user_source.application.workspace,
            context=user_source,
        )

        user_source_type: UserSourceType = user_source.get_type()
        prepared_values = user_source_type.prepare_values(kwargs, user, user_source)

        # Detect if a user re-count is required. Per user source type
        # we track which properties changing triggers a recount.
        trigger_user_count_update = (
            user_source_type.after_user_source_update_requires_user_recount(
                user_source, prepared_values
            )
        )

        user_source = self.handler.update_user_source(
            user_source_type, user_source, **prepared_values
        )

        user_source_type.after_update(
            user,
            user_source,
            prepared_values,
            trigger_user_count_update=trigger_user_count_update,
        )

        user_source_updated.send(self, user_source=user_source, user=user)

        return user_source

    def delete_user_source(self, user: AbstractUser, user_source: UserSourceForUpdate):
        """
        Deletes an user_source.

        :param user: The user trying to delete the user_source.
        :param user_source: The to-be-deleted user_source.
        """

        application = user_source.application

        CoreHandler().check_permissions(
            user,
            DeleteUserSourceOperationType.type,
            workspace=application.workspace,
            context=user_source,
        )

        self.handler.delete_user_source(user_source)

        user_source_deleted.send(
            self, user_source_id=user_source.id, application=application, user=user
        )

    def move_user_source(
        self,
        user: AbstractUser,
        user_source: UserSourceForUpdate,
        before: Optional[UserSource] = None,
    ) -> UserSource:
        """
        Moves an user_source in the application before another user_source. If the
        `before` user_source is omitted the user_source is moved at the end of the
        application.

        :param user: The user who move the user_source.
        :param user_source: The user_source we want to move.
        :param before: The user_source before which we want to move the given
            user_source.
        :return: The user_source with an updated order.
        """

        CoreHandler().check_permissions(
            user,
            UpdateUserSourceOperationType.type,
            workspace=user_source.application.workspace,
            context=user_source,
        )

        # Check we are on the same application.
        if before and user_source.application_id != before.application_id:
            raise UserSourceNotInSameApplication()

        try:
            user_source = self.handler.move_user_source(user_source, before=before)
        except CannotCalculateIntermediateOrder:
            # If it's failing, we need to recalculate all orders then move again.
            self.recalculate_full_orders(user, user_source.application)
            # Refresh the before user_source as the order might have changed.
            before.refresh_from_db()
            user_source = self.handler.move_user_source(user_source, before=before)

        user_source_moved.send(self, user_source=user_source, before=before, user=user)

        return user_source

    def recalculate_full_orders(self, user: AbstractUser, application: Application):
        """
        Recalculates the order to whole numbers of all user_sources of the given
        application and send a signal.
        """

        self.handler.recalculate_full_orders(application)

        user_source_orders_recalculated.send(self, application=application)
