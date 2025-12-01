from typing import List, Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.domains.operations import (
    CreateDomainOperationType,
    DeleteDomainOperationType,
    ReadDomainOperationType,
    UpdateDomainOperationType,
)
from baserow.contrib.builder.domains.signals import (
    domain_created,
    domain_deleted,
    domain_updated,
    domains_reordered,
)
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.operations import (
    ListDomainsBuilderOperationType,
    OrderDomainsBuilderOperationType,
)
from baserow.core.handler import CoreHandler
from baserow.core.jobs.handler import JobHandler
from baserow.core.operations import ReadApplicationOperationType
from baserow.core.utils import Progress, extract_allowed

from .job_types import PublishDomainJobType
from .operations import PublishDomainOperationType
from .registries import DomainType


class DomainService:
    def __init__(self):
        self.handler = DomainHandler()

    def get_domain(
        self,
        user: AbstractUser,
        domain_id: int,
        base_queryset: Optional[QuerySet] = None,
        for_update: bool = False,
    ) -> Domain:
        """
        Gets a domain by ID

        :param user: The user requesting the domain
        :param domain_id: The ID of the domain
        :param base_queryset: Can be used to already apply changes to the qs used
        :param for_update: Ensure only one update can happen at a time.
        :return: The model instance of the Domain
        """

        base_queryset = base_queryset if base_queryset is not None else Domain.objects
        base_queryset = base_queryset.select_related("builder", "builder__workspace")

        domain = self.handler.get_domain(
            domain_id, base_queryset=base_queryset, for_update=for_update
        )

        CoreHandler().check_permissions(
            user,
            ReadDomainOperationType.type,
            workspace=domain.builder.workspace,
            context=domain,
        )

        return domain

    def get_domains(
        self,
        user: AbstractUser,
        builder: Builder,
        base_queryset: Optional[QuerySet] = None,
    ) -> QuerySet[Domain]:
        """
        Gets all the domains of a builder.

        :param user: The user trying to get the domains
        :param builder: The builder we are trying to get all domains for
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed
        :return: A queryset with all the domains
        """

        CoreHandler().check_permissions(
            user,
            ListDomainsBuilderOperationType.type,
            workspace=builder.workspace,
            context=builder,
        )

        queryset = base_queryset if base_queryset is not None else Domain.objects.all()
        queryset = CoreHandler().filter_queryset(
            user,
            ListDomainsBuilderOperationType.type,
            queryset=queryset,
            workspace=builder.workspace,
        )

        return DomainHandler().get_domains(builder, queryset)

    def get_public_builder_by_domain_name(self, user: AbstractUser, domain_name: str):
        """
        Returns the published builder related to the given domain name if the user has
        the permission to access it.

        :param user: The user doing the operation.
        :param domain_name: The builder the user wants the builder for.
        :return: the builder instance.
        """

        builder = self.handler.get_public_builder_by_domain_name(domain_name)

        application = builder.application_ptr

        CoreHandler().check_permissions(
            user,
            ReadApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        return builder

    def create_domain(
        self,
        user: AbstractUser,
        domain_type: DomainType,
        builder: Builder,
        **kwargs,
    ) -> Domain:
        """
        Creates a new domain

        :param user: The user trying to create the domain
        :param domain_type: The type of domain that's being created
        :param builder: The builder the domain belongs to
        :param kwargs: Additional attributes of the domain
        :return: The newly created domain instance
        """

        CoreHandler().check_permissions(
            user,
            CreateDomainOperationType.type,
            workspace=builder.workspace,
            context=builder,
        )

        domain = self.handler.create_domain(domain_type, builder, **kwargs)

        domain_created.send(self, domain=domain, user=user)

        return domain

    def delete_domain(self, user: AbstractUser, domain: Domain):
        """
        Deletes the domain provided

        :param user: The user trying to delete the domain
        :param domain: The domain that must be deleted
        """

        CoreHandler().check_permissions(
            user,
            DeleteDomainOperationType.type,
            workspace=domain.builder.workspace,
            context=domain,
        )

        self.handler.delete_domain(domain)

        domain_deleted.send(
            self, builder=domain.builder, domain_id=domain.id, user=user
        )

    def update_domain(self, user: AbstractUser, domain: Domain, **kwargs) -> Domain:
        """
        Updates fields of a domain

        :param user: The user trying to update the domain
        :param domain: The domain that should be updated
        :param kwargs: The fields that should be updated with their corresponding value
        :return: The updated domain
        """

        CoreHandler().check_permissions(
            user,
            UpdateDomainOperationType.type,
            workspace=domain.builder.workspace,
            context=domain,
        )

        allowed_updates = extract_allowed(kwargs, ["domain_name"])

        self.handler.update_domain(domain, **allowed_updates)

        domain_updated.send(self, domain=domain, user=user)

        return domain

    def order_domains(
        self, user: AbstractUser, builder: Builder, order: List[int]
    ) -> List[int]:
        """
        Assigns a new order to the domains in a builder application.

        :param user: The user trying to order the domains
        :param builder: The builder that the domains belong to
        :param order: The new order of the domains
        :return: The new order of the domains
        """

        CoreHandler().check_permissions(
            user,
            OrderDomainsBuilderOperationType.type,
            workspace=builder.workspace,
            context=builder,
        )

        all_domains = Domain.objects.filter(builder_id=builder.id)
        user_domains = CoreHandler().filter_queryset(
            user,
            OrderDomainsBuilderOperationType.type,
            all_domains,
            workspace=builder.workspace,
        )

        full_order = self.handler.order_domains(builder, order, user_domains)

        domains_reordered.send(self, builder=builder, order=full_order, user=user)

        return full_order

    def async_publish(self, user: AbstractUser, domain: Domain):
        """
        Starts an async job to publish the given builder for the given domain if the
        user has the right permission.

        :param user: The user publishing the builder.
        :param domain: The domain the user wants to publish the builder for.
        """

        CoreHandler().check_permissions(
            user,
            PublishDomainOperationType.type,
            workspace=domain.builder.workspace,
            context=domain,
        )

        job = JobHandler().create_and_start_job(
            user,
            PublishDomainJobType.type,
            domain=domain,
        )

        return job

    def publish(self, user: AbstractUser, domain: Domain, progress: Progress):
        """
        Publish the given builder for the given domain if the
        user has the right permission.

        :param user: The user publishing the builder.
        :param domain: The domain the user wants to publish the builder for.
        """

        CoreHandler().check_permissions(
            user,
            PublishDomainOperationType.type,
            workspace=domain.builder.workspace,
            context=domain,
        )

        domain = self.handler.publish(domain, progress)

        domain_updated.send(self, domain=domain, user=user)

        return domain
