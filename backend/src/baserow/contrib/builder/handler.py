from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.formula_property_extractor import (
    get_builder_used_property_names,
)
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.theme.registries import theme_config_block_registry
from baserow.core.handler import CoreHandler
from baserow.core.utils import invalidate_versioned_cache, safe_get_or_set_cache

User = get_user_model()
CACHE_KEY_PREFIX = "used_properties_for_page"
BUILDER_PREVIEW_USED_PROPERTIES_CACHE_TTL_SECONDS = 60


SENTINEL = "__no_results__"


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

    @classmethod
    def _get_builder_version_cache(cls, builder: Builder):
        return f"{CACHE_KEY_PREFIX}_version_{builder.id}"

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

        if user.is_anonymous or not user.role:
            # When the user is anonymous, only use the prefix + page ID.
            role = ""
        else:
            role = f"_{user.role}"

        return f"{CACHE_KEY_PREFIX}_{builder.id}{role}"

    @classmethod
    def invalidate_builder_public_properties_cache(cls, builder):
        invalidate_versioned_cache(cls._get_builder_version_cache(builder))

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

        def compute_properties():
            properties = get_builder_used_property_names(user, builder)
            return SENTINEL if properties is None else properties

        result = safe_get_or_set_cache(
            self.get_builder_used_properties_cache_key(user, builder),
            self._get_builder_version_cache(builder),
            default=compute_properties,
            timeout=settings.BUILDER_PUBLICLY_USED_PROPERTIES_CACHE_TTL_SECONDS
            if builder.workspace_id
            else BUILDER_PREVIEW_USED_PROPERTIES_CACHE_TTL_SECONDS,
        )

        return result if result != SENTINEL else None
