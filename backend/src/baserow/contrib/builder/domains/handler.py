from datetime import datetime, timezone
from typing import Iterable, List, Optional, cast

from django.db.models import QuerySet
from django.db.utils import IntegrityError

from baserow.contrib.builder.domains.exceptions import (
    DomainDoesNotExist,
    DomainNameNotUniqueError,
    DomainNotInBuilder,
)
from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.domains.registries import DomainType
from baserow.contrib.builder.exceptions import BuilderDoesNotExist
from baserow.contrib.builder.models import Builder
from baserow.core.cache import global_cache
from baserow.core.db import specific_iterator
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.models import Workspace
from baserow.core.psycopg import is_unique_violation_error
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.storage import get_default_storage
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import Progress, extract_allowed


class DomainHandler:
    allowed_fields_create = ["domain_name"]
    allowed_fields_update = ["domain_name", "last_published"]

    def get_domain(
        self, domain_id: int, base_queryset: QuerySet | None = None, for_update=False
    ) -> Domain:
        """
        Gets a domain by ID

        :param domain_id: The ID of the domain
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed
        :param for_update: Ensure only one update can happen at a time.
        :raises DomainDoesNotExist: If the domain doesn't exist
        :return: The model instance of the domain
        """

        if base_queryset is None:
            base_queryset = Domain.objects

        if for_update:
            base_queryset = base_queryset.select_for_update(of=("self",))

        try:
            return base_queryset.get(id=domain_id)
        except Domain.DoesNotExist:
            raise DomainDoesNotExist()

    def get_domains(
        self, builder: Builder, base_queryset: QuerySet = None
    ) -> Iterable[Domain]:
        """
        Gets all the domains of a builder.

        :param builder: The builder we are trying to get all domains for
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed
        :return: An iterable of all the specific domains
        """

        if base_queryset is None:
            base_queryset = Domain.objects.all()

        return specific_iterator(base_queryset.filter(builder=builder))

    def get_public_builder_by_domain_name(self, domain_name: str) -> Builder:
        """
        Returns a builder given a domain name it's been published for.

        :param domain_name: The domain name we want the builder for.
        :raise BuilderDoesNotExist: When no builder is published with this domain name.
        :return: A public builder instance.
        """

        try:
            domain = (
                Domain.objects.exclude(published_to=None)
                .select_related("published_to", "builder__workspace")
                .only("published_to", "builder")
                .get(domain_name=domain_name)
            )
        except Domain.DoesNotExist:
            raise BuilderDoesNotExist()

        if TrashHandler.item_has_a_trashed_parent(domain, check_item_also=True):
            raise BuilderDoesNotExist()

        return domain.published_to

    def get_domain_for_builder(self, builder: Builder) -> Domain | None:
        """
        Returns the domain the builder is published for or None if it's not a published
        builder.
        """

        try:
            return Domain.objects.get(published_to=builder)
        except Domain.DoesNotExist:
            return None

    def create_domain(
        self, domain_type: DomainType, builder: Builder, **kwargs
    ) -> Domain:
        """
        Creates a new domain

        :param domain_type: The type of domain that's being created
        :param builder: The builder the domain belongs to
        :param kwargs: Additional attributes of the domain
        :return: The newly created domain instance
        """

        last_order = Domain.get_last_order(builder)

        model_class = cast(Domain, domain_type.model_class)

        allowed_values = extract_allowed(
            kwargs, self.allowed_fields_create + domain_type.allowed_fields
        )

        prepared_values = domain_type.prepare_values(allowed_values)

        # Save only lower case domain
        if "domain_name" in prepared_values:
            prepared_values["domain_name"] = prepared_values["domain_name"].lower()

        domain = model_class(builder=builder, order=last_order, **prepared_values)

        try:
            domain.save()
        except IntegrityError as error:
            if is_unique_violation_error(error):
                raise DomainNameNotUniqueError(prepared_values["domain_name"])
            raise error

        return domain

    def delete_domain(self, domain: Domain):
        """
        Deletes the domain provided

        :param domain: The domain that must be deleted
        """

        domain.delete()

    def update_domain(self, domain: Domain, **kwargs) -> Domain:
        """
        Updates fields of a domain

        :param domain: The domain that should be updated
        :param kwargs: The fields that should be updated with their corresponding value
        :return: The updated domain
        """

        domain_type = domain.get_type()

        allowed_values = extract_allowed(
            kwargs, self.allowed_fields_update + domain_type.allowed_fields
        )

        prepared_values = domain_type.prepare_values(allowed_values)

        # Save only lower case domain
        if "domain_name" in prepared_values:
            prepared_values["domain_name"] = prepared_values["domain_name"].lower()

        for key, value in prepared_values.items():
            setattr(domain, key, value)

        try:
            domain.save()
        except IntegrityError as error:
            if is_unique_violation_error(error):
                raise DomainNameNotUniqueError(prepared_values["domain_name"])
            raise error

        return domain

    def order_domains(
        self, builder: Builder, order: List[int], base_qs=None
    ) -> List[int]:
        """
        Assigns a new order to the domains in a builder application.
        You can provide a base_qs for pre-filter the domains affected by this change.

        :param builder: The builder that the domains belong to
        :param order: The new order of the domains
        :param base_qs: A QS that can have filters already applied
        :raises DomainNotInBuilder: If the domain is not part of the provided builder
        :return: The new order of the domains
        """

        if base_qs is None:
            base_qs = Domain.objects.filter(builder=builder)

        try:
            full_order = Domain.order_objects(base_qs, order)
        except IdDoesNotExist as error:
            raise DomainNotInBuilder(error.not_existing_id)

        return full_order

    def get_published_domain_applications(
        self, workspace: Optional[Workspace] = None
    ) -> QuerySet[Builder]:
        """
        Returns all published domain applications in a workspace or all published
        domain applications in the instance if no workspace is provided.

        A domain application is the builder application which is associated with
        the domain it was published to. It is not the application which the page
        designer created their application with.

        :param workspace: Only return published domain applications in this workspace.
        :return: A queryset of published domain applications.
        """

        applications = Builder.objects.exclude(published_from=None)
        return (
            applications.filter(published_from__builder__workspace=workspace)
            if workspace
            else applications
        )

    def publish(self, domain: Domain, progress: Progress | None = None):
        """
        Publishes a builder for the given domain object. If the builder was
        already published, the previous version is deleted and a new one is created.
        When a builder is published, a clone of the current version is created to avoid
        further modifications to the original builder affect the published version.

        :param domain: The object carrying the information for the publishing.
        :param progress: A progress object to track the publishing operation progress.
        """

        # Make sure we are the only process to update the domain to prevent race
        # conditions
        domain = DomainHandler().get_domain(domain.id, for_update=True)

        builder = domain.builder
        workspace = builder.workspace

        # Delete previously existing builder publication
        if domain.published_to:
            domain.published_to.delete()

        builder_application_type = application_type_registry.get("builder")

        import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            exclude_sensitive_data=False,
            is_publishing=True,
        )

        default_storage = get_default_storage()

        exported_builder = builder_application_type.export_serialized(
            builder, import_export_config, None, default_storage
        )

        if progress:
            progress.increment(by=50)

        id_mapping = {"import_workspace_id": workspace.id}
        duplicate_builder = builder_application_type.import_serialized(
            None,
            exported_builder,
            import_export_config,
            id_mapping,
            None,
            default_storage,
            progress_builder=progress.create_child_builder(represents_progress=50)
            if progress
            else None,
        )
        domain.published_to = duplicate_builder
        domain.last_published = datetime.now(tz=timezone.utc)
        domain.save()

        # We need a stable/predictable uuid for published user sources. That's why we
        # override the generated uuid with the uuid from the original user_source
        # prefixed with the domain id.
        # For a certain domain the domain id is always the same as long as you don't
        # recreate it.
        for imported_user_source, original_user_source in zip(
            duplicate_builder.user_sources.all(), builder.user_sources.all()
        ):
            imported_user_source.uid = f"domain_{domain.id}__{original_user_source.uid}"
            imported_user_source.save()

        # Invalidate the public builder-by-domain cache after a new publication.
        DomainHandler.invalidate_public_builder_by_domain_cache(domain.domain_name)

        return domain

    @classmethod
    def get_public_builder_by_domain_cache_key(cls, domain_name: str) -> str:
        return f"ab_public_builder_by_domain_{domain_name}"

    @classmethod
    def invalidate_public_builder_by_domain_cache(cls, domain_name: str):
        global_cache.invalidate(cls.get_public_builder_by_domain_cache_key(domain_name))
