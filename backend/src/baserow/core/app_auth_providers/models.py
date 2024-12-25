from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.auth_provider.models import BaseAuthProviderModel
from baserow.core.mixins import HierarchicalModelMixin
from baserow.core.user_sources.models import UserSource


class AppAuthProvider(BaseAuthProviderModel, HierarchicalModelMixin):
    """
    Base class for all auth provider used by applications.
    """

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="app_auth_providers",
        on_delete=models.CASCADE,
    )

    user_source = models.ForeignKey(
        UserSource,
        related_name="auth_providers",
        on_delete=models.CASCADE,
    )

    @classmethod
    def get_parent(cls):
        return UserSource

    @staticmethod
    def get_type_registry():
        from baserow.core.app_auth_providers.registries import (
            app_auth_provider_type_registry,
        )

        return app_auth_provider_type_registry

    class Meta:
        ordering = ["id"]
