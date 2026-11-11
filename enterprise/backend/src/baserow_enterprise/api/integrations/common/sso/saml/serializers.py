from urllib.parse import parse_qsl, urlparse

from rest_framework import serializers

from baserow_enterprise.api.sso.utils import is_sso_callback_param
from baserow_enterprise.sso.saml.exceptions import InvalidSamlResponse


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
        try:
            parsed_relay_state = urlparse(relay_state)
        except ValueError as exc:
            raise InvalidSamlResponse("Invalid RelayState.") from exc
        # The view adds these to the redirect url next to the real token.
        query_params = {
            name: value
            for name, value in parse_qsl(parsed_relay_state.query)
            if not is_sso_callback_param(name)
        }
        if query_params:
            data["saml_request_data"] = query_params

        data["RelayState"] = parsed_relay_state._replace(query="").geturl()

        return data
