from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from baserow.core.auth_provider.models import AuthProviderModel


class SamlAuthProviderModelMixin(models.Model):
    metadata = models.TextField(
        blank=True, help_text="The XML metadata downloaded from the metadata_url."
    )
    is_verified = models.BooleanField(
        default=False,
        help_text=(
            "This will be set to True only after a user successfully login with this IdP. "
            "This must be True to disable normal username/password login and "
            "make SAML the only authentication provider. "
        ),
    )
    email_attr_key = models.CharField(
        max_length=32,
        default="user.email",
        db_default="user.email",
        help_text=(
            "The key in the SAML response that contains the email address of the user. "
            "If this is not set, the email will be taken from the user's profile."
        ),
    )
    first_name_attr_key = models.CharField(
        max_length=32,
        default="user.first_name",
        db_default="user.first_name",
        help_text=(
            "The key in the SAML response that contains the first name of the user. "
            "If this is not set, the first name will be taken from the user's profile."
        ),
    )
    last_name_attr_key = models.CharField(
        max_length=32,
        default="user.last_name",
        db_default="user.last_name",
        blank=True,
        help_text=(
            "The key in the SAML response that contains the last name of the user. "
            "If this is not set, the last name will be taken from the user's profile."
        ),
    )

    class Meta:
        abstract = True


class SamlAuthProviderModel(SamlAuthProviderModelMixin, AuthProviderModel):
    # Restore ordering
    class Meta(AuthProviderModel.Meta):
        ordering = ["domain"]


@receiver(pre_save, sender=SamlAuthProviderModel)
def reset_is_verified_if_metadata_changed(sender, instance, **kwargs):
    """
    When the metadata is changed, we want to reset the is_verified flag to False. This
    will force the user to login again with the IdP to verify that the metadata is still
    valid.
    """

    if instance.pk:
        original = sender.objects.get(pk=instance.pk)
        if original.metadata != instance.metadata:
            instance.is_verified = False
