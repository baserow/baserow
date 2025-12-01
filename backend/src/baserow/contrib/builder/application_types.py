import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.db.transaction import Atomic
from django.urls import include, path

from rest_framework import serializers

from baserow.contrib.builder.builder_beta_init_application import (
    BuilderApplicationTypeInitApplication,
)
from baserow.contrib.builder.constants import IMPORT_SERIALIZED_IMPORTING
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.operations import ListPagesBuilderOperationType
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.theme.handler import ThemeHandler
from baserow.contrib.builder.theme.registries import theme_config_block_registry
from baserow.contrib.builder.types import BuilderDict
from baserow.core.handler import CoreHandler
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.models import Application, Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.storage import ExportZipFile
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.utils import ChildProgressBuilder


# This lazy loads the serializer, which is needed because the `BuilderSerializer`
# needs to decorate the `get_theme` with the `extend_schema_field` using a
# generated serializer that needs the registry to be populated.
def lazy_get_instance_serializer_class():
    from baserow.contrib.builder.api.serializers import BuilderSerializer

    return BuilderSerializer


def lazy_get_instance_public_serializer_class():
    from baserow.contrib.builder.api.domains.serializers import PublicBuilderSerializer

    return PublicBuilderSerializer


class BuilderApplicationType(ApplicationType):
    type = "builder"
    model_class = Builder
    supports_actions = False
    supports_integrations = True
    supports_user_sources = True
    allowed_fields = ["favicon_file", "login_page_id"]
    serializer_field_names = [
        "favicon_file",
        "login_page_id",
        "pages",
        "theme",
    ]
    public_serializer_field_names = [
        "favicon_file",
        "login_page_id",
        "pages",
        "theme",
        "user_sources",
    ]
    request_serializer_field_names = [
        "favicon_file",
        "login_page_id",
    ]

    serializer_mixins = [lazy_get_instance_serializer_class]
    public_serializer_mixins = [lazy_get_instance_public_serializer_class]
    request_serializer_mixins = []

    # Builder applications are imported second.
    import_application_priority = 1

    @property
    def serializer_field_overrides(self):
        from baserow.api.user_files.serializers import UserFileField
        from baserow.contrib.builder.api.validators import (
            image_file_validation,
            login_page_id_validator,
        )

        return {
            "favicon_file": UserFileField(
                allow_null=True,
                required=False,
                default=None,
                help_text="The favicon image file",
                validators=[image_file_validation],
            ),
            "login_page_id": serializers.IntegerField(
                allow_null=True,
                required=False,
                default=None,
                help_text=Builder._meta.get_field("login_page").help_text,
                validators=[login_page_id_validator],
            ),
        }

    def get_api_urls(self):
        from .api import urls as api_urls

        return [
            path("builder/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application: Application) -> Atomic:
        return transaction.atomic()

    def init_application(self, user: AbstractUser, application: Application) -> None:
        """
        Responsible for creating dummy data in the newly created builder application.

        By default, we'll always create a page with an intro section, and a paragraph
        explaining what the designer can do in the editor.

        If the dummy "Customers" table in `application.workspace` hasn't changed its
        schema (i.e. version = initial_version) then we'll also creating some extra
        fun elements with a data source and workflow action.

        :param user: The user who is creating a new builder application.
        :param application: The newly created builder application.
        :return: None
        """

        builder_init = BuilderApplicationTypeInitApplication(user, application)

        # Get our target table, "Customers". It won't be returned if:
        # 1. It's been trashed, or renamed.
        # 2. The table has permissions the user doesn't have.
        # 3. It exists, but the fields we want (first/last name) have been changed.
        table = builder_init.get_target_table()

        # Create the Homepage Page.
        homepage = builder_init.create_page(builder_init.homepage_name, "/")

        # Create the Examples Page.
        examples = builder_init.create_page(builder_init.examples_name, "/examples")

        # Create the Local Baserow integration.
        integration = builder_init.create_integration()

        # Create our intro section in Homepage.
        builder_init.create_intro_element(homepage, link_to_page=examples)

        # If we found a table...
        if table:
            # Create our sample table element, if we have a Customers table.
            builder_init.create_table_element(examples, table, integration)

        # Create our sample form element
        builder_init.create_form_element(examples, integration, table=table)

        # Create our sample container element.
        builder_init.create_container_element(examples)

    def export_serialized(
        self,
        builder: Builder,
        import_export_config: ImportExportConfig,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> BuilderDict:
        """
        Exports the builder application type to a serialized format that can later
        be imported via the `import_serialized`.
        """

        self.cache = {}

        serialized_integrations = [
            IntegrationHandler().export_integration(
                i,
                import_export_config,
                files_zip=files_zip,
                storage=storage,
                cache=self.cache,
            )
            for i in IntegrationHandler().get_integrations(builder)
        ]

        serialized_user_sources = [
            UserSourceHandler().export_user_source(
                us,
                files_zip=files_zip,
                storage=storage,
                cache=self.cache,
            )
            for us in UserSourceHandler().get_user_sources(builder)
        ]

        pages = PageHandler().get_pages(
            builder,
            base_queryset=Page.objects.prefetch_related(
                "element_set", "datasource_set"
            ),
        )

        serialized_pages = [
            PageHandler().export_page(
                p,
                files_zip=files_zip,
                storage=storage,
                cache=self.cache,
            )
            for p in pages
        ]

        serialized_theme = ThemeHandler().export_theme(
            builder,
            files_zip=files_zip,
            storage=storage,
            cache=self.cache,
        )

        serialized_favicon_file = UserFileHandler().export_user_file(
            builder.favicon_file,
            files_zip,
            storage,
        )

        serialized_builder = super().export_serialized(
            builder,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
            progress_builder=progress_builder,
        )

        serialized_login_page = None
        if builder.login_page:
            serialized_login_page = PageHandler().export_page(
                builder.login_page,
                files_zip=files_zip,
                storage=storage,
                cache=self.cache,
            )

        return BuilderDict(
            pages=serialized_pages,
            integrations=serialized_integrations,
            theme=serialized_theme,
            user_sources=serialized_user_sources,
            favicon_file=serialized_favicon_file,
            login_page=serialized_login_page,
            **serialized_builder,
        )

    def import_integrations_serialized(
        self,
        builder: Builder,
        serialized_integrations: List[Dict[str, Any]],
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Integration]:
        """
        Import integrations to builder. This method has to be compatible with the output
        of `export_integrations_serialized`.

        :param builder: The builder the pages where exported from.
        :param serialized_integrations: The integrations that are supposed to be
            imported.
        :param progress_builder: A progress builder that allows for publishing progress.
        :param files_zip: An optional zip file for the related files.
        :param storage: The storage instance.
        :return: The created integration instances.
        """

        progress = ChildProgressBuilder.build(
            progress_builder, child_total=len(serialized_integrations)
        )

        imported_integrations: List[Integration] = []

        for serialized_integration in serialized_integrations:
            integration = IntegrationHandler().import_integration(
                builder,
                serialized_integration,
                id_mapping,
                cache=self.cache,
                files_zip=files_zip,
                storage=storage,
            )
            imported_integrations.append(integration)

            progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        return imported_integrations

    def import_user_sources_serialized(
        self,
        builder: Builder,
        serialized_user_sources: List[Dict[str, Any]],
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Page]:
        """
        Import user sources to builder.

        :param builder: The builder the pages where exported from.
        :param serialized_user_sources: The user sources that are supposed to be
            imported.
        :param progress_builder: A progress builder that allows for publishing progress.
        :param files_zip: An optional zip file for the related files.
        :param storage: The storage instance.
        :return: The created user sources instances.
        """

        progress = ChildProgressBuilder.build(
            progress_builder, child_total=len(serialized_user_sources)
        )

        imported_user_sources: List[Integration] = []

        for serialized_user_source in serialized_user_sources:
            integration = UserSourceHandler().import_user_source(
                builder,
                serialized_user_source,
                id_mapping,
                cache=self.cache,
                files_zip=files_zip,
                storage=storage,
            )
            imported_user_sources.append(integration)

            progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        return imported_user_sources

    def import_serialized(
        self,
        workspace: Workspace,
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Application:
        """
        Imports a builder application exported by the `export_serialized` method.
        """

        self.cache = {}

        serialized_pages = serialized_values.pop("pages")
        serialized_integrations = serialized_values.pop("integrations")
        serialized_user_sources = serialized_values.pop("user_sources")
        serialized_theme = serialized_values.pop("theme")

        (
            builder_progress,
            integration_progress,
            user_source_progress,
            page_progress,
        ) = (5, 10, 15, 80)
        progress = ChildProgressBuilder.build(
            progress_builder, child_total=builder_progress + page_progress
        )

        if "import_workspace_id" not in id_mapping and workspace is not None:
            id_mapping["import_workspace_id"] = workspace.id

        if "workspace_id" not in id_mapping and workspace is not None:
            id_mapping["workspace_id"] = workspace.id

        application = super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip,
            storage,
            progress.create_child_builder(represents_progress=builder_progress),
        )

        builder = application.specific

        if not serialized_integrations:
            progress.increment(
                state=IMPORT_SERIALIZED_IMPORTING, by=integration_progress
            )
        else:
            self.import_integrations_serialized(
                builder,
                serialized_integrations,
                id_mapping,
                files_zip,
                storage,
                progress.create_child_builder(represents_progress=integration_progress),
            )

        if not serialized_user_sources:
            progress.increment(
                state=IMPORT_SERIALIZED_IMPORTING, by=user_source_progress
            )
        else:
            self.import_user_sources_serialized(
                builder,
                serialized_user_sources,
                id_mapping,
                files_zip,
                storage,
                progress.create_child_builder(represents_progress=user_source_progress),
            )

        if not serialized_pages:
            progress.increment(state=IMPORT_SERIALIZED_IMPORTING, by=page_progress)
        else:
            PageHandler().import_pages(
                builder,
                serialized_pages,
                id_mapping,
                files_zip,
                storage,
                progress.create_child_builder(represents_progress=page_progress),
            )

        if serialized_favicon_file := serialized_values.pop("favicon_file", None):
            if favicon_file := UserFileHandler().import_user_file(
                serialized_favicon_file,
                files_zip,
                storage,
            ):
                builder.favicon_file = favicon_file
                builder.save()

        if serialized_login_page := serialized_values.pop("login_page", None):
            if login_page_id := id_mapping["builder_pages"].get(
                serialized_login_page["id"], None
            ):
                builder.login_page_id = login_page_id
                builder.save()

        ThemeHandler().import_theme(
            builder, serialized_theme, id_mapping, files_zip, storage
        )

        return builder

    def get_application_urls(self, application: Builder) -> list[str]:
        """
        Returns the default frontend urls of a builder application.
        """

        from baserow.contrib.builder.domains.handler import DomainHandler

        domain = DomainHandler().get_domain_for_builder(application)

        if domain is not None:
            # Let's also return the preview url so that it's easier to test
            preview_url = urljoin(
                settings.PUBLIC_WEB_FRONTEND_URL,
                f"/builder/{domain.builder_id}/preview/",
            )
            return [domain.get_public_url(), preview_url]

        preview_url = urljoin(
            settings.PUBLIC_WEB_FRONTEND_URL,
            f"/builder/{application.id}/preview/",
        )
        # It's an unpublished version let's return to the home preview page
        return [preview_url]

    @classmethod
    def _extract_builder_id_from_path(cls, url_path):
        # Define the regex pattern with a capturing group for the integer
        pattern = r"^/builder/(\d+)/preview/.*$"

        # Use re.match to find the match
        match = re.match(pattern, url_path)

        if match:
            # Extract the integer from the first capturing group
            return int(match.group(1))
        return None

    @classmethod
    def get_application_id_for_url(cls, url: str) -> int | None:
        """
        If the given URL is relative to the PUBLIC_WEB_FRONTEND_URL, we try to match
        the preview path and to extract the builder id from it.

        Otherwise, we try to match a published domain and return the related
        application id.
        """

        from baserow.contrib.builder.domains.models import Domain

        parsed_url = urlparse(url)
        parsed_frontend_url = urlparse(settings.PUBLIC_WEB_FRONTEND_URL)

        if (parsed_url.scheme, parsed_url.hostname) == (
            parsed_frontend_url.scheme,
            parsed_frontend_url.hostname,
        ):
            # It's an unpublished app and we try to access the preview
            url_path = parsed_url.path
            return cls._extract_builder_id_from_path(url_path)

        try:
            # Let's search for a published app
            domain = Domain.objects.exclude(published_to=None).get(
                domain_name=parsed_url.hostname
            )
            return domain.published_to_id
        except Domain.DoesNotExist:
            return None

    def _get_base_enhanced_queryset(self, queryset):
        queryset = queryset.select_related("favicon_file").prefetch_related(
            "user_sources", "integrations"
        )
        return theme_config_block_registry.enhance_list_builder_queryset(queryset)

    def enhance_queryset(self, queryset):
        enhanced_queryset = self._get_base_enhanced_queryset(queryset)
        return enhanced_queryset.prefetch_related("page_set")

    def enhance_and_filter_queryset(
        self,
        queryset: QuerySet[Builder],
        user: AbstractUser,
        workspace: Workspace,
    ) -> QuerySet[Builder]:
        enhanced_queryset = self._get_base_enhanced_queryset(queryset)
        return enhanced_queryset.prefetch_related(
            Prefetch(
                "page_set",
                queryset=CoreHandler().filter_queryset(
                    user,
                    ListPagesBuilderOperationType.type,
                    Page.objects.select_related("builder__workspace").all(),
                    workspace=workspace,
                ),
                to_attr="pages",
            ),
        )

    def fetch_pages_to_serialize(
        self, builder: Builder, user: AbstractUser | None
    ) -> List[Page]:
        """
        Serializes the pages of the builder application, making sure that the user has
        the correct permissions to view them if provided, and fetching the related
        elements and data sources correctly so additional queries are not needed.

        :param builder: The builder application instance.
        :param user: The user trying to access the pages.
        :return: A list of serialized pages that belong to this instance with all
            related elements and data sources fetched correctly.
        """

        base_queryset = Builder.objects.filter(id=builder.id)
        if user:
            instance = self.enhance_and_filter_queryset(
                base_queryset, user, builder.workspace
            ).first()
            return instance and instance.pages or []
        else:
            instance = self.enhance_queryset(base_queryset).first()
            return instance and list(instance.page_set.all()) or []
