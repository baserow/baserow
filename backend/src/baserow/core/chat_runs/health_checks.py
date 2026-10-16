from datetime import timedelta

from django.utils import timezone

from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import ServiceWarning

from .constants import WAITING_WARNING_AFTER
from .models import ChatRun, ChatRunStatus

UNENDED_RUN_WARNING_AFTER = timedelta(minutes=2)


class ChatRunsHealthCheck(BaseHealthCheckBackend):
    """
    Warns when chat runs wait too long for a worker, or when runs whose worker
    died are not ended, which means the sweeper isn't running.
    """

    critical_service = False

    def check_status(self) -> None:
        """
        :raises ServiceWarning: When runs wait or nobody ends lost runs.
        """

        now = timezone.now()
        if ChatRun.objects.filter(
            status=ChatRunStatus.QUEUED, created_on__lt=now - WAITING_WARNING_AFTER
        ).exists():
            raise ServiceWarning(
                "Chat runs are waiting for a worker. Check that a worker consumes "
                "the chat_run queue."
            )
        if ChatRun.objects.filter(
            status=ChatRunStatus.RUNNING,
            lease_expires_at__lt=now - UNENDED_RUN_WARNING_AFTER,
        ).exists():
            raise ServiceWarning(
                "Chat runs lost their worker and were not ended. Check that "
                "celery-beat runs."
            )

    def identifier(self) -> str:
        return self.__class__.__name__
