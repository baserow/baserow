from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
)


class TwoFactorAuthProviderModel(
    CreatedAndUpdatedOnMixin, PolymorphicContentTypeMixin, WithRegistry, models.Model
):
    """
    Base model for two factor auth.
    """

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="two_factor_auth_providers",
        on_delete=models.CASCADE,
    )
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="two_factor_auth_provider",
        help_text="User that setup 2fa with this provider",
    )

    @staticmethod
    def get_type_registry():
        from baserow.core.two_factor_auth.registries import (
            two_factor_auth_type_registry,
        )

        return two_factor_auth_type_registry

    @property
    def is_enabled(self):
        return False


class TOTPAuthProviderModel(TwoFactorAuthProviderModel):
    enabled = models.BooleanField(default=False)
    secret = models.CharField(max_length=32, help_text="base32 secret")
    provisioning_url = models.CharField(max_length=255)
    provisioning_qr_code = models.TextField(blank=True)

    @property
    def backup_codes(self):
        return getattr(self, "_backup_codes", [])

    @property
    def is_enabled(self):
        return self.enabled


class TOTPUsedCode(models.Model):
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="totp_used_codes",
    )
    used_at = models.DateTimeField()
    code = models.CharField(max_length=64, help_text="Hash of the used code")

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "code"],
                name="totp_usedcode_user_code_idx",
            ),
        ]


class TwoFactorAuthRecoveryCode(models.Model):
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="two_factor_recovery_codes",
        help_text="User that setup 2fa with recovery codes",
    )
    code = models.CharField(
        max_length=64, help_text="SHA-256 hash of the recovery code"
    )
