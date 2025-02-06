from urllib.parse import parse_qsl, urlparse

from rest_framework import serializers


class CommonSAMLResponseSerializer(serializers.Serializer):
    SAMLResponse = serializers.CharField(
        required=True, help_text="The encoded SAML response from the IdP."
    )
    RelayState = serializers.CharField(
        required=True,
        help_text="The frontend URL where redirect the authenticated user.",
    )

    def to_internal_value(self, data):
        data = super().to_internal_value(data)

        # decode the RelayState and extract the query parameters
        # as additional data for the user login request
        relay_state = data["RelayState"]
        data["saml_request_data"] = {}
        parsed_relay_state = urlparse(relay_state)
        query_params = dict(parse_qsl(parsed_relay_state.query))
        if query_params:
            data["saml_request_data"] = query_params

        data["RelayState"] = parsed_relay_state._replace(query="").geturl()

        return data
