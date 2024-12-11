from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from django.db.models import QuerySet

from baserow.core.auth_provider.exceptions import (
    CannotCreateAuthProvider,
    CannotDeleteAuthProvider,
)
from baserow.core.exceptions import (
    AuthenticationProviderTypeAlreadyRegistered,
    AuthenticationProviderTypeDoesNotExist,
)
from baserow.core.registry import (
    APIUrlsInstanceMixin,
    APIUrlsRegistryMixin,
    CustomFieldsInstanceMixin,
    ImportExportMixin,
    Instance,
    MapAPIExceptionsInstanceMixin,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.utils import extract_allowed, set_allowed_attrs

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.auth_provider.types import AuthProviderModelSubClass


class BaseAuthProviderType(
    MapAPIExceptionsInstanceMixin,
    APIUrlsInstanceMixin,
    CustomFieldsInstanceMixin,
    ModelInstanceMixin,
    ImportExportMixin,
    Instance,
    ABC,
):
    """
    This class represents the auth provider type use to handle authentication in
    Baserow.
    """

    default_create_allowed_fields = ["domain", "enabled"]
    default_update_allowed_fields = ["domain", "enabled"]

    def can_create_new_providers(self, **kwargs) -> bool:
        """
        Returns True if it's possible to create an authentication provider of this type.
        """

        return True

    def can_delete_existing_providers(self) -> bool:
        """
        Returns True if it's possible to delete an authentication provider of this type.
        """

        return True

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: "AbstractUser",
        instance: Optional["AuthProviderModelSubClass"] = None,
    ) -> Dict[str, Any]:
        """
        The prepare_values hook gives the possibility to change the provided values
        just before they are going to be used to create or update the instance. For
        example if an ID is provided, it can be converted to a model instance. Or to
        convert a certain date string to a date object. It's also an opportunity to add
        specific validations.

        :param values: The provided values.
        :param user: The user on whose behalf the change is made.
        :param instance: The existing instance if any.
        :return: The updated values.
        """

        return values

    def before_create(self, user: "AbstractUser", **values):
        """
        This hook is called before the authentication provider is created.

        :param user: The user that is creating the authentication provider.
        :param values: The values that are used to create the authentication provider.
        """

        if not self.can_create_new_providers(**values):
            raise CannotCreateAuthProvider()

    def create(self, **kwargs) -> "AuthProviderModelSubClass":
        """
        Creates a new authentication provider instance of the provided type. The
        authentication provider is not saved to the database. The caller is
        responsible for saving the instance.

        :param handler: The handler that is used to manage the authentication providers.
        :return: The created authentication provider instance.
        """

        values = extract_allowed(
            kwargs, self.default_create_allowed_fields + self.allowed_fields
        )
        return self.model_class.objects.create(**values)

    def after_create(
        self, user: "AbstractUser", auth_provider: "AuthProviderModelSubClass"
    ):
        """
        This hook is called after the authentication provider is created.

        :param user: The user that has created the authentication provider.
        :param auth_provider: The created instance.
        """

    def before_update(
        self, user: "AbstractUser", auth_provider: "AuthProviderModelSubClass", **values
    ):
        """
        This hook is called before the authentication provider is updated.

        :param user: The user that is updating the authentication provider.
        :param auth_provider: The authentication provider that is being updated.
        :param values: The values that are used to update the authentication provider.
        """

    def update(
        self, auth_provider: "AuthProviderModelSubClass", **values
    ) -> "AuthProviderModelSubClass":
        """
        Updates the authentication provider instance of the provided type.

        :param auth_provider: The authentication provider that is being updated.
        :param values: The values that are used to update the authentication provider.
        :return: The updated authentication provider instance.
        """

        set_allowed_attrs(
            values,
            self.default_update_allowed_fields + self.allowed_fields,
            auth_provider,
        )
        auth_provider.save()

        return auth_provider

    def after_update(
        self, user: "AbstractUser", auth_provider: "AuthProviderModelSubClass"
    ):
        """
        This hook is called after the authentication provider is updated.

        :param user: The user that has updated the authentication provider.
        :param auth_provider: The updated instance.
        """

    def before_delete(
        self, user: "AbstractUser", auth_provider: "AuthProviderModelSubClass"
    ):
        """
        This hook is called before the authentication provider is deleted.

        :param user: The user that is deleting the authentication provider.
        :param auth_provider: The authentication provider that is being deleted.
        """

        if not auth_provider.get_type().can_delete_existing_providers():
            raise CannotDeleteAuthProvider()

    def delete(self, auth_provider: "AuthProviderModelSubClass"):
        """
        Deletes the authentication provider instance of the provided type.

        :param auth_provider: The authentication provider that is being deleted.
        """

        auth_provider.delete()

    def after_delete(
        self, user: "AbstractUser", auth_provider: "AuthProviderModelSubClass"
    ):
        """
        This hook is called after the authentication provider is deleted.

        :param user: The user that is deleting the authentication provider.
        :param auth_provider: The authentication provider that has been deleted.
        """

    def list_providers(
        self, base_queryset=None
    ) -> QuerySet["AuthProviderModelSubClass"]:
        """
        Returns a queryset containing all the authentication providers of this type.

        :param base_queryset: The base queryset that can be used to filter the
        """

        if base_queryset is None:
            base_queryset = self.model_class.objects

        return base_queryset.all()

    @abstractmethod
    def get_or_create_user_and_sign_in(
        self, auth_provider: "AuthProviderModelSubClass", user_info: Dict[str, Any]
    ) -> Tuple["AbstractUser", bool]:
        """
        Gets the user if present or creates it if not, based on the
        user info that was received from the identity provider.

        :param auth_provider: The authentication provider that was used to
            authenticate the user.
        :param user_info: A dict containing the user info that can be sent
            to the UserHandler().create_user() method.
        :raises DeactivatedUserException: If the user exists but has been
            disabled.
        :return: The user that was created or retrieved and a boolean flag set
            to True if the user has been created, False otherwise.
        """


class AuthenticationProviderTypeRegistry(
    MapAPIExceptionsInstanceMixin, APIUrlsRegistryMixin, ModelRegistryMixin, Registry
):
    """
    With the authentication provider registry it is possible to register new
    authentication providers. An authentication provider is an abstraction made
    specifically for Baserow. If added to the registry a user can use that
    authentication provider to login.
    """

    name = "authentication_provider"
    does_not_exist_exception_class = AuthenticationProviderTypeDoesNotExist
    already_registered_exception_class = AuthenticationProviderTypeAlreadyRegistered

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._default = None

    @abstractmethod
    def get_login_options(self, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Returns a dictionary containing the login options
        to populate the login component accordingly.
        """

    def get_all_available_login_options(self):
        login_options = {}
        for provider_type in self.get_all():
            provider_login_options = provider_type.get_login_options()
            if provider_login_options:
                login_options[provider_type.type] = provider_login_options
        return login_options
