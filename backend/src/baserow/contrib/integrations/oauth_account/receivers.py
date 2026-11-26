from django.conf import settings
from django.db.models import F, Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from baserow.core.integrations.registries import integration_type_registry
from baserow.core.registries import application_type_registry
from baserow.core.signals import before_workspace_user_deleted

from .models import OAuthAccountIntegrationMixin


def oauth_account_models() -> list[type[OAuthAccountIntegrationMixin]]:
    """
    :return: The model of every registered OAuth account integration type.
    """

    return [
        integration_type.model_class
        for integration_type in integration_type_registry.get_all()
        if issubclass(integration_type.model_class, OAuthAccountIntegrationMixin)
    ]


def _forget_tokens(model: type[OAuthAccountIntegrationMixin], queryset):
    # Querysets of `objects_and_trash`: an integration in the trash, or in a
    # trashed application, could be restored with the tokens otherwise.
    queryset.update(**model.get_cleared_token_values(), generation=F("generation") + 1)


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def forget_oauth_tokens_connected_by_deleted_user(sender, instance, **kwargs):
    """
    Integrations stop acting as an account once the Baserow user who connected
    it is deleted. The account is kept, so editors see whom to sign in as again.
    Runs before the deletion, while `connected_by` still points to the user.
    """

    for model in oauth_account_models():
        _forget_tokens(
            model, model.objects_and_trash.filter(connected_by_id=instance.id)
        )


@receiver(before_workspace_user_deleted)
def forget_oauth_tokens_connected_by_departing_member(
    sender, user, workspace, **kwargs
):
    """
    A member who leaves, or is removed from, a workspace stops being the account
    its applications act as, published copies included: those have no workspace
    of their own, so they're found through the application they were published
    from.
    """

    in_workspace = Q(application__workspace_id=workspace.id)
    for application_type in application_type_registry.get_all():
        in_workspace |= Q(
            application_id__in=application_type.get_published_applications(
                workspace
            ).values("pk")
        )
    for model in oauth_account_models():
        _forget_tokens(
            model,
            model.objects_and_trash.filter(in_workspace, connected_by_id=user.id),
        )
