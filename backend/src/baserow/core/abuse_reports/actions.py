import dataclasses
from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import RootActionScopeType, WorkspaceActionScopeType

from .handler import AbuseReportHandler
from .models import AbuseReport
from .notification_types import AbuseReportCreatedNotificationType
from .registries import AbuseReportResourceType, ReportedResource


class SubmitAbuseReportActionType(ActionType):
    type = "submit_abuse_report"
    description = ActionTypeDescription(
        _("Submit abuse report"),
        _(
            'Publicly shared %(resource_type)s "%(resource_name)s" '
            "(%(resource_id)s) was reported for abuse by %(reporter_email)s"
        ),
    )
    analytics_params = [
        "resource_type",
        "resource_id",
        "workspace_id",
        "abuse_report_id",
    ]

    @dataclasses.dataclass
    class Params:
        abuse_report_id: int
        resource_type: str
        resource_id: int
        resource_name: str
        workspace_id: Optional[int]
        workspace_name: str
        public_url: str
        reporter_name: str
        reporter_email: str
        description: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        resource_type: AbuseReportResourceType,
        resource: ReportedResource,
        reporter_name: str,
        reporter_email: str,
        description: str,
        ip_address: Optional[str] = None,
    ) -> AbuseReport:
        """
        Submits an abuse report for a publicly shared resource, and notifies the
        instance admins unless they were recently notified about the same resource.
        The user is expected to be anonymous because reports are submitted from
        publicly shared pages.

        :param user: The user submitting the report, typically an `AnonymousUser`.
        :param resource_type: The registered resource type that resolved the reported
            resource.
        :param resource: The resolved publicly shared resource.
        :param reporter_name: The self-reported name of the reporter.
        :param reporter_email: The self-reported email address of the reporter.
        :param description: Why the reporter believes the resource is abusive.
        :param ip_address: The IP address the report was submitted from.
        :raises AbuseReportingDisabledException: When the instance admin has disabled
            abuse reporting.
        :return: The created abuse report.
        """

        report, should_notify = AbuseReportHandler.create_abuse_report(
            resource_type,
            resource,
            reporter_name,
            reporter_email,
            description,
            ip_address=ip_address,
        )

        params = cls.Params(
            abuse_report_id=report.id,
            resource_type=report.resource_type,
            resource_id=report.resource_id,
            resource_name=report.resource_name,
            workspace_id=report.workspace_id,
            workspace_name=report.workspace_name,
            public_url=report.public_url,
            reporter_name=report.reporter_name,
            reporter_email=report.reporter_email,
            description=report.description,
        )
        cls.register_action(
            user,
            params,
            scope=cls.scope(report.workspace_id),
            workspace=resource.workspace,
        )

        if should_notify:
            AbuseReportCreatedNotificationType.notify_instance_admins(report)

        return report

    @classmethod
    def scope(cls, workspace_id: Optional[int] = None) -> ActionScopeStr:
        if workspace_id is not None:
            return WorkspaceActionScopeType.value(workspace_id)
        return RootActionScopeType.value()
