from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, List, Tuple, Type, Union

from django.contrib.auth.models import AbstractUser

from loguru import logger

from baserow.core.app_auth_providers.exceptions import IncompatibleUserSourceType
from baserow.core.app_auth_providers.types import AppAuthProviderTypeDict
from baserow.core.auth_provider.exceptions import UnverifiedEmailFromProvider
from baserow.core.auth_provider.registries import BaseAuthProviderType
from baserow.core.auth_provider.types import AuthProviderModelSubClass, UserInfo
from baserow.core.registry import EasyImportExportMixin, PublicCustomFieldsInstanceMixin

if TYPE_CHECKING:
    from baserow.core.user_sources.types import UserSourceSubClass


class AppAuthProviderType(
    EasyImportExportMixin, PublicCustomFieldsInstanceMixin, BaseAuthProviderType
):
    """
    Authentication provider for application user sources.
    """

    default_create_allowed_fields = ["domain", "enabled", "user_source"]
    default_update_allowed_fields = ["domain", "enabled"]

    SerializedDict: Type[AppAuthProviderTypeDict]
    parent_property_name = "user_source"
    id_mapping_name = "app_auth_providers"

    compatible_user_source_types: List[
        Union[str, Callable[["UserSourceSubClass"], bool]]
    ] = []
    """
    Defines which user source types are compatible with the auth provider.
    Only the supported ones can be used in combination with the user source.
    The values in this list can either be the literal field_type.type string,
    or a callable which takes the user source being checked and returns True if
    compatible or False if not.
    """

    def export_prepared_values(self, instance: AuthProviderModelSubClass) -> dict:
        """
        Returns a serializable dict of this auth provider's values in the
        `prepare_values` shape, so they can be re-created - e.g. to capture a user
        source's auth providers for undo/redo, since the generic
        `extract_undo_redo_values` cannot serialise related models. This is the
        counterpart of `prepare_values` (mirroring `ServiceType.export_prepared_values`);
        types with foreign-key fields override this to emit the `_id` form.
        """

        return {key: getattr(instance, key) for key in self.allowed_fields}

    def check_user_source_compatibility(self, user_source):
        """
        Given a particular instance of a user source returns if it's compatible
        with this particular auth_provider type.

        :param user_source: The user_source to check.
        :param raise_exception: Whether to raise an exception instead of returning a
          value.
        :raises IncompatibleUserSourceType: If the user source and auth provider
          are incompatible.
        """

        from baserow.core.user_sources.registries import user_source_type_registry

        user_source_type = user_source_type_registry.get_by_model(
            user_source.specific_class
        )

        if not any(
            callable(t) and t(user_source) or t == user_source_type.type
            for t in self.compatible_user_source_types
        ):
            raise IncompatibleUserSourceType(user_source_type.type, self.type)

    def after_user_source_update(
        self,
        user: "AbstractUser",
        instance: AuthProviderModelSubClass,
        user_source: "UserSourceSubClass",
    ):
        """
        Hooks to act after a user source update.
        :param instance: The auth provider instance related to the user source.
        :param user_source: The user source being updated.
        """

    def get_or_create_user_and_sign_in(
        self, auth_provider: AuthProviderModelSubClass, user_info: UserInfo
    ) -> Tuple[AbstractUser, bool]:
        """
        Get or create a user for the given UserInfo. Calls the related userSource
        get_or_create_user.

        :raises UnverifiedEmailFromProvider: If the provider reports the
            email as unverified.
        """

        if not user_info.email_verified:
            logger.warning(
                "Rejecting Builder SSO login — provider reported email as "
                "unverified (provider_id={})",
                auth_provider.id,
            )
            raise UnverifiedEmailFromProvider()

        user_source = auth_provider.user_source.specific
        return user_source.get_type().get_or_create_user(
            user_source, email=user_info.email, name=user_info.name
        )

    def get_pytest_params(self, pytest_data_fixture) -> dict[str, Any]:
        """
        Returns a sample of params for this type. This can be used to tests the provider
        for instance.

        :param pytest_data_fixture: A Pytest data fixture which can be used to
            create related objects when the import / export functionality is tested.
        """

        return {}

    @contextmanager
    def apply_patch_pytest(self):
        """
        Hook to mock something during the tests.
        """

        yield
