from datetime import timedelta

from django.contrib.auth import get_user_model

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import accept_timezone
from baserow.core.admin.dashboard.handler import AdminDashboardHandler
from baserow.core.models import Application, Workspace

from .serializers import AdminDashboardSerializer

User = get_user_model()


class AdminDashboardView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_dashboard",
        description="Returns the new and active users for the last 24 hours, 7 days and"
        " 30 days. The `previous_` values are the values of the period before, so for "
        "example `previous_new_users_last_24_hours` are the new users that signed up "
        "from 48 to 24 hours ago. It can be used to calculate an increase or decrease "
        "in the amount of signups. A list of the new and active users for every day "
        "for the last 30 days is also included.",
        responses={
            200: AdminDashboardSerializer,
            401: None,
        },
    )
    @accept_timezone()
    def get(self, request, now):
        """
        Returns the new and active users for the last 24 hours, 7 days and 30 days.
        The `previous_` values are the values of the period before, so for example
        `previous_new_users_last_24_hours` are the new users that signed up from 48
        to 24 hours ago. It can be used to calculate an increase or decrease in the
        amount of signups. A list of the new and active users for every day for the
        last 30 days is also included.
        """

        handler = AdminDashboardHandler()
        total_users = User.objects.filter(is_active=True).count()
        total_workspaces = Workspace.objects.filter(template__isnull=True).count()
        total_applications = Application.objects.filter(
            workspace__template__isnull=True
        ).count()
        new_users = handler.get_new_user_counts(
            {
                "new_users_last_24_hours": timedelta(hours=24),
                "new_users_last_7_days": timedelta(days=7),
                "new_users_last_30_days": timedelta(days=30),
            },
            include_previous=True,
        )
        active_users = handler.get_active_user_count(
            {
                "active_users_last_24_hours": timedelta(hours=24),
                "active_users_last_7_days": timedelta(days=7),
                "active_users_last_30_days": timedelta(days=30),
            },
            include_previous=True,
        )
        new_users_per_day = handler.get_new_user_count_per_day(
            timedelta(days=30), now=now
        )
        active_users_per_day = handler.get_active_user_count_per_day(
            timedelta(days=30), now=now
        )

        serializer = AdminDashboardSerializer(
            {
                "total_users": total_users,
                "total_workspaces": total_workspaces,
                "total_applications": total_applications,
                "new_users_per_day": new_users_per_day,
                "active_users_per_day": active_users_per_day,
                **new_users,
                **active_users,
            }
        )
        return Response(serializer.data)
