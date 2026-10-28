import re
from datetime import timedelta

from django.db import models

USER_TEMPLATE_DESCRIPTION_MAX_LENGTH = 80

# The icons an author can pick are listed in `templateIcons.js` of the
# web-frontend. The backend only checks that an icon is an iconoir class that fits
# `Template.icon`, so that the list is kept in one place.
USER_TEMPLATE_ICON_MAX_LENGTH = 32
USER_TEMPLATE_ICON_REGEX = re.compile(r"iconoir-[a-z0-9]+(-[a-z0-9]+)*")

# How long a deleted user template is kept before it's removed permanently. It must
# be longer than a job can run, `BASEROW_JOB_SOFT_TIME_LIMIT` + 30 seconds, so that
# an install or an update that started before the deletion finishes first.
USER_TEMPLATE_DELETION_GRACE_PERIOD = timedelta(days=1)
# How many deleted user templates one run of the cleanup task removes at most, so
# that a backlog doesn't keep it from cleaning up the rest. The next run takes the
# next ones.
USER_TEMPLATE_PURGE_BATCH_SIZE = 20


class UserTemplateState(models.TextChoices):
    PRIVATE = "private", "Private"
    IN_REVIEW = "in_review", "In review"
    REJECTED = "rejected", "Rejected"
    BLOCKED = "blocked", "Blocked"
    PUBLIC = "public", "Public"


# The views mapping is created together with the mappings of its children, see
# `ViewType.import_serialized`, so they're seeded together too.
USER_TEMPLATE_SEEDED_ID_MAPPINGS = (
    "database_tables",
    "database_fields",
    "database_views",
    "database_view_filters",
    "database_view_filter_groups",
    "database_view_sortings",
    "database_view_group_bys",
    "database_view_decorations",
    "automation_workflows",
)
