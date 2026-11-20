from rest_framework import serializers


class MicrosoftTeamsTeamSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="The id of the team.")
    name = serializers.CharField(help_text="The name of the team.")


class MicrosoftTeamsChannelSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="The id of the channel.")
    name = serializers.CharField(help_text="The name of the channel.")
    membership_type = serializers.CharField(
        help_text="`standard`, `private` or `shared`."
    )


class MicrosoftTeamsChatSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="The id of the chat.")
    name = serializers.CharField(
        help_text="The topic of the chat, or the names of its other members."
    )
    chat_type = serializers.CharField(help_text="`oneOnOne`, `group` or `meeting`.")
