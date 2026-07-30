from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from rest_framework.request import Request

from baserow.core.models import Workspace
from baserow.core.registry import Instance, MapAPIExceptionsInstanceMixin, Registry

from .exceptions import (
    AbuseReportResourceTypeAlreadyRegistered,
    AbuseReportResourceTypeDoesNotExist,
)


@dataclass
class ReportedResource:
    resource_id: int
    name: str
    workspace: Optional[Workspace]
    # Must be constructed by the backend based on the resolved resource, never taken
    # from client input, because it ends up in admin notifications.
    public_url: str


class AbuseReportResourceType(MapAPIExceptionsInstanceMixin, Instance, ABC):
    """
    Represents a kind of publicly shared resource that anonymous visitors can report
    for abuse, for example a publicly shared database view.
    """

    @abstractmethod
    def resolve(self, request: Request, identifier: str) -> ReportedResource:
        """
        Resolves the public identifier to a publicly shared resource. The request is
        provided so that implementations can read additional authorization headers, for
        example the public view authorization token of a password protected view.

        :param request: The request that submitted the abuse report.
        :param identifier: The public identifier of the resource, for example the slug
            of a shared view.
        :raises Exception: A type specific exception mapped via `api_exceptions_map` if
            the resource doesn't exist or isn't publicly shared.
        :return: The resolved resource.
        """


class AbuseReportResourceTypeRegistry(Registry[AbuseReportResourceType]):
    name = "abuse_report_resource_type"
    does_not_exist_exception_class = AbuseReportResourceTypeDoesNotExist
    already_registered_exception_class = AbuseReportResourceTypeAlreadyRegistered


abuse_report_resource_type_registry = AbuseReportResourceTypeRegistry()
