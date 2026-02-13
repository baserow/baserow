import base64
import binascii
from typing import TYPE_CHECKING, Any, Dict, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db.models import Model, QuerySet

from defusedxml import ElementTree
from loguru import logger

from baserow.core.auth_provider.types import UserInfo
from baserow_enterprise.api.sso.utils import get_valid_frontend_url
from baserow_enterprise.sso.saml.models import (
    SamlAuthProviderModel,
    SamlAuthProviderModelMixin,
)

from .exceptions import (
    InvalidSamlConfiguration,
    InvalidSamlRequest,
    InvalidSamlResponse,
)

if TYPE_CHECKING:
    from saml2.client import Saml2Client
    from saml2.response import AuthnResponse


class SamlAuthProviderHandler:
    model_class: Model = SamlAuthProviderModel

    @classmethod
    def prepare_saml_client(
        cls,
        saml_auth_provider: SamlAuthProviderModelMixin,
    ) -> "Saml2Client":
        """
        Returns a SAML client with the correct configuration for the given
        authentication provider.

        :param saml_auth_provider: The authentication provider that needs to be
            used to authenticate the user.
        :return: The SAML client that can be used to authenticate the user.
        """

        from saml2 import BINDING_HTTP_POST, BINDING_HTTP_REDIRECT
        from saml2.client import Saml2Client
        from saml2.config import Config as Saml2Config

        acs_url = saml_auth_provider.get_type().get_acs_absolute_url(
            saml_auth_provider.specific
        )

        saml_settings: Dict[str, Any] = {
            "entityid": acs_url,
            "metadata": {"inline": [saml_auth_provider.metadata]},
            "allow_unknown_attributes": True,
            "debug": settings.DEBUG,
            "service": {
                "sp": {
                    "endpoints": {
                        "assertion_consumer_service": [
                            (acs_url, BINDING_HTTP_REDIRECT),
                            (acs_url, BINDING_HTTP_POST),
                        ],
                    },
                    "allow_unsolicited": True,
                    "authn_requests_signed": False,
                    "logout_requests_signed": True,
                    "want_assertions_signed": False,
                    "want_response_signed": False,
                },
            },
        }
        sp_config = Saml2Config()
        sp_config.load(saml_settings)
        return Saml2Client(config=sp_config)

    @classmethod
    def check_authn_response_is_valid_or_raise(cls, authn_response: "AuthnResponse"):
        """
        Checks if the authn response is valid and raises an exception if not.

        :param authn_response: The authn response that should be checked.
        :raises InvalidSamlResponse: When the authn response is not valid.
        :return: True if the authn response is valid.
        """

        if not authn_response:
            raise InvalidSamlResponse(
                "There was no response from SAML identity provider."
            )

        if not authn_response.name_id:
            raise InvalidSamlResponse("No name_id in SAML response.")

        if not authn_response.issuer():
            raise InvalidSamlResponse("No issuer/entity_id in SAML response.")

        if not authn_response.get_identity():
            raise InvalidSamlResponse("No user identity in SAML response.")

    @classmethod
    def get_saml_auth_provider_from_saml_response(
        cls, raw_saml_response: str, base_queryset: QuerySet | None = None
    ) -> SamlAuthProviderModelMixin:
        """
        Parses the saml response and returns the authentication provider that needs to
        be used to authenticate the user.

        :param saml_raw_response: The raw saml response that was received from the
            identity provider.
        :raises InvalidSamlResponse: When the saml response is not valid.
        :raises InvalidSamlConfiguration: When the correct authentication provider is
            not found in the system based on the information of saml response received.
        :return: The authentication provider that needs to be used to authenticate the
            user.
        """

        try:
            saml_response = cls.decode_saml_response(raw_saml_response)
            saml_response_xml_tree = ElementTree.fromstring(saml_response)
            issuer = saml_response_xml_tree.find(
                "{urn:oasis:names:tc:SAML:2.0:assertion}Issuer"
            ).text
        except (ElementTree.ParseError, AttributeError):
            raise InvalidSamlResponse("Impossible decode SAML response.")

        if base_queryset is None:
            base_queryset = cls.model_class.objects

        saml_auth_provider = base_queryset.filter(
            enabled=True, metadata__contains=issuer
        ).first()
        if not saml_auth_provider:
            raise InvalidSamlConfiguration("SAML auth provider not found.")
        return saml_auth_provider

    @classmethod
    def get_user_info_from_authn_user_identity(
        cls,
        saml_auth_provider: SamlAuthProviderModelMixin,
        authn_identity: Dict[str, str],
        saml_request_data: Optional[Dict[str, str]] = None,
    ) -> UserInfo:
        """
        Extracts the information from the dict returned by
        `authn_response.get_identity()` and merge them with data sent in the
        SAML request (e.g. language and group invitation token) to
        create/retrieve the correct user.

        :param saml_auth_provider: The related saml auth provider model instance.
        :param authn_identity: The dict returned by
            `authn_response.get_identity()` that contains the user identity
            information.
        :param saml_request_data: Additional data sent together in the SAML
            request (e.g. language and group invitation token).
        :return: A UserInfo object containing all the information needed to
            create/retrieve the correct user.
        """

        email_key = saml_auth_provider.email_attr_key
        first_name_key = saml_auth_provider.first_name_attr_key
        last_name_key = saml_auth_provider.last_name_attr_key

        logger.debug("Expected email key: {0}", email_key)
        logger.debug("SAML authn identity: {0}", authn_identity)

        saml_request_data = saml_request_data or {}
        email = authn_identity[email_key][0]
        if first_name_key in authn_identity:
            first_name = authn_identity[first_name_key][0]
            if last_name_key in authn_identity:
                last_name = authn_identity[last_name_key][0]
            else:
                last_name = ""
            name = f"{first_name} {last_name}".strip()
        elif "user.name" in authn_identity:
            # kept for backward compatibility
            name = authn_identity["user.name"][0]
        else:
            name = email

        logger.debug("Extracted user info: {0} {1} {2}", email, name, saml_request_data)
        return UserInfo(email, name, **saml_request_data)

    @classmethod
    def get_saml_auth_provider_from_email(
        cls, email: Optional[str] = None, base_queryset: QuerySet | None = None
    ) -> SamlAuthProviderModel:
        """
        It returns the Saml Identity Provider for the the given email address.
        If the email address and only one IdP is configured, it returns that
        IdP.

        :param email: The email address of the user.
        :raises InvalidSamlRequest: If there is no SamlAuthProviderModel for
            the domain provided or the email is invalid.
        :return: The SamlAuthProvider model relative to the domain of the email
            address provided.
        """

        if base_queryset is None:
            base_queryset = cls.model_class.objects

        queryset = base_queryset.filter(enabled=True)

        if email is not None:
            try:
                domain = email.rsplit("@", 1)[1]
            except IndexError:
                raise InvalidSamlRequest("Invalid mail address provided.")

            queryset = queryset.filter(domain=domain)

        try:
            return queryset.get()
        except (
            cls.model_class.DoesNotExist,
            cls.model_class.MultipleObjectsReturned,
        ):
            raise InvalidSamlRequest("No valid SAML identity provider found.")

    @classmethod
    def decode_saml_response(self, raw_saml_response: str) -> str:
        try:
            return base64.b64decode(raw_saml_response).decode("utf-8")
        except binascii.Error:
            raise InvalidSamlResponse("SAML response payload should be base64 encoded.")

    @classmethod
    def sign_in_user_from_saml_response(
        cls,
        saml_response: str,
        saml_request_data: Optional[Dict[str, str]] = None,
        base_queryset: QuerySet | None = None,
    ) -> AbstractUser:
        """
        Signs in the user using the SAML response received from the identity
        provider.

        :param saml_response: The encoded SAML response sent from the Identity
            Provider.
        :param saml_request_data: The data that was sent in the SAML request.
        :raises InvalidSamlResponse: When the SAML response is not valid.
        :raises InvalidSamlConfiguration: When the SAML configuration is not
            valid.
        :return: The user that was signed in.
        """

        from saml2 import entity

        try:
            saml_auth_provider = cls.get_saml_auth_provider_from_saml_response(
                saml_response, base_queryset=base_queryset
            )

            saml_client = cls.prepare_saml_client(saml_auth_provider)
            authn_response = saml_client.parse_authn_request_response(
                saml_response, entity.BINDING_HTTP_POST
            )
            cls.check_authn_response_is_valid_or_raise(authn_response)
            authn_user_identity = authn_response.get_identity()
            idp_provided_user_info = cls.get_user_info_from_authn_user_identity(
                saml_auth_provider, authn_user_identity, saml_request_data
            )
        except (InvalidSamlConfiguration, InvalidSamlResponse) as exc:
            logger.exception(exc)
            raise exc
        except Exception as exc:
            logger.exception(exc)
            raise InvalidSamlResponse(str(exc))

        (
            user,
            _,
        ) = saml_auth_provider.get_type().get_or_create_user_and_sign_in(
            saml_auth_provider, idp_provided_user_info
        )

        # since we correctly sign in a user, we can set this IdP as verified
        # This means it can be used as unique authentication provider from now on
        if not saml_auth_provider.is_verified:
            saml_auth_provider.is_verified = True
            saml_auth_provider.save()

        return user

    @classmethod
    def get_sign_in_url_for_auth_provider(
        cls,
        saml_auth_provider: SamlAuthProviderModelMixin,
        relay_state: str = "",
    ) -> str:
        """
        Returns the redirect url to the identity provider. This url is used to
        initiate the SAML authentication flow from the service provider.

        :param saml_auth_provider: The identity provider to which the user
            should be redirected.
        :param relay_state: Data relayed by the Idp. Usually the url to which the user
            should be redirected after a successful login.
        :raises InvalidSamlConfiguration: If the SAML configuration is invalid.
        :return: The redirect URL to the identity provider.
        """

        saml_client = cls.prepare_saml_client(saml_auth_provider)

        _, info = saml_client.prepare_for_authenticate(relay_state=relay_state)

        for key, value in info["headers"]:
            if key == "Location":
                redirect_url = value
                return redirect_url
        else:
            raise InvalidSamlConfiguration("No Location header found in SAML response.")

    @classmethod
    def get_sign_in_url(
        cls,
        query_params: Dict[str, str],
        base_queryset: QuerySet | None = None,
        relay_state: str | None = None,
    ) -> str:
        """
        Returns the sign in url for the correct identity provider. This url is
        used to initiate the SAML authentication flow from the service provider.

        :param query_params: A dict containing the query parameters from the
            sign in request.
        :param relay_state: if set, used as relay state.
        :raises InvalidSamlRequest: If the email address is invalid.
        :raises InvalidSamlConfiguration: If the SAML configuration is invalid.
        :return: The redirect url to the identity provider.
        """

        user_email = query_params.pop("email", None)

        if relay_state is None:
            original_url = query_params.pop("original", "")
            relay_state = get_valid_frontend_url(original_url, query_params)

        try:
            saml_auth_provider = cls.get_saml_auth_provider_from_email(
                user_email, base_queryset=base_queryset
            )
            return cls.get_sign_in_url_for_auth_provider(
                saml_auth_provider, relay_state
            )
        except (InvalidSamlRequest, InvalidSamlConfiguration) as exc:
            logger.exception(exc)
            raise exc
        except Exception as exc:
            logger.exception(exc)
            raise InvalidSamlRequest(str(exc))
