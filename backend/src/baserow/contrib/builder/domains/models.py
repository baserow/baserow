from urllib.parse import urlparse

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CASCADE, SET_NULL

import validators
from rest_framework.exceptions import ValidationError

from baserow.contrib.builder.domains.registries import domain_type_registry
from baserow.core.jobs.mixins import JobWithUserIpAddress
from baserow.core.jobs.models import Job
from baserow.core.mixins import (
    HierarchicalModelMixin,
    OrderableMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)
from baserow.core.registry import ModelRegistryMixin


def validate_domain(value: str):
    """
    Checks if the domain name follows the correct syntax.

    Note: this should exist in a validators.py, but since the module this uses is called
    "validators" we run into an importing issue where the file tries to import itself.
    Therefor this validator function is declared locally in the models.py

    :param value: The domain name that's being checked
    :raises ValidationError: If the domain name is invalid
    """

    if isinstance(validators.domain(value), validators.utils.ValidationError):
        raise ValidationError("Invalid domain syntax")


def get_default_domain_content_type():
    return ContentType.objects.get_for_model(CustomDomain)


class Domain(
    HierarchicalModelMixin,
    TrashableModelMixin,
    OrderableMixin,
    WithRegistry,
    PolymorphicContentTypeMixin,
    models.Model,
):
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="builder_domains",
        on_delete=models.SET(get_default_domain_content_type),
    )
    builder = models.ForeignKey(
        "builder.Builder",
        on_delete=CASCADE,
        related_name="domains",
    )
    order = models.PositiveIntegerField()
    domain_name = models.CharField(
        max_length=255, unique=True, validators=[validate_domain]
    )
    last_published = models.DateTimeField(
        null=True,
        default=None,
        help_text="Last publication date of this domain",
    )
    published_to = models.OneToOneField(
        "builder.Builder",
        null=True,
        on_delete=SET_NULL,
        related_name="published_from",
        help_text="The published builder.",
    )

    def get_parent(self):
        return self.builder

    class Meta:
        ordering = ("order",)

    def get_public_url(self):
        """
        Returns the URL for this domain.
        """

        # Parse the PUBLIC_WEB_FRONTEND_URL to extract the scheme and port
        parsed_url = urlparse(settings.PUBLIC_WEB_FRONTEND_URL)
        port_string = f":{parsed_url.port}" if parsed_url.port else ""
        return f"{parsed_url.scheme}://{self.domain_name}{port_string}"

    @classmethod
    def get_last_order(cls, builder):
        queryset = Domain.objects.filter(builder=builder)
        return cls.get_highest_order_of_queryset(queryset) + 1

    @staticmethod
    def get_type_registry() -> ModelRegistryMixin:
        return domain_type_registry


class CustomDomain(Domain):
    pass


class SubDomain(Domain):
    pass


class PublishDomainJob(JobWithUserIpAddress, Job):
    domain: Domain = models.ForeignKey(Domain, null=True, on_delete=models.SET_NULL)
