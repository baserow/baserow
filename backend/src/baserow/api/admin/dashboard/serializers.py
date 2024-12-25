from rest_framework import serializers


class AdminDashboardPerDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()


class AdminDashboardSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_workspaces = serializers.IntegerField()
    total_applications = serializers.IntegerField()
    new_users_last_24_hours = serializers.IntegerField()
    new_users_last_7_days = serializers.IntegerField()
    new_users_last_30_days = serializers.IntegerField()
    previous_new_users_last_24_hours = serializers.IntegerField()
    previous_new_users_last_7_days = serializers.IntegerField()
    previous_new_users_last_30_days = serializers.IntegerField()
    active_users_last_24_hours = serializers.IntegerField()
    active_users_last_7_days = serializers.IntegerField()
    active_users_last_30_days = serializers.IntegerField()
    previous_active_users_last_24_hours = serializers.IntegerField()
    previous_active_users_last_7_days = serializers.IntegerField()
    previous_active_users_last_30_days = serializers.IntegerField()
    new_users_per_day = serializers.ListSerializer(
        child=AdminDashboardPerDaySerializer()
    )
    active_users_per_day = serializers.ListSerializer(
        child=AdminDashboardPerDaySerializer()
    )
