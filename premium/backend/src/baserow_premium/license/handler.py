import base64
import binascii
import hashlib
import json
from datetime import datetime, timezone
from os.path import dirname, join
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import DatabaseError, transaction
from django.db.models import Q

import requests
from baserow_premium.api.user.user_data_types import ActiveLicensesDataType
from baserow_premium.license.exceptions import (
    CantManuallyChangeSeatsError,
    InvalidLicenseError,
)
from baserow_premium.license.models import License
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from dateutil import parser
from loguru import logger
from requests.exceptions import RequestException
from rest_framework.status import HTTP_200_OK

from baserow.api.user.registries import user_data_registry
from baserow.core.exceptions import IsNotAdminError
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.registries import plugin_registry
from baserow.core.utils import get_baserow_saas_base_url
from baserow.ws.signals import broadcast_to_users

from .constants import (
    AUTHORITY_RESPONSE_DOES_NOT_EXIST,
    AUTHORITY_RESPONSE_INSTANCE_ID_MISMATCH,
    AUTHORITY_RESPONSE_INVALID,
    AUTHORITY_RESPONSE_UPDATE,
)
from .exceptions import (
    FeaturesNotAvailableError,
    LicenseAlreadyExistsError,
    LicenseAuthorityUnavailable,
    LicenseHasExpiredError,
    LicenseInstanceIdMismatchError,
    NoSeatsLeftInLicenseError,
    UnsupportedLicenseError,
    UserAlreadyOnLicenseError,
)
from .models import LicenseUser
from .registries import license_type_registry

User = get_user_model()


class LicenseHandler:
    @classmethod
    def raise_if_user_doesnt_have_feature_instance_wide(
        cls,
        feature: str,
        user: AbstractUser,
    ):
        """
        Raises the `FeaturesNotAvailableError` if the user does not have an
        active license granting them the provided feature.
        """

        if not cls.user_has_feature_instance_wide(feature, user):
            raise FeaturesNotAvailableError()

    @classmethod
    def raise_if_user_doesnt_have_feature(
        cls, feature: str, user: AbstractUser, workspace: Workspace
    ):
        """
        Checks if the provided user has the feature for a workspace or instance-wide.

        :param user: The user to check for feature access.
        :param workspace: The workspace that the user must have active premium for.
        :param feature: The feature the user must have.
        :raises FeaturesNotAvailableError: if the user does not have premium
            features from a license the provided workspace.
        """

        if not cls.user_has_feature(feature, user, workspace):
            raise FeaturesNotAvailableError()

    @classmethod
    def raise_if_workspace_doesnt_have_feature(cls, feature: str, workspace: Workspace):
        """
        Checks if the provided workspace has the feature for a workspace or
        instance-wide.

        :param feature: The feature the user must have.
        :param workspace: The workspace that the user must have active premium for.
        :raises FeaturesNotAvailableError: if the user does not have premium
            features from a license the provided workspace.
        """

        if not cls.workspace_has_feature(feature, workspace):
            raise FeaturesNotAvailableError()

    @classmethod
    def user_has_feature(cls, feature: str, user: AbstractUser, workspace: Workspace):
        """
        Checks if the user has a particular feature granted by an active license for a
        workspace. This could be granted by a license specific to that workspace, or an
        instance level license, or a license which is instance wide.

        :param feature: The feature to check to see if active. Look for features.py
            files for these constant strings to use.
        :param user: The user to check.
        :param workspace: The workspace that the user is attempting to
            use the feature in.
        :return: True if the user is allowed to use that feature, False otherwise.
        """

        license_plugin = cls._get_license_plugin()
        return license_plugin.user_has_feature(feature, user, workspace)

    @classmethod
    def instance_has_feature(cls, feature: str):
        """
        Checks if the Baserow instance has a particular feature granted by an active
        instance wide license

        :param feature: The feature to check to see if active. Look for features.py
            files for these constant strings to use.
        :return: True if the feature is enabled globally for all users.
        """

        license_plugin = cls._get_license_plugin()
        return license_plugin.instance_has_feature(feature)

    @classmethod
    def workspace_has_feature(cls, feature: str, workspace: Workspace):
        """
        Checks if the Baserow workspace has a particular feature granted to the
        workspace itself.

        :param feature: The feature to check to see if active. Look for features.py
            files for these constant strings to use.
        :param workspace: The workspace to check to see if the feature is active for
            everyone in that workspace.
        :return: True if the feature is enabled for a particular workspace.
        """

        license_plugin = cls._get_license_plugin()
        return license_plugin.workspace_has_feature(feature, workspace)

    @classmethod
    def user_has_feature_instance_wide(cls, feature: str, user: AbstractUser):
        """
        Checks if the Baserow instance has a particular feature granted by an active
        instance wide license

        :param feature: The feature to check to see if active. Look for features.py
            files for these constant strings to use.
        :param user: The user to check.
        :return: True if the feature is enabled globally for all users.
        """

        license_plugin = cls._get_license_plugin()
        return license_plugin.user_has_feature_instance_wide(feature, user)

    @classmethod
    def _get_license_plugin(cls):
        from baserow_premium.plugins import PremiumPlugin

        license_plugin = plugin_registry.get_by_type(PremiumPlugin).get_license_plugin()
        return license_plugin

    @classmethod
    def get_public_key(cls):
        """
        Returns the public key instance that can be used to verify licenses. A different
        key file is loaded when Baserow is in debug mode.
        """

        import baserow_premium

        file_name = "public_key_debug.pem" if settings.DEBUG else "public_key.pem"
        public_key_path = join(dirname(baserow_premium.__file__), file_name)
        with open(public_key_path, "rb") as key_file:
            public_key = serialization.load_pem_public_key(
                key_file.read(), backend=default_backend()
            )
        return public_key

    @classmethod
    def decode_license(cls, license_payload: bytes) -> dict:
        """
        Tries to decode the provided license and returns the payload if successful.

        :param license_payload: The raw license that must be decoded.
        :raises InvalidLicenseError: When the provided license is invalid. This
            could for example be when the signature or payload is invalid.
        :raises UnsupportedLicenseError: When the provided license payload is an
            unsupported version. If this happens, you probably need to update your
            Baserow installation.
        :return: If successful, the decoded license payload is returned.
        """

        try:
            payload_base64, signature_base64 = license_payload.split(b".")
        except ValueError:
            raise InvalidLicenseError(
                "The provided payload does not follow the expected format."
            )

        pre_hashed = hashlib.sha256(payload_base64).hexdigest().encode()

        try:
            signature = base64.urlsafe_b64decode(signature_base64)
        except binascii.Error:
            raise InvalidLicenseError("Invalid base64 signature provided.")

        public_key = cls.get_public_key()

        try:
            public_key.verify(
                signature,
                pre_hashed,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
        except InvalidSignature:
            raise InvalidLicenseError(
                "The signature of the premium license is invalid."
            )

        try:
            payload_json = base64.urlsafe_b64decode(payload_base64)
        except binascii.Error:
            raise InvalidLicenseError("Invalid base64 payload provided.")

        try:
            payload = json.loads(payload_json)
        except json.decoder.JSONDecodeError:
            raise InvalidLicenseError("Invalid JSON payload provided.")

        if "version" not in payload:
            raise InvalidLicenseError("The payload does not contain a version.")

        if payload["version"] != 1:
            raise UnsupportedLicenseError(
                "Only license version 1 is supported. You probably need to update your "
                "copy of Baserow."
            )

        return payload

    @classmethod
    def send_license_info_and_fetch_license_status_with_authority(
        cls, license_objects: List[License]
    ):
        license_payloads = []
        extra_license_info = []

        for license_object in license_objects:
            license_payloads.append(license_object.license)

            try:
                license_type = license_object.license_type
                usage = license_type.get_seat_usage_summary(license_object)
                if usage is not None:
                    extra_info = {
                        "id": license_object.license_id,
                        "seats_taken": usage.seats_taken,
                        "free_users_count": usage.free_users_count,
                        "highest_role_per_user_id": usage.highest_role_per_user_id,
                    }
                    extra_license_info.append(extra_info)
            except (InvalidLicenseError, UnsupportedLicenseError, DatabaseError):
                pass

        return cls.fetch_license_status_with_authority(
            license_payloads, extra_license_info
        )

    @classmethod
    def fetch_license_status_with_authority(
        cls,
        license_payloads: List[Union[str, bytes]],
        extra_license_info: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Fetches the state of the license with the authority. It could be that the
        license must be updated because it has changed, it might have been deleted,
        the instance_id might not match anymore or it might be invalid.

        :param license_payloads: A list of licenses that must be checked with the
            authority.
        :param extra_license_info: A list of extra information about each license
            to send to the authority.
        :return: The state of each license provided.
        """

        settings_object = CoreHandler().get_settings()

        try:
            base_url, headers = get_baserow_saas_base_url()
            authority_url = f"{base_url}/api/saas/licenses/check/"

            response = requests.post(
                authority_url,
                json={
                    "licenses": license_payloads,
                    "instance_id": settings_object.instance_id,
                    "extra_license_info": extra_license_info,
                },
                timeout=settings.LICENSE_AUTHORITY_CHECK_TIMEOUT_SECONDS,
                headers=headers,
            )

            if response.status_code == HTTP_200_OK:
                return response.json()
            else:
                raise LicenseAuthorityUnavailable(
                    "The license authority can't be reached because it didn't returned "
                    "with an ok response."
                )
        except RequestException:
            raise LicenseAuthorityUnavailable(
                "The license authority can't be reached because of a network error."
            )
        except json.decoder.JSONDecodeError:
            raise LicenseAuthorityUnavailable(
                "The license authority did not respond with valid json."
            )

    @classmethod
    def check_licenses(cls, license_objects: List[License]) -> List[License]:
        """
        Checks the state of the licenses with the authority and checks if the licenses
        are operating within their limits.

        - It will update the license payload if needed.
        - It removes the license if it doesn't exist, if it's invalid or if the instance
          id doesn't match.
        - It also checks if the license is operating within its limit. For example if
          the license has not crossed the maximum amount of seats.

        :param license_objects: The license objects that must be checked
        :return: The updated license objects.
        """

        try:
            authority_response = (
                cls.send_license_info_and_fetch_license_status_with_authority(
                    license_objects
                )
            )

            for license_object in license_objects:
                if license_object.license not in authority_response:
                    continue

                authority_check = authority_response[license_object.license]

                if authority_check["type"] == AUTHORITY_RESPONSE_UPDATE:
                    license_object.license = authority_check["new_license_payload"]
                    license_payload_as_string = authority_check["new_license_payload"]
                    license_payload = license_payload_as_string.encode()
                    decoded_license_payload = cls.decode_license(license_payload)
                    instance_wide = license_type_registry.get(
                        decoded_license_payload["product_code"]
                    ).instance_wide
                    license_object.cached_untrusted_instance_wide = instance_wide
                    license_object.save()
                elif authority_check["type"] in [
                    AUTHORITY_RESPONSE_DOES_NOT_EXIST,
                    AUTHORITY_RESPONSE_INSTANCE_ID_MISMATCH,
                    AUTHORITY_RESPONSE_INVALID,
                ]:
                    license_object.delete()

        except LicenseAuthorityUnavailable as e:
            # If the license authority is unavailable for whatever reason, we don't want
            # the check to fail because the cls hosted instance might not have
            # internet and the license is already validated locally.
            logger.warning(str(e))

        for license_object in license_objects:
            # If the license object has been deleted we can skip it.
            if not license_object.pk:
                continue

            # If the license payload could not be decoded, it must be deleted.
            try:
                license_object.payload
            except InvalidLicenseError:
                license_object.delete()
                continue

            summary = license_object.license_type.get_seat_usage_summary(license_object)
            if summary is not None and summary.seats_taken > license_object.seats:
                license_object.license_type.handle_seat_overflow(
                    summary.seats_taken, license_object
                )

            license_object.last_check = datetime.now(tz=timezone.utc)
            license_object.save()

        return license_objects

    @classmethod
    def register_license(
        cls, requesting_user: User, license_payload: Union[bytes, str]
    ) -> License:
        """
        Registers a new license by adding it to the database. If a license with same id
        already exists and the provided one was issued later, then the existing one will
        be updated.

        :param requesting_user: The user on whose behalf the license is registered.
        :param license_payload: The license that must be decoded and added.
        :raises LicenseAlreadyExistsError: When the license already exists.
        :raises LicenseHasExpiredError: When the license has expired.
        :return: The created license instance.
        """

        if not requesting_user.is_staff:
            raise IsNotAdminError()

        if isinstance(license_payload, str):
            license_payload_as_string = license_payload
            license_payload = license_payload.encode()
        else:
            license_payload_as_string = license_payload.decode()

        try:
            authority_response = cls.fetch_license_status_with_authority(
                [license_payload_as_string]
            )
            authority_check = authority_response[license_payload_as_string]

            if authority_check["type"] == AUTHORITY_RESPONSE_UPDATE:
                # If there is a newer version of the license, we can replace the license
                # payload that we have in memory with that one.
                license_payload_as_string = authority_check["new_license_payload"]
                license_payload = license_payload_as_string.encode()
            elif authority_check["type"] == AUTHORITY_RESPONSE_DOES_NOT_EXIST:
                # If the authority tells us that the license does not exist there,
                # we must stop the registering.
                raise InvalidLicenseError(
                    "The license does not exist according to the authority."
                )
            elif authority_check["type"] == AUTHORITY_RESPONSE_INSTANCE_ID_MISMATCH:
                # If the authority tells us the instance id doesn't match,
                # we can immediately raise that error.
                raise LicenseInstanceIdMismatchError(
                    "The instance id doesn't match according to the authority."
                )
            elif authority_check["type"] == AUTHORITY_RESPONSE_INVALID:
                raise InvalidLicenseError(
                    "The license is invalid according to the authority."
                )

        except LicenseAuthorityUnavailable as e:
            # If the license authority is unavailable for whatever reason, we don't want
            # the registering to fail because the cls hosted instance might not have
            # internet and the license can be validated locally with the public key.
            logger.warning(str(e))

        # Try to decode the provided license payload in order to trigger the errors
        # if needed. We also need the `valid_through` date to check if the license
        # has expired.
        decoded_license_payload = cls.decode_license(license_payload)
        valid_through = parser.parse(decoded_license_payload["valid_through"]).replace(
            tzinfo=timezone.utc
        )
        issued_on = parser.parse(decoded_license_payload["issued_on"]).replace(
            tzinfo=timezone.utc
        )

        if valid_through < datetime.now(tz=timezone.utc):
            raise LicenseHasExpiredError(
                "Cannot add the license because it has already expired."
            )

        # The `instance_id` of the license must match with the `instance_id` of the cls
        # hosted copy.
        settings_object = CoreHandler().get_settings()
        if decoded_license_payload["instance_id"] != settings_object.instance_id:
            raise LicenseInstanceIdMismatchError(
                "The license instance id does not match the instance id."
            )

        instance_wide = license_type_registry.get(
            decoded_license_payload["product_code"]
        ).instance_wide

        license_id = decoded_license_payload["id"]
        license_object = cls.find_license_older_than(license_id, issued_on) or License()

        license_object.license = license_payload_as_string
        license_object.cached_untrusted_instance_wide = instance_wide
        license_object.save()

        if instance_wide:
            transaction.on_commit(
                lambda: broadcast_to_users.delay(
                    send_to_all_users=True,
                    user_ids=[],
                    payload=user_data_registry.get_by_type(
                        ActiveLicensesDataType
                    ).realtime_message_to_enable_instancewide_license(
                        license_object.license_type
                    ),
                )
            )
        return license_object

    @classmethod
    def find_license_older_than(cls, license_id, issued_on):
        # Loop over all licenses to check if a license with the same ID already
        # exists. We can't use `objects.filter` because we need to decode the license
        # with the public key before we can extract the id.
        for license_object in License.objects.all():
            if license_object.license_id == license_id:
                # If the `issued_on` date of the existing license is lower then the new
                # license, we want to update it because a new one has been issued later
                # and is newer.
                if license_object.issued_on < issued_on:
                    return license_object
                # If the `issued_on` date of the existing license is higher or equal to
                # the new license, we want to raise the exception that the most license
                # already exists.
                else:
                    raise LicenseAlreadyExistsError("The license already exists.")
        return None

    @classmethod
    def remove_license(cls, requesting_user: User, license: License):
        """
        Removes an existing license. If the license is still active, all the users that
        are on that license will lose access to the licenses features.

        :param requesting_user: The user on whose behalf the license is removed.
        :param license: The license that must be removed.
        """

        if not requesting_user.is_staff:
            raise IsNotAdminError()

        license_type = license.license_type
        if license_type.instance_wide:
            transaction.on_commit(
                lambda: broadcast_to_users.delay(
                    send_to_all_users=True,
                    user_ids=[],
                    payload=user_data_registry.get_by_type(
                        ActiveLicensesDataType
                    ).realtime_message_to_disable_instancewide_license(license_type),
                )
            )
        license.delete()

    @classmethod
    def add_user_to_license(
        cls, requesting_user: User, license_object: License, user: User
    ) -> LicenseUser:
        """
        Adds a user to the provided license.

        :param requesting_user: The user on whose behalf the user is added to the
            license.
        :param license_object: The license that the user must be added to.
        :param user: The user that must be added to the license.
        :raises UserAlreadyInPremiumLicenseError: When the user already has a seat in
            the license.
        :raises NoSeatsLeftInLicenseError: When the license doesn't have any seats
            left.
        :return: The newly created license user object.
        """

        if not requesting_user.is_staff:
            raise IsNotAdminError()

        if LicenseUser.objects.filter(license=license_object, user=user).exists():
            raise UserAlreadyOnLicenseError(
                "The user already has a seat on this license."
            )

        if not license_object.license_type.seats_manually_assigned:
            raise CantManuallyChangeSeatsError()

        seats_taken = license_object.users.all().count()
        if seats_taken >= license_object.seats:
            raise NoSeatsLeftInLicenseError(
                "There aren't any seats left in the license."
            )

        al = user_data_registry.get_by_type(ActiveLicensesDataType)

        if license_object.is_active:
            transaction.on_commit(
                lambda: broadcast_to_users.delay(
                    [user.id],
                    al.realtime_message_to_enable_instancewide_license(
                        license_object.license_type
                    ),
                )
            )

        return LicenseUser.objects.create(license=license_object, user=user)

    @classmethod
    def remove_user_from_license(
        cls, requesting_user: User, license_object: License, user: User
    ):
        """
        Removes the provided user from the provided license if the user has a seat.

        :param requesting_user: The user on whose behalf the user is removed from the
            license.
        :param license_object: The license object where the user must be removed from.
        :param user: The user that must be removed from the license.
        """

        if not requesting_user.is_staff:
            raise IsNotAdminError()

        if not license_object.license_type.seats_manually_assigned:
            raise CantManuallyChangeSeatsError()

        LicenseUser.objects.filter(license=license_object, user=user).delete()

        al = user_data_registry.get_by_type(ActiveLicensesDataType)

        if license_object.is_active:
            transaction.on_commit(
                lambda: broadcast_to_users.delay(
                    [user.id],
                    al.realtime_message_to_disable_instancewide_license(
                        license_object.license_type
                    ),
                )
            )

    @classmethod
    def fill_remaining_seats_of_license(
        cls, requesting_user: User, license_object: License
    ) -> List[LicenseUser]:
        """
        Fills the remaining seats of the license with additional users.

        :param requesting_user: The user on whose behalf the request is made.
        :param license_object: The license object where the users must be added to.
        :return: A list of created license users.
        """

        if not requesting_user.is_staff:
            raise IsNotAdminError()

        if not license_object.license_type.seats_manually_assigned:
            raise CantManuallyChangeSeatsError()

        already_in_license = license_object.users.all().values_list(
            "user_id", flat=True
        )
        remaining_seats = license_object.seats - len(already_in_license)

        if remaining_seats > 0:
            users_to_add = User.objects.filter(~Q(id__in=already_in_license)).order_by(
                "id"
            )[:remaining_seats]
            user_licenses = [
                LicenseUser(license=license_object, user=user) for user in users_to_add
            ]
            LicenseUser.objects.bulk_create(user_licenses)

            if license_object.is_active:
                al = user_data_registry.get_by_type(ActiveLicensesDataType)

                transaction.on_commit(
                    lambda: broadcast_to_users.delay(
                        [user_license.user_id for user_license in user_licenses],
                        al.realtime_message_to_enable_instancewide_license(
                            license_object.license_type
                        ),
                    )
                )

            return user_licenses

        return []

    @classmethod
    def remove_all_users_from_license(
        cls, requesting_user: User, license_object: License
    ):
        """
        Removes all the users from a license. This will clear up all the seats.

        :param requesting_user: The user on whose behalf the users are removed.
        :param license_object: The license object where the users must be removed from.
        """

        if not requesting_user.is_staff:
            raise IsNotAdminError()

        if not license_object.license_type.seats_manually_assigned:
            raise CantManuallyChangeSeatsError()

        license_users = LicenseUser.objects.filter(license=license_object)
        license_user_ids = list(license_users.values_list("user_id", flat=True))
        license_users.delete()

        if license_object.is_active:
            al = user_data_registry.get_by_type(ActiveLicensesDataType)

            transaction.on_commit(
                lambda: broadcast_to_users.delay(
                    license_user_ids,
                    al.realtime_message_to_disable_instancewide_license(
                        license_object.license_type
                    ),
                )
            )
