from rest_framework import serializers


class NewEndpointSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    workspace_id = serializers.IntegerField()


class ConsentSerializer(serializers.Serializer):
    query = serializers.CharField()
    allow = serializers.BooleanField()
    endpoint_id = serializers.IntegerField(required=False)
    new_endpoint = NewEndpointSerializer(required=False)

    def validate(self, data):
        if data["allow"] and "endpoint_id" not in data and "new_endpoint" not in data:
            raise serializers.ValidationError(
                "Either endpoint_id or new_endpoint is required when allowing."
            )
        return data
