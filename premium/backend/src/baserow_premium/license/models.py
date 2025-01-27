from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Type

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.functional import cached_property

from dateutil import parser

if TYPE_CHECKING:
    from baserow_premium.license.addons.registries import LicenseAddonType

User = get_user_model()


class License(models.Model):
    license = models.TextField()
    last_check = models.DateTimeField(null=True)
    cached_untrusted_instance_wide = models.BooleanField(default=False)
    """
    This property is purely set to make looking up instance wide licenses quicker.
    You must always explicitly check `license.is_instance_wide` per looked up license
    as we only trust the `.license` payload attribute and is_instance_wide will check
    using the payload.
    The `cached_untrusted_instance_wide` value might have been manipulated and is not
    signed and hence is untrusted on its own.
    """

    def save(self, *args, **kwargs):
        try:
            del self.payload
        except AttributeError:
            pass
        return super().save(*args, **kwargs)

    @cached_property
    def payload(self):
        from .handler import LicenseHandler

        possibly_encoded_license = self.license
        if isinstance(possibly_encoded_license, str):
            encoded_license = possibly_encoded_license.encode()
        else:
            encoded_license = possibly_encoded_license
        return LicenseHandler.decode_license(encoded_license)

    @property
    def license_id(self):
        return self.payload["id"]

    @property
    def valid_from(self):
        return parser.parse(self.payload["valid_from"]).replace(tzinfo=timezone.utc)

    @property
    def valid_through(self):
        return parser.parse(self.payload["valid_through"]).replace(tzinfo=timezone.utc)

    @property
    def is_active(self):
        """
        An active license is one which is valid right now and has valid cached
        properties which haven't been manipulated.
        """

        return (
            self.valid_from <= datetime.now(tz=timezone.utc) <= self.valid_through
            and self.valid_cached_properties
        )

    @property
    def valid_cached_properties(self):
        """
        Returns True if the cached properties on the license database row match the
        decoded properties from the signed license. If they don't match then manual
        changes have been made to the cached properties.
        """

        return self.cached_untrusted_instance_wide == self.license_type.instance_wide

    @property
    def product_code(self):
        return self.payload["product_code"]

    @property
    def seats(self):
        return self.payload["seats"]

    @property
    def addon_product_code(self) -> Optional[str]:
        # `addon_product_code` is only present >=v1.32
        return self.payload.get("addon_product_code")

    @property
    def application_users(self) -> Optional[int]:
        # `application_users` is only present >=v1.32
        return self.payload.get("application_users")

    @property
    def license_addon_type(self) -> Optional[Type["LicenseAddonType"]]:
        from baserow_premium.license.addons.registries import (
            license_addon_type_registry,
        )

        # `addon_product_code` is only present >=v1.32
        return (
            license_addon_type_registry.get(self.addon_product_code)
            if self.addon_product_code
            else None
        )

    @property
    def issued_on(self):
        return parser.parse(self.payload["issued_on"]).replace(tzinfo=timezone.utc)

    @property
    def issued_to_email(self):
        return self.payload["issued_to_email"]

    @property
    def issued_to_name(self):
        return self.payload["issued_to_name"]

    @property
    def license_type(self):
        from baserow_premium.license.registries import license_type_registry

        return license_type_registry.get(self.product_code)


class LicenseUser(models.Model):
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name="users")
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("license", "user")
