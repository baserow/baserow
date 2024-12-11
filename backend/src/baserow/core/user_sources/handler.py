from ast import Dict
from typing import Iterable, List, Optional, Union
from zipfile import ZipFile

from django.conf import settings
from django.core.files.storage import Storage
from django.db.models import QuerySet

from loguru import logger

from baserow.core.db import specific_iterator
from baserow.core.exceptions import ApplicationOperationNotSupported
from baserow.core.models import Application
from baserow.core.registries import application_type_registry
from baserow.core.storage import ExportZipFile
from baserow.core.user_sources.exceptions import UserSourceDoesNotExist
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import (
    UserSourceType,
    user_source_type_registry,
)
from baserow.core.utils import extract_allowed

from .types import UserSourceForUpdate


class UserSourceHandler:
    allowed_fields_create = ["type", "name", "integration"]
    allowed_fields_update = ["name", "integration"]

    def get_user_source(
        self, user_source_id: int, base_queryset: Optional[QuerySet] = None
    ) -> UserSource:
        """
        Returns a user_source instance from the database.

        :param user_source_id: The ID of the user_source.
        :param base_queryset: The base queryset use to build the query if provided.
        :raises UserSourceDoesNotExist: If the user_source can't be found.
        :return: The specific user_source instance.
        """

        queryset = (
            base_queryset if base_queryset is not None else UserSource.objects.all()
        )

        try:
            user_source = (
                queryset.select_related("application", "application__workspace")
                .get(id=user_source_id)
                .specific
            )
        except UserSource.DoesNotExist as exc:
            raise UserSourceDoesNotExist() from exc

        return user_source

    def get_user_source_by_uid(
        self,
        user_source_uid: str,
        base_queryset: Optional[QuerySet] = None,
    ) -> UserSource:
        """
        Returns a user_source instance from the database.

        :param user_source_uid: The uid of the user_source.
        :param base_queryset: The base queryset use to build the query if provided.
        :raises UserSourceDoesNotExist: If the user_source can't be found.
        :return: The specific user_source instance.
        """

        queryset = (
            base_queryset if base_queryset is not None else UserSource.objects.all()
        )

        try:
            user_source = (
                queryset.select_related("application", "application__workspace")
                .get(uid=user_source_uid)
                .specific
            )
        except UserSource.DoesNotExist as exc:
            raise UserSourceDoesNotExist() from exc

        return user_source

    def get_user_source_for_update(
        self, user_source_id: int, base_queryset: Optional[QuerySet] = None
    ) -> UserSourceForUpdate:
        """
        Returns a user_source instance from the database that can be safely updated.

        :param user_source_id: The ID of the user_source.
        :param base_queryset: The base queryset use to build the query if provided.
        :raises UserSourceDoesNotExist: If the user_source can't be found.
        :return: The user_source instance.
        """

        queryset = (
            base_queryset if base_queryset is not None else UserSource.objects.all()
        )

        queryset = queryset.select_for_update(of=("self",))

        return self.get_user_source(
            user_source_id,
            base_queryset=queryset,
        )

    def get_user_sources(
        self,
        application: Optional[Application] = None,
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
    ) -> Union[QuerySet[UserSource], Iterable[UserSource]]:
        """
        Gets all the specific user_sources of a given application.

        :param application: The application that holds the user_sources if provided.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Whether to return the generic user_sources or the specific
            instances.
        :return: The user_sources of that application.
        """

        queryset = (
            base_queryset if base_queryset is not None else UserSource.objects.all()
        )

        if application:
            queryset = queryset.filter(application=application)

        if specific:
            # Enhance the queryset for the given user_source type for better perf
            def per_content_type_queryset_hook(model, queryset):
                user_source_type = user_source_type_registry.get_by_model(model)
                return user_source_type.enhance_queryset(queryset)

            queryset = queryset.select_related(
                "content_type", "application", "application__workspace"
            )

            return specific_iterator(
                queryset, per_content_type_queryset_hook=per_content_type_queryset_hook
            )
        else:
            return queryset

    def get_all_roles_for_application(self, application: Application) -> List[str]:
        """Return a sorted list of all unique user roles for a specific application."""

        user_roles = set()
        for user_source in self.get_user_sources(application):
            user_roles.update(user_source.get_type().get_roles(user_source))

        return sorted(list(user_roles))

    def create_user_source(
        self,
        user_source_type: UserSourceType,
        application: Application,
        before=None,
        **kwargs,
    ) -> UserSource:
        """
        Creates a new user_source for an application.

        :param user_source_type: The type of the user_source.
        :param application: The application the user_source exists in.
        :param before: The user_source before which we want to create the user_source.
            If not provided, the user_source is added as last one.
        :param kwargs: Additional attributes of the user_source.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the user_source of the application
            must be recalculated in this case before calling this method again.
        :return: The created user_source.
        """

        application_type = application_type_registry.get_by_model(
            application.specific_class
        )

        if not application_type.supports_user_sources:
            raise ApplicationOperationNotSupported()

        if before:
            order = UserSource.get_unique_order_before_user_source(before)
        else:
            order = UserSource.get_last_order(application)

        allowed_values = extract_allowed(
            kwargs, self.allowed_fields_create + user_source_type.allowed_fields
        )

        user_source = user_source_type.model_class(
            application=application, order=order, **allowed_values
        )
        user_source.save()

        # We need to save the user_source first to make sure we have the Id in case if
        # we use it in the gen_uid method.
        uid = user_source_type.gen_uid(user_source)
        user_source.uid = uid
        user_source.save()

        return user_source

    def update_user_source(
        self,
        user_source_type: UserSourceType,
        user_source: UserSourceForUpdate,
        **kwargs,
    ) -> UserSource:
        """
        Updates and user_source with values. Will also check if the values are allowed
        to be set on the user_source first.

        :param user_source_type: The type of the user_source.
        :param user_source: The user_source that should be updated.
        :param kwargs: The values that should be set on the user_source.
        :return: The updated user_source.
        """

        allowed_updates = extract_allowed(
            kwargs, self.allowed_fields_update + user_source_type.allowed_fields
        )

        for key, value in allowed_updates.items():
            setattr(user_source, key, value)

        uid = user_source_type.gen_uid(user_source)
        user_source.uid = uid
        user_source.save()

        return user_source

    def delete_user_source(self, user_source: UserSource):
        """
        Deletes a user_source.

        :param user_source: The to-be-deleted user_source.
        """

        user_source.delete()

    def move_user_source(
        self, user_source: UserSourceForUpdate, before: Optional[UserSource] = None
    ) -> UserSource:
        """
        Moves the given user_source before the specified `before` user_source in the
        same application.

        :param user_source: The user_source to move.
        :param before: The user_source before which to move the `user_source`. If
            before is not specified, the user_source is moved at the end of the list.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the user_source of the application
            must be recalculated in this case before calling this method again.
        :return: The moved user_source.
        """

        if before:
            user_source.order = UserSource.get_unique_order_before_user_source(before)
        else:
            user_source.order = UserSource.get_last_order(user_source.application)

        user_source.save()

        return user_source

    def recalculate_full_orders(
        self,
        application: Application,
    ):
        """
        Recalculates the order to whole numbers of all user_sources of the given
        application.
        """

        UserSource.recalculate_full_orders(
            queryset=UserSource.objects.filter(application=application)
        )

    def export_user_source(
        self,
        user_source,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ):
        return user_source.get_type().export_serialized(
            user_source,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def import_user_source(
        self,
        application,
        serialized_user_source,
        id_mapping,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ):
        if "user_sources" not in id_mapping:
            id_mapping["user_sources"] = {}

        user_source_type = user_source_type_registry.get(serialized_user_source["type"])
        user_source = user_source_type.import_serialized(
            application,
            serialized_user_source,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

        id_mapping["user_sources"][serialized_user_source["id"]] = user_source.id

        return user_source

    def update_all_user_source_counts(
        self, user_source_type: Optional[str] = None, raise_on_error: bool = False
    ):
        """
        Responsible for iterating over all registered user source types, and asking the
        implementation to count the number of external users it points to.

        :param user_source_type: Optionally, a specific user source type to update.
        :param raise_on_error: Whether to raise an exception when a user source
            type raises an exception, or to continue with the remaining user sources.
        :return: None
        """

        user_source_types = (
            [user_source_type_registry.get(user_source_type)]
            if user_source_type
            else user_source_type_registry.get_all()
        )
        for user_source_type in user_source_types:
            try:
                user_source_type.update_user_count()
            except Exception as e:
                if not settings.TESTS:
                    logger.exception(
                        f"Counting {user_source_type.type} external users failed: {e}"
                    )
                if raise_on_error:
                    raise e
                continue
