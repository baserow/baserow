from django.db.models.signals import post_migrate

from .base import *  # noqa: F403, F401
from .utils import setup_dev_e2e

DEBUG = True


def sync_templates_only_for_e2e(sender, **kwargs):
    """
    Some tests work with templates, to keep things fast in the e2e CI job we only
    want to sync one template instead of all of them.
    """

    from django.conf import settings

    from baserow.core.handler import CoreHandler

    pattern = f"^({'|'.join(settings.DEFAULT_APPLICATION_TEMPLATES)})$"

    CoreHandler().sync_templates(pattern=pattern)


# Disable normal template syncing in CI as we will sync a single template ourselves
# instead.
BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION = False
post_migrate.connect(sync_templates_only_for_e2e)

# Don't bother waiting for the non-existent license authority
LICENSE_AUTHORITY_CHECK_TIMEOUT_SECONDS = 0.001

post_migrate.connect(setup_dev_e2e, dispatch_uid="setup_dev_e2e")
