from typing import TYPE_CHECKING, Dict, Optional
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage

from baserow.core.app_auth_providers.auth_provider_types import AppAuthProviderType
from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.auth_provider.handler import BaseAuthProviderHandler

if TYPE_CHECKING:
    from baserow.core.user_sources.models import UserSource


class AppAuthProviderHandler(BaseAuthProviderHandler):
    base_class = AppAuthProvider

    @classmethod
    def list_app_auth_providers_for_user_source(
        cls, user_source: "UserSource", **kwargs
    ):
        """
        Returns the list of app auth providers for the given user source.

        :param user_source: The user source we want the provider for.
        :return: an iterable of auth providers related to the given user source.
        """

        base_queryset = cls.base_class.objects.filter(
            user_source=user_source
        ).select_related(
            "user_source__application__workspace",
        )

        return cls.list_all_auth_providers(base_queryset=base_queryset, **kwargs)

    @classmethod
    def create_app_auth_provider(
        cls,
        user: AbstractUser,
        auth_provider_type: AppAuthProviderType,
        user_source: "UserSource",
        **kwargs,
    ):
        """
        Creates an app auth provider for the given user source.

        :param user: The user that is creating the authentication provider.
        :param auth_provider_type: The type of the authentication provider.
        :param user_source: The user source for which the provider should belong.
        :param values: The values that should be set on the authentication provider.
        :return: The created authentication provider.
        """

        return cls.create_auth_provider(
            user, auth_provider_type, user_source=user_source, **kwargs
        )

    @classmethod
    def export_app_auth_provider(
        cls,
        app_auth_provider: AppAuthProviderType,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Export an app auth provider.
        """

        return app_auth_provider.get_type().export_serialized(
            app_auth_provider, files_zip=files_zip, storage=storage, cache=cache
        )

    @classmethod
    def import_app_auth_provider(
        cls,
        user_source: "UserSource",
        serialized_app_auth_provider: Dict,
        id_mapping: Dict,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache=None,
    ):
        """
        Imports a serialized app_auth_provider.
        """

        if "app_auth_providers" not in id_mapping:
            id_mapping["app_auth_providers"] = {}

        app_auth_provider_type = app_auth_provider_type_registry.get(
            serialized_app_auth_provider["type"]
        )
        app_auth_provider = app_auth_provider_type.import_serialized(
            user_source,
            serialized_app_auth_provider,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

        id_mapping["app_auth_providers"][
            serialized_app_auth_provider["id"]
        ] = app_auth_provider.id

        return app_auth_provider
