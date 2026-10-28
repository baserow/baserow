from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.builder.data_sources import signals as ds_signals
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.elements import signals as element_signals
from baserow.contrib.builder.handler import BuilderHandler
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages import signals as page_signals
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.workflow_actions import signals as wa_signals
from baserow.core import signals as core_signals
from baserow.core.user_sources import signals as us_signals

__all__ = [
    "element_created",
    "elements_created",
    "element_deleted",
    "element_updated",
    "wa_created",
    "wa_updated",
    "wa_deleted",
    "ds_created",
    "ds_updated",
    "ds_deleted",
    "page_deleted",
    "page_updated",
    "application_deleted",
    "workspace_deleted",
]

# Elements


@receiver(element_signals.element_created)
def element_created(sender, element, user, before_id=None, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(element.page.builder)


@receiver(element_signals.elements_created)
def elements_created(sender, elements, page, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(page.builder)


@receiver(element_signals.element_updated)
def element_updated(sender, element, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(element.page.builder)


@receiver(element_signals.element_deleted)
def element_deleted(sender, page, element_id, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(page.builder)


# Workflow actions


@receiver(wa_signals.workflow_action_created)
def wa_created(sender, workflow_action, user, before_id=None, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(
        workflow_action.page.builder
    )


@receiver(wa_signals.workflow_action_updated)
def wa_updated(sender, workflow_action, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(
        workflow_action.page.builder
    )


@receiver(wa_signals.workflow_action_deleted)
def wa_deleted(sender, workflow_action_id, page, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(page.builder)


# Data sources


@receiver(ds_signals.data_source_created)
def ds_created(sender, data_source, user, before_id=None, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(
        data_source.page.builder
    )


@receiver(ds_signals.data_source_updated)
def ds_updated(sender, data_source, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(
        data_source.page.builder
    )


@receiver(ds_signals.data_source_deleted)
def ds_deleted(sender, data_source_id, page, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(page.builder)


# Page


@receiver(page_signals.page_deleted)
def page_deleted(sender, builder, page_id, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(builder)
    transaction.on_commit(lambda: PageHandler.invalidate_page_public_cache(page_id))


@receiver(page_signals.page_updated)
def page_updated(sender, page, user, **kwargs):
    BuilderHandler().invalidate_builder_public_properties_cache(page.builder)


# User sources


@receiver(us_signals.user_source_created)
def us_created(sender, user_source, user, before_id=None, **kwargs):
    if isinstance(user_source.application.specific, Builder):
        BuilderHandler().invalidate_builder_public_properties_cache(
            user_source.application.specific
        )


@receiver(us_signals.user_source_updated)
def us_updated(sender, user_source, user, **kwargs):
    if isinstance(user_source.application.specific, Builder):
        BuilderHandler().invalidate_builder_public_properties_cache(
            user_source.application.specific
        )


@receiver(us_signals.user_source_deleted)
def us_deleted(sender, user_source_id, application, user, **kwargs):
    if isinstance(application.specific, Builder):
        BuilderHandler().invalidate_builder_public_properties_cache(
            application.specific
        )


# Applications and workspaces


@receiver(core_signals.application_deleted)
def application_deleted(sender, application_id, **kwargs):
    # A trashed builder stops being served on its domains.
    DomainHandler.invalidate_public_cache_on_commit(
        Domain.objects.filter(builder_id=application_id)
    )


@receiver(core_signals.workspace_deleted)
def workspace_deleted(sender, workspace_id, **kwargs):
    # The builders of a trashed workspace stop being served on their domains.
    DomainHandler.invalidate_public_cache_on_commit(
        Domain.objects.filter(builder__workspace_id=workspace_id)
    )
