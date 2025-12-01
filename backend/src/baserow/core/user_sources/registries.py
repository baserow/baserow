import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Tuple, Type, TypeVar

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.exceptions import RequestBodyValidationException
from baserow.core.app_auth_providers.handler import AppAuthProviderHandler
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    EasyImportExportMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.constants import DEFAULT_USER_ROLE_PREFIX
from baserow.core.user_sources.user_source_user import UserSourceUser

from .models import UserSource
from .types import UserSourceDictSubClass, UserSourceSubClass


class UserSourceCount(NamedTuple):
    count: Optional[int]
    last_updated: Optional[datetime]


class UserSourceType(
    ModelInstanceMixin[UserSource],
    EasyImportExportMixin[UserSourceSubClass],
    CustomFieldsInstanceMixin,
    Instance,
    ABC,
):
    SerializedDict: Type[UserSourceDictSubClass]
    parent_property_name = "application"
    id_mapping_name = "user_sources"

    # When any of these properties are updated, the user count will be updated.
    properties_requiring_user_recount = []

    """
    An user_source type define a specific user_source with a given external service.
    """

    def enhance_queryset(self, queryset):
        """
        Allow to enhance the queryset when querying the user_source mainly to improve
        performances.
        """

        return queryset

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[UserSourceSubClass] = None,
    ) -> Dict[str, Any]:
        """
        The prepare_values hook gives the possibility to change the provided values
        that just before they are going to be used to create or update the instance. For
        example if an ID is provided, it can be converted to a model instance. Or to
        convert a certain date string to a date object. It's also an opportunity to add
        specific validations.

        :param values: The provided values.
        :param user: The user on whose behalf the change is made.
        :param instance: The current instance if it exists.
        :return: The updated values.
        """

        # We load the actual integration object
        if "integration_id" in values:
            integration_id = values.pop("integration_id")
            if integration_id is not None:
                integration = IntegrationHandler().get_integration(integration_id)
                values["integration"] = integration
            else:
                values["integration"] = None

        return values

    def after_create(self, user, user_source, values):
        """
        Add the auth providers.
        """

        if "auth_providers" in values:
            errors = []
            for ap in values["auth_providers"]:
                ap_type = app_auth_provider_type_registry.get(ap["type"])
                ap_type.check_user_source_compatibility(user_source)

                try:
                    AppAuthProviderHandler.create_app_auth_provider(
                        user, ap_type, user_source, **ap
                    )
                    errors.append({})
                except DRFValidationError as e:
                    errors.append(e.detail)
                    raise RequestBodyValidationException(
                        {"auth_providers": errors},
                    ) from e

    def after_update(
        self,
        user: AbstractUser,
        user_source: UserSource,
        values: Dict[str, Any],
        trigger_user_count_update: bool = False,
    ):
        """
        Responsible for re-creating `auth_providers` if they are updated, and also
        updating the user count if necessary.

        :param user: The user on whose behalf the change is made.
        :param user_source: The user source that has been updated.
        :param values: The values that have been updated.
        :param trigger_user_count_update: If True, the user count will be updated.
        """

        if "auth_providers" in values:
            user_source.auth_providers.all().delete()
            self.after_create(user, user_source, values)

        if trigger_user_count_update:
            from baserow.core.user_sources.handler import UserSourceHandler

            queryset = UserSourceHandler().get_user_sources(
                user_source.application,
                self.model_class.objects.filter(pk=user_source.pk),
                specific=True,
            )
            self.update_user_count(queryset)

    def serialize_property(
        self,
        instance: UserSource,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "order":
            return str(instance.order)

        if prop_name == "auth_providers":
            return [
                ap.get_type().export_serialized(
                    ap, files_zip=files_zip, storage=storage, cache=cache
                )
                for ap in AppAuthProviderHandler.list_app_auth_providers_for_user_source(
                    instance
                )
            ]

        return super().serialize_property(
            instance, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Dict[int, int]],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        if prop_name == "integration_id" and value:
            return id_mapping["integrations"][value]

        if prop_name == "uid":
            # We generate a temporary uuid to prevent DB integrity error but it will be
            # generated later once the instance exists
            return uuid.uuid4().hex

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> UserSourceSubClass:
        """
        Handles the auth provider import.
        """

        auth_providers = serialized_values.pop("auth_providers", [])

        created_user_source = super().import_serialized(
            parent, serialized_values, id_mapping, **kwargs
        )

        for auth_provider in auth_providers:
            auth_provider_type = app_auth_provider_type_registry.get(
                auth_provider["type"]
            )
            auth_provider_type.import_serialized(
                created_user_source,
                auth_provider,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                cache=cache,
            )

        return created_user_source

    def get_default_user_role(self, user_source: UserSource) -> str:
        """
        Generate the Default User Role for the User Source.

        The Visibility permission manager needs a user role to check whether
        a user has permissions to view a specific element.

        When the User Source does not have roles defined, a default user role
        is used by the Visibility permission manager to control access to elements.
        """

        return f"{DEFAULT_USER_ROLE_PREFIX}{user_source.id}"

    @abstractmethod
    def gen_uid(self, user_source):
        """
        Should generate a new UID given a user_source. This UID must be different if
        the configuration has changed substantially and the current user tokens need
        to be invalidated.
        """

    @abstractmethod
    def list_users(
        self, user_source: UserSource, count: int = 5, search: str = ""
    ) -> Iterable[UserSourceUser]:
        """
        Returns a list of users for this user source.

        :param user_source: The user source instance.
        :param count: The number of user we want.
        :param search: A search term to filter the users.
        :return: An iterable of users.
        """

    @abstractmethod
    def get_roles(self, user_source: UserSource) -> List[str]:
        """
        Returns a list of strings representing valid roles for the user_source.

        :param user_source: The user source used to get the roles.
        :return: A list of roles if any found with the given parameters.
        """

    @abstractmethod
    def create_user(
        self, user_source: UserSource, email: str, name: str
    ) -> UserSourceUser:
        """
        Create a user for the given user source instance from it's email and name.

        :param user_source: The user source we want to create the user for.
        :param email: Email of the user to create.
        :param name: Name of the user to create.
        :return: A user instance.
        """

    @abstractmethod
    def get_user(self, user_source: UserSource, **kwargs) -> UserSourceUser:
        """
        Returns a user given some args.

        :param user_source: The user source used to get the user.
        :param kwargs: Keyword arguments to get the user.
        :raises UserNotFound: When the user can't be found.
        :return: A user instance if any found with the given parameters.
        """

    def get_or_create_user(
        self, user_source: UserSource, email: str, name: str
    ) -> Tuple[UserSourceUser, bool]:
        """
        Shorthand to create a user if he doesn't exist.
        """

        try:
            return self.get_user(user_source, email=email), False
        except UserNotFound:
            return self.create_user(user_source, email, name), True

    @abstractmethod
    def authenticate(self, user_source: UserSource, **kwargs) -> UserSourceUser:
        """
        Authenticates using the given credentials. It uses the password auth provider.

        :param user_source: The user source used to authenticate the user.
        :param kwargs: The credential used to authenticate the user.
        """

    def after_user_source_update_requires_user_recount(
        self,
        user_source: UserSource,
        prepared_values: dict[str, Any],
    ) -> bool:
        """
        Detects if any of the properties in the prepared_values require
        a recount of the user source's user count.

        :param user_source: the user source which is being updated.
        :param prepared_values: the prepared values which will be
            used to update the user source.
        :return: whether a re-count is required.
        """

        recount_required = False
        for recount_property in self.properties_requiring_user_recount:
            if recount_property in prepared_values:
                current_value = getattr(user_source, recount_property)
                updated_value = prepared_values[recount_property]
                if current_value != updated_value:
                    recount_required = True
        return recount_required

    @abstractmethod
    def update_user_count(
        self,
        user_sources: QuerySet[UserSource] = None,
    ) -> Optional[UserSourceCount]:
        """
        Responsible for updating the cached number of users in this user source type.
        If `user_sources` are provided, we will only update the user count for those
        user sources. If no `user_sources` are provided, we will update the user count
        for all user sources of this type.

        :param user_sources: If a queryset of user sources is provided, we will only
            update the user count for those user sources, otherwise we'll find all
            user sources and update their user counts.
        :return: if a `user_source` is provided, a `UserSourceCount is returned,
            otherwise we will return `None`.
        """

    @abstractmethod
    def get_user_count(
        self,
        user_source: UserSource,
        force_recount: bool = False,
        update_if_uncached: bool = True,
    ) -> UserSourceCount:
        """
        Responsible for retrieving a user source's count.

        :param user_source: The user source we want a count from.
        :param force_recount: If True, we will re-count the users and ignore any
            existing cached count.
        :param update_if_uncached: If True, we will count the users and cache the
            result if the cache entry is missing. Set this to False if you need to
            know if the cache entry is missing.
        :return: A `UserSourceCount` instance or `None`.
        """


UserSourceTypeSubClass = TypeVar("UserSourceTypeSubClass", bound=UserSourceType)


class UserSourceTypeRegistry(
    ModelRegistryMixin[UserSourceSubClass, UserSourceTypeSubClass],
    Registry[UserSourceTypeSubClass],
    CustomFieldsRegistryMixin,
):
    """
    Contains all the user_source types.
    """

    name = "user_source"


user_source_type_registry: UserSourceTypeRegistry = UserSourceTypeRegistry()
