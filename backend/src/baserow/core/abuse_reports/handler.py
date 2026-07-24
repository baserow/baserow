from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from baserow.core.handler import CoreHandler

from .exceptions import AbuseReportingDisabledException
from .models import AbuseReport
from .notification_types import AbuseReportCreatedNotificationType
from .registries import AbuseReportResourceType, ReportedResource


class AbuseReportHandler:
    @classmethod
    def create_abuse_report(
        cls,
        resource_type: AbuseReportResourceType,
        resource: ReportedResource,
        reporter_name: str,
        reporter_email: str,
        description: str,
        ip_address: Optional[str] = None,
    ) -> AbuseReport:
        """
        Persists an abuse report for the provided resource, and notifies the
        instance admins unless they were recently notified about the same resource.

        :param resource_type: The registered resource type that resolved the resource.
        :param resource: The resolved publicly shared resource.
        :param reporter_name: The self-reported name of the reporter.
        :param reporter_email: The self-reported email address of the reporter.
        :param description: Why the reporter believes the resource is abusive.
        :param ip_address: The IP address the report was submitted from.
        :raises AbuseReportingDisabledException: When the instance admin has disabled
            abuse reporting.
        :return: The created report.
        """

        if not CoreHandler().get_settings().allow_reporting_abuse:
            raise AbuseReportingDisabledException(
                "Reporting abuse has been disabled by the instance administrator."
            )

        cooldown_start = timezone.now() - timedelta(
            seconds=settings.BASEROW_ABUSE_REPORT_NOTIFICATION_COOLDOWN_SECONDS
        )
        already_notified = AbuseReport.objects.filter(
            resource_type=resource_type.type,
            resource_id=resource.resource_id,
            admins_notified=True,
            created_on__gte=cooldown_start,
        ).exists()

        report = AbuseReport.objects.create(
            resource_type=resource_type.type,
            resource_id=resource.resource_id,
            resource_name=resource.name,
            workspace=resource.workspace,
            workspace_name=resource.workspace.name if resource.workspace else "",
            public_url=resource.public_url,
            reporter_name=reporter_name,
            reporter_email=reporter_email,
            description=description,
            ip_address=ip_address,
        )

        if not already_notified:
            AbuseReportCreatedNotificationType.notify_instance_admins(report)

        return report
