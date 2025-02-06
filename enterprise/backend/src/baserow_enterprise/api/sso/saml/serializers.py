from urllib.parse import parse_qsl, urlparse

from rest_framework import serializers

from baserow_enterprise.api.sso.serializers import SsoLoginRequestSerializer
from baserow_enterprise.sso.saml.exceptions import InvalidSamlResponse


class SAMLResponseSerializer(serializers.Serializer):
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
            request_data_serializer = SsoLoginRequestSerializer(data=query_params)
            if request_data_serializer.is_valid():
                data["saml_request_data"] = request_data_serializer.validated_data
            else:
                raise InvalidSamlResponse("Invalid RelayState query parameters.")

        data["RelayState"] = parsed_relay_state._replace(query="").geturl()

        return data
