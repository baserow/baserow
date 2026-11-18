from django.contrib.auth.models import AnonymousUser

from rest_framework.request import Request

from baserow.contrib.builder.domains.service import DomainService
from baserow.contrib.builder.errors import ERROR_BUILDER_DOES_NOT_EXIST
from baserow.contrib.builder.exceptions import BuilderDoesNotExist
from baserow.core.abuse_reports.registries import (
    AbuseReportResourceType,
    ReportedResource,
)


class BuilderAbuseReportResourceType(AbuseReportResourceType):
    """
    Lets the visitors of a published application report it for abuse. The
    application is identified by the domain name it's published to.
    """

    type = "builder"
    api_exceptions_map = {
        BuilderDoesNotExist: ERROR_BUILDER_DOES_NOT_EXIST,
    }

    def resolve(self, request: Request, identifier: str) -> ReportedResource:
        # Resolved like the published site itself, as an anonymous visitor.
        published_builder = DomainService().get_public_builder_by_domain_name(
            AnonymousUser(), identifier
        )
        domain = published_builder.published_from
        # The editor builder is reported instead of the published copy, because a
        # new copy is created every time the application is published. Its id stays
        # the same, and it's the application the admins can find in the workspace.
        builder = domain.builder
        return ReportedResource(
            resource_id=builder.id,
            name=builder.name,
            workspace=builder.workspace,
            public_url=domain.get_public_url(),
        )
