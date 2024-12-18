from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache

from baserow.contrib.builder.formula_property_extractor import (
    get_builder_used_property_names,
)
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.theme.registries import theme_config_block_registry
from baserow.core.handler import CoreHandler

User = get_user_model()
CACHE_KEY_PREFIX = "used_properties_for_page"


class BuilderHandler:
    def get_builder(self, builder_id: int) -> Builder:
        """
        Gets builder instance from database using its ID

        :param builder_id: ID of the builder instance you want to get
        :return: The builder model instance
        """

        theme_config_block_related_names = [
            config_block.related_name_in_builder_model
            for config_block in theme_config_block_registry.get_all()
        ]

        return (
            CoreHandler()
            .get_application(
                builder_id,
                base_queryset=Builder.objects.select_related(
                    "workspace", *theme_config_block_related_names
                ),
            )
            .specific
        )

    def get_builder_used_properties_cache_key(
        self, user: AbstractUser, builder: Builder
    ) -> Optional[str]:
        """
        Returns a cache key that can be used to key the results of making the
        expensive function call to get_builder_used_property_names().

        If the user is a Django user, return None. This is because the Page
        Designer should always have the latest data in the Preview (e.g. when
        they are not authenticated). Also, the Django user doesn't have the role
        attribute, unlike the User Source User.
        """

        if isinstance(user, User):
            return None
        elif user.is_anonymous:
            # When the user is anonymous, only use the prefix + page ID.
            role = ""
        else:
            role = f"_{user.role}"

        return f"{CACHE_KEY_PREFIX}_{builder.id}{role}"

    def get_builder_public_properties(
        self, user: AbstractUser, builder: Builder
    ) -> Dict[str, Dict[int, List[str]]]:
        """
        Return a Dict where keys are ["all", "external", "internal"] and values
        are dicts. The internal dicts' keys are Service IDs and values are a
        list of public properties, such as Data Source field names.

        The public properties are used to improve the security of the backend by
        ensuring that only the minimum necessary data is exposed to the frontend.

        It is used to restrict the queryset as well as to discern which public
        properties are external and safe (user facing) vs internal and sensitive
        (required only by the backend).
        """

        cache_key = self.get_builder_used_properties_cache_key(user, builder)
        properties = cache.get(cache_key) if cache_key else None
        if properties is None:
            properties = get_builder_used_property_names(user, builder)
            if cache_key:
                cache.set(
                    cache_key,
                    properties,
                    timeout=settings.BUILDER_PUBLICLY_USED_PROPERTIES_CACHE_TTL_SECONDS,
                )

        return properties
