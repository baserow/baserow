from rest_framework import serializers

from baserow.core.models import Workspace


class AdminWorkspaceSerializer(serializers.ModelSerializer):
    value = serializers.CharField(source="name")

    class Meta:
        model = Workspace
        fields = ("id", "value")
