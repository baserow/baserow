from django.db import models

from baserow.core.models import Application

__all__ = ["Whiteboard", "WhiteboardComment"]


class Whiteboard(Application):
    content = models.JSONField(default=dict, blank=True)

    def get_parent(self):
        return self.application_ptr


# ruff: noqa: E402
# Keep this import at the bottom — `comments.models` imports `Whiteboard`
# from this module, so circular imports are avoided. Re-exporting here is
# what makes Django's app loader see the comment model under the
# `whiteboard` app label.
from baserow.contrib.whiteboard.comments.models import WhiteboardComment  # noqa: F401
