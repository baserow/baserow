from django.dispatch import receiver

from baserow.contrib.builder.pages.last_viewed_types import (
    BuilderPageLastViewedItemType,
)
from baserow.contrib.builder.pages.signals import page_loaded
from baserow.core.last_viewed.handler import LastViewedHandler


@receiver(page_loaded)
def page_loaded_mark_last_viewed(sender, page, user, **kwargs):
    # The editor loads the shared page's elements on every builder visit, which
    # says nothing about what the user is looking at.
    if page.shared:
        return
    LastViewedHandler.schedule_mark_viewed(
        user, BuilderPageLastViewedItemType.type, page.id
    )
