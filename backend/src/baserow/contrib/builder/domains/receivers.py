from django.db.models.signals import pre_delete

from baserow.contrib.builder.domains.models import Domain


def before_domain_permanently_deleted(sender, instance, **kwargs):
    """
    Delete the published builder instance.
    """

    if instance.published_to:
        from baserow.contrib.builder.domains.handler import DomainHandler

        DomainHandler().delete_published_builder(instance.published_to)


def connect_to_domain_pre_delete_signal():
    pre_delete.connect(before_domain_permanently_deleted, Domain)
