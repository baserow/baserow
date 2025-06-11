from typing import Dict, List, Optional

from django.conf import settings
from django.db.models.query import QuerySet

from baserow.contrib.builder.formula_property_extractor import (
    get_builder_used_property_names,
)
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.theme.registries import theme_config_block_registry
from baserow.core.cache import global_cache
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.user_source_user import UserSourceUser

USED_PROPERTIES_CACHE_KEY_PREFIX = "used_properties_for_page"

# The duration of the cached public element, data source and workflow action API views.
BUILDER_PUBLIC_RECORDS_CACHE_TTL_SECONDS = 60 * 60

# The duration of the cached public properties for the builder API views.
BUILDER_PREVIEW_USED_PROPERTIES_CACHE_TTL_SECONDS = 60 * 10

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
    def _get_builder_public_properties_version_cache(cls, builder: Builder) -> str:
        return f"{USED_PROPERTIES_CACHE_KEY_PREFIX}_version_{builder.id}"

    def get_builder_used_properties_cache_key(
        self, user: UserSourceUser, builder: Builder
    ) -> str:
        """
        Returns a cache key that can be used to key the results of making the
        expensive function call to get_builder_used_property_names().
        """

        if user.is_anonymous or not user.role:
            # When the user is anonymous, only use the prefix + page ID.
            role = ""
        else:
            role = f"_{user.role}"

        return f"{USED_PROPERTIES_CACHE_KEY_PREFIX}_{builder.id}{role}"

    @classmethod
    def invalidate_builder_public_properties_cache(cls, builder: Builder):
        global_cache.invalidate(
            invalidate_key=cls._get_builder_public_properties_version_cache(builder)
        )

    def get_builder_public_properties(
        self, user: UserSourceUser, builder: Builder
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

        result = global_cache.get(
            self.get_builder_used_properties_cache_key(user, builder),
            default=compute_properties,
            # We want to invalidate the cache for all roles at once so we create a
            # unique invalidate key for all.
            invalidate_key=self._get_builder_public_properties_version_cache(builder),
            timeout=settings.BUILDER_PUBLICLY_USED_PROPERTIES_CACHE_TTL_SECONDS
            if not builder.workspace_id
            else BUILDER_PREVIEW_USED_PROPERTIES_CACHE_TTL_SECONDS,
        )

        return result if result != SENTINEL else None

    def get_published_applications(
        self, workspace: Optional[Workspace] = None
    ) -> QuerySet[Builder]:
        """
        Returns all published applications in a workspace or all published applications
        in the instance if no workspace is provided.

        A published application is a builder application which points to one more
        published domains. The application is the one that the page designer is
        creating their application in.

        :param workspace: Only return published applications in this workspace.
        :return: A queryset of published applications.
        """

        applications = Builder.objects.exclude(domains__published_to=None)
        return applications.filter(workspace=workspace) if workspace else applications

    def aggregate_user_source_counts(
        self,
        workspace: Optional[Workspace] = None,
    ) -> int:
        """
        The builder implementation of the `UserSourceHandler.aggregate_user_counts`
        method, we need it to only count user sources in published applications.

        :param workspace: If provided, only count user sources in published
            applications within this workspace.
        :return: The total number of user sources in published applications.
        """

        queryset = UserSourceHandler().get_user_sources(
            base_queryset=UserSource.objects.filter(
                application__in=self.get_published_applications(workspace)
            )
        )
        return UserSourceHandler().aggregate_user_counts(workspace, queryset)
