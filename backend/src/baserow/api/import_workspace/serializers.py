from rest_framework import serializers

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.core.db import specific_iterator
from baserow.core.models import Application


class ImportWorkspaceSerializerMixin(serializers.Serializer):
    installed_applications = serializers.SerializerMethodField()

    def get_installed_applications(self, instance):
        if not instance.application_ids:
            return None

        application_ids = instance.application_ids.split(",")

        applications = specific_iterator(
            Application.objects.select_related("content_type", "workspace").filter(
                pk__in=application_ids, workspace__trashed=False
            )
        )
        return [
            PolymorphicApplicationResponseSerializer(app).data for app in applications
        ]
